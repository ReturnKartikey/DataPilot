# Data Pilot V4.1 — Analytics, Research and Report Quality Update

## Dataset-aware question answering
- Added schema-and-value-based target inference for natural-language category questions.
- Questions such as "how many tweets are neutral sentiment?" now prefer a sentiment column whose observed values contain `neutral`, rather than an unrelated field such as timezone.
- Target distributions exclude missing target labels; missingness remains reported separately.
- Direct answers use Python-computed counts and percentages from the uploaded dataset. No dataset result counts are hardcoded.
- Conventional coded class labels (such as UCI mushroom `p`/`e`) are translated only when the dataset context supports that interpretation; the underlying count remains data-derived.

## Visualization
- Explicit pie/donut requests are preserved as chart type in the report payload.
- Interactive report supports pie/donut charts with legends, counts and percentages.
- PDF export supports pie charts as well as bar charts.
- Global SHAP contribution magnitudes are shown as ranked horizontal bars with numeric values.
- Report chart headings identify mean absolute SHAP contribution when SHAP is the explanation method.

## Research Agent
- Live research discovery searches OpenAlex and Crossref using the objective, target, problem type and dataset column context.
- OpenAlex abstracts are reconstructed and shown when available.
- Crossref-only results are explicitly marked metadata-only.
- External papers, local indexed RAG excerpts and offline methodology guidance are displayed as separate evidence classes.
- Research cards show title, authors, year, provider, abstract when available, and DOI/source links.
- Live research is enabled in `backend/.env.example` with `DATAPILOT_ENABLE_LIVE_RESEARCH=true`; set it to false for offline-only runs.
- External retrieval is best-effort and falls back transparently if the network/index is unavailable.

## Report and UI quality
- Research records and methodology recommendations render as structured cards instead of raw JSON strings.
- PDF report headings, body typography, brand colors, header/footer and page numbers are improved.
- Light cards on the forest-green workspace now use explicit dark heading/body colors for readable contrast.

## Validation
- Backend test suite: 73 tests passed.
- Python compilation: passed.
- JSX parser check: all 6 JSX files parsed successfully.
- Full Vite production build was not run because npm dependency installation stalled in this environment; run `npm ci` and `npm run build` locally.
