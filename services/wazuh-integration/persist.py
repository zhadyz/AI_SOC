"""
Persist EnrichedAlert JSON to disk for E2E testing and audit.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _safe_id(alert_id: str) -> str:
    cleaned = re.sub(r"[^\w.\-]", "_", alert_id or "unknown")
    return cleaned[:128] or "unknown"


def save_enriched_alert(
    directory: str,
    payload: Dict[str, Any],
    wazuh_alert_id: str,
) -> Optional[str]:
    """
    Write one enriched alert JSON file. Returns path written or None on failure.
    """
    if not directory:
        return None

    try:
        out_dir = Path(directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = out_dir / f"enriched-{_safe_id(wazuh_alert_id)}-{ts}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info("enriched_alert_saved", path=str(path), alert_id=wazuh_alert_id)
        return str(path)
    except OSError as exc:
        logger.warning(
            "enriched_alert_save_failed",
            alert_id=wazuh_alert_id,
            directory=directory,
            error=str(exc),
        )
        return None
