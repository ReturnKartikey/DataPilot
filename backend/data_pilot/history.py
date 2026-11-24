"""Local SQLite experiment history; stores analysis metadata and JSON results."""
from __future__ import annotations
import json, sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

class ExperimentStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with closing(self._connect()) as db:
            db.execute("CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, dataset_name TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL)")
            db.commit()
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=15000")
        return db
    def save(self, dataset_name: str, result: dict) -> str:
        experiment_id = str(uuid4())
        with closing(self._connect()) as db:
            db.execute("INSERT INTO experiments VALUES (?, ?, ?, ?, ?)", (experiment_id, datetime.now(timezone.utc).isoformat(), dataset_name, result.get("status", "unknown"), json.dumps(result, default=str)))
            db.commit()
        return experiment_id
    def list(self, limit: int = 20):
        with closing(self._connect()) as db:
            rows = db.execute("SELECT id, created_at, dataset_name, status FROM experiments ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
        return [{"id":r[0], "created_at":r[1], "dataset_name":r[2], "status":r[3]} for r in rows]
    def get(self, experiment_id: str):
        with closing(self._connect()) as db:
            row = db.execute("SELECT result_json FROM experiments WHERE id=?", (experiment_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def update_result(self, experiment_id: str, result: dict) -> bool:
        with closing(self._connect()) as db:
            cursor = db.execute("UPDATE experiments SET result_json=? WHERE id=?", (json.dumps(result, default=str), experiment_id))
            db.commit()
            return cursor.rowcount > 0
