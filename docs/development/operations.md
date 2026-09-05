# Operating the recovered platform

## Local installation in this assessment

The repository is in `outputs/AI_SOC`. Native services were started with:

```bash
.venv/bin/python scripts/local_stack.py up --skip-model-pull --state-dir ../../work/runtime
```

Use that same state directory for `status` and `down`. The dashboard is
http://localhost:5050. Process logs, Ollama models, embeddings, Chroma data, rules
and simulation history are under the state directory. Alert/incident/feedback and
response state is in the isolated `ai-soc-postgres-1` container and its named
volume. `docker compose stop postgres` stops it without deleting the volume.
Existing unrelated Docker containers were left unchanged. Ollama and libomp were
installed through Homebrew; the launcher starts Ollama for this workspace, without
registering an automatic login service.

## API usage

The generated `.env` contains the local API key and database password. This example
uses them without putting secrets in the command line or output:

```python
from dotenv import dotenv_values
import requests
key = dotenv_values('.env')['AI_SOC_API_KEY']
headers = {'Authorization': f'Bearer {key}'}
response = requests.get('http://127.0.0.1:8500/models', headers=headers, timeout=10)
response.raise_for_status()
print(response.json())
```

The same header is required for `/docs` and `/openapi.json`. The dashboard proxy
attaches it server-side. This local shared-key boundary is not enterprise identity:
analyst/reviewer IDs are user-supplied audit fields. Before shared/remote use,
add an identity provider, enforce role separation, configure TLS, audit retention,
rate limits, backup/restore, and validate all vendor integrations in a lab.

## Knowledge and rules

Runbooks load into `security_runbooks` during startup. Populate MITRE with
`POST http://127.0.0.1:8300/ingest/mitre` using the bearer header. This downloads
MITRE's enterprise ATT&CK data. The assessment loaded 858 technique documents.
CVE and historical-incident ingestion remain optional data-source integrations.
RAG exceptions surface as errors; triage includes a pipeline warning if retrieval
is unavailable. Retrieved text and LLM outputs remain untrusted evidence.

Rule generation uses Ollama JSON-schema output to create a conjunctive Sigma
mapping selector, then serializes and validates YAML. Rules and review state are
stored in SQLite under `RULE_STORE_PATH`. `PUT /rules/{id}/approve?analyst_id=...`
approves a draft for export; it does not activate it on a SIEM.

Use `POST /rules/{id}/backtest` with `{"events":[{"event":{"EventID":4625},
"label":"ATTACK"},{"event":{"EventID":4624},"label":"BENIGN"}]}`. Supply actual
normalized fields matching the rule's log source. The matcher supports mapping
selectors, scalar/list values, wildcards, contains/startswith/endswith/all modifiers,
and boolean conditions including `1/all of`. Aggregation, regex and other Sigma
features are rejected. False-positive rate is false matches / benign events;
it is unknown without benign labeled events. A two-event smoke fixture does not
establish operational detection quality.

## Defense lifecycle and lab integration

`POST /defend` accepts an incident ID, optional environment, `dry_run`,
`auto_execute`, and `skip_simulation`. Request and deployment defaults are dry-run.
The native launcher always forces dry-run. The dashboard explicitly submits
`dry_run=true, auto_execute=false`. Missing affected accounts/domains are not
invented: supply `affected_accounts` and `confirmed_malicious_domains` in an
operator-reviewed environment when those targets are known.

Plans and audit events are committed together before and after actions. View them
at `GET /plans/{id}` and `GET /plans/{id}/events`. Dry runs are terminal
`dry_run_completed`; actions are `simulated`, without `executed_at`. Restarted
execution/verification becomes `recovery_required`; it is never automatically
replayed. Native processes use a single orchestrator worker. Horizontal execution
across multiple orchestrator replicas is not supported by the current in-process
execution locks.

For a configured lab plan requiring a decision, post
`{"approved":true,"analyst_id":"operator-id","notes":"review rationale"}` to
`/plans/{plan}/actions/{action}/approve`. Use `approved=false` to reject or veto.
`POST /plans/{id}/cancel` takes `analyst_id` and optional `notes`. Uncertain remote
actions require out-of-band reconciliation with the target system. The API refuses
to retry an uncertain action as if it had never run.

Verification requires both observed post-action environment data and monitoring.
`POST /plans/{id}/verify` takes `analyst_id` and `environment_json`. A model-generated
posture or a missing indexer is not proof of enforcement. The default monitoring
window is 30 minutes; configure it for the lab. Unsupported rollback is reported
as unavailable rather than successful.

To test real Wazuh command submission, first configure a disposable Wazuh lab:

- `ORCHESTRATOR_WAZUH_API_URL`, `ORCHESTRATOR_WAZUH_API_USERNAME`,
  `ORCHESTRATOR_WAZUH_API_PASSWORD` and trusted TLS certificates.
- `ORCHESTRATOR_WAZUH_AGENT_IDS` as an explicit JSON list of lab-agent IDs.
- `ORCHESTRATOR_WAZUH_BLOCK_COMMAND` as a command already configured and tested
  on those agents. Manager/all-agent targets are rejected.
- `ORCHESTRATOR_WAZUH_INDEXER_URL`, `ORCHESTRATOR_WAZUH_INDEXER_USERNAME`,
  `ORCHESTRATOR_WAZUH_INDEXER_PASSWORD` for monitoring `wazuh-alerts-*`.

A separately reviewed Compose override must explicitly set
`ORCHESTRATOR_DRY_RUN_MODE=false` before a request with `dry_run=false` can execute.
Wazuh `PUT /active-response?agents_list=...` acknowledgment means the command was
submitted, not that a host enforced it. Only `block_ip` submission is implemented;
other Wazuh commands and firewall/EDR/identity vendor enforcement remain unavailable.
Choose and test those vendor adapters rather than filling in successful stubs.
The Wazuh API contract is described in the [official reference](https://documentation.wazuh.com/current/user-manual/api/reference.html).

## Feedback and retraining

Submit labels to `POST /feedback/{alert_id}`; approved labels use
`POST /feedback/reviews/{feedback_id}` with a different `reviewer_id`, `approved`
and optional `notes`. Only independently reviewed, unambiguous BENIGN/ATTACK labels
with all finite 77 named flow features qualify. Self-review, missing flows,
contradictory labels and conflicting duplicate feature vectors are excluded.

```bash
.venv/bin/python scripts/retrain_local.py --evaluate-only
.venv/bin/python scripts/retrain_local.py --holdout /path/to/independent.csv
.venv/bin/python scripts/retrain_local.py --holdout /path/to/independent.csv --promote
```

The holdout CSV requires all feature columns plus `Label`, both classes, and no
feature-vector overlap with training feedback. `--force` permits exploratory runs
below the usual 100-sample threshold, never bypasses review/feature/holdout checks,
and still requires at least five examples per class. Candidate and champion
models use the same scaler. Bundles contain all three classifiers, the scaler,
encoder, feature names and evaluation metadata. `models/active.json` is the atomic
bundle pointer; `/models/reload` retains the previous in-memory bundle if loading
fails. Retain accepted previous bundles and their evaluation metadata for rollback.

The assessment's synthetic text alerts yielded **zero eligible training flows**;
no classifier was trained or promoted. Supply real reviewed traffic and an
independent holdout to complete the empirical learning cycle.

## Research and deployment limits

The live smoke verifies one short campaign, not swarm-scale throughput, adversarial
robustness, calibrated probability, real prevention, or longitudinal improvement.
Simulation rankings and confidence are heuristics. The simplified kill-chain
mapping is a UI/correlation abstraction rather than a canonical ATT&CK sequence.
Historical phase reports are retained as prior material, not revalidated results.

The root Compose file and compatibility includes validate locally. A complete
image build could not be verified on this host: Docker stalled while retrieving
`python:3.11-slim` metadata and timed out. Native services were used for live
acceptance. CI now builds all actual images and fails on build/test errors, but
GitHub Actions and registry publication were not run from this local task.

Rule drafts must use observed sample-event fields and match that event before acceptance. Supply `sample_event` (a flat scalar-valued event) and `logsource` when generating a source-specific rule. Without a sample event, the alert text is treated as a generic `message` field; the source remains generic. This grounding check is not a substitute for representative labeled backtesting.

If two model drafts fail evidence validation, the service discards their filters and emits an explicitly marked `evidence_fallback` rule matching the sample exactly. The dashboard labels this fallback; it still requires analyst review and backtesting. Unavailable model service calls remain errors.
