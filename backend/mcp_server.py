"""Data Pilot MCP server (stdio transport).

Run from backend/: python mcp_server.py
Install the optional MCP SDK with: pip install -r requirements-optional.txt
Tools are allowlisted and never accept arbitrary filesystem paths or executable code.
"""
from __future__ import annotations
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from data_pilot.agents.eda import EDAAgent
from data_pilot.agents.reporting import ReportingAgent
from data_pilot.agents.risk_generator import RiskTrajectoryGenerator
from data_pilot.agents.security import SecurityGuardian
from data_pilot.agents.planner import PlannerAgent
from data_pilot.agents.schemas import Objective
from data_pilot.history import ExperimentStore
from data_pilot.profiler import profile_dataframe
from data_pilot.pipeline import run_pipeline
from data_pilot.research.rag import ResearchRAG
from app import _load_dataframe, SAMPLE_METADATA, LANGGRAPH_AVAILABLE

mcp=FastMCP("DataPilot")
DATA_DIR=Path(os.getenv("DATAPILOT_DATA_DIR",str(Path(__file__).resolve().parent))).resolve(); DATA_DIR.mkdir(parents=True,exist_ok=True)
STORE=ExperimentStore(DATA_DIR/"datapilot_history.sqlite3"); RAG=ResearchRAG(DATA_DIR/"research_knowledge.sqlite3")

@mcp.tool()
def list_sample_datasets() -> list[dict]:
    """List bundled sample datasets available for safe analysis."""
    return [{"id":x["id"],"name":x["title"],"problem_type":x["problem_type"]} for x in SAMPLE_METADATA]

@mcp.tool()
def get_runtime_capabilities() -> dict:
    """Report LangGraph, deep-learning, DuckDB, MLflow and RAG configuration."""
    def available(name):
        try: __import__(name); return True
        except ImportError: return False
    return {"orchestration":"LangGraph" if LANGGRAPH_AVAILABLE else "unavailable","deep_learning_enabled":os.getenv("DATAPILOT_ENABLE_DEEP_LEARNING","false").lower() in {"1","true","yes"},"torch_installed":available("torch"),"duckdb_installed":available("duckdb"),"mlflow_installed":available("mlflow"),"research_rag":RAG.status(),"transport":"MCP stdio"}

@mcp.tool()
def profile_sample_dataset(sample_id: str="churn",target_column: str="") -> dict:
    """Profile a bundled dataset; arbitrary local paths are not accepted."""
    return profile_dataframe(_load_dataframe(None,sample_id),target_column=target_column or None).to_dict()

@mcp.tool()
def run_sample_eda(sample_id: str="churn") -> dict:
    """Run exploratory data analysis on one bundled sample."""
    return EDAAgent().analyze(_load_dataframe(None,sample_id))

@mcp.tool()
def run_sample_analysis(sample_id: str="churn",inquiry: str="") -> dict:
    """Execute the complete LangGraph-orchestrated analysis on a bundled sample."""
    meta=next((x for x in SAMPLE_METADATA if x["id"]==sample_id),None)
    if not meta: return {"error":"Unknown sample_id. Allowed: churn, housing, sales."}
    result=run_pipeline(_load_dataframe(None,sample_id),inquiry or meta["suggested_query"],meta["target_column"],meta["problem_type"],meta["filename"])
    return {"status":result.get("status"),"plan":result.get("plan"),"models":result.get("models"),"critic":result.get("critic"),"orchestration":result.get("orchestration"),"report":result.get("report")}

@mcp.tool()
def index_research_text(title: str,text: str,source: str="MCP-provided source",doi: str="") -> dict:
    """Index text supplied by the MCP client for later local evidence retrieval."""
    try: return RAG.index_text(title,text,source,doi)
    except ValueError as exc: return {"error":str(exc)}

@mcp.tool()
def search_indexed_research(query: str,top_k: int=4) -> dict:
    """Retrieve relevant passages from research documents explicitly indexed by the user."""
    return RAG.answer_context(query,max(1,min(int(top_k),10)))

@mcp.tool()
def get_saved_analysis_report(experiment_id: str) -> dict:
    """Generate a Markdown report for a previously saved experiment."""
    result=STORE.get(experiment_id)
    if result is None: return {"error":"Experiment not found"}
    return ReportingAgent().generate(result)

@mcp.tool()
def run_security_guardrail_self_test() -> dict:
    """Run controlled adversarial plan cases through the Security Guardian."""
    df=_load_dataframe(None,"churn"); profile=profile_dataframe(df,target_column="churn")
    plan=PlannerAgent().create_plan(profile,Objective("Predict churn","churn","classification"))
    scenarios=RiskTrajectoryGenerator().evaluate(plan,profile,SecurityGuardian())
    return {"scenarios":scenarios,"all_blocked":all(x["blocked"] for x in scenarios)}

if __name__=="__main__": mcp.run(transport="stdio")
