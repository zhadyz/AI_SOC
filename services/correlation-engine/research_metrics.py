"""
Research Metrics Analyzer - Paper Data Extraction
AI-Augmented SOC

Analyzes stored swarm history to compute the specific metrics needed
for the research paper. Exports CSV files for matplotlib/R plotting.

Key research questions answered:
  1. Minimum swarm size for statistical reliability
  2. Emergent discovery rate vs swarm size
  3. Strategic diversity vs number of leaders
  4. Prediction accuracy against known-vulnerable hosts
"""

import csv
import json
import logging
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from services.correlation_engine.history_store import HistoryStore

logger = logging.getLogger(__name__)


def minimum_reliable_swarm_size(history: HistoryStore) -> Dict:
    """
    Research Q: What's the minimum swarm size for statistically reliable predictions?

    Groups benchmark runs by swarm_size and checks when confidence
    intervals stabilize (width < threshold).
    """
    benchmarks = history.get_by_config(trigger="benchmark")
    if not benchmarks:
        return {"error": "No benchmark data available. Run benchmark.py first."}

    by_size = defaultdict(list)
    for s in benchmarks:
        size = s.get("config", {}).get("swarm_size", 0)
        by_size[size].append(s)

    results = []
    for size in sorted(by_size.keys()):
        runs = by_size[size]
        rates = [
            r.get("metrics", {}).get("overall_compromise_rate", 0)
            for r in runs
        ]
        if len(rates) >= 2:
            std = statistics.stdev(rates)
            ci_width = std * 2 * 1.96  # approximate 95% CI width
        else:
            std = 0
            ci_width = 1.0  # unknown

        convergence_count = sum(
            1 for r in runs
            if r.get("metrics", {}).get("convergence_achieved", False)
        )

        results.append({
            "swarm_size": size,
            "runs": len(runs),
            "mean_compromise_rate": round(statistics.mean(rates), 4) if rates else 0,
            "std_compromise_rate": round(std, 4),
            "ci_width": round(ci_width, 4),
            "convergence_rate": round(convergence_count / max(len(runs), 1), 4),
            "reliable": ci_width < 0.10,  # CI width < 10%
        })

    # Find recommended size (smallest where reliable=True)
    recommended = next(
        (r["swarm_size"] for r in results if r["reliable"]),
        results[-1]["swarm_size"] if results else 0,
    )

    return {
        "by_size": results,
        "recommended_size": recommended,
        "conclusion": f"Minimum reliable swarm size: {recommended} followers/archetype"
        if any(r["reliable"] for r in results)
        else "Insufficient data to determine minimum reliable size — run more benchmarks",
    }


def emergent_discovery_rate(history: HistoryStore) -> Dict:
    """
    Research Q: Do you find more emergent paths with more agents?

    Maps swarm_size → emergent_discovery_count / total_agent_runs.
    A positive correlation supports the swarm intelligence hypothesis.
    """
    all_runs = history.get_trend()
    by_size = defaultdict(list)

    for s in all_runs:
        size = s.get("config", {}).get("swarm_size", 0)
        metrics = s.get("metrics", {})
        by_size[size].append({
            "emergent_count": metrics.get("emergent_discovery_count", 0),
            "total_agents": metrics.get("total_agent_runs", 1),
        })

    results = {}
    for size in sorted(by_size.keys()):
        entries = by_size[size]
        total_emergent = sum(e["emergent_count"] for e in entries)
        total_agents = sum(e["total_agents"] for e in entries)
        results[size] = {
            "emergent_discoveries": total_emergent,
            "total_agent_runs": total_agents,
            "discovery_rate": round(
                total_emergent / max(total_agents, 1), 6
            ),
            "runs": len(entries),
        }

    # Check for positive correlation
    sizes = sorted(results.keys())
    rates = [results[s]["discovery_rate"] for s in sizes]
    trend = "positive" if len(rates) >= 2 and rates[-1] > rates[0] else (
        "negative" if len(rates) >= 2 and rates[-1] < rates[0] else "insufficient_data"
    )

    return {
        "by_size": results,
        "correlation_trend": trend,
        "conclusion": (
            "Larger swarms discover more emergent paths — supports swarm intelligence hypothesis"
            if trend == "positive"
            else "No clear correlation between swarm size and emergent discoveries"
            if trend == "negative"
            else "Insufficient data to determine correlation"
        ),
    }


def strategic_diversity_analysis(history: HistoryStore) -> Dict:
    """
    Research Q: Does increasing leaders_per_archetype produce more unique strategies?
    """
    all_runs = history.get_trend()
    by_leaders = defaultdict(list)

    for s in all_runs:
        leaders = s.get("config", {}).get("leaders_per_archetype", 1)
        metrics = s.get("metrics", {})
        by_leaders[leaders].append({
            "unique_paths": metrics.get("unique_paths_discovered", 0),
            "diversity_score": metrics.get("strategic_diversity_score", 0),
        })

    results = {}
    for leaders in sorted(by_leaders.keys()):
        entries = by_leaders[leaders]
        results[leaders] = {
            "avg_unique_paths": round(
                statistics.mean(e["unique_paths"] for e in entries), 1
            ),
            "avg_diversity_score": round(
                statistics.mean(e["diversity_score"] for e in entries), 4
            ),
            "runs": len(entries),
        }

    return {"by_leaders_per_archetype": results}


def prediction_accuracy(
    history: HistoryStore,
    ground_truth: Dict[str, bool],
) -> Dict:
    """
    Research Q: For hosts where we know the answer, does the swarm predict correctly?

    ground_truth: {ip: should_be_compromisable} e.g. {"10.0.0.10": True, "10.0.2.20": False}
    """
    latest = history.get_latest()
    if not latest:
        return {"error": "No swarm data available"}

    rates = latest.get("metrics", {}).get("host_compromise_rates", {})

    tp = fp = tn = fn = 0
    predictions = []
    for ip, should_compromise in ground_truth.items():
        rate = rates.get(ip, 0)
        predicted = rate > 0.3  # threshold: >30% compromise rate = "compromisable"
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
            "compromise_rate": rate,
            "predicted_vulnerable": predicted,
            "actually_vulnerable": actual,
            "correct": predicted == actual,
        })

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / max(total, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 0.001)

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "predictions": predictions,
    }


def export_for_paper(
    history: HistoryStore,
    output_dir: str = "paper_data",
) -> List[str]:
    """Export CSV files suitable for matplotlib/R paper figures."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []

    all_snapshots = history.get_trend()

    # 1. Swarm scale vs discoveries
    benchmarks = history.get_by_config(trigger="benchmark")
    if benchmarks:
        f = out / "swarm_scale_vs_discoveries.csv"
        with open(f, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                "swarm_size", "total_agents", "unique_paths",
                "emergent_discoveries", "duration_seconds",
                "convergence_achieved", "compromise_rate",
            ])
            for s in benchmarks:
                cfg = s.get("config", {})
                m = s.get("metrics", {})
                writer.writerow([
                    cfg.get("swarm_size", 0),
                    m.get("total_agent_runs", 0),
                    m.get("unique_paths_discovered", 0),
                    m.get("emergent_discovery_count", 0),
                    m.get("duration_ms", 0) / 1000,
                    m.get("convergence_achieved", False),
                    m.get("overall_compromise_rate", 0),
                ])
        files.append(str(f))

    # 2. Host risk over time
    if all_snapshots:
        f = out / "host_risk_over_time.csv"
        all_hosts = set()
        for s in all_snapshots:
            all_hosts.update(s.get("metrics", {}).get("host_compromise_rates", {}).keys())

        with open(f, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["timestamp", "snapshot_id"] + sorted(all_hosts))
            for s in all_snapshots:
                rates = s.get("metrics", {}).get("host_compromise_rates", {})
                row = [s.get("timestamp", ""), s.get("snapshot_id", "")]
                for host in sorted(all_hosts):
                    row.append(rates.get(host, 0))
                writer.writerow(row)
        files.append(str(f))

    # 3. Archetype comparison
    if all_snapshots:
        f = out / "archetype_comparison.csv"
        with open(f, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                "timestamp", "archetype", "success_rate",
                "total_agents", "compromise_rate",
            ])
            for s in all_snapshots:
                rates = s.get("metrics", {}).get("archetype_success_rates", {})
                for arch, rate in rates.items():
                    writer.writerow([
                        s.get("timestamp", ""),
                        arch, rate,
                        s.get("metrics", {}).get("total_agent_runs", 0),
                        s.get("metrics", {}).get("overall_compromise_rate", 0),
                    ])
        files.append(str(f))

    # 4. Convergence by batch
    if all_snapshots:
        f = out / "convergence_by_batch.csv"
        with open(f, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                "snapshot_id", "swarm_size", "convergence_achieved",
                "convergence_batch", "total_agents",
            ])
            for s in all_snapshots:
                m = s.get("metrics", {})
                cfg = s.get("config", {})
                writer.writerow([
                    s.get("snapshot_id", ""),
                    cfg.get("swarm_size", 0),
                    m.get("convergence_achieved", False),
                    m.get("convergence_batch", -1),
                    m.get("total_agent_runs", 0),
                ])
        files.append(str(f))

    logger.info(f"Exported {len(files)} CSV files to {out}")
    return files


def compute_all_metrics(history: HistoryStore) -> Dict:
    """Compute all research metrics from stored history."""
    return {
        "minimum_reliable_swarm_size": minimum_reliable_swarm_size(history),
        "emergent_discovery_rate": emergent_discovery_rate(history),
        "strategic_diversity": strategic_diversity_analysis(history),
        "timestamp": datetime.utcnow().isoformat() if True else "",
    }


# Needed for compute_all_metrics
from datetime import datetime
