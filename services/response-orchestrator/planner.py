"""
Defense Planner - Response Orchestrator
AI-Augmented SOC

Generates ranked defense plans by combining:
  1. D3FEND countermeasure lookup for detected ATT&CK techniques
  2. Simulation results to estimate impact of each countermeasure
  3. LLM reasoning to score, rank, and explain the defense strategy

This is the novel component: no existing system uses simulation results
to rank candidate defenses before execution.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

from services.response_orchestrator.models import (
    ActionType,
    AdapterType,
    BlastRadius,
    ApprovalTier,
    PlannedAction,
    ActionStatus,
    DefensePlan,
    PlanStatus,
)
from services.response_orchestrator.d3fend import (
    D3FENDTechnique,
    get_countermeasures,
    get_unique_actions_for_incident,
)
from services.response_orchestrator.safety import (
    build_planned_action,
    check_plan_safety,
)

logger = logging.getLogger(__name__)


class DefensePlanner:
    """
    Generates defense plans for detected incidents.

    The planner takes:
      - Incident context (techniques, IPs, kill chain stage)
      - Simulation results (attack paths, host compromise rates, defense effectiveness)
      - Environment state (hosts, defenses, criticality)

    And produces:
      - A ranked list of PlannedActions with D3FEND mapping
      - A natural-language rationale explaining the strategy
      - Safety violations and warnings
    """

    def __init__(
        self,
        ollama_host: str = "http://ollama:11434",
        ollama_model: str = "llama3.2:3b",
        auto_execute_min: float = 0.70,
        auto_veto_min: float = 0.85,
    ):
        self.ollama_host = ollama_host
        self.ollama_model = ollama_model
        self.auto_execute_min = auto_execute_min
        self.auto_veto_min = auto_veto_min

    async def generate_plan(
        self,
        incident_id: str,
        detected_techniques: List[str],
        kill_chain_stage: str,
        source_ips: List[str],
        dest_ips: List[str],
        incident_summary: str,
        simulation_results: Optional[Dict[str, Any]] = None,
        environment: Optional[Dict[str, Any]] = None,
        dry_run: bool = True,
    ) -> DefensePlan:
        """
        Generate a complete defense plan for an incident.

        Args:
            incident_id: The incident being defended against
            detected_techniques: ATT&CK technique IDs from the incident
            kill_chain_stage: Current kill chain position
            source_ips: Attacker source IPs
            dest_ips: Target destination IPs
            incident_summary: Human-readable incident description
            simulation_results: Swarm simulation output (optional)
            environment: Environment state dict (optional)
            dry_run: If true, mark plan as dry-run

        Returns:
            A DefensePlan with ranked, classified actions
        """
        plan_id = (
            f"PLAN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
        )

        logger.info(
            f"Generating defense plan {plan_id} for incident {incident_id}: "
            f"{len(detected_techniques)} techniques, stage={kill_chain_stage}"
        )

        # Step 1: Get D3FEND countermeasures for all detected techniques
        d3fend_candidates = get_unique_actions_for_incident(detected_techniques)

        if not d3fend_candidates:
            logger.warning(
                f"No D3FEND countermeasures found for techniques: {detected_techniques}"
            )

        # Step 2: Score each candidate using simulation results and environment
        impact_scores = self._compute_impact_scores(
            d3fend_candidates, simulation_results, environment, dest_ips
        )

        # Step 3: Build classified PlannedActions
        actions = []
        action_counter = 0
        for d3f_technique in d3fend_candidates:
            # Determine the best target for this action
            targets = self._select_targets(
                d3f_technique, source_ips, dest_ips, environment
            )

            for target_ip, target_hostname, target_criticality in targets:
                action_counter += 1
                action_id = f"{plan_id}-ACT-{action_counter:03d}"

                impact = impact_scores.get((d3f_technique.technique_id, target_ip), 0.5)

                # Build which techniques this action counters
                countered = [
                    tid
                    for tid in detected_techniques
                    if d3f_technique in get_countermeasures(tid)
                ]

                action = build_planned_action(
                    action_id=action_id,
                    d3fend_technique=d3f_technique,
                    target_ip=target_ip,
                    target_hostname=target_hostname,
                    target_criticality=target_criticality,
                    impact_score=impact,
                    confidence=self._compute_confidence(
                        d3f_technique, simulation_results, kill_chain_stage
                    ),
                    counters_techniques=countered,
                    rationale="",  # Filled from policy below
                    auto_execute_min=self.auto_execute_min,
                    auto_veto_min=self.auto_veto_min,
                )
                actions.append(action)

        # Step 4: Deduplicate (same action_type + target)
        actions = self._deduplicate_actions(actions)

        # Step 5: Rank by composite score
        actions.sort(key=lambda a: a.composite_score, reverse=True)

        # Step 6: Generate an evidence-bounded policy summary
        rationale = await self._generate_rationale(
            incident_summary=incident_summary,
            detected_techniques=detected_techniques,
            kill_chain_stage=kill_chain_stage,
            actions=actions,
            simulation_results=simulation_results,
        )

        # Assign per-action rationale from the LLM output
        for action in actions:
            action.rationale = self._extract_action_rationale(
                action, rationale, simulation_results
            )

        # Step 7: Safety check
        violations = check_plan_safety(actions)
        for v in violations:
            logger.warning(f"Safety violation: [{v.severity}] {v.rule}: {v.detail}")

        # Extract simulation risk if available
        pre_risk = None
        sim_id = None
        if simulation_results:
            pre_risk = simulation_results.get("results_summary", {}).get("success_rate")
            sim_id = simulation_results.get("simulation_id")

        plan = DefensePlan(
            plan_id=plan_id,
            incident_id=incident_id,
            simulation_id=sim_id,
            status=PlanStatus.PLANNING,
            incident_summary=incident_summary,
            detected_techniques=detected_techniques,
            kill_chain_stage=kill_chain_stage,
            source_ips=source_ips,
            dest_ips=dest_ips,
            pre_defense_risk=pre_risk,
            simulation_summary=self._summarize_simulation(simulation_results),
            actions=actions,
            rationale=rationale,
            total_actions=len(actions),
            dry_run=dry_run,
        )

        logger.info(
            f"Defense plan {plan_id} generated: {len(actions)} actions, "
            f"{sum(1 for a in actions if not a.requires_approval)} auto-executable"
        )

        return plan

    # ----- Impact Scoring -----

    def _compute_impact_scores(
        self,
        candidates: List[D3FENDTechnique],
        simulation_results: Optional[Dict],
        environment: Optional[Dict],
        dest_ips: List[str],
    ) -> Dict[Tuple[str, str], float]:
        """
        Estimate the impact of each defense action using simulation data.

        If simulation results are available, impact is derived from:
        - Host compromise frequency (actions that protect frequently-compromised hosts score higher)
        - Defense effectiveness data (actions matching proven defenses score higher)
        - Weakest point data (actions addressing identified weaknesses score highest)

        Without simulation, falls back to heuristic scoring.
        """
        scores: Dict[Tuple[str, str], float] = {}

        if not simulation_results:
            # Heuristic: containment actions score higher than detection
            for candidate in candidates:
                for ip in dest_ips or ["0.0.0.0"]:
                    base = 0.5
                    if candidate.action_type in (
                        ActionType.ISOLATE_HOST,
                        ActionType.BLOCK_IP,
                        ActionType.REVOKE_CREDENTIALS,
                    ):
                        base = 0.70
                    elif candidate.action_type in (
                        ActionType.DEPLOY_EDR,
                        ActionType.ENABLE_MFA,
                    ):
                        base = 0.60
                    scores[(candidate.technique_id, ip)] = base
            return scores

        # Extract simulation signals
        host_compromise_freq = {}
        if "environment" in simulation_results:
            compromised = simulation_results["environment"].get("compromised_hosts", [])
            total_hosts = len(simulation_results["environment"].get("hosts", {}))
            for ip in compromised:
                host_compromise_freq[ip] = 1.0  # Was compromised in this run

        # From swarm data (if available)
        if "host_compromise_frequencies" in simulation_results:
            host_compromise_freq = simulation_results["host_compromise_frequencies"]

        # Defense effectiveness from simulation
        defense_effectiveness = simulation_results.get("defense_validation", {})

        # Weakest points
        weakest = {
            wp["vulnerability"]: wp["exploit_count"]
            for wp in simulation_results.get("weakest_points", [])
        }

        for candidate in candidates:
            for ip in dest_ips or ["0.0.0.0"]:
                base = 0.5

                # Hosts that were compromised more need more protection
                freq = host_compromise_freq.get(ip, 0.0)
                base = max(base, freq * 0.9)

                # Actions that match proven defenses get a boost
                if candidate.action_type == ActionType.DEPLOY_EDR:
                    edr_data = defense_effectiveness.get("edr", {})
                    if edr_data.get("blocked", 0) > 0:
                        base = max(base, 0.80)

                if candidate.action_type == ActionType.ENABLE_MFA:
                    mfa_data = defense_effectiveness.get("mfa", {})
                    if mfa_data.get("blocked", 0) > 0:
                        base = max(base, 0.85)

                # Check if this target appears in weakest points
                for vuln_key in weakest:
                    if ip in vuln_key:
                        if (
                            "no EDR" in vuln_key
                            and candidate.action_type == ActionType.DEPLOY_EDR
                        ):
                            base = 0.95
                        elif (
                            "no MFA" in vuln_key
                            and candidate.action_type == ActionType.ENABLE_MFA
                        ):
                            base = 0.95
                        elif (
                            "CVE-" in vuln_key
                            and candidate.action_type == ActionType.PATCH_VULNERABILITY
                        ):
                            base = 0.95

                scores[(candidate.technique_id, ip)] = min(base, 1.0)

        return scores

    def _compute_confidence(
        self,
        technique: D3FENDTechnique,
        simulation_results: Optional[Dict],
        kill_chain_stage: str,
    ) -> float:
        """Compute confidence in the action's effectiveness."""
        base = 0.60

        # Higher confidence if we have simulation data backing the decision
        if simulation_results:
            base += 0.15

        # Containment actions in active attack phases are higher confidence
        active_stages = {
            "lateral_movement",
            "execution",
            "privilege_escalation",
            "exfiltration",
            "impact",
        }
        if kill_chain_stage in active_stages:
            if technique.action_type in (
                ActionType.ISOLATE_HOST,
                ActionType.BLOCK_IP,
                ActionType.REVOKE_CREDENTIALS,
            ):
                base += 0.10

        # Detection-only actions always have high confidence (low risk)
        if technique.action_type in (
            ActionType.ADD_MONITORING,
            ActionType.DEPLOY_SIGMA_RULE,
        ):
            base = 0.90

        return min(round(base, 2), 0.99)

    # ----- Target Selection -----

    def _select_targets(
        self,
        technique: D3FENDTechnique,
        source_ips: List[str],
        dest_ips: List[str],
        environment: Optional[Dict],
    ) -> List[Tuple[str, str, str]]:
        """
        Select appropriate targets for a defense action.

        Returns list of (ip, hostname, criticality) tuples.
        """
        targets = []

        # Block IP actions target source (attacker) IPs
        if technique.action_type == ActionType.BLOCK_IP:
            for ip in source_ips:
                targets.append((ip, f"attacker-{ip}", "low"))
            return targets

        # DNS sinkhole targets domains, not IPs
        if technique.action_type == ActionType.SINKHOLE_DOMAIN:
            return [
                (domain, domain, "medium")
                for domain in (environment or {}).get("confirmed_malicious_domains", [])
            ]

        # Account controls require an explicit identity, never a victim host IP.
        if technique.action_type in {ActionType.DISABLE_ACCOUNT, ActionType.ENABLE_MFA}:
            return [
                (account, account, "high")
                for account in (environment or {}).get("affected_accounts", [])
            ]

        # Most defense actions target destination (victim) hosts
        hosts_data = {}
        if environment and "hosts" in environment:
            hosts_data = environment["hosts"]

        for ip in dest_ips:
            host_data = hosts_data.get(ip, {})
            hostname = host_data.get("hostname", ip)
            criticality = host_data.get("criticality", "medium")
            targets.append((ip, hostname, criticality))

        return targets

    # ----- Deduplication -----

    def _deduplicate_actions(self, actions: List[PlannedAction]) -> List[PlannedAction]:
        """Remove duplicate actions (same type + target), keeping highest scoring."""
        seen = {}
        for action in actions:
            key = (action.action_type, action.target)
            if key not in seen or action.composite_score > seen[key].composite_score:
                seen[key] = action
        return list(seen.values())

    # ----- LLM Rationale Generation -----

    async def _generate_rationale(
        self,
        incident_summary: str,
        detected_techniques: List[str],
        kill_chain_stage: str,
        actions: List[PlannedAction],
        simulation_results: Optional[Dict],
    ) -> str:
        """Summarize recorded policy and evidence without invented risk reductions."""
        evidence = (
            "A research simulation informed ranking."
            if simulation_results
            else "No simulation evidence was supplied; ranking uses policy heuristics."
        )
        return (
            f"Proposed response to {kill_chain_stage}; detected techniques: {', '.join(detected_techniques)}. "
            f"{len(actions)} actions have identifiable targets. {evidence} "
            "Approval requirements and actual outcomes are recorded on each action. "
            "Expected real-world risk reduction is unknown; only independent post-action evidence can establish effectiveness. "
            "Account and domain controls are omitted unless explicit affected_accounts or confirmed_malicious_domains are supplied in the environment."
        )

    def _extract_action_rationale(
        self,
        action: PlannedAction,
        plan_rationale: str,
        simulation_results: Optional[Dict],
    ) -> str:
        """Build per-action rationale from context."""
        parts = [
            f"{action.d3fend_label} ({action.d3fend_technique}): "
            f"{action.action_type.value} on {action.target}"
        ]

        if action.counters_techniques:
            parts.append(f"Counters: {', '.join(action.counters_techniques)}")

        if simulation_results and action.impact_score >= 0.8:
            parts.append("High heuristic priority in the supplied simulation")
        elif simulation_results and action.impact_score >= 0.6:
            parts.append("Moderate heuristic priority in the supplied simulation")

        if not action.requires_approval:
            parts.append(
                f"Eligible for configured execution policy (tier {action.approval_tier.name})"
            )
        else:
            parts.append(f"Requires approval (tier {action.approval_tier.name})")

        return ". ".join(parts)

    # ----- Helpers -----

    def _summarize_simulation(
        self, simulation_results: Optional[Dict]
    ) -> Optional[Dict]:
        """Extract a compact summary from full simulation results."""
        if not simulation_results:
            return None

        return {
            "simulation_id": simulation_results.get("simulation_id"),
            "total_actions": simulation_results.get("results_summary", {}).get(
                "total_actions", 0
            ),
            "success_rate": simulation_results.get("results_summary", {}).get(
                "success_rate", 0
            ),
            "detection_rate": simulation_results.get("results_summary", {}).get(
                "detection_rate", 0
            ),
            "weakest_points": simulation_results.get("weakest_points", [])[:5],
            "recommended_actions": simulation_results.get("recommended_actions", [])[
                :5
            ],
        }
