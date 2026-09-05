# Current implementation and acceptance state

Assessment: 2026-09-04 (America/Los_Angeles). Upstream baseline: `60902fa` on
`master`. Local branch: `codex/complete-research-platform`. The initial recovery
was committed as `be32d29`; this continuation adds the functionality below.

## Outcome

The reconstructed local research platform is implemented and accepted end to end.
Native and full-container deployments have passed the strict live workflow. Browser
review/export/account workflows pass. The disposable Wazuh/Linux lab demonstrates
actual HTTP and SSH denial/restoration, real agent forwarding, and response-plan
approval/restart reconciliation/rollback through the real engine and adapters.

The downloaded installation uses the native application at http://localhost:5050
for its faster local Ollama runtime. Container volumes and all built images are
retained. Production vendor rollout and research generalization remain separate
external validation work; they are not claimed by these local results.

## Implemented in this continuation

| Area | Current behavior |
|---|---|
| Identity | Persistent scrypt password accounts, viewer/analyst/reviewer/admin roles, CSRF-protected browser sessions, role-preserving short-lived API tokens and rate limits |
| Audit authorship | Human authors/reviewers come from verified identities; ordinary analysts cannot approve their own labels or elevate response execution |
| Review interface | Pending independent label review, source alert evidence, rule review/backtest/YAML export, response reconciliation and rollback |
| Queue durability | Accepted jobs commit to SQLite before HTTP 202; bounded admission, restart recovery, durable result lookup and idempotent downstream alert correlation |
| Model integrity | Hashes checked before deserialization, signed candidate manifests, complete-bundle validation, failed promotion restores the previous active pointer |
| Flow schema | Known CICFlowMeter aliases normalize into the exact 77-feature contract; conflicting aliases, missing Protocol and fabricated partial measurements are rejected |
| Multiclass research | Three real classifiers trained and evaluated across 15 CICIDS2017 classes; a separate signed research bundle serves through the real inference API |
| Response recovery | Durable operation IDs; observe uncertain effects without replay; reviewer attestation and tested settled-action rollback state transitions |
| Disposable enforcement lab | Scoped Linux gateway/network/account controller, durable intent/prior-state journal, Wazuh manager/agent configuration, pinned local certificates and strict behavior/rollback/forwarding acceptance script |
| Dependency posture | Embedded Chroma with fixed ONNX embeddings; removed unused PyTorch/Transformers stack; enforcing audit with four narrow, expiring mitigations |
| Recovery | Private cold backup and an actual restore drill into a separate PostgreSQL database, with row-count/hash/SQLite-integrity validation |
| Delivery | Aligned cached Docker builds, current operating instructions and evidence reports; no remote publication |

The lab changes real behavior in disposable containers. IP blocking applies to
the target HTTP/SSH ingress gateways; it is not a production firewall implementation.

## Verification evidence

- **193 offline tests passed; one explicitly opt-in live case skipped.** No
  placeholder security skips remain. Tests cover actual model inference, auth,
  CSRF, role boundaries, independent review, rate limiting, tampered artifacts,
  failed promotion, interrupted durable jobs, lab intent/rollback/idempotency, response recovery, rule matching,
  TCP gateway revocation, Docker transport uncertainty, preserved volumes, durable
  Wazuh admission, and exact serving-artifact fingerprints.
  The live case calls the same full workflow that was exercised separately.
- **12 live workflow checks passed** against the native APIs, real local Ollama,
  PostgreSQL and ONNX/Chroma retrieval. They cover health/auth, all three serving
  models, knowledge retrieval, triage/persistence/correlation, concurrent retries,
  independent review, stored dry runs/audit, grounded rule generation/backtesting,
  Wazuh-format webhook ingestion and simulation.
  [Workflow evidence](live-verification.json).
- **Six live identity/review checks passed**, including account creation/sign-in,
  rejected privilege escalation, identity-bound authorship, self-review rejection,
  YAML export and account/session revocation. A bounded 100-request inference run
  with concurrency 10 had zero failures (p50 326.72 ms, p95 377.83 ms). Synthetic
  complete inputs measure this workload only, not flow classification accuracy or
  whole-SOC scale. Test accounts were disabled afterward.
  [Security/load evidence](security-live-verification.json).
- A real async alert received HTTP 202, completed through LLM/storage/correlation,
  and remained queryable after a complete service restart. Interrupted work is
  additionally tested by cancellation and reconstruction of the worker pool.
  [Queue evidence](async-verification.json).
- **31 backup files verified**. A fresh PostgreSQL restore matched every table
  count, including 25 alerts and 60 response audit events. Identity, rules, job
  journal and Chroma SQLite checks all returned `ok`. The temporary restore DB was
  removed and the working DB was not overwritten. The final snapshot is
  `../../work/backups/completed-20260904`. [Restore evidence](restore-verification.json).
- The three 15-class models loaded through the real inference API from an isolated
  signed bundle and returned valid 15-class probabilities.
  [Serving-contract evidence](multiclass-serving-verification.json).
- Dependency audit scanned **151 installed packages**, with zero unresolved
  findings and **four documented Chroma mitigations**, reviewed by 2026-10-04.
  This is not a zero-CVE claim. [Audit](dependency-audit.json),
  [exact policy](../security/dependency-exceptions.json).
- Python compilation, fatal-error Ruff checks, root/compatibility/lab Compose
  validation, rendered dashboard JavaScript syntax, and `git diff --check` passed.
  The new identity values were moved outside Jinja's raw script block after the
  rendered-script check caught invalid JavaScript; a regression test covers it.
- **Ten application/maintenance images and the Linux lab target image built.**
  The full container deployment passed all **12 live workflow checks**. Repeating
  startup preserved existing volumes and returned every service to health; four
  core checks passed after the final image replacement. Container feedback
  retraining connected to the database and correctly found zero eligible flows.
  [Container runtime and image evidence](container-runtime-verification.json),
  [full workflow](container-live-verification.json),
  [resume checks](container-resume-verification.json).
- **Five real browser checks passed**, with screenshots reviewed: sign-in and
  command center, independent label review with source inspection, YAML download,
  viewer-account creation/disable, and sign-out access revocation. No page script
  errors occurred. The test uses fresh headless Chromium, without desktop unlock.
  [Browser evidence](browser-verification.json),
  [container browser evidence](container-browser-verification.json).
- **Eight live lab checks passed**: baseline probe HTTP and pinned-host-key SSH;
  IP gateway denial, network detachment and Linux account locking; restoration
  after each action; a real agent event reaching the Wazuh manager and entering
  SOC triage/storage through the durable queued webhook.
  [Lab evidence](lab-verification.json).
- **Four live response drill checks passed** using authored fixture plans and
  separate durable storage: reviewer approval changes real traffic; rollback
  restores it; an effect interrupted before result persistence survives restart
  and is reconciled without replay; rollback then restores traffic and records
  the audit. Missing prevention evidence stays unavailable, not successful.
  [Response recovery evidence and audit](lab-plan-verification.json).
- Docker Desktop required a preserved-disk recovery and a switch from its failing
  Apple Virtualization backend to the installed Docker VMM backend. Previously
  running unrelated containers were restored. The operating guide records the
  recovery copies, bounded startup retries, and deployment data boundaries.

## Multiclass results

Archive: `GeneratedLabelledFlows.zip` from an explicitly identified public mirror
of CICIDS2017, pinned by SHA-256. The original repository's purported MD5 file was
an HTML 404 response and has been removed. Input provenance is documented under
`datasets/CICIDS2017/raw/README.md`.

The benchmark fits on 34,935 rows and evaluates 8,728 held-out rows across all 15
classes, with zero feature-vector overlap. It caps unique samples per class,
rejects nonfinite rows and observed conflicting labels, and fits scaling on the
training set only.

| Model | Accuracy | Macro F1 |
|---|---:|---:|
| Random Forest | 97.54% | 0.8746 |
| Decision Tree | 97.22% | 0.9073 |
| XGBoost | 97.88% | 0.8616 |

[Per-class supports, scores, confusion matrices and methodology](multiclass-evaluation.json)
are part of the result. Very small rare classes limit conclusions. This is a
within-dataset split, not a held-out deployment or time-based generalization test.
The signed research bundle exists locally under
`models/bundles/cicids2017-multiclass-20260904`; large generated artifacts are
excluded from Git. The original binary serving bundle is unchanged.

Genuine independently reviewed complete feedback flows remain absent. No
feedback-driven improvement or candidate promotion has been claimed or performed.

## External deployment and research validation

| Gate | Current blocker / needed input | Required acceptance |
|---|---|---|
| Production integrations | Selected vendors, credentials, assets and deployment target | Actual vendor contract/enforcement/telemetry/rollback checks |
| Shared operations | Identity provider, TLS endpoint, retention and recovery requirements | Deployment-specific auth, TLS, load, backup cutover and operational review |
| ML robustness | Independent deployment captures and defined acceptance thresholds | Out-of-distribution/time-separated evaluation with adequate class support |
| Learning improvement | Genuine reviewed flows accumulated over time | Accepted candidate/champion evaluation and promotion |
| Simulation validity/scale | Controlled exercises and workload definition | Forecast agreement with observed outcomes and repeatable system-scale measurements |

No remote push, pull request, image publication or production deployment occurred.
See [operations.md](operations.md) for exact launch, sign-in, recovery and lab
commands. This report supersedes historical phase-completion claims.
