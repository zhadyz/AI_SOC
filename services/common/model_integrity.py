"""Verify bytes before deserializing trusted model artifacts.

The base manifest is versioned with the source. Promoted bundles additionally
require an HMAC from the local training authority. An API caller cannot create
or sign a model through the inference API.
"""
import hashlib
import hmac
import json
from pathlib import Path

MODEL_FILES = tuple(f"{name}.pkl" for name in (
    "random_forest_ids", "xgboost_ids", "decision_tree_ids", "scaler", "label_encoder", "feature_names"))


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def write_manifest(directory, signing_key=None):
    directory = Path(directory)
    payload = {"version": 1, "files": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                       for name in MODEL_FILES}}
    if signing_key:
        if len(signing_key) < 32:
            raise ValueError("Model signing key must contain at least 32 characters")
        payload["signature"] = hmac.new(signing_key.encode(), canonical(payload), hashlib.sha256).hexdigest()
    (directory / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n")


def verified_bytes(directory, signing_key=None, require_signature=False):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    signature = manifest.pop("signature", "")
    if manifest.get("version") != 1 or set(manifest.get("files", {})) != set(MODEL_FILES):
        raise ValueError("Invalid model manifest")
    if require_signature or signature:
        if not signing_key or len(signing_key) < 32:
            raise ValueError("A trusted signing key is required for promoted model bundles")
        expected = hmac.new(signing_key.encode(), canonical(manifest), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Model manifest signature does not match the training authority")
    result = {}
    for name in MODEL_FILES:
        path = directory / name
        if path.is_symlink() or path.stat().st_size > 256 * 1024 * 1024:
            raise ValueError(f"Invalid artifact: {name}")
        data = path.read_bytes()
        if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), manifest["files"][name]):
            raise ValueError(f"Model integrity check failed: {name}")
        result[name] = data
    return result
