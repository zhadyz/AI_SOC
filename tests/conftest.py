"""
Pytest Configuration - AI-SOC Testing Framework
Provides fixtures and configuration for all test suites

Author: LOVELESS (Elite QA Specialist)
Mission: OPERATION TEST-FORTRESS
Date: 2025-10-22
"""

import os
import sys
import pytest
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Generator

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "common"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "alert-triage"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "rag-service"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "log-summarization"))
sys.path.insert(0, str(PROJECT_ROOT / "ml_training"))


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "load: Load/performance tests")
    config.addinivalue_line("markers", "browser: Browser/UI tests")
    config.addinivalue_line("markers", "slow: Tests that take >5 seconds")
    config.addinivalue_line("markers", "requires_ollama: Tests requiring Ollama")
    config.addinivalue_line("markers", "requires_docker: Tests requiring Docker")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Service URL Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def alert_triage_url() -> str:
    """Alert Triage Service URL"""
    return os.getenv("ALERT_TRIAGE_URL", "http://localhost:8100")


@pytest.fixture(scope="session")
def rag_service_url() -> str:
    """RAG Service URL"""
    return os.getenv("RAG_SERVICE_URL", "http://localhost:8300")


@pytest.fixture(scope="session")
def ml_inference_url() -> str:
    """ML Inference API URL"""
    return os.getenv("ML_INFERENCE_URL", "http://localhost:8500")


@pytest.fixture(scope="session")
def ollama_url() -> str:
    """Ollama API URL"""
    return os.getenv("OLLAMA_HOST", "http://localhost:11434")


@pytest.fixture(scope="session")
def chromadb_url() -> str:
    """ChromaDB URL"""
    return os.getenv("CHROMADB_URL", "http://localhost:8200")


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_security_alert() -> dict:
    """Sample security alert for testing"""
    return {
        "alert_id": "test-alert-001",
        "timestamp": "2025-10-22T10:30:00Z",
        "source_ip": "192.168.1.100",
        "destination_ip": "10.0.0.50",
        "rule_id": "100002",
        "rule_level": 10,
        "rule_description": "Multiple failed SSH login attempts detected",
        "full_log": "Oct 22 10:30:00 server sshd[1234]: Failed password for root from 192.168.1.100",
        "agent_name": "web-server-01",
        "mitre_tactic": "Credential Access",
        "mitre_technique": "T1110.001"
    }


@pytest.fixture
def sample_network_flow() -> dict:
    """Sample network flow for ML inference testing"""
    return {
        "features": [0.0] * 78,  # 78 features as expected by ML models
        "model_name": "random_forest"
    }


@pytest.fixture
def sample_log_batch() -> list:
    """Sample log batch for log summarization testing"""
    return [
        "2025-10-22 10:30:00 [INFO] User alice logged in successfully",
        "2025-10-22 10:30:15 [WARN] Failed login attempt from 192.168.1.50",
        "2025-10-22 10:30:30 [ERROR] Database connection timeout",
        "2025-10-22 10:31:00 [INFO] User bob accessed /admin",
        "2025-10-22 10:31:15 [CRITICAL] Potential SQL injection detected"
    ]


@pytest.fixture
def sample_mitre_query() -> dict:
    """Sample MITRE ATT&CK query for RAG testing"""
    return {
        "query": "What is MITRE ATT&CK technique T1110 Brute Force?",
        "collection": "mitre_attack",
        "top_k": 3,
        "min_similarity": 0.7
    }


# ============================================================================
# Mock Service Fixtures
# ============================================================================

@pytest.fixture
def mock_ollama_response() -> dict:
    """Mock Ollama API response"""
    return {
        "model": "llama3.1:8b",
        "created_at": "2025-10-22T10:30:00Z",
        "response": "This alert indicates a brute force attack targeting SSH. Severity: HIGH. Recommended action: Block source IP immediately.",
        "done": True
    }


@pytest.fixture
def mock_ml_prediction() -> dict:
    """Mock ML inference prediction"""
    return {
        "prediction": "ATTACK",
        "confidence": 0.95,
        "probabilities": {
            "BENIGN": 0.05,
            "ATTACK": 0.95
        },
        "model_used": "random_forest",
        "inference_time_ms": 0.5,
        "timestamp": "2025-10-22T10:30:00Z"
    }


# ============================================================================
# HTTP Client Fixtures
# ============================================================================

@pytest.fixture
async def http_client():
    """Async HTTP client for API testing"""
    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def test_db_path(tmp_path) -> Path:
    """Temporary database path for testing"""
    return tmp_path / "test_db.sqlite"


# ============================================================================
# Performance Tracking
# ============================================================================

@pytest.fixture(autouse=True)
def track_test_performance(request):
    """Track test execution time"""
    import time
    start_time = time.time()
    yield
    duration = time.time() - start_time
    if duration > 5.0:
        print(f"\n⚠️  SLOW TEST: {request.node.nodeid} took {duration:.2f}s")


# ============================================================================
# Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_test_artifacts(tmp_path):
    """Cleanup temporary test artifacts"""
    yield
    # Cleanup logic here if needed
    pass


# ============================================================================
# Environment Setup
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment variables"""
    os.environ.setdefault("TESTING", "true")
    os.environ.setdefault("LOG_LEVEL", "DEBUG")
    yield
    # Cleanup
    os.environ.pop("TESTING", None)
