import json
import os
import unittest
from unittest.mock import patch

from data_pilot.llm_provider import OpenAICompatibleProvider


class FakeHTTPResponse:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self.payload).encode("utf-8")


class LLMProviderTests(unittest.TestCase):
    def setUp(self):
        self.old_mode = os.environ.pop("LLM_API_MODE", None)
        self.old_format = os.environ.get("LLM_RESPONSE_FORMAT")
        os.environ["LLM_RESPONSE_FORMAT"] = "json_schema"

    def tearDown(self):
        if self.old_mode is not None: os.environ["LLM_API_MODE"] = self.old_mode
        else: os.environ.pop("LLM_API_MODE", None)
        if self.old_format is None: os.environ.pop("LLM_RESPONSE_FORMAT", None)
        else: os.environ["LLM_RESPONSE_FORMAT"] = self.old_format

    def test_openai_uses_responses_api_and_strict_schema(self):
        content = {"executive_interpretation": [], "key_findings": [], "recommendations": [], "caveats": []}
        fake = FakeHTTPResponse({"output_text": json.dumps(content)})
        with patch("urllib.request.urlopen", return_value=fake) as call:
            provider = OpenAICompatibleProvider(api_key="test", base_url="https://api.openai.com/v1")
            result = provider.generate_json("Return JSON", {"rows": 10})
        request = call.call_args.args[0]
        body = json.loads(request.data)
        self.assertTrue(request.full_url.endswith("/responses"))
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertEqual(result, content)


    def test_openrouter_uses_chat_completions_and_server_key(self):
        content = {"executive_interpretation": [], "key_findings": [], "recommendations": [], "caveats": []}
        fake = FakeHTTPResponse({"choices": [{"message": {"content": json.dumps(content)}}]})
        env = {
            "LLM_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "openrouter-test-key",
            "LLM_BASE_URL": "https://openrouter.ai/api/v1",
            "LLM_API_MODE": "chat_completions",
            "LLM_RESPONSE_FORMAT": "json_object",
        }
        with patch.dict(os.environ, env, clear=False), patch("urllib.request.urlopen", return_value=fake) as call:
            provider = OpenAICompatibleProvider()
            result = provider.generate_json("Return JSON", {"rows": 10})
        request = call.call_args.args[0]
        body = json.loads(request.data)
        self.assertTrue(request.full_url.endswith("/chat/completions"))
        self.assertEqual(request.get_header("Authorization"), "Bearer openrouter-test-key")
        self.assertEqual(request.get_header("X-title"), "Data Pilot")
        self.assertEqual(body["response_format"]["type"], "json_object")
        self.assertEqual(result, content)

    def test_compatible_provider_uses_chat_completions(self):
        content = {"executive_interpretation": [], "key_findings": [], "recommendations": [], "caveats": []}
        fake = FakeHTTPResponse({"choices": [{"message": {"content": json.dumps(content)}}]})
        with patch("urllib.request.urlopen", return_value=fake) as call:
            provider = OpenAICompatibleProvider(api_key="test", base_url="https://example.invalid/v1")
            result = provider.generate_json("Return JSON", {"rows": 10})
        request = call.call_args.args[0]
        body = json.loads(request.data)
        self.assertTrue(request.full_url.endswith("/chat/completions"))
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertEqual(result, content)


if __name__ == "__main__":
    unittest.main()
