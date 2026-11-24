# Data Pilot V3 API quick reference

Base URL: `http://127.0.0.1:8000`

## Health and samples

- `GET /api/health` — API version, LangGraph availability, feature flags, agent names and research index status.
- `GET /api/samples` — bundled datasets and previews.
- `POST /api/profile` — multipart dataset/sample profiling.
- `POST /api/data-engine/profile` — SQL/Pandas engine profile for a bundled sample.

## Analysis and experiments

- `POST /api/analysis/start` — multipart upload/sample + inquiry; returns a job ID.
- `GET /api/analysis/{job_id}` — poll queued/running/completed/failed status.
- `POST /api/analyze` — synchronous compatibility endpoint.
- `GET /api/history` — saved experiment list.
- `GET /api/history/{experiment_id}` — saved result.
- `GET /api/history/{experiment_id}/agents` — graph events and specialist outcome trace.
- `POST /api/history/{experiment_id}/report/regenerate` — regenerate report narrative.
- `GET /api/history/{experiment_id}/report.pdf` — PDF report.
- `POST /api/models/{artifact_id}/predict` — multipart prediction input for a locally generated trusted model bundle.

## Research

- `GET /api/research/status` — indexed document/chunk counts and active retriever.
- `POST /api/research/index` — JSON `{ "title": "...", "text": "...", "source": "...", "doi": "..." }`.
- `POST /api/research/index-pdf` — multipart `file` PDF, optional `title` and `doi`; requires PyMuPDF.
- `POST /api/research/query` — JSON `{ "query": "...", "top_k": 4 }`; returns ranked evidence excerpts and metadata, not an unsupported generated answer.

## Tools and integrations

- `GET /api/tools` — allowlisted REST tool catalogue.
- `POST /api/tools/call` — JSON `{ "name": "research.search", "arguments": { "query": "...", "top_k": 4 } }`.
- `POST /api/security/self-test` — Security Guardian adversarial self-test.
- MCP stdio transport is provided separately by `backend/mcp_server.py`; REST tool calls are not MCP transport.

See the OpenAPI schema at `/openapi.json` when running in development mode.
