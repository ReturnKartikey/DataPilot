# Data Pilot V4 implementation notes

V4 is an incremental upgrade of the V3 archive, not a rewrite.

## Added in this build
- `/api/v4/analytics/query`: upload/select a dataset and ask a natural-language analytics question.
- Intent routing supports OpenAI and Gemini provider configuration, with conservative deterministic fallback.
- Structured plan fields are restricted to actual dataset columns before execution.
- Deterministic descriptive, diagnostic and bounded prescriptive analysis engines.
- Predictive intent delegates to the existing supervised ML pipeline when a target is supplied.
- New React Analytics Studio page.
- Analysis results modal widened and its horizontal tab strip now prevents flex shrinking/cropped labels.
- Agent trace rows and responsive layouts improved.
- V4 analytics tests added.

## Configuration
Set in `backend/.env`:
- `LLM_PROVIDER=openai` or `LLM_PROVIDER=gemini`
- OpenAI: `LLM_API_KEY=...`, optional `LLM_MODEL=gpt-4o-mini`
- Gemini: `GEMINI_API_KEY=...`, optional `LLM_MODEL=gemini-2.0-flash`
- Keep secrets server-side. Never put API keys in the React app.

## Important capability boundaries
- Without an API key, intent routing uses conservative keyword fallback; it is not equivalent to LLM understanding.
- Descriptive and diagnostic calculations are deterministic. Diagnostic outputs identify associations and group differences, not causal proof.
- Prescriptive currently provides ranked historical scenario options and clearly states that it is not causal optimization. Full constrained optimization, costs, budgets and response models remain a next implementation stage.
- Predictive requests use the existing supervised pipeline and require a valid target. Dedicated time-series forecasting is not yet implemented.
- LangGraph V3 graph remains the existing lifecycle graph; V4 analytics query currently runs through its dedicated endpoint. Converting each specialist and analytics branch into separate LangGraph nodes remains a follow-on integration.
- DuckDB V3 adaptive profiling remains in place; V4 analytical query engine currently uses Pandas. SQL pushdown and larger-data query execution remain follow-on work.
- PyTorch V3 tabular MLP remains optional and integrated into the existing ML candidate pipeline. It has not been expanded into CNN/RNN/image or sequence models.

## Validation
- Python syntax compilation and deterministic analytics smoke tests were run during packaging.
- Full pytest suite, frontend production build, live OpenAI/Gemini API calls, LangGraph/DuckDB optional runtime, and Docker build must be run in the target environment before describing V4 as fully validated.


## Default LLM provider update (OpenRouter)

The V4 default provider is now OpenRouter. Configure `OPENROUTER_API_KEY` in `backend/.env`, with `LLM_PROVIDER=openrouter`, `LLM_BASE_URL=https://openrouter.ai/api/v1`, `LLM_API_MODE=chat_completions`, and a model ID such as `openai/gpt-4o-mini`. Both constrained analytics intent routing and optional report narratives use this server-side configuration. The API key is never exposed to the React client.
