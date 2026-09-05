"""
MITRE D3FEND Integration - Response Orchestrator
AI-Augmented SOC

Maps ATT&CK offensive techniques to D3FEND defensive countermeasures,
then maps those to concrete executable actions. This is the bridge
between "what attack was detected" and "what defense should we deploy."

D3FEND v1.3.0 (December 2025) defines 267 countermeasure techniques
organized into 7 tactical categories: Model, Harden, Detect, Isolate,
Deceive, Evict, Restore.

This module provides a curated, runtime-queryable mapping covering the
20 attack actions in the AI-SOC simulator's action space, extended to
the broader ATT&CK techniques commonly seen in real SIEM alerts.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from services.response_orchestrator.models import ActionType, AdapterType, BlastRadius

logger = logging.getLogger(__name__)


@dataclass
class D3FENDTechnique:
    """A D3FEND defensive technique with its mapping to concrete actions."""
    technique_id: str          # e.g., "d3f:InboundTrafficFiltering"
    label: str                 # Human-readable name
    tactic: str                # D3FEND tactic: Harden, Detect, Isolate, Evict, Restore
    description: str           # What this technique does
    action_type: ActionType    # Concrete action in our system
    adapter: AdapterType       # Which adapter executes it
    blast_radius: BlastRadius  # Default blast radius for this action
    default_safety: float      # Base safety score (0-1), adjusted per target


# ---------------------------------------------------------------------------
# D3FEND Technique Registry
# ---------------------------------------------------------------------------

_D3FEND_TECHNIQUES: Dict[str, D3FENDTechnique] = {
    "d3f:InboundTrafficFiltering": D3FENDTechnique(
        technique_id="d3f:InboundTrafficFiltering",
        label="Inbound Traffic Filtering",
        tactic="Isolate",
        description="Restrict inbound network traffic from specific sources",
        action_type=ActionType.BLOCK_IP,
        adapter=AdapterType.WAZUH,
        blast_radius=BlastRadius.LOW,
        default_safety=0.92,
    ),
    "d3f:NetworkIsolation": D3FENDTechnique(
        technique_id="d3f:NetworkIsolation",
        label="Network Isolation",
        tactic="Isolate",
        description="Remove a host from the network to prevent lateral movement",
        action_type=ActionType.ISOLATE_HOST,
        adapter=AdapterType.WAZUH,
        blast_radius=BlastRadius.MEDIUM,
        default_safety=0.65,
    ),
    "d3f:EndpointHealthBeacon": D3FENDTechnique(
        technique_id="d3f:EndpointHealthBeacon",
        label="Endpoint Health Beacon",
        tactic="Detect",
        description="Deploy EDR agent for continuous endpoint monitoring",
        action_type=ActionType.DEPLOY_EDR,
        adapter=AdapterType.EDR,
        blast_radius=BlastRadius.LOW,
        default_safety=0.95,
    ),
    "d3f:CredentialHardening": D3FENDTechnique(
        technique_id="d3f:CredentialHardening",
        label="Credential Hardening",
        tactic="Harden",
        description="Revoke compromised credentials and force rotation",
        action_type=ActionType.REVOKE_CREDENTIALS,
        adapter=AdapterType.IDENTITY,
        blast_radius=BlastRadius.MEDIUM,
        default_safety=0.80,
    ),
    "d3f:MultiFactorAuthentication": D3FENDTechnique(
        technique_id="d3f:MultiFactorAuthentication",
        label="Multi-factor Authentication",
        tactic="Harden",
        description="Enforce multi-factor authentication on target service",
        action_type=ActionType.ENABLE_MFA,
        adapter=AdapterType.IDENTITY,
        blast_radius=BlastRadius.LOW,
        default_safety=0.90,
    ),
    "d3f:AccountLocking": D3FENDTechnique(
        technique_id="d3f:AccountLocking",
        label="Account Locking",
        tactic="Evict",
        description="Disable a user account suspected of compromise",
        action_type=ActionType.DISABLE_ACCOUNT,
        adapter=AdapterType.IDENTITY,
        blast_radius=BlastRadius.MEDIUM,
        default_safety=0.70,
    ),
    "d3f:ApplicationHardening": D3FENDTechnique(
        technique_id="d3f:ApplicationHardening",
        label="Application Hardening",
        tactic="Harden",
        description="Patch known vulnerability on target service",
        action_type=ActionType.PATCH_VULNERABILITY,
        adapter=AdapterType.WAZUH,
        blast_radius=BlastRadius.MEDIUM,
        default_safety=0.55,
    ),
    "d3f:FileIntegrityMonitoring": D3FENDTechnique(
        technique_id="d3f:FileIntegrityMonitoring",
        label="File Integrity Monitoring",
        tactic="Detect",
        description="Add enhanced monitoring and detection rules for target",
        action_type=ActionType.ADD_MONITORING,
        adapter=AdapterType.WAZUH,
        blast_radius=BlastRadius.NONE,
        default_safety=0.98,
    ),
    "d3f:ProcessAnalysis": D3FENDTechnique(
        technique_id="d3f:ProcessAnalysis",
        label="Process Analysis",
        tactic="Detect",
        description="Deploy detection rule for suspicious process behavior",
        action_type=ActionType.DEPLOY_SIGMA_RULE,
        adapter=AdapterType.WAZUH,
        blast_radius=BlastRadius.NONE,
        default_safety=0.97,
    ),
    "d3f:NetworkSegmentation": D3FENDTechnique(
        technique_id="d3f:NetworkSegmentation",
        label="Network Segmentation",
        tactic="Isolate",
        description="Restrict network segment reachability",
        action_type=ActionType.NETWORK_SEGMENT,
        adapter=AdapterType.NETWORK,
        blast_radius=BlastRadius.HIGH,
        default_safety=0.45,
    ),
    "d3f:ProcessTermination": D3FENDTechnique(
        technique_id="d3f:ProcessTermination",
        label="Process Termination",
        tactic="Evict",
        description="Kill a suspicious or malicious process on target host",
        action_type=ActionType.KILL_PROCESS,
        adapter=AdapterType.WAZUH,
        blast_radius=BlastRadius.LOW,
        default_safety=0.80,
    ),
    "d3f:DNSSinkhole": D3FENDTechnique(
        technique_id="d3f:DNSSinkhole",
        label="DNS Sinkhole",
        tactic="Isolate",
        description="Redirect DNS resolution for a malicious domain to a sinkhole",
        action_type=ActionType.SINKHOLE_DOMAIN,
        adapter=AdapterType.NETWORK,
        blast_radius=BlastRadius.LOW,
        default_safety=0.88,
    ),
    "d3f:RestoreBackup": D3FENDTechnique(
        technique_id="d3f:RestoreBackup",
        label="Restore from Backup",
        tactic="Restore",
        description="Restore system from clean backup after compromise",
        action_type=ActionType.RESTORE_BACKUP,
        adapter=AdapterType.WAZUH,
        blast_radius=BlastRadius.HIGH,
        default_safety=0.40,
    ),
}


# ---------------------------------------------------------------------------
# ATT&CK → D3FEND Mapping
#
# Each ATT&CK technique maps to an ordered list of D3FEND countermeasures.
# Order reflects defensive priority: containment first, then hardening,
# then detection enhancement.
# ---------------------------------------------------------------------------

_ATTACK_TO_D3FEND: Dict[str, List[str]] = {
    # Reconnaissance
    "T1046": [  # Network Service Scanning
        "d3f:InboundTrafficFiltering",
        "d3f:FileIntegrityMonitoring",
    ],
    "T1589": [  # Gather Victim Identity Info
        "d3f:FileIntegrityMonitoring",
    ],
    "T1595": [  # Active Scanning
        "d3f:InboundTrafficFiltering",
        "d3f:FileIntegrityMonitoring",
    ],

    # Initial Access
    "T1190": [  # Exploit Public-Facing Application
        "d3f:ApplicationHardening",
        "d3f:NetworkIsolation",
        "d3f:InboundTrafficFiltering",
        "d3f:EndpointHealthBeacon",
    ],
    "T1566": [  # Phishing
        "d3f:InboundTrafficFiltering",
        "d3f:FileIntegrityMonitoring",
        "d3f:ProcessAnalysis",
    ],
    "T1566.001": [  # Spearphishing Attachment
        "d3f:InboundTrafficFiltering",
        "d3f:ProcessAnalysis",
        "d3f:EndpointHealthBeacon",
    ],
    "T1078": [  # Valid Accounts
        "d3f:MultiFactorAuthentication",
        "d3f:CredentialHardening",
        "d3f:AccountLocking",
    ],
    "T1133": [  # External Remote Services
        "d3f:MultiFactorAuthentication",
        "d3f:InboundTrafficFiltering",
        "d3f:NetworkSegmentation",
    ],

    # Credential Access
    "T1110": [  # Brute Force
        "d3f:AccountLocking",
        "d3f:MultiFactorAuthentication",
        "d3f:InboundTrafficFiltering",
        "d3f:CredentialHardening",
    ],
    "T1110.001": [  # Password Guessing
        "d3f:AccountLocking",
        "d3f:MultiFactorAuthentication",
        "d3f:InboundTrafficFiltering",
    ],
    "T1003": [  # OS Credential Dumping
        "d3f:CredentialHardening",
        "d3f:EndpointHealthBeacon",
        "d3f:ProcessTermination",
        "d3f:NetworkIsolation",
    ],
    "T1003.001": [  # LSASS Memory
        "d3f:CredentialHardening",
        "d3f:EndpointHealthBeacon",
        "d3f:ProcessTermination",
    ],
    "T1550": [  # Use Alternate Authentication Material
        "d3f:CredentialHardening",
        "d3f:MultiFactorAuthentication",
        "d3f:FileIntegrityMonitoring",
    ],
    "T1550.002": [  # Pass the Hash
        "d3f:CredentialHardening",
        "d3f:MultiFactorAuthentication",
        "d3f:NetworkIsolation",
    ],

    # Execution
    "T1059": [  # Command and Scripting Interpreter
        "d3f:ProcessTermination",
        "d3f:EndpointHealthBeacon",
        "d3f:ProcessAnalysis",
        "d3f:NetworkIsolation",
    ],
    "T1059.001": [  # PowerShell
        "d3f:ProcessTermination",
        "d3f:EndpointHealthBeacon",
        "d3f:ProcessAnalysis",
    ],
    "T1059.003": [  # Windows Command Shell
        "d3f:ProcessTermination",
        "d3f:EndpointHealthBeacon",
        "d3f:ProcessAnalysis",
    ],

    # Persistence
    "T1547": [  # Boot or Logon Autostart Execution
        "d3f:EndpointHealthBeacon",
        "d3f:ProcessAnalysis",
        "d3f:FileIntegrityMonitoring",
    ],
    "T1053": [  # Scheduled Task/Job
        "d3f:EndpointHealthBeacon",
        "d3f:ProcessAnalysis",
        "d3f:FileIntegrityMonitoring",
    ],
    "T1136": [  # Create Account
        "d3f:AccountLocking",
        "d3f:FileIntegrityMonitoring",
    ],

    # Privilege Escalation
    "T1068": [  # Exploitation for Privilege Escalation
        "d3f:ApplicationHardening",
        "d3f:EndpointHealthBeacon",
        "d3f:NetworkIsolation",
    ],

    # Lateral Movement
    "T1210": [  # Exploitation of Remote Services
        "d3f:NetworkIsolation",
        "d3f:NetworkSegmentation",
        "d3f:EndpointHealthBeacon",
        "d3f:ApplicationHardening",
    ],
    "T1021": [  # Remote Services
        "d3f:MultiFactorAuthentication",
        "d3f:NetworkIsolation",
        "d3f:InboundTrafficFiltering",
    ],
    "T1021.001": [  # Remote Desktop Protocol
        "d3f:MultiFactorAuthentication",
        "d3f:NetworkIsolation",
        "d3f:InboundTrafficFiltering",
    ],
    "T1570": [  # Lateral Tool Transfer
        "d3f:NetworkIsolation",
        "d3f:EndpointHealthBeacon",
        "d3f:FileIntegrityMonitoring",
    ],

    # Defense Evasion
    "T1562": [  # Impair Defenses
        "d3f:EndpointHealthBeacon",
        "d3f:ProcessAnalysis",
        "d3f:FileIntegrityMonitoring",
    ],
    "T1070": [  # Indicator Removal
        "d3f:FileIntegrityMonitoring",
        "d3f:ProcessAnalysis",
        "d3f:EndpointHealthBeacon",
    ],

    # Collection & C2
    "T1071": [  # Application Layer Protocol (C2)
        "d3f:InboundTrafficFiltering",
        "d3f:DNSSinkhole",
        "d3f:FileIntegrityMonitoring",
    ],
    "T1071.004": [  # DNS tunneling
        "d3f:DNSSinkhole",
        "d3f:InboundTrafficFiltering",
        "d3f:FileIntegrityMonitoring",
    ],
    "T1105": [  # Ingress Tool Transfer
        "d3f:InboundTrafficFiltering",
        "d3f:NetworkIsolation",
        "d3f:EndpointHealthBeacon",
    ],

    # Exfiltration
    "T1041": [  # Exfiltration Over C2 Channel
        "d3f:NetworkIsolation",
        "d3f:InboundTrafficFiltering",
        "d3f:DNSSinkhole",
    ],
    "T1048": [  # Exfiltration Over Alternative Protocol
        "d3f:NetworkIsolation",
        "d3f:InboundTrafficFiltering",
    ],

    # Impact
    "T1486": [  # Data Encrypted for Impact (Ransomware)
        "d3f:NetworkIsolation",
        "d3f:RestoreBackup",
        "d3f:ProcessTermination",
        "d3f:EndpointHealthBeacon",
    ],
    "T1489": [  # Service Stop
        "d3f:NetworkIsolation",
        "d3f:FileIntegrityMonitoring",
    ],
    "T1490": [  # Inhibit System Recovery
        "d3f:RestoreBackup",
        "d3f:NetworkIsolation",
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_countermeasures(technique_id: str) -> List[D3FENDTechnique]:
    """
    Given an ATT&CK technique ID, return ordered D3FEND countermeasures.

    Handles both exact matches (T1110.001) and parent matches (T1110).
    Returns empty list for unknown techniques.
    """
    # Try exact match first
    d3fend_ids = _ATTACK_TO_D3FEND.get(technique_id, [])

    # Fall back to parent technique (e.g., T1110.001 → T1110)
    if not d3fend_ids and "." in technique_id:
        parent = technique_id.split(".")[0]
        d3fend_ids = _ATTACK_TO_D3FEND.get(parent, [])

    techniques = []
    for d3f_id in d3fend_ids:
        technique = _D3FEND_TECHNIQUES.get(d3f_id)
        if technique:
            techniques.append(technique)
        else:
            logger.warning(f"D3FEND technique not found in registry: {d3f_id}")

    return techniques


def get_all_countermeasures_for_incident(
    technique_ids: List[str],
) -> Dict[str, List[D3FENDTechnique]]:
    """
    Given all ATT&CK techniques in an incident, return a deduplicated
    map of technique_id → countermeasures.
    """
    result = {}
    for tid in technique_ids:
        countermeasures = get_countermeasures(tid)
        if countermeasures:
            result[tid] = countermeasures
    return result


def get_unique_actions_for_incident(
    technique_ids: List[str],
) -> List[D3FENDTechnique]:
    """
    Deduplicate countermeasures across all detected techniques.
    Returns unique D3FEND techniques, preserving priority order.
    """
    seen: Set[str] = set()
    unique = []
    for tid in technique_ids:
        for technique in get_countermeasures(tid):
            if technique.technique_id not in seen:
                seen.add(technique.technique_id)
                unique.append(technique)
    return unique


def get_technique_info(d3fend_id: str) -> Optional[D3FENDTechnique]:
    """Look up a D3FEND technique by its ID."""
    return _D3FEND_TECHNIQUES.get(d3fend_id)


def get_supported_attack_techniques() -> List[str]:
    """Return all ATT&CK technique IDs that have D3FEND mappings."""
    return sorted(_ATTACK_TO_D3FEND.keys())
