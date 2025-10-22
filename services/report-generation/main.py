"""
Report Generation Service - FastAPI Application
AI-Augmented SOC

Generates comprehensive incident reports from TheHive cases using AGIR-inspired methodology.
Includes MITRE ATT&CK mapping, timeline generation, and multi-format export.

Author: HOLLOWED_EYES
Mission: Phase 3 AI Service Integration
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import settings
from report_generator import ReportGenerator
from thehive_client import TheHiveClient
from mitre_mapper import MITREMapper
from export_manager import ExportManager

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
report_generator: ReportGenerator = None
thehive_client: TheHiveClient = None
mitre_mapper: MITREMapper = None
export_manager: ExportManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    global report_generator, thehive_client, mitre_mapper, export_manager

    logger.info(f"Starting {settings.service_name} v{settings.service_version}")

    # Initialize components
    report_generator = ReportGenerator(
        ollama_host=settings.ollama_host,
        model=settings.primary_model
    )
    thehive_client = TheHiveClient(
        api_url=settings.thehive_url,
        api_key=settings.thehive_api_key
    )
    mitre_mapper = MITREMapper()
    export_manager = ExportManager()

    # Check connectivity
    if not await report_generator.check_health():
        logger.warning("Ollama not reachable at startup")

    if not await thehive_client.check_health():
        logger.warning("TheHive not reachable at startup")

    yield

    logger.info("Shutting down Report Generation Service")


app = FastAPI(
    title="Report Generation Service",
    description="AI-powered incident report generation with MITRE ATT&CK mapping",
    version=settings.service_version,
    lifespan=lifespan
)


class ReportRequest(BaseModel):
    """Request model for report generation"""
    case_id: str = Field(..., description="TheHive case ID")
    include_timeline: bool = Field(True, description="Include event timeline")
    include_mitre: bool = Field(True, description="Include MITRE ATT&CK mapping")
    include_recommendations: bool = Field(True, description="Include response recommendations")
    format: str = Field("markdown", description="Output format: markdown, pdf, json")


class ReportResponse(BaseModel):
    """Response model for generated report"""
    report_id: str
    case_id: str
    case_title: str
    severity: str
    executive_summary: str
    incident_timeline: List[Dict[str, Any]] = Field(default_factory=list)
    mitre_techniques: List[Dict[str, Any]] = Field(default_factory=list)
    mitre_tactics: List[str] = Field(default_factory=list)
    indicators_of_compromise: List[Dict[str, Any]] = Field(default_factory=list)
    affected_systems: List[str] = Field(default_factory=list)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_used: str


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    ollama_connected = await report_generator.check_health()
    thehive_connected = await thehive_client.check_health()

    status = "healthy"
    if not ollama_connected or not thehive_connected:
        status = "degraded"

    return {
        "status": status,
        "service": settings.service_name,
        "version": settings.service_version,
        "timestamp": datetime.utcnow(),
        "ollama_connected": ollama_connected,
        "thehive_connected": thehive_connected
    }


@app.post("/generate", response_model=ReportResponse)
async def generate_report(request: ReportRequest):
    """
    Generate comprehensive incident report from TheHive case.

    **Workflow:**
    1. Fetch case data from TheHive
    2. Extract observables (IOCs) and tasks
    3. Map to MITRE ATT&CK techniques
    4. Generate timeline of events
    5. Use LLM to create narrative summary
    6. Compile structured report
    7. Export to requested format

    **Args:**
        request: Report generation parameters

    **Returns:**
        ReportResponse: Structured incident report
    """
    try:
        logger.info(f"Generating report for case: {request.case_id}")

        # Step 1: Fetch case from TheHive
        case_data = await thehive_client.get_case(request.case_id)

        if not case_data:
            raise HTTPException(
                status_code=404,
                detail=f"Case {request.case_id} not found in TheHive"
            )

        # Step 2: Fetch case observables and tasks
        observables = await thehive_client.get_case_observables(request.case_id)
        tasks = await thehive_client.get_case_tasks(request.case_id)

        # Step 3: Map to MITRE ATT&CK
        mitre_techniques = []
        mitre_tactics = []
        if request.include_mitre:
            mitre_techniques, mitre_tactics = await mitre_mapper.map_case_to_mitre(
                case_data,
                observables
            )

        # Step 4: Generate timeline
        timeline = []
        if request.include_timeline:
            timeline = await report_generator.generate_timeline(
                case_data,
                observables,
                tasks
            )

        # Step 5: Generate executive summary with LLM
        executive_summary = await report_generator.generate_executive_summary(
            case_data,
            observables,
            mitre_techniques
        )

        # Step 6: Generate recommendations
        recommendations = []
        if request.include_recommendations:
            recommendations = await report_generator.generate_recommendations(
                case_data,
                mitre_techniques,
                observables
            )

        # Step 7: Compile report
        report_id = f"report-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"

        response = ReportResponse(
            report_id=report_id,
            case_id=request.case_id,
            case_title=case_data.get('title', 'Unknown'),
            severity=case_data.get('severity', 'Medium'),
            executive_summary=executive_summary,
            incident_timeline=timeline,
            mitre_techniques=mitre_techniques,
            mitre_tactics=mitre_tactics,
            indicators_of_compromise=[
                {
                    "type": obs.get('dataType', 'unknown'),
                    "value": obs.get('data', ''),
                    "tags": obs.get('tags', [])
                }
                for obs in observables
            ],
            affected_systems=_extract_affected_systems(case_data, observables),
            recommendations=recommendations,
            generated_at=datetime.utcnow(),
            model_used=settings.primary_model
        )

        logger.info(f"Report generated: {report_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/export/{report_id}")
async def export_report(
    report_id: str,
    format: str = "markdown",
    case_id: Optional[str] = None
):
    """
    Export report in specified format.

    **Formats:**
    - markdown: Markdown document
    - pdf: PDF report (requires wkhtmltopdf)
    - json: JSON structure

    **Args:**
        report_id: Report identifier
        format: Output format
        case_id: Optional case ID to regenerate

    **Returns:**
        File download
    """
    try:
        # In production, retrieve from database or regenerate
        # For now, return placeholder

        if format == "markdown":
            content = "# Incident Report\n\nPlaceholder report content."
            media_type = "text/markdown"
            filename = f"{report_id}.md"
        elif format == "pdf":
            raise HTTPException(
                status_code=501,
                detail="PDF export not yet implemented"
            )
        elif format == "json":
            content = '{"report_id": "' + report_id + '"}'
            media_type = "application/json"
            filename = f"{report_id}.json"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {format}"
            )

        return StreamingResponse(
            iter([content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "operational",
        "endpoints": {
            "generate": "/generate",
            "export": "/export/{report_id}",
            "health": "/health",
            "docs": "/docs"
        },
        "supported_formats": ["markdown", "json", "pdf (planned)"],
        "features": {
            "timeline_generation": True,
            "mitre_mapping": True,
            "llm_summaries": True,
            "multi_format_export": "partial"
        }
    }


def _extract_affected_systems(
    case_data: Dict[str, Any],
    observables: List[Dict[str, Any]]
) -> List[str]:
    """Extract list of affected systems from case and observables"""
    systems = set()

    # Extract from case tags
    for tag in case_data.get('tags', []):
        if 'host:' in tag.lower() or 'system:' in tag.lower():
            systems.add(tag)

    # Extract from observables
    for obs in observables:
        if obs.get('dataType') == 'hostname':
            systems.add(obs.get('data', ''))
        elif obs.get('dataType') == 'ip':
            systems.add(f"IP: {obs.get('data', '')}")

    return list(systems)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level=settings.log_level.lower()
    )
