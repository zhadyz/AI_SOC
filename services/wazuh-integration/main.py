"""
Main Application - Wazuh Integration Service
AI-Augmented SOC

FastAPI webhook receiver for Wazuh alerts with AI-powered triage and enrichment.
"""

import structlog
import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime

from services.wazuh_integration.config import get_settings
from services.wazuh_integration.models import WazuhAlert, EnrichedAlert
from services.wazuh_integration.wazuh_client import WazuhClient
from services.wazuh_integration.ai_client import AIClient

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize clients on startup"""
    settings = get_settings()

    # Initialize clients
    app.state.wazuh_client = WazuhClient(settings)
    app.state.ai_client = AIClient(settings)
    app.state.settings = settings

    logger.info(
        "service_startup",
        service=settings.service_name,
        version=settings.service_version,
        min_severity=settings.min_severity,
        rag_threshold=settings.rag_severity_threshold
    )

    yield

    logger.info("service_shutdown")


# FastAPI application
app = FastAPI(
    title="Wazuh Integration Service",
    description="AI-powered webhook receiver for Wazuh alerts with intelligent triage and enrichment",
    version="1.0.0",
    lifespan=lifespan
)


from services.common.api_security import protect_app
protect_app(app)


@app.post("/webhook/async", status_code=202)
async def queue_wazuh_alert(alert: WazuhAlert):
    """Receive a Wazuh event with durable admission before HTTP 202.

    Poll the returned job_id through the triage service. This path includes
    triage's RAG enrichment, storage and correlation without holding a sender
    connection open for local model inference.
    """
    if alert.rule.level < app.state.settings.min_severity:
        raise HTTPException(400, "Alert severity below minimum threshold")
    try:
        return await app.state.ai_client.queue_alert(alert)
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        raise HTTPException(code if code in {422, 429} else 503, "Triage did not accept the alert") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Durable admission was not confirmed; retry with the same alert ID") from exc


@app.post(
    "/webhook",
    response_model=EnrichedAlert,
    status_code=status.HTTP_200_OK,
    summary="Receive and analyze Wazuh alert",
    description="""
    Primary webhook endpoint for Wazuh alert integration.

    Workflow:
    1. Receive Wazuh alert JSON
    2. Transform to Alert Triage format
    3. Call AI Triage service for analysis
    4. If severity >= 8, call RAG service for MITRE enrichment
    5. Return enriched analysis

    Configuration:
    - Minimum severity filter: >= 7 (configurable via MIN_SEVERITY)
    - RAG enrichment threshold: >= 8 (configurable via RAG_SEVERITY_THRESHOLD)
    """
)
async def receive_wazuh_alert(alert: WazuhAlert):
    """
    Main webhook endpoint: Receive Wazuh alert, analyze with AI, enrich if high severity.

    Args:
        alert: Wazuh alert JSON payload

    Returns:
        EnrichedAlert with AI triage analysis and optional RAG enrichment
    """
    logger.info(
        "webhook_alert_received",
        alert_id=alert.id,
        rule_level=alert.rule.level,
        rule_description=alert.rule.description
    )

    # Filter by minimum severity
    if alert.rule.level < app.state.settings.min_severity:
        logger.info(
            "alert_filtered_low_severity",
            alert_id=alert.id,
            rule_level=alert.rule.level,
            min_severity=app.state.settings.min_severity
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Alert severity {alert.rule.level} below minimum threshold {app.state.settings.min_severity}"
        )

    try:
        # Step 1: AI Triage Analysis
        ai_client: AIClient = app.state.ai_client
        triage_result = await ai_client.analyze_alert(alert)

        # Step 2: Conditional RAG Enrichment
        rag_result = None
        rag_enrichment_applied = False

        if alert.rule.level >= app.state.settings.rag_severity_threshold:
            logger.info(
                "triggering_rag_enrichment",
                alert_id=alert.id,
                rule_level=alert.rule.level
            )

            # Extract MITRE techniques
            mitre_techniques = None
            if alert.rule.mitre:
                mitre_techniques = alert.rule.mitre.get("id")

            rag_result = await ai_client.enrich_with_rag(
                alert_id=alert.id,
                rule_description=alert.rule.description,
                mitre_techniques=mitre_techniques
            )

            if rag_result:
                rag_enrichment_applied = True

        # Step 3: Build enriched response
        enriched_alert = EnrichedAlert(
            wazuh_alert_id=alert.id,
            wazuh_rule_level=alert.rule.level,
            wazuh_rule_description=alert.rule.description,
            ai_severity=triage_result["severity"],
            ai_category=triage_result["category"],
            ai_confidence=triage_result["confidence"],
            ai_summary=triage_result["summary"],
            ai_is_true_positive=triage_result["is_true_positive"],
            ai_recommendations=triage_result["recommendations"],
            investigation_priority=triage_result["investigation_priority"],
            rag_enrichment_applied=rag_enrichment_applied,
            processing_timestamp=datetime.utcnow()
        )

        # Add RAG enrichment if available
        if rag_result and rag_result.get("results"):
            results = rag_result.get("results", [])
            # Extract MITRE context from top results
            context_parts = []
            kb_refs = []
            for r in results[:3]:  # Top 3 results
                if r.get("document"):
                    context_parts.append(r["document"][:500])  # Truncate long docs
                if r.get("metadata", {}).get("technique_id"):
                    kb_refs.append(r["metadata"]["technique_id"])
            enriched_alert.mitre_context = "\n---\n".join(context_parts) if context_parts else None
            enriched_alert.kb_references = kb_refs if kb_refs else None

        # Step 4: Correlate into incident
        try:
            correlation = await ai_client.correlate_alert(enriched_alert)
            if correlation:
                enriched_alert.incident_id = correlation.get("incident_id")
                enriched_alert.incident_is_new = correlation.get("is_new_incident")
                enriched_alert.incident_alert_count = correlation.get("incident_alert_count")
                enriched_alert.kill_chain_stage = correlation.get("kill_chain_stage")
        except Exception as e:
            logger.warning("correlation_failed", error=str(e))

        logger.info(
            "alert_processing_complete",
            alert_id=alert.id,
            ai_severity=enriched_alert.ai_severity,
            is_true_positive=enriched_alert.ai_is_true_positive,
            rag_enriched=rag_enrichment_applied
        )

        return enriched_alert

    except Exception as e:
        logger.error(
            "alert_processing_failed",
            alert_id=alert.id,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Alert processing failed: {str(e)}"
        )


@app.get(
    "/alerts",
    summary="Fetch recent alerts from Wazuh Manager",
    description="Query Wazuh Manager API for high-severity alerts and return enriched analysis"
)
async def fetch_and_analyze_alerts(
    limit: int = 10,
    min_level: int = None,
    time_range: str = "1h"
):
    """
    Fetch alerts from Wazuh Manager and analyze them.

    Args:
        limit: Maximum number of alerts to fetch (default: 10)
        min_level: Minimum rule level filter (default: from config)
        time_range: Time range for alerts (e.g., "1h", "24h", "7d")

    Returns:
        List of enriched alerts with AI analysis
    """
    try:
        wazuh_client: WazuhClient = app.state.wazuh_client
        ai_client: AIClient = app.state.ai_client

        # Fetch alerts from Wazuh
        raw_alerts = await wazuh_client.get_alerts(
            min_level=min_level,
            limit=limit,
            time_range=time_range
        )

        enriched_alerts = []

        for raw_alert in raw_alerts:
            # Parse into WazuhAlert model
            try:
                wazuh_alert = WazuhAlert(**raw_alert)

                # Analyze with AI
                triage_result = await ai_client.analyze_alert(wazuh_alert)

                # Conditional RAG enrichment
                rag_enrichment_applied = False
                rag_result = None

                if wazuh_alert.rule.level >= app.state.settings.rag_severity_threshold:
                    mitre_techniques = None
                    if wazuh_alert.rule.mitre:
                        mitre_techniques = wazuh_alert.rule.mitre.get("id")

                    rag_result = await ai_client.enrich_with_rag(
                        alert_id=wazuh_alert.id,
                        rule_description=wazuh_alert.rule.description,
                        mitre_techniques=mitre_techniques
                    )
                    if rag_result:
                        rag_enrichment_applied = True

                # Build enriched response
                enriched_alert = {
                    "wazuh_alert_id": wazuh_alert.id,
                    "wazuh_rule_level": wazuh_alert.rule.level,
                    "wazuh_rule_description": wazuh_alert.rule.description,
                    "ai_analysis": triage_result,
                    "rag_enrichment": rag_result if rag_enrichment_applied else None,
                    "processing_timestamp": datetime.utcnow().isoformat()
                }

                enriched_alerts.append(enriched_alert)

            except Exception as e:
                logger.error(
                    "alert_parsing_failed",
                    alert=raw_alert,
                    error=str(e)
                )
                continue

        return {
            "total_fetched": len(raw_alerts),
            "total_analyzed": len(enriched_alerts),
            "time_range": time_range,
            "alerts": enriched_alerts
        }

    except Exception as e:
        logger.error("fetch_alerts_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch alerts: {str(e)}"
        )


@app.get(
    "/health",
    summary="Service health check",
    description="Check health of Wazuh Integration service and dependencies"
)
async def health_check():
    """
    Health check endpoint with dependency status.

    Returns:
        Service health status and dependency connectivity
    """
    settings = get_settings()
    wazuh_client: WazuhClient = app.state.wazuh_client
    ai_client: AIClient = app.state.ai_client

    # Check dependencies
    wazuh_healthy = await wazuh_client.health_check()
    triage_healthy = await ai_client.health_check_triage()
    rag_healthy = await ai_client.health_check_rag()

    overall_status = "healthy" if (wazuh_healthy and triage_healthy) else "degraded"

    return {
        "status": overall_status,
        "service": settings.service_name,
        "version": settings.service_version,
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {
            "wazuh_manager": wazuh_healthy,
            "alert_triage": triage_healthy,
            "rag_service": rag_healthy  # Optional dependency
        },
        "configuration": {
            "min_severity": settings.min_severity,
            "rag_threshold": settings.rag_severity_threshold
        }
    }


@app.get("/", summary="Service information")
async def root():
    """Root endpoint with service information"""
    settings = get_settings()
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "description": "Wazuh-AI Integration: Intelligent alert triage and enrichment",
        "endpoints": {
            "webhook": "/webhook (POST)",
            "alerts": "/alerts (GET)",
            "health": "/health (GET)",
            "docs": "/docs (GET)"
        }
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=True  # Enable for development
    )
