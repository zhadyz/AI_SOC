#!/usr/bin/env python3
"""Strict live smoke test. Uses reserved example IPs and never executes defenses."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
PORTS = {"ml": 8500, "triage": 8100, "rag": 8300, "feedback": 8400,
         "correlation": 8600, "response": 8800, "rules": 8700, "wazuh": 8002}


def run(skip_llm=False, full=False):
    key = os.getenv("AI_SOC_API_KEY") or dotenv_values(ROOT/".env").get("AI_SOC_API_KEY", "")
    headers = {"Authorization": f"Bearer {key}"}
    checks = []
    def call(service, path, method="GET", **kwargs):
        response = requests.request(method, f"http://127.0.0.1:{PORTS[service]}{path}",
                                    headers=headers, timeout=240, **kwargs)
        if not response.ok:
            raise RuntimeError(f"{service}{path}: HTTP {response.status_code}: {response.text[:400]}")
        return response.json()
    def passed(name):
        checks.append(name)
        print(f"PASS {name}", flush=True)
    for service in PORTS:
        call(service, "/health")
    assert requests.get("http://localhost:5050/health", timeout=5).status_code == 200
    passed("All eight service health endpoints and dashboard respond")
    assert requests.get("http://127.0.0.1:8500/models", timeout=5).status_code == 401
    passed("Unauthenticated model API access is rejected")
    for model in ("random_forest", "xgboost", "decision_tree"):
        prediction = call("ml", "/predict", "POST", json={"features": [0.0]*77, "model_name": model})
        assert prediction["model_used"] == model and abs(sum(prediction["probabilities"].values())-1) < 1e-5
    passed("All three bundled models produce real predictions")
    result = call("rag", "/retrieve", "POST", json={"query": "SSH brute force incident response",
                  "collection": "security_runbooks", "min_similarity": 0.1, "top_k": 3})
    assert result["results"]
    passed("Runbook retrieval returns embedded security knowledge")
    if skip_llm:
        return {"checks": checks, "llm_exercised": False}
    alert_id = "smoke-" + uuid.uuid4().hex[:12]
    alert = {"alert_id": alert_id, "timestamp": datetime.now(timezone.utc).isoformat(),
             "source_ip": "203.0.113.42", "dest_ip": "10.0.1.50", "rule_id": "5712", "rule_level": 10,
             "rule_description": "Repeated failed SSH logins for root: suspected brute force",
             "mitre_technique": ["T1110"],
             "full_log": {"message": "Twenty failed SSH passwords for root from 203.0.113.42"}}
    triage = call("triage", "/analyze", "POST", json=alert)
    assert triage["alert_id"] == alert_id and triage["incident_id"] and not triage["pipeline_warnings"]
    assert triage["knowledge_base_references"] and triage["ml_prediction"] is None
    stored = call("feedback", f"/alerts/{alert_id}")
    assert stored["alert_id"] == alert_id
    passed("Local LLM triage persists the alert and creates a correlated incident")
    incident_id = triage["incident_id"]
    before = call("correlation", f"/incidents/{incident_id}")["alert_count"]
    correlation = {"alert_id": alert_id, "timestamp": alert["timestamp"], "source_ip": alert["source_ip"],
                   "dest_ip": alert["dest_ip"], "severity": triage["severity"], "category": triage["category"],
                   "mitre_techniques": triage["mitre_techniques"], "mitre_tactics": triage["mitre_tactics"]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: call("correlation", "/correlate", "POST", json=correlation), range(2)))
    assert all(result["incident_id"] == incident_id and result["incident_alert_count"] == before for result in results)
    passed("Concurrent retries do not duplicate incident alerts")
    feedback = call("feedback", f"/feedback/{alert_id}", "POST", json={"analyst_id": "smoke-analyst",
                    "true_label": "ATTACK", "is_false_positive": False, "notes": "Synthetic workflow check"})
    review = call("feedback", f"/feedback/reviews/{feedback['feedback_id']}", "POST",
                  json={"reviewer_id": "smoke-reviewer", "approved": True})
    assert review["approved"]
    passed("Independent feedback review is recorded")
    plan = call("response", "/defend", "POST", json={"incident_id": incident_id, "dry_run": True,
                "auto_execute": False, "skip_simulation": True})
    assert plan["status"] == "dry_run_completed" and plan["dry_run"]
    assert all(action["executed_at"] is None for action in plan["actions"])
    events = call("response", f"/plans/{plan['plan_id']}/events")
    assert any(event["event"] == "dry_run_completed" for event in events)
    passed("Defense dry run produces a stored plan and audit trail without real actions")
    if full:
        rule = call("rules", "/generate", "POST", json={"alert_id": alert_id,
                    "alert_description": "Windows EventID 4625 failed logon from repeated attempts",
                    "sample_event": {"EventID": 4625}, "logsource": {"product": "windows", "service": "security"},
                    "mitre_techniques": ["T1110"], "severity": "high"})
        assert rule["rule"]["status"] == "pending" and rule["backtest"]["status"] == "not_evaluated"
        passed("Grounded Sigma draft is generated and remains pending review")
        tested = call("rules", f"/rules/{rule['rule']['rule_id']}/backtest", "POST", json={"events": [
            {"event": {"EventID": 4625}, "label": "ATTACK"},
            {"event": {"EventID": 4624}, "label": "BENIGN"}]})
        assert tested["total_tested"] == 2 and tested["benign_events"] == 1
        assert tested["matches"] == 1 and tested["false_positive_rate"] == 0.0
        passed("Generated rule backtest counts supplied labeled events")
        webhook = call("wazuh", "/webhook", "POST", json={"id": alert_id + "-wazuh",
            "timestamp": alert["timestamp"], "rule": {"id": "5712", "level": 10,
            "description": alert["rule_description"], "mitre": {"id": ["T1110"]}},
            "agent": {"id": "001", "ip": "10.0.1.50", "name": "lab-example"},
            "data": {"srcip": "203.0.113.42", "dstip": "10.0.1.50"},
            "full_log": alert["full_log"]["message"]})
        assert webhook["wazuh_alert_id"] == alert_id + "-wazuh" and webhook["incident_id"]
        assert call("feedback", f"/alerts/{alert_id}-wazuh")["alert_id"] == alert_id + "-wazuh"
        passed("Wazuh-format webhook completes triage, storage and correlation")
        simulation = call("correlation", "/simulate?timesteps=1", "POST")
        assert simulation.get("simulation_id") and "results_summary" in simulation
        passed("Local attack-campaign simulation completes")
    return {"checks": checks, "llm_exercised": True, "full": full,
            "rule_generation_method": rule["rule"]["generation_method"] if full else None,
            "rule_id": rule["rule"]["rule_id"] if full else None,
            "alert_id": alert_id, "incident_id": incident_id, "plan_id": plan["plan_id"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args.skip_llm, args.full)
    report["verified_at"] = datetime.now(timezone.utc).isoformat()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+"\n")
