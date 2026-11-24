# Data Pilot V4.2 — Automatic intent, runtime reliability and report redesign

## Workspace objective routing
- Removed manual Target Feature and Problem Type controls from the homepage workspace.
- Removed the pre-analysis profiling request that was only used to preselect those controls.
- Workspace now sends the dataset and plain-English objective; Data Pilot resolves a target and problem type automatically.
- Added schema-validated LLM target/problem suggestions when configured, with deterministic semantic inference taking precedence for strong dataset/question matches and a safe fallback when the provider is unavailable.
- Prevents a sentiment objective from being overridden by a stale UI-selected field such as `user_timezone`.

## Analytics Studio reliability
- Fixed the Python 3.13 / LangGraph `NameError: AnalyticsState is not defined` by removing the nested callback's annotation that LangGraph tried to resolve outside its local scope.
- Removed a duplicate intent-router request in the Analytics Studio endpoint; the graph now performs intent inference once.
- Removed the manual analytics-type selector so the objective and dataset drive the route automatically.

## Runtime visibility
- Added elapsed-time and estimated-remaining-time progress indicators to Workspace and Analytics Studio.
- The progress percentage is explicitly labelled as an estimate; final completion is determined by the backend response.
- Extended Workspace background-job polling from 10 to 30 minutes with gradual polling backoff.
- Added queued/running/failed background jobs to Experiment History so long-running or failed jobs remain visible even before a completed experiment record is saved.

## Report redesign
- Removed raw confusion-matrix arrays from the report narrative; compact model metrics are shown instead.
- Reworked PDF report header and title banner using Data Pilot's forest-green / lime identity.
- Replaced cramped pie labels with a clean legend showing category, count and percentage.
- Replaced crowded vertical category/SHAP charts with readable horizontal bars and numeric contribution values.
- Added consistent page header/footer and confidential page numbering.

## Validation performed
- Python compileall: passed.
- Analytics intent and semantic-reporting tests: 16 passed.
- Analytics Studio API smoke test: HTTP 200.
- LangGraph analytics graph smoke test: completed without the AnalyticsState NameError.
- PDF export smoke test: returned a valid PDF document.
- Full frontend production build was not verified in this environment because npm dependency installation did not complete; run `npm ci` and `npm run build` locally.
