"""The Wazuh receiver must not acknowledge work absent durable admission."""
import httpx
import pytest
from fastapi.testclient import TestClient

from services.wazuh_integration import ai_client, main


EVENT = {'id': 'controlled-test', 'timestamp': '2026-09-04T12:00:00Z',
         'rule': {'id': '100100', 'level': 10, 'description': 'Controlled fixture'},
         'data': {'srcip': '172.30.77.20'}}


@pytest.mark.parametrize('downstream,payload,expected', [
    (202, {'job_id': 'durably-stored', 'status': 'queued'}, 202),
    (200, {'job_id': 'not-an-admission'}, 503),
    (202, {}, 503),
    (429, {'detail': 'full'}, 429),
    (503, {'detail': 'disk unavailable'}, 503),
])
def test_webhook_requires_confirmed_admission(monkeypatch, downstream, payload, expected):
    monkeypatch.setenv('AI_SOC_API_KEY', 'test-key')
    def handle(request):
        assert request.url.path == '/analyze/async'
        assert b'controlled-test' in request.content
        return httpx.Response(downstream, json=payload)
    monkeypatch.setattr(ai_client, 'service_client', lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handle), **kw))
    # Keep real application lifespan and real queue client; replace only transport.
    with TestClient(main.app) as client:
        response = client.post('/webhook/async', headers={'Authorization': 'Bearer test-key'}, json=EVENT)
    assert response.status_code == expected
    if expected == 202:
        assert response.json()['wazuh_alert_id'] == EVENT['id']


def test_low_severity_is_filtered_before_admission(monkeypatch):
    monkeypatch.setenv('AI_SOC_API_KEY', 'test-key')
    with TestClient(main.app) as client:
        response = client.post('/webhook/async', headers={'Authorization': 'Bearer test-key'},
                               json={**EVENT, 'rule': {**EVENT['rule'], 'level': 2}})
    assert response.status_code == 400
