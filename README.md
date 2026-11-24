# Data Pilot V4 — Autonomous Data Science Platform

> **Current release: V4.5.0 — Question-first Workspace & report answers.** See [RELEASE_NOTES_V4.5.md](RELEASE_NOTES_V4.5.md) for Workspace navigation cleanup, question-first intent handling, direct question answers in reports, and expanded EDA interpretation.


Data Pilot is a local-first, agent-based tabular data-science platform. V3 preserves the V2 modelling pipeline and adds a LangGraph-controlled lifecycle, optional PyTorch tabular MLPs, adaptive DuckDB/Pandas execution, local research retrieval, expanded MCP tools, MLflow metadata tracking, multiclass statistical tests and a multi-section React workspace.

> **Release classification:** academic/demo single-node release. It is not a multi-tenant production SaaS. Authentication, tenant isolation, durable distributed jobs, managed storage, deployment monitoring and operational backups remain deployment work.

## V3 capabilities

- Upload CSV, XLS/XLSX and JSON datasets or use bundled examples.
- Profile data, identify targets, inspect distributions, correlations, missingness, outliers and descriptive statistics.
- Generate a deterministic plan and pass it through the Security Guardian before execution.
- Run leakage-aware preprocessing, classification/regression baselines, holdout evaluation and cross-validation.
- Critic quality checks and bounded, security-rechecked replanning.
- Optional PyTorch MLP classifier/regressor; disabled by default and CPU-capable.
- SHAP/native explainability and deterministic reports with optional server-side LLM narrative.
- LangGraph `StateGraph` lifecycle orchestration when dependencies are installed. An explicitly labelled sequential compatibility fallback keeps the app usable in offline environments.
- DuckDB SQL profiling for larger frames, with Pandas fallback/selection.
- Research library: index user-provided text or PDFs, chunk sources, retrieve passages using TF-IDF by default, and optionally use Sentence Transformers embeddings. Retrieval returns excerpts and source metadata; it does not invent answers or citations.
- Optional Crossref bibliographic metadata lookup.
- Optional MLflow metrics and compact analysis metadata artifact logging.
- MCP stdio server with allowlisted sample analysis, profiling, EDA, research retrieval, report and capability tools.
- Multi-section React interface: Overview, Workspace, Datasets, Experiments, Agent graph, Integrations and Settings.

## Agent architecture and honesty about autonomy

The agents are real Python components with distinct responsibilities. Planner, Security Guardian, EDA, Statistics, Preprocessing, ML, Critic, Replanner, Explainability, Research and Reporting are not all LLM agents. The Planner and quality/security checks are deterministic. Selected research/report tasks can use external metadata or an optional LLM provider.

LangGraph is used by `backend/data_pilot/orchestration/graph.py` to manage request validation, conditional routing, execution and finalization with a `StateGraph` and per-invocation in-memory checkpointer. The existing specialist pipeline is currently invoked by the graph's execution node; specialist agent logic remains in independently testable Python modules. It is therefore accurate to call this a **LangGraph-orchestrated agent pipeline**, not a swarm of independently reasoning LLMs. Persistent multi-worker checkpointing and fully separate graph nodes for every specialist are future hardening work.

Agent outcomes and graph events are saved with each experiment and exposed through `GET /api/history/{experiment_id}/agents`. The UI's Agent graph is an architecture view; saved execution trace is the record of what ran for a particular experiment.

## Architecture

```text
React + Vite multi-section workspace
              │ REST
              ▼
           FastAPI
              │
              ▼
       LangGraph StateGraph
       ├── Input validation
       ├── Conditional execution
       └── Finalization + checkpoint
              │
              ▼
     Specialist Python pipeline
     ├── Profiler → Planner → Security Guardian
     ├── EDA + Statistical Analysis
     ├── Preprocessing → ML Runner
     ├── Critic → bounded Replanner
     ├── Explainability
     ├── Research Agent → local RAG / Crossref
     └── Reporting Agent → optional LLM narrative
              │
       ┌──────┼─────────┬─────────┐
       ▼      ▼         ▼         ▼
     SQLite  Artifacts  MLflow   MCP stdio server
              │
        Pandas / DuckDB
        sklearn / PyTorch
```

## Requirements

- Python 3.11 or 3.12 recommended.
- Node.js 20+ recommended.
- Base install uses FastAPI, Pandas, scikit-learn, SciPy, LangGraph and DuckDB.
- Optional install includes XGBoost, MLflow, MCP SDK, PyTorch, Sentence Transformers and PyMuPDF.

## Windows setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
# Install only the optional components you plan to use:
# pip install -r requirements-mcp.txt
# pip install -r requirements-deep-learning.txt
# pip install -r requirements-research.txt
# pip install -r requirements-tracking.txt
cd ..\frontend
npm ci
cd ..
```

If you do not need deep learning, you may skip installing the optional PyTorch wheel. For a CUDA-enabled machine, install the PyTorch build appropriate to that machine rather than assuming the generic CPU/GPU wheel is correct.

Copy `backend/.env.example` to `backend/.env`. Add your OpenRouter key to `OPENROUTER_API_KEY` in that backend file. The key is read only by Python and must never be placed in frontend code or a `VITE_` variable. Create a key at https://openrouter.ai/keys. The default model is `openai/gpt-4o-mini`; update `LLM_MODEL` to another model ID listed at https://openrouter.ai/models if preferred. Model pricing and free-tier availability vary, so check the model listing before running paid requests.

Then launch:

```powershell
.\start.bat
```

- Frontend: http://localhost:5173
- API: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

## Optional configuration

```dotenv
# Adaptive data engine
DATAPILOT_DATA_ENGINE=auto
DATAPILOT_DUCKDB_THRESHOLD_MB=100

# Optional PyTorch MLP candidate
DATAPILOT_ENABLE_DEEP_LEARNING=false
DATAPILOT_MLP_EPOCHS=80

# Optional MLflow
DATAPILOT_ENABLE_MLFLOW=false
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
MLFLOW_EXPERIMENT_NAME=DataPilot

# Research retrieval
DATAPILOT_RESEARCH_DB=research_knowledge.sqlite3
DATAPILOT_ENABLE_RESEARCH_EMBEDDINGS=false
DATAPILOT_RESEARCH_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
DATAPILOT_ENABLE_LIVE_RESEARCH=false

# OpenRouter LLM (server-side only)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_MODE=chat_completions
LLM_MODEL=openai/gpt-4o-mini
LLM_RESPONSE_FORMAT=json_object

# Upload / API controls
DATAPILOT_MAX_UPLOAD_MB=25
DATAPILOT_MAX_ROWS=250000
DATAPILOT_MAX_COLUMNS=250
DATAPILOT_MAX_CELLS=5000000
DATAPILOT_ALLOWED_HOSTS=localhost,127.0.0.1,testserver
DATAPILOT_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### Research RAG

Research RAG remains available to the research agent and MCP/API tools (the standalone Research navigation page has been removed). PDF ingestion is available through `POST /api/research/index-pdf` and requires PyMuPDF. The default TF-IDF retriever runs locally without downloading a model. To enable semantic embeddings, install `requirements-research.txt` and set `DATAPILOT_ENABLE_RESEARCH_EMBEDDINGS=true`; the first model use may download the configured model. Do not index documents you are not permitted to use. Retrieved excerpts are source evidence, not automatically verified scientific conclusions.

### MCP server

Install the optional MCP SDK with `pip install -r requirements-mcp.txt`, then run from the backend directory:

```powershell
python mcp_server.py
```

The server uses stdio transport. Its allowlisted tools include sample listing, profiling, EDA, full sample analysis, local research indexing/retrieval, saved report retrieval, security self-test and capability discovery. The REST endpoints `/api/tools` and `/api/tools/call` are a separate REST adapter, not MCP transport.

### Deep learning

Install `requirements-deep-learning.txt` and set `DATAPILOT_ENABLE_DEEP_LEARNING=true` to add a PyTorch MLP candidate to the existing model comparison. The model uses the existing transformed tabular features, AdamW, dropout, early stopping and deterministic seeds. It is an optional baseline, not assumed to outperform classical models. Current deep-learning support is tabular only; image and sequence pipelines are not part of this release.

### MLflow

Install `requirements-tracking.txt` and set `DATAPILOT_ENABLE_MLFLOW=true` to enable MLflow. This file also includes optional XGBoost. Data Pilot logs run parameters, numeric model metrics and a compact JSON analysis metadata artifact. Raw dataset rows are not logged. The run ID is returned in the result. Validate the tracking URI and storage permissions in the target environment before a demo.

## API endpoints

```text
GET  /api/health
GET  /api/reporting/status
GET  /api/samples
POST /api/profile
POST /api/analyze
POST /api/analysis/start
GET  /api/analysis/{job_id}
POST /api/security/self-test
GET  /api/history
GET  /api/history/{experiment_id}
GET  /api/history/{experiment_id}/agents
POST /api/history/{experiment_id}/report/regenerate
GET  /api/history/{experiment_id}/report.pdf
POST /api/models/{artifact_id}/predict
GET  /api/research/status
POST /api/research/index
POST /api/research/index-pdf
POST /api/research/query
POST /api/data-engine/profile
GET  /api/tools
POST /api/tools/call
```

## Tests

```powershell
cd backend
$env:PYTHONPATH = "."
python -m pytest -q
cd ..\frontend
npm ci
npm run build
```

## Important limitations

- LangGraph's actual graph path is used only when the LangGraph dependency is installed. Otherwise the API marks execution as `python_fallback`; it does not mislabel fallback execution as LangGraph.
- The graph currently orchestrates the lifecycle around the specialist pipeline; every specialist is not yet its own independent LangGraph node.
- LangGraph checkpointing is in-memory per invocation; this is not durable cross-process state.
- DuckDB currently performs SQL-based profiling over an in-memory DataFrame. The upload path still parses files through Pandas; this is not a streaming/out-of-core ingestion engine.
- Research RAG indexes user-provided text/PDFs. It does not automatically download paywalled papers. Crossref is bibliographic metadata only.
- MLflow, MCP, PDF extraction and semantic embeddings require their optional packages and environment configuration.
- No authentication, tenant isolation, durable queue, managed database/object storage, cloud deployment, TLS, backups or production monitoring is supplied.
- Generated model bundles, databases, local research indexes and caches are runtime data and must not be committed to Git or included in the source release.


## V4 additions
Earlier V4 releases experimented with a separate natural-language Analytics Studio. It is not part of the current V4.5 product navigation; Workspace is the primary dataset-question and autonomous analysis workflow.


## OpenRouter configuration

Data Pilot uses OpenRouter for both the V4 analytics intent router and optional LLM-generated report narrative. Configure `OPENROUTER_API_KEY`, `LLM_PROVIDER=openrouter`, `LLM_BASE_URL=https://openrouter.ai/api/v1`, `LLM_API_MODE=chat_completions`, and a model ID in `backend/.env`. The deterministic Python analytics and model evaluation do not depend on the LLM; they continue to work if the key is absent or the provider request fails.


## Research retrieval behavior (V4 update)
Live research discovery is enabled by default in the supplied `.env.example` via
`DATAPILOT_ENABLE_LIVE_RESEARCH=true`. The Research Agent searches OpenAlex and
Crossref using the analysis objective, selected target, problem type, and dataset
column context. OpenAlex abstracts are shown only when supplied by the index;
Crossref-only records are clearly marked metadata-only. Full-text claims are not
made unless a full paper was separately indexed in local Research RAG. If external
network access is unavailable, Data Pilot falls back to explicitly labelled offline
methodology guidance. Set `DATAPILOT_ENABLE_LIVE_RESEARCH=false` for offline runs.

## Dataset question and report improvements
Natural-language category questions now infer likely categorical targets using
column names and observed values (for example `neutral` in a sentiment field),
then compute counts and percentages from the uploaded DataFrame. The report
renders the requested pie/donut chart when the question explicitly asks for one.
SHAP global feature contributions are displayed as a ranked horizontal bar chart.
The PDF export supports pie charts and uses a consistent branded report style.


## V4.1 quality update
See `RELEASE_NOTES_V4.1.md` for the full list of dataset-aware target selection,
research retrieval, chart, SHAP, report and contrast improvements.

For live literature discovery, ensure `DATAPILOT_ENABLE_LIVE_RESEARCH=true` is
present in `backend/.env`. OpenAlex and Crossref require outbound internet access.
If either source is unavailable, the Research Agent clearly reports offline
methodology guidance instead of presenting it as retrieved literature.
