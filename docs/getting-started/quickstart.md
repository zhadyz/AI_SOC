# Getting Started with AI-SOC

## System Deployment Guide

This document provides comprehensive instructions for deploying the AI-Augmented Security Operations Center (AI-SOC) platform. The deployment process has been designed to minimize technical complexity while maintaining enterprise-grade security and performance standards.

---

## Prerequisites

### Required Software Components

The AI-SOC platform requires two foundational software packages for operation. Both components are freely available and must be installed prior to system deployment.

### 1. Docker Desktop

Docker Desktop provides the containerization infrastructure necessary for AI-SOC service orchestration. The platform utilizes Docker Compose for multi-container deployment and management.

**Installation Procedure (Windows):**
1. Navigate to https://www.docker.com/products/docker-desktop/
2. Execute the installer package
3. Select "Use WSL 2" (Windows Subsystem for Linux 2) when prompted
4. Complete system restart as required
5. Verify Docker Desktop initialization via system tray indicator

**Minimum System Requirements:**
- Memory: 16GB RAM (32GB recommended for optimal performance)
- Storage: 50GB available disk space
- Operating System: Windows 10/11 (Professional or Home edition)

### 2. Python Runtime Environment

Python 3.x serves as the runtime environment for the graphical launcher interface and web dashboard components.

**Installation Procedure:**
1. Download installer from https://www.python.org/downloads/
2. Execute installer package
3. Select "Add Python to PATH" during installation (critical requirement)
4. Complete installation using default configuration

**Note:** The "Add to PATH" option ensures command-line accessibility for the launcher scripts.

---

## System Initialization

### Primary Deployment Method

The AI-SOC platform provides a graphical launcher interface for simplified deployment. This method is recommended for standard operational use.

**Execution Procedure:**

1. Navigate to the AI_SOC installation directory
2. Execute `START-AI-SOC.bat` via double-click operation
3. The graphical control interface will initialize
4. Select "START AI-SOC" to initiate service deployment
5. Allow 1-2 minutes for complete service initialization
6. Select "Open Dashboard" to access the web-based monitoring interface

**Expected Behavior:** The launcher will automatically validate prerequisites, install required Python dependencies, and initialize the control interface.

### Alternative Deployment Method

For command-line operation, the launcher may be invoked directly:

```bash
python AI-SOC-Launcher.py
```

This method provides identical functionality through a terminal-based workflow.

---

## Control Interface Operations

The graphical control interface provides comprehensive system management capabilities through an integrated dashboard.

### Status Indicators

The interface employs color-coded status indicators for real-time system health monitoring:

- **Green**: All services operational and healthy
- **Yellow**: Services in initialization state (transient)
- **Red**: Service failure or attention required (consult system log)

### Control Functions

The interface provides the following operational controls:

- **START AI-SOC**: Initiates all platform services via Docker Compose orchestration
- **STOP AI-SOC**: Gracefully terminates all running services
- **Open Dashboard**: Launches the web-based monitoring interface in the default browser

### Service Monitoring

The status panel displays real-time operational state for all platform components:

- Wazuh Indexer (OpenSearch database backend)
- Wazuh Manager (SIEM core and security event processing)
- ML Inference (Machine learning threat detection engine)
- Alert Triage (Intelligent alert prioritization service)
- RAG Service (Retrieval-Augmented Generation knowledge base)

### System Log

The integrated log console displays real-time system events, service initialization progress, and diagnostic information.

---

## Web-Based Monitoring Interface

Following successful system initialization, the web dashboard provides comprehensive real-time monitoring capabilities.

**Access URL:** http://localhost:3000

### Dashboard Features

The monitoring interface provides the following information panels:

- **System Status**: Overall platform health indicator (color-coded: green = operational, yellow = initializing, red = service failure)
- **Service Count**: Quantitative metric displaying number of active services versus total deployed services
- **Service Details**: Individual health status for each microservice component
- **Auto-Refresh**: Automatic status updates every 5 seconds via asynchronous polling

---

## Troubleshooting Guide

### Docker Not Installed

**Symptom:** Launcher reports Docker is not installed or not found.

**Resolution:**
- Complete Docker Desktop installation as described in Prerequisites section
- Verify Docker Desktop is running via system tray indicator

### Docker Service Not Running

**Symptom:** Services fail to start with Docker daemon error.

**Resolution:**
- Locate Docker Desktop icon in system tray
- Right-click and select "Start" to initialize Docker daemon
- Wait for status message "Docker Desktop is running"

### Python Runtime Not Found

**Symptom:** Batch launcher reports Python is not installed or not in PATH.

**Resolution:**
- Reinstall Python runtime environment
- Ensure "Add Python to PATH" option is selected during installation

### Service Initialization Failures

**Symptom:** One or more services fail to start or remain in unhealthy state.

**Diagnostic Steps:**
1. Verify Docker Desktop is operational
2. Confirm system meets minimum RAM requirements (16GB)
3. Close resource-intensive applications to free system memory
4. Attempt system restart to clear transient resource constraints

### General Recovery Procedure

For persistent initialization failures:

1. Execute STOP AI-SOC to gracefully terminate all services
2. Wait 30 seconds for complete service shutdown
3. Execute START AI-SOC to reinitialize deployment

---

## Platform Architecture Overview

### Service Component Descriptions

The AI-SOC platform consists of six primary microservice components operating in coordinated fashion:

### Wazuh Indexer (Data Persistence Layer)
OpenSearch-based database backend providing persistent storage for security events, logs, and analytical data. Implements distributed search and aggregation capabilities for historical threat analysis.

### Wazuh Manager (SIEM Core)
Central security information and event management engine. Performs real-time log collection, correlation, and security event processing. Integrates with network agents for distributed monitoring.

### ML Inference Engine (Threat Detection)
Machine learning-based intrusion detection system trained on CICIDS2017 dataset. Achieves 99.28% classification accuracy for network-based threats using ensemble classification methods.

### Alert Triage Service (Prioritization Layer)
Intelligent alert filtering and prioritization service. Reduces false positive rates through multi-factor severity assessment and contextual analysis.

### RAG Service (Knowledge Augmentation)
Retrieval-Augmented Generation service providing contextual threat intelligence. Supplies natural language explanations for detected security events using vector-based knowledge retrieval.

### ChromaDB (Vector Database)
Embedding storage for RAG service. Maintains vector representations of threat intelligence data for semantic similarity search and knowledge retrieval operations.

---

## Advanced Operations

Following successful deployment, the platform provides access to individual service endpoints for advanced integration:

1. **Wazuh Web Interface**: https://localhost:443 (SIEM dashboard and configuration)
2. **ML Inference API**: http://localhost:8500 (threat classification endpoint)
3. **Alert Triage API**: http://localhost:8100 (alert management interface)

---

## Operational Best Practices

### Recommended Procedures

- Maintain Docker Desktop in running state during AI-SOC operation
- Allow 2-3 minutes for complete service initialization before accessing endpoints
- Monitor system health via web dashboard at regular intervals
- Execute graceful shutdown via STOP AI-SOC when platform is not required (conserves system resources)

### Prohibited Operations

- Do not terminate Docker Desktop while AI-SOC services are running (may cause data corruption)
- Do not manually stop containers via Docker CLI (bypasses graceful shutdown procedures)
- Do not attempt deployment on systems with less than 16GB RAM (insufficient resources)
- Do not interrupt service initialization sequence (allow full startup cycle)

---

## Deployment Verification

Upon successful deployment, verify the following conditions are met:

1. Docker Desktop operational and running
2. Python runtime environment installed with PATH configuration
3. START-AI-SOC.bat executed successfully
4. All services reporting healthy status in control interface
5. Web dashboard accessible and displaying current system state
6. No error messages in system log console

For diagnostic assistance, consult the integrated log console or refer to the Troubleshooting Guide section.

---

## Security Configuration

### Default Credentials

The platform ships with default authentication credentials defined in the `.env` configuration file. These credentials are suitable for development and testing environments.

### Production Security Requirements

For production deployment or external network exposure, the following security hardening procedures are mandatory:

1. Modify all default passwords in `.env` configuration file
2. Enable SSL/TLS certificate-based encryption for all service endpoints
3. Implement network-level access controls via firewall configuration
4. Follow comprehensive security hardening procedures documented in `/docs/security-hardening.md`
5. Establish regular security update and patch management procedures

### Development and Testing Environments

For isolated testing, laboratory research, or educational purposes, default security configuration is acceptable provided the platform is not exposed to untrusted networks.
