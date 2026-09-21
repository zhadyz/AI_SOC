"""Executable security acceptance checks, without placeholder skips."""
import hashlib
import json
from pathlib import Path
import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient
from flask import Flask
import pytest

from dashboard.authentication import install_auth
from services.common.api_security import actor_id, protect_app
from services.common.identity import IdentityStore, issue_token, verify_token
from services.common.model_integrity import verified_bytes, write_manifest
from services.common.rate_limit import SlidingWindowRateLimiter
from scripts.configure_local import configure

SECRET = "test-only-signing-key-" * 3


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setenv("AI_SOC_API_KEY", "test-machine-key")
    monkeypatch.setenv("AI_SOC_AUTH_SECRET", SECRET)
    app = FastAPI()
    protect_app(app)

    @app.get("/health")
    def health():
        return {"healthy": True}

    @app.get("/plans")
    @app.post("/feedback/test")
    @app.post("/plans/1/actions/2/approve")
    @app.post("/models/reload")
    def protected():
        return {"actor": actor_id("forged-reviewer")}

    return TestClient(app)


@pytest.mark.parametrize("role,path,status", [
    ("viewer", "/feedback/test", 403), ("analyst", "/feedback/test", 200),
    ("analyst", "/plans/1/actions/2/approve", 403),
    ("reviewer", "/plans/1/actions/2/approve", 200),
    ("reviewer", "/models/reload", 403), ("admin", "/models/reload", 200),
])
def test_permissions_at_service_boundary(service, role, path, status):
    token = issue_token({"username": "alice", "role": role}, SECRET)
    response = service.post(path, headers={"Authorization": "Bearer " + token})
    assert response.status_code == status
    if status == 200:
        assert response.json()["actor"] == "alice"


def test_anonymous_and_forged_credentials_rejected(service):
    assert service.get("/health").status_code == 200
    assert service.get("/plans").status_code == 401
    token = issue_token({"username": "alice", "role": "admin"}, "wrong-secret-" * 4)
    assert service.get("/plans", headers={"Authorization": "Bearer " + token}).status_code == 401
    assert service.get("/health").headers["x-frame-options"] == "DENY"


def test_no_implicit_auth_bypass(service, monkeypatch):
    monkeypatch.delenv("AI_SOC_API_KEY")
    monkeypatch.delenv("AI_SOC_ALLOW_INSECURE_LOCAL")
    assert service.get("/plans").status_code == 401


def test_token_expiration_and_tampering():
    token = issue_token({"username": "alice", "role": "viewer"}, SECRET, now=100)
    assert verify_token(token, SECRET, now=219)["role"] == "viewer"
    assert verify_token(token, SECRET, now=220) is None
    assert verify_token(token, SECRET, now=99) is None
    assert verify_token(token + "x", SECRET, now=110) is None


def test_passwords_sessions_and_revocation(tmp_path):
    store = IdentityStore(tmp_path / "users.sqlite")
    store.create_user("alice", "a long unique passphrase", "admin")
    with pytest.raises(ValueError, match="14"):
        store.create_user("bob", "short", "viewer")
    with pytest.raises(ValueError):
        store.create_user("<script>", "a long unique passphrase", "admin")
    assert store.login("alice", "incorrect") is None
    assert store.login("unknown", "incorrect") is None
    token = store.login("alice", "a long unique passphrase")
    assert IdentityStore(store.path).session_user(token)["username"] == "alice"
    with store.connect() as db:
        row = dict(db.execute("SELECT * FROM users").fetchone())
        assert row["password_hash"] != "a long unique passphrase"
        assert db.execute("SELECT digest FROM sessions").fetchone()[0] == hashlib.sha256(token.encode()).hexdigest()
    with pytest.raises(ValueError, match="last"):
        store.update_user("alice", active=False)
    store.update_user("alice", password="a changed unique passphrase")
    assert store.session_user(token) is None
    assert store.login("alice", "a long unique passphrase") is None


def test_gateway_login_csrf_and_admin_boundaries(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_SOC_AUTH_SECRET", SECRET)
    monkeypatch.setenv("AI_SOC_IDENTITY_DB", str(tmp_path / "identity.sqlite"))
    template_dir = Path(__file__).resolve().parents[2] / "dashboard/templates"
    app = Flask(__name__, template_folder=str(template_dir))
    install_auth(app)
    store = app.extensions["identity_store"]
    store.create_user("reader", "a long unique passphrase", "viewer")
    client = app.test_client()
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/account").status_code == 302
    assert client.get("/login").status_code == 200
    with client.session_transaction() as session:
        csrf = session["csrf"]
    assert client.post("/login", data={"username": "reader", "password": "a long unique passphrase"}).status_code == 403
    response = client.post("/login", data={"username": "reader", "password": "a long unique passphrase", "csrf": csrf})
    assert response.status_code == 302
    assert "HttpOnly" in response.headers["Set-Cookie"] and "SameSite=Strict" in response.headers["Set-Cookie"]
    assert client.get("/api/auth/users").status_code == 403
    assert client.post("/api/auth/token").status_code == 403
    assert client.get("/api/auth/me").json["username"] == "reader"
    with client.session_transaction() as session:
        csrf = session["csrf"]
    # Token issuance is allowed for every signed-in role but retains that role.
    result = client.post("/api/auth/token", headers={"X-CSRF-Token": csrf})
    assert result.status_code == 200
    assert verify_token(result.json["access_token"], SECRET)["role"] == "viewer"


def test_rate_limit_expires_and_cannot_be_evicted_by_rotating_clients():
    clock = [0.0]
    limiter = SlidingWindowRateLimiter(2, 60, 2, clock=lambda: clock[0])
    assert limiter.is_allowed("alice")[0]
    assert limiter.is_allowed("alice")[0]
    assert limiter.is_allowed("alice") == (False, 60)
    assert limiter.is_allowed("bob")[0]
    assert not limiter.is_allowed("third")[0]
    assert not limiter.is_allowed("alice")[0]
    clock[0] = 60
    assert limiter.is_allowed("alice")[0]


def test_http_rate_limit_is_enforced(monkeypatch):
    monkeypatch.setenv("AI_SOC_RATE_LIMIT", "2")
    monkeypatch.setenv("AI_SOC_API_KEY", "machine-key")
    app = FastAPI()
    protect_app(app)
    @app.get("/protected")
    def route():
        return {}
    client = TestClient(app, headers={"Authorization": "Bearer machine-key"})
    assert client.get("/protected").status_code == 200
    assert client.get("/protected").status_code == 200
    result = client.get("/protected", headers={"X-Forwarded-For": "198.51.100.1"})
    assert result.status_code == 429 and int(result.headers["Retry-After"]) > 0


def test_model_integrity_checked_before_deserialization(tmp_path):
    root = Path(__file__).resolve().parents[2] / "models"
    for name in [*root.glob("*.pkl"), root / "manifest.json"]:
        shutil.copy(name, tmp_path / name.name)
    assert len(verified_bytes(tmp_path)) == 6
    write_manifest(tmp_path, SECRET)
    assert len(verified_bytes(tmp_path, SECRET, require_signature=True)) == 6
    with pytest.raises(ValueError, match="signature"):
        verified_bytes(tmp_path, "another-signing-key-" * 3, True)
    (tmp_path / "scaler.pkl").write_bytes(b"malicious pickle bytes")
    with pytest.raises(ValueError, match="integrity"):
        verified_bytes(tmp_path, SECRET, True)


def test_setup_is_idempotent_and_rejects_weak_existing_keys(tmp_path):
    config = configure(tmp_path)
    before = (tmp_path / ".env").read_bytes()
    assert configure(tmp_path) == config
    assert (tmp_path / ".env").read_bytes() == before
    assert (tmp_path / ".env").stat().st_mode & 0o777 == 0o600
    (tmp_path / ".env").write_text(before.decode().replace(config["AI_SOC_API_KEY"], "weak"))
    with pytest.raises(ValueError, match="AI_SOC_API_KEY"):
        configure(tmp_path)
