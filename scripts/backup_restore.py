#!/usr/bin/env python3
"""Cold backup of the native stack and a restore drill in a fresh PostgreSQL DB.

Stop scripts/local_stack.py before backup. PostgreSQL remains running. Backups
contain credentials and are private directories; keep them on protected storage.
The drill never overwrites the working database or runtime directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.local_stack import occupied


def pg(*args, data=None):
    result = subprocess.run(["docker", "compose", "exec", "-T", "postgres", *args],
                            cwd=ROOT, input=data, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"PostgreSQL operation {args[0]} failed: {result.stderr.decode()[:1000]}")
    return result.stdout


def counts(database):
    tables = pg("psql", "-U", "ai_soc", "-d", database, "-Atc",
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").decode().splitlines()
    result = {}
    for table in tables:
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", table):
            raise ValueError("Unexpected table name")
        result[table] = int(pg("psql", "-U", "ai_soc", "-d", database, "-Atc", f'SELECT count(*) FROM "{table}"'))
    return result


def backup(state, destination):
    records = state / "processes.json"
    if records.exists() and any(occupied(row["port"]) for row in json.loads(records.read_text()).values()):
        raise ValueError("Stop the native stack before creating a consistent cold backup")
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(destination, 0o700)
    (destination / "postgres.dump").write_bytes(pg("pg_dump", "-U", "ai_soc", "-d", "ai_soc", "-Fc", "--no-owner"))
    config = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines()
                  if line and not line.startswith("#") and "=" in line)
    shutil.copy2(ROOT / ".env", destination / "config.env")
    shutil.copytree(ROOT / "models", destination / "models")
    for name in ("chroma", "simulation"):
        if (state / name).exists():
            shutil.copytree(state / name, destination / name)
    sources = {"rules.sqlite": state / "rules.sqlite",
               "triage-jobs.sqlite": state / "triage-jobs.sqlite",
               "identity.sqlite": Path(config["AI_SOC_IDENTITY_DIR"]) / "identity.sqlite"}
    for name, source in sources.items():
        if source.exists():
            with sqlite3.connect(source) as src, sqlite3.connect(destination / name) as dst:
                src.backup(dst)
    manifest = {"version": 1, "postgres_row_counts": counts("ai_soc"), "sha256": {}}
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            os.chmod(path, 0o600)
            manifest["sha256"][str(path.relative_to(destination))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    os.chmod(destination / "manifest.json", 0o600)
    return {"backup": str(destination), "files": len(manifest["sha256"]), "row_counts": manifest["postgres_row_counts"]}


def verify_backup(source):
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text())
    for name, digest in manifest["sha256"].items():
        path = (source / name).resolve()
        if not path.is_relative_to(source) or not path.is_file():
            raise ValueError("Invalid backup path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Backup checksum mismatch: {name}")
    return manifest


def restore_drill(source, report=None):
    manifest = verify_backup(source)
    database = "ai_soc_restore_" + uuid.uuid4().hex
    pg("createdb", "-U", "ai_soc", database)
    try:
        pg("pg_restore", "-U", "ai_soc", "-d", database, "--no-owner", "--exit-on-error",
           data=(source / "postgres.dump").read_bytes())
        restored = counts(database)
        if restored != manifest["postgres_row_counts"]:
            raise ValueError("Restored row counts differ from the snapshot")
        sqlite_checks = {}
        for filename in ("rules.sqlite", "identity.sqlite", "triage-jobs.sqlite", "chroma/chroma.sqlite3"):
            if (source / filename).exists():
                with sqlite3.connect(f"file:{source / filename}?mode=ro", uri=True) as db:
                    result = db.execute("PRAGMA integrity_check").fetchone()[0]
                    if result != "ok":
                        raise ValueError(f"Invalid SQLite backup: {filename}")
                    sqlite_checks[filename] = result
        result = {"status": "passed", "postgres_restored_row_counts": restored,
                  "sqlite_integrity": sqlite_checks, "verified_files": len(manifest["sha256"]),
                  "working_database_changed": False, "temporary_database_removed": True}
    finally:
        pg("dropdb", "-U", "ai_soc", database)
    if report:
        report.write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "drill"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--state-dir", type=Path, default=ROOT / "work/runtime")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = backup(args.state_dir.resolve(), args.directory.resolve()) if args.action == "backup" else restore_drill(args.directory.resolve(), args.report)
    print(json.dumps(result, indent=2))
