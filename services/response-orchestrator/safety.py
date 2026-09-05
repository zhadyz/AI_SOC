"""
Trust & Safety Model - Response Orchestrator
AI-Augmented SOC

Graduated autonomy for defense actions. Determines which actions can
be auto-executed, which require human approval, and which are blocked.

Safety invariant: Any action touching a CRITICAL asset always requires
human approval, regardless of confidence score. This is structural —
the threshold formula ensures critical + high-blast actions can never
reach auto-execute tier.

Tiers:
  0 — Observe:        Log only, no action
  1 — Recommend:      Display recommendation, analyst decides
  2 — Auto-safe:      Auto-execute, low blast radius
  3 — Auto-veto:      Auto-execute with veto window (60s default)
  4 — Human-required: Always requires human approval
"""

import logging
from typing import List, Optional, Tuple

from services.response_orchestrator.models import (
    ActionType, AdapterType, ApprovalTier, BlastRadius,
    PlannedAction, ActionStatus,
)
from services.response_orchestrator.d3fend import D3FENDTechnique

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Blast Radius Classification
# ---------------------------------------------------------------------------

# Actions that are inherently safe (no environment mutation)
_OBSERVE_ONLY_ACTIONS = {
    ActionType.ADD_MONITORING,
    ActionType.DEPLOY_SIGMA_RULE,
}

# Actions that affect only a single external entity
_LOW_BLAST_ACTIONS = {
    ActionType.BLOCK_IP,
    ActionType.DEPLOY_EDR,
    ActionType.SINKHOLE_DOMAIN,
    ActionType.KILL_PROCESS,
}

# Actions that affect a single internal host or identity
_MEDIUM_BLAST_ACTIONS = {
    ActionType.ISOLATE_HOST,
    ActionType.REVOKE_CREDENTIALS,
    ActionType.DISABLE_ACCOUNT,
    ActionType.ENABLE_MFA,
    ActionType.PATCH_VULNERABILITY,
}

# Actions that affect multiple hosts or network topology
_HIGH_BLAST_ACTIONS = {
    ActionType.NETWORK_SEGMENT,
    ActionType.RESTORE_BACKUP,
}


def classify_blast_radius(
    action_type: ActionType,
    target_criticality: str,
) -> BlastRadius:
    """
    Determine blast radius based on action type and target criticality.

    Critical targets always escalate blast radius by one level.
    """
    if action_type in _OBSERVE_ONLY_ACTIONS:
        return BlastRadius.NONE

    if action_type in _HIGH_BLAST_ACTIONS:
        return BlastRadius.HIGH

    if action_type in _MEDIUM_BLAST_ACTIONS:
        # Medium actions on critical targets escalate to high
        if target_criticality == "critical":
            return BlastRadius.HIGH
        return BlastRadius.MEDIUM

    if action_type in _LOW_BLAST_ACTIONS:
        # Low actions on critical targets escalate to medium
        if target_criticality == "critical":
            return BlastRadius.MEDIUM
        return BlastRadius.LOW

    return BlastRadius.MEDIUM  # Default to medium for unknown actions


# ---------------------------------------------------------------------------
# Approval Tier Determination
# ---------------------------------------------------------------------------

# Numerical mapping for blast radius severity
_BLAST_SEVERITY = {
    BlastRadius.NONE: 0,
    BlastRadius.LOW: 1,
    BlastRadius.MEDIUM: 2,
    BlastRadius.HIGH: 3,
}


def determine_approval_tier(
    confidence: float,
    blast_radius: BlastRadius,
    target_criticality: str,
    auto_execute_min: float = 0.70,
    auto_veto_min: float = 0.85,
) -> ApprovalTier:
    """
    Determine the approval tier for an action.

    The formula ensures:
    - CRITICAL assets + blast_radius >= MEDIUM always require human approval
    - High-blast actions always require human approval
    - Low confidence always falls to recommend tier
    - Only high confidence + low blast can auto-execute
    """
    blast_severity = _BLAST_SEVERITY[blast_radius]

    # Structural safety: critical targets with meaningful blast always need humans
    if target_criticality == "critical" and blast_severity >= 2:
        return ApprovalTier.HUMAN_REQUIRED

    # High blast always needs humans regardless of confidence
    if blast_radius == BlastRadius.HIGH:
        return ApprovalTier.HUMAN_REQUIRED

    # Observe-only actions are always auto
    if blast_radius == BlastRadius.NONE:
        return ApprovalTier.AUTO_SAFE

    # Low confidence: recommend only
    if confidence < auto_execute_min:
        return ApprovalTier.RECOMMEND

    # Medium confidence + low blast: auto-safe
    if confidence >= auto_execute_min and blast_severity <= 1:
        return ApprovalTier.AUTO_SAFE

    # High confidence + medium blast: auto with veto window
    if confidence >= auto_veto_min and blast_severity <= 2:
        if target_criticality != "critical":
            return ApprovalTier.AUTO_VETO

    # Medium confidence + medium blast: human required
    if blast_severity >= 2:
        return ApprovalTier.HUMAN_REQUIRED

    # Default: recommend
    return ApprovalTier.RECOMMEND


def requires_human_approval(tier: ApprovalTier) -> bool:
    """Whether this tier requires a human to explicitly approve."""
    return tier in (ApprovalTier.RECOMMEND, ApprovalTier.HUMAN_REQUIRED)


# ---------------------------------------------------------------------------
# Composite Score
# ---------------------------------------------------------------------------

def compute_composite_score(
    impact_score: float,
    safety_score: float,
    confidence: float,
    impact_weight: float = 0.45,
    safety_weight: float = 0.35,
    confidence_weight: float = 0.20,
) -> float:
    """
    Weighted composite score for ranking candidate actions.

    Impact is weighted highest because the primary goal is attack surface
    reduction. Safety is second because a dangerous action isn't useful even
    if it has high impact. Confidence is a tiebreaker.
    """
    return round(
        impact_score * impact_weight
        + safety_score * safety_weight
        + confidence * confidence_weight,
        4,
    )


# ---------------------------------------------------------------------------
# Safety Checks
# ---------------------------------------------------------------------------

class SafetyViolation:
    """A safety rule that was violated."""
    def __init__(self, rule: str, severity: str, detail: str):
        self.rule = rule
        self.severity = severity  # "block", "warn"
        self.detail = detail


def check_plan_safety(
    actions: List[PlannedAction],
    max_auto_actions: int = 5,
) -> List[SafetyViolation]:
    """
    Run safety checks against a full defense plan.
    Returns violations — blocking violations prevent execution.
    """
    violations = []

    # Check: too many auto-execute actions
    auto_count = sum(1 for a in actions if not a.requires_approval)
    if auto_count > max_auto_actions:
        violations.append(SafetyViolation(
            rule="max_auto_actions",
            severity="warn",
            detail=f"Plan has {auto_count} auto-execute actions (limit: {max_auto_actions}). "
                   f"Excess actions will require approval.",
        ))

    # Check: multiple isolations (could take down the network)
    isolations = [a for a in actions if a.action_type == ActionType.ISOLATE_HOST]
    if len(isolations) > 2:
        violations.append(SafetyViolation(
            rule="multiple_isolations",
            severity="warn",
            detail=f"Plan isolates {len(isolations)} hosts. "
                   f"Verify this won't cause a service outage.",
        ))

    # Check: conflicting actions (isolate + deploy EDR on same host)
    isolated_targets = {a.target for a in actions if a.action_type == ActionType.ISOLATE_HOST}
    for action in actions:
        if (
            action.action_type in (ActionType.DEPLOY_EDR, ActionType.PATCH_VULNERABILITY)
            and action.target in isolated_targets
        ):
            violations.append(SafetyViolation(
                rule="action_after_isolation",
                severity="warn",
                detail=f"Action {action.action_type.value} on {action.target} "
                       f"may fail because the host is being isolated.",
            ))

    # Check: credential revocation without investigation
    has_revoke = any(a.action_type == ActionType.REVOKE_CREDENTIALS for a in actions)
    if has_revoke:
        violations.append(SafetyViolation(
            rule="credential_revocation_impact",
            severity="warn",
            detail="Credential revocation will affect all sessions. "
                   "Verify which users/services depend on these credentials.",
        ))

    return violations


# ---------------------------------------------------------------------------
# Action Builder
# ---------------------------------------------------------------------------

def build_planned_action(
    action_id: str,
    d3fend_technique: D3FENDTechnique,
    target_ip: str,
    target_hostname: str,
    target_criticality: str,
    impact_score: float,
    confidence: float,
    counters_techniques: List[str],
    rationale: str,
    auto_execute_min: float = 0.70,
    auto_veto_min: float = 0.85,
) -> PlannedAction:
    """
    Build a fully-classified PlannedAction from a D3FEND technique and context.
    """
    blast_radius = classify_blast_radius(
        d3fend_technique.action_type, target_criticality
    )

    safety_score = d3fend_technique.default_safety
    # Reduce safety for critical targets
    if target_criticality == "critical":
        safety_score *= 0.75
    elif target_criticality == "high":
        safety_score *= 0.90

    composite = compute_composite_score(impact_score, safety_score, confidence)

    tier = determine_approval_tier(
        confidence=confidence,
        blast_radius=blast_radius,
        target_criticality=target_criticality,
        auto_execute_min=auto_execute_min,
        auto_veto_min=auto_veto_min,
    )

    return PlannedAction(
        action_id=action_id,
        action_type=d3fend_technique.action_type,
        target=target_ip,
        target_hostname=target_hostname,
        adapter=d3fend_technique.adapter,
        confidence=confidence,
        impact_score=impact_score,
        safety_score=round(safety_score, 4),
        composite_score=composite,
        blast_radius=blast_radius,
        approval_tier=tier,
        requires_approval=requires_human_approval(tier),
        d3fend_technique=d3fend_technique.technique_id,
        d3fend_label=d3fend_technique.label,
        counters_techniques=counters_techniques,
        status=ActionStatus.PENDING,
        rationale=rationale,
    )
