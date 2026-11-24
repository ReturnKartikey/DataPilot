# V3 change summary

V3 builds on the V2 consolidated source tree.

- `backend/data_pilot/orchestration/` — LangGraph state and graph lifecycle with explicit sequential fallback.
- `backend/data_pilot/data_engine/` — adaptive Pandas/DuckDB selection and profiling.
- `backend/data_pilot/deep_learning/` — optional PyTorch tabular MLP estimator classes.
- `backend/data_pilot/research/rag.py` — chunk store, TF-IDF retrieval, optional semantic embeddings and PDF extraction.
- `backend/data_pilot/agents/statistics.py` — additional assumption-aware multiclass statistical tests.
- `backend/data_pilot/agents/research.py` and `agents/reporting.py` — indexed research evidence context in analysis/report output.
- `backend/data_pilot/tracking.py` — expanded MLflow metadata/metrics artifact logging.
- `backend/data_pilot/tool_registry.py` and `backend/mcp_server.py` — expanded allowlisted REST and MCP tools.
- `backend/app.py` — health/capability metadata, research APIs, data-engine API and saved agent trace API.
- `frontend/src/App.jsx`, `frontend/src/App.css` — multi-section product shell and agent/research views; existing `DataPilot.jsx` analysis workspace retained.
- `backend/tests/test_v3_extensions.py` — tests for new V3 capabilities.
- `README.md`, `ARCHITECTURE.md`, `API.md`, `TESTING.md`, `IMPLEMENTATION_STATUS.md`, `RELEASE_NOTES_V3.md` — V3 docs and validation boundaries.

Runtime-generated artifacts, local SQLite databases, environment secrets, caches and dependency folders are excluded from the release archive.


## V4.3 additions

- `backend/data_pilot/jobs.py`: persisted per-stage execution progress.
- `backend/data_pilot/pipeline.py` and `backend/data_pilot/orchestration/graph.py`: stage telemetry, descriptive ranking fast path, dataset-domain research context, and adaptive CV cutoff.
- `backend/data_pilot/agents/research.py`: dataset-oriented OpenAlex query with Crossref fallback.
- `backend/data_pilot/llm/intent.py`: provider-aware OpenRouter default base URL and actionable sanitized HTTP diagnostics.
- `backend/app.py`: persists pipeline progress in background jobs.
- `frontend/src/api.js`, `frontend/src/DataPilot.jsx`: backend-driven progress, measured stage percentage, ETA estimate, and gentler polling.
- `frontend/src/pages/AnalyticsStudio.jsx`: remove uploaded dataset control and LLM configuration status.
- `frontend/src/App.jsx`: live experiment history progress display.
- `backend/tests/test_v4_3_execution_intelligence.py`: regression tests for progress, research query relevance, and descriptive routing.
