import json
import httpx
import pytest
from fastapi import HTTPException
from services.rule_generator import main
from services.rule_generator.sigma import backtest


def fake_draft(monkeypatch, field, value):
    draft = {
        "title": "Failed logon",
        "description": "Observed logon failure",
        "filters": [{"field": field, "value": value, "modifier": "equals"}],
    }

    def response(request):
        # Models can repeat an identical constraint; normalize it safely.
        draft["filters"] = draft["filters"][:1] * 2
        schema = json.loads(request.content)["format"]
        assert schema["properties"]["filters"]["maxItems"] == 1
        assert schema["$defs"]["DetectionFilter"]["properties"]["field"]["enum"] == [
            "EventID"
        ]
        return httpx.Response(200, json={"response": json.dumps(draft)})

    monkeypatch.setattr(
        main,
        "service_client",
        lambda **kwargs: httpx.AsyncClient(
            transport=httpx.MockTransport(response), **kwargs
        ),
    )


async def test_generated_rule_uses_observed_event(monkeypatch):
    fake_draft(monkeypatch, "EventID", 4625)
    request = main.RuleGenerationRequest(
        alert_id="sample",
        alert_description="Failed logon",
        sample_event={"EventID": 4625},
        logsource={"product": "windows", "service": "security"},
    )
    rule = await main.generate_sigma_rule(request)
    result = backtest(
        rule,
        [
            {"event": {"EventID": 4625}, "label": "ATTACK"},
            {"event": {"EventID": 4624}, "label": "BENIGN"},
        ],
    )
    assert result["matches"] == 1 and result["false_positive_rate"] == 0


@pytest.mark.parametrize(
    "field,value", [("InventedField", "fiction"), ("EventID", 9999)]
)
async def test_unobserved_filters_are_discarded_for_labeled_exact_sample_fallback(
    monkeypatch, field, value
):
    fake_draft(monkeypatch, field, value)
    rule = await main.generate_sigma_rule(
        main.RuleGenerationRequest(
            alert_id="sample",
            alert_description="Failed logon",
            sample_event={"EventID": 4625},
        )
    )
    assert rule.startswith("# generation_method: evidence_fallback")
    assert "InventedField" not in rule and "9999" not in rule
    result = backtest(
        rule,
        [
            {"event": {"EventID": 4625}, "label": "ATTACK"},
            {"event": {"EventID": 4624}, "label": "BENIGN"},
        ],
    )
    assert result["matches"] == 1 and result["false_positive_rate"] == 0
