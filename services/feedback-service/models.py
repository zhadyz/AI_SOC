"""
Pydantic Models - Feedback Service
AI-Augmented SOC

Data models for alert persistence and analyst feedback.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, model_validator
from typing import Literal


class SeverityLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class AlertCategory(str, Enum):
    MALWARE = "malware"
    INTRUSION_ATTEMPT = "intrusion_attempt"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    LATERAL_MOVEMENT = "lateral_movement"
    PERSISTENCE = "persistence"
    RECONNAISSANCE = "reconnaissance"
    COMMAND_AND_CONTROL = "command_and_control"
    POLICY_VIOLATION = "policy_violation"
    ANOMALY = "anomaly"
    OTHER = "other"


# --- Request Models ---

class StoreAlertRequest(BaseModel):
    """Request to persist an alert and its triage result."""
    alert_id: str = Field(..., description="Unique alert identifier")
    wazuh_alert_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_ip: Optional[str] = None
    dest_ip: Optional[str] = None
    rule_id: Optional[str] = None
    rule_description: Optional[str] = None
    rule_level: Optional[int] = None
    raw_alert: Optional[Dict[str, Any]] = Field(None, description="Full SecurityAlert as dict")
    triage_result: Optional[Dict[str, Any]] = Field(None, description="Full TriageResponse as dict")
    ai_severity: Optional[str] = None
    ai_category: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_is_true_positive: Optional[bool] = None
    ml_prediction: Optional[str] = None
    ml_confidence: Optional[float] = None


class FeedbackSubmission(BaseModel):
    """Analyst feedback on a triage result."""
    analyst_id: str = Field(..., min_length=1, description="Analyst identifier")
    true_severity: Optional[SeverityLevel] = Field(None, description="Corrected severity")
    true_category: Optional[AlertCategory] = Field(None, description="Corrected category")
    is_false_positive: bool = Field(False, description="Mark as false positive")
    true_label: Optional[Literal["BENIGN", "ATTACK"]] = Field(
        None,
        description="Ground truth label for ML retraining (BENIGN or attack type)"
    )
    notes: Optional[str] = Field(None, max_length=2000, description="Analyst notes")


    @model_validator(mode="after")
    def consistent_label(self):
        if self.is_false_positive and self.true_label == "ATTACK":
            raise ValueError("A false positive cannot have an ATTACK ground-truth label")
        return self


class FeedbackReview(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=100)
    approved: bool
    notes: Optional[str] = Field(None, max_length=2000)


class AlertQuery(BaseModel):
    """Query parameters for alert search."""
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
    severity: Optional[str] = None
    source_ip: Optional[str] = None
    dest_ip: Optional[str] = None
    has_feedback: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


# --- Response Models ---

class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""
    feedback_id: str
    alert_id: str
    analyst_id: str
    is_false_positive: bool
    created_at: datetime


class StoredAlertResponse(BaseModel):
    """A persisted alert with its triage result and feedback."""
    alert_id: str
    wazuh_alert_id: Optional[str] = None
    timestamp: datetime
    source_ip: Optional[str] = None
    dest_ip: Optional[str] = None
    rule_id: Optional[str] = None
    rule_description: Optional[str] = None
    rule_level: Optional[int] = None
    ai_severity: Optional[str] = None
    ai_category: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_is_true_positive: Optional[bool] = None
    ml_prediction: Optional[str] = None
    ml_confidence: Optional[float] = None
    created_at: datetime
    feedback_count: int = 0
    feedback: List[Dict[str, Any]] = []


class FeedbackStats(BaseModel):
    """Aggregated feedback statistics."""
    total_alerts: int = 0
    total_feedback: int = 0
    false_positive_count: int = 0
    false_positive_rate: float = 0.0
    severity_corrections: int = 0
    severity_correction_rate: float = 0.0
    category_corrections: int = 0
    labeled_for_retraining: int = 0
    avg_confidence_when_correct: Optional[float] = None
    avg_confidence_when_wrong: Optional[float] = None
    top_false_positive_sources: List[Dict[str, Any]] = []
