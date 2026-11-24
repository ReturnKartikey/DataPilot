"""Safe, deterministic analytics operations. LLMs may propose intent; this module computes results."""
from __future__ import annotations
from typing import Any
import re
import numpy as np
import pandas as pd

SUPPORTED = {"descriptive", "diagnostic", "predictive", "prescriptive"}

def _resolve_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lookup = {str(c).strip().lower(): str(c) for c in df.columns}
    for c in candidates:
        if c.lower() in lookup: return lookup[c.lower()]
    for c in candidates:
        for existing in df.columns:
            if c.lower() in str(existing).lower(): return str(existing)
    return None

def _top_values(series: pd.Series, limit: int = 15):
    counts = series.astype("string").fillna("(missing)").value_counts().head(limit)
    return [{"value": str(k), "count": int(v)} for k,v in counts.items()]

def descriptive(df: pd.DataFrame, plan: dict[str,Any]) -> dict[str,Any]:
    requested = plan.get("column")
    column = _resolve_column(df, [requested]) if requested else None
    group = _resolve_column(df, [plan["group_by"]]) if plan.get("group_by") else None
    numeric = df.select_dtypes(include="number")
    result: dict[str,Any] = {
        "analytics_type":"descriptive",
        "dataset":{"rows":int(len(df)),"columns":int(len(df.columns)),"column_names":[str(c) for c in df.columns]},
        "missing_values":{str(k):int(v) for k,v in df.isna().sum().items()},
        "duplicate_rows":int(df.duplicated().sum()),
        "numeric_summary":numeric.describe().replace({np.nan:None}).to_dict(),
    }
    if column:
        result["column"] = column
        if pd.api.types.is_numeric_dtype(df[column]):
            result["distribution"] = {"count":int(df[column].count()),"mean":float(df[column].mean()) if df[column].notna().any() else None,
                "median":float(df[column].median()) if df[column].notna().any() else None,
                "min":float(df[column].min()) if df[column].notna().any() else None,
                "max":float(df[column].max()) if df[column].notna().any() else None}
            counts, edges = np.histogram(df[column].dropna().astype(float), bins=min(20,max(5,int(np.sqrt(max(1,df[column].notna().sum())))))) if df[column].notna().any() else ([],[])
            result["histogram"]={"counts":[int(x) for x in counts],"bin_edges":[float(x) for x in edges]}
        else:
            result["value_counts"] = _top_values(df[column], int(plan.get("limit",15)))
    if group and column and pd.api.types.is_numeric_dtype(df[column]):
        result["grouped_summary"] = df.groupby(group,dropna=False)[column].agg(["count","mean","sum","median"]).reset_index().replace({np.nan:None}).to_dict("records")
    elif group:
        result["grouped_counts"] = df[group].astype("string").fillna("(missing)").value_counts().head(30).to_dict()
    return result

def diagnostic(df: pd.DataFrame, plan: dict[str,Any]) -> dict[str,Any]:
    target = _resolve_column(df,[plan["target"]]) if plan.get("target") else None
    group = _resolve_column(df,[plan["group_by"]]) if plan.get("group_by") else None
    numeric = df.select_dtypes(include="number")
    corr = numeric.corr(numeric_only=True).replace({np.nan:None}).to_dict()
    result={"analytics_type":"diagnostic","correlations":corr,"investigated_target":target,"group_by":group,
            "interpretation_boundary":"Associations and group differences are diagnostic clues, not proof of causation."}
    if target and group:
        if pd.api.types.is_numeric_dtype(df[target]):
            result["group_comparison"]=df.groupby(group,dropna=False)[target].agg(["count","mean","median","std"]).reset_index().replace({np.nan:None}).to_dict("records")
        else:
            result["group_comparison"]=pd.crosstab(df[group].fillna("(missing)").astype(str),df[target].fillna("(missing)").astype(str)).to_dict()
    elif target and pd.api.types.is_numeric_dtype(df[target]):
        result["target_summary"]={"mean":float(df[target].mean()),"median":float(df[target].median()),"std":float(df[target].std()) if df[target].notna().sum()>1 else None}
    return result

def predictive(df: pd.DataFrame, plan: dict[str,Any]) -> dict[str,Any]:
    target = _resolve_column(df,[plan["target"]]) if plan.get("target") else None
    if not target:
        return {"analytics_type":"predictive","status":"needs_target","message":"Specify a target column to train a supervised predictive model. Forecasting requires a time column and a value column."}
    # Reuse existing ML pipeline for supervised learning, but do not recursively call it here.
    from data_pilot.pipeline import run_pipeline
    outcome=run_pipeline(df, inquiry=plan.get("question",""), target_column=target, problem_type=plan.get("problem_type","unknown"), dataset_name=plan.get("dataset_name","analytics dataset"))
    return {"analytics_type":"predictive","target":target,"pipeline_result":outcome}

def prescriptive(df: pd.DataFrame, plan: dict[str,Any]) -> dict[str,Any]:
    objective=plan.get("objective","maximize")
    variable=_resolve_column(df,[plan["decision_variable"]]) if plan.get("decision_variable") else None
    value=_resolve_column(df,[plan["value_column"]]) if plan.get("value_column") else None
    budget=plan.get("budget")
    if not variable or not value:
        return {"analytics_type":"prescriptive","status":"needs_inputs",
                "message":"Prescriptive optimization needs a decision variable and an outcome/value column, plus optional business constraints.",
                "required_inputs":["decision_variable","value_column","constraints"]}
    frame=df[[variable,value]].copy()
    frame[value]=pd.to_numeric(frame[value],errors="coerce")
    summary=frame.groupby(variable,dropna=False)[value].agg(["count","mean","sum"]).dropna().reset_index()
    ascending = str(objective).lower() in {"minimize","minimise","min"}
    summary=summary.sort_values("mean",ascending=ascending)
    recommendations=summary.head(int(plan.get("limit",10))).replace({np.nan:None}).to_dict("records")
    return {"analytics_type":"prescriptive","status":"scenario_recommendations","objective":objective,
            "decision_variable":variable,"outcome":value,"budget_constraint":budget,
            "ranked_options":recommendations,
            "method":"Observed historical outcome ranking; this is not causal optimization. Add explicit costs, constraints and response models for mathematically optimal recommendations."}

def run_analytics(df: pd.DataFrame, plan: dict[str,Any]) -> dict[str,Any]:
    kind=str(plan.get("analytics_type","descriptive")).lower()
    if kind not in SUPPORTED: raise ValueError(f"Unsupported analytics type: {kind}")
    if df.empty: raise ValueError("Dataset is empty")
    return {"status":"completed","result": {"descriptive":descriptive,"diagnostic":diagnostic,"predictive":predictive,"prescriptive":prescriptive}[kind](df,plan)}
