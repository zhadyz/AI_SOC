# RAG Service API Reference

Retrieval-Augmented Generation service for grounding LLM responses with security knowledge bases using ChromaDB vector search and semantic embeddings.

---

## Service Overview

| Property | Value |
|----------|-------|
| **Base URL** | `http://rag-service:8002` (internal), `https://api.ai-soc.example.com:8300` (external) |
| **Protocol** | HTTP/HTTPS (REST) |
| **Content Type** | `application/json` |
| **Authentication** | API Key (Bearer token) or JWT |
| **Vector Database** | ChromaDB (persistent storage) |
| **Embedding Model** | nomic-embed-text (137M parameters, 768 dimensions) |
| **Search Algorithm** | HNSW (Hierarchical Navigable Small World) |
| **Latency** | 50-200ms average (embedding + retrieval) |

---

## Authentication

All endpoints except `/health` require authentication.

### API Key Authentication

```http
POST /retrieve HTTP/1.1
Host: rag-service:8002
Authorization: Bearer aisoc_<your-api-key>
Content-Type: application/json
```

### JWT Authentication

```http
POST /retrieve HTTP/1.1
Host: rag-service:8002
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

---

## Endpoints

### GET /health

Health check endpoint for monitoring vector database connectivity.

#### Request

```http
GET /health HTTP/1.1
Host: rag-service:8002
```

#### Response

**Status**: `200 OK`

```json
{
  "status": "healthy",
  "service": "rag-service",
  "version": "1.0.0",
  "chromadb_connected": true
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Service status: `healthy`, `degraded`, `unhealthy` |
| `service` | string | Service identifier |
| `version` | string | API version |
| `chromadb_connected` | boolean | Whether ChromaDB is reachable |

---

### POST /retrieve

Retrieve relevant context from knowledge base using semantic search.

#### Request

```http
POST /retrieve HTTP/1.1
Host: rag-service:8002
Authorization: Bearer aisoc_<your-api-key>
Content-Type: application/json

{
  "query": "What are common brute force attack techniques?",
  "collection": "mitre_attack",
  "top_k": 3,
  "min_similarity": 0.7
}
```

**Request Body Schema:**

```json
{
  "query": {
    "type": "string",
    "minLength": 1,
    "required": true,
    "description": "Search query for semantic matching"
  },
  "collection": {
    "type": "string",
    "default": "mitre_attack",
    "enum": ["mitre_attack", "cve_database", "incident_history", "security_runbooks"],
    "description": "Knowledge base collection name"
  },
  "top_k": {
    "type": "integer",
    "minimum": 1,
    "maximum": 10,
    "default": 3,
    "description": "Number of results to return"
  },
  "min_similarity": {
    "type": "number",
    "minimum": 0.0,
    "maximum": 1.0,
    "default": 0.7,
    "description": "Minimum cosine similarity threshold (0.0-1.0)"
  }
}
```

#### Response (Success)

**Status**: `200 OK`

```json
{
  "query": "What are common brute force attack techniques?",
  "results": [
    {
      "document": "MITRE ATT&CK T1110: Brute Force - Adversaries may use brute force techniques to gain access to accounts when passwords are unknown or when password hashes are obtained. Without knowledge of the password for an account or set of accounts, an adversary may systematically guess the password using a repetitive or iterative mechanism.",
      "metadata": {
        "technique_id": "T1110",
        "tactic": "Credential Access",
        "sub_techniques": ["T1110.001", "T1110.002", "T1110.003", "T1110.004"],
        "data_sources": ["Authentication logs", "Application logs"],
        "mitigations": ["M1036", "M1027", "M1032"]
      },
      "similarity_score": 0.92
    },
    {
      "document": "T1110.001 - Password Guessing: Adversaries may use brute force techniques to attempt access to accounts by guessing passwords. This technique involves trying common passwords, dictionary words, or systematically generated passwords until the correct one is found.",
      "metadata": {
        "technique_id": "T1110.001",
        "parent_technique": "T1110",
        "tactic": "Credential Access",
        "detection": "Monitor authentication logs for multiple failed attempts"
      },
      "similarity_score": 0.89
    },
    {
      "document": "T1110.003 - Password Spraying: Adversaries may use a single or small list of commonly used passwords against many different accounts to attempt to acquire valid account credentials. This technique avoids account lockouts by trying one password against multiple accounts.",
      "metadata": {
        "technique_id": "T1110.003",
        "parent_technique": "T1110",
        "tactic": "Credential Access"
      },
      "similarity_score": 0.85
    }
  ],
  "total_results": 3
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `query` | string | Original search query (echo) |
| `results` | array | Matching documents with metadata |
| `results[].document` | string | Retrieved text content |
| `results[].metadata` | object | Document metadata (technique IDs, tactics, etc.) |
| `results[].similarity_score` | float | Cosine similarity (0.0-1.0) |
| `total_results` | integer | Number of results returned |

#### Response (No Results Found)

**Status**: `200 OK` (empty results)

```json
{
  "query": "quantum entanglement in cybersecurity",
  "results": [],
  "total_results": 0
}
```

**Interpretation**: No documents exceeded the `min_similarity` threshold of 0.7.

#### Response (Collection Not Found)

**Status**: `404 Not Found`

```json
{
  "error": "Collection not found",
  "detail": "Collection 'invalid_collection' does not exist",
  "available_collections": ["mitre_attack", "cve_database", "incident_history", "security_runbooks"]
}
```

---

### POST /ingest

Ingest documents into knowledge base collection.

#### Request

```http
POST /ingest HTTP/1.1
Host: rag-service:8002
Authorization: Bearer aisoc_<your-api-key>
Content-Type: application/json

{
  "collection": "incident_history",
  "documents": [
    {
      "text": "Ransomware incident on 2025-10-15 affecting file servers. Attack vector: phishing email with malicious attachment. Impact: 50 workstations encrypted. Response: Restored from backups, implemented email filtering.",
      "metadata": {
        "incident_id": "INC-2025-001",
        "date": "2025-10-15",
        "severity": "HIGH",
        "attack_type": "Ransomware",
        "resolution_status": "Resolved"
      }
    },
    {
      "text": "SQL injection attempt detected on web application. Attack blocked by WAF. No data exfiltration occurred. Patched vulnerability in login form.",
      "metadata": {
        "incident_id": "INC-2025-002",
        "date": "2025-10-18",
        "severity": "MEDIUM",
        "attack_type": "SQL Injection",
        "resolution_status": "Resolved"
      }
    }
  ]
}
```

**Request Body Schema:**

```json
{
  "collection": {
    "type": "string",
    "required": true,
    "description": "Target collection name"
  },
  "documents": {
    "type": "array",
    "required": true,
    "minItems": 1,
    "maxItems": 100,
    "items": {
      "type": "object",
      "properties": {
        "text": {
          "type": "string",
          "minLength": 1,
          "description": "Document text content"
        },
        "metadata": {
          "type": "object",
          "description": "Arbitrary metadata fields"
        }
      },
      "required": ["text"]
    }
  }
}
```

#### Response (Success)

**Status**: `201 Created`

```json
{
  "status": "success",
  "collection": "incident_history",
  "documents_added": 2,
  "embedding_time_ms": 45,
  "indexing_time_ms": 23,
  "total_time_ms": 68
}
```

#### Response (Partial Success)

**Status**: `207 Multi-Status`

```json
{
  "status": "partial_success",
  "collection": "incident_history",
  "documents_added": 8,
  "documents_failed": 2,
  "failed_documents": [
    {
      "index": 3,
      "error": "Empty text field"
    },
    {
      "index": 7,
      "error": "Text exceeds maximum length (10,000 characters)"
    }
  ]
}
```

---

### GET /collections

List available knowledge base collections with statistics.

#### Request

```http
GET /collections HTTP/1.1
Host: rag-service:8002
Authorization: Bearer aisoc_<your-api-key>
```

#### Response

**Status**: `200 OK`

```json
{
  "collections": [
    {
      "name": "mitre_attack",
      "description": "MITRE ATT&CK techniques and tactics (version 14.0)",
      "document_count": 793,
      "status": "ready",
      "last_updated": "2025-10-20T12:00:00Z",
      "embedding_dimensions": 768,
      "index_type": "HNSW"
    },
    {
      "name": "cve_database",
      "description": "Critical vulnerabilities (CVSS >= 7.0)",
      "document_count": 2547,
      "status": "ready",
      "last_updated": "2025-10-23T08:00:00Z",
      "embedding_dimensions": 768,
      "index_type": "HNSW"
    },
    {
      "name": "incident_history",
      "description": "Resolved security incidents from TheHive",
      "document_count": 156,
      "status": "ready",
      "last_updated": "2025-10-24T10:15:30Z",
      "embedding_dimensions": 768,
      "index_type": "HNSW"
    },
    {
      "name": "security_runbooks",
      "description": "Incident response playbooks and procedures",
      "document_count": 42,
      "status": "ready",
      "last_updated": "2025-10-15T14:30:00Z",
      "embedding_dimensions": 768,
      "index_type": "HNSW"
    }
  ],
  "total_collections": 4,
  "total_documents": 3538
}
```

---

### DELETE /collections/{collection_name}

Delete an entire collection (admin only).

#### Request

```http
DELETE /collections/test_collection HTTP/1.1
Host: rag-service:8002
Authorization: Bearer aisoc_admin_api_key
```

#### Response

**Status**: `204 No Content`

---

## Error Codes

| HTTP Status | Error Code | Description |
|-------------|-----------|-------------|
| 400 | `invalid_query` | Query validation failed (empty or malformed) |
| 401 | `unauthorized` | Missing or invalid authentication |
| 404 | `collection_not_found` | Specified collection does not exist |
| 413 | `payload_too_large` | Document batch exceeds size limit |
| 429 | `rate_limit_exceeded` | Request quota exhausted |
| 503 | `chromadb_unavailable` | Vector database unreachable |
| 500 | `internal_error` | Unexpected server error |

---

## Knowledge Base Collections

### mitre_attack

**Description**: Complete MITRE ATT&CK framework (version 14.0)

**Contents**:
- 793 techniques and sub-techniques
- Tactics, data sources, mitigations
- Platform-specific information
- Detection guidance

**Example Queries**:
- "How do adversaries escalate privileges?"
- "What are common lateral movement techniques?"
- "Reconnaissance tactics in cyber attacks"

**Metadata Fields**:
```json
{
  "technique_id": "T1110.001",
  "tactic": "Credential Access",
  "sub_techniques": ["T1110.001", "T1110.002"],
  "platforms": ["Windows", "Linux", "macOS"],
  "data_sources": ["Authentication logs"],
  "mitigations": ["M1036", "M1027"]
}
```

---

### cve_database

**Description**: High-severity CVE database (CVSS >= 7.0)

**Contents**:
- 2,547 critical vulnerabilities
- CVE descriptions, affected software
- Exploit availability, remediation

**Example Queries**:
- "Recent remote code execution vulnerabilities"
- "Critical Apache web server CVEs"
- "Vulnerabilities affecting Windows Server 2019"

**Metadata Fields**:
```json
{
  "cve_id": "CVE-2025-1234",
  "cvss_score": 9.8,
  "severity": "CRITICAL",
  "affected_software": "Apache HTTP Server 2.4.x",
  "exploit_available": true,
  "published_date": "2025-09-15"
}
```

---

### incident_history

**Description**: Resolved security incidents from TheHive case management

**Contents**:
- 156 historical incidents
- Attack patterns, resolution procedures
- Lessons learned, indicators of compromise

**Example Queries**:
- "How was the ransomware incident resolved?"
- "Previous SQL injection attempts"
- "Incidents involving phishing emails"

**Metadata Fields**:
```json
{
  "incident_id": "INC-2025-001",
  "date": "2025-10-15",
  "severity": "HIGH",
  "attack_type": "Ransomware",
  "resolution_status": "Resolved",
  "resolution_time_hours": 4.5
}
```

---

### security_runbooks

**Description**: Incident response playbooks and SOC procedures

**Contents**:
- 42 response playbooks
- NIST-aligned procedures
- Escalation guidelines, checklists

**Example Queries**:
- "Malware infection response procedure"
- "DDoS attack mitigation steps"
- "Data breach notification requirements"

**Metadata Fields**:
```json
{
  "playbook_id": "PB-RANSOMWARE-001",
  "incident_type": "Ransomware",
  "severity_level": "P0",
  "estimated_duration_minutes": 30,
  "required_tools": ["EDR", "Backup System"]
}
```

---

## Rate Limiting

| Profile | Default | Retrieve Endpoint | Ingest Endpoint |
|---------|---------|-------------------|-----------------|
| Strict | 30 req/min | 20 req/min | 5 req/min |
| Moderate | 100 req/min | 50 req/min | 10 req/min |
| Permissive | 300 req/min | 150 req/min | 50 req/min |

**Rate Limit Headers:**

```
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1698765432
```

---

## Example Usage

### Python (RAG Integration with Alert Triage)

```python
import httpx
import asyncio

async def enrich_alert_with_context(alert_description: str):
    """Retrieve threat intelligence context for alert analysis"""

    url = "http://rag-service:8002/retrieve"
    headers = {
        "Authorization": "Bearer aisoc_your_api_key",
        "Content-Type": "application/json"
    }

    payload = {
        "query": alert_description,
        "collection": "mitre_attack",
        "top_k": 3,
        "min_similarity": 0.7
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            data = response.json()

            # Extract relevant context for LLM
            context = []
            for result in data['results']:
                context.append({
                    "technique": result['metadata'].get('technique_id'),
                    "description": result['document'],
                    "similarity": result['similarity_score']
                })

            return context
        else:
            print(f"RAG error: {response.status_code}")
            return []

# Usage in LLM prompt
alert = "Multiple failed SSH login attempts from 192.168.1.50"
context = await enrich_alert_with_context(alert)

llm_prompt = f"""
Analyze this security alert: {alert}

Relevant threat intelligence:
{context}

Provide verdict, severity, and recommendations.
"""
```

### cURL (Retrieve)

```bash
curl -X POST http://rag-service:8002/retrieve \
  -H "Authorization: Bearer aisoc_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are common brute force techniques?",
    "collection": "mitre_attack",
    "top_k": 3,
    "min_similarity": 0.7
  }'
```

### cURL (Ingest Incident)

```bash
curl -X POST http://rag-service:8002/ingest \
  -H "Authorization: Bearer aisoc_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "incident_history",
    "documents": [
      {
        "text": "Phishing campaign detected targeting finance department...",
        "metadata": {
          "incident_id": "INC-2025-042",
          "severity": "HIGH",
          "attack_type": "Phishing"
        }
      }
    ]
  }'
```

---

## Embedding Model Information

### nomic-embed-text

**Specialization**: Text embeddings optimized for semantic search
**Parameters**: 137 million
**Dimensions**: 768
**Context Window**: 8,192 tokens

**Performance**:
- Embedding latency: 20-40ms (batch of 10)
- Quality: MTEB score 62.4
- Memory: 550MB model size

**Advantages**:
- Fast inference (CPU-optimized)
- Strong semantic understanding
- Efficient batching
- No GPU required

---

## Vector Search Configuration

### HNSW Index Parameters

```yaml
index_configuration:
  algorithm: HNSW  # Hierarchical Navigable Small World
  space: cosine    # Cosine similarity metric
  ef_construction: 200  # Higher = better quality, slower indexing
  M: 16           # Number of connections per node
  ef_search: 100  # Higher = better recall, slower search
```

**Performance Characteristics**:
- Build time: ~1 second per 1,000 documents
- Search time: <50ms for 10,000 documents
- Recall@10: >95% for typical queries

---

## Production Considerations

### Scaling

**Horizontal Scaling (Read Replicas):**
```yaml
# docker-compose.yml
services:
  rag-service:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
```

**Throughput:**
- Single instance: 200-300 retrievals/minute
- 3 replicas: 600-900 retrievals/minute
- Ingestion: 50-100 documents/minute (single instance)

### ChromaDB Persistence

**Data Directory:**
```yaml
services:
  chromadb:
    volumes:
      - chromadb-data:/chroma/chroma
```

**Backup Strategy:**
```bash
# Backup ChromaDB data directory
tar -czf chromadb-backup-$(date +%Y%m%d).tar.gz /var/lib/docker/volumes/chromadb-data

# Restore from backup
tar -xzf chromadb-backup-20251024.tar.gz -C /var/lib/docker/volumes/chromadb-data
```

### Monitoring

**Prometheus Metrics:**

```promql
# Retrieval latency
histogram_quantile(0.95, rag_retrieve_duration_seconds_bucket)

# Embedding throughput
rate(rag_embeddings_generated_total[5m])

# Collection size growth
rag_collection_documents_total{collection="mitre_attack"}
```

---

## Changelog

### Version 1.0.0 (Current)

- Initial production release
- ChromaDB vector storage
- nomic-embed-text embeddings
- 4 knowledge base collections
- HNSW index for fast retrieval
- RESTful API with OpenAPI schema

### Version 1.1.0 (Planned - Week 5)

- MITRE ATT&CK v14.0 update
- CVE database auto-sync (NVD feeds)
- TheHive incident auto-ingestion
- Hybrid search (dense + sparse)
- Re-ranking with cross-encoder
- Query expansion with synonyms

---

## Support

**API Issues**: api-support@ai-soc.example.com
**RAG Questions**: rag-team@ai-soc.example.com
**Documentation**: https://docs.ai-soc.example.com/api/rag-service

---

**Document Version**: 1.0
**Last Updated**: October 24, 2025
**Maintained By**: AI-SOC RAG Team
