"""
Log Summarization Service - FastAPI Application
AI-Augmented SOC

Batch processes security logs from OpenSearch and generates LLM-powered summaries.
Stores summaries in ChromaDB for RAG retrieval.

Author: HOLLOWED_EYES
Mission: Phase 3 AI Service Integration
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List
from datetime import datetime
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from config import settings
from summarizer import LogSummarizer
from opensearch_client import OpenSearchClient
from chromadb_client import ChromaDBClient
from parser import LogParser

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
log_parser: LogParser = None
summarizer: LogSummarizer = None
opensearch_client: OpenSearchClient = None
chromadb_client: ChromaDBClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    global log_parser, summarizer, opensearch_client, chromadb_client

    logger.info(f"Starting {settings.service_name} v{settings.service_version}")

    # Initialize components
    log_parser = LogParser()
    summarizer = LogSummarizer(
        ollama_host=settings.ollama_host,
        model=settings.primary_model,
        chunk_size=settings.summary_chunk_size
    )
    opensearch_client = OpenSearchClient()
    chromadb_client = ChromaDBClient()

    # Check connectivity
    if not await summarizer.check_health():
        logger.warning("Ollama not reachable at startup")

    if not await opensearch_client.check_health():
        logger.warning("OpenSearch not reachable at startup")

    if not await chromadb_client.check_health():
        logger.warning("ChromaDB not reachable at startup")

    yield

    logger.info("Shutting down Log Summarization Service")


app = FastAPI(
    title="Log Summarization Service",
    description="LLM-powered batch log summarization for security operations",
    version=settings.service_version,
    lifespan=lifespan
)


class SummarizeRequest(BaseModel):
    """Request model for log summarization"""
    time_range_hours: int = Field(
        settings.default_time_range_hours,
        ge=1,
        le=settings.max_time_range_hours,
        description="Hours to summarize"
    )
    log_source: str = Field("wazuh", description="Log source (wazuh, suricata, zeek, all)")
    max_logs: int = Field(
        settings.batch_size,
        ge=100,
        le=settings.max_logs_per_summary,
        description="Max logs to process"
    )


class SummaryResponse(BaseModel):
    """Response model for log summary"""
    summary_id: str
    time_range: str
    log_count: int
    executive_summary: str
    key_events: List[str]
    threat_indicators: List[str]
    recommendations: List[str]
    statistics: Dict[str, Any]
    mitre_techniques: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_used: str
    stored_in_chromadb: bool = False


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    ollama_connected = await summarizer.check_health()
    opensearch_connected = await opensearch_client.check_health()
    chromadb_connected = await chromadb_client.check_health()

    status = "healthy"
    if not ollama_connected or not opensearch_connected:
        status = "degraded"

    return {
        "status": status,
        "service": settings.service_name,
        "version": settings.service_version,
        "timestamp": datetime.utcnow(),
        "ollama_connected": ollama_connected,
        "opensearch_connected": opensearch_connected,
        "chromadb_connected": chromadb_connected
    }


@app.post("/summarize", response_model=SummaryResponse)
async def summarize_logs(request: SummarizeRequest, background_tasks: BackgroundTasks):
    """
    Generate summary of security logs from specified time range.

    **Workflow:**
    1. Query OpenSearch for logs in time range
    2. Parse and normalize logs
    3. Batch process through LLM (LLaMA 3.1 8B)
    4. Generate structured summary
    5. Store in ChromaDB for RAG retrieval (background task)

    **Args:**
        request: Summarization parameters

    **Returns:**
        SummaryResponse: Generated summary
    """
    try:
        logger.info(
            f"Summarization request: time_range={request.time_range_hours}h, "
            f"source={request.log_source}, max_logs={request.max_logs}"
        )

        # Step 1: Fetch logs from OpenSearch
        log_source = None if request.log_source == "all" else request.log_source
        logs = await opensearch_client.fetch_logs(
            time_range_hours=request.time_range_hours,
            log_source=log_source,
            max_logs=request.max_logs
        )

        if not logs:
            logger.warning("No logs found for summarization")
            raise HTTPException(
                status_code=404,
                detail="No logs found in specified time range"
            )

        if len(logs) < settings.min_logs_for_summary:
            logger.warning(f"Insufficient logs for summary: {len(logs)}")
            raise HTTPException(
                status_code=400,
                detail=f"Minimum {settings.min_logs_for_summary} logs required"
            )

        # Step 2: Parse logs (LibreLog would go here in production)
        parsed_logs = log_parser.parse_batch(logs)

        # Step 3: Generate summary with LLM
        time_range_desc = f"{request.time_range_hours} hours"
        summary = await summarizer.generate_summary(parsed_logs, time_range_desc)

        if not summary:
            raise HTTPException(
                status_code=500,
                detail="Summary generation failed"
            )

        # Step 4: Build response
        summary_id = f"summary-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"

        response = SummaryResponse(
            summary_id=summary_id,
            time_range=time_range_desc,
            log_count=len(logs),
            executive_summary=summary.get("executive_summary", ""),
            key_events=summary.get("key_events", []),
            threat_indicators=summary.get("threat_indicators", []),
            recommendations=summary.get("recommendations", []),
            statistics=summary.get("statistics", {}),
            mitre_techniques=summary.get("mitre_techniques", []),
            generated_at=datetime.utcnow(),
            model_used=summary.get("model_used", settings.primary_model)
        )

        # Step 5: Store in ChromaDB (background task)
        background_tasks.add_task(
            store_summary_background,
            summary_id,
            summary,
            request.time_range_hours,
            len(logs)
        )

        logger.info(f"Summary generated: {summary_id} ({len(logs)} logs)")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summarization failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def store_summary_background(
    summary_id: str,
    summary: Dict[str, Any],
    time_range_hours: int,
    log_count: int
):
    """Background task to store summary in ChromaDB"""
    try:
        summary_text = f"{summary.get('executive_summary', '')}\n\n"
        summary_text += "Key Events:\n" + "\n".join(summary.get('key_events', []))

        metadata = {
            "summary_id": summary_id,
            "time_range_hours": time_range_hours,
            "log_count": log_count,
            "generated_at": summary.get("generated_at", datetime.utcnow().isoformat()),
            "model_used": summary.get("model_used", ""),
            "mitre_techniques": ",".join(summary.get("mitre_techniques", []))
        }

        await chromadb_client.store_summary(
            summary_id=summary_id,
            summary_text=summary_text,
            metadata=metadata
        )

        logger.info(f"Summary {summary_id} stored in ChromaDB")

    except Exception as e:
        logger.error(f"Failed to store summary in ChromaDB: {e}")


@app.post("/summarize/daily")
async def daily_summary(background_tasks: BackgroundTasks):
    """
    Generate daily security summary (automated task).

    This endpoint should be called by a scheduler (cron) daily.
    """
    if not settings.daily_summary_enabled:
        return {
            "status": "disabled",
            "message": "Daily summaries are disabled in configuration"
        }

    logger.info("Daily summary generation triggered")

    try:
        # Generate summary for last 24 hours
        request = SummarizeRequest(
            time_range_hours=24,
            log_source="all",
            max_logs=settings.max_logs_per_summary
        )

        summary = await summarize_logs(request, background_tasks)

        return {
            "status": "success",
            "summary_id": summary.summary_id,
            "log_count": summary.log_count,
            "message": "Daily summary generated successfully"
        }

    except Exception as e:
        logger.error(f"Daily summary generation failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }


@app.get("/summaries")
async def list_summaries(limit: int = 10):
    """List recent summaries from ChromaDB"""
    try:
        summaries = await chromadb_client.get_recent_summaries(limit=limit)

        return {
            "summaries": summaries,
            "count": len(summaries),
            "timestamp": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Failed to list summaries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/summaries/search")
async def search_summaries(query: str, top_k: int = 5):
    """Search summaries using semantic search"""
    try:
        results = await chromadb_client.search_similar_summaries(
            query_text=query,
            top_k=top_k
        )

        return {
            "query": query,
            "results": results,
            "count": len(results),
            "timestamp": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Summary search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "operational",
        "endpoints": {
            "summarize": "/summarize",
            "daily": "/summarize/daily",
            "search": "/summaries/search",
            "history": "/summaries",
            "health": "/health",
            "docs": "/docs"
        },
        "configuration": {
            "default_time_range": f"{settings.default_time_range_hours}h",
            "max_time_range": f"{settings.max_time_range_hours}h",
            "batch_size": settings.batch_size,
            "model": settings.primary_model
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level=settings.log_level.lower()
    )
