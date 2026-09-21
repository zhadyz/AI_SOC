"""Durable local users/sessions and audience-bound, two-minute API identities."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

ROLES = {"viewer", "analyst", "reviewer", "admin"}


def _b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def issue_token(user, secret, now=None):
    if len(secret) < 32 or user["role"] not in ROLES:
        raise ValueError("A strong signing secret and valid role are required")
    now = int(time.time() if now is None else now)
    payload = _b64(json.dumps({"sub": user["username"], "role": user["role"],
                              "aud": "ai-soc-api", "iat": now, "exp": now + 120},
                             separators=(",", ":")).encode())
    signature = hmac.new(secret.encode(), ("ai-soc-v1." + payload).encode(), hashlib.sha256).digest()
    return "soc1." + payload + "." + _b64(signature)


def verify_token(token, secret, now=None):
    try:
        if len(secret) < 32 or len(token) > 2048:
            return None
        version, payload, signature = token.split(".")
        expected = _b64(hmac.new(secret.encode(), ("ai-soc-v1." + payload).encode(), hashlib.sha256).digest())
        if version != "soc1" or not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        now = time.time() if now is None else now
        if (claims["aud"] != "ai-soc-api" or claims["role"] not in ROLES
                or not re.fullmatch(r"[A-Za-z0-9_.@-]{1,64}", claims["sub"])
                or not (claims["iat"] <= now < claims["exp"] <= claims["iat"] + 120)):
            return None
        return {"username": claims["sub"], "role": claims["role"]}
    except (ValueError, KeyError, TypeError):
        return None


def permitted(role, method, path):
    if role in {"admin", "service"}:
        return True
    if path in {"/auth/token", "/logout"}:
        return True
    if path.startswith("/auth/users") or path == "/models/reload" or path.startswith("/ingest"):
        return False
    if method in {"GET", "HEAD", "OPTIONS"}:
        return True
    if any(part in path.split("/") for part in ("approve", "reject", "reviews", "execute", "reconcile", "rollback", "verify", "cancel")):
        return role == "reviewer"
    if method == "POST" and path in {"/query", "/retrieve", "/predict", "/predict/named", "/predict/batch"}:
        return True
    return role in {"analyst", "reviewer"}


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32).hex()


class IdentityStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, role TEXT NOT NULL, salt TEXT NOT NULL,
                password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
              CREATE TABLE IF NOT EXISTS sessions (
                digest TEXT PRIMARY KEY, username TEXT NOT NULL, expires REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS identity_audit (
                id INTEGER PRIMARY KEY, timestamp REAL NOT NULL, actor TEXT NOT NULL,
                event TEXT NOT NULL, subject TEXT NOT NULL);
            """)
        os.chmod(self.path, 0o600)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def users(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT username, role, active FROM users ORDER BY username")]

    def create_user(self, username, password, role, actor="local-admin"):
        if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,64}", username) or role not in ROLES:
            raise ValueError("Use a valid username and role")
        if not 14 <= len(password) <= 256:
            raise ValueError("Use a password or passphrase of 14–256 characters")
        salt = secrets.token_bytes(16)
        with self.connect() as db:
            try:
                db.execute("INSERT INTO users (username,role,salt,password_hash) VALUES (?,?,?,?)",
                           (username, role, salt.hex(), password_hash(password, salt)))
            except sqlite3.IntegrityError:
                raise ValueError("Username already exists") from None
            self._audit(db, actor, "user_created", username)

    def update_user(self, username, *, role=None, active=None, password=None, actor="local-admin"):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if not row:
                raise ValueError("User not found")
            new_role = row["role"] if role is None else role
            new_active = row["active"] if active is None else int(bool(active))
            if new_role not in ROLES:
                raise ValueError("Invalid role")
            if row["role"] == "admin" and row["active"] and (new_role != "admin" or not new_active):
                if db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0] <= 1:
                    raise ValueError("Cannot remove the last active administrator")
            salt, hashed = row["salt"], row["password_hash"]
            if password is not None:
                if not 14 <= len(password) <= 256:
                    raise ValueError("Use a password or passphrase of 14–256 characters")
                salt = secrets.token_hex(16)
                hashed = password_hash(password, bytes.fromhex(salt))
            db.execute("UPDATE users SET role=?, active=?, salt=?, password_hash=? WHERE username=?",
                       (new_role, new_active, salt, hashed, username))
            db.execute("DELETE FROM sessions WHERE username=?", (username,))
            self._audit(db, actor, "user_updated_sessions_revoked", username)

    def login(self, username, password):
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            salt = bytes.fromhex(row["salt"]) if row else b"ai-soc-dummy-salt"
            hashed = password_hash(password[:257], salt)
            valid = bool(row and row["active"] and hmac.compare_digest(hashed, row["password_hash"]))
            self._audit(db, username[:64], "login_success" if valid else "login_failed", username[:64])
            if not valid:
                return None
            token = secrets.token_urlsafe(32)
            db.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (self.digest(token), username, time.time() + 8 * 3600))
            return token

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def session_user(self, token):
        with self.connect() as db:
            row = db.execute("""SELECT u.username,u.role FROM sessions s JOIN users u USING(username)
                              WHERE s.digest=? AND s.expires>? AND u.active=1""",
                             (self.digest(token), time.time())).fetchone()
            return dict(row) if row else None

    def logout(self, token):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE digest=?", (self.digest(token),))

    @staticmethod
    def _audit(db, actor, event, subject):
        db.execute("INSERT INTO identity_audit(timestamp,actor,event,subject) VALUES (?,?,?,?)",
                   (time.time(), actor, event, subject))
