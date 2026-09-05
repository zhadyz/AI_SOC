"""
Unit Tests for Ollama LLM Client
Alert Triage Service
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from services.alert_triage.llm_client import OllamaClient
from services.alert_triage.models import SecurityAlert, SeverityLevel, AlertCategory


@pytest.fixture
def llm_client():
    """Create LLM client for testing"""
    with patch("services.alert_triage.llm_client.MLInferenceClient"):
        return OllamaClient()


@pytest.fixture
def sample_alert():
    """Create sample security alert"""
    return SecurityAlert(
        alert_id="test-001",
        rule_id="5710",
        rule_description="SSH brute force attempt",
        rule_level=10,
        source_ip="203.0.113.42",
        dest_ip="10.0.1.50",
        user="admin",
        raw_log="Failed password for admin from 203.0.113.42"
    )


@pytest.mark.asyncio
async def test_check_health_success(llm_client):
    """Test Ollama health check when service is available"""
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        result = await llm_client.check_health()

        assert result is True


@pytest.mark.asyncio
async def test_check_health_failure(llm_client):
    """Test Ollama health check when service is unavailable"""
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        result = await llm_client.check_health()

        assert result is False


def test_build_triage_prompt(llm_client, sample_alert):
    """Test prompt generation for alert triage"""
    prompt = llm_client._build_triage_prompt(sample_alert)

    # Verify key elements are in prompt
    assert "cybersecurity analyst" in prompt.lower()
    assert sample_alert.alert_id in prompt
    assert sample_alert.rule_description in prompt
    assert sample_alert.source_ip in prompt
    assert "OUTPUT FORMAT (JSON)" in prompt
    assert "severity" in prompt.lower()
    assert "mitre" in prompt.lower()


@pytest.mark.asyncio
async def test_call_ollama_success(llm_client):
    """Test successful Ollama API call"""
    mock_response_data = {
        "response": '{"severity": "high", "category": "intrusion_attempt"}'
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=mock_response_data)

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        result = await llm_client._call_ollama(
            prompt="Test prompt",
            model="test-model"
        )

        assert result == '{"severity": "high", "category": "intrusion_attempt"}'


@pytest.mark.asyncio
async def test_call_ollama_timeout(llm_client):
    """Test Ollama API call timeout"""
    with patch("httpx.AsyncClient") as mock_client:
        import httpx
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        result = await llm_client._call_ollama(
            prompt="Test prompt",
            model="test-model"
        )

        assert result is None


def test_parse_llm_response_success(llm_client, sample_alert):
    """Test parsing valid LLM JSON response"""
    llm_output = json.dumps({
        "severity": "high",
        "category": "intrusion_attempt",
        "confidence": 0.92,
        "summary": "SSH brute force attack detected",
        "detailed_analysis": "Multiple failed authentication attempts",
        "potential_impact": "Account compromise risk",
        "is_true_positive": True,
        "iocs": [{"ioc_type": "ip", "value": "203.0.113.42", "confidence": 0.95}],
        "mitre_techniques": ["T1110.001"],
        "mitre_tactics": ["TA0006"],
        "recommendations": [
            {"action": "Block IP", "priority": 1, "rationale": "Stop attack"}
        ],
        "investigation_priority": 2
    })

    result = llm_client._parse_llm_response(
        sample_alert,
        llm_output,
        "foundation-sec-8b"
    )

    assert result is not None
    assert result.alert_id == "test-001"
    assert result.severity == SeverityLevel.HIGH
    assert result.category == AlertCategory.INTRUSION
    assert result.confidence == 0.92
    assert len(result.iocs) == 1
    assert len(result.recommendations) == 1


def test_parse_llm_response_markdown_codeblock(llm_client, sample_alert):
    """Test parsing LLM response wrapped in markdown code block"""
    llm_output = """```json
{
    "severity": "medium",
    "category": "anomaly",
    "confidence": 0.75,
    "summary": "Test",
    "detailed_analysis": "Test",
    "potential_impact": "Test",
    "is_true_positive": true,
    "iocs": [],
    "mitre_techniques": [],
    "mitre_tactics": [],
    "recommendations": [],
    "investigation_priority": 3
}
```"""

    result = llm_client._parse_llm_response(
        sample_alert,
        llm_output,
        "llama3.1:8b"
    )

    assert result is not None
    assert result.severity == SeverityLevel.MEDIUM
    assert result.confidence == 0.75


def test_parse_llm_response_invalid_json(llm_client, sample_alert):
    """Test parsing invalid JSON returns None"""
    llm_output = "This is not valid JSON"

    result = llm_client._parse_llm_response(
        sample_alert,
        llm_output,
        "test-model"
    )

    assert result is None


@pytest.mark.asyncio
async def test_analyze_alert_success(llm_client, sample_alert):
    """Test full alert analysis workflow"""
    mock_llm_response = json.dumps({
        "severity": "high",
        "category": "intrusion_attempt",
        "confidence": 0.88,
        "summary": "Brute force attack",
        "detailed_analysis": "Analysis",
        "potential_impact": "Impact",
        "is_true_positive": True,
        "iocs": [],
        "mitre_techniques": [],
        "mitre_tactics": [],
        "recommendations": [],
        "investigation_priority": 2
    })

    llm_client.ml_client.predict_with_fallback = AsyncMock(return_value=None)
    llm_client._call_ollama = AsyncMock(return_value=mock_llm_response)

    result = await llm_client.analyze_alert(sample_alert)

    assert result is not None
    assert result.alert_id == "test-001"
    assert result.severity == SeverityLevel.HIGH
    assert result.model_used == llm_client.primary_model


@pytest.mark.asyncio
async def test_analyze_alert_with_ml(llm_client, sample_alert):
    """Test alert analysis with ML prediction enrichment"""
    from services.alert_triage.ml_client import MLPrediction

    mock_ml_prediction = MLPrediction(
        prediction="DoS",
        confidence=0.94,
        probabilities={"DoS": 0.94, "Normal": 0.06},
        model_used="random_forest",
        inference_time_ms=15.2
    )

    mock_llm_response = json.dumps({
        "severity": "critical",
        "category": "intrusion_attempt",
        "confidence": 0.95,
        "summary": "DDoS attack detected",
        "detailed_analysis": "ML predicted DoS attack",
        "potential_impact": "Service disruption",
        "is_true_positive": True,
        "iocs": [],
        "mitre_techniques": [],
        "mitre_tactics": [],
        "recommendations": [],
        "investigation_priority": 1
    })

    llm_client.ml_client.predict_with_fallback = AsyncMock(
        return_value=mock_ml_prediction
    )
    llm_client._call_ollama = AsyncMock(return_value=mock_llm_response)

    result = await llm_client.analyze_alert(sample_alert)

    assert result is not None
    assert result.ml_prediction == "DoS"
    assert result.ml_confidence == 0.94
