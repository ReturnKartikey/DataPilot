"""Vendor-neutral LLM client for report narratives.

Uses OpenAI Responses API for the official OpenAI endpoint and an
OpenAI-compatible Chat Completions API for other configured endpoints. The LLM
only interprets verified facts; deterministic metrics remain authoritative.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class LLMConfigurationError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None, timeout: int | None = None):
        provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
        self.api_key = api_key or (
            os.getenv("GEMINI_API_KEY") if provider == "gemini"
            else (os.getenv("OPENROUTER_API_KEY") if provider == "openrouter"
                  else (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")))
        )
        default_base_url = "https://openrouter.ai/api/v1" if provider == "openrouter" else "https://api.openai.com/v1"
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or default_base_url).rstrip("/")
        self.model = model or os.getenv(
            "LLM_MODEL",
            "gemini-2.0-flash" if provider == "gemini"
            else ("openai/gpt-4o-mini" if provider == "openrouter" else "gpt-4o-mini"),
        )
        self.timeout = timeout or int(os.getenv("LLM_TIMEOUT_SECONDS", "35"))
        default_mode = "responses" if self.base_url.startswith("https://api.openai.com") else "chat_completions"
        self.api_mode = os.getenv("LLM_API_MODE", default_mode).lower()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _schema() -> dict[str, Any]:
        keys = ["executive_interpretation", "key_findings", "recommendations", "caveats"]
        return {
            "type": "object",
            "properties": {key: {"type": "array", "items": {"type": "string"}} for key in keys},
            "required": keys,
            "additionalProperties": False,
        }

    def generate_json(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise LLMConfigurationError("No API key configured for the selected LLM provider")
        schema = self._schema()
        provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
        use_schema = os.getenv("LLM_RESPONSE_FORMAT", "json_schema").lower() == "json_schema"
        if provider == "gemini":
            # Gemini native generateContent adapter. The same verified-facts
            # contract is used for report narratives.
            prompt = system_prompt + "\nReturn JSON only matching this schema: " + json.dumps(schema)
            payload = {"contents": [{"parts": [{"text": prompt + "\nVerified facts: " + json.dumps(user_payload, ensure_ascii=False, default=str)}]}],
                       "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            request = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"),
                                             headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                content = raw["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise ValueError("LLM response must be a JSON object")
                return parsed
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"Gemini provider returned HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                raise RuntimeError("Gemini provider request failed or timed out") from exc
            except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
                raise RuntimeError("Gemini provider returned an invalid structured response") from exc
        if self.api_mode == "responses":
            body: dict[str, Any] = {
                "model": self.model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user_payload, ensure_ascii=False, default=str)}]},
                ],
            }
            if use_schema:
                body["text"] = {"format": {"type": "json_schema", "name": "datapilot_report_narrative", "strict": True, "schema": schema}}
            else:
                body["text"] = {"format": {"type": "json_object"}}
            endpoint = f"{self.base_url}/responses"
        elif self.api_mode == "chat_completions":
            response_format: dict[str, Any] = {"type": "json_object"}
            if use_schema:
                response_format = {"type": "json_schema", "json_schema": {"name": "datapilot_report_narrative", "strict": True, "schema": schema}}
            body = {
                "model": self.model,
                "temperature": 0.2,
                "response_format": response_format,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, default=str)},
                ],
            }
            endpoint = f"{self.base_url}/chat/completions"
        else:
            raise LLMConfigurationError("LLM_API_MODE must be 'responses' or 'chat_completions'")

        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                **({"HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173"),
                    "X-Title": os.getenv("OPENROUTER_APP_NAME", "Data Pilot")}
                   if os.getenv("LLM_PROVIDER", "openrouter").lower() == "openrouter" else {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
            if self.api_mode == "responses":
                content = raw.get("output_text")
                if not content:
                    chunks = []
                    for item in raw.get("output", []):
                        for part in item.get("content", []):
                            if part.get("type") in {"output_text", "text"}:
                                chunks.append(part.get("text", ""))
                    content = "".join(chunks)
            else:
                content = raw["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("LLM response must be a JSON object")
            return parsed
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"LLM provider returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError("LLM provider request failed or timed out") from exc
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError("LLM provider returned an invalid structured response") from exc
