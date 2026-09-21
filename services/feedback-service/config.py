"""
Configuration - Feedback Service
AI-Augmented SOC
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "feedback-service"
    service_version: str = "1.0.0"
    database_url: str = "postgresql+asyncpg://ai_soc:ai_soc_password@postgres:5432/ai_soc"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    # Pagination defaults
    default_page_size: int = 50
    max_page_size: int = 200

    class Config:
        hide_input_in_errors = True
        env_prefix = "FEEDBACK_"
