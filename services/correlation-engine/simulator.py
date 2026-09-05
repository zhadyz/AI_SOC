"""
Attack Campaign Simulator - Orchestration Engine
AI-Augmented SOC

Runs LLM-powered attacker agents through timesteps against an
infrastructure environment model. Produces a CampaignReport with
environment-specific predictions, defense validation, and
recommended preemptive actions.

No external dependencies beyond httpx + Ollama.
Inspired by OASIS architecture patterns, purpose-built for security.
"""

import asyncio
import json
import logging
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

from services.correlation_engine.environment import Environment
from services.correlation_engine.actions import (
    ActionOutcome,
    ActionResult,
    AgentState,
    execute_action,
    get_available_actions,
)
from services.correlation_engine.archetypes import AttackerAgent
from services.correlation_engine.defender_archetypes import DefenderAgent
from services.correlation_engine.defender_actions import (
    DefenderState,
    DefenderActionOutcome,
    execute_defender_action,
    get_available_defender_actions,
)

logger = logging.getLogger(__name__)


@dataclass
class SimulationConfig:
    """Configuration for a simulation run."""
    agent_archetypes: List[str] = field(
        default_factory=lambda: ["opportunist", "apt", "ransomware", "insider"]
    )
    defender_archetypes: List[str] = field(
        default_factory=lambda: ["soc_analyst", "incident_responder", "threat_hunter"]
    )
    defenders_enabled: bool = True
    timesteps: int = 3
    concurrency: int = 3
    ollama_host: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"


@dataclass
class TraceRecord:
    """A single action taken during simulation."""
    timestep: int
    agent_id: str
    archetype: str
    action_id: str
    target_ip: str
    result: str
    detected: bool
    kill_chain_stage: str
    mitre_technique: str
    reasoning: str
    detail: str


@dataclass
class DefenderTraceRecord:
    """A single defensive action taken during simulation."""
    timestep: int
    agent_id: str
    archetype: str
    action_id: str
    target_ip: str
    result: str
    environment_modified: bool
    defense_stage: str
    reasoning: str
    detail: str


@dataclass
class AgentCampaign:
    """Summary of one agent's campaign through the simulation."""
    agent_id: str
    archetype: str
    actions_taken: int
    successful_actions: int
    detected_actions: int
    hosts_compromised: List[str]
    final_kill_chain_stage: str
    data_exfiltrated: bool
    persistence_established: List[str]
    attack_path: List[Dict]


class CampaignSimulator:
    """
    Orchestrates attack campaign simulations.

    Spawns attacker agents with distinct archetypes, runs them through
    timesteps against the environment, records every action in a trace,
    and generates a structured report with predictions and defense validation.
    """

    def __init__(self, config: SimulationConfig):
        self.config = config
        self._semaphore = asyncio.Semaphore(config.concurrency)

    async def run(self, environment: Environment) -> Dict:
        """
        Execute a full simulation campaign.

        Returns a CampaignReport dict with predictions, defense validation,
        and recommended actions.
        """
        sim_id = f"SIM-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
        start_time = time.time()

        logger.info(
            f"Starting simulation {sim_id}: "
            f"{len(self.config.agent_archetypes)} agents, "
            f"{self.config.timesteps} timesteps"
        )

        # Create attacker agents
        agents: List[AttackerAgent] = []
        for i, archetype in enumerate(self.config.agent_archetypes):
            agent = AttackerAgent(
                agent_id=f"{archetype}-{i}",
                archetype=archetype,
                ollama_host=self.config.ollama_host,
                model=self.config.ollama_model,
            )
            # Insider starts with access to one internal host
            if archetype == "insider":
                internal_hosts = [
                    h for h in environment.get_all_hosts()
                    if not h.has_exposed_services() and h.criticality != "critical"
                ]
                if internal_hosts:
                    starting_host = internal_hosts[0]
                    agent.state.starting_access = starting_host.ip
                    agent.state.discovered_hosts.add(starting_host.ip)
                    agent.state.compromised_hosts.add(starting_host.ip)

            agents.append(agent)

        # Create defender agents (Phase 2: Red vs Blue)
        defenders: List[DefenderAgent] = []
        if self.config.defenders_enabled:
            for i, archetype in enumerate(self.config.defender_archetypes):
                defender = DefenderAgent(
                    agent_id=f"{archetype}-{i}",
                    archetype=archetype,
                    ollama_host=self.config.ollama_host,
                    model=self.config.ollama_model,
                )
                defenders.append(defender)
            logger.info(f"Simulation {sim_id}: {len(defenders)} defender agents active")

        # Run simulation timesteps
        all_traces: List[TraceRecord] = []
        all_defender_traces: List[DefenderTraceRecord] = []

        for timestep in range(self.config.timesteps):
            logger.info(f"Simulation {sim_id}: timestep {timestep + 1}/{self.config.timesteps}")

            # Phase 1: Attackers act
            attacker_tasks = [
                self._step_agent(agent, environment, timestep)
                for agent in agents
            ]
            timestep_traces = await asyncio.gather(*attacker_tasks, return_exceptions=True)

            timestep_attacker_traces = []
            for result in timestep_traces:
                if isinstance(result, TraceRecord):
                    all_traces.append(result)
                    timestep_attacker_traces.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Agent step failed: {result}")

            # Phase 2: Defenders react (only see detected actions)
            if defenders:
                alerts = self._generate_alerts(timestep_attacker_traces, environment)
                escalation_queue: List[Dict] = []

                defender_tasks = [
                    self._step_defender(
                        defender, environment, timestep, alerts, escalation_queue
                    )
                    for defender in defenders
                ]
                defender_results = await asyncio.gather(
                    *defender_tasks, return_exceptions=True
                )

                for result in defender_results:
                    if isinstance(result, DefenderTraceRecord):
                        all_defender_traces.append(result)
                        # Handle escalations for next timestep
                        if result.action_id == "escalate":
                            escalation_queue.append({
                                "from": result.agent_id,
                                "target_ip": result.target_ip,
                                "detail": result.reasoning,
                            })
                    elif isinstance(result, Exception):
                        logger.error(f"Defender step failed: {result}")

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Generate report
        report = self._generate_report(
            sim_id=sim_id,
            traces=all_traces,
            agents=agents,
            environment=environment,
            elapsed_ms=elapsed_ms,
            defender_traces=all_defender_traces,
            defenders=defenders,
        )

        # Reset environment for next simulation
        environment.reset()

        logger.info(
            f"Simulation {sim_id} complete: {len(all_traces)} attacker actions, "
            f"{len(all_defender_traces)} defender actions, {elapsed_ms}ms"
        )

        return report

    async def _step_agent(
        self,
        agent: AttackerAgent,
        env: Environment,
        timestep: int,
    ) -> Optional[TraceRecord]:
        """Execute one timestep for a single agent."""
        async with self._semaphore:
            try:
                # Build observation for this agent
                observation = env.to_observation(agent.state.discovered_hosts)
                observation["compromised_hosts"] = list(agent.state.compromised_hosts)
                observation["admin_hosts"] = list(agent.state.admin_hosts)
                observation["credentials_dumped"] = list(agent.state.credentials_dumped)
                observation["persistence_hosts"] = list(agent.state.persistence_hosts)

                # Get available actions
                available = get_available_actions(env, agent.state)

                if not available:
                    available = ["do_nothing"]

                # Agent decides action via LLM
                action_id, target_ip, reasoning = await agent.decide(
                    observation, available
                )

                # Validate target
                if not target_ip or not env.get_host(target_ip):
                    # Pick a valid target
                    all_ips = [h.ip for h in env.get_all_hosts()]
                    target_ip = all_ips[0] if all_ips else "unknown"

                # Execute action against environment
                outcome = execute_action(action_id, env, target_ip, agent.state)

                # Update agent memory
                agent.update_memory(action_id, target_ip, outcome)

                # Record trace
                trace = TraceRecord(
                    timestep=timestep,
                    agent_id=agent.agent_id,
                    archetype=agent.archetype,
                    action_id=action_id,
                    target_ip=target_ip,
                    result=outcome.result.value,
                    detected=outcome.detected,
                    kill_chain_stage=outcome.kill_chain_stage,
                    mitre_technique=outcome.mitre_technique_id,
                    reasoning=reasoning,
                    detail=outcome.detail,
                )

                logger.debug(
                    f"  {agent.agent_id}: {action_id} on {target_ip} -> "
                    f"{outcome.result.value} (detected={outcome.detected})"
                )

                return trace

            except Exception as e:
                logger.error(f"Agent {agent.agent_id} step failed: {e}")
                return None

    async def _step_defender(
        self,
        defender: DefenderAgent,
        env: Environment,
        timestep: int,
        alerts: List[Dict],
        escalation_queue: List[Dict],
    ) -> Optional[DefenderTraceRecord]:
        """Execute one defensive timestep for a single defender agent."""
        async with self._semaphore:
            try:
                observation = env.to_defender_observation(alerts, defender.state)
                available = get_available_defender_actions(env, defender.state)

                if not available:
                    available = ["do_nothing"]

                # Filter escalations (don't show agent its own)
                other_escalations = [
                    e for e in escalation_queue
                    if e.get("from") != defender.agent_id
                ]

                action_id, target_ip, reasoning = await defender.decide(
                    observation, available, alerts, other_escalations
                )

                # Validate target
                if not target_ip or not env.get_host(target_ip):
                    all_ips = [h.ip for h in env.get_all_hosts()]
                    target_ip = all_ips[0] if all_ips else "unknown"

                outcome = execute_defender_action(
                    action_id, env, target_ip, defender.state
                )
                defender.update_memory(action_id, target_ip, outcome)

                trace = DefenderTraceRecord(
                    timestep=timestep,
                    agent_id=defender.agent_id,
                    archetype=defender.archetype,
                    action_id=action_id,
                    target_ip=target_ip,
                    result=outcome.result.value,
                    environment_modified=outcome.environment_modified,
                    defense_stage=outcome.defense_stage,
                    reasoning=reasoning,
                    detail=outcome.detail,
                )

                logger.debug(
                    f"  {defender.agent_id}: {action_id} on {target_ip} -> "
                    f"{outcome.result.value} (env_modified={outcome.environment_modified})"
                )

                return trace

            except Exception as e:
                logger.error(f"Defender {defender.agent_id} step failed: {e}")
                return None

    def _generate_alerts(
        self, traces: List[TraceRecord], environment: Environment
    ) -> List[Dict]:
        """Convert attacker traces to defender-visible alerts.

        Only detected actions on hosts with detection capability become
        visible alerts. Undetected actions are invisible to defenders.
        """
        alerts = []
        for trace in traces:
            if not trace.detected:
                continue
            host = environment.get_host(trace.target_ip)
            if not host:
                continue
            if not (host.defenses.wazuh_agent or host.defenses.edr_present):
                continue

            severity = "medium"
            if trace.kill_chain_stage in (
                "exfiltration", "impact", "command_and_control"
            ):
                severity = "critical"
            elif trace.kill_chain_stage in (
                "lateral_movement", "privilege_escalation", "persistence"
            ):
                severity = "high"
            elif trace.kill_chain_stage in ("initial_access", "execution"):
                severity = "medium"
            else:
                severity = "low"

            alerts.append({
                "target_ip": trace.target_ip,
                "action_type": trace.action_id,
                "severity": severity,
                "kill_chain_stage": trace.kill_chain_stage,
                "mitre_technique": trace.mitre_technique,
                "detail": trace.detail,
                "timestep": trace.timestep,
            })
        return alerts

    def _generate_report(
        self,
        sim_id: str,
        traces: List[TraceRecord],
        agents: List[AttackerAgent],
        environment: Environment,
        elapsed_ms: int,
        defender_traces: Optional[List[DefenderTraceRecord]] = None,
        defenders: Optional[List[DefenderAgent]] = None,
    ) -> Dict:
        """Analyze simulation traces and produce a campaign report."""

        # Per-agent campaign summaries
        campaigns = []
        for agent in agents:
            agent_traces = [t for t in traces if t.agent_id == agent.agent_id]

            # Determine highest kill chain stage reached
            stage_order = [
                "reconnaissance", "initial_access", "execution", "persistence",
                "privilege_escalation", "lateral_movement", "collection",
                "command_and_control", "exfiltration", "impact",
            ]
            highest_stage = "none"
            for t in agent_traces:
                if t.result in ("success", "detected") and t.kill_chain_stage in stage_order:
                    idx = stage_order.index(t.kill_chain_stage)
                    if idx > stage_order.index(highest_stage) if highest_stage in stage_order else -1:
                        highest_stage = t.kill_chain_stage

            campaigns.append({
                "agent_id": agent.agent_id,
                "archetype": agent.archetype,
                "actions_taken": len(agent_traces),
                "successful_actions": sum(
                    1 for t in agent_traces if t.result in ("success", "detected")
                ),
                "detected_actions": sum(1 for t in agent_traces if t.detected),
                "hosts_compromised": list(agent.state.compromised_hosts),
                "final_kill_chain_stage": highest_stage,
                "data_exfiltrated": agent.state.exfiltrated,
                "persistence_established": list(agent.state.persistence_hosts),
                "attack_path": [
                    {
                        "timestep": t.timestep,
                        "action": t.action_id,
                        "target": t.target_ip,
                        "result": t.result,
                        "mitre": t.mitre_technique,
                        "reasoning": t.reasoning[:200],
                    }
                    for t in agent_traces
                ],
            })

        # Aggregate predictions
        successful_stages = Counter()
        attempted_stages = Counter()
        for t in traces:
            if t.kill_chain_stage and t.kill_chain_stage != "-":
                attempted_stages[t.kill_chain_stage] += 1
                if t.result in ("success", "detected"):
                    successful_stages[t.kill_chain_stage] += 1

        stage_probabilities = {}
        for stage in attempted_stages:
            stage_probabilities[stage] = round(
                successful_stages[stage] / attempted_stages[stage], 4
            ) if attempted_stages[stage] > 0 else 0.0

        # Defense validation
        defenses_tested = defaultdict(lambda: {"blocked": 0, "bypassed": 0})
        for t in traces:
            host = environment.get_host(t.target_ip)
            if not host:
                continue
            if host.defenses.mfa_enabled and t.action_id in ("brute_force_creds", "exploit_weak_password"):
                if t.result == "blocked":
                    defenses_tested["mfa"]["blocked"] += 1
                else:
                    defenses_tested["mfa"]["bypassed"] += 1
            if host.defenses.edr_present and t.action_id in ("deploy_payload", "credential_dump", "bypass_edr"):
                if t.result in ("blocked", "failure"):
                    defenses_tested["edr"]["blocked"] += 1
                else:
                    defenses_tested["edr"]["bypassed"] += 1
            if host.defenses.firewall_enabled and t.action_id in ("pivot_to_host", "exploit_public_service"):
                if t.result == "blocked":
                    defenses_tested["firewall"]["blocked"] += 1

        # Identify weakest points
        exploit_counts = Counter()
        for t in traces:
            if t.result in ("success", "detected"):
                host = environment.get_host(t.target_ip)
                if host:
                    for cve in host.get_cves():
                        exploit_counts[f"{t.target_ip} ({host.hostname}): {cve}"] += 1
                    if not host.defenses.mfa_enabled and t.action_id in ("brute_force_creds",):
                        exploit_counts[f"{t.target_ip} ({host.hostname}): no MFA"] += 1
                    if not host.defenses.edr_present and t.action_id in ("deploy_payload",):
                        exploit_counts[f"{t.target_ip} ({host.hostname}): no EDR"] += 1

        weakest_points = [
            {"vulnerability": vuln, "exploit_count": count}
            for vuln, count in exploit_counts.most_common(5)
        ]

        # Recommended preemptive actions
        recommended_actions = []
        for wp in weakest_points:
            vuln = wp["vulnerability"]
            if "CVE-" in vuln:
                recommended_actions.append({
                    "action": f"Patch vulnerability in {vuln.split(':')[0].strip()}",
                    "priority": 1,
                    "rationale": f"Exploited by {wp['exploit_count']} attacker agents: {vuln.split(':')[1].strip()}",
                })
            elif "no MFA" in vuln:
                recommended_actions.append({
                    "action": f"Enable MFA on {vuln.split(':')[0].strip()}",
                    "priority": 1,
                    "rationale": f"Brute force succeeded against {vuln.split(':')[0].strip()} without MFA",
                })
            elif "no EDR" in vuln:
                recommended_actions.append({
                    "action": f"Deploy EDR on {vuln.split(':')[0].strip()}",
                    "priority": 2,
                    "rationale": f"Payload deployment succeeded without EDR detection",
                })

        # Compile report
        total_actions = len(traces)
        total_success = sum(1 for t in traces if t.result in ("success", "detected"))
        total_detected = sum(1 for t in traces if t.detected)
        total_blocked = sum(1 for t in traces if t.result == "blocked")

        return {
            "simulation_id": sim_id,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_ms": elapsed_ms,
            "config": {
                "archetypes": self.config.agent_archetypes,
                "timesteps": self.config.timesteps,
                "model": self.config.ollama_model,
            },
            "environment": environment.snapshot(),
            "environment_summary": {
                "name": environment.name,
                "total_hosts": len(environment.hosts),
                "total_segments": len(environment.segments),
                "externally_exposed": len(environment.get_externally_exposed()),
                "hosts_with_cves": sum(1 for h in environment.get_all_hosts() if h.has_cves()),
            },
            "results_summary": {
                "total_actions": total_actions,
                "successful_actions": total_success,
                "detected_actions": total_detected,
                "blocked_actions": total_blocked,
                "success_rate": round(total_success / total_actions, 4) if total_actions > 0 else 0,
                "detection_rate": round(total_detected / total_actions, 4) if total_actions > 0 else 0,
            },
            "campaigns": campaigns,
            "predictions": {
                "stage_success_probability": stage_probabilities,
                "most_likely_next_stages": sorted(
                    stage_probabilities.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:5],
            },
            "defense_validation": dict(defenses_tested),
            "weakest_points": weakest_points,
            "recommended_actions": recommended_actions,
            **self._build_defender_report(
                defender_traces or [], defenders or [], traces
            ),
        }

    def _build_defender_report(
        self,
        defender_traces: List[DefenderTraceRecord],
        defenders: List[DefenderAgent],
        attacker_traces: List[TraceRecord],
    ) -> Dict:
        """Build the defender portion of the simulation report."""
        if not defenders:
            return {}

        # Count attacker actions blocked specifically by defender interventions
        defender_blocked = sum(
            1 for t in attacker_traces if t.result == "blocked"
            and ("blocked by defenders" in t.detail or "isolated" in t.detail
                 or "revoked" in t.detail)
        )

        # Per-defender campaigns
        defender_campaigns = []
        for defender in defenders:
            agent_traces = [
                t for t in defender_traces if t.agent_id == defender.agent_id
            ]
            defender_campaigns.append({
                "agent_id": defender.agent_id,
                "archetype": defender.archetype,
                "actions_taken": len(agent_traces),
                "successful_blocks": defender.state.successful_blocks,
                "investigations_completed": len(defender.state.investigated_hosts),
                "escalations_sent": len(defender.state.escalations_sent),
                "defense_path": [
                    {
                        "timestep": t.timestep,
                        "action": t.action_id,
                        "target": t.target_ip,
                        "result": t.result,
                        "reasoning": t.reasoning[:200],
                        "environment_modified": t.environment_modified,
                        "defense_stage": t.defense_stage,
                    }
                    for t in agent_traces
                ],
            })

        # Aggregate defender summary
        all_isolated = set()
        all_blocked = set()
        all_edr = set()
        creds_revoked = False
        for d in defenders:
            all_isolated.update(d.state.isolated_hosts)
            all_blocked.update(d.state.blocked_ips)
            all_edr.update(d.state.edr_deployed)
            if d.state.credentials_revoked:
                creds_revoked = True

        return {
            "defender_campaigns": defender_campaigns,
            "defender_summary": {
                "total_defender_actions": len(defender_traces),
                "hosts_isolated": list(all_isolated),
                "ips_blocked": list(all_blocked),
                "edr_deployed": list(all_edr),
                "credentials_revoked": creds_revoked,
                "attacks_prevented": defender_blocked,
            },
        }
