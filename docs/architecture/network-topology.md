# AI-SOC Network Topology

**Version:** 1.0
**Date:** October 22, 2025
**Status:** Production Deployment

---

## Overview

This document describes the complete network architecture of the AI-SOC platform, including all networks, services, ports, and data flows.

---

## Network Architecture Diagram

```
                             ┌─────────────────────────────────────────────────┐
                             │         EXTERNAL ACCESS (Internet)              │
                             │    Port 443 (HTTPS), Port 3000, Port 9010, etc. │
                             └────────────────────┬────────────────────────────┘
                                                  │
                                                  │
                    ┌─────────────────────────────┼─────────────────────────────┐
                    │                    Docker Host                             │
                    │                                                            │
┌───────────────────┴───────────────────────────────────────────────────────────┴────────────────────┐
│                                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐    │
│  │                          SIEM STACK (Phase 1)                                              │    │
│  │  Network: siem-backend (172.20.0.0/24)  |  siem-frontend (172.21.0.0/24)                  │    │
│  ├────────────────────────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                                            │    │
│  │  ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐               │    │
│  │  │ Wazuh Manager    │◄────►│ Wazuh Indexer    │◄────►│ Wazuh Dashboard  │               │    │
│  │  │                  │      │  (OpenSearch)    │      │                  │               │    │
│  │  │ Ports:           │      │ Ports: 9200,9600 │      │ Port: 443 (HTTPS)│               │    │
│  │  │ 1514, 1515, 514  │      │                  │      │                  │               │    │
│  │  │ 55000 (API)      │      │                  │      │                  │               │    │
│  │  └────────┬─────────┘      └──────────────────┘      └──────────────────┘               │    │
│  │           │                                                                               │    │
│  │           │ Log Ingestion                                                                 │    │
│  │           ▼                                                                               │    │
│  │  ┌────────────────────────────────────────────────────────────────┐                     │    │
│  │  │  External Logs: Suricata, Zeek, Filebeat, System Logs         │                     │    │
│  │  └────────────────────────────────────────────────────────────────┘                     │    │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐    │
│  │                          SOAR STACK (Phase 2)                                              │    │
│  │  Network: soar-backend (172.26.0.0/24)  |  soar-frontend (172.27.0.0/24)                  │    │
│  ├────────────────────────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                                            │    │
│  │  ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐               │    │
│  │  │ TheHive 5.x      │◄────►│     Cortex       │      │ Shuffle Workflow │               │    │
│  │  │ Case Management  │      │  Analysis Engine │      │   Orchestration  │               │    │
│  │  │ Port: 9010       │      │  Port: 9011      │      │  Ports: 3001,5001│               │    │
│  │  └────────┬─────────┘      └────────┬─────────┘      └────────┬─────────┘               │    │
│  │           │                          │                          │                         │    │
│  │           │                          │                          │                         │    │
│  │           ▼                          ▼                          ▼                         │    │
│  │  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐                   │    │
│  │  │  Cassandra   │          │    MinIO     │          │  OpenSearch  │                   │    │
│  │  │   Database   │          │   S3 Store   │          │   Database   │                   │    │
│  │  │  Port: 9042  │          │ Ports: 9000, │          │  Port: 9201  │                   │    │
│  │  │              │          │       9001   │          │              │                   │    │
│  │  └──────────────┘          └──────────────┘          └──────────────┘                   │    │
│  │                                                                                            │    │
│  │  Webhooks: Wazuh → TheHive → Shuffle → Cortex                                            │    │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐    │
│  │                          MONITORING STACK                                                  │    │
│  │  Network: monitoring (172.28.0.0/24)                                                       │    │
│  ├────────────────────────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                                            │    │
│  │  ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐               │    │
│  │  │   Prometheus     │◄────►│     Grafana      │◄────►│  AlertManager    │               │    │
│  │  │ Metrics Collect  │      │  Visualization   │      │  Alert Routing   │               │    │
│  │  │  Port: 9090      │      │   Port: 3000     │      │   Port: 9093     │               │    │
│  │  └────────┬─────────┘      └──────────────────┘      └──────────────────┘               │    │
│  │           │                                                                               │    │
│  │           │ Scrapes Metrics From:                                                         │    │
│  │           ├─► Node Exporter (Port 9100) - Host Metrics                                   │    │
│  │           ├─► cAdvisor (Port 8080) - Container Metrics                                   │    │
│  │           ├─► Wazuh Manager (Port 55000) - SIEM Metrics                                  │    │
│  │           ├─► TheHive (Port 9010) - SOAR Metrics                                         │    │
│  │           ├─► Cortex (Port 9011) - Analysis Metrics                                      │    │
│  │           ├─► ML Inference (Port 8500) - AI Metrics                                      │    │
│  │           └─► All AI Services (8100, 8200, 8300) - Service Metrics                       │    │
│  │                                                                                            │    │
│  │  ┌──────────────────┐      ┌──────────────────┐                                         │    │
│  │  │      Loki        │◄────►│    Promtail      │                                         │    │
│  │  │ Log Aggregation  │      │   Log Shipper    │                                         │    │
│  │  │  Port: 3100      │      │                  │                                         │    │
│  │  └──────────────────┘      └──────────────────┘                                         │    │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐    │
│  │                          AI SERVICES STACK                                                 │    │
│  │  Network: ai-network (172.30.0.0/24)                                                       │    │
│  ├────────────────────────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                                            │    │
│  │  ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐               │    │
│  │  │  ML Inference    │◄────►│  Alert Triage    │◄────►│   RAG Service    │               │    │
│  │  │      API         │      │    Service       │      │                  │               │    │
│  │  │  Port: 8500      │      │   Port: 8100     │      │   Port: 8300     │               │    │
│  │  │  99.28% Accuracy │      │  LLM-Powered     │      │  MITRE ATT&CK    │               │    │
│  │  └──────────────────┘      └────────┬─────────┘      └────────┬─────────┘               │    │
│  │                                      │                          │                         │    │
│  │                                      ▼                          ▼                         │    │
│  │                             ┌──────────────────┐      ┌──────────────────┐               │    │
│  │                             │  Ollama Server   │      │    ChromaDB      │               │    │
│  │                             │  LLaMA 3.1:8b    │      │  Vector Database │               │    │
│  │                             │  Port: 11434     │      │   Port: 8200     │               │    │
│  │                             └──────────────────┘      └──────────────────┘               │    │
│  │                                                                                            │    │
│  │  Data Flow: Alert → ML Inference → Alert Triage → RAG → TheHive                          │    │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐    │
│  │                   NETWORK ANALYSIS STACK (Linux Only)                                      │    │
│  │  Network: network_mode: host (Direct Host Network Access)                                 │    │
│  ├────────────────────────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                                            │    │
│  │  ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐               │    │
│  │  │    Suricata      │      │       Zeek       │      │    Filebeat      │               │    │
│  │  │    IDS/IPS       │      │  Network Monitor │      │   Log Shipper    │               │    │
│  │  │ Promiscuous Mode │      │ Promiscuous Mode │      │  → Wazuh Manager │               │    │
│  │  │  Interface: eth0 │      │  Interface: eth0 │      │                  │               │    │
│  │  └────────┬─────────┘      └────────┬─────────┘      └────────┬─────────┘               │    │
│  │           │                          │                          │                         │    │
│  │           └──────────────────────────┴──────────────────────────┘                         │    │
│  │                                      │                                                     │    │
│  │                                      ▼                                                     │    │
│  │                          Raw Network Traffic (eth0)                                        │    │
│  │                          ▲                                                                 │    │
│  │                          │                                                                 │    │
│  │                   Network TAP / SPAN Port                                                  │    │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Network Subnets

| Network              | Subnet           | Purpose                          | Services                          |
|----------------------|------------------|----------------------------------|-----------------------------------|
| `siem-backend`       | 172.20.0.0/24    | SIEM internal communication      | Wazuh Manager, Indexer            |
| `siem-frontend`      | 172.21.0.0/24    | SIEM user-facing services        | Wazuh Dashboard                   |
| `soar-backend`       | 172.26.0.0/24    | SOAR internal communication      | TheHive, Cortex, Databases        |
| `soar-frontend`      | 172.27.0.0/24    | SOAR user-facing services        | Shuffle UI                        |
| `monitoring`         | 172.28.0.0/24    | Monitoring stack                 | Prometheus, Grafana, AlertManager |
| `ai-network`         | 172.30.0.0/24    | AI/ML services                   | ML Inference, Triage, RAG         |
| `network-analysis`   | 172.29.0.0/24    | Network analysis stack           | Filebeat (Suricata/Zeek use host) |

---

## Service Connectivity Matrix

| Source Service       | Target Service       | Port  | Protocol | Purpose                     |
|----------------------|----------------------|-------|----------|-----------------------------|
| Wazuh Manager        | Wazuh Indexer        | 9200  | HTTPS    | Log storage                 |
| Wazuh Dashboard      | Wazuh Manager        | 55000 | HTTPS    | API queries                 |
| Wazuh Manager        | TheHive              | 9010  | HTTP     | Alert webhook               |
| TheHive              | Cortex               | 9001  | HTTP     | Observable analysis         |
| TheHive              | Shuffle              | 5001  | HTTP     | Workflow trigger            |
| Shuffle              | TheHive              | 9010  | HTTP     | Case creation               |
| Alert Triage         | ML Inference         | 8500  | HTTP     | Prediction request          |
| Alert Triage         | RAG Service          | 8300  | HTTP     | Context retrieval           |
| Alert Triage         | Ollama               | 11434 | HTTP     | LLM inference               |
| RAG Service          | ChromaDB             | 8200  | HTTP     | Vector search               |
| Prometheus           | All Services         | *     | HTTP     | Metrics scraping            |
| Grafana              | Prometheus           | 9090  | HTTP     | Query metrics               |
| Grafana              | Loki                 | 3100  | HTTP     | Query logs                  |
| AlertManager         | Email/Slack          | *     | SMTP/HTTP| Send alerts                 |
| Filebeat             | Wazuh Manager        | 1514  | TCP      | Ship Suricata/Zeek logs     |

---

## Data Flow Diagrams

### Alert Processing Flow

```
Network Traffic
      │
      ▼
 Suricata/Zeek (IDS Detection)
      │
      ▼
   Filebeat (Log Shipping)
      │
      ▼
Wazuh Manager (Aggregation & Correlation)
      │
      ├──► Wazuh Indexer (Storage)
      │
      └──► TheHive (Case Creation via Webhook)
             │
             ├──► Cortex (Observable Analysis)
             │
             └──► Shuffle (Workflow Automation)
                    │
                    └──► Response Actions (Block IP, Notify SOC, etc.)
```

### ML-Powered Alert Triage Flow

```
Wazuh Alert
      │
      ▼
Alert Triage Service
      │
      ├──► ML Inference API (Prediction: BENIGN vs ATTACK)
      │          │
      │          └──► Random Forest Model (99.28% accuracy)
      │
      ├──► RAG Service (MITRE ATT&CK context retrieval)
      │          │
      │          └──► ChromaDB (Vector search)
      │
      └──► Ollama LLM (Natural language analysis)
             │
             └──► LLaMA 3.1:8b (Threat assessment)

Combined Output:
  - Risk Score (0-100)
  - Attack Classification
  - MITRE Techniques
  - Recommended Actions
      │
      ▼
TheHive (Prioritized Case with AI Enrichment)
```

### Monitoring Data Flow

```
All Services
      │
      ├──► Metrics (Prometheus Format)
      │          │
      │          └──► Prometheus (Scrape every 15s)
      │                    │
      │                    └──► Grafana (Visualization)
      │
      └──► Logs (JSON/Plain Text)
                 │
                 └──► Promtail (Ship to Loki)
                          │
                          └──► Loki (Storage & Indexing)
                                   │
                                   └──► Grafana (Log Queries)

Alerts:
Prometheus → AlertManager → Email/Slack/Shuffle
```

---

## Port Summary

### Externally Accessible Ports

| Port  | Service                  | Protocol | Purpose                    |
|-------|--------------------------|----------|----------------------------|
| 443   | Wazuh Dashboard          | HTTPS    | SIEM Web UI                |
| 3000  | Grafana                  | HTTP     | Monitoring Dashboard       |
| 9010  | TheHive                  | HTTP     | Case Management UI         |
| 9011  | Cortex                   | HTTP     | Analysis Engine UI         |
| 3001  | Shuffle                  | HTTP     | Workflow Automation UI     |
| 8500  | ML Inference API         | HTTP     | Prediction Endpoint        |
| 8100  | Alert Triage Service     | HTTP     | Triage API                 |
| 8300  | RAG Service              | HTTP     | Context Retrieval API      |
| 9090  | Prometheus               | HTTP     | Metrics Query UI           |
| 9093  | AlertManager             | HTTP     | Alert Management UI        |

### Internal Ports (Docker Networks Only)

| Port  | Service                  | Purpose                    |
|-------|--------------------------|----------------------------|
| 9200  | Wazuh Indexer            | OpenSearch API             |
| 55000 | Wazuh Manager            | Wazuh API                  |
| 1514  | Wazuh Manager            | Log Ingestion              |
| 9042  | Cassandra                | Database                   |
| 9000  | MinIO                    | Object Storage API         |
| 9201  | OpenSearch (Shuffle)     | Database                   |
| 8200  | ChromaDB                 | Vector Database API        |
| 11434 | Ollama                   | LLM Inference              |
| 3100  | Loki                     | Log Aggregation API        |
| 8080  | cAdvisor                 | Container Metrics          |
| 9100  | Node Exporter            | Host Metrics               |

---

## Security Considerations

### Network Segmentation

1. **Backend Networks** - Internal service communication only
2. **Frontend Networks** - User-facing services with restricted access
3. **Monitoring Network** - Separate network for observability
4. **Host Network** - Only for Suricata/Zeek (packet capture requirements)

### Firewall Rules (Production)

```bash
# Allow HTTPS for web UIs
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p tcp --dport 3000 -j ACCEPT
iptables -A INPUT -p tcp --dport 9010 -j ACCEPT

# Allow Wazuh agent connections
iptables -A INPUT -p tcp --dport 1514 -j ACCEPT
iptables -A INPUT -p udp --dport 514 -j ACCEPT

# Block all other inbound traffic
iptables -A INPUT -j DROP
```

### TLS/SSL Configuration

All external services should use HTTPS in production:
- Wazuh Dashboard: Already configured (self-signed)
- TheHive: Configure reverse proxy (Nginx/Traefik)
- Grafana: Enable HTTPS in grafana.ini
- Prometheus/AlertManager: Reverse proxy recommended

---

## Scalability Notes

### Horizontal Scaling Options

1. **Wazuh Cluster** - Multi-node manager cluster for HA
2. **Cassandra Ring** - Scale TheHive/Cortex storage
3. **Prometheus Federation** - Multi-datacenter monitoring
4. **Shuffle Workers** - Scale workflow execution

### Resource Requirements by Scale

| Scale      | Deployment      | RAM    | CPU   | Disk  |
|------------|-----------------|--------|-------|-------|
| Small      | Single Host     | 16GB   | 4C    | 100GB |
| Medium     | Single Host     | 32GB   | 8C    | 250GB |
| Large      | Multi-Host      | 64GB+  | 16C+  | 500GB+|
| Enterprise | Multi-Datacenter| 128GB+ | 32C+  | 1TB+  |

---

## Integration Points

### Webhook Endpoints

```
Wazuh → TheHive:
  POST http://thehive:9010/api/alert
  Headers: Authorization: Bearer <API_KEY>

TheHive → Shuffle:
  POST http://shuffle-backend:5001/api/v1/hooks/webhook
  Body: JSON alert data

AlertManager → Shuffle:
  POST http://shuffle-backend:5001/api/v1/hooks/alertmanager
  Body: AlertManager webhook format
```

### API Endpoints

```
ML Inference:
  POST http://ml-inference:8500/predict
  Body: {"features": [...], "model_name": "random_forest"}

Alert Triage:
  POST http://alert-triage:8100/triage
  Body: {"alert_data": {...}}

RAG Service:
  POST http://rag-service:8300/retrieve
  Body: {"query": "MITRE T1055", "top_k": 5}
```

---

## Disaster Recovery

### Backup Strategy

1. **Configuration** - All YAML files in version control
2. **Data Volumes** - Daily backups of Docker volumes
3. **Databases** - Automated snapshots (Cassandra, OpenSearch)
4. **Logs** - Retained 30 days in Wazuh, 7 days in Loki

### Recovery Procedures

```bash
# Restore from backup
docker compose down
docker volume rm <volume-name>
# Restore volume from backup
docker compose up -d
```

---

**Network Topology Documentation v1.0**
**Generated by:** ZHADYZ DevOps Orchestrator
**Date:** October 22, 2025
**AI-SOC Project**
