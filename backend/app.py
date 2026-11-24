"""DataPilot REST API Server."""

import hmac
import io
import os
import time
import logging
import importlib.util
from collections import defaultdict, deque
from html import escape
from pathlib import Path
from threading import Lock
from typing import Optional
from pydantic import BaseModel, Field

import pandas as pd
import numpy as np
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from data_pilot.agents import RiskTrajectoryGenerator, SecurityGuardian
from data_pilot.agents.eda import EDAAgent
from data_pilot.agents.reporting import ReportingAgent
from data_pilot.history import ExperimentStore
from data_pilot.jobs import AnalysisJobStore
from data_pilot.artifacts import ArtifactStore
from data_pilot.agents.preprocessing import PreprocessingAgent
from uuid import uuid4
from data_pilot.tool_registry import ToolRegistry
from data_pilot.pipeline import run_pipeline
from data_pilot.profiler import profile_dataframe
from data_pilot.research.rag import ResearchRAG, extract_pdf_text
from data_pilot.data_engine import get_engine
from data_pilot.orchestration.graph import LANGGRAPH_AVAILABLE


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
VERSION_FILE = BASE_DIR.parent / "VERSION"
APP_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.is_file() else "4.5.0"
DATA_DIR = Path(os.getenv("DATAPILOT_DATA_DIR", str(BASE_DIR))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
ENVIRONMENT = os.getenv("DATAPILOT_ENV", "development").lower()
logger = logging.getLogger("datapilot.api")
MAX_UPLOAD_BYTES = int(os.getenv("DATAPILOT_MAX_UPLOAD_MB", "25")) * 1024 * 1024
MAX_FILE_SIZE = MAX_UPLOAD_BYTES  # Backwards-compatible alias used by regression tests.
MAX_DATASET_ROWS = int(os.getenv("DATAPILOT_MAX_ROWS", "250000"))
MAX_DATASET_COLUMNS = int(os.getenv("DATAPILOT_MAX_COLUMNS", "250"))
MAX_DATASET_CELLS = int(os.getenv("DATAPILOT_MAX_CELLS", "5000000"))
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"
EXPERIMENT_STORE = ExperimentStore(DATA_DIR / "datapilot_history.sqlite3")
JOB_STORE = AnalysisJobStore(DATA_DIR / "datapilot_history.sqlite3")
TOOL_REGISTRY = ToolRegistry()
RESEARCH_RAG = ResearchRAG(DATA_DIR / "research_knowledge.sqlite3")
_RATE_LIMIT_LOCK = Lock()
_RATE_LIMIT_BUCKETS: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _require_api_access(request: Request) -> None:
    """Enforce optional bearer/API-key auth when DATAPILOT_API_TOKEN is configured."""
    expected = os.getenv("DATAPILOT_API_TOKEN", "").strip()
    if not expected:
        return
    auth_header = request.headers.get("authorization", "")
    bearer = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""
    api_key = request.headers.get("x-api-key", "").strip()
    supplied = bearer or api_key
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid API authentication token.")


def _enforce_rate_limit(request: Request) -> None:
    """Sliding-window per-client rate limiter for expensive/mutating endpoints."""
    limit = int(os.getenv("DATAPILOT_RATE_LIMIT_PER_MIN", "60"))
    if limit <= 0:
        return
    client_ip = request.client.host if request.client else "unknown"
    bucket_key = (client_ip, request.url.path)
    now = time.monotonic()
    cutoff = now - 60.0
    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS[bucket_key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Retry shortly.")
        bucket.append(now)

app = FastAPI(
    title="DataPilot API",
    description="Autonomous multi-agent data science REST API",
    version=APP_VERSION,
    docs_url=None if ENVIRONMENT == "production" else "/docs",
    redoc_url=None if ENVIRONMENT == "production" else "/redoc",
    openapi_url=None if ENVIRONMENT == "production" else "/openapi.json",
)

CORS_ORIGINS = [x.strip() for x in os.getenv("DATAPILOT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)
ALLOWED_HOSTS = [x.strip() for x in os.getenv("DATAPILOT_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if x.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

@app.on_event("startup")
async def recover_stale_analysis_jobs():
    """Do not leave jobs from a previous local server process marked as running."""
    recovered = JOB_STORE.recover_interrupted()
    if recovered:
        logger.warning("Marked %s stale analysis job(s) as interrupted after server restart", recovered)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "failed",
            "detail": exc.detail,
            "error": {
                "type": "HTTPException",
                "message": str(exc.detail),
                "status_code": exc.status_code,
            },
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception (%s): %s", type(exc).__name__, exc)
    return JSONResponse(
        status_code=500,
        content={
            "status": "failed",
            "detail": "An internal error occurred during processing.",
            "error": {
                "type": type(exc).__name__,
                "message": "An internal error occurred during processing. Please verify input data and parameters.",
            },
        },
    )


SAMPLE_METADATA = [
    {
        "id": "churn",
        "title": "Customer Churn",
        "filename": "customer_churn.csv",
        "problem_type": "classification",
        "suggested_query": "Predict customer churn and identify high-risk risk factors across contracts.",
        "target_column": "churn",
        "description": "Telecom customer profiles with service tiers, tenure, charges, and churn status.",
    },
    {
        "id": "housing",
        "title": "Housing Valuation",
        "filename": "housing_prices.csv",
        "problem_type": "regression",
        "suggested_query": "Estimate house sale prices based on square footage, location score, and bedrooms.",
        "target_column": "price",
        "description": "Property characteristics, room counts, location rating, and market valuation.",
    },
    {
        "id": "sales",
        "title": "Quarterly Sales & Revenue",
        "filename": "quarterly_sales.csv",
        "problem_type": "regression",
        "suggested_query": "Compare Q3 revenue by region and flag any anomalies against last year.",
        "target_column": "revenue",
        "description": "Regional enterprise sales, marketing expenditure, deal counts, and revenue outcomes.",
    },
]


def _validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df.columns) == 0:
        raise HTTPException(status_code=400, detail="The uploaded dataset is empty.")
    if len(df) > MAX_DATASET_ROWS:
        raise HTTPException(status_code=413, detail=f"Dataset exceeds the {MAX_DATASET_ROWS:,}-row limit.")
    if len(df.columns) > MAX_DATASET_COLUMNS or len(df) * len(df.columns) > MAX_DATASET_CELLS:
        raise HTTPException(status_code=413, detail="Dataset dimensions exceed configured safety limits.")
    names = [str(c).strip() for c in df.columns]
    if any(not name for name in names) or len(set(names)) != len(names):
        raise HTTPException(status_code=400, detail="Column names must be non-empty and unique.")
    df.columns = names
    # Prevent pathological object columns from carrying giant cells into agents/reports.
    for column in df.select_dtypes(include=["object", "string"]).columns:
        if df[column].dropna().astype(str).str.len().gt(100_000).any():
            raise HTTPException(status_code=400, detail=f"Column '{column}' contains an oversized text value.")
    return df


def _load_dataframe(file: Optional[UploadFile], sample_id: Optional[str]) -> pd.DataFrame:
    if file and file.filename:
        filename = Path(file.filename).name
        suffix = Path(filename).suffix.lower()
        if suffix not in {".csv", ".xlsx", ".xls", ".json"}:
            raise HTTPException(status_code=415, detail="Unsupported file type. Upload CSV, XLSX, XLS, or JSON.")
        content = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"Upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
        try:
            if suffix == ".csv":
                frame = pd.read_csv(io.BytesIO(content), low_memory=False)
            elif suffix in {".xlsx", ".xls"}:
                frame = pd.read_excel(io.BytesIO(content))
            else:
                frame = pd.read_json(io.BytesIO(content))
            return _validate_dataframe(frame)
        except HTTPException:
            raise
        except Exception as exc:
            logger.info("Dataset parse rejected (%s)", type(exc).__name__)
            raise HTTPException(status_code=400, detail="Could not parse the uploaded dataset. Check the file format and contents.") from exc

    if sample_id:
        sample = next((item for item in SAMPLE_METADATA if item["id"] == sample_id), None)
        if not sample:
            raise HTTPException(status_code=404, detail="Sample dataset not found.")
        sample_path = SAMPLE_DATA_DIR / sample["filename"]
        if not sample_path.exists():
            raise HTTPException(status_code=404, detail="Sample dataset file is missing.")
        return _validate_dataframe(pd.read_csv(sample_path))

    default_path = SAMPLE_DATA_DIR / "customer_churn.csv"
    if default_path.exists():
        return _validate_dataframe(pd.read_csv(default_path))
    raise HTTPException(status_code=400, detail="No dataset provided. Upload a file or select a sample dataset.")


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "DataPilot REST API",
        "version": APP_VERSION,
        "orchestration": {"framework": "LangGraph" if LANGGRAPH_AVAILABLE else "python_fallback", "available": LANGGRAPH_AVAILABLE},
        "data_engine": {"configured": os.getenv("DATAPILOT_DATA_ENGINE", "auto"), "duckdb_available": importlib.util.find_spec("duckdb") is not None},
        "deep_learning": {"enabled": os.getenv("DATAPILOT_ENABLE_DEEP_LEARNING", "false").lower() in {"1", "true", "yes"} and importlib.util.find_spec("torch") is not None},
        "integrations": {"mcp_available": importlib.util.find_spec("mcp") is not None, "mlflow_available": importlib.util.find_spec("mlflow") is not None, "torch_available": importlib.util.find_spec("torch") is not None, "pymupdf_available": importlib.util.find_spec("fitz") is not None, "sentence_transformers_available": importlib.util.find_spec("sentence_transformers") is not None},
        "research_rag": RESEARCH_RAG.status(),
        "reporting": {  "llm_configured": bool(
                          os.getenv("GEMINI_API_KEY") if os.getenv("LLM_PROVIDER", "openrouter").lower() == "gemini"
                          else (os.getenv("OPENROUTER_API_KEY") if os.getenv("LLM_PROVIDER", "openrouter").lower() == "openrouter"
                                else (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")))
                      ),
                     "provider": os.getenv("LLM_PROVIDER","openrouter"),
                      "model": os.getenv("LLM_MODEL", "gemini-2.0-flash" if os.getenv("LLM_PROVIDER","openrouter").lower()=="gemini" else ("openai/gpt-4o-mini" if os.getenv("LLM_PROVIDER","openrouter").lower()=="openrouter" else "gpt-4o-mini"))},
        "agents": [
            "Profiler",
            "PlannerAgent",
            "SecurityGuardian",
            "EDAAgent",
            "PreprocessingAgent",
            "MLRunner",
            "ExplainabilityAgent",
            "CriticAgent",
            "ReplannerAgent (bounded retry)",
            "ReportingAgent",
            "ResearchAgent (local RAG + optional Crossref metadata)",
            "ExperimentHistory",
            "AllowlistedToolRegistry",
            "LangGraphOrchestrator",
            "DuckDBDataEngine (optional auto-selection)",
            "PyTorchTabularMLP (optional)",
            "LocalResearchRAG (TF-IDF / optional semantic embeddings)",
        ],
    }


@app.get("/api/reporting/status")
def reporting_status():
    """Expose safe LLM configuration metadata without revealing credentials."""
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
    configured = bool(
        os.getenv("OPENROUTER_API_KEY") if provider == "openrouter"
        else (os.getenv("GEMINI_API_KEY") if provider == "gemini"
              else (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")))
    )
    return {"llm_configured": configured, "provider": provider, "model": os.getenv("LLM_MODEL", "openai/gpt-4o-mini" if provider == "openrouter" else "gpt-4o-mini") if configured else None, "fallback": "deterministic_markdown"}


@app.get("/api/samples")
def list_samples():
    """Return metadata and preview of built-in sample datasets."""
    results = []
    for meta in SAMPLE_METADATA:
        path = SAMPLE_DATA_DIR / meta["filename"]
        preview = []
        rows = 0
        cols = 0

        if path.exists():
            try:
                df = pd.read_csv(path)
                rows = len(df)
                cols = len(df.columns)
                preview = df.head(3).fillna("").to_dict(orient="records")
            except Exception:
                pass

        item = dict(meta)
        item["rows"] = rows
        item["columns_count"] = cols
        item["preview"] = preview
        results.append(item)

    return results


@app.post("/api/profile")
async def profile_endpoint(
    file: Optional[UploadFile] = File(None),
    sample_id: Optional[str] = Form(None),
    target_column: Optional[str] = Form(None),
):
    """Profile the provided dataset deterministically."""
    df = _load_dataframe(file, sample_id)
    profile = profile_dataframe(df, target_column=target_column)
    return {
        "status": "success",
        "profile": profile.to_dict(),
        "preview": df.head(5).fillna("").to_dict(orient="records"),
    }


@app.post("/api/security/self-test")
async def security_self_test_endpoint():
    """Run controlled adversarial plan scenarios through the SecurityGuardian."""
    df = _load_dataframe(None, "churn")
    profile = profile_dataframe(df, target_column="churn")

    from data_pilot.agents import Objective, PlannerAgent

    plan = PlannerAgent().create_plan(
        profile,
        Objective(
            text="Predict customer churn",
            target_column="churn",
            problem_type="classification",
        ),
    )

    results = RiskTrajectoryGenerator().evaluate(
        plan=plan,
        profile=profile,
        guardian=SecurityGuardian(),
    )

    return {
        "status": "success",
        "description": "AuraGen-inspired controlled risk trajectory test",
        "scenarios": results,
        "all_blocked": all(item["blocked"] for item in results),
    }


def _execute_analysis_job(job_id: str, df: pd.DataFrame, inquiry: str, target_column: str | None, problem_type: str, dataset_name: str):
    JOB_STORE.update(job_id, "running", progress_percent=1, current_stage="Starting worker", completed_steps=0, total_steps=11)
    def report_progress(payload):
        JOB_STORE.progress(job_id, payload.get("progress_percent", 0), payload.get("current_stage", "Working"),
                           payload.get("completed_steps", 0), payload.get("total_steps", 11))
    try:
        result = run_pipeline(df=df, inquiry=inquiry, target_column=target_column, problem_type=problem_type, dataset_name=dataset_name, progress_callback=report_progress)
        experiment_id = EXPERIMENT_STORE.save(dataset_name, result)
        result["experiment_id"] = experiment_id
        result["dataset_name"] = dataset_name
        EXPERIMENT_STORE.update_result(experiment_id, result)
        JOB_STORE.update(job_id, "completed", result=result, progress_percent=100, current_stage="Completed", completed_steps=11, total_steps=11)
    except Exception as exc:
        logger.exception("Analysis job failed: id=%s type=%s", job_id, type(exc).__name__)
        JOB_STORE.update(job_id, "failed", error_code=type(exc).__name__, current_stage="Failed")


@app.post("/api/analysis/start", status_code=202, dependencies=[Depends(_require_api_access), Depends(_enforce_rate_limit)])
async def start_analysis_endpoint(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    sample_id: Optional[str] = Form(None),
    inquiry: Optional[str] = Form(""),
    target_column: Optional[str] = Form(None),
    problem_type: Optional[str] = Form("unknown"),
):
    """Queue an analysis and return immediately; poll GET /api/analysis/{job_id}."""
    df = _load_dataframe(file, sample_id)
    dataset_name = (Path(file.filename.replace("\\", "/")).name[:120] if file and file.filename else (sample_id or "default_sample"))
    job_id = str(uuid4())
    JOB_STORE.create(job_id, dataset_name)
    background_tasks.add_task(_execute_analysis_job, job_id, df.copy(), inquiry or "", target_column, problem_type or "unknown", dataset_name)
    return {"job_id": job_id, "status": "queued", "poll_url": f"/api/analysis/{job_id}"}


@app.get("/api/analysis/{job_id}")
def get_analysis_job(job_id: str):
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found.")
    return job


@app.post("/api/analyze", dependencies=[Depends(_require_api_access), Depends(_enforce_rate_limit)])
async def analyze_endpoint(
    file: Optional[UploadFile] = File(None),
    sample_id: Optional[str] = Form(None),
    inquiry: Optional[str] = Form(""),
    target_column: Optional[str] = Form(None),
    problem_type: Optional[str] = Form("unknown"),
):
    """Execute the guarded Data Pilot autonomous pipeline."""
    df = _load_dataframe(file, sample_id)
    dataset_name = (Path(file.filename.replace("\\", "/")).name[:120] if file and file.filename else (sample_id or "default_sample"))
    result = run_pipeline(
        df=df,
        inquiry=inquiry or "",
        target_column=target_column,
        problem_type=problem_type or "unknown",
        dataset_name=dataset_name,
    )
    experiment_id = EXPERIMENT_STORE.save(dataset_name, result)
    result["experiment_id"] = experiment_id
    result["dataset_name"] = dataset_name
    EXPERIMENT_STORE.update_result(experiment_id, result)
    return result


@app.get("/api/history")
def list_experiments(limit: int = 20):
    completed = EXPERIMENT_STORE.list(limit)
    jobs = JOB_STORE.list(limit, statuses=("queued", "running", "failed"))
    active = [{**job, "is_job": True} for job in jobs]
    return {"items": sorted(completed + active, key=lambda item: item.get("created_at", ""), reverse=True)[:max(1, min(limit, 100))]}


@app.get("/api/history/{experiment_id}/agents")
def get_agent_trace(experiment_id: str):
    result = EXPERIMENT_STORE.get(experiment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return {"experiment_id": experiment_id, "orchestration": result.get("orchestration", {}), "agents": result.get("agent_trace", [])}

@app.post("/api/history/{experiment_id}/report/regenerate", dependencies=[Depends(_require_api_access), Depends(_enforce_rate_limit)])
def regenerate_saved_report(experiment_id: str):
    """Regenerate the narrative for a saved analysis using current server LLM settings."""
    result = EXPERIMENT_STORE.get(experiment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    dataset_name = result.get("dataset_name", "uploaded dataset")
    result["report"] = ReportingAgent().generate(result, dataset_name=dataset_name)
    EXPERIMENT_STORE.update_result(experiment_id, result)
    return {"report": result["report"]}


@app.get("/api/history/{experiment_id}/report.pdf")
def download_report_pdf(experiment_id: str):
    """Render the saved Markdown report as a downloadable PDF."""
    result = EXPERIMENT_STORE.get(experiment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    markdown = result.get("report", {}).get("markdown", "")
    if not markdown:
        raise HTTPException(status_code=404, detail="No report is available for this experiment.")
    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, HRFlowable, KeepTogether, Table, TableStyle
        from reportlab.graphics.shapes import Drawing, String, Rect
        from reportlab.graphics.charts.barcharts import VerticalBarChart
        from reportlab.graphics.charts.piecharts import Pie
        from reportlab.lib import colors
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
        styles = getSampleStyleSheet()
        body = ParagraphStyle("ReportBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.2, leading=14, textColor=colors.HexColor("#39463D"), spaceAfter=7)
        title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=23, leading=28, textColor=colors.white, alignment=0, spaceAfter=5)
        subtitle_style = ParagraphStyle("ReportSubtitle", parent=body, fontName="Helvetica", fontSize=8.5, leading=12, textColor=colors.HexColor("#DCE8CF"), spaceAfter=0)
        h2_style = ParagraphStyle("ReportH2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=colors.HexColor("#20392D"), spaceBefore=15, spaceAfter=8)
        h3_style = ParagraphStyle("ReportH3", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=colors.HexColor("#78964A"), spaceBefore=8, spaceAfter=5)
        story = []
        def draw_page(canvas, document):
            canvas.saveState()
            forest = colors.HexColor("#20392D")
            lime = colors.HexColor("#CFE77B")
            canvas.setFillColor(forest)
            canvas.rect(0, A4[1]-5*mm, A4[0], 5*mm, stroke=0, fill=1)
            canvas.setStrokeColor(colors.HexColor("#D9E0D4"))
            canvas.line(18*mm, 13*mm, A4[0]-18*mm, 13*mm)
            canvas.setFont("Helvetica-Bold", 7)
            canvas.setFillColor(forest)
            canvas.drawString(18*mm, 8*mm, "DATA PILOT  /  ANALYTICS INTELLIGENCE")
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#718071"))
            canvas.drawRightString(A4[0]-18*mm, 8*mm, f"CONFIDENTIAL  ·  PAGE {document.page}")
            canvas.restoreState()
        for line in markdown.splitlines():
            if line.startswith("# "):
                banner = Table([[Paragraph(escape(line[2:]), title_style), Paragraph("EVIDENCE-LED ANALYSIS<br/>Verified computations · model interpretation", subtitle_style)]], colWidths=[doc.width*0.67, doc.width*0.33])
                banner.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#20392D")),
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                    ("LEFTPADDING", (0,0), (-1,-1), 14), ("RIGHTPADDING", (0,0), (-1,-1), 14),
                    ("TOPPADDING", (0,0), (-1,-1), 16), ("BOTTOMPADDING", (0,0), (-1,-1), 16),
                ]))
                story.append(banner)
                story.append(Spacer(1, 10))
                story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#CFE77B"), spaceBefore=0, spaceAfter=10))
            elif line.startswith("## "):
                story.append(Spacer(1, 7)); story.append(Paragraph(escape(line[3:]), h2_style))
                if line[3:].strip().lower() == "visual analysis":
                    charts = result.get("report", {}).get("charts", [])
                    for chart_data in charts:
                        rows = (chart_data.get("data") or [])[:10]
                        if not rows:
                            continue
                        row_height = 20
                        drawing = Drawing(470, max(190, 42 + row_height * len(rows)))
                        forest = colors.HexColor("#20392D")
                        green = colors.HexColor("#78964A")
                        clay = colors.HexColor("#A77A65")
                        palette = ["#78964A", "#A77A65", "#D2B96F", "#567C70", "#B7A08B", "#8C9B6B"]
                        drawing.add(String(8, drawing.height-18, str(chart_data.get("title", "Data distribution"))[:90], fontSize=10, fillColor=forest))
                        if chart_data.get("type") in {"pie", "donut"}:
                            pie = Pie()
                            pie.x = 8; pie.y = 8; pie.width = 172; pie.height = 160
                            pie.data = [max(0, float(row.get("value", 0) or 0)) for row in rows]
                            pie.labels = []
                            pie.slices.strokeWidth = 0.8
                            pie.slices.strokeColor = colors.white
                            for i in range(len(rows)):
                                pie.slices[i].fillColor = colors.HexColor(palette[i % len(palette)])
                            drawing.add(pie)
                            total = sum(max(0, float(row.get("value", 0) or 0)) for row in rows) or 1
                            for i, row in enumerate(rows):
                                yy = drawing.height - 48 - i*17
                                col = colors.HexColor(palette[i % len(palette)])
                                drawing.add(Rect(198, yy-2, 8, 8, fillColor=col, strokeColor=col))
                                val = float(row.get("value", 0) or 0)
                                pct = float(row.get("percentage", val/total*100) or 0)
                                drawing.add(String(212, yy, f"{str(row.get('label',''))[:28]}   {int(val):,}   ({pct:.1f}%)", fontSize=7.5, fillColor=forest))
                        else:
                            values = [max(0, float(row.get("value", 0) or 0)) for row in rows]
                            max_value = max(values) if values else 1
                            for i, row in enumerate(rows):
                                yy = drawing.height - 43 - i*row_height
                                label = str(row.get("label", ""))
                                val = values[i]
                                drawing.add(String(8, yy+3, label[:29], fontSize=7.3, fillColor=forest))
                                bar_width = 265 * val / max_value if max_value else 0
                                drawing.add(Rect(190, yy, bar_width, 10, fillColor=green, strokeColor=None))
                                drawing.add(String(465, yy+2, f"{val:,.4g}", fontSize=7.2, textAnchor="end", fillColor=clay))
                        story.append(Spacer(1, 5)); story.append(drawing); story.append(Spacer(1, 8))
            elif line.startswith("### "):
                story.append(Paragraph(escape(line[4:]), h3_style))
            elif line.startswith("- "):
                story.append(Paragraph("• " + escape(line[2:]), body))
            elif line.strip():
                story.append(Paragraph(escape(line), body))
            else:
                story.append(Spacer(1, 4))
        doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="datapilot-report-{experiment_id[:8]}.pdf"'})
    except Exception as exc:
        logger.exception("PDF report rendering failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="PDF report could not be generated. Install reportlab and retry.") from exc


@app.get("/api/history/{experiment_id}")
def get_experiment(experiment_id: str):
    result = EXPERIMENT_STORE.get(experiment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return result


@app.post("/api/models/{artifact_id}/predict", dependencies=[Depends(_require_api_access), Depends(_enforce_rate_limit)])
async def predict_with_saved_model(artifact_id: str, file: UploadFile = File(...)):
    """Run predictions with a model artifact created by this Data Pilot instance."""
    try:
        bundle = ArtifactStore(DATA_DIR / "artifacts").load_model(artifact_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Trusted model artifact not found.")
    df = _load_dataframe(file, None)
    features = PreprocessingAgent._expand_datetime(df, bundle.get("datetime_columns", []))
    try:
        transformed = bundle["preprocessor"].transform(features)
        predictions = bundle["estimator"].predict(transformed)
        probabilities = bundle["estimator"].predict_proba(transformed) if hasattr(bundle["estimator"], "predict_proba") else None
        classes = bundle.get("target_classes", [])
        rows = []
        for index, pred in enumerate(predictions):
            value = classes[int(pred)] if classes and isinstance(pred, (int, float, np.integer, np.floating)) and 0 <= int(pred) < len(classes) else pred
            item = {"prediction": str(value)}
            if probabilities is not None:
                item["probabilities"] = {str(classes[i] if i < len(classes) else i): round(float(score), 6) for i, score in enumerate(probabilities[index])}
            rows.append(item)
        return {"status": "success", "artifact_id": artifact_id, "model_name": bundle["model_name"], "rows": len(rows), "predictions": rows}
    except Exception as exc:
        logger.info("Prediction rejected (%s)", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Prediction failed. Check that the input columns match the training feature schema.") from exc


class ResearchIndexRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=80, max_length=2_000_000)
    source: str = Field(default="user-provided text", max_length=1000)
    doi: str = Field(default="", max_length=200)

class ResearchQueryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)

@app.get("/api/research/status")
def research_status():
    return RESEARCH_RAG.status()

@app.post("/api/research/index", dependencies=[Depends(_require_api_access), Depends(_enforce_rate_limit)])
def research_index(request: ResearchIndexRequest):
    try: return RESEARCH_RAG.index_text(request.title, request.text, request.source, request.doi)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/research/query")
def research_query(request: ResearchQueryRequest):
    return RESEARCH_RAG.answer_context(request.query, request.top_k)

@app.post("/api/research/index-pdf", dependencies=[Depends(_require_api_access), Depends(_enforce_rate_limit)])
async def research_index_pdf(file: UploadFile = File(...), title: str = Form(""), doi: str = Form("")):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Upload a PDF research document.")
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Research PDF exceeds the 20 MB limit.")
    try:
        extracted, pages = extract_pdf_text(content)
        result = RESEARCH_RAG.index_text(title.strip() or Path(file.filename).stem, extracted, file.filename, doi)
        result["pages_extracted"] = pages
        return result
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.info("Research PDF rejected (%s)", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Could not extract text from this PDF. Check that it is a readable, non-encrypted PDF.") from exc

@app.post("/api/data-engine/profile")
def data_engine_profile(sample_id: str = Form(default="churn")):
    frame = _load_dataframe(None, sample_id)
    engine = get_engine(frame)
    try: return engine.profile(frame)
    except Exception as exc:
        logger.warning("Data engine profiling failed (%s); falling back to Pandas", type(exc).__name__)
        from data_pilot.data_engine.selector import PandasEngine
        return {**PandasEngine().profile(frame), "fallback_reason": type(exc).__name__}

@app.get("/api/tools")
def list_agent_tools():
    """List safe, schema-described tools exposed at the MCP adapter boundary."""
    return {"tools": TOOL_REGISTRY.list_tools(), "transport": "REST tool adapter; standalone MCP stdio server is available via backend/mcp_server.py"}


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)


@app.post("/api/tools/call", dependencies=[Depends(_require_api_access), Depends(_enforce_rate_limit)])
def call_agent_tool(request: ToolCallRequest):
    try:
        args = TOOL_REGISTRY.validate_arguments(request.name, request.arguments)
    except KeyError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if request.name == "dataset.list_samples":
        return {"content": [{"type": "text", "text": SAMPLE_METADATA}]}
    if request.name == "dataset.profile":
        df = _load_dataframe(None, "churn")
        profile = profile_dataframe(df, target_column=args.get("target_column"))
        return {"content": [{"type": "text", "text": profile.to_dict()}]}
    if request.name == "dataset.eda":
        df = _load_dataframe(None, "churn")
        return {"content": [{"type": "text", "text": EDAAgent().analyze(df)}]}
    if request.name == "security.self_test":
        df = _load_dataframe(None, "churn")
        profile = profile_dataframe(df, target_column="churn")
        from data_pilot.agents import Objective, PlannerAgent
        plan = PlannerAgent().create_plan(profile, Objective("Predict churn", "churn", "classification"))
        scenarios = RiskTrajectoryGenerator().evaluate(plan, profile, SecurityGuardian())
        return {"content": [{"type": "text", "text": {"scenarios": scenarios, "all_blocked": all(x["blocked"] for x in scenarios)}}]}
    if request.name == "analysis.run_sample":
        sample_id = str(args.get("sample_id", ""))
        meta = next((x for x in SAMPLE_METADATA if x["id"] == sample_id), None)
        if not meta: raise HTTPException(status_code=400, detail="sample_id must be churn, housing, or sales.")
        result = run_pipeline(_load_dataframe(None, sample_id), str(args.get("inquiry", meta["suggested_query"])), meta["target_column"], meta["problem_type"], meta["filename"])
        experiment_id = EXPERIMENT_STORE.save(meta["filename"], result)
        return {"content": [{"type": "text", "text": {"experiment_id": experiment_id, "result": result}}]}
    if request.name == "research.search":
        top_k = max(1, min(int(args.get("top_k", 4)), 10))
        return {"content": [{"type": "text", "text": RESEARCH_RAG.answer_context(str(args.get("query", "")), top_k)}]}
    if request.name == "system.capabilities":
        return {"content": [{"type": "text", "text": {"langgraph": LANGGRAPH_AVAILABLE, "duckdb": get_engine().name, "deep_learning_enabled": os.getenv("DATAPILOT_ENABLE_DEEP_LEARNING", "false"), "mlflow_enabled": os.getenv("DATAPILOT_ENABLE_MLFLOW", "false"), "research": RESEARCH_RAG.status()}}]}
    if request.name == "analysis.report":
        experiment_id = args.get("experiment_id")
        result = EXPERIMENT_STORE.get(str(experiment_id)) if experiment_id else None
        if result is None:
            raise HTTPException(status_code=400, detail="Provide a valid experiment_id.")
        return {"content": [{"type": "text", "text": ReportingAgent().generate(result)}]}
    raise HTTPException(status_code=403, detail="Tool is not executable.")


FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIST), html=True),
        name="frontend",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
