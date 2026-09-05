# Completion plan and repository assessment

Assessment date: 2026-09-04. Upstream baseline: `60902fa` (`master`).
Implementation branch: `codex/complete-research-platform`.

## Reconstructed intent

No separate master plan is committed: the development roadmap is a placeholder
and its linked status document is missing. The README, architecture, service
code, and experiments describe a local-first research SOC with this workflow:

1. Ingest Wazuh alerts and complete CICIDS2017 network flows.
2. Classify flows with the bundled models, enrich alerts with local knowledge,
   and obtain structured triage from a local Ollama model.
3. Persist alerts, correlate incidents, and capture analyst corrections.
4. Model attack campaigns and propose D3FEND-informed defenses.
5. Review, execute, persist, and verify response plans with explicit approvals.
6. Generate reviewable detection rules and evaluate feedback-driven retraining.
7. Run the system reproducibly with an analyst dashboard and enforceable CI.

This is the implementation target. Vendor-specific production rollout and
empirical research claims require external infrastructure or datasets; they
cannot be declared complete through code changes or synthetic test results.

## Evidence at baseline

* Python source compiles; fatal-error lint passes.
* The first combined unit/orchestrator run stops at 11 failures and one fixture
  error, with only three passes and three skips. Tests use stale Pydantic schemas;
  unqualified `models`/`config` imports collide across services.
* Most CI commands suppress failures. Its matrix includes nonexistent services.
* The bundled model contract is 77 features; numerous tests expect 78. Artifacts
  were serialized with scikit-learn 1.7.2. XGBoost needs an OpenMP runtime.
* Response tables exist but the orchestrator never reads or writes them. Plans
  and approvals disappear on restart. Adapter parameters are not propagated.
* Firewall, EDR, and identity stubs report successful execution and verification.
* Verification estimates risk reduction when simulation fails and treats failed
  monitoring as an absence of attacks. The documented veto delay is not enforced.
* Compose defaults enable response execution; some dependency health checks use
  binaries absent from the images, and an external SIEM network is mandatory.
* RAG falls back to zero embeddings and can report healthy without its database.
* Retraining fabricates network features from alert metadata and promotes models
  individually despite replacing the scaler shared by all models.

## Acceptance gates

- [x] Real model inference, finite 77-feature validation, atomic model reload.
- [x] Reliable isolated tests and CI that fails on regressions.
- [x] Durable response plans and approval audit with restart recovery.
- [x] Dry-run default, enforceable approval/veto rules, honest adapter results.
- [x] Evidence-based verification with unavailable dependencies reported explicitly.
- [x] Working alert → triage → persistence → correlation → defense workflow.
- [x] RAG ingestion/retrieval that fails clearly when dependencies are unavailable.
- [x] Reviewed feedback only; no fabricated training features or mixed model bundles.
- [x] Reproducible local deployment, documented configuration and smoke checks.
- [x] Verified dashboard/API access and a current status report with remaining gates.

## Continuation acceptance

- [x] Persistent accounts, service-enforced roles, CSRF, identity-bound audit and rate limits.
- [x] Analyst/reviewer interface with independent label decisions and real YAML exports.
- [x] Durable triage admission/results and restart recovery; no accepted in-memory-only jobs.
- [x] Artifact verification before deserialization, signed candidates and failed-promotion recovery.
- [x] Train/evaluate all three classifiers on real 15-class flows with leakage checks.
- [x] Cold backup and real isolated restore drill, including the job journal and identity.
- [x] Enforcing dependency audit with explicit expiring mitigations.
- [x] Build all nine application images and the Linux/Wazuh lab target image.
- [x] Implement narrowly scoped lab actions, observation, rollback and acceptance tooling.
- [ ] Accept full Compose runtime and execute the real lab traffic/SSH/Wazuh checks.
- [ ] Visually accept the new review/access pages after the Mac is unlocked.
- [ ] Validate production vendors, shared deployment and empirical research claims.

## Remaining acceptance

Docker new-container startup stalled on this host. The desktop tool reports that
manual Mac unlock is required. Pending launch attempts were stopped; native
services remain operational. The lab has code and a built target image, but its
real effects/rollback have not passed acceptance. No successful lab report is
implied by unit tests or simulated webhooks.

The real multiclass benchmark is complete as a within-dataset experiment. Separate
captures are still required for generalization/robustness claims. Genuine reviewed
traffic remains necessary for empirical feedback-driven improvement. Production
vendor choices, identity/TLS deployment, retention requirements and observed
adversary-emulation outcomes also remain external inputs.

The exact passed checks, limitations and next acceptance commands are recorded in
[status.md](status.md) and [operations.md](operations.md). These distinctions prevent
an implemented feature from being mistaken for a verified production outcome.
