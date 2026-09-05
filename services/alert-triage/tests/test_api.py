"""
Integration Tests for FastAPI Endpoints
Alert Triage Service
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.alert_triage.main import app
from services.alert_triage.models import SecurityAlert, TriageResponse, SeverityLevel, AlertCategory

client = TestClient(app)


def test_root_endpoint():
    """Test GET / returns service information"""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert data["service"] == "alert-triage"
    assert "version" in data
    assert "endpoints" in data
    assert "models" in data


def test_health_endpoint_healthy():
    """Test GET /health when services are connected"""
    with patch("services.alert_triage.main.llm_client") as mock_llm:
        mock_llm.check_health = AsyncMock(return_value=True)
        mock_llm.ml_client.check_health = AsyncMock(return_value=True)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] in ["healthy", "degraded", "partial"]
        assert "service" in data
        assert "ollama_connected" in data


def test_health_endpoint_degraded():
    """Test GET /health when Ollama is disconnected"""
    with patch("services.alert_triage.main.llm_client") as mock_llm:
        mock_llm.check_health = AsyncMock(return_value=False)
        mock_llm.ml_client.check_health = AsyncMock(return_value=False)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"


def test_metrics_endpoint():
    """Test GET /metrics returns Prometheus metrics"""
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_analyze_endpoint_success():
    """Test POST /analyze with successful analysis"""
    # Mock LLM response
    mock_triage = TriageResponse(
        alert_id="test-001",
        severity=SeverityLevel.HIGH,
        category=AlertCategory.INTRUSION,
        confidence=0.92,
        summary="SSH brute force attack",
        detailed_analysis="Multiple failed authentication attempts",
        potential_impact="Account compromise",
        is_true_positive=True,
        recommendations=[],
        investigation_priority=2,
        model_used="foundation-sec-8b"
    )

    with patch("services.alert_triage.main.llm_client") as mock_llm:
        mock_llm.analyze_alert = AsyncMock(return_value=mock_triage)

        alert_data = {
            "alert_id": "test-001",
            "rule_description": "SSH brute force",
            "rule_level": 10,
            "source_ip": "203.0.113.42",
            "dest_ip": "10.0.1.50"
        }

        response = client.post("/analyze", json=alert_data)

        assert response.status_code == 200
        data = response.json()

        assert data["alert_id"] == "test-001"
        assert data["severity"] == "high"
        assert data["confidence"] == 0.92


def test_analyze_endpoint_llm_failure():
    """Test POST /analyze when LLM analysis fails"""
    with patch("services.alert_triage.main.llm_client") as mock_llm:
        mock_llm.analyze_alert = AsyncMock(return_value=None)

        alert_data = {
            "alert_id": "test-002",
            "rule_description": "Test alert",
            "rule_level": 5
        }

        response = client.post("/analyze", json=alert_data)

        assert response.status_code == 503
        assert "LLM analysis failed" in response.json()["detail"]


def test_analyze_endpoint_invalid_input():
    """Test POST /analyze with invalid input"""
    invalid_data = {
        "alert_id": "test-003",
        "rule_level": 20  # Invalid: must be 0-15
    }

    response = client.post("/analyze", json=invalid_data)

    assert response.status_code == 422  # Validation error


def test_batch_endpoint_success():
    """Test POST /batch with successful batch analysis"""
    mock_triage = TriageResponse(
        alert_id="test-batch-001",
        severity=SeverityLevel.MEDIUM,
        category=AlertCategory.ANOMALY,
        confidence=0.75,
        summary="Test analysis",
        detailed_analysis="Test",
        potential_impact="Test",
        is_true_positive=True,
        recommendations=[],
        investigation_priority=3,
        model_used="llama3.1:8b"
    )

    with patch("services.alert_triage.main.llm_client") as mock_llm:
        mock_llm.analyze_alert = AsyncMock(return_value=mock_triage)

        alerts_data = [
            {
                "alert_id": f"test-batch-{i:03d}",
                "rule_description": f"Test alert {i}",
                "rule_level": 5
            }
            for i in range(3)
        ]

        response = client.post("/batch", json=alerts_data)

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert data["successful"] == 3
        assert data["failed"] == 0
        assert len(data["results"]) == 3


def test_batch_endpoint_empty():
    """Test POST /batch with empty alert list"""
    response = client.post("/batch", json=[])

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 0
    assert data["successful"] == 0


def test_batch_endpoint_partial_failure():
    """Test POST /batch with some alerts failing"""
    def mock_analyze(alert):
        # Fail on second alert
        if "002" in alert.alert_id:
            return None
        return TriageResponse(
            alert_id=alert.alert_id,
            severity=SeverityLevel.LOW,
            category=AlertCategory.OTHER,
            confidence=0.5,
            summary="Test",
            detailed_analysis="Test",
            potential_impact="Test",
            is_true_positive=True,
            recommendations=[],
            investigation_priority=4,
            model_used="test"
        )

    with patch("services.alert_triage.main.llm_client") as mock_llm:
        mock_llm.analyze_alert = AsyncMock(side_effect=mock_analyze)

        alerts_data = [
            {"alert_id": f"test-{i:03d}", "rule_description": "Test", "rule_level": 5}
            for i in range(3)
        ]

        response = client.post("/batch", json=alerts_data)

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert data["successful"] == 2
        assert data["failed"] == 1


@pytest.fixture(autouse=True)
def external_pipeline_dependencies(monkeypatch):
    from services.alert_triage import main
    monkeypatch.setattr(main, "_persist_alert", AsyncMock())
    monkeypatch.setattr(main, "_correlate_alert", AsyncMock())
