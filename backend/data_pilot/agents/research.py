"""Research agent: live Crossref metadata when enabled, transparent offline fallback."""
from __future__ import annotations
import os, json, re
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .schemas import DatasetProfile, AnalysisPlan, ModelResult

class ResearchAgent:
    """Research supports methodology; it never controls the ML execution plan."""
    def __init__(self, timeout: int = 3):
        self.timeout = timeout

    @staticmethod
    def _offline_findings(profile, plan, models, preprocessing):
        findings: list[dict[str, str]] = []
        if profile.rows < 500:
            findings.append({"topic":"Small-sample validation", "finding":"The dataset is relatively small; a single holdout score may have high variance.", "recommendation":"Use repeated or stratified cross-validation before drawing strong conclusions."})
        if profile.class_imbalance_ratio is not None and profile.class_imbalance_ratio < 0.75:
            findings.append({"topic":"Class imbalance", "finding":"The profiler detected an uneven class distribution.", "recommendation":"Inspect per-class precision/recall, confusion matrix, PR-AUC, and class-weighted baselines."})
        missing = [c.name for c in profile.columns if c.missing_count]
        if missing:
            findings.append({"topic":"Missing data", "finding":f"Missing values were detected in {len(missing)} columns.", "recommendation":"Review missingness patterns and validate that median/mode imputation is appropriate for each feature."})
        if plan.problem_type == "classification":
            findings.append({"topic":"Classification evaluation", "finding":"Accuracy alone can hide minority-class failures.", "recommendation":"Compare weighted and macro F1, class-wise recall, confusion matrix, and ROC/PR curves."})
        elif plan.problem_type == "regression":
            findings.append({"topic":"Regression evaluation", "finding":"A single aggregate error metric may hide subgroup or range-specific errors.", "recommendation":"Inspect residual plots, MAE/RMSE, R², and errors across important data segments."})
        if preprocessing.get("execution", {}).get("fitted"):
            findings.append({"topic":"Preprocessing validation", "finding":"The fitted ColumnTransformer was learned on the training split only.", "recommendation":"Keep the fitted preprocessing object with the model for reproducible inference and monitor unseen categories/missingness."})
        if not models:
            findings.append({"topic":"Target selection", "finding":"No predictive models were evaluated.", "recommendation":"Choose a valid target column and explicitly specify classification or regression when automatic inference is ambiguous."})
        return findings

    @staticmethod
    def _abstract_from_inverted_index(index: dict[str, list[int]] | None) -> str:
        if not isinstance(index, dict):
            return ""
        words: dict[int, str] = {}
        for word, positions in index.items():
            for position in positions:
                words[int(position)] = word
        return " ".join(words[i] for i in sorted(words))

    @staticmethod
    def _build_query(profile: DatasetProfile, plan: AnalysisPlan, dataset_name: str = "") -> str:
        """Build a literature query from dataset domain/schema, not the user's task wording."""
        name = re.sub(r"[_-]+", " ", os.path.splitext(os.path.basename(dataset_name or ""))[0]).strip()
        name_l = name.casefold()
        columns = [c.name.casefold().replace("_", " ") for c in profile.columns]
        domain_map = {
            "netflix": "Netflix movie television streaming catalog film industry content metadata",
            "imdb": "film television movie ratings reviews entertainment industry",
            "titanic": "maritime passenger survival historical disaster dataset",
            "mushroom": "mushroom species classification ecology fungi dataset",
            "housing": "real estate housing prices property valuation dataset",
            "churn": "telecommunications customer churn retention dataset",
            "sales": "retail sales revenue forecasting business analytics dataset",
            "tweet": "social media Twitter sentiment analysis text mining dataset",
            "airline": "airline passenger sentiment customer experience dataset",
        }
        domain = next((terms for key, terms in domain_map.items() if key in name_l), "")
        if not domain:
            schema_terms = [x for x in columns if x not in {"id", "index", "description", "name"}]
            domain = " ".join(schema_terms[:10])
        topic = " " .join(x for x in [name, domain] if x).strip()
        if not topic:
            topic = "tabular dataset statistical analysis methodology"
        return re.sub(r"\s+", " ", f"{topic} dataset research empirical studies methodology")[:240]

    def _openalex(self, query: str) -> list[dict[str, Any]]:
        params = urlencode({"search": query, "per-page": 5,
                            "select": "id,doi,title,publication_year,authorships,primary_location,abstract_inverted_index,cited_by_count"})
        req = Request(f"https://api.openalex.org/works?{params}",
                      headers={"User-Agent": "DataPilot/4.0 (research discovery; mailto:research@datapilot.local)"})
        with urlopen(req, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        records = []
        for item in payload.get("results", [])[:5]:
            title = item.get("title")
            if not title:
                continue
            authors = []
            for author in (item.get("authorships") or [])[:5]:
                name = (author.get("author") or {}).get("display_name")
                if name:
                    authors.append(name)
            location = item.get("primary_location") or {}
            source = ((location.get("source") or {}).get("display_name")
                      if isinstance(location, dict) else None)
            doi = item.get("doi")
            abstract = self._abstract_from_inverted_index(item.get("abstract_inverted_index"))
            records.append({
                "title": title, "authors": authors,
                "year": item.get("publication_year"),
                "url": doi or item.get("id"), "doi": doi,
                "source": source or "OpenAlex indexed work",
                "abstract": abstract[:1800] if abstract else None,
                "summary": (abstract[:700] if abstract else
                            "Abstract not available in OpenAlex metadata; title and bibliographic metadata only."),
                "relevance": "OpenAlex search result; verify the abstract and dataset applicability before citing.",
                "provider": "OpenAlex", "cited_by_count": item.get("cited_by_count"),
                "evidence_level": "abstract" if abstract else "metadata_only",
            })
        return records

    def _crossref(self, query: str) -> list[dict[str, Any]]:
        params = urlencode({"query": query[:240], "rows": 3, "select": "title,author,published,URL,DOI,container-title"})
        req = Request(f"https://api.crossref.org/works?{params}", headers={"User-Agent": "DataPilot/1.3 (academic research assistant)"})
        with urlopen(req, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        records = []
        for item in payload.get("message", {}).get("items", [])[:3]:
            title = (item.get("title") or [None])[0]
            if not title: continue
            date_parts = item.get("published", {}).get("date-parts", [[None]])
            authors = [" ".join(x for x in [a.get("given"), a.get("family")] if x) for a in item.get("author", [])[:5]]
            records.append({"title": title, "authors": authors, "year": date_parts[0][0] if date_parts and date_parts[0] else None, "url": item.get("URL"), "doi": item.get("DOI"), "source": (item.get("container-title") or [None])[0], "summary": "Metadata retrieved from Crossref; abstract text was not available in this metadata response.", "relevance": "Search relevance ranking returned by Crossref", "provider": "Crossref"})
        return records

    def investigate(self, profile: DatasetProfile, plan: AnalysisPlan, models: tuple[ModelResult, ...], preprocessing: dict[str, Any], dataset_name: str = "") -> dict[str, Any]:
        findings: list[dict[str, str]] = []
        live_enabled = os.getenv("DATAPILOT_ENABLE_LIVE_RESEARCH", "true").lower() in {"1", "true", "yes"}
        query = self._build_query(profile, plan, dataset_name)
        sources: list[dict[str, Any]] = []
        research_error = None
        if live_enabled:
            try:
                sources.extend(self._openalex(query))
            except Exception as exc:
                research_error = type(exc).__name__
            if not sources:
                try:
                    sources.extend(self._crossref(query))
                except Exception as exc:
                    research_error = research_error or type(exc).__name__

        retrieved = {"mode": "no_evidence", "sources": []}
        try:
            from pathlib import Path
            from ..research.rag import ResearchRAG
            data_dir = Path(os.getenv("DATAPILOT_DATA_DIR", str(Path(__file__).resolve().parents[2])))
            rag = ResearchRAG(data_dir / "research_knowledge.sqlite3")
            retrieved = rag.answer_context(f"{query} methodology evidence", 4)
        except Exception as exc:
            research_error = research_error or type(exc).__name__

        # Recommendations are explicitly separate from paper retrieval.
        findings = self._offline_findings(profile, plan, models, preprocessing)
        if sources:
            mode = "live_research"
        elif retrieved.get("sources"):
            mode = "local_rag"
        else:
            mode = "offline_methodology_guidance"
        return {
            "mode": mode,
            "external_sources_used": bool(sources),
            "research_query": query,
            "sources": sources,
            "retrieved_evidence": retrieved.get("sources", []),
            "retrieval_mode": retrieved.get("mode"),
            "findings": findings,
            "error_type": research_error,
            "disclaimer": "OpenAlex/Crossref records are bibliographic metadata; abstract text is shown only when returned by the provider. Full-text claims require an accessible paper. Offline findings are methodological guidance, not retrieved literature. Local RAG excerpts come only from documents indexed by the user.",
        }
