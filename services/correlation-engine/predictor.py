"""
Predictive Detection - Correlation Engine
AI-Augmented SOC

Learns attack transition probabilities from incident history.
When early-stage activity is detected (e.g., reconnaissance),
predicts next-stage attacks with probability and recommended
pre-emptive actions.

Uses a Markov chain of kill chain stage transitions learned
from closed incidents in PostgreSQL.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from services.correlation_engine.database import IncidentModel, IncidentAlertModel
from services.correlation_engine.models import KillChainStage, KILL_CHAIN_ORDER

logger = logging.getLogger(__name__)

# Kill chain stage ordering for transition matrix
STAGE_NAMES = [s.value for s in KILL_CHAIN_ORDER]
STAGE_INDEX = {name: i for i, name in enumerate(STAGE_NAMES)}

# Pre-emptive actions by predicted stage
PREEMPTIVE_ACTIONS = {
    "initial_access": [
        "Increase authentication monitoring on exposed services",
        "Enable enhanced logging on perimeter firewalls",
        "Verify MFA is enforced on all external-facing services",
    ],
    "execution": [
        "Enable enhanced process monitoring on targeted hosts",
        "Stage endpoint isolation playbook for one-click execution",
        "Alert SOC to monitor targeted systems for suspicious processes",
    ],
    "persistence": [
        "Monitor for new scheduled tasks, services, and registry changes",
        "Scan for unauthorized SSH keys or account creation",
        "Enable file integrity monitoring on critical directories",
    ],
    "privilege_escalation": [
        "Audit privileged account usage on targeted systems",
        "Enable enhanced credential access monitoring",
        "Stage credential rotation playbook",
    ],
    "lateral_movement": [
        "Enable network segmentation monitoring",
        "Monitor for unusual SMB, RDP, and WinRM traffic",
        "Stage network isolation playbook for compromised segments",
    ],
    "exfiltration": [
        "Enable DLP monitoring on all egress points",
        "Monitor for unusual outbound data volumes",
        "Stage DNS sinkhole for suspicious domains",
    ],
    "command_and_control": [
        "Monitor for beaconing patterns in network traffic",
        "Block known C2 infrastructure at firewall",
        "Enable DNS query logging and anomaly detection",
    ],
    "impact": [
        "Stage backup restoration playbook",
        "Enable ransomware canary file monitoring",
        "Notify incident response team for standby",
    ],
}


class AttackPredictor:
    """
    Predicts next-stage attacks using Markov chain transition
    probabilities learned from historical incident data.
    """

    def __init__(self):
        # Transition matrix: transitions[from_stage][to_stage] = count
        self.transitions: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # Total transitions from each stage
        self.stage_totals: Dict[str, int] = defaultdict(int)
        # Trained flag
        self.trained = False
        self.training_incidents = 0

    async def train(self, db_session: AsyncSession):
        """
        Learn transition probabilities from closed incidents.
        Reads incident_alerts table, orders by time, and counts
        stage-to-stage transitions.
        """
        self.transitions = defaultdict(lambda: defaultdict(int))
        self.stage_totals = defaultdict(int)

        # Get all closed incidents with multiple alerts
        result = await db_session.execute(
            select(IncidentModel).where(
                and_(
                    IncidentModel.status == "closed",
                    IncidentModel.alert_count >= 2,
                )
            )
        )
        incidents = result.scalars().all()

        if not incidents:
            logger.info("No closed incidents with 2+ alerts for training")
            self.trained = True
            self.training_incidents = 0
            return

        for incident in incidents:
            # Get alerts ordered by time
            alerts_result = await db_session.execute(
                select(IncidentAlertModel)
                .where(IncidentAlertModel.incident_id == incident.incident_id)
                .order_by(IncidentAlertModel.added_at)
            )
            alerts = alerts_result.scalars().all()

            # Extract kill chain stage sequence
            stages = []
            for alert in alerts:
                stage = alert.kill_chain_stage
                if stage and (not stages or stages[-1] != stage):
                    stages.append(stage)

            # Count transitions
            for i in range(len(stages) - 1):
                from_stage = stages[i]
                to_stage = stages[i + 1]
                self.transitions[from_stage][to_stage] += 1
                self.stage_totals[from_stage] += 1

        self.trained = True
        self.training_incidents = len(incidents)

        total_transitions = sum(self.stage_totals.values())
        logger.info(
            f"Predictor trained on {len(incidents)} incidents, "
            f"{total_transitions} stage transitions"
        )

    def predict_next_stages(
        self,
        current_stage: str,
        top_k: int = 3,
    ) -> List[Dict]:
        """
        Predict the most likely next kill chain stages given the current stage.

        Returns list of predictions sorted by probability.
        """
        if not self.trained or current_stage not in self.transitions:
            # Fallback: use domain knowledge for common progressions
            return self._default_predictions(current_stage, top_k)

        total = self.stage_totals.get(current_stage, 0)
        if total == 0:
            return self._default_predictions(current_stage, top_k)

        predictions = []
        for next_stage, count in self.transitions[current_stage].items():
            probability = count / total
            predictions.append({
                "predicted_stage": next_stage,
                "probability": round(probability, 4),
                "transition_count": count,
                "preemptive_actions": PREEMPTIVE_ACTIONS.get(next_stage, []),
                "source": "learned",
            })

        # Sort by probability descending
        predictions.sort(key=lambda x: x["probability"], reverse=True)
        return predictions[:top_k]

    def _default_predictions(self, current_stage: str, top_k: int) -> List[Dict]:
        """
        Default predictions based on common attack progression patterns
        when insufficient historical data exists.
        """
        # Typical kill chain progressions
        default_next = {
            "reconnaissance": [
                ("initial_access", 0.60),
                ("execution", 0.20),
                ("credential_access", 0.15),
            ],
            "initial_access": [
                ("execution", 0.50),
                ("persistence", 0.25),
                ("privilege_escalation", 0.20),
            ],
            "execution": [
                ("persistence", 0.35),
                ("privilege_escalation", 0.35),
                ("lateral_movement", 0.20),
            ],
            "persistence": [
                ("privilege_escalation", 0.40),
                ("lateral_movement", 0.30),
                ("command_and_control", 0.20),
            ],
            "privilege_escalation": [
                ("lateral_movement", 0.45),
                ("collection", 0.25),
                ("persistence", 0.20),
            ],
            "lateral_movement": [
                ("collection", 0.40),
                ("exfiltration", 0.30),
                ("privilege_escalation", 0.20),
            ],
            "collection": [
                ("exfiltration", 0.55),
                ("command_and_control", 0.25),
                ("impact", 0.15),
            ],
            "command_and_control": [
                ("exfiltration", 0.40),
                ("lateral_movement", 0.30),
                ("impact", 0.20),
            ],
            "exfiltration": [
                ("impact", 0.50),
                ("command_and_control", 0.25),
                ("persistence", 0.15),
            ],
        }

        progressions = default_next.get(current_stage, [])
        predictions = []
        for next_stage, prob in progressions[:top_k]:
            predictions.append({
                "predicted_stage": next_stage,
                "probability": prob,
                "transition_count": 0,
                "preemptive_actions": PREEMPTIVE_ACTIONS.get(next_stage, []),
                "source": "domain_knowledge",
            })

        return predictions

    @property
    def stats(self) -> Dict:
        return {
            "trained": self.trained,
            "training_incidents": self.training_incidents,
            "stages_with_data": len(self.transitions),
            "total_transitions": sum(self.stage_totals.values()),
        }
