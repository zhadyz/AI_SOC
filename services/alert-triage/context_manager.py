"""
Context Manager - Alert Triage Service
AI-Augmented SOC

Fetches contextual information from the feedback service and formats it
for injection into LLM prompts before alert analysis. Provides three
context layers: environment knowledge, recent alert history, and analyst
feedback patterns.

Context is strictly supplementary — every fetch is timeboxed and any
failure results in empty string, never a blocked triage.

Author: HOLLOWED_EYES
"""

import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
import httpx
from services.common.api_security import service_client

from services.alert_triage.models import SecurityAlert

logger = logging.getLogger(__name__)

# Hard limit on notes text to keep prompts from ballooning
_MAX_NOTE_CHARS = 200
_MAX_NOTES_INCLUDED = 5


class ContextManager:
    """
    Builds contextual prompt sections by querying the feedback service.

    Three context layers:
      1. Environment context — static org knowledge (overridable via env var)
      2. Alert history     — recent alerts from the same source IP
      3. Feedback patterns — analyst verdicts for that source IP

    All external calls use a shared timeout and degrade gracefully to
    empty string on any error, ensuring triage is never blocked.
    """

    def __init__(
        self,
        feedback_service_url: str,
        enabled: bool = True,
        timeout: int = 5,
        history_limit: int = 5,
        environment_context: str = "",
    ):
        self.feedback_url = feedback_service_url.rstrip("/")
        self.enabled = enabled
        self.timeout = float(timeout)
        self.history_limit = history_limit
        self.environment_context = environment_context

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def build_context(self, alert: SecurityAlert) -> str:
        """
        Assemble all available context sections for the given alert.

        Returns a single string ready for prompt injection, or empty
        string if context is disabled or nothing is available.

        Args:
            alert: The SecurityAlert about to be triaged.

        Returns:
            str: Formatted context block, or "" if nothing to inject.
        """
        if not self.enabled:
            return ""

        sections = []

        # Layer 1: Environment context
        env_ctx = await self._get_environment_context()
        if env_ctx:
            sections.append(env_ctx)

        # Layers 2 & 3 are IP-scoped; skip if no source IP
        if alert.source_ip:
            history = await self._get_alert_history(alert.source_ip)
            if history:
                sections.append(history)

            patterns = await self._get_feedback_patterns(alert.source_ip)
            if patterns:
                sections.append(patterns)

        if not sections:
            return ""

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_environment_context(self) -> str:
        """Operator-provided environment notes, bounded before prompt insertion."""
        if self.environment_context:
            return f"**ENVIRONMENT CONTEXT:**\n{self.environment_context[:4000]}"
        return ""

    async def _get_alert_history(self, source_ip: str) -> str:
        """
        Fetch recent alerts from the feedback service for source_ip and
        summarise them for the LLM.

        Args:
            source_ip: The source IP address to query.

        Returns:
            str: Formatted history section, or "".
        """
        try:
            async with service_client(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.feedback_url}/alerts",
                    params={"source_ip": source_ip, "limit": self.history_limit},
                )

            if response.status_code != 200:
                logger.debug(
                    f"Alert history fetch returned {response.status_code} "
                    f"for IP {source_ip}"
                )
                return ""

            data = response.json()
            alerts = data if isinstance(data, list) else data.get("alerts", [])

            if not alerts:
                return ""

            total = len(alerts)

            # Severity breakdown
            severity_counts: dict[str, int] = {}
            category_counts: dict[str, int] = {}
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            within_24h = 0

            for a in alerts:
                sev = a.get("ai_severity") or a.get("severity") or "unknown"
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

                cat = a.get("ai_category") or a.get("category") or "unknown"
                category_counts[cat] = category_counts.get(cat, 0) + 1

                ts_raw = a.get("timestamp") or a.get("created_at")
                if ts_raw:
                    try:
                        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                        if ts >= cutoff:
                            within_24h += 1
                    except (ValueError, TypeError):
                        pass

            sev_summary = ", ".join(
                f"{k}: {v}" for k, v in sorted(severity_counts.items())
            )
            cat_summary = ", ".join(
                f"{k}: {v}" for k, v in sorted(category_counts.items())
            )

            lines = [
                f"In the last retrieved {total} alert(s) from this IP, "
                f"{within_24h} occurred within the past 24 hours.",
                f"Severities: {sev_summary}.",
                f"Categories: {cat_summary}.",
            ]

            body = " ".join(lines)
            return f"**RECENT ALERT HISTORY from {source_ip}:**\n{body}"

        except httpx.TimeoutException:
            logger.debug(f"Alert history fetch timeout for IP {source_ip}")
            return ""
        except Exception as e:
            logger.debug(f"Alert history fetch failed for IP {source_ip}: {e}")
            return ""

    async def _get_feedback_patterns(self, source_ip: str) -> str:
        """
        Fetch analyst feedback for alerts from source_ip and summarise
        the false-positive rate and common analyst notes.

        Args:
            source_ip: The source IP address to query.

        Returns:
            str: Formatted feedback patterns section, or "".
        """
        try:
            async with service_client(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.feedback_url}/alerts",
                    params={
                        "source_ip": source_ip,
                        "has_feedback": "true",
                        "limit": 10,
                    },
                )

            if response.status_code != 200:
                logger.debug(
                    f"Feedback patterns fetch returned {response.status_code} "
                    f"for IP {source_ip}"
                )
                return ""

            data = response.json()
            alerts = data if isinstance(data, list) else data.get("alerts", [])

            # The list endpoint contains summaries; read the latest analyst
            # verdict for each returned alert from its actual feedback endpoint.
            reviewed = []
            async with service_client(timeout=self.timeout) as client:
                for item in alerts[: self.history_limit]:
                    result = await client.get(
                        f"{self.feedback_url}/feedback/{item['alert_id']}"
                    )
                    result.raise_for_status()
                    feedback = result.json().get("feedback", [])
                    if feedback:
                        latest = feedback[0]
                        reviewed.append(
                            {
                                "analyst_verdict": "false_positive"
                                if latest["is_false_positive"]
                                else "true_positive",
                                "analyst_notes": latest.get("notes", ""),
                            }
                        )

            if not reviewed:
                return ""

            total_reviewed = len(reviewed)
            false_positives = sum(
                1
                for a in reviewed
                if (
                    a.get("analyst_verdict") == "false_positive"
                    or a.get("feedback") == "false_positive"
                    or str(a.get("is_true_positive", "true")).lower() == "false"
                )
            )

            fp_pct = round((false_positives / total_reviewed) * 100)

            # Collect analyst notes, capped for brevity
            raw_notes: list[str] = []
            for a in reviewed:
                note = a.get("analyst_notes") or a.get("notes") or ""
                if note and isinstance(note, str):
                    note = note.strip()[:_MAX_NOTE_CHARS]
                    if note:
                        raw_notes.append(note)
                if len(raw_notes) >= _MAX_NOTES_INCLUDED:
                    break

            lines = [
                f"Analysts have reviewed {total_reviewed} previous alert(s) "
                f"from this IP.",
                f"{fp_pct}% were marked as false positives.",
            ]

            if raw_notes:
                notes_block = "; ".join(f'"{n}"' for n in raw_notes)
                lines.append(f"Common notes: {notes_block}.")

            body = " ".join(lines)
            return f"**ANALYST FEEDBACK HISTORY for {source_ip}:**\n{body}"

        except httpx.TimeoutException:
            logger.debug(f"Feedback patterns fetch timeout for IP {source_ip}")
            return ""
        except Exception as e:
            logger.debug(f"Feedback patterns fetch failed for IP {source_ip}: {e}")
            return ""
