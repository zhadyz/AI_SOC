"""
Alert Triage Service - FastAPI Application
AI-Augmented SOC

Main application entrypoint for LLM-powered security alert triage.
Receives alerts from Shuffle/Wazuh and returns structured analysis.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

import httpx
from services.common.api_security import service_client
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from services.alert_triage.config import settings
from services.alert_triage.models import SecurityAlert, TriageResponse, HealthResponse
from services.alert_triage.llm_client import OllamaClient
from services.alert_triage.worker_pool import WorkerPool

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

# Global LLM client and worker pool
llm_client: OllamaClient = None
worker_pool: WorkerPool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown logic.

    Initializes Ollama client and validates connectivity.
    """
    global llm_client, worker_pool

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

    # Initialize async worker pool
    async def _analyze_from_dict(alert_data: dict):
        alert = SecurityAlert(**alert_data)
        return await analyze_alert(alert)

    worker_pool = WorkerPool(
        analyze_fn=_analyze_from_dict,
        worker_count=settings.worker_count,
        queue_threshold=settings.queue_threshold,
        circuit_breaker_enabled=settings.circuit_breaker_enabled,
        store_path=settings.job_store_path,
        queue_capacity=settings.queue_capacity,
    )
    await worker_pool.start()
    app.state.worker_pool = worker_pool
    logger.info(f"Worker pool started: {settings.worker_count} workers")

    yield

    # Shutdown
    logger.info("Shutting down Alert Triage Service")
    await worker_pool.stop()


# FastAPI app
app = FastAPI(
    title="Alert Triage Service",
    description="LLM-powered security alert analysis for SOC automation",
    version=settings.service_version,
    lifespan=lifespan
)


from services.common.api_security import protect_app
protect_app(app)

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

        # Persist alert + result to feedback service (fire-and-forget)
        if settings.feedback_enabled:
            await _persist_alert(alert, result)
        if settings.correlation_enabled:
            await _correlate_alert(alert, result)

        return result

    except HTTPException:
        raise
    except Exception as e:
        REQUEST_COUNT.labels(status="error").inc()
        logger.error(f"Unexpected error analyzing alert {alert.alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _persist_alert(alert: SecurityAlert, result: TriageResponse):
    """Fire-and-forget: persist alert + triage result to feedback service."""
    try:
        payload = {
            "alert_id": alert.alert_id,
            "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
            "source_ip": alert.source_ip,
            "dest_ip": alert.dest_ip,
            "rule_id": alert.rule_id,
            "rule_description": alert.rule_description,
            "rule_level": alert.rule_level,
            "raw_alert": alert.model_dump(mode="json"),
            "triage_result": result.model_dump(mode="json"),
            "ai_severity": result.severity.value if hasattr(result.severity, 'value') else str(result.severity),
            "ai_category": result.category.value if hasattr(result.category, 'value') else str(result.category),
            "ai_confidence": result.confidence,
            "ai_is_true_positive": result.is_true_positive,
            "ml_prediction": result.ml_prediction,
            "ml_confidence": result.ml_confidence,
        }
        async with service_client(timeout=10.0) as client:
            response = await client.post(f"{settings.feedback_service_url}/alerts", json=payload)
            response.raise_for_status()
        logger.debug(f"Alert {alert.alert_id} persisted to feedback service")
    except Exception as e:
        logger.warning(f"Failed to persist alert {alert.alert_id}: {e}")
        raise HTTPException(503, "Analysis completed but storage failed; retry using the same alert_id")


async def _correlate_alert(alert, result):
    payload = {
        "alert_id": alert.alert_id, "source_ip": alert.source_ip, "dest_ip": alert.dest_ip,
        "timestamp": alert.timestamp.isoformat(), "severity": result.severity.value,
        "category": result.category.value, "mitre_techniques": result.mitre_techniques,
        "mitre_tactics": result.mitre_tactics, "rule_description": alert.rule_description,
    }
    try:
        async with service_client(timeout=15) as client:
            response = await client.post(f"{settings.correlation_engine_url}/correlate", json=payload)
            response.raise_for_status()
            result.incident_id = response.json()["incident_id"]
    except (httpx.HTTPError, KeyError):
        logger.exception("Correlation unavailable for stored alert %s", alert.alert_id)
        result.pipeline_warnings.append("Alert stored; correlation unavailable. Retry with the same alert_id.")


@app.post("/batch", response_model=Dict[str, Any])
async def batch_analyze(alerts: list[SecurityAlert]):
    """
    Batch analyze multiple alerts concurrently.

    Uses asyncio.gather() for parallel processing with error handling.

    **Args:**
        alerts: List of SecurityAlert objects

    **Returns:**
        Dict with results and statistics
    """
    import asyncio

    if not alerts:
        return {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "results": [],
            "errors": []
        }

    start_time = time.time()
    logger.info(f"Starting batch analysis of {len(alerts)} alerts")

    # Process alerts concurrently
    tasks = [analyze_alert(alert) for alert in alerts]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Categorize results
    successful = []
    failed = []
    errors = []

    for idx, result in enumerate(results):
        alert_id = alerts[idx].alert_id

        if isinstance(result, Exception):
            failed.append(alert_id)
            errors.append({
                "alert_id": alert_id,
                "error": str(result)
            })
            logger.error(f"Batch analysis failed for {alert_id}: {result}")
        elif result is None:
            failed.append(alert_id)
            errors.append({
                "alert_id": alert_id,
                "error": "LLM analysis returned None"
            })
        else:
            successful.append(result.dict())

    duration = time.time() - start_time

    logger.info(
        f"Batch analysis complete: {len(successful)}/{len(alerts)} successful "
        f"in {duration:.2f}s"
    )

    return {
        "total": len(alerts),
        "successful": len(successful),
        "failed": len(failed),
        "processing_time_seconds": round(duration, 2),
        "results": successful,
        "errors": errors
    }


@app.post("/analyze/async", status_code=202)
async def analyze_async(alert: SecurityAlert, callback_url: str = None):
    """
    Submit alert for async triage. Returns job_id immediately.

    High-severity alerts are processed first. Accepted jobs persist before
    acknowledgment and unfinished jobs resume after a process restart.

    Poll GET /jobs/{job_id} for results.
    """
    if callback_url:
        raise HTTPException(422, "Callbacks are disabled; poll /jobs/{job_id} for results")
    pool = app.state.worker_pool
    try:
        job_id = pool.submit(alert.model_dump(mode="json"), callback_url=callback_url)
    except asyncio.QueueFull:
        raise HTTPException(429, "Triage queue is full; retry later")
    except Exception:
        logger.exception("Failed to persist accepted triage job")
        raise HTTPException(503, "Job could not be persisted; it was not accepted")
    return {
        "job_id": job_id,
        "status": "queued",
        "queue_depth": pool.queue_depth,
        "message": f"Alert {alert.alert_id} queued for async analysis",
    }


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """
    Get the status and result of an async triage job.

    Returns job status (queued/processing/completed/failed) and
    result when complete.
    """
    pool = app.state.worker_pool
    result = pool.get_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {
        "job_id": result.job_id,
        "status": result.status,
        "alert_id": result.alert_id,
        "result": result.result,
        "error": result.error,
        "created_at": result.created_at,
        "completed_at": result.completed_at,
        "processing_time_ms": result.processing_time_ms,
        "circuit_breaker_applied": result.circuit_breaker_applied,
    }


@app.get("/workers/stats")
async def worker_stats():
    """Get worker pool statistics."""
    pool = app.state.worker_pool
    return pool.stats


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
            "analyze_async": "/analyze/async",
            "jobs": "/jobs/{job_id}",
            "batch": "/batch",
            "workers": "/workers/stats",
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
