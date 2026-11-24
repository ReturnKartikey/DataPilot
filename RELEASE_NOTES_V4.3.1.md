# Data Pilot V4.3.1 — OpenRouter JSON-mode fix

## Fixed
- Added an explicit JSON-only instruction to the OpenRouter/OpenAI-compatible intent-router messages.
- Added a regression test asserting that the request contains the literal `JSON` instruction whenever `response_format=json_object` is sent.
- Preserved structured output validation and the existing conservative fallback for genuine provider/network failures.

## Why
OpenRouter rejects `response_format: {"type":"json_object"}` unless at least one message contains the word `json`. The previous intent prompt omitted that literal requirement, causing HTTP 400 and deterministic fallback despite a valid API key.
