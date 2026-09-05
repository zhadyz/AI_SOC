"""Contracts at the authentication, data, callback and retrieval boundaries."""

import pickle
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from services.common.api_security import protect_app
from services.alert_triage import llm_client
from services.alert_triage.main import analyze_async
from services.alert_triage.ml_client import MLInferenceClient, CICIDS2017_FEATURES
from services.alert_triage.models import SecurityAlert
from services.correlation_engine.correlator import _get_highest_stage
from services.correlation_engine.models import KillChainStage


@pytest.mark.parametrize("authorization", [None, "Bearer wrong", "Token test-secret"])
def test_api_requires_correct_bearer(monkeypatch, authorization):
    monkeypatch.setenv("AI_SOC_API_KEY", "test-secret")
    app = FastAPI()
    protect_app(app)
    app.get("/health")(lambda: {"status": "healthy"})
    app.post("/action")(lambda: {"accepted": True})
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    headers = {"Authorization": authorization} if authorization else {}
    assert client.post("/action", headers=headers).status_code == 401
    assert (
        client.post(
            "/action", headers={"Authorization": "Bearer test-secret"}
        ).status_code
        == 200
    )


def test_triage_feature_order_matches_bundled_training_artifact():
    root = Path(__file__).resolve().parents[2]
    with (root / "models/feature_names.pkl").open("rb") as source:
        assert list(pickle.load(source)) == CICIDS2017_FEATURES


@pytest.mark.parametrize("tactic", ["TA0006", "Credential Access", "credential_access", "credential-access"])
def test_tactic_ids_and_names_correlate_to_same_stage(tactic):
    assert _get_highest_stage([tactic]) == KillChainStage.PRIVILEGE_ESCALATION


def test_metadata_and_incomplete_flows_are_not_fabricated():
    client = MLInferenceClient("http://unused")
    alert = SimpleNamespace(full_log={"rule_level": 12, "dest_port": 443})
    assert client._extract_network_features(alert) is None
    alert.full_log = {"network_flow": dict.fromkeys(CICIDS2017_FEATURES[:20], 1)}
    assert client._extract_network_features(alert) is None
    alert.full_log = {"network_flow": dict.fromkeys(CICIDS2017_FEATURES, 0)}
    assert client._extract_network_features(alert)["features"] == [0.0] * 77
    alert.full_log["network_flow"]["Protocol"] = float("nan")
    assert client._extract_network_features(alert) is None


async def test_callbacks_rejected_before_queuing(sample_security_alert):
    with pytest.raises(HTTPException) as error:
        await analyze_async(
            SecurityAlert(**sample_security_alert), "http://169.254.169.254/latest"
        )
    assert error.value.status_code == 422


async def test_retrieved_evidence_and_sources_reach_triage(
    sample_security_alert, monkeypatch
):
    monkeypatch.setattr(llm_client.settings, "rag_enabled", True)
    monkeypatch.setattr(llm_client.settings, "rag_service_url", "http://rag")

    def respond(request):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "document": "Use SSH authentication logs",
                        "metadata": {"source": "runbook.md"},
                    }
                ]
            },
        )

    monkeypatch.setattr(
        llm_client,
        "service_client",
        lambda **kwargs: httpx.AsyncClient(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    )
    text, sources, warnings = await llm_client.OllamaClient().get_rag_context(
        SecurityAlert(**sample_security_alert)
    )
    assert "Use SSH authentication logs" in text
    assert sources == ["runbook.md"] and not warnings


async def test_rag_failure_is_explicit_and_does_not_invent_evidence(
    sample_security_alert, monkeypatch
):
    monkeypatch.setattr(llm_client.settings, "rag_enabled", True)
    monkeypatch.setattr(llm_client.settings, "rag_service_url", "http://rag")
    monkeypatch.setattr(
        llm_client,
        "service_client",
        lambda **kwargs: httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(503)), **kwargs
        ),
    )
    text, sources, warnings = await llm_client.OllamaClient().get_rag_context(
        SecurityAlert(**sample_security_alert)
    )
    assert not text and not sources and len(warnings) == 2
