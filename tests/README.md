# Verification

Install `tests/requirements.txt` with Python 3.11 and run `pytest` from the root.
This exercises actual bundled models and isolated service/state-machine contracts.
It does not require a running stack. Explicit live tests are skipped offline.

Run `python scripts/smoke_test.py --full` against the configured local stack for
real Ollama, Chroma, PostgreSQL and HTTP workflow acceptance. Any failed assertion
or service fails the command. The same check is `pytest --live tests/e2e`.

The original external-product UI and pipeline sketches live in
`experiments/legacy-tests`; their swallowed failures are not verification evidence.
The current result and limitations are in `docs/development/status.md`.

## Recovered platform acceptance

The repository-wide `pytest` run enforces offline regression tests, including real
model inference, access controls, response persistence/recovery, durable job
admission, container retry/seeding, artifact fingerprints and real ephemeral TCP
gateway behavior. One end-to-end case is explicitly opt-in; the standalone strict
live workflow runs it against an actual deployment:

```bash
.venv/bin/python scripts/smoke_test.py --full --output work/live-report.json
```

For browser acceptance, first run a stack and generate at least one detection rule
(the full workflow above does this). Install with `npm ci --prefix tests/browser`,
then install Chromium from that directory with `npx playwright install chromium`.
Run `npm test --prefix tests/browser`. The test uses private bootstrap credentials,
creates a clearly marked synthetic review fixture, exercises UI review/export and
account administration, disables the test account, and signs out. Reports and
screenshots are written to `docs/development`.

The isolated Wazuh lab has two sequential acceptance scripts:

```bash
.venv/bin/python scripts/lab_smoke.py --state-dir work/lab --output work/lab-report.json
.venv/bin/python scripts/lab_plan_smoke.py --state-dir work/lab --output work/lab-plan-report.json
```

They require the labeled disposable lab and a running SOC. They perform real
probe-only effects and restore them. The second uses authored fixture plans and a
separate durable store to exercise the actual response engine, HTTP adapter,
controller, approval, restart reconciliation and rollback. No production vendor
or empirical prevention result is implied by these tests.
