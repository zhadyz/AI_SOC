"""
Alert Processing Pipeline Orchestration
========================================

End-to-end pipeline for automated security alert processing:
Network Traffic → Detection → Triage → Case Creation → Response

Author: HOLLOWED_EYES
Mission: OPERATION PIPELINE-INTEGRATION
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import json

from integration import (
    MLInferenceClient,
    AlertTriageClient,
    RAGServiceClient,
    TheHiveClient,
    FallbackHandler,
    event_bus
)

logger = logging.getLogger(__name__)


# ============================================================================
# Pipeline Models
# ============================================================================

class PipelineStage(str, Enum):
    """Pipeline processing stages"""
    RECEIVED = "received"
    ML_DETECTION = "ml_detection"
    TRIAGE_ANALYSIS = "triage_analysis"
    CONTEXT_ENRICHMENT = "context_enrichment"
    CASE_CREATION = "case_creation"
    RESPONSE_ACTION = "response_action"
    COMPLETED = "completed"
    FAILED = "failed"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PipelineMetrics:
    """Track pipeline performance metrics"""

    def __init__(self):
        self.total_processed = 0
        self.total_failed = 0
        self.stage_times: Dict[str, List[float]] = {}
        self.severity_counts: Dict[str, int] = {}

    def record_stage_time(self, stage: str, duration: float):
        """Record stage processing time"""
        if stage not in self.stage_times:
            self.stage_times[stage] = []
        self.stage_times[stage].append(duration)

    def record_severity(self, severity: str):
        """Record alert severity"""
        self.severity_counts[severity] = self.severity_counts.get(severity, 0) + 1

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        stats = {
            "total_processed": self.total_processed,
            "total_failed": self.total_failed,
            "success_rate": (
                self.total_processed / (self.total_processed + self.total_failed)
                if (self.total_processed + self.total_failed) > 0 else 0
            ),
            "severity_distribution": self.severity_counts,
            "stage_performance": {}
        }

        for stage, times in self.stage_times.items():
            if times:
                stats["stage_performance"][stage] = {
                    "avg_time_ms": sum(times) / len(times),
                    "min_time_ms": min(times),
                    "max_time_ms": max(times),
                    "count": len(times)
                }

        return stats


# ============================================================================
# Alert Processing Pipeline
# ============================================================================

class AlertPipeline:
    """
    End-to-end alert processing pipeline.

    Flow:
    1. Receive alert from Wazuh/Suricata/Zeek
    2. ML Detection (predict attack/benign)
    3. LLM Triage (analyze severity, extract IOCs)
    4. Context Enrichment (RAG retrieval)
    5. Case Creation (TheHive)
    6. Response Actions (Shuffle workflows)
    """

    def __init__(
        self,
        ml_client: Optional[MLInferenceClient] = None,
        triage_client: Optional[AlertTriageClient] = None,
        rag_client: Optional[RAGServiceClient] = None,
        thehive_client: Optional[TheHiveClient] = None,
        enable_ml: bool = True,
        enable_rag: bool = True,
        thehive_threshold: str = "high"
    ):
        self.ml_client = ml_client or MLInferenceClient()
        self.triage_client = triage_client or AlertTriageClient()
        self.rag_client = rag_client or RAGServiceClient()
        self.thehive_client = thehive_client or TheHiveClient()

        self.enable_ml = enable_ml
        self.enable_rag = enable_rag
        self.thehive_threshold = thehive_threshold

        self.metrics = PipelineMetrics()
        self.processing_queue = asyncio.Queue()

    async def process_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single alert through the complete pipeline.

        Args:
            alert: Raw alert from Wazuh/IDS

        Returns:
            Processed alert with enriched data and actions taken
        """
        alert_id = alert.get("id", "unknown")
        start_time = datetime.now()

        pipeline_result = {
            "alert_id": alert_id,
            "timestamp": start_time.isoformat(),
            "stages": {},
            "actions": [],
            "final_status": PipelineStage.RECEIVED
        }

        try:
            logger.info(f"Processing alert {alert_id}")

            # Stage 1: ML Detection
            ml_result = await self._ml_detection_stage(alert)
            pipeline_result["stages"]["ml_detection"] = ml_result
            pipeline_result["final_status"] = PipelineStage.ML_DETECTION

            # Stage 2: LLM Triage
            triage_result = await self._triage_stage(alert, ml_result)
            pipeline_result["stages"]["triage"] = triage_result
            pipeline_result["final_status"] = PipelineStage.TRIAGE_ANALYSIS

            # Record severity
            severity = triage_result.get("severity", "medium")
            self.metrics.record_severity(severity)

            # Stage 3: Context Enrichment (if enabled)
            if self.enable_rag:
                rag_result = await self._enrichment_stage(alert, triage_result)
                pipeline_result["stages"]["enrichment"] = rag_result
                pipeline_result["final_status"] = PipelineStage.CONTEXT_ENRICHMENT

            # Stage 4: Case Creation (if severity meets threshold)
            if self._should_create_case(triage_result):
                case_result = await self._case_creation_stage(
                    alert, triage_result, pipeline_result.get("stages", {}).get("enrichment")
                )
                pipeline_result["stages"]["case_creation"] = case_result
                pipeline_result["actions"].append("case_created")
                pipeline_result["final_status"] = PipelineStage.CASE_CREATION

            # Stage 5: Response Actions (for critical/high alerts)
            if severity in ["critical", "high"]:
                response_result = await self._response_stage(alert, triage_result)
                pipeline_result["stages"]["response"] = response_result
                pipeline_result["actions"].append("response_triggered")
                pipeline_result["final_status"] = PipelineStage.RESPONSE_ACTION

            # Mark as completed
            pipeline_result["final_status"] = PipelineStage.COMPLETED
            self.metrics.total_processed += 1

            # Calculate total processing time
            duration = (datetime.now() - start_time).total_seconds() * 1000
            pipeline_result["processing_time_ms"] = duration

            logger.info(
                f"Alert {alert_id} processed successfully in {duration:.2f}ms - "
                f"Severity: {severity}, Actions: {pipeline_result['actions']}"
            )

            # Publish completion event
            await event_bus.publish("alert_processed", pipeline_result)

            return pipeline_result

        except Exception as e:
            logger.error(f"Pipeline failed for alert {alert_id}: {e}", exc_info=True)
            pipeline_result["final_status"] = PipelineStage.FAILED
            pipeline_result["error"] = str(e)
            self.metrics.total_failed += 1
            return pipeline_result

    async def _ml_detection_stage(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stage 1: ML-based attack detection.

        Extracts network flow features and predicts attack/benign.
        """
        stage_start = datetime.now()

        try:
            # Extract features from alert
            features = self._extract_features(alert)

            if not features or not self.enable_ml:
                logger.warning("ML detection skipped (no features or disabled)")
                return {"skipped": True, "reason": "no_features_or_disabled"}

            # Call ML inference API
            ml_result = await self.ml_client.predict(
                features=features,
                model_name="random_forest"
            )

            duration = (datetime.now() - stage_start).total_seconds() * 1000
            self.metrics.record_stage_time("ml_detection", duration)

            return {
                "prediction": ml_result.get("prediction"),
                "confidence": ml_result.get("confidence"),
                "model": ml_result.get("model_used"),
                "duration_ms": duration
            }

        except Exception as e:
            logger.warning(f"ML detection failed, using fallback: {e}")
            return await FallbackHandler.ml_fallback(alert)

    async def _triage_stage(
        self,
        alert: Dict[str, Any],
        ml_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stage 2: LLM-powered alert triage.

        Analyzes alert context, extracts IOCs, assigns severity.
        """
        stage_start = datetime.now()

        try:
            # Enrich alert with ML prediction
            enriched_alert = {
                **alert,
                "ml_prediction": ml_result.get("prediction"),
                "ml_confidence": ml_result.get("confidence")
            }

            # Call Alert Triage service
            triage_result = await self.triage_client.analyze_alert(enriched_alert)

            duration = (datetime.now() - stage_start).total_seconds() * 1000
            self.metrics.record_stage_time("triage", duration)

            return {
                "severity": triage_result.get("severity"),
                "confidence": triage_result.get("confidence"),
                "iocs": triage_result.get("iocs", []),
                "recommendations": triage_result.get("recommendations", []),
                "mitre_tactics": triage_result.get("mitre_tactics", []),
                "duration_ms": duration
            }

        except Exception as e:
            logger.warning(f"Triage failed, using fallback: {e}")
            return await FallbackHandler.llm_fallback(alert)

    async def _enrichment_stage(
        self,
        alert: Dict[str, Any],
        triage_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stage 3: Context enrichment via RAG.

        Retrieves relevant knowledge from MITRE ATT&CK and incident history.
        """
        stage_start = datetime.now()

        try:
            # Build query from alert and triage results
            query = self._build_rag_query(alert, triage_result)

            # Retrieve context
            rag_result = await self.rag_client.retrieve(
                query=query,
                collection="mitre_attack",
                top_k=3
            )

            duration = (datetime.now() - stage_start).total_seconds() * 1000
            self.metrics.record_stage_time("enrichment", duration)

            return {
                "context_documents": rag_result.get("results", []),
                "query": query,
                "duration_ms": duration
            }

        except Exception as e:
            logger.warning(f"RAG enrichment failed: {e}")
            return {"error": str(e), "context_documents": []}

    async def _case_creation_stage(
        self,
        alert: Dict[str, Any],
        triage_result: Dict[str, Any],
        enrichment_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Stage 4: Create case in TheHive.

        For high-severity alerts, automatically create investigation case.
        """
        stage_start = datetime.now()

        try:
            # Build TheHive case
            case_data = self._build_thehive_case(alert, triage_result, enrichment_result)

            # Create case
            case_result = await self.thehive_client.create_case(case_data)

            duration = (datetime.now() - stage_start).total_seconds() * 1000
            self.metrics.record_stage_time("case_creation", duration)

            case_id = case_result.get("id", case_result.get("_id"))

            logger.info(f"Created TheHive case: {case_id}")

            return {
                "case_id": case_id,
                "case_url": f"{self.thehive_client.base_url}/case/{case_id}",
                "duration_ms": duration
            }

        except Exception as e:
            logger.error(f"Case creation failed: {e}")
            return {"error": str(e), "case_id": None}

    async def _response_stage(
        self,
        alert: Dict[str, Any],
        triage_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stage 5: Trigger automated response actions.

        For critical alerts, trigger Shuffle workflows (isolation, blocking, etc.)
        """
        stage_start = datetime.now()

        try:
            # TODO: Implement Shuffle webhook integration
            # For now, just log the action
            severity = triage_result.get("severity")
            actions_triggered = []

            if severity == "critical":
                actions_triggered = [
                    "isolate_host",
                    "block_ip",
                    "notify_security_team"
                ]
            elif severity == "high":
                actions_triggered = [
                    "monitor_host",
                    "alert_analyst"
                ]

            logger.info(
                f"Response actions triggered for alert {alert.get('id')}: {actions_triggered}"
            )

            duration = (datetime.now() - stage_start).total_seconds() * 1000
            self.metrics.record_stage_time("response", duration)

            return {
                "actions": actions_triggered,
                "duration_ms": duration,
                "note": "Shuffle integration pending"
            }

        except Exception as e:
            logger.error(f"Response action failed: {e}")
            return {"error": str(e), "actions": []}

    def _extract_features(self, alert: Dict[str, Any]) -> Optional[List[float]]:
        """
        Extract ML features from alert.

        TODO: Implement proper feature extraction from network flow data.
        For now, returns None to skip ML stage if features not present.
        """
        # Check if alert already has features
        if "features" in alert:
            return alert["features"]

        # Check if we can extract from flow data
        if "flow" in alert:
            # TODO: Extract 78 features from flow data
            pass

        return None

    def _build_rag_query(
        self,
        alert: Dict[str, Any],
        triage_result: Dict[str, Any]
    ) -> str:
        """Build semantic query for RAG retrieval"""
        alert_type = alert.get("rule", {}).get("description", "")
        tactics = triage_result.get("mitre_tactics", [])

        query_parts = [alert_type]
        if tactics:
            query_parts.append(f"MITRE tactics: {', '.join(tactics)}")

        return " ".join(query_parts)

    def _build_thehive_case(
        self,
        alert: Dict[str, Any],
        triage_result: Dict[str, Any],
        enrichment_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build TheHive case structure"""
        severity = triage_result.get("severity", "medium")

        # Map severity to TheHive severity (1-4)
        severity_map = {
            "info": 1,
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4
        }

        description_parts = [
            f"**Alert ID:** {alert.get('id')}",
            f"**Source:** {alert.get('agent', {}).get('name', 'Unknown')}",
            f"**ML Prediction:** {alert.get('ml_prediction', 'N/A')}",
            f"**Confidence:** {triage_result.get('confidence', 'N/A')}",
            "",
            "**Analysis:**",
            triage_result.get("analysis", "No analysis available"),
            "",
            "**Recommendations:**",
            "\n".join(f"- {rec}" for rec in triage_result.get("recommendations", []))
        ]

        if enrichment_result and enrichment_result.get("context_documents"):
            description_parts.extend([
                "",
                "**Related Context:**",
                "\n".join(
                    f"- {doc.get('document', '')[:200]}"
                    for doc in enrichment_result["context_documents"][:2]
                )
            ])

        return {
            "title": alert.get("rule", {}).get("description", "Security Alert"),
            "description": "\n".join(description_parts),
            "severity": severity_map.get(severity, 2),
            "tags": ["automated", "ai-soc", severity],
            "tlp": 2,  # TLP:AMBER
            "pap": 2,  # PAP:AMBER
            "customFields": {
                "alertId": alert.get("id"),
                "mlConfidence": triage_result.get("confidence"),
                "mitreTactics": triage_result.get("mitre_tactics", [])
            }
        }

    def _should_create_case(self, triage_result: Dict[str, Any]) -> bool:
        """Determine if case should be created based on severity"""
        severity = triage_result.get("severity", "medium")
        threshold_order = ["info", "low", "medium", "high", "critical"]

        threshold_idx = threshold_order.index(self.thehive_threshold)
        severity_idx = threshold_order.index(severity)

        return severity_idx >= threshold_idx

    async def batch_process(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process multiple alerts concurrently.

        Args:
            alerts: List of alerts to process

        Returns:
            List of pipeline results
        """
        logger.info(f"Batch processing {len(alerts)} alerts")

        # Process alerts concurrently with limit
        sem = asyncio.Semaphore(10)  # Max 10 concurrent

        async def process_with_limit(alert):
            async with sem:
                return await self.process_alert(alert)

        tasks = [process_with_limit(alert) for alert in alerts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Alert {i} failed: {result}")
                processed_results.append({
                    "alert_id": alerts[i].get("id", "unknown"),
                    "error": str(result),
                    "final_status": PipelineStage.FAILED
                })
            else:
                processed_results.append(result)

        logger.info(f"Batch processing complete: {len(processed_results)} results")
        return processed_results

    def get_metrics(self) -> Dict[str, Any]:
        """Get pipeline performance metrics"""
        return self.metrics.get_stats()


# ============================================================================
# Pipeline Manager
# ============================================================================

class PipelineManager:
    """
    Global pipeline manager for handling continuous alert stream.
    """

    def __init__(self):
        self.pipeline = AlertPipeline()
        self.running = False
        self.worker_task = None

    async def start(self):
        """Start pipeline worker"""
        if self.running:
            logger.warning("Pipeline already running")
            return

        self.running = True
        self.worker_task = asyncio.create_task(self._worker())
        logger.info("Pipeline manager started")

    async def stop(self):
        """Stop pipeline worker"""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Pipeline manager stopped")

    async def _worker(self):
        """Background worker for processing alert queue"""
        while self.running:
            try:
                # Get alert from queue (with timeout)
                alert = await asyncio.wait_for(
                    self.pipeline.processing_queue.get(),
                    timeout=1.0
                )

                # Process alert
                await self.pipeline.process_alert(alert)

            except asyncio.TimeoutError:
                # No alerts in queue, continue
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)

    async def enqueue_alert(self, alert: Dict[str, Any]):
        """Add alert to processing queue"""
        await self.pipeline.processing_queue.put(alert)

    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.pipeline.processing_queue.qsize()

    def get_metrics(self) -> Dict[str, Any]:
        """Get pipeline metrics"""
        return self.pipeline.get_metrics()


# Global pipeline manager instance
pipeline_manager = PipelineManager()
