"""
RAG Service - FastAPI Application
AI-Augmented SOC

Retrieval-Augmented Generation service for grounding LLM responses.
Provides semantic search over security knowledge base.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.rag_service.vector_store import VectorStore
from services.rag_service.embeddings import EmbeddingEngine
from services.rag_service.knowledge_base import KnowledgeBaseManager

# Default runbooks directory (relative to this file)
RUNBOOKS_DIR = str(Path(__file__).parent / "runbooks")

# Configure logging
logging.basicConfig(
    level="INFO",
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
vector_store: VectorStore = None
embedding_engine: EmbeddingEngine = None
kb_manager: KnowledgeBaseManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    global vector_store, embedding_engine, kb_manager

    logger.info("Starting RAG Service")

    try:
        # Initialize components
        embedding_engine = EmbeddingEngine()
        vector_store = VectorStore(embedding_engine, host=os.getenv("RAG_CHROMADB_HOST", "chromadb"),
                                   port=int(os.getenv("RAG_CHROMADB_PORT", "8000")))
        kb_manager = KnowledgeBaseManager(vector_store)

        # Initialize ChromaDB collections
        logger.info("Initializing ChromaDB collections...")
        collections = ['mitre_attack', 'cve_database', 'incident_history', 'security_runbooks']
        for collection in collections:
            vector_store.create_collection(collection)

        if os.getenv("RAG_INGEST_RUNBOOKS", "true").lower() == "true":
            ingestion = await kb_manager.ingest_security_runbooks(RUNBOOKS_DIR)
            if ingestion.get("status") == "error":
                raise RuntimeError("Runbook ingestion failed")
        logger.info("RAG Service initialization complete")

    except Exception as e:
        logger.error(f"Failed to initialize RAG Service: {e}")
        logger.exception(e)
        raise

    yield

    logger.info("Shutting down RAG Service")


app = FastAPI(
    title="RAG Service",
    description="Retrieval-Augmented Generation for security knowledge",
    version="1.0.0",
    lifespan=lifespan
)


class RetrievalRequest(BaseModel):
    """Request model for context retrieval"""
    query: str = Field(..., min_length=1, description="Search query")
    collection: str = Field("mitre_attack", description="Knowledge base collection")
    top_k: int = Field(3, ge=1, le=10, description="Number of results to return")
    min_similarity: float = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity threshold")


class RetrievalResult(BaseModel):
    """Individual retrieval result"""
    document: str
    metadata: Dict[str, Any]
    similarity_score: float


class RetrievalResponse(BaseModel):
    """Response model for context retrieval"""
    query: str
    results: List[RetrievalResult]
    total_results: int


from services.common.api_security import protect_app
protect_app(app)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if not vector_store or not vector_store.is_connected() or not embedding_engine.model:
        raise HTTPException(503, "RAG dependencies unavailable")
    return {
        "status": "healthy",
        "service": "rag-service",
        "version": "1.0.0",
        "chromadb_connected": vector_store.is_connected() if vector_store else False
    }


@app.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_context(request: RetrievalRequest):
    """
    Retrieve relevant context from knowledge base.

    **Workflow:**
    1. Embed query using sentence-transformers
    2. Search ChromaDB for similar documents
    3. Filter by similarity threshold
    4. Return top-k most relevant results

    **Collections:**
    - `mitre_attack`: MITRE ATT&CK techniques and tactics
    - `cve_database`: Critical vulnerabilities
    - `incident_history`: Resolved TheHive cases
    - `security_runbooks`: Response playbooks

    **Args:**
        request: Retrieval parameters

    **Returns:**
        RetrievalResponse: Relevant documents with similarity scores
    """
    try:
        logger.info(f"Retrieval request: query='{request.query}', collection={request.collection}")

        # Query vector store
        results = await vector_store.query(
            collection_name=request.collection,
            query_text=request.query,
            top_k=request.top_k,
            min_similarity=request.min_similarity
        )

        # Convert to response model
        retrieval_results = [
            RetrievalResult(
                document=r['document'],
                metadata=r['metadata'],
                similarity_score=r['similarity_score']
            )
            for r in results
        ]

        return RetrievalResponse(
            query=request.query,
            results=retrieval_results,
            total_results=len(retrieval_results)
        )

    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest")
async def ingest_documents(collection: str, documents: List[Dict[str, Any]]):
    """
    Ingest documents into knowledge base.

    **Args:**
        collection: Target collection name
        documents: List of documents with text and metadata

    **Returns:**
        Ingestion status
    """
    try:
        logger.info(f"Ingesting {len(documents)} documents into {collection}")

        # Extract text and metadata
        texts = [doc.get('text', '') for doc in documents]
        metadatas = [doc.get('metadata', {}) for doc in documents]
        ids = [doc.get('id') for doc in documents if 'id' in doc]

        # Ingest documents
        success = await vector_store.add_documents(
            collection_name=collection,
            documents=texts,
            metadatas=metadatas,
            ids=ids if ids else None
        )

        if success:
            return {
                "status": "success",
                "collection": collection,
                "documents_added": len(documents),
                "message": f"Successfully ingested {len(documents)} documents"
            }
        else:
            raise HTTPException(status_code=500, detail="Document ingestion failed")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/collections")
async def list_collections():
    """
    List available knowledge base collections.
    """
    try:
        collection_metadata = {
            "mitre_attack": "MITRE ATT&CK techniques and tactics",
            "cve_database": "Critical vulnerabilities",
            "incident_history": "Resolved security incidents",
            "security_runbooks": "Response playbooks"
        }

        collections = []
        for name, description in collection_metadata.items():
            stats = vector_store.get_collection_stats(name)
            collections.append({
                "name": name,
                "description": description,
                "document_count": stats.get('count', 0),
                "status": "initialized" if stats.get('count', 0) > 0 else "empty",
                "metadata": stats.get('metadata', {})
            })

        return {"collections": collections}

    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/mitre")
async def ingest_mitre():
    """
    Ingest MITRE ATT&CK framework into knowledge base.

    Downloads latest MITRE ATT&CK data and ingests all techniques.
    """
    try:
        logger.info("Starting MITRE ATT&CK ingestion")
        result = await kb_manager.ingest_mitre_attack()
        if result.get("status") != "success":
            raise RuntimeError(result.get("message", "MITRE ingestion failed"))
        return result
    except Exception as e:
        logger.error(f"MITRE ingestion failed: {e}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/cve")
async def ingest_cve(severity: str = "CRITICAL"):
    """
    Ingest CVE vulnerability database from NVD API v2.

    Queries the NVD API for CRITICAL (and optionally HIGH) severity CVEs
    and ingests them into the cve_database ChromaDB collection.

    **Query Parameters:**
    - `severity`: Filter level - "CRITICAL" (default) or "HIGH" (fetches both CRITICAL and HIGH)

    **Rate limits:** NVD allows 5 requests/30s without API key. Large ingestions take time.

    **Returns:**
        Ingestion status with count of CVEs ingested
    """
    if severity not in ("CRITICAL", "HIGH"):
        raise HTTPException(
            status_code=400,
            detail="severity must be 'CRITICAL' or 'HIGH'"
        )
    try:
        logger.info(f"Starting CVE ingestion with severity filter: {severity}")
        result = await kb_manager.ingest_cve_database(severity_filter=severity)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CVE ingestion failed: {e}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/runbooks")
async def ingest_runbooks(runbooks_dir: Optional[str] = None):
    """
    Ingest security runbooks from markdown files.

    Parses runbook markdown files, splits them into sections, and embeds
    them into the security_runbooks ChromaDB collection.

    **Query Parameters:**
    - `runbooks_dir`: Path to runbooks directory (default: services/rag-service/runbooks/)

    **Returns:**
        Ingestion status with count of runbooks and sections ingested
    """
    target_dir = runbooks_dir or RUNBOOKS_DIR
    try:
        logger.info(f"Starting runbook ingestion from: {target_dir}")
        result = await kb_manager.ingest_security_runbooks(runbooks_dir=target_dir)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Runbook ingestion failed: {e}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update/{collection}")
async def update_collection(collection: str):
    """
    Update a knowledge base collection by re-ingesting from source.

    Deletes the existing collection and re-ingests fresh data.

    **Path Parameters:**
    - `collection`: Collection name to update (mitre_attack, cve_database, security_runbooks)

    **Returns:**
        Update status with ingestion details
    """
    supported = ["mitre_attack", "cve_database", "security_runbooks"]
    if collection not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported collection: {collection}. Supported: {', '.join(supported)}"
        )
    try:
        logger.info(f"Starting collection update: {collection}")
        result = await kb_manager.update_knowledge_base(collection)
        return result
    except Exception as e:
        logger.error(f"Collection update failed for {collection}: {e}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "rag-service",
        "version": "1.0.0",
        "status": "production",
        "note": "Full RAG implementation with ChromaDB, MITRE ATT&CK, CVE database, and security runbooks",
        "endpoints": {
            "retrieve": "/retrieve",
            "ingest": "/ingest",
            "ingest_mitre": "/ingest/mitre",
            "ingest_cve": "/ingest/cve",
            "ingest_runbooks": "/ingest/runbooks",
            "update_collection": "/update/{collection}",
            "collections": "/collections",
            "health": "/health",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
