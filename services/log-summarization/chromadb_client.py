"""
ChromaDB Client - Log Summarization Service
AI-Augmented SOC

Handles storage and retrieval of log summaries in ChromaDB vector database.

Author: HOLLOWED_EYES
Mission: Phase 3 AI Service Integration
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
import chromadb
from chromadb.config import Settings as ChromaSettings
from config import settings

logger = logging.getLogger(__name__)


class ChromaDBClient:
    """
    Client for ChromaDB vector database.

    Features:
    - Store log summaries with embeddings
    - Semantic search for similar summaries
    - Temporal filtering
    - Metadata storage
    """

    def __init__(self):
        """Initialize ChromaDB client"""
        try:
            # Initialize ChromaDB client
            self.client = chromadb.HttpClient(
                host=settings.chromadb_host.replace("http://", "").replace("https://", ""),
                port=8000,
                settings=ChromaSettings(anonymized_telemetry=False)
            )

            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=settings.chromadb_collection,
                metadata={"description": "Security log summaries for RAG"}
            )

            logger.info(
                f"ChromaDB client initialized: collection={settings.chromadb_collection}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.client = None
            self.collection = None

    async def check_health(self) -> bool:
        """
        Check ChromaDB connectivity.

        Returns:
            bool: True if ChromaDB is accessible
        """
        if not self.client:
            return False

        try:
            # Attempt to list collections
            collections = self.client.list_collections()
            logger.info(f"ChromaDB healthy: {len(collections)} collections")
            return True
        except Exception as e:
            logger.error(f"ChromaDB health check failed: {e}")
            return False

    async def store_summary(
        self,
        summary_id: str,
        summary_text: str,
        metadata: Dict[str, Any],
        embedding: Optional[List[float]] = None
    ) -> bool:
        """
        Store log summary in ChromaDB.

        Args:
            summary_id: Unique summary identifier
            summary_text: Full summary text
            metadata: Summary metadata (time_range, log_count, etc)
            embedding: Pre-computed embedding (optional)

        Returns:
            bool: True if successful
        """
        if not self.collection:
            logger.warning("ChromaDB not initialized - cannot store summary")
            return False

        try:
            # Add timestamp to metadata
            metadata["stored_at"] = datetime.utcnow().isoformat()

            # Store in ChromaDB
            if embedding:
                # Use provided embedding
                self.collection.add(
                    ids=[summary_id],
                    documents=[summary_text],
                    metadatas=[metadata],
                    embeddings=[embedding]
                )
            else:
                # Let ChromaDB compute embedding
                self.collection.add(
                    ids=[summary_id],
                    documents=[summary_text],
                    metadatas=[metadata]
                )

            logger.info(f"Stored summary: {summary_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store summary: {e}")
            return False

    async def search_similar_summaries(
        self,
        query_text: str,
        top_k: int = 5,
        time_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar summaries using semantic search.

        Args:
            query_text: Search query
            top_k: Number of results to return
            time_filter: Optional time-based filter

        Returns:
            List[Dict]: Similar summaries with metadata
        """
        if not self.collection:
            logger.warning("ChromaDB not initialized - cannot search")
            return []

        try:
            # Build where filter if time_filter provided
            where_filter = None
            if time_filter:
                # Example: {"time_range_start": {"$gte": "2025-01-01"}}
                where_filter = time_filter

            # Perform semantic search
            results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k,
                where=where_filter
            )

            # Format results
            summaries = []
            if results and results['ids'] and len(results['ids']) > 0:
                for i, doc_id in enumerate(results['ids'][0]):
                    summaries.append({
                        "id": doc_id,
                        "text": results['documents'][0][i] if results['documents'] else "",
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else 0.0
                    })

            logger.info(f"Found {len(summaries)} similar summaries")
            return summaries

        except Exception as e:
            logger.error(f"Failed to search summaries: {e}")
            return []

    async def get_recent_summaries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recent summaries.

        Args:
            limit: Number of summaries to return

        Returns:
            List[Dict]: Recent summaries
        """
        if not self.collection:
            return []

        try:
            # Get all documents (ChromaDB doesn't have built-in sorting by metadata)
            results = self.collection.get(
                limit=limit,
                include=["documents", "metadatas"]
            )

            summaries = []
            if results and results['ids']:
                for i, doc_id in enumerate(results['ids']):
                    summaries.append({
                        "id": doc_id,
                        "text": results['documents'][i] if results['documents'] else "",
                        "metadata": results['metadatas'][i] if results['metadatas'] else {}
                    })

            # Sort by stored_at timestamp if available
            summaries.sort(
                key=lambda x: x['metadata'].get('stored_at', ''),
                reverse=True
            )

            return summaries[:limit]

        except Exception as e:
            logger.error(f"Failed to get recent summaries: {e}")
            return []

    async def delete_old_summaries(self, days_old: int = 90) -> int:
        """
        Delete summaries older than specified days.

        Args:
            days_old: Delete summaries older than this

        Returns:
            int: Number of summaries deleted
        """
        if not self.collection:
            return 0

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            cutoff_iso = cutoff_date.isoformat()

            # Query old summaries
            # Note: ChromaDB filtering is limited, may need to get all and filter
            results = self.collection.get(include=["metadatas"])

            ids_to_delete = []
            if results and results['ids']:
                for i, doc_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i] if results['metadatas'] else {}
                    stored_at = metadata.get('stored_at', '')
                    if stored_at and stored_at < cutoff_iso:
                        ids_to_delete.append(doc_id)

            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} old summaries")

            return len(ids_to_delete)

        except Exception as e:
            logger.error(f"Failed to delete old summaries: {e}")
            return 0


from datetime import timedelta  # Add missing import
