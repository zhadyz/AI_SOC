"""
RAG Service Integration Test
AI-Augmented SOC

Tests the complete RAG service implementation:
- ChromaDB connection
- Embedding generation
- Document ingestion
- Semantic search
- MITRE ATT&CK ingestion
"""

import logging
import asyncio
from services.rag_service.embeddings import EmbeddingEngine
from services.rag_service.vector_store import VectorStore
from services.rag_service.knowledge_base import KnowledgeBaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_embedding_engine():
    """Test embedding generation"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Embedding Engine")
    logger.info("="*60)

    engine = EmbeddingEngine()

    # Test single embedding
    text = "SSH brute force attack from external IP"
    embedding = engine.embed_text(text)

    logger.info(f"✓ Generated embedding for: '{text}'")
    logger.info(f"✓ Embedding dimensions: {len(embedding)}")
    assert len(embedding) == 384, "Embedding should be 384 dimensions"

    # Test batch embedding
    texts = [
        "Malware detected on endpoint",
        "Suspicious network traffic",
        "Failed login attempts"
    ]
    embeddings = engine.embed_batch(texts)

    logger.info(f"✓ Generated {len(embeddings)} batch embeddings")
    logger.info(f"✓ Batch shape: {embeddings.shape}")
    assert embeddings.shape == (3, 384), "Batch embeddings shape incorrect"

    # Test similarity
    sim = engine.compute_similarity(
        "SSH brute force attack",
        "Multiple failed SSH login attempts"
    )
    logger.info(f"✓ Similarity score: {sim:.3f}")
    assert sim > 0.5, "Similar texts should have high similarity"

    logger.info("✓ Embedding Engine: PASSED\n")


async def test_vector_store():
    """Test ChromaDB vector store operations"""
    logger.info("="*60)
    logger.info("TEST 2: Vector Store (ChromaDB)")
    logger.info("="*60)

    engine = EmbeddingEngine()
    store = VectorStore(engine, host="localhost", port=8000)

    # Test connection
    connected = store.is_connected()
    logger.info(f"✓ ChromaDB connected: {connected}")

    if not connected:
        logger.error("✗ ChromaDB not running. Start with: docker run -p 8000:8000 chromadb/chroma")
        return False

    # Create test collection
    collection_name = "test_collection"
    success = store.create_collection(collection_name)
    logger.info(f"✓ Created collection: {collection_name}")

    # Add test documents
    documents = [
        "T1110 Brute Force: Adversaries may use brute force techniques to gain access to accounts",
        "T1021 Remote Services: Adversaries may use Valid Accounts to log into a service",
        "T1078 Valid Accounts: Adversaries may obtain and abuse credentials of existing accounts"
    ]

    metadatas = [
        {"technique_id": "T1110", "tactic": "Credential Access"},
        {"technique_id": "T1021", "tactic": "Lateral Movement"},
        {"technique_id": "T1078", "tactic": "Persistence"}
    ]

    ids = ["T1110", "T1021", "T1078"]

    success = await store.add_documents(
        collection_name=collection_name,
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    logger.info(f"✓ Added {len(documents)} documents")

    # Test semantic search
    results = await store.query(
        collection_name=collection_name,
        query_text="SSH brute force attack",
        top_k=2,
        min_similarity=0.0
    )

    logger.info(f"✓ Query results: {len(results)} documents")
    for i, result in enumerate(results):
        logger.info(f"  {i+1}. {result['metadata'].get('technique_id')} - Similarity: {result['similarity_score']:.3f}")

    assert len(results) > 0, "Should find relevant documents"
    assert results[0]['metadata']['technique_id'] == "T1110", "Most relevant should be T1110 Brute Force"

    # Get collection stats
    stats = store.get_collection_stats(collection_name)
    logger.info(f"✓ Collection stats: {stats['count']} documents")

    # Cleanup
    store.delete_collection(collection_name)
    logger.info(f"✓ Deleted test collection")

    logger.info("✓ Vector Store: PASSED\n")
    return True


async def test_mitre_ingestion():
    """Test MITRE ATT&CK ingestion (optional - downloads 10MB)"""
    logger.info("="*60)
    logger.info("TEST 3: MITRE ATT&CK Ingestion")
    logger.info("="*60)

    response = input("Download and ingest MITRE ATT&CK (~10MB, 3000+ techniques)? (y/n): ")
    if response.lower() != 'y':
        logger.info("⊘ Skipping MITRE ingestion (user choice)\n")
        return

    engine = EmbeddingEngine()
    store = VectorStore(engine, host="localhost", port=8000)
    kb_manager = KnowledgeBaseManager(store)

    logger.info("Downloading MITRE ATT&CK framework...")
    result = await kb_manager.ingest_mitre_attack()

    if result['status'] == 'success':
        logger.info(f"✓ Ingested {result['techniques_ingested']} MITRE techniques")

        # Test query
        logger.info("\nTesting semantic search on MITRE collection...")
        results = await store.query(
            collection_name='mitre_attack',
            query_text="SSH brute force attack detection",
            top_k=3,
            min_similarity=0.6
        )

        logger.info(f"✓ Found {len(results)} relevant techniques:")
        for i, result in enumerate(results):
            logger.info(f"  {i+1}. {result['metadata'].get('name')} ({result['metadata'].get('technique_id')})")
            logger.info(f"     Similarity: {result['similarity_score']:.3f}")

        logger.info("✓ MITRE Ingestion: PASSED\n")
    else:
        logger.error(f"✗ MITRE Ingestion failed: {result['message']}")


async def main():
    """Run all tests"""
    logger.info("\n" + "="*60)
    logger.info("RAG SERVICE INTEGRATION TESTS")
    logger.info("="*60 + "\n")

    try:
        # Test 1: Embedding Engine
        await test_embedding_engine()

        # Test 2: Vector Store
        vector_store_ok = await test_vector_store()

        # Test 3: MITRE Ingestion (optional)
        if vector_store_ok:
            await test_mitre_ingestion()

        logger.info("="*60)
        logger.info("ALL TESTS PASSED ✓")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"\n✗ TEST FAILED: {e}")
        logger.exception(e)


if __name__ == "__main__":
    asyncio.run(main())
