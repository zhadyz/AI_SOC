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
