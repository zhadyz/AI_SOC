#!/usr/bin/env python3
"""Run retraining against the local stack without printing or exporting secrets."""

import os
from pathlib import Path
import runpy
import sys
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
config = dotenv_values(root / ".env")
if not config.get("POSTGRES_PASSWORD"):
    raise SystemExit("Run scripts/configure_local.py and start the local stack first")
os.environ.setdefault(
    "FEEDBACK_DATABASE_URL",
    f"postgresql://ai_soc:{config['POSTGRES_PASSWORD']}@127.0.0.1:5435/ai_soc",
)
os.environ.setdefault("AI_SOC_API_KEY", config.get("AI_SOC_API_KEY", ""))
os.environ.setdefault("AI_SOC_MODEL_SIGNING_KEY", config.get("AI_SOC_MODEL_SIGNING_KEY", ""))
sys.path.insert(0, str(root))
runpy.run_module("services.retraining.retrain", run_name="__main__")
