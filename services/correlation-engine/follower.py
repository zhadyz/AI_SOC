"""
Follower Agent - Swarm Architecture
AI-Augmented SOC

Lightweight rule-based agents that replay a leader's attack/defense path
with randomized parameters. No LLM calls — purely deterministic with
variance from re-rolled detection/success probabilities.

A single follower + 3 timesteps executes in ~0.3ms. 1000 followers
complete in under 1 second.
"""

import random
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from services.correlation_engine.environment import Environment
from services.correlation_engine.actions import (
    ActionResult,
    AgentState,
    execute_action,
    get_available_actions,
)
from services.correlation_engine.defender_actions import (
    DefenderState,
    execute_defender_action,
    get_available_defender_actions,
)

logger = logging.getLogger(__name__)


@dataclass
class FollowerConfig:
    """Configuration for a follower agent."""
    leader_agent_id: str
    leader_archetype: str
    follower_index: int
    seed: int
    target_jitter: bool = True
    is_defender: bool = False


@contextmanager
def _seeded_random(seed: int):
    """Temporarily seed the global random module, then restore state."""
    old_state = random.getstate()
    random.seed(seed)
    try:
        yield
    finally:
        random.setstate(old_state)


class FollowerAgent:
    """
    Replays a leader's attack path with randomized outcomes.

    Does NOT call the LLM. The leader already decided the strategy —
    the follower re-executes with different random seeds to explore
    the probability space.
    """

    def __init__(self, config: FollowerConfig):
        self.agent_id = f"{config.leader_archetype}-f{config.follower_index}"
        self.archetype = config.leader_archetype
        self.config = config
        self.rng = random.Random(config.seed)

    def replay_attack(
        self,
        leader_path: List[Dict],
        environment: Environment,
    ) -> Dict:
        """
        Replay a leader's attack path against an isolated environment copy.

        Returns a summary dict (not full trace records — too much memory at scale).
        """
        state = AgentState()

        # Insider starting access
        if self.archetype == "insider":
            internal_hosts = [
                h for h in environment.get_all_hosts()
                if not h.has_exposed_services() and h.criticality != "critical"
            ]
            if internal_hosts:
                host = internal_hosts[0]
                state.starting_access = host.ip
                state.discovered_hosts.add(host.ip)
                state.compromised_hosts.add(host.ip)

        actions_taken = 0
        successful = 0
        detected = 0
        blocked = 0
        path_actions = []

        for step in leader_path:
            action_id = step.get("action", "do_nothing")
            target_ip = step.get("target", "")
            timestep = step.get("timestep", 0)

            # Target jitter: 30% chance to pick a different host in same segment
            if self.config.target_jitter and target_ip and self.rng.random() < 0.3:
                target_ip = self._jitter_target(target_ip, environment)

            # Validate action is available
            available = get_available_actions(environment, state)
            if action_id not in available:
                # Fall back to first available or do_nothing
                if available:
                    action_id = self._pick_fallback(available, state, environment)
                else:
                    action_id = "do_nothing"

            # Validate target exists
            if not target_ip or not environment.get_host(target_ip):
                all_ips = [h.ip for h in environment.get_all_hosts()]
                target_ip = all_ips[0] if all_ips else ""

            # Execute with a unique seed for this step
            step_seed = self.config.seed * 1000 + timestep * 100 + actions_taken
            with _seeded_random(step_seed):
                outcome = execute_action(action_id, environment, target_ip, state)

            actions_taken += 1
            path_actions.append(action_id)

            if outcome.result in (ActionResult.SUCCESS, ActionResult.DETECTED):
                successful += 1
            if outcome.detected:
                detected += 1
            if outcome.result == ActionResult.BLOCKED:
                blocked += 1

        return {
            "agent_id": self.agent_id,
            "archetype": self.archetype,
            "leader_id": self.config.leader_agent_id,
            "actions_taken": actions_taken,
            "successful_actions": successful,
            "detected_actions": detected,
            "blocked_actions": blocked,
            "hosts_compromised": list(state.compromised_hosts),
            "final_kill_chain_stage": self._highest_stage(path_actions),
            "data_exfiltrated": state.exfiltrated,
            "path_sequence": "->".join(path_actions),
        }

    def replay_defense(
        self,
        leader_path: List[Dict],
        environment: Environment,
        alerts_per_timestep: Dict[int, List[Dict]],
    ) -> Dict:
        """Replay a leader's defense path with randomized outcomes."""
        state = DefenderState()
        actions_taken = 0
        successful_blocks = 0

        for step in leader_path:
            action_id = step.get("action", "do_nothing")
            target_ip = step.get("target", "")
            timestep = step.get("timestep", 0)

            # Target jitter for defenders too
            if self.config.target_jitter and target_ip and self.rng.random() < 0.2:
                target_ip = self._jitter_target(target_ip, environment)

            # Validate
            available = get_available_defender_actions(environment, state)
            if action_id not in available and available:
                action_id = available[0]

            if not target_ip or not environment.get_host(target_ip):
                all_ips = [h.ip for h in environment.get_all_hosts()]
                target_ip = all_ips[0] if all_ips else ""

            outcome = execute_defender_action(action_id, environment, target_ip, state)
            actions_taken += 1
            if outcome.environment_modified:
                successful_blocks += 1

        return {
            "agent_id": self.agent_id,
            "archetype": self.archetype,
            "leader_id": self.config.leader_agent_id,
            "actions_taken": actions_taken,
            "successful_blocks": successful_blocks,
            "hosts_isolated": list(state.isolated_hosts),
            "ips_blocked": list(state.blocked_ips),
            "edr_deployed": list(state.edr_deployed),
            "credentials_revoked": state.credentials_revoked,
        }

    def _jitter_target(self, original_ip: str, env: Environment) -> str:
        """Pick a different host in the same network segment."""
        segment = env.get_segment_for_host(original_ip)
        if not segment or len(segment.host_ips) <= 1:
            return original_ip
        alternatives = [ip for ip in segment.host_ips if ip != original_ip]
        return self.rng.choice(alternatives) if alternatives else original_ip

    def _pick_fallback(
        self, available: List[str], state: AgentState, env: Environment
    ) -> str:
        """Simple rule-based fallback when leader's action isn't available."""
        # Priority: exploit > scan > credential > do_nothing
        priority = [
            "exploit_public_service", "brute_force_creds", "port_scan",
            "osint_enum", "credential_dump", "pass_the_hash",
            "pivot_to_host", "execute_command", "do_nothing",
        ]
        for action in priority:
            if action in available:
                return action
        return available[0]

    def _highest_stage(self, actions: List[str]) -> str:
        """Determine highest kill chain stage from action sequence."""
        stage_map = {
            "port_scan": "reconnaissance", "osint_enum": "reconnaissance",
            "exploit_public_service": "initial_access", "phishing": "initial_access",
            "brute_force_creds": "initial_access",
            "execute_command": "execution", "deploy_payload": "execution",
            "create_scheduled_task": "persistence",
            "exploit_local_vuln": "privilege_escalation",
            "credential_dump": "credential_access",
            "pass_the_hash": "lateral_movement", "pivot_to_host": "lateral_movement",
            "exfil_data": "exfiltration", "dns_tunnel_c2": "command_and_control",
            "encrypt_files": "impact",
        }
        stages = [
            "reconnaissance", "initial_access", "execution", "persistence",
            "privilege_escalation", "credential_access", "lateral_movement",
            "collection", "command_and_control", "exfiltration", "impact",
        ]
        highest = "none"
        for action in actions:
            stage = stage_map.get(action, "")
            if stage in stages:
                idx = stages.index(stage)
                if highest == "none" or idx > stages.index(highest):
                    highest = stage
        return highest
