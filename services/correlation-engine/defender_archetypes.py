"""
Defender Agent Archetypes - Attack Campaign Simulator
AI-Augmented SOC

Three LLM-powered defender agents that respond to attacks in real-time.
Mirrors the AttackerAgent pattern from archetypes.py.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

import httpx

from services.correlation_engine.defender_actions import (
    DefenderState,
    DefenderActionOutcome,
    get_available_defender_actions,
    format_defender_actions_for_prompt,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Defender personality prompts
# ---------------------------------------------------------------------------

DEFENDER_ARCHETYPE_PROMPTS: Dict[str, str] = {
    "soc_analyst": """You are a SOC Analyst monitoring a live security environment.
You receive alerts from detection systems (Wazuh, EDR). You triage, classify severity, and escalate.
You do NOT take containment actions directly — you acknowledge alerts, investigate hosts,
and escalate confirmed threats for the Incident Responder to act on.
You are methodical and conservative. You never isolate or block without strong evidence.
If an alert is low severity or ambiguous, you investigate first before escalating.
You track patterns across multiple alerts to identify coordinated attacks.
Preferred actions: acknowledge_alert, investigate_host, escalate, do_nothing.
You never use: isolate_host, block_ip, revoke_credentials (those are IR actions).""",

    "incident_responder": """You are an Incident Responder. You take decisive containment actions.
When threats are confirmed — especially via escalations from the SOC Analyst — you act fast.
You isolate compromised hosts, block attacker IPs, revoke dumped credentials, deploy EDR.
You are aggressive when the threat is confirmed but do not act on unconfirmed alerts alone.
You prioritize containment of active compromise over investigation.
Critical hosts (databases, domain controllers) get priority protection.
If credentials have been dumped, revoke them immediately.
If a host is compromised and has lateral movement capability, isolate it now.
Preferred actions: isolate_host, block_ip, revoke_credentials, deploy_edr.
You rely on escalation signals from analysts to prioritize targets.""",

    "threat_hunter": """You are a Threat Hunter proactively searching for indicators of compromise.
You look for patterns the SOC Analyst may miss: lateral movement chains,
credential reuse across hosts, persistence mechanisms, and reconnaissance sweeps.
You think in terms of attacker TTPs — if you see a port scan, you predict initial access next.
You investigate hosts that haven't triggered alerts but are in the blast radius.
You can recommend preemptive blocks on hosts the attacker hasn't reached yet.
You focus on high-value targets: domain controllers, databases, file servers.
Preferred actions: investigate_host, block_ip, deploy_edr, escalate, do_nothing.
You are proactive — you do not wait for alerts to find threats.""",
}


# ---------------------------------------------------------------------------
# Defender Agent
# ---------------------------------------------------------------------------

class DefenderAgent:
    """
    LLM-powered defender agent with a distinct defensive archetype.

    Observes alerts and environment state, selects defensive actions via Ollama,
    and falls back to rule-based selection when LLM response is unparseable.
    """

    def __init__(
        self,
        agent_id: str,
        archetype: str,
        ollama_host: str,
        model: str,
    ) -> None:
        if archetype not in DEFENDER_ARCHETYPE_PROMPTS:
            raise ValueError(
                f"Unknown defender archetype '{archetype}'. "
                f"Valid: {list(DEFENDER_ARCHETYPE_PROMPTS.keys())}"
            )

        self.agent_id = agent_id
        self.archetype = archetype
        self.ollama_host = ollama_host.rstrip("/")
        self.model = model
        self.state = DefenderState()
        self.memory: List[str] = []
        self.system_prompt = DEFENDER_ARCHETYPE_PROMPTS[archetype]

    async def decide(
        self,
        observation: dict,
        available_actions: List[str],
        alerts: List[dict],
        escalations: List[dict],
    ) -> Tuple[str, str, str]:
        """
        Given alerts, environment observation, and available actions, choose next action.
        Returns (action_id, target_ip, reasoning).
        """
        if not available_actions:
            return "do_nothing", "", "No defensive actions available"

        actions_text = format_defender_actions_for_prompt(available_actions)
        prompt = self._build_decision_prompt(observation, actions_text, alerts, escalations)

        logger.info(
            "defender_deciding",
            extra={
                "agent_id": self.agent_id,
                "archetype": self.archetype,
                "alert_count": len(alerts),
                "escalation_count": len(escalations),
            },
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 512},
                        "format": "json",
                    },
                )

                if response.status_code == 200:
                    raw = response.json().get("response", "{}")
                    parsed = json.loads(raw)

                    action_id = parsed.get("action", "").strip()
                    target_ip = parsed.get("target", "").strip()
                    reasoning = parsed.get("reasoning", "No reasoning").strip()

                    if action_id not in available_actions:
                        return self._fallback_decision(
                            available_actions, observation, alerts, escalations
                        )

                    # Validate target IP
                    known_ips = [h["ip"] for h in observation.get("monitored_hosts", [])]
                    alert_ips = [a.get("target_ip", "") for a in alerts]
                    all_ips = list(set(known_ips + alert_ips))
                    if target_ip not in all_ips and all_ips:
                        target_ip = all_ips[0]

                    return action_id, target_ip, reasoning

        except httpx.TimeoutException:
            logger.error("defender_ollama_timeout", extra={"agent_id": self.agent_id})
        except json.JSONDecodeError as exc:
            logger.error("defender_json_error", extra={"agent_id": self.agent_id, "error": str(exc)})
        except Exception as exc:
            logger.error("defender_decision_error", extra={"agent_id": self.agent_id, "error": str(exc)})

        return self._fallback_decision(available_actions, observation, alerts, escalations)

    def update_memory(self, action_id: str, target: str, outcome: DefenderActionOutcome) -> None:
        """Record action outcome in defender memory."""
        entry = (
            f"[{action_id}] target={target} "
            f"result={outcome.result.value} "
            f"env_modified={outcome.environment_modified} "
            f"detail={outcome.detail}"
        )
        self.memory.append(entry)
        if len(self.memory) > 10:
            self.memory = self.memory[-10:]

    def _build_decision_prompt(
        self, observation: dict, actions_text: str,
        alerts: List[dict], escalations: List[dict],
    ) -> str:
        """Build the full decision prompt for Ollama."""
        memory_section = ""
        if self.memory:
            past = "\n".join(f"  {e}" for e in self.memory[-5:])
            memory_section = f"\n\nYOUR RECENT ACTIONS (last 5):\n{past}"

        alerts_text = "No new alerts this cycle."
        if alerts:
            alert_lines = []
            for a in alerts:
                alert_lines.append(
                    f"  [{a.get('severity', '?')}] {a.get('action_type', '?')} on "
                    f"{a.get('target_ip', '?')} — {a.get('detail', '')}"
                )
            alerts_text = "ALERTS THIS CYCLE:\n" + "\n".join(alert_lines)

        escalation_text = ""
        if escalations:
            esc_lines = [
                f"  From {e.get('from', '?')}: threat on {e.get('target_ip', '?')} — {e.get('detail', '')}"
                for e in escalations
            ]
            escalation_text = f"\n\nESCALATIONS RECEIVED:\n" + "\n".join(esc_lines)

        obs_text = json.dumps(observation, indent=2, default=str)

        prompt = (
            f"{self.system_prompt}\n\n"
            f"=== {alerts_text} ===\n"
            f"{escalation_text}\n\n"
            f"=== ENVIRONMENT STATUS ===\n{obs_text}"
            f"{memory_section}\n\n"
            f"=== {actions_text} ===\n\n"
            f"=== DECISION REQUIRED ===\n"
            f"Based on the alerts, escalations, and your defensive role, choose the optimal action.\n"
            f"You MUST select an action from the available actions list.\n"
            f"You MUST select a target IP from the monitored hosts or alert targets.\n\n"
            f"Respond with ONLY a JSON object:\n"
            f'{{"action": "<action_id>", "target": "<ip_address>", "reasoning": "<1-2 sentence explanation>"}}'
        )
        return prompt

    def _fallback_decision(
        self,
        available_actions: List[str],
        observation: dict,
        alerts: List[dict],
        escalations: List[dict],
    ) -> Tuple[str, str, str]:
        """Rule-based fallback when LLM response cannot be parsed."""
        alert_ips = [a.get("target_ip", "") for a in alerts if a.get("target_ip")]
        escalated_ips = [e.get("target_ip", "") for e in escalations if e.get("target_ip")]
        monitored_ips = [h["ip"] for h in observation.get("monitored_hosts", [])]
        default_target = alert_ips[0] if alert_ips else (monitored_ips[0] if monitored_ips else "")

        # High-severity alerts → investigate
        high_alerts = [a for a in alerts if a.get("severity") in ("high", "critical")]
        if high_alerts and "investigate_host" in available_actions:
            return (
                "investigate_host",
                high_alerts[0].get("target_ip", default_target),
                "Fallback: high-severity alert detected, investigating",
            )

        # Escalation received → isolate
        if escalated_ips and "isolate_host" in available_actions:
            return (
                "isolate_host",
                escalated_ips[0],
                "Fallback: escalation received, isolating target",
            )

        # Any alerts → acknowledge
        if alert_ips and "acknowledge_alert" in available_actions:
            return (
                "acknowledge_alert",
                alert_ips[0],
                "Fallback: acknowledging alert",
            )

        # Default
        if "do_nothing" in available_actions:
            return "do_nothing", default_target, "Fallback: monitoring"

        return available_actions[0], default_target, "Fallback: first available action"
