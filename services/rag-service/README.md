# RAG Service

**AI-Augmented SOC - Retrieval-Augmented Generation**

> Ground LLM responses in verified security knowledge to reduce hallucinations by 30-40%.

---

## Overview

The RAG (Retrieval-Augmented Generation) Service provides semantic search over security knowledge bases, enabling LLMs to cite verified sources instead of hallucinating information.

**Knowledge Sources:**
- **MITRE ATT&CK:** 3000+ attack techniques and tactics
- **CVE Database:** Critical vulnerabilities (CVSS >= 9.0)
- **Incident History:** Resolved TheHive cases
- **Security Runbooks:** Response playbooks and procedures

**Performance Targets:**
- **Faithfulness (RAGAS):** >0.90 (RAG accuracy)
- **Retrieval Precision:** >0.85 (relevant results)
- **Hallucination Reduction:** 30-40% vs non-RAG baseline
- **Latency:** <500ms per query

---

## Architecture

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Alert Triage │─────>│ RAG Service  │─────>│  ChromaDB    │
│   Service    │Query │ (Embeddings) │Search│ (Vector DB)  │
└──────────────┘      └──────────────┘      └──────┬───────┘
                                                    │
                                             ┌──────┴───────┐
                                             │ Knowledge    │
                                             │ - MITRE      │
                                             │ - CVE        │
                                             │ - Incidents  │
                                             └──────────────┘
```

**RAG Workflow:**
1. User query: "What is this attack technique?"
2. Embed query using sentence-transformers (all-MiniLM-L6-v2)
3. Search ChromaDB for semantically similar documents
4. Return top-3 most relevant results
5. LLM uses results as context in prompt

---

## API Endpoints

### `POST /retrieve`

Retrieve relevant context from knowledge base.

**Request:**
```json
{
  "query": "SSH brute force attack techniques",
  "collection": "mitre_attack",
  "top_k": 3,
  "min_similarity": 0.7
}
```

**Response:**
```json
{
  "query": "SSH brute force attack techniques",
  "results": [
    {
      "document": "T1110.001 - Brute Force: Password Guessing - Adversaries may use brute force techniques to gain access to accounts when passwords are unknown or when password hashes are obtained.",
      "metadata": {
        "technique_id": "T1110.001",
        "tactic": "Credential Access",
        "type": "mitre_technique"
      },
      "similarity_score": 0.92
    },
    {
      "document": "T1021.004 - Remote Services: SSH - Adversaries may use Valid Accounts to log into remote machines using Secure Shell (SSH)...",
      "metadata": {
        "technique_id": "T1021.004",
        "tactic": "Lateral Movement"
      },
      "similarity_score": 0.85
    }
  ],
  "total_results": 2
}
```

### `POST /ingest`

Ingest documents into knowledge base.

**Request:**
```json
{
  "collection": "security_runbooks",
  "documents": [
    {
      "text": "SSH Brute Force Response Runbook: 1. Block source IP...",
      "metadata": {"title": "SSH Brute Force Response", "version": "1.0"}
    }
  ]
}
```

### `GET /collections`

List available knowledge base collections.

---

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_CHROMADB_HOST` | `chromadb` | ChromaDB hostname |
| `RAG_CHROMADB_PORT` | `8000` | ChromaDB port |
| `RAG_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | HuggingFace model |
| `RAG_DEFAULT_TOP_K` | `3` | Default results count |
| `RAG_MIN_SIMILARITY` | `0.7` | Minimum similarity threshold |

---

## Knowledge Base Ingestion

### MITRE ATT&CK

**Source:** https://github.com/mitre-attack/attack-stix-data

**Ingestion Command:**
```bash
curl -X POST http://rag-service:8001/ingest/mitre
```

**Data Structure:**
- **Techniques:** 3000+ attack techniques (T1110, T1021, etc.)
- **Tactics:** 14 tactics (Initial Access, Lateral Movement, etc.)
- **Groups:** APT groups and threat actors
- **Software:** Malware and tools

**Example Document:**
```
T1110.001 - Brute Force: Password Guessing

Description: Adversaries may use brute force techniques to gain access...

Detection: Monitor authentication logs for multiple failed attempts...

Mitigations: Implement account lockout policies, multi-factor authentication...
```

### CVE Database

**Source:** NVD API (https://nvd.nist.gov/)

**Ingestion Command:**
```bash
curl -X POST http://rag-service:8001/ingest/cve \
  -d '{"severity_filter": "CRITICAL"}'
```

**Filters:**
- CVSS score >= 9.0
- Published within last 2 years
- Exploits available

**Example Document:**
```
CVE-2024-12345: Remote Code Execution in Apache Tomcat

CVSS: 9.8 (Critical)

Description: Remote attackers can execute arbitrary code via crafted HTTP requests...

Affected Versions: 9.0.0-9.0.75

Fix: Upgrade to 9.0.76 or later
```

### Incident History

**Source:** TheHive API

**Ingestion Command:**
```bash
curl -X POST http://rag-service:8001/ingest/incidents \
  -H "Authorization: Bearer $THEHIVE_API_KEY"
```

**Criteria:**
- Status: Resolved
- Minimum 50 cases
- Contains observables and resolution

**Example Document:**
```
Incident #2024-042: SSH Brute Force from Botnet

Description: Multiple failed SSH login attempts from 203.0.113.0/24

Observables:
- 203.0.113.42 (IP)
- 203.0.113.89 (IP)

Resolution: Blocked source IPs at firewall, implemented fail2ban

Lessons Learned: Need automated blocking after 5 failed attempts
```

---

## Embedding Model

**Model:** `all-MiniLM-L6-v2`

**Specifications:**
- **Dimensions:** 384
- **Speed:** ~1000 sentences/second (CPU)
- **Size:** 80 MB
- **Quality:** High for semantic similarity

**Why This Model?**
- ✅ Fast inference (CPU-friendly)
- ✅ Good balance of speed/quality
- ✅ Pre-trained on diverse text
- ✅ Well-supported by sentence-transformers

**Alternative Models (Future):**
- `bge-large-en-v1.5` (higher quality, slower)
- Fine-tuned security domain model (Week 8+)

---

## RAG Integration with Alert Triage

### Enhanced Prompt with RAG Context

**Without RAG:**
```
Analyze this SSH brute force alert...

[LLM may hallucinate MITRE techniques or response steps]
```

**With RAG:**
```
Analyze this SSH brute force alert...

**VERIFIED CONTEXT FROM KNOWLEDGE BASE:**
1. MITRE T1110.001 - Password Guessing: Adversaries use brute force...
2. Past Incident #2024-042: Similar attack blocked at firewall...
3. Runbook: SSH Brute Force Response - Step 1: Block IP...

[LLM cites specific sources, no hallucination]
```

**Integration Code (alert-triage service):**
```python
# Query RAG service for context
rag_response = await httpx.post(
    "http://rag-service:8001/retrieve",
    json={"query": f"SSH brute force {alert.source_ip}", "top_k": 3}
)

# Inject context into prompt
context = "\n".join([r['document'] for r in rag_response['results']])
prompt = f"""
{base_prompt}

**VERIFIED CONTEXT:**
{context}

**IMPORTANT:** Base your analysis on the verified context above.
"""
```

---

## Evaluation Metrics

### RAGAS (RAG Assessment)

**Metrics:**
- **Faithfulness:** Is the response grounded in retrieved context?
- **Answer Relevancy:** Does the answer address the question?
- **Context Precision:** Are retrieved documents relevant?
- **Context Recall:** Is all necessary context retrieved?

**Target:** >0.90 overall RAGAS score

**Evaluation Command:**
```bash
pytest tests/test_ragas.py -v
```

### Retrieval Precision

**Formula:** `Relevant Results / Total Results`

**Target:** >0.85 precision at k=3

**Measurement:**
- Human annotation of 100 test queries
- Label retrieved results as relevant/irrelevant
- Calculate precision

---

## ChromaDB Schema

### Collections

**mitre_attack:**
```python
{
  "id": "T1110.001",
  "document": "Brute Force: Password Guessing - Adversaries...",
  "metadata": {
    "technique_id": "T1110.001",
    "tactic": "Credential Access",
    "type": "mitre_technique",
    "url": "https://attack.mitre.org/techniques/T1110/001/"
  },
  "embedding": [0.123, 0.456, ...]  # 384 dimensions
}
```

**cve_database:**
```python
{
  "id": "CVE-2024-12345",
  "document": "Remote Code Execution in Apache Tomcat...",
  "metadata": {
    "cvss_score": 9.8,
    "severity": "CRITICAL",
    "published": "2024-06-15"
  }
}
```

**incident_history:**
```python
{
  "id": "incident-2024-042",
  "document": "SSH Brute Force from Botnet - Multiple failed...",
  "metadata": {
    "case_id": "2024-042",
    "status": "Resolved",
    "date": "2024-03-20",
    "severity": "medium"
  }
}
```

---

## Local Development

### Prerequisites

- Python 3.11+
- Docker (for ChromaDB)

### Setup

1. **Start ChromaDB:**
   ```bash
   docker run -d -p 8000:8000 chromadb/chroma:latest
   ```

2. **Install dependencies:**
   ```bash
   cd services/rag-service
   pip install -r requirements.txt
   ```

3. **Run service:**
   ```bash
   python main.py
   ```

4. **Test retrieval:**
   ```bash
   curl -X POST http://localhost:8001/retrieve \
     -H "Content-Type: application/json" \
     -d '{
       "query": "What is SSH brute force?",
       "collection": "mitre_attack",
       "top_k": 3
     }'
   ```

---

## Testing

```bash
# Unit tests
pytest tests/ -v

# Integration tests (requires ChromaDB)
pytest tests/integration/ -v

# RAGAS evaluation
pytest tests/test_ragas.py -v

# Benchmark retrieval speed
pytest tests/test_performance.py -v
```

**TODO: Week 5** - Implement comprehensive test suite

---

## Known Limitations

1. **Embedding Quality:** Generic model may miss domain-specific terms
   - **Mitigation:** Fine-tune on security corpus (Week 8)
2. **Knowledge Freshness:** Static knowledge base becomes outdated
   - **Mitigation:** Scheduled updates (daily for CVEs)
3. **Retrieval Latency:** Embedding + search adds 200-500ms
   - **Mitigation:** Caching, optimized ChromaDB config

---

## Roadmap

### Week 5 (Target Phase)
- [ ] ChromaDB integration
- [ ] MITRE ATT&CK ingestion (3000+ techniques)
- [ ] Embedding pipeline (all-MiniLM-L6-v2)
- [ ] Semantic search API
- [ ] Integration with alert-triage service

### Week 6+
- [ ] CVE database ingestion
- [ ] TheHive incident history
- [ ] RAGAS evaluation framework
- [ ] Automated knowledge base updates

### Week 8+ (Advanced)
- [ ] Fine-tune embeddings on security corpus
- [ ] Hybrid search (semantic + keyword)
- [ ] Multi-modal RAG (images, PDFs)

---

## References

- **MITRE ATT&CK:** https://attack.mitre.org/
- **ChromaDB Docs:** https://docs.trychroma.com/
- **Sentence-Transformers:** https://www.sbert.net/
- **RAGAS Framework:** https://github.com/explodinggradients/ragas

---

**Last Updated:** 2025-01-13
**Status:** Scaffolded - Implementation in Week 5
**Maintainer:** Abdul Bari
