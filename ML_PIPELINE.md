# ML pipeline

- Target rows with missing/invalid target values are removed.
- Exact duplicate rows are removed from the supervised modelling copy; original dataset profile/EDA still reports them.
- Raw predictors are split before learned transformations.
- Numeric features: median imputation → IQR clipping (bounds fit on training partition/fold) → standard scaling.
- Categorical/boolean: most-frequent imputation → one-hot encoding (`handle_unknown=ignore`).
- Datetime: year/month/day/day-of-week features before numeric preprocessing.
- Holdout metrics are calculated on the validation partition.
- Cross-validation uses a fresh sklearn Pipeline inside each fold, so imputers, clipping bounds, encoders and scalers are fit within the fold.
- Classification metrics include accuracy, weighted/macro F1, precision, recall, confusion matrix, ROC-AUC and PR-AUC when valid.
- Regression metrics include normalized/raw RMSE, normalized MAE and R².
- Explainability selects SHAP for supported tree/linear models when enabled, else native feature importance/coefficients.
- Optional PyTorch MLP candidates can be enabled with `DATAPILOT_ENABLE_DEEP_LEARNING=true`; they use the same transformed training features, AdamW, dropout and an internal validation split for early stopping.
- Adaptive profiling selects Pandas or DuckDB based on `DATAPILOT_DATA_ENGINE` and the configured memory threshold. DuckDB currently profiles an in-memory DataFrame; upload ingestion remains Pandas-based.
- Statistical tests include Welch t-test and Mann–Whitney U for two groups, plus ANOVA/Kruskal–Wallis for eligible multi-group data and chi-square association for categorical features.
- Artifacts save estimator + fitted transformer + transformed feature names. Joblib artifacts must only be loaded from a trusted source.

Current limits: tabular classification/regression, random holdout and KFold/StratifiedKFold. Do not use this random-split pipeline for temporal forecasting; implement a time-aware split and TimeSeriesSplit before claiming time-series support.
