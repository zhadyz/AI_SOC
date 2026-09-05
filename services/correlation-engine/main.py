"""
Alert Correlation Engine - FastAPI Application
AI-Augmented SOC

Groups related security alerts into incidents based on IP affinity,
temporal proximity, and MITRE ATT&CK kill chain progression.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

from typing import Dict, Optional
from fastapi import FastAPI, HTTPException, Query, Depends, Request, status
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from services.correlation_engine.config import get_settings
from services.correlation_engine.database import (
    create_db_pool,
    close_db_pool,
    check_db_health,
    get_db,
    IncidentModel,
    IncidentAlertModel,
)
from services.correlation_engine.models import (
    CorrelationRequest,
    CorrelationResponse,
    Incident,
    IncidentSummary,
    IncidentAlert,
    StatusUpdate,
    HealthResponse,
)
from services.correlation_engine.correlator import CorrelationEngine
from services.correlation_engine.predictor import AttackPredictor
from services.correlation_engine.simulator import CampaignSimulator, SimulationConfig
from services.correlation_engine.environment import Environment
from services.correlation_engine.dataset_generator import DatasetGenerator
from services.correlation_engine.wazuh_environment import WazuhEnvironmentBuilder
from services.correlation_engine.risk_scorer import RiskScorer
from collections import OrderedDict
import httpx
from services.common.api_security import service_client
from pydantic import BaseModel
from services.correlation_engine.archetypes import ARCHETYPE_PROMPTS
from services.correlation_engine.defender_archetypes import DEFENDER_ARCHETYPE_PROMPTS
from services.correlation_engine.swarm import SwarmSimulator, SwarmConfig
from services.correlation_engine.history_store import HistoryStore
from services.correlation_engine.research_metrics import compute_all_metrics, export_for_paper, prediction_accuracy
import asyncio

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

CORRELATION_REQUESTS = Counter(
    "correlation_requests_total",
    "Total correlation requests processed",
    ["status"],
)
CORRELATION_DURATION = Histogram(
    "correlation_request_duration_seconds",
    "Correlation request processing duration",
)
INCIDENTS_CREATED = Counter(
    "incidents_created_total",
    "Total new incidents opened",
)
INCIDENTS_UPDATED = Counter(
    "incidents_updated_total",
    "Total alerts attached to existing incidents",
)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database connection pool on startup, close on shutdown."""
    logger.info(
        "Starting %s v%s", settings.service_name, settings.service_version
    )

    try:
        await create_db_pool(settings.database_url)
        logger.info("Database pool initialised successfully")

        # Initialize attack predictor
        predictor = AttackPredictor()
        try:
            async for db in get_db():
                await predictor.train(db)
                break
        except Exception as e:
            logger.warning("Predictor training skipped: %s", e)
        app.state.predictor = predictor
        logger.info("Attack predictor initialized: %s", predictor.stats)
    except Exception as exc:
        # Graceful degradation: service starts but reports DB as unavailable
        logger.warning("Database not available at startup: %s", exc)
        app.state.predictor = AttackPredictor()

    # Initialize risk scorer
    app.state.risk_scorer = RiskScorer()
    logger.info("Risk scorer initialized")

    # Initialize simulation store for chat feature
    app.state.simulation_store = OrderedDict()
    logger.info("Simulation store initialized")

    # Initialize swarm store and task tracker
    app.state.swarm_store = OrderedDict()
    app.state.swarm_tasks = {}
    import os
    history_dir = os.environ.get(
        "SWARM_HISTORY_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
    )
    app.state.history_store = HistoryStore(data_dir=history_dir)
    logger.info("Swarm store and history initialized")

    yield

    logger.info("Shutting down %s", settings.service_name)
    await close_db_pool()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Alert Correlation Engine",
    description=(
        "Groups related security alerts into incidents based on IP affinity, "
        "temporal proximity, and MITRE ATT&CK kill chain progression."
    ),
    version=settings.service_version,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEVERITY_TRIGGER_ORDER = {
    "informational": 0, "low": 1, "medium": 2, "high": 3, "critical": 4,
}


async def _trigger_defense(incident_id: str, severity: str, is_new: bool):
    """
    Non-blocking callback to the Response Orchestrator.

    Fires when a new high-severity incident is created OR when an existing
    incident escalates to a qualifying severity level. Failures are logged
    but never block the correlation response.
    """
    if not settings.auto_defend_enabled:
        return

    min_level = SEVERITY_TRIGGER_ORDER.get(settings.auto_defend_min_severity, 3)
    current_level = SEVERITY_TRIGGER_ORDER.get(severity, 0)
    if current_level < min_level:
        return

    trigger_reason = "new_incident" if is_new else "severity_escalation"
    logger.info(
        "Triggering autonomous defense for %s (severity=%s, reason=%s)",
        incident_id, severity, trigger_reason,
    )

    try:
        async with service_client() as client:
            resp = await client.post(
                f"{settings.response_orchestrator_url}/defend",
                json={
                    "incident_id": incident_id,
                    "auto_execute": False,
                    "dry_run": True,
                    "skip_simulation": False,
                },
                timeout=300.0,  # Planning completes before the response is returned
            )
            if resp.status_code == 201:
                plan = resp.json()
                logger.info(
                    "Defense plan triggered: %s (%d actions) for incident %s",
                    plan.get("plan_id", "unknown"),
                    plan.get("total_actions", 0),
                    incident_id,
                )
            elif resp.status_code == 429:
                logger.warning(
                    "Defense trigger rate-limited for %s: %s",
                    incident_id, resp.text,
                )
            else:
                logger.warning(
                    "Defense trigger returned %d for %s: %s",
                    resp.status_code, incident_id, resp.text[:200],
                )
    except httpx.ConnectError:
        logger.debug(
            "Response orchestrator not available — defense trigger skipped for %s",
            incident_id,
        )
    except Exception as exc:
        logger.warning(
            "Defense trigger failed for %s: %s", incident_id, exc,
        )


def _incident_model_to_summary(row: IncidentModel) -> IncidentSummary:
    return IncidentSummary(
        incident_id=row.incident_id,
        status=row.status,
        severity=row.severity or "unknown",
        kill_chain_stage=row.kill_chain_stage or "unknown",
        alert_count=row.alert_count or 0,
        first_seen=row.first_seen or datetime.now(timezone.utc),
        last_seen=row.last_seen or datetime.now(timezone.utc),
        source_ips=row.source_ips or [],
        dest_ips=row.dest_ips or [],
        summary=row.summary or "",
    )


def _incident_model_to_full(
    row: IncidentModel, alert_rows: List[IncidentAlertModel]
) -> Incident:
    alerts = [
        IncidentAlert(
            alert_id=a.alert_id,
            added_at=a.added_at,
            severity=a.severity or "unknown",
            category=a.category or "unknown",
            kill_chain_stage=a.kill_chain_stage,
        )
        for a in alert_rows
    ]
    return Incident(
        incident_id=row.incident_id,
        status=row.status,
        severity=row.severity or "unknown",
        kill_chain_stage=row.kill_chain_stage or "unknown",
        kill_chain_stages_seen=row.kill_chain_stages_seen or [],
        alert_count=row.alert_count or 0,
        first_seen=row.first_seen or datetime.now(timezone.utc),
        last_seen=row.last_seen or datetime.now(timezone.utc),
        source_ips=row.source_ips or [],
        dest_ips=row.dest_ips or [],
        mitre_techniques=row.mitre_techniques or [],
        mitre_tactics=row.mitre_tactics or [],
        alerts=alerts,
        summary=row.summary or "",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


from services.common.api_security import protect_app
protect_app(app)

@app.post(
    "/correlate",
    response_model=CorrelationResponse,
    status_code=status.HTTP_200_OK,
    summary="Correlate an alert into an incident",
    description=(
        "Score the incoming alert against all active incidents. "
        "Attach to the best match if score >= threshold, otherwise open a new incident."
    ),
)
async def correlate_alert(
    request: CorrelationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Receives a correlation request, scores it against active incidents,
    and returns the incident assignment.
    """
    start = time.time()

    try:
        engine = CorrelationEngine(db, settings)
        result = await engine.correlate(request)

        duration = time.time() - start
        CORRELATION_REQUESTS.labels(status="success").inc()
        CORRELATION_DURATION.observe(duration)

        if result.is_new_incident:
            INCIDENTS_CREATED.inc()
            logger.info(
                "New incident created: %s for alert %s",
                result.incident_id,
                request.alert_id,
            )
            # Trigger autonomous defense (non-blocking)
            asyncio.create_task(
                _trigger_defense(
                    result.incident_id, request.severity, is_new=True,
                )
            )
        else:
            INCIDENTS_UPDATED.inc()
            logger.info(
                "Alert %s attached to incident %s (score=%.3f)",
                request.alert_id,
                result.incident_id,
                result.correlation_score,
            )
            # Trigger defense on escalation (severity >= threshold on existing incident)
            asyncio.create_task(
                _trigger_defense(
                    result.incident_id, request.severity, is_new=False,
                )
            )

        return result

    except Exception as exc:
        CORRELATION_REQUESTS.labels(status="error").inc()
        logger.error(
            "Correlation failed for alert %s: %s", request.alert_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Correlation failed: {str(exc)}",
        )


@app.get(
    "/incidents",
    response_model=List[IncidentSummary],
    summary="List incidents",
    description="Paginated list of all incidents, optionally filtered by status.",
)
async def list_incidents(
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by status: open, investigating, closed"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Return a paginated list of incidents, newest first.
    """
    try:
        query = select(IncidentModel).order_by(IncidentModel.last_seen.desc())

        if status_filter:
            valid_statuses = {"open", "investigating", "closed"}
            if status_filter not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status '{status_filter}'. Must be one of: {valid_statuses}",
                )
            query = query.where(IncidentModel.status == status_filter)

        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        rows = result.scalars().all()

        return [_incident_model_to_summary(row) for row in rows]

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to list incidents: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve incidents: {str(exc)}",
        )


@app.get(
    "/incidents/active",
    response_model=List[IncidentSummary],
    summary="List active incidents",
    description="Return all incidents with status 'open' or 'investigating'.",
)
async def list_active_incidents(
    db: AsyncSession = Depends(get_db),
):
    """Return only open and investigating incidents, newest first."""
    try:
        result = await db.execute(
            select(IncidentModel)
            .where(IncidentModel.status.in_(["open", "investigating"]))
            .order_by(IncidentModel.last_seen.desc())
        )
        rows = result.scalars().all()
        return [_incident_model_to_summary(row) for row in rows]

    except Exception as exc:
        logger.error("Failed to list active incidents: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve active incidents: {str(exc)}",
        )


@app.get(
    "/incidents/{incident_id}",
    response_model=Incident,
    summary="Get incident details",
    description="Return full incident including all member alerts and kill chain timeline.",
)
async def get_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Return full incident details with member alerts ordered by time.
    """
    try:
        # Fetch incident row
        result = await db.execute(
            select(IncidentModel).where(
                IncidentModel.incident_id == incident_id
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found",
            )

        # Fetch member alerts
        alerts_result = await db.execute(
            select(IncidentAlertModel)
            .where(IncidentAlertModel.incident_id == incident_id)
            .order_by(IncidentAlertModel.added_at.asc())
        )
        alert_rows = list(alerts_result.scalars().all())

        return _incident_model_to_full(row, alert_rows)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get incident %s: %s", incident_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve incident: {str(exc)}",
        )


@app.put(
    "/incidents/{incident_id}/status",
    response_model=IncidentSummary,
    summary="Update incident status",
    description="Transition incident to open, investigating, or closed.",
)
async def update_incident_status(
    incident_id: str,
    body: StatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update the status of an incident. Automatically sets closed_at when
    the status is changed to 'closed'.
    """
    valid_statuses = {"open", "investigating", "closed"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{body.status}'. Must be one of: {valid_statuses}",
        )

    try:
        # Check existence first
        result = await db.execute(
            select(IncidentModel).where(
                IncidentModel.incident_id == incident_id
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found",
            )

        # Build update payload
        update_values = {"status": body.status}
        if body.status == "closed":
            update_values["closed_at"] = datetime.now(timezone.utc)

        await db.execute(
            update(IncidentModel)
            .where(IncidentModel.incident_id == incident_id)
            .values(**update_values)
        )
        await db.flush()

        # Re-fetch updated row
        result = await db.execute(
            select(IncidentModel).where(
                IncidentModel.incident_id == incident_id
            )
        )
        updated = result.scalar_one()

        logger.info(
            "Incident %s status updated to '%s'", incident_id, body.status
        )
        return _incident_model_to_summary(updated)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to update incident %s status: %s", incident_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update incident status: {str(exc)}",
        )


@app.post("/simulate")
async def run_simulation(
    archetypes: Optional[List[str]] = None,
    timesteps: int = Query(3, ge=1, le=10),
    environment_json: Optional[Dict] = None,
):
    """
    Run an attack campaign simulation against the infrastructure environment.

    Spawns LLM-powered attacker agents with distinct behavioral archetypes
    that attempt to progress through the kill chain. Returns a campaign report
    with environment-specific predictions, defense validation, and recommended
    preemptive actions.

    Default: 4 archetypes (opportunist, apt, ransomware, insider) x 3 timesteps.
    """
    config = SimulationConfig(
        agent_archetypes=archetypes or ["opportunist", "apt", "ransomware", "insider"],
        timesteps=timesteps,
        concurrency=settings.simulator_default_concurrency,
        ollama_host=settings.simulator_ollama_host,
        ollama_model=settings.simulator_ollama_model,
    )

    # Load environment
    try:
        if environment_json:
            env = Environment.from_dict(environment_json)
        elif settings.simulator_environment_config:
            env = Environment.load_from_json(settings.simulator_environment_config)
        else:
            # Try default config path
            default_path = "/app/config/simulation/default-environment.json"
            try:
                env = Environment.load_from_json(default_path)
            except FileNotFoundError:
                raise HTTPException(
                    status_code=400,
                    detail="No environment config provided and default not found. "
                    "Pass environment_json in the request body or set "
                    "CORRELATION_SIMULATOR_ENVIRONMENT_CONFIG."
                )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load environment: {e}")

    simulator = CampaignSimulator(config)

    try:
        report = await simulator.run(env)

        # Store for chat feature (LRU, max 20)
        store = getattr(app.state, "simulation_store", None)
        if store is not None:
            sim_id = report.get("simulation_id", "unknown")
            store[sim_id] = {"report": report, "chat_sessions": {}}
            while len(store) > 20:
                store.popitem(last=False)

        return report
    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Simulation failed: {e}")


# ---------------------------------------------------------------------------
# Chat with Attacker Agent
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    agent_id: str
    message: str


@app.post("/simulate/{simulation_id}/chat")
async def chat_with_attacker(simulation_id: str, body: ChatMessage):
    """
    Chat with an attacker agent from a completed simulation.

    The agent stays in character, references its actual attack path,
    and can explain strategy, reasoning, and what defenses would stop it.
    """
    store = getattr(app.state, "simulation_store", None)
    if not store or simulation_id not in store:
        raise HTTPException(
            status_code=404,
            detail=f"Simulation '{simulation_id}' not found. Run a simulation first.",
        )

    sim_data = store[simulation_id]
    report = sim_data["report"]

    # Find agent campaign (check both attackers and defenders)
    campaign = None
    is_defender = False
    for c in report.get("campaigns", []):
        if c["agent_id"] == body.agent_id:
            campaign = c
            break
    if not campaign:
        for c in report.get("defender_campaigns", []):
            if c["agent_id"] == body.agent_id:
                campaign = c
                is_defender = True
                break

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{body.agent_id}' not found in simulation '{simulation_id}'",
        )

    archetype = campaign["archetype"]

    # Get or create chat session
    chat_sessions = sim_data.setdefault("chat_sessions", {})
    if body.agent_id not in chat_sessions:
        chat_sessions[body.agent_id] = []

    # Build system prompt (different for attackers vs defenders)
    if is_defender:
        system_prompt = _build_defender_chat_prompt(
            archetype, campaign, report.get("environment", {}),
            report.get("campaigns", []),
        )
    else:
        system_prompt = _build_chat_system_prompt(
            archetype, campaign, report.get("environment", {})
        )

    # Build message history
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_sessions[body.agent_id])
    messages.append({"role": "user", "content": body.message})

    # Call Ollama /api/chat
    try:
        async with service_client(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.simulator_ollama_host}/api/chat",
                json={
                    "model": settings.simulator_ollama_model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.6},
                },
            )
            if resp.status_code == 200:
                result = resp.json()
                assistant_msg = result.get("message", {}).get(
                    "content", "I cannot respond right now."
                )
            else:
                logger.error("Ollama chat error: status=%d", resp.status_code)
                raise HTTPException(
                    status_code=502, detail="LLM service returned an error"
                )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM request timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Chat failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to reach LLM: {e}")

    # Store conversation
    chat_sessions[body.agent_id].append({"role": "user", "content": body.message})
    chat_sessions[body.agent_id].append(
        {"role": "assistant", "content": assistant_msg}
    )

    return {
        "response": assistant_msg,
        "agent_id": body.agent_id,
        "archetype": archetype,
    }


def _build_chat_system_prompt(
    archetype: str, campaign: dict, environment: dict
) -> str:
    """Build the system prompt for chatting with an attacker agent."""
    personality = ARCHETYPE_PROMPTS.get(archetype, "You are an attacker agent.")

    # Format attack path
    path_lines = []
    for step in campaign.get("attack_path", []):
        ts = step.get("timestep", 0) + 1
        line = (
            f"  Turn {ts}: {step.get('action', '?')} on "
            f"{step.get('target', '?')} -> {step.get('result', '?')}"
        )
        if step.get("reasoning"):
            line += f"\n    Reasoning: {step['reasoning']}"
        path_lines.append(line)
    path_text = "\n".join(path_lines) if path_lines else "  No actions recorded"

    # Format environment
    env_lines = []
    for ip, h in environment.get("hosts", {}).items():
        hostname = h.get("hostname", ip)
        os_type = h.get("os", "?")
        crit = h.get("criticality", "?")
        services = ", ".join(s.get("name", "?") for s in h.get("services", []))
        defenses = h.get("defenses", {})
        def_list = [k.replace("_", " ") for k, v in defenses.items() if v]
        env_lines.append(
            f"  {ip} ({hostname}) - {os_type} - criticality: {crit}"
            f" - services: {services or 'none'}"
            f" - defenses: {', '.join(def_list) or 'none'}"
        )
    env_text = "\n".join(env_lines) if env_lines else "  No environment data"

    compromised = ", ".join(campaign.get("hosts_compromised", [])) or "None"
    persistence = ", ".join(campaign.get("persistence_established", [])) or "None"

    return (
        f"You are roleplaying as an attacker agent from a completed "
        f"cybersecurity simulation.\n\n"
        f"YOUR PERSONALITY/ARCHETYPE:\n{personality}\n\n"
        f"YOUR CAMPAIGN RESULTS:\n"
        f"  Agent ID: {campaign.get('agent_id', '?')}\n"
        f"  Archetype: {archetype}\n"
        f"  Actions taken: {campaign.get('actions_taken', 0)}\n"
        f"  Successful actions: {campaign.get('successful_actions', 0)}\n"
        f"  Detected actions: {campaign.get('detected_actions', 0)}\n"
        f"  Hosts compromised: {compromised}\n"
        f"  Final kill chain stage: {campaign.get('final_kill_chain_stage', 'none')}\n"
        f"  Data exfiltrated: {campaign.get('data_exfiltrated', False)}\n"
        f"  Persistence established: {persistence}\n\n"
        f"YOUR ATTACK PATH:\n{path_text}\n\n"
        f"THE ENVIRONMENT YOU ATTACKED:\n{env_text}\n\n"
        f"INSTRUCTIONS:\n"
        f"- Stay in character as your archetype at all times\n"
        f"- Reference your ACTUAL actions from the simulation — never invent "
        f"actions you didn't take\n"
        f"- When asked 'why' questions, explain your reasoning based on your "
        f"archetype's goals\n"
        f"- When asked about defenses, give specific recommendations based on "
        f"what would have stopped your actual attack path\n"
        f"- Be conversational but maintain your attacker persona\n"
        f"- You can discuss strategy, your decision-making process, and what "
        f"defenses concerned you\n"
        f"- If asked about actions you didn't take, explain why your archetype "
        f"chose differently"
    )


def _build_defender_chat_prompt(
    archetype: str, campaign: dict, environment: dict,
    attacker_campaigns: list,
) -> str:
    """Build the system prompt for chatting with a defender agent."""
    personality = DEFENDER_ARCHETYPE_PROMPTS.get(
        archetype, "You are a SOC defender agent."
    )

    # Format defense path
    path_lines = []
    for step in campaign.get("defense_path", []):
        ts = step.get("timestep", 0) + 1
        line = (
            f"  Turn {ts}: {step.get('action', '?')} on "
            f"{step.get('target', '?')} -> {step.get('result', '?')}"
        )
        if step.get("reasoning"):
            line += f"\n    Reasoning: {step['reasoning']}"
        path_lines.append(line)
    path_text = "\n".join(path_lines) if path_lines else "  No actions recorded"

    # Summarize attacker outcomes (what the defender was up against)
    attacker_summary_lines = []
    for ac in attacker_campaigns:
        compromised = ", ".join(ac.get("hosts_compromised", [])) or "None"
        attacker_summary_lines.append(
            f"  {ac.get('agent_id', '?')} ({ac.get('archetype', '?')}): "
            f"{ac.get('actions_taken', 0)} actions, "
            f"compromised: {compromised}"
        )
    attacker_text = "\n".join(attacker_summary_lines) or "  No attacker data"

    blocks = campaign.get("successful_blocks", 0)
    investigations = campaign.get("investigations_completed", 0)

    return (
        f"You are roleplaying as a defender agent from a completed "
        f"cybersecurity simulation.\n\n"
        f"YOUR PERSONALITY/ARCHETYPE:\n{personality}\n\n"
        f"YOUR DEFENSE RESULTS:\n"
        f"  Agent ID: {campaign.get('agent_id', '?')}\n"
        f"  Archetype: {archetype}\n"
        f"  Actions taken: {campaign.get('actions_taken', 0)}\n"
        f"  Successful blocks: {blocks}\n"
        f"  Investigations: {investigations}\n"
        f"  Escalations sent: {campaign.get('escalations_sent', 0)}\n\n"
        f"YOUR DEFENSE PATH:\n{path_text}\n\n"
        f"ATTACKER OUTCOMES (what you were defending against):\n{attacker_text}\n\n"
        f"INSTRUCTIONS:\n"
        f"- Stay in character as your defender archetype\n"
        f"- Reference your ACTUAL defensive actions — never invent actions\n"
        f"- When asked 'why' questions, explain your triage/prioritization logic\n"
        f"- Discuss what additional resources or tools would have helped\n"
        f"- Be honest about what you missed and what you caught\n"
        f"- You can recommend improvements to the security posture"
    )


@app.post("/simulate/generate-dataset")
async def generate_dataset(
    runs: int = Query(10, ge=1, le=500, description="Number of simulation runs"),
    timesteps: int = Query(3, ge=1, le=10, description="Timesteps per run"),
    environment_json: Optional[Dict] = None,
):
    """
    Run N simulations with randomized environments and collect all traces into
    a structured dataset.

    Produces a novel dataset of attacker decision-making capturing strategy,
    reasoning, and outcomes across diverse infrastructure configurations.

    Note: This is a long-running endpoint. For large runs (>50) consider running
    dataset_generator.py directly via the CLI.
    """
    # Load base environment
    try:
        if environment_json:
            base_env_dict = environment_json
        elif settings.simulator_environment_config:
            import json as _json
            with open(settings.simulator_environment_config) as fh:
                base_env_dict = _json.load(fh)
        else:
            default_path = "/app/config/simulation/default-environment.json"
            try:
                import json as _json
                with open(default_path) as fh:
                    base_env_dict = _json.load(fh)
            except FileNotFoundError:
                raise HTTPException(
                    status_code=400,
                    detail="No environment config provided and default not found. "
                           "Pass environment_json in the request body or set "
                           "CORRELATION_SIMULATOR_ENVIRONMENT_CONFIG.",
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load environment: {exc}")

    generator = DatasetGenerator(
        ollama_host=settings.simulator_ollama_host,
        ollama_model=settings.simulator_ollama_model,
        concurrency=settings.simulator_default_concurrency,
    )

    try:
        dataset = await generator.generate(
            num_runs=runs,
            base_environment=base_env_dict,
            timesteps=timesteps,
        )
        return dataset
    except Exception as exc:
        logger.error("Dataset generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dataset generation failed: {exc}")


# ---------------------------------------------------------------------------
# Swarm Simulation (Phase 3)
# ---------------------------------------------------------------------------


@app.post("/simulate/swarm/start")
async def start_swarm_simulation(
    swarm_size: int = Query(50, ge=10, le=1000),
    monte_carlo_runs: int = Query(10, ge=1, le=100),
    timesteps: int = Query(3, ge=1, le=10),
    defenders_enabled: bool = Query(True),
    environment_json: Optional[Dict] = None,
):
    """
    Start a swarm simulation in the background.

    Returns a swarm_id immediately. Poll GET /simulate/swarm/{swarm_id}/status
    for progress, then GET /simulate/swarm/{swarm_id}/result when complete.

    Spawns N follower agents per archetype across M Monte Carlo batches.
    Leaders use LLM decisions; followers replay with randomized parameters.
    """
    # Load environment
    try:
        if environment_json:
            env = Environment.from_dict(environment_json)
        elif settings.simulator_environment_config:
            env = Environment.load_from_json(settings.simulator_environment_config)
        else:
            default_path = "/app/config/simulation/default-environment.json"
            try:
                env = Environment.load_from_json(default_path)
            except FileNotFoundError:
                raise HTTPException(
                    status_code=400,
                    detail="No environment config provided and default not found.",
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load environment: {exc}")

    config = SwarmConfig(
        agent_archetypes=["opportunist", "apt", "ransomware", "insider"],
        defenders_enabled=defenders_enabled,
        timesteps=timesteps,
        swarm_size=swarm_size,
        monte_carlo_runs=monte_carlo_runs,
        concurrency=settings.simulator_default_concurrency,
        ollama_host=settings.simulator_ollama_host,
        ollama_model=settings.simulator_ollama_model,
    )

    simulator = SwarmSimulator(config)

    import asyncio as _asyncio

    async def _run_swarm():
        try:
            report = await simulator.run(env)
            # Store in memory
            store = getattr(app.state, "swarm_store", None)
            if store is not None:
                store[report["swarm_id"]] = report
                while len(store) > 5:
                    store.popitem(last=False)
            # Persist to history (for trends + research)
            hist = getattr(app.state, "history_store", None)
            if hist:
                hist.append(report, trigger="manual", env_snapshot=env.snapshot())
                spike = hist.detect_risk_spike()
                if spike:
                    logger.warning(f"RISK SPIKE DETECTED: {spike}")
            return report
        except Exception as e:
            logger.error(f"Swarm simulation failed: {e}", exc_info=True)
            return {"error": str(e)}

    # Launch as background task
    task = _asyncio.create_task(_run_swarm())
    swarm_id = f"SWARM-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    tasks = getattr(app.state, "swarm_tasks", {})
    tasks[swarm_id] = {"task": task, "simulator": simulator}

    return {
        "swarm_id": swarm_id,
        "status": "started",
        "config": {
            "swarm_size": swarm_size,
            "monte_carlo_runs": monte_carlo_runs,
            "timesteps": timesteps,
            "defenders_enabled": defenders_enabled,
        },
    }


@app.get("/simulate/swarm/{swarm_id}/status")
async def swarm_status(swarm_id: str):
    """Poll progress of a running swarm simulation."""
    tasks = getattr(app.state, "swarm_tasks", {})
    if swarm_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Swarm '{swarm_id}' not found")

    entry = tasks[swarm_id]
    task = entry["task"]
    simulator = entry["simulator"]

    if task.done():
        result = task.result()
        if isinstance(result, dict) and "error" in result:
            return {"status": "failed", "error": result["error"]}
        return {"status": "complete", "swarm_id": result.get("swarm_id", swarm_id)}

    progress = simulator.progress
    return {
        "status": progress.get("status", "running"),
        "current_batch": progress.get("current_batch", 0),
        "total_batches": progress.get("total_batches", 0),
        "total_agent_runs": progress.get("total_agent_runs", 0),
        "elapsed_ms": progress.get("elapsed_ms", 0),
    }


@app.get("/simulate/swarm/{swarm_id}/result")
async def swarm_result(swarm_id: str):
    """Get the completed swarm simulation report."""
    # Check store first
    store = getattr(app.state, "swarm_store", {})
    if swarm_id in store:
        return store[swarm_id]

    # Check if task completed with a different swarm_id
    tasks = getattr(app.state, "swarm_tasks", {})
    if swarm_id in tasks:
        task = tasks[swarm_id]["task"]
        if task.done():
            result = task.result()
            if isinstance(result, dict) and "error" not in result:
                # Store by the actual swarm_id from the result
                actual_id = result.get("swarm_id", swarm_id)
                if actual_id in store:
                    return store[actual_id]
                return result
            elif isinstance(result, dict):
                raise HTTPException(status_code=500, detail=result.get("error", "Swarm failed"))
        raise HTTPException(status_code=202, detail="Swarm simulation still running")

    raise HTTPException(status_code=404, detail=f"Swarm '{swarm_id}' not found")


# ---------------------------------------------------------------------------
# Risk Trends & Research Metrics
# ---------------------------------------------------------------------------


@app.get("/simulate/swarm/trend")
async def swarm_trend(last_n: int = Query(50, ge=1, le=500)):
    """Get time-series swarm results for risk trend visualization."""
    hist = getattr(app.state, "history_store", None)
    if not hist:
        return {"snapshots": [], "spike_alert": None}

    snapshots = hist.get_trend(last_n=last_n)
    spike = hist.detect_risk_spike()
    return {"snapshots": snapshots, "spike_alert": spike}


@app.get("/simulate/research/metrics")
async def research_metrics():
    """Compute research paper metrics from stored swarm history."""
    hist = getattr(app.state, "history_store", None)
    if not hist:
        raise HTTPException(status_code=503, detail="History store not available")
    return compute_all_metrics(hist)


@app.post("/simulate/research/export")
async def research_export():
    """Export CSV files for paper figures."""
    hist = getattr(app.state, "history_store", None)
    if not hist:
        raise HTTPException(status_code=503, detail="History store not available")
    files = export_for_paper(hist)
    return {"exported_files": files, "count": len(files)}


@app.post("/simulate/environment/from-wazuh")
async def environment_from_wazuh():
    """
    Query the Wazuh Manager API to automatically build an Environment model
    from the real infrastructure.

    Reads Wazuh credentials from CORRELATION_WAZUH_API_URL,
    CORRELATION_WAZUH_API_USERNAME, and CORRELATION_WAZUH_API_PASSWORD
    environment variables.

    Returns the generated environment JSON which can be saved and used for
    future simulations by passing it as environment_json in POST /simulate.
    """
    if not settings.wazuh_api_password:
        raise HTTPException(
            status_code=503,
            detail=(
                "Wazuh API password not configured. "
                "Set CORRELATION_WAZUH_API_PASSWORD environment variable."
            ),
        )

    builder = WazuhEnvironmentBuilder(
        wazuh_url=settings.wazuh_api_url,
        username=settings.wazuh_api_username,
        password=settings.wazuh_api_password,
        verify_ssl=settings.wazuh_api_verify_ssl,
    )

    try:
        environment = await builder.build_environment()
        env_dict = builder.to_dict(environment)
        return {
            "status": "success",
            "hosts_discovered": len(environment.hosts),
            "segments_built": len(environment.segments),
            "environment": env_dict,
        }
    except Exception as exc:
        logger.error("Wazuh environment build failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to build environment from Wazuh: {exc}",
        )


@app.get("/risk-scores")
async def get_risk_scores(request: Request):
    """
    Return per-host risk scores sorted by risk score descending.

    Scores are computed from all simulations ingested since startup or the
    last refresh. Call POST /risk-scores/refresh to populate.
    """
    scorer: RiskScorer = getattr(request.app.state, "risk_scorer", None)
    if scorer is None:
        raise HTTPException(status_code=503, detail="Risk scorer not initialized")

    scores = scorer.compute_risk_scores()
    return {"hosts": [s.to_dict() for s in scores], "total": len(scores)}


@app.get("/risk-scores/{host_ip:path}")
async def get_risk_score_for_host(host_ip: str, request: Request):
    """
    Return detailed risk score for a specific host IP address.
    """
    scorer: RiskScorer = getattr(request.app.state, "risk_scorer", None)
    if scorer is None:
        raise HTTPException(status_code=503, detail="Risk scorer not initialized")

    scores = scorer.compute_risk_scores()
    for score in scores:
        if score.host_ip == host_ip:
            return score.to_dict()

    raise HTTPException(status_code=404, detail=f"Host '{host_ip}' not found in risk scores")


@app.get("/risk-summary")
async def get_risk_summary(request: Request):
    """
    Overall risk summary with security posture rating (A-F), highest-risk
    hosts, most common attack technique, and most effective defense.
    """
    scorer: RiskScorer = getattr(request.app.state, "risk_scorer", None)
    if scorer is None:
        raise HTTPException(status_code=503, detail="Risk scorer not initialized")

    return scorer.get_risk_summary()


@app.post("/risk-scores/refresh")
async def refresh_risk_scores(
    request: Request,
    runs: int = Query(5, ge=1, le=50, description="Number of simulations to run"),
    environment_json: Optional[Dict] = None,
):
    """
    Run N simulations and ingest the results into the risk scorer.

    Updates the persistent risk score state used by GET /risk-scores and
    GET /risk-summary. Returns the updated summary after ingestion.
    """
    scorer: RiskScorer = getattr(request.app.state, "risk_scorer", None)
    if scorer is None:
        raise HTTPException(status_code=503, detail="Risk scorer not initialized")

    # Load environment
    try:
        if environment_json:
            env = Environment.from_dict(environment_json)
        elif settings.simulator_environment_config:
            env = Environment.load_from_json(settings.simulator_environment_config)
        else:
            default_path = "/app/config/simulation/default-environment.json"
            try:
                env = Environment.load_from_json(default_path)
            except FileNotFoundError:
                raise HTTPException(
                    status_code=400,
                    detail="No environment config provided and default not found.",
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load environment: {exc}")

    config = SimulationConfig(
        agent_archetypes=["opportunist", "apt", "ransomware", "insider"],
        timesteps=settings.simulator_default_timesteps,
        concurrency=settings.simulator_default_concurrency,
        ollama_host=settings.simulator_ollama_host,
        ollama_model=settings.simulator_ollama_model,
    )
    simulator = CampaignSimulator(config)

    completed = 0
    for _ in range(runs):
        try:
            report = await simulator.run(env)
            scorer.ingest_simulation(report)
            completed += 1
        except Exception as exc:
            logger.warning("Risk score refresh: simulation run failed: %s", exc)

    logger.info(
        "Risk score refresh complete: %d/%d simulations succeeded, "
        "total history=%d",
        completed, runs, scorer.simulation_count,
    )

    summary = scorer.get_risk_summary()
    summary["refresh_completed"] = completed
    summary["refresh_requested"] = runs
    return summary


@app.get("/predict/{kill_chain_stage}")
async def predict_next_stage(kill_chain_stage: str, top_k: int = Query(3, ge=1, le=5)):
    """
    Predict the most likely next kill chain stages from the current stage.

    Uses Markov chain transition probabilities learned from historical
    incidents. Falls back to domain knowledge when insufficient data.
    """
    predictor = getattr(app.state, "predictor", None)
    if not predictor:
        raise HTTPException(status_code=503, detail="Predictor not initialized")

    predictions = predictor.predict_next_stages(kill_chain_stage, top_k=top_k)
    return {
        "current_stage": kill_chain_stage,
        "predictions": predictions,
        "predictor_stats": predictor.stats,
    }


@app.post("/predict/retrain")
async def retrain_predictor(db: AsyncSession = Depends(get_db)):
    """Retrain the predictor from current incident history."""
    predictor = getattr(app.state, "predictor", None)
    if not predictor:
        app.state.predictor = AttackPredictor()
        predictor = app.state.predictor

    await predictor.train(db)
    return {"status": "retrained", "stats": predictor.stats}


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Return service and database connection status.",
)
async def health_check():
    """
    Returns overall health including database connectivity.
    Status is 'healthy' if DB is reachable, 'degraded' otherwise.
    """
    db_ok = await check_db_health()
    if not db_ok:
        raise HTTPException(503, "Database unavailable")

    svc_status = "healthy" if db_ok else "degraded"

    return HealthResponse(
        status=svc_status,
        service=settings.service_name,
        version=settings.service_version,
        db_connected=db_ok,
    )


@app.get("/metrics", summary="Prometheus metrics")
async def metrics():
    """Expose Prometheus metrics for scraping."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/", summary="Service information")
async def root():
    """Root endpoint with service metadata."""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "operational",
        "endpoints": {
            "correlate": "POST /correlate",
            "incidents": "GET /incidents",
            "active_incidents": "GET /incidents/active",
            "incident_detail": "GET /incidents/{incident_id}",
            "update_status": "PUT /incidents/{incident_id}/status",
            "simulate": "POST /simulate",
            "generate_dataset": "POST /simulate/generate-dataset",
            "environment_from_wazuh": "POST /simulate/environment/from-wazuh",
            "risk_scores": "GET /risk-scores",
            "risk_score_host": "GET /risk-scores/{host_ip}",
            "risk_summary": "GET /risk-summary",
            "risk_refresh": "POST /risk-scores/refresh",
            "health": "GET /health",
            "metrics": "GET /metrics",
            "docs": "GET /docs",
        },
    }


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions."""
    logger.error("Unhandled exception on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": str(request.url),
        },
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=True,
    )
