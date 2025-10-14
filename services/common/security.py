"""
Security Utilities - Common Utilities
AI-Augmented SOC

Input validation, sanitization, and prompt injection detection.
"""

import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def validate_input(
    text: str,
    max_length: int = 10000,
    allow_special_chars: bool = True
) -> tuple[bool, Optional[str]]:
    """
    Validate user input for security risks.

    Args:
        text: Input text to validate
        max_length: Maximum allowed length
        allow_special_chars: Allow special characters

    Returns:
        tuple: (is_valid, error_message)
    """
    # Length check
    if len(text) > max_length:
        return False, f"Input exceeds maximum length of {max_length} characters"

    # Empty input
    if not text.strip():
        return False, "Input cannot be empty"

    # Check for null bytes
    if '\x00' in text:
        logger.warning("Null byte detected in input")
        return False, "Invalid characters in input"

    # Detect SQL injection patterns (basic)
    sql_patterns = [
        r'(\bUNION\b.*\bSELECT\b)',
        r'(\bDROP\b.*\bTABLE\b)',
        r'(--\s*$)',
        r'(;\s*DROP\b)',
    ]
    for pattern in sql_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning(f"Potential SQL injection detected: {pattern}")
            return False, "Invalid input pattern detected"

    # Detect command injection
    command_patterns = [
        r'(\$\(.*\))',
        r'(`.*`)',
        r'(;\s*(ls|cat|wget|curl|chmod)\b)',
    ]
    for pattern in command_patterns:
        if re.search(pattern, text):
            logger.warning(f"Potential command injection detected: {pattern}")
            return False, "Invalid input pattern detected"

    return True, None


def sanitize_log(log_text: str, preserve_context: bool = True) -> str:
    """
    Sanitize log text before passing to LLM.

    Removes:
    - Sensitive data (passwords, keys)
    - Excessive whitespace
    - Control characters

    Args:
        log_text: Raw log text
        preserve_context: Keep important structure

    Returns:
        str: Sanitized log text
    """
    if not log_text:
        return ""

    text = log_text

    # Redact passwords
    text = re.sub(
        r'(password|passwd|pwd)\s*[:=]\s*\S+',
        r'\1=***REDACTED***',
        text,
        flags=re.IGNORECASE
    )

    # Redact API keys
    text = re.sub(
        r'(api[_-]?key|token|secret)\s*[:=]\s*[\w\-]+',
        r'\1=***REDACTED***',
        text,
        flags=re.IGNORECASE
    )

    # Redact authentication tokens
    text = re.sub(
        r'(Bearer|Authorization:\s*Bearer)\s+[\w\-\.]+',
        r'\1 ***REDACTED***',
        text,
        flags=re.IGNORECASE
    )

    # Remove control characters (except newline/tab if preserving context)
    if preserve_context:
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
    else:
        text = re.sub(r'[\x00-\x1F\x7F]', '', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def detect_prompt_injection(text: str) -> tuple[bool, Optional[str]]:
    """
    Detect prompt injection attempts.

    Looks for patterns that attempt to manipulate LLM behavior:
    - System prompt override attempts
    - Instruction injections
    - Jailbreak attempts

    Args:
        text: User input to check

    Returns:
        tuple: (is_injection, detected_pattern)
    """
    # Patterns indicating prompt injection
    injection_patterns = [
        # System prompt override
        (r'ignore\s+(previous|all)\s+(instructions|prompts)', 'system_override'),
        (r'disregard\s+(previous|all)\s+(instructions|prompts)', 'system_override'),

        # Role switching
        (r'you\s+are\s+now', 'role_switch'),
        (r'act\s+as\s+(if|though)', 'role_switch'),
        (r'pretend\s+(you|to)\s+are', 'role_switch'),

        # Jailbreak attempts
        (r'DAN\s+mode', 'jailbreak'),
        (r'developer\s+mode', 'jailbreak'),
        (r'sudo\s+mode', 'jailbreak'),

        # Instruction injection
        (r'new\s+instructions?:', 'instruction_injection'),
        (r'system\s*:', 'instruction_injection'),
        (r'\\n\\nHuman:', 'instruction_injection'),

        # Output manipulation
        (r'output\s+your\s+(prompt|instructions)', 'output_manipulation'),
        (r'what\s+(is|are)\s+your\s+(system|original)\s+(prompt|instructions)', 'output_manipulation'),
    ]

    for pattern, attack_type in injection_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning(f"Potential prompt injection detected: {attack_type}")
            return True, attack_type

    return False, None


def validate_json_structure(data: Dict[str, Any], required_fields: list[str]) -> tuple[bool, Optional[str]]:
    """
    Validate JSON structure has required fields.

    Args:
        data: JSON data to validate
        required_fields: List of required field names

    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Input must be a JSON object"

    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"

    return True, None


# TODO: Week 5 - Add rate limiting
# class RateLimiter:
#     """Rate limit API requests per client"""
#     def __init__(self, max_requests: int, window_seconds: int):
#         pass
#
#     def is_allowed(self, client_id: str) -> bool:
#         pass


# TODO: Week 8 - Add WAF-style rules
# def detect_attack_patterns(request: Dict[str, Any]) -> tuple[bool, Optional[str]]:
#     """Detect common attack patterns (XSS, CSRF, etc.)"""
#     pass
