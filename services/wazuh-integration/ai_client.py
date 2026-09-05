"""
AI Client - Wazuh Integration Service
AI-Augmented SOC

Handles communication with Alert Triage and RAG services.
"""

import httpx
from services.common.api_security import service_client
import structlog
from typing import Dict, Any, Optional
from services.wazuh_integration.config import Settings
from services.wazuh_integration.models import WazuhAlert

logger = structlog.get_logger()


class AIClient:
    """Client for AI service integration"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.triage_url = settings.alert_triage_url
        self.rag_url = settings.rag_service_url
        self.correlation_url = settings.correlation_engine_url
        self.ai_timeout = settings.ai_service_timeout

        logger.info(
            "ai_client_initialized",
            triage_url=self.triage_url,
            rag_url=self.rag_url,
            correlation_url=self.correlation_url,
        )

    def transform_wazuh_to_triage_format(self, wazuh_alert: WazuhAlert) -> Dict[str, Any]:
        """
        Transform Wazuh alert JSON to Alert Triage SecurityAlert format.

        Args:
            wazuh_alert: Parsed Wazuh alert

        Returns:
            Dictionary matching SecurityAlert model from alert-triage service
        """
        # Extract MITRE techniques if present
        mitre_techniques = None
        if wazuh_alert.rule.mitre:
            mitre_techniques = wazuh_alert.rule.mitre.get("id", [])

        # Build SecurityAlert payload
        triage_payload = {
            "alert_id": wazuh_alert.id,
            "timestamp": wazuh_alert.timestamp,
            "rule_id": wazuh_alert.rule.id,
            "rule_description": wazuh_alert.rule.description,
            "rule_level": wazuh_alert.rule.level,
            "raw_log": wazuh_alert.full_log,
            "full_log": wazuh_alert.model_dump(),  # Entire Wazuh alert as context
            "mitre_technique": mitre_techniques
        }

        # Add agent information if available
        if wazuh_alert.agent:
            triage_payload["source_hostname"] = wazuh_alert.agent.name
            triage_payload["source_ip"] = wazuh_alert.agent.ip

        # Add parsed data fields if available
        if wazuh_alert.data:
            data = wazuh_alert.data
            if data.srcip:
                triage_payload["source_ip"] = data.srcip
            if data.srcport:
                triage_payload["source_port"] = data.srcport
            if data.dstip:
                triage_payload["dest_ip"] = data.dstip
            if data.dstport:
                triage_payload["dest_port"] = data.dstport
            if data.srcuser:
                triage_payload["user"] = data.srcuser
            elif data.dstuser:
                triage_payload["user"] = data.dstuser

        return triage_payload

    async def analyze_alert(self, wazuh_alert: WazuhAlert) -> Dict[str, Any]:
        """
        Send alert to Alert Triage service for AI analysis.

        Args:
            wazuh_alert: Parsed Wazuh alert

        Returns:
            TriageResponse from alert-triage service
        """
        triage_payload = self.transform_wazuh_to_triage_format(wazuh_alert)
        analyze_url = f"{self.triage_url}/analyze"

        try:
            async with service_client() as client:
                response = await client.post(
                    analyze_url,
                    json=triage_payload,
                    timeout=self.ai_timeout
                )
                response.raise_for_status()

                triage_result = response.json()

                logger.info(
                    "alert_triage_analysis_complete",
                    alert_id=wazuh_alert.id,
                    severity=triage_result.get("severity"),
                    is_true_positive=triage_result.get("is_true_positive")
                )

                return triage_result

        except httpx.HTTPError as e:
            logger.error(
                "alert_triage_failed",
                error=str(e),
                alert_id=wazuh_alert.id,
                url=analyze_url
            )
            raise

    async def enrich_with_rag(
        self,
        alert_id: str,
        rule_description: str,
        mitre_techniques: Optional[list] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Query RAG service for MITRE ATT&CK and incident context.

        Args:
            alert_id: Alert identifier
            rule_description: Wazuh rule description
            mitre_techniques: List of MITRE technique IDs (e.g., ["T1110"])

        Returns:
            RAG enrichment data or None if service unavailable
        """
        # Build RAG query
        query_parts = [rule_description]
        if mitre_techniques:
            query_parts.extend([f"MITRE {t}" for t in mitre_techniques])

        query = " ".join(query_parts)

        rag_url = f"{self.rag_url}/retrieve"

        try:
            async with service_client() as client:
                response = await client.post(
                    rag_url,
                    json={
                        "query": query,
                        "collection": "mitre_attack",
                        "top_k": 3,
                        "min_similarity": 0.5
                    },
                    timeout=self.ai_timeout
                )
                response.raise_for_status()

                rag_result = response.json()

                logger.info(
                    "rag_enrichment_complete",
                    alert_id=alert_id,
                    sources_found=len(rag_result.get("results", []))
                )

                return rag_result

        except httpx.HTTPError as e:
            logger.warning(
                "rag_enrichment_failed",
                error=str(e),
                alert_id=alert_id,
                # Don't fail the entire pipeline if RAG is unavailable
            )
            return None

    async def correlate_alert(self, enriched_alert) -> Optional[Dict[str, Any]]:
        """
        Send an enriched alert to the Correlation Engine for incident grouping.

        Args:
            enriched_alert: EnrichedAlert instance after triage and RAG enrichment

        Returns:
            CorrelationResponse dict or None if the service is unavailable
        """
        try:
            # Build correlation payload from enriched alert fields
            correlation_data = {
                "alert_id": enriched_alert.wazuh_alert_id,
                "timestamp": enriched_alert.processing_timestamp.isoformat(),
                "severity": enriched_alert.ai_severity,
                "category": enriched_alert.ai_category,
                "mitre_techniques": enriched_alert.kb_references or [],
                "mitre_tactics": [],
                "rule_description": enriched_alert.wazuh_rule_description,
            }

            async with service_client(timeout=30) as client:
                response = await client.post(
                    f"{self.correlation_url}/correlate",
                    json=correlation_data,
                )
                response.raise_for_status()

                result = response.json()

                logger.info(
                    "correlation_complete",
                    alert_id=enriched_alert.wazuh_alert_id,
                    incident_id=result.get("incident_id"),
                    is_new=result.get("is_new_incident"),
                    score=result.get("correlation_score"),
                )

                return result

        except Exception as exc:
            logger.warning(
                "correlation_failed",
                alert_id=enriched_alert.wazuh_alert_id,
                error=str(exc),
            )
            return None

    async def health_check_triage(self) -> bool:
        """Check Alert Triage service health"""
        try:
            async with service_client() as client:
                response = await client.get(
                    f"{self.triage_url}/health",
                    timeout=5
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error("triage_health_check_failed", error=str(e))
            return False

    async def health_check_rag(self) -> bool:
        """Check RAG service health"""
        try:
            async with service_client() as client:
                response = await client.get(
                    f"{self.rag_url}/health",
                    timeout=5
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.warning("rag_health_check_failed", error=str(e))
            return False  # RAG is optional, so don't fail hard
