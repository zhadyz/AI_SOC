"""
Correlation Engine - Core Algorithm
AI-Augmented SOC

Scores incoming alerts against active incidents using temporal proximity,
IP affinity, and MITRE kill chain progression. Attaches alerts to the
best-matching incident or opens a new one.
"""

import math
import logging
from sqlalchemy import text
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.correlation_engine.models import (
    CorrelationRequest,
    CorrelationResponse,
    TACTIC_TO_STAGE,
    KILL_CHAIN_ORDER,
    KillChainStage,
    SEVERITY_ORDER,
)
from services.correlation_engine.database import IncidentModel, IncidentAlertModel
from services.correlation_engine.config import Settings

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_incident_id() -> str:
    """
    Generate a deterministic-looking incident ID in the format
    INC-{YYYYMMDDHHmmss}-{4-char uuid fragment}.
    """
    ts = _now_utc().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:4]
    return f"INC-{ts}-{short_uuid}"


def _stage_index(stage_name: Optional[str]) -> int:
    """Return the numerical order index of a stage name, or -1 if unknown."""
    if stage_name is None:
        return -1
    for i, stage in enumerate(KILL_CHAIN_ORDER):
        if stage.value == stage_name:
            return i
    return -1


def _get_highest_stage(tactics: List[str]) -> Optional[KillChainStage]:
    """
    Given a list of MITRE tactic names, return the stage with the
    highest kill-chain index.
    """
    best_index = -1
    best_stage: Optional[KillChainStage] = None
    for tactic in tactics:
        tactic_lower = tactic.lower().strip().replace(" ", "-").replace("_", "-")
        stage = TACTIC_TO_STAGE.get(tactic_lower)
        if stage is None:
            continue
        idx = _stage_index(stage.value)
        if idx > best_index:
            best_index = idx
            best_stage = stage
    return best_stage


def _higher_severity(a: str, b: str) -> str:
    """Return the more severe of two severity strings."""
    if SEVERITY_ORDER.get(a, 0) >= SEVERITY_ORDER.get(b, 0):
        return a
    return b


def _build_summary(incident: IncidentModel) -> str:
    """
    Auto-generate a human-readable incident summary from incident data.
    """
    src_str = ", ".join(incident.source_ips[:3]) if incident.source_ips else "unknown source"
    dst_str = ", ".join(incident.dest_ips[:3]) if incident.dest_ips else "unknown destination"
    tactics = ", ".join(incident.mitre_tactics[:3]) if incident.mitre_tactics else "unknown tactics"
    stage = incident.kill_chain_stage or "unknown"
    return (
        f"{incident.severity.capitalize()} severity incident involving {src_str} "
        f"targeting {dst_str}. Kill chain stage: {stage}. "
        f"MITRE tactics: {tactics}. Alert count: {incident.alert_count}."
    )


class CorrelationEngine:
    """
    Core alert-to-incident correlation logic.

    Scoring weights:
      - Temporal proximity  40% (exponential decay over temporal_window)
      - IP overlap          40% (source + dest IPs)
      - Kill chain progress 20% (MITRE tactic stage progression)
    """

    def __init__(self, db: AsyncSession, settings: Settings):
        self.db = db
        self.temporal_window = settings.temporal_window_minutes
        self.threshold = settings.correlation_threshold
        self.auto_close_minutes = settings.incident_auto_close_minutes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def correlate(self, request: CorrelationRequest) -> CorrelationResponse:
        """
        Main entry point: score the incoming alert against all active
        incidents and either attach it or create a new incident.
        """
        # Serialize the correlation transaction so retries and concurrent alert
        # arrivals cannot create duplicate incidents or lose alert counts.
        if self.db.bind.dialect.name == "postgresql":
            await self.db.execute(text("SELECT pg_advisory_xact_lock(660748)"))
        existing = (await self.db.execute(
            select(IncidentAlertModel).where(IncidentAlertModel.alert_id == request.alert_id)
        )).scalars().first()
        if existing:
            incident = (await self.db.execute(select(IncidentModel).where(
                IncidentModel.incident_id == existing.incident_id))).scalar_one()
            return CorrelationResponse(incident_id=incident.incident_id, is_new_incident=False,
                correlation_score=1.0, kill_chain_stage=incident.kill_chain_stage,
                incident_alert_count=incident.alert_count)

        # Resolve kill chain stage from tactics
        alert_stage: Optional[KillChainStage] = None
        if request.mitre_tactics:
            alert_stage = _get_highest_stage(request.mitre_tactics)

        alert_stage_str = alert_stage.value if alert_stage else KillChainStage.RECONNAISSANCE.value

        # Retrieve active incidents
        active_incidents = await self._get_active_incidents()

        # Score each incident
        best_score = 0.0
        best_incident: Optional[IncidentModel] = None

        for incident in active_incidents:
            score = self._compute_score(request, incident)
            logger.debug(
                "correlation_score",
                extra={
                    "alert_id": request.alert_id,
                    "incident_id": incident.incident_id,
                    "score": round(score, 4),
                }
            )
            if score > best_score:
                best_score = score
                best_incident = incident

        # Attach to existing incident if score exceeds threshold
        if best_incident and best_score >= self.threshold:
            updated = await self._add_alert_to_incident(
                best_incident, request, alert_stage_str
            )
            return CorrelationResponse(
                incident_id=updated.incident_id,
                is_new_incident=False,
                correlation_score=round(best_score, 4),
                kill_chain_stage=updated.kill_chain_stage or alert_stage_str,
                incident_alert_count=updated.alert_count,
            )

        # Otherwise open a new incident
        new_incident = await self._create_incident(request, alert_stage_str)
        return CorrelationResponse(
            incident_id=new_incident.incident_id,
            is_new_incident=True,
            correlation_score=0.0,
            kill_chain_stage=new_incident.kill_chain_stage or alert_stage_str,
            incident_alert_count=new_incident.alert_count,
        )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _compute_score(
        self, alert: CorrelationRequest, incident: IncidentModel
    ) -> float:
        """
        Compute a [0, 1] correlation score between the alert and an incident.

        Components:
          - Temporal proximity (40%): exponential decay relative to temporal window
          - IP overlap (40%): matching source/dest IPs against incident IPs
          - Kill chain progression (20%): alert tactic advances the kill chain
        """
        score = 0.0

        # --- Temporal proximity (40%) ---
        if incident.last_seen:
            last_seen_aware = incident.last_seen
            if last_seen_aware.tzinfo is None:
                last_seen_aware = last_seen_aware.replace(tzinfo=timezone.utc)

            alert_ts = alert.timestamp
            if alert_ts.tzinfo is None:
                alert_ts = alert_ts.replace(tzinfo=timezone.utc)

            time_diff = abs((alert_ts - last_seen_aware).total_seconds())
            window_seconds = self.temporal_window * 60

            if time_diff <= window_seconds:
                temporal_score = math.exp(-time_diff / window_seconds)
                score += temporal_score * 0.4

        # --- IP overlap (40%) ---
        ip_matches = 0
        incident_src_ips = incident.source_ips or []
        incident_dst_ips = incident.dest_ips or []

        if alert.source_ip and alert.source_ip in incident_src_ips:
            ip_matches += 1
        if alert.dest_ip and alert.dest_ip in incident_dst_ips:
            ip_matches += 1

        score += (ip_matches / 2.0) * 0.4

        # --- Kill chain progression (20%) ---
        if alert.mitre_tactics:
            alert_stage = _get_highest_stage(alert.mitre_tactics)
            if alert_stage is not None:
                incident_stage_idx = _stage_index(incident.kill_chain_stage)
                alert_stage_idx = _stage_index(alert_stage.value)

                # Award points if the alert continues or advances the chain
                if alert_stage_idx >= incident_stage_idx:
                    score += 0.2

        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    async def _get_active_incidents(self) -> List[IncidentModel]:
        """Fetch all incidents with status 'open' or 'investigating'."""
        result = await self.db.execute(
            select(IncidentModel).where(
                IncidentModel.status.in_(["open", "investigating"])
            )
        )
        return list(result.scalars().all())

    async def _create_incident(
        self, request: CorrelationRequest, stage: str
    ) -> IncidentModel:
        """Create a new incident from the first alert."""
        incident_id = _generate_incident_id()

        source_ips = [request.source_ip] if request.source_ip else []
        dest_ips = [request.dest_ip] if request.dest_ip else []

        incident = IncidentModel(
            incident_id=incident_id,
            status="open",
            severity=request.severity,
            kill_chain_stage=stage,
            kill_chain_stages_seen=[stage],
            alert_count=1,
            first_seen=request.timestamp,
            last_seen=request.timestamp,
            source_ips=source_ips,
            dest_ips=dest_ips,
            mitre_techniques=list(request.mitre_techniques),
            mitre_tactics=list(request.mitre_tactics),
            summary="",
        )

        self.db.add(incident)
        await self.db.flush()  # Populate defaults before building summary

        incident.summary = _build_summary(incident)
        await self.db.flush()

        # Add the first alert record
        alert_record = IncidentAlertModel(
            incident_id=incident_id,
            alert_id=request.alert_id,
            severity=request.severity,
            category=request.category,
            kill_chain_stage=stage,
        )
        self.db.add(alert_record)
        await self.db.flush()

        logger.info(
            "incident_created",
            extra={
                "incident_id": incident_id,
                "alert_id": request.alert_id,
                "severity": request.severity,
                "stage": stage,
            }
        )
        return incident

    async def _add_alert_to_incident(
        self,
        incident: IncidentModel,
        request: CorrelationRequest,
        alert_stage: str,
    ) -> IncidentModel:
        """
        Attach a new alert to an existing incident and update all aggregated
        fields: severity, kill chain stage, IPs, techniques, tactics, timestamps.
        """
        # Merge IPs (deduplicated)
        src_ips: List[str] = list(incident.source_ips or [])
        dst_ips: List[str] = list(incident.dest_ips or [])
        if request.source_ip and request.source_ip not in src_ips:
            src_ips.append(request.source_ip)
        if request.dest_ip and request.dest_ip not in dst_ips:
            dst_ips.append(request.dest_ip)

        # Merge MITRE data (deduplicated)
        techniques: List[str] = list(incident.mitre_techniques or [])
        tactics: List[str] = list(incident.mitre_tactics or [])
        for t in request.mitre_techniques:
            if t not in techniques:
                techniques.append(t)
        for t in request.mitre_tactics:
            if t not in tactics:
                tactics.append(t)

        # Advance kill chain if the alert is further along
        stages_seen: List[str] = list(incident.kill_chain_stages_seen or [])
        if alert_stage not in stages_seen:
            stages_seen.append(alert_stage)

        current_stage_idx = _stage_index(incident.kill_chain_stage)
        alert_stage_idx = _stage_index(alert_stage)
        new_stage = (
            alert_stage if alert_stage_idx > current_stage_idx
            else (incident.kill_chain_stage or alert_stage)
        )

        # Escalate severity if this alert is more severe
        new_severity = _higher_severity(
            incident.severity or "informational", request.severity
        )

        # Update last_seen
        alert_ts = request.timestamp
        if alert_ts.tzinfo is None:
            alert_ts = alert_ts.replace(tzinfo=timezone.utc)

        last_seen_aware = incident.last_seen
        if last_seen_aware and last_seen_aware.tzinfo is None:
            last_seen_aware = last_seen_aware.replace(tzinfo=timezone.utc)

        new_last_seen = (
            alert_ts
            if last_seen_aware is None or alert_ts > last_seen_aware
            else last_seen_aware
        )

        new_alert_count = (incident.alert_count or 0) + 1

        # Apply updates via SQLAlchemy ORM (avoid stale-object issues)
        await self.db.execute(
            update(IncidentModel)
            .where(IncidentModel.incident_id == incident.incident_id)
            .values(
                severity=new_severity,
                kill_chain_stage=new_stage,
                kill_chain_stages_seen=stages_seen,
                alert_count=new_alert_count,
                last_seen=new_last_seen,
                source_ips=src_ips,
                dest_ips=dst_ips,
                mitre_techniques=techniques,
                mitre_tactics=tactics,
            )
        )

        # Re-fetch to get updated state for summary generation
        result = await self.db.execute(
            select(IncidentModel).where(
                IncidentModel.incident_id == incident.incident_id
            )
        )
        updated_incident = result.scalar_one()
        updated_incident.summary = _build_summary(updated_incident)
        await self.db.flush()

        # Insert alert record
        alert_record = IncidentAlertModel(
            incident_id=incident.incident_id,
            alert_id=request.alert_id,
            severity=request.severity,
            category=request.category,
            kill_chain_stage=alert_stage,
        )
        self.db.add(alert_record)
        await self.db.flush()

        logger.info(
            "alert_added_to_incident",
            extra={
                "incident_id": incident.incident_id,
                "alert_id": request.alert_id,
                "new_alert_count": new_alert_count,
                "kill_chain_stage": new_stage,
            }
        )
        return updated_incident
