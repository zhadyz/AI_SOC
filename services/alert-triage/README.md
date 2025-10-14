# Alert Triage Service

**AI-Augmented SOC - LLM-Powered Security Alert Analysis**

> Intelligent alert triage using Foundation-Sec-8B (Cisco's security-optimized LLM) to reduce analyst workload and accelerate threat detection.

---

## Overview

The Alert Triage Service is the core AI component of the AI-Augmented SOC platform. It receives security alerts from Wazuh (via Shuffle webhooks) and uses LLMs to:

- **Classify severity** (Critical/High/Medium/Low/Informational)
- **Identify attack categories** (Malware, Intrusion, Exfiltration, etc.)
- **Determine true/false positives** (Reduce alert fatigue)
- **Extract IOCs** (IPs, domains, file hashes)
- **Map to MITRE ATT&CK** (Techniques and tactics)
- **Generate recommendations** (Prioritized response actions)

**Performance Targets:**
- **Accuracy:** F1 Score >0.90
- **Confidence Threshold:** >0.80 for auto-escalation
- **Latency:** <10 seconds per alert
- **Throughput:** 250 alerts/day

---

## Architecture

```
┌─────────────┐        ┌─────────────┐        ┌──────────────┐
│   Wazuh     │──────> │   Shuffle   │──────> │ Alert Triage │
│   Manager   │ Alert  │    SOAR     │ Webhook│   Service    │
└─────────────┘        └─────────────┘        └──────┬───────┘
                                                      │
                                                      ▼
                                               ┌──────────────┐
                                               │    Ollama    │
                                               │ Foundation-  │
                                               │  Sec-8B      │
                                               └──────────────┘
```

**Data Flow:**
1. Wazuh detects security event → generates alert
2. Shuffle receives alert webhook → forwards to `/analyze` endpoint
3. LLM analyzes alert → returns structured JSON response
4. Shuffle routes alert to TheHive based on severity
5. Analyst reviews high-priority alerts with AI context

---

## API Endpoints

### `POST /analyze`

Analyze a single security alert.

**Request Body:**
```json
{
  "alert_id": "wazuh-001-20250113-1234",
  "timestamp": "2025-01-13T14:30:00Z",
  "rule_id": "5710",
  "rule_description": "Multiple failed SSH login attempts",
  "rule_level": 10,
  "source_ip": "203.0.113.42",
  "dest_ip": "10.0.1.50",
  "user": "admin",
  "raw_log": "Failed password for admin from 203.0.113.42"
}
```

**Response:**
```json
{
  "alert_id": "wazuh-001-20250113-1234",
  "severity": "high",
  "category": "intrusion_attempt",
  "confidence": 0.92,
  "summary": "Brute force SSH attack from 203.0.113.42 targeting admin account",
  "detailed_analysis": "Multiple failed authentication attempts indicate credential stuffing...",
  "is_true_positive": true,
  "iocs": [
    {"ioc_type": "ip", "value": "203.0.113.42", "confidence": 0.95}
  ],
  "mitre_techniques": ["T1110.001"],
  "mitre_tactics": ["TA0006"],
  "recommendations": [
    {
      "action": "Block source IP at firewall",
      "priority": 1,
      "rationale": "Prevent continued brute force attempts"
    }
  ],
  "investigation_priority": 2,
  "model_used": "foundation-sec-8b"
}
```

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "alert-triage",
  "version": "1.0.0",
  "ollama_connected": true,
  "timestamp": "2025-01-13T14:30:00Z"
}
```

### `GET /metrics`

Prometheus metrics for monitoring.

---

## Configuration

Environment variables (prefix: `TRIAGE_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `TRIAGE_OLLAMA_HOST` | `http://ollama:11434` | Ollama API endpoint |
| `TRIAGE_PRIMARY_MODEL` | `foundation-sec-8b` | Primary LLM model |
| `TRIAGE_FALLBACK_MODEL` | `llama3.1:8b` | Fallback model |
| `TRIAGE_LLM_TEMPERATURE` | `0.1` | Sampling temperature |
| `TRIAGE_HIGH_CONFIDENCE_THRESHOLD` | `0.85` | High confidence cutoff |
| `TRIAGE_AUTO_ACTION_THRESHOLD` | `0.80` | Auto-escalation threshold |
| `TRIAGE_LOG_LEVEL` | `INFO` | Logging verbosity |

**Example `.env` file:**
```bash
TRIAGE_OLLAMA_HOST=http://ollama:11434
TRIAGE_PRIMARY_MODEL=foundation-sec-8b
TRIAGE_LOG_LEVEL=DEBUG
```

---

## Local Development

### Prerequisites

- Python 3.11+
- Docker (for Ollama)
- Ollama with Foundation-Sec-8B or LLaMA 3.1

### Setup

1. **Install dependencies:**
   ```bash
   cd services/alert-triage
   pip install -r requirements.txt
   ```

2. **Start Ollama (separate terminal):**
   ```bash
   docker run -d -p 11434:11434 --name ollama ollama/ollama
   docker exec ollama ollama pull llama3.1:8b
   ```

3. **Run the service:**
   ```bash
   python main.py
   ```

4. **Test the API:**
   ```bash
   curl -X POST http://localhost:8000/analyze \
     -H "Content-Type: application/json" \
     -d '{
       "alert_id": "test-001",
       "rule_description": "SSH brute force detected",
       "rule_level": 10,
       "source_ip": "203.0.113.42"
     }'
   ```

### Docker Build

```bash
docker build -t ai-soc/alert-triage:latest .
docker run -p 8000:8000 \
  -e TRIAGE_OLLAMA_HOST=http://host.docker.internal:11434 \
  ai-soc/alert-triage:latest
```

---

## Testing

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Test specific module
pytest tests/test_llm_client.py -v
```

**TODO: Week 4** - Implement comprehensive test suite:
- Unit tests for prompt generation
- Mock Ollama responses
- Integration tests with real Ollama
- Performance benchmarks

---

## Prompt Engineering

### Design Principles

1. **Security-First Context:** Frame the task as SOC analyst work
2. **Structured Output:** Enforce JSON format with schema
3. **Evidence-Based:** Instruct model to cite evidence from logs
4. **Hallucination Prevention:** Explicitly forbid unsupported claims
5. **Confidence Scoring:** Request self-assessment of certainty

### Current Prompt Structure

```
You are an expert cybersecurity analyst...

TASK: Analyze the following security alert...

ALERT DETAILS:
[Structured alert information]

YOUR ANALYSIS MUST INCLUDE:
1. Severity Assessment
2. Category Classification
...

CRITICAL RULES:
- Base assessment ONLY on provided evidence
- Do NOT hallucinate IOCs
...

OUTPUT FORMAT (JSON):
{...}
```

**TODO: Week 4** - Iterate on prompt based on evaluation:
- A/B test different prompt structures
- Optimize for precision/recall trade-offs
- Add few-shot examples for edge cases

---

## Hallucination Mitigation

The service implements multiple strategies to reduce false information:

1. **Structured Prompting:** Explicitly forbid unsupported claims
2. **Confidence Thresholds:** Only auto-escalate if confidence >80%
3. **JSON Schema Validation:** Pydantic models enforce type safety
4. **RAG Integration (Week 5):** Ground responses in verified knowledge base

**Measured Hallucination Rate (Target):** <10%

---

## Performance Optimization

### Current Optimizations

- **Low Temperature (0.1):** Deterministic, consistent outputs
- **Async I/O:** Non-blocking Ollama API calls
- **Model Fallback:** Automatic retry with secondary model
- **Connection Pooling:** Reuse HTTP connections

### TODO: Week 4-5

- [ ] Implement batch processing (`asyncio.gather`)
- [ ] Add request queuing for high load
- [ ] GPU acceleration for Ollama (if available)
- [ ] Cache frequent alerts (deduplication)

---

## Integration with SOAR

### Shuffle Workflow

```yaml
Trigger: Wazuh Webhook
  ↓
HTTP POST → /analyze
  ↓
Condition: severity == "critical" OR "high"
  ↓
  Yes → Create TheHive case (priority: urgent)
  No  → Log to dashboard
```

**Shuffle Configuration:**

1. Add webhook receiver for Wazuh alerts
2. HTTP action: POST to `http://alert-triage:8000/analyze`
3. Conditional routing based on `response.severity`
4. TheHive action: Create case with AI analysis

---

## Monitoring & Observability

### Prometheus Metrics

- `triage_requests_total{status}` - Request count by status
- `triage_request_duration_seconds` - Latency histogram
- `triage_confidence_score` - Confidence distribution

### Grafana Dashboard (TODO: Week 6)

- Alerts processed per hour
- Average confidence scores
- Model success/failure rates
- Latency percentiles (p50, p95, p99)

---

## Security Considerations

### Input Validation

- All inputs validated via Pydantic schemas
- No SQL/command injection risk (stateless service)
- Logs treated as untrusted data

### Prompt Injection Protection

- User input sanitized before prompt construction
- LLM outputs parsed, never executed
- No shell commands generated by AI

### Secrets Management

- No API keys hardcoded in code
- Environment variables for sensitive config
- TODO: Week 8 - Integrate HashiCorp Vault

---

## Known Limitations

1. **Model Availability:** Requires Foundation-Sec-8B (not yet public)
   - **Mitigation:** Use LLaMA 3.1 8B as fallback
2. **Latency:** LLM inference takes 5-10 seconds
   - **Mitigation:** Batch processing, async workflows
3. **Hallucinations:** Model may generate false IOCs
   - **Mitigation:** RAG grounding (Week 5), confidence thresholds

---

## Roadmap

### Week 4 (Current Phase)
- [x] Service scaffolding complete
- [ ] Deploy Ollama with Foundation-Sec-8B
- [ ] Integration testing with Shuffle
- [ ] Initial accuracy evaluation (50 alerts)

### Week 5
- [ ] RAG integration (ChromaDB)
- [ ] Query similar incidents for context
- [ ] Hallucination reduction (<10%)

### Week 6+
- [ ] Batch processing optimization
- [ ] Custom fine-tuning on organization data
- [ ] Multi-model ensemble (vote aggregation)

---

## Contributing

**TODO: Phase 5** - Add contribution guidelines

For now, all development by Abdul Bari (abdul.bari8019@coyote.csusb.edu)

---

## References

- **Foundation-Sec-8B:** https://arxiv.org/abs/2504.21039
- **MITRE ATT&CK:** https://attack.mitre.org/
- **Ollama API Docs:** https://github.com/ollama/ollama/blob/main/docs/api.md

---

**Last Updated:** 2025-01-13
**Status:** Phase 3 (Week 4) - Development Ready
**Maintainer:** Abdul Bari
