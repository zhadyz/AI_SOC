"""
Response Orchestrator - FastAPI Application
AI-Augmented SOC

Autonomous Adaptive Defense: the closed loop that detects an incident,
simulates what the attacker will do next, generates a defense plan,
executes it, and verifies it worked.

This is the service that gives the AI-SOC "hands" — translating
intelligence into action.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from services.response_orchestrator.config import get_settings
from services.response_orchestrator.database import create_db_pool, close_db_pool, check_db_health
from services.response_orchestrator.models import (
    DefensePlan, PlanSummary, PlannedAction, PlanStatus,
    HealthResponse, TriggerPlanRequest, ApproveActionRequest,
    VerificationResult,
)
from services.response_orchestrator.orchestrator import ResponseOrchestrator
from services.response_orchestrator.store import PlanStore
from pydantic import BaseModel, Field

import httpx

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus Metrics
# ---------------------------------------------------------------------------

PLANS_TRIGGERED = Counter(
    "defense_plans_triggered_total",
    "Total defense plans triggered",
    ["status"],
)
PLANS_COMPLETED = Counter(
    "defense_plans_completed_total",
    "Total defense plans completed",
    ["verification_result"],
)
ACTIONS_EXECUTED = Counter(
    "defense_actions_executed_total",
    "Total defense actions executed",
    ["action_type", "adapter", "result"],
)
PLAN_DURATION = Histogram(
    "defense_plan_duration_seconds",
    "Time from plan trigger to completion",
)
APPROVAL_LATENCY = Histogram(
    "defense_approval_latency_seconds",
    "Time actions spend waiting for human approval",
)

# ---------------------------------------------------------------------------
# Orchestrator instance
# ---------------------------------------------------------------------------

orchestrator: Optional[ResponseOrchestrator] = None

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise database and orchestrator on startup."""
    global orchestrator

    logger.info(
        "Starting %s v%s", settings.service_name, settings.service_version
    )

    await create_db_pool(settings.database_url)
    store = PlanStore(settings.database_url)
    await store.initialize()
    orchestrator = ResponseOrchestrator(settings, store=store)
    await orchestrator.restore()

    logger.info(
        "Response Orchestrator ready — dry_run=%s, auto_execute_min=%.2f",
        settings.dry_run_mode,
        settings.auto_execute_confidence_min,
    )

    yield

    await orchestrator.close()
    await store.close()
    await close_db_pool()
    logger.info("Response Orchestrator shut down")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI-SOC Response Orchestrator",
    description=(
        "Autonomous Adaptive Defense — the closed loop that detects threats, "
        "simulates attacker behavior, generates defense plans, executes them "
        "via real infrastructure adapters, and verifies effectiveness through "
        "re-simulation. D3FEND-mapped, simulation-driven, human-in-the-loop."
    ),
    version=settings.service_version,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health & Info
# ---------------------------------------------------------------------------

from services.common.api_security import protect_app
protect_app(app)

@app.get("/", tags=["Info"])
async def root():
    """Service information."""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "description": "Autonomous Adaptive Defense — simulation-driven response orchestration",
        "capabilities": [
            "Incident-triggered defense planning",
            "D3FEND countermeasure mapping",
            "Simulation-informed action ranking",
            "Graduated autonomy with human-in-the-loop",
            "Wazuh Active Response execution",
            "Post-action verification via re-simulation",
            "Automatic rollback on verification failure",
        ],
        "status": "operational",
        "dry_run_mode": settings.dry_run_mode,
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Comprehensive service health check."""
    db_ok = await check_db_health()

    if not db_ok:
        raise HTTPException(503, "Database unavailable")

    # Check upstream services
    correlation_ok = False
    ollama_ok = False
    wazuh_ok = False

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"{settings.correlation_engine_url}/health", timeout=5.0
            )
            correlation_ok = r.status_code == 200
        except Exception:
            pass

        try:
            r = await client.get(
                f"{settings.ollama_host}/api/tags", timeout=5.0
            )
            ollama_ok = r.status_code == 200
        except Exception:
            pass

        try:
            r = await client.get(
                f"{settings.wazuh_api_url}/", timeout=5.0,
            )
            wazuh_ok = r.status_code in (200, 401)  # 401 means reachable
        except Exception:
            pass

    active_plans = 0
    if orchestrator:
        active_plans = len([
            p for p in orchestrator.get_all_plans()
            if p.status not in (PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.ROLLED_BACK, PlanStatus.DRY_RUN, PlanStatus.CANCELLED)
        ])

    overall = "healthy" if db_ok else "degraded"

    return HealthResponse(
        status=overall,
        service=settings.service_name,
        version=settings.service_version,
        db_connected=db_ok,
        correlation_engine_reachable=correlation_ok,
        ollama_reachable=ollama_ok,
        wazuh_reachable=wazuh_ok,
        active_plans=active_plans,
        dry_run_mode=settings.dry_run_mode,
    )


# ---------------------------------------------------------------------------
# Defense Plan Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/defend",
    response_model=DefensePlan,
    tags=["Defense"],
    summary="Trigger autonomous defense for an incident",
    status_code=status.HTTP_201_CREATED,
)
async def trigger_defense(request: TriggerPlanRequest):
    """
    Trigger the full autonomous defense loop for an incident.

    The system will:
    1. Fetch incident context from the correlation engine
    2. Run a simulation to predict attacker next moves
    3. Query D3FEND for candidate countermeasures
    4. Score and rank actions using simulation results
    5. Auto-execute safe actions (tier 2+)
    6. Queue remaining actions for human approval
    7. Start verification via re-simulation and monitoring

    Set `dry_run=true` to generate a plan without executing any actions.
    Set `skip_simulation=true` to plan from incident data only (faster).
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        plan = await orchestrator.trigger_defense(
            incident_id=request.incident_id,
            environment_json=request.environment_json,
            auto_execute=request.auto_execute,
            dry_run=request.dry_run,
            skip_simulation=request.skip_simulation,
        )
        PLANS_TRIGGERED.labels(status="success").inc()
        return plan

    except ValueError as e:
        PLANS_TRIGGERED.labels(status="not_found").inc()
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        PLANS_TRIGGERED.labels(status="rate_limited").inc()
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        PLANS_TRIGGERED.labels(status="error").inc()
        logger.error(f"Defense trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/plans",
    response_model=List[PlanSummary],
    tags=["Defense"],
    summary="List all defense plans",
)
async def list_plans(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
):
    """List defense plans with optional status filter."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    plans = orchestrator.get_all_plans(status=status_filter, limit=limit)
    return [
        PlanSummary(
            plan_id=p.plan_id,
            incident_id=p.incident_id,
            status=p.status,
            total_actions=p.total_actions,
            auto_executed_count=p.auto_executed_count,
            pending_approval_count=sum(
                1 for a in p.actions
                if a.requires_approval and a.status.value == "pending"
            ),
            pre_defense_risk=p.pre_defense_risk,
            post_defense_risk=p.post_defense_risk,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in plans
    ]


@app.get(
    "/plans/{plan_id}",
    response_model=DefensePlan,
    tags=["Defense"],
    summary="Get full defense plan details",
)
async def get_plan(plan_id: str):
    """Get complete defense plan including all actions and verification results."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    plan = orchestrator.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return plan


# ---------------------------------------------------------------------------
# Approval Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/approvals",
    tags=["Approval"],
    summary="List all pending approval requests",
)
async def list_pending_approvals():
    """
    Get all defense actions across all plans that require human approval.

    Returns action details, rationale, impact scores, and which
    ATT&CK techniques the action counters.
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    return orchestrator.get_pending_approvals()


@app.post(
    "/plans/{plan_id}/actions/{action_id}/approve",
    response_model=PlannedAction,
    tags=["Approval"],
    summary="Approve or reject a pending defense action",
)
async def approve_action(
    plan_id: str,
    action_id: str,
    request: ApproveActionRequest,
):
    """
    Approve or reject a defense action that requires human authorization.

    If approved, the action is immediately executed via its adapter.
    If rejected, the action is marked as vetoed and skipped.
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        action = await orchestrator.approve_action(
            plan_id=plan_id,
            action_id=action_id,
            approved=request.approved,
            analyst_id=request.analyst_id,
            notes=request.notes,
        )
        return action

    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


class PlanDecision(BaseModel):
    analyst_id: str = Field(min_length=1, max_length=255)
    notes: Optional[str] = Field(None, max_length=2000)


class VerificationRequest(PlanDecision):
    environment_json: dict


@app.get("/plans/{plan_id}/events", tags=["Defense"])
async def plan_events(plan_id: str):
    if not orchestrator or not orchestrator.get_plan(plan_id):
        raise HTTPException(404, "Plan not found")
    return await orchestrator.store.events(plan_id)


@app.post("/plans/{plan_id}/cancel", response_model=DefensePlan, tags=["Defense"])
async def cancel_plan(plan_id: str, request: PlanDecision):
    if not orchestrator:
        raise HTTPException(503, "Orchestrator not initialized")
    try:
        return await orchestrator.cancel_plan(plan_id, request.analyst_id, request.notes)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.post("/plans/{plan_id}/verify", response_model=DefensePlan, tags=["Defense"])
async def verify_plan(plan_id: str, request: VerificationRequest):
    if not orchestrator:
        raise HTTPException(503, "Orchestrator not initialized")
    try:
        return await orchestrator.request_verification(plan_id, request.environment_json, request.analyst_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


# ---------------------------------------------------------------------------
# D3FEND Reference Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/d3fend/lookup/{technique_id}",
    tags=["D3FEND"],
    summary="Look up D3FEND countermeasures for an ATT&CK technique",
)
async def d3fend_lookup(technique_id: str):
    """
    Given a MITRE ATT&CK technique ID, return the D3FEND countermeasures
    and their mapped concrete defense actions.
    """
    from services.response_orchestrator.d3fend import get_countermeasures
    countermeasures = get_countermeasures(technique_id)

    if not countermeasures:
        return {
            "technique_id": technique_id,
            "countermeasures": [],
            "note": "No D3FEND mapping found for this technique",
        }

    return {
        "technique_id": technique_id,
        "countermeasures": [
            {
                "d3fend_id": c.technique_id,
                "label": c.label,
                "tactic": c.tactic,
                "description": c.description,
                "action_type": c.action_type.value,
                "adapter": c.adapter.value,
                "blast_radius": c.blast_radius.value,
                "default_safety": c.default_safety,
            }
            for c in countermeasures
        ],
    }


@app.get(
    "/d3fend/techniques",
    tags=["D3FEND"],
    summary="List all supported ATT&CK techniques with D3FEND mappings",
)
async def d3fend_supported_techniques():
    """Return all ATT&CK technique IDs that have D3FEND countermeasure mappings."""
    from services.response_orchestrator.d3fend import get_supported_attack_techniques
    techniques = get_supported_attack_techniques()
    return {"total": len(techniques), "techniques": techniques}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@app.get("/metrics", tags=["Monitoring"])
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        workers=2,
    )
