"""
Ollama LLM Client - Alert Triage Service
AI-Augmented SOC

Handles communication with Ollama API for security alert analysis.
Includes prompt engineering, fallback logic, and structured output parsing.
"""

import json
import logging
from typing import Optional, Dict, Any
import httpx
from config import settings
from models import SecurityAlert, TriageResponse, SeverityLevel, AlertCategory, IOC, TriageRecommendation
from ml_client import MLInferenceClient, MLPrediction, enrich_llm_prompt_with_ml

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Client for interacting with Ollama LLM API.

    Implements:
    - Security-focused prompt engineering
    - Structured JSON output
    - Model fallback logic
    - Error handling and retries
    """

    def __init__(self):
        self.base_url = settings.ollama_host
        self.primary_model = settings.primary_model
        self.fallback_model = settings.fallback_model
        self.timeout = settings.llm_timeout

        # Initialize ML inference client
        self.ml_client = MLInferenceClient(
            ml_api_url=settings.ml_api_url,
            timeout=settings.ml_timeout,
            enabled=settings.ml_enabled
        )

    async def check_health(self) -> bool:
        """
        Check if Ollama service is reachable.

        Returns:
            bool: True if Ollama is available
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    def _build_triage_prompt(self, alert: SecurityAlert) -> str:
        """
        Construct security-focused prompt for alert triage.

        Uses structured prompting with clear instructions for JSON output.

        Args:
            alert: SecurityAlert object

        Returns:
            str: Formatted prompt for LLM
        """
        # TODO: Week 4 - Refine prompt based on evaluation results
        # TODO: Week 5 - Add RAG context injection here

        prompt = f"""You are an expert cybersecurity analyst performing alert triage for a Security Operations Center (SOC).

**TASK:** Analyze the following security alert and provide a structured assessment.

**ALERT DETAILS:**
- Alert ID: {alert.alert_id}
- Rule: {alert.rule_description} (Level {alert.rule_level})
- Timestamp: {alert.timestamp}
- Source IP: {alert.source_ip or 'N/A'}
- Destination IP: {alert.dest_ip or 'N/A'}
- User: {alert.user or 'N/A'}
- Process: {alert.process or 'N/A'}
- Raw Log: {alert.raw_log or 'N/A'}

**YOUR ANALYSIS MUST INCLUDE:**
1. **Severity Assessment:** Classify as critical/high/medium/low/informational
2. **Category:** Identify attack category (malware, intrusion, exfiltration, etc)
3. **True/False Positive:** Determine if this is a genuine threat
4. **IOC Extraction:** Extract all Indicators of Compromise (IPs, domains, hashes, files)
5. **MITRE ATT&CK:** Map to relevant techniques and tactics
6. **Recommendations:** Provide 3-5 prioritized response actions

**CRITICAL RULES:**
- Base assessment ONLY on provided evidence
- If information is insufficient, state "INSUFFICIENT_DATA"
- Do NOT hallucinate IOCs or details not present in the log
- Provide confidence score (0.0-1.0) for your assessment
- Be concise but thorough

**OUTPUT FORMAT (JSON):**
{{
    "severity": "high",
    "category": "intrusion_attempt",
    "confidence": 0.92,
    "summary": "Brief 1-sentence summary",
    "detailed_analysis": "Technical analysis with evidence",
    "potential_impact": "Business/security impact",
    "is_true_positive": true,
    "false_positive_reason": null,
    "iocs": [
        {{"ioc_type": "ip", "value": "203.0.113.42", "confidence": 0.95}}
    ],
    "mitre_techniques": ["T1110.001"],
    "mitre_tactics": ["TA0006"],
    "recommendations": [
        {{
            "action": "Block source IP at firewall",
            "priority": 1,
            "rationale": "Prevent continued brute force attempts"
        }}
    ],
    "investigation_priority": 2,
    "estimated_analyst_time": 15
}}

Begin your analysis now:"""

        return prompt

    async def _call_ollama(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.1
    ) -> Optional[str]:
        """
        Make API call to Ollama.

        Args:
            prompt: Text prompt
            model: Model identifier
            temperature: Sampling temperature

        Returns:
            Optional[str]: Model response or None on error
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": settings.max_tokens,
                    },
                    "format": "json"  # Request JSON output
                }

                logger.info(f"Calling Ollama model: {model}")
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("response")
                else:
                    logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                    return None

        except httpx.TimeoutException:
            logger.error(f"Ollama request timeout after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            return None

    def _parse_llm_response(
        self,
        alert: SecurityAlert,
        llm_output: str,
        model_used: str
    ) -> Optional[TriageResponse]:
        """
        Parse LLM JSON output into TriageResponse model.

        Handles malformed JSON and missing fields gracefully.

        Args:
            alert: Original alert
            llm_output: Raw LLM response
            model_used: Model identifier

        Returns:
            Optional[TriageResponse]: Parsed response or None
        """
        try:
            # TODO: Week 4 - Add more robust JSON extraction (handle markdown code blocks)
            parsed = json.loads(llm_output)

            # Map parsed data to Pydantic model
            response = TriageResponse(
                alert_id=alert.alert_id,
                severity=SeverityLevel(parsed.get("severity", "medium")),
                category=AlertCategory(parsed.get("category", "other")),
                confidence=float(parsed.get("confidence", 0.5)),
                summary=parsed.get("summary", "No summary provided"),
                detailed_analysis=parsed.get("detailed_analysis", ""),
                potential_impact=parsed.get("potential_impact", ""),
                is_true_positive=parsed.get("is_true_positive", True),
                false_positive_reason=parsed.get("false_positive_reason"),
                iocs=[IOC(**ioc) for ioc in parsed.get("iocs", [])],
                mitre_techniques=parsed.get("mitre_techniques", []),
                mitre_tactics=parsed.get("mitre_tactics", []),
                recommendations=[
                    TriageRecommendation(**rec)
                    for rec in parsed.get("recommendations", [])
                ],
                investigation_priority=int(parsed.get("investigation_priority", 3)),
                estimated_analyst_time=parsed.get("estimated_analyst_time"),
                model_used=model_used
            )

            return response

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON output: {e}")
            logger.debug(f"Raw output: {llm_output[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error constructing TriageResponse: {e}")
            return None

    async def analyze_alert(self, alert: SecurityAlert) -> Optional[TriageResponse]:
        """
        Main entrypoint: Analyze security alert using LLM with ML enhancement.

        Workflow:
        1. Attempt ML prediction for additional context
        2. Enhance LLM prompt with ML results
        3. Try primary model (Foundation-Sec-8B)
        4. Fall back to secondary model (LLaMA 3.1) if primary fails
        5. Return None if both fail

        Args:
            alert: SecurityAlert to analyze

        Returns:
            Optional[TriageResponse]: Analysis result or None
        """
        # Step 1: Get ML prediction (if available)
        ml_prediction = None
        if settings.ml_enabled:
            logger.debug("Attempting ML prediction...")
            ml_prediction = await self.ml_client.predict_with_fallback(alert)
            if ml_prediction:
                logger.info(
                    f"ML prediction: {ml_prediction.prediction} "
                    f"(confidence={ml_prediction.confidence:.2f})"
                )

        # Step 2: Build prompt with ML enrichment
        base_prompt = self._build_triage_prompt(alert)
        enriched_prompt = enrich_llm_prompt_with_ml(base_prompt, ml_prediction)

        # Step 3: Try primary model
        logger.info(f"Analyzing alert {alert.alert_id} with {self.primary_model}")
        llm_output = await self._call_ollama(
            enriched_prompt,
            self.primary_model,
            settings.llm_temperature
        )

        if llm_output:
            response = self._parse_llm_response(alert, llm_output, self.primary_model)
            if response:
                # Add ML metadata to response
                if ml_prediction:
                    response.ml_prediction = ml_prediction.prediction
                    response.ml_confidence = ml_prediction.confidence
                logger.info(f"Alert {alert.alert_id} analyzed successfully")
                return response

        # Step 4: Fallback to secondary model
        logger.warning(f"Primary model failed, trying fallback: {self.fallback_model}")
        llm_output = await self._call_ollama(
            enriched_prompt,
            self.fallback_model,
            settings.llm_temperature
        )

        if llm_output:
            response = self._parse_llm_response(alert, llm_output, self.fallback_model)
            if response:
                # Add ML metadata to response
                if ml_prediction:
                    response.ml_prediction = ml_prediction.prediction
                    response.ml_confidence = ml_prediction.confidence
                logger.info(f"Alert {alert.alert_id} analyzed with fallback model")
                return response

        # Both models failed
        logger.error(f"Failed to analyze alert {alert.alert_id} with all models")
        return None


# TODO: Week 5 - Add RAG integration
# class RAGEnhancedClient(OllamaClient):
#     """Extended client with RAG capabilities"""
#     async def get_rag_context(self, alert: SecurityAlert) -> str:
#         """Query RAG service for relevant context"""
#         pass
