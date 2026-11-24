# Data Pilot V3 setup guide

## Prerequisites

- Python 3.11 or 3.12 recommended.
- Node.js 20+ and npm.
- Git (optional).

## Project structure

```text
DataPilot_V3/
├── backend/
│   ├── app.py
│   ├── mcp_server.py
│   ├── data_pilot/
│   │   ├── agents/
│   │   ├── orchestration/       # LangGraph StateGraph
│   │   ├── data_engine/         # Pandas / DuckDB selector
│   │   ├── deep_learning/       # Optional PyTorch MLP
│   │   └── research/            # Local RAG and PDF extraction
│   ├── sample_data/
│   ├── tests/
│   └── requirements*.txt
├── frontend/                    # React + Vite
├── Dockerfile
├── compose.yaml
└── documentation
```

## Backend installation (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The base requirements include LangGraph and DuckDB. Install optional components only when needed:

```powershell
pip install -r requirements-mcp.txt
pip install -r requirements-deep-learning.txt
pip install -r requirements-research.txt
pip install -r requirements-tracking.txt
```

Copy `backend/.env.example` to `backend/.env` and set feature flags. LLM credentials belong only in this backend file.

## Frontend installation

```powershell
cd frontend
npm ci
cd ..
```

## Run

```powershell
.\start.bat
```

- Frontend: http://localhost:5173
- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs

## Test

```powershell
cd backend
$env:PYTHONPATH = "."
python -m pytest -q
```

See `README.md` for optional feature configuration, MCP, research indexing, Docker and known limitations.
