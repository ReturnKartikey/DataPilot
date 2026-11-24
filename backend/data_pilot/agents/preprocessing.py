"""Data preprocessing agent: strategy + safe executable sklearn transformer."""

from __future__ import annotations

import pandas as pd
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .schemas import DatasetProfile


class IQRClipper(BaseEstimator, TransformerMixin):
    """Learn IQR clipping bounds on training folds only."""
    def fit(self, X, y=None):
        values = np.asarray(X, dtype=float)
        q1 = np.nanquantile(values, 0.25, axis=0)
        q3 = np.nanquantile(values, 0.75, axis=0)
        spread = q3 - q1
        self.lower_ = q1 - 1.5 * spread
        self.upper_ = q3 + 1.5 * spread
        return self
    def transform(self, X):
        values = np.asarray(X, dtype=float)
        return np.clip(values, self.lower_, self.upper_)
    def get_feature_names_out(self, input_features=None):
        return np.asarray(input_features if input_features is not None else [f"x{i}" for i in range(len(self.lower_))], dtype=object)


class PreprocessingAgent:
    """Plans and executes leakage-safe preprocessing.

    The transformer is fitted only on the training split by the pipeline. This
    keeps learned statistics (medians, category vocabularies and scaling) out
    of validation data.
    """

    def create_strategy(
        self,
        df: pd.DataFrame,
        profile: DatasetProfile,
        target_column: str | None = None,
    ) -> dict:
        numeric_columns: list[str] = []
        categorical_columns: list[str] = []
        datetime_columns: list[str] = []

        for column in profile.columns:
            if column.name == target_column:
                continue
            if column.kind == "numeric":
                numeric_columns.append(column.name)
            elif column.kind in {"categorical", "boolean"}:
                categorical_columns.append(column.name)
            elif column.kind == "datetime":
                datetime_columns.append(column.name)

        strategies: list[dict] = []
        if numeric_columns:
            strategies += [
                {"operation": "numeric_imputation", "strategy": "median", "columns": numeric_columns},
                {"operation": "outlier_treatment", "strategy": "training_fold_iqr_clipping", "columns": numeric_columns},
                {"operation": "numeric_scaling", "strategy": "standard_scaler", "columns": numeric_columns},
            ]
        if categorical_columns:
            strategies += [
                {"operation": "categorical_imputation", "strategy": "most_frequent", "columns": categorical_columns},
                {"operation": "categorical_encoding", "strategy": "one_hot", "columns": categorical_columns},
            ]
        if datetime_columns:
            strategies.append({
                "operation": "datetime_handling",
                "strategy": "extract_year_month_day_dayofweek_then_scale",
                "columns": datetime_columns,
            })
        if profile.duplicate_rows:
            strategies.append({"operation": "duplicate_removal", "strategy": "drop"})

        return {
            "target_column": target_column,
            "numeric_columns": numeric_columns,
            "categorical_columns": categorical_columns,
            "datetime_columns": datetime_columns,
            "strategies": strategies,
            "data_leakage_protection": True,
            "execution": "sklearn ColumnTransformer fitted only on training data",
            "notes": [
                "Fit learned transformations only on the training split.",
                "Never transform the target column as a feature.",
                "Unknown categories at validation/inference time are ignored safely.",
                "IQR outlier bounds are learned only from the training data/fold.",
            ],
        }

    @staticmethod
    def _expand_datetime(df: pd.DataFrame, datetime_columns: list[str]) -> pd.DataFrame:
        """Turn datetime columns into numeric calendar features."""
        result = df.copy()
        for col in datetime_columns:
            parsed = pd.to_datetime(result[col], errors="coerce")
            result[f"{col}__year"] = parsed.dt.year
            result[f"{col}__month"] = parsed.dt.month
            result[f"{col}__day"] = parsed.dt.day
            result[f"{col}__dayofweek"] = parsed.dt.dayofweek
            result.drop(columns=[col], inplace=True)
        return result

    def build_transformer(
        self,
        profile: DatasetProfile,
        target_column: str | None = None,
    ) -> tuple[ColumnTransformer, list[str], list[str]]:
        """Build an sklearn transformer without fitting it."""
        numeric_columns: list[str] = []
        categorical_columns: list[str] = []
        datetime_columns: list[str] = []

        for column in profile.columns:
            if column.name == target_column:
                continue
            if column.kind == "numeric":
                numeric_columns.append(column.name)
            elif column.kind in {"categorical", "boolean"}:
                categorical_columns.append(column.name)
            elif column.kind == "datetime":
                datetime_columns.append(column.name)

        datetime_features = [
            f"{col}__{part}"
            for col in datetime_columns
            for part in ("year", "month", "day", "dayofweek")
        ]
        expanded_numeric = numeric_columns + datetime_features

        numeric_pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("outlier_clipper", IQRClipper()),
            ("scaler", StandardScaler()),
        ])
        categorical_pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent", fill_value="missing")),
            ("encoder", OneHotEncoder(
                handle_unknown="ignore",
                sparse_output=False,
                min_frequency=2,
                max_categories=50,
            )),
        ])

        transformers = []
        if expanded_numeric:
            transformers.append(("numeric", numeric_pipeline, expanded_numeric))
        if categorical_columns:
            transformers.append(("categorical", categorical_pipeline, categorical_columns))

        if not transformers:
            # A dataset with no usable predictors gets a constant feature.
            from sklearn.preprocessing import FunctionTransformer
            transformer = ColumnTransformer(
                [("constant", FunctionTransformer(lambda x: [[1.0]] * len(x), validate=False), [])],
                remainder="drop",
            )
        else:
            transformer = ColumnTransformer(
                transformers,
                remainder="drop",
                verbose_feature_names_out=False,
            )

        return transformer, expanded_numeric, datetime_columns

    def prepare_features(
        self,
        X_train: pd.DataFrame,
        X_val: pd.DataFrame,
        profile: DatasetProfile,
        target_column: str | None = None,
    ):
        """Fit on train and transform train/validation with identical rules."""
        transformer, _, datetime_columns = self.build_transformer(profile, target_column)
        train_expanded = self._expand_datetime(X_train, datetime_columns)
        val_expanded = self._expand_datetime(X_val, datetime_columns)

        # Align validation columns exactly to the training schema.
        val_expanded = val_expanded.reindex(columns=train_expanded.columns)

        X_train_t = transformer.fit_transform(train_expanded)
        X_val_t = transformer.transform(val_expanded)

        try:
            feature_names = transformer.get_feature_names_out().tolist()
        except Exception:
            feature_names = [f"feature_{i}" for i in range(X_train_t.shape[1])]

        return X_train_t, X_val_t, feature_names, transformer
