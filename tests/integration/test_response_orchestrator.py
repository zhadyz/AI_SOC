"""
Integration Tests - Response Orchestrator
AI-Augmented SOC

Tests the full autonomous defense loop:
  D3FEND mapping → Safety model → Plan generation →
  Adapter dispatch → Verification logic

These tests are self-contained — they test the orchestrator's internal
logic without requiring external services (Wazuh, Ollama, PostgreSQL).
External calls are mocked.
"""

import asyncio
import sys
import os
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ORCHESTRATOR_DIR = Path(__file__).resolve().parents[2] / "services" / "response-orchestrator"


@pytest.fixture(scope="module", autouse=True)
def orchestrator_service_path():
    """Expose response-orchestrator imports without polluting other test modules."""
    conflicting = ("config", "models", "d3fend", "orchestrator", "planner", "safety")
    for module_name in conflicting:
        sys.modules.pop(module_name, None)

    path = str(ORCHESTRATOR_DIR)
    sys.path.insert(0, path)
    yield
    sys.path.remove(path)
    for module_name in conflicting:
        sys.modules.pop(module_name, None)


# ============================================================================
# D3FEND Integration Tests
# ============================================================================

class TestD3FENDMapping:
    """Test ATT&CK → D3FEND → concrete action mapping."""

    def test_brute_force_returns_countermeasures(self):
        from d3fend import get_countermeasures
        results = get_countermeasures("T1110")
        assert len(results) >= 3
        action_types = [r.action_type.value for r in results]
        assert "disable_account" in action_types  # AccountLocking
        assert "enable_mfa" in action_types        # MFA
        assert "block_ip" in action_types          # InboundTrafficFiltering

    def test_exploit_public_facing_returns_countermeasures(self):
        from d3fend import get_countermeasures
        results = get_countermeasures("T1190")
        assert len(results) >= 3
        action_types = [r.action_type.value for r in results]
        assert "patch_vulnerability" in action_types
        assert "isolate_host" in action_types

    def test_ransomware_returns_isolation_and_restore(self):
        from d3fend import get_countermeasures
        results = get_countermeasures("T1486")
        action_types = [r.action_type.value for r in results]
        assert "isolate_host" in action_types
        assert "restore_backup" in action_types

    def test_subtechnique_falls_back_to_parent(self):
        from d3fend import get_countermeasures
        results = get_countermeasures("T1110.001")  # Password Guessing
        assert len(results) >= 2
        # Should match T1110.001 directly (we have it mapped)
        action_types = [r.action_type.value for r in results]
        assert "disable_account" in action_types

    def test_unknown_technique_returns_empty(self):
        from d3fend import get_countermeasures
        results = get_countermeasures("T9999")
        assert results == []

    def test_unique_actions_deduplicates(self):
        from d3fend import get_unique_actions_for_incident
        # T1110 and T1078 both map to MFA — should appear only once
        results = get_unique_actions_for_incident(["T1110", "T1078"])
        technique_ids = [r.technique_id for r in results]
        assert len(technique_ids) == len(set(technique_ids))

    def test_all_supported_techniques_have_mappings(self):
        from d3fend import get_supported_attack_techniques, get_countermeasures
        for tid in get_supported_attack_techniques():
            results = get_countermeasures(tid)
            assert len(results) > 0, f"Technique {tid} has no countermeasures"

    def test_credential_dump_includes_credential_hardening(self):
        from d3fend import get_countermeasures
        results = get_countermeasures("T1003")
        d3fend_ids = [r.technique_id for r in results]
        assert "d3f:CredentialHardening" in d3fend_ids

    def test_lateral_movement_includes_network_isolation(self):
        from d3fend import get_countermeasures
        results = get_countermeasures("T1210")
        d3fend_ids = [r.technique_id for r in results]
        assert "d3f:NetworkIsolation" in d3fend_ids


# ============================================================================
# Safety Model Tests
# ============================================================================

class TestSafetyModel:
    """Test graduated autonomy, blast radius, and approval routing."""

    def test_observe_only_actions_always_auto(self):
        from safety import classify_blast_radius, determine_approval_tier
        from models import ActionType, BlastRadius, ApprovalTier
        blast = classify_blast_radius(ActionType.ADD_MONITORING, "critical")
        assert blast == BlastRadius.NONE
        tier = determine_approval_tier(0.50, blast, "critical")
        assert tier == ApprovalTier.AUTO_SAFE

    def test_block_ip_on_low_target_is_low_blast(self):
        from safety import classify_blast_radius
        from models import ActionType, BlastRadius
        blast = classify_blast_radius(ActionType.BLOCK_IP, "low")
        assert blast == BlastRadius.LOW

    def test_isolate_host_on_critical_escalates_to_high(self):
        from safety import classify_blast_radius
        from models import ActionType, BlastRadius
        blast = classify_blast_radius(ActionType.ISOLATE_HOST, "critical")
        assert blast == BlastRadius.HIGH

    def test_critical_high_blast_always_requires_human(self):
        from safety import determine_approval_tier
        from models import BlastRadius, ApprovalTier
        tier = determine_approval_tier(
            confidence=0.99,  # Max confidence
            blast_radius=BlastRadius.HIGH,
            target_criticality="critical",
        )
        assert tier == ApprovalTier.HUMAN_REQUIRED

    def test_high_confidence_low_blast_auto_executes(self):
        from safety import determine_approval_tier
        from models import BlastRadius, ApprovalTier
        tier = determine_approval_tier(
            confidence=0.85,
            blast_radius=BlastRadius.LOW,
            target_criticality="medium",
        )
        assert tier == ApprovalTier.AUTO_SAFE

    def test_low_confidence_falls_to_recommend(self):
        from safety import determine_approval_tier
        from models import BlastRadius, ApprovalTier
        tier = determine_approval_tier(
            confidence=0.50,
            blast_radius=BlastRadius.LOW,
            target_criticality="low",
        )
        assert tier == ApprovalTier.RECOMMEND

    def test_composite_score_weights(self):
        from safety import compute_composite_score
        score = compute_composite_score(
            impact_score=1.0, safety_score=1.0, confidence=1.0
        )
        assert score == 1.0

        score_low_impact = compute_composite_score(
            impact_score=0.0, safety_score=1.0, confidence=1.0
        )
        score_low_safety = compute_composite_score(
            impact_score=1.0, safety_score=0.0, confidence=1.0
        )
        # Impact weighted higher than safety
        assert score_low_impact < score_low_safety

    def test_plan_safety_warns_on_multiple_isolations(self):
        from safety import check_plan_safety
        from models import PlannedAction, ActionType, AdapterType, BlastRadius, ApprovalTier, ActionStatus
        actions = [
            PlannedAction(
                action_id=f"ACT-{i}", action_type=ActionType.ISOLATE_HOST,
                target=f"10.0.0.{i}", adapter=AdapterType.WAZUH,
                confidence=0.8, impact_score=0.8, safety_score=0.6,
                composite_score=0.7, blast_radius=BlastRadius.MEDIUM,
                approval_tier=ApprovalTier.HUMAN_REQUIRED, requires_approval=True,
            )
            for i in range(4)
        ]
        violations = check_plan_safety(actions)
        rules = [v.rule for v in violations]
        assert "multiple_isolations" in rules

    def test_build_planned_action_classifies_correctly(self):
        from safety import build_planned_action
        from d3fend import get_countermeasures
        from models import ApprovalTier

        technique = get_countermeasures("T1110")[0]  # First countermeasure for brute force
        action = build_planned_action(
            action_id="TEST-001",
            d3fend_technique=technique,
            target_ip="203.0.113.42",
            target_hostname="attacker",
            target_criticality="low",
            impact_score=0.7,
            confidence=0.85,
            counters_techniques=["T1110"],
            rationale="Block brute force source",
        )
        assert action.d3fend_technique == technique.technique_id
        assert action.counters_techniques == ["T1110"]
        assert action.confidence == 0.85
        assert action.composite_score > 0


# ============================================================================
# Adapter Tests
# ============================================================================

class TestAdapters:
    """Test adapter pattern and execution."""

    @pytest.mark.asyncio
    async def test_firewall_adapter_block_ip(self):
        from adapters.firewall import FirewallAdapter
        adapter = FirewallAdapter(firewall_type="test")
        result = await adapter.execute("block_ip", "203.0.113.42")
        assert result.success
        assert result.action_type == "block_ip"
        assert "203.0.113.42" in result.detail

    @pytest.mark.asyncio
    async def test_firewall_adapter_dry_run(self):
        from adapters.firewall import FirewallAdapter
        adapter = FirewallAdapter()
        result = await adapter.dry_run("block_ip", "203.0.113.42")
        assert result.success
        assert "DRY RUN" in result.detail

    @pytest.mark.asyncio
    async def test_edr_adapter_deploy(self):
        from adapters.edr import EDRAdapter
        adapter = EDRAdapter(platform="test")
        result = await adapter.execute("deploy_edr", "10.0.0.10")
        assert result.success
        assert "deployment" in result.detail.lower()

    @pytest.mark.asyncio
    async def test_edr_adapter_isolate(self):
        from adapters.edr import EDRAdapter
        adapter = EDRAdapter(platform="test")
        result = await adapter.execute("isolate_host", "10.0.0.10")
        assert result.success
        assert "isolated" in result.detail.lower()

    @pytest.mark.asyncio
    async def test_edr_adapter_rollback_isolation(self):
        from adapters.edr import EDRAdapter
        adapter = EDRAdapter(platform="test")
        result = await adapter.rollback("isolate_host", "10.0.0.10")
        assert result.success
        assert "released" in result.detail.lower()

    @pytest.mark.asyncio
    async def test_identity_adapter_revoke(self):
        from adapters.identity import IdentityAdapter
        adapter = IdentityAdapter(provider="test")
        result = await adapter.execute("revoke_credentials", "10.0.0.10")
        assert result.success
        assert "revoked" in result.detail.lower()

    @pytest.mark.asyncio
    async def test_identity_adapter_enable_mfa(self):
        from adapters.identity import IdentityAdapter
        adapter = IdentityAdapter(provider="test")
        result = await adapter.execute("enable_mfa", "10.0.0.10")
        assert result.success
        assert "mfa" in result.detail.lower()

    @pytest.mark.asyncio
    async def test_unsupported_action_returns_failure(self):
        from adapters.firewall import FirewallAdapter
        adapter = FirewallAdapter()
        result = await adapter.execute("nonexistent_action", "10.0.0.10")
        assert not result.success
        assert "unsupported" in result.detail.lower()

    @pytest.mark.asyncio
    async def test_adapter_result_to_dict(self):
        from adapters.base import AdapterResult
        result = AdapterResult(
            success=True, action_type="block_ip", target="1.2.3.4",
            adapter="test", detail="Blocked",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["target"] == "1.2.3.4"
        assert "timestamp" in d


# ============================================================================
# Planner Tests (with mocked LLM)
# ============================================================================

class TestPlanner:
    """Test defense plan generation with mocked LLM."""

    @pytest.mark.asyncio
    async def test_planner_generates_plan_for_brute_force(self):
        from planner import DefensePlanner
        planner = DefensePlanner(ollama_host="http://fake:11434")

        with patch.object(planner, "_generate_rationale", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "Defense strategy for brute force attack."

            plan = await planner.generate_plan(
                incident_id="INC-TEST-001",
                detected_techniques=["T1110"],
                kill_chain_stage="initial_access",
                source_ips=["203.0.113.42"],
                dest_ips=["10.0.0.10"],
                incident_summary="SSH brute force from 203.0.113.42",
            )

            assert plan.plan_id.startswith("PLAN-")
            assert plan.incident_id == "INC-TEST-001"
            assert len(plan.actions) > 0
            assert plan.total_actions == len(plan.actions)
            assert plan.rationale != ""

    @pytest.mark.asyncio
    async def test_planner_deduplicates_actions(self):
        from planner import DefensePlanner
        planner = DefensePlanner(ollama_host="http://fake:11434")

        with patch.object(planner, "_generate_rationale", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "Strategy."

            plan = await planner.generate_plan(
                incident_id="INC-TEST-002",
                detected_techniques=["T1110", "T1078"],  # Both map to MFA
                kill_chain_stage="credential_access",
                source_ips=["203.0.113.42"],
                dest_ips=["10.0.0.10"],
                incident_summary="Credential attack",
            )

            # Should not have duplicate (action_type, target) pairs
            seen = set()
            for a in plan.actions:
                key = (a.action_type, a.target)
                assert key not in seen, f"Duplicate action: {key}"
                seen.add(key)

    @pytest.mark.asyncio
    async def test_planner_uses_simulation_results_for_scoring(self):
        from planner import DefensePlanner
        planner = DefensePlanner(ollama_host="http://fake:11434")

        sim_results = {
            "simulation_id": "SIM-TEST",
            "results_summary": {
                "total_actions": 12,
                "success_rate": 0.72,
                "detection_rate": 0.58,
            },
            "weakest_points": [
                {"vulnerability": "10.0.0.10 (web-server-01): no EDR", "exploit_count": 4}
            ],
            "defense_validation": {
                "edr": {"blocked": 5, "bypassed": 1},
                "mfa": {"blocked": 3, "bypassed": 0},
            },
            "recommended_actions": [],
        }

        with patch.object(planner, "_generate_rationale", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "Simulation-informed strategy."

            plan = await planner.generate_plan(
                incident_id="INC-TEST-003",
                detected_techniques=["T1190"],
                kill_chain_stage="initial_access",
                source_ips=["203.0.113.42"],
                dest_ips=["10.0.0.10"],
                incident_summary="Exploit on web server",
                simulation_results=sim_results,
            )

            assert plan.simulation_id == "SIM-TEST"
            assert plan.simulation_summary is not None
            # Actions should have simulation-informed impact scores
            assert any(a.impact_score > 0.5 for a in plan.actions)

    @pytest.mark.asyncio
    async def test_planner_actions_sorted_by_composite_score(self):
        from planner import DefensePlanner
        planner = DefensePlanner(ollama_host="http://fake:11434")

        with patch.object(planner, "_generate_rationale", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "Strategy."

            plan = await planner.generate_plan(
                incident_id="INC-TEST-004",
                detected_techniques=["T1190", "T1110"],
                kill_chain_stage="initial_access",
                source_ips=["203.0.113.42"],
                dest_ips=["10.0.0.10"],
                incident_summary="Multi-technique attack",
            )

            scores = [a.composite_score for a in plan.actions]
            assert scores == sorted(scores, reverse=True)


# ============================================================================
# End-to-End Orchestrator Tests (all external services mocked)
# ============================================================================

class TestOrchestratorE2E:
    """Test the full orchestrator loop with mocked services."""

    def _make_settings(self):
        from config import Settings
        return Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            correlation_engine_url="http://fake-correlation:8000",
            simulation_url="http://fake-simulation:8000",
            ollama_host="http://fake-ollama:11434",
            wazuh_api_url="https://fake-wazuh:55000",
            wazuh_api_password="test",
            dry_run_mode=True,  # Never execute real actions in tests
            auto_execute_confidence_min=0.70,
            verification_monitoring_duration_seconds=1,  # Fast tests
        )

    @pytest.mark.asyncio
    async def test_full_loop_dry_run(self):
        from orchestrator import ResponseOrchestrator

        settings = self._make_settings()
        orch = ResponseOrchestrator(settings)

        # Mock incident fetch
        mock_incident = {
            "incident_id": "INC-TEST-E2E",
            "status": "open",
            "severity": "high",
            "kill_chain_stage": "initial_access",
            "source_ips": ["203.0.113.42"],
            "dest_ips": ["10.0.0.10"],
            "mitre_techniques": ["T1110"],
            "mitre_tactics": ["credential-access"],
            "summary": "SSH brute force detected",
        }

        with patch.object(orch, "_fetch_incident", new_callable=AsyncMock) as mock_fetch, \
             patch.object(orch, "_run_simulation", new_callable=AsyncMock) as mock_sim, \
             patch.object(orch.planner, "_generate_rationale", new_callable=AsyncMock) as mock_llm, \
             patch.object(orch, "_record_outcome", new_callable=AsyncMock):

            mock_fetch.return_value = mock_incident
            mock_sim.return_value = None  # No simulation
            mock_llm.return_value = "Defense plan rationale."

            plan = await orch.trigger_defense(
                incident_id="INC-TEST-E2E",
                dry_run=True,
                skip_simulation=True,
            )

            assert plan.plan_id.startswith("PLAN-")
            assert plan.incident_id == "INC-TEST-E2E"
            assert plan.dry_run is True
            assert len(plan.actions) > 0
            assert plan.detected_techniques == ["T1110"]

    @pytest.mark.asyncio
    async def test_auto_actions_execute_in_dry_run(self):
        from orchestrator import ResponseOrchestrator

        settings = self._make_settings()
        orch = ResponseOrchestrator(settings)

        mock_incident = {
            "incident_id": "INC-AUTO",
            "status": "open",
            "severity": "high",
            "kill_chain_stage": "lateral_movement",
            "source_ips": ["203.0.113.42"],
            "dest_ips": ["10.0.0.10"],
            "mitre_techniques": ["T1210"],
            "mitre_tactics": ["lateral-movement"],
            "summary": "Lateral movement detected",
        }

        with patch.object(orch, "_fetch_incident", new_callable=AsyncMock) as mock_fetch, \
             patch.object(orch, "_run_simulation", new_callable=AsyncMock) as mock_sim, \
             patch.object(orch.planner, "_generate_rationale", new_callable=AsyncMock) as mock_llm, \
             patch.object(orch, "_record_outcome", new_callable=AsyncMock):

            mock_fetch.return_value = mock_incident
            mock_sim.return_value = None
            mock_llm.return_value = "Strategy."

            plan = await orch.trigger_defense(
                incident_id="INC-AUTO",
                auto_execute=True,
                dry_run=True,
                skip_simulation=True,
            )

            # Some actions should have been auto-executed OR are pending approval
            # (depends on blast radius and confidence for each action)
            completed = [a for a in plan.actions if a.status.value == "completed"]
            pending = [a for a in plan.actions if a.status.value == "pending"]
            assert len(completed) + len(pending) == len(plan.actions), \
                "All actions should be either completed or pending"
            assert len(plan.actions) > 0, "Expected at least one action in the plan"

    @pytest.mark.asyncio
    async def test_plan_not_found_raises(self):
        from orchestrator import ResponseOrchestrator

        settings = self._make_settings()
        orch = ResponseOrchestrator(settings)

        with patch.object(orch, "_fetch_incident", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None

            with pytest.raises(ValueError, match="not found"):
                await orch.trigger_defense(incident_id="NONEXISTENT")

    @pytest.mark.asyncio
    async def test_approval_workflow(self):
        from orchestrator import ResponseOrchestrator
        from models import ActionStatus

        settings = self._make_settings()
        orch = ResponseOrchestrator(settings)

        mock_incident = {
            "incident_id": "INC-APPROVE",
            "status": "open",
            "severity": "critical",
            "kill_chain_stage": "impact",
            "source_ips": ["203.0.113.42"],
            "dest_ips": ["10.0.2.10"],  # Critical host
            "mitre_techniques": ["T1486"],  # Ransomware
            "mitre_tactics": ["impact"],
            "summary": "Ransomware detected on production DB",
        }

        with patch.object(orch, "_fetch_incident", new_callable=AsyncMock) as mock_fetch, \
             patch.object(orch, "_run_simulation", new_callable=AsyncMock) as mock_sim, \
             patch.object(orch.planner, "_generate_rationale", new_callable=AsyncMock) as mock_llm, \
             patch.object(orch, "_record_outcome", new_callable=AsyncMock), \
             patch.object(orch, "_verify_and_complete", new_callable=AsyncMock):

            mock_fetch.return_value = mock_incident
            mock_sim.return_value = None
            mock_llm.return_value = "Ransomware response."

            plan = await orch.trigger_defense(
                incident_id="INC-APPROVE",
                auto_execute=True,
                dry_run=True,
                skip_simulation=True,
                environment_json={
                    "hosts": {
                        "10.0.2.10": {
                            "hostname": "prod-db-01",
                            "criticality": "critical",
                        }
                    }
                },
            )

            # Critical targets should require approval
            pending = [a for a in plan.actions if a.requires_approval and a.status == ActionStatus.PENDING]
            # There should be at least some requiring approval due to critical target
            # (observe-only actions auto-execute even on critical targets)

            # Approve one
            if pending:
                action = await orch.approve_action(
                    plan_id=plan.plan_id,
                    action_id=pending[0].action_id,
                    approved=True,
                    analyst_id="test-analyst",
                )
                assert action.status in (ActionStatus.COMPLETED, ActionStatus.FAILED)

    @pytest.mark.asyncio
    async def test_get_pending_approvals(self):
        from orchestrator import ResponseOrchestrator
        from models import PlanStatus

        settings = self._make_settings()
        orch = ResponseOrchestrator(settings)

        mock_incident = {
            "incident_id": "INC-PENDING",
            "status": "open",
            "severity": "high",
            "kill_chain_stage": "exfiltration",
            "source_ips": ["203.0.113.42"],
            "dest_ips": ["10.0.2.10"],
            "mitre_techniques": ["T1041"],
            "mitre_tactics": ["exfiltration"],
            "summary": "Data exfiltration attempt",
        }

        with patch.object(orch, "_fetch_incident", new_callable=AsyncMock) as mock_fetch, \
             patch.object(orch, "_run_simulation", new_callable=AsyncMock), \
             patch.object(orch.planner, "_generate_rationale", new_callable=AsyncMock) as mock_llm, \
             patch.object(orch, "_record_outcome", new_callable=AsyncMock), \
             patch.object(orch, "_verify_and_complete", new_callable=AsyncMock):

            mock_fetch.return_value = mock_incident
            mock_llm.return_value = "Exfil response."

            plan = await orch.trigger_defense(
                incident_id="INC-PENDING",
                dry_run=True,
                skip_simulation=True,
            )

            # Get all pending approvals
            all_pending = orch.get_pending_approvals()
            assert isinstance(all_pending, list)
            for item in all_pending:
                assert "action_id" in item
                assert "action_type" in item
                assert "rationale" in item
