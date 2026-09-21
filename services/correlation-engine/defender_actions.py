"""
Defender Action Space - Attack Campaign Simulator
AI-Augmented SOC

8 defender actions for SOC Analyst, Incident Responder, and Threat Hunter
agents. Each action has prerequisites, an evaluator, and environment
mutations. Mirrors the attacker actions.py pattern.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from services.correlation_engine.actions import ActionResult

logger = logging.getLogger(__name__)


@dataclass
class DefenderState:
    """Tracks what a defender agent knows and has done."""
    investigated_hosts: Set[str] = field(default_factory=set)
    blocked_ips: Set[str] = field(default_factory=set)
    isolated_hosts: Set[str] = field(default_factory=set)
    edr_deployed: Set[str] = field(default_factory=set)
    credentials_revoked: bool = False
    acknowledged_alerts: List[str] = field(default_factory=list)
    escalations_sent: List[str] = field(default_factory=list)
    successful_blocks: int = 0
    total_actions: int = 0


@dataclass
class DefenderActionOutcome:
    """Result of a defender action."""
    action_id: str
    result: ActionResult
    target_ip: str
    detail: str
    environment_modified: bool
    defense_stage: str  # detection, containment, investigation, prevention


# ---------------------------------------------------------------------------
# Action definitions
# ---------------------------------------------------------------------------

def _eval_acknowledge_alert(env, target_ip, defender_state):
    defender_state.acknowledged_alerts.append(target_ip)
    return DefenderActionOutcome(
        action_id="acknowledge_alert",
        result=ActionResult.SUCCESS,
        target_ip=target_ip,
        detail=f"Alert for {target_ip} acknowledged and triaged",
        environment_modified=False,
        defense_stage="detection",
    )


def _eval_investigate_host(env, target_ip, defender_state):
    host = env.get_host(target_ip)
    if not host:
        return DefenderActionOutcome(
            action_id="investigate_host",
            result=ActionResult.FAILURE,
            target_ip=target_ip,
            detail=f"Host {target_ip} not found in environment",
            environment_modified=False,
            defense_stage="investigation",
        )

    defender_state.investigated_hosts.add(target_ip)
    findings = []
    if host.compromised:
        findings.append("HOST IS COMPROMISED")
    if host.admin_access:
        findings.append("attacker has admin access")
    if host.persistence_installed:
        findings.append("persistence mechanism detected")
    if host.credentials_dumped:
        findings.append("credentials have been dumped")

    detail = (
        f"Investigation of {target_ip} ({host.hostname}): "
        + (", ".join(findings) if findings else "no indicators of compromise found")
    )
    return DefenderActionOutcome(
        action_id="investigate_host",
        result=ActionResult.SUCCESS,
        target_ip=target_ip,
        detail=detail,
        environment_modified=False,
        defense_stage="investigation",
    )


def _eval_block_ip(env, target_ip, defender_state):
    if target_ip in env.blocked_ips:
        return DefenderActionOutcome(
            action_id="block_ip",
            result=ActionResult.SUCCESS,
            target_ip=target_ip,
            detail=f"IP {target_ip} is already blocked",
            environment_modified=False,
            defense_stage="containment",
        )

    env.blocked_ips.add(target_ip)
    defender_state.blocked_ips.add(target_ip)
    defender_state.successful_blocks += 1
    return DefenderActionOutcome(
        action_id="block_ip",
        result=ActionResult.SUCCESS,
        target_ip=target_ip,
        detail=f"IP {target_ip} blocked at firewall — all future attacks to/from this IP will be prevented",
        environment_modified=True,
        defense_stage="containment",
    )


def _eval_isolate_host(env, target_ip, defender_state):
    if target_ip in env.isolated_hosts:
        return DefenderActionOutcome(
            action_id="isolate_host",
            result=ActionResult.SUCCESS,
            target_ip=target_ip,
            detail=f"Host {target_ip} is already isolated",
            environment_modified=False,
            defense_stage="containment",
        )

    host = env.get_host(target_ip)
    if not host:
        return DefenderActionOutcome(
            action_id="isolate_host",
            result=ActionResult.FAILURE,
            target_ip=target_ip,
            detail=f"Host {target_ip} not found",
            environment_modified=False,
            defense_stage="containment",
        )

    env.isolated_hosts.add(target_ip)
    host.isolated = True
    defender_state.isolated_hosts.add(target_ip)
    defender_state.successful_blocks += 1
    return DefenderActionOutcome(
        action_id="isolate_host",
        result=ActionResult.SUCCESS,
        target_ip=target_ip,
        detail=f"Host {target_ip} ({host.hostname}) isolated from network — no lateral movement possible",
        environment_modified=True,
        defense_stage="containment",
    )


def _eval_deploy_edr(env, target_ip, defender_state):
    host = env.get_host(target_ip)
    if not host:
        return DefenderActionOutcome(
            action_id="deploy_edr",
            result=ActionResult.FAILURE,
            target_ip=target_ip,
            detail=f"Host {target_ip} not found",
            environment_modified=False,
            defense_stage="prevention",
        )

    if host.defenses.edr_present:
        return DefenderActionOutcome(
            action_id="deploy_edr",
            result=ActionResult.SUCCESS,
            target_ip=target_ip,
            detail=f"EDR already deployed on {target_ip}",
            environment_modified=False,
            defense_stage="prevention",
        )

    host.defenses.edr_present = True
    defender_state.edr_deployed.add(target_ip)
    return DefenderActionOutcome(
        action_id="deploy_edr",
        result=ActionResult.SUCCESS,
        target_ip=target_ip,
        detail=f"EDR deployed on {target_ip} ({host.hostname}) — payload deployment will now be detected/blocked",
        environment_modified=True,
        defense_stage="prevention",
    )


def _eval_revoke_credentials(env, target_ip, defender_state):
    if env.credentials_revoked:
        return DefenderActionOutcome(
            action_id="revoke_credentials",
            result=ActionResult.SUCCESS,
            target_ip=target_ip,
            detail="Credentials already revoked",
            environment_modified=False,
            defense_stage="containment",
        )

    env.credentials_revoked = True
    defender_state.credentials_revoked = True
    defender_state.successful_blocks += 1
    return DefenderActionOutcome(
        action_id="revoke_credentials",
        result=ActionResult.SUCCESS,
        target_ip=target_ip,
        detail="All dumped credentials revoked — pass-the-hash and credential reuse will fail",
        environment_modified=True,
        defense_stage="containment",
    )


def _eval_escalate(env, target_ip, defender_state):
    defender_state.escalations_sent.append(target_ip)
    return DefenderActionOutcome(
        action_id="escalate",
        result=ActionResult.SUCCESS,
        target_ip=target_ip,
        detail=f"Escalated threat on {target_ip} to incident responder",
        environment_modified=False,
        defense_stage="detection",
    )


def _eval_do_nothing(env, target_ip, defender_state):
    return DefenderActionOutcome(
        action_id="do_nothing",
        result=ActionResult.SUCCESS,
        target_ip=target_ip,
        detail="Monitoring — no action taken this cycle",
        environment_modified=False,
        defense_stage="detection",
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_DEFENDER_ACTION_REGISTRY = {
    "acknowledge_alert": {
        "name": "Acknowledge Alert",
        "description": "Triage and acknowledge an alert — no containment action",
        "defense_stage": "detection",
        "evaluate": _eval_acknowledge_alert,
        "check_prerequisites": lambda env, state: True,
    },
    "investigate_host": {
        "name": "Investigate Host",
        "description": "Deep forensic investigation — reveals hidden compromise, persistence, credential theft",
        "defense_stage": "investigation",
        "evaluate": _eval_investigate_host,
        "check_prerequisites": lambda env, state: True,
    },
    "block_ip": {
        "name": "Block IP at Firewall",
        "description": "Block all traffic to/from an IP — prevents future attacks from this source",
        "defense_stage": "containment",
        "evaluate": _eval_block_ip,
        "check_prerequisites": lambda env, state: True,
    },
    "isolate_host": {
        "name": "Isolate Host from Network",
        "description": "Remove host from all network segments — stops lateral movement to/from this host",
        "defense_stage": "containment",
        "evaluate": _eval_isolate_host,
        "check_prerequisites": lambda env, state: True,
    },
    "deploy_edr": {
        "name": "Deploy EDR Agent",
        "description": "Install EDR on a host — enables detection of payload deployment and credential dumping",
        "defense_stage": "prevention",
        "evaluate": _eval_deploy_edr,
        "check_prerequisites": lambda env, state: True,
    },
    "revoke_credentials": {
        "name": "Revoke Compromised Credentials",
        "description": "Invalidate all dumped credentials — blocks pass-the-hash and credential reuse attacks",
        "defense_stage": "containment",
        "evaluate": _eval_revoke_credentials,
        "check_prerequisites": lambda env, state: True,
    },
    "escalate": {
        "name": "Escalate to Incident Responder",
        "description": "Flag a host for priority response — other defenders will see this escalation",
        "defense_stage": "detection",
        "evaluate": _eval_escalate,
        "check_prerequisites": lambda env, state: True,
    },
    "do_nothing": {
        "name": "Monitor — No Action",
        "description": "Continue monitoring without taking action",
        "defense_stage": "detection",
        "evaluate": _eval_do_nothing,
        "check_prerequisites": lambda env, state: True,
    },
}


def get_available_defender_actions(env, defender_state: DefenderState) -> List[str]:
    """Return action_ids whose prerequisites are met."""
    return [
        action_id
        for action_id, action in _DEFENDER_ACTION_REGISTRY.items()
        if action["check_prerequisites"](env, defender_state)
    ]


def format_defender_actions_for_prompt(available_action_ids: List[str]) -> str:
    """Format available defender actions as text for LLM prompt."""
    lines = ["Available defensive actions:"]
    for action_id in available_action_ids:
        action = _DEFENDER_ACTION_REGISTRY.get(action_id)
        if action:
            lines.append(
                f"  - {action_id}: {action['name']} "
                f"(stage={action['defense_stage']}) — {action['description']}"
            )
    return "\n".join(lines)


def execute_defender_action(
    action_id: str,
    env,
    target_ip: str,
    defender_state: DefenderState,
) -> DefenderActionOutcome:
    """Execute a defender action and return the outcome."""
    action = _DEFENDER_ACTION_REGISTRY.get(action_id)

    if action is None:
        logger.error("unknown_defender_action", extra={"action_id": action_id})
        return DefenderActionOutcome(
            action_id=action_id,
            result=ActionResult.FAILURE,
            target_ip=target_ip,
            detail=f"Unknown defender action '{action_id}'",
            environment_modified=False,
            defense_stage="detection",
        )

    try:
        defender_state.total_actions += 1
        outcome = action["evaluate"](env, target_ip, defender_state)
        logger.info(
            "defender_action_executed",
            extra={
                "action_id": action_id,
                "target_ip": target_ip,
                "result": outcome.result.value,
                "env_modified": outcome.environment_modified,
            },
        )
        return outcome
    except Exception as exc:
        logger.error(
            "defender_action_error",
            extra={"action_id": action_id, "error": str(exc)},
        )
        return DefenderActionOutcome(
            action_id=action_id,
            result=ActionResult.FAILURE,
            target_ip=target_ip,
            detail=f"Defender action raised exception: {exc}",
            environment_modified=False,
            defense_stage="detection",
        )
