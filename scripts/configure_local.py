#!/usr/bin/env python3
"""Generate local credentials once without printing secrets or overwriting config."""
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
target = root / ".env"
if target.exists():
    print("Using existing .env; no changes made")
else:
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(f"AI_SOC_API_KEY={secrets.token_hex(32)}\n")
        stream.write(f"POSTGRES_PASSWORD={secrets.token_hex(24)}\n")
        stream.write("OLLAMA_MODEL=llama3.2:3b\n")
    print("Created private .env for the local research stack")
