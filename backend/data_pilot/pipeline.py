"""End-to-end Data Pilot pipeline with security and specialist agents.

Profiler -> Planner -> Security Guardian -> Preprocessing/EDA -> ML ->
Explainability -> Critic.
"""

from __future__ import annotations

import re

import math
import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score, average_precision_score, confusion_matrix,
)
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from .agents.critic import CriticAgent
from .agents.eda import EDAAgent
from .agents.explainability import ExplainabilityAgent
from .agents.planner import PlannerAgent
from .agents.preprocessing import PreprocessingAgent
from .agents.schemas import ModelResult, Objective, ProblemType
from .agents.security import SecurityGuardian
from .agents.replanner import ReplannerAgent
from .agents.reporting import ReportingAgent
from .artifacts import ArtifactStore
from .tracking import log_with_mlflow
from pathlib import Path
from .agents.statistics import StatisticalAnalysisAgent
from .agents.research import ResearchAgent
from .profiler import profile_dataframe

warnings.filterwarnings("ignore", category=ConvergenceWarning)


def _instantiate_model(name: str, overrides: dict[str, Any] | None = None):
    overrides = overrides or {}
    class_weight = "balanced" if overrides.get("class_weight") == "balanced" else None
    reduce_complexity = bool(overrides.get("prefer_regularized_models"))
    models = {
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=42, class_weight=class_weight),
        "decision_tree_classifier": DecisionTreeClassifier(max_depth=3 if reduce_complexity else 5, class_weight=class_weight, random_state=42),
        "random_forest_classifier": RandomForestClassifier(
            n_estimators=50, max_depth=4 if reduce_complexity else 6, class_weight=class_weight, random_state=42
        ),
        "gradient_boosting_classifier": GradientBoostingClassifier(
            n_estimators=50, max_depth=3, random_state=42
        ),
        "linear_regression": LinearRegression(),
        "ridge_regression": Ridge(alpha=1.0, random_state=42),
        "decision_tree_regressor": DecisionTreeRegressor(max_depth=3 if reduce_complexity else 5, random_state=42),
        "random_forest_regressor": RandomForestRegressor(
            n_estimators=50, max_depth=4 if reduce_complexity else 6, random_state=42
        ),
        "gradient_boosting_regressor": GradientBoostingRegressor(
            n_estimators=50, max_depth=3, random_state=42
        ),
    }
    if name in {"xgboost_classifier", "xgboost_regressor"}:
        try:
            from xgboost import XGBClassifier, XGBRegressor
            if name == "xgboost_classifier":
                return XGBClassifier(n_estimators=100, max_depth=4 if reduce_complexity else 5, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, eval_metric="logloss", random_state=42, n_jobs=2, verbosity=0)
            return XGBRegressor(n_estimators=100, max_depth=4 if reduce_complexity else 5, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, objective="reg:squarederror", random_state=42, n_jobs=2, verbosity=0)
        except ImportError:
            return None
    if name == "pytorch_mlp_classifier":
        if __import__("os").getenv("DATAPILOT_ENABLE_DEEP_LEARNING", "false").lower() in {"1", "true", "yes"}:
            try:
                from .deep_learning import TabularMLPClassifier
                return TabularMLPClassifier(epochs=int(__import__("os").getenv("DATAPILOT_MLP_EPOCHS", "80")))
            except ImportError:
                return None
    if name == "pytorch_mlp_regressor":
        if __import__("os").getenv("DATAPILOT_ENABLE_DEEP_LEARNING", "false").lower() in {"1", "true", "yes"}:
            try:
                from .deep_learning import TabularMLPRegressor
                return TabularMLPRegressor(epochs=int(__import__("os").getenv("DATAPILOT_MLP_EPOCHS", "80")))
            except ImportError:
                return None
    return models.get(name)


def _prepare_target(df: pd.DataFrame, target_col: str, problem_type: str):
    """Prepare only the target; feature preprocessing is handled leakage-safely by PreprocessingAgent."""
    working_df = df.copy().dropna(subset=[target_col])
    y_raw = working_df[target_col]

    if problem_type == "classification":
        if y_raw.dtype == bool or set(y_raw.dropna().unique()).issubset({True, False}):
            y = y_raw.astype(int).to_numpy()
        elif pd.api.types.is_numeric_dtype(y_raw.dtype):
            unique_vals = sorted(y_raw.dropna().unique())
            val_to_idx = {v: i for i, v in enumerate(unique_vals)}
            y = y_raw.map(val_to_idx).to_numpy()
        else:
            y, _ = pd.factorize(y_raw)
        return working_df, y

    y = pd.to_numeric(y_raw, errors="coerce")
    valid = y.notna()
    working_df = working_df.loc[valid].copy()
    return working_df, y.loc[valid].to_numpy(dtype=float)


def _prepare_train_val_data(
    df: pd.DataFrame, target_col: str, problem_type: str
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    from sklearn.preprocessing import StandardScaler
    working_df, y = _prepare_target(df, target_col, problem_type)
    is_classification = problem_type == "classification"

    X_raw = working_df.drop(columns=[target_col])

    # Drop clear identifier columns (ID columns, etc.)
    cols_to_drop = [
        c for c in X_raw.columns
        if c.lower().endswith(("_id", "id")) or (X_raw[c].dtype == object and X_raw[c].nunique() == len(X_raw))
    ]
    if cols_to_drop and len(cols_to_drop) < len(X_raw.columns):
        X_raw = X_raw.drop(columns=cols_to_drop)

    stratify = y if (is_classification and len(np.unique(y)) > 1 and min(pd.Series(y).value_counts()) >= 2) else None
    X_train_raw, X_val_raw, y_train, y_val = train_test_split(
        X_raw, y, test_size=0.25, random_state=42, stratify=stratify
    )

    num_cols = [c for c in X_raw.columns if pd.api.types.is_numeric_dtype(X_raw[c].dtype)]
    cat_cols = [c for c in X_raw.columns if c not in num_cols]

    train_parts = []
    val_parts = []

    if num_cols:
        X_train_num = X_train_raw[num_cols].copy()
        X_val_num = X_val_raw[num_cols].copy()
        meds = X_train_num.median().fillna(0.0)
        X_train_num = X_train_num.fillna(meds)
        X_val_num = X_val_num.fillna(meds)
        scaler = StandardScaler()
        X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train_num), columns=num_cols, index=X_train_raw.index)
        X_val_scaled = pd.DataFrame(scaler.transform(X_val_num), columns=num_cols, index=X_val_raw.index)
        train_parts.append(X_train_scaled)
        val_parts.append(X_val_scaled)

    if cat_cols:
        safe_cat_cols = [c for c in cat_cols if X_train_raw[c].nunique() <= 50]
        if safe_cat_cols:
            X_train_cat_raw = X_train_raw[safe_cat_cols].fillna("missing").astype(str)
            X_val_cat_raw = X_val_raw[safe_cat_cols].fillna("missing").astype(str)
            X_train_cat = pd.get_dummies(X_train_cat_raw, prefix=safe_cat_cols, drop_first=True)
            X_val_cat = pd.get_dummies(X_val_cat_raw, prefix=safe_cat_cols, drop_first=True)
            X_val_cat = X_val_cat.reindex(columns=X_train_cat.columns, fill_value=0)
            train_parts.append(X_train_cat.astype(float))
            val_parts.append(X_val_cat.astype(float))

    if train_parts:
        X_train = pd.concat(train_parts, axis=1).fillna(0.0)
        X_val = pd.concat(val_parts, axis=1).fillna(0.0)
    else:
        X_train = pd.DataFrame({"dummy": np.ones(len(X_train_raw))}, index=X_train_raw.index)
        X_val = pd.DataFrame({"dummy": np.ones(len(X_val_raw))}, index=X_val_raw.index)

    return X_train, X_val, y_train, y_val


def _infer_target_from_question(df: pd.DataFrame, inquiry: str, candidates: tuple[str, ...] | list[str] = ()) -> str | None:
    """Infer a categorical target from the question and observed values, without dataset-specific row counts."""
    if not inquiry:
        return None
    q = inquiry.casefold()
    columns = [str(c) for c in df.columns]

    # Explicit column-name mention is the strongest signal.
    exact = [c for c in columns if re.search(r"(?<![a-z0-9_])" + re.escape(c.casefold()) + r"(?![a-z0-9_])", q)]
    if exact:
        return max(exact, key=lambda c: len(c))
    # Entity-ranking requests often refer to a concept rather than the exact
    # field spelling; allow high-cardinality entity columns such as directors.
    if "director" in q:
        matches = [c for c in columns if "director" in c.casefold() or "filmmaker" in c.casefold()]
        if matches:
            return max(matches, key=len)

    # Common natural-language concepts map to column-name concepts, not fixed datasets.
    concept_terms = {
        "sentiment": ("sentiment", "polarity", "opinion"),
        "class": ("class", "label", "target", "category", "outcome"),
        "poison": ("class", "label", "target", "poison", "toxicity"),
        "edible": ("class", "label", "target", "edible", "food_safety"),
        "churn": ("churn", "attrition", "cancel"),
        "fraud": ("fraud", "is_fraud", "label", "class"),
        "survival": ("survival", "survived", "outcome"),
        "diagnosis": ("diagnosis", "diagnostic", "class", "target"),
        "rating": ("rating", "score", "stars"),
        "obesity": ("obesity", "obese", "weight_category", "weightcategory", "nobeyesdad", "bmi_class"),
        "weight": ("weight", "obesity", "nobeyesdad", "bmi_class"),
    }
    semantic_terms = {term for phrase, terms in concept_terms.items() if phrase in q for term in terms}
    named = [c for c in columns if any(term in c.casefold().replace("-", "_") for term in semantic_terms)]
    # Category values (e.g. neutral, positive, poisonous) are strong evidence that a
    # categorical column is the subject of a "how many ... are ..." question.
    category_words = re.findall(r"[a-z][a-z_-]{2,}", q)
    ignored = {"how", "many", "what", "percentage", "percent", "share", "number", "count",
               "tweets", "tweet", "mushrooms", "mushroom", "samples", "records", "rows",
               "are", "were", "that", "this", "with", "from", "dataset", "data", "please",
               "show", "give", "chart", "pie", "bar", "plot", "distribution"}
    category_words = [w for w in category_words if w not in ignored]
    value_matches = []
    for col in columns:
        series = df[col]
        if series.nunique(dropna=True) > 50:
            continue
        values = {str(v).strip().casefold() for v in series.dropna().unique()}
        if any(word in values or any(word == v.replace("_", " ").casefold() for v in values) for word in category_words):
            value_matches.append(col)

    # Prefer semantically named candidates that also contain one of the requested values.
    overlap = [c for c in value_matches if c in named]
    if overlap:
        return max(overlap, key=lambda c: (len(set(c.casefold().replace("_", " ").split()) & set(q.split())), -df[c].nunique()))
    if len(value_matches) == 1:
        return value_matches[0]
    if named:
        eligible = [c for c in named if df[c].nunique(dropna=True) <= 50]
        if eligible:
            return max(eligible, key=lambda c: (c in candidates, -df[c].nunique()))
    # A request explicitly about sentiment should select the sentiment field even if
    # category values are not present in the wording.
    if "sentiment" in q:
        sentiment_cols = [c for c in columns if "sentiment" in c.casefold()]
        if sentiment_cols:
            return min(sentiment_cols, key=lambda c: df[c].nunique(dropna=True))
    return None


def _resolve_context(df, profile, inquiry, target_column, problem_type):
    effective_target = target_column
    inq_lower = inquiry.lower() if inquiry else ""
    llm_problem_type = "unknown"

    # Explicit semantic evidence in the question and observed dataset values
    # takes precedence over a model guess (e.g. "sentiments" must not map to
    # a timezone field). The LLM then resolves less obvious objectives.
    if not effective_target and inquiry.strip():
        effective_target = _infer_target_from_question(df, inquiry, profile.potential_target_columns)

    if not effective_target and inquiry.strip():
        try:
            from data_pilot.llm.intent import understand_intent
            llm_plan = understand_intent(inquiry, [str(c) for c in df.columns])
            candidate = llm_plan.get("target") or llm_plan.get("column")
            if candidate in df.columns:
                effective_target = candidate
            llm_problem_type = llm_plan.get("problem_type", "unknown")
        except Exception:
            pass

    if not effective_target:
        for candidate in profile.potential_target_columns:
            if candidate.lower() in inq_lower:
                effective_target = candidate
                break

    if not effective_target and len(profile.potential_target_columns) == 1:
        effective_target = profile.potential_target_columns[0]

    resolved_problem_type = problem_type
    if resolved_problem_type == "unknown" and llm_problem_type in {"classification", "regression"}:
        resolved_problem_type = llm_problem_type

    if resolved_problem_type == "unknown" and inquiry:
        if any(
            word in inq_lower
            for word in ["estimate", "forecast", "regression", "price", "amount", "revenue"]
        ):
            resolved_problem_type = "regression"
        elif any(
            word in inq_lower
            for word in ["predict churn", "classification", "classify", "categorize"]
        ):
            resolved_problem_type = "classification"

    if resolved_problem_type == "unknown" and effective_target:
        target_profile = profile.column(effective_target)
        if target_profile:
            if target_profile.kind in {"categorical", "boolean"}:
                resolved_problem_type = "classification"
            elif target_profile.kind == "numeric":
                resolved_problem_type = (
                    "classification" if target_profile.unique_count <= 2 else "regression"
                )

    return effective_target, resolved_problem_type


def _run_pipeline_core(
    df: pd.DataFrame,
    inquiry: str = "",
    target_column: str | None = None,
    problem_type: ProblemType = "unknown",
    dataset_name: str = "uploaded dataset",
    progress_callback=None,
) -> dict[str, Any]:
    """Execute the Data Pilot analysis pipeline with optional stage telemetry."""
    def progress(percent, stage, completed):
        if progress_callback:
            try:
                total_steps = 11
                # Progress is the count of completed backend stages, not a timer.
                measured_percent = round(max(0, min(total_steps, int(completed))) / total_steps * 100)
                progress_callback({"progress_percent": measured_percent, "current_stage": stage,
                                   "completed_steps": int(completed), "total_steps": total_steps})
            except Exception:
                pass
    progress(3, "Inspecting dataset schema", 0)

    # 1. Select an adaptive execution engine and profile the dataset.
    from .data_engine import get_engine
    selected_engine = get_engine(df)
    engine_profile = selected_engine.profile(df)
    profile = profile_dataframe(df, target_column=target_column)

    effective_target, resolved_problem_type = _resolve_context(
        df, profile, inquiry, target_column, problem_type,
    )
    # Aggregation/ranking questions are descriptive analytics, not classification
    # tasks. Preserve the semantic focus for EDA but do not train classifiers on it.
    descriptive_focus = effective_target
    q_lower = (inquiry or "").casefold()
    descriptive_request = any(term in q_lower for term in (
        "top ", "most number", "most movies", "count", "how many", "number of",
        "distribution", "breakdown", "rank", "ranking", "highest", "lowest",
        "average", "mean", "median", "sum", "total", "compare", "group by",
    )) and not any(term in q_lower for term in ("predict", "forecast", "classify", "classification", "regression", "churn prediction"))
    if descriptive_request and target_column is None:
        effective_target = None
        resolved_problem_type = "unknown"

    progress(9, "Planning analysis and checking security", 1)

    # 2. Planner
    objective = Objective(
        text=inquiry,
        target_column=effective_target,
        problem_type=resolved_problem_type,
    )
    plan = PlannerAgent().create_plan(profile, objective)
    if descriptive_request and target_column is None:
        # Prevent PlannerAgent's generic last-column heuristic from turning an
        # aggregation request into a spurious classification task.
        from dataclasses import replace
        plan = replace(plan, target_column=None, problem_type="unknown",
                       steps=("profile", "clean", "eda"),
                       recommended_models=(), primary_metric=None,
                       validation_strategy="not_applicable")

    # 3. PRE-EXECUTION SECURITY GUARD
    security_guardian = SecurityGuardian()
    security = security_guardian.inspect(
        plan=plan,
        profile=profile,
        inquiry=inquiry,
    )

    if not security.allowed:
        preview_rows = df.head(5).fillna("").to_dict(orient="records")
        return {
            "status": "blocked",
            "blocked_at": "security_guardian",
            "security": security.to_dict(),
            "dataset_summary": {
                "rows": profile.rows,
                "columns_count": len(profile.columns),
                "columns": [column.to_dict() for column in profile.columns],
                "duplicate_rows": profile.duplicate_rows,
                "class_imbalance_ratio": profile.class_imbalance_ratio,
                "warnings": list(profile.warnings),
                "preview": preview_rows,
            },
            "plan": plan.to_dict(),
            "models": [],
            "eda": {},
            "preprocessing": {},
            "explainability": {},
            "critic": {
                "satisfactory": False,
                "score": 0.0,
                "issues": list(security.violations),
                "recommendations": [
                    "Do not execute the current plan.",
                    "Regenerate a policy-compliant plan.",
                ],
                "next_plan_overrides": {},
                "security": security.to_dict(),
            },
        }

    # 4. Specialist agents
    progress(15, "Security checks passed", 2)
    duplicate_rows_removed = int(df.duplicated().sum())
    modeling_df = df.drop_duplicates().copy()

    preprocessing = PreprocessingAgent().create_strategy(
        df=df,
        profile=profile,
        target_column=plan.target_column,
    )

    eda = EDAAgent().analyze(df, target_column=plan.target_column or descriptive_focus)
    if descriptive_request and descriptive_focus and descriptive_focus in df.columns:
        focus_series = df[descriptive_focus].dropna().astype(str).str.strip()
        # Multi-valued columns such as directors/cast/genres/countries need to
        # be exploded before counting entities, rather than counting whole cells.
        comma_share = float(focus_series.str.contains(",", regex=False).mean()) if len(focus_series) else 0.0
        if comma_share >= 0.15:
            focus_series = focus_series.str.split(r"\s*,\s*").explode().str.strip()
        focus_series = focus_series[focus_series.ne("")]
        top_n_match = re.search(r"top\s+(\d{1,2})", q_lower)
        top_n = min(50, max(1, int(top_n_match.group(1)))) if top_n_match else 10
        top_values = focus_series.value_counts().head(top_n)
        eda["requested_analysis"] = {
            "kind": "top_value_counts", "column": descriptive_focus,
            "metric": "record_count", "limit": top_n,
            "results": [{"value": str(value), "count": int(count)} for value, count in top_values.items()],
            "note": "Comma-separated multi-value cells were split before counting." if comma_share >= 0.15 else "Counts are based on the selected column values.",
        }
    statistics = StatisticalAnalysisAgent().analyze(df, target_column=plan.target_column)
    progress(27, "Exploratory and statistical analysis complete", 3)
    preprocessing["execution"] = {"fitted": False, "duplicate_rows_removed": duplicate_rows_removed, "transformer": "pending model selection"}

    model_results: list[ModelResult] = []
    trained_estimators: dict[str, Any] = {}
    feature_names: list[str] = []
    model_errors: list[str] = []
    X_train = X_val = y_train = y_val = None
    X_train_raw = None
    fitted_preprocessor = None
    target_classes: list[Any] = []
    is_classification = plan.problem_type == "classification"
    attempted_models: set[str] = set()
    replan_history: list[dict[str, Any]] = []

    # 5. ML execution
    target_col = plan.target_column
    if (
        not descriptive_request
        and plan.problem_type != "unknown"
        and target_col
        and target_col in df.columns
        and len(df) >= 8
    ):
        try:
            working_df, y = _prepare_target(modeling_df, target_col, plan.problem_type)
            if is_classification:
                raw_target = working_df[target_col]
                if raw_target.dtype == bool:
                    target_classes = [False, True]
                elif pd.api.types.is_numeric_dtype(raw_target.dtype):
                    target_classes = sorted(raw_target.dropna().unique().tolist())
                else:
                    target_classes = pd.factorize(raw_target)[1].tolist()
            X_raw = working_df.drop(columns=[target_col])
            is_classification = plan.problem_type == "classification"

            stratify = (
                y
                if (
                    is_classification
                    and len(np.unique(y)) > 1
                    and min(pd.Series(y).value_counts()) >= 2
                )
                else None
            )

            X_train_raw, X_val_raw, y_train, y_val = train_test_split(
                X_raw,
                y,
                test_size=0.25,
                random_state=42,
                stratify=stratify,
            )

            X_train, X_val, feature_names, fitted_preprocessor = PreprocessingAgent().prepare_features(
                X_train_raw,
                X_val_raw,
                profile,
                target_column=target_col,
            )
            preprocessing["execution"] = {
                "fitted": True,
                "duplicate_rows_removed": duplicate_rows_removed,
                "fit_rows": int(len(X_train_raw)),
                "validation_rows": int(len(X_val_raw)),
                "transformed_feature_count": int(X_train.shape[1]),
                "transformed_features_preview": feature_names[:50],
                "transformer": "ColumnTransformer",
                "fit_scope": "training split only",
            }

            models_to_run = list(plan.recommended_models[:2])
            progress(35, "Preprocessing fitted on training data", 4)
            if __import__("os").getenv("DATAPILOT_ENABLE_DEEP_LEARNING", "false").lower() in {"1", "true", "yes"}:
                models_to_run.append("pytorch_mlp_classifier" if is_classification else "pytorch_mlp_regressor")

            for model_index, model_name in enumerate(models_to_run):
                attempted_models.add(model_name)
                estimator = _instantiate_model(model_name)
                if estimator is None:
                    continue

                try:
                    estimator.fit(X_train, y_train)
                    train_preds = estimator.predict(X_train)
                    val_preds = estimator.predict(X_val)

                    metrics: dict[str, float] = {}
                    warnings_list: list[str] = []

                    if is_classification:
                        train_acc = float(accuracy_score(y_train, train_preds))
                        val_acc = float(accuracy_score(y_val, val_preds))
                        train_score = round(train_acc, 4)
                        validation_score = round(val_acc, 4)

                        metrics["f1_weighted"] = round(
                            float(
                                f1_score(
                                    y_val,
                                    val_preds,
                                    average="weighted",
                                    zero_division=0,
                                )
                            ),
                            4,
                        )
                        metrics["accuracy"] = round(val_acc, 4)
                        metrics["precision"] = round(
                            float(
                                precision_score(
                                    y_val,
                                    val_preds,
                                    average="weighted",
                                    zero_division=0,
                                )
                            ),
                            4,
                        )
                        metrics["recall"] = round(
                            float(recall_score(y_val, val_preds, average="weighted", zero_division=0)), 4
                        )
                        metrics["f1_macro"] = round(float(f1_score(y_val, val_preds, average="macro", zero_division=0)), 4)
                        metrics["confusion_matrix"] = confusion_matrix(y_val, val_preds).tolist()

                        if hasattr(estimator, "predict_proba") and len(np.unique(y)) == 2:
                            try:
                                proba = estimator.predict_proba(X_val)[:, 1]
                                metrics["roc_auc"] = round(float(roc_auc_score(y_val, proba)), 4)
                                metrics["pr_auc"] = round(float(average_precision_score(y_val, proba)), 4)
                            except Exception as exc:
                                warnings_list.append(
                                    f"ROC-AUC unavailable: {type(exc).__name__}"
                                )
                        # Do not substitute accuracy for ROC-AUC; unavailable metrics stay absent.

                    else:
                        train_rmse = float(
                            np.sqrt(mean_squared_error(y_train, train_preds))
                        )
                        val_rmse = float(
                            np.sqrt(mean_squared_error(y_val, val_preds))
                        )
                        val_mae = float(mean_absolute_error(y_val, val_preds))
                        val_r2 = float(r2_score(y_val, val_preds))

                        y_range = (
                            float(y.max() - y.min())
                            if float(y.max() - y.min()) > 0
                            else 1.0
                        )
                        norm_rmse = float(val_rmse / y_range)
                        norm_mae = float(val_mae / y_range)

                        train_score = (
                            round(max(0.0, float(r2_score(y_train, train_preds))), 4)
                            if len(y_train) > 2
                            else 0.8
                        )
                        validation_score = (
                            round(max(0.0, val_r2), 4)
                            if len(y_val) > 2
                            else 0.8
                        )

                        metrics["rmse"] = round(norm_rmse, 4)
                        metrics["mae"] = round(norm_mae, 4)
                        metrics["r2"] = round(val_r2, 4)
                        metrics["raw_rmse"] = round(val_rmse, 2)
                        _ = train_rmse

                    model_results.append(
                        ModelResult(
                            model_name=model_name,
                            metrics=metrics,
                            train_score=train_score,
                            validation_score=validation_score,
                            warnings=tuple(warnings_list),
                        )
                    )
                    trained_estimators[model_name] = estimator
                    progress(42 + int((model_index + 1) / max(1, len(models_to_run)) * 20),
                             f"Evaluated model: {model_name}", 5 + model_index)

                except Exception as exc:
                    model_errors.append(
                        f"{model_name}: {type(exc).__name__}: {exc}"
                    )

        except Exception as exc:
            model_errors.append(
                f"ML preparation failed: {type(exc).__name__}: {exc}"
            )

    progress(65, "Model evaluation finished", 6)
    if descriptive_request:
        progress(62, "Predictive modelling skipped for descriptive objective", 6)
    # 6. Critic: security is checked again here as a defense-in-depth layer.
    critic_agent = CriticAgent(security_guardian=security_guardian)
    critic = critic_agent.review(plan, profile, tuple(model_results), inquiry=inquiry)

    # 7. Bounded autonomous replanning: at most one retry, and re-check security.
    replanner = ReplannerAgent()
    revised_plan, replan_decision = replanner.create_revision(
        plan, critic, attempted_models=attempted_models, max_models=2
    )
    replan_history.append(replan_decision.to_dict())
    if replan_decision.attempted and X_train is not None and X_val is not None:
        revised_security = security_guardian.inspect(
            plan=revised_plan, profile=profile, inquiry=inquiry
        )
        replan_history[-1]["security_recheck"] = revised_security.to_dict()
        if revised_security.allowed:
            retry_estimators = {}
            for model_name in revised_plan.recommended_models:
                attempted_models.add(model_name)
                estimator = _instantiate_model(model_name, replan_decision.applied_overrides)
                if estimator is None:
                    continue
                try:
                    estimator.fit(X_train, y_train)
                    train_preds = estimator.predict(X_train)
                    val_preds = estimator.predict(X_val)
                    if is_classification:
                        train_score = float(accuracy_score(y_train, train_preds))
                        val_score = float(accuracy_score(y_val, val_preds))
                        metrics = {
                            "accuracy": round(val_score, 4),
                            "f1_weighted": round(float(f1_score(y_val, val_preds, average="weighted", zero_division=0)), 4),
                            "precision": round(float(precision_score(y_val, val_preds, average="weighted", zero_division=0)), 4),
                            "recall": round(float(recall_score(y_val, val_preds, average="weighted", zero_division=0)), 4),
                        }
                        if hasattr(estimator, "predict_proba") and len(np.unique(y_val)) == 2:
                            try:
                                metrics["roc_auc"] = round(float(roc_auc_score(y_val, estimator.predict_proba(X_val)[:, 1])), 4)
                            except Exception:
                                pass
                    else:
                        val_rmse = float(np.sqrt(mean_squared_error(y_val, val_preds)))
                        yrange = float(np.max(y) - np.min(y)) or 1.0
                        train_score = float(r2_score(y_train, train_preds)) if len(y_train) > 2 else 0.0
                        val_score = float(r2_score(y_val, val_preds)) if len(y_val) > 2 else 0.0
                        metrics = {"rmse": round(val_rmse / yrange, 4), "mae": round(float(mean_absolute_error(y_val, val_preds)) / yrange, 4), "r2": round(val_score, 4), "raw_rmse": round(val_rmse, 2)}
                    model_results.append(ModelResult(model_name=model_name, metrics=metrics, train_score=round(train_score, 4), validation_score=round(val_score, 4), warnings=("Replanner retry",)))
                    retry_estimators[model_name] = estimator
                except Exception as exc:
                    model_errors.append(f"replanner/{model_name}: {type(exc).__name__}: {exc}")
            trained_estimators.update(retry_estimators)
            replan_history[-1]["models_trained"] = list(retry_estimators)
            if retry_estimators:
                critic = critic_agent.review(revised_plan, profile, tuple(model_results), inquiry=inquiry)
                plan = revised_plan
        else:
            replan_history[-1]["blocked"] = True
            replan_history[-1]["block_reason"] = list(revised_security.violations)

    progress(72, "Critic review and bounded replanning complete", 7)
    # 8. Cross-validation uses a fresh preprocessing pipeline inside each fold.
    cross_validation: dict[str, Any] = {"performed": False, "summary": "Not performed: no valid training target/model."}
    max_cv_rows = int(__import__("os").getenv("DATAPILOT_MAX_CV_ROWS", "10000"))
    if model_results and X_train_raw is not None and y_train is not None and len(X_train_raw) <= max_cv_rows:
        try:
            best_for_cv = max(model_results, key=lambda item: CriticAgent._score(item, plan.primary_metric))
            base_estimator = _instantiate_model(best_for_cv.model_name)
            if base_estimator is not None:
                preprocessing_agent = PreprocessingAgent()
                transformer, _, datetime_cols = preprocessing_agent.build_transformer(profile, target_col)
                fold_pipeline = Pipeline([
                    ("datetime_features", FunctionTransformer(
                        lambda frame: preprocessing_agent._expand_datetime(frame, datetime_cols),
                        validate=False, feature_names_out="one-to-one")),
                    ("preprocessing", transformer),
                    ("model", base_estimator),
                ])
                if is_classification:
                    min_class = int(pd.Series(y_train).value_counts().min())
                    folds = min(5, min_class)
                    if folds >= 2:
                        cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
                        scores = cross_val_score(fold_pipeline, X_train_raw, y_train, cv=cv, scoring="f1_weighted", error_score="raise")
                        cross_validation = {"performed": True, "strategy": "StratifiedKFold", "folds": folds, "metric": "f1_weighted", "scores": [round(float(x), 4) for x in scores], "mean": round(float(np.mean(scores)), 4), "std": round(float(np.std(scores)), 4), "summary": f"{folds}-fold stratified CV weighted F1: {np.mean(scores):.3f} ± {np.std(scores):.3f}"}
                    else:
                        cross_validation["summary"] = "Skipped: at least two samples per class are required for stratified CV."
                else:
                    folds = min(5, len(y_train))
                    if folds >= 2:
                        cv = KFold(n_splits=folds, shuffle=True, random_state=42)
                        scores = cross_val_score(fold_pipeline, X_train_raw, y_train, cv=cv, scoring="neg_root_mean_squared_error", error_score="raise")
                        rmse_scores = (-scores).tolist()
                        cross_validation = {"performed": True, "strategy": "KFold", "folds": folds, "metric": "rmse", "scores": [round(float(x), 4) for x in rmse_scores], "mean": round(float(np.mean(rmse_scores)), 4), "std": round(float(np.std(rmse_scores)), 4), "summary": f"{folds}-fold CV RMSE: {np.mean(rmse_scores):.3f} ± {np.std(rmse_scores):.3f}"}
        except Exception as exc:
            cross_validation = {"performed": False, "summary": "Cross-validation failed safely; holdout metrics retained.", "error_type": type(exc).__name__}
    elif model_results and X_train_raw is not None and len(X_train_raw) > max_cv_rows:
        cross_validation = {"performed": False, "summary": f"Skipped for performance: {len(X_train_raw):,} training rows exceed the {max_cv_rows:,}-row CV limit. Holdout metrics are retained."}
    progress(80, "Validation checks complete", 8)

    # 9. Explainability for the best available model.
    explainability: dict[str, Any] = {}
    if model_results and trained_estimators:
        best = max(
            model_results,
            key=lambda result: CriticAgent._score(result, plan.primary_metric),
        )
        estimator = trained_estimators.get(best.model_name)
        if estimator is not None:
            explainability = ExplainabilityAgent().explain_model(
                estimator=estimator,
                feature_names=feature_names,
                X_sample=X_val,
            )
            explainability["best_model"] = best.model_name
    progress(87, "Model explanations complete", 9)

    # Persist the winning estimator together with its fitted preprocessing object.
    artifact = {"status": "not_created", "reason": "No fitted model/preprocessor available."}
    if model_results and trained_estimators and fitted_preprocessor is not None:
        try:
            best_artifact_model = max(model_results, key=lambda item: CriticAgent._score(item, plan.primary_metric))
            winning_estimator = trained_estimators.get(best_artifact_model.model_name)
            if winning_estimator is not None:
                artifact = {"status": "saved", **ArtifactStore(Path(__import__("os").getenv("DATAPILOT_DATA_DIR", str(Path(__file__).resolve().parents[1]))).resolve() / "artifacts").save_model(winning_estimator, fitted_preprocessor, best_artifact_model.model_name, feature_names, preprocessing.get("datetime_columns", []), target_classes)}
        except Exception as exc:
            artifact = {"status": "failed", "error_type": type(exc).__name__}

    preview_rows = df.head(5).fillna("").to_dict(orient="records")

    status = "success"
    if not model_results and plan.problem_type != "unknown":
        status = "partial"

    result = {
        "status": status,
        "data_engine": engine_profile,
        "dataset_summary": {
            "rows": profile.rows,
            "columns_count": len(profile.columns),
            "columns": [column.to_dict() for column in profile.columns],
            "duplicate_rows": profile.duplicate_rows,
            "class_imbalance_ratio": profile.class_imbalance_ratio,
            "warnings": list(profile.warnings),
            "preview": preview_rows,
        },
        "plan": plan.to_dict(),
        "security": security.to_dict(),
        "preprocessing": preprocessing,
        "eda": eda,
        "statistics": statistics,
        "cross_validation": cross_validation,
        "artifact": artifact,
        "models": [model.to_dict() for model in model_results],
        "explainability": explainability,
        "critic": critic.to_dict(),
        "execution_errors": model_errors,
        "replanning": {"max_retries": 1, "history": replan_history, "attempted_models": sorted(attempted_models)},
    }
    progress(91, "Research and methodology review", 10)
    result["research"] = ResearchAgent().investigate(profile, plan, tuple(model_results), preprocessing, dataset_name=dataset_name)
    result["mlflow"] = {"enabled": False, "status": "deferred_to_orchestrator"}
    result["report"] = ReportingAgent().generate(result, dataset_name=dataset_name)
    progress(98, "Generating final report", 10)
    return result


def run_pipeline(
    df: pd.DataFrame, inquiry: str = "", target_column: str | None = None,
    problem_type: ProblemType = "unknown", dataset_name: str = "uploaded dataset", progress_callback=None
) -> dict[str, Any]:
    """Execute analysis through the LangGraph-controlled V3 lifecycle."""
    from .orchestration.graph import run_langgraph_pipeline
    return run_langgraph_pipeline(df, inquiry, target_column, problem_type, dataset_name, progress_callback=progress_callback)
