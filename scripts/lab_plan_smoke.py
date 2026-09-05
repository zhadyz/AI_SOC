#!/usr/bin/env python3
"""Live scoped effects through the real response engine, with restart recovery.

Uses explicitly authored test plans and a separate SQLite plan store. It does not
change the main orchestrator's dry-run setting or claim prevention effectiveness.
Run after lab_smoke.py, with no other lab actions in progress.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import uuid

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lab.control import container, docker, PROBE_IP
from services.response_orchestrator.config import Settings
from services.response_orchestrator.models import (ActionStatus, ActionType, AdapterType, ApprovalTier,
                                                  BlastRadius, DefensePlan, PlannedAction, PlanStatus)
from services.response_orchestrator.orchestrator import ResponseOrchestrator
from services.response_orchestrator.store import PlanStore


async def run(state):
    os.environ['AI_SOC_API_KEY'] = dotenv_values(ROOT / '.env')['AI_SOC_API_KEY']
    settings = Settings(dry_run_mode=False, lab_url='http://127.0.0.1:8900',
                        feedback_service_url='http://127.0.0.1:8400', cooldown_between_actions_seconds=0)
    probe, _ = container('probe')
    def traffic():
        return docker('exec', probe, 'python', '-c',
                      "import urllib.request; assert b'AI-SOC' in urllib.request.urlopen('http://172.30.77.10:8080',timeout=2).read()", check=False).returncode == 0
    async def expect_traffic(allowed):
        for _ in range(10):
            if await asyncio.to_thread(traffic) == allowed:
                return
            await asyncio.sleep(.5)
        raise AssertionError('Traffic did not match independently expected state')
    checks, audits = [], []
    store_url = 'sqlite+aiosqlite:///' + str(state / 'plan-acceptance.sqlite')
    for crash in (False, True):
        store = PlanStore(store_url)
        await store.initialize()
        orchestrator = ResponseOrchestrator(settings, store=store)
        identity = 'lab-plan-' + uuid.uuid4().hex
        action = PlannedAction(action_id=identity + '-action', action_type=ActionType.BLOCK_IP,
                               target=PROBE_IP, adapter=AdapterType.FIREWALL, confidence=.9,
                               impact_score=.8, safety_score=.9, composite_score=.85,
                               blast_radius=BlastRadius.LOW, approval_tier=ApprovalTier.HUMAN_REQUIRED,
                               requires_approval=True, parameters={'operation_id': identity})
        plan = DefensePlan(plan_id=identity, incident_id='controlled-lab-acceptance',
                           actions=[action], total_actions=1, dry_run=False, status=PlanStatus.AWAITING_APPROVAL)
        await store.save(plan, 'controlled_lab_plan_created', controlled_fixture=True)
        orchestrator._plans[identity] = plan
        applied = False
        try:
            await expect_traffic(True)
            if crash:
                plan.status = PlanStatus.EXECUTING
                action.status = ActionStatus.EXECUTING
                await store.save(plan, 'action_intent', action_id=action.action_id)
                applied = True  # A lost response can conceal a completed effect.
                effect = await orchestrator._adapters['firewall'].execute('block_ip', PROBE_IP, action.parameters)
                assert effect.success
                # Deliberately stop before recording the successful result.
                await orchestrator.close()
                await store.close()
                store = PlanStore(store_url)
                await store.initialize()
                orchestrator = ResponseOrchestrator(settings, store=store)
                await orchestrator.restore()
                plan = orchestrator.get_plan(identity)
                assert plan.status == PlanStatus.RECOVERY_REQUIRED
                await expect_traffic(False)
                await orchestrator.reconcile_action(identity, action.action_id, 'lab-acceptance-reviewer',
                    'verify_active', 'Controller observed the active policy; independent probe confirmed denied traffic')
                checks.append('A real effect survives an interrupted result write; restart requests reconciliation and observes without replay')
            else:
                applied = True
                approved = await orchestrator.approve_action(identity, action.action_id, True,
                    'lab-acceptance-reviewer', 'Approve this controlled probe-only test plan')
                assert approved.status == ActionStatus.COMPLETED
                await expect_traffic(False)
                for _ in range(100):
                    if plan.status == PlanStatus.RECOVERY_REQUIRED:
                        break
                    await asyncio.sleep(.1)
                assert plan.status == PlanStatus.RECOVERY_REQUIRED
                assert not plan.verification.evidence_available
                checks.append('Reviewer approval executes a real scoped block and records unavailable prevention evidence honestly')
            await orchestrator.request_rollback(identity, 'lab-acceptance-reviewer', 'Restore the controlled lab baseline')
            assert plan.status == PlanStatus.ROLLED_BACK
            await expect_traffic(True)
            applied = False
            events = await store.events(identity)
            assert any(event['event'] == 'rollback_result' for event in events)
            audits.append({'plan_id': identity, 'events': events, 'final_status': plan.status.value})
            checks.append(('Interrupted' if crash else 'Approved') + ' plan rollback restores real traffic and persists its audit')
            print('PASS', checks[-2], flush=True)
            print('PASS', checks[-1], flush=True)
        finally:
            if applied:
                restored = await orchestrator._adapters['firewall'].rollback('block_ip', PROBE_IP, action.parameters)
                assert restored.success, 'Lab rollback needs reconciliation'
            await orchestrator.close()
            await store.close()
    return {'status': 'passed', 'verified_at': datetime.now(timezone.utc).isoformat(),
            'checks': checks, 'audits': audits,
            'scope': 'Real engine/adapters/controller/traffic with authored fixture plans and isolated durable storage; no production prevention claim'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=ROOT / 'work/lab')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(asyncio.run(run(args.state_dir.resolve())), indent=2) + '\n')
