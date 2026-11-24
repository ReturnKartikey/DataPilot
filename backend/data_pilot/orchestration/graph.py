"""LangGraph orchestration for Data Pilot's analysis lifecycle.

The graph controls request validation, execution, and final audit. Existing
specialist agents remain deterministic Python components invoked by the
analysis node; they are not falsely represented as independent LLM agents.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from .state import DataPilotState
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE=True
except ImportError:
    StateGraph=END=MemorySaver=None
    LANGGRAPH_AVAILABLE=False

def _stamp(name: str, status: str, detail: str=""):
    return {"node":name,"status":status,"detail":detail,"timestamp":datetime.now(timezone.utc).isoformat()}

def run_langgraph_pipeline(df, inquiry="", target_column=None, problem_type="unknown", dataset_name="uploaded dataset", progress_callback=None) -> dict[str,Any]:
    from data_pilot.pipeline import _run_pipeline_core
    if not LANGGRAPH_AVAILABLE:
        # Keep the application usable in constrained/offline environments. This
        # fallback is explicitly labelled and is not presented as LangGraph.
        result = _run_pipeline_core(df, inquiry, target_column, problem_type, dataset_name, progress_callback=progress_callback)
        result["orchestration"] = {"framework": "python_fallback", "graph_version": "v3", "status": "completed", "events": [_stamp("input_validation", "success", "Input accepted"), _stamp("specialist_agent_pipeline", "success", "Sequential compatibility execution"), _stamp("finalize", "success", "Result assembled")], "checkpointing": "disabled in fallback mode"}
        result["agent_trace"] = _agent_trace(result)
        from data_pilot.tracking import log_with_mlflow
        result["mlflow"] = log_with_mlflow(dataset_name, result)
        return result
    def validate(state: DataPilotState):
        frame=state["dataframe"]
        if frame is None or frame.empty: return {"status":"failed","error":"Dataset is empty.","events":[_stamp("input_validation","failed","Empty dataset")]}
        if len(frame.columns)>250 or len(frame)>250000: return {"status":"failed","error":"Dataset exceeds configured dimensions.","events":[_stamp("input_validation","failed","Dataset limits exceeded")]}
        return {"status":"ready","events":[_stamp("input_validation","success","Input schema and dimensions accepted")]}
    def execute(state: DataPilotState):
        if state.get("status")!="ready": return {}
        try:
            result=_run_pipeline_core(state["dataframe"],state.get("inquiry", ""),state.get("target_column"),state.get("problem_type","unknown"),state.get("dataset_name","uploaded dataset"), progress_callback=progress_callback)
            return {"result":result,"status":"executed","events":state.get("events",[])+[_stamp("specialist_agent_pipeline","success","Planner, security, EDA, preprocessing, ML, critic, explainability, research and reporting executed by their Python components")]}
        except Exception as exc:
            return {"status":"failed","error":f"{type(exc).__name__}: {exc}","events":state.get("events",[])+[_stamp("specialist_agent_pipeline","failed",type(exc).__name__)]}
    def finalize(state: DataPilotState):
        result=state.get("result") or {}
        final_events=state.get("events",[])+[_stamp("finalize","success" if state.get("status")=="executed" else "failed","Final result assembled")]
        result["orchestration"]={"framework":"LangGraph","graph_version":"v3","status":state.get("status"),"events":final_events,"checkpointing":"in-memory per invocation; configure persistent checkpointer for multi-worker deployments"}
        result["agent_trace"]=_agent_trace(result)
        from data_pilot.tracking import log_with_mlflow
        result["mlflow"]=log_with_mlflow(state.get("dataset_name","uploaded dataset"),result)
        return {"result":result,"events":final_events}
    def route(state: DataPilotState): return "execute" if state.get("status")=="ready" else "finalize"
    graph=StateGraph(DataPilotState)
    graph.add_node("validate",validate); graph.add_node("execute",execute); graph.add_node("finalize",finalize)
    graph.set_entry_point("validate"); graph.add_conditional_edges("validate",route,{"execute":"execute","finalize":"finalize"})
    graph.add_edge("execute","finalize"); graph.add_edge("finalize",END)
    compiled = graph.compile()
    state={"dataframe":df,"inquiry":inquiry,"target_column":target_column,"problem_type":problem_type,"dataset_name":dataset_name,"events":[]}
    output = compiled.invoke(state)
    if output.get("status")=="failed": raise ValueError(output.get("error","Analysis failed"))
    return output.get("result",{})

def _agent_trace(result: dict[str,Any]) -> list[dict[str,Any]]:
    plan=result.get("plan",{}); blocked=result.get("status")=="blocked"
    items=[("Profiler",True,"Dataset schema and quality profile"),("Planner",bool(plan),"Structured analysis plan"),("Security Guardian",bool(result.get("security")),"Pre-execution policy decision"),("EDA Agent",bool(result.get("eda")),"Exploratory analysis"),("Statistics Agent",bool(result.get("statistics")),"Statistical summaries and tests"),("Preprocessing Agent",bool(result.get("preprocessing")),"Leakage-safe feature transformation"),("ML Agent",bool(result.get("models")),"Model training and evaluation"),("Critic Agent",bool(result.get("critic")),"Quality assessment and retry decision"),("Replanner Agent",bool(result.get("replanning",{}).get("history")),"Bounded retry after critic feedback"),("Explainability Agent",bool(result.get("explainability")),"Model interpretation"),("Research Agent",bool(result.get("research")),"Methodology and retrieved evidence"),("Reporting Agent",bool(result.get("report")),"Final report generation")]
    trace=[]
    for name,ran,detail in items:
        status="blocked" if blocked and name not in {"Profiler","Planner","Security Guardian"} else ("completed" if ran else "skipped")
        trace.append({"agent":name,"status":status,"detail":detail})
    return trace


def run_v4_analytics_graph(df, inquiry: str, analytics_type: str | None = None) -> dict[str, Any]:
    """Route a natural-language analytics request through explicit V4 graph nodes."""
    from typing import TypedDict
    from data_pilot.llm.intent import understand_intent
    from data_pilot.analytics import run_analytics

    class AnalyticsState(TypedDict, total=False):
        dataframe: Any
        inquiry: str
        requested_type: str | None
        plan: dict[str, Any]
        result: dict[str, Any]
        status: str
        events: list[dict[str, Any]]

    def understand(state: AnalyticsState):
        plan = understand_intent(state["inquiry"], [str(c) for c in state["dataframe"].columns])
        if state.get("requested_type"):
            plan["analytics_type"] = state["requested_type"]
        return {"plan": plan, "events": [_stamp("intent_understanding", "success", plan.get("analytics_type", "unknown"))]}

    def validate(state: AnalyticsState):
        plan = state.get("plan", {})
        if plan.get("analytics_type") not in {"descriptive", "diagnostic", "predictive", "prescriptive"}:
            return {"status": "failed", "events": state.get("events", []) + [_stamp("plan_validation", "failed", "Unsupported analytics type")]}
        return {"status": "ready", "events": state.get("events", []) + [_stamp("plan_validation", "success", "Structured plan accepted")]}

    def execute(kind: str):
        def node(state: AnalyticsState):
            plan = dict(state["plan"])
            plan["analytics_type"] = kind
            result = run_analytics(state["dataframe"], plan)
            return {"result": result["result"], "status": "completed",
                    "events": state.get("events", []) + [_stamp(f"{kind}_analytics", "success", "Deterministic analytics engine executed")]}
        return node

    def finalize(state: AnalyticsState):
        return {"events": state.get("events", []) + [_stamp("finalize", state.get("status", "failed"), "V4 analytics result assembled")]}

    if not LANGGRAPH_AVAILABLE:
        plan = understand_intent(inquiry, [str(c) for c in df.columns])
        if analytics_type:
            plan["analytics_type"] = analytics_type
        result = run_analytics(df, plan)["result"]
        return {"plan": plan, "result": result, "status": "completed",
                "orchestration": {"framework": "python_fallback", "graph_version": "v4-analytics",
                                  "events": [_stamp("intent_understanding","success",plan["analytics_type"]),
                                             _stamp("analytics_execution","success","Deterministic Python engine")]}}

    graph = StateGraph(AnalyticsState)
    graph.add_node("understand", understand)
    graph.add_node("validate", validate)
    graph.add_node("descriptive", execute("descriptive"))
    graph.add_node("diagnostic", execute("diagnostic"))
    graph.add_node("predictive", execute("predictive"))
    graph.add_node("prescriptive", execute("prescriptive"))
    graph.add_node("finalize", finalize)
    graph.set_entry_point("understand")
    graph.add_edge("understand", "validate")
    # Do not annotate this nested callback with the function-local TypedDict.
    # LangGraph introspects callback annotations via get_type_hints(), where a
    # local AnalyticsState name is not resolvable on Python 3.13 / newer LangGraph.
    def route(state):
        if state.get("status") != "ready":
            return "finalize"
        return state["plan"]["analytics_type"]
    graph.add_conditional_edges("validate", route, {
        "descriptive":"descriptive", "diagnostic":"diagnostic",
        "predictive":"predictive", "prescriptive":"prescriptive", "finalize":"finalize"})
    for node in ("descriptive","diagnostic","predictive","prescriptive"):
        graph.add_edge(node, "finalize")
    graph.add_edge("finalize", END)
    compiled=graph.compile()
    out=compiled.invoke({"dataframe":df,"inquiry":inquiry,"requested_type":analytics_type,"events":[]})
    return {"plan":out.get("plan",{}),"result":out.get("result",{}),"status":out.get("status","completed"),
            "orchestration":{"framework":"LangGraph","graph_version":"v4-analytics","events":out.get("events",[])}}
