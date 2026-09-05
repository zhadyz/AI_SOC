# Recovery assessment and verified state

Date: 2026-09-04 (America/Los_Angeles). Upstream baseline: `60902fa` on `master`.
Local branch: `codex/complete-research-platform`.

## Outcome

The recoverable local research workflow is operational. Eight APIs, PostgreSQL,
ChromaDB, Ollama and the dashboard run locally. The original repository had no
complete committed master plan: its roadmap was a placeholder and its status link
was missing. The target was reconstructed from the README, architecture, services
and experiments, and recorded in [completion-plan.md](completion-plan.md).

This completes that local implementation scope. It does **not** establish a
production SOC, empirical prevention effectiveness, multiclass classification,
robustness, or feedback-driven model improvement. Those acceptance gates are listed
below with the information required to complete them.

## What was recovered

| Area | Baseline problem | Current behavior |
|---|---|---|
| Packaging | `models`/`config` imports collided across service test suites | Explicit importable service namespaces; existing directory names preserved |
| ML | Stale dependency versions, 78-feature tests, fabricated partial flows, weak reload behavior | Real 77-feature models validated together, complete finite measurements only, named-feature reordering and atomic bundle reload |
| Triage | RAG setting unused; storage/correlation differed by entry point | Retrieved evidence and references in the prompt; sync/batch/async share durable alert storage and idempotent correlation |
| Context | Requests to an absent contexts API and feedback summaries with no verdicts | Bounded operator environment notes and actual analyst verdict retrieval |
| Knowledge | Zero-embedding fallbacks and false-success errors | Real embeddings; explicit dependency failures; persistent runbook/MITRE retrieval |
| Correlation | Concurrent retries could duplicate incident membership | Transaction lock and alert-ID deduplication; tactic IDs/names normalize consistently |
| Response | In-memory plans, unenforced veto delay, missing action parameters | Transactional plan/event state, approval identities, waiting veto windows, parameter forwarding and restart recovery |
| Evidence | Stub adapters and failed monitoring reported success; briefings invented reductions and targets | Unavailable adapter outcomes, no fabricated targets, policy-derived briefings, independent monitoring/post-action evidence required |
| Learning | Synthetic features and inconsistent partial model promotion | Independent review, actual flow features, conflicting-label exclusion, holdout-overlap checks and complete immutable bundles |
| Rules | Fragile YAML generation, keyword-based fake backtests, volatile state | Sample-grounded schema-constrained drafts, validated Sigma subset, labeled-event evaluation, persisted reviews, unknown FPR until measured |
| Dashboard | Misleading containment buttons, invalid sample/rule requests, lost corrections | Accurate feedback labels, explicit defense previews, saved plan/audit view and corrected investigation requests |
| Runtime | Conflicting stacks, stale Dockerfiles and failure-suppressing CI | Canonical loopback Compose, private generated config, native launcher, aligned root-context Dockerfiles and enforceable CI definitions |

## Verification evidence

- **160 tests passed, 14 skipped** in the final offline run with Python 3.11.15.
  These include real bundled-model inference, malformed/nonfinite input, failed
  reload preservation, durable plan recovery, duplicate approval races, veto
  timing, unavailable evidence, honest targets, review eligibility and rule
  matching. Skips comprise nine explicit live tests and five old placeholders
  covering rate limiting, dependency scanning, user management, artifact integrity
  checks and broader configuration validation. Skips are not successful checks.
- **12 live workflow checks passed** using real local Ollama, PostgreSQL, ChromaDB
  and service HTTP endpoints. See [live-verification.json](live-verification.json)
  for timestamp and artifact IDs. The checks cover all service health endpoints,
  authentication, all three trained models, real knowledge retrieval, LLM triage,
  persistence/correlation, concurrent retries, independent feedback review,
  durable dry-run planning/audit, rule generation/backtesting, Wazuh-format webhook
  ingestion, and a short simulated campaign. Some checks combine related steps.
- **Four saved PostgreSQL plans were restored after a process restart**, including
  prior dry-run results and audit events. SQLite lifecycle tests also exercise
  interrupted execution recovery without replay.
- **858 MITRE technique documents were ingested** from MITRE's enterprise dataset;
  startup runbooks and MITRE persist in ChromaDB.
- **Zero eligible retraining flows** were found among synthetic text-only smoke
  alerts. No candidate was trained or promoted; bundled models remain unchanged.
- Python compilation, fatal-error Ruff checks, dashboard JavaScript syntax, root
  Compose validation, both compatibility includes, `git diff --check`, and a scan
  for the newly generated credentials passed.
- The dashboard was inspected in the browser with all eight services responding,
  incident investigation, accurate dry-run controls, and saved plans/audit visible.
  Browser testing confirmed that a submitted severity correction was saved under the correct backend field. The browser displayed a clearly labeled sample-match fallback and persisted its approval for export under analyst-1. Rule generation and review use the actual nested rule response and per-alert rule IDs. Earlier smoke drafts are test artifacts, not operational detection recommendations.

Commands: `pytest -q -rs`, `python -m compileall -q services ml_training dashboard
scripts`, `ruff check --select E9,F63,F7,F82 services ml_training dashboard scripts
tests`, `python scripts/smoke_test.py --full`, and `docker compose config --quiet`.

## Deployment qualification

Native Python/Ollama plus an isolated PostgreSQL container is the verified runtime
on this Mac. The native dashboard uses Waitress to avoid macOS process-fork reload
failures; container deployment uses Gunicorn on Linux. See [operations.md](operations.md)
and the root README for start/stop/configuration instructions.

Docker stalled fetching `python:3.11-slim` metadata and eventually timed out. The
Compose definitions validate, but a complete image build/start was **not verified
on this host**. The new CI matrix builds all nine actual application images and
fails on errors; it has not been executed on GitHub. No remote code, images or
production resources were published by this task.

## Remaining acceptance gates

| Work | Required input/environment | Completion evidence |
|---|---|---|
| Vendor enforcement | Selected firewall, EDR and identity vendors; credentials; disposable assets | Contract tests and lab execution/rollback with independent telemetry |
| Wazuh command enforcement | Running manager/indexer, named lab agents, installed/tested command, trusted certificates | Actual agent command submission, verified host behavior and recovery; the webhook test alone is insufficient |
| Shared/production operations | Identity provider and role model, deployment target, retention and recovery requirements | Enforced authorization, TLS, rate limits, backup/restore, security review and operational load tests |
| Container acceptance | Working Docker base-image retrieval and a clean build runner | All service image builds plus the strict live smoke against Compose |
| Multiclass/robust ML | Real labeled multiclass flows and a held-out independent dataset | Reproducible evaluation, leakage checks and accepted baseline comparison |
| Learning improvement | Enough genuine independently reviewed complete flows, independent holdout | Measured candidate/champion improvement and accepted bundle promotion |
| Simulation validity/scale | Controlled adversary-emulation lab and defined workload | Forecast agreement with observed outcomes, repeatable scale/robustness measurements |

These are unfinished parts of the broader vision. Code and synthetic smoke results
cannot substitute for their missing evidence. Historical phase documents and
archived test sketches are preserved for reference; this report is the current
source of verification status.
