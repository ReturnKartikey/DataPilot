import json
import os
import unittest
from unittest.mock import patch
from data_pilot.llm import intent


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "analytics_type": "descriptive",
                        "target": "price",
                        "column": "price",
                        "group_by": None,
                        "problem_type": "unknown",
                        "objective": "maximize",
                        "limit": 10
                    })
                }
            }]
        }).encode("utf-8")


class OpenRouterJsonModeTests(unittest.TestCase):
    def test_json_instruction_is_present_when_json_object_requested(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return _FakeResponse()

        env = {
            "LLM_PROVIDER": "openrouter",
            "LLM_BASE_URL": "https://openrouter.ai/api/v1",
            "LLM_RESPONSE_FORMAT": "json_object",
            "LLM_INTENT_TIMEOUT_SECONDS": "12",
        }
        with patch.dict(os.environ, env, clear=False), \
             patch.object(intent.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = intent._call_openai(
                "test-key", "openai/gpt-4o-mini",
                "top factor influencing house price",
                ["price", "area", "bedrooms"]
            )

        self.assertEqual(result["analytics_type"], "descriptive")
        messages = captured["body"]["messages"]
        all_text = " ".join(message["content"] for message in messages).lower()
        self.assertIn("json", all_text)
        self.assertEqual(captured["body"]["response_format"]["type"], "json_object")


if __name__ == "__main__":
    unittest.main()
