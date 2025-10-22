"""
Pydantic Models - Alert Triage Service
AI-Augmented SOC

Defines structured data models for security alerts and LLM responses.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SeverityLevel(str, Enum):
    """Alert severity classification"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "informational"


class AlertCategory(str, Enum):
    """Security alert categories"""
    MALWARE = "malware"
    INTRUSION = "intrusion_attempt"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    LATERAL_MOVEMENT = "lateral_movement"
    PERSISTENCE = "persistence"
    RECONNAISSANCE = "reconnaissance"
    COMMAND_AND_CONTROL = "command_and_control"
    POLICY_VIOLATION = "policy_violation"
    ANOMALY = "anomaly"
    OTHER = "other"


class IOC(BaseModel):
    """Indicator of Compromise"""
    ioc_type: str = Field(..., description="Type: IP, domain, hash, etc")
    value: str = Field(..., description="IOC value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class SecurityAlert(BaseModel):
    """
    Input model for security alerts from Wazuh/Shuffle.

    This structure aligns with Wazuh alert format.
    """
    alert_id: str = Field(..., description="Unique alert identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Alert Details
    rule_id: Optional[str] = Field(None, description="Wazuh rule ID")
    rule_description: str = Field(..., description="Alert description")
    rule_level: int = Field(..., ge=0, le=15, description="Wazuh rule level (0-15)")

    # Source Information
    source_ip: Optional[str] = None
    source_port: Optional[int] = None
    source_hostname: Optional[str] = None

    # Destination Information
    dest_ip: Optional[str] = None
    dest_port: Optional[int] = None
    dest_hostname: Optional[str] = None

    # Additional Context
    user: Optional[str] = None
    process: Optional[str] = None
    command: Optional[str] = None
    file_path: Optional[str] = None

    # Raw Data
    raw_log: Optional[str] = Field(None, description="Original log message")
    full_log: Optional[Dict[str, Any]] = Field(None, description="Complete Wazuh alert JSON")

    # MITRE ATT&CK
    mitre_technique: Optional[List[str]] = Field(None, description="MITRE ATT&CK technique IDs")

    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v


class TriageRecommendation(BaseModel):
    """Actionable recommendation from LLM"""
    action: str = Field(..., description="Recommended action")
    priority: int = Field(..., ge=1, le=5, description="Priority 1-5")
    rationale: str = Field(..., description="Why this action is recommended")


class TriageResponse(BaseModel):
    """
    Output model for LLM alert triage analysis.

    This is the structured response returned to Shuffle/TheHive.
    """
    alert_id: str
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Core Assessment
    severity: SeverityLevel = Field(..., description="AI-assessed severity")
    category: AlertCategory = Field(..., description="Alert category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")

    # Analysis
    summary: str = Field(..., description="Human-readable summary")
    detailed_analysis: str = Field(..., description="In-depth technical analysis")
    potential_impact: str = Field(..., description="Business/security impact")

    # Threat Intelligence
    is_true_positive: bool = Field(..., description="True positive vs false positive")
    false_positive_reason: Optional[str] = Field(None, description="Why this is a false positive")

    # IOCs and Artifacts
    iocs: List[IOC] = Field(default_factory=list, description="Extracted IOCs")

    # MITRE ATT&CK Mapping
    mitre_techniques: List[str] = Field(default_factory=list, description="Mapped MITRE techniques")
    mitre_tactics: List[str] = Field(default_factory=list, description="MITRE tactics")

    # Recommendations
    recommendations: List[TriageRecommendation] = Field(..., description="Prioritized actions")

    # Investigation Context
    investigation_priority: int = Field(..., ge=1, le=5, description="Investigation urgency")
    estimated_analyst_time: Optional[int] = Field(None, description="Est. minutes to investigate")

    # RAG Context (if enabled)
    similar_incidents: Optional[List[str]] = Field(None, description="Similar past incidents")
    knowledge_base_references: Optional[List[str]] = Field(None, description="Relevant KB articles")

    # Model Metadata
    model_used: str = Field(..., description="LLM model identifier")
    processing_time_ms: Optional[int] = Field(None, description="Analysis duration")

    # ML Inference Metadata (Phase 3 integration)
    ml_prediction: Optional[str] = Field(None, description="ML model prediction")
    ml_confidence: Optional[float] = Field(None, description="ML model confidence")

    class Config:
        json_schema_extra = {
            "example": {
                "alert_id": "wazuh-001-20250113-1234",
                "severity": "high",
                "category": "intrusion_attempt",
                "confidence": 0.92,
                "summary": "Multiple failed SSH login attempts detected from 203.0.113.42",
                "is_true_positive": True,
                "investigation_priority": 2,
                "model_used": "foundation-sec-8b"
            }
        }


class HealthResponse(BaseModel):
    """Service health check response"""
    status: str
    service: str
    version: str
    ollama_connected: bool
    ml_api_connected: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)
