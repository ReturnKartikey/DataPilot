"""Deterministic Pandas query executor for validated natural-language intent plans.

LLM intent parsing produces a declarative, schema-validated JSON plan (filters,
operation, metric_column, group_by, limit). This module executes that plan
deterministically on the DataFrame without ever running generated code.
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


def _apply_filters(df: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
    if not filters:
        return df
    mask = pd.Series(True, index=df.index)
    for item in filters:
        col = item.get("column")
        op = item.get("op", "eq")
        val = item.get("value")
        if not col or col not in df.columns:
            continue
        series = df[col]
        if op in {"gt", "gte", "lt", "lte"}:
            num_series = pd.to_numeric(series, errors="coerce")
            try:
                threshold = float(val)
            except (TypeError, ValueError):
                continue
            if op == "gt":
                mask &= num_series > threshold
            elif op == "gte":
                mask &= num_series >= threshold
            elif op == "lt":
                mask &= num_series < threshold
            elif op == "lte":
                mask &= num_series <= threshold
        elif op in {"eq", "neq"}:
            if pd.api.types.is_numeric_dtype(series) and isinstance(val, (int, float)) and not isinstance(val, bool):
                cond = series == val
            else:
                target_cf = str(val).strip().casefold()
                cond = series.astype(str).str.strip().str.casefold() == target_cf
                cond &= series.notna()
            mask &= cond if op == "eq" else ~cond
        elif op == "contains":
            target_cf = str(val).strip().casefold()
            cond = series.dropna().astype(str).str.casefold().str.contains(target_cf, regex=False)
            mask &= cond.reindex(df.index, fill_value=False)
    return df.loc[mask]


def _format_filter_label(filters: list[dict[str, Any]]) -> str:
    if not filters:
        return ""
    op_symbols = {"eq": "=", "neq": "≠", "gt": ">", "gte": "≥", "lt": "<", "lte": "≤", "contains": "~"}
    return ", ".join(f"{f['column']} {op_symbols.get(f['op'], f['op'])} {f['value']}" for f in filters)


def _explode_if_multivalue(series: pd.Series) -> tuple[pd.Series, bool]:
    clean = series.dropna().astype(str).str.strip()
    comma_share = float(clean.str.contains(",", regex=False).mean()) if len(clean) else 0.0
    if comma_share >= 0.15:
        clean = clean.str.split(r"\s*,\s*").explode().str.strip()
        return clean[clean.ne("")], True
    return clean[clean.ne("")], False


def execute_question_plan(df: pd.DataFrame, plan: dict[str, Any]) -> dict[str, Any] | None:
    """Execute a validated question-answering plan and return computed results."""
    if df.empty:
        return None

    question = str(plan.get("question") or "").strip()
    operation = str(plan.get("operation") or "none").lower()
    filters = list(plan.get("filters") or [])
    group_by = plan.get("group_by") if plan.get("group_by") in df.columns else None
    metric_col = plan.get("metric_column") if plan.get("metric_column") in df.columns else None
    focus_col = (
        plan.get("column")
        if plan.get("column") in df.columns
        else (plan.get("target") if plan.get("target") in df.columns else None)
    )
    limit = max(1, min(50, int(plan.get("limit") or 10)))
    ascending = str(plan.get("objective") or "maximize").lower() == "minimize"

    total_rows = int(len(df))
    filtered = _apply_filters(df, filters)
    matched_rows = int(len(filtered))
    filter_summary = _format_filter_label(filters)

    # 1. Grouped aggregation or grouped counts
    if group_by and (metric_col or operation in {"mean", "median", "sum", "min", "max", "count", "top_k", "distribution"}):
        if metric_col and pd.api.types.is_numeric_dtype(filtered[metric_col]) and operation in {"mean", "median", "sum", "min", "max"}:
            agg_fn = operation
            grouped = (
                filtered.groupby(group_by, dropna=False)[metric_col]
                .agg(["count", agg_fn])
                .dropna(subset=[agg_fn])
                .reset_index()
                .sort_values(agg_fn, ascending=ascending)
                .head(limit)
            )
            rows = [
                {
                    "label": str(r[group_by]) if pd.notna(r[group_by]) else "(missing)",
                    "value": round(float(r[agg_fn]), 4),
                    "count": int(r["count"]),
                }
                for _, r in grouped.iterrows()
            ]
            if rows:
                top = rows[0]
                return {
                    "question": question,
                    "task_mode": plan.get("task_mode", "question_answering"),
                    "operation": operation,
                    "answer_type": "grouped_metric",
                    "category": f"{top['label']} ({operation} {metric_col}: {top['value']:,.2f})",
                    "answer_label": f"{operation.title()} {metric_col} by {group_by}",
                    "answer_value": top["value"],
                    "count": matched_rows,
                    "total": total_rows,
                    "percentage": round((matched_rows / total_rows) * 100, 2) if total_rows else 0.0,
                    "target_column": group_by,
                    "metric_column": metric_col,
                    "filters_applied": filters,
                    "rows": rows,
                    "planner_provider": plan.get("provider", "deterministic_fallback"),
                    "summary": (
                        f"Across {matched_rows:,} matching rows"
                        + (f" ({filter_summary})" if filter_summary else "")
                        + f", {group_by} = '{top['label']}' has the {'lowest' if ascending else 'highest'} {operation} {metric_col} ({top['value']:,.2f})."
                    ),
                    "chart": {
                        "id": "question-grouped-metric",
                        "type": "bar",
                        "title": f"{operation.title()} {metric_col} by {group_by}",
                        "data": [{"label": r["label"], "value": r["value"]} for r in rows],
                    },
                }

        # Grouped counts on group_by
        exploded, was_split = _explode_if_multivalue(filtered[group_by])
        counts = exploded.value_counts().head(limit)
        denom = int(len(exploded)) if was_split else max(1, matched_rows)
        rows = [
            {
                "label": str(k),
                "value": int(v),
                "count": int(v),
                "percentage": round(int(v) / denom * 100, 2) if denom else 0.0,
            }
            for k, v in counts.items()
        ]
        if rows:
            top = rows[0]
            return {
                "question": question,
                "task_mode": plan.get("task_mode", "question_answering"),
                "operation": operation if operation != "none" else "count",
                "answer_type": "grouped_count",
                "category": top["label"],
                "count": int(top["count"]),
                "total": denom,
                "percentage": float(top["percentage"]),
                "target_column": group_by,
                "filters_applied": filters,
                "rows": rows,
                "planner_provider": plan.get("provider", "deterministic_fallback"),
                "summary": (
                    f"Top {group_by} category"
                    + (f" where {filter_summary}" if filter_summary else "")
                    + f": '{top['label']}' with {top['count']:,} records ({top['percentage']:.2f}%)."
                ),
                "chart": {
                    "id": "question-grouped-count",
                    "type": "bar",
                    "title": f"Breakdown by {group_by}" + (f" ({filter_summary})" if filter_summary else ""),
                    "data": [{"label": r["label"], "value": r["count"], "percentage": r["percentage"]} for r in rows],
                },
            }

    # 2. Scalar numeric aggregation (mean/median/sum/min/max) on filtered or full dataset
    if metric_col and pd.api.types.is_numeric_dtype(filtered[metric_col]) and operation in {"mean", "median", "sum", "min", "max"}:
        series = pd.to_numeric(filtered[metric_col], errors="coerce").dropna()
        if len(series) > 0:
            agg_funcs = {
                "mean": float(series.mean()),
                "median": float(series.median()),
                "sum": float(series.sum()),
                "min": float(series.min()),
                "max": float(series.max()),
            }
            val = round(agg_funcs[operation], 4)
            return {
                "question": question,
                "task_mode": plan.get("task_mode", "question_answering"),
                "operation": operation,
                "answer_type": "scalar_metric",
                "category": f"{operation.title()} {metric_col}: {val:,.2f}",
                "answer_value": val,
                "count": int(len(series)),
                "total": total_rows,
                "percentage": round((len(series) / total_rows) * 100, 2) if total_rows else 0.0,
                "target_column": metric_col,
                "filters_applied": filters,
                "rows": [],
                "planner_provider": plan.get("provider", "deterministic_fallback"),
                "summary": (
                    f"{operation.title()} of {metric_col}"
                    + (f" where {filter_summary}" if filter_summary else "")
                    + f" is {val:,.2f} across {len(series):,} non-missing records."
                ),
            }

    # 3. Filtered count / percentage query (e.g., "Get me the number of students not placed")
    if filters:
        pct = round((matched_rows / total_rows) * 100, 2) if total_rows else 0.0
        primary_filter = filters[0]
        label_display = (
            str(primary_filter["value"])
            if len(filters) == 1 and primary_filter["op"] == "eq"
            else filter_summary
        )
        source_col = primary_filter["column"]
        # Build clean distribution chart of the primary filter column on full dataset if low-cardinality
        chart = None
        if source_col in df.columns and df[source_col].nunique(dropna=True) <= 15:
            vc = df[source_col].dropna().astype(str).value_counts()
            vc_total = int(vc.sum()) or 1
            chart = {
                "id": "question-filter-distribution",
                "type": "bar",
                "title": f"Distribution — {source_col}",
                "data": [
                    {"label": str(k), "value": int(v), "percentage": round(int(v) / vc_total * 100, 2)}
                    for k, v in vc.items()
                ],
            }
        return {
            "question": question,
            "task_mode": plan.get("task_mode", "question_answering"),
            "operation": operation if operation in {"count", "percentage"} else "count",
            "answer_type": "filtered_count",
            "category": label_display,
            "raw_label": label_display,
            "count": matched_rows,
            "total": total_rows,
            "percentage": pct,
            "target_column": source_col,
            "filters_applied": filters,
            "rows": [],
            "planner_provider": plan.get("provider", "deterministic_fallback"),
            "summary": f"{matched_rows:,} out of {total_rows:,} records ({pct:.2f}%) match {filter_summary}.",
            "chart": chart,
        }

    # 4. Unfiltered ranking / top-k / highest-frequency category on focus_col
    if focus_col and focus_col in df.columns and operation in {"top_k", "max", "min", "distribution", "count", "percentage"}:
        exploded, was_split = _explode_if_multivalue(df[focus_col])
        if len(exploded) > 0:
            vc = exploded.value_counts()
            if operation == "min":
                vc = vc.sort_values(ascending=True)
            vc_top = vc.head(limit)
            denom = int(len(exploded)) if was_split else int(df[focus_col].notna().sum()) or total_rows
            rows = [
                {
                    "label": str(k),
                    "value": int(v),
                    "count": int(v),
                    "percentage": round(int(v) / denom * 100, 2) if denom else 0.0,
                }
                for k, v in vc_top.items()
            ]
            top = rows[0]
            return {
                "question": question,
                "task_mode": plan.get("task_mode", "question_answering"),
                "operation": operation,
                "answer_type": "highest_frequency_category" if operation == "max" else "distribution",
                "category": top["label"],
                "raw_label": top["label"],
                "count": int(top["count"]),
                "total": denom,
                "percentage": float(top["percentage"]),
                "target_column": focus_col,
                "filters_applied": [],
                "rows": rows,
                "planner_provider": plan.get("provider", "deterministic_fallback"),
                "summary": f"'{top['label']}' in {focus_col} has {top['count']:,} records ({top['percentage']:.2f}% of {denom:,}).",
                "chart": {
                    "id": "question-column-distribution",
                    "type": "bar",
                    "title": f"Top categories — {focus_col}",
                    "data": [{"label": r["label"], "value": r["count"], "percentage": r["percentage"]} for r in rows],
                },
            }

    return None
