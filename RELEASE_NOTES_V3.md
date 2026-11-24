# Data Pilot V3 release notes

## Added
- LangGraph StateGraph lifecycle orchestration with explicit Python fallback behavior.
- Per-experiment orchestration events and specialist outcome trace endpoint.
- Adaptive Pandas/DuckDB data engine and SQL-based DuckDB profiling.
- Optional PyTorch tabular MLP classifier and regressor.
- Additional multiclass ANOVA, Kruskal-Wallis and chi-square tests.
- Local research library with chunking, TF-IDF retrieval, optional Sentence Transformers embeddings and optional PDF text extraction.
- Research excerpts are available to the Research Agent and report context.
- Expanded MLflow tracking metadata and JSON artifact logging.
- Expanded MCP stdio tools and REST tool catalogue.
- Multi-section React workspace with dataset, experiment, research and integration views.

## Preserved
- V2 upload validation, preprocessing, classification/regression baselines, cross-validation, critic/replanning, SHAP/native explanations, deterministic/LLM-assisted reports, experiment history and trusted model inference.

## Validation notes
- 73 backend tests pass in the current environment.
- Sample churn analysis and optional PyTorch MLP pipeline smoke test pass using the sequential fallback because LangGraph could not be installed in this offline build environment.
- LangGraph, DuckDB, MCP, MLflow, PyMuPDF, Sentence Transformers, Vite production build and Docker build still require target-environment validation.
