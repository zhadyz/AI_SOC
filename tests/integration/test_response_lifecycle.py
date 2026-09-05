"""Real persistence and state-machine regression tests with injected external effects."""
import asyncio
from unittest.mock import AsyncMock

import pytest

from services.response_orchestrator.adapters.base import AdapterResult
from services.response_orchestrator.adapters.wazuh import WazuhAdapter
from services.response_orchestrator.config import Settings
from services.response_orchestrator.models import (
    ActionStatus, ActionType, AdapterType, ApprovalTier, BlastRadius,
    DefensePlan, PlannedAction, PlanStatus,
)
from services.response_orchestrator.orchestrator import ResponseOrchestrator
from services.response_orchestrator.store import PlanStore
from services.response_orchestrator.verification import VerificationEngine


def action(tier=ApprovalTier.HUMAN_REQUIRED):
    return PlannedAction(action_id="act-1", action_type=ActionType.BLOCK_IP, target="203.0.113.5",
                         adapter=AdapterType.FIREWALL, confidence=.9, impact_score=.8, safety_score=.9,
                         composite_score=.85, blast_radius=BlastRadius.LOW, approval_tier=tier,
                         requires_approval=tier == ApprovalTier.HUMAN_REQUIRED,
                         parameters={"duration_hours": 1})


@pytest.fixture
async def store(tmp_path):
    instance = PlanStore(f"sqlite+aiosqlite:///{tmp_path}/plans.sqlite")
    await instance.initialize()
    yield instance
    await instance.close()


def make_orch(store, *, tier=ApprovalTier.HUMAN_REQUIRED):
    orch = ResponseOrchestrator(Settings(dry_run_mode=False, cooldown_between_actions_seconds=0,
                                         veto_window_seconds=1), store=store)
    plan = DefensePlan(plan_id="plan-1", incident_id="inc-1", actions=[action(tier)], total_actions=1, dry_run=False)
    orch._fetch_incident = AsyncMock(return_value={"mitre_techniques": ["T1110"]})
    orch.planner.generate_plan = AsyncMock(return_value=plan)
    orch._record_outcome = AsyncMock()
    adapter = orch._adapters["firewall"]
    adapter.execute = AsyncMock(return_value=AdapterResult(True, "block_ip", "203.0.113.5", "firewall",
                                                          "Test transport accepted", rollback_capable=False))
    return orch, plan, adapter


async def test_restart_preserves_plan_and_approval_audit(store):
    orch, plan, adapter = make_orch(store)
    await orch.trigger_defense("inc-1", dry_run=False, skip_simulation=True)
    assert plan.status == PlanStatus.AWAITING_APPROVAL
    restored = ResponseOrchestrator(orch.settings, store=store)
    await restored.restore()
    assert restored.get_plan("plan-1").actions[0].parameters == {"duration_hours": 1}
    restored._adapters["firewall"] = adapter
    await restored.approve_action("plan-1", "act-1", False, "analyst-1", "Wrong source")
    adapter.execute.assert_not_called()
    durable = (await store.load())[0]
    assert durable.actions[0].approved_by == "analyst-1"
    assert durable.actions[0].approval_notes == "Wrong source"
    assert durable.status == PlanStatus.CANCELLED
    assert any(e["event"] == "approval_decision" and not e["detail"]["approved"] for e in await store.events("plan-1"))


async def test_concurrent_approvals_execute_once_and_forward_parameters(store):
    orch, plan, adapter = make_orch(store)
    await orch.trigger_defense("inc-1", dry_run=False, skip_simulation=True)
    orch._verify_and_complete = AsyncMock()
    results = await asyncio.gather(
        orch.approve_action("plan-1", "act-1", True, "analyst-1"),
        orch.approve_action("plan-1", "act-1", True, "analyst-2"), return_exceptions=True)
    assert sum(isinstance(result, ValueError) for result in results) == 1
    adapter.execute.assert_awaited_once_with("block_ip", "203.0.113.5", {"duration_hours": 1})
    assert (await store.load())[0].actions[0].status == ActionStatus.COMPLETED
    await orch.close()


async def test_restart_does_not_replay_uncertain_remote_action(store):
    orch, plan, adapter = make_orch(store)
    plan.status = PlanStatus.EXECUTING
    plan.actions[0].status = ActionStatus.EXECUTING
    await store.save(plan, "action_intent")
    await orch.restore()
    assert orch.get_plan("plan-1").status == PlanStatus.RECOVERY_REQUIRED
    adapter.execute.assert_not_called()
    with pytest.raises(ValueError):
        await orch.approve_action("plan-1", "act-1", True, "analyst")


async def test_failed_intent_persistence_prevents_remote_execution(store, monkeypatch):
    orch, plan, adapter = make_orch(store)
    monkeypatch.setattr(store, "save", AsyncMock(side_effect=RuntimeError("database unavailable")))
    with pytest.raises(RuntimeError):
        await orch._execute_action(plan, plan.actions[0])
    adapter.execute.assert_not_called()


async def test_veto_window_can_stop_auto_action(store):
    orch, plan, adapter = make_orch(store, tier=ApprovalTier.AUTO_VETO)
    await orch.trigger_defense("inc-1", dry_run=False, auto_execute=True, skip_simulation=True)
    adapter.execute.assert_not_called()
    assert orch.get_pending_approvals()[0]["veto_deadline"]
    await orch.approve_action("plan-1", "act-1", False, "analyst")
    await asyncio.sleep(1.05)
    adapter.execute.assert_not_called()
    await orch.close()


async def test_auto_veto_executes_only_after_deadline(store):
    orch, plan, adapter = make_orch(store, tier=ApprovalTier.AUTO_VETO)
    orch._verify_and_complete = AsyncMock()
    await orch.trigger_defense("inc-1", dry_run=False, auto_execute=True, skip_simulation=True)
    adapter.execute.assert_not_called()
    await asyncio.sleep(1.05)
    adapter.execute.assert_awaited_once()
    await orch.close()


async def test_dry_run_has_no_execution_or_verification(store):
    orch, plan, adapter = make_orch(store)
    plan.dry_run = True
    await orch.trigger_defense("inc-1", dry_run=True, skip_simulation=True)
    assert plan.status == PlanStatus.DRY_RUN
    assert plan.actions[0].status == ActionStatus.SIMULATED
    assert plan.actions[0].executed_at is None
    assert plan.verification is None
    adapter.execute.assert_not_called()
    assert (await store.load())[0].status == PlanStatus.DRY_RUN


async def test_dependency_failure_does_not_claim_reduction_or_rollback(store):
    orch, plan, adapter = make_orch(store)
    plan.actions[0].status = ActionStatus.COMPLETED
    plan.pre_defense_risk = .8
    adapter.rollback = AsyncMock()
    await orch._verify_and_complete(plan)
    assert plan.status == PlanStatus.RECOVERY_REQUIRED
    assert not plan.verification.verification_passed
    assert not plan.verification.evidence_available
    assert plan.verification.risk_reduction_pct == 0
    adapter.rollback.assert_not_called()


async def test_verification_requires_both_evidence_sources():
    verifier = VerificationEngine()
    plan = DefensePlan(plan_id="p", incident_id="i", dry_run=False, pre_defense_risk=.8)
    verifier._track_resimulation = AsyncMock(return_value={"available": True, "simulation_id": "sim",
                                                         "pre_success_rate": .8, "post_success_rate": .2})
    verifier._track_monitoring = AsyncMock(return_value={"available": False, "error": "indexer down"})
    result = await verifier.verify_plan(plan)
    assert not result.verification_passed
    verifier._track_monitoring.return_value = {"available": True, "continued_indicators": False, "duration": 1800}
    result = await verifier.verify_plan(plan)
    assert result.verification_passed and result.evidence_available
    assert result.risk_reduction_pct == pytest.approx(.75)


async def test_wazuh_scoping_and_acknowledgement():
    adapter = WazuhAdapter(password="test", block_command="firewall-drop600")
    adapter._api_call = AsyncMock(return_value={"error": 0, "data": {"affected_items": ["001"]}})
    for scope in [[], ["all"], ["000"]]:
        assert not (await adapter.execute("block_ip", "203.0.113.5", {"agent_list": scope})).success
    adapter._api_call.assert_not_called()
    result = await adapter.execute("block_ip", "203.0.113.5", {"agent_list": ["001"]})
    assert result.success and not result.rollback_capable
    assert "unverified" in result.detail
    assert adapter._api_call.await_args.kwargs["params"]["agents_list"] == "001"
    adapter._api_call.return_value = {"data": {"affected_items": []}}
    assert not (await adapter.execute("block_ip", "203.0.113.5", {"agent_list": ["001"]})).success
