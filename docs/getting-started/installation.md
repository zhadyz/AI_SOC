# Installation Guide

This document provides comprehensive instructions for installing and deploying the AI-Augmented Security Operations Center (AI-SOC) platform.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [System Requirements](#system-requirements)
3. [Installation Methods](#installation-methods)
4. [Post-Installation Verification](#post-installation-verification)
5. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

#### Docker Desktop / Docker Engine
- **Version**: 24.0 or higher
- **Components**: Docker Engine + Docker Compose V2
- **Configuration**:
  - Windows: WSL2 backend enabled
  - Linux: Native Docker installation
  - macOS: Docker Desktop with sufficient resource allocation

**Installation:**
```bash
# Linux (Ubuntu/Debian)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Verify installation
docker --version  # Should be 24.0+
docker compose version  # Should be v2.x
```

#### Git
- **Version**: 2.30 or higher
- **Purpose**: Repository cloning and version control

```bash
# Verify installation
git --version
```

### System Requirements

See [System Requirements](requirements.md) for detailed hardware specifications.

**Minimum:**
- CPU: 4 cores (8 threads)
- RAM: 16GB
- Disk: 50GB available SSD storage
- Network: Broadband internet (for initial image downloads)

**Recommended:**
- CPU: 8 cores (16 threads)
- RAM: 32GB
- Disk: 100GB NVMe SSD
- Network: 1Gbps

---

## Installation Methods

The AI-SOC platform provides three deployment methods optimized for different user profiles:

### Method 1: Quick Start (Recommended for Most Users)

This automated deployment method handles all configuration and deployment steps.

**Windows:**
```bash
# 1. Clone repository
git clone https://github.com/zhadyz/AI_SOC.git
cd AI_SOC

# 2. Run deployment script
.\quickstart.sh  # Via Git Bash or WSL2

# OR double-click: START-AI-SOC.bat (graphical launcher)
```

**Linux/macOS:**
```bash
# 1. Clone repository
git clone https://github.com/zhadyz/AI_SOC.git
cd AI_SOC

# 2. Make script executable
chmod +x quickstart.sh

# 3. Run deployment
./quickstart.sh
```

**What the Quick Start Does:**
1. Validates system prerequisites (Docker, resources)
2. Generates SSL/TLS certificates
3. Configures environment variables
4. Builds custom Docker images
5. Deploys core services
6. Validates deployment health
7. Provides access URLs

**Deployment Time:** 10-15 minutes (including downloads)

---

### Method 2: Manual Deployment (Advanced Users)

For users requiring custom configuration or troubleshooting.

#### Step 1: Clone Repository
```bash
git clone https://github.com/zhadyz/AI_SOC.git
cd AI_SOC
```

#### Step 2: Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your configuration
nano .env  # or use any text editor
```

**Critical Environment Variables:**
```bash
# SIEM Credentials
INDEXER_PASSWORD=SecurePassword123!
API_PASSWORD=SecurePassword456!

# Service Endpoints
ML_INFERENCE_URL=http://ml-inference:8500
ALERT_TRIAGE_URL=http://alert-triage:8100
RAG_SERVICE_URL=http://rag-service:8300

# Resource Limits
WAZUH_MANAGER_MEMORY=2g
WAZUH_INDEXER_MEMORY=4g
```

#### Step 3: Generate SSL Certificates
```bash
cd docker-compose
./generate-certs.sh  # Creates self-signed certs for development
```

#### Step 4: Deploy Core Services

**Option A: Full Deployment (All Services)**
```bash
# Deploy SIEM stack
docker compose -f phase1-siem-core-windows.yml up -d

# Wait for initialization (5-10 minutes)
docker compose -f phase1-siem-core-windows.yml logs -f wazuh-manager

# Deploy AI services
docker compose -f ai-services.yml up -d

# Deploy monitoring
docker compose -f monitoring-stack.yml up -d
```

**Option B: Incremental Deployment (Layer by Layer)**
```bash
# 1. SIEM Core (Foundation)
docker compose -f phase1-siem-core-windows.yml up -d
# Verify: https://localhost:443

# 2. AI Services
docker compose -f ai-services.yml up -d
# Verify: http://localhost:8500/docs

# 3. Monitoring
docker compose -f monitoring-stack.yml up -d
# Verify: http://localhost:3000
```

#### Step 5: Verify Deployment
```bash
# Check all containers
docker ps

# Verify health
docker compose -f phase1-siem-core-windows.yml ps
docker compose -f ai-services.yml ps

# Test API endpoints
curl http://localhost:8500/health  # ML Inference
curl http://localhost:8100/health  # Alert Triage
curl http://localhost:8300/health  # RAG Service
```

---

### Method 3: Production Deployment

For enterprise deployments requiring high availability, security hardening, and monitoring.

See [Production Deployment Guide](../deployment/production.md) for:
- Multi-node cluster configuration
- Load balancing and high availability
- Security hardening procedures
- Automated backup and disaster recovery
- Monitoring and alerting setup
- Performance optimization

---

## Post-Installation Verification

### Automated Validation Script

The repository includes a comprehensive validation tool:

```bash
cd tests
python validate_deployment.py
```

**Validation Checks:**
- [ ] Docker daemon running
- [ ] All containers in 'healthy' state
- [ ] Network connectivity between services
- [ ] API endpoints responding
- [ ] Database connectivity
- [ ] ML models loaded correctly
- [ ] MITRE ATT&CK knowledge base populated
- [ ] Web dashboards accessible

### Manual Verification Checklist

#### 1. Container Health
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Expected Output:**
```
NAMES                   STATUS                  PORTS
wazuh-manager          Up (healthy)            1514-1515, 55000
wazuh-indexer          Up (healthy)            9200, 9300
wazuh-dashboard        Up (healthy)            0.0.0.0:443->5601
ml-inference           Up (healthy)            0.0.0.0:8500->8500
alert-triage           Up (healthy)            0.0.0.0:8100->8100
rag-service            Up (healthy)            0.0.0.0:8300->8300
```

#### 2. Web Interface Access

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Wazuh Dashboard | https://localhost:443 | admin / admin |
| Grafana | http://localhost:3000 | admin / admin |
| ML Inference API | http://localhost:8500/docs | N/A (OpenAPI docs) |
| Alert Triage API | http://localhost:8100/docs | N/A (OpenAPI docs) |
| RAG Service API | http://localhost:8300/docs | N/A (OpenAPI docs) |

#### 3. Service Health Endpoints

Test all health check endpoints:

```bash
# ML Inference Service
curl -s http://localhost:8500/health | jq

# Expected response:
{
  "status": "healthy",
  "models_loaded": 3,
  "model_names": ["random_forest", "xgboost", "decision_tree"],
  "uptime_seconds": 3600
}
```

```bash
# Alert Triage Service
curl -s http://localhost:8100/health | jq

# RAG Service
curl -s http://localhost:8300/health | jq
```

#### 4. ML Model Inference Test

Verify ML prediction capability:

```bash
curl -X POST http://localhost:8500/predict \
  -H "Content-Type: application/json" \
  -d '{
    "features": [/* 79 network features */],
    "model": "random_forest"
  }' | jq
```

**Expected Response:**
```json
{
  "prediction": "ATTACK",
  "confidence": 0.9856,
  "model": "random_forest",
  "inference_time_ms": 0.8
}
```

#### 5. Log Ingestion Test

Verify Wazuh can receive and index logs:

```bash
# Send test alert
logger -t test "AI-SOC deployment test alert"

# Query Wazuh API
curl -u admin:admin -X GET \
  "https://localhost:9200/_cat/indices?v" \
  --insecure
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Docker Daemon Not Running
**Symptoms:**
```
Error: Cannot connect to the Docker daemon
```

**Solution:**
```bash
# Linux
sudo systemctl start docker
sudo systemctl enable docker

# Windows/macOS
# Start Docker Desktop application
```

---

#### Issue 2: Port Conflicts
**Symptoms:**
```
Error: bind: address already in use
```

**Solution:**
```bash
# Find process using port (example: 443)
# Linux/macOS
sudo lsof -i :443

# Windows
netstat -ano | findstr :443

# Kill conflicting process or change AI-SOC port mapping
# Edit docker-compose/*.yml files to use alternative ports
```

---

#### Issue 3: Insufficient Resources
**Symptoms:**
```
Container exits with code 137 (OOM killed)
Slow performance or container restarts
```

**Solution:**
```bash
# Check available resources
docker system df
free -h  # Linux
systeminfo | findstr Memory  # Windows

# Increase Docker Desktop resource allocation:
# Settings → Resources → Advanced
# Increase: RAM to 16GB+, CPUs to 4+
```

---

#### Issue 4: SSL Certificate Errors
**Symptoms:**
```
curl: (60) SSL certificate problem: self signed certificate
```

**Solution:**
```bash
# Option 1: Use --insecure flag (development only)
curl --insecure https://localhost:443

# Option 2: Trust self-signed certificate (Linux)
sudo cp certs/root-ca.pem /usr/local/share/ca-certificates/ai-soc-ca.crt
sudo update-ca-certificates

# Option 3: Use production certificates
# Replace certs in docker-compose/certs/ with valid CA-signed certificates
```

---

#### Issue 5: Wazuh Indexer Authentication Failures
**Symptoms:**
```
ERROR: [publisher_pipeline_output] Failed to connect: 401 Unauthorized
```

**Solution:**
```bash
# 1. Verify credentials in .env match docker-compose configuration
grep INDEXER_PASSWORD .env

# 2. Recreate Docker volumes (WARNING: Deletes data)
docker compose -f docker-compose/phase1-siem-core-windows.yml down -v
docker compose -f docker-compose/phase1-siem-core-windows.yml up -d

# 3. Manually verify OpenSearch connection
curl -u admin:admin -X GET \
  "https://localhost:9200/_cluster/health?pretty" \
  --insecure
```

---

#### Issue 6: ML Models Not Loading
**Symptoms:**
```
FileNotFoundError: models/random_forest_ids.pkl not found
```

**Solution:**
```bash
# Verify models exist
ls -lh models/

# If models missing, train them:
cd evaluation
python baseline_models.py

# Rebuild ML inference container
docker compose -f docker-compose/ai-services.yml build ml-inference
docker compose -f docker-compose/ai-services.yml up -d ml-inference
```

---

### Diagnostic Commands

#### View Container Logs
```bash
# Real-time logs for all services
docker compose -f docker-compose/phase1-siem-core-windows.yml logs -f

# Specific service logs
docker logs wazuh-manager --tail 100

# ML inference service logs
docker logs ml-inference --since 10m
```

#### Check Resource Usage
```bash
# Container resource stats
docker stats

# Disk usage
docker system df -v
```

#### Network Debugging
```bash
# Inspect Docker networks
docker network ls
docker network inspect ai_soc_siem-backend

# Test connectivity between containers
docker exec wazuh-manager ping wazuh-indexer
docker exec ml-inference curl http://alert-triage:8100/health
```

---

## Support Resources

### Documentation
- [Quick Start Guide](quickstart.md)
- [System Requirements](requirements.md)
- [User Guide](user-guide.md)
- [Deployment Guide](../deployment/guide.md)

### Community
- **GitHub Issues**: https://github.com/zhadyz/AI_SOC/issues
- **Discussions**: https://github.com/zhadyz/AI_SOC/discussions
- **Email Support**: abdul.bari8019@coyote.csusb.edu

### Logs and Diagnostics
```bash
# Generate diagnostic report
./scripts/generate-diagnostic-report.sh

# Creates: diagnostic-report-YYYYMMDD-HHMMSS.tar.gz
# Contains: logs, configs, system info
# Share with support team for troubleshooting
```

---

## Next Steps

After successful installation:

1. **Complete Initial Configuration**
   - Change default passwords
   - Configure alert notification channels
   - Set up user accounts

2. **Load Test Data**
   - Import CICIDS2017 dataset
   - Generate sample alerts
   - Validate ML predictions

3. **Configure Monitoring**
   - Set up Grafana dashboards
   - Configure AlertManager notifications
   - Test alert workflows

4. **Security Hardening** (Before Production)
   - See [Security Guide](../security/guide.md)
   - See [Hardening Procedures](../security/hardening.md)

5. **User Training**
   - See [User Guide](user-guide.md)
   - Review API documentation
   - Practice incident response workflows

---

**Installation Guide Version:** 1.0
**Last Updated:** October 24, 2025
**Maintained By:** AI-SOC Development Team
