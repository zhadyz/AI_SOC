"""
Embedding Engine - RAG Service
AI-Augmented SOC

Generates vector embeddings using HuggingFace sentence-transformers.
Optimized for security domain with all-MiniLM-L6-v2 model.
"""

import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """
    Text embedding generator using sentence-transformers.

    Model: all-MiniLM-L6-v2
    - Dimensions: 384
    - Speed: ~1000 sentences/second (CPU)
    - Quality: Balanced for semantic similarity
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding model.

        Args:
            model_name: HuggingFace model identifier
        """
        self.model_name = model_name

        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {model_name}")
            self.model = SentenceTransformer(model_name)
            logger.info(f"Successfully loaded embedding model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load embedding model {model_name}: {e}")
            raise RuntimeError(f"Embedding model {model_name} is unavailable") from e

        logger.info(f"EmbeddingEngine initialized (model: {model_name})")

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for single text.

        Args:
            text: Input text

        Returns:
            List of 384 floats (embedding vector)
        """
        if not self.model:
            logger.warning("Embedding model not loaded, returning zero vector")
            raise RuntimeError("Embedding model unavailable")

        try:
            embedding = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise RuntimeError("Embedding failed") from e

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for batch of texts.

        Optimized for throughput with batching.

        Args:
            texts: List of input texts
            batch_size: Batch size for processing

        Returns:
            numpy array of shape (len(texts), 384)
        """
        if not self.model:
            logger.warning("Embedding model not loaded, returning zero vectors")
            raise RuntimeError("Embedding model unavailable")

        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=len(texts) > 100,  # Only show progress for large batches
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            return embeddings
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise RuntimeError("Embedding model unavailable")

    def get_embedding_function(self):
        """
        Get embedding function for ChromaDB integration.

        Returns:
            Callable embedding function

        TODO: Week 5 - Return ChromaDB-compatible function
        """
        engine = self
        class EmbeddingFunction:
            def __call__(self, input):
                return engine.embed_batch(input).tolist()
        return EmbeddingFunction()

    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            float: Similarity score (0.0-1.0)
        """
        if not self.model:
            logger.warning("Embedding model not loaded")
            return 0.0

        try:
            emb1 = np.array(self.embed_text(text1))
            emb2 = np.array(self.embed_text(text2))

            # Cosine similarity (already normalized, so just dot product)
            similarity = np.dot(emb1, emb2)
            return float(similarity)
        except Exception as e:
            logger.error(f"Failed to compute similarity: {e}")
            return 0.0


# TODO: Week 5 - Add domain-specific embedding optimization
# class SecurityEmbedding(EmbeddingEngine):
#     """
#     Security-domain optimized embeddings.
#
#     Potential improvements:
#     - Fine-tune on security text corpus
#     - Add domain-specific vocabulary
#     - Optimize for technical terms (CVE, MITRE ATT&CK, etc)
#     """
#
#     def __init__(self):
#         super().__init__(model_name="all-MiniLM-L6-v2")
#
#     def preprocess_security_text(self, text: str) -> str:
#         """Preprocess security-specific text for better embeddings"""
#         # Normalize CVE IDs, IP addresses, etc.
#         pass
