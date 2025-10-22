"""
Configuration Management - Log Summarization Service
AI-Augmented SOC

Environment variables and service configuration.

Author: HOLLOWED_EYES
Mission: Phase 3 AI Service Integration
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Service Configuration
    service_name: str = "log-summarization"
    service_version: str = "1.0.0"
    log_level: str = "INFO"

    # Ollama LLM Configuration
    ollama_host: str = "http://ollama:11434"
    primary_model: str = "llama3.1:8b"
    fallback_model: str = "mistral:7b"

    # LLM Parameters
    llm_temperature: float = 0.2  # Slightly higher for creative summaries
    llm_timeout: int = 120  # Longer timeout for batch processing
    max_tokens: int = 4096

    # OpenSearch Configuration
    opensearch_host: str = "https://wazuh-indexer:9200"
    opensearch_user: str = "admin"
    opensearch_password: str = "SecretPassword"  # TODO: Use secrets management
    opensearch_verify_ssl: bool = False  # Set to True in production
    opensearch_index_pattern: str = "wazuh-alerts-*"

    # ChromaDB Configuration
    chromadb_host: str = "http://chromadb:8000"
    chromadb_collection: str = "log_summaries"
    embedding_model: str = "all-minilm"  # For Ollama embeddings

    # Batch Processing
    batch_size: int = 1000
    max_logs_per_summary: int = 10000
    summary_chunk_size: int = 100  # Process logs in chunks

    # Summarization Settings
    default_time_range_hours: int = 24
    max_time_range_hours: int = 168  # 1 week
    min_logs_for_summary: int = 10

    # Scheduled Tasks
    daily_summary_enabled: bool = True
    daily_summary_hour: int = 8  # Run at 8:00 AM
    weekly_summary_enabled: bool = True
    weekly_summary_day: int = 1  # Monday

    class Config:
        env_prefix = "LOGSUMM_"
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
