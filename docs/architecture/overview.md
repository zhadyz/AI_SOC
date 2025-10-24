# Architecture Overview

Comprehensive system architecture for the AI-Augmented Security Operations Center (AI-SOC) platform.

---

## Executive Summary

The AI-SOC platform implements a microservices-based architecture designed for scalability, resilience, and operational intelligence. The system integrates traditional SIEM capabilities with cutting-edge machine learning and large language models to provide autonomous threat detection, analysis, and response capabilities.

**Core Design Principles:**
- **Microservices Architecture:** Independent, loosely-coupled services enable fault isolation and horizontal scaling
- **Defense in Depth:** Multi-layered security with network segmentation and zero-trust principles
- **API-First Design:** RESTful interfaces enable integration and extensibility
- **Observable by Default:** Comprehensive metrics, logs, and traces for operational visibility
- **Infrastructure as Code:** Complete configuration management via Docker Compose

---

## System Architecture

### High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        External Data Sources                        │
│  Network Traffic, System Logs, Security Events, Threat Intelligence│
└───────────────────────────────┬────────────────────────────────────┘
                                │
        ┌───────────────────────┴────────────────────────┐
        │                                                  │
        ▼                                                  ▼
┌──────────────────────┐                    ┌─────────────────────────┐
│  Network Analysis    │                    │   External Log Sources  │
│  ─────────────────   │                    │   ──────────────────    │
│  • Suricata IDS/IPS  │                    │   • System Logs         │
│  • Zeek Monitor      │                    │   • Application Logs    │
│  • Packet Capture    │                    │   • Cloud Security Logs │
└──────────┬───────────┘                    └────────────┬────────────┘
           │                                             │
           └─────────────────┬───────────────────────────┘
                             │
                             ▼
            ┌────────────────────────────────┐
            │      SIEM Core (Phase 1)       │
            │  ─────────────────────────     │
            │  • Wazuh Manager (Ingestion)   │
            │  • Wazuh Indexer (Storage)     │
            │  • Wazuh Dashboard (UI)        │
            └───────────┬────────────────────┘
                        │
        ┌───────────────┼────────────────┐
        │               │                 │
        ▼               ▼                 ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│  AI Services │ │ SOAR Stack   │ │   Monitoring     │
│  ─────────── │ │ ──────────── │ │   ──────────     │
│  • ML Models │ │ • TheHive    │ │   • Prometheus   │
│  • LLM Agent │ │ • Cortex     │ │   • Grafana      │
│  • RAG/CTI   │ │ • Shuffle    │ │   • AlertManager │
└──────────────┘ └──────────────┘ └──────────────────┘
        │               │                 │
        └───────────────┴─────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │   Orchestration & Response    │
        │   ───────────────────────     │
        │   • Automated Playbooks       │
        │   • Case Management           │
        │   • Incident Response         │
        └───────────────────────────────┘
```

---

## Architectural Layers

### Layer 1: Data Ingestion

**Purpose:** Collect and normalize security telemetry from diverse sources.

**Components:**
- **Suricata IDS/IPS** - Network-based intrusion detection using signature and anomaly detection
- **Zeek Network Monitor** - Passive network traffic analysis and metadata extraction
- **Filebeat** - Log shipping agent for centralized log collection
- **Wazuh Agents** - Host-based security monitoring and file integrity

**Design Rationale:**
- Multi-source ingestion provides comprehensive visibility across network and host layers
- Standard log formats (JSON, CEF, Syslog) enable interoperability
- Buffering and retry mechanisms ensure reliable data delivery

**Performance Characteristics:**
- Throughput: 10,000+ events/second sustained
- Latency: <100ms from event generation to indexing
- Reliability: 99.9% delivery guarantee with persistent queues

---

### Layer 2: SIEM Core

**Purpose:** Centralized log aggregation, correlation, and persistent storage.

**Components:**
- **Wazuh Manager** - Event processing, correlation engine, API gateway
- **Wazuh Indexer** - OpenSearch-based distributed search and analytics engine
- **Wazuh Dashboard** - Web-based visualization and investigation interface

**Technology Stack:**
- OpenSearch 2.x (distributed search engine)
- Wazuh 4.8.2 (security information management)
- Kibana fork (visualization framework)

**Design Rationale:**
- OpenSearch provides horizontal scalability for petabyte-scale log storage
- Wazuh's rule-based correlation enables real-time threat detection
- RESTful API enables programmatic access for automation

**Data Flow:**
```
Event → Wazuh Manager → Rule Engine → Correlation → Indexer → Storage
                ↓
          Alert Generation → Webhook → SOAR
```

**Performance Characteristics:**
- Indexing Rate: 50,000 events/second (3-node cluster)
- Query Latency: <500ms for 90th percentile
- Retention: 30 days hot storage, 365 days warm/cold tiers
- Storage Efficiency: 10:1 compression ratio

---

### Layer 3: AI Services

**Purpose:** Autonomous threat detection, classification, and contextual analysis using machine learning and large language models.

**Architecture:**

```
┌──────────────────────────────────────────────────────┐
│              AI Services Layer                        │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌───────────────┐      ┌──────────────────┐        │
│  │ ML Inference  │◄────►│  Alert Triage    │        │
│  │    Engine     │      │    Service       │        │
│  ├───────────────┤      ├──────────────────┤        │
│  │ Random Forest │      │ LLaMA 3.1:8b     │        │
│  │ XGBoost       │      │ Risk Scoring     │        │
│  │ Decision Tree │      │ Prioritization   │        │
│  └───────────────┘      └─────────┬────────┘        │
│                                    │                  │
│                         ┌──────────▼────────┐        │
│                         │  RAG Service      │        │
│                         ├───────────────────┤        │
│                         │ MITRE ATT&CK DB   │        │
│                         │ Threat Intel      │        │
│                         │ ChromaDB Vector   │        │
│                         └───────────────────┘        │
└──────────────────────────────────────────────────────┘
```

**Components:**

**1. ML Inference Engine**
- **Models:** Random Forest (primary), XGBoost (low-FP), Decision Tree (interpretable)
- **Performance:** 99.28% accuracy, 0.8ms inference latency
- **API:** FastAPI with automatic OpenAPI documentation
- **Deployment:** Docker containerized with health checks

**2. Alert Triage Service**
- **LLM:** LLaMA 3.1:8b via Ollama runtime
- **Function:** Natural language analysis of security alerts
- **Capabilities:**
  - Risk scoring (0-100 scale)
  - Attack classification
  - Recommended response actions
  - Executive summaries

**3. RAG Service**
- **Knowledge Base:** 823 MITRE ATT&CK techniques
- **Vector Database:** ChromaDB for semantic search
- **Retrieval:** Top-k context retrieval for LLM augmentation
- **Latency:** <50ms for 5 nearest neighbors

**Design Rationale:**
- **Ensemble Approach:** Multiple ML models provide redundancy and complementary strengths
- **Hybrid Intelligence:** Traditional ML (fast, deterministic) + LLM (contextual, adaptive)
- **Offline-First:** Models deployed locally, no external API dependencies
- **Explainability:** Decision tree model provides full transparency for compliance

**Data Flow:**
```
Alert → ML Classification → Prediction (BENIGN/ATTACK)
                          ↓
                    Alert Triage
                          ↓
              ┌───────────┴──────────┐
              ▼                       ▼
        RAG Retrieval           LLM Analysis
    (MITRE Techniques)       (Natural Language)
              │                       │
              └───────────┬───────────┘
                          ▼
              Enriched Alert (Risk Score,
               Classification, Context)
                          ▼
                      TheHive
```

---

### Layer 4: SOAR Stack

**Purpose:** Security orchestration, automation, and response.

**Components:**
- **TheHive** - Collaborative case management platform
- **Cortex** - Observable analysis engine with 100+ analyzers
- **Shuffle** - Workflow automation and playbook execution

**Integration Points:**
- Wazuh → TheHive (webhook-based alert ingestion)
- TheHive → Cortex (automated IOC enrichment)
- TheHive → Shuffle (workflow triggers)
- Shuffle → Response Actions (firewall rules, EDR isolation, notifications)

**Design Rationale:**
- TheHive provides centralized case management for multi-analyst collaboration
- Cortex automates repetitive analysis tasks (IP reputation, file hashing, threat intel)
- Shuffle enables no-code playbook development for rapid response

**Workflow Example:**
```
Wazuh Alert → TheHive Case
                    ↓
          Cortex Analysis (IP reputation, geolocation)
                    ↓
         Shuffle Playbook Execution
                    ↓
         ┌──────────┴──────────┐
         ▼                      ▼
   Block IP (Firewall)    Notify SOC Team
```

---

### Layer 5: Monitoring & Observability

**Purpose:** Real-time health monitoring, performance metrics, and alerting.

**Components:**
- **Prometheus** - Time-series metrics database
- **Grafana** - Visualization and dashboards
- **AlertManager** - Alert routing and deduplication
- **Loki** - Log aggregation for troubleshooting
- **cAdvisor + Node Exporter** - Container and host metrics

**Metrics Collection:**
- 13 scrape targets across all services
- 15-second scrape interval
- 30-day retention for high-resolution data

**Dashboards:**
- SIEM Stack Health (Wazuh Manager, Indexer, Dashboard)
- ML Model Performance (inference latency, prediction distribution)
- AI Services Metrics (LLM response times, RAG retrieval accuracy)
- Infrastructure Resources (CPU, RAM, disk, network)

**Alerting Rules:**
- Service down detection (<30 seconds)
- Resource exhaustion (CPU >80%, RAM >90%)
- ML model drift detection
- Abnormal false positive rates

**Design Rationale:**
- Prometheus provides industry-standard metrics format (compatible with all major tools)
- Grafana enables custom dashboards for different stakeholder personas (SOC analyst, engineer, executive)
- AlertManager prevents alert fatigue through intelligent grouping and inhibition

---

## Network Architecture

### Network Segmentation

**Isolation Strategy:** Backend/Frontend network separation per stack.

| Network          | Subnet         | Purpose                    | Security Posture |
|------------------|----------------|----------------------------|------------------|
| siem-backend     | 172.20.0.0/24  | SIEM internal comms        | No external exposure |
| siem-frontend    | 172.21.0.0/24  | SIEM web UI                | HTTPS only |
| soar-backend     | 172.26.0.0/24  | SOAR databases             | No external exposure |
| soar-frontend    | 172.27.0.0/24  | SOAR web UIs               | HTTP (reverse proxy recommended) |
| monitoring       | 172.28.0.0/24  | Observability stack        | Internal only |
| ai-network       | 172.30.0.0/24  | AI/ML services             | API gateway protected |

**Benefits:**
- Compromised web UI cannot directly access backend databases
- Lateral movement requires crossing network boundaries
- Simplified firewall rule management
- Clear trust boundaries for security policies

### Port Allocation

**Externally Accessible:**
- 443 (Wazuh Dashboard - HTTPS)
- 3000 (Grafana)
- 9010 (TheHive)
- 9011 (Cortex)
- 3001 (Shuffle)
- 8500 (ML Inference API)
- 8100 (Alert Triage API)
- 8300 (RAG Service API)

**Internal Only:**
- 9200 (Wazuh Indexer - OpenSearch)
- 55000 (Wazuh Manager API)
- 9042 (Cassandra)
- 8200 (ChromaDB)
- 11434 (Ollama LLM)

See [Network Topology](network-topology.md) for complete port mapping.

---

## Technology Stack

### Backend Services

| Component | Technology | Version | Justification |
|-----------|-----------|---------|---------------|
| SIEM | Wazuh | 4.8.2 | Open-source, MITRE ATT&CK mapping, active community |
| Search Engine | OpenSearch | 2.x | Elasticsearch fork, scalable, no licensing restrictions |
| Case Management | TheHive | 5.2.9 | Purpose-built for SOC workflows, Cortex integration |
| Orchestration | Shuffle | 1.4.0 | Open-source SOAR, drag-drop workflows |
| Database | Cassandra | 4.1.3 | Distributed, fault-tolerant, scales horizontally |
| Vector DB | ChromaDB | Latest | AI-native, embedding support, simple API |
| Object Storage | MinIO | Latest | S3-compatible, self-hosted |

### AI/ML Stack

| Component | Technology | Version | Justification |
|-----------|-----------|---------|---------------|
| ML Framework | scikit-learn | 1.3+ | Industry standard, battle-tested algorithms |
| LLM Runtime | Ollama | Latest | Local inference, model management, OpenAI-compatible API |
| LLM Model | LLaMA 3.1 | 8B params | State-of-the-art open-source, optimal size/performance |
| API Framework | FastAPI | 0.100+ | Async support, automatic docs, type safety |
| Vector Embeddings | sentence-transformers | Latest | Pre-trained models, semantic similarity |

### Infrastructure

| Component | Technology | Version | Justification |
|-----------|-----------|---------|---------------|
| Container Runtime | Docker | 24.0+ | Industry standard, mature ecosystem |
| Orchestration | Docker Compose | V2 | Simplified multi-container management |
| Monitoring | Prometheus | 2.48+ | De facto standard, extensive integrations |
| Visualization | Grafana | 10.2+ | Powerful dashboards, alerting, multi-datasource |
| Log Aggregation | Loki | 2.9+ | Prometheus-style log queries, low storage overhead |

---

## Scalability Considerations

### Horizontal Scaling

**SIEM Stack:**
- Wazuh Manager: Multi-node cluster with load balancing
- Wazuh Indexer: OpenSearch cluster (3+ nodes for HA)
- Capacity: 100,000+ events/second with 5-node indexer cluster

**AI Services:**
- ML Inference: Stateless, add replicas behind load balancer
- Alert Triage: Horizontal scaling limited by Ollama GPU availability
- RAG Service: Stateless, ChromaDB supports distributed deployment

**SOAR Stack:**
- TheHive: Multi-master cluster with Cassandra ring
- Shuffle: Worker scaling for parallel workflow execution

### Vertical Scaling

**Resource Limits (per service):**
- Wazuh Indexer: 16GB RAM (configurable JVM heap)
- ML Inference: 1GB RAM, 1 CPU (sufficient for 1,000 req/sec)
- Ollama LLM: 8GB RAM minimum (16GB for larger models)
- ChromaDB: 4GB RAM for 100K vectors

### Performance Targets

| Metric | Small Deployment | Medium | Large |
|--------|------------------|--------|-------|
| Event Throughput | 1,000/sec | 10,000/sec | 100,000/sec |
| Concurrent Analysts | 5 | 25 | 100 |
| Data Retention | 30 days | 90 days | 365 days |
| Query Response (p95) | <1s | <500ms | <200ms |
| ML Inference Latency | <5ms | <2ms | <1ms |

---

## High Availability Design

### Service Redundancy

**Critical Services (require 99.9% uptime):**
- Wazuh Manager: 2+ nodes with failover
- Wazuh Indexer: 3+ nodes (quorum-based)
- Cassandra: 3+ nodes (RF=3)

**Non-Critical Services (tolerate brief downtime):**
- Grafana: Single instance acceptable (read-only impact)
- Shuffle: Workflow queue prevents data loss

### Data Persistence

**Volumes:**
- All stateful services use named Docker volumes
- Volume backup strategy: daily snapshots
- Retention: 30 days for volume backups

**Backup Procedures:**
```bash
# Wazuh Indexer snapshot
docker exec wazuh-indexer curl -X PUT "localhost:9200/_snapshot/backup"

# Cassandra backup
docker exec cassandra nodetool snapshot

# ChromaDB export
docker exec chromadb curl "http://localhost:8000/api/v1/export"
```

---

## Security Architecture

### Defense in Depth

**Layer 1: Network Segmentation**
- Isolated Docker networks per stack
- No direct backend exposure to internet
- Firewall rules restrict inter-service communication

**Layer 2: Authentication & Authorization**
- API key authentication for service-to-service
- OAuth2/SAML for user authentication
- Role-based access control (RBAC) in TheHive

**Layer 3: Encryption**
- TLS 1.3 for all external communication
- Self-signed certificates (development)
- Let's Encrypt integration (production)

**Layer 4: Secrets Management**
- Environment variable injection
- Docker secrets for production
- HashiCorp Vault integration (future)

**Layer 5: Audit Logging**
- All API calls logged to Wazuh
- Immutable audit trail
- Retention: 365 days minimum

### Threat Model

**Assumed Threats:**
- External network attackers
- Compromised web application
- Insider threats (malicious analyst)
- Supply chain attacks (vulnerable dependencies)

**Mitigations:**
- Web Application Firewall (WAF) recommended
- Principle of least privilege
- Audit logging and anomaly detection
- Dependency scanning (Dependabot, Snyk)

See [Security Guide](../security/guide.md) for detailed hardening procedures.

---

## Integration Patterns

### Event-Driven Architecture

**Webhooks:**
- Wazuh → TheHive: Alert creation on rule match
- TheHive → Shuffle: Case status changes trigger workflows
- AlertManager → Shuffle: Infrastructure alerts trigger remediation

**Benefits:**
- Loose coupling between services
- Asynchronous processing prevents blocking
- Retry mechanisms handle transient failures

### API-First Design

**RESTful APIs:**
- All services expose standardized REST endpoints
- OpenAPI/Swagger documentation auto-generated
- Consistent error handling (RFC 7807 Problem Details)

**Example API Flow:**
```
POST /triage
  → GET /ml-inference/predict (ML classification)
  → GET /rag-service/retrieve (MITRE context)
  → POST /ollama/api/generate (LLM analysis)
  → Response: Enriched alert
```

---

## Development & Deployment

### CI/CD Pipeline (Planned)

```
Code Commit → GitHub Actions
                    ↓
              Unit Tests
                    ↓
              Docker Build
                    ↓
         Integration Tests
                    ↓
      Deploy to Staging
                    ↓
         Smoke Tests
                    ↓
    Production Deployment
```

### Configuration Management

**Environment Variables:**
- `.env` file for local development
- Docker Compose env_file directive
- Secrets injected at runtime

**Infrastructure as Code:**
- All configurations version-controlled
- Declarative Docker Compose specifications
- Idempotent deployment scripts

---

## Future Architecture Enhancements

### Short-term (Weeks 3-4)
- Multi-class ML classification (24 attack types)
- Reverse proxy (Nginx/Traefik) for HTTPS termination
- Secrets management (HashiCorp Vault)
- Automated backups

### Medium-term (Months 2-3)
- Kubernetes migration for production deployments
- Multi-region deployment for disaster recovery
- Advanced ML models (deep learning, transformers)
- Custom Cortex analyzers

### Long-term (Months 4-6)
- Multi-agent collaboration framework
- Automated playbook generation via LLM
- Predictive threat modeling
- Zero-trust network architecture

---

## Appendices

### A. Service Dependencies

```
Wazuh Dashboard → Wazuh Manager → Wazuh Indexer
TheHive → Cassandra + MinIO
Cortex → Cassandra + TheHive
Shuffle → OpenSearch
Alert Triage → ML Inference + RAG Service + Ollama
RAG Service → ChromaDB
Grafana → Prometheus + Loki
AlertManager → Prometheus
```

### B. Resource Requirements

**Minimum (Development/Testing):**
- CPU: 4 cores (8 threads)
- RAM: 16GB
- Disk: 50GB SSD
- Network: 100Mbps

**Recommended (Production):**
- CPU: 8 cores (16 threads)
- RAM: 32GB
- Disk: 250GB NVMe SSD
- Network: 1Gbps

See [System Requirements](../getting-started/requirements.md) for detailed specifications.

### C. Glossary

- **SIEM:** Security Information and Event Management
- **SOAR:** Security Orchestration, Automation, and Response
- **RAG:** Retrieval-Augmented Generation
- **CTI:** Cyber Threat Intelligence
- **MITRE ATT&CK:** Adversarial Tactics, Techniques, and Common Knowledge framework
- **IOC:** Indicator of Compromise
- **EDR:** Endpoint Detection and Response

---

**Architecture Documentation Version:** 1.0
**Last Updated:** October 24, 2025
**Maintained By:** AI-SOC Architecture Team
