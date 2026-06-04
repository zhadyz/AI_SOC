"""
Core Orchestrator - Response Orchestrator Service
AI-Augmented SOC

The central state machine that drives the autonomous defense loop:

  TRIGGERED → SIMULATING → PLANNING → AWAITING_APPROVAL →
  EXECUTING → VERIFYING → COMPLETED (or ROLLED_BACK)

Each transition is logged, persisted, and observable via API.
The orchestrator coordinates between:
  - Correlation Engine (incident data, simulation)
  - Defense Planner (D3FEND lookup, LLM scoring)
  - Action Execution Layer (adapters)
  - Verification Engine (re-simulation, monitoring)
  - Feedback Service (outcome recording)
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from models import (
    ActionStatus, ActionType, AdapterType, ApprovalTier,
    DefensePlan, PlannedAction, PlanStatus, VerificationResult,
)
from planner import DefensePlanner
from verification import VerificationEngine
from adapters.base import BaseAdapter, AdapterResult
from adapters.wazuh import WazuhAdapter
from adapters.firewall import FirewallAdapter
from adapters.edr import EDRAdapter
from adapters.identity import IdentityAdapter
from config import Settings
from persist import save_defense_plan

logger = logging.getLogger(__name__)


class ResponseOrchestrator:
    """
    Drives the full autonomous defense loop.

    Manages active defense plans, coordinates simulation → planning →
    execution → verification, and handles approval workflows.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        # Active plans (in-memory cache, backed by PostgreSQL)
        self._plans: Dict[str, DefensePlan] = {}

        # Components
        self.planner = DefensePlanner(
            ollama_host=settings.ollama_host,
            ollama_model=settings.ollama_model,
            auto_execute_min=settings.auto_execute_confidence_min,
            auto_veto_min=settings.auto_execute_with_veto_confidence_min,
        )
        self.verifier = VerificationEngine(
            simulation_url=settings.simulation_url,
            correlation_url=settings.correlation_engine_url,
            wazuh_api_url=settings.wazuh_api_url,
            wazuh_username=settings.wazuh_api_username,
            wazuh_password=settings.wazuh_api_password,
            wazuh_verify_ssl=settings.wazuh_api_verify_ssl,
            risk_reduction_threshold=settings.verification_risk_reduction_threshold,
            monitoring_duration_seconds=settings.verification_monitoring_duration_seconds,
        )

        # Adapters
        self._adapters: Dict[str, BaseAdapter] = {
            "wazuh": WazuhAdapter(
                api_url=settings.wazuh_api_url,
                username=settings.wazuh_api_username,
                password=settings.wazuh_api_password,
                verify_ssl=settings.wazuh_api_verify_ssl,
            ),
            "firewall": FirewallAdapter(),
            "edr": EDRAdapter(),
            "identity": IdentityAdapter(),
        }

    def _persist_plan(self, plan: DefensePlan) -> None:
        if not self.settings.defense_plans_enabled:
            return
        save_defense_plan(
            self.settings.defense_plans_dir,
            plan.model_dump(mode="json"),
        )

    # ----- Main Loop -----

    async def trigger_defense(
        self,
        incident_id: str,
        environment_json: Optional[Dict] = None,
        auto_execute: bool = True,
        dry_run: bool = False,
        skip_simulation: bool = False,
    ) -> DefensePlan:
        """
        Entry point: trigger the full defense loop for an incident.

        1. Fetch incident context from correlation engine
        2. Run simulation (unless skipped)
        3. Generate defense plan
        4. Execute auto-approved actions
        5. Queue remaining actions for human approval
        6. Start verification (async)
        """
        logger.info(f"Defense triggered for incident {incident_id}")

        # Check concurrent plan limit
        active = [
            p for p in self._plans.values()
            if p.status not in (PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.ROLLED_BACK)
        ]
        if len(active) >= self.settings.max_concurrent_plans:
            raise RuntimeError(
                f"Max concurrent plans ({self.settings.max_concurrent_plans}) reached. "
                f"Complete or cancel existing plans first."
            )

        # Step 1: Fetch incident context
        incident = await self._fetch_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        # Step 2: Run simulation
        simulation_results = None
        if not skip_simulation:
            simulation_results = await self._run_simulation(
                incident, environment_json
            )

        # Step 3: Generate plan
        plan = await self.planner.generate_plan(
            incident_id=incident_id,
            detected_techniques=incident.get("mitre_techniques", []),
            kill_chain_stage=incident.get("kill_chain_stage", ""),
            source_ips=incident.get("source_ips", []),
            dest_ips=incident.get("dest_ips", []),
            incident_summary=incident.get("summary", ""),
            simulation_results=simulation_results,
            environment=environment_json,
            dry_run=dry_run or self.settings.dry_run_mode,
        )

        self._plans[plan.plan_id] = plan

        # Step 4: Execute auto-approved actions
        if auto_execute and not plan.dry_run:
            await self._execute_auto_actions(plan)

        # Update status based on remaining actions
        pending_approval = [
            a for a in plan.actions
            if a.requires_approval and a.status == ActionStatus.PENDING
        ]
        if pending_approval:
            plan.status = PlanStatus.AWAITING_APPROVAL
        elif all(a.status in (ActionStatus.COMPLETED, ActionStatus.SKIPPED) for a in plan.actions):
            plan.status = PlanStatus.VERIFYING
            # Start async verification
            asyncio.create_task(self._verify_and_complete(plan))
        else:
            plan.status = PlanStatus.EXECUTING

        plan.updated_at = datetime.utcnow()
        self._persist_plan(plan)
        return plan

    # ----- Incident Fetch -----

    async def _fetch_incident(self, incident_id: str) -> Optional[Dict]:
        """Fetch incident details from the correlation engine."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.settings.correlation_engine_url}/incidents/{incident_id}",
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 404:
                    logger.warning(f"Incident {incident_id} not found")
                    return None
                else:
                    logger.error(f"Fetch incident failed: {resp.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Failed to fetch incident {incident_id}: {e}")
            return None

    # ----- Simulation -----

    async def _run_simulation(
        self,
        incident: Dict,
        environment_json: Optional[Dict],
    ) -> Optional[Dict]:
        """Run a simulation against the environment."""
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "timesteps": self.settings.simulation_timesteps,
                }
                resp = await client.post(
                    f"{self.settings.simulation_url}/simulate",
                    params=params,
                    json=environment_json,
                    timeout=self.settings.simulation_timeout_seconds,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    logger.info(
                        f"Simulation complete: {result.get('simulation_id', 'unknown')}"
                    )
                    return result
                else:
                    logger.error(f"Simulation failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"Simulation request failed: {e}")

        return None

    # ----- Action Execution -----

    async def _execute_auto_actions(self, plan: DefensePlan) -> None:
        """Execute all actions that don't require human approval."""
        auto_count = 0
        for action in plan.actions:
            if action.requires_approval:
                continue
            if action.status != ActionStatus.PENDING:
                continue

            # Enforce rate limit
            if auto_count >= self.settings.max_auto_actions_per_incident:
                logger.warning(
                    f"Max auto-actions ({self.settings.max_auto_actions_per_incident}) "
                    f"reached for plan {plan.plan_id}. Remaining actions need approval."
                )
                action.requires_approval = True
                continue

            await self._execute_action(plan, action)
            auto_count += 1

            # Cooldown between actions
            if self.settings.cooldown_between_actions_seconds > 0:
                await asyncio.sleep(self.settings.cooldown_between_actions_seconds)

        plan.auto_executed_count = auto_count

    async def _execute_action(
        self, plan: DefensePlan, action: PlannedAction
    ) -> AdapterResult:
        """Execute a single defense action via its adapter."""
        adapter = self._adapters.get(action.adapter.value)
        if not adapter:
            action.status = ActionStatus.FAILED
            action.error_message = f"No adapter found for {action.adapter.value}"
            return AdapterResult(
                success=False,
                action_type=action.action_type.value,
                target=action.target,
                adapter=action.adapter.value,
                detail=action.error_message,
                error=action.error_message,
            )

        action.status = ActionStatus.EXECUTING
        action.executed_at = datetime.utcnow()

        logger.info(
            f"Executing: {action.action_type.value} on {action.target} "
            f"via {action.adapter.value} (plan {plan.plan_id})"
        )

        if plan.dry_run:
            result = await adapter.dry_run(action.action_type.value, action.target)
        else:
            result = await adapter.execute(action.action_type.value, action.target)

        if result.success:
            action.status = ActionStatus.COMPLETED
            action.completed_at = datetime.utcnow()
            action.adapter_response = result.to_dict()
        else:
            action.status = ActionStatus.FAILED
            action.error_message = result.error or result.detail
            action.adapter_response = result.to_dict()

        plan.updated_at = datetime.utcnow()
        return result

    # ----- Approval Handling -----

    async def approve_action(
        self,
        plan_id: str,
        action_id: str,
        approved: bool,
        analyst_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> PlannedAction:
        """Approve or reject a pending action."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        action = next(
            (a for a in plan.actions if a.action_id == action_id), None
        )
        if not action:
            raise ValueError(f"Action {action_id} not found in plan {plan_id}")

        if action.status != ActionStatus.PENDING:
            raise ValueError(
                f"Action {action_id} is {action.status.value}, not pending"
            )

        if approved:
            plan.human_approved_count += 1
            result = await self._execute_action(plan, action)
            if not result.success:
                logger.error(
                    f"Approved action {action_id} failed: {result.error}"
                )
        else:
            action.status = ActionStatus.VETOED
            logger.info(f"Action {action_id} vetoed by {analyst_id}")

        # Check if all actions are now resolved
        all_resolved = all(
            a.status in (
                ActionStatus.COMPLETED, ActionStatus.FAILED,
                ActionStatus.SKIPPED, ActionStatus.VETOED,
            )
            for a in plan.actions
        )

        if all_resolved:
            plan.status = PlanStatus.VERIFYING
            asyncio.create_task(self._verify_and_complete(plan))

        plan.updated_at = datetime.utcnow()
        self._persist_plan(plan)
        return action

    # ----- Verification & Completion -----

    async def _verify_and_complete(self, plan: DefensePlan) -> None:
        """Run verification and finalize the plan."""
        try:
            verification = await self.verifier.verify_plan(plan)
            plan.verification = verification
            plan.post_defense_risk = verification.post_attack_success_rate

            if verification.verification_passed:
                plan.status = PlanStatus.COMPLETED
                plan.completed_at = datetime.utcnow()
                logger.info(
                    f"Plan {plan.plan_id} COMPLETED — "
                    f"risk reduced by {verification.risk_reduction_pct*100:.1f}%"
                )
            else:
                # Check if auto-rollback is enabled
                if self.settings.auto_rollback_on_verification_failure:
                    await self._rollback_plan(plan)
                    plan.status = PlanStatus.ROLLED_BACK
                    logger.warning(
                        f"Plan {plan.plan_id} ROLLED BACK — "
                        f"verification failed: {verification.verdict_reason[:100]}"
                    )
                else:
                    plan.status = PlanStatus.COMPLETED
                    plan.completed_at = datetime.utcnow()
                    logger.warning(
                        f"Plan {plan.plan_id} completed with verification failure: "
                        f"{verification.verdict_reason[:100]}"
                    )

            # Record outcome in feedback service
            await self._record_outcome(plan)

        except Exception as e:
            logger.error(f"Verification failed for plan {plan.plan_id}: {e}")
            plan.status = PlanStatus.FAILED
            plan.completed_at = datetime.utcnow()

        plan.updated_at = datetime.utcnow()
        self._persist_plan(plan)

    async def _rollback_plan(self, plan: DefensePlan) -> None:
        """Rollback all completed actions in reverse order."""
        reversed_actions = [
            a for a in reversed(plan.actions)
            if a.status == ActionStatus.COMPLETED
        ]

        for action in reversed_actions:
            adapter = self._adapters.get(action.adapter.value)
            if not adapter:
                continue

            try:
                result = await adapter.rollback(
                    action.action_type.value, action.target
                )
                if result.success:
                    action.status = ActionStatus.ROLLED_BACK
                    action.rolled_back_at = datetime.utcnow()
                    logger.info(
                        f"Rolled back: {action.action_type.value} on {action.target}"
                    )
                else:
                    logger.error(
                        f"Rollback failed for {action.action_id}: {result.error}"
                    )
            except Exception as e:
                logger.error(f"Rollback error for {action.action_id}: {e}")

    # ----- Feedback Recording -----

    async def _record_outcome(self, plan: DefensePlan) -> None:
        """Record defense outcome in the feedback service for learning."""
        if not plan.verification:
            return

        try:
            async with httpx.AsyncClient() as client:
                outcome = {
                    "plan_id": plan.plan_id,
                    "incident_id": plan.incident_id,
                    "total_actions": plan.total_actions,
                    "auto_executed": plan.auto_executed_count,
                    "human_approved": plan.human_approved_count,
                    "pre_risk": plan.pre_defense_risk,
                    "post_risk": plan.post_defense_risk,
                    "verification_passed": plan.verification.verification_passed,
                    "risk_reduction_pct": plan.verification.risk_reduction_pct,
                    "actions": [
                        {
                            "action_type": a.action_type.value,
                            "target": a.target,
                            "status": a.status.value,
                            "d3fend_technique": a.d3fend_technique,
                            "counters_techniques": a.counters_techniques,
                            "impact_score": a.impact_score,
                        }
                        for a in plan.actions
                    ],
                }

                await client.post(
                    f"{self.settings.feedback_service_url}/alerts",
                    json={
                        "alert_id": f"defense-{plan.plan_id}",
                        "source": "response-orchestrator",
                        "data": outcome,
                    },
                    timeout=10.0,
                )
        except Exception as e:
            logger.warning(f"Failed to record defense outcome: {e}")

    # ----- Plan Management -----

    def get_plan(self, plan_id: str) -> Optional[DefensePlan]:
        """Get a plan by ID."""
        return self._plans.get(plan_id)

    def get_all_plans(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[DefensePlan]:
        """Get all plans, optionally filtered by status."""
        plans = list(self._plans.values())
        if status:
            plans = [p for p in plans if p.status.value == status]
        plans.sort(key=lambda p: p.created_at, reverse=True)
        return plans[:limit]

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get all actions across all plans that need human approval."""
        pending = []
        for plan in self._plans.values():
            if plan.status != PlanStatus.AWAITING_APPROVAL:
                continue
            for action in plan.actions:
                if action.requires_approval and action.status == ActionStatus.PENDING:
                    pending.append({
                        "plan_id": plan.plan_id,
                        "incident_id": plan.incident_id,
                        "action_id": action.action_id,
                        "action_type": action.action_type.value,
                        "target": action.target,
                        "target_hostname": action.target_hostname,
                        "d3fend_label": action.d3fend_label,
                        "impact_score": action.impact_score,
                        "safety_score": action.safety_score,
                        "blast_radius": action.blast_radius.value,
                        "rationale": action.rationale,
                        "counters_techniques": action.counters_techniques,
                    })
        return pending
