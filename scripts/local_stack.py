#!/usr/bin/env python3
"""Start/stop AI-SOC locally using Python/Ollama plus an isolated PostgreSQL container.

Install tests/requirements.txt and services/rag-service/requirements.txt in .venv,
then use `python scripts/local_stack.py up`. Logs/PIDs stay in --state-dir.
"""

import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
SERVICES = {
    "ml-inference": ("ml_training.inference_api:app", 8500),
    "feedback-service": ("services.feedback_service.main:app", 8400),
    "correlation-engine": ("services.correlation_engine.main:app", 8600),
    "rag-service": ("services.rag_service.main:app", 8300),
    "alert-triage": ("services.alert_triage.main:app", 8100),
    "rule-generator": ("services.rule_generator.main:app", 8700),
    "response-orchestrator": ("services.response_orchestrator.main:app", 8800),
    "wazuh-integration": ("services.wazuh_integration.main:app", 8002),
}


def occupied(port):
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


def wait_http(url, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return json.load(response)
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {url}; inspect service logs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "down", "status"])
    parser.add_argument("--state-dir", type=Path, default=ROOT / "work" / "runtime")
    parser.add_argument(
        "--skip-model-pull",
        action="store_true",
        help="Use an already installed local model",
    )
    args = parser.parse_args()
    state = args.state_dir.resolve()
    state.mkdir(parents=True, exist_ok=True)
    pid_file = state / "processes.json"
    records = json.loads(pid_file.read_text()) if pid_file.exists() else {}
    if args.action == "status":
        for name, record in records.items():
            print(
                f"{name}: {'listening' if occupied(record['port']) else 'stopped'} on {record['port']}"
            )
        return
    if args.action == "down":
        for name, record in records.items():
            # Check process identity before terminating a PID that might be reused.
            check = subprocess.run(
                ["ps", "-p", str(record["pid"]), "-o", "command="],
                capture_output=True,
                text=True,
            )
            if record["identity"] in check.stdout:
                os.killpg(record["pid"], signal.SIGTERM)
                print(f"Stopped {name}")
        deadline = time.monotonic() + 15
        while (
            any(occupied(record["port"]) for record in records.values())
            and time.monotonic() < deadline
        ):
            time.sleep(0.2)
        if any(occupied(record["port"]) for record in records.values()):
            raise RuntimeError(
                "Some services are still stopping; PID records retained for inspection"
            )
        pid_file.unlink(missing_ok=True)
        return
    if records:
        raise RuntimeError(
            "This state directory already has a run; use status/down before up"
        )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/configure_local.py"), "--state-dir", str(state)], check=True
    )
    config = dict(
        line.split("=", 1)
        for line in (ROOT / ".env").read_text().splitlines()
        if line and not line.startswith("#")
    )
    env = {**os.environ, **config, "PYTHONUNBUFFERED": "1", "PYTHONPATH": str(ROOT)}
    python = ROOT / ".venv/bin/python"
    if not python.exists():
        raise RuntimeError("Create .venv and install dependencies first")
    for port in [11434, 5050] + [p for _, p in SERVICES.values()]:
        if occupied(port):
            raise RuntimeError(
                f"Port {port} is already in use; no existing process was changed"
            )
    subprocess.run(
        ["docker", "compose", "up", "-d", "--pull", "never", "--wait", "postgres"],
        cwd=ROOT,
        check=True,
    )
    db_url = f"postgresql+asyncpg://ai_soc:{config['POSTGRES_PASSWORD']}@127.0.0.1:5435/ai_soc"
    env.update(
        {
            "MODEL_PATH": str(ROOT / "models"),
            "AI_SOC_IDENTITY_DB": str(Path(config["AI_SOC_IDENTITY_DIR"]) / "identity.sqlite"),
            "OLLAMA_HOST": "http://127.0.0.1:11434",
            "OLLAMA_MODELS": str(state / "ollama-models"),
            "OLLAMA_MODEL": config.get("OLLAMA_MODEL", "llama3.2:3b"),
            "RAG_CHROMADB_PATH": str(state / "chroma"),
            "RAG_EMBEDDING_CACHE": str(state / "embedding-model"),
            "HF_HOME": str(state / "huggingface"),
            "TRIAGE_OLLAMA_HOST": "http://127.0.0.1:11434",
            "TRIAGE_PRIMARY_MODEL": config.get("OLLAMA_MODEL", "llama3.2:3b"),
            "TRIAGE_FALLBACK_MODEL": config.get("OLLAMA_MODEL", "llama3.2:3b"),
            "TRIAGE_ML_API_URL": "http://127.0.0.1:8500",
            "TRIAGE_RAG_SERVICE_URL": "http://127.0.0.1:8300",
            "TRIAGE_RAG_ENABLED": "true",
            "TRIAGE_FEEDBACK_SERVICE_URL": "http://127.0.0.1:8400",
            "TRIAGE_CORRELATION_ENGINE_URL": "http://127.0.0.1:8600",
            "TRIAGE_LLM_TIMEOUT": "180",
            "TRIAGE_JOB_STORE_PATH": str(state / "triage-jobs.sqlite"),
            "FEEDBACK_DATABASE_URL": db_url,
            "CORRELATION_DATABASE_URL": db_url,
            "ORCHESTRATOR_DATABASE_URL": db_url,
            "CORRELATION_SIMULATOR_OLLAMA_HOST": "http://127.0.0.1:11434",
            "CORRELATION_AUTO_DEFEND_ENABLED": "false",
            "CORRELATION_SIMULATOR_ENVIRONMENT_CONFIG": str(
                ROOT / "config/simulation/default-environment.json"
            ),
            "CORRELATION_SIMULATOR_OLLAMA_MODEL": config.get(
                "OLLAMA_MODEL", "llama3.2:3b"
            ),
            "SWARM_HISTORY_DIR": str(state / "simulation"),
            "RULE_STORE_PATH": str(state / "rules.sqlite"),
            "FEEDBACK_SERVICE_URL": "http://127.0.0.1:8400",
            "ORCHESTRATOR_CORRELATION_ENGINE_URL": "http://127.0.0.1:8600",
            "ORCHESTRATOR_SIMULATION_URL": "http://127.0.0.1:8600",
            "ORCHESTRATOR_FEEDBACK_SERVICE_URL": "http://127.0.0.1:8400",
            "ORCHESTRATOR_OLLAMA_HOST": "http://127.0.0.1:11434",
            "ORCHESTRATOR_OLLAMA_MODEL": config.get("OLLAMA_MODEL", "llama3.2:3b"),
            "ORCHESTRATOR_DRY_RUN_MODE": "true",
            "ALERT_TRIAGE_URL": "http://127.0.0.1:8100",
            "RAG_SERVICE_URL": "http://127.0.0.1:8300",
            "CORRELATION_ENGINE_URL": "http://127.0.0.1:8600",
        }
    )

    def start(name, command, port, identity):
        with (state / f"{name}.log").open("a") as log:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        records[name] = {"pid": process.pid, "port": port, "identity": identity}
        pid_file.write_text(json.dumps(records, indent=2))
        print(f"Started {name} on {port}", flush=True)

    start("ollama", ["ollama", "serve"], 11434, "ollama serve")
    wait_http("http://127.0.0.1:11434/api/tags")
    if not args.skip_model_pull:
        subprocess.run(
            ["ollama", "pull", env["OLLAMA_MODEL"]], cwd=ROOT, env=env, check=True
        )
    for name, (module, port) in SERVICES.items():
        start(
            name,
            [
                str(python),
                "-m",
                "uvicorn",
                module,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            port,
            module,
        )
    start(
        "dashboard",
        [
            str(python),
            "-m",
            "waitress",
            "--listen=127.0.0.1:5050",
            "--threads=8",
            "--channel-timeout=300",
            "dashboard.app:app",
        ],
        5050,
        "dashboard.app:app",
    )
    for name, (_, port) in SERVICES.items():
        wait_http(f"http://127.0.0.1:{port}/health", timeout=300)
        print(f"Ready: {name}", flush=True)
    print("Dashboard: http://localhost:5050")


if __name__ == "__main__":
    main()
