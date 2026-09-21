"""
Swarm Simulator - Monte Carlo Attack Campaign Engine
AI-Augmented SOC

Runs hierarchical leader/follower simulations across multiple Monte Carlo
batches and aggregates results into statistical output.

Leaders: LLM-powered agents (existing CampaignSimulator)
Followers: Rule-based agents (FollowerAgent) — no LLM, instant execution

Output shifts from anecdotal stories to DATA:
  "73% of attackers exploited this path"
  "web-server-01 compromised in 89% of simulations"
"""

import asyncio
import logging
import statistics
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable

from services.correlation_engine.environment import Environment
from services.correlation_engine.simulator import CampaignSimulator, SimulationConfig
from services.correlation_engine.follower import FollowerAgent, FollowerConfig

logger = logging.getLogger(__name__)


@dataclass
class SwarmConfig:
    """Configuration for a swarm simulation."""
    agent_archetypes: List[str] = field(
        default_factory=lambda: ["opportunist", "apt", "ransomware", "insider"]
    )
    defender_archetypes: List[str] = field(
        default_factory=lambda: ["soc_analyst", "incident_responder", "threat_hunter"]
    )
    defenders_enabled: bool = True
    timesteps: int = 3
    swarm_size: int = 50          # followers per leader strategy
    monte_carlo_runs: int = 10    # independent leader batches
    leaders_per_archetype: int = 3  # diverse LLM leaders per archetype per batch
    concurrency: int = 3
    ollama_host: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"
    target_jitter: bool = True
    env_randomization: bool = True  # randomize defenses/CVEs per batch


# ---------------------------------------------------------------------------
# Environment Randomizer
# ---------------------------------------------------------------------------

import copy
import random as _random


class EnvironmentRandomizer:
    """Randomly varies defenses and CVEs across Monte Carlo batches.

    Models uncertainty in infrastructure knowledge — maybe that host
    DOES have EDR but you forgot, maybe that CVE was patched last week.
    Each batch sees a slightly different environment, producing more
    realistic variance than pure dice-rolling.
    """

    def __init__(self, seed: int = 0):
        self.rng = _random.Random(seed)

    def randomize(self, env_snapshot: Dict, batch_idx: int) -> Dict:
        """Return a modified copy of the environment snapshot."""
        env = copy.deepcopy(env_snapshot)
        self.rng.seed(batch_idx * 7919)  # deterministic per batch

        for ip, host in env.get("hosts", {}).items():
            defenses = host.get("defenses", {})

            # 15% chance to flip each defense (models uncertainty)
            for key in ["mfa_enabled", "edr_present", "firewall_enabled", "patched"]:
                if key in defenses and self.rng.random() < 0.15:
                    defenses[key] = not defenses[key]

            # 20% chance to add or remove a CVE per service
            for svc in host.get("services", []):
                cves = svc.get("cves", [])
                if cves and self.rng.random() < 0.20:
                    # Remove a CVE (it was patched)
                    svc["cves"] = cves[:-1]
                elif not cves and self.rng.random() < 0.10:
                    # Add a plausible CVE (unknown vuln discovered)
                    svc["cves"] = [f"CVE-2024-{self.rng.randint(10000, 99999)}"]

        return env


class SwarmSimulator:
    """
    Orchestrates swarm simulations with hierarchical leader/follower model.

    For each Monte Carlo batch:
      1. Leaders decide via LLM (existing CampaignSimulator)
      2. Followers replay leader paths with randomized parameters
      3. Traces collected for aggregation

    After all batches: statistical aggregation into SwarmReport.
    """

    def __init__(self, config: SwarmConfig):
        self.config = config
        self._progress = {
            "status": "initializing",
            "current_batch": 0,
            "total_batches": config.monte_carlo_runs,
            "total_agent_runs": 0,
            "elapsed_ms": 0,
        }

    @property
    def progress(self) -> Dict:
        return dict(self._progress)

    async def run(
        self,
        environment: Environment,
        on_progress: Optional[Callable] = None,
    ) -> Dict:
        """Execute a full swarm simulation with Monte Carlo batches."""
        swarm_id = f"SWARM-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
        start_time = time.time()

        logger.info(
            f"Starting swarm {swarm_id}: {self.config.monte_carlo_runs} batches, "
            f"{self.config.swarm_size} followers/archetype, "
            f"{self.config.timesteps} timesteps"
        )

        self._progress["status"] = "running"
        all_batch_results = []
        env_snapshot = environment.snapshot()
        randomizer = EnvironmentRandomizer() if self.config.env_randomization else None

        # Cross-batch learning: accumulate successful strategies
        successful_strategies: List[Dict] = []

        for batch_idx in range(self.config.monte_carlo_runs):
            self._progress["current_batch"] = batch_idx + 1
            self._progress["elapsed_ms"] = int((time.time() - start_time) * 1000)

            if on_progress:
                on_progress(self._progress)

            logger.info(f"Swarm {swarm_id}: batch {batch_idx + 1}/{self.config.monte_carlo_runs}")

            # 1. Environment randomization per batch
            if randomizer:
                batch_env_data = randomizer.randomize(env_snapshot, batch_idx)
            else:
                batch_env_data = env_snapshot

            # 2. Run MULTIPLE diverse leaders per archetype
            # Each leader makes independent LLM decisions → strategic diversity
            all_leader_reports = []
            expanded_archetypes = []
            for archetype in self.config.agent_archetypes:
                for leader_idx in range(self.config.leaders_per_archetype):
                    expanded_archetypes.append(archetype)

            batch_env = Environment.from_dict(batch_env_data)
            leader_config = SimulationConfig(
                agent_archetypes=expanded_archetypes,
                defender_archetypes=self.config.defender_archetypes,
                defenders_enabled=self.config.defenders_enabled,
                timesteps=self.config.timesteps,
                concurrency=self.config.concurrency,
                ollama_host=self.config.ollama_host,
                ollama_model=self.config.ollama_model,
            )
            leader_sim = CampaignSimulator(leader_config)
            leader_report = await leader_sim.run(batch_env)

            # 3. Cross-batch learning: feed successful strategies to next batch
            for c in leader_report.get("campaigns", []):
                if len(c.get("hosts_compromised", [])) > 0:
                    path_seq = "->".join(
                        s.get("action", "?") for s in c.get("attack_path", [])
                    )
                    successful_strategies.append({
                        "archetype": c["archetype"],
                        "path": path_seq,
                        "hosts_compromised": len(c.get("hosts_compromised", [])),
                        "batch": batch_idx,
                    })

            # 4. Replay through followers
            follower_results = self._run_followers(
                leader_report, batch_env_data, batch_idx
            )

            total_runs = (
                len(leader_report.get("campaigns", []))
                + len(leader_report.get("defender_campaigns", []))
                + len(follower_results["attacker_summaries"])
                + len(follower_results["defender_summaries"])
            )
            self._progress["total_agent_runs"] += total_runs

            all_batch_results.append({
                "batch_idx": batch_idx,
                "leader_report": leader_report,
                "follower_results": follower_results,
            })

        elapsed_ms = int((time.time() - start_time) * 1000)
        self._progress["status"] = "aggregating"
        self._progress["elapsed_ms"] = elapsed_ms

        # 4. Aggregate across all batches (including emergent path detection)
        report = self._aggregate(
            swarm_id, all_batch_results, env_snapshot, elapsed_ms,
            successful_strategies,
        )

        self._progress["status"] = "complete"
        logger.info(
            f"Swarm {swarm_id} complete: {report['total_agent_runs']} agent runs, "
            f"{elapsed_ms}ms"
        )

        return report

    def _run_followers(
        self, leader_report: Dict, env_snapshot: Dict, batch_idx: int
    ) -> Dict:
        """Replay leader paths through follower agents."""
        attacker_summaries = []
        defender_summaries = []

        # Attacker followers
        for campaign in leader_report.get("campaigns", []):
            leader_path = campaign.get("attack_path", [])
            if not leader_path:
                continue

            for f_idx in range(self.config.swarm_size):
                seed = batch_idx * 100000 + hash(campaign["agent_id"]) % 10000 + f_idx
                follower_env = Environment.from_dict(env_snapshot)

                # Apply defender state from leader run
                self._apply_defender_state(follower_env, leader_report)

                follower = FollowerAgent(FollowerConfig(
                    leader_agent_id=campaign["agent_id"],
                    leader_archetype=campaign["archetype"],
                    follower_index=f_idx,
                    seed=seed,
                    target_jitter=self.config.target_jitter,
                ))

                summary = follower.replay_attack(leader_path, follower_env)
                attacker_summaries.append(summary)

        # Defender followers
        for def_campaign in leader_report.get("defender_campaigns", []):
            leader_path = def_campaign.get("defense_path", [])
            if not leader_path:
                continue

            for f_idx in range(self.config.swarm_size):
                seed = batch_idx * 100000 + hash(def_campaign["agent_id"]) % 10000 + f_idx + 50000
                follower_env = Environment.from_dict(env_snapshot)

                follower = FollowerAgent(FollowerConfig(
                    leader_agent_id=def_campaign["agent_id"],
                    leader_archetype=def_campaign["archetype"],
                    follower_index=f_idx,
                    seed=seed,
                    target_jitter=self.config.target_jitter,
                    is_defender=True,
                ))

                summary = follower.replay_defense(leader_path, follower_env, {})
                defender_summaries.append(summary)

        return {
            "attacker_summaries": attacker_summaries,
            "defender_summaries": defender_summaries,
        }

    def _apply_defender_state(self, env: Environment, leader_report: Dict) -> None:
        """Apply defender interventions from leader run to follower environment."""
        ds = leader_report.get("defender_summary", {})
        for ip in ds.get("ips_blocked", []):
            env.blocked_ips.add(ip)
        for ip in ds.get("hosts_isolated", []):
            env.isolated_hosts.add(ip)
            host = env.get_host(ip)
            if host:
                host.isolated = True
        if ds.get("credentials_revoked"):
            env.credentials_revoked = True
        for ip in ds.get("edr_deployed", []):
            host = env.get_host(ip)
            if host:
                host.defenses.edr_present = True

    def _aggregate(
        self,
        swarm_id: str,
        all_batch_results: List[Dict],
        env_snapshot: Dict,
        elapsed_ms: int,
        successful_strategies: Optional[List[Dict]] = None,
    ) -> Dict:
        """Aggregate all batch results into a SwarmReport."""
        hosts = env_snapshot.get("hosts", {})

        # Collect all agent summaries (leaders + followers)
        all_attacker_runs = []
        all_defender_runs = []
        batch_success_rates = []

        for batch in all_batch_results:
            lr = batch["leader_report"]
            fr = batch["follower_results"]

            # Leader campaigns as summaries
            for c in lr.get("campaigns", []):
                all_attacker_runs.append({
                    "archetype": c["archetype"],
                    "hosts_compromised": c.get("hosts_compromised", []),
                    "actions_taken": c.get("actions_taken", 0),
                    "successful_actions": c.get("successful_actions", 0),
                    "detected_actions": c.get("detected_actions", 0),
                    "data_exfiltrated": c.get("data_exfiltrated", False),
                    "path_sequence": "->".join(
                        s.get("action", "?") for s in c.get("attack_path", [])
                    ),
                    "is_leader": True,
                })

            # Follower summaries
            for fs in fr["attacker_summaries"]:
                all_attacker_runs.append({
                    "archetype": fs["archetype"],
                    "hosts_compromised": fs["hosts_compromised"],
                    "actions_taken": fs["actions_taken"],
                    "successful_actions": fs["successful_actions"],
                    "detected_actions": fs.get("detected_actions", 0),
                    "blocked_actions": fs.get("blocked_actions", 0),
                    "data_exfiltrated": fs.get("data_exfiltrated", False),
                    "path_sequence": fs.get("path_sequence", ""),
                    "is_leader": False,
                })

            # Leader defender campaigns
            for dc in lr.get("defender_campaigns", []):
                all_defender_runs.append({
                    "archetype": dc["archetype"],
                    "actions_taken": dc.get("actions_taken", 0),
                    "successful_blocks": dc.get("successful_blocks", 0),
                    "is_leader": True,
                })

            for ds in fr["defender_summaries"]:
                all_defender_runs.append({
                    "archetype": ds["archetype"],
                    "actions_taken": ds["actions_taken"],
                    "successful_blocks": ds["successful_blocks"],
                    "is_leader": False,
                })

            # Batch-level success rate
            batch_actions = sum(
                c.get("actions_taken", 0)
                for c in lr.get("campaigns", [])
            )
            batch_successes = sum(
                c.get("successful_actions", 0)
                for c in lr.get("campaigns", [])
            )
            if batch_actions > 0:
                batch_success_rates.append(batch_successes / batch_actions)

        total_agent_runs = len(all_attacker_runs) + len(all_defender_runs)

        return {
            "swarm_id": swarm_id,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_ms": elapsed_ms,
            "config": {
                "swarm_size": self.config.swarm_size,
                "monte_carlo_runs": self.config.monte_carlo_runs,
                "timesteps": self.config.timesteps,
                "agent_archetypes": self.config.agent_archetypes,
                "defender_archetypes": self.config.defender_archetypes,
                "defenders_enabled": self.config.defenders_enabled,
            },
            "total_simulations": self.config.monte_carlo_runs,
            "total_agent_runs": total_agent_runs,
            "host_risk_heatmap": self._compute_host_heatmap(
                all_attacker_runs, hosts
            ),
            "archetype_statistics": self._compute_archetype_stats(
                all_attacker_runs
            ),
            "path_frequency": self._compute_path_frequency(all_attacker_runs),
            "defense_effectiveness": self._compute_defense_effectiveness(
                all_attacker_runs, hosts
            ),
            "defender_statistics": self._compute_defender_stats(
                all_defender_runs
            ),
            "vulnerability_ranking": self._compute_vuln_ranking(
                all_attacker_runs, hosts
            ),
            "statistical_confidence": {
                "total_agent_runs": total_agent_runs,
                "convergence_achieved": _check_convergence(batch_success_rates),
                "convergence_batch": _convergence_batch(batch_success_rates),
                "batch_success_rate_series": [
                    round(r, 4) for r in batch_success_rates
                ],
            },
            "emergent_discoveries": self._detect_emergent_paths(
                all_attacker_runs
            ),
            "cross_batch_intelligence": self._build_cross_batch_intel(
                successful_strategies or [], all_batch_results
            ),
            "environment": env_snapshot,
        }

    # --- Statistical computation helpers ---

    def _compute_host_heatmap(
        self, runs: List[Dict], hosts: Dict
    ) -> Dict:
        """Per-host compromise statistics."""
        host_compromised = defaultdict(int)
        host_attacked = defaultdict(int)

        for run in runs:
            compromised = set(run.get("hosts_compromised", []))
            for ip in compromised:
                host_compromised[ip] += 1
            # Every run attacks all reachable hosts conceptually
            for ip in hosts:
                host_attacked[ip] += 1

        total_runs = len(runs) if runs else 1
        heatmap = {}
        for ip in hosts:
            comp_count = host_compromised.get(ip, 0)
            rate = comp_count / total_runs if total_runs > 0 else 0
            heatmap[ip] = {
                "hostname": hosts[ip].get("hostname", ip),
                "criticality": hosts[ip].get("criticality", "medium"),
                "compromise_rate": round(rate, 4),
                "compromise_count": comp_count,
                "total_runs": total_runs,
                "confidence_interval_95": _confidence_interval_95(rate, total_runs),
            }

        return heatmap

    def _compute_archetype_stats(self, runs: List[Dict]) -> Dict:
        """Per-archetype aggregated statistics."""
        by_archetype = defaultdict(list)
        for run in runs:
            by_archetype[run["archetype"]].append(run)

        stats = {}
        for archetype, arch_runs in by_archetype.items():
            hosts_counts = [len(r.get("hosts_compromised", [])) for r in arch_runs]
            success_rates = [
                r["successful_actions"] / max(r["actions_taken"], 1)
                for r in arch_runs
            ]
            detection_rates = [
                r.get("detected_actions", 0) / max(r["actions_taken"], 1)
                for r in arch_runs
            ]
            exfil_count = sum(1 for r in arch_runs if r.get("data_exfiltrated"))

            stats[archetype] = {
                "sample_size": len(arch_runs),
                **_compute_stats(hosts_counts, "hosts_compromised"),
                **_compute_stats(success_rates, "success_rate"),
                **_compute_stats(detection_rates, "detection_rate"),
                "data_exfiltration_rate": round(
                    exfil_count / max(len(arch_runs), 1), 4
                ),
            }

        return stats

    def _compute_path_frequency(self, runs: List[Dict]) -> Dict:
        """Attack path frequency analysis."""
        path_counter = Counter()
        path_successes = defaultdict(int)

        for run in runs:
            path = run.get("path_sequence", "")
            if path:
                path_counter[path] += 1
                comp = len(run.get("hosts_compromised", []))
                if comp > 0:
                    path_successes[path] += 1

        total = len(runs) if runs else 1
        result = {}
        for path, count in path_counter.most_common(20):
            result[path] = {
                "frequency": round(count / total, 4),
                "count": count,
                "success_rate": round(
                    path_successes.get(path, 0) / max(count, 1), 4
                ),
            }

        return result

    def _compute_defense_effectiveness(
        self, runs: List[Dict], hosts: Dict
    ) -> Dict:
        """Defense mechanism effectiveness statistics."""
        # Infer from host defenses + attack outcomes
        defense_tests = defaultdict(lambda: {"tested": 0, "blocked": 0})

        for run in runs:
            compromised = set(run.get("hosts_compromised", []))
            for ip, host_data in hosts.items():
                defenses = host_data.get("defenses", {})
                # MFA effectiveness
                if defenses.get("mfa_enabled"):
                    defense_tests["mfa"]["tested"] += 1
                    if ip not in compromised:
                        defense_tests["mfa"]["blocked"] += 1
                # EDR effectiveness
                if defenses.get("edr_present"):
                    defense_tests["edr"]["tested"] += 1
                    if ip not in compromised:
                        defense_tests["edr"]["blocked"] += 1
                # Firewall
                if defenses.get("firewall_enabled"):
                    defense_tests["firewall"]["tested"] += 1
                    if ip not in compromised:
                        defense_tests["firewall"]["blocked"] += 1
                # Patching
                if defenses.get("patched"):
                    defense_tests["patching"]["tested"] += 1
                    if ip not in compromised:
                        defense_tests["patching"]["blocked"] += 1

        result = {}
        for defense, counts in defense_tests.items():
            tested = counts["tested"]
            blocked = counts["blocked"]
            rate = blocked / max(tested, 1)
            result[defense] = {
                "block_rate": round(rate, 4),
                "times_tested": tested,
                "times_blocked": blocked,
                "confidence_interval_95": _confidence_interval_95(rate, tested),
            }

        return result

    def _compute_defender_stats(self, runs: List[Dict]) -> Dict:
        """Aggregated defender statistics."""
        if not runs:
            return {}

        blocks = [r.get("successful_blocks", 0) for r in runs]
        actions = [r.get("actions_taken", 0) for r in runs]

        return {
            "sample_size": len(runs),
            **_compute_stats(blocks, "blocks"),
            **_compute_stats(actions, "actions"),
        }

    def _compute_vuln_ranking(
        self, runs: List[Dict], hosts: Dict
    ) -> List[Dict]:
        """Rank vulnerabilities by exploit frequency × impact."""
        cve_exploits = Counter()
        cve_hosts = defaultdict(set)

        # Identify which CVEs are on which hosts
        host_cves = {}
        for ip, host_data in hosts.items():
            for svc in host_data.get("services", []):
                for cve in svc.get("cves", []):
                    cve_exploits[cve]  # init
                    cve_hosts[cve].add(ip)
                    host_cves.setdefault(ip, []).append(cve)

        # Count how often hosts with each CVE were compromised
        for run in runs:
            for ip in run.get("hosts_compromised", []):
                for cve in host_cves.get(ip, []):
                    cve_exploits[cve] += 1

        total_runs = len(runs) if runs else 1
        criticality_score = {"critical": 10, "high": 8, "medium": 5, "low": 2}

        ranking = []
        for cve, exploit_count in cve_exploits.most_common():
            cve_host_ips = list(cve_hosts.get(cve, set()))
            if not cve_host_ips:
                continue
            # Impact based on host criticality
            max_crit = max(
                criticality_score.get(
                    hosts.get(ip, {}).get("criticality", "medium"), 5
                )
                for ip in cve_host_ips
            )
            exploit_rate = exploit_count / total_runs
            hostname = hosts.get(cve_host_ips[0], {}).get("hostname", cve_host_ips[0])

            ranking.append({
                "vuln": cve,
                "host": cve_host_ips[0],
                "hostname": hostname,
                "exploit_rate": round(exploit_rate, 4),
                "exploit_count": exploit_count,
                "impact_score": max_crit,
                "priority_score": round(exploit_rate * max_crit, 4),
                "confidence_interval_95": _confidence_interval_95(
                    exploit_rate, total_runs
                ),
            })

        ranking.sort(key=lambda x: x["priority_score"], reverse=True)
        for i, r in enumerate(ranking):
            r["priority"] = i + 1

        return ranking

    def _detect_emergent_paths(self, all_runs: List[Dict]) -> List[Dict]:
        """Detect when followers discover paths MORE successful than leaders.

        This is genuine emergent intelligence: a follower's fallback decision
        (when the leader's action wasn't available due to divergent state)
        accidentally found a better attack path. These discoveries are
        insights no single agent would have produced.
        """
        # Group by archetype
        leader_paths = defaultdict(list)
        follower_paths = defaultdict(list)

        for run in all_runs:
            path = run.get("path_sequence", "")
            comp = len(run.get("hosts_compromised", []))
            archetype = run["archetype"]
            if run.get("is_leader"):
                leader_paths[archetype].append({"path": path, "compromised": comp})
            else:
                follower_paths[archetype].append({"path": path, "compromised": comp})

        discoveries = []
        for archetype in follower_paths:
            # Find leader success rate for this archetype
            leader_runs = leader_paths.get(archetype, [])
            if not leader_runs:
                continue
            leader_success = sum(1 for r in leader_runs if r["compromised"] > 0)
            leader_rate = leader_success / len(leader_runs) if leader_runs else 0
            leader_path_set = set(r["path"] for r in leader_runs)

            # Find follower paths that differ from ALL leader paths (diverged)
            # and have higher success rate
            follower_unique = defaultdict(lambda: {"count": 0, "successes": 0})
            for r in follower_paths[archetype]:
                if r["path"] not in leader_path_set and r["path"]:
                    follower_unique[r["path"]]["count"] += 1
                    if r["compromised"] > 0:
                        follower_unique[r["path"]]["successes"] += 1

            for path, stats in follower_unique.items():
                if stats["count"] < 3:
                    continue  # need minimum sample
                follower_rate = stats["successes"] / stats["count"]
                if follower_rate > leader_rate + 0.1:  # meaningfully better
                    discoveries.append({
                        "archetype": archetype,
                        "emergent_path": path,
                        "follower_success_rate": round(follower_rate, 4),
                        "leader_success_rate": round(leader_rate, 4),
                        "improvement": round(follower_rate - leader_rate, 4),
                        "sample_size": stats["count"],
                        "insight": (
                            f"Followers diverged from {archetype} leader strategy "
                            f"and discovered path '{path}' with "
                            f"{round(follower_rate * 100)}% success vs "
                            f"leader's {round(leader_rate * 100)}% — "
                            f"a {round((follower_rate - leader_rate) * 100)}pp improvement"
                        ),
                    })

        # Sort by improvement magnitude
        discoveries.sort(key=lambda x: x["improvement"], reverse=True)
        return discoveries[:10]

    def _build_cross_batch_intel(
        self, strategies: List[Dict], all_batch_results: List[Dict]
    ) -> Dict:
        """Build cross-batch intelligence showing how attacker effectiveness
        evolves across batches (simulating real-world attacker learning).

        Tracks: does the swarm get MORE effective in later batches? If yes,
        it means repeated probing reveals weaknesses — a predictive signal.
        """
        if not all_batch_results:
            return {}

        # Per-batch metrics
        batch_metrics = []
        for batch in all_batch_results:
            lr = batch["leader_report"]
            campaigns = lr.get("campaigns", [])
            total_comp = sum(
                len(c.get("hosts_compromised", [])) for c in campaigns
            )
            total_actions = sum(c.get("actions_taken", 0) for c in campaigns)
            total_success = sum(c.get("successful_actions", 0) for c in campaigns)
            batch_metrics.append({
                "batch": batch["batch_idx"],
                "hosts_compromised": total_comp,
                "success_rate": round(
                    total_success / max(total_actions, 1), 4
                ),
                "unique_strategies": len(set(
                    "->".join(s.get("action", "?") for s in c.get("attack_path", []))
                    for c in campaigns
                )),
            })

        # Detect trend: are later batches more effective?
        if len(batch_metrics) >= 3:
            early = batch_metrics[:len(batch_metrics) // 2]
            late = batch_metrics[len(batch_metrics) // 2:]
            early_rate = statistics.mean(m["success_rate"] for m in early)
            late_rate = statistics.mean(m["success_rate"] for m in late)
            early_comp = statistics.mean(m["hosts_compromised"] for m in early)
            late_comp = statistics.mean(m["hosts_compromised"] for m in late)
            trend = "improving" if late_rate > early_rate + 0.05 else (
                "degrading" if late_rate < early_rate - 0.05 else "stable"
            )
        else:
            early_rate = late_rate = 0
            early_comp = late_comp = 0
            trend = "insufficient_data"

        # Most successful strategies across all batches
        strat_counter = Counter()
        for s in strategies:
            strat_counter[f"{s['archetype']}: {s['path']}"] += s["hosts_compromised"]

        return {
            "batch_evolution": batch_metrics,
            "attacker_learning_trend": trend,
            "early_batch_success_rate": round(early_rate, 4),
            "late_batch_success_rate": round(late_rate, 4),
            "early_batch_compromises": round(early_comp, 2),
            "late_batch_compromises": round(late_comp, 2),
            "top_strategies": [
                {"strategy": strat, "total_compromises": count}
                for strat, count in strat_counter.most_common(5)
            ],
            "total_unique_strategies": len(set(s["path"] for s in strategies)),
            "strategic_diversity_score": round(
                len(set(s["path"] for s in strategies)) / max(len(strategies), 1), 4
            ) if strategies else 0,
        }


# ---------------------------------------------------------------------------
# Statistical helpers (module-level)
# ---------------------------------------------------------------------------


def _compute_stats(values: List[float], prefix: str) -> Dict:
    """Compute mean, std, min, max for a list of values."""
    if not values:
        return {
            f"{prefix}_mean": 0, f"{prefix}_std": 0,
            f"{prefix}_min": 0, f"{prefix}_max": 0,
        }
    return {
        f"{prefix}_mean": round(statistics.mean(values), 4),
        f"{prefix}_std": round(
            statistics.stdev(values) if len(values) > 1 else 0, 4
        ),
        f"{prefix}_min": round(min(values), 4),
        f"{prefix}_max": round(max(values), 4),
    }


def _confidence_interval_95(rate: float, n: int) -> List[float]:
    """Wilson score interval for binomial proportion."""
    if n == 0:
        return [0.0, 0.0]
    z = 1.96
    denom = 1 + z ** 2 / n
    centre = (rate + z ** 2 / (2 * n)) / denom
    margin = z * ((rate * (1 - rate) / n + z ** 2 / (4 * n ** 2)) ** 0.5) / denom
    return [round(max(0, centre - margin), 4), round(min(1, centre + margin), 4)]


def _check_convergence(batch_means: List[float], threshold: float = 0.05) -> bool:
    """Check if the running mean has stabilized."""
    if len(batch_means) < 3:
        return False
    recent = batch_means[-3:]
    return (max(recent) - min(recent)) < threshold


def _convergence_batch(batch_means: List[float], threshold: float = 0.05) -> int:
    """Find the batch where convergence was first achieved."""
    for i in range(2, len(batch_means)):
        window = batch_means[max(0, i - 2):i + 1]
        if len(window) >= 3 and (max(window) - min(window)) < threshold:
            return i + 1
    return -1
