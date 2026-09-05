"""Durable response lifecycle with explicit dry runs, approvals and recovery."""
import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from services.common.api_security import service_client

from services.response_orchestrator.models import (
    ActionStatus, ApprovalTier, DefensePlan, PlanStatus,
)
from services.response_orchestrator.planner import DefensePlanner
from services.response_orchestrator.verification import VerificationEngine
from services.response_orchestrator.adapters.base import AdapterResult
from services.response_orchestrator.adapters.wazuh import WazuhAdapter
from services.response_orchestrator.adapters.firewall import FirewallAdapter
from services.response_orchestrator.adapters.edr import EDRAdapter
from services.response_orchestrator.adapters.identity import IdentityAdapter

logger = logging.getLogger(__name__)
TERMINAL = {PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.ROLLED_BACK,
            PlanStatus.DRY_RUN, PlanStatus.CANCELLED}


class ResponseOrchestrator:
    def __init__(self, settings, store=None):
        self.settings = settings
        self.store = store
        self._plans = {}
        self._locks = {}
        self._tasks = set()
        self._starting = 0
        self._capacity_lock = asyncio.Lock()
        self.planner = DefensePlanner(
            ollama_host=settings.ollama_host, ollama_model=settings.ollama_model,
            auto_execute_min=settings.auto_execute_confidence_min,
            auto_veto_min=settings.auto_execute_with_veto_confidence_min,
        )
        self.verifier = VerificationEngine(
            simulation_url=settings.simulation_url, correlation_url=settings.correlation_engine_url,
            wazuh_api_url=settings.wazuh_api_url, wazuh_username=settings.wazuh_api_username,
            wazuh_password=settings.wazuh_api_password, wazuh_verify_ssl=settings.wazuh_api_verify_ssl,
            risk_reduction_threshold=settings.verification_risk_reduction_threshold,
            monitoring_duration_seconds=settings.verification_monitoring_duration_seconds,
            indexer_url=settings.wazuh_indexer_url, indexer_username=settings.wazuh_indexer_username,
            indexer_password=settings.wazuh_indexer_password,
        )
        self._adapters = {
            "wazuh": WazuhAdapter(api_url=settings.wazuh_api_url, username=settings.wazuh_api_username,
                                  password=settings.wazuh_api_password, verify_ssl=settings.wazuh_api_verify_ssl,
                                  ca_bundle=settings.wazuh_api_ca_bundle,
                                  block_command=settings.wazuh_block_command),
            "firewall": FirewallAdapter(), "network": FirewallAdapter(), "edr": EDRAdapter(), "identity": IdentityAdapter(),
        }
        if settings.lab_url:
            from services.response_orchestrator.adapters.lab import LabAdapter
            for name in ("firewall", "network", "edr", "identity"):
                self._adapters[name] = LabAdapter(name, settings.lab_url)

    async def restore(self):
        if not self.store:
            return
        for plan in await self.store.load():
            self._plans[plan.plan_id] = plan
            self._locks[plan.plan_id] = asyncio.Lock()
            uncertain = plan.status in {PlanStatus.EXECUTING, PlanStatus.VERIFYING}
            uncertain |= any(a.status == ActionStatus.EXECUTING for a in plan.actions)
            if uncertain:
                # A remote action may have succeeded before the process died.
                # Never replay it automatically.
                plan.status = PlanStatus.RECOVERY_REQUIRED
                await self._save(plan, "restart_requires_reconciliation")
            for action in plan.actions:
                if action.veto_deadline and action.status == ActionStatus.PENDING:
                    action.requires_approval = True
                    action.veto_deadline = None
                    plan.status = PlanStatus.AWAITING_APPROVAL
                    await self._save(plan, "restart_requires_approval", action_id=action.action_id)

    async def close(self):
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _save(self, plan, event, **detail):
        plan.updated_at = datetime.utcnow()
        if self.store:
            await self.store.save(plan, event, **detail)

    def _spawn(self, coroutine):
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        def finished(done):
            self._tasks.discard(done)
            if not done.cancelled() and done.exception():
                logger.error("Response background task failed", exc_info=done.exception())
        task.add_done_callback(finished)

    async def trigger_defense(self, incident_id, environment_json=None, auto_execute=False,
                              dry_run=True, skip_simulation=False):
        async with self._capacity_lock:
            active = sum(p.status not in TERMINAL for p in self._plans.values())
            if active + self._starting >= self.settings.max_concurrent_plans:
                raise RuntimeError("Max concurrent plans reached; resolve active plans first")
            self._starting += 1
        try:
            incident = await self._fetch_incident(incident_id)
            if not incident:
                raise ValueError(f"Incident {incident_id} not found")
            simulation = None if skip_simulation else await self._run_simulation(incident, environment_json)
            plan = await self.planner.generate_plan(
                incident_id=incident_id, detected_techniques=incident.get("mitre_techniques", []),
                kill_chain_stage=incident.get("kill_chain_stage", ""), source_ips=incident.get("source_ips", []),
                dest_ips=incident.get("dest_ips", []), incident_summary=incident.get("summary", ""),
                simulation_results=simulation, environment=environment_json,
                dry_run=dry_run or self.settings.dry_run_mode,
            )
            self._plans[plan.plan_id] = plan
            self._locks[plan.plan_id] = asyncio.Lock()
            for action in plan.actions:
                action.parameters.setdefault("operation_id", action.action_id)
                if action.adapter.value == "wazuh":
                    action.parameters.setdefault("agent_list", list(self.settings.wazuh_agent_ids))
            await self._save(plan, "plan_created")
            if plan.dry_run:
                for action in plan.actions:
                    await self._execute_action(plan, action)
                plan.status = PlanStatus.DRY_RUN
                plan.completed_at = datetime.utcnow()
                await self._save(plan, "dry_run_completed")
            else:
                if auto_execute:
                    await self._execute_auto_actions(plan)
                else:
                    for action in plan.actions:
                        action.requires_approval = True
                await self._finish_actions(plan)
            return plan
        except Exception:
            if "plan" in locals():
                plan.status = PlanStatus.RECOVERY_REQUIRED
            raise
        finally:
            async with self._capacity_lock:
                self._starting -= 1

    async def _fetch_incident(self, incident_id):
        async with service_client() as client:
            response = await client.get(f"{self.settings.correlation_engine_url}/incidents/{incident_id}", timeout=15)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def _run_simulation(self, incident, environment_json):
        try:
            async with service_client() as client:
                response = await client.post(f"{self.settings.simulation_url}/simulate",
                    params={"timesteps": self.settings.simulation_timesteps}, json=environment_json,
                    timeout=self.settings.simulation_timeout_seconds)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError):
            logger.exception("Simulation unavailable; plan has no simulated risk baseline")
            return None

    async def _execute_auto_actions(self, plan):
        for action in plan.actions:
            if action.status != ActionStatus.PENDING:
                continue
            if action.approval_tier == ApprovalTier.OBSERVE:
                action.status = ActionStatus.SKIPPED
                continue
            if action.requires_approval or action.approval_tier not in {ApprovalTier.AUTO_SAFE, ApprovalTier.AUTO_VETO}:
                action.requires_approval = True
                continue
            if plan.auto_executed_count >= self.settings.max_auto_actions_per_incident:
                action.requires_approval = True
                continue
            plan.auto_executed_count += 1
            if action.approval_tier == ApprovalTier.AUTO_VETO:
                action.veto_deadline = datetime.utcnow() + timedelta(seconds=self.settings.veto_window_seconds)
                await self._save(plan, "veto_window_opened", action_id=action.action_id,
                                 deadline=action.veto_deadline.isoformat())
                self._spawn(self._execute_after_veto(plan, action))
            else:
                await self._execute_action(plan, action)
            if self.settings.cooldown_between_actions_seconds:
                await asyncio.sleep(self.settings.cooldown_between_actions_seconds)

    async def _execute_after_veto(self, plan, action):
        delay = max(0, (action.veto_deadline - datetime.utcnow()).total_seconds())
        await asyncio.sleep(delay)
        async with self._locks[plan.plan_id]:
            if action.status != ActionStatus.PENDING or action.requires_approval or plan.status in TERMINAL:
                return
            await self._execute_action(plan, action)
            await self._finish_actions(plan)

    async def _execute_action(self, plan, action):
        adapter = self._adapters.get(action.adapter.value)
        action.status = ActionStatus.EXECUTING
        if not plan.dry_run:
            action.executed_at = datetime.utcnow()
        await self._save(plan, "action_intent", action_id=action.action_id, dry_run=plan.dry_run)
        try:
            if adapter is None:
                raise ValueError(f"No adapter for {action.adapter.value}")
            if plan.dry_run:
                result = await adapter.dry_run(action.action_type.value, action.target, action.parameters)
            else:
                result = await adapter.execute(action.action_type.value, action.target, action.parameters)
        except Exception as exc:
            result = AdapterResult(False, action.action_type.value, action.target, action.adapter.value,
                                   "Adapter execution failed", error=str(exc), rollback_capable=False)
        action.adapter_response = result.to_dict()
        if result.success:
            action.status = ActionStatus.SIMULATED if plan.dry_run else ActionStatus.COMPLETED
            action.completed_at = datetime.utcnow()
        else:
            action.status = ActionStatus.FAILED
            action.error_message = result.error or result.detail
        await self._save(plan, "action_result", action_id=action.action_id, result=result.to_dict())
        return result

    async def approve_action(self, plan_id, action_id, approved, analyst_id=None, notes=None):
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        if not analyst_id or not analyst_id.strip():
            raise ValueError("An analyst identity is required")
        async with self._locks.setdefault(plan_id, asyncio.Lock()):
            if plan.status in TERMINAL or plan.status == PlanStatus.RECOVERY_REQUIRED:
                raise ValueError(f"Plan {plan_id} does not accept approvals")
            action = next((a for a in plan.actions if a.action_id == action_id), None)
            if not action:
                raise ValueError(f"Action {action_id} not found")
            if action.status != ActionStatus.PENDING:
                raise ValueError(f"Action {action_id} is not pending")
            action.approved_by, action.approval_notes = analyst_id, notes
            action.approved_at = datetime.utcnow()
            await self._save(plan, "approval_decision", action_id=action_id, approved=approved,
                             analyst_id=analyst_id, notes=notes)
            if approved:
                plan.human_approved_count += 1
                await self._execute_action(plan, action)
            else:
                action.status = ActionStatus.VETOED
                await self._save(plan, "action_vetoed", action_id=action_id)
            await self._finish_actions(plan)
            return action

    async def _finish_actions(self, plan):
        if any(a.status == ActionStatus.PENDING for a in plan.actions):
            plan.status = PlanStatus.AWAITING_APPROVAL
        elif any(a.status == ActionStatus.FAILED for a in plan.actions):
            plan.status = PlanStatus.RECOVERY_REQUIRED if any(a.executed_at for a in plan.actions) else PlanStatus.FAILED
        elif any(a.status == ActionStatus.COMPLETED for a in plan.actions):
            plan.status = PlanStatus.VERIFYING
            await self._save(plan, "verification_started")
            self._spawn(self._verify_and_complete(plan))
            return
        else:
            plan.status = PlanStatus.CANCELLED
            plan.completed_at = datetime.utcnow()
        await self._save(plan, "plan_state", status=plan.status.value)

    async def request_verification(self, plan_id, environment_json, analyst_id):
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError("Plan not found")
        async with self._locks.setdefault(plan_id, asyncio.Lock()):
            if plan.dry_run or plan.status != PlanStatus.RECOVERY_REQUIRED:
                raise ValueError("Only an executed plan awaiting reconciliation can be reverified")
            if any(a.status in {ActionStatus.PENDING, ActionStatus.EXECUTING, ActionStatus.FAILED} for a in plan.actions):
                raise ValueError("Resolve uncertain, pending or failed actions before verification")
            plan.status = PlanStatus.VERIFYING
            await self._save(plan, "verification_requested", analyst_id=analyst_id,
                             observed_environment=environment_json)
            self._spawn(self._verify_and_complete(plan, environment_json))
        return plan

    async def reconcile_action(self, plan_id, action_id, analyst_id, disposition, notes):
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError("Plan not found")
        async with self._locks.setdefault(plan_id, asyncio.Lock()):
            if plan.dry_run or plan.status != PlanStatus.RECOVERY_REQUIRED:
                raise ValueError("Only a real plan requiring recovery can be reconciled")
            action = next((a for a in plan.actions if a.action_id == action_id), None)
            if not action or action.status not in {ActionStatus.EXECUTING, ActionStatus.FAILED}:
                raise ValueError("Action is not awaiting reconciliation")
            if disposition == "verify_active":
                adapter = self._adapters.get(action.adapter.value)
                if not adapter:
                    raise ValueError("No adapter can verify this action")
                result = await adapter.verify(action.action_type.value, action.target, action.parameters)
                await self._save(plan, "reconciliation_probe", action_id=action_id,
                                 analyst_id=analyst_id, result=result.to_dict())
                if not result.success:
                    raise ValueError("Adapter could not independently confirm the action")
                action.adapter_response = result.to_dict()
                action.status = ActionStatus.COMPLETED
            elif disposition == "confirm_not_applied":
                # Explicit reviewer attestation is preserved separately from
                # machine verification; this never re-executes the action.
                action.status = ActionStatus.SKIPPED
            else:
                raise ValueError("Invalid reconciliation disposition")
            action.error_message = None
            await self._save(plan, "action_reconciled", action_id=action_id, analyst_id=analyst_id,
                             disposition=disposition, notes=notes)
            if all(a.status in {ActionStatus.SKIPPED, ActionStatus.VETOED, ActionStatus.ROLLED_BACK} for a in plan.actions):
                plan.status = PlanStatus.CANCELLED
                plan.completed_at = datetime.utcnow()
                await self._save(plan, "reconciled_without_active_actions")
        return plan

    async def request_rollback(self, plan_id, analyst_id, notes):
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError("Plan not found")
        async with self._locks.setdefault(plan_id, asyncio.Lock()):
            if plan.dry_run or plan.status not in {PlanStatus.RECOVERY_REQUIRED, PlanStatus.COMPLETED}:
                raise ValueError("Only a settled real response can be rolled back")
            if any(a.status in {ActionStatus.PENDING, ActionStatus.EXECUTING, ActionStatus.FAILED} for a in plan.actions):
                raise ValueError("Reconcile uncertain actions before rollback")
            if not any(a.status == ActionStatus.COMPLETED for a in plan.actions):
                raise ValueError("No executed actions remain to roll back")
            await self._save(plan, "rollback_requested", analyst_id=analyst_id, notes=notes)
            complete = await self._rollback_plan(plan)
            plan.status = PlanStatus.ROLLED_BACK if complete else PlanStatus.RECOVERY_REQUIRED
            plan.completed_at = datetime.utcnow() if complete else None
            await self._save(plan, "manual_rollback_result", complete=complete)
        return plan

    async def _verify_and_complete(self, plan, updated_environment=None):
        try:
            verification = await self.verifier.verify_plan(plan, updated_environment)
            plan.verification = verification
            plan.post_defense_risk = verification.post_attack_success_rate if verification.simulation_available else None
            if verification.verification_passed and verification.evidence_available:
                plan.status = PlanStatus.COMPLETED
            elif verification.evidence_available and self.settings.auto_rollback_on_verification_failure:
                rolled_back = await self._rollback_plan(plan)
                plan.status = PlanStatus.ROLLED_BACK if rolled_back else PlanStatus.RECOVERY_REQUIRED
            else:
                plan.status = PlanStatus.RECOVERY_REQUIRED
            plan.completed_at = datetime.utcnow() if plan.status in TERMINAL else None
            await self._save(plan, "verification_result", evidence=verification.model_dump(mode="json"))
            await self._record_outcome(plan)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Verification failed")
            plan.status = PlanStatus.RECOVERY_REQUIRED
            await self._save(plan, "verification_unavailable")

    async def _rollback_plan(self, plan):
        if plan.dry_run:
            return False
        complete = True
        for action in reversed(plan.actions):
            if action.status != ActionStatus.COMPLETED:
                continue
            adapter = self._adapters.get(action.adapter.value)
            if not adapter or not (action.adapter_response or {}).get("rollback_capable", False):
                complete = False
                continue
            await self._save(plan, "rollback_intent", action_id=action.action_id)
            try:
                result = await adapter.rollback(action.action_type.value, action.target, action.parameters)
            except Exception:
                complete = False
                logger.exception("Rollback failed")
                continue
            if result.success:
                action.status = ActionStatus.ROLLED_BACK
                action.rolled_back_at = datetime.utcnow()
            else:
                complete = False
            await self._save(plan, "rollback_result", action_id=action.action_id, result=result.to_dict())
        return complete

    async def cancel_plan(self, plan_id, analyst_id, notes=None):
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        async with self._locks.setdefault(plan_id, asyncio.Lock()):
            if any(a.status in {ActionStatus.EXECUTING, ActionStatus.COMPLETED} for a in plan.actions):
                raise ValueError("Executed actions require reconciliation; cancellation cannot undo them")
            for action in plan.actions:
                if action.status == ActionStatus.PENDING:
                    action.status = ActionStatus.VETOED
            plan.status = PlanStatus.CANCELLED
            plan.completed_at = datetime.utcnow()
            await self._save(plan, "plan_cancelled", analyst_id=analyst_id, notes=notes)
        return plan

    async def _record_outcome(self, plan):
        try:
            async with service_client() as client:
                response = await client.post(f"{self.settings.feedback_service_url}/alerts", json={
                    "alert_id": f"defense-{plan.plan_id}", "rule_description": "Defense outcome",
                    "raw_alert": {"source": "response-orchestrator", "defense_plan": plan.model_dump(mode="json")},
                }, timeout=10)
                response.raise_for_status()
        except httpx.HTTPError:
            # The canonical outcome is already durably stored with the plan.
            logger.exception("Feedback projection failed; outcome remains in response plan audit")

    def get_plan(self, plan_id):
        return self._plans.get(plan_id)

    def get_all_plans(self, status=None, limit=50):
        plans = [p for p in self._plans.values() if not status or p.status.value == status]
        return sorted(plans, key=lambda p: p.created_at, reverse=True)[:limit]

    def get_pending_approvals(self):
        return [{"plan_id": plan.plan_id, "incident_id": plan.incident_id,
                 **action.model_dump(mode="json")} for plan in self._plans.values()
                if plan.status == PlanStatus.AWAITING_APPROVAL for action in plan.actions
                if action.status == ActionStatus.PENDING]
