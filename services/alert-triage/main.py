"""
Alert Triage Service - FastAPI Application
AI-Augmented SOC

Main application entrypoint for LLM-powered security alert triage.
Receives alerts from Shuffle/Wazuh and returns structured analysis.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from config import settings
from models import SecurityAlert, TriageResponse, HealthResponse
from llm_client import OllamaClient

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'triage_requests_total',
    'Total alert triage requests',
    ['status']
)
REQUEST_DURATION = Histogram(
    'triage_request_duration_seconds',
    'Alert triage request duration'
)
ANALYSIS_CONFIDENCE = Histogram(
    'triage_confidence_score',
    'LLM confidence scores'
)

# Global LLM client
llm_client: OllamaClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown logic.

    Initializes Ollama client and validates connectivity.
    """
    global llm_client

    logger.info(f"Starting {settings.service_name} v{settings.service_version}")
    logger.info(f"Ollama host: {settings.ollama_host}")
    logger.info(f"Primary model: {settings.primary_model}")

    # Initialize LLM client
    llm_client = OllamaClient()

    # Check Ollama connectivity
    if not await llm_client.check_health():
        logger.warning("Ollama service not reachable at startup")
    else:
        logger.info("Ollama service connected successfully")

    yield

    # Shutdown
    logger.info("Shutting down Alert Triage Service")


# FastAPI app
app = FastAPI(
    title="Alert Triage Service",
    description="LLM-powered security alert analysis for SOC automation",
    version=settings.service_version,
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns service status, Ollama connectivity, and ML API status.
    """
    ollama_connected = await llm_client.check_health()
    ml_connected = await llm_client.ml_client.check_health() if settings.ml_enabled else False

    status = "healthy"
    if not ollama_connected:
        status = "degraded"
    elif settings.ml_enabled and not ml_connected:
        status = "partial"  # LLM works but ML is down

    return HealthResponse(
        status=status,
        service=settings.service_name,
        version=settings.service_version,
        ollama_connected=ollama_connected,
        ml_api_connected=ml_connected
    )


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Exposes service metrics for monitoring.
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/analyze", response_model=TriageResponse)
async def analyze_alert(alert: SecurityAlert):
    """
    Analyze security alert using LLM.

    **Workflow:**
    1. Receive alert from Shuffle webhook
    2. Query Ollama (Foundation-Sec-8B or fallback)
    3. Parse structured response
    4. Return severity, IOCs, and recommendations

    **Args:**
        alert: SecurityAlert object from Wazuh

    **Returns:**
        TriageResponse: Structured analysis result

    **Raises:**
        HTTPException: If analysis fails
    """
    start_time = time.time()

    try:
        logger.info(f"Received alert: {alert.alert_id}")

        # Perform LLM analysis
        result = await llm_client.analyze_alert(alert)

        if result is None:
            REQUEST_COUNT.labels(status="failed").inc()
            raise HTTPException(
                status_code=503,
                detail="LLM analysis failed - all models unavailable"
            )

        # Record metrics
        duration = time.time() - start_time
        result.processing_time_ms = int(duration * 1000)

        REQUEST_COUNT.labels(status="success").inc()
        REQUEST_DURATION.observe(duration)
        ANALYSIS_CONFIDENCE.observe(result.confidence)

        logger.info(
            f"Alert {alert.alert_id} analyzed: "
            f"severity={result.severity}, confidence={result.confidence:.2f}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        REQUEST_COUNT.labels(status="error").inc()
        logger.error(f"Unexpected error analyzing alert {alert.alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch", response_model=Dict[str, Any])
async def batch_analyze(alerts: list[SecurityAlert]):
    """
    Batch analyze multiple alerts.

    TODO: Week 4 - Implement concurrent processing with asyncio.gather()

    **Args:**
        alerts: List of SecurityAlert objects

    **Returns:**
        Dict with results and statistics
    """
    # TODO: Implement batch processing
    # This is critical for processing high-volume alert queues
    raise HTTPException(
        status_code=501,
        detail="Batch analysis not yet implemented - coming in Week 4"
    )


@app.get("/")
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "operational",
        "endpoints": {
            "analyze": "/analyze",
            "batch": "/batch",
            "health": "/health",
            "metrics": "/metrics",
            "docs": "/docs"
        },
        "models": {
            "primary": settings.primary_model,
            "fallback": settings.fallback_model
        }
    }


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": str(request.url)
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Development only
        log_level=settings.log_level.lower()
    )
