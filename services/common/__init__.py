"""Shared service utilities, imported lazily so setup needs only the standard library."""
from importlib import import_module

__version__ = "1.1.0"
_EXPORTS = {"OllamaClient": "ollama_client", "setup_logging": "logging_config",
            "get_logger": "logging_config", "ServiceMetrics": "metrics",
            "validate_input": "security", "sanitize_log": "security", "detect_prompt_injection": "security"}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{_EXPORTS[name]}"), name)
    globals()[name] = value
    return value
