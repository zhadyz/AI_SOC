# AI Services Layer

**AI-Augmented SOC - LLM-Powered Security Operations**

> Intelligent automation for alert triage, log summarization, and threat analysis using state-of-the-art large language models.

---

## Overview

This directory contains the core AI services that power the AI-Augmented SOC platform. Each service is containerized, independently scalable, and communicates via REST APIs.

**Architecture Principles:**
- **Microservices:** Each service has a single responsibility
- **API-First:** All services expose FastAPI REST endpoints
- **Observability:** Prometheus metrics, structured logging
- **Security:** Input validation, prompt injection protection
- **Resilience:** Automatic retries, fallback models

---

## Services

### 1. Alert Triage Service (`alert-triage/`)

**Purpose:** LLM-powered security alert analysis and prioritization

**Technology Stack:**
- FastAPI
- Ollama (Foundation-Sec-8B / LLaMA 3.1)
- Pydantic (structured outputs)

**API Endpoints:**
- `POST /analyze` - Analyze single alert
- `POST /batch` - Batch process alerts
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

**Key Features:**
- Severity classification (Critical/High/Medium/Low/Info)
- IOC extraction (IPs, domains, hashes)
- MITRE ATT&CK mapping
- True/false positive detection
- Confidence scoring
- Actionable recommendations

**Performance Targets:**
- **F1 Score:** >0.90
- **Latency:** <10 seconds per alert
- **Throughput:** 250 alerts/day
- **Auto-action threshold:** 80% confidence

**Status:** ✅ Scaffolded - Ready for Week 4 implementation

---

### 2. Log Summarization Service (`log-summarization/`)

**Purpose:** Batch processing and summarization of security logs

**Technology Stack:**
- FastAPI
- Ollama (LLaMA 3.1 8B)
- LibreLog (log parsing)
- OpenSearch (log storage)
- ChromaDB (summary storage)

**API Endpoints:**
- `POST /summarize` - Generate summary for time range
- `POST /summarize/daily` - Automated daily summary
- `GET /summaries` - List recent summaries

**Key Features:**
- Process 1000+ logs per batch
- Daily/weekly security briefings
- Threat indicator extraction
- Executive-friendly summaries
- Historical trend analysis

**Performance Targets:**
- **BERTScore:** >0.85
- **Throughput:** 1M+ logs/day
- **Time savings:** 42%+ vs manual review

**Status:** ✅ Scaffolded - Ready for Week 6 implementation

---

### 3. RAG Service (`rag-service/`)

**Purpose:** Retrieval-Augmented Generation for grounding LLM responses

**Technology Stack:**
- FastAPI
- ChromaDB (vector database)
- sentence-transformers (all-MiniLM-L6-v2)
- LangChain (RAG framework)

**API Endpoints:**
- `POST /retrieve` - Semantic search over knowledge base
- `POST /ingest` - Add documents to knowledge base
- `GET /collections` - List available collections

**Knowledge Base Collections:**
- **mitre_attack:** 3000+ MITRE ATT&CK techniques
- **cve_database:** Critical vulnerabilities (CVSS >= 9.0)
- **incident_history:** Resolved TheHive cases
- **security_runbooks:** Response playbooks

**Key Features:**
- Semantic search (cosine similarity)
- Top-k retrieval with confidence thresholds
- Source citation in LLM responses
- Hallucination reduction (30-40%)

**Performance Targets:**
- **RAGAS Faithfulness:** >0.90
- **Retrieval Precision:** >0.85
- **Latency:** <500ms per query

**Status:** ✅ Scaffolded - Ready for Week 5 implementation

---

### 4. Common Library (`common/`)

**Purpose:** Shared utilities across all services

**Modules:**
- `ollama_client.py` - Reusable Ollama API client
- `logging_config.py` - Structured JSON logging
- `metrics.py` - Prometheus metrics wrapper
- `security.py` - Input validation & prompt injection detection

**Usage:**
```python
from common import OllamaClient, setup_logging, ServiceMetrics

# Initialize logging
setup_logging("my-service", log_level="INFO")

# Create LLM client
llm = OllamaClient(host="http://ollama:11434", primary_model="llama3.1:8b")

# Generate completion
response = await llm.generate("Analyze this alert...", temperature=0.1)

# Record metrics
metrics = ServiceMetrics("my-service")
metrics.record_llm_request(model="llama3.1:8b", status="success", latency=5.2)
```

---

## System Architecture

### Data Flow Diagram

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Wazuh      │      │   Shuffle    │      │ Alert Triage │
│   Manager    │─────>│    SOAR      │─────>│   Service    │
│              │Alert │              │HTTP  │ (Foundation- │
└──────────────┘      └──────────────┘      │  Sec-8B)     │
                                             └──────┬───────┘
                                                    │
                                             ┌──────▼───────┐
                      ┌─────────────────────┤ RAG Service  │
                      │                     │ (ChromaDB)   │
                      │                     └──────────────┘
                      │
                      ▼
              ┌──────────────┐
              │   TheHive    │
              │ Case Manager │
              └──────────────┘

┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ OpenSearch   │      │ Log Summary  │      │  ChromaDB    │
│ (Wazuh Logs) │─────>│   Service    │─────>│ (Summaries)  │
│              │Query │ (LLaMA 3.1)  │Store │              │
└──────────────┘      └──────────────┘      └──────────────┘
```

### Integration Points

**Wazuh → Shuffle → Alert Triage:**
1. Wazuh detects security event
2. Generates alert (JSON)
3. Sends webhook to Shuffle
4. Shuffle forwards to Alert Triage `/analyze`
5. LLM analyzes alert (severity, IOCs, recommendations)
6. Shuffle routes to TheHive based on severity

**Alert Triage ↔ RAG Service:**
1. Alert Triage queries RAG `/retrieve` for context
2. RAG searches ChromaDB for similar incidents/techniques
3. Returns top-3 relevant documents
4. Alert Triage injects context into LLM prompt
5. LLM generates response grounded in verified knowledge

**OpenSearch → Log Summarization → ChromaDB:**
1. Log Summarization queries OpenSearch for logs (24 hours)
2. Parses logs with LibreLog
3. Batches logs by category
4. LLM generates executive summary
5. Stores summary in ChromaDB for RAG retrieval

---

## Deployment

### Docker Compose

**File:** `docker-compose/ai-services.yml`

```yaml
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-models:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  alert-triage:
    build: ./services/alert-triage
    ports:
      - "8000:8000"
    environment:
      - TRIAGE_OLLAMA_HOST=http://ollama:11434
      - TRIAGE_PRIMARY_MODEL=foundation-sec-8b
    depends_on:
      - ollama

  rag-service:
    build: ./services/rag-service
    ports:
      - "8001:8001"
    environment:
      - RAG_CHROMADB_HOST=chromadb
    depends_on:
      - chromadb

  log-summarization:
    build: ./services/log-summarization
    ports:
      - "8002:8002"
    environment:
      - SUMMARIZER_OLLAMA_HOST=http://ollama:11434
      - SUMMARIZER_OPENSEARCH_HOST=http://opensearch:9200
    depends_on:
      - ollama
      - opensearch

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - chromadb-data:/chroma/chroma

volumes:
  ollama-models:
  chromadb-data:
```

### Build and Run

```bash
# Build all services
cd services
docker-compose -f ../docker-compose/ai-services.yml build

# Start all services
docker-compose -f ../docker-compose/ai-services.yml up -d

# Check health
curl http://localhost:8000/health  # Alert Triage
curl http://localhost:8001/health  # RAG Service
curl http://localhost:8002/health  # Log Summarization

# View logs
docker-compose -f ../docker-compose/ai-services.yml logs -f alert-triage

# Stop all services
docker-compose -f ../docker-compose/ai-services.yml down
```

---

## Local Development

### Prerequisites

- Python 3.11+
- Docker
- Ollama (with models)
- OpenSearch (for log-summarization)
- ChromaDB (for RAG)

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/zhadyz/AI_SOC.git
cd AI_SOC/services

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies for all services
cd alert-triage && pip install -r requirements.txt && cd ..
cd log-summarization && pip install -r requirements.txt && cd ..
cd rag-service && pip install -r requirements.txt && cd ..

# Start Ollama
docker run -d -p 11434:11434 --name ollama ollama/ollama
docker exec ollama ollama pull llama3.1:8b

# Start ChromaDB
docker run -d -p 8000:8000 --name chromadb chromadb/chroma

# Run service (example: alert-triage)
cd alert-triage
python main.py  # Starts on http://localhost:8000
```

---

## Testing

### Unit Tests

Each service has its own test suite:

```bash
# Alert Triage tests
cd alert-triage
pytest tests/ -v --cov=.

# RAG Service tests
cd rag-service
pytest tests/ -v --cov=.

# Log Summarization tests
cd log-summarization
pytest tests/ -v --cov=.
```

### Integration Tests

```bash
# End-to-end workflow test
cd services
pytest tests/integration/ -v
```

### Performance Benchmarks

```bash
# Load testing with Locust
cd services
locust -f tests/load_test.py --host http://localhost:8000
```

**TODO: Week 4** - Implement comprehensive test suites

---

## Monitoring & Observability

### Prometheus Metrics

All services expose `/metrics` endpoint:

```bash
curl http://localhost:8000/metrics
```

**Key Metrics:**
- `{service}_requests_total` - Request count by status
- `{service}_request_duration_seconds` - Latency histogram
- `{service}_llm_requests_total` - LLM calls
- `{service}_llm_latency_seconds` - LLM inference time
- `{service}_errors_total` - Error count by type

### Grafana Dashboard

**TODO: Week 6** - Create Grafana dashboards

**Panels:**
1. Requests per second (by service)
2. P50/P95/P99 latency
3. LLM inference time
4. Error rate
5. Alert severity distribution
6. RAG retrieval quality

### Structured Logging

All logs are JSON-formatted for ELK Stack:

```json
{
  "timestamp": "2025-01-13T14:30:00Z",
  "service": "alert-triage",
  "level": "INFO",
  "logger": "llm_client",
  "message": "Alert analyzed successfully",
  "alert_id": "wazuh-001",
  "severity": "high",
  "confidence": 0.92
}
```

---

## Security Considerations

### Input Validation

All services validate inputs using `common/security.py`:

- Max length checks (10,000 characters)
- SQL injection detection
- Command injection detection
- Null byte filtering

### Prompt Injection Protection

LLM inputs are screened for injection attempts:

- System prompt override attempts
- Role switching ("you are now...")
- Jailbreak patterns ("DAN mode")
- Output manipulation requests

### Secrets Management

**Current:** Environment variables
**TODO: Week 8** - Integrate HashiCorp Vault

Never commit:
- API keys
- Passwords
- Ollama API tokens (if auth enabled)
- TheHive API keys

### Network Security

**TODO: Week 8** - Production hardening:
- TLS/SSL for all inter-service communication
- API key authentication
- Rate limiting per client
- WAF integration

---

## Performance Optimization

### Current Optimizations

1. **Async I/O:** Non-blocking HTTP calls with `httpx`
2. **Connection Pooling:** Reuse HTTP connections to Ollama
3. **Low Temperature:** Deterministic LLM outputs (0.1)
4. **Model Fallback:** Automatic retry with secondary model

### Future Optimizations (Week 6+)

- [ ] Batch processing with `asyncio.gather`
- [ ] Request queuing for high load
- [ ] GPU acceleration for Ollama
- [ ] Alert deduplication caching
- [ ] RAG result caching (1-hour TTL)

---

## Roadmap

### Week 4: Alert Triage MVP
- [x] Service scaffolding
- [ ] Ollama deployment (Foundation-Sec-8B)
- [ ] Shuffle integration
- [ ] Initial evaluation (50 alerts)

### Week 5: RAG Implementation
- [x] RAG service scaffolding
- [ ] ChromaDB deployment
- [ ] MITRE ATT&CK ingestion (3000+ techniques)
- [ ] RAG-enhanced alert triage
- [ ] Hallucination reduction measurement

### Week 6: Log Summarization
- [x] Log summarization scaffolding
- [ ] LibreLog integration
- [ ] OpenSearch query pipeline
- [ ] Daily summary automation
- [ ] BERTScore evaluation

### Week 7-8: Advanced Features
- [ ] Multi-agent collaboration (LangGraph)
- [ ] Report generation (AGIR)
- [ ] Security hardening
- [ ] Performance optimization

---

## Contributing

**TODO: Phase 5** - Open for community contributions

**Current Development:**
- Abdul Bari (abdul.bari8019@coyote.csusb.edu)
- CSUSB Cybersecurity Research

---

## References

### Research Papers

- **Foundation-Sec-8B:** https://arxiv.org/abs/2504.21039
- **LibreLog:** https://arxiv.org/abs/2408.01585
- **AGIR (Report Generation):** https://github.com/Mhackiori/AGIR
- **RAGAS (RAG Evaluation):** https://arxiv.org/abs/2309.15217

### Documentation

- **Ollama API:** https://github.com/ollama/ollama/blob/main/docs/api.md
- **ChromaDB:** https://docs.trychroma.com/
- **FastAPI:** https://fastapi.tiangolo.com/
- **MITRE ATT&CK:** https://attack.mitre.org/

### Tools & Frameworks

- **LangChain:** https://python.langchain.com/
- **sentence-transformers:** https://www.sbert.net/
- **Prometheus:** https://prometheus.io/docs/

---

## Troubleshooting

### Ollama Connection Failed

**Symptom:** `ollama_connected: false` in health check

**Solution:**
```bash
# Check if Ollama is running
docker ps | grep ollama

# Check logs
docker logs ollama

# Verify model is downloaded
docker exec ollama ollama list
```

### ChromaDB Initialization Failed

**Symptom:** RAG service errors on startup

**Solution:**
```bash
# Check ChromaDB status
docker ps | grep chroma

# Reset ChromaDB data (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d chromadb
```

### High Latency / Timeout

**Symptom:** Requests take >30 seconds

**Solution:**
- Check Ollama GPU usage: `nvidia-smi`
- Reduce `max_tokens` in config
- Use smaller model (Mistral 7B instead of LLaMA 8B)
- Enable batch processing

---

## License

**MIT License** - See LICENSE file

---

## Contact

**Project Lead:** Abdul Bari
**Email:** abdul.bari8019@coyote.csusb.edu
**GitHub:** https://github.com/zhadyz/AI_SOC

---

**Last Updated:** 2025-01-13
**Phase:** 3 (Weeks 4-5) - AI Layer Development
**Status:** Scaffolding Complete ✅
