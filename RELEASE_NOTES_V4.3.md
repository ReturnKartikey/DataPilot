# Data Pilot V4.3 — Performance & Execution Intelligence

## Main changes

- Added persisted job telemetry: percentage (completed stages / total stages), current stage, completed stages, and total stages are stored in SQLite and returned by the job status/history APIs.
- Workspace progress now follows backend pipeline milestones instead of a fixed timer. Experiment History refreshes active jobs every five seconds and displays their current stage and progress. ETA is derived from observed elapsed time and completed backend stages; it is an estimate, not a guaranteed completion time.
- Reduced status polling frequency with exponential backoff (2.5s to 8s) and extended the client wait window to 90 minutes. If the client wait window ends, it reports the existing job ID and warns against starting a duplicate. Jobs left queued/running after a backend restart are marked interrupted instead of remaining stuck forever.
- Descriptive ranking/count/aggregation prompts no longer become accidental classification/regression tasks. They skip predictive model training and calculate top-value counts, including comma-separated multi-value columns such as directors/cast/genres.
- Cross-validation is skipped above `DATAPILOT_MAX_CV_ROWS` (default 10,000); holdout metrics remain available. This prevents repeated fitting on large datasets.
- Research queries are now built from dataset filename/domain and schema rather than the user's immediate analytical question. OpenAlex is queried first; Crossref is a fallback, not a second serial search every time.
- Fixed OpenRouter intent routing when `LLM_BASE_URL` is absent: the default now follows `LLM_PROVIDER` instead of incorrectly defaulting to OpenAI's host.
- LLM HTTP failures now include a short provider diagnostic in the fallback notice (credentials are never included).
- Analytics Studio now supports removing an uploaded file and shows whether an LLM key is configured. Its progress indicator is explicitly indeterminate because that endpoint is not the multi-agent Workspace job lifecycle; it no longer invents a time-based ETA.

## Configuration

Optional performance controls:

```env
DATAPILOT_MAX_CV_ROWS=10000
DATAPILOT_ENABLE_LIVE_RESEARCH=true
DATAPILOT_ENABLE_SHAP=true
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
# Optional; when omitted, the provider-specific default URL is used.
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
```

Keep the real `.env` file local. Do not commit API keys.

## Validation

- Python compilation: passed.
- V4 analytics tests: 5 passed.
- LLM provider and research tests: 8 passed.
- V4.3 execution telemetry, research-query and descriptive-routing tests: included in this release.
- Full frontend production build: not verified in the packaging environment because npm dependency installation did not complete.
- Full backend suite: not completed within the available test window; selected relevant suites passed.
