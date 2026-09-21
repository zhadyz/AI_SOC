"""Shared API-key boundary for local AI-SOC services and their internal clients."""
import hmac
import os
from contextvars import ContextVar

import httpx
from starlette.responses import JSONResponse
from services.common.identity import verify_token, permitted
from services.common.rate_limit import SlidingWindowRateLimiter

principal = ContextVar("ai_soc_principal", default=None)


def actor_id(supplied):
    """Human audit identities always come from the verified token."""
    user = principal.get()
    return user["username"] if user and user["role"] != "service" else supplied


def service_headers():
    key = os.getenv("AI_SOC_API_KEY", "")
    return {"Authorization": f"Bearer {key}"} if key else {}


def service_client(**kwargs):
    # Use only for AI-SOC services and the local Ollama backend, never vendor APIs.
    headers = {**service_headers(), **kwargs.pop("headers", {})}
    return httpx.AsyncClient(headers=headers, **kwargs)


def protect_app(app):
    limiter = SlidingWindowRateLimiter(int(os.getenv("AI_SOC_RATE_LIMIT", "600")), 60)

    @app.middleware("http")
    async def api_boundary(request, call_next):
        key = os.getenv("AI_SOC_API_KEY", "")
        user = None
        if request.url.path not in {"/health", "/metrics"}:
            authorization = request.headers.get("authorization", "")
            if key and hmac.compare_digest(authorization, f"Bearer {key}"):
                user = {"username": "service", "role": "service"}
            elif authorization.startswith("Bearer "):
                user = verify_token(authorization[7:], os.getenv("AI_SOC_AUTH_SECRET", ""))
            elif not key and os.getenv("AI_SOC_ALLOW_INSECURE_LOCAL") == "true":
                user = {"username": "local-development", "role": "service"}
            if not user:
                return JSONResponse({"detail": "API credentials required"}, status_code=401,
                                    headers={"WWW-Authenticate": "Bearer"})
            if not permitted(user["role"], request.method, request.url.path):
                return JSONResponse({"detail": "Role does not permit this operation"}, status_code=403)
            allowed, retry = limiter.is_allowed(user["username"])
            if not allowed:
                return JSONResponse({"detail": "Request limit exceeded"}, status_code=429,
                                    headers={"Retry-After": str(retry)})
        token = principal.set(user)
        try:
            response = await call_next(request)
        finally:
            principal.reset(token)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response
