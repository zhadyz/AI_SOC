"""
AI-SOC Command Center — Dashboard Backend
==========================================
Flask proxy server that forwards requests from the frontend to the
individual AI-SOC microservices.  The browser only ever talks to
port 5050 (this process), eliminating all CORS friction.

Run with: python dashboard/app.py
Access at: http://localhost:5050
"""

from flask import Flask, render_template, jsonify, request, Response, g
import subprocess
import json
import requests
import os
from urllib.parse import urlparse
from services.common.api_security import service_headers as machine_headers
from services.common.identity import issue_token
from datetime import datetime

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Service registry
# ---------------------------------------------------------------------------
AI_SERVICES = {
    "ml-inference": {
        "url": "http://localhost:8500",
        "label": "ML Inference",
        "description": "Anomaly detection and threat classification",
    },
    "alert-triage": {
        "url": "http://localhost:8100",
        "label": "Alert Triage",
        "description": "LLM-powered alert analysis",
    },
    "rag-service": {
        "url": "http://localhost:8300",
        "label": "RAG Service",
        "description": "Security knowledge base retrieval",
    },
    "wazuh-integration": {
        "url": "http://localhost:8002",
        "label": "Wazuh Integration",
        "description": "SIEM alert forwarding and enrichment",
    },
    "feedback-service": {
        "url": "http://localhost:8400",
        "label": "Feedback Service",
        "description": "Alert persistence and analyst feedback",
    },
    "correlation-engine": {
        "url": "http://localhost:8600",
        "label": "Correlation Engine",
        "description": "Alert correlation and incident grouping",
    },
    "rule-generator": {
        "url": "http://localhost:8700",
        "label": "Rule Generator",
        "description": "AI-powered Sigma rule generation",
    },
    "response-orchestrator": {
        "url": "http://localhost:8800",
        "label": "Response Orchestrator",
        "description": "Autonomous adaptive defense — simulation-driven response",
    },
}

_PORT_SERVICE = {8500: "ml-inference", 8100: "alert-triage", 8300: "rag-service",
                 8002: "wazuh-integration", 8400: "feedback-service", 8600: "correlation-engine",
                 8700: "rule-generator", 8800: "response-orchestrator"}
for _port, _name in _PORT_SERVICE.items():
    _default = f"http://{_name}:8000" if os.getenv("DASHBOARD_CONTAINER_NETWORK") == "true" else f"http://127.0.0.1:{_port}"
    AI_SERVICES[_name]["url"] = os.getenv(_name.upper().replace("-", "_") + "_URL", _default)


def _service_url(url):
    parsed = urlparse(url)
    if parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port in _PORT_SERVICE:
        return AI_SERVICES[_PORT_SERVICE[parsed.port]]["url"] + parsed.path
    return url


@app.before_request
def local_browser_boundary():
    if request.host.split(":")[0] not in {"localhost", "127.0.0.1"}:
        return jsonify({"error": "Use the local dashboard address"}), 403
    origin = request.headers.get("Origin")
    if request.path.startswith("/api/") and (request.headers.get("Sec-Fetch-Site") == "cross-site"
            or (origin and origin.rstrip("/") != request.host_url.rstrip("/"))):
        return jsonify({"error": "Cross-origin API access is disabled"}), 403


from dashboard.authentication import install_auth
install_auth(app)


def service_headers():
    # Preserve the authenticated human identity through every gateway route.
    if getattr(g, "user", None) and os.getenv("AI_SOC_AUTH_SECRET"):
        return {"Authorization": "Bearer " + issue_token(g.user, os.environ["AI_SOC_AUTH_SECRET"])}
    return machine_headers()


@app.route("/health")
def dashboard_health():
    return jsonify({"status": "healthy", "service": "dashboard"})

QUICK_LINKS = [
    {"name": "Grafana", "url": "http://localhost:3001", "description": "Metrics and dashboards"},
    {"name": "Wazuh Dashboard", "url": "https://localhost:443", "description": "SIEM alerts and agents"},
    {"name": "Prometheus", "url": "http://localhost:9090", "description": "Raw metrics"},
    {"name": "ChromaDB", "url": "http://localhost:8200", "description": "Vector database"},
    {"name": "Ollama", "url": "http://localhost:11434", "description": "LLM server"},
]

# ---------------------------------------------------------------------------
# Generic proxy helper
# ---------------------------------------------------------------------------
TIMEOUT_LONG = 180  # LLM-heavy endpoints (analysis, simulation — can take 2+ min)
TIMEOUT_STD  = 15   # Fast endpoints


def _proxy(upstream_url, method="GET", timeout=TIMEOUT_STD):
    """
    Forward the current request to *upstream_url* and return a Flask response.
    Passes the original request body + Content-Type header unchanged.
    On any downstream failure returns {error: ...} with HTTP 502.
    """
    try:
        headers = service_headers()
        if request.content_type:
            headers["Content-Type"] = request.content_type

        resp = requests.request(
            method=method,
            url=_service_url(upstream_url),
            headers=headers,
            data=request.get_data(),
            params=request.args,
            timeout=timeout,
            verify=True,
        )
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text}
        return jsonify(body), resp.status_code

    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Service unavailable — connection refused", "upstream": upstream_url}), 502
    except requests.exceptions.Timeout:
        return jsonify({"error": "Service unavailable — request timed out", "upstream": upstream_url}), 504
    except Exception as exc:
        return jsonify({"error": str(exc), "upstream": upstream_url}), 502


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Docker / infrastructure endpoints (exist already — kept/improved)
# ---------------------------------------------------------------------------
@app.route("/api/status")
def get_status():
    """Docker container status."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "label=com.docker.compose.project=ai-soc", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=5,
        )
        containers = []
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        c = json.loads(line)
                        containers.append({
                            "name":   c.get("Names", "unknown"),
                            "status": c.get("Status", "unknown"),
                            "ports":  c.get("Ports", ""),
                            "state":  c.get("State", "unknown"),
                        })
                    except json.JSONDecodeError:
                        continue

        healthy = sum(
            1 for c in containers
            if "healthy" in c["status"].lower() or "up" in c["status"].lower()
        )
        total = len(containers)
        overall = "healthy" if total > 0 and healthy == total else "partial" if healthy > 0 else "offline"

        return jsonify({
            "status": overall,
            "containers": containers,
            "healthy_count": healthy,
            "total_count": total,
            "timestamp": datetime.now().isoformat(),
        })

    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc), "containers": [], "healthy_count": 0, "total_count": 0})


@app.route("/api/services")
def get_services():
    """Health-check all AI microservices."""
    services_status = []
    for service_id, cfg in AI_SERVICES.items():
        result = {
            "id": service_id,
            "label": cfg["label"],
            "description": cfg["description"],
            "url": cfg["url"],
            "docs_url": f"{cfg['url']}/docs",
            "status": "offline",
            "details": {},
        }
        try:
            resp = requests.get(f"{cfg['url']}/health", timeout=3, verify=True)
            if resp.status_code == 200:
                result["status"] = "healthy"
                try:
                    result["details"] = resp.json()
                except Exception:
                    result["details"] = {"message": "OK"}
            else:
                result["status"] = "degraded"
                result["details"] = {"http_status": resp.status_code}
        except requests.exceptions.ConnectionError:
            result["status"] = "offline"
            result["details"] = {"error": "Connection refused"}
        except requests.exceptions.Timeout:
            result["status"] = "timeout"
            result["details"] = {"error": "Request timed out"}
        except Exception as exc:
            result["status"] = "error"
            result["details"] = {"error": str(exc)}
        services_status.append(result)

    healthy = sum(1 for s in services_status if s["status"] == "healthy")
    return jsonify({
        "services": services_status,
        "healthy_count": healthy,
        "total_count": len(services_status),
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/ml/stats")
def get_ml_stats():
    """ML model info."""
    try:
        resp = requests.get(_service_url("http://localhost:8500/models"), headers=service_headers(), timeout=5)
        if resp.status_code == 200:
            return jsonify(resp.json())
    except Exception:
        pass
    return jsonify({
        "models": [], "status": "offline",
        "message": "ML inference service is not running",
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/test-alert", methods=["POST"])
def test_alert():
    """Send a canned SSH brute-force alert through the triage pipeline."""
    payload = {
        "alert_id": f"test-{int(datetime.now().timestamp())}",
        "timestamp": datetime.now().isoformat(),
        "source_ip": "203.0.113.42",
        "dest_ip": "10.0.0.1",
        "rule_id": "5710",
        "rule_level": 10,
        "rule_description": "Multiple failed SSH login attempts (Dashboard Test)",
        "full_log": {"message": "Oct 01 12:00:00 server sshd[1234]: Failed password for invalid user admin from 203.0.113.42 port 54321 ssh2"},
        "agent_name": "test-agent",
        "mitre_tactic": ["Credential Access"],
        "mitre_technique": ["T1110.001"],
    }
    try:
        resp = requests.post(_service_url("http://localhost:8100/analyze"), headers=service_headers(), json=payload, timeout=TIMEOUT_LONG)
        result = resp.json()
        result["test_mode"] = True
        result["input_alert"] = payload
        return jsonify(result), resp.status_code
    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": "Alert triage service not running",
            "test_mode": True,
            "input_alert": payload,
            "demo_result": {
                "severity": "HIGH",
                "confidence": 0.91,
                "mitre_tactic": ["Credential Access"],
                "mitre_technique": "T1110.001 - Password Guessing",
                "summary": "SSH brute force attack detected from 192.168.1.200.",
                "recommended_actions": [
                    "Block source IP 192.168.1.200 at firewall",
                    "Review /var/log/auth.log for successful logins",
                    "Enable fail2ban if not already active",
                ],
            },
        }), 503
    except Exception as exc:
        return jsonify({"error": str(exc), "test_mode": True}), 500


@app.route("/api/logs/<container>")
def get_logs(container):
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", "100", container],
            capture_output=True, text=True, timeout=5,
        )
        return jsonify({"container": container, "logs": result.stdout + result.stderr, "timestamp": datetime.now().isoformat()})
    except Exception as exc:
        return jsonify({"container": container, "error": str(exc), "logs": ""})


# ---------------------------------------------------------------------------
# Alert Triage  (port 8100)
# ---------------------------------------------------------------------------
@app.route("/api/analyze", methods=["POST"])
def analyze():
    return _proxy("http://localhost:8100/analyze", method="POST", timeout=TIMEOUT_LONG)


@app.route("/api/analyze/async", methods=["POST"])
def analyze_async():
    return _proxy("http://localhost:8100/analyze/async", method="POST", timeout=TIMEOUT_LONG)


@app.route("/api/jobs/<job_id>")
def get_job(job_id):
    return _proxy(f"http://localhost:8100/jobs/{job_id}", timeout=TIMEOUT_STD)


@app.route("/api/workers/stats")
def workers_stats():
    return _proxy("http://localhost:8100/workers/stats", timeout=TIMEOUT_STD)


# ---------------------------------------------------------------------------
# Feedback Service  (port 8400)
# ---------------------------------------------------------------------------
@app.route("/api/alerts")
def get_alerts():
    return _proxy("http://localhost:8400/alerts", timeout=TIMEOUT_STD)


@app.route("/api/alerts/<alert_id>")
def get_alert(alert_id):
    return _proxy(f"http://localhost:8400/alerts/{alert_id}", timeout=TIMEOUT_STD)


@app.route("/api/feedback/<alert_id>", methods=["POST"])
def post_feedback(alert_id):
    return _proxy(f"http://localhost:8400/feedback/{alert_id}", method="POST", timeout=TIMEOUT_STD)


@app.route("/api/feedback/stats")
def feedback_stats():
    return _proxy("http://localhost:8400/feedback/stats", timeout=TIMEOUT_STD)


@app.get("/reviews")
def reviews_page():
    return render_template("reviews.html")


@app.get("/api/feedback/reviews/pending")
def pending_feedback_reviews():
    return _proxy("http://localhost:8400/feedback/reviews/pending")


@app.post("/api/feedback/reviews/<feedback_id>")
def review_feedback(feedback_id):
    return _proxy(f"http://localhost:8400/feedback/reviews/{feedback_id}", method="POST")


@app.put("/api/rules/<rule_id>/reject")
def reject_rule(rule_id):
    return _proxy(f"http://localhost:8700/rules/{rule_id}/reject", method="PUT")


@app.get("/api/rules/<rule_id>/export")
def export_rule(rule_id):
    try:
        response = requests.get(_service_url(f"http://localhost:8700/rules/{rule_id}/export"), headers=service_headers(), timeout=TIMEOUT_STD)
        return Response(response.content, status=response.status_code,
                        content_type=response.headers.get("Content-Type", "application/yaml"),
                        headers={"Content-Disposition": 'attachment; filename="approved-rule.yml"'})
    except requests.RequestException:
        return jsonify(error="Rule service unavailable"), 502


@app.post("/api/defense/plans/<plan_id>/rollback")
def rollback_plan(plan_id):
    return _proxy(f"http://localhost:8800/plans/{plan_id}/rollback", method="POST", timeout=TIMEOUT_LONG)


@app.post("/api/defense/plans/<plan_id>/actions/<action_id>/reconcile")
def reconcile_action(plan_id, action_id):
    return _proxy(f"http://localhost:8800/plans/{plan_id}/actions/{action_id}/reconcile", method="POST", timeout=TIMEOUT_LONG)


# ---------------------------------------------------------------------------
# Correlation Engine / Simulation / Risk  (port 8600)
# ---------------------------------------------------------------------------
@app.route("/api/incidents")
def get_incidents():
    return _proxy("http://localhost:8600/incidents", timeout=TIMEOUT_STD)


@app.route("/api/incidents/active")
def get_active_incidents():
    return _proxy("http://localhost:8600/incidents/active", timeout=TIMEOUT_STD)


@app.route("/api/incidents/<incident_id>")
def get_incident(incident_id):
    return _proxy(f"http://localhost:8600/incidents/{incident_id}", timeout=TIMEOUT_STD)


@app.route("/api/predict/<stage>")
def predict_stage(stage):
    return _proxy(f"http://localhost:8600/predict/{stage}", timeout=TIMEOUT_STD)


@app.route("/api/simulate", methods=["POST"])
def simulate():
    return _proxy("http://localhost:8600/simulate", method="POST", timeout=TIMEOUT_LONG)


@app.route("/api/simulate/environment/from-wazuh", methods=["POST"])
def simulate_env_from_wazuh():
    return _proxy("http://localhost:8600/simulate/environment/from-wazuh", method="POST", timeout=TIMEOUT_LONG)


@app.route("/api/simulate/swarm/start", methods=["POST"])
def simulate_swarm_start():
    return _proxy("http://localhost:8600/simulate/swarm/start", method="POST", timeout=30)


@app.route("/api/simulate/swarm/<swarm_id>/status")
def simulate_swarm_status(swarm_id):
    return _proxy(f"http://localhost:8600/simulate/swarm/{swarm_id}/status", timeout=TIMEOUT_STD)


@app.route("/api/simulate/swarm/<swarm_id>/result")
def simulate_swarm_result(swarm_id):
    return _proxy(f"http://localhost:8600/simulate/swarm/{swarm_id}/result", timeout=TIMEOUT_STD)


@app.route("/api/simulate/swarm/trend")
def simulate_swarm_trend():
    return _proxy("http://localhost:8600/simulate/swarm/trend", timeout=TIMEOUT_STD)


@app.route("/api/simulate/research/metrics")
def simulate_research_metrics():
    return _proxy("http://localhost:8600/simulate/research/metrics", timeout=TIMEOUT_STD)


@app.route("/api/simulate/research/export", methods=["POST"])
def simulate_research_export():
    return _proxy("http://localhost:8600/simulate/research/export", method="POST", timeout=TIMEOUT_STD)


@app.route("/api/simulate/<simulation_id>/chat", methods=["POST"])
def simulate_chat(simulation_id):
    return _proxy(f"http://localhost:8600/simulate/{simulation_id}/chat", method="POST", timeout=TIMEOUT_LONG)


@app.route("/api/environment/default")
def get_default_environment():
    import os
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'simulation', 'default-environment.json')
    try:
        with open(env_path) as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({"error": f"Default environment not found at {env_path}"}), 404


@app.route("/api/risk-scores")
def risk_scores():
    return _proxy("http://localhost:8600/risk-scores", timeout=TIMEOUT_STD)


@app.route("/api/risk-summary")
def risk_summary():
    return _proxy("http://localhost:8600/risk-summary", timeout=TIMEOUT_STD)


@app.route("/api/risk-scores/refresh", methods=["POST"])
def risk_scores_refresh():
    return _proxy("http://localhost:8600/risk-scores/refresh", method="POST", timeout=TIMEOUT_LONG)


# ---------------------------------------------------------------------------
# Rule Generator  (port 8700)
# ---------------------------------------------------------------------------
@app.route("/api/generate-rule", methods=["POST"])
def generate_rule():
    return _proxy("http://localhost:8700/generate", method="POST", timeout=TIMEOUT_LONG)


@app.route("/api/rules")
def get_rules():
    return _proxy("http://localhost:8700/rules", timeout=TIMEOUT_STD)


@app.route("/api/rules/pending")
def get_pending_rules():
    return _proxy("http://localhost:8700/rules/pending", timeout=TIMEOUT_STD)


@app.route("/api/rules/<rule_id>/approve", methods=["PUT"])
def approve_rule(rule_id):
    return _proxy(f"http://localhost:8700/rules/{rule_id}/approve", method="PUT", timeout=TIMEOUT_STD)


# ---------------------------------------------------------------------------
# Response Orchestrator  (port 8800)
# ---------------------------------------------------------------------------
@app.route("/api/defend", methods=["POST"])
def trigger_defense():
    return _proxy("http://localhost:8800/defend", method="POST", timeout=TIMEOUT_LONG)


@app.route("/api/defense/plans")
def defense_plans():
    return _proxy("http://localhost:8800/plans", timeout=TIMEOUT_STD)


@app.route("/api/defense/plans/<plan_id>")
def defense_plan_detail(plan_id):
    return _proxy(f"http://localhost:8800/plans/{plan_id}", timeout=TIMEOUT_STD)


@app.route("/api/defense/plans/<plan_id>/events")
def defense_plan_events(plan_id):
    return _proxy(f"http://localhost:8800/plans/{plan_id}/events", timeout=TIMEOUT_STD)


@app.route("/api/defense/plans/<plan_id>/cancel", methods=["POST"])
def defense_cancel_plan(plan_id):
    return _proxy(f"http://localhost:8800/plans/{plan_id}/cancel", method="POST", timeout=TIMEOUT_STD)


@app.route("/api/defense/plans/<plan_id>/verify", methods=["POST"])
def defense_verify_plan(plan_id):
    return _proxy(f"http://localhost:8800/plans/{plan_id}/verify", method="POST", timeout=TIMEOUT_LONG)


@app.route("/api/rules/<rule_id>/backtest", methods=["POST"])
def rule_backtest(rule_id):
    return _proxy(f"http://localhost:8700/rules/{rule_id}/backtest", method="POST", timeout=TIMEOUT_STD)


@app.route("/api/defense/approvals")
def defense_approvals():
    return _proxy("http://localhost:8800/approvals", timeout=TIMEOUT_STD)


@app.route("/api/defense/plans/<plan_id>/actions/<action_id>/approve", methods=["POST"])
def defense_approve_action(plan_id, action_id):
    return _proxy(
        f"http://localhost:8800/plans/{plan_id}/actions/{action_id}/approve",
        method="POST", timeout=TIMEOUT_STD,
    )


@app.route("/api/d3fend/lookup/<technique_id>")
def d3fend_lookup(technique_id):
    return _proxy(f"http://localhost:8800/d3fend/lookup/{technique_id}", timeout=TIMEOUT_STD)


@app.route("/api/d3fend/techniques")
def d3fend_techniques():
    return _proxy("http://localhost:8800/d3fend/techniques", timeout=TIMEOUT_STD)


# ---------------------------------------------------------------------------
# Wazuh Integration  (port 8002)
# ---------------------------------------------------------------------------
@app.route("/api/webhook", methods=["POST"])
def webhook():
    return _proxy("http://localhost:8002/webhook", method="POST", timeout=TIMEOUT_LONG)


# ---------------------------------------------------------------------------
# RAG Service  (port 8300)
# ---------------------------------------------------------------------------
@app.route("/api/rag/retrieve", methods=["POST"])
def rag_retrieve():
    return _proxy("http://localhost:8300/retrieve", method="POST", timeout=TIMEOUT_LONG)


@app.route("/api/rag/collections")
def rag_collections():
    return _proxy("http://localhost:8300/collections", timeout=TIMEOUT_STD)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("AI-SOC Command Center starting…")
    print("Access at: http://localhost:5050")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
