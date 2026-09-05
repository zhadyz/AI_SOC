# Current implementation and acceptance state

Assessment: 2026-09-04 (America/Los_Angeles). Upstream baseline: `60902fa` on
`master`. Local branch: `codex/complete-research-platform`. The initial recovery
was committed as `be32d29`; this continuation adds the functionality below.

## Outcome

The native research application is operational at http://localhost:5050 with
persistent sign-in, eight authenticated APIs, local Ollama, embedded vector
retrieval, PostgreSQL, and a durable asynchronous queue. All nine application
images and the disposable lab target image build successfully.

The wider master-plan vision is **not fully accepted yet**. Full Compose startup,
the real Linux/Wazuh enforcement lab, and visual review of the new access/review
pages remain blocked on this Mac. Docker new-container startup stalled; the desktop
automation tool explicitly reported a locked Mac and requested manual unlock.
The stalled launch/diagnostic CLI processes were stopped. Other applications and
Docker Desktop itself were not restarted or reconfigured.

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
| Disposable enforcement lab | Scoped Linux firewall/network/account controller, durable intent/prior-state journal, Wazuh manager/agent configuration, pinned local certificates and strict behavior/rollback/forwarding acceptance script |
| Dependency posture | Embedded Chroma with fixed ONNX embeddings; removed unused PyTorch/Transformers stack; enforcing audit with four narrow, expiring mitigations |
| Recovery | Private cold backup and an actual restore drill into a separate PostgreSQL database, with row-count/hash/SQLite-integrity validation |
| Delivery | Aligned cached Docker builds, current operating instructions and evidence reports; no remote publication |

The lab row records implemented code, not successful live enforcement. Its
acceptance is explicitly pending below.

## Verification evidence

- **180 offline tests passed; one explicitly opt-in live case skipped.** No
  placeholder security skips remain. Tests cover actual model inference, auth,
  CSRF, role boundaries, independent review, rate limiting, tampered artifacts,
  failed promotion, interrupted durable jobs, lab intent/rollback/idempotency, response recovery and rule matching.
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
  count, including 14 alerts and 44 response audit events. Identity, rules, job
  journal and Chroma SQLite checks all returned `ok`. The temporary restore DB was
  removed and the working DB was not overwritten. Later smoke records are not
  part of that earlier snapshot. [Restore evidence](restore-verification.json).
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
- All nine final application images and the final Linux lab target image built.
  Full container startup is not verified. GitHub Actions was not run remotely.
- All four dashboard pages (`/`, `/reviews`, `/account`, `/login`) render and their
  inline JavaScript parses after restart. New-page visual interaction remains
  unverified because desktop access requires the Mac to be unlocked.

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

## Remaining gates

| Gate | Current blocker / needed input | Required acceptance |
|---|---|---|
| Full Compose runtime | New container startup stalled on this host | Start isolated stack and pass the strict live workflow against container services |
| Disposable lab runtime | Same Docker startup issue; desktop is locked | Real HTTP/SSH denial and restoration; Wazuh agent event forwarded through triage; audited plan execution/recovery |
| New dashboard visual QA | Manual Mac unlock | Sign in, navigate reviews/accounts, submit a review and inspect an export in the browser |
| Production integrations | Selected vendors, credentials, assets and deployment target | Actual vendor contract/enforcement/telemetry/rollback checks |
| Shared operations | Identity provider, TLS endpoint, retention and recovery requirements | Deployment-specific auth, TLS, load, backup cutover and operational review |
| ML robustness | Independent deployment captures and defined acceptance thresholds | Out-of-distribution/time-separated evaluation with adequate class support |
| Learning improvement | Genuine reviewed flows accumulated over time | Accepted candidate/champion evaluation and promotion |
| Simulation validity/scale | Controlled exercises and workload definition | Forecast agreement with observed outcomes and repeatable system-scale measurements |

No remote push, pull request, image publication or production deployment occurred.
See [operations.md](operations.md) for exact launch, sign-in, recovery and lab
commands. This report supersedes historical phase-completion claims.
