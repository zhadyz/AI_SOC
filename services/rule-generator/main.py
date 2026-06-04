"""
LLM Rule Generator - FastAPI Application
AI-Augmented SOC

Phase 8: The system writes its own detection rules.

Analyzes uncategorized or novel attacks, uses the LLM to generate
Sigma detection rules, back-tests against historical alert data,
calculates false positive rates, and queues rules for analyst approval.
"""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from prometheus_client import Counter, generate_latest
from starlette.responses import Response

logging.basicConfig(
    level="INFO",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Config (compose sets RULE_GENERATOR_*; OLLAMA_* used when synced from .env)
OLLAMA_HOST = os.getenv(
    "RULE_GENERATOR_OLLAMA_HOST",
    os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
)
OLLAMA_MODEL = os.getenv(
    "RULE_GENERATOR_OLLAMA_MODEL",
    os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
)
FEEDBACK_SERVICE_URL = "http://feedback-service:8000"

# In-memory rule store (would be PostgreSQL in production)
rules_store: Dict[str, Dict[str, Any]] = {}

RULES_GENERATED = Counter("rules_generated_total", "Total rules generated")


# --- Models ---

class RuleGenerationRequest(BaseModel):
    alert_id: str = Field(..., description="Alert that triggered rule generation")
    alert_description: str = Field(..., description="Description of the attack pattern")
    raw_log: Optional[str] = Field(None, description="Raw log sample")
    source_ip: Optional[str] = None
    dest_ip: Optional[str] = None
    dest_port: Optional[int] = None
    mitre_techniques: List[str] = Field(default_factory=list)
    severity: str = "high"


class GeneratedRule(BaseModel):
    rule_id: str
    title: str
    rule_text: str
    rule_format: str = "sigma"
    source_alert_id: str
    mitre_techniques: List[str] = []
    severity: str = "high"
    false_positive_rate: Optional[float] = None
    tested_against: int = 0
    status: str = "pending"  # pending, approved, rejected, testing
    created_at: str
    analyst_notes: Optional[str] = None


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Rule Generator Service")
    yield
    logger.info("Shutting down Rule Generator Service")


app = FastAPI(
    title="LLM Rule Generator",
    description="AI-generated Sigma detection rules from novel attack patterns",
    version="1.0.0",
    lifespan=lifespan,
)


# --- LLM Rule Generation ---

SIGMA_PROMPT = """You are a detection engineering expert. Generate a Sigma detection rule for the following attack pattern.

The rule must be in valid Sigma YAML format. Include:
- title: A descriptive title
- status: experimental
- description: What the rule detects
- logsource: category, product, service
- detection: selection criteria with field names and values
- condition: How selections combine
- falsepositives: Known false positive scenarios
- level: {severity}
- tags: MITRE ATT&CK technique IDs

Attack Pattern:
{description}

{raw_log_section}

{network_section}

MITRE Techniques: {mitre}

Generate ONLY the Sigma YAML rule. No explanation, no markdown fencing. Just the raw YAML."""


async def generate_sigma_rule(request: RuleGenerationRequest) -> Optional[str]:
    """Use the LLM to generate a Sigma detection rule."""
    raw_log_section = f"Raw Log Sample:\n{request.raw_log}" if request.raw_log else ""
    network_section = ""
    if request.source_ip or request.dest_ip:
        parts = []
        if request.source_ip:
            parts.append(f"Source IP: {request.source_ip}")
        if request.dest_ip:
            parts.append(f"Destination IP: {request.dest_ip}")
        if request.dest_port:
            parts.append(f"Destination Port: {request.dest_port}")
        network_section = "Network Context:\n" + "\n".join(parts)

    prompt = SIGMA_PROMPT.format(
        severity=request.severity,
        description=request.alert_description,
        raw_log_section=raw_log_section,
        network_section=network_section,
        mitre=", ".join(request.mitre_techniques) if request.mitre_techniques else "Unknown",
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 1024},
                },
            )
            if response.status_code == 200:
                result = response.json()
                rule_text = result.get("response", "").strip()
                # Clean up markdown fencing if present
                if rule_text.startswith("```"):
                    lines = rule_text.split("\n")
                    rule_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                return rule_text
            else:
                logger.error(f"Ollama returned {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"LLM rule generation failed: {e}")
        return None


async def backtest_rule(rule_text: str) -> Dict[str, Any]:
    """
    Back-test a generated rule against historical alert data.
    Queries the feedback service for recent alerts and checks if the rule
    would have matched.
    """
    matches = 0
    false_positives = 0
    total_tested = 0

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{FEEDBACK_SERVICE_URL}/alerts",
                params={"limit": 100},
            )
            if response.status_code == 200:
                data = response.json()
                alerts = data.get("alerts", [])
                total_tested = len(alerts)

                # Simple keyword matching against rule detection fields
                # In production, this would parse the Sigma rule and match fields
                for alert in alerts:
                    desc = (alert.get("rule_description") or "").lower()
                    rule_lower = rule_text.lower()

                    # Check if rule keywords appear in alert
                    if any(
                        keyword in desc
                        for keyword in _extract_rule_keywords(rule_lower)
                    ):
                        matches += 1
                        # If the alert was marked as false positive, count it
                        if alert.get("feedback_count", 0) > 0:
                            false_positives += 1

    except Exception as e:
        logger.warning(f"Backtest failed: {e}")

    fp_rate = false_positives / matches if matches > 0 else 0.0

    return {
        "total_tested": total_tested,
        "matches": matches,
        "false_positives": false_positives,
        "false_positive_rate": round(fp_rate, 4),
    }


def _extract_rule_keywords(rule_text: str) -> List[str]:
    """Extract detection keywords from a Sigma rule for basic matching."""
    keywords = []
    in_detection = False
    for line in rule_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("detection:"):
            in_detection = True
            continue
        if in_detection:
            if stripped and not stripped.startswith("#"):
                # Extract values from key: value pairs
                if ":" in stripped:
                    value = stripped.split(":", 1)[1].strip().strip("'\"")
                    if value and len(value) > 3:
                        keywords.append(value.lower())
            if stripped and not stripped.startswith(" ") and not stripped.startswith("-"):
                if not stripped.startswith("selection") and not stripped.startswith("condition"):
                    in_detection = False
    return keywords[:10]  # Limit to 10 keywords


# --- Endpoints ---

@app.post("/generate")
async def generate_rule(request: RuleGenerationRequest):
    """
    Generate a Sigma detection rule from an attack pattern using the LLM.
    Back-tests against historical data and queues for analyst approval.
    """
    start = time.time()

    # Generate rule via LLM
    rule_text = await generate_sigma_rule(request)
    if not rule_text:
        raise HTTPException(status_code=503, detail="LLM rule generation failed")

    # Extract title from rule
    title = "Generated Detection Rule"
    for line in rule_text.split("\n"):
        if line.strip().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            break

    # Back-test against historical alerts
    backtest = await backtest_rule(rule_text)

    # Store rule
    rule_id = f"RULE-{uuid.uuid4().hex[:8]}"
    rule = GeneratedRule(
        rule_id=rule_id,
        title=title,
        rule_text=rule_text,
        rule_format="sigma",
        source_alert_id=request.alert_id,
        mitre_techniques=request.mitre_techniques,
        severity=request.severity,
        false_positive_rate=backtest["false_positive_rate"],
        tested_against=backtest["total_tested"],
        status="pending",
        created_at=datetime.utcnow().isoformat(),
    )

    rules_store[rule_id] = rule.model_dump()
    RULES_GENERATED.inc()

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        f"Generated rule {rule_id}: {title} "
        f"(FP rate={backtest['false_positive_rate']:.2%}, {elapsed}ms)"
    )

    return {
        "rule": rule.model_dump(),
        "backtest": backtest,
        "processing_time_ms": elapsed,
    }


@app.get("/rules")
async def list_rules(
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """List all generated rules, optionally filtered by status."""
    rules = list(rules_store.values())
    if status:
        rules = [r for r in rules if r.get("status") == status]
    return {"total": len(rules), "rules": rules}


@app.get("/rules/pending")
async def pending_rules():
    """Get rules pending analyst approval."""
    pending = [r for r in rules_store.values() if r.get("status") == "pending"]
    return {"total": len(pending), "rules": pending}


@app.put("/rules/{rule_id}/approve")
async def approve_rule(rule_id: str, notes: Optional[str] = None):
    """Approve a generated rule for deployment."""
    if rule_id not in rules_store:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    rules_store[rule_id]["status"] = "approved"
    rules_store[rule_id]["analyst_notes"] = notes
    logger.info(f"Rule {rule_id} approved")
    return rules_store[rule_id]


@app.put("/rules/{rule_id}/reject")
async def reject_rule(rule_id: str, notes: Optional[str] = None):
    """Reject a generated rule."""
    if rule_id not in rules_store:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    rules_store[rule_id]["status"] = "rejected"
    rules_store[rule_id]["analyst_notes"] = notes
    logger.info(f"Rule {rule_id} rejected")
    return rules_store[rule_id]


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "rule-generator",
        "version": "1.0.0",
        "rules_count": len(rules_store),
        "pending_count": sum(1 for r in rules_store.values() if r.get("status") == "pending"),
    }


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


@app.get("/")
async def root():
    return {
        "service": "rule-generator",
        "version": "1.0.0",
        "description": "AI-generated Sigma detection rules from novel attack patterns",
        "endpoints": {
            "generate": "POST /generate",
            "list_rules": "GET /rules",
            "pending": "GET /rules/pending",
            "approve": "PUT /rules/{rule_id}/approve",
            "reject": "PUT /rules/{rule_id}/reject",
            "health": "GET /health",
        },
    }
