# Alert Triage API Reference

LLM-powered security alert analysis service using Foundation-Sec-8B or LLaMA 3.1:8b for automated SOC triage and threat intelligence enrichment.

---

## Service Overview

| Property | Value |
|----------|-------|
| **Base URL** | `http://alert-triage:8000` (internal), `https://api.ai-soc.example.com:8100` (external) |
| **Protocol** | HTTP/HTTPS (REST) |
| **Content Type** | `application/json` |
| **Authentication** | API Key (Bearer token) or JWT |
| **Primary Model** | Foundation-Sec-8B (specialized for cybersecurity) |
| **Fallback Model** | LLaMA 3.1:8b (general-purpose reasoning) |
| **Latency** | 800ms-1.5s average (model-dependent) |
| **Throughput** | 45-60 alerts/minute |

---

## Authentication

All endpoints except `/health` and `/metrics` require authentication.

### API Key Authentication

```http
POST /analyze HTTP/1.1
Host: alert-triage:8000
Authorization: Bearer aisoc_<your-api-key>
Content-Type: application/json
```

### JWT Authentication

```http
POST /analyze HTTP/1.1
Host: alert-triage:8000
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

---

## Endpoints

### GET /health

Health check endpoint for service and dependency monitoring.

#### Request

```http
GET /health HTTP/1.1
Host: alert-triage:8000
```

#### Response

**Status**: `200 OK`

```json
{
  "status": "healthy",
  "service": "alert-triage",
  "version": "1.0.0",
  "ollama_connected": true,
  "ml_api_connected": false
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Service status: `healthy`, `degraded`, `unhealthy` |
| `service` | string | Service identifier |
| `version` | string | API version |
| `ollama_connected` | boolean | Whether Ollama LLM backend is reachable |
| `ml_api_connected` | boolean | Whether ML Inference API is available |

**Status Interpretation:**

- `healthy`: All dependencies operational
- `degraded`: Ollama unavailable, ML API may be degraded
- `partial`: LLM works but ML Inference is down

---

### GET /metrics

Prometheus metrics endpoint for monitoring LLM performance.

#### Request

```http
GET /metrics HTTP/1.1
Host: alert-triage:8000
```

#### Response

**Status**: `200 OK`
**Content-Type**: `text/plain; version=0.0.4`

```
# HELP triage_requests_total Total alert triage requests
# TYPE triage_requests_total counter
triage_requests_total{status="success"} 4523
triage_requests_total{status="failed"} 12

# HELP triage_request_duration_seconds Alert triage request duration
# TYPE triage_request_duration_seconds histogram
triage_request_duration_seconds_bucket{le="0.5"} 0
triage_request_duration_seconds_bucket{le="1.0"} 3245
triage_request_duration_seconds_bucket{le="2.0"} 4510
triage_request_duration_seconds_bucket{le="+Inf"} 4523
triage_request_duration_seconds_sum 5234.12
triage_request_duration_seconds_count 4523

# HELP triage_confidence_score LLM confidence scores
# TYPE triage_confidence_score histogram
triage_confidence_score_bucket{le="0.7"} 345
triage_confidence_score_bucket{le="0.8"} 1250
triage_confidence_score_bucket{le="0.9"} 3560
triage_confidence_score_bucket{le="+Inf"} 4523
```

**Metrics Exposed:**

- `triage_requests_total{status}`: Counter of triage requests by outcome
- `triage_request_duration_seconds`: Histogram of LLM analysis latency
- `triage_confidence_score`: Distribution of LLM confidence scores
- `ollama_model_switches_total`: Count of fallback activations

---

### POST /analyze

Analyze security alert using LLM reasoning and threat intelligence.

#### Request

```http
POST /analyze HTTP/1.1
Host: alert-triage:8000
Authorization: Bearer aisoc_<your-api-key>
Content-Type: application/json

{
  "alert_id": "wazuh-alert-2025102401234",
  "timestamp": "2025-10-24T10:15:30Z",
  "rule_id": "5710",
  "rule_level": 7,
  "rule_description": "Multiple authentication failures",
  "source_ip": "192.168.1.50",
  "destination_ip": "10.0.1.100",
  "source_port": 54321,
  "destination_port": 22,
  "protocol": "TCP",
  "agent_name": "web-server-01",
  "full_log": "Oct 24 10:15:30 web-server-01 sshd[12345]: Failed password for invalid user admin from 192.168.1.50 port 54321 ssh2",
  "raw_data": {
    "authentication_attempts": 15,
    "time_window_seconds": 60,
    "usernames_attempted": ["admin", "root", "user"]
  }
}
```

**Request Body Schema:**

```json
{
  "alert_id": {
    "type": "string",
    "required": true,
    "description": "Unique alert identifier from Wazuh"
  },
  "timestamp": {
    "type": "string",
    "format": "date-time",
    "required": true,
    "description": "Alert generation timestamp (ISO 8601)"
  },
  "rule_id": {
    "type": "string",
    "required": true,
    "description": "Wazuh rule identifier"
  },
  "rule_level": {
    "type": "integer",
    "minimum": 0,
    "maximum": 15,
    "required": true,
    "description": "Wazuh severity level (0-15)"
  },
  "rule_description": {
    "type": "string",
    "required": true,
    "description": "Human-readable rule description"
  },
  "source_ip": {
    "type": "string",
    "format": "ipv4/ipv6",
    "description": "Source IP address"
  },
  "destination_ip": {
    "type": "string",
    "format": "ipv4/ipv6",
    "description": "Destination IP address"
  },
  "full_log": {
    "type": "string",
    "description": "Complete log entry from source system"
  },
  "raw_data": {
    "type": "object",
    "description": "Additional context fields"
  }
}
```

#### Response (Success)

**Status**: `200 OK`

```json
{
  "alert_id": "wazuh-alert-2025102401234",
  "severity": "HIGH",
  "verdict": "True Positive",
  "confidence": 0.92,
  "threat_category": "Brute Force Attack",
  "mitre_techniques": [
    "T1110.001 - Brute Force: Password Guessing",
    "T1078 - Valid Accounts"
  ],
  "indicators_of_compromise": [
    {
      "type": "ipv4",
      "value": "192.168.1.50",
      "context": "Source IP attempting authentication",
      "threat_level": "HIGH"
    },
    {
      "type": "username",
      "value": "admin",
      "context": "Common target for brute force",
      "threat_level": "MEDIUM"
    }
  ],
  "recommendations": [
    "IMMEDIATE: Block source IP 192.168.1.50 at firewall",
    "SHORT-TERM: Implement fail2ban or equivalent on SSH service",
    "LONG-TERM: Enable multi-factor authentication for SSH access",
    "MONITORING: Review authentication logs for lateral movement"
  ],
  "analysis_reasoning": "Alert indicates systematic SSH brute force attack. Source IP attempted 15 failed authentication attempts in 60 seconds using common usernames (admin, root, user). Pattern consistent with automated credential stuffing or dictionary attack. Rule level 7 appropriate for threat severity.",
  "false_positive_likelihood": "LOW",
  "next_steps": [
    "Verify if source IP is internal (possible compromised host) or external",
    "Check TheHive for existing incidents involving 192.168.1.50",
    "Query threat intelligence feeds for IP reputation"
  ],
  "processing_time_ms": 1250,
  "model_used": "foundation-sec-8b:latest"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `alert_id` | string | Original alert identifier (echo) |
| `severity` | string | Assessed severity: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `verdict` | string | Classification: `True Positive`, `False Positive`, `Benign Positive`, `Needs Investigation` |
| `confidence` | float | LLM confidence score (0.0-1.0) |
| `threat_category` | string | Attack classification (e.g., "Brute Force", "Malware", "Reconnaissance") |
| `mitre_techniques` | array | Relevant MITRE ATT&CK techniques |
| `indicators_of_compromise` | array | Extracted IOCs with context |
| `recommendations` | array | Prioritized remediation actions |
| `analysis_reasoning` | string | LLM reasoning process (explainability) |
| `false_positive_likelihood` | string | FP probability: `LOW`, `MEDIUM`, `HIGH` |
| `next_steps` | array | Investigation procedures |
| `processing_time_ms` | integer | Analysis latency in milliseconds |
| `model_used` | string | LLM model identifier |

#### Response (Low Confidence - Requires Human Review)

**Status**: `200 OK` (with confidence < 0.7)

```json
{
  "alert_id": "wazuh-alert-2025102401235",
  "severity": "UNKNOWN",
  "verdict": "Needs Investigation",
  "confidence": 0.65,
  "threat_category": "UNCERTAIN",
  "analysis_reasoning": "Insufficient context to determine true/false positive. Alert pattern ambiguous - could be legitimate application behavior or reconnaissance activity.",
  "recommendations": [
    "ANALYST REVIEW REQUIRED: Manual analysis needed for verdict",
    "Gather additional context: user behavior history, application logs",
    "Correlate with network traffic analysis (Zeek/Suricata)"
  ],
  "low_confidence_reason": "Ambiguous log format, lack of historical baseline data",
  "processing_time_ms": 980,
  "model_used": "llama3.1:8b"
}
```

#### Response (Error - LLM Unavailable)

**Status**: `503 Service Unavailable`

```json
{
  "error": "LLM analysis failed",
  "detail": "All language models unavailable - Ollama service unreachable",
  "alert_id": "wazuh-alert-2025102401236",
  "retry_after": 60
}
```

---

### POST /batch

Batch analyze multiple alerts (up to 50 per request).

#### Request

```http
POST /batch HTTP/1.1
Host: alert-triage:8000
Authorization: Bearer aisoc_<your-api-key>
Content-Type: application/json

{
  "alerts": [
    {
      "alert_id": "wazuh-alert-001",
      "timestamp": "2025-10-24T10:15:30Z",
      "rule_id": "5710",
      ...
    },
    {
      "alert_id": "wazuh-alert-002",
      "timestamp": "2025-10-24T10:16:45Z",
      "rule_id": "5712",
      ...
    }
  ]
}
```

#### Response

**Status**: `501 Not Implemented` (Week 4 feature)

```json
{
  "error": "Not implemented",
  "detail": "Batch analysis not yet implemented - coming in Week 4",
  "expected_release": "2025-11-15"
}
```

**Planned Implementation (Week 4):**

- Concurrent processing with `asyncio.gather()`
- Throughput: 200-300 alerts/minute
- Automatic parallelization across available CPU cores

---

### GET /

API root endpoint with service information.

#### Request

```http
GET / HTTP/1.1
Host: alert-triage:8000
```

#### Response

**Status**: `200 OK`

```json
{
  "service": "alert-triage",
  "version": "1.0.0",
  "description": "LLM-powered security alert analysis for SOC automation",
  "endpoints": {
    "analyze": "/analyze",
    "batch": "/batch",
    "health": "/health",
    "metrics": "/metrics"
  },
  "models": {
    "primary": "foundation-sec-8b:latest",
    "fallback": "llama3.1:8b"
  },
  "documentation": "https://docs.ai-soc.example.com/api/alert-triage"
}
```

---

## Error Codes

| HTTP Status | Error Code | Description |
|-------------|-----------|-------------|
| 400 | `invalid_alert` | Alert validation failed (missing required fields) |
| 401 | `unauthorized` | Missing or invalid authentication |
| 429 | `rate_limit_exceeded` | Request quota exhausted |
| 503 | `llm_unavailable` | Ollama service unreachable |
| 500 | `internal_error` | Unexpected server error |

---

## Rate Limiting

| Profile | Default | Analyze Endpoint | Batch Endpoint |
|---------|---------|------------------|----------------|
| Strict | 30 req/min | 10 req/min | 5 req/min |
| Moderate | 100 req/min | 30 req/min | 10 req/min |
| Permissive | 300 req/min | 100 req/min | 50 req/min |

**Rate Limit Headers:**

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1698765432
```

---

## Example Usage

### Python (httpx - async)

```python
import httpx
import asyncio

async def analyze_alert():
    url = "http://alert-triage:8000/analyze"
    headers = {
        "Authorization": "Bearer aisoc_your_api_key",
        "Content-Type": "application/json"
    }

    alert = {
        "alert_id": "wazuh-001",
        "timestamp": "2025-10-24T10:15:30Z",
        "rule_id": "5710",
        "rule_level": 7,
        "rule_description": "Multiple authentication failures",
        "source_ip": "192.168.1.50",
        "destination_ip": "10.0.1.100",
        "destination_port": 22,
        "full_log": "Failed password for invalid user admin..."
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=alert, headers=headers)

        if response.status_code == 200:
            result = response.json()
            print(f"Verdict: {result['verdict']}")
            print(f"Severity: {result['severity']}")
            print(f"Confidence: {result['confidence']:.2f}")
            print(f"MITRE: {result['mitre_techniques']}")
            print(f"Recommendations: {result['recommendations']}")
        else:
            print(f"Error: {response.status_code} - {response.text}")

asyncio.run(analyze_alert())
```

### cURL

```bash
curl -X POST http://alert-triage:8000/analyze \
  -H "Authorization: Bearer aisoc_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "wazuh-001",
    "timestamp": "2025-10-24T10:15:30Z",
    "rule_id": "5710",
    "rule_level": 7,
    "rule_description": "Multiple authentication failures",
    "source_ip": "192.168.1.50",
    "destination_ip": "10.0.1.100",
    "destination_port": 22,
    "full_log": "Failed password for invalid user admin from 192.168.1.50 port 54321 ssh2"
  }'
```

### Shuffle Workflow Integration

```json
{
  "name": "Alert Triage - AI Analysis",
  "trigger": "wazuh_alert_received",
  "actions": [
    {
      "app": "HTTP",
      "function": "POST",
      "parameters": {
        "url": "http://alert-triage:8000/analyze",
        "headers": {
          "Authorization": "Bearer $workflow.secrets.aisoc_api_key",
          "Content-Type": "application/json"
        },
        "body": "$trigger.alert_data"
      }
    },
    {
      "app": "TheHive",
      "function": "create_case",
      "condition": "$action1.severity == 'HIGH' or $action1.severity == 'CRITICAL'",
      "parameters": {
        "title": "AI-Detected Threat: $trigger.rule_description",
        "description": "$action1.analysis_reasoning",
        "severity": "$action1.severity",
        "tags": "$action1.mitre_techniques",
        "tasks": "$action1.next_steps"
      }
    }
  ]
}
```

---

## LLM Model Information

### Foundation-Sec-8B (Primary Model)

**Specialization**: Cybersecurity threat analysis
**Parameters**: 8 billion
**Advantages**:
- Trained on security-specific datasets
- Understands MITRE ATT&CK framework
- Superior IOC extraction
- Context-aware threat classification

**Performance**:
- Avg latency: 800ms-1.2s
- Confidence (avg): 0.87
- True positive detection: 94%

### LLaMA 3.1:8b (Fallback Model)

**Specialization**: General-purpose reasoning
**Parameters**: 8 billion
**Advantages**:
- Faster inference (600ms-900ms)
- Robust fallback option
- Good contextual understanding

**Fallback Triggers**:
- Foundation-Sec-8B unavailable
- Foundation-Sec-8B timeout (>5s)
- Foundation-Sec-8B low confidence (<0.5)

---

## Integration with ML Inference API

When enabled (`ML_ENABLED=true`), the service integrates with ML Inference API for network flow classification.

### Workflow

```
┌────────────────┐
│  Wazuh Alert   │
└───────┬────────┘
        │
        ▼
┌──────────────────────┐
│ Alert Triage Service │
│  (LLM Analysis)      │
└───────┬──────────────┘
        │
        ├──────────────────┐
        │                  │
        ▼                  ▼
┌────────────────┐   ┌────────────────┐
│  LLM Reasoning │   │  ML Prediction │
│ (Foundation-Sec│   │  (Random Forest│
│  -8B/LLaMA)    │   │   CICIDS2017)  │
└───────┬────────┘   └───────┬────────┘
        │                    │
        └─────────┬──────────┘
                  │
                  ▼
        ┌──────────────────┐
        │ Unified Verdict  │
        │ (LLM + ML Fusion)│
        └──────────────────┘
```

### Enhanced Response (with ML)

```json
{
  "alert_id": "wazuh-001",
  "severity": "HIGH",
  "verdict": "True Positive",
  "confidence": 0.94,
  "llm_analysis": {
    "verdict": "True Positive",
    "confidence": 0.92,
    "reasoning": "..."
  },
  "ml_prediction": {
    "verdict": "ATTACK",
    "confidence": 0.9856,
    "model": "random_forest_cicids2017"
  },
  "consensus_verdict": "CONFIRMED TRUE POSITIVE (LLM + ML Agreement)"
}
```

---

## Production Considerations

### Scaling

**Horizontal Scaling:**
```yaml
# docker-compose.yml
services:
  alert-triage:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
```

**Throughput:**
- Single instance: 45-60 alerts/minute
- 3 replicas: 135-180 alerts/minute
- With batch processing (Week 4): 200-300 alerts/minute per instance

### Ollama Configuration

**GPU Acceleration (Recommended):**
```yaml
services:
  ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

**Multi-Model Loading:**
```bash
# Pre-load models for faster switching
docker exec ollama ollama pull foundation-sec:8b
docker exec ollama ollama pull llama3.1:8b
```

### Monitoring

**Prometheus Alerts:**

```yaml
groups:
  - name: alert_triage
    rules:
      - alert: HighLLMLatency
        expr: histogram_quantile(0.95, triage_request_duration_seconds_bucket) > 3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "95th percentile LLM latency > 3s"

      - alert: LowConfidenceRate
        expr: rate(triage_confidence_score_bucket{le="0.7"}[5m]) > 0.3
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: ">30% of analyses have low confidence"
```

---

## Changelog

### Version 1.0.0 (Current)

- Initial production release
- Foundation-Sec-8B integration
- LLaMA 3.1:8b fallback
- Single alert analysis (`/analyze`)
- MITRE ATT&CK mapping
- IOC extraction
- Prometheus metrics

### Version 1.1.0 (Planned - Week 4)

- Batch processing (`/batch` endpoint)
- Concurrent analysis (200-300 alerts/min)
- Enhanced RAG integration
- Historical context awareness
- Automated playbook suggestions

---

## Support

**API Issues**: api-support@ai-soc.example.com
**LLM Questions**: llm-team@ai-soc.example.com
**Documentation**: https://docs.ai-soc.example.com/api/alert-triage

---

**Document Version**: 1.0
**Last Updated**: October 24, 2025
**Maintained By**: AI-SOC LLM Team
