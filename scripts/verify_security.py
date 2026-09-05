#!/usr/bin/env python3
"""Exercise live login, roles, independent review, export and bounded inference load."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import secrets
import time
import uuid

from dotenv import dotenv_values
import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:5050"


def login(username, password):
    client = requests.Session()
    form = client.get(BASE + "/login", timeout=10)
    form.raise_for_status()
    csrf = re.search(r'name="csrf" value="([^"]+)"', form.text)[1]
    response = client.post(BASE + "/login", data={"username": username, "password": password, "csrf": csrf}, timeout=20)
    response.raise_for_status()
    me = client.get(BASE + "/api/auth/me", timeout=10)
    me.raise_for_status()
    assert me.json()["username"] == username
    client.headers["X-CSRF-Token"] = me.json()["csrf"]
    return client


def run():
    config = dotenv_values(ROOT / ".env")
    credentials = (Path(config["AI_SOC_IDENTITY_DIR"]).parent / "admin-credentials.txt").read_text()
    admin = login("admin", credentials.split("Password: ", 1)[1].strip())
    suffix = uuid.uuid4().hex[:8]
    users, created = {}, []
    checks = []
    def passed(message):
        checks.append(message)
        print("PASS", message, flush=True)
    try:
        for role in ("viewer", "analyst", "reviewer"):
            username, password = "check-" + role + "-" + suffix, secrets.token_urlsafe(24)
            response = admin.post(BASE + "/api/auth/users", json={"username": username, "password": password, "role": role}, timeout=10)
            assert response.status_code == 201, response.text
            created.append(username)
            users[role] = (username, login(username, password))
        passed("Persistent accounts sign in with distinct viewer, analyst and reviewer roles")
        viewer = users["viewer"][1]
        assert requests.get(BASE + "/api/services", timeout=10).status_code == 401
        assert viewer.post(BASE + "/api/feedback/unknown", json={}, timeout=10).status_code == 403
        assert viewer.get(BASE + "/api/auth/users", timeout=10).status_code == 403
        saved_csrf = viewer.headers.pop("X-CSRF-Token")
        assert viewer.post(BASE + "/api/auth/token", timeout=10).status_code == 403
        viewer.headers["X-CSRF-Token"] = saved_csrf
        passed("Anonymous access, viewer writes, privilege escalation and missing CSRF are rejected")
        evidence = json.loads((ROOT / "docs/development/live-verification.json").read_text())
        alert_id = evidence["alert_id"]
        analyst_name, analyst = users["analyst"]
        reviewer_name, reviewer = users["reviewer"]
        feedback = analyst.post(BASE + f"/api/feedback/{alert_id}", json={"analyst_id": "forged-author", "true_label": "ATTACK", "is_false_positive": False, "notes": "Automated security acceptance; synthetic alert"}, timeout=10)
        feedback.raise_for_status()
        feedback_id = feedback.json()["feedback_id"]
        review_path = BASE + "/api/feedback/reviews/" + feedback_id
        assert analyst.post(review_path, json={"reviewer_id": "forged-reviewer", "approved": True}, timeout=10).status_code == 403
        reviewed = reviewer.post(review_path, json={"reviewer_id": "forged-reviewer", "approved": True}, timeout=10)
        reviewed.raise_for_status()
        assert reviewed.json()["reviewer_id"] == reviewer_name
        alert = reviewer.get(BASE + f"/api/alerts/{alert_id}", timeout=10).json()
        assert any(f["feedback_id"] == feedback_id and f["analyst_id"] == analyst_name for f in alert["feedback"])
        self_label = reviewer.post(BASE + f"/api/feedback/{alert_id}", json={"analyst_id": "forged-author", "true_label": "ATTACK", "is_false_positive": False}, timeout=10).json()["feedback_id"]
        assert reviewer.post(BASE + "/api/feedback/reviews/" + self_label, json={"reviewer_id": analyst_name, "approved": True}, timeout=10).status_code == 422
        passed("Services bind audit authors to verified identities and enforce independent review")
        rule_id = evidence.get("rule_id") or next(r["rule_id"] for r in reviewer.get(BASE + "/api/rules", timeout=10).json()["rules"] if r.get("source_alert_id") == alert_id)
        approved = reviewer.put(BASE + f"/api/rules/{rule_id}/approve", params={"analyst_id": "forged-reviewer", "notes": "Automated export acceptance; controlled smoke rule"}, timeout=10)
        approved.raise_for_status()
        assert approved.json()["reviewed_by"] == reviewer_name
        export = reviewer.get(BASE + f"/api/rules/{rule_id}/export", timeout=10)
        assert export.status_code == 200 and "detection:" in export.text
        assert "attachment" in export.headers["Content-Disposition"]
        for page in ("/", "/reviews", "/account"):
            response = reviewer.get(BASE + page, timeout=10)
            assert response.status_code == 200 and response.headers["X-Frame-Options"] == "DENY"
        passed("Authenticated review pages render and approved rules download as YAML")
        token = viewer.post(BASE + "/api/auth/token", timeout=10).json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        assert requests.post("http://127.0.0.1:8500/models/reload", headers=headers, timeout=10).status_code == 403
        def prediction(_):
            start = time.perf_counter()
            response = requests.post("http://127.0.0.1:8500/predict", headers=headers,
                                     json={"features": [0.0] * 77}, timeout=30)
            assert response.status_code == 200
            assert response.json()["prediction"] in {"ATTACK", "BENIGN"}
            return (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=10) as pool:
            latencies = list(pool.map(prediction, range(100)))
        load = {"requests": len(latencies), "concurrency": 10, "failed": 0,
                "elapsed_seconds": round(time.perf_counter() - start, 3),
                "p50_ms": round(float(np.percentile(latencies, 50)), 2),
                "p95_ms": round(float(np.percentile(latencies, 95)), 2),
                "input": "Synthetic zero-valued complete flows; throughput test only"}
        passed("Direct service tokens preserve roles; 100 concurrent-workload inference requests succeed")
    finally:
        for username in created:
            response = admin.patch(BASE + "/api/auth/users/" + username, json={"active": False}, timeout=10)
            response.raise_for_status()
    assert viewer.get(BASE + "/api/auth/me", timeout=10).status_code == 401
    passed("Disabling test accounts revokes their browser sessions")
    return {"status": "passed", "checks": checks, "inference_load": load,
            "test_accounts_disabled": created, "browser_visual_review": "Requires an unlocked desktop"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), indent=2) + "\n")
