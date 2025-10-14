# AI-SOC Docker Infrastructure Documentation

**Version:** 1.0.0
**Last Updated:** 2025-10-13
**Deployment Target:** Phase 1 - Core SIEM Stack

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [System Requirements](#system-requirements)
4. [Prerequisites](#prerequisites)
5. [Quick Start Guide](#quick-start-guide)
6. [Service Descriptions](#service-descriptions)
7. [Configuration](#configuration)
8. [Network Architecture](#network-architecture)
9. [Storage and Volumes](#storage-and-volumes)
10. [Security Considerations](#security-considerations)
11. [Monitoring and Health Checks](#monitoring-and-health-checks)
12. [Troubleshooting](#troubleshooting)
13. [Maintenance Operations](#maintenance-operations)
14. [Performance Tuning](#performance-tuning)
15. [Backup and Recovery](#backup-and-recovery)

---

## Overview

The AI-SOC Docker infrastructure provides a production-ready Security Operations Center (SOC) platform combining:

- **SIEM Core:** Wazuh Manager, Indexer (OpenSearch), and Dashboard
- **Network Monitoring:** Suricata (IDS/IPS) and Zeek (passive analysis)
- **Development Tools:** PostgreSQL, Redis, Jupyter Lab, Portainer

All services are containerized, orchestrated with Docker Compose, and configured for high availability and observability.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI-SOC ARCHITECTURE                           │
└─────────────────────────────────────────────────────────────────────┘

                         INTERNET / NETWORK TRAFFIC
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │    Network Monitoring Layer   │
                    │  ┌─────────┐    ┌──────────┐ │
                    │  │ Suricata│    │   Zeek   │ │
                    │  │  (IPS)  │    │ (Passive)│ │
                    │  └────┬────┘    └────┬─────┘ │
                    └───────┼──────────────┼───────┘
                            │              │
                            │  Logs/Alerts │
                            ▼              ▼
                    ┌──────────────────────────────┐
                    │       Filebeat Forwarder     │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│                          SIEM CORE LAYER                            │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    Wazuh Manager (Core)                      │ │
│  │  - Event Processing  - Rules Engine  - Agent Management      │ │
│  └──────────────────────┬───────────────────────────────────────┘ │
│                         │                                          │
│                         ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              Wazuh Indexer (OpenSearch)                      │ │
│  │  - Event Storage  - Full-Text Search  - Analytics           │ │
│  └──────────────────────┬───────────────────────────────────────┘ │
│                         │                                          │
│                         ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                  Wazuh Dashboard (UI)                        │ │
│  │  - Visualization  - Dashboards  - Alerts Management          │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ API / Queries
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│                     DEVELOPMENT LAYER                               │
│  ┌────────────┐  ┌──────────┐  ┌────────────┐  ┌──────────────┐  │
│  │ PostgreSQL │  │  Redis   │  │ Jupyter    │  │  Portainer   │  │
│  │ (Metadata) │  │ (Cache)  │  │ (Analysis) │  │  (Mgmt UI)   │  │
│  └────────────┘  └──────────┘  └────────────┘  └──────────────┘  │
└────────────────────────────────────────────────────────────────────┘

NETWORKS:
├── siem-backend (172.20.0.0/24)    - Internal SIEM communication
├── siem-frontend (172.21.0.0/24)   - Dashboard access
├── dev-backend (172.22.0.0/24)     - Database/cache services
└── dev-frontend (172.23.0.0/24)    - Development UI access
```

---

## System Requirements

### Minimum Requirements (Testing/Development)
- **CPU:** 4 cores (x86_64)
- **RAM:** 16 GB
- **Disk:** 100 GB SSD
- **OS:** Linux (Ubuntu 22.04+, Debian 11+, RHEL 8+)
- **Docker Engine:** 23.0.15+
- **Docker Compose:** 2.20.2+

### Recommended Requirements (Production)
- **CPU:** 8+ cores (x86_64)
- **RAM:** 32 GB
- **Disk:** 250 GB NVMe SSD (500 IOPS+)
- **Network:** 1 Gbps interface
- **OS:** Linux (Ubuntu 22.04 LTS recommended)
- **Docker Engine:** 25.0.0+
- **Docker Compose:** 2.24.0+

### Resource Allocation by Service

| Service | Min RAM | Rec RAM | Min CPU | Rec CPU |
|---------|---------|---------|---------|---------|
| **Wazuh Indexer** | 2 GB | 4 GB | 1.0 | 2.0 |
| **Wazuh Manager** | 2 GB | 4 GB | 1.0 | 2.0 |
| **Wazuh Dashboard** | 1 GB | 2 GB | 0.5 | 1.0 |
| **Suricata** | 2 GB | 4 GB | 1.0 | 2.0 |
| **Zeek** | 2 GB | 4 GB | 1.0 | 2.0 |
| **PostgreSQL** | 512 MB | 2 GB | 0.25 | 1.0 |
| **Redis** | 256 MB | 1 GB | 0.1 | 0.5 |
| **Jupyter Lab** | 2 GB | 4 GB | 1.0 | 2.0 |
| **Portainer** | 256 MB | 512 MB | 0.1 | 0.5 |
| **TOTAL** | **12 GB** | **26 GB** | **6.0** | **13.0** |

---

## Prerequisites

### 1. Install Docker and Docker Compose

**Ubuntu/Debian:**
```bash
# Remove old versions
sudo apt-get remove docker docker-engine docker.io containerd runc

# Install dependencies
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg lsb-release

# Add Docker GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

**RHEL/CentOS/Fedora:**
```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl start docker
sudo systemctl enable docker
```

### 2. System Tuning (Required for OpenSearch)

**Linux:**
```bash
# Increase virtual memory map count (required for OpenSearch/Elasticsearch)
sudo sysctl -w vm.max_map_count=262144

# Make permanent
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf

# Verify
sysctl vm.max_map_count
```

### 3. Network Configuration

Identify your network interface for packet capture:
```bash
# Linux
ip link show

# Example output: eth0, ens33, enp0s3, etc.
```

### 4. User Permissions

Add your user to the Docker group (avoid using sudo):
```bash
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker ps
```

---

## Quick Start Guide

### Step 1: Clone Repository and Navigate to Directory

```bash
cd /path/to/AI_SOC
```

### Step 2: Configure Environment Variables

```bash
# Copy example configuration
cp .env.example .env

# Edit with secure passwords
nano .env  # or vim, code, etc.
```

**CRITICAL:** Generate strong passwords for:
- `INDEXER_PASSWORD`
- `API_PASSWORD`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `JUPYTER_TOKEN`
- `PORTAINER_ADMIN_PASSWORD`

**Generate secure passwords:**
```bash
# Linux/Mac
openssl rand -base64 32

# Windows PowerShell
[System.Convert]::ToBase64String((1..32|%{Get-Random -Max 256}))
```

### Step 3: Generate SSL/TLS Certificates

```bash
# Create certificate directory structure
mkdir -p docker-compose/config/{wazuh-indexer,wazuh-manager,wazuh-dashboard}/certs

# Generate certificates (script will be created in Phase 1 delivery)
./scripts/generate-certs.sh
```

**For Quick Testing (Self-Signed):**
```bash
cd docker-compose/config/wazuh-indexer/certs
openssl req -x509 -newkey rsa:4096 -keyout root-ca-key.pem -out root-ca.pem -days 365 -nodes
openssl req -x509 -newkey rsa:4096 -keyout indexer-key.pem -out indexer.pem -days 365 -nodes
cd ../../wazuh-manager/certs
openssl req -x509 -newkey rsa:4096 -keyout filebeat-key.pem -out filebeat.pem -days 365 -nodes
cp ../wazuh-indexer/certs/root-ca.pem .
cd ../../wazuh-dashboard/certs
openssl req -x509 -newkey rsa:4096 -keyout dashboard-key.pem -out dashboard.pem -days 365 -nodes
```

### Step 4: Create Configuration Files

```bash
# Create required directories
mkdir -p docker-compose/config/{suricata,zeek/site,filebeat,postgres/init-scripts,redis,jupyter}

# Create minimal Suricata config
cat > docker-compose/config/suricata/suricata.yaml <<EOF
%YAML 1.1
---
vars:
  address-groups:
    HOME_NET: "[192.168.0.0/16,10.0.0.0/8,172.16.0.0/12]"
    EXTERNAL_NET: "!\\$HOME_NET"
outputs:
  - eve-log:
      enabled: yes
      filetype: regular
      filename: eve.json
EOF

# Create Zeek local configuration
cat > docker-compose/config/zeek/local.zeek <<EOF
@load base/protocols/conn
@load base/protocols/dns
@load base/protocols/http
@load base/protocols/ssl
EOF

# Create Jupyter requirements
cat > docker-compose/config/jupyter/requirements.txt <<EOF
pandas>=2.0.0
scikit-learn>=1.3.0
matplotlib>=3.7.0
seaborn>=0.12.0
psycopg2-binary>=2.9.0
redis>=5.0.0
elasticsearch>=8.11.0
EOF
```

### Step 5: Deploy Phase 1 (Core SIEM)

```bash
cd docker-compose

# Pull images (optional, speeds up first start)
docker compose -f phase1-siem-core.yml pull

# Start services in detached mode
docker compose -f phase1-siem-core.yml up -d

# Monitor startup logs
docker compose -f phase1-siem-core.yml logs -f
```

**Wait for all services to become healthy (2-5 minutes):**
```bash
watch -n 2 docker compose -f phase1-siem-core.yml ps
```

### Step 6: Deploy Development Environment (Optional)

```bash
docker compose -f dev-environment.yml up -d

# With optional services (Adminer, Redis Commander)
docker compose -f dev-environment.yml --profile optional up -d
```

### Step 7: Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Wazuh Dashboard** | https://localhost:443 | admin / INDEXER_PASSWORD |
| **Wazuh API** | https://localhost:55000 | wazuh-wui / API_PASSWORD |
| **Jupyter Lab** | http://localhost:8888 | token: JUPYTER_TOKEN |
| **Portainer** | https://localhost:9443 | admin / PORTAINER_ADMIN_PASSWORD |
| **Adminer** | http://localhost:8080 | postgres / aisoc / POSTGRES_PASSWORD |
| **Redis Commander** | http://localhost:8081 | admin / REDIS_COMMANDER_PASSWORD |

### Step 8: Verify Installation

```bash
# Check all services are running
docker compose -f phase1-siem-core.yml ps
docker compose -f dev-environment.yml ps

# Test Wazuh Indexer
curl -k -u admin:INDEXER_PASSWORD https://localhost:9200/_cluster/health?pretty

# Test Wazuh Manager API
curl -k -u wazuh-wui:API_PASSWORD https://localhost:55000/

# View logs
docker compose -f phase1-siem-core.yml logs wazuh-manager
```

---

## Service Descriptions

### Phase 1: Core SIEM Stack

#### Wazuh Indexer (OpenSearch)
- **Purpose:** Event storage, search, and analytics backend
- **Image:** `wazuh/wazuh-indexer:4.8.2`
- **Ports:** 9200 (REST API), 9600 (Performance Analyzer)
- **Volumes:** `wazuh-indexer-data` (event storage)
- **Dependencies:** None (starts first)

#### Wazuh Manager
- **Purpose:** Security event processing, rules engine, agent management
- **Image:** `wazuh/wazuh-manager:4.8.2`
- **Ports:** 1514 (agents), 1515 (enrollment), 514/udp (syslog), 55000 (API)
- **Volumes:** `wazuh-manager-data`, `wazuh-manager-logs`, `wazuh-manager-etc`
- **Dependencies:** Wazuh Indexer

#### Wazuh Dashboard
- **Purpose:** Web UI for visualization and management
- **Image:** `wazuh/wazuh-dashboard:4.8.2`
- **Ports:** 443 (HTTPS)
- **Dependencies:** Wazuh Manager, Wazuh Indexer

#### Suricata
- **Purpose:** Real-time intrusion detection and prevention (IDS/IPS)
- **Image:** `jasonish/suricata:7.0.3`
- **Network Mode:** Host (required for packet capture)
- **Capabilities:** NET_ADMIN, NET_RAW, SYS_NICE
- **Volumes:** `suricata-logs`, `suricata-rules`

#### Zeek
- **Purpose:** Passive network traffic analysis and metadata extraction
- **Image:** `zeek/zeek:6.0.3`
- **Network Mode:** Host (required for packet capture)
- **Capabilities:** NET_ADMIN, NET_RAW
- **Volumes:** `zeek-logs`, `zeek-spool`

#### Filebeat
- **Purpose:** Log forwarder (Suricata/Zeek → Wazuh Indexer)
- **Image:** `docker.elastic.co/beats/filebeat:8.11.3`
- **Dependencies:** Wazuh Indexer, Suricata, Zeek

### Development Environment

#### PostgreSQL
- **Purpose:** Relational database for metadata and structured data
- **Image:** `postgres:16.2-alpine`
- **Port:** 5432
- **Database:** aisoc_metadata

#### Redis
- **Purpose:** In-memory cache for sessions and rate limiting
- **Image:** `redis:7.2.4-alpine`
- **Port:** 6379

#### Jupyter Lab
- **Purpose:** Interactive notebook environment for data analysis
- **Image:** `jupyter/scipy-notebook:python-3.11`
- **Port:** 8888

#### Portainer
- **Purpose:** Docker container management UI
- **Image:** `portainer/portainer-ce:2.19.5-alpine`
- **Ports:** 9000 (HTTP), 9443 (HTTPS)

---

## Configuration

### Environment Variables

All configuration is managed via `.env` file. See `.env.example` for complete reference.

**Critical Variables:**
```bash
# Wazuh
INDEXER_PASSWORD=<secure-password>
API_PASSWORD=<secure-password>

# Network
MONITOR_INTERFACE=eth0

# Development
POSTGRES_PASSWORD=<secure-password>
REDIS_PASSWORD=<secure-password>
JUPYTER_TOKEN=<secure-token>
```

### Custom Rules and Decoders (Wazuh)

Add custom rules to `docker-compose/config/wazuh-manager/rules/`:
```xml
<!-- Example: custom-rules.xml -->
<group name="custom_rules">
  <rule id="100001" level="5">
    <if_sid>5710</if_sid>
    <match>Failed password</match>
    <description>SSH brute force attempt detected</description>
  </rule>
</group>
```

### Suricata Rules

Custom rules in `docker-compose/config/suricata/rules/local.rules`:
```bash
alert tcp any any -> $HOME_NET 22 (msg:"SSH Connection Attempt"; sid:1000001; rev:1;)
```

### Zeek Scripts

Custom scripts in `docker-compose/config/zeek/site/`:
```zeek
# custom-logging.zeek
@load base/protocols/http
event http_request(c: connection, method: string, original_URI: string) {
    print fmt("HTTP Request: %s %s", method, original_URI);
}
```

---

## Network Architecture

### Docker Networks

| Network | Subnet | Purpose | Services |
|---------|--------|---------|----------|
| **siem-backend** | 172.20.0.0/24 | Internal SIEM | Indexer, Manager, Filebeat |
| **siem-frontend** | 172.21.0.0/24 | Dashboard access | Manager, Dashboard |
| **dev-backend** | 172.22.0.0/24 | Databases | PostgreSQL, Redis, Jupyter |
| **dev-frontend** | 172.23.0.0/24 | Development UI | Jupyter, Portainer, Adminer |

### Port Mapping

| Service | Internal Port | External Port | Protocol |
|---------|---------------|---------------|----------|
| Wazuh Indexer | 9200 | 9200 | HTTPS |
| Wazuh Manager (API) | 55000 | 55000 | HTTPS |
| Wazuh Manager (Agents) | 1514 | 1514 | TCP |
| Wazuh Dashboard | 5601 | 443 | HTTPS |
| PostgreSQL | 5432 | 5432 | TCP |
| Redis | 6379 | 6379 | TCP |
| Jupyter Lab | 8888 | 8888 | HTTP |
| Portainer | 9443 | 9443 | HTTPS |

---

## Storage and Volumes

### Volume Overview

| Volume | Purpose | Size (Typical) | Backup Priority |
|--------|---------|----------------|-----------------|
| `wazuh-indexer-data` | Event storage | 50-200 GB | CRITICAL |
| `wazuh-manager-data` | Rules, agents | 5-10 GB | CRITICAL |
| `wazuh-manager-logs` | Manager logs | 10-50 GB | HIGH |
| `suricata-logs` | IDS alerts | 5-20 GB | HIGH |
| `zeek-logs` | Network metadata | 10-50 GB | HIGH |
| `postgres-data` | Metadata DB | 5-10 GB | CRITICAL |
| `jupyter-data` | Notebooks | 1-5 GB | MEDIUM |

### Volume Management

**List volumes:**
```bash
docker volume ls
```

**Inspect volume:**
```bash
docker volume inspect wazuh-indexer-data
```

**Backup volume:**
```bash
docker run --rm -v wazuh-indexer-data:/data -v $(pwd):/backup alpine tar czf /backup/indexer-backup-$(date +%Y%m%d).tar.gz /data
```

**Restore volume:**
```bash
docker run --rm -v wazuh-indexer-data:/data -v $(pwd):/backup alpine tar xzf /backup/indexer-backup-20251013.tar.gz -C /
```

---

## Security Considerations

### 1. Password Security
- **Never use default passwords**
- Use 32+ character passwords with alphanumeric + symbols
- Rotate passwords every 90 days
- Store passwords in a secure vault (e.g., HashiCorp Vault, 1Password)

### 2. Network Security
- **Restrict access with firewall rules:**
```bash
# Allow only specific IPs to access dashboard
sudo ufw allow from 192.168.1.0/24 to any port 443
sudo ufw enable
```

- **Use VPN for remote access**
- **Enable TLS/SSL for all services**

### 3. Container Security
- Run containers as non-root where possible
- Enable Docker Content Trust: `export DOCKER_CONTENT_TRUST=1`
- Scan images for vulnerabilities:
```bash
docker scan wazuh/wazuh-manager:4.8.2
```

### 4. Certificate Management
- Use trusted CA certificates in production
- Rotate certificates every 365 days
- Monitor certificate expiration:
```bash
openssl x509 -in certificate.pem -noout -dates
```

### 5. Audit Logging
- Enable Docker audit logging
- Monitor authentication failures
- Review logs regularly

---

## Monitoring and Health Checks

### Container Health Status

```bash
# Check all container health
docker compose -f phase1-siem-core.yml ps

# Watch health status in real-time
watch -n 2 'docker compose -f phase1-siem-core.yml ps'
```

### Service-Specific Health Checks

**Wazuh Indexer:**
```bash
curl -k -u admin:PASSWORD https://localhost:9200/_cluster/health?pretty
```

**Wazuh Manager:**
```bash
docker exec wazuh-manager /var/ossec/bin/wazuh-control status
```

**Suricata:**
```bash
docker exec suricata suricatasc -c "uptime"
```

**Zeek:**
```bash
docker exec zeek zeekctl status
```

### Resource Monitoring

**Container resource usage:**
```bash
docker stats
```

**Detailed container metrics:**
```bash
docker inspect wazuh-manager | jq '.[0].State'
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Wazuh Indexer Fails to Start
**Symptom:** `max virtual memory areas vm.max_map_count [65530] is too low`

**Solution:**
```bash
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

#### Issue 2: Network Monitoring Not Capturing Traffic
**Symptom:** Suricata/Zeek show no traffic

**Solution:**
```bash
# Verify interface name
ip link show

# Update .env with correct interface
MONITOR_INTERFACE=ens33

# Restart containers
docker compose -f phase1-siem-core.yml restart suricata zeek
```

#### Issue 3: Dashboard Connection Refused
**Symptom:** Cannot access https://localhost:443

**Solution:**
```bash
# Check dashboard logs
docker logs wazuh-dashboard

# Verify Wazuh Manager is healthy
docker exec wazuh-manager curl -k https://localhost:55000/

# Restart dashboard
docker compose -f phase1-siem-core.yml restart wazuh-dashboard
```

#### Issue 4: Out of Memory Errors
**Symptom:** Containers crashing with OOM errors

**Solution:**
```bash
# Check available memory
free -h

# Reduce memory limits in docker-compose file
# Edit phase1-siem-core.yml and reduce deploy.resources.limits.memory

# Restart with new limits
docker compose -f phase1-siem-core.yml up -d
```

#### Issue 5: Permission Denied Errors
**Symptom:** Container fails with permission errors

**Solution:**
```bash
# Fix ownership of mounted directories
sudo chown -R 1000:1000 docker-compose/config
sudo chmod -R 755 docker-compose/config

# For Zeek logs
sudo chown -R root:root docker-compose/config/zeek
```

### Debugging Commands

**View logs:**
```bash
# All services
docker compose -f phase1-siem-core.yml logs -f

# Specific service
docker logs -f wazuh-manager

# Last 100 lines
docker logs --tail 100 wazuh-indexer
```

**Execute commands inside container:**
```bash
docker exec -it wazuh-manager bash
```

**Inspect container configuration:**
```bash
docker inspect wazuh-manager | jq
```

**Network troubleshooting:**
```bash
# Test connectivity between containers
docker exec wazuh-manager curl -k https://wazuh-indexer:9200

# Inspect network
docker network inspect siem-backend
```

---

## Maintenance Operations

### Starting Services

```bash
# Start all Phase 1 services
docker compose -f phase1-siem-core.yml up -d

# Start specific service
docker compose -f phase1-siem-core.yml up -d wazuh-manager

# Start and view logs
docker compose -f phase1-siem-core.yml up
```

### Stopping Services

```bash
# Stop all services (preserve data)
docker compose -f phase1-siem-core.yml down

# Stop and remove volumes (DELETE ALL DATA)
docker compose -f phase1-siem-core.yml down -v

# Stop specific service
docker compose -f phase1-siem-core.yml stop wazuh-dashboard
```

### Restarting Services

```bash
# Restart all services
docker compose -f phase1-siem-core.yml restart

# Restart specific service
docker compose -f phase1-siem-core.yml restart wazuh-manager
```

### Updating Services

```bash
# Pull latest images
docker compose -f phase1-siem-core.yml pull

# Recreate containers with new images
docker compose -f phase1-siem-core.yml up -d --force-recreate

# Verify new versions
docker compose -f phase1-siem-core.yml images
```

### Scaling Services

```bash
# Scale filebeat to 2 instances (if supported)
docker compose -f phase1-siem-core.yml up -d --scale filebeat=2
```

---

## Performance Tuning

### OpenSearch/Wazuh Indexer

**Heap Size (in .env or docker-compose):**
```yaml
environment:
  - "OPENSEARCH_JAVA_OPTS=-Xms4g -Xmx4g"  # Use 50% of available RAM
```

**Index Management:**
```bash
# Delete old indices
curl -k -u admin:PASSWORD -X DELETE https://localhost:9200/wazuh-alerts-4.x-2024.01.*

# Create index lifecycle policy
curl -k -u admin:PASSWORD -X PUT https://localhost:9200/_plugins/_ism/policies/wazuh-policy
```

### Suricata Performance

**Increase worker threads:**
```yaml
# suricata.yaml
threading:
  set-cpu-affinity: yes
  cpu-affinity:
    - management-cpu-set:
        cpu: [ 0 ]
    - receive-cpu-set:
        cpu: [ 1-3 ]
    - worker-cpu-set:
        cpu: [ 4-7 ]
```

### PostgreSQL Tuning

**Memory settings (based on 8GB RAM):**
```sql
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
work_mem = 16MB
```

---

## Backup and Recovery

### Automated Backup Script

```bash
#!/bin/bash
# backup-ai-soc.sh

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup Wazuh Indexer
docker run --rm -v wazuh-indexer-data:/data -v "$BACKUP_DIR":/backup alpine tar czf /backup/indexer.tar.gz /data

# Backup PostgreSQL
docker exec ai-soc-postgres pg_dump -U aisoc aisoc_metadata | gzip > "$BACKUP_DIR/postgres.sql.gz"

# Backup configurations
tar czf "$BACKUP_DIR/configs.tar.gz" docker-compose/config .env

echo "Backup completed: $BACKUP_DIR"
```

### Restore Procedure

```bash
# Restore Wazuh Indexer
docker run --rm -v wazuh-indexer-data:/data -v "$BACKUP_DIR":/backup alpine tar xzf /backup/indexer.tar.gz -C /

# Restore PostgreSQL
zcat "$BACKUP_DIR/postgres.sql.gz" | docker exec -i ai-soc-postgres psql -U aisoc aisoc_metadata

# Restore configurations
tar xzf "$BACKUP_DIR/configs.tar.gz"
```

---

## Additional Resources

### Official Documentation
- **Wazuh:** https://documentation.wazuh.com/current/docker/index.html
- **Suricata:** https://docs.suricata.io/
- **Zeek:** https://docs.zeek.org/
- **Docker Compose:** https://docs.docker.com/compose/

### AI-SOC Project
- **GitHub Repository:** https://github.com/zhadyz/AI_SOC
- **ROADMAP:** See `ROADMAP.md` in project root
- **Issue Tracker:** GitHub Issues

### Support
- **Email:** abdul.bari8019@coyote.csusb.edu
- **GitHub Discussions:** https://github.com/zhadyz/AI_SOC/discussions

---

**Last Updated:** 2025-10-13
**Author:** ZHADYZ DevOps Agent
**Version:** 1.0.0

**Built with resilience and security in mind.**
