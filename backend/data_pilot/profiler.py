"""Deterministic tabular data profiler for Data Pilot."""

from __future__ import annotations

import re
from typing import Any
import numpy as np
import pandas as pd

from .agents.schemas import ColumnKind, ColumnProfile, DatasetProfile


def _classify_column(series: pd.Series) -> ColumnKind:
    """Classifies a pandas Series into ColumnKind."""
    dtype = series.dtype

    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"
    if pd.api.types.is_numeric_dtype(dtype):
        return "numeric"

    # Datetime string detection
    if pd.api.types.is_string_dtype(dtype) or pd.api.types.is_object_dtype(dtype):
        sample = series.dropna().head(20)
        if len(sample) > 0:
            date_pattern = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")
            if sample.astype(str).str.match(date_pattern).all():
                return "datetime"

    return "categorical"


def profile_dataframe(df: pd.DataFrame, target_column: str | None = None) -> DatasetProfile:
    """Profiles a pandas DataFrame deterministically to produce a DatasetProfile."""
    rows = len(df)
    columns_list: list[ColumnProfile] = []
    warnings: list[str] = []

    for col in df.columns:
        series = df[col]
        col_name = str(col)
        unique_cnt = int(series.nunique(dropna=True))
        missing_cnt = int(series.isna().sum())
        kind = _classify_column(series)

        columns_list.append(
            ColumnProfile(
                name=col_name,
                kind=kind,
                unique_count=unique_cnt,
                missing_count=missing_cnt,
            )
        )

        if missing_cnt > 0:
            pct = round((missing_cnt / max(1, rows)) * 100, 1)
            if pct > 15:
                warnings.append(f"Column '{col_name}' has high missing rate: {missing_cnt} missing rows ({pct}%).")
        if unique_cnt == 1 and rows > 1:
            warnings.append(f"Column '{col_name}' is constant with only 1 unique value.")

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows > 0:
        warnings.append(f"Dataset contains {duplicate_rows} duplicate rows.")

    # Target column resolution & heuristics
    col_names = [str(c) for c in df.columns]
    target_candidates: list[str] = []

    if target_column and target_column in col_names:
        target_candidates = [target_column]
    else:
        # Common target keywords
        keywords = ("target", "label", "churn", "price", "outcome", "status", "class", "revenue", "converted", "default")
        for name in col_names:
            lower_name = name.lower()
            if any(kw in lower_name for kw in keywords):
                target_candidates.append(name)

        # Fallback: if no keyword matches and columns exist, suggest the last column
        if not target_candidates and col_names:
            last_col = col_names[-1]
            last_col_prof = next((c for c in columns_list if c.name == last_col), None)
            if last_col_prof and (last_col_prof.kind in {"categorical", "boolean"} or last_col_prof.unique_count > 1):
                target_candidates.append(last_col)

    # Calculate class imbalance if target is categorical/boolean or binary numeric (e.g. 0 and 1)
    class_imbalance_ratio: float | None = None
    active_target = target_column if (target_column and target_column in col_names) else (target_candidates[0] if len(target_candidates) == 1 else None)

    if active_target:
        target_series = df[active_target].dropna()
        target_col_prof = next((c for c in columns_list if c.name == active_target), None)
        if target_col_prof:
            is_binary_numeric = False
            if target_col_prof.kind == "numeric":
                unique_vals = set(target_series.unique())
                if unique_vals.issubset({0, 1, 0.0, 1.0}) or len(unique_vals) <= 2:
                    is_binary_numeric = True

            if target_col_prof.kind in {"categorical", "boolean"} or is_binary_numeric:
                counts = target_series.value_counts()
                if len(counts) >= 2:
                    min_c = float(counts.min())
                    max_c = float(counts.max())
                    class_imbalance_ratio = round(min_c / max_c, 3) if max_c > 0 else 1.0

    return DatasetProfile(
        rows=rows,
        columns=tuple(columns_list),
        duplicate_rows=duplicate_rows,
        potential_target_columns=tuple(target_candidates),
        class_imbalance_ratio=class_imbalance_ratio,
        warnings=tuple(warnings),
    )
