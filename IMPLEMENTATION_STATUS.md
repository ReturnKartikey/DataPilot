# Data Pilot V3 implementation status

This document distinguishes code present in the repository from capabilities actually validated in the current build environment.

## Implemented in source

| Area | V3 implementation |
|---|---|
| Existing ML pipeline | Preserved from V2: profiling, planning, security, EDA, preprocessing, supervised ML, evaluation, critic, bounded retry, explainability, reporting and inference |
| LangGraph | `StateGraph` lifecycle in `backend/data_pilot/orchestration/graph.py`; conditional route, execution node, finalization and in-memory checkpointer |
| Fallback | Explicitly labelled sequential fallback when LangGraph is unavailable |
| Agent trace | Saved per-experiment agent outcome summary and graph events; API endpoint added |
| DuckDB | Adaptive engine selector; SQL-based row/null/numeric profiling; Pandas fallback |
| PyTorch | Optional tabular MLP classifier and regressor integrated as additional model candidates behind feature flag |
| Statistics | Welch t-test, Mann–Whitney U, multiclass ANOVA, Kruskal-Wallis and chi-square association tests with assumption notes |
| Research RAG | SQLite-backed chunk store, local TF-IDF retrieval, source excerpts/DOI metadata, optional Sentence Transformers embeddings |
| PDF ingestion | Optional PyMuPDF text extraction endpoint |
| Crossref | Existing optional bibliographic metadata lookup retained; no claim of full-text summary |
| MLflow | Expanded params, numeric metrics and compact JSON artifact logging |
| MCP | Expanded stdio server tools and allowlisted REST tool adapter |
| Frontend | Multi-section React workspace: Overview, Workspace, Datasets, Experiments, Agent graph, Research, Integrations and Settings |
| Packaging | Runtime artifacts and local state excluded from source release |

## Validation performed in the current build environment

- Python compilation: passed.
- Backend test suite: **73 passed** (includes 65 inherited V2 tests and 8 V3 extension tests).
- Sample customer-churn pipeline: completed successfully in sequential fallback mode; produced model results, 11 agent trace entries and a report.
- PyTorch MLP classifier/regressor smoke tests: passed on CPU.
- Research RAG indexing/retrieval tests: passed using TF-IDF.
- Multiclass statistical tests: passed.
- LangGraph and DuckDB: packages were not installed in this build environment. Package installation was attempted but the environment could not reach the Python package registry. Their source integrations and requirements are included, but actual runtime execution is not validated here.
- MCP stdio server: not runtime-tested because the optional MCP SDK is not installed here.
- PyMuPDF and Sentence Transformers paths: not runtime-tested because optional dependencies are not installed.
- Frontend production build and Docker build: not validated in this environment; run the commands in README on a machine with Node dependencies and package registry access.
- MLflow: source integration present, not runtime-tested because MLflow is optional and unavailable here.

## Known architectural boundaries

1. The LangGraph graph controls validation, conditional execution and finalization. The specialist agent pipeline is still called as one execution node; each specialist is not yet an independent LangGraph node.
2. Agent trace is a persisted post-run outcome summary, not a live streaming per-agent event bus.
3. The data engine profiles in-memory DataFrames. It does not yet stream large CSVs directly from disk or replace Pandas across all modelling operations.
4. RAG retrieves only text explicitly indexed by the user. PDF extraction requires PyMuPDF. Semantic embeddings require Sentence Transformers and optional model download. No automatic paywalled paper download is implemented.
5. PyTorch supports tabular MLPs only; no CNN, RNN, image, or time-series workflow is included.
6. The application remains single-node/local-first without authentication, tenant isolation, distributed queue, or managed cloud persistence.

## Release recommendation

Use this as a V3 academic development release after installing base requirements and running the complete local validation checklist. Do not describe optional components as validated until their optional packages have been installed and their integration tests have been run on the target machine.
