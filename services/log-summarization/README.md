# Log Summarization Service

**AI-Augmented SOC - Automated Security Log Analysis**

> Transform thousands of security logs into actionable intelligence with LLM-powered summarization.

---

## Overview

The Log Summarization Service processes large volumes of security logs from OpenSearch and generates human-readable summaries using LLaMA 3.1 8B. It provides daily security briefings, trend analysis, and threat intelligence extraction.

**Key Features:**
- **Batch Processing:** Handle 1000+ logs per summary
- **LibreLog Integration:** Automatic log parsing and normalization
- **LLM Summarization:** Generate executive-friendly briefings
- **ChromaDB Storage:** Store summaries for RAG retrieval
- **Scheduled Tasks:** Automated daily/weekly summaries

**Performance Targets:**
- **BERTScore:** >0.85 (semantic similarity)
- **Processing Speed:** 1M+ logs/day
- **Time Savings:** 42%+ vs manual review

---

## Architecture

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  OpenSearch  │─────>│ Log Parser   │─────>│ LLM Summarizer│
│  (Wazuh Logs)│Query │ (LibreLog)   │Parse │ (LLaMA 3.1)  │
└──────────────┘      └──────────────┘      └──────┬───────┘
                                                    │
                                                    ▼
                                             ┌──────────────┐
                                             │  ChromaDB    │
                                             │  (Vector DB) │
                                             └──────────────┘
```

**Data Flow:**
1. Query OpenSearch for logs in time range (e.g., last 24 hours)
2. Parse and normalize logs using LibreLog
3. Aggregate logs by category (auth, network, file, etc.)
4. Generate LLM summary with key events and recommendations
5. Store summary in ChromaDB for RAG retrieval
6. Deliver summary via email/Slack/dashboard

---

## API Endpoints

### `POST /summarize`

Generate summary for specified time range.

**Request:**
```json
{
  "time_range_hours": 24,
  "log_source": "wazuh",
  "max_logs": 1000
}
```

**Response:**
```json
{
  "summary_id": "summary-20250113-001",
  "time_range": "Last 24 hours",
  "log_count": 856,
  "summary": "Overall security posture is stable. Detected 3 SSH brute force attempts (blocked), 1 port scan from 203.0.113.42, and routine policy violations. No critical incidents.",
  "key_events": [
    "SSH brute force from 203.0.113.42 (blocked after 15 attempts)",
    "Port scan detected on DMZ segment",
    "3 failed VPN authentications from unknown device"
  ],
  "threat_indicators": [
    "203.0.113.42 (brute force source)",
    "198.51.100.10 (port scanner)"
  ],
  "recommendations": [
    "Investigate 203.0.113.42 for botnet activity",
    "Review VPN authentication policies",
    "Update firewall rules for DMZ"
  ],
  "generated_at": "2025-01-13T08:00:00Z"
}
```

### `POST /summarize/daily`

Trigger automated daily summary (called by cron).

### `GET /summaries`

List recent summaries.

---

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SUMMARIZER_OPENSEARCH_HOST` | `http://opensearch:9200` | OpenSearch endpoint |
| `SUMMARIZER_OLLAMA_HOST` | `http://ollama:11434` | Ollama API endpoint |
| `SUMMARIZER_MODEL` | `llama3.1:8b` | LLM model |
| `SUMMARIZER_CHROMADB_HOST` | `http://chromadb:8000` | ChromaDB endpoint |
| `SUMMARIZER_BATCH_SIZE` | `1000` | Logs per batch |

---

## LibreLog Integration

**LibreLog** (https://arxiv.org/abs/2408.01585) is a research framework for log parsing using LLMs.

**Key Features:**
- Automatic log format detection
- Field extraction without regex patterns
- Normalization to common schema
- Timestamp parsing

**Integration Plan (Week 6):**
1. Fork LibreLog repository
2. Dockerize for production use
3. Configure for LLaMA 3.1 8B
4. Benchmark parsing accuracy

**Example Usage:**
```python
from librelog import LogParser

parser = LogParser(model="llama3.1:8b")
parsed = parser.parse("Jan 13 10:15:30 sshd[1234]: Failed password for admin")

# Output:
# {
#   'timestamp': '2025-01-13T10:15:30',
#   'service': 'sshd',
#   'event_type': 'authentication_failure',
#   'user': 'admin'
# }
```

---

## Scheduled Summaries

### Daily Summary (8:00 AM)

Automated daily briefing sent to security team:
- Previous 24 hours
- Top 10 security events
- Threat indicators
- Recommendations

**Delivery Methods:**
- Email digest (HTML format)
- Slack/Discord notification
- Dashboard widget

### Weekly Summary (Monday 9:00 AM)

Executive-level weekly report:
- 7-day trend analysis
- Critical incidents recap
- Risk metrics
- Strategic recommendations

---

## ChromaDB Storage

Summaries are stored in ChromaDB for RAG retrieval:

**Collection Schema:**
```python
{
  "id": "summary-20250113-001",
  "document": "Overall security posture is stable...",
  "metadata": {
    "timestamp": "2025-01-13T08:00:00Z",
    "log_count": 856,
    "time_range": "24h",
    "severity": "low"
  }
}
```

**RAG Use Cases:**
- "What similar security incidents occurred last week?"
- "Show me all summaries mentioning brute force"
- "What were the top threats in December?"

---

## Evaluation Metrics

### BERTScore

Measures semantic similarity between generated and reference summaries:

```python
from bert_score import score

generated = "Detected 3 SSH brute force attempts..."
reference = "Multiple SSH authentication failures observed..."

P, R, F1 = score([generated], [reference], lang="en")
print(f"BERTScore F1: {F1.mean():.3f}")  # Target: >0.85
```

### Human Evaluation

5 security analysts review summaries:
- **Completeness:** Are key events included?
- **Accuracy:** Are facts correct?
- **Actionability:** Are recommendations useful?
- **Clarity:** Is it easy to understand?

**Target:** >4.0/5.0 average rating

---

## Local Development

### Prerequisites

- Python 3.11+
- Docker
- OpenSearch (for testing)
- Ollama with LLaMA 3.1 8B

### Setup

1. **Install dependencies:**
   ```bash
   cd services/log-summarization
   pip install -r requirements.txt
   ```

2. **Start dependencies:**
   ```bash
   docker run -d -p 9200:9200 opensearchproject/opensearch:latest
   docker run -d -p 11434:11434 ollama/ollama
   docker exec ollama ollama pull llama3.1:8b
   ```

3. **Run service:**
   ```bash
   python main.py
   ```

4. **Test API:**
   ```bash
   curl -X POST http://localhost:8002/summarize \
     -H "Content-Type: application/json" \
     -d '{"time_range_hours": 24, "log_source": "wazuh"}'
   ```

---

## Testing

```bash
# Unit tests
pytest tests/ -v

# Integration tests (requires OpenSearch)
pytest tests/integration/ -v

# Benchmark BERTScore
pytest tests/test_bertscore.py -v
```

**TODO: Week 6** - Implement test suite:
- Mock OpenSearch responses
- Test LibreLog integration
- Benchmark summarization quality
- Load testing (1M+ logs)

---

## Known Limitations

1. **LibreLog Dependency:** Research code requires productionization
   - **Mitigation:** Fork and containerize in Week 6
2. **Processing Latency:** Summarizing 1000 logs takes 30-60 seconds
   - **Mitigation:** Batch processing, async workers
3. **Hallucination Risk:** LLM may invent events
   - **Mitigation:** Structured prompts, fact verification

---

## Roadmap

### Week 6 (Target Phase)
- [ ] OpenSearch integration
- [ ] LibreLog parsing
- [ ] LLM summarization pipeline
- [ ] ChromaDB storage
- [ ] BERTScore evaluation

### Week 7+
- [ ] Scheduled daily summaries
- [ ] Email/Slack delivery
- [ ] Dashboard widgets
- [ ] Multi-language support (Spanish, etc.)

---

## Contributing

**TODO: Phase 5** - Open for contributions

---

## References

- **LibreLog Paper:** https://arxiv.org/abs/2408.01585
- **BERTScore:** https://github.com/Tiiiger/bert_score
- **OpenSearch:** https://opensearch.org/docs/latest/

---

**Last Updated:** 2025-01-13
**Status:** Scaffolded - Implementation in Week 6
**Maintainer:** Abdul Bari
