# Data Pilot V3 agent contracts

| Component | Responsibility | Execution style |
|---|---|---|
| Profiler | Dataset shape, types, missingness, duplicates, target candidates | Deterministic Python |
| Planner | Structured objective and model plan from profile facts | Deterministic Python |
| Security Guardian | Validate initial and revised plans before execution | Deterministic policy checks |
| EDA Agent | Distributions, correlations, categories, missingness, outliers | Deterministic Python |
| Statistics Agent | Descriptive stats, Welch t-test, Mann–Whitney U, ANOVA, Kruskal–Wallis, chi-square | Deterministic SciPy/Pandas |
| Preprocessing Agent | Leakage-safe imputation, encoding, scaling and datetime features | scikit-learn pipelines |
| ML Agent | Classification/regression baselines and optional PyTorch MLP | scikit-learn / PyTorch |
| Critic Agent | Evaluate measured quality, imbalance, overfit and security feedback | Deterministic rules |
| Replanner Agent | Revise declarative plan with at most one guarded retry | Deterministic Python |
| Explainability Agent | SHAP or native feature importance/coefficient explanations | Deterministic Python |
| Research Agent | Offline guidance, optional Crossref metadata and local retrieved evidence | Retrieval + optional metadata lookup |
| Reporting Agent | Verified metrics, evidence excerpts and optional LLM narrative | Deterministic report + optional LLM |

## Orchestration

`backend/data_pilot/orchestration/graph.py` contains the LangGraph `StateGraph` lifecycle. It currently controls input validation, conditional execution of the existing specialist pipeline and finalization/checkpointing. Individual specialists are real Python components but are not yet independent LangGraph nodes. If LangGraph is not installed, the application uses a clearly labelled sequential compatibility fallback (`orchestration.framework = python_fallback`).

## Tool access

`backend/mcp_server.py` is the actual MCP stdio server. `backend/data_pilot/tool_registry.py` defines allowlisted tool schemas shared with the REST adapter. Tools do not accept arbitrary filesystem paths or execute user-supplied code.

No agent receives arbitrary shell, filesystem or Python execution access. LLM output is not directly executed. Python-computed metrics remain authoritative.
