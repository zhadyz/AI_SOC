"""Additional triage contracts; endpoint/model/client tests also live with the service."""
import pytest
from pydantic import ValidationError

from services.alert_triage.config import Settings
from services.alert_triage.models import SecurityAlert
from services.response_orchestrator.config import Settings as ResponseSettings


def test_service_namespaces_are_independent():
    assert Settings().service_name == "alert-triage"
    assert ResponseSettings().service_name == "response-orchestrator"


def test_environment_override(monkeypatch):
    monkeypatch.setenv("TRIAGE_OLLAMA_HOST", "http://custom-ollama:11434")
    assert Settings().ollama_host == "http://custom-ollama:11434"
    assert ResponseSettings().ollama_host != "http://custom-ollama:11434"


@pytest.mark.parametrize("level", [-1, 16])
def test_invalid_rule_level(level):
    with pytest.raises(ValidationError):
        SecurityAlert(alert_id="invalid", rule_description="test", rule_level=level)


def test_default_response_is_dry_run():
    assert ResponseSettings().dry_run_mode
