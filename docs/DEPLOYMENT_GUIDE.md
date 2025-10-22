# AI-SOC Complete Deployment Guide

**Last Updated:** October 22, 2025
**Version:** 1.0
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Quick Start](#quick-start)
5. [Stack Deployments](#stack-deployments)
6. [Configuration](#configuration)
7. [Monitoring & Health Checks](#monitoring--health-checks)
8. [Integration](#integration)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

---

## Overview

The AI-SOC (AI-Augmented Security Operations Center) is a comprehensive security platform consisting of four integrated stacks:

### Deployed Stacks

1. **SIEM Stack (Phase 1)** - Security Information and Event Management
   - Wazuh Manager, Indexer, Dashboard
   - Log aggregation and threat detection

2. **SOAR Stack (Phase 2)** - Security Orchestration, Automation, Response
   - TheHive 5.x (Case Management)
   - Cortex 3.x (Observable Analysis)
   - Shuffle (Workflow Automation)

3. **Monitoring Stack** - Observability and Metrics
   - Prometheus (Metrics Collection)
   - Grafana (Visualization)
   - AlertManager (Alert Routing)
   - Loki & Promtail (Log Aggregation)

4. **Network Analysis Stack** - Traffic Inspection (Linux Only)
   - Suricata (IDS/IPS)
   - Zeek (Network Security Monitor)

5. **AI Services** - Machine Learning and Intelligence
   - ML Inference API (99.28% accuracy)
   - Alert Triage Service
   - RAG Service with ChromaDB

---

## Architecture

### Network Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         AI-SOC Platform                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ SIEM Stack   │  │ SOAR Stack   │  │ Monitoring   │         │
│  │              │  │              │  │  Stack       │         │
│  │ Wazuh        │──┼─TheHive      │  │ Prometheus   │         │
│  │ Indexer      │  │ Cortex       │  │ Grafana      │         │
│  │ Dashboard    │  │ Shuffle      │  │ Loki         │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                  │                  │                 │
│         └──────────────────┼──────────────────┘                 │
│                            │                                    │
│  ┌──────────────────────────┼────────────────────────────┐     │
│  │         AI Services      │                            │     │
│  │  ┌──────────────┐  ┌────┴──────┐  ┌──────────────┐  │     │
│  │  │ ML Inference │  │   Alert   │  │ RAG Service  │  │     │
│  │  │     API      │  │  Triage   │  │  ChromaDB    │  │     │
│  │  │  (99.28%)    │  │  Service  │  │  Ollama      │  │     │
│  │  └──────────────┘  └───────────┘  └──────────────┘  │     │
│  └───────────────────────────────────────────────────────┘     │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │ Network Analysis (Linux)                             │      │
│  │  Suricata IDS/IPS  │  Zeek NSM  │  Filebeat         │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Port Mapping

| Service               | Port(s)        | Description                    |
|-----------------------|----------------|--------------------------------|
| **SIEM Stack**        |                |                                |
| Wazuh Manager         | 1514, 1515, 514/udp, 55000 | Log ingestion, API |
| Wazuh Indexer         | 9200, 9600     | OpenSearch API                 |
| Wazuh Dashboard       | 443            | Web UI (HTTPS)                 |
| **SOAR Stack**        |                |                                |
| TheHive               | 9010           | Case Management UI             |
| Cortex                | 9011           | Analysis Engine UI             |
| Shuffle Frontend      | 3001           | Workflow Automation UI         |
| Shuffle Backend       | 5001           | API Endpoint                   |
| Cassandra             | 9042           | Database                       |
| MinIO                 | 9000, 9001     | Object Storage, Console        |
| OpenSearch            | 9201           | Shuffle Database               |
| **Monitoring**        |                |                                |
| Grafana               | 3000           | Visualization Dashboard        |
| Prometheus            | 9090           | Metrics Collection             |
| AlertManager          | 9093           | Alert Management               |
| Loki                  | 3100           | Log Aggregation                |
| cAdvisor              | 8080           | Container Metrics              |
| Node Exporter         | 9100           | Host Metrics                   |
| **AI Services**       |                |                                |
| ML Inference          | 8500           | Prediction API                 |
| Alert Triage          | 8100           | Triage Service                 |
| RAG Service           | 8300           | RAG Endpoint                   |
| ChromaDB              | 8200           | Vector Database                |
| Ollama                | 11434          | LLM Server                     |

---

## Prerequisites

### System Requirements

**Minimum (Development):**
- OS: Windows 10/11 with Docker Desktop OR Linux (Ubuntu 20.04+)
- RAM: 16GB
- CPU: 4 cores
- Disk: 50GB free space
- Docker: 24.0+ with Compose v2

**Recommended (Production):**
- OS: Linux (Ubuntu 22.04 LTS)
- RAM: 32GB
- CPU: 8 cores
- Disk: 200GB SSD
- Docker: 24.0+ with Compose v2

### Software Dependencies

```bash
# Docker (Linux)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Docker Desktop (Windows)
# Download from: https://www.docker.com/products/docker-desktop/

# Verify installation
docker --version
docker compose version
```

### Environment Setup

1. Clone the repository:
```bash
git clone https://github.com/zhadyz/AI_SOC.git
cd AI_SOC
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with secure credentials
```

3. **CRITICAL:** Update passwords in `.env`:
```bash
# Generate secure passwords
openssl rand -base64 32  # Linux/Mac
# OR
python -c "import secrets; print(secrets.token_urlsafe(32))"  # Cross-platform
```

---

## Quick Start

### Option 1: Full Deployment (Linux)

Deploy all stacks simultaneously:

```bash
# Phase 1: SIEM Stack
docker compose -f docker-compose/phase1-siem-core-windows.yml up -d

# Phase 2: SOAR Stack
docker compose -f docker-compose/phase2-soar-stack.yml up -d

# Monitoring Stack
docker compose -f docker-compose/monitoring-stack.yml up -d

# Network Analysis (Linux only)
docker compose -f docker-compose/network-analysis-stack.yml up -d

# AI Services
docker compose -f docker-compose/ai-services.yml up -d
```

### Option 2: Windows Deployment

Windows Docker Desktop does not support `network_mode: host` required for Suricata/Zeek:

```bash
# Deploy everything EXCEPT network analysis
docker compose -f docker-compose/phase1-siem-core-windows.yml up -d
docker compose -f docker-compose/phase2-soar-stack.yml up -d
docker compose -f docker-compose/monitoring-stack.yml up -d
docker compose -f docker-compose/ai-services.yml up -d
```

**Alternative for Network Analysis on Windows:**
- Deploy Suricata/Zeek in WSL2 (see detailed guide below)
- Use a Linux VM (VMware, VirtualBox)
- Deploy on dedicated Linux sensor

### Option 3: Incremental Deployment

Deploy one stack at a time for testing:

```bash
# Start with monitoring
docker compose -f docker-compose/monitoring-stack.yml up -d

# Wait 60 seconds, verify health
docker compose -f docker-compose/monitoring-stack.yml ps

# Add SIEM
docker compose -f docker-compose/phase1-siem-core-windows.yml up -d

# Continue with other stacks...
```

---

## Stack Deployments

### 1. SIEM Stack (Phase 1)

**File:** `docker-compose/phase1-siem-core-windows.yml`

**Components:**
- Wazuh Manager 4.8.2
- Wazuh Indexer 4.8.2 (OpenSearch)
- Wazuh Dashboard 4.8.2

**Deploy:**
```bash
cd "C:\Users\eclip\Desktop\Bari 2025 Portfolio\AI_SOC"
docker compose -f docker-compose/phase1-siem-core-windows.yml up -d
```

**Verify:**
```bash
docker compose -f docker-compose/phase1-siem-core-windows.yml ps
```

**Access:**
- Dashboard: https://localhost:443
- Credentials: `admin` / (INDEXER_PASSWORD from .env)

**First-Time Setup:**
1. Accept self-signed certificate warning
2. Login with admin credentials
3. Complete initial setup wizard
4. Configure log sources

---

### 2. SOAR Stack (Phase 2)

**File:** `docker-compose/phase2-soar-stack.yml`

**Components:**
- TheHive 5.2.9 (Case Management)
- Cortex 3.1.7 (Analysis Engine)
- Shuffle 1.4.0 (Workflow Automation)
- Cassandra 4.1.3 (Database)
- MinIO (Object Storage)
- OpenSearch 2.11.1 (Shuffle DB)

**Deploy:**
```bash
docker compose -f docker-compose/phase2-soar-stack.yml up -d
```

**Wait 5 minutes for initialization:**
```bash
# Monitor startup
docker compose -f docker-compose/phase2-soar-stack.yml logs -f cassandra
# Wait for: "Startup complete"
```

**First-Time Setup:**

1. **Create MinIO Bucket:**
```bash
# Install MinIO client (Linux)
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc

# Configure and create bucket
./mc alias set myminio http://localhost:9000 minioadmin minioadmin123
./mc mb myminio/thehive
```

2. **TheHive Setup:**
- Access: http://localhost:9010
- Default credentials: `admin@thehive.local` / `secret`
- **CRITICAL:** Change password immediately
- Create organization
- Generate API key for integrations

3. **Cortex Setup:**
- Access: http://localhost:9011
- Create admin user on first access
- Update database (follow prompts)
- Generate API key
- Install analyzers:
  ```bash
  docker exec -it soar-cortex bash
  cd /opt/cortex
  ./analyzers/install.sh
  ```

4. **Shuffle Setup:**
- Access: http://localhost:3001
- Create admin account
- Connect to TheHive (API key)

---

### 3. Monitoring Stack

**File:** `docker-compose/monitoring-stack.yml`

**Components:**
- Prometheus 2.48.0 (Metrics)
- Grafana 10.2.2 (Visualization)
- AlertManager 0.26.0 (Alerting)
- Loki 2.9.3 (Logs)
- Promtail (Log Shipper)
- cAdvisor (Container Metrics)
- Node Exporter (Host Metrics)

**Deploy:**
```bash
docker compose -f docker-compose/monitoring-stack.yml up -d
```

**Access:**
- Grafana: http://localhost:3000
- Credentials: `admin` / `admin123` (from .env)
- Prometheus: http://localhost:9090
- AlertManager: http://localhost:9093

**First-Time Setup:**

1. **Login to Grafana:**
   - Navigate to http://localhost:3000
   - Login with credentials
   - Change password on first login

2. **Verify Datasources:**
   - Configuration > Data Sources
   - Prometheus should be automatically configured
   - Test connection

3. **Import Dashboards:**
```bash
# Pre-configured dashboards in config/grafana/dashboards/
# Automatically loaded via provisioning
```

4. **Configure Alerting:**
   - Edit `config/alertmanager/alertmanager.yml`
   - Update SMTP settings for email alerts
   - Update Slack webhook for Slack alerts
   - Reload AlertManager:
   ```bash
   docker compose -f docker-compose/monitoring-stack.yml restart alertmanager
   ```

---

### 4. Network Analysis Stack (Linux Only)

**File:** `docker-compose/network-analysis-stack.yml`

**⚠️ CRITICAL: Linux Only - Requires `network_mode: host`**

**Components:**
- Suricata 7.0.2 (IDS/IPS)
- Zeek 6.0.3 (NSM)
- Filebeat 8.11.3 (Log Shipper)

**Prerequisites:**
```bash
# Identify network interface
ip addr show  # Linux
ifconfig      # Mac/Linux

# Set interface in .env
echo "MONITOR_INTERFACE=eth0" >> .env

# Enable promiscuous mode
sudo ip link set eth0 promisc on
```

**Deploy:**
```bash
# Linux only
docker compose -f docker-compose/network-analysis-stack.yml up -d
```

**Update Suricata Rules:**
```bash
docker compose run --rm suricata-update
```

**Verify Packet Capture:**
```bash
docker logs network-suricata
docker logs network-zeek
```

**Windows WSL2 Deployment:**
```bash
# Install WSL2
wsl --install

# Install Docker in WSL2
curl -fsSL https://get.docker.com | sh

# Deploy from WSL2 terminal
cd /mnt/c/Users/eclip/Desktop/Bari\ 2025\ Portfolio/AI_SOC
docker compose -f docker-compose/network-analysis-stack.yml up -d
```

---

### 5. AI Services

**File:** `docker-compose/ai-services.yml`

**Components:**
- ML Inference API (FastAPI)
- Alert Triage Service
- RAG Service
- ChromaDB (Vector DB)
- (Ollama running separately)

**Deploy:**
```bash
docker compose -f docker-compose/ai-services.yml up -d
```

**Verify:**
```bash
# Check ML Inference health
curl http://localhost:8500/health

# Check models loaded
curl http://localhost:8500/models

# Test prediction
curl -X POST http://localhost:8500/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [0.0, ...], "model_name": "random_forest"}'
```

---

## Configuration

### Environment Variables

Critical `.env` variables:

```bash
# Wazuh
INDEXER_PASSWORD=<CHANGE_ME>
API_PASSWORD=<CHANGE_ME>

# SOAR
MINIO_ROOT_PASSWORD=<CHANGE_ME>
CORTEX_API_KEY=<CHANGE_ME>
OPENSEARCH_PASSWORD=<CHANGE_ME>

# Monitoring
GRAFANA_ADMIN_PASSWORD=<CHANGE_ME>

# Alerting
SMTP_HOST=smtp.gmail.com
SMTP_USERNAME=<your-email>
SMTP_PASSWORD=<app-password>
SLACK_WEBHOOK_URL=<webhook-url>

# Network Interface (Linux)
MONITOR_INTERFACE=eth0
```

### SSL/TLS Certificates

Certificates are pre-generated in `config/*/certs/`. For production:

```bash
# Regenerate certificates
./scripts/generate-certs.sh

# Or manually with OpenSSL
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout config/wazuh-indexer/certs/indexer-key.pem \
  -out config/wazuh-indexer/certs/indexer.pem
```

---

## Monitoring & Health Checks

### Health Check Commands

```bash
# Check all containers
docker ps --format "table {{.Names}}\t{{.Status}}"

# SIEM Stack
docker compose -f docker-compose/phase1-siem-core-windows.yml ps

# SOAR Stack
docker compose -f docker-compose/phase2-soar-stack.yml ps

# Monitoring Stack
docker compose -f docker-compose/monitoring-stack.yml ps

# Individual service logs
docker logs wazuh-manager
docker logs soar-thehive
docker logs monitoring-prometheus
```

### Prometheus Targets

Check all monitored services:
```
http://localhost:9090/targets
```

Expected targets:
- ✅ prometheus (self)
- ✅ node-exporter (host metrics)
- ✅ cadvisor (container metrics)
- ⚠️ wazuh-manager (requires Wazuh deployment)
- ⚠️ thehive (requires SOAR deployment)
- ⚠️ ml-inference (requires AI services)

### Grafana Dashboards

Pre-configured dashboards:
1. **System Overview** - Host metrics (CPU, RAM, Disk)
2. **Docker Containers** - Container resource usage
3. **SIEM Health** - Wazuh service status
4. **SOAR Performance** - TheHive/Cortex/Shuffle metrics
5. **ML Model Metrics** - Inference latency, accuracy

---

## Integration

### Wazuh → TheHive Integration

Configure webhook in Wazuh:

1. Edit `config/wazuh-manager/ossec.conf`:
```xml
<integration>
  <name>thehive</name>
  <hook_url>http://thehive:9010/api/alert</hook_url>
  <api_key>YOUR_THEHIVE_API_KEY</api_key>
  <alert_format>json</alert_format>
</integration>
```

2. Restart Wazuh Manager:
```bash
docker compose -f docker-compose/phase1-siem-core-windows.yml restart wazuh-manager
```

### TheHive → Shuffle Integration

Already configured via webhook in `config/thehive/application.conf`:
```
notification.webhook.endpoints = [
  {
    name: shuffle
    url: "http://shuffle-backend:5001/api/v1/hooks/webhook"
  }
]
```

### Shuffle → Cortex Integration

1. In Shuffle, create workflow
2. Add Cortex action
3. Configure:
   - URL: `http://cortex:9001`
   - API Key: (from Cortex UI)

---

## Troubleshooting

### Common Issues

#### 1. Container Fails to Start

```bash
# Check logs
docker logs <container-name>

# Check resource limits
docker stats

# Verify environment variables
docker compose -f <compose-file> config
```

#### 2. Network Connectivity Issues

```bash
# List networks
docker network ls

# Inspect network
docker network inspect docker-compose_monitoring

# Test connectivity
docker exec monitoring-prometheus ping -c 3 grafana
```

#### 3. Wazuh Manager Health Check Failing

```bash
# Check API endpoint
docker exec wazuh-manager curl -f http://localhost:55000/health

# Verify indexer connection
docker exec wazuh-manager curl -k -u admin:PASSWORD https://wazuh-indexer:9200/_cluster/health
```

#### 4. TheHive/Cortex Database Issues

```bash
# Check Cassandra status
docker exec soar-cassandra nodetool status

# Restart if needed
docker compose -f docker-compose/phase2-soar-stack.yml restart cassandra thehive cortex
```

#### 5. Prometheus Not Scraping Targets

```bash
# Check Prometheus config syntax
docker exec monitoring-prometheus promtool check config /etc/prometheus/prometheus.yml

# Verify network connectivity
docker exec monitoring-prometheus ping thehive
```

#### 6. ML Inference API Model Loading Errors

```bash
# Check logs
docker logs ml-inference

# Verify models exist
docker exec ml-inference ls -lh /app/models

# Check volume mount
docker inspect ml-inference | grep -A 10 Mounts
```

---

## Maintenance

### Backup Procedures

#### 1. Database Backups

```bash
# Wazuh Indexer
docker exec wazuh-indexer curl -X PUT "localhost:9200/_snapshot/my_backup" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/backup"
  }
}'

# Cassandra (TheHive/Cortex)
docker exec soar-cassandra nodetool snapshot thehive
```

#### 2. Configuration Backups

```bash
# Backup entire config directory
tar -czf ai-soc-config-backup-$(date +%F).tar.gz config/

# Backup .env file (encrypted)
gpg -c .env -o .env.gpg
```

#### 3. Volume Backups

```bash
# List volumes
docker volume ls | grep docker-compose

# Backup volume
docker run --rm -v docker-compose_wazuh-manager-data:/data -v $(pwd):/backup ubuntu tar czf /backup/wazuh-manager-backup.tar.gz -C /data .
```

### Update Procedures

#### 1. Update Single Stack

```bash
# Pull latest images
docker compose -f docker-compose/phase2-soar-stack.yml pull

# Recreate containers
docker compose -f docker-compose/phase2-soar-stack.yml up -d
```

#### 2. Update All Stacks

```bash
#!/bin/bash
for stack in phase1-siem-core-windows phase2-soar-stack monitoring-stack ai-services; do
  echo "Updating $stack..."
  docker compose -f docker-compose/${stack}.yml pull
  docker compose -f docker-compose/${stack}.yml up -d
done
```

### Log Rotation

Logs are managed by Docker:

```bash
# Configure log rotation in daemon.json
cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  }
}
EOF

# Restart Docker daemon
sudo systemctl restart docker
```

### Resource Cleanup

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove unused networks
docker network prune

# Clean everything (CAUTION)
docker system prune -a --volumes
```

---

## Production Hardening

Before deploying to production:

1. **Change All Default Passwords**
2. **Enable HTTPS for All Web UIs**
3. **Configure Firewall Rules**
4. **Enable Authentication on All APIs**
5. **Set Up Log Retention Policies**
6. **Configure Automated Backups**
7. **Enable Two-Factor Authentication**
8. **Review Security Audit Findings** (see `docs/Phase0-Security-Audit.md`)

---

## Support & Resources

- **GitHub:** https://github.com/zhadyz/AI_SOC
- **Documentation:** See `docs/` directory
- **Issues:** GitHub Issues
- **Contact:** abdul.bari8019@coyote.csusb.edu

---

**Deployment Guide v1.0**
**Generated by:** ZHADYZ DevOps Orchestrator
**Date:** October 22, 2025
**AI-SOC Project - CSUSB Cybersecurity Research**
