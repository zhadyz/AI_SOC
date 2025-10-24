# System Requirements

This document specifies the hardware, software, and network requirements for deploying the AI-Augmented Security Operations Center (AI-SOC) platform.

---

## Hardware Requirements

### Minimum Configuration

Sufficient for development, testing, and small-scale deployments (< 1,000 events/day).

| Component | Specification | Notes |
|-----------|---------------|-------|
| **CPU** | 4 physical cores (8 threads) | Intel i5/i7, AMD Ryzen 5/7, or equivalent |
| **RAM** | 16GB | 8GB for SIEM stack, 4GB for AI services, 4GB for OS |
| **Storage** | 50GB SSD | NVMe/SATA SSD required for acceptable performance |
| **Network** | 100Mbps | For initial Docker image downloads (~5GB) |

### Recommended Configuration

Optimized for production deployments, enterprise environments, and high-throughput scenarios (10,000+ events/day).

| Component | Specification | Notes |
|-----------|---------------|-------|
| **CPU** | 8 physical cores (16 threads) | Intel Xeon, AMD EPYC, or high-end desktop processors |
| **RAM** | 32GB | 16GB for SIEM, 8GB for AI services, 8GB for OS/cache |
| **Storage** | 100GB NVMe SSD | M.2 NVMe for maximum IOPS |
| **Network** | 1Gbps | Low-latency network for distributed components |

---

## Software Requirements

### Operating System

#### Supported Operating Systems

| OS | Version | Notes |
|----|---------|-------|
| **Ubuntu** | 20.04 LTS, 22.04 LTS | Recommended for production |
| **Debian** | 11 (Bullseye), 12 (Bookworm) | Stable, well-tested |
| **CentOS/RHEL** | 8.x, 9.x | Enterprise deployments |
| **Windows** | 10 Pro/Enterprise, 11 Pro, Server 2019/2022 | Requires WSL2 for network analysis |
| **macOS** | 11 (Big Sur) or later | Docker Desktop required |

### Container Runtime

**Docker Engine:** Version 24.0 or higher
**Docker Compose:** V2.x

Verification:
```bash
docker --version    # Should be 24.0+
docker compose version  # Should be v2.x
```

---

## Network Requirements

### Required Ports

| Port | Service | Purpose |
|------|---------|---------|
| **443** | Wazuh Dashboard | Web UI access |
| **8500** | ML Inference API | Model predictions |
| **8100** | Alert Triage API | Alert prioritization |
| **8300** | RAG Service API | Threat intelligence |
| **3000** | Grafana | Monitoring dashboards |
| **9200** | Wazuh Indexer | OpenSearch API |

---

## Performance Expectations

| Metric | Minimum Config | Recommended Config |
|--------|----------------|-------------------|
| **ML Inference** | 2-5ms | <1ms |
| **Event Throughput** | 500/sec | 10,000/sec |
| **Concurrent Users** | 5 | 50 |
| **Query Response** | 1-3s | <500ms |

---

## Pre-Deployment Validation

Verify system meets requirements:

```bash
# CPU cores
nproc  # Linux

# Memory
free -h  # Linux

# Disk space
df -h  # Linux

# Docker version
docker --version
```

See [Installation Guide](installation.md) for complete deployment procedures.

---

**Requirements Specification Version:** 1.0
**Last Updated:** October 24, 2025
