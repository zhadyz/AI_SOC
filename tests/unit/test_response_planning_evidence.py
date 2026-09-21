"""Do not manufacture response targets or claims when evidence is missing."""

from types import SimpleNamespace
import pytest
from services.response_orchestrator.planner import DefensePlanner
from services.response_orchestrator.models import ActionType


@pytest.mark.parametrize(
    "action",
    [
        ActionType.BLOCK_IP,
        ActionType.SINKHOLE_DOMAIN,
        ActionType.DISABLE_ACCOUNT,
        ActionType.ENABLE_MFA,
    ],
)
def test_missing_targets_are_not_invented(action):
    planner = DefensePlanner()
    assert (
        planner._select_targets(
            SimpleNamespace(action_type=action), [], ["10.0.1.2"], None
        )
        == []
    )


def test_explicit_account_target_is_distinct_from_host_ip():
    planner = DefensePlanner()
    targets = planner._select_targets(
        SimpleNamespace(action_type=ActionType.DISABLE_ACCOUNT),
        [],
        ["10.0.1.2"],
        {"affected_accounts": ["lab-user"]},
    )
    assert targets == [("lab-user", "lab-user", "high")]


async def test_rationale_does_not_claim_reduction_without_evidence():
    result = await DefensePlanner()._generate_rationale(
        "test incident", ["T1110"], "initial_access", [], None
    )
    assert "No simulation evidence" in result
    assert "risk reduction is unknown" in result
    assert "%" not in result
