"""Evidence-based verification. Missing telemetry is never a successful defense."""
import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone

import httpx
from services.common.api_security import service_client

from services.response_orchestrator.models import VerificationResult

logger = logging.getLogger(__name__)


class VerificationEngine:
    def __init__(self, simulation_url="http://correlation-engine:8000", correlation_url="http://correlation-engine:8000",
                 wazuh_api_url="", wazuh_username="", wazuh_password="", wazuh_verify_ssl=True,
                 risk_reduction_threshold=0.30, monitoring_duration_seconds=1800,
                 indexer_url="", indexer_username="", indexer_password=""):
        self.simulation_url = simulation_url
        self.correlation_url = correlation_url
        self.wazuh_verify_ssl = wazuh_verify_ssl
        self.risk_reduction_threshold = risk_reduction_threshold
        self.monitoring_duration_seconds = monitoring_duration_seconds
        self.indexer_url = indexer_url.rstrip("/")
        self.indexer_username = indexer_username
        self.indexer_password = indexer_password

    async def verify_plan(self, plan, updated_environment=None):
        if plan.dry_run:
            return self._unavailable(plan, "Dry runs do not verify real defensive effects")
        resim, monitor = await asyncio.gather(
            self._track_resimulation(plan, updated_environment), self._track_monitoring(plan))
        sim_available = resim.get("available", False)
        monitor_available = monitor.get("available", False)
        available = sim_available and monitor_available
        pre = resim.get("pre_success_rate", plan.pre_defense_risk if plan.pre_defense_risk is not None else 0.0)
        post = resim.get("post_success_rate", pre)
        reduction = (pre - post) / pre if pre > 0 else 0.0
        continued = monitor.get("continued_indicators", False)
        passed = available and reduction >= self.risk_reduction_threshold and not continued
        if not available:
            reason = "Verification unavailable: " + "; ".join(x.get("error", "") for x in (resim, monitor) if not x.get("available"))
        elif passed:
            reason = f"Measured simulation reduction {reduction:.1%}; no matching indicators during the observed window"
        else:
            reason = f"Verification failed: simulation reduction {reduction:.1%}; continued indicators={continued}"
        return VerificationResult(
            plan_id=plan.plan_id, pre_attack_success_rate=pre, post_attack_success_rate=post,
            risk_reduction_pct=reduction, re_simulation_id=resim.get("simulation_id"),
            continued_indicators=continued, monitoring_duration_seconds=monitor.get("duration", 0),
            new_alerts_during_monitoring=monitor.get("new_alerts", 0), verification_passed=passed,
            verdict_reason=reason, evidence_available=available, simulation_available=sim_available,
            monitoring_available=monitor_available,
        )

    def _unavailable(self, plan, reason):
        baseline = plan.pre_defense_risk if plan.pre_defense_risk is not None else 0.0
        return VerificationResult(plan_id=plan.plan_id, pre_attack_success_rate=baseline,
                                  post_attack_success_rate=baseline, risk_reduction_pct=0.0,
                                  verification_passed=False, verdict_reason=reason)

    async def _track_resimulation(self, plan, updated_environment):
        if plan.pre_defense_risk is None or updated_environment is None:
            return {"available": False, "error": "a measured baseline and observed post-action environment are required"}
        try:
            async with service_client() as client:
                response = await client.post(f"{self.simulation_url}/simulate", params={"timesteps": 3},
                                             json=updated_environment, timeout=120)
                response.raise_for_status()
                data = response.json()
                post = float(data["results_summary"]["success_rate"])
                if not math.isfinite(post) or not 0 <= post <= 1 or not data.get("simulation_id"):
                    raise ValueError("Invalid simulation evidence")
                return {"available": True, "simulation_id": data["simulation_id"],
                        "pre_success_rate": plan.pre_defense_risk, "post_success_rate": post}
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            logger.warning("Re-simulation unavailable: %s", exc)
            return {"available": False, "error": "re-simulation request failed or returned incomplete evidence"}

    async def _track_monitoring(self, plan):
        if not self.indexer_url or not (plan.source_ips or plan.detected_techniques):
            return {"available": False, "error": "Wazuh indexer and incident indicators must be configured"}
        if self.monitoring_duration_seconds <= 0:
            return {"available": False, "error": "monitoring duration must be positive"}
        since = datetime.now(timezone.utc)
        loop = asyncio.get_running_loop()
        started = loop.time()
        seen = set()
        try:
            while True:
                elapsed = loop.time() - started
                await asyncio.sleep(min(10, max(0, self.monitoring_duration_seconds - elapsed)))
                alerts = await self._check_wazuh_alerts(plan.source_ips, plan.detected_techniques, since=since)
                seen.update(item["_id"] for item in alerts)
                if loop.time() - started >= self.monitoring_duration_seconds:
                    break
            return {"available": True, "continued_indicators": bool(seen), "new_alerts": len(seen),
                    "duration": int(loop.time() - started)}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            logger.exception("Wazuh monitoring unavailable")
            return {"available": False, "error": "Wazuh indexer query failed", "duration": int(loop.time() - started)}

    async def _check_wazuh_alerts(self, source_ips, techniques, since_minutes=5, since=None):
        # Alerts live in the indexer, not GET /alerts on the manager API.
        since = since or datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        indicators = []
        if source_ips:
            indicators.append({"terms": {"data.srcip": source_ips}})
        if techniques:
            indicators.append({"terms": {"rule.mitre.id": techniques}})
        query = {"size": 100, "query": {"bool": {
            "filter": [{"range": {"timestamp": {"gte": since.isoformat()}}}],
            "should": indicators, "minimum_should_match": 1}}, "sort": [{"timestamp": "desc"}]}
        async with httpx.AsyncClient(verify=self.wazuh_verify_ssl) as client:
            response = await client.post(f"{self.indexer_url}/wazuh-alerts-*/_search", json=query,
                auth=(self.indexer_username, self.indexer_password), timeout=15)
            response.raise_for_status()
            payload = response.json()
            if payload.get("timed_out") or payload.get("_shards", {}).get("failed", 0):
                raise ValueError("Incomplete indexer results")
            return payload["hits"]["hits"]
