#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 scripts/container_stack.py up "$@"
printf '%s\n' 'AI-SOC dashboard: http://localhost:5050' 'Run python scripts/smoke_test.py --full after installing tests/requirements.txt.'
