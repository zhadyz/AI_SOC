"""Narrow response API for containers belonging to the ai-soc-lab project.

No Docker socket is exposed to an SOC container. This local controller accepts
three typed actions and operates only on the lab target, never arbitrary hosts.
"""
import ipaddress
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import threading
import time
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from services.common.api_security import protect_app

STATE = Path(os.getenv("AI_SOC_LAB_STATE", "work/lab"))
STATE.mkdir(parents=True, exist_ok=True)
DB = STATE / "actions.sqlite"
LOCK = threading.Lock()
NETWORK = "ai-soc-lab_workload"
TARGET_IP = "172.30.77.10"
PROBE_IP = "172.30.77.20"


def docker(*args, data=None, check=True):
    result = subprocess.run(["docker", *args], input=data, text=True, capture_output=True, timeout=30)
    if check and result.returncode:
        raise RuntimeError("Lab container operation failed: " + result.stderr[:400])
    return result


def container(service):
    if service not in {"target", "probe", "manager"}:
        raise ValueError("Unknown lab service")
    ids = docker("ps", "-q", "--filter", "label=com.docker.compose.project=ai-soc-lab",
                 "--filter", "label=com.docker.compose.service=" + service,
                 "--filter", "label=ai-soc.lab=true").stdout.split()
    if len(ids) != 1:
        raise RuntimeError("Expected exactly one running lab " + service)
    details = json.loads(docker("inspect", ids[0]).stdout)[0]
    if details["Config"]["Labels"].get("ai-soc.lab") != "true":
        raise RuntimeError("Target is outside the managed lab")
    return ids[0], details


class Action(BaseModel):
    action_type: Literal["block_ip", "isolate_host", "disable_account"]
    target: str = Field(min_length=1, max_length=128)
    operation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")


def validate_action(action):
    if action.action_type == "block_ip":
        if str(ipaddress.ip_address(action.target)) != PROBE_IP:
            raise ValueError("Only the lab probe IP can be blocked")
    elif action.action_type == "isolate_host":
        if action.target not in {"lab-target", TARGET_IP}:
            raise ValueError("Only lab-target can be isolated")
        # Both supported names refer to the same effect/rollback lease.
        action.target = "lab-target"
    elif action.action_type == "disable_account" and action.target != "lab-user":
        raise ValueError("Only lab-user can be disabled")


def observe(action):
    cid, details = container("target")
    if action.action_type == "block_ip":
        result = docker("exec", cid, "cat", "/run/ai-soc/blocked-ips.json")
        elements = json.loads(result.stdout)
        if not isinstance(elements, list):
            raise ValueError("Invalid lab gateway policy")
        return {"active": action.target in elements, "container_id": details["Id"], "blocked_ips": elements,
                "scope": "Lab ingress gateway: HTTP 8080 and SSH 2222"}
    if action.action_type == "isolate_host":
        networks = details["NetworkSettings"]["Networks"]
        if set(networks) - {NETWORK}:
            raise ValueError("Target has an unexpected network; isolated-lab scope is no longer valid")
        return {"active": not networks, "container_id": details["Id"], "networks": list(networks)}
    # The pinned Wazuh image has shadow-utils but no passwd executable. Query
    # shadow inside the target and return only lock status, never its hash.
    status = docker("exec", cid, "python3", "-c",
                    "import spwd; h=spwd.getspnam('lab-user').sp_pwdp; print('L' if h.startswith(('!','*')) else 'P')").stdout.strip()
    if status not in {"L", "P"}:
        raise RuntimeError("Unexpected lab account state")
    return {"active": status == "L", "container_id": details["Id"], "account_status": status}


def connect():
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, request TEXT NOT NULL, previous TEXT NOT NULL, phase TEXT NOT NULL, updated REAL NOT NULL)")
    return db


def result(action, operation, evidence, success=True):
    return {"success": success, "action_type": action.action_type, "target": action.target,
            "detail": f"Lab {operation}: independently observed container state",
            "evidence": evidence, "rollback_capable": True, "simulated": False}


def perform(action, operation):
    validate_action(action)
    with LOCK, connect() as db:
        current = observe(action)
        row = db.execute("SELECT * FROM actions WHERE id=?", (action.operation_id,)).fetchone()
        if row:
            if json.loads(row["request"]) != action.model_dump():
                raise ValueError("Operation ID was already used for a different request")
            previous = json.loads(row["previous"])
            if previous["container_id"] != current["container_id"]:
                raise ValueError("Lab target was recreated; historical rollback is unsafe")
        elif operation == "execute":
            for other in db.execute("SELECT request FROM actions WHERE phase IN ('intent','executed','uncertain')"):
                owned = json.loads(other[0])
                if (owned["action_type"], owned["target"]) == (action.action_type, action.target):
                    raise ValueError("Another active operation owns this target; roll it back first")
            previous = current
            db.execute("INSERT INTO actions VALUES (?,?,?,?,?)", (action.operation_id, action.model_dump_json(), json.dumps(previous), "intent", time.time()))
            db.commit()  # Durable intent before effect.
        elif operation == "rollback":
            raise ValueError("No recorded action to roll back")
        if operation == "verify":
            return result(action, operation, current, current["active"])
        if row and row["phase"] == "rolled_back" and operation == "execute":
            raise ValueError("A rolled-back operation cannot be replayed")
        desired = True if operation == "execute" else previous["active"]
        if current["active"] != desired:
            cid, _ = container("target")
            if action.action_type == "block_ip":
                update = "import json,os,sys; from pathlib import Path; p=Path('/run/ai-soc/blocked-ips.json'); ips=set(json.loads(p.read_text())); (ips.add if sys.argv[2]=='true' else ips.discard)(sys.argv[1]); q=p.with_suffix('.tmp'); q.write_text(json.dumps(sorted(ips))); q.chmod(0o600); os.replace(q,p)"
                docker("exec", cid, "python3", "-c", update, action.target, "true" if desired else "false")
            elif action.action_type == "isolate_host":
                if desired:
                    docker("network", "disconnect", NETWORK, cid)
                else:
                    docker("network", "connect", "--ip", TARGET_IP, NETWORK, cid)
            else:
                docker("exec", cid, "usermod", "-L" if desired else "-U", "lab-user")
        evidence = observe(action)
        success = evidence["active"] == desired
        db.execute("UPDATE actions SET phase=?, updated=? WHERE id=?",
                   (("executed" if operation == "execute" else "rolled_back") if success else "uncertain", time.time(), action.operation_id))
        return result(action, operation, evidence, success)


app = FastAPI(title="AI-SOC isolated lab controller")
protect_app(app)


@app.get("/health")
def health():
    try:
        _, details = container("target")
        return {"status": "healthy", "target": details["Name"], "scope": "ai-soc-lab only"}
    except RuntimeError:
        raise HTTPException(503, "Lab target is not running")


@app.post("/actions/{operation}")
def action(operation: Literal["execute", "verify", "rollback"], request: Action):
    try:
        return perform(request, operation)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except (RuntimeError, subprocess.TimeoutExpired):
        raise HTTPException(503, "Lab operation failed; inspect target state before retrying")
