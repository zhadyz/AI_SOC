"""
Pydantic Models - Correlation Engine Service
AI-Augmented SOC

Defines structured data models for alert correlation requests and incident tracking.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class KillChainStage(str, Enum):
    """MITRE ATT&CK kill chain stages in progression order"""
    RECONNAISSANCE = "reconnaissance"
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    LATERAL_MOVEMENT = "lateral_movement"
    COLLECTION = "collection"
    COMMAND_AND_CONTROL = "command_and_control"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"


# Ordered list for progression comparison (index = stage order)
KILL_CHAIN_ORDER = [
    KillChainStage.RECONNAISSANCE,
    KillChainStage.INITIAL_ACCESS,
    KillChainStage.EXECUTION,
    KillChainStage.PERSISTENCE,
    KillChainStage.PRIVILEGE_ESCALATION,
    KillChainStage.LATERAL_MOVEMENT,
    KillChainStage.COLLECTION,
    KillChainStage.COMMAND_AND_CONTROL,
    KillChainStage.EXFILTRATION,
    KillChainStage.IMPACT,
]


# Mapping from MITRE ATT&CK tactic names to kill chain stages
TACTIC_TO_STAGE = {
    "reconnaissance": KillChainStage.RECONNAISSANCE,
    "resource-development": KillChainStage.RECONNAISSANCE,
    "initial-access": KillChainStage.INITIAL_ACCESS,
    "execution": KillChainStage.EXECUTION,
    "persistence": KillChainStage.PERSISTENCE,
    "privilege-escalation": KillChainStage.PRIVILEGE_ESCALATION,
    "defense-evasion": KillChainStage.PERSISTENCE,
    "credential-access": KillChainStage.PRIVILEGE_ESCALATION,
    "discovery": KillChainStage.RECONNAISSANCE,
    "lateral-movement": KillChainStage.LATERAL_MOVEMENT,
    "collection": KillChainStage.COLLECTION,
    "command-and-control": KillChainStage.COMMAND_AND_CONTROL,
    "exfiltration": KillChainStage.EXFILTRATION,
    "impact": KillChainStage.IMPACT,
}

for tactic_id, tactic_name in {
    "ta0043": "reconnaissance", "ta0042": "resource-development",
    "ta0001": "initial-access", "ta0002": "execution", "ta0003": "persistence",
    "ta0004": "privilege-escalation", "ta0005": "defense-evasion",
    "ta0006": "credential-access", "ta0007": "discovery", "ta0008": "lateral-movement",
    "ta0009": "collection", "ta0011": "command-and-control", "ta0010": "exfiltration",
    "ta0040": "impact",
}.items():
    TACTIC_TO_STAGE[tactic_id] = TACTIC_TO_STAGE[tactic_name]

# Severity ordering for comparison
SEVERITY_ORDER = {
    "informational": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


class CorrelationRequest(BaseModel):
    """
    Input model for alert correlation requests.

    Sent from the wazuh-integration service after AI triage.
    """
    alert_id: str = Field(..., description="Unique alert identifier")
    source_ip: Optional[str] = Field(None, description="Source IP address")
    dest_ip: Optional[str] = Field(None, description="Destination IP address")
    timestamp: datetime = Field(..., description="Alert timestamp")
    severity: str = Field(..., description="AI-assessed severity level")
    category: str = Field(..., description="Alert category")
    mitre_techniques: List[str] = Field(default_factory=list, description="MITRE technique IDs")
    mitre_tactics: List[str] = Field(default_factory=list, description="MITRE tactic names")
    rule_description: Optional[str] = Field(None, description="Alert rule description")

    class Config:
        json_schema_extra = {
            "example": {
                "alert_id": "wazuh-001-20250321-1234",
                "source_ip": "203.0.113.42",
                "dest_ip": "10.0.1.50",
                "timestamp": "2025-03-21T14:30:45Z",
                "severity": "high",
                "category": "intrusion_attempt",
                "mitre_techniques": ["T1110"],
                "mitre_tactics": ["credential-access"],
                "rule_description": "Multiple failed SSH login attempts"
            }
        }


class IncidentAlert(BaseModel):
    """
    A single alert attached to an incident, stored in incident_alerts table.
    """
    alert_id: str
    added_at: datetime
    severity: str
    category: str
    kill_chain_stage: Optional[str] = None


class Incident(BaseModel):
    """
    Full incident model returned by GET /incidents/{incident_id}.
    """
    incident_id: str
    status: str = Field("open", description="open, investigating, or closed")
    severity: str = Field(..., description="Highest severity among member alerts")
    kill_chain_stage: str = Field(..., description="Current highest kill chain stage")
    kill_chain_stages_seen: List[str] = Field(default_factory=list)
    alert_count: int = Field(0, description="Total number of correlated alerts")
    first_seen: datetime
    last_seen: datetime
    source_ips: List[str] = Field(default_factory=list)
    dest_ips: List[str] = Field(default_factory=list)
    mitre_techniques: List[str] = Field(default_factory=list)
    mitre_tactics: List[str] = Field(default_factory=list)
    alerts: List[IncidentAlert] = Field(default_factory=list)
    summary: str

    class Config:
        json_schema_extra = {
            "example": {
                "incident_id": "INC-20250321143045-ab12",
                "status": "open",
                "severity": "high",
                "kill_chain_stage": "credential-access",
                "alert_count": 5,
                "first_seen": "2025-03-21T14:30:45Z",
                "last_seen": "2025-03-21T14:42:10Z",
                "source_ips": ["203.0.113.42"],
                "dest_ips": ["10.0.1.50"],
                "mitre_techniques": ["T1110"],
                "mitre_tactics": ["credential-access"],
                "summary": "Ongoing brute-force attack from 203.0.113.42 targeting SSH"
            }
        }


class IncidentSummary(BaseModel):
    """
    Lightweight incident model for list endpoints (no alert details).
    """
    incident_id: str
    status: str
    severity: str
    kill_chain_stage: str
    alert_count: int
    first_seen: datetime
    last_seen: datetime
    source_ips: List[str] = Field(default_factory=list)
    dest_ips: List[str] = Field(default_factory=list)
    summary: str


class CorrelationResponse(BaseModel):
    """
    Response returned by POST /correlate.
    """
    incident_id: str
    is_new_incident: bool
    correlation_score: float = Field(..., ge=0.0, le=1.0)
    kill_chain_stage: str
    incident_alert_count: int

    class Config:
        json_schema_extra = {
            "example": {
                "incident_id": "INC-20250321143045-ab12",
                "is_new_incident": False,
                "correlation_score": 0.82,
                "kill_chain_stage": "privilege_escalation",
                "incident_alert_count": 6
            }
        }


class StatusUpdate(BaseModel):
    """Request body for PUT /incidents/{incident_id}/status"""
    status: str = Field(..., description="New status: open, investigating, or closed")

    class Config:
        json_schema_extra = {
            "example": {"status": "investigating"}
        }


class HealthResponse(BaseModel):
    """Service health check response"""
    status: str
    service: str
    version: str
    db_connected: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)
