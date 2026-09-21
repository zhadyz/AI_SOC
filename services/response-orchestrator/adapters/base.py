"""
Base Adapter - Action Execution Layer
AI-Augmented SOC

Abstract base class for all defense action adapters. Every adapter
must implement execute, verify, rollback, and dry_run.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class AdapterResult:
    """Standardized result from any adapter operation."""

    success: bool
    action_type: str
    target: str
    adapter: str
    detail: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    rollback_capable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action_type": self.action_type,
            "target": self.target,
            "adapter": self.adapter,
            "detail": self.detail,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "rollback_capable": self.rollback_capable,
            "raw_response": self.raw_response,
        }


class BaseAdapter(ABC):
    """
    Abstract base class for defense action adapters.

    Subclasses implement the four lifecycle methods for their
    specific infrastructure integration (Wazuh, firewall, EDR, etc.).
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"adapter.{name}")

    @abstractmethod
    async def execute(
        self, action_type: str, target: str, params: Optional[Dict] = None
    ) -> AdapterResult:
        """
        Execute a defense action against the target.

        Args:
            action_type: The ActionType enum value (e.g., "block_ip")
            target: Target IP, hostname, or resource identifier
            params: Additional action-specific parameters

        Returns:
            AdapterResult with success/failure and details
        """
        ...

    @abstractmethod
    async def verify(
        self, action_type: str, target: str, params: Optional[Dict] = None
    ) -> AdapterResult:
        """
        Verify that a previously executed action is still in effect.

        Returns:
            AdapterResult where success=True means the action is confirmed active
        """
        ...

    @abstractmethod
    async def rollback(
        self, action_type: str, target: str, params: Optional[Dict] = None
    ) -> AdapterResult:
        """
        Reverse a previously executed action.

        Returns:
            AdapterResult with success/failure of the rollback
        """
        ...

    async def dry_run(
        self, action_type: str, target: str, params: Optional[Dict] = None
    ) -> AdapterResult:
        """
        Simulate execution without making changes. Default implementation
        returns a synthetic success result.
        """
        return AdapterResult(
            success=True,
            action_type=action_type,
            target=target,
            adapter=self.name,
            detail=f"[DRY RUN] Would execute {action_type} on {target}",
            rollback_capable=False,
        )

    async def health_check(self) -> bool:
        """Check if the adapter's backend is reachable. Override in subclass."""
        return False


class UnavailableAdapter(BaseAdapter):
    """Honest boundary for a vendor integration that is not implemented."""

    supported_actions: tuple[str, ...] = ()

    async def execute(self, action_type, target, params=None):
        if action_type not in self.supported_actions:
            return AdapterResult(
                False,
                action_type,
                target,
                self.name,
                "Unsupported action",
                error="unsupported_action",
                rollback_capable=False,
            )
        return AdapterResult(
            False,
            action_type,
            target,
            self.name,
            "Vendor integration is not configured or implemented",
            error="adapter_unavailable",
            rollback_capable=False,
        )

    async def verify(self, action_type, target, params=None):
        return await self.execute(action_type, target, params)

    async def rollback(self, action_type, target, params=None):
        return await self.execute(action_type, target, params)

    async def dry_run(self, action_type, target, params=None):
        if action_type not in self.supported_actions:
            return AdapterResult(
                False,
                action_type,
                target,
                self.name,
                "Unsupported action",
                error="unsupported_action",
                rollback_capable=False,
            )
        return AdapterResult(
            True,
            action_type,
            target,
            self.name,
            f"[DRY RUN] Proposed {action_type} on {target}; vendor adapter unavailable",
            raw_response={"simulated": True, "parameters": params or {}},
            rollback_capable=False,
        )

    async def health_check(self):
        return False
