"""
LLM Summarizer - Log Summarization Service
AI-Augmented SOC

Generates human-readable summaries of security logs using LLMs.
Stores summaries in ChromaDB for RAG retrieval.

Author: HOLLOWED_EYES
Mission: Phase 3 AI Service Integration
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
import json

logger = logging.getLogger(__name__)


class LogSummarizer:
    """
    LLM-powered log summarization engine.

    Uses LLaMA 3.1 8B to generate:
    - Executive summaries (high-level overview)
    - Key security events
    - Threat indicators
    - Actionable recommendations
    """

    def __init__(
        self,
        ollama_host: str = "http://ollama:11434",
        model: str = "llama3.1:8b",
        chunk_size: int = 100
    ):
        """
        Initialize summarizer.

        Args:
            ollama_host: Ollama API endpoint
            model: LLM model to use
            chunk_size: Logs per summarization chunk
        """
        self.ollama_host = ollama_host
        self.model = model
        self.chunk_size = chunk_size
        logger.info(f"LogSummarizer initialized: model={model}, chunk_size={chunk_size}")

    async def check_health(self) -> bool:
        """Check if Ollama is accessible"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_host}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    def _build_summary_prompt(
        self,
        logs: List[Dict[str, Any]],
        time_range: str
    ) -> str:
        """
        Construct prompt for log summarization.

        Args:
            logs: Parsed log entries
            time_range: Time range description

        Returns:
            Formatted prompt for LLM
        """
        # Format logs for prompt (limit to 50 for token budget)
        log_entries = []
        for i, log in enumerate(logs[:50], 1):
            timestamp = log.get('@timestamp', 'N/A')
            rule = log.get('rule', {}).get('description', 'Unknown')
            level = log.get('rule', {}).get('level', 0)
            agent = log.get('agent', {}).get('name', 'N/A')
            srcip = log.get('data', {}).get('srcip', 'N/A')

            log_entries.append(
                f"{i}. [{timestamp}] Severity:{level} - {rule} | "
                f"Agent:{agent} | SrcIP:{srcip}"
            )

        logs_text = "\n".join(log_entries)
        if len(logs) > 50:
            logs_text += f"\n... and {len(logs) - 50} more logs"

        prompt = f"""You are an expert cybersecurity analyst reviewing security logs for a SOC team.

**TASK:** Analyze the following {len(logs)} security logs from the past {time_range} and generate a comprehensive summary.

**SECURITY LOGS:**
{logs_text}

**YOUR SUMMARY MUST INCLUDE:**

1. **Executive Summary** (2-3 sentences)
   - High-level overview of security posture
   - Most critical findings

2. **Key Security Events** (5-10 bullet points)
   - Notable incidents or patterns
   - Severity and frequency

3. **Threat Indicators** (IOCs and suspicious activity)
   - IP addresses of concern
   - Attack patterns detected
   - MITRE ATT&CK techniques observed

4. **Recommendations** (3-5 actionable items)
   - Prioritized response actions
   - Investigation priorities
   - Prevention measures

5. **Statistical Overview**
   - Total alerts analyzed
   - Severity distribution
   - Top alert types

**CRITICAL GUIDELINES:**
- Base analysis ONLY on provided logs
- Identify patterns and correlations
- Highlight high-severity events (level >= 10)
- Map to MITRE ATT&CK where applicable
- Be concise but thorough
- Use clear, non-technical language for executives

**OUTPUT FORMAT (JSON):**
{{
    "executive_summary": "Brief overview...",
    "key_events": [
        "Event 1 description",
        "Event 2 description"
    ],
    "threat_indicators": [
        "Suspicious activity from IP 203.0.113.42",
        "MITRE T1110: Brute Force detected"
    ],
    "recommendations": [
        "1. Block IP 203.0.113.42 at firewall",
        "2. Investigate authentication logs for user 'admin'"
    ],
    "statistics": {{
        "total_alerts": {len(logs)},
        "critical_alerts": 0,
        "high_alerts": 0,
        "medium_alerts": 0,
        "low_alerts": 0,
        "top_alert_types": []
    }},
    "mitre_techniques": ["T1110.001", "T1078"],
    "time_range": "{time_range}"
}}

Generate the summary now:"""

        return prompt

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """
        Call Ollama LLM for summarization.

        Args:
            prompt: Summarization prompt

        Returns:
            Optional[str]: LLM response or None
        """
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": 4096
                    },
                    "format": "json"
                }

                logger.debug(f"Calling Ollama for summarization: model={self.model}")
                response = await client.post(
                    f"{self.ollama_host}/api/generate",
                    json=payload
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("response")
                else:
                    logger.error(f"Ollama error: {response.status_code}")
                    return None

        except httpx.TimeoutException:
            logger.error("Ollama timeout during summarization")
            return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    async def generate_summary(
        self,
        logs: List[Dict[str, Any]],
        time_range: str = "24 hours"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate comprehensive summary of security logs.

        Args:
            logs: Parsed log entries
            time_range: Time range description

        Returns:
            Optional[Dict]: Structured summary or None
        """
        if not logs:
            logger.warning("No logs provided for summarization")
            return None

        try:
            # Build prompt
            prompt = self._build_summary_prompt(logs, time_range)

            # Call LLM
            llm_output = await self._call_llm(prompt)

            if not llm_output:
                logger.error("LLM summarization failed")
                return None

            # Parse JSON response
            summary = json.loads(llm_output)

            # Add metadata
            summary["generated_at"] = datetime.utcnow().isoformat()
            summary["model_used"] = self.model
            summary["total_logs_analyzed"] = len(logs)

            logger.info(f"Generated summary for {len(logs)} logs")
            return summary

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON output: {e}")
            return None
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return None

    async def batch_summarize(
        self,
        logs: List[Dict[str, Any]],
        time_range: str = "24 hours"
    ) -> Optional[Dict[str, Any]]:
        """
        Batch summarize large log volumes using chunking.

        For very large log sets, this splits them into chunks,
        summarizes each chunk, then aggregates the results.

        Args:
            logs: List of log entries
            time_range: Time range description

        Returns:
            Optional[Dict]: Aggregated summary or None
        """
        if len(logs) <= self.chunk_size:
            # Small enough to summarize directly
            return await self.generate_summary(logs, time_range)

        logger.info(f"Batch summarizing {len(logs)} logs in chunks of {self.chunk_size}")

        # For now, just use the first chunk_size logs
        # TODO: Implement hierarchical summarization
        return await self.generate_summary(logs[:self.chunk_size], time_range)

    def calculate_bert_score(self, generated: str, reference: str) -> float:
        """
        Calculate BERTScore for summary quality (future enhancement).

        BERTScore measures semantic similarity between:
        - Generated summary
        - Human-written reference summary

        Target: >0.85

        Args:
            generated: LLM-generated summary
            reference: Human reference summary

        Returns:
            BERTScore (0.0-1.0)
        """
        # TODO: Implement BERTScore evaluation
        # from bert_score import score
        # P, R, F1 = score([generated], [reference], lang="en")
        # return F1.mean().item()

        return 0.0
