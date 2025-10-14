"""
Common Utilities - AI-Augmented SOC Services

Shared functionality across all AI services:
- Ollama client interface
- Logging configuration
- Prometheus metrics
- Security utilities
"""

__version__ = "1.0.0"

from .ollama_client import OllamaClient
from .logging_config import setup_logging, get_logger
from .metrics import ServiceMetrics
from .security import validate_input, sanitize_log, detect_prompt_injection

__all__ = [
    "OllamaClient",
    "setup_logging",
    "get_logger",
    "ServiceMetrics",
    "validate_input",
    "sanitize_log",
    "detect_prompt_injection"
]
