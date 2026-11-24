"""Evidence-first report generation with optional LLM-written interpretation."""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Any

from data_pilot.llm_provider import OpenAICompatibleProvider


class ReportingAgent:
    SYSTEM_PROMPT = """You are Data Pilot's report-writing assistant. You receive verified facts computed by Python.
Return one JSON object with exactly these string-array keys: executive_interpretation,
key_findings, recommendations, caveats. Use only facts in the payload. When question_answer is present, directly answer the user's dataset question using that computed category/count/percentage and explain it briefly. Do not invent
metrics, sample sizes, citations, papers, causes, model results, or data not supplied.
Do not repeat numeric metrics; those are rendered separately from verified source data.
Use retrieved research abstracts and local excerpts only when relevant to interpret methodology. Never invent paper titles, authors, DOI values, page numbers or citations. Metadata-only records are not evidence of a paper's findings. Distinguish correlation from causation. Mention uncertainty and validation limitations.
Each array should contain at most 5 concise, specific items. No markdown fences."""

    def __init__(self, provider: OpenAICompatibleProvider | None = None):
        self.provider = provider or OpenAICompatibleProvider()

    @staticmethod
    def _facts(result: dict[str, Any], dataset_name: str) -> dict[str, Any]:
        summary = result.get("dataset_summary", {})
        plan = result.get("plan", {})
        models = result.get("models", [])
        critic = result.get("critic", {})
        research = result.get("research", {})
        return {
            "dataset_name": dataset_name,
            "status": result.get("status", "unknown"),
            "rows": summary.get("rows", 0),
            "columns": summary.get("columns_count", 0),
            "column_profile": summary.get("columns", [])[:60],
            "warnings": summary.get("warnings", [])[:20],
            "objective": plan.get("goal", "Dataset exploration"),
            "question_answer": ReportingAgent._question_specific_answer(result, dataset_name),
            "problem_type": plan.get("problem_type", "unknown"),
            "target": plan.get("target_column"),
            "models": [{"name": m.get("model_name"), "metrics": m.get("metrics", {}), "validation_score": m.get("validation_score")} for m in models[:10]],
            "critic": {"score": critic.get("score"), "satisfactory": critic.get("satisfactory"), "issues": critic.get("issues", [])[:10], "recommendations": critic.get("recommendations", [])[:10]},
            "preprocessing": result.get("preprocessing", {}).get("execution", {}),
            "eda": {
                "target_column": plan.get("target_column"),
                "target_distribution": result.get("eda", {}).get("target_distribution", {}),
                "target_distribution_percentages": result.get("eda", {}).get("target_distribution_percentages", {}),
                "categorical_summary": result.get("eda", {}).get("categorical_summary", {}),
            },
            "explainability": result.get("explainability", {}),
            "research_findings": research.get("findings", [])[:10],
            "retrieved_evidence": research.get("retrieved_evidence", [])[:6],
            "research_papers": [
                {"title": source.get("title"), "authors": source.get("authors", []),
                 "year": source.get("year"), "doi": source.get("doi"),
                 "abstract": source.get("abstract") or source.get("summary"),
                 "evidence_level": source.get("evidence_level", "metadata_only"),
                 "provider": source.get("provider")}
                for source in research.get("sources", [])[:6]
            ],
            "replanning": result.get("replanning", {}),
        }

    def _llm_narrative(self, facts: dict[str, Any]) -> dict[str, list[str]] | None:
        if not self.provider.configured:
            return None
        generated = self.provider.generate_json(self.SYSTEM_PROMPT, facts)
        keys = ("executive_interpretation", "key_findings", "recommendations", "caveats")
        clean: dict[str, list[str]] = {}
        for key in keys:
            value = generated.get(key, [])
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                raise ValueError(f"Invalid LLM report field: {key}")
            clean[key] = [x.strip()[:700] for x in value[:5] if x.strip()]
        if not any(clean.values()):
            raise ValueError("LLM report narrative was empty")
        return clean

    @staticmethod
    def _question_specific_answer(result: dict[str, Any], dataset_name: str = "") -> dict[str, Any] | None:
        """Resolve requested class/category labels or structured query answers against deterministic EDA counts."""
        eda = result.get("eda", {}) or {}
        if eda.get("query_answer"):
            return eda["query_answer"]
        plan = result.get("plan", {})
        question = str(plan.get("goal", "")).casefold()
        distribution = eda.get("target_distribution", {}) or {}
        percentages = eda.get("target_distribution_percentages", {}) or {}
        if not distribution:
            return None

        # Natural-language ranking questions ("which type has the most patients?")
        # should be answered from observed category frequencies, without requiring
        # the user to name the target column explicitly.
        ranking_question = any(term in question for term in (
            "which type", "which category", "which class", "highest", "most patients",
            "most common", "largest number", "maximum number", "highest number",
        ))
        if ranking_question:
            top_label, top_count = max(distribution.items(), key=lambda item: int(item[1]))
            total = int(sum(int(v) for v in distribution.values()))
            return {
                "question": plan.get("goal", ""),
                "category": str(top_label),
                "raw_label": str(top_label),
                "count": int(top_count),
                "total": total,
                "percentage": round(float(percentages.get(top_label, (int(top_count) / total * 100) if total else 0.0)), 2),
                "target_column": plan.get("target_column") or (eda.get("requested_analysis", {}) or {}).get("column"),
                "answer_type": "highest_frequency_category",
            }

        labels = {str(k).strip().casefold(): str(k) for k in distribution}
        requested = None
        # Check longest observed category labels first so "Not Placed" beats "Placed".
        for label in sorted(distribution, key=lambda item: len(str(item).strip()), reverse=True):
            label_text = str(label).strip().casefold()
            if label_text:
                pattern = r"(?<![a-z0-9])" + re.escape(label_text).replace(r"\ ", r"[\s_-]+") + r"(?![a-z0-9])"
                if re.search(pattern, question):
                    requested = str(label)
                    break

        # Semantic aliases are only used when the uploaded dataset's labels are coded.
        # Counts and percentages always come from EDA; these aliases never encode results.
        target_name = str(plan.get("target_column") or "").casefold()
        context = (str(dataset_name) + " " + target_name + " " + question).casefold()
        aliases: dict[str, tuple[str, ...]] = {
            "poisonous": ("poisonous", "poison", "toxic", "unsafe"),
            "edible": ("edible", "safe", "non-toxic", "nontoxic"),
            "neutral": ("neutral",),
            "positive": ("positive",),
            "negative": ("negative",),
        }
        if requested is None:
            wanted = next((canonical for canonical, terms in aliases.items()
                           if any(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", question) for term in terms)), None)
            if wanted:
                for label_key, original in labels.items():
                    if label_key in aliases[wanted] or any(alias in label_key for alias in aliases[wanted]):
                        requested = original
                        break
            # Conventional one-letter class codes require domain evidence. This is
            # deliberately a label interpretation, not a hardcoded statistic.
            if requested is None and "mushroom" in context and set(labels) == {"e", "p"}:
                if any(term in question for term in ("poison", "toxic", "unsafe")):
                    requested = labels["p"]
                elif "edible" in question or "safe" in question:
                    requested = labels["e"]

        if requested is None:
            return None
        count = int(distribution.get(requested, 0))
        total = int(sum(int(v) for v in distribution.values()))
        percentage = float(percentages.get(requested, (count / total * 100) if total else 0.0))
        display = requested
        if "mushroom" in context and set(labels) == {"e", "p"}:
            display = "poisonous" if requested.casefold() == "p" else "edible"
        return {
            "question": plan.get("goal", ""),
            "category": display,
            "raw_label": requested,
            "count": count,
            "total": total,
            "percentage": round(percentage, 2),
            "target_column": plan.get("target_column") or (eda.get("requested_analysis", {}) or {}).get("column"),
        }

    @staticmethod
    def _build_charts(result: dict[str, Any]) -> list[dict[str, Any]]:
        eda = result.get("eda", {}) or {}
        charts: list[dict[str, Any]] = []
        question = str(result.get("plan", {}).get("goal", "")).casefold()
        requested_pie = any(token in question for token in ("pie chart", "pie graph", "donut chart", "doughnut chart"))
        query_chart = (eda.get("query_answer") or {}).get("chart")
        has_query_dist_chart = False
        if isinstance(query_chart, dict) and query_chart.get("data"):
            q_chart = dict(query_chart)
            if requested_pie and q_chart.get("type") == "bar":
                q_chart["type"] = "pie"
            charts.append(q_chart)
            has_query_dist_chart = q_chart.get("id") in {"question-filter-distribution", "question-column-distribution"}
        target_rows = eda.get("target_distribution_rows", [])
        if target_rows and not has_query_dist_chart:
            labels = [str(x["label"]) for x in target_rows]
            chart_rows = []
            mushroom_binary = {label.strip().lower() for label in labels} == {"e", "p"}
            for row in target_rows:
                label = str(row["label"])
                if mushroom_binary:
                    label = "Poisonous" if label.strip().lower() == "p" else "Edible"
                chart_rows.append({"label": label, "value": row["count"], "percentage": row["percentage"]})
            charts.append({"id": "target-distribution", "type": "pie" if requested_pie else "bar",
                           "title": f"Target distribution — {result.get('plan', {}).get('target_column') or 'target'}",
                           "data": chart_rows})
        elif not has_query_dist_chart:
            target_dist = eda.get("target_distribution", {}) or {}
            if target_dist:
                total = sum(int(v) for v in target_dist.values())
                charts.append({"id": "target-distribution", "type": "pie" if requested_pie else "bar", "title": "Target distribution",
                               "data": [{"label": str(k), "value": int(v), "percentage": round(int(v)/total*100, 2) if total else 0.0} for k,v in target_dist.items()]})
        for column, values in list((eda.get("categorical_summary", {}) or {}).items())[:2]:
            if values and column != result.get("plan", {}).get("target_column"):
                charts.append({"id": "category-" + str(column), "type": "bar", "title": f"Top categories — {column}",
                               "data": [{"label": str(k), "value": int(v)} for k,v in list(values.items())[:8]]})
        importance = result.get("explainability", {}).get("feature_importance", {}) or {}
        if importance:
            explanation_method = str(result.get("explainability", {}).get("method") or "")
            chart_title = "Mean absolute SHAP contribution" if explanation_method == "shap" else "Model feature importance"
            charts.append({"id": "feature-importance", "type": "bar", "title": chart_title,
                           "data": [{"label": str(k), "value": float(v)} for k,v in list(importance.items())[:10]]})
        return charts

    def generate(self, result: dict[str, Any], dataset_name: str = "uploaded dataset") -> dict[str, Any]:
        generated_at = datetime.now(timezone.utc).isoformat()
        summary = result.get("dataset_summary", {})
        plan = result.get("plan", {})
        models = result.get("models", [])
        critic = result.get("critic", {})
        security = result.get("security", {})
        best = max(models, key=lambda m: float(m.get("validation_score") or 0), default=None)
        facts = self._facts(result, dataset_name)
        question_answer = self._question_specific_answer(result, dataset_name)
        charts = self._build_charts(result)
        narrative = None
        llm_error = None
        if self.provider.configured:
            try:
                narrative = self._llm_narrative(facts)
            except Exception as exc:
                llm_error = type(exc).__name__

        lines = [
            f"# Data Pilot Analysis Report — {dataset_name}", f"Generated: {generated_at}", "",
            "## Executive summary", f"- Status: **{result.get('status', 'unknown')}**",
            f"- Dataset: {summary.get('rows', 0)} rows × {summary.get('columns_count', 0)} columns",
            f"- Objective: {plan.get('goal', 'Dataset exploration')}",
            f"- Problem type: {plan.get('problem_type', 'unknown')}",
            f"- Target: {plan.get('target_column') or 'Not selected'}", f"- Models evaluated: {len(models)}",
            f"- Critic score: {critic.get('score', 0)}", "",
        ]
        if question_answer:
            lines += ["## Direct answer to your question"]
            if question_answer.get("summary"):
                lines += [f"- {question_answer['summary']}"]
            elif question_answer.get("answer_type") == "highest_frequency_category":
                lines += [f"- **{question_answer['category']}** is the most frequent category, with **{question_answer['count']:,}** records ({question_answer['percentage']:.2f}% of {question_answer['total']:,} non-missing records)."]
            else:
                lines += [f"- **{str(question_answer['category']).capitalize()}:** {question_answer['count']:,} out of {question_answer['total']:,}.",
                          f"- **Percentage:** {question_answer['percentage']:.2f}%."]
            if question_answer.get("rows"):
                for row in question_answer["rows"][:10]:
                    pct_part = f" ({row['percentage']:.2f}%)" if row.get("percentage") is not None else ""
                    lines += [f"  - **{row['label']}**: {row['value']:,}{pct_part}" if isinstance(row.get("value"), int) else f"  - **{row['label']}**: {row['value']:,.2f}{pct_part}"]
            if question_answer.get("target_column"):
                lines += [f"- **Calculated from:** `{question_answer['target_column']}` column in the uploaded dataset.", ""]
            else:
                lines += [""]
        if narrative:
            lines += ["### LLM-assisted interpretation (narrative only)"]
            lines += [f"- {x}" for x in narrative["executive_interpretation"]]
            lines += ["", "### Key findings"] + [f"- {x}" for x in narrative["key_findings"]]
        elif self.provider.configured:
            lines += ["### Report narrative", "- LLM narrative unavailable; deterministic report retained."]
        else:
            lines += ["### Report narrative", "- LLM not configured; deterministic report retained."]
        lines += ["", "## Dataset overview", f"- Shape: {summary.get('rows', 0)} × {summary.get('columns_count', 0)}", f"- Duplicate rows detected: {summary.get('duplicate_rows', 0)}"]
        if charts:
            lines += ["", "## Visual analysis", f"- {len(charts)} data-driven chart(s) are included in the interactive report and PDF export."]
        lines += [f"- Warning: {x}" for x in summary.get("warnings", [])] or ["- No profiler warnings recorded."]
        lines += ["", "## Security review", f"- Allowed: {security.get('allowed', False)}", f"- Risk level: {security.get('risk_level', 'unknown')}", f"- Rationale: {security.get('rationale', 'Not provided')}"]
        lines += ["", "## Exploratory analysis", f"- Numeric columns: {len(result.get('eda', {}).get('numeric_columns', []))}", f"- Categorical columns: {len(result.get('eda', {}).get('categorical_columns', []))}"]
        statistics = result.get("statistics", {})
        lines += [f"- Statistical summary: {statistics.get('status', 'not available')}"]
        lines += ["", "## Preprocessing", f"- Execution: {result.get('preprocessing', {}).get('execution', {}).get('transformer', 'Not executed')}", f"- Fit scope: {result.get('preprocessing', {}).get('execution', {}).get('fit_scope', 'Not applicable')}", f"- Duplicate rows removed: {result.get('preprocessing', {}).get('execution', {}).get('duplicate_rows_removed', 0)}"]
        lines += ["", "## Model evaluation"]
        if models:
            for model in models:
                metrics = model.get("metrics", {}) or {}
                compact = {key: value for key, value in metrics.items() if key != "confusion_matrix" and isinstance(value, (int, float, str))}
                metric_text = ", ".join(f"{key.replace('_', ' ')}: {value:.4f}" if isinstance(value, float) else f"{key.replace('_', ' ')}: {value}" for key, value in compact.items())
                lines.append(f"- **{model.get('model_name')}** — validation score: {float(model.get('validation_score') or 0):.4f}; {metric_text or 'metrics not available'}")
        else:
            lines.append("No predictive model was trained. Select a valid target and problem type to enable modeling.")
        lines += ["", "## Cross-validation", f"- {result.get('cross_validation', {}).get('summary', 'Not performed')}"]
        lines += ["", "## Best available model", f"- {best.get('model_name')}" if best else "- Not available"]
        lines += ["", "## Explainability", f"- Method: {result.get('explainability', {}).get('method', 'Not available')}", f"- Best model: {result.get('explainability', {}).get('best_model', 'Not available')}"]
        lines += ["", "## Critic findings"] + [f"- {x}" for x in critic.get("issues", [])] or ["- No issues recorded."]
        lines += ["", "## Recommendations"]
        recommendations = narrative["recommendations"] if narrative and narrative["recommendations"] else critic.get("recommendations", [])
        lines += [f"- {x}" for x in recommendations] or ["- Validate the selected model on an independent dataset."]
        lines += ["", "## Research and methodology"]
        for source in result.get("research", {}).get("sources", []):
            authors = ", ".join(source.get("authors", [])) or "Authors not listed"
            lines.append(f"- **{source.get('title')}** ({source.get('year') or 'n.d.'}). {authors}. {source.get('source') or 'Crossref record'}. {source.get('url') or ''}")
        findings = result.get("research", {}).get("findings", [])
        lines += [f"- **{x.get('topic')}**: {x.get('recommendation')}" for x in findings] or ["- No research findings generated."]
        evidence = result.get("research", {}).get("retrieved_evidence", [])
        if evidence:
            lines += ["", "### Retrieved local evidence"]
            for item in evidence[:6]:
                lines.append(f"- **{item.get('title', 'Untitled source')}** — {item.get('section', 'Excerpt')}; source: {item.get('source', 'not specified')}; DOI: {item.get('doi') or 'not provided'}; relevance: {item.get('relevance')}")
                lines.append(f"  - Excerpt: {str(item.get('excerpt', ''))[:700]}")
        lines += ["", "## Limitations", "- Validation metrics are not a substitute for an independent production test set.", "- Automatic target inference can be ambiguous; verify the selected target.", "- Explanations show model behavior/associations, not causation.", "- LLM-generated narrative is interpretive; all reported metrics are computed deterministically by Python.", "- Research guidance is not a live literature review unless sources and citations are explicitly returned."]
        if narrative and narrative["caveats"]:
            lines += ["", "### Additional caveats"] + [f"- {x}" for x in narrative["caveats"]]
        llm_status = "used" if narrative else ("failed_fallback" if llm_error else "not_configured")
        return {
            "title": f"Data Pilot Analysis Report — {dataset_name}", "format": "markdown",
            "markdown": "\n".join(lines), "generated_at": generated_at,
            "llm": {"status": llm_status, "provider": "openai_compatible", "model": self.provider.model if narrative else None, "error_type": llm_error},
            "verified_facts": facts,
            "question_answer": question_answer,
            "charts": charts,
        }
