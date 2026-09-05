"""
Unit Tests for Pydantic Models
Alert Triage Service
"""

import pytest
from datetime import datetime
from services.alert_triage.models import (
    SecurityAlert,
    TriageResponse,
    SeverityLevel,
    AlertCategory,
    IOC,
    TriageRecommendation,
    HealthResponse
)


def test_security_alert_minimal():
    """Test SecurityAlert with minimal required fields"""
    alert = SecurityAlert(
        alert_id="test-001",
        rule_description="Test alert",
        rule_level=5
    )

    assert alert.alert_id == "test-001"
    assert alert.rule_description == "Test alert"
    assert alert.rule_level == 5
    assert isinstance(alert.timestamp, datetime)


def test_security_alert_full():
    """Test SecurityAlert with all fields populated"""
    alert = SecurityAlert(
        alert_id="test-002",
        timestamp=datetime.now(),
        rule_id="5710",
        rule_description="SSH brute force",
        rule_level=10,
        source_ip="203.0.113.42",
        source_port=54321,
        dest_ip="10.0.1.50",
        dest_port=22,
        user="admin",
        process="sshd",
        raw_log="Failed password for admin from 203.0.113.42"
    )

    assert alert.source_ip == "203.0.113.42"
    assert alert.dest_port == 22
    assert alert.user == "admin"


def test_security_alert_validation():
    """Test SecurityAlert validation errors"""
    with pytest.raises(ValueError):
        # rule_level must be 0-15
        SecurityAlert(
            alert_id="test-003",
            rule_description="Invalid level",
            rule_level=20  # Invalid
        )


def test_ioc_creation():
    """Test IOC model"""
    ioc = IOC(
        ioc_type="ip",
        value="203.0.113.42",
        confidence=0.95
    )

    assert ioc.ioc_type == "ip"
    assert ioc.value == "203.0.113.42"
    assert ioc.confidence == 0.95


def test_ioc_validation():
    """Test IOC confidence validation"""
    with pytest.raises(ValueError):
        # Confidence must be 0.0-1.0
        IOC(ioc_type="ip", value="1.2.3.4", confidence=1.5)


def test_triage_recommendation():
    """Test TriageRecommendation model"""
    rec = TriageRecommendation(
        action="Block source IP at firewall",
        priority=1,
        rationale="Prevent continued brute force attempts"
    )

    assert rec.action == "Block source IP at firewall"
    assert rec.priority == 1


def test_triage_response_minimal():
    """Test TriageResponse with minimal fields"""
    response = TriageResponse(
        alert_id="test-001",
        severity=SeverityLevel.HIGH,
        category=AlertCategory.INTRUSION,
        confidence=0.92,
        summary="SSH brute force detected",
        detailed_analysis="Multiple failed login attempts",
        potential_impact="Account compromise risk",
        is_true_positive=True,
        recommendations=[
            TriageRecommendation(
                action="Block IP",
                priority=1,
                rationale="Stop attack"
            )
        ],
        investigation_priority=2,
        model_used="foundation-sec-8b"
    )

    assert response.severity == SeverityLevel.HIGH
    assert response.category == AlertCategory.INTRUSION
    assert response.confidence == 0.92
    assert len(response.recommendations) == 1


def test_triage_response_with_ml():
    """Test TriageResponse with ML metadata"""
    response = TriageResponse(
        alert_id="test-002",
        severity=SeverityLevel.CRITICAL,
        category=AlertCategory.MALWARE,
        confidence=0.88,
        summary="Malware detected",
        detailed_analysis="Suspicious process execution",
        potential_impact="System compromise",
        is_true_positive=True,
        recommendations=[],
        investigation_priority=1,
        model_used="llama3.1:8b",
        ml_prediction="DoS",
        ml_confidence=0.94
    )

    assert response.ml_prediction == "DoS"
    assert response.ml_confidence == 0.94


def test_health_response():
    """Test HealthResponse model"""
    health = HealthResponse(
        status="healthy",
        service="alert-triage",
        version="1.0.0",
        ollama_connected=True,
        ml_api_connected=True
    )

    assert health.status == "healthy"
    assert health.ollama_connected is True
    assert isinstance(health.timestamp, datetime)


def test_severity_levels():
    """Test all severity level enum values"""
    assert SeverityLevel.CRITICAL.value == "critical"
    assert SeverityLevel.HIGH.value == "high"
    assert SeverityLevel.MEDIUM.value == "medium"
    assert SeverityLevel.LOW.value == "low"
    assert SeverityLevel.INFO.value == "informational"


def test_alert_categories():
    """Test all alert category enum values"""
    assert AlertCategory.MALWARE.value == "malware"
    assert AlertCategory.INTRUSION.value == "intrusion_attempt"
    assert AlertCategory.DATA_EXFILTRATION.value == "data_exfiltration"
    assert AlertCategory.PRIVILEGE_ESCALATION.value == "privilege_escalation"
