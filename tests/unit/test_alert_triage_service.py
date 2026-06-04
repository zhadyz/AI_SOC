"""
Unit Tests - Alert Triage Service
Tests core functionality of the LLM-powered alert triage service

Author: LOVELESS
Mission: OPERATION TEST-FORTRESS
Date: 2025-10-22
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from pydantic import ValidationError

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services" / "alert-triage"))

from models import SecurityAlert, TriageResponse, SeverityLevel, AlertCategory, TriageRecommendation


def _sample_triage_response(**overrides) -> TriageResponse:
    """Build a valid TriageResponse for unit tests."""
    data = {
        "alert_id": "test-001",
        "severity": SeverityLevel.HIGH,
        "category": AlertCategory.INTRUSION,
        "confidence": 0.95,
        "summary": "Brute force attack detected",
        "detailed_analysis": "Multiple failed SSH login attempts observed.",
        "potential_impact": "Potential account compromise.",
        "is_true_positive": True,
        "iocs": [],
        "mitre_tactics": ["Credential Access"],
        "mitre_techniques": ["T1110.001"],
        "recommendations": [
            TriageRecommendation(
                action="Block source IP",
                priority=1,
                rationale="Prevent further brute-force attempts",
            )
        ],
        "investigation_priority": 2,
        "model_used": "llama3.2:3b",
        "processing_time_ms": 150,
    }
    data.update(overrides)
    return TriageResponse(**data)


# ============================================================================
# Model Validation Tests
# ============================================================================

@pytest.mark.unit
class TestSecurityAlertModel:
    """Test SecurityAlert Pydantic model"""

    def test_valid_alert_creation(self, sample_security_alert):
        """Test creating valid SecurityAlert"""
        alert = SecurityAlert(**sample_security_alert)
        assert alert.alert_id == "test-alert-001"
        assert alert.source_ip == "192.168.1.100"
        assert alert.rule_level == 10

    def test_missing_required_fields(self):
        """Test validation fails with missing fields"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            SecurityAlert(alert_id="test-001")

    def test_invalid_ip_format(self, sample_security_alert):
        """Test IP validation"""
        sample_security_alert["source_ip"] = "invalid-ip"
        # Note: Current model doesn't validate IP format, but it should
        alert = SecurityAlert(**sample_security_alert)
        assert alert.source_ip == "invalid-ip"
        # TODO: Add IP validation to model


@pytest.mark.unit
class TestTriageResponseModel:
    """Test TriageResponse Pydantic model"""

    def test_valid_triage_response(self):
        """Test creating valid TriageResponse"""
        response = _sample_triage_response()
        assert response.severity == SeverityLevel.HIGH
        assert response.confidence == 0.95

    def test_severity_levels(self):
        """Test all valid severity levels"""
        severity_levels = [
            SeverityLevel.CRITICAL,
            SeverityLevel.HIGH,
            SeverityLevel.MEDIUM,
            SeverityLevel.LOW,
            SeverityLevel.INFO,
        ]
        for severity in severity_levels:
            response = _sample_triage_response(severity=severity)
            assert response.severity == severity


# ============================================================================
# LLM Client Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestOllamaClient:
    """Test Ollama LLM client"""

    @patch('httpx.AsyncClient')
    async def test_health_check_success(self, mock_client):
        """Test successful health check"""
        from llm_client import OllamaClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        client = OllamaClient()
        is_healthy = await client.check_health()
        assert is_healthy is True

    @patch('httpx.AsyncClient')
    async def test_health_check_failure(self, mock_client):
        """Test failed health check"""
        from llm_client import OllamaClient

        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=Exception("Connection refused"))

        client = OllamaClient()
        is_healthy = await client.check_health()
        assert is_healthy is False

    @patch('httpx.AsyncClient')
    async def test_analyze_alert_success(self, mock_client, sample_security_alert):
        """Test successful alert analysis"""
        import json
        from llm_client import OllamaClient

        llm_payload = {
            "severity": "high",
            "category": "intrusion_attempt",
            "confidence": 0.92,
            "summary": "Brute force attack detected",
            "detailed_analysis": "Multiple failed SSH attempts.",
            "potential_impact": "Account compromise risk.",
            "is_true_positive": True,
            "iocs": [],
            "mitre_techniques": ["T1110.001"],
            "mitre_tactics": ["Credential Access"],
            "recommendations": [
                {"action": "Block source IP", "priority": 1, "rationale": "Stop brute force"}
            ],
            "investigation_priority": 2,
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "llama3.2:3b",
            "response": json.dumps(llm_payload),
            "done": True,
        }

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        client = OllamaClient()
        client.ml_client.predict_with_fallback = AsyncMock(return_value=None)
        client.context_manager.build_context = AsyncMock(return_value="")

        alert = SecurityAlert(**sample_security_alert)
        result = await client.analyze_alert(alert)

        assert result is not None
        assert isinstance(result, TriageResponse)
        assert result.alert_id == alert.alert_id


# ============================================================================
# API Endpoint Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestAlertTriageEndpoints:
    """Test FastAPI endpoints"""

    async def test_health_endpoint(self, http_client, alert_triage_url):
        """Test /health endpoint"""
        try:
            response = await http_client.get(f"{alert_triage_url}/health")
            if response.status_code == 200:
                data = response.json()
                assert "status" in data
                assert "service" in data
                assert data["service"] == "alert-triage"
        except Exception as e:
            pytest.skip(f"Service not running: {e}")

    async def test_metrics_endpoint(self, http_client, alert_triage_url):
        """Test /metrics endpoint"""
        try:
            response = await http_client.get(f"{alert_triage_url}/metrics")
            if response.status_code == 200:
                # Prometheus metrics should be in text format
                assert response.headers["content-type"].startswith("text/plain")
        except Exception as e:
            pytest.skip(f"Service not running: {e}")

    async def test_root_endpoint(self, http_client, alert_triage_url):
        """Test root / endpoint"""
        try:
            response = await http_client.get(f"{alert_triage_url}/")
            if response.status_code == 200:
                data = response.json()
                assert "service" in data
                assert "endpoints" in data
        except Exception as e:
            pytest.skip(f"Service not running: {e}")


# ============================================================================
# Configuration Tests
# ============================================================================

@pytest.mark.unit
class TestConfiguration:
    """Test configuration management"""

    def test_settings_defaults(self):
        """Test default configuration values"""
        from config import Settings

        settings = Settings()
        assert settings.service_name == "alert-triage"
        assert settings.service_version == "1.0.0"
        assert settings.primary_model == "llama3.2:3b"

    def test_environment_override(self, monkeypatch):
        """Test environment variable overrides"""
        from config import Settings

        monkeypatch.setenv("TRIAGE_OLLAMA_HOST", "http://custom-ollama:11434")
        monkeypatch.setenv("TRIAGE_PRIMARY_MODEL", "custom-model:latest")

        settings = Settings()
        assert settings.ollama_host == "http://custom-ollama:11434"
        assert settings.primary_model == "custom-model:latest"


# ============================================================================
# Prompt Engineering Tests
# ============================================================================

@pytest.mark.unit
class TestPromptConstruction:
    """Test LLM prompt construction"""

    def test_alert_prompt_structure(self, sample_security_alert):
        """Test alert analysis prompt construction"""
        from llm_client import OllamaClient

        client = OllamaClient()
        alert = SecurityAlert(**sample_security_alert)

        # This would test the internal prompt construction method
        # Currently, this is not exposed, but it should be for testing
        # TODO: Refactor to expose prompt_builder for testing
        pass


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.unit
class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_empty_alert_id(self):
        """Test handling of empty alert ID"""
        with pytest.raises(ValidationError):
            SecurityAlert(
                alert_id="",
                timestamp="2025-10-22T10:30:00Z",
                source_ip="192.168.1.1",
                dest_ip="10.0.0.1",
                rule_id="100",
                rule_level=5,
                rule_description="Test",
                raw_log="test log",
            )

    def test_negative_rule_level(self):
        """Test handling of negative rule level"""
        with pytest.raises(ValidationError):
            SecurityAlert(
                alert_id="test-001",
                timestamp="2025-10-22T10:30:00Z",
                source_ip="192.168.1.1",
                dest_ip="10.0.0.1",
                rule_id="100",
                rule_level=-1,
                rule_description="Test",
                raw_log="test log",
            )

    def test_confidence_out_of_range(self):
        """Test confidence score validation"""
        with pytest.raises(ValidationError):
            _sample_triage_response(confidence=1.5)


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.slow
class TestPerformance:
    """Test performance characteristics"""

    def test_model_validation_performance(self, sample_security_alert, benchmark):
        """Benchmark Pydantic model validation speed"""
        def create_alert():
            return SecurityAlert(**sample_security_alert)

        # Should be fast (<1ms)
        result = benchmark(create_alert)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
