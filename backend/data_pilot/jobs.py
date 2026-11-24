"""SQLite-backed analysis job state for the single-node academic deployment."""
from __future__ import annotations
import json, sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

class AnalysisJobStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with closing(self._connect()) as db:
            db.execute("CREATE TABLE IF NOT EXISTS analysis_jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, dataset_name TEXT NOT NULL, result_json TEXT, error_code TEXT, progress_percent INTEGER NOT NULL DEFAULT 0, current_stage TEXT NOT NULL DEFAULT 'Queued', completed_steps INTEGER NOT NULL DEFAULT 0, total_steps INTEGER NOT NULL DEFAULT 11)")
            existing = {row[1] for row in db.execute("PRAGMA table_info(analysis_jobs)").fetchall()}
            for name, declaration in (("progress_percent", "INTEGER NOT NULL DEFAULT 0"), ("current_stage", "TEXT NOT NULL DEFAULT 'Queued'"), ("completed_steps", "INTEGER NOT NULL DEFAULT 0"), ("total_steps", "INTEGER NOT NULL DEFAULT 11")):
                if name not in existing:
                    db.execute(f"ALTER TABLE analysis_jobs ADD COLUMN {name} {declaration}")
            db.commit()
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=15000")
        return db
    def create(self, job_id: str, dataset_name: str):
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            db.execute("INSERT INTO analysis_jobs (id,status,created_at,updated_at,dataset_name) VALUES (?,?,?,?,?)", (job_id,"queued",now,now,dataset_name))
            db.commit()
    def update(self, job_id: str, status: str, result: dict | None = None, error_code: str | None = None,
               progress_percent: int | None = None, current_stage: str | None = None,
               completed_steps: int | None = None, total_steps: int | None = None):
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            db.execute("""UPDATE analysis_jobs SET status=?, updated_at=?,
                result_json=COALESCE(?, result_json), error_code=?,
                progress_percent=COALESCE(?, progress_percent), current_stage=COALESCE(?, current_stage),
                completed_steps=COALESCE(?, completed_steps), total_steps=COALESCE(?, total_steps)
                WHERE id=?""", (status, now, json.dumps(result,default=str) if result is not None else None,
                    error_code, progress_percent, current_stage, completed_steps, total_steps, job_id))
            db.commit()

    def progress(self, job_id: str, percent: int, stage: str, completed_steps: int, total_steps: int = 11):
        self.update(job_id, "running", progress_percent=max(0, min(99, int(percent))),
                    current_stage=stage, completed_steps=completed_steps, total_steps=total_steps)

    def recover_interrupted(self):
        """Mark jobs left active by a process restart as interrupted, not running forever."""
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            cursor = db.execute("""UPDATE analysis_jobs SET status='failed', updated_at=?,
                error_code='server_restarted', current_stage='Interrupted by server restart'
                WHERE status IN ('queued','running')""", (now,))
            db.commit()
            return int(cursor.rowcount)
    def list(self, limit: int = 30, statuses: tuple[str, ...] | None = None):
        query = "SELECT id,status,created_at,updated_at,dataset_name,error_code,progress_percent,current_stage,completed_steps,total_steps FROM analysis_jobs"
        params = []
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            query += f" WHERE status IN ({placeholders})"
            params.extend(statuses)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 100)))
        with closing(self._connect()) as db:
            rows = db.execute(query, params).fetchall()
        return [{"id":r[0],"status":r[1],"created_at":r[2],"updated_at":r[3],
                 "dataset_name":r[4],"error_code":r[5],"progress_percent":r[6],"current_stage":r[7],"completed_steps":r[8],"total_steps":r[9]} for r in rows]
    def get(self, job_id: str):
        with closing(self._connect()) as db:
            row = db.execute("SELECT id,status,created_at,updated_at,dataset_name,result_json,error_code,progress_percent,current_stage,completed_steps,total_steps FROM analysis_jobs WHERE id=?", (job_id,)).fetchone()
        if not row: return None
        return {"id":row[0],"status":row[1],"created_at":row[2],"updated_at":row[3],"dataset_name":row[4],"result":json.loads(row[5]) if row[5] else None,"error_code":row[6],"progress_percent":row[7],"current_stage":row[8],"completed_steps":row[9],"total_steps":row[10]}
