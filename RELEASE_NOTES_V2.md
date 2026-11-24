# Data Pilot — Consolidated V2 Release

This release combines the strongest parts of V1 and Production Hardened. It is intended to replace both as the main development version.

## Retained from V1
- Automatic dataset profiling immediately after file selection.
- Detected-column list and explicit target-column/problem-type controls.
- Editorial information modal and its navigation entry points.
- Expanded regression tests for EDA/statistics, explainability/artifacts, pipeline fixes, benchmark datasets, and reporting/research.
- Safe structured API exception responses.
- Binary numeric target handling and continuous numeric target regression defaults.
- Autonomous replanning stage represented and allowed in the security plan.

## Retained from Production Hardened
- Server-side LLM provider abstraction and OpenAI Responses API / compatible Chat Completions support.
- Deterministic report fallback; LLM narrative cannot overwrite computed metrics.
- Leakage-safe preprocessing and cross-validation.
- Background analysis jobs, SQLite WAL persistence, model artifact storage and prediction endpoint.
- PDF export, report regeneration, optional MLflow/XGBoost/MCP integrations.
- Restricted default CORS origins and trusted hosts, explicit allowed headers, and a 25 MB default upload limit.
- Pinned core backend dependencies and deployment/security documentation.

## Important deployment note
This is a hardened single-node academic/demo release, not a public multi-tenant SaaS deployment. Public deployment still requires authentication, tenant isolation, rate limiting, durable distributed workers, managed database/object storage, monitoring, and backups. Configure allowed CORS origins and hosts for the actual deployment domain. Keep all API keys in the backend environment only.

## Verification
The backend test suite is run with `python -m unittest discover -s tests -v` from `backend/`. Run `npm ci` and `npm run build` from `frontend/` before deployment.
