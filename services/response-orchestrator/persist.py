"""
Persist DefensePlan JSON to disk for E2E testing and audit.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _safe_id(plan_id: str) -> str:
    cleaned = re.sub(r"[^\w.\-]", "_", plan_id or "unknown")
    return cleaned[:128] or "unknown"


def save_defense_plan(directory: str, payload: Dict[str, Any]) -> Optional[str]:
    """
    Write one defense plan JSON file (overwrites prior file for same plan_id).
    Returns path written or None on failure.
    """
    if not directory:
        return None

    plan_id = payload.get("plan_id") or "unknown"
    try:
        out_dir = Path(directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"defense-{_safe_id(plan_id)}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info("defense_plan_saved", path=str(path), plan_id=plan_id)
        return str(path)
    except OSError as exc:
        logger.warning(
            "defense_plan_save_failed",
            plan_id=plan_id,
            directory=directory,
            error=str(exc),
        )
        return None
