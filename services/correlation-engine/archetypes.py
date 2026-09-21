"""
Attacker Agent Archetypes - Attack Campaign Simulator
AI-Augmented SOC

Four LLM-powered attacker agents with distinct behavioral profiles.
Uses httpx + Ollama /api/generate (same pattern as llm_client.py).
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import httpx

from services.correlation_engine.actions import AgentState, ActionOutcome, get_available_actions, format_actions_for_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Archetype personality prompts
# ---------------------------------------------------------------------------

ARCHETYPE_PROMPTS: Dict[str, str] = {
    "opportunist": """You are an opportunistic attacker with limited technical skill.
You scan indiscriminately for easy wins: default credentials, unpatched web apps, open ports.
You have no patience — if an attack takes more than two attempts, you move to the next target.
You bail immediately on any sign of detection; getting caught is catastrophic for you.
You prioritize speed over stealth and do not bother covering tracks unless trivial.
You prefer well-known, automated techniques that require minimal expertise.
Your goal is to compromise as many hosts as possible with minimal effort.
Avoid privilege escalation or lateral movement unless the path is obvious and low-risk.
You are driven by opportunism, not strategy — take what is easy, ignore what is hard.
When choosing targets, always prefer externally exposed, unpatched services.
If you have already compromised a host, look for even easier adjacent targets.
You would rather do nothing than attempt a complex technique that risks detection.
Prefer actions: port_scan, osint_enum, brute_force_creds, exploit_weak_password, phishing.
Avoid actions that have high observability or require significant prerequisites.""",

    "apt": """You are an Advanced Persistent Threat actor: nation-state caliber, patient, methodical.
Your primary objective is long-term, undetected access to high-value targets.
Stealth is paramount — you will wait, observe, and plan before executing any action.
You prefer low-observability actions and always clear logs after significant operations.
You target the highest-criticality hosts in the environment: database servers, domain controllers, HR systems.
You establish persistence before moving laterally, and bypass EDR before deploying payloads.
You use living-off-the-land techniques to blend into normal traffic wherever possible.
Credential dumping and pass-the-hash are preferred for lateral movement — no noisy scanning.
You exfiltrate data slowly over covert channels such as DNS tunneling.
You think in multi-step sequences: recon first, access second, establish persistence, then collect.
You never rush. If an action carries high detection risk, choose a lower-risk alternative and wait.
Your memory of past actions is critical — review it before every decision.
When in doubt, do nothing rather than risk burning your access.
Preferred action sequence: osint_enum -> exploit_public_service -> bypass_edr -> credential_dump -> pass_the_hash -> dns_tunnel_c2 -> exfil_data.""",

    "ransomware": """You are a ransomware operator focused on maximum impact in minimum time.
Speed is everything — you must encrypt as many systems as possible before defenders respond.
Stealth is secondary; you accept that you will eventually be detected and act before that happens.
Your goal is to achieve admin access on as many hosts as possible, then deploy ransomware simultaneously.
Lateral movement is your highest priority once initial access is established.
You spread aggressively using pass-the-hash and pivoting to every reachable host.
You deploy persistence on every host you compromise before moving to the next.
You target the most critical systems first: domain controllers, file servers, backup systems.
Credential dumping is essential — credentials enable fast, widespread lateral movement.
You do not bother with DNS tunneling or slow exfiltration; time is your scarcest resource.
Execute commands immediately after compromising hosts to deploy your staging payload.
When you have admin + persistence on a target, encrypt it immediately.
Do not waste time on reconnaissance beyond what is necessary to find your next target.
Preferred action sequence: brute_force_creds -> execute_command -> deploy_payload -> credential_dump -> pass_the_hash -> create_scheduled_task -> encrypt_files.""",

    "insider": """You are a malicious insider with legitimate network credentials and physical access.
You already have authenticated access to systems — you do not need to exploit external services.
Your goal is to steal specific sensitive data: financial records, intellectual property, HR data.
You use only normal, authorized tools to avoid triggering behavioral anomalies.
You work during normal business hours and mimic legitimate user activity patterns.
You never run port scans or exploit frameworks — that behavior would immediately stand out.
Your starting access is already configured; use it to navigate directly to target data.
You prefer exfiltration over slow, authorized channels: email, cloud sync, USB.
You are patient and deliberate — you have weeks or months before anyone notices.
Clear logs only when absolutely necessary; log clearing by non-admin users raises flags.
Focus on discovering what data is on each host before deciding whether to exfiltrate.
If you have admin access on a host, credential dumping gives you broader reach.
Never attempt exploitation of CVEs — that is the signature of an external attacker, not an insider.
Preferred action sequence: execute_command -> exfil_data (using existing access paths only).""",
}


# ---------------------------------------------------------------------------
# Agent implementation
# ---------------------------------------------------------------------------

class AttackerAgent:
    """
    LLM-powered attacker agent with a distinct behavioral archetype.

    The agent observes the environment, selects an action using Ollama,
    and falls back to rule-based selection when the LLM response is unparseable.
    """

    def __init__(
        self,
        agent_id: str,
        archetype: str,
        ollama_host: str,
        model: str,
    ) -> None:
        if archetype not in ARCHETYPE_PROMPTS:
            raise ValueError(
                f"Unknown archetype '{archetype}'. "
                f"Valid options: {list(ARCHETYPE_PROMPTS.keys())}"
            )

        self.agent_id = agent_id
        self.archetype = archetype
        self.ollama_host = ollama_host.rstrip("/")
        self.model = model
        self.state = AgentState()
        self.memory: List[str] = []  # rolling window of past action outcomes
        self.system_prompt = ARCHETYPE_PROMPTS[archetype]

    async def decide(
        self,
        observation: dict,
        available_actions: List[str],
    ) -> Tuple[str, str, str]:
        """
        Given environment observation and available actions, choose next action.

        Returns (action_id, target_ip, reasoning).

        Calls Ollama /api/generate with the archetype system prompt, current
        observation, available actions, and a rolling memory of past outcomes.
        Falls back to rule-based selection if the LLM response cannot be parsed.
        """
        if not available_actions:
            logger.warning(
                "no_available_actions",
                extra={"agent_id": self.agent_id, "archetype": self.archetype},
            )
            return "do_nothing", observation.get("target_ip", ""), "No actions available"

        actions_text = format_actions_for_prompt(available_actions)
        prompt = self._build_decision_prompt(observation, actions_text)

        logger.info(
            "agent_deciding",
            extra={
                "agent_id": self.agent_id,
                "archetype": self.archetype,
                "available_action_count": len(available_actions),
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
                        "options": {"temperature": 0.4, "num_predict": 512},
                        "format": "json",
                    },
                )

                if response.status_code == 200:
                    raw = response.json().get("response", "{}")
                    parsed = json.loads(raw)

                    action_id = parsed.get("action", "").strip()
                    target_ip = parsed.get("target", "").strip()
                    reasoning = parsed.get("reasoning", "No reasoning provided").strip()

                    # Validate the LLM chose a real, available action
                    if action_id not in available_actions:
                        logger.warning(
                            "llm_invalid_action",
                            extra={
                                "agent_id": self.agent_id,
                                "chosen": action_id,
                                "available": available_actions,
                            },
                        )
                        return self._fallback_decision(available_actions, observation)

                    # Validate the LLM chose a real IP from the observation
                    known_ips = (
                        list(observation.get("discovered_hosts", []))
                        + list(observation.get("all_host_ips", []))
                    )
                    if target_ip not in known_ips and known_ips:
                        target_ip = known_ips[0]

                    logger.info(
                        "llm_decision",
                        extra={
                            "agent_id": self.agent_id,
                            "action": action_id,
                            "target": target_ip,
                        },
                    )
                    return action_id, target_ip, reasoning

                else:
                    logger.error(
                        "ollama_api_error",
                        extra={
                            "agent_id": self.agent_id,
                            "status_code": response.status_code,
                        },
                    )

        except httpx.TimeoutException:
            logger.error(
                "ollama_timeout",
                extra={"agent_id": self.agent_id, "model": self.model},
            )
        except json.JSONDecodeError as exc:
            logger.error(
                "llm_json_parse_error",
                extra={"agent_id": self.agent_id, "error": str(exc)},
            )
        except Exception as exc:
            logger.error(
                "llm_decision_error",
                extra={"agent_id": self.agent_id, "error": str(exc)},
            )

        return self._fallback_decision(available_actions, observation)

    def update_memory(
        self,
        action_id: str,
        target: str,
        outcome: ActionOutcome,
    ) -> None:
        """Record action outcome in agent memory (rolling 10-entry window)."""
        entry = (
            f"[{action_id}] target={target} "
            f"result={outcome.result.value} "
            f"detected={outcome.detected} "
            f"detail={outcome.detail}"
        )
        self.memory.append(entry)
        # Keep only the most recent 10 entries to bound context size
        if len(self.memory) > 10:
            self.memory = self.memory[-10:]

        logger.debug(
            "memory_updated",
            extra={
                "agent_id": self.agent_id,
                "memory_length": len(self.memory),
                "latest_entry": entry,
            },
        )

    def _build_decision_prompt(self, observation: dict, actions_text: str) -> str:
        """Build the full decision prompt for Ollama."""
        memory_section = ""
        if self.memory:
            past = "\n".join(f"  {entry}" for entry in self.memory[-5:])
            memory_section = f"\n\nRECENT ACTION HISTORY (last 5 steps):\n{past}"

        observation_text = json.dumps(observation, indent=2, default=str)

        prompt = (
            f"{self.system_prompt}\n\n"
            f"=== CURRENT ENVIRONMENT OBSERVATION ===\n"
            f"{observation_text}"
            f"{memory_section}\n\n"
            f"=== AVAILABLE ACTIONS ===\n"
            f"{actions_text}\n\n"
            f"=== DECISION REQUIRED ===\n"
            f"Based on your archetype, goals, and current state, choose the optimal next action.\n"
            f"You MUST select an action from the available actions list above.\n"
            f"You MUST select a target IP from the discovered or reachable hosts in the observation.\n\n"
            f"Respond with ONLY a JSON object in this exact format:\n"
            f'{{"action": "<action_id>", "target": "<ip_address>", "reasoning": "<1-2 sentence explanation>"}}'
        )
        return prompt

    def _fallback_decision(
        self,
        available_actions: List[str],
        observation: dict,
    ) -> Tuple[str, str, str]:
        """
        Rule-based fallback when LLM response cannot be parsed.

        Priority rules:
        1. No discovered hosts -> port_scan on first available target
        2. Hosts discovered but none compromised -> exploit_public_service on CVE host
        3. Host compromised, no credentials -> credential_dump
        4. Credentials available -> pass_the_hash to reach next target
        5. Default -> do_nothing
        """
        discovered = list(observation.get("discovered_hosts", []))
        compromised = list(observation.get("compromised_hosts", []))
        admin_hosts = list(observation.get("admin_hosts", []))
        credentials_dumped = list(observation.get("credentials_dumped", []))
        all_ips = list(observation.get("all_host_ips", discovered))

        default_target = all_ips[0] if all_ips else ""

        # Rule 1: No discovered hosts — start with reconnaissance
        if not discovered and "port_scan" in available_actions and default_target:
            return (
                "port_scan",
                default_target,
                "Fallback: No hosts discovered yet; starting with port scan",
            )

        if not discovered and "osint_enum" in available_actions and default_target:
            return (
                "osint_enum",
                default_target,
                "Fallback: No hosts discovered; using passive OSINT enumeration",
            )

        # Rule 2: Hosts discovered but none compromised — try exploitation
        hosts_with_cves = observation.get("hosts_with_cves", [])
        if not compromised and hosts_with_cves and "exploit_public_service" in available_actions:
            return (
                "exploit_public_service",
                hosts_with_cves[0],
                "Fallback: Discovered hosts with CVEs; attempting exploitation",
            )

        if not compromised and discovered and "brute_force_creds" in available_actions:
            return (
                "brute_force_creds",
                discovered[0],
                "Fallback: No compromised hosts; attempting credential brute force",
            )

        # Rule 3: Have compromised hosts — escalate privileges
        if compromised and admin_hosts and not credentials_dumped:
            if "credential_dump" in available_actions:
                return (
                    "credential_dump",
                    admin_hosts[0],
                    "Fallback: Have admin access; dumping credentials for lateral movement",
                )

        if compromised and not admin_hosts:
            if "exploit_local_vuln" in available_actions:
                return (
                    "exploit_local_vuln",
                    compromised[0],
                    "Fallback: Have foothold but no admin; attempting local privilege escalation",
                )

        # Rule 4: Have credentials — use pass-the-hash
        unreached = [
            ip for ip in discovered
            if ip not in compromised
        ]
        if credentials_dumped and unreached and "pass_the_hash" in available_actions:
            return (
                "pass_the_hash",
                unreached[0],
                "Fallback: Have credentials; attempting pass-the-hash lateral movement",
            )

        if unreached and compromised and "pivot_to_host" in available_actions:
            return (
                "pivot_to_host",
                unreached[0],
                "Fallback: Have compromised hosts; pivoting to next reachable target",
            )

        # Rule 5: Default safe choice
        if "do_nothing" in available_actions:
            return (
                "do_nothing",
                default_target,
                "Fallback: No clear next step; waiting to avoid detection",
            )

        # Last resort — pick the first available action
        return (
            available_actions[0],
            default_target,
            "Fallback: Selecting first available action",
        )


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def create_agent(
    agent_id: str,
    archetype: str,
    ollama_host: str = "http://localhost:11434",
    model: str = "llama3.1",
) -> AttackerAgent:
    """
    Convenience factory for constructing an AttackerAgent.

    Args:
        agent_id:    Unique identifier for this agent instance.
        archetype:   One of 'opportunist', 'apt', 'ransomware', 'insider'.
        ollama_host: Base URL of the Ollama API server.
        model:       Ollama model identifier to use for decisions.

    Returns:
        AttackerAgent: Configured and ready to run.
    """
    logger.info(
        "agent_created",
        extra={
            "agent_id": agent_id,
            "archetype": archetype,
            "model": model,
            "ollama_host": ollama_host,
        },
    )
    return AttackerAgent(
        agent_id=agent_id,
        archetype=archetype,
        ollama_host=ollama_host,
        model=model,
    )
