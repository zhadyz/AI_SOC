"""
Configuration - Response Orchestrator Service
AI-Augmented SOC

Environment-based configuration for autonomous adaptive defense.
Controls simulation integration, approval thresholds, adapter settings,
and verification parameters.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Service Identity
    service_name: str = "response-orchestrator"
    service_version: str = "1.0.0"

    # Database
    database_url: str = "postgresql+asyncpg://ai_soc:ai_soc_password@postgres:5432/ai_soc"

    # Upstream Service URLs
    correlation_engine_url: str = "http://correlation-engine:8000"
    simulation_url: str = "http://correlation-engine:8000"
    rag_service_url: str = "http://rag-service:8000"
    feedback_service_url: str = "http://feedback-service:8000"
    rule_generator_url: str = "http://rule-generator:8000"

    # LLM (for defense plan rationale generation)
    ollama_host: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"

    # Wazuh Active Response
    wazuh_api_url: str = "https://wazuh-manager:55000"
    wazuh_api_username: str = "wazuh-wui"
    wazuh_api_password: str = ""
    wazuh_api_verify_ssl: bool = False

    # Simulation Integration
    simulation_swarm_size: int = 50
    simulation_monte_carlo_runs: int = 3
    simulation_timesteps: int = 3
    simulation_timeout_seconds: int = 300

    # Approval Thresholds (graduated autonomy)
    auto_execute_confidence_min: float = 0.70
    auto_execute_with_veto_confidence_min: float = 0.85
    veto_window_seconds: int = 60
    max_auto_actions_per_incident: int = 5
    cooldown_between_actions_seconds: int = 10

    # Verification
    verification_re_simulation_enabled: bool = True
    verification_monitoring_duration_seconds: int = 1800  # 30 minutes
    verification_risk_reduction_threshold: float = 0.30  # 30% minimum reduction
    auto_rollback_on_verification_failure: bool = True
    rollback_window_seconds: int = 300  # 5 minutes

    # Safety Limits
    max_concurrent_plans: int = 3
    critical_asset_always_requires_approval: bool = True
    dry_run_mode: bool = False  # When true, no actions are actually executed

    # Disk persistence (E2E / audit; host path via docker volume)
    defense_plans_enabled: bool = True
    defense_plans_dir: str = "/data/defense-plans"

    # Logging / Server
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_prefix = "ORCHESTRATOR_"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
