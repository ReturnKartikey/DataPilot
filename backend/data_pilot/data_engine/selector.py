"""Select DuckDB for larger tabular workloads, with a Pandas-safe fallback."""
from __future__ import annotations
import os
from typing import Any
import pandas as pd

class PandasEngine:
    name = "pandas"
    def profile(self, frame: pd.DataFrame) -> dict[str, Any]:
        return {"engine": self.name, "rows": int(len(frame)), "columns": int(len(frame.columns)),
                "memory_bytes": int(frame.memory_usage(index=True, deep=True).sum()),
                "null_cells": int(frame.isna().sum().sum()), "duplicate_rows": int(frame.duplicated().sum())}

class DuckDBEngine(PandasEngine):
    name = "duckdb"
    def profile(self, frame: pd.DataFrame) -> dict[str, Any]:
        import duckdb
        con = duckdb.connect(database=":memory:")
        try:
            con.register("dataset", frame)
            rows = int(con.execute("SELECT COUNT(*) FROM dataset").fetchone()[0])
            null_terms = []
            for column in frame.columns:
                safe = '"' + str(column).replace('"', '""') + '"'
                null_terms.append(f"COUNT(*) FILTER (WHERE {safe} IS NULL)")
            null_cells = int(con.execute("SELECT " + " + ".join(null_terms) + " FROM dataset").fetchone()[0]) if null_terms else 0
            duplicates = int(frame.duplicated().sum())
            numeric_summary = {}
            for column in frame.select_dtypes(include="number").columns:
                safe = '"' + str(column).replace('"', '""') + '"'
                row = con.execute(f"SELECT COUNT({safe}), AVG({safe}), STDDEV_SAMP({safe}), MIN({safe}), MAX({safe}) FROM dataset").fetchone()
                numeric_summary[str(column)] = {"count": int(row[0]), "mean": row[1], "std": row[2], "min": row[3], "max": row[4]}
            return {"engine": self.name, "rows": rows, "columns": int(len(frame.columns)),
                    "memory_bytes": int(frame.memory_usage(index=True, deep=True).sum()),
                    "null_cells": null_cells, "duplicate_rows": duplicates, "numeric_summary": numeric_summary}
        finally:
            con.close()

def get_engine(frame: pd.DataFrame | None = None):
    mode = os.getenv("DATAPILOT_DATA_ENGINE", "auto").lower()
    if mode not in {"auto", "pandas", "duckdb"}: mode = "auto"
    threshold = max(1, int(os.getenv("DATAPILOT_DUCKDB_THRESHOLD_MB", "100"))) * 1024 * 1024
    size = int(frame.memory_usage(index=True, deep=True).sum()) if frame is not None else 0
    if mode == "pandas": return PandasEngine()
    try:
        import duckdb  # noqa: F401
        if mode == "duckdb" or (mode == "auto" and size >= threshold): return DuckDBEngine()
    except ImportError:
        if mode == "duckdb": raise RuntimeError("DuckDB was requested but is not installed. Install backend requirements.")
    return PandasEngine()
