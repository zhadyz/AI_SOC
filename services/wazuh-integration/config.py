"""
Configuration - Wazuh Integration Service
AI-Augmented SOC

Environment-based configuration for Wazuh API and AI service integration.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, AliasChoices
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Service Identity
    service_name: str = "wazuh-integration"
    service_version: str = "1.0.0"

    # Wazuh Manager Configuration
    wazuh_manager_url: str = "https://wazuh-manager:55000"
    wazuh_username: str = "wazuh-wui"
    wazuh_password: str = Field("", validation_alias=AliasChoices("WAZUH_PASSWORD", "API_PASSWORD"))
    wazuh_verify_ssl: bool = True
    wazuh_ca_bundle: str = ""

    # Wazuh Alert Filtering
    min_severity: int = 7  # Minimum rule_level to process (7-15 = high priority)
    max_alerts_per_request: int = 100

    # AI Service Endpoints
    alert_triage_url: str = "http://alert-triage:8000"
    rag_service_url: str = "http://rag-service:8000"
    correlation_engine_url: str = "http://correlation-engine:8000"

    # RAG Enrichment Threshold
    rag_severity_threshold: int = 8  # Only enrich alerts with severity >= 8

    # API Configuration
    host: str = "0.0.0.0"
    port: int = 8002
    log_level: str = "info"

    # Timeouts
    wazuh_api_timeout: int = 30
    ai_service_timeout: int = 420  # Two bounded triage attempts plus enrichment on CPU

    class Config:
        hide_input_in_errors = True
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"



@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()
