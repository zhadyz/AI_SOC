# AI-SOC

A local research SOC that ingests alerts, retrieves security knowledge, triages with
Ollama, correlates incidents, records analyst feedback, and produces auditable
defense dry runs. Bundled Random Forest, XGBoost and Decision Tree models classify
complete 77-feature CICIDS2017 network flows.

The recovery assessment and exact verification evidence are in
[development status](docs/development/status.md). The reconstructed target is in
[the completion plan](docs/development/completion-plan.md). This is a research
platform; production vendor enforcement and empirical model/simulation validation
remain external acceptance gates.

## Start with Docker Compose

Requirements: Python 3.11, Docker with Compose v2.20+, internet access for image,
embedding and Ollama downloads, and enough memory for a local 3B model plus the
services (16 GB or more recommended). The first start downloads several GB.

```bash
python3 scripts/configure_local.py
docker compose up -d --build --wait --wait-timeout 900
```

Open **http://localhost:5050**. All published ports bind to loopback. The dashboard
keeps the generated API key on its server; direct API clients must send
`Authorization: Bearer <AI_SOC_API_KEY from .env>`. Health and metrics are public
on loopback. Keep `.env` private and out of version control.

`./deploy-ai-soc.sh` and `./deploy-ai-soc.ps1` run the same setup. The root
`compose.yaml` is authoritative. The old `ai-services.yml` and
`integrated-stack.yml` now include it; other compose files are optional historical
lab configurations and are not needed to start this platform.

```bash
docker compose ps
docker compose logs --tail 100 alert-triage
docker compose down
```

`down` preserves data volumes. Do not use `down -v` unless intentionally deleting
local alerts, plans, feedback, rules and downloaded models.

## Native Python and Ollama alternative

This path was exercised on macOS when Docker's Python base-image download stalled.
It still uses one isolated PostgreSQL container. Install Python 3.11, Ollama and an
OpenMP runtime (`brew install ollama libomp` on macOS), then:

```bash
uv venv --python 3.11
uv pip install --python .venv/bin/python -r tests/requirements.txt -r services/rag-service/requirements.txt -r dashboard/requirements.txt
python3 scripts/configure_local.py
docker pull postgres:16-alpine
.venv/bin/python scripts/local_stack.py up
```

The launcher refuses occupied ports, writes logs and PID records under
`work/runtime`, and downloads the selected Ollama model on first start. Subsequent
starts can use `--skip-model-pull`. Native response is always configured as a dry
run. Use the same `--state-dir` for every command when overriding its location.

```bash
.venv/bin/python scripts/local_stack.py status
.venv/bin/python scripts/local_stack.py down
docker compose stop postgres
```

Stopping native processes keeps their model caches and databases. PostgreSQL is
stopped separately. Never run the full Compose stack and native stack together;
they intentionally use the same application ports.

## What to do in the dashboard

- Inspect incidents and their underlying alerts. **Confirm Attack** and **False
  Positive** save analyst labels; they do not contain hosts or close incidents.
- Select **Preview Defense** to create a stored dry run. **View plan & audit**
  shows proposed actions, their outcomes, and the durable event trail.
- Run a short simulation against the example environment. The topology and risk
  scores are research estimates. The live Wazuh option requires a configured lab.
- Investigate an alert, generate a Sigma draft, and review it for export. Approval
  does not install the rule on a SIEM. Backtests require supplied normalized,
  labeled events; untested rules have an unknown false-positive rate.

## Services and contracts

| Port | Service | Main endpoints |
|---|---|---|
| 5050 | Dashboard | Analyst interface and authenticated API proxy |
| 8002 | Wazuh receiver | `POST /webhook` accepts Wazuh JSON |
| 8100 | Triage | `POST /analyze`, `/analyze/batch`, `/analyze/async`; `GET /jobs/{id}` |
| 8200 | ChromaDB | Local knowledge storage dependency |
| 8300 | RAG | `POST /retrieve`, `/ingest/mitre`, `/ingest/runbooks` |
| 8400 | Feedback | Alerts, corrections, independent label reviews |
| 8500 | ML inference | `POST /predict`, `/predict/named`, `/predict/batch`, `/models/reload` |
| 8600 | Correlation | Incidents, prediction, simulation, research metrics |
| 8700 | Rules | Generate drafts, review, backtest supplied events |
| 8800 | Response | Plans, approval/veto, cancellation, audit, verification |
| 11434 | Ollama | Local model runtime |

The ML model contract is available from authenticated `GET /models`. Missing,
nonfinite or wrong-size flow data is rejected; no port numbers or severity values
are substituted for network measurements. Wazuh alerts without complete flows
receive LLM triage without an ML prediction. RAG retrieves runbooks and MITRE
context before analysis and returns source references. Runbooks load on startup;
MITRE data is populated explicitly through `POST /ingest/mitre`.

Synchronous, batch and async triage use the same persistence/correlation path.
Retries with an existing alert ID update stored analysis without incrementing
incident counts. Async jobs are an in-process convenience queue and do not survive
a service restart; retry unresolved jobs using the original alert ID. Outbound
callback URLs are disabled; poll the job endpoint.

## Response and learning boundaries

Response plans and events are stored transactionally in PostgreSQL. Dry-run
outcomes are marked `simulated`, with no real execution timestamp. Approval records
identify the analyst; veto windows actually wait. Interrupted execution recovers
as `recovery_required` and is not replayed automatically. Missing monitoring or
post-action evidence cannot be reported as successful verification.

Firewall, EDR and identity integrations expose unavailable results until a vendor
adapter is implemented. Wazuh supports explicit submission of a configured
`block_ip` active-response command to configured lab agents; acknowledgment means
submission, not proven enforcement. See [operations](docs/development/operations.md)
for the configuration and acceptance gates before enabling live execution.

Retraining accepts only independently reviewed, unambiguous binary labels paired
with complete real flows. Candidate models share the champion feature schema and
scaler. Promotion requires a supplied independent holdout CSV, rejects overlapping
samples, and atomically activates a complete bundle. See operations for usage.
The bundled models remain binary; no multiclass or measured improvement claim is
made by this recovery work.

## Verification

```bash
uv pip install --python .venv/bin/python -r tests/requirements.txt
.venv/bin/pytest
.venv/bin/ruff check --select E9,F63,F7,F82 services ml_training dashboard scripts tests
.venv/bin/python scripts/smoke_test.py --full
```

The live smoke test requires the running stack and local model. It uses reserved
example addresses and defense dry runs, writes sample alerts/feedback/plans/rules,
and fails on missing services or invalid results. `--skip-llm` checks health,
authentication, real bundled predictions and runbook retrieval only. An equivalent
full live pytest case is enabled with `pytest --live tests/e2e`.

CI runs offline tests, fatal-error lint, Compose validation, and builds every
actual service image without suppressing failures. Image publishing is an explicit
manual workflow after verification. Historical test sketches that swallowed
failures are retained in `experiments/legacy-tests` outside test discovery.

[Apache 2.0 license](LICENSE). Original research and architecture material is
preserved under `docs`, `ml_training`, and the service directories; old phase
completion claims should be read alongside the current development status.

Rule drafts must use observed sample-event fields and match that event before acceptance. Supply `sample_event` (a flat scalar-valued event) and `logsource` when generating a source-specific rule. Without a sample event, the alert text is treated as a generic `message` field; the source remains generic. This grounding check is not a substitute for representative labeled backtesting.
