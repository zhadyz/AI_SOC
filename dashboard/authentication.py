"""Browser authentication and administration for the local SOC gateway."""
import os
from pathlib import Path
import secrets

from flask import g, jsonify, redirect, render_template, request, session
from services.common.identity import IdentityStore, issue_token, permitted
from services.common.rate_limit import SlidingWindowRateLimiter


def install_auth(app):
    secret = os.getenv("AI_SOC_AUTH_SECRET", "")
    app.secret_key = secret or secrets.token_hex(32)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                      SESSION_COOKIE_SECURE=os.getenv("AI_SOC_HTTPS") == "true",
                      MAX_CONTENT_LENGTH=8 * 1024 * 1024)
    limiter = SlidingWindowRateLimiter(10, 60)
    request_limiter = SlidingWindowRateLimiter(600, 60)
    store_path = os.getenv("AI_SOC_IDENTITY_DB", str(Path(__file__).resolve().parent.parent / "work/identity.sqlite"))
    store = IdentityStore(store_path)
    app.extensions["identity_store"] = store

    @app.before_request
    def authenticate():
        g.user = None
        if request.path in {"/health", "/login"} or request.path.startswith("/static/"):
            return
        if not secret and os.getenv("AI_SOC_ALLOW_INSECURE_LOCAL") == "true":
            g.user = {"username": "local-development", "role": "admin"}
            return
        if len(secret) < 32:
            return jsonify(error="Run scripts/configure_local.py and restart the dashboard"), 503
        g.user = store.session_user(session.get("token", ""))
        if not g.user:
            if request.path.startswith("/api/"):
                return jsonify(error="Sign in to continue"), 401
            return redirect("/login")
        allowed, retry = request_limiter.is_allowed(g.user["username"])
        if not allowed:
            return jsonify(error="Request limit exceeded"), 429, {"Retry-After": str(retry)}
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            csrf = request.headers.get("X-CSRF-Token") or request.form.get("csrf", "")
            if not secrets.compare_digest(csrf, session.get("csrf", "invalid")):
                return jsonify(error="Invalid CSRF token; reload the page"), 403
        path = request.path.removeprefix("/api")
        if not permitted(g.user["role"], request.method, path):
            return jsonify(error="Role does not permit this operation"), 403

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        # Inline scripts/styles are retained for the existing dashboard. No
        # external framing, embedded plugins or off-origin API calls are allowed.
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if len(secret) < 32:
            return "Run scripts/configure_local.py and restart the dashboard.", 503
        error = None
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        if request.method == "POST":
            if not secrets.compare_digest(request.form.get("csrf", ""), session["csrf"]):
                return "Invalid sign-in form; reload the page.", 403
            allowed, retry = limiter.is_allowed(request.remote_addr or "unknown")
            if not allowed:
                return render_template("login.html", error="Too many attempts. Try again shortly."), 429, {"Retry-After": str(retry)}
            token = store.login(request.form.get("username", ""), request.form.get("password", ""))
            if token:
                session.clear()
                session.update(token=token, csrf=secrets.token_urlsafe(32))
                return redirect("/")
            error = "Username or password is incorrect."
        return render_template("login.html", error=error), 401 if error else 200

    @app.post("/logout")
    def logout():
        store.logout(session.get("token", ""))
        session.clear()
        return redirect("/login")

    @app.get("/api/auth/me")
    def whoami():
        return jsonify(**g.user, csrf=session.get("csrf"))

    @app.post("/api/auth/token")
    def api_token():
        return jsonify(access_token=issue_token(g.user, secret), token_type="Bearer", expires_in=120)

    @app.route("/api/auth/users", methods=["GET", "POST"])
    def users():
        if request.method == "GET":
            return jsonify(users=store.users())
        data = request.get_json() or {}
        try:
            store.create_user(data.get("username", ""), data.get("password", ""), data.get("role", "viewer"), g.user["username"])
        except (ValueError, TypeError) as exc:
            return jsonify(error=str(exc)), 422
        return jsonify(status="created"), 201

    @app.patch("/api/auth/users/<username>")
    def update_user(username):
        data = request.get_json() or {}
        try:
            store.update_user(username, role=data.get("role"), active=data.get("active"),
                              password=data.get("password"), actor=g.user["username"])
        except (ValueError, TypeError) as exc:
            return jsonify(error=str(exc)), 422
        return jsonify(status="updated", sessions_revoked=True)

    @app.get("/account")
    def account():
        return render_template("account.html")
