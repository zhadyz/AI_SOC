"""
Synthetic Attack Campaign Dataset Generator
AI-Augmented SOC

Generates a dataset of attack campaigns by running the simulator
repeatedly with randomized infrastructure environments. Produces
a dataset of attacker decision-making that captures strategy,
reasoning, and outcomes — not just network flows.

Usage:
    python dataset_generator.py --runs 100 --output campaigns.json
    python dataset_generator.py --runs 500 --timesteps 5 --output large_dataset.json
"""

import argparse
import asyncio
import copy
import json
import logging
import random
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from services.correlation_engine.environment import Environment
from services.correlation_engine.simulator import CampaignSimulator, SimulationConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CVE pool used for probabilistic service injection
# ---------------------------------------------------------------------------

_CVE_POOL: Dict[str, List[str]] = {
    "nginx": ["CVE-2024-7347", "CVE-2023-44487", "CVE-2022-41741"],
    "apache": ["CVE-2024-38475", "CVE-2023-25690", "CVE-2021-41773"],
    "ssh": ["CVE-2023-38408", "CVE-2023-48795", "CVE-2021-28041"],
    "smb": ["CVE-2024-21334", "CVE-2023-35311", "CVE-2021-36942"],
    "rdp": ["CVE-2024-38077", "CVE-2023-28267", "CVE-2022-21990"],
    "postgresql": ["CVE-2024-10978", "CVE-2023-2454", "CVE-2022-21724"],
    "mysql": ["CVE-2024-20999", "CVE-2023-22005", "CVE-2022-21417"],
    "ldap": ["CVE-2023-28353", "CVE-2022-26925"],
    "postfix": ["CVE-2023-51764", "CVE-2022-3219"],
    "dovecot": ["CVE-2024-23185", "CVE-2022-30550"],
}


class EnvironmentRandomizer:
    """Generate randomized but realistic infrastructure environments."""

    def randomize(self, base_env: dict, seed: Optional[int] = None) -> dict:
        """
        Create a randomized variant of the base environment.

        Randomly varies:
        - Which hosts have MFA enabled (30-80% chance per host)
        - Which hosts have EDR deployed (20-60% chance)
        - Which hosts are patched (40-90% chance)
        - Which services have CVEs (add/remove CVEs probabilistically)
        - Firewall rules (enable/disable per host)
        - Network segment reachability (sometimes add/remove paths)
        """
        rng = random.Random(seed)
        env = copy.deepcopy(base_env)

        for ip, host_data in env.get("hosts", {}).items():
            defenses = host_data.setdefault("defenses", {})
            criticality = host_data.get("criticality", "medium")

            # Criticality-weighted defense probabilities
            if criticality == "critical":
                mfa_prob = rng.uniform(0.5, 0.95)
                edr_prob = rng.uniform(0.4, 0.85)
                patch_prob = rng.uniform(0.6, 0.95)
                fw_prob = rng.uniform(0.7, 1.0)
            elif criticality == "high":
                mfa_prob = rng.uniform(0.3, 0.80)
                edr_prob = rng.uniform(0.2, 0.70)
                patch_prob = rng.uniform(0.4, 0.90)
                fw_prob = rng.uniform(0.5, 0.95)
            else:
                mfa_prob = rng.uniform(0.1, 0.60)
                edr_prob = rng.uniform(0.1, 0.50)
                patch_prob = rng.uniform(0.3, 0.85)
                fw_prob = rng.uniform(0.3, 0.90)

            defenses["mfa_enabled"] = rng.random() < mfa_prob
            defenses["edr_present"] = rng.random() < edr_prob
            defenses["patched"] = rng.random() < patch_prob
            defenses["firewall_enabled"] = rng.random() < fw_prob

            # Randomize CVEs per service
            services = host_data.get("services", [])
            for svc in services:
                svc_name = svc.get("name", "").lower()
                pool = _CVE_POOL.get(svc_name, [])
                if not pool:
                    svc["cves"] = []
                    continue
                # Patched hosts rarely have CVEs; unpatched hosts often do
                if defenses["patched"]:
                    cve_count = rng.choices([0, 1], weights=[0.80, 0.20])[0]
                else:
                    cve_count = rng.choices([0, 1, 2], weights=[0.25, 0.50, 0.25])[0]
                svc["cves"] = rng.sample(pool, min(cve_count, len(pool)))

        # Randomize segment reachability (10% chance to add or remove a path)
        segments = env.get("segments", {})
        seg_names = list(segments.keys())
        for seg_name, seg_data in segments.items():
            reachable = list(seg_data.get("reachable_from", []))
            # Possibly add a new reachability link
            candidates = [s for s in seg_names if s != seg_name and s not in reachable]
            if candidates and rng.random() < 0.10:
                reachable.append(rng.choice(candidates))
            # Possibly remove a non-critical link
            non_critical = [r for r in reachable if r != "external"]
            if len(non_critical) > 1 and rng.random() < 0.10:
                reachable.remove(rng.choice(non_critical))
            seg_data["reachable_from"] = reachable

        return env


class DatasetGenerator:
    """Run N simulations and collect results into a dataset."""

    def __init__(
        self,
        ollama_host: str = "http://ollama:11434",
        ollama_model: str = "llama3.2:3b",
        concurrency: int = 3,
    ):
        self._ollama_host = ollama_host
        self._ollama_model = ollama_model
        self._concurrency = concurrency
        self._randomizer = EnvironmentRandomizer()

    async def generate(
        self,
        num_runs: int,
        base_environment: dict,
        timesteps: int = 3,
        output_path: Optional[str] = None,
    ) -> dict:
        """
        Run num_runs simulations with randomized environments.

        Returns a dataset dict with:
        - metadata: {total_runs, timesteps, archetypes, generation_time}
        - environments: [{run_id, environment_config}]
        - campaigns: [{run_id, agent_id, archetype, attack_path,
                       final_stage, success, hosts_compromised}]
        - traces: [{run_id, timestep, agent_id, action, target, result,
                    detected, mitre_technique, reasoning}]
        - statistics: {success_rate_by_archetype, most_exploited_cves,
                       avg_kill_chain_depth, detection_rate}
        """
        start_time = time.time()
        logger.info("DatasetGenerator: starting %d runs, %d timesteps", num_runs, timesteps)

        all_environments: List[dict] = []
        all_campaigns: List[dict] = []
        all_traces: List[dict] = []

        config = SimulationConfig(
            agent_archetypes=["opportunist", "apt", "ransomware", "insider"],
            timesteps=timesteps,
            concurrency=self._concurrency,
            ollama_host=self._ollama_host,
            ollama_model=self._ollama_model,
        )
        simulator = CampaignSimulator(config)

        stage_order = [
            "reconnaissance", "initial_access", "execution", "persistence",
            "privilege_escalation", "lateral_movement", "collection",
            "command_and_control", "exfiltration", "impact",
        ]

        for run_idx in range(num_runs):
            run_id = f"run-{run_idx:04d}"
            logger.info("DatasetGenerator: run %d/%d (%s)", run_idx + 1, num_runs, run_id)

            # Randomize environment for this run
            rand_env_dict = self._randomizer.randomize(base_environment, seed=run_idx)
            all_environments.append({"run_id": run_id, "environment_config": rand_env_dict})

            # Build Environment object and run simulation
            try:
                env = Environment.from_dict(rand_env_dict)
                report = await simulator.run(env)
            except Exception as exc:
                logger.warning("Run %s failed (skipping): %s", run_id, exc)
                continue

            # Flatten campaign records
            for camp in report.get("campaigns", []):
                hosts_compromised = camp.get("hosts_compromised", [])
                final_stage = camp.get("final_kill_chain_stage", "none")
                success = (
                    final_stage in stage_order
                    and stage_order.index(final_stage) >= stage_order.index("initial_access")
                )
                all_campaigns.append({
                    "run_id": run_id,
                    "agent_id": camp.get("agent_id"),
                    "archetype": camp.get("archetype"),
                    "attack_path": camp.get("attack_path", []),
                    "final_stage": final_stage,
                    "success": success,
                    "hosts_compromised": hosts_compromised,
                    "data_exfiltrated": camp.get("data_exfiltrated", False),
                    "persistence_established": camp.get("persistence_established", []),
                    "actions_taken": camp.get("actions_taken", 0),
                    "detected_actions": camp.get("detected_actions", 0),
                })

                # Flatten individual trace records from attack_path
                for step in camp.get("attack_path", []):
                    all_traces.append({
                        "run_id": run_id,
                        "timestep": step.get("timestep"),
                        "agent_id": camp.get("agent_id"),
                        "archetype": camp.get("archetype"),
                        "action": step.get("action"),
                        "target": step.get("target"),
                        "result": step.get("result"),
                        "detected": step.get("result") in ("detected",),
                        "mitre_technique": step.get("mitre"),
                        "reasoning": step.get("reasoning", ""),
                    })

        generation_time = round(time.time() - start_time, 2)
        statistics = self._compute_statistics(all_campaigns, all_traces)

        dataset = {
            "metadata": {
                "total_runs": num_runs,
                "completed_runs": len(all_environments),
                "timesteps": timesteps,
                "archetypes": config.agent_archetypes,
                "generation_time_seconds": generation_time,
                "generated_at": datetime.utcnow().isoformat(),
                "ollama_model": self._ollama_model,
            },
            "environments": all_environments,
            "campaigns": all_campaigns,
            "traces": all_traces,
            "statistics": statistics,
        }

        if output_path:
            try:
                with open(output_path, "w") as fh:
                    json.dump(dataset, fh, indent=2)
                logger.info("DatasetGenerator: dataset written to %s", output_path)
            except OSError as exc:
                logger.error("DatasetGenerator: failed to write output file: %s", exc)

        logger.info(
            "DatasetGenerator: complete — %d campaigns, %d traces in %.1fs",
            len(all_campaigns),
            len(all_traces),
            generation_time,
        )
        return dataset

    def _compute_statistics(self, all_campaigns: List[dict], all_traces: List[dict]) -> dict:
        """Aggregate statistics across all runs."""
        if not all_campaigns:
            return {}

        # Success rate per archetype
        by_archetype: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "success": 0})
        for camp in all_campaigns:
            arch = camp.get("archetype", "unknown")
            by_archetype[arch]["total"] += 1
            if camp.get("success"):
                by_archetype[arch]["success"] += 1

        success_rate_by_archetype = {
            arch: round(v["success"] / v["total"], 4) if v["total"] > 0 else 0.0
            for arch, v in by_archetype.items()
        }

        # Most exploited MITRE techniques from traces
        technique_counter: Counter = Counter()
        for trace in all_traces:
            if trace.get("result") in ("success", "detected"):
                tech = trace.get("mitre_technique")
                if tech and tech != "-":
                    technique_counter[tech] += 1

        # Kill chain depth (index of final stage for successful campaigns)
        stage_order = [
            "reconnaissance", "initial_access", "execution", "persistence",
            "privilege_escalation", "lateral_movement", "collection",
            "command_and_control", "exfiltration", "impact",
        ]
        depths = []
        for camp in all_campaigns:
            stage = camp.get("final_stage", "none")
            if stage in stage_order:
                depths.append(stage_order.index(stage))
        avg_kill_chain_depth = round(sum(depths) / len(depths), 3) if depths else 0.0

        # Overall detection rate across all traces
        total_traces = len(all_traces)
        detected_traces = sum(1 for t in all_traces if t.get("detected"))
        detection_rate = round(detected_traces / total_traces, 4) if total_traces > 0 else 0.0

        # Overall success rate
        total_campaigns = len(all_campaigns)
        successful_campaigns = sum(1 for c in all_campaigns if c.get("success"))
        overall_success_rate = round(successful_campaigns / total_campaigns, 4) if total_campaigns > 0 else 0.0

        # Most compromised hosts
        host_hit_counter: Counter = Counter()
        for camp in all_campaigns:
            for host in camp.get("hosts_compromised", []):
                host_hit_counter[host] += 1

        return {
            "total_campaigns": total_campaigns,
            "successful_campaigns": successful_campaigns,
            "overall_success_rate": overall_success_rate,
            "success_rate_by_archetype": success_rate_by_archetype,
            "most_exploited_techniques": technique_counter.most_common(10),
            "avg_kill_chain_depth": avg_kill_chain_depth,
            "detection_rate": detection_rate,
            "most_compromised_hosts": host_hit_counter.most_common(10),
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def _cli_main():
    parser = argparse.ArgumentParser(
        description="Synthetic Attack Campaign Dataset Generator"
    )
    parser.add_argument("--runs", type=int, default=10, help="Number of simulation runs")
    parser.add_argument("--timesteps", type=int, default=3, help="Timesteps per run")
    parser.add_argument("--output", type=str, default="campaigns.json", help="Output JSON file")
    parser.add_argument(
        "--env",
        type=str,
        default="/app/config/simulation/default-environment.json",
        help="Base environment JSON file",
    )
    parser.add_argument("--ollama-host", type=str, default="http://ollama:11434")
    parser.add_argument("--ollama-model", type=str, default="llama3.2:3b")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    import json as _json
    with open(args.env) as fh:
        base_env = _json.load(fh)

    generator = DatasetGenerator(
        ollama_host=args.ollama_host,
        ollama_model=args.ollama_model,
    )
    dataset = await generator.generate(
        num_runs=args.runs,
        base_environment=base_env,
        timesteps=args.timesteps,
        output_path=args.output,
    )

    print(json.dumps(dataset["statistics"], indent=2))


if __name__ == "__main__":
    asyncio.run(_cli_main())
