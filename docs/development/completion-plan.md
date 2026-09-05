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

## External acceptance still required

* Choose production firewall/EDR/identity vendors and provide a disposable test
  environment before implementing or accepting real destructive response actions.
* Connect a Wazuh installation and test active-response commands on lab agents.
* Supply labeled multiclass flow data and independent held-out traffic for
  multiclass training, robustness evaluation, and promotion acceptance.
* Run controlled adversary-emulation exercises to validate simulation forecasts.
* Observe genuine analyst feedback over time to measure retraining improvement.

These checked gates cover the implemented local research scope. Container-image build acceptance and the external production/research gates above remain open. Exact commands and limits are recorded in `status.md`.
