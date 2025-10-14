"""
Logging Configuration - Common Utilities
AI-Augmented SOC

Structured JSON logging for all services with ELK Stack compatibility.
"""

import logging
import sys
from typing import Optional
from pythonjsonlogger import jsonlogger


def setup_logging(
    service_name: str,
    log_level: str = "INFO",
    json_logs: bool = True
) -> None:
    """
    Configure structured logging for service.

    Args:
        service_name: Service identifier
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_logs: Use JSON format (for ELK Stack)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if json_logs:
        # JSON formatter for structured logging
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s',
            rename_fields={
                'asctime': 'timestamp',
                'levelname': 'level',
                'name': 'logger'
            }
        )
        console_handler.setFormatter(formatter)
    else:
        # Human-readable formatter for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # Add service context to all logs
    logger = logging.LoggerAdapter(logger, {'service': service_name})

    logging.info(f"Logging configured: service={service_name}, level={log_level}, json={json_logs}")


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance for module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        logging.Logger: Configured logger
    """
    return logging.getLogger(name)


class SecurityLogFilter(logging.Filter):
    """
    Filter to sanitize sensitive data from logs.

    Redacts:
    - API keys
    - Passwords
    - Tokens
    - IP addresses (optional)
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Sanitize log record before emission.

        Args:
            record: Log record

        Returns:
            bool: True to emit, False to drop
        """
        # TODO: Week 4 - Implement sensitive data redaction
        # if hasattr(record, 'msg'):
        #     record.msg = self._redact_secrets(str(record.msg))
        return True

    def _redact_secrets(self, message: str) -> str:
        """
        Redact sensitive information from message.

        Args:
            message: Log message

        Returns:
            str: Sanitized message
        """
        import re

        # Redact API keys (pattern: key=xxx or apikey=xxx)
        message = re.sub(r'(api[_-]?key|token|password)\s*=\s*[\w\-]+', r'\1=***REDACTED***', message, flags=re.IGNORECASE)

        # Redact bearer tokens
        message = re.sub(r'Bearer\s+[\w\-\.]+', 'Bearer ***REDACTED***', message, flags=re.IGNORECASE)

        return message


# TODO: Week 6 - Add ELK Stack integration
# class ElasticsearchHandler(logging.Handler):
#     """Send logs directly to Elasticsearch"""
#     def emit(self, record: logging.LogRecord):
#         # Send to Elasticsearch
#         pass
