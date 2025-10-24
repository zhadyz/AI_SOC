# Component Design

Detailed technical specifications for all AI-SOC platform components.

---

## Overview

The AI-SOC platform consists of 35+ containerized services organized into five integrated stacks. This document provides comprehensive technical specifications, configuration details, and operational characteristics for each component.

---

## SIEM Stack Components

### Wazuh Manager

**Purpose:** Central log aggregation, correlation engine, and threat detection system.

**Technical Specifications:**
- **Version:** 4.8.2
- **Base Image:** wazuh/wazuh:4.8.2
- **Container Resources:**
  - Memory Limit: 2GB
  - CPU Limit: 2.0 cores
  - Memory Reservation: 1GB
- **Ports:**
  - 1514/TCP: Agent communication (TLS)
  - 1515/TCP: Agent enrollment
  - 514/UDP: Syslog reception
  - 55000/TCP: REST API

**Key Features:**
- **Rule-Based Correlation:** 3,000+ built-in detection rules
- **File Integrity Monitoring:** Real-time file change detection
- **Vulnerability Detection:** CVE database integration
- **Compliance Modules:** PCI-DSS, HIPAA, GDPR, NIST
- **Active Response:** Automated blocking capabilities

**Configuration Files:**
- `/var/ossec/etc/ossec.conf` - Main configuration
- `/var/ossec/etc/rules/` - Detection rules
- `/var/ossec/etc/decoders/` - Log parsing decoders

**Performance:**
- Events Processing: 15,000/second sustained
- Agent Capacity: 10,000 agents per manager
- API Response Time: <100ms (p95)

**Health Checks:**
```bash
# Container health
docker exec wazuh-manager /var/ossec/bin/wazuh-control status

# API health
curl -u admin:password https://localhost:55000/
```

**Operational Notes:**
- Requires 5-10 minutes for full initialization
- Auto-restart enabled for resilience
- Logs stored in `/var/ossec/logs/`

---

### Wazuh Indexer

**Purpose:** Distributed search and analytics engine based on OpenSearch.

**Technical Specifications:**
- **Version:** 4.8.2 (OpenSearch 2.x)
- **Base Image:** wazuh/wazuh-indexer:4.8.2
- **Container Resources:**
  - Memory Limit: 4GB
  - JVM Heap: 2GB (-Xms2g -Xmx2g)
  - CPU Limit: 2.0 cores
- **Ports:**
  - 9200/TCP: REST API (HTTPS)
  - 9300/TCP: Inter-node communication
  - 9600/TCP: Performance analyzer

**Key Features:**
- **Distributed Storage:** Horizontal scaling with sharding
- **Full-Text Search:** Lucene-based inverted index
- **Aggregations:** Real-time analytics and statistics
- **Index Lifecycle Management:** Hot/warm/cold tier optimization
- **Snapshots:** Incremental backups to S3/filesystem

**Configuration:**
```yaml
# opensearch.yml
cluster.name: wazuh-cluster
node.name: wazuh-indexer
network.host: 0.0.0.0
discovery.type: single-node  # Multi-node for production
plugins.security.ssl.http.enabled: true
```

**Index Templates:**
- `wazuh-alerts-*` - Security alerts (daily indices)
- `wazuh-archives-*` - Raw event archives
- `wazuh-monitoring-*` - Agent health metrics

**Performance:**
- Indexing Rate: 50,000 events/second (single node)
- Query Latency: <500ms (90th percentile)
- Storage Compression: 10:1 ratio
- Shard Size: 30-50GB optimal

**Cluster Scaling:**
```
Single Node:     10,000 events/sec
3-Node Cluster:  50,000 events/sec
5-Node Cluster: 100,000 events/sec
```

**Maintenance:**
```bash
# Check cluster health
curl -u admin:password https://localhost:9200/_cluster/health?pretty

# Force merge old indices (reduce storage)
curl -X POST "https://localhost:9200/wazuh-alerts-2024.10.*/_forcemerge?max_num_segments=1"

# Delete old indices
curl -X DELETE "https://localhost:9200/wazuh-alerts-2024.09.*"
```

---

### Wazuh Dashboard

**Purpose:** Web-based visualization and investigation interface.

**Technical Specifications:**
- **Version:** 4.8.2 (Kibana fork)
- **Base Image:** wazuh/wazuh-dashboard:4.8.2
- **Container Resources:**
  - Memory Limit: 1GB
  - CPU Limit: 1.0 core
- **Ports:**
  - 443/TCP: HTTPS web interface (maps to 5601 internally)

**Key Features:**
- **Pre-built Dashboards:** Security overview, compliance, vulnerability
- **Discover Interface:** Ad-hoc log search and filtering
- **Dev Tools:** Direct OpenSearch API access
- **MITRE ATT&CK Visualization:** Attack technique mapping
- **Reporting:** PDF/CSV export capabilities

**Default Credentials:**
- Username: `admin`
- Password: `admin` (change immediately)

**Configuration:**
```yaml
# opensearch_dashboards.yml
server.host: "0.0.0.0"
server.port: 5601
opensearch.hosts: ["https://wazuh-indexer:9200"]
opensearch.ssl.verificationMode: none
wazuh.api.url: "https://wazuh-manager"
```

**User Management:**
- RBAC via OpenSearch Security plugin
- LDAP/Active Directory integration supported
- SAML SSO for enterprise authentication

---

## AI Services Components

### ML Inference API

**Purpose:** High-performance machine learning inference engine for intrusion detection.

**Technical Specifications:**
- **Framework:** scikit-learn 1.3+
- **API Framework:** FastAPI 0.100+
- **Base Image:** Custom (Python 3.11-slim)
- **Container Resources:**
  - Memory Limit: 1GB
  - CPU Limit: 1.0 core
  - Memory Reservation: 512MB
- **Ports:**
  - 8500/TCP: REST API (maps to 8000 internally)

**Loaded Models:**
1. **Random Forest (Primary)**
   - File: `random_forest_ids.pkl`
   - Size: 2.93MB
   - Accuracy: 99.28%
   - Inference Time: 0.8ms

2. **XGBoost (Low False Positive)**
   - File: `xgboost_ids.pkl`
   - Size: 0.18MB
   - Accuracy: 99.21%
   - Inference Time: 0.3ms

3. **Decision Tree (Interpretable)**
   - File: `decision_tree_ids.pkl`
   - Size: 0.03MB
   - Accuracy: 99.10%
   - Inference Time: 0.2ms

**Supporting Files:**
- `scaler.pkl` - StandardScaler for feature normalization
- `label_encoder.pkl` - Label encoding (BENIGN/ATTACK)
- `feature_names.pkl` - 79 CICIDS2017 features

**API Endpoints:**
```
POST /predict
  Body: {
    "features": [79 numerical values],
    "model_name": "random_forest"  # or "xgboost", "decision_tree"
  }
  Response: {
    "prediction": "ATTACK",
    "confidence": 0.9856,
    "model": "random_forest",
    "inference_time_ms": 0.8
  }

GET /health
  Response: {
    "status": "healthy",
    "models_loaded": 3,
    "uptime_seconds": 3600
  }

GET /docs - OpenAPI interactive documentation
GET /metrics - Prometheus metrics endpoint
```

**Performance Characteristics:**
- Throughput: 1,250 predictions/second (single container)
- Latency: 0.8ms average, 1.8ms p99
- Memory Usage: ~300MB steady-state
- Model Loading Time: <2 seconds

**Health Check:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

**Environment Variables:**
- `MODEL_PATH=/app/models` - Model directory path
- `LOG_LEVEL=INFO` - Logging verbosity

**Scaling:**
- Stateless design enables horizontal scaling
- Place behind load balancer for production
- GPU acceleration not required (CPU-optimized models)

---

### Alert Triage Service

**Purpose:** LLM-powered alert analysis and prioritization.

**Technical Specifications:**
- **LLM:** LLaMA 3.1:8b via Ollama
- **API Framework:** FastAPI 0.100+
- **Container Resources:**
  - Memory Limit: 2GB
  - CPU Limit: 2.0 cores
- **Ports:**
  - 8100/TCP: REST API

**Dependencies:**
- ML Inference API (http://ml-inference:8000)
- RAG Service (http://rag-service:8000)
- Ollama Server (http://ollama-server:11434)

**Key Capabilities:**
1. **Risk Scoring:** 0-100 scale based on multiple factors
2. **Attack Classification:** Maps alerts to attack types
3. **MITRE Mapping:** Identifies applicable ATT&CK techniques
4. **Response Recommendations:** Suggests containment actions
5. **Executive Summaries:** Natural language explanations

**API Endpoints:**
```
POST /triage
  Body: {
    "alert_data": {
      "rule_id": 100001,
      "src_ip": "192.168.1.100",
      "dst_ip": "10.0.0.50",
      "protocol": "TCP",
      "payload": "..."
    }
  }
  Response: {
    "risk_score": 85,
    "classification": "Brute Force Attack",
    "mitre_techniques": ["T1110.001", "T1078"],
    "recommended_actions": ["Block source IP", "Force password reset"],
    "summary": "High-confidence brute force attack detected...",
    "ml_prediction": "ATTACK",
    "ml_confidence": 0.9828
  }

GET /health
  Response: {"status": "healthy", "llm_loaded": true}
```

**Processing Pipeline:**
```
Alert → ML Classification (BENIGN/ATTACK)
     → RAG Retrieval (MITRE context)
     → LLM Analysis (natural language reasoning)
     → Risk Score Calculation
     → Response: Enriched alert
```

**Performance:**
- Latency: 2-5 seconds (LLM inference dominant)
- Throughput: 10-20 alerts/minute (single instance)
- Token Usage: ~500 tokens per alert

**Environment Variables:**
- `TRIAGE_OLLAMA_HOST=http://ollama-server:11434`
- `TRIAGE_PRIMARY_MODEL=llama3.1:8b`
- `ML_INFERENCE_URL=http://ml-inference:8000`
- `RAG_SERVICE_URL=http://rag-service:8000`

---

### RAG Service

**Purpose:** Retrieval-Augmented Generation for cyber threat intelligence.

**Technical Specifications:**
- **Vector Database:** ChromaDB
- **Embeddings:** sentence-transformers/all-MiniLM-L6-v2
- **API Framework:** FastAPI 0.100+
- **Container Resources:**
  - Memory Limit: 1GB
  - CPU Limit: 1.0 core
- **Ports:**
  - 8300/TCP: REST API

**Knowledge Base:**
- **MITRE ATT&CK:** 823 techniques across 14 tactics
- **Embedding Dimensions:** 384 (MiniLM-L6)
- **Total Vectors:** 823
- **Storage Size:** ~15MB

**API Endpoints:**
```
POST /retrieve
  Body: {
    "query": "lateral movement via SMB",
    "top_k": 5,
    "threshold": 0.7
  }
  Response: {
    "results": [
      {
        "technique_id": "T1021.002",
        "technique_name": "Remote Services: SMB/Windows Admin Shares",
        "similarity_score": 0.89,
        "description": "Adversaries may use Valid Accounts to interact with...",
        "tactics": ["Lateral Movement"],
        "platforms": ["Windows"]
      },
      ...
    ],
    "retrieval_time_ms": 45
  }

GET /health
  Response: {"status": "healthy", "vector_count": 823}
```

**Performance:**
- Query Latency: <50ms for top-5 retrieval
- Vector Search: Cosine similarity
- Throughput: 100+ queries/second

**Data Ingestion:**
```python
# Initial population from MITRE ATT&CK JSON
POST /ingest
  Body: {
    "techniques": [ ... MITRE ATT&CK JSON ... ]
  }
```

**Environment Variables:**
- `RAG_CHROMADB_HOST=chromadb`
- `RAG_CHROMADB_PORT=8000`
- `RAG_COLLECTION_NAME=mitre_attack`

---

### ChromaDB

**Purpose:** AI-native vector database for semantic search.

**Technical Specifications:**
- **Version:** Latest
- **Image:** chromadb/chroma:latest
- **Container Resources:**
  - Memory Limit: 2GB
  - CPU Limit: 1.0 core
- **Ports:**
  - 8200/TCP: HTTP API (maps to 8000 internally)

**Storage:**
- Volume: `chromadb-data:/chroma/chroma`
- Persistence: Persistent across restarts
- Size: ~20MB (823 MITRE techniques)

**API:**
```
GET /api/v1/heartbeat - Health check
GET /api/v1/collections - List collections
POST /api/v1/collections/{name}/query - Semantic search
```

**Performance:**
- Vector Indexing: HNSW algorithm
- Query Latency: <10ms for nearest neighbors
- Scalability: Millions of vectors supported

---

### Ollama Server

**Purpose:** Local LLM inference runtime.

**Technical Specifications:**
- **Version:** Latest
- **Image:** ollama/ollama:latest
- **Loaded Model:** LLaMA 3.1:8b
- **Container Resources:**
  - Memory Limit: 8GB (model size: ~4.7GB)
  - CPU Limit: 4.0 cores
  - GPU: Optional (CUDA support)
- **Ports:**
  - 11434/TCP: HTTP API

**Model Specifications:**
- **Parameters:** 8 billion
- **Quantization:** Q4_0 (4-bit)
- **Context Window:** 8,192 tokens
- **Model Size:** ~4.7GB

**API:**
```
POST /api/generate
  Body: {
    "model": "llama3.1:8b",
    "prompt": "Analyze this security alert...",
    "stream": false
  }
  Response: {
    "response": "This appears to be a brute force attack...",
    "tokens_evaluated": 1024,
    "eval_duration": 2500000000  # nanoseconds
  }
```

**Performance:**
- Tokens/Second: 15-25 (CPU), 50-100 (GPU)
- Latency: 2-5 seconds for 200-token response
- Concurrent Requests: 1 (sequential processing)

**Model Management:**
```bash
# List models
docker exec ollama-server ollama list

# Pull new model
docker exec ollama-server ollama pull llama3.1:70b

# Delete model
docker exec ollama-server ollama rm llama3.1:8b
```

---

## SOAR Stack Components

### TheHive

**Purpose:** Collaborative security incident response platform.

**Technical Specifications:**
- **Version:** 5.2.9
- **Image:** strangebee/thehive:5.2.9
- **Container Resources:**
  - Memory Limit: 2GB
  - CPU Limit: 2.0 cores
- **Ports:**
  - 9010/TCP: Web UI and API

**Backend Dependencies:**
- **Cassandra 4.1.3** - Primary database
- **MinIO** - File attachment storage (S3-compatible)

**Key Features:**
- **Case Management:** Multi-analyst collaboration
- **Observables:** IOCs, hashes, IPs, domains
- **Tasks:** Actionable investigation steps
- **Cortex Integration:** Automated analysis
- **Webhooks:** Bidirectional Wazuh/Shuffle integration
- **Templates:** Predefined case types

**Configuration:**
```hocon
# application.conf
db {
  provider: janusgraph
  janusgraph {
    storage.backend: cql
    storage.hostname: ["cassandra"]
    storage.cql.keyspace: thehive
  }
}

storage {
  provider: s3
  s3 {
    endpoint: "http://minio:9000"
    bucket: "thehive"
    access-key: "minioadmin"
    secret-key: "minioadmin"
  }
}

cortex {
  servers: [
    {
      name: local
      url: "http://cortex:9001"
      auth {
        type: "bearer"
        key: "API_KEY"
      }
    }
  ]
}
```

**Default Credentials:**
- Email: `admin@thehive.local`
- Password: `secret` (change immediately)

**API Usage:**
```bash
# Create case from Wazuh alert
curl -X POST http://localhost:9010/api/v1/case \
  -H "Authorization: Bearer API_KEY" \
  -d '{
    "title": "Suspicious Login",
    "description": "Multiple failed login attempts detected",
    "severity": 3,
    "tlp": 2,
    "pap": 2
  }'
```

**Performance:**
- Case Creation: <500ms
- Search Query: <1s (100K cases)
- Concurrent Users: 50+

---

### Cortex

**Purpose:** Observable analysis engine.

**Technical Specifications:**
- **Version:** 3.1.7
- **Image:** thehiveproject/cortex:3.1.7
- **Container Resources:**
  - Memory Limit: 1.5GB
  - CPU Limit: 2.0 cores
- **Ports:**
  - 9011/TCP: Web UI and API

**Analyzers (100+ available):**
- **Threat Intelligence:** VirusTotal, AbuseIPDB, OTX
- **File Analysis:** ClamAV, Yara, PEInfo
- **Network:** Shodan, MaxMind GeoIP, DomainTools
- **OSINT:** Google SafeBrowsing, PhishTank

**Responders:**
- **Firewall:** Block IP, add to blacklist
- **EDR:** Isolate host, kill process
- **Notification:** Email, Slack, PagerDuty

**Configuration:**
```hocon
# application.conf
analyzer {
  urls: [
    "https://download.thehive-project.org/analyzers.json"
  ]
}

responder {
  urls: [
    "https://download.thehive-project.org/responders.json"
  ]
}

job {
  runner: docker
  dockerJob {
    baseImage: python:3.11-alpine
  }
}
```

**Usage:**
```bash
# Run IP reputation analyzer
curl -X POST http://localhost:9011/api/analyzer/AbuseIPDB/run \
  -H "Authorization: Bearer API_KEY" \
  -d '{
    "data": "8.8.8.8",
    "dataType": "ip",
    "tlp": 2,
    "pap": 2
  }'
```

---

### Shuffle

**Purpose:** Security workflow automation and orchestration.

**Technical Specifications:**
- **Version:** 1.4.0
- **Components:**
  - Frontend: Port 3001
  - Backend: Port 5001
  - Orborus (Worker): Background execution
- **Database:** OpenSearch 2.11.1
- **Container Resources:**
  - Frontend: 512MB RAM
  - Backend: 1GB RAM
  - Orborus: 512MB RAM

**Key Features:**
- **Drag-and-Drop Workflows:** No-code playbook creation
- **100+ Integrations:** TheHive, Cortex, Slack, Email, AWS
- **Webhook Triggers:** Event-driven automation
- **Conditional Logic:** If/else branching
- **Data Transformation:** JSON parsing, filtering
- **Scheduling:** Cron-based execution

**Workflow Example:**
```yaml
Trigger: Wazuh Alert (High Severity)
  ↓
Action 1: Create TheHive Case
  ↓
Action 2: Run Cortex Analyzers (IP reputation, geo-location)
  ↓
Condition: If IOC is malicious
  ↓ (True)
  Action 3: Block IP on Firewall
  Action 4: Send Slack Notification
  ↓ (False)
  Action 5: Create Low-Priority Ticket
```

**API:**
```bash
# Trigger workflow via webhook
curl -X POST http://localhost:5001/api/v1/hooks/webhook_id \
  -H "Content-Type: application/json" \
  -d '{"alert_data": {...}}'
```

**Performance:**
- Workflow Execution: <2 seconds (simple), <30 seconds (complex)
- Concurrent Workflows: 10+
- Orborus Workers: Scalable (add more workers for parallelism)

---

## Monitoring Stack Components

### Prometheus

**Purpose:** Time-series metrics database and alerting engine.

**Technical Specifications:**
- **Version:** 2.48.0
- **Image:** prom/prometheus:v2.48.0
- **Container Resources:**
  - Memory Limit: 2GB
  - CPU Limit: 1.0 core
- **Ports:**
  - 9090/TCP: Web UI and API

**Scrape Targets (13):**
1. Prometheus itself (9090)
2. Node Exporter (9100) - Host metrics
3. cAdvisor (8080) - Container metrics
4. Wazuh Manager (55000) - SIEM metrics
5. Wazuh Indexer (9200) - Database metrics
6. TheHive (9010) - SOAR metrics
7. Cortex (9011) - Analysis metrics
8. ML Inference (8500) - AI service metrics
9. Alert Triage (8100)
10. RAG Service (8300)
11. ChromaDB (8200)
12. Grafana (3000)
13. AlertManager (9093)

**Configuration:**
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ml-inference'
    static_configs:
      - targets: ['ml-inference:8000']
    metrics_path: /metrics
```

**Alert Rules:**
```yaml
# alerts/ai-soc-alerts.yml
groups:
  - name: services
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.job }} is down"

      - alert: HighMemoryUsage
        expr: (container_memory_usage_bytes / container_spec_memory_limit_bytes) > 0.9
        for: 5m
        labels:
          severity: warning
```

**Performance:**
- Metrics Ingestion: 100,000 samples/second
- Query Latency: <100ms (simple), <1s (complex)
- Retention: 30 days (configurable)
- Storage: ~1GB per million samples

---

### Grafana

**Purpose:** Metrics visualization and dashboarding.

**Technical Specifications:**
- **Version:** 10.2.2
- **Image:** grafana/grafana:10.2.2
- **Container Resources:**
  - Memory Limit: 512MB
  - CPU Limit: 0.5 core
- **Ports:**
  - 3000/TCP: Web UI

**Default Credentials:**
- Username: `admin`
- Password: `admin` (change on first login)

**Provisioned Datasources:**
- Prometheus (http://prometheus:9090)
- Loki (http://loki:3100)

**Pre-built Dashboards:**
1. **AI-SOC Overview** - High-level health metrics
2. **SIEM Stack** - Wazuh Manager, Indexer, Dashboard
3. **ML Performance** - Inference latency, prediction distribution
4. **Container Metrics** - CPU, memory, network per service
5. **Host Metrics** - Node Exporter data

**Features:**
- **Alerting:** Email, Slack, PagerDuty, webhooks
- **Variables:** Dynamic dashboard filtering
- **Annotations:** Event markers on graphs
- **Snapshots:** Share dashboard views

---

### AlertManager

**Purpose:** Alert routing, grouping, and deduplication.

**Technical Specifications:**
- **Version:** 0.26.0
- **Image:** prom/alertmanager:v0.26.0
- **Container Resources:**
  - Memory Limit: 256MB
  - CPU Limit: 0.25 core
- **Ports:**
  - 9093/TCP: Web UI and API

**Routing Configuration:**
```yaml
# alertmanager.yml
route:
  receiver: 'default'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h

  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'

    - match:
        severity: warning
      receiver: 'warning-alerts'

receivers:
  - name: 'critical-alerts'
    email_configs:
      - to: 'soc-team@example.com'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/...'
        channel: '#security-alerts'
    webhook_configs:
      - url: 'http://shuffle-backend:5001/api/v1/hooks/alertmanager'

  - name: 'warning-alerts'
    email_configs:
      - to: 'soc-oncall@example.com'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

**Features:**
- **Grouping:** Combine related alerts
- **Inhibition:** Suppress dependent alerts
- **Silencing:** Temporary muting
- **Routing:** Multi-channel delivery

---

## Network Analysis Components

### Suricata

**Purpose:** Network-based intrusion detection and prevention.

**Technical Specifications:**
- **Version:** 7.0.2
- **Image:** jasonish/suricata:7.0.2
- **Network Mode:** `host` (promiscuous packet capture)
- **Container Resources:**
  - Memory Limit: 2GB
  - CPU Limit: 2.0 cores

**Rule Sources:**
- Emerging Threats Open (30,000+ rules)
- Suricata Ruleset
- Custom rules

**Performance:**
- Throughput: 1-10 Gbps (depends on hardware)
- CPU: Multi-threaded (AF_PACKET)
- Memory: ~1GB for ruleset

**Configuration:**
```yaml
# suricata.yaml
af-packet:
  - interface: eth0
    threads: auto
    cluster-type: cluster_flow

outputs:
  - eve-log:
      enabled: yes
      filetype: regular
      filename: /var/log/suricata/eve.json
      types:
        - alert
        - http
        - dns
        - tls
        - files
        - flow
```

**Integration:**
- Logs shipped via Filebeat to Wazuh Manager
- JSON format for parsing

**Limitations:**
- Requires Linux host (Windows Docker Desktop incompatible)
- Needs promiscuous mode network interface

---

### Zeek

**Purpose:** Passive network traffic analyzer and metadata extractor.

**Technical Specifications:**
- **Version:** 6.0.3
- **Image:** zeek/zeek:6.0.3
- **Network Mode:** `host`
- **Container Resources:**
  - Memory Limit: 2GB
  - CPU Limit: 2.0 cores

**Analysis Capabilities:**
- Protocol detection (HTTP, DNS, SSH, FTP, SMB, etc.)
- File extraction and hashing
- SSL/TLS certificate logging
- Connection tracking (flows)

**Output Logs:**
- `conn.log` - Connection metadata
- `http.log` - HTTP requests/responses
- `dns.log` - DNS queries
- `ssl.log` - TLS handshakes
- `files.log` - Transferred files

**Configuration:**
```zeek
# local.zeek
@load protocols/http/detect-webapps
@load protocols/dns/detect-external-names
@load protocols/ssl/extract-certs
@load frameworks/files/extract-all-files
```

**Performance:**
- Throughput: 1-10 Gbps
- Memory: ~1.5GB
- Disk I/O: High (extensive logging)

---

## Support Components

### Node Exporter

**Purpose:** Host-level metrics (CPU, memory, disk, network).

**Specifications:**
- **Version:** Latest
- **Image:** prom/node-exporter:latest
- **Port:** 9100
- **Metrics:** 800+ Linux system metrics

---

### cAdvisor

**Purpose:** Container-level resource metrics.

**Specifications:**
- **Version:** Latest
- **Image:** gcr.io/cadvisor/cadvisor:latest
- **Port:** 8080
- **Metrics:** CPU, memory, network, disk per container

---

### Loki

**Purpose:** Log aggregation for troubleshooting.

**Specifications:**
- **Version:** 2.9.3
- **Image:** grafana/loki:2.9.3
- **Port:** 3100
- **Retention:** 7 days (configurable)

---

### Promtail

**Purpose:** Log shipping agent for Loki.

**Specifications:**
- **Version:** 2.9.3
- **Image:** grafana/promtail:2.9.3
- **Sources:** Docker container logs via `/var/lib/docker/containers`

---

## Summary

**Total Components:** 35+
**Total Memory (Full Deployment):** ~25GB
**Total CPU (Active Load):** ~15 cores
**Docker Images:** ~10GB compressed
**Persistent Volumes:** 18+

---

**Component Documentation Version:** 1.0
**Last Updated:** October 24, 2025
**Maintained By:** AI-SOC Engineering Team
