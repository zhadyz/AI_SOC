# Operating AI-SOC

## This installation

From the repository, use `.venv/bin/python scripts/local_stack.py up
--skip-model-pull --state-dir ../../work/runtime`. Use the same state option for
`status`, `down`, and backup. The dashboard is http://localhost:5050.

The private administrator password is in `../../work/runtime/admin-credentials.txt`.
Identity lives in the `.env`-configured `AI_SOC_IDENTITY_DIR`. Runtime logs, the
triage job journal, Chroma, rules, simulation state, Ollama models and embeddings
live under the state directory. PostgreSQL uses the `ai-soc-postgres-1` container
and its named volume. `docker compose stop postgres` stops only this database.
Other applications' containers are not part of this deployment.

## Identity and API access

| Role | Access |
|---|---|
| Viewer | Read incidents, plans and rules; retrieval and inference |
| Analyst | Viewer access plus triage, investigation, labels, rule drafts and dry runs |
| Reviewer | Analyst access plus independent label review, response decisions and rule approval |
| Admin | All operations, account administration, ingestion and model reload |

Accounts are persistent. Passwords use salted scrypt. Browser sessions last eight
hours and are revoked on account/password/role changes. Browser writes require a
CSRF token and login attempts are limited to ten per minute per source address.
API limits default to 600 requests per minute per identity. Forged forwarding
headers do not change the rate-limit identity.

The gateway signs two-minute, audience-bound human API tokens. Services enforce
roles and replace human-supplied audit names with the verified username. An already
issued direct token can remain valid for up to two minutes after account revocation;
browser sessions are revoked immediately. The privileged `AI_SOC_API_KEY` is for
trusted automation and internal services and can deliberately supply audit IDs.
Do not distribute it to ordinary dashboard users.

Create users in **Account & access**. Admins can PATCH `/api/auth/users/{username}`
with `role`, boolean `active`, or a new `password` (14–256 characters). This revokes
existing browser sessions. The last active administrator cannot be disabled or
demoted. Local emergency recovery can use `IdentityStore.update_user` after stopping
the dashboard and reading its private database path from `.env`.

```python
from dotenv import dotenv_values
import requests
key = dotenv_values('.env')['AI_SOC_API_KEY']
response = requests.get('http://127.0.0.1:8500/models',
                        headers={'Authorization': f'Bearer {key}'}, timeout=10)
response.raise_for_status()
print(response.json())
```

All published endpoints bind to loopback. Shared/remote deployment still needs a
chosen identity provider, HTTPS termination and trusted-proxy configuration,
retention policy and operational review. `AI_SOC_HTTPS=true` makes session cookies
secure; it does not itself install a TLS proxy. Native defaults are intended for
one local deployment, not multiple uncoordinated replicas.

## Knowledge, queues and rules

RAG uses Chroma `PersistentClient` with fixed ONNX MiniLM embeddings and no Chroma
HTTP server. Never expose a Chroma listener without resolving the documented
advisories. `POST :8300/ingest/mitre` imports enterprise ATT&CK; 858 techniques were
loaded in this installation. Runbooks load automatically. Treat retrieved text
and generated outputs as untrusted evidence.

The triage SQLite journal commits jobs before returning HTTP 202. Unfinished jobs
are replayed at least once after restart; persistence and correlation deduplicate
by alert ID. Completed/failed results remain on disk. Failed jobs are not retried
automatically; investigate the error before submitting the original alert again.
Queue capacity defaults to 1,000 waiting jobs and rejects excess requests. Use one
triage process per journal; no distributed worker lease is implemented. Configure
retention/archival before sustained ingestion, since journal and audit data are
not deleted automatically.

Rules and reviews persist in `RULE_STORE_PATH`. `/reviews` provides independent
label decisions, sample inspection, rule backtesting and YAML export. Rules require
observed event fields and a sample match. If two model drafts fail that constraint,
the service labels a deterministic sample-match fallback. This is a draft, not
proof of detection quality. The supported Sigma subset rejects unsupported features.

`POST /rules/{id}/backtest` accepts `{"events":[{"event":{"EventID":4625},
"label":"ATTACK"},{"event":{"EventID":4624},"label":"BENIGN"}]}`. Supply real
normalized events for meaningful evaluation. Only approved rules can be downloaded
from `GET /rules/{id}/export`; approval never installs a rule in a SIEM.

## Response lifecycle

`POST :8800/defend` takes an incident ID and optional environment. Both request and
deployment defaults are dry-run. The native launcher forces dry-run, and the
dashboard submits `dry_run=true, auto_execute=false`. Known accounts/domains can
be supplied through `affected_accounts` and `confirmed_malicious_domains`; missing
targets are never invented.

Plans and audit events are committed before/after effects. Dry runs use terminal
`dry_run_completed` with simulated actions and no execution timestamp. Approval and
veto require reviewer/admin identity. Veto windows wait before execution.
Interrupted real execution becomes `recovery_required` and is not automatically
replayed. Use one orchestrator process; horizontal execution is not supported.

The review center exposes recovery actions:

- `POST /plans/{p}/actions/{a}/reconcile` with `resolution="verify_active"` asks the
  adapter to observe the target without executing anything.
- `resolution="confirm_not_applied"` records a reviewer's explicit out-of-band
  attestation. Notes must explain the evidence. This is not machine verification.
- `POST /plans/{p}/rollback` restores supported settled actions. Unknown effects
  must be reconciled first. Partial or unsupported rollback remains visible.

Post-plan verification needs observed environment data and independent monitoring;
a simulated posture or missing indexer cannot establish prevention. The monitoring
window defaults to 30 minutes. Generic production firewall/EDR/identity adapters
remain unavailable until actual vendors are chosen and tested.

## Disposable Linux/Wazuh lab — runtime acceptance pending

Install `lab/requirements.txt` alongside native dependencies, then:

```bash
.venv/bin/python scripts/lab_stack.py up --state-dir work/lab
.venv/bin/python scripts/lab_smoke.py --state-dir work/lab --output work/lab-verification.json
.venv/bin/python scripts/lab_stack.py down --state-dir work/lab
```

The lab owns only project `ai-soc-lab`: Wazuh manager, a Linux agent/HTTP/SSH target,
and a probe on `172.30.77.0/24`. Check this subnet does not conflict with local
routing. Bindings are loopback: manager API 15500, target HTTP 18910, SSH 18922,
controller 8900. Generated passwords and a local trusted certificate stay in the
private lab state directory. The target gets NET_ADMIN for its own network
namespace; no host firewall or arbitrary container target is accepted.

The controller scopes IP blocking to the probe, isolation to the lab target and
account disabling to `lab-user`. It journals intent/prior state before effects,
checks operation IDs and container identity, and restores prior state on rollback.
The acceptance script verifies real HTTP and SSH behavior, restoration, and a real
Wazuh agent event forwarded into SOC storage. A simulated webhook does not meet
that acceptance criterion. On this Mac container startup stalled; no successful
live lab report has been produced.

The optional `ORCHESTRATOR_LAB_URL` selects these adapters. A separately configured
lab orchestrator must explicitly set `ORCHESTRATOR_DRY_RUN_MODE=false` for real plan
execution. The standard native launch path keeps dry-run enforced. The smoke script
calls only the scoped lab controller and does not change the main orchestrator.

The Wazuh adapter can submit configured `block_ip` commands to an explicit list of
agent IDs. Set `ORCHESTRATOR_WAZUH_API_URL`, `_API_USERNAME`, `_API_PASSWORD`,
`_API_CA_BUNDLE`, `_AGENT_IDS` and `_BLOCK_COMMAND`. All-agent/manager targets are rejected.
An API acknowledgment is only submission evidence; host behavior and rollback still
need verification. Monitoring requires a real Wazuh indexer. Production integration
is not implied by the disposable lab.

## Models and empirical research

The binary baseline remains active. Six artifact hashes are checked before pickle
deserialization. Promoted bundles require HMAC signatures using the private
`AI_SOC_MODEL_SIGNING_KEY`. Treat both source-controlled baseline artifacts and
training inputs as trusted local material. A signing key does not make an arbitrary
untrusted pickle safe to use.

The locally generated bundle `models/bundles/cicids2017-multiclass-20260904` includes
15-class models, a train-only scaler, encoder, feature names, training/holdout CSVs,
signed manifest and evaluation. The original dataset is
[UNB CICIDS2017](https://www.unb.ca/cic/datasets/ids-2017.html). The downloaded archive
came from the [bencorn public mirror](https://huggingface.co/datasets/bencorn/CICIDS2017),
not an official UNB distribution endpoint. Its pinned SHA-256 is recorded in the
benchmark report and script. GeneratedLabelledFlows includes the required Protocol
column; the MachineLearningCSV variant lacks it and is rejected.

Sampling retains at most 5,000 deduplicated vectors per class and removes observed
conflicting labels. A deterministic hash-ranked 20% holdout per class is excluded before
fitting the scaler and models. This is a within-dataset split; it does not remove
all host/day/environment correlations or prove out-of-distribution robustness.
Rare-class support and per-class scores must accompany overall accuracy claims.

Feedback retraining requires independently approved, unambiguous BENIGN/ATTACK
labels with all 77 finite flow values. Genuine eligible feedback remains absent in
this installation. Use `scripts/retrain_local.py --evaluate-only` to inspect it.
`--holdout /path/to/independent.csv` trains/evaluates; adding `--promote` requires
acceptance checks and activates a complete signed bundle. Feature overlap with the
holdout is rejected. `--force` relaxes only the normal sample threshold, not review,
feature or holdout checks.

`models/active.json` is the bundle pointer. Failed promotion restores the preceding
pointer and tries to reload the prior model; a failed API reload keeps the working
in-memory model. Keep accepted old bundles and metadata for rollback. No bundle
was promoted during this assessment.

## Backup and restore drill

Stop native services first, leaving PostgreSQL running. With this installation's
state override:

```bash
.venv/bin/python scripts/local_stack.py down --state-dir ../../work/runtime
.venv/bin/python scripts/backup_restore.py backup ../../work/backups/new-snapshot --state-dir ../../work/runtime
.venv/bin/python scripts/backup_restore.py drill ../../work/backups/new-snapshot --report work/restore-report.json
.venv/bin/python scripts/local_stack.py up --skip-model-pull --state-dir ../../work/runtime
```

The private backup includes a PostgreSQL custom dump and row counts, consistent
SQLite snapshots, Chroma/simulation state, model bundles, configuration and hashes.
The restore drill creates a fresh temporary PostgreSQL database, restores and
compares every table count, checks SQLite integrity, then removes the temporary
database. It does not replace the working database. A disaster cutover requires a
stopped target and an operator-controlled restoration of these files/credentials;
the drill deliberately has no overwrite-working-deployment option.

Keep backups on protected storage with a retention policy. Model/embedding download
caches can be reacquired and are omitted. Loss of configuration/signing keys can
prevent authentication or acceptance of signed model bundles.

## Verification limits

The enforcing dependency audit has four version-specific Chroma exceptions for
unused HTTP/configurable-embedding/SimpleRBAC features, expiring 2026-10-04. This
means mitigated findings, not zero known advisories. Recheck before that date and
before changing RAG deployment shape.

Live workflow, identity, bounded inference load and restore evidence are in
[status.md](status.md). CI definitions build every application image, but no GitHub
run, push, registry publish or production deployment was performed. Native HTTP
page rendering was verified; the newly added review/access pages still need visual
inspection after the Mac is unlocked. Simulation accuracy, multi-user operational
load, production enforcement and longitudinal learning are open research gates.
