"""
Vector Store - RAG Service
AI-Augmented SOC

ChromaDB interface for semantic search and document storage.
Manages collections, embeddings, and similarity search.
"""

import logging
import hashlib
import os
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class VectorStore:
    """
    ChromaDB vector database interface.

    Manages:
    - Collection creation and management
    - Document ingestion with embeddings
    - Semantic search queries
    - Metadata filtering
    """

    def __init__(self, embedding_engine, host: str = "chromadb", port: int = 8000):
        """
        Initialize ChromaDB client.

        Args:
            embedding_engine: EmbeddingEngine instance
            host: ChromaDB hostname (default: "chromadb" for Docker)
            port: ChromaDB port (default: 8000)
        """
        self.embedding_engine = embedding_engine
        self.host = host
        self.port = port

        try:
            self.client = chromadb.PersistentClient(
                path=os.getenv("RAG_CHROMADB_PATH", "work/chroma"),
                settings=Settings(anonymized_telemetry=False, allow_reset=False)
            )
            logger.info("Opened private embedded ChromaDB; no HTTP database listener")
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            raise RuntimeError("ChromaDB connection unavailable") from e

        logger.info("VectorStore initialized")

    def is_connected(self) -> bool:
        """
        Check if ChromaDB connection is active.

        Returns:
            bool: Connection status
        """
        try:
            if self.client:
                self.client.heartbeat()
                return True
            return False
        except Exception as e:
            logger.error(f"ChromaDB connection check failed: {e}")
            return False

    def create_collection(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create new ChromaDB collection.

        Args:
            name: Collection name
            metadata: Optional collection metadata

        Returns:
            bool: Success status
        """
        try:
            if not self.client:
                logger.error("ChromaDB client not initialized")
                raise RuntimeError("ChromaDB client unavailable")

            logger.info(f"Creating collection: {name}")

            # Try to get existing collection first
            try:
                self.client.get_collection(name=name, embedding_function=None)
                logger.info(f"Collection {name} already exists")
                return True
            except:
                # Collection doesn't exist, create it
                self.client.create_collection(
                    name=name,
                    embedding_function=None,
                    metadata=metadata or {"hnsw:space": "l2"}
                )
                logger.info(f"Successfully created collection: {name}")
                return True

        except Exception as e:
            logger.error(f"Failed to create collection {name}: {e}")
            raise RuntimeError("Collection creation failed") from e

    async def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None
    ) -> bool:
        """
        Add documents to collection with automatic embedding.

        Args:
            collection_name: Target collection
            documents: List of text documents
            metadatas: Optional metadata for each document
            ids: Optional document IDs
            embeddings: Optional pre-computed embeddings (if None, will generate)

        Returns:
            bool: Success status
        """
        try:
            if not self.client:
                logger.error("ChromaDB client not initialized")
                raise RuntimeError("ChromaDB client unavailable")

            logger.info(f"Adding {len(documents)} documents to {collection_name}")

            # Get collection
            collection = self.client.get_collection(collection_name, embedding_function=None)

            # Generate IDs if not provided
            if ids is None:
                ids = [hashlib.sha256(doc.encode()).hexdigest() for doc in documents]

            # Generate embeddings if not provided
            if embeddings is None:
                logger.info("Generating embeddings for documents...")
                embeddings = self.embedding_engine.embed_batch(documents)
                if isinstance(embeddings, list):
                    embeddings = embeddings
                else:
                    embeddings = embeddings.tolist()

            # Add documents to collection
            collection.upsert(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas or [{"source": "unspecified"} for _ in documents],
                ids=ids
            )

            logger.info(f"Successfully added {len(documents)} documents to {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            logger.exception(e)
            raise RuntimeError("Document ingestion failed") from e

    async def query(
        self,
        collection_name: str,
        query_text: str,
        top_k: int = 3,
        min_similarity: float = 0.7,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search on collection.

        Args:
            collection_name: Collection to search
            query_text: Search query
            top_k: Number of results
            min_similarity: Minimum similarity threshold
            metadata_filter: Optional metadata filtering

        Returns:
            List of results with documents, metadata, and scores
        """
        try:
            if not self.client:
                logger.error("ChromaDB client not initialized")
                raise RuntimeError("ChromaDB client unavailable")

            logger.info(f"Querying {collection_name}: '{query_text[:50]}...'")

            # Get collection
            collection = self.client.get_collection(collection_name, embedding_function=None)

            # Generate query embedding
            query_embedding = self.embedding_engine.embed_text(query_text)

            # Query ChromaDB
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=metadata_filter
            )

            # Filter by similarity threshold
            filtered_results = []

            # Check if results are empty
            if not results['documents'] or not results['documents'][0]:
                logger.warning(f"No results found for query: {query_text[:50]}")
                return []

            for doc, metadata, distance in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ):
                # Convert distance to similarity (ChromaDB uses L2 distance)
                # For normalized vectors, cosine similarity = 1 - (L2_distance^2 / 2)
                similarity = 1 - (distance / 2)

                if similarity >= min_similarity:
                    filtered_results.append({
                        'document': doc,
                        'metadata': metadata,
                        'similarity_score': float(similarity)
                    })

            logger.info(f"Found {len(filtered_results)} results above threshold {min_similarity}")
            return filtered_results

        except Exception as e:
            logger.error(f"Query failed: {e}")
            logger.exception(e)
            raise RuntimeError("Retrieval failed") from e

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Get statistics for collection.

        Returns:
            Dict with count, metadata, etc.
        """
        try:
            if not self.client:
                logger.error("ChromaDB client not initialized")
                return {"count": 0, "status": "not_connected"}

            collection = self.client.get_collection(collection_name, embedding_function=None)
            return {
                'name': collection_name,
                'count': collection.count(),
                'metadata': collection.metadata
            }
        except Exception as e:
            logger.error(f"Failed to get stats for {collection_name}: {e}")
            return {"count": 0, "error": str(e)}

    def delete_collection(self, collection_name: str) -> bool:
        """
        Delete collection.

        Args:
            collection_name: Collection to delete

        Returns:
            bool: Success status
        """
        try:
            if not self.client:
                logger.error("ChromaDB client not initialized")
                raise RuntimeError("ChromaDB client unavailable")

            logger.warning(f"Deleting collection: {collection_name}")
            self.client.delete_collection(collection_name)
            logger.info(f"Successfully deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {e}")
            return False


# TODO: Week 5 - Add advanced filtering
# class AdvancedVectorStore(VectorStore):
#     """Extended vector store with hybrid search"""
#
#     async def hybrid_search(
#         self,
#         collection_name: str,
#         query_text: str,
#         keyword_boost: float = 0.3
#     ) -> List[Dict[str, Any]]:
#         """Combine semantic search with keyword matching"""
#         pass
