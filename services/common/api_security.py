"""Shared API-key boundary for local AI-SOC services and their internal clients."""
import hmac
import os

import httpx
from starlette.responses import JSONResponse


def service_headers():
    key = os.getenv("AI_SOC_API_KEY", "")
    return {"Authorization": f"Bearer {key}"} if key else {}


def service_client(**kwargs):
    # Use only for AI-SOC services and the local Ollama backend, never vendor APIs.
    headers = {**service_headers(), **kwargs.pop("headers", {})}
    return httpx.AsyncClient(headers=headers, **kwargs)


def protect_app(app):
    @app.middleware("http")
    async def api_boundary(request, call_next):
        key = os.getenv("AI_SOC_API_KEY", "")
        if key and request.url.path not in {"/health", "/metrics"}:
            authorization = request.headers.get("authorization", "")
            if not hmac.compare_digest(authorization, f"Bearer {key}"):
                return JSONResponse({"detail": "API credentials required"}, status_code=401,
                                    headers={"WWW-Authenticate": "Bearer"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
