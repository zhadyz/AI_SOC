# AI-SOC

A local research SOC with Wazuh-format ingestion, real flow classification, local
Ollama triage, retrieved security knowledge, incident correlation, analyst review,
Sigma rule export, and durable response plans. The dashboard includes persistent
accounts with viewer, analyst, reviewer and administrator roles.

The native application has passed live acceptance on macOS. All nine application
images build. **Full Compose startup and the disposable Wazuh enforcement lab are
not yet accepted:** Docker container startup stalled on this host. See the current
[evidence and remaining gates](docs/development/status.md) and reconstructed
[completion plan](docs/development/completion-plan.md). Historical phase documents
are research material, not the current completion record.

## Start locally

Requirements: Python 3.11, Docker with Compose, Ollama, and an OpenMP runtime
(`brew install ollama libomp` on macOS). A local 3B model and the services need
several GB of disk and memory; 16 GB RAM is a practical starting point.

```bash
uv venv --python 3.11
uv pip install --python .venv/bin/python -r tests/requirements.txt -r services/rag-service/requirements.txt -r dashboard/requirements.txt
python3 scripts/configure_local.py
docker pull postgres:16-alpine
.venv/bin/python scripts/local_stack.py up
```

Open **http://localhost:5050** and sign in as `admin`. The setup command prints the
location of a private `admin-credentials.txt` containing the generated password.
It creates `.env` with random API, database, identity-signing and model-signing
secrets; keep these files private. Existing credentials are preserved on reruns.
Create separate analyst and reviewer accounts from **Account & access**.

The launcher writes logs, databases, model caches and PID records under
`work/runtime`. It uses one isolated PostgreSQL container; the other services and
Ollama run natively. Response execution is always a dry run on this launch path.
Subsequent starts can use `--skip-model-pull`.

```bash
.venv/bin/python scripts/local_stack.py status
.venv/bin/python scripts/local_stack.py down
docker compose stop postgres
```

This downloaded installation uses `--state-dir ../../work/runtime` for every
native command. Its administrator credentials are in
`../../work/runtime/admin-credentials.txt`. Use the same state directory when
restarting or backing up. No automatic login/startup service is installed.

## Container deployment

The root `compose.yaml` is authoritative. All published application ports bind to
loopback. Do not run it alongside the native application because the ports match.

```bash
python3 scripts/configure_local.py
docker compose up -d --build --wait --wait-timeout 900
docker compose ps
```

`./deploy-ai-soc.sh` and `./deploy-ai-soc.ps1` use this configuration. The legacy
`docker-compose/ai-services.yml` and `docker-compose/integrated-stack.yml` include
it. `docker compose down` preserves named data volumes; `down -v` deletes them.
Image builds passed locally; full container runtime acceptance remains pending.

## Analyst workflow

- Inspect incidents and source alerts. **Confirm Attack** and **False Positive**
  save labels. Human audit authors come from the signed-in account.
- **Preview Defense** stores a dry run with proposed actions and an audit trail.
- **Reviews** lists labels awaiting a different reviewer's decision, detection
  drafts to backtest/approve/export, and interrupted response plans to reconcile.
- Rules must match their supplied sample event. A constrained exact-match fallback
  is labeled when model drafts fail validation. Backtests measure supplied labeled
  events; false-positive rate remains unknown without benign examples. Export is
  a YAML download and does not install rules on a SIEM.
- Simulations show research estimates. Measured prevention and forecast accuracy
  require controlled exercises against an actual environment.

## Services and data contracts

| Port | Service | Main endpoints |
|---|---|---|
| 5050 | Dashboard | Login, incidents, reviews, account administration |
| 8002 | Wazuh receiver | `POST /webhook` |
| 8100 | Triage | `/analyze`, `/analyze/batch`, `/analyze/async`, `/jobs/{id}` |
| 8300 | RAG | `/retrieve`, `/ingest/mitre`, `/ingest/runbooks` |
| 8400 | Feedback | Alerts, labels, independent reviews |
| 8500 | ML inference | `/predict`, `/predict/named`, `/predict/batch`, `/models/reload` |
| 8600 | Correlation | Incidents, prediction, simulation |
| 8700 | Rules | Generate, review, backtest, export |
| 8800 | Response | Plans, approval/veto, audit, verification, reconciliation, rollback |
| 11434 | Ollama | Local model runtime |

Chroma is embedded inside the authenticated RAG process; it has no public HTTP
listener. A fixed MiniLM ONNX embedding model runs on CPU. Runbooks load on startup;
MITRE ingestion is explicit. No zero-vector fallback or invented references are
used when retrieval fails.

Direct API clients require a bearer credential. Human clients can obtain a
120-second role-preserving token from the authenticated dashboard's
`POST /api/auth/token` with its CSRF token. `AI_SOC_API_KEY` is a privileged machine
credential, not an analyst identity. Health and metrics are public on loopback.

ML requires all 77 finite CICIDS2017 flow features; `GET /models` exposes the exact
schema. Named inputs normalize known CICFlowMeter aliases and reject conflicts.
Missing protocol or flow measurements are never fabricated from alert metadata.
Alerts without complete flows receive LLM analysis without an ML prediction.

Async jobs persist in SQLite before HTTP 202 acknowledgment. A bounded priority
queue rejects overload with HTTP 429. Unfinished jobs resume after restart; alert
IDs make persistence and correlation idempotent. Results remain queryable after
restart. Callback URLs are disabled. Use one triage process per job database and
one response-orchestrator process per deployment.

## Models and research

The bundled binary classifiers remain the serving baseline. A separately trained,
signed **15-class CICIDS2017 bundle** and its reproducible benchmark are available:
34,935 training rows and 8,728 held-out rows, with zero feature-vector overlap.
See [evaluation details](docs/development/multiclass-evaluation.json). Sampling is
class-capped and deduplicated; these are within-dataset results with small rare-class
supports, not deployment generalization or evidence of feedback-driven improvement.

```bash
.venv/bin/python scripts/benchmark_models.py /path/to/GeneratedLabelledFlows.zip --output models/bundles/cicids2017-multiclass --report work/multiclass-evaluation.json
.venv/bin/python scripts/retrain_local.py --evaluate-only
.venv/bin/python scripts/retrain_local.py --holdout /path/to/independent.csv --promote
```

The benchmark pins the downloaded archive's SHA-256. Feedback training requires
real, complete flows with independently approved binary labels and an independent
holdout. Model artifacts are verified before deserialization. Candidate bundles
are signed; failed promotion restores the previous disk pointer and serving model.
No candidate has been promoted in this installation.

## Recovery and lab acceptance

[Operations](docs/development/operations.md) covers roles, backups, model rollback,
response recovery, and the optional disposable Linux/Wazuh lab. The lab implements
scoped IP blocking, container network isolation and account disabling with durable
intent, independent state checks and rollback. Its strict smoke script additionally
checks HTTP traffic, SSH denial and real agent-to-manager-to-SOC forwarding.
**These lab runtime checks have not passed on this host yet.**

```bash
.venv/bin/python scripts/local_stack.py down
.venv/bin/python scripts/backup_restore.py backup work/backups/snapshot
.venv/bin/python scripts/backup_restore.py drill work/backups/snapshot --report work/restore-report.json
.venv/bin/python scripts/local_stack.py up --skip-model-pull
```

Backups contain secrets. The drill restores PostgreSQL into a new temporary database
and validates copied SQLite databases without overwriting the working deployment.

## Verification

```bash
.venv/bin/pytest
.venv/bin/python -m compileall -q services ml_training dashboard scripts lab
.venv/bin/ruff check --select E9,F63,F7,F82 services ml_training dashboard scripts tests lab
.venv/bin/python scripts/smoke_test.py --full
uv pip install --python .venv/bin/python -r requirements-security.txt
.venv/bin/python scripts/audit_dependencies.py --output work/dependency-audit.json
```

Live acceptance creates clearly marked test alerts, feedback, plans and rules; it
never executes defenses. CI enforces tests, lint, dependency policy, Compose
validation and all nine image builds. Four Chroma advisories have narrowly scoped,
versioned, expiring mitigations because the affected HTTP/configurable-embedding
features are absent from this deployment. New or expired advisories fail the audit.
See [the exception rationale](docs/security/dependency-exceptions.json).

[Apache 2.0 license](LICENSE).
