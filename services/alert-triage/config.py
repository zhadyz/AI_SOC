"""
Configuration Management - Alert Triage Service
AI-Augmented SOC

Manages environment variables and service configuration with Pydantic.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Environment variables should be prefixed with TRIAGE_
    Example: TRIAGE_OLLAMA_HOST=http://ollama:11434
    """

    # Service Configuration
    service_name: str = "alert-triage"
    service_version: str = "1.0.0"
    log_level: str = "INFO"

    # Ollama LLM Configuration
    ollama_host: str = "http://ollama:11434"
    primary_model: str = "foundation-sec-8b"
    fallback_model: str = "llama3.1:8b"

    # LLM Parameters
    llm_temperature: float = 0.1  # Low temperature for consistency
    llm_timeout: int = 60  # Seconds
    max_tokens: int = 2048

    # Confidence Thresholds
    high_confidence_threshold: float = 0.85
    medium_confidence_threshold: float = 0.70
    auto_action_threshold: float = 0.80  # Only auto-escalate if >80%

    # ML Inference Configuration
    ml_enabled: bool = True
    ml_api_url: str = "http://ml-inference:8001"
    ml_timeout: int = 10
    ml_default_model: str = "random_forest"

    # RAG Configuration (for future Phase 3.2)
    rag_enabled: bool = False
    rag_service_url: Optional[str] = "http://rag-service:8001"
    rag_top_k: int = 3

    # Wazuh Integration
    wazuh_dashboard_url: Optional[str] = None
    wazuh_api_url: Optional[str] = None

    # TheHive Integration
    thehive_url: Optional[str] = None
    thehive_api_key: Optional[str] = None

    # Performance Tuning
    max_concurrent_requests: int = 10
    request_timeout: int = 120

    # Security
    api_key_enabled: bool = False
    api_key: Optional[str] = None

    class Config:
        env_prefix = "TRIAGE_"
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
