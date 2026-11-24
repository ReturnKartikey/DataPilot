# Data Pilot V3 testing

## Backend regression and extension tests

```powershell
cd backend
$env:PYTHONPATH = "."
python -m pytest -q
```

The suite covers the inherited V2 pipeline/security/API behavior plus V3 research retrieval, statistical extensions, PyTorch MLP smoke tests, orchestration fallback metadata and the new research/tool APIs.

## Optional integration validation

After installing the optional packages, validate each feature on the target machine:

- LangGraph: run a full sample analysis and confirm `result.orchestration.framework == "LangGraph"` (not `python_fallback`).
- DuckDB: set `DATAPILOT_DATA_ENGINE=duckdb` and call `POST /api/data-engine/profile`.
- PyTorch: set `DATAPILOT_ENABLE_DEEP_LEARNING=true` and run classification and regression samples.
- MLflow: set `DATAPILOT_ENABLE_MLFLOW=true`, run an analysis and verify the returned run ID in the configured tracking store.
- MCP: run `python mcp_server.py` from `backend/` with an MCP client connected over stdio.
- PDF RAG: upload a text-based PDF to `POST /api/research/index-pdf`.
- Embeddings: set `DATAPILOT_ENABLE_RESEARCH_EMBEDDINGS=true`, install Sentence Transformers and index/query a source.

## Frontend

```powershell
cd frontend
npm ci
npm run build
```

The current build environment did not have the local Vite installation and could not access the package registry. JSX syntax was checked independently; a Vite production build still needs to be run locally.

## Docker

```bash
docker compose up --build
```

Docker build/runtime was not validated in the current environment. Review `.env.example`, persistent volume configuration and `DEPLOYMENT.md` before deployment.
