# Data Pilot V4 — Release Notes

## New
- V4 Analytics Studio page in React.
- `/api/v4/analytics/query` natural-language analytics endpoint.
- OpenAI and Gemini intent-routing adapters, with deterministic fallback.
- Explicit V4 LangGraph analytics subgraph with intent, validation, conditional analytics branch and finalization nodes (sequential fallback when LangGraph is unavailable).
- Deterministic descriptive and diagnostic analysis.
- Predictive requests delegate to the existing supervised ML pipeline.
- Prescriptive historical option ranking with explicit non-causal limitations.
- Evidence-first Gemini/OpenAI report narrative provider support.
- Added V4 analytics unit tests.

## Frontend fixes
- Analysis modal widened.
- Horizontal stage tabs no longer shrink; labels remain full-width and scroll horizontally.
- Agent trace rows have wider columns, wrapping and mobile stacking.
- Added Analytics Studio navigation and query/results page.

## Validation in packaging environment
- Python compilation: passed.
- Backend pytest: 78 passed, 2 warnings.
- V4 API smoke test: HTTP 200 on the bundled churn sample.
- Frontend production build: not run because `node_modules` is not installed.
- Live OpenAI/Gemini calls: not run; no API credentials supplied.
- Optional LangGraph/DuckDB runtime availability depends on installed backend requirements.

## Known V4 scope boundaries
- Prescriptive engine is currently ranked historical options, not full constrained optimization.
- Dedicated time-series forecasting is not implemented yet.
- DuckDB adaptive profiling from V3 is retained, but V4 query operations currently execute through Pandas.
- Existing PyTorch tabular MLP remains optional; no CNN/RNN/image model family added.
- V4 analytics subgraph is separate from the existing end-to-end ML graph; unifying all analytics and ML branches into one persistent supervisor graph remains future integration work.
- API keys are configured server-side in `backend/.env`; no browser-side key storage.
