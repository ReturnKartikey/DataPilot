"""Deterministic EDA Agent."""

from __future__ import annotations

import numpy as np
import pandas as pd


class EDAAgent:
    """Produces reproducible exploratory statistics from a DataFrame."""

    def analyze(self, df: pd.DataFrame, target_column: str | None = None) -> dict:
        numerical = df.select_dtypes(include=np.number)
        categorical = df.select_dtypes(exclude=np.number)

        result = {
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "numeric_columns": list(numerical.columns),
            "categorical_columns": list(categorical.columns),
            "numeric_summary": {},
            "histograms": {},
            "categorical_summary": {},
            "correlations": {},
            "outliers": {},
            "missing_values": {
                column: int(value)
                for column, value in df.isna().sum().items()
                if int(value) > 0
            },
            "warnings": [],
        }

        if not numerical.empty:
            summary = numerical.describe().round(4)
            result["numeric_summary"] = summary.where(
                pd.notna(summary), None
            ).to_dict()
            for column in numerical.columns[:30]:
                series = numerical[column].replace([np.inf, -np.inf], np.nan).dropna()
                if len(series) >= 2:
                    counts, edges = np.histogram(series.to_numpy(dtype=float), bins=min(10, max(2, int(np.sqrt(len(series))))))
                    result["histograms"][str(column)] = {"counts": counts.astype(int).tolist(), "bin_edges": np.round(edges, 5).tolist()}

            correlations = numerical.corr().round(4)
            result["correlations"] = correlations.where(
                pd.notna(correlations), None
            ).to_dict()

        for column in categorical.columns:
            counts = df[column].value_counts(dropna=False).head(10)
            result["categorical_summary"][column] = {
                str(key): int(value)
                for key, value in counts.items()
            }

        for column in numerical.columns:
            series = numerical[column].replace([np.inf, -np.inf], np.nan).dropna()
            if len(series) < 4:
                continue

            q1 = float(series.quantile(0.25))
            q3 = float(series.quantile(0.75))
            iqr = q3 - q1

            if iqr == 0:
                continue

            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            count = int(((series < lower) | (series > upper)).sum())

            result["outliers"][column] = {
                "count": count,
                "percentage": round(count / len(series) * 100, 2),
            }

        if df.duplicated().sum() > 0:
            result["warnings"].append(
                f"{int(df.duplicated().sum())} duplicate rows detected."
            )

        if target_column and target_column in df.columns:
            # Target class distributions exclude missing labels; missingness is reported
            # separately so percentages use the valid labelled population as denominator.
            counts = df[target_column].value_counts(dropna=True).head(20)
            total = int(df[target_column].notna().sum())
            result["target_distribution"] = {str(k): int(v) for k, v in counts.items()}
            result["target_distribution_percentages"] = {
                str(k): round((int(v) / total) * 100, 2) if total else 0.0
                for k, v in counts.items()
            }
            result["target_distribution_rows"] = [
                {"label": str(k), "count": int(v),
                 "percentage": round((int(v) / total) * 100, 2) if total else 0.0}
                for k, v in counts.items()
            ]
        return result
