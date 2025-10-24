# AI-SOC Testing Framework

**Author:** LOVELESS (Elite QA Specialist)
**Mission:** OPERATION TEST-FORTRESS
**Date:** 2025-10-22

Comprehensive testing infrastructure for the AI-Augmented Security Operations Center.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Quick Start](#quick-start)
- [Test Categories](#test-categories)
- [Running Tests](#running-tests)
- [CI/CD Integration](#cicd-integration)
- [Coverage Reports](#coverage-reports)
- [Contributing](#contributing)

---

## 🎯 Overview

This testing framework provides comprehensive coverage for all AI-SOC components:

- **Unit Tests:** Individual component testing
- **Integration Tests:** Service-to-service communication
- **End-to-End Tests:** Complete workflow validation
- **Security Tests:** OWASP Top 10 compliance
- **Load Tests:** Performance and stress testing
- **Browser Tests:** UI/dashboard testing

### Testing Philosophy

1. **Test-Driven Quality:** All code must have tests
2. **Continuous Validation:** Automated testing on every commit
3. **Security-First:** OWASP Top 10 coverage mandatory
4. **Performance Monitoring:** Load testing on every release
5. **Real-World Scenarios:** E2E tests mirror production workflows

---

## 📁 Test Structure

```
tests/
├── conftest.py                 # Pytest configuration and fixtures
├── requirements.txt            # Testing dependencies
├── README.md                   # This file
│
├── unit/                       # Unit tests
│   ├── test_alert_triage_service.py
│   ├── test_ml_inference.py
│   ├── test_rag_service.py
│   └── test_security_utilities.py
│
├── integration/                # Integration tests
│   ├── test_service_integration.py
│   └── test_data_flow.py
│
├── e2e/                        # End-to-end tests
│   ├── test_complete_workflows.py
│   └── test_incident_response.py
│
├── security/                   # Security tests
│   ├── test_owasp_top10.py
│   └── test_prompt_injection.py
│
├── load/                       # Load testing
│   ├── locustfile.py
│   └── k6_script.js
│
├── browser/                    # Browser tests
│   ├── test_dashboards.py
│   └── test_api_docs.py
│
└── fixtures/                   # Test data
    ├── sample_alerts.json
    ├── sample_network_flows.json
    └── sample_logs.json
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install testing requirements
pip install -r tests/requirements.txt

# Install Playwright browsers
playwright install
```

### 2. Run All Tests

```bash
# Run complete test suite
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=services --cov-report=html
```

### 3. Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/ -m unit

# Integration tests
pytest tests/integration/ -m integration

# Security tests
pytest tests/security/ -m security

# E2E tests (slow)
pytest tests/e2e/ -m e2e
```

---

## 🧪 Test Categories

### Unit Tests (`tests/unit/`)

**Purpose:** Test individual components in isolation

**Coverage:**
- Alert Triage Service models and endpoints
- ML Inference API predictions
- RAG Service retrieval
- Security utilities

**Example:**
```bash
pytest tests/unit/test_alert_triage_service.py -v
```

**Success Criteria:**
- ✅ All models validate correctly
- ✅ API endpoints return expected responses
- ✅ Error handling works properly
- ✅ Code coverage >80%

---

### Integration Tests (`tests/integration/`)

**Purpose:** Test service-to-service communication

**Coverage:**
- Alert Triage ↔ Ollama integration
- RAG Service ↔ ChromaDB integration
- ML Inference ↔ Alert Triage integration
- Multi-service health checks

**Example:**
```bash
pytest tests/integration/test_service_integration.py -v
```

**Success Criteria:**
- ✅ Services communicate correctly
- ✅ Data flows through pipelines
- ✅ Error propagation works
- ✅ Dependencies are validated

---

### End-to-End Tests (`tests/e2e/`)

**Purpose:** Test complete workflows from start to finish

**Workflows Tested:**
1. Network Traffic → ML Detection → Alert → Triage → Case → Response
2. Batch alert processing (20+ alerts)
3. Critical alert escalation
4. RAG-enhanced analysis
5. System resilience and recovery

**Example:**
```bash
pytest tests/e2e/test_complete_workflows.py -v --tb=short
```

**Success Criteria:**
- ✅ Complete workflows execute successfully
- ✅ End-to-end latency <30 seconds
- ✅ Success rate >95%
- ✅ Critical alerts escalate properly

---

### Security Tests (`tests/security/`)

**Purpose:** Validate security against OWASP Top 10

**Coverage:**
- A01: Broken Access Control
- A02: Cryptographic Failures
- A03: Injection (SQL, Command, NoSQL, LDAP)
- A04: Insecure Design
- A05: Security Misconfiguration
- A06: Vulnerable Components
- A07: Authentication Failures
- A08: Integrity Failures
- A09: Logging Failures
- A10: SSRF Prevention
- **LLM-Specific:** Prompt Injection

**Example:**
```bash
pytest tests/security/test_owasp_top10.py -m security -v
```

**Success Criteria:**
- ✅ 90%+ injection attack detection
- ✅ Sensitive data sanitized in logs
- ✅ Prompt injection detection >80%
- ✅ No critical vulnerabilities

---

### Load Tests (`tests/load/`)

**Purpose:** Performance and stress testing

**Tools:** Locust

**Scenarios:**
1. **Normal Load:** 10 users, 5 minutes
2. **High Load:** 50 users, 10 minutes
3. **Spike Load:** 100 users, 2 minutes
4. **Endurance:** 20 users, 30 minutes

**Example:**
```bash
# Web UI
locust -f tests/load/locustfile.py --host=http://localhost:8100

# Headless mode
locust -f tests/load/locustfile.py --headless -u 50 -r 10 --run-time 5m --host=http://localhost:8100
```

**Performance Targets:**
- 🎯 Alert Triage: <30s per request (with LLM)
- 🎯 ML Inference: <100ms per prediction
- 🎯 RAG Retrieval: <2s per query
- 🎯 Throughput: 10+ alerts/second
- 🎯 Success Rate: >95%

---

### Browser Tests (`tests/browser/`)

**Purpose:** UI and dashboard testing

**Tools:** Playwright (cross-browser)

**Dashboards Tested:**
- Wazuh Dashboard
- Grafana Monitoring
- TheHive Case Management
- FastAPI Documentation

**Example:**
```bash
# Run with visible browser
pytest tests/browser/test_dashboards.py --headed

# Cross-browser testing
pytest tests/browser/test_dashboards.py --browser firefox
pytest tests/browser/test_dashboards.py --browser webkit
```

**Success Criteria:**
- ✅ All dashboards load correctly
- ✅ Key functionality works
- ✅ Responsive design validated
- ✅ Screenshots captured for docs

---

## 🔧 Running Tests

### Basic Usage

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Run last failed tests only
pytest --lf
```

### By Marker

```bash
# Unit tests only
pytest -m unit

# Integration tests
pytest -m integration

# Security tests
pytest -m security

# Exclude slow tests
pytest -m "not slow"

# Multiple markers
pytest -m "unit or integration"
```

### By Path

```bash
# Specific directory
pytest tests/unit/

# Specific file
pytest tests/unit/test_alert_triage_service.py

# Specific test
pytest tests/unit/test_alert_triage_service.py::TestSecurityAlertModel::test_valid_alert_creation
```

### With Coverage

```bash
# Coverage report
pytest --cov=services --cov-report=term

# HTML coverage report
pytest --cov=services --cov-report=html
open htmlcov/index.html

# XML coverage for CI/CD
pytest --cov=services --cov-report=xml
```

### Parallel Execution

```bash
# Run tests in parallel (4 workers)
pytest -n 4

# Run tests in parallel with auto detection
pytest -n auto
```

---

## 🔄 CI/CD Integration

### GitHub Actions Workflows

**CI Pipeline (`.github/workflows/ci.yml`):**
- ✅ Code quality checks (Black, Pylint, MyPy)
- ✅ Unit tests
- ✅ Integration tests
- ✅ Security tests
- ✅ Docker builds
- ✅ Dependency scanning

**CD Pipeline (`.github/workflows/cd.yml`):**
- 🚀 Build and push Docker images
- 🔒 Security scanning (Trivy)
- 🌐 Deploy to staging
- 🧪 Smoke tests
- 🚀 Deploy to production (on tags)
- ⚡ Performance tests

### Running CI Locally

```bash
# Install act (GitHub Actions locally)
brew install act

# Run CI workflow locally
act push

# Run specific job
act -j unit-tests
```

---

## 📊 Coverage Reports

### Generating Reports

```bash
# Terminal report
pytest --cov=services --cov-report=term-missing

# HTML report
pytest --cov=services --cov-report=html
open htmlcov/index.html

# XML report (for CI/CD)
pytest --cov=services --cov-report=xml
```

### Coverage Targets

| Component | Target | Current |
|-----------|--------|---------|
| Alert Triage | >80% | 🔄 TBD |
| RAG Service | >80% | 🔄 TBD |
| ML Inference | >90% | 🔄 TBD |
| Security Utils | >95% | 🔄 TBD |
| **Overall** | **>80%** | **🔄 TBD** |

---

## 🤝 Contributing

### Adding New Tests

1. **Identify test category** (unit/integration/e2e/security/etc.)
2. **Create test file** following naming convention `test_*.py`
3. **Add appropriate markers** (`@pytest.mark.unit`, etc.)
4. **Use fixtures** from `conftest.py`
5. **Document test purpose** in docstring
6. **Run tests locally** before committing

### Test Writing Guidelines

```python
"""
Test [Component] - [Functionality]
Brief description of what this test validates

Author: [Your Name]
Date: [YYYY-MM-DD]
"""

import pytest

@pytest.mark.unit
class TestMyComponent:
    """Test suite for MyComponent"""

    def test_basic_functionality(self, sample_fixture):
        """Test basic functionality works correctly"""
        # Arrange
        input_data = sample_fixture

        # Act
        result = my_function(input_data)

        # Assert
        assert result is not None
        assert result.status == "success"
```

### Code Quality

Before committing, run:

```bash
# Format code
black tests/ services/

# Lint code
pylint tests/ services/

# Type checking
mypy tests/ services/

# Security scan
bandit -r services/
```

---

## 📚 Additional Resources

- **Pytest Documentation:** https://docs.pytest.org/
- **Playwright Documentation:** https://playwright.dev/python/
- **Locust Documentation:** https://docs.locust.io/
- **OWASP Top 10:** https://owasp.org/www-project-top-ten/

---

## 🏆 Quality Metrics Dashboard

```
╔═══════════════════════════════════════════════════════════╗
║           AI-SOC TESTING QUALITY METRICS                  ║
╠═══════════════════════════════════════════════════════════╣
║ Test Coverage:        🔄 TBD (Target: >80%)              ║
║ Tests Passed:         🔄 TBD                              ║
║ Security Score:       🔄 TBD (Target: 9/10)              ║
║ Performance Score:    🔄 TBD (Target: <100ms avg)        ║
║ Code Quality:         🔄 TBD (Pylint >8.0)               ║
╚═══════════════════════════════════════════════════════════╝
```

---

**Built with 🧪 by LOVELESS - Elite QA Specialist**
