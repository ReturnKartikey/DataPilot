"""Optional MLflow experiment tracking with safe degradation when unavailable."""
from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from typing import Any

def log_with_mlflow(dataset_name: str, result: dict) -> dict:
    if os.getenv("DATAPILOT_ENABLE_MLFLOW", "false").lower() not in {"1", "true", "yes"}:
        return {"enabled": False, "status": "disabled"}
    try:
        import mlflow
        tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_NAME", "DataPilot"))
        with mlflow.start_run(run_name=dataset_name[:120]) as run:
            plan=result.get("plan",{}); summary=result.get("dataset_summary",{})
            params={"dataset_name":dataset_name[:120],"problem_type":plan.get("problem_type","unknown"),"target_column":str(plan.get("target_column") or ""),"rows":summary.get("rows",0),"columns":summary.get("columns_count",0),"orchestrator":result.get("orchestration",{}).get("framework","legacy")}
            for key,value in params.items(): mlflow.log_param(key,str(value)[:500])
            for model in result.get("models",[]):
                model_name=str(model.get("model_name","model"))[:80]
                for key,value in model.get("metrics",{}).items():
                    if isinstance(value,(int,float)) and not isinstance(value,bool):
                        mlflow.log_metric(f"{model_name}.{key}"[:250],float(value))
            # Store reproducibility context as a compact JSON artifact, excluding raw rows and secrets.
            artifact={"plan":plan,"dataset_summary":{k:v for k,v in summary.items() if k!="preview"},"models":result.get("models",[]),"cross_validation":result.get("cross_validation",{}),"critic":result.get("critic",{}),"replanning":result.get("replanning",{}),"agent_trace":result.get("agent_trace",[])}
            with tempfile.TemporaryDirectory(prefix="datapilot-mlflow-") as tmp:
                path=Path(tmp)/"analysis_metadata.json"
                path.write_text(json.dumps(artifact,ensure_ascii=False,default=str,indent=2),encoding="utf-8")
                mlflow.log_artifact(str(path),artifact_path="datapilot")
            return {"enabled":True,"status":"logged","run_id":run.info.run_id,"tracking_uri":tracking_uri,"artifacts":["datapilot/analysis_metadata.json"]}
    except Exception as exc:
        return {"enabled":True,"status":"failed","error_type":type(exc).__name__}
