"""
Pydantic Models - Response Orchestrator Service
AI-Augmented SOC

Data models for defense plans, planned actions, execution results,
verification outcomes, and the orchestrator state machine.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PlanStatus(str, Enum):
    """State machine for a defense plan lifecycle."""
    TRIGGERED = "triggered"
    SIMULATING = "simulating"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    DRY_RUN = "dry_run_completed"
    RECOVERY_REQUIRED = "recovery_required"
    CANCELLED = "cancelled"


class ActionStatus(str, Enum):
    """Lifecycle of a single planned action."""
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"
    VETOED = "vetoed"
    SIMULATED = "simulated"


class ApprovalTier(int, Enum):
    """Graduated autonomy tiers."""
    OBSERVE = 0        # Log only, no action
    RECOMMEND = 1      # Display recommendation to analyst
    AUTO_SAFE = 2      # Auto-execute, low blast radius
    AUTO_VETO = 3      # Auto-execute with veto window
    HUMAN_REQUIRED = 4 # Always requires human approval


class BlastRadius(str, Enum):
    """Impact scope of a defense action."""
    NONE = "none"       # Observational only
    LOW = "low"         # Single external entity (block 1 IP)
    MEDIUM = "medium"   # Single internal host or service
    HIGH = "high"       # Critical asset, multiple hosts, or network segment


class ActionType(str, Enum):
    """Concrete defense actions the system can take."""
    BLOCK_IP = "block_ip"
    ISOLATE_HOST = "isolate_host"
    DEPLOY_EDR = "deploy_edr"
    REVOKE_CREDENTIALS = "revoke_credentials"
    DISABLE_ACCOUNT = "disable_account"
    PATCH_VULNERABILITY = "patch_vulnerability"
    ADD_MONITORING = "add_monitoring"
    DEPLOY_SIGMA_RULE = "deploy_sigma_rule"
    ENABLE_MFA = "enable_mfa"
    NETWORK_SEGMENT = "network_segment"
    KILL_PROCESS = "kill_process"
    SINKHOLE_DOMAIN = "sinkhole_domain"
    RESTORE_BACKUP = "restore_backup"


class AdapterType(str, Enum):
    """Which adapter executes the action."""
    WAZUH = "wazuh"
    FIREWALL = "firewall"
    EDR = "edr"
    IDENTITY = "identity"
    NETWORK = "network"


# ---------------------------------------------------------------------------
# Action Models
# ---------------------------------------------------------------------------

class PlannedAction(BaseModel):
    """A single defense action within a plan."""
    action_id: str = Field(..., description="Unique action identifier")
    action_type: ActionType = Field(..., description="Type of defense action")
    target: str = Field(..., description="Target IP, hostname, or resource")
    target_hostname: Optional[str] = Field(None, description="Human-readable hostname")
    adapter: AdapterType = Field(..., description="Adapter responsible for execution")

    # Scoring
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence in this action")
    impact_score: float = Field(..., ge=0.0, le=1.0, description="Expected attack surface reduction")
    safety_score: float = Field(..., ge=0.0, le=1.0, description="Safety of executing this action")
    composite_score: float = Field(..., ge=0.0, le=1.0, description="Weighted composite score")

    # Safety classification
    blast_radius: BlastRadius = Field(..., description="Impact scope")
    approval_tier: ApprovalTier = Field(..., description="Required approval level")
    requires_approval: bool = Field(..., description="Whether human approval is needed")

    # MITRE mapping
    d3fend_technique: str = Field("", description="D3FEND technique ID")
    d3fend_label: str = Field("", description="D3FEND technique name")
    counters_techniques: List[str] = Field(default_factory=list, description="ATT&CK techniques this counters")

    # Execution state
    status: ActionStatus = Field(ActionStatus.PENDING, description="Current action status")
    rationale: str = Field("", description="Why this action was selected")
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    adapter_response: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None
    approved_at: Optional[datetime] = None
    veto_deadline: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "action_id": "ACT-001",
                "action_type": "block_ip",
                "target": "203.0.113.42",
                "adapter": "wazuh",
                "confidence": 0.85,
                "impact_score": 0.31,
                "safety_score": 0.95,
                "composite_score": 0.52,
                "blast_radius": "low",
                "approval_tier": 2,
                "requires_approval": False,
                "d3fend_technique": "d3f:InboundTrafficFiltering",
                "d3fend_label": "Inbound Traffic Filtering",
                "counters_techniques": ["T1190", "T1046"],
                "status": "pending",
                "rationale": "Block attacker source IP to prevent further reconnaissance",
            }
        }


# ---------------------------------------------------------------------------
# Verification Models
# ---------------------------------------------------------------------------

class VerificationResult(BaseModel):
    """Result of verifying a defense plan's effectiveness."""
    plan_id: str
    verified_at: datetime = Field(default_factory=datetime.utcnow)

    # Re-simulation track
    pre_attack_success_rate: float = Field(..., description="Attack success rate before defense")
    post_attack_success_rate: float = Field(..., description="Attack success rate after defense")
    risk_reduction_pct: float = Field(..., description="Percentage reduction in attack success")
    re_simulation_id: Optional[str] = None

    # Monitoring track
    continued_indicators: bool = Field(False, description="Whether attack indicators persisted")
    monitoring_duration_seconds: int = 0
    new_alerts_during_monitoring: int = 0

    # Verdict
    verification_passed: bool = Field(..., description="Whether the defense is considered effective")
    verdict_reason: str = Field("", description="Why the verification passed or failed")
    evidence_available: bool = False
    simulation_available: bool = False
    monitoring_available: bool = False


# ---------------------------------------------------------------------------
# Defense Plan Models
# ---------------------------------------------------------------------------

class DefensePlan(BaseModel):
    """A complete defense plan generated for an incident."""
    plan_id: str = Field(..., description="Unique plan identifier")
    incident_id: str = Field(..., description="Incident this plan addresses")
    simulation_id: Optional[str] = Field(None, description="Simulation that informed this plan")

    # State
    status: PlanStatus = Field(PlanStatus.TRIGGERED, description="Current plan status")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Context
    incident_summary: str = Field("", description="Human-readable incident description")
    detected_techniques: List[str] = Field(default_factory=list, description="ATT&CK techniques detected")
    kill_chain_stage: str = Field("", description="Current kill chain position")
    source_ips: List[str] = Field(default_factory=list)
    dest_ips: List[str] = Field(default_factory=list)

    # Simulation results
    pre_defense_risk: Optional[float] = Field(None, description="Risk score before defense actions")
    post_defense_risk: Optional[float] = Field(None, description="Risk score after defense actions")
    simulation_summary: Optional[Dict[str, Any]] = None

    # The plan itself
    actions: List[PlannedAction] = Field(default_factory=list, description="Ordered list of defense actions")
    rationale: str = Field("", description="LLM-generated explanation of the defense strategy")

    # Verification
    verification: Optional[VerificationResult] = None

    # Metadata
    total_actions: int = Field(0)
    auto_executed_count: int = Field(0)
    human_approved_count: int = Field(0)
    dry_run: bool = Field(True, description="If true, no actions were actually executed")

    class Config:
        json_schema_extra = {
            "example": {
                "plan_id": "PLAN-20250324-abc1",
                "incident_id": "INC-20250324143045-ab12",
                "status": "completed",
                "detected_techniques": ["T1110", "T1210"],
                "kill_chain_stage": "lateral_movement",
                "pre_defense_risk": 0.72,
                "post_defense_risk": 0.04,
                "total_actions": 4,
                "auto_executed_count": 3,
                "human_approved_count": 1,
            }
        }


# ---------------------------------------------------------------------------
# API Request/Response Models
# ---------------------------------------------------------------------------

class TriggerPlanRequest(BaseModel):
    """Request to trigger a defense plan for an incident."""
    incident_id: str = Field(..., description="Incident to defend against")
    environment_json: Optional[Dict[str, Any]] = Field(
        None, description="Custom environment (uses default if omitted)"
    )
    auto_execute: bool = Field(False, description="Allow auto-execution of safe actions")
    dry_run: bool = Field(True, description="Simulate without executing")
    skip_simulation: bool = Field(False, description="Skip simulation, plan from incident data only")


class ApproveActionRequest(BaseModel):
    """Request to approve or reject a pending action."""
    approved: bool = Field(..., description="True to approve, False to reject")
    analyst_id: str = Field(..., min_length=1, max_length=255, description="Analyst who made the decision")
    notes: Optional[str] = Field(None, max_length=2000, description="Analyst notes")


class PlanSummary(BaseModel):
    """Lightweight plan model for list endpoints."""
    plan_id: str
    incident_id: str
    status: PlanStatus
    total_actions: int
    auto_executed_count: int
    pending_approval_count: int
    pre_defense_risk: Optional[float]
    post_defense_risk: Optional[float]
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    """Service health check response."""
    status: str
    service: str
    version: str
    db_connected: bool
    correlation_engine_reachable: bool
    ollama_reachable: bool
    wazuh_reachable: bool
    active_plans: int
    dry_run_mode: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)
