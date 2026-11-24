"""LLM intent parsing and structured query planning.

Outputs a constrained, schema-validated declarative plan; never executes
model-generated code.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

ALLOWED_OPS = {"eq", "neq", "gt", "gte", "lt", "lte", "contains"}
ALLOWED_OPERATIONS = {
    "count",
    "percentage",
    "mean",
    "median",
    "sum",
    "min",
    "max",
    "distribution",
    "top_k",
    "correlation",
    "none",
}
ALLOWED_TASK_MODES = {"question_answering", "predictive_ml"}


def build_schema_context(df) -> dict[str, Any]:
    """Build a compact schema + low-cardinality distinct values summary without raw PII rows."""
    columns_info: list[dict[str, Any]] = []
    for col in list(df.columns)[:40]:
        name = str(col)
        series = df[col]
        non_null = series.dropna()
        entry: dict[str, Any] = {
            "name": name,
            "kind": "numeric" if str(series.dtype).startswith(("int", "float", "uint")) else "categorical",
            "unique_count": int(non_null.nunique()),
        }
        if entry["kind"] == "numeric" and len(non_null) > 0:
            try:
                entry["min"] = round(float(non_null.min()), 4)
                entry["max"] = round(float(non_null.max()), 4)
                entry["mean"] = round(float(non_null.mean()), 4)
            except Exception:
                pass
        elif entry["unique_count"] <= 25:
            counts = non_null.astype(str).str.strip().value_counts().head(20)
            entry["values"] = [str(v) for v in counts.index.tolist() if str(v)]
        columns_info.append(entry)
    return {"rows": int(len(df)), "columns": columns_info}


def _resolve_column_name(candidate: Any, columns: list[str]) -> str | None:
    if not isinstance(candidate, str) or not candidate.strip():
        return None
    if candidate in columns:
        return candidate
    lookup = {str(c).strip().casefold(): str(c) for c in columns}
    return lookup.get(candidate.strip().casefold())


def _canonicalize_filter_value(column: str, op: str, value: Any, schema_context: dict[str, Any] | None) -> Any:
    if op in {"gt", "gte", "lt", "lte"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if isinstance(value, str) and schema_context:
        col_meta = next((c for c in schema_context.get("columns", []) if c.get("name") == column), None)
        if col_meta and col_meta.get("values"):
            val_cf = value.strip().casefold()
            for observed in col_meta["values"]:
                if observed.strip().casefold() == val_cf:
                    return observed
    return value


def validate_intent_plan(
    raw_plan: dict[str, Any],
    question: str,
    columns: list[str],
    schema_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and normalize an intent + query plan against dataset columns."""
    plan = dict(raw_plan or {})
    allowed_analytics = {"descriptive", "diagnostic", "predictive", "prescriptive"}
    if plan.get("analytics_type") not in allowed_analytics:
        plan["analytics_type"] = "descriptive"

    if plan.get("task_mode") not in ALLOWED_TASK_MODES:
        plan["task_mode"] = "predictive_ml" if plan["analytics_type"] == "predictive" else "question_answering"

    if plan.get("operation") not in ALLOWED_OPERATIONS:
        plan["operation"] = "none"

    for keyname in ("target", "column", "metric_column", "group_by"):
        plan[keyname] = _resolve_column_name(plan.get(keyname), columns)

    if plan.get("problem_type") not in {"unknown", "classification", "regression"}:
        plan["problem_type"] = "unknown"

    if plan.get("objective") not in {"maximize", "minimize"}:
        plan["objective"] = "maximize"

    try:
        limit = int(plan.get("limit", 10) or 10)
    except (TypeError, ValueError):
        limit = 10
    plan["limit"] = max(1, min(50, limit))

    clean_filters: list[dict[str, Any]] = []
    for item in (plan.get("filters") or [])[:10]:
        if not isinstance(item, dict):
            continue
        col = _resolve_column_name(item.get("column"), columns)
        op = str(item.get("op", "eq")).lower()
        val = item.get("value")
        if not col or op not in ALLOWED_OPS or val is None or val == "":
            continue
        clean_filters.append({
            "column": col,
            "op": op,
            "value": _canonicalize_filter_value(col, op, val, schema_context),
        })
    plan["filters"] = clean_filters
    plan["question"] = question
    return plan


def _fallback(
    question: str,
    columns: list[str],
    schema_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    q = (question or "").strip()
    q_cf = q.casefold()

    explicit_ml = any(
        re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", q_cf)
        for term in ("predict", "prediction", "forecast", "classify", "classification", "regression", "train", "modeling", "estimate")
    ) and not any(
        term in q_cf for term in ("how many", "number of", "count ", "percentage", "percent", "average", "mean", "median", "sum ", "total ")
    )

    kind = "descriptive"
    if any(w in q_cf for w in ("why", "reason", "cause", "decline", "contribut", "correlat", "factor")):
        kind = "diagnostic"
    if explicit_ml:
        kind = "predictive"
    if any(w in q_cf for w in ("recommend", "optimize", "optimise", "allocate", "what should", "budget")):
        kind = "prescriptive"

    task_mode = "predictive_ml" if (explicit_ml or not q) else "question_answering"

    # Detect aggregation operation
    operation = "none"
    if any(re.search(r"(?<![a-z0-9])" + w + r"(?![a-z0-9])", q_cf) for w in ("average", "mean", "avg")):
        operation = "mean"
    elif "median" in q_cf:
        operation = "median"
    elif any(re.search(r"(?<![a-z0-9])" + w + r"(?![a-z0-9])", q_cf) for w in ("sum", "total")):
        operation = "sum"
    elif any(w in q_cf for w in ("minimum", "lowest", "smallest", "min ")):
        operation = "min"
    elif any(w in q_cf for w in ("maximum", "highest", "largest", "most ", "max ")):
        operation = "max"
    elif any(w in q_cf for w in ("percentage", "percent", "share", "proportion", "rate")):
        operation = "percentage"
    elif re.search(r"\btop\s+\d{1,2}\b", q_cf):
        operation = "top_k"
    elif any(w in q_cf for w in ("how many", "number of", "count")):
        operation = "count"
    elif any(w in q_cf for w in ("distribution", "breakdown", "chart", "pie", "bar", "plot")):
        operation = "distribution"

    top_match = re.search(r"\btop\s+(\d{1,2})\b", q_cf)
    limit = min(50, max(1, int(top_match.group(1)))) if top_match else 10

    # Longest-first exact column mentions
    mentioned_cols = sorted(
        [c for c in columns if re.search(r"(?<![a-z0-9_])" + re.escape(c.casefold()) + r"(?![a-z0-9_])", q_cf)],
        key=len,
        reverse=True,
    )

    numeric_cols = {
        c["name"] for c in (schema_context or {}).get("columns", []) if c.get("kind") == "numeric"
    }
    metric_column = next((c for c in mentioned_cols if c in numeric_cols), None)

    # Longest-first exact observed categorical value matches -> filters
    filters: list[dict[str, Any]] = []
    filter_col: str | None = None
    if schema_context:
        candidates: list[tuple[int, str, str]] = []
        for col_meta in schema_context.get("columns", []):
            for val in col_meta.get("values") or []:
                val_s = str(val).strip()
                if val_s:
                    candidates.append((len(val_s), col_meta["name"], val_s))
        candidates.sort(key=lambda item: item[0], reverse=True)
        matched_spans: list[tuple[int, int]] = []
        for _, col_name, val_s in candidates:
            pattern = r"(?<![a-z0-9])" + re.escape(val_s.casefold()).replace(r"\ ", r"[\s_-]+") + r"(?![a-z0-9])"
            m = re.search(pattern, q_cf)
            if m and not any(not (m.end() <= s or m.start() >= e) for s, e in matched_spans):
                if not any(f["column"] == col_name for f in filters):
                    filters.append({"column": col_name, "op": "eq", "value": val_s})
                    matched_spans.append((m.start(), m.end()))
                    if filter_col is None:
                        filter_col = col_name

    # Numeric threshold filters like "salary > 250000" or "mba_p >= 70"
    for col in mentioned_cols:
        if col in numeric_cols:
            num_pat = (
                r"(?<![a-z0-9_])"
                + re.escape(col.casefold())
                + r"\s*(>=|<=|>|<|=|above|over|greater than|more than|below|under|less than)\s*(\d+(?:\.\d+)?)"
            )
            nm = re.search(num_pat, q_cf)
            if nm:
                op_raw, num_val = nm.group(1), float(nm.group(2))
                op_map = {
                    ">=": "gte", "<=": "lte", ">": "gt", "<": "lt", "=": "eq",
                    "above": "gt", "over": "gt", "greater than": "gt", "more than": "gt",
                    "below": "lt", "under": "lt", "less than": "lt",
                }
                filters.append({"column": col, "op": op_map[op_raw], "value": num_val})

    group_by = None
    group_match = re.search(r"\b(?:by|per|across|for each)\s+([a-z0-9_ -]{2,40})", q_cf)
    if group_match:
        tail = group_match.group(1)
        group_by = next((c for c in columns if re.search(r"(?<![a-z0-9_])" + re.escape(c.casefold()) + r"(?![a-z0-9_])", tail)), None)
    if not group_by:
        group_by = next((c for c in mentioned_cols if c != metric_column and c != filter_col), None)

    target = filter_col or (mentioned_cols[0] if mentioned_cols else None)
    column = metric_column or target

    return validate_intent_plan(
        {
            "analytics_type": kind,
            "task_mode": task_mode,
            "operation": operation,
            "target": target,
            "column": column,
            "metric_column": metric_column,
            "group_by": group_by,
            "filters": filters,
            "problem_type": "unknown",
            "objective": "minimize" if operation == "min" else "maximize",
            "limit": limit,
            "provider": "deterministic_fallback",
            "notice": "LLM unavailable; intent was inferred using conservative keyword matching. Review the plan.",
        },
        question,
        columns,
        schema_context,
    )


def _call_openai(key, model, question, columns, schema_context: dict[str, Any] | None = None):
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
    default_base = "https://openrouter.ai/api/v1" if provider == "openrouter" else "https://api.openai.com/v1"
    base = (os.getenv("LLM_BASE_URL") or default_base).rstrip("/")
    schema = {
        "type": "object",
        "properties": {
            "analytics_type": {"type": "string", "enum": ["descriptive", "diagnostic", "predictive", "prescriptive"]},
            "task_mode": {"type": "string", "enum": ["question_answering", "predictive_ml"]},
            "operation": {
                "type": "string",
                "enum": ["count", "percentage", "mean", "median", "sum", "min", "max", "distribution", "top_k", "correlation", "none"],
            },
            "target": {"type": ["string", "null"]},
            "column": {"type": ["string", "null"]},
            "metric_column": {"type": ["string", "null"]},
            "group_by": {"type": ["string", "null"]},
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "op": {"type": "string", "enum": ["eq", "neq", "gt", "gte", "lt", "lte", "contains"]},
                        "value": {"type": ["string", "number", "boolean"]},
                    },
                    "required": ["column", "op", "value"],
                    "additionalProperties": False,
                },
            },
            "problem_type": {"type": "string", "enum": ["unknown", "classification", "regression"]},
            "objective": {"type": "string", "enum": ["maximize", "minimize"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "required": [
            "analytics_type",
            "task_mode",
            "operation",
            "target",
            "column",
            "metric_column",
            "group_by",
            "filters",
            "problem_type",
            "objective",
            "limit",
        ],
        "additionalProperties": False,
    }
    prompt = {
        "question": question,
        "available_columns": columns,
        "schema_summary": schema_context or {"columns": [{"name": c} for c in columns]},
        "instructions": (
            "Route the user's question to either 'question_answering' (direct counts, percentages, filters, averages, group-bys, rankings, charts) "
            "or 'predictive_ml' (only when the user asks to predict, forecast, classify, or train/evaluate predictive models). "
            "When the question asks about specific category values (for example 'not placed', 'churned', 'Science'), map them to exact observed values in schema_summary.columns[].values inside 'filters' using exact column names. "
            "Pay careful attention to negation like 'not placed' vs 'placed'. "
            "For row counts (e.g. 'how many students not placed'), set operation='count' and metric_column=null. "
            "Set metric_column only when computing mean/median/sum/min/max on a numeric column. "
            "Set group_by when comparing across groups (e.g. 'by gender' or 'per region'). "
            "Never invent columns or values, and never compute numbers yourself."
        ),
        "output_format": (
            "Return one valid JSON object matching this exact structure and allowed values: "
            + json.dumps({
                "analytics_type": "descriptive | diagnostic | predictive | prescriptive",
                "task_mode": "question_answering | predictive_ml",
                "operation": "count | percentage | mean | median | sum | min | max | distribution | top_k | correlation | none",
                "target": "<exact column name or null>",
                "column": "<exact column name or null>",
                "metric_column": "<exact numeric column name or null>",
                "group_by": "<exact column name or null>",
                "filters": [{"column": "<exact column name>", "op": "eq | neq | gt | gte | lt | lte | contains", "value": "<exact value>"}],
                "problem_type": "unknown | classification | regression",
                "objective": "maximize | minimize",
                "limit": 10,
            })
        ),
    }
    response_format = (
        {"type": "json_schema", "json_schema": {"name": "analytics_intent", "strict": True, "schema": schema}}
        if os.getenv("LLM_RESPONSE_FORMAT", "json_object").lower() == "json_schema"
        else {"type": "json_object"}
    )
    system_message = (
        "You are Data Pilot's analytical question router and query planner. "
        "Translate natural-language questions into a strict JSON query and routing plan grounded in the provided dataset schema and distinct category values. "
        "Distinguish direct dataset questions ('question_answering') from machine-learning requests ('predictive_ml'). "
        "Return valid JSON only. Never generate code, fabricate results, or invent column names."
    )
    body = {
        "model": model,
        "temperature": 0,
        "response_format": response_format,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
    }
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    if os.getenv("LLM_PROVIDER", "").lower() == "openrouter":
        headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173")
        headers["X-Title"] = os.getenv("OPENROUTER_APP_NAME", "Data Pilot")
    req = urllib.request.Request(base + "/chat/completions", data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=int(os.getenv("LLM_INTENT_TIMEOUT_SECONDS", "12"))) as r:
            raw = json.loads(r.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read(1200).decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM provider HTTP {exc.code}: {detail[:500]}") from exc
    return json.loads(raw["choices"][0]["message"]["content"])


def _call_gemini(key, model, question, columns, schema_context: dict[str, Any] | None = None):
    prompt = (
        "Route the user's question to a strict JSON query and routing plan grounded in the dataset schema. "
        "Return only JSON with keys: analytics_type (descriptive|diagnostic|predictive|prescriptive), "
        "task_mode (question_answering|predictive_ml), operation (count|percentage|mean|median|sum|min|max|distribution|top_k|correlation|none), "
        "target, column, metric_column, group_by (exact column names or null), "
        "filters (list of {column, op (eq|neq|gt|gte|lt|lte|contains), value}), "
        "problem_type (unknown|classification|regression), objective (maximize|minimize), limit (integer 1-50). "
        "Pay close attention to negation like 'not placed' vs 'placed' using exact observed values. Never invent columns or compute results.\n"
        "Available columns: " + json.dumps(columns) + "\n"
        "Schema summary: " + json.dumps(schema_context or {}) + "\n"
        "Question: " + question
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=int(os.getenv("LLM_INTENT_TIMEOUT_SECONDS", "12"))) as r:
        raw = json.loads(r.read())
    return json.loads(raw["candidates"][0]["content"]["parts"][0]["text"])


def understand_intent(
    question: str,
    columns: list[str],
    schema_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
    key = (
        os.getenv("GEMINI_API_KEY")
        if provider == "gemini"
        else (
            os.getenv("OPENROUTER_API_KEY")
            if provider == "openrouter"
            else (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))
        )
    )
    if not key:
        return _fallback(question, columns, schema_context=schema_context)
    model = os.getenv(
        "LLM_MODEL",
        "gemini-2.0-flash" if provider == "gemini" else ("openai/gpt-4o-mini" if provider == "openrouter" else "gpt-4o-mini"),
    )
    try:
        raw_plan = (
            _call_gemini(key, model, question, columns, schema_context=schema_context)
            if provider == "gemini"
            else _call_openai(key, model, question, columns, schema_context=schema_context)
        )
        if not isinstance(raw_plan, dict):
            raise ValueError("LLM response must be a JSON object")
        allowed = {"descriptive", "diagnostic", "predictive", "prescriptive"}
        if raw_plan.get("analytics_type") not in allowed and raw_plan.get("task_mode") not in ALLOWED_TASK_MODES:
            raise ValueError("Invalid analytics type")
        plan = validate_intent_plan(raw_plan, question, columns, schema_context=schema_context)
        plan["provider"] = provider
        return plan
    except Exception as exc:
        result = _fallback(question, columns, schema_context=schema_context)
        result["notice"] = f"LLM request failed: {str(exc)[:260]}; conservative fallback used."
        return result
