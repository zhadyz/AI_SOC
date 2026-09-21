"""Fixed, checksum-verified MiniLM ONNX embeddings; no remote model code."""
import os
from pathlib import Path
from threading import Lock

import numpy as np
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2


class EmbeddingEngine:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        if model_name != "all-MiniLM-L6-v2":
            raise ValueError("Only the fixed MiniLM embedding model is supported")
        self.model_name = model_name
        self.lock = Lock()
        self.model = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
        self.model.DOWNLOAD_PATH = Path(os.getenv("RAG_EMBEDDING_CACHE", "work/embedding-model"))
        # The library verifies the archive SHA256 before loading ONNX weights.
        self.model(["startup probe"])
        self.model.tokenizer.enable_truncation(max_length=256)
        self.model.tokenizer.enable_padding(length=256)

    def embed_text(self, text):
        return self.embed_batch([text])[0].tolist()

    def embed_batch(self, texts, batch_size=32):
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        with self.lock:
            result = np.concatenate([np.asarray(self.model(texts[i:i + batch_size]))
                                     for i in range(0, len(texts), batch_size)])
        if result.shape != (len(texts), 384) or not np.isfinite(result).all():
            raise RuntimeError("Invalid embedding output")
        return result

    def get_embedding_function(self):
        return self.model

    def compute_similarity(self, text1, text2):
        a, b = self.embed_batch([text1, text2])
        return float(np.dot(a, b))
