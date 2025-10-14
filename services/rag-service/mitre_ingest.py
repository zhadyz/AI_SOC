"""
MITRE ATT&CK Knowledge Base Ingestion Script
AI-Augmented SOC

Downloads MITRE ATT&CK Enterprise framework and ingests into ChromaDB.
Run this script to populate the RAG knowledge base.
"""

import requests
import json
import logging
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MITRE ATT&CK Enterprise JSON URL
MITRE_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
CHROMADB_HOST = "chromadb"  # Container hostname
CHROMADB_PORT = 8000  # Internal port


def download_mitre_attack():
    """Download MITRE ATT&CK Enterprise framework"""
    logger.info("Downloading MITRE ATT&CK Enterprise framework...")
    try:
        response = requests.get(MITRE_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Downloaded {len(data['objects'])} MITRE ATT&CK objects")
        return data
    except Exception as e:
        logger.error(f"Failed to download MITRE ATT&CK: {e}")
        return None


def extract_techniques(mitre_data):
    """Extract attack techniques from MITRE data"""
    techniques = []

    for obj in mitre_data['objects']:
        if obj['type'] == 'attack-pattern':
            # Extract technique details
            technique = {
                'id': obj.get('external_references', [{}])[0].get('external_id', 'Unknown'),
                'name': obj.get('name', 'Unknown'),
                'description': obj.get('description', ''),
                'tactics': [phase['phase_name'] for phase in obj.get('kill_chain_phases', [])],
                'platforms': obj.get('x_mitre_platforms', []),
                'data_sources': obj.get('x_mitre_data_sources', []),
            }

            # Create searchable text
            technique['text'] = f"""
Technique: {technique['id']} - {technique['name']}
Tactics: {', '.join(technique['tactics'])}
Description: {technique['description']}
Platforms: {', '.join(technique['platforms'])}
Data Sources: {', '.join(technique['data_sources'])}
""".strip()

            techniques.append(technique)

    logger.info(f"Extracted {len(techniques)} attack techniques")
    return techniques


def ingest_to_chromadb(techniques):
    """Ingest techniques into ChromaDB"""
    logger.info(f"Connecting to ChromaDB at {CHROMADB_HOST}:{CHROMADB_PORT}...")

    try:
        # Connect to ChromaDB
        client = chromadb.HttpClient(
            host=CHROMADB_HOST,
            port=CHROMADB_PORT,
            settings=Settings(anonymized_telemetry=False)
        )

        # Test connection
        logger.info(f"ChromaDB heartbeat: {client.heartbeat()}")

        # Create or get collection
        collection_name = "mitre_attack"

        # Create embedding function
        logger.info("Loading sentence-transformers model...")
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

        # Get or create collection
        collection = client.get_or_create_collection(
            name=collection_name
        )

        logger.info(f"Created collection: {collection_name}")

        # Batch ingest techniques
        batch_size = 50
        for i in range(0, len(techniques), batch_size):
            batch = techniques[i:i+batch_size]

            documents = [t['text'] for t in batch]
            ids = [t['id'] for t in batch]
            metadatas = [
                {
                    'name': t['name'],
                    'tactics': json.dumps(t['tactics']),
                    'platforms': json.dumps(t['platforms']),
                }
                for t in batch
            ]

            # Generate embeddings
            embeddings = embedding_model.encode(documents).tolist()

            # Add to collection
            collection.add(
                documents=documents,
                embeddings=embeddings,
                ids=ids,
                metadatas=metadatas
            )

            logger.info(f"Ingested batch {i//batch_size + 1}: {len(batch)} techniques")

        # Verify ingestion
        count = collection.count()
        logger.info(f"Successfully ingested {count} techniques into ChromaDB")

        # Test query
        logger.info("Testing semantic search...")
        results = collection.query(
            query_texts=["SSH brute force attack"],
            n_results=3
        )

        logger.info("Top 3 results for 'SSH brute force attack':")
        for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
            logger.info(f"{i+1}. {metadata['name']}")
            logger.info(f"   {doc[:100]}...")

        return True

    except Exception as e:
        logger.error(f"Failed to ingest to ChromaDB: {e}")
        logger.exception(e)
        return False


def main():
    """Main ingestion workflow"""
    logger.info("="*60)
    logger.info("MITRE ATT&CK Knowledge Base Ingestion")
    logger.info("="*60)

    # Download MITRE ATT&CK
    mitre_data = download_mitre_attack()
    if not mitre_data:
        logger.error("Failed to download MITRE ATT&CK data")
        sys.exit(1)

    # Extract techniques
    techniques = extract_techniques(mitre_data)
    if not techniques:
        logger.error("No techniques extracted")
        sys.exit(1)

    # Ingest to ChromaDB
    success = ingest_to_chromadb(techniques)

    if success:
        logger.info("="*60)
        logger.info("MITRE ATT&CK ingestion completed successfully!")
        logger.info(f"Total techniques ingested: {len(techniques)}")
        logger.info("="*60)
    else:
        logger.error("MITRE ATT&CK ingestion failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
