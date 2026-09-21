"""
Benchmark Runner - Swarm Scale Testing
AI-Augmented SOC

Runs the swarm simulator at configurable scales to measure how
performance, discovery rate, and convergence change with agent count.
Produces structured data for the research paper.

Usage:
    python benchmark.py --scales 10,50,100 --batches 3 --timesteps 2
    python benchmark.py --quick  (10 followers, 2 batches, 2 timesteps)
"""

import argparse
import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from services.correlation_engine.environment import Environment
from services.correlation_engine.swarm import SwarmSimulator, SwarmConfig
from services.correlation_engine.history_store import HistoryStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def run_benchmark(
    scales: list,
    monte_carlo_runs: int = 3,
    timesteps: int = 2,
    leaders_per_archetype: int = 3,
    ollama_host: str = "http://localhost:11434",
    ollama_model: str = "llama3.2:3b",
    env_path: str = "../../config/simulation/default-environment.json",
    output_dir: str = "benchmarks",
) -> dict:
    """Run swarm simulations at increasing scales and collect metrics."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    env = Environment.load_from_json(env_path)
    history = HistoryStore(data_dir=str(output_path))

    results = []
    benchmark_id = f"BENCH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    logger.info(f"Starting benchmark {benchmark_id}: scales={scales}, batches={monte_carlo_runs}")

    for swarm_size in scales:
        logger.info(f"Running scale: {swarm_size} followers/archetype")

        config = SwarmConfig(
            swarm_size=swarm_size,
            monte_carlo_runs=monte_carlo_runs,
            timesteps=timesteps,
            leaders_per_archetype=leaders_per_archetype,
            ollama_host=ollama_host,
            ollama_model=ollama_model,
        )

        env_fresh = Environment.from_dict(env.snapshot())
        simulator = SwarmSimulator(config)

        start = time.time()
        report = await simulator.run(env_fresh)
        elapsed = time.time() - start

        # Store in history
        history.append(report, trigger="benchmark", env_snapshot=env.snapshot())

        # Extract research metrics
        confidence = report.get("statistical_confidence", {})
        cross_batch = report.get("cross_batch_intelligence", {})
        emergent = report.get("emergent_discoveries", [])
        heatmap = report.get("host_risk_heatmap", {})

        scale_result = {
            "swarm_size": swarm_size,
            "leaders_per_archetype": leaders_per_archetype,
            "total_leaders": leaders_per_archetype * 4,  # 4 archetypes
            "total_agents": report.get("total_agent_runs", 0),
            "monte_carlo_runs": monte_carlo_runs,
            "timesteps": timesteps,
            "duration_seconds": round(elapsed, 1),
            "unique_paths": cross_batch.get("total_unique_strategies", 0),
            "strategic_diversity": cross_batch.get("strategic_diversity_score", 0),
            "emergent_discoveries": len(emergent),
            "emergent_max_improvement": max(
                (d.get("improvement", 0) for d in emergent), default=0
            ),
            "convergence_achieved": confidence.get("convergence_achieved", False),
            "convergence_batch": confidence.get("convergence_batch", -1),
            "overall_compromise_rate": round(
                sum(h.get("compromise_rate", 0) for h in heatmap.values())
                / max(len(heatmap), 1),
                4,
            ),
            "attacker_learning_trend": cross_batch.get("attacker_learning_trend", "unknown"),
        }
        results.append(scale_result)

        logger.info(
            f"  Scale {swarm_size}: {scale_result['total_agents']} agents, "
            f"{scale_result['unique_paths']} unique paths, "
            f"{scale_result['emergent_discoveries']} emergent discoveries, "
            f"{scale_result['duration_seconds']}s"
        )

    # Write benchmark results
    benchmark = {
        "benchmark_id": benchmark_id,
        "timestamp": datetime.utcnow().isoformat(),
        "scales": results,
        "summary": {
            "scales_tested": len(scales),
            "total_duration_seconds": round(sum(r["duration_seconds"] for r in results), 1),
            "max_unique_paths": max(r["unique_paths"] for r in results) if results else 0,
            "max_emergent_discoveries": max(r["emergent_discoveries"] for r in results) if results else 0,
            "discovery_rate_by_scale": {
                r["swarm_size"]: round(r["emergent_discoveries"] / max(r["total_agents"], 1), 6)
                for r in results
            },
        },
    }

    outfile = output_path / f"{benchmark_id}.json"
    with open(outfile, "w") as f:
        json.dump(benchmark, f, indent=2)

    logger.info(f"Benchmark complete: {outfile}")
    return benchmark


def main():
    parser = argparse.ArgumentParser(description="Swarm Benchmark Runner")
    parser.add_argument("--scales", default="10,50", help="Comma-separated follower counts")
    parser.add_argument("--batches", type=int, default=3, help="Monte Carlo batches per scale")
    parser.add_argument("--timesteps", type=int, default=2, help="Timesteps per simulation")
    parser.add_argument("--leaders", type=int, default=3, help="Leaders per archetype")
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--ollama-model", default="llama3.2:3b")
    parser.add_argument("--env", default="../../config/simulation/default-environment.json")
    parser.add_argument("--output", default="benchmarks")
    parser.add_argument("--quick", action="store_true", help="Quick test: 10 followers, 2 batches")
    args = parser.parse_args()

    if args.quick:
        scales = [10]
        batches = 2
    else:
        scales = [int(s) for s in args.scales.split(",")]
        batches = args.batches

    result = asyncio.run(run_benchmark(
        scales=scales,
        monte_carlo_runs=batches,
        timesteps=args.timesteps,
        leaders_per_archetype=args.leaders,
        ollama_host=args.ollama_host,
        ollama_model=args.ollama_model,
        env_path=args.env,
        output_dir=args.output,
    ))

    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
