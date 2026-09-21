"""SQLite-backed rule snapshots for the single-process research service."""
from collections.abc import MutableMapping
import json
from pathlib import Path
import sqlite3


class RuleStore(MutableMapping):
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS rules (id TEXT PRIMARY KEY, document TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def __getitem__(self, key):
        with self.connect() as connection:
            row = connection.execute("SELECT document FROM rules WHERE id=?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return json.loads(row[0])

    def __setitem__(self, key, value):
        with self.connect() as connection:
            connection.execute("INSERT INTO rules VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET document=excluded.document",
                               (key, json.dumps(value)))

    def __delitem__(self, key):
        with self.connect() as connection:
            connection.execute("DELETE FROM rules WHERE id=?", (key,))

    def __iter__(self):
        with self.connect() as connection:
            return iter([row[0] for row in connection.execute("SELECT id FROM rules ORDER BY id")])

    def __len__(self):
        with self.connect() as connection:
            return connection.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
