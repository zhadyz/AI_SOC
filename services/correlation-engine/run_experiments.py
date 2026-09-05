"""
Research Experiment Runner
AI-Augmented SOC — Swarm Intelligence for Automated Threat Modeling

Orchestrates all 4 experiments for the research paper:
  Exp 1: Scale vs Discovery — how does swarm size affect attack path discovery?
  Exp 2: Prediction Accuracy — does the swarm correctly predict vulnerable hosts?
  Exp 3: Single-Run vs Swarm — does statistical aggregation change host prioritization?
  Exp 4: Defender Impact — how much do LLM defenders reduce compromise rates?

Usage:
    python run_experiments.py                    # Full run (all 4 experiments)
    python run_experiments.py --exp 1            # Only Experiment 1
    python run_experiments.py --exp 1,2          # Experiments 1 and 2
    python run_experiments.py --quick            # Quick validation (small scales)
    python run_experiments.py --resume DIR       # Resume from existing experiment dir
"""

import argparse
import asyncio
import json
import logging
import os
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from services.correlation_engine.environment import Environment
from services.correlation_engine.swarm import SwarmSimulator, SwarmConfig
from services.correlation_engine.simulator import CampaignSimulator, SimulationConfig
from services.correlation_engine.history_store import HistoryStore
from services.correlation_engine.research_metrics import prediction_accuracy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ground Truth — Expert assessment of the 6-host environment
# ---------------------------------------------------------------------------
# Based on CVEs, defenses, exposure, and network position.
# TRUE = an expert pen-tester would expect this host to be compromisable.

GROUND_TRUTH = {
    "10.0.0.10": True,   # web-server-01: CVE-2024-7347, exposed, no EDR/MFA, unpatched
    "10.0.0.20": False,  # mail-server-01: no CVEs, has MFA, has Wazuh
    "10.0.1.10": True,   # workstation-01: CVE-2024-38077, no Wazuh/EDR, unpatched
    "10.0.1.20": True,   # file-server-01: no firewall, no MFA — lateral target
    "10.0.2.10": True,   # prod-db-01: CVE-2024-10978, unpatched despite EDR/MFA
    "10.0.2.20": False,  # dc-01: no CVEs, fully patched, MFA+EDR+Wazuh
}

GROUND_TRUTH_REASONING = {
    "10.0.0.10": "CVE-2024-7347 in nginx, externally exposed in DMZ, no EDR, no MFA, unpatched",
    "10.0.0.20": "No known CVEs, MFA enabled, Wazuh monitored — no direct exploit path",
    "10.0.1.10": "CVE-2024-38077 (Windows RDP), no monitoring, no EDR, unpatched",
    "10.0.1.20": "No firewall, no MFA, SMB/RDP exposed — easy lateral movement target",
    "10.0.2.10": "CVE-2024-10978 (PostgreSQL) unpatched despite EDR+MFA layered defense",
    "10.0.2.20": "Fully hardened: no CVEs, patched, MFA, EDR, Wazuh — the control case",
}


# ---------------------------------------------------------------------------
# Experiment 1: Scale vs Discovery
# ---------------------------------------------------------------------------

async def experiment_1_scale_vs_discovery(
    env: Environment,
    scales: List[int],
    batches: int,
    timesteps: int,
    leaders: int,
    ollama_host: str,
    ollama_model: str,
    output_dir: Path,
) -> Dict:
    """Run swarm at increasing scales. Measure discovery rate and convergence."""
    logger.info("=" * 70)
    logger.info("EXPERIMENT 1: Scale vs Discovery")
    logger.info(f"  Scales: {scales}")
    logger.info(f"  Batches: {batches}, Timesteps: {timesteps}, Leaders/arch: {leaders}")
    logger.info("=" * 70)

    results = []
    raw_reports = {}

    for i, swarm_size in enumerate(scales):
        logger.info(f"\n--- Scale {i+1}/{len(scales)}: {swarm_size} followers/archetype ---")

        config = SwarmConfig(
            swarm_size=swarm_size,
            monte_carlo_runs=batches,
            timesteps=timesteps,
            leaders_per_archetype=leaders,
            defenders_enabled=True,
            env_randomization=True,
            target_jitter=True,
            ollama_host=ollama_host,
            ollama_model=ollama_model,
        )

        env_fresh = Environment.from_dict(env.snapshot())
        simulator = SwarmSimulator(config)

        start = time.time()
        report = await simulator.run(env_fresh)
        elapsed = time.time() - start

        raw_reports[swarm_size] = report

        # Extract metrics
        confidence = report.get("statistical_confidence", {})
        cross_batch = report.get("cross_batch_intelligence", {})
        emergent = report.get("emergent_discoveries", [])
        heatmap = report.get("host_risk_heatmap", {})
        archetype_stats = report.get("archetype_statistics", {})

        scale_result = {
            "swarm_size": swarm_size,
            "total_agents": report.get("total_agent_runs", 0),
            "duration_seconds": round(elapsed, 1),
            "unique_paths": cross_batch.get("total_unique_strategies", 0),
            "strategic_diversity": cross_batch.get("strategic_diversity_score", 0),
            "emergent_discoveries": len(emergent),
            "emergent_details": emergent[:3],  # top 3 for the paper
            "convergence_achieved": confidence.get("convergence_achieved", False),
            "convergence_batch": confidence.get("convergence_batch", -1),
            "overall_compromise_rate": round(
                sum(h.get("compromise_rate", 0) for h in heatmap.values())
                / max(len(heatmap), 1), 4
            ),
            "host_compromise_rates": {
                ip: round(h.get("compromise_rate", 0), 4)
                for ip, h in heatmap.items()
            },
            "host_confidence_intervals": {
                ip: h.get("confidence_interval_95", [0, 0])
                for ip, h in heatmap.items()
            },
            "attacker_learning_trend": cross_batch.get("attacker_learning_trend", "unknown"),
            "batch_evolution": cross_batch.get("batch_evolution", []),
            "archetype_stats": {
                arch: {
                    "success_rate_mean": stats.get("success_rate_mean", 0),
                    "hosts_compromised_mean": stats.get("hosts_compromised_mean", 0),
                }
                for arch, stats in archetype_stats.items()
            },
        }
        results.append(scale_result)

        logger.info(
            f"  Agents: {scale_result['total_agents']} | "
            f"Paths: {scale_result['unique_paths']} | "
            f"Emergent: {scale_result['emergent_discoveries']} | "
            f"Converged: {scale_result['convergence_achieved']} | "
            f"Time: {scale_result['duration_seconds']}s"
        )

    # Save raw reports for reuse by other experiments
    for size, report in raw_reports.items():
        raw_file = output_dir / f"exp1_raw_scale_{size}.json"
        with open(raw_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

    return {
        "experiment": "Scale vs Discovery",
        "hypothesis": "Larger swarms discover more unique attack paths and emergent strategies",
        "scales_tested": len(scales),
        "results": results,
        "analysis": _analyze_scale_trend(results),
    }


def _analyze_scale_trend(results: List[Dict]) -> Dict:
    """Analyze the trend across scales."""
    if len(results) < 2:
        return {"conclusion": "Insufficient data points"}

    sizes = [r["swarm_size"] for r in results]
    paths = [r["unique_paths"] for r in results]
    emergent = [r["emergent_discoveries"] for r in results]
    rates = [r["overall_compromise_rate"] for r in results]

    # Compute discovery rate per agent
    discovery_per_agent = [
        r["emergent_discoveries"] / max(r["total_agents"], 1)
        for r in results
    ]

    # Simple trend detection
    path_trend = "increasing" if paths[-1] > paths[0] else "flat_or_decreasing"
    emergent_trend = "increasing" if emergent[-1] > emergent[0] else "flat_or_decreasing"

    # Find minimum convergent size
    converged_sizes = [r["swarm_size"] for r in results if r["convergence_achieved"]]
    min_convergent = min(converged_sizes) if converged_sizes else None

    return {
        "path_count_trend": path_trend,
        "emergent_discovery_trend": emergent_trend,
        "min_convergent_swarm_size": min_convergent,
        "discovery_per_agent": {
            r["swarm_size"]: round(d, 6) for r, d in zip(results, discovery_per_agent)
        },
        "compromise_rate_range": [round(min(rates), 4), round(max(rates), 4)],
        "conclusion": (
            f"Unique paths {'increase' if path_trend == 'increasing' else 'do not clearly increase'} "
            f"with swarm size. "
            f"Emergent discoveries {'increase' if emergent_trend == 'increasing' else 'do not clearly increase'}. "
            + (f"Convergence first achieved at {min_convergent} followers/archetype."
               if min_convergent else "No convergence achieved at tested scales.")
        ),
    }


# ---------------------------------------------------------------------------
# Experiment 2: Prediction Accuracy
# ---------------------------------------------------------------------------

async def experiment_2_prediction_accuracy(
    env: Environment,
    output_dir: Path,
    swarm_report: Optional[Dict] = None,
    ollama_host: str = "http://localhost:11434",
    ollama_model: str = "llama3.2:3b",
) -> Dict:
    """Test swarm predictions against expert ground truth."""
    logger.info("=" * 70)
    logger.info("EXPERIMENT 2: Prediction Accuracy")
    logger.info("=" * 70)

    # Use provided report or run a fresh swarm at scale 100
    if swarm_report is None:
        logger.info("  No pre-computed report — running swarm at scale 100...")
        config = SwarmConfig(
            swarm_size=100,
            monte_carlo_runs=5,
            timesteps=3,
            leaders_per_archetype=3,
            defenders_enabled=True,
            ollama_host=ollama_host,
            ollama_model=ollama_model,
        )
        env_fresh = Environment.from_dict(env.snapshot())
        simulator = SwarmSimulator(config)
        swarm_report = await simulator.run(env_fresh)

    heatmap = swarm_report.get("host_risk_heatmap", {})

    # Apply multiple thresholds to find optimal
    thresholds = [0.1, 0.2, 0.3, 0.4, 0.5]
    threshold_results = []

    for threshold in thresholds:
        tp = fp = tn = fn = 0
        predictions = []

        for ip, should_compromise in GROUND_TRUTH.items():
            rate = heatmap.get(ip, {}).get("compromise_rate", 0)
            predicted = rate > threshold
            actual = should_compromise

            if predicted and actual:
                tp += 1
            elif predicted and not actual:
                fp += 1
            elif not predicted and actual:
                fn += 1
            else:
                tn += 1

            predictions.append({
                "host": ip,
                "hostname": heatmap.get(ip, {}).get("hostname", ip),
                "compromise_rate": round(rate, 4),
                "ci_95": heatmap.get(ip, {}).get("confidence_interval_95", [0, 0]),
                "predicted_vulnerable": predicted,
                "ground_truth_vulnerable": actual,
                "ground_truth_reasoning": GROUND_TRUTH_REASONING.get(ip, ""),
                "correct": predicted == actual,
            })

        total = tp + fp + tn + fn
        accuracy = (tp + tn) / max(total, 1)
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 0.001)

        threshold_results.append({
            "threshold": threshold,
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "predictions": predictions,
        })

    # Find best threshold by F1
    best = max(threshold_results, key=lambda x: x["f1_score"])

    return {
        "experiment": "Prediction Accuracy",
        "hypothesis": "Swarm compromise rates predict which hosts are truly vulnerable",
        "ground_truth": {
            ip: {"vulnerable": v, "reasoning": GROUND_TRUTH_REASONING[ip]}
            for ip, v in GROUND_TRUTH.items()
        },
        "best_threshold": best["threshold"],
        "best_results": {
            "accuracy": best["accuracy"],
            "precision": best["precision"],
            "recall": best["recall"],
            "f1_score": best["f1_score"],
            "confusion_matrix": best["confusion_matrix"],
        },
        "all_thresholds": threshold_results,
        "per_host_predictions": best["predictions"],
        "analysis": (
            f"Best F1={best['f1_score']:.2f} at threshold={best['threshold']}. "
            f"Accuracy={best['accuracy']:.0%}, Precision={best['precision']:.0%}, "
            f"Recall={best['recall']:.0%}."
        ),
    }


# ---------------------------------------------------------------------------
# Experiment 3: Single-Run vs Swarm
# ---------------------------------------------------------------------------

async def experiment_3_single_vs_swarm(
    env: Environment,
    output_dir: Path,
    swarm_report: Optional[Dict] = None,
    ollama_host: str = "http://localhost:11434",
    ollama_model: str = "llama3.2:3b",
) -> Dict:
    """Compare a single 4-agent campaign against swarm statistical output."""
    logger.info("=" * 70)
    logger.info("EXPERIMENT 3: Single-Run vs Swarm")
    logger.info("=" * 70)

    # --- Single run ---
    logger.info("  Running single 4-agent campaign...")
    single_config = SimulationConfig(
        agent_archetypes=["opportunist", "apt", "ransomware", "insider"],
        defender_archetypes=["soc_analyst", "incident_responder", "threat_hunter"],
        defenders_enabled=True,
        timesteps=3,
        ollama_host=ollama_host,
        ollama_model=ollama_model,
    )
    env_single = Environment.from_dict(env.snapshot())
    single_sim = CampaignSimulator(single_config)

    start = time.time()
    single_report = await single_sim.run(env_single)
    single_elapsed = time.time() - start

    # Extract single-run host compromise data
    single_compromised = set()
    for campaign in single_report.get("campaigns", []):
        single_compromised.update(campaign.get("hosts_compromised", []))

    single_host_data = {}
    for host in env.get_all_hosts():
        single_host_data[host.ip] = {
            "compromised": host.ip in single_compromised,
            "compromise_rate": 1.0 if host.ip in single_compromised else 0.0,
        }

    # --- Swarm run ---
    if swarm_report is None:
        logger.info("  Running swarm at scale 100...")
        config = SwarmConfig(
            swarm_size=100,
            monte_carlo_runs=5,
            timesteps=3,
            leaders_per_archetype=3,
            defenders_enabled=True,
            ollama_host=ollama_host,
            ollama_model=ollama_model,
        )
        env_swarm = Environment.from_dict(env.snapshot())
        simulator = SwarmSimulator(config)
        swarm_report = await simulator.run(env_swarm)

    heatmap = swarm_report.get("host_risk_heatmap", {})
    swarm_host_data = {}
    for ip, data in heatmap.items():
        swarm_host_data[ip] = {
            "compromise_rate": data.get("compromise_rate", 0),
            "ci_95": data.get("confidence_interval_95", [0, 0]),
        }

    # --- Compare prioritization ---
    # Single-run: binary (compromised or not), ranked by what was hit
    # Swarm: probabilistic, ranked by compromise_rate
    single_priority = sorted(
        single_host_data.items(),
        key=lambda x: x[1]["compromise_rate"],
        reverse=True,
    )
    swarm_priority = sorted(
        swarm_host_data.items(),
        key=lambda x: x[1]["compromise_rate"],
        reverse=True,
    )

    single_ranking = {ip: rank + 1 for rank, (ip, _) in enumerate(single_priority)}
    swarm_ranking = {ip: rank + 1 for rank, (ip, _) in enumerate(swarm_priority)}

    # Compare rankings
    comparison = []
    rank_deltas = []
    for host in env.get_all_hosts():
        ip = host.ip
        s_rank = single_ranking.get(ip, 99)
        w_rank = swarm_ranking.get(ip, 99)
        delta = s_rank - w_rank
        rank_deltas.append(abs(delta))

        comparison.append({
            "host": ip,
            "hostname": host.hostname,
            "single_run_compromised": single_host_data.get(ip, {}).get("compromised", False),
            "single_run_priority": s_rank,
            "swarm_compromise_rate": round(
                swarm_host_data.get(ip, {}).get("compromise_rate", 0), 4
            ),
            "swarm_ci_95": swarm_host_data.get(ip, {}).get("ci_95", [0, 0]),
            "swarm_priority": w_rank,
            "priority_change": delta,
            "ground_truth": GROUND_TRUTH.get(ip, None),
        })

    # Check which approach aligns better with ground truth
    single_correct = sum(
        1 for c in comparison
        if c["ground_truth"] is not None
        and (c["single_run_compromised"] == c["ground_truth"])
    )
    swarm_correct = sum(
        1 for c in comparison
        if c["ground_truth"] is not None
        and ((c["swarm_compromise_rate"] > 0.3) == c["ground_truth"])
    )

    return {
        "experiment": "Single-Run vs Swarm",
        "hypothesis": "Swarm statistical output changes (improves) host prioritization vs single run",
        "single_run": {
            "agents": 4,
            "duration_seconds": round(single_elapsed, 1),
            "hosts_compromised": list(single_compromised),
            "total_actions": single_report.get("results_summary", {}).get("total_actions", 0),
        },
        "swarm_run": {
            "total_agents": swarm_report.get("total_agent_runs", 0),
            "duration_seconds": swarm_report.get("duration_ms", 0) / 1000,
        },
        "host_comparison": comparison,
        "ranking_changed": any(c["priority_change"] != 0 for c in comparison),
        "mean_rank_delta": round(statistics.mean(rank_deltas), 2) if rank_deltas else 0,
        "single_run_ground_truth_matches": single_correct,
        "swarm_ground_truth_matches": swarm_correct,
        "total_hosts": len(GROUND_TRUTH),
        "analysis": (
            f"Single-run matched ground truth on {single_correct}/{len(GROUND_TRUTH)} hosts. "
            f"Swarm matched on {swarm_correct}/{len(GROUND_TRUTH)} hosts. "
            f"Mean rank delta: {round(statistics.mean(rank_deltas), 2) if rank_deltas else 0} positions. "
            + ("Swarm provides richer signal with confidence intervals."
               if swarm_correct >= single_correct
               else "Single run surprisingly competitive at this scale.")
        ),
    }


# ---------------------------------------------------------------------------
# Experiment 4: Defender Impact
# ---------------------------------------------------------------------------

async def experiment_4_defender_impact(
    env: Environment,
    output_dir: Path,
    swarm_with_defenders: Optional[Dict] = None,
    ollama_host: str = "http://localhost:11434",
    ollama_model: str = "llama3.2:3b",
) -> Dict:
    """Compare swarm outcomes with and without LLM-powered defenders."""
    logger.info("=" * 70)
    logger.info("EXPERIMENT 4: Defender Impact")
    logger.info("=" * 70)

    # --- With defenders (reuse from Experiment 1 if available) ---
    if swarm_with_defenders is None:
        logger.info("  Running swarm WITH defenders (scale 100)...")
        config_on = SwarmConfig(
            swarm_size=100,
            monte_carlo_runs=5,
            timesteps=3,
            leaders_per_archetype=3,
            defenders_enabled=True,
            ollama_host=ollama_host,
            ollama_model=ollama_model,
        )
        env_on = Environment.from_dict(env.snapshot())
        sim_on = SwarmSimulator(config_on)
        swarm_with_defenders = await sim_on.run(env_on)

    # --- Without defenders ---
    logger.info("  Running swarm WITHOUT defenders (scale 100)...")
    config_off = SwarmConfig(
        swarm_size=100,
        monte_carlo_runs=5,
        timesteps=3,
        leaders_per_archetype=3,
        defenders_enabled=False,
        ollama_host=ollama_host,
        ollama_model=ollama_model,
    )
    env_off = Environment.from_dict(env.snapshot())
    sim_off = SwarmSimulator(config_off)

    start = time.time()
    swarm_no_defenders = await sim_off.run(env_off)
    elapsed_no_def = time.time() - start

    # Save raw
    with open(output_dir / "exp4_raw_no_defenders.json", "w") as f:
        json.dump(swarm_no_defenders, f, indent=2, default=str)

    # --- Compare ---
    heatmap_on = swarm_with_defenders.get("host_risk_heatmap", {})
    heatmap_off = swarm_no_defenders.get("host_risk_heatmap", {})
    arch_on = swarm_with_defenders.get("archetype_statistics", {})
    arch_off = swarm_no_defenders.get("archetype_statistics", {})
    defense_eff = swarm_with_defenders.get("defense_effectiveness", {})

    host_comparison = []
    for host in env.get_all_hosts():
        ip = host.ip
        rate_on = heatmap_on.get(ip, {}).get("compromise_rate", 0)
        rate_off = heatmap_off.get(ip, {}).get("compromise_rate", 0)
        reduction = rate_off - rate_on

        host_comparison.append({
            "host": ip,
            "hostname": host.hostname,
            "criticality": host.criticality,
            "rate_with_defenders": round(rate_on, 4),
            "rate_without_defenders": round(rate_off, 4),
            "absolute_reduction": round(reduction, 4),
            "relative_reduction_pct": round(
                (reduction / max(rate_off, 0.001)) * 100, 1
            ),
        })

    archetype_comparison = {}
    for arch in ["opportunist", "apt", "ransomware", "insider"]:
        on_stats = arch_on.get(arch, {})
        off_stats = arch_off.get(arch, {})
        archetype_comparison[arch] = {
            "success_rate_with_defenders": on_stats.get("success_rate_mean", 0),
            "success_rate_without_defenders": off_stats.get("success_rate_mean", 0),
            "hosts_compromised_with": on_stats.get("hosts_compromised_mean", 0),
            "hosts_compromised_without": off_stats.get("hosts_compromised_mean", 0),
        }

    overall_on = sum(h.get("compromise_rate", 0) for h in heatmap_on.values()) / max(len(heatmap_on), 1)
    overall_off = sum(h.get("compromise_rate", 0) for h in heatmap_off.values()) / max(len(heatmap_off), 1)

    return {
        "experiment": "Defender Impact",
        "hypothesis": "LLM-powered defenders meaningfully reduce compromise rates",
        "overall_compromise_with_defenders": round(overall_on, 4),
        "overall_compromise_without_defenders": round(overall_off, 4),
        "overall_reduction_pct": round(
            ((overall_off - overall_on) / max(overall_off, 0.001)) * 100, 1
        ),
        "host_comparison": host_comparison,
        "archetype_impact": archetype_comparison,
        "defense_effectiveness": defense_eff,
        "no_defender_run_duration": round(elapsed_no_def, 1),
        "analysis": (
            f"Defenders reduced overall compromise rate from "
            f"{overall_off:.1%} to {overall_on:.1%} "
            f"({((overall_off - overall_on) / max(overall_off, 0.001)) * 100:.1f}% reduction). "
            + (
                "Defenders have measurable impact on attacker success."
                if overall_on < overall_off
                else "Defenders did not reduce compromise rates — investigate defender logic."
            )
        ),
    }


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

async def run_all_experiments(args) -> Dict:
    """Orchestrate all experiments with data reuse."""

    # Setup output directory
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output) / f"EXP-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Experiment output: {output_dir}")

    # Load environment
    env = Environment.load_from_json(args.env)
    logger.info(f"Environment loaded: {len(env.hosts)} hosts, {len(env.segments)} segments")

    experiments_to_run = set()
    if args.exp:
        experiments_to_run = set(int(x) for x in args.exp.split(","))
    else:
        experiments_to_run = {1, 2, 3, 4}

    # Configure scales
    if args.quick:
        scales = [10, 25]
        batches = 2
        timesteps = 2
    else:
        scales = [int(s) for s in args.scales.split(",")]
        batches = args.batches
        timesteps = args.timesteps

    all_results = {
        "experiment_run_id": f"EXP-{timestamp}",
        "started_at": datetime.utcnow().isoformat(),
        "config": {
            "scales": scales,
            "batches": batches,
            "timesteps": timesteps,
            "leaders_per_archetype": args.leaders,
            "ollama_model": args.ollama_model,
            "quick_mode": args.quick,
        },
        "experiments": {},
    }

    # Track reusable swarm reports
    scale_100_report = None

    # ----- Experiment 1 -----
    if 1 in experiments_to_run:
        exp1 = await experiment_1_scale_vs_discovery(
            env=env,
            scales=scales,
            batches=batches,
            timesteps=timesteps,
            leaders=args.leaders,
            ollama_host=args.ollama_host,
            ollama_model=args.ollama_model,
            output_dir=output_dir,
        )
        all_results["experiments"]["1_scale_vs_discovery"] = exp1

        # Cache the scale-100 report for reuse (or closest available)
        target_scale = 100 if 100 in scales else (scales[-1] if scales else None)
        if target_scale:
            raw_file = output_dir / f"exp1_raw_scale_{target_scale}.json"
            if raw_file.exists():
                with open(raw_file) as f:
                    scale_100_report = json.load(f)
                logger.info(f"  Cached scale-{target_scale} report for Experiments 2-4")

        with open(output_dir / "exp1_results.json", "w") as f:
            json.dump(exp1, f, indent=2, default=str)

    # ----- Experiment 2 -----
    if 2 in experiments_to_run:
        exp2 = await experiment_2_prediction_accuracy(
            env=env,
            output_dir=output_dir,
            swarm_report=scale_100_report,
            ollama_host=args.ollama_host,
            ollama_model=args.ollama_model,
        )
        all_results["experiments"]["2_prediction_accuracy"] = exp2

        with open(output_dir / "exp2_results.json", "w") as f:
            json.dump(exp2, f, indent=2, default=str)

    # ----- Experiment 3 -----
    if 3 in experiments_to_run:
        exp3 = await experiment_3_single_vs_swarm(
            env=env,
            output_dir=output_dir,
            swarm_report=scale_100_report,
            ollama_host=args.ollama_host,
            ollama_model=args.ollama_model,
        )
        all_results["experiments"]["3_single_vs_swarm"] = exp3

        with open(output_dir / "exp3_results.json", "w") as f:
            json.dump(exp3, f, indent=2, default=str)

    # ----- Experiment 4 -----
    if 4 in experiments_to_run:
        exp4 = await experiment_4_defender_impact(
            env=env,
            output_dir=output_dir,
            swarm_with_defenders=scale_100_report,
            ollama_host=args.ollama_host,
            ollama_model=args.ollama_model,
        )
        all_results["experiments"]["4_defender_impact"] = exp4

        with open(output_dir / "exp4_results.json", "w") as f:
            json.dump(exp4, f, indent=2, default=str)

    # ----- Save combined results -----
    all_results["completed_at"] = datetime.utcnow().isoformat()
    with open(output_dir / "all_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    logger.info(f"\nAll results saved to: {output_dir}")
    _print_summary(all_results)

    return all_results


def _print_summary(results: Dict):
    """Print a human-readable summary of all experiments."""
    print("\n" + "=" * 70)
    print("EXPERIMENT SUMMARY")
    print("=" * 70)

    for key, exp in results.get("experiments", {}).items():
        print(f"\n--- {exp.get('experiment', key)} ---")
        if "analysis" in exp:
            print(f"  {exp['analysis']}")
        if "best_results" in exp:
            br = exp["best_results"]
            print(f"  Accuracy={br['accuracy']:.0%}  Precision={br['precision']:.0%}  "
                  f"Recall={br['recall']:.0%}  F1={br['f1_score']:.2f}")

    print(f"\nOutput directory: {results.get('experiment_run_id', 'unknown')}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Research Experiment Runner — Swarm Intelligence Paper"
    )
    parser.add_argument("--exp", default=None, help="Experiments to run (e.g. '1,2,3,4')")
    parser.add_argument("--scales", default="10,25,50,100,200,500",
                        help="Comma-separated follower counts for Experiment 1")
    parser.add_argument("--batches", type=int, default=5, help="Monte Carlo batches per scale")
    parser.add_argument("--timesteps", type=int, default=3, help="Timesteps per simulation")
    parser.add_argument("--leaders", type=int, default=3, help="Leaders per archetype")
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--ollama-model", default="llama3.2:3b")
    parser.add_argument("--env", default="../../config/simulation/default-environment.json")
    parser.add_argument("--output", default="experiments")
    parser.add_argument("--quick", action="store_true", help="Quick validation run")
    parser.add_argument("--resume", default=None, help="Resume from existing experiment dir")
    args = parser.parse_args()

    result = asyncio.run(run_all_experiments(args))
    return result


if __name__ == "__main__":
    main()
