#!/usr/bin/env python3
"""Create private local credentials and bootstrap one administrator, idempotently."""
import argparse
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from services.common.identity import IdentityStore


def configure(root=ROOT, state_dir=None):
    target = root / ".env"
    config = {}
    if target.exists():
        config = dict(line.split("=", 1) for line in target.read_text().splitlines()
                      if line and not line.startswith("#") and "=" in line)
    state = (state_dir or root / "work/runtime").resolve()
    additions = {"AI_SOC_API_KEY": secrets.token_hex(32), "POSTGRES_PASSWORD": secrets.token_hex(24),
                 "AI_SOC_AUTH_SECRET": secrets.token_hex(32), "OLLAMA_MODEL": "llama3.2:3b",
                 "AI_SOC_MODEL_SIGNING_KEY": secrets.token_hex(32),
                 "AI_SOC_IDENTITY_DIR": str(state / "identity")}
    missing = {k: v for k, v in additions.items() if not config.get(k)}
    if missing:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a") as stream:
            stream.write("\n" + "".join(f"{k}={v}\n" for k, v in missing.items()))
        config.update(missing)
    os.chmod(target, 0o600)
    for field in ("AI_SOC_API_KEY", "POSTGRES_PASSWORD", "AI_SOC_AUTH_SECRET", "AI_SOC_MODEL_SIGNING_KEY"):
        if len(config[field]) < 32 or config[field].lower().startswith(("replace-", "change-me", "example-")):
            raise ValueError(f"{field} must have at least 32 characters; existing values were preserved")
    identity_dir = Path(config["AI_SOC_IDENTITY_DIR"])
    store = IdentityStore(identity_dir / "identity.sqlite")
    if not store.users():
        credentials = identity_dir.parent / "admin-credentials.txt"
        if credentials.exists():
            # Recover an interrupted bootstrap without replacing its password.
            contents = credentials.read_text()
            if "Username: admin\nPassword: " not in contents:
                raise ValueError("Existing bootstrap credentials are malformed; inspect the private file")
            password = contents.split("Password: ", 1)[1].strip()
            os.chmod(credentials, 0o600)
        else:
            password = secrets.token_urlsafe(24)
            fd = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                stream.write(f"AI-SOC local administrator\nUsername: admin\nPassword: {password}\n")
        store.create_user("admin", password, "admin", "bootstrap")
        print(f"Created administrator; private sign-in details: {credentials}")
    print("Local credentials and identity directory are ready; existing settings preserved")
    return config


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path)
    args = parser.parse_args()
    configure(state_dir=args.state_dir)
