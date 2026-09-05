"""Durable accepted triage jobs for the single-process worker pool."""
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3


class JobStore:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, input TEXT NOT NULL, result TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def save(self, job, result):
        with self.connect() as db:
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET result=excluded.result,status=excluded.status",
                       (job.job_id, json.dumps(asdict(job)), json.dumps(asdict(result)), result.status, job.created_at))

    def load(self):
        with self.connect() as db:
            # Finished job payloads stay on disk; only unfinished work is loaded.
            return [(json.loads(row[0]), json.loads(row[1])) for row in db.execute(
                "SELECT input,result FROM jobs WHERE status IN ('queued','processing') ORDER BY created")]

    def get(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT result FROM jobs WHERE id=?", (job_id,)).fetchone()
            return json.loads(row[0]) if row else None
