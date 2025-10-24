"""
Security Utilities - Common Utilities
AI-Augmented SOC

Input validation, sanitization, prompt injection detection, and security headers.

Author: LOVELESS (Elite Security Specialist)
Mission: OPERATION SECURITY-FORTRESS
Date: 2025-10-23 (Enhanced)
"""

import logging
import re
from typing import Optional, Dict, Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, RedirectResponse

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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add comprehensive security headers to all responses.

    Implements OWASP security best practices:
    - Content Security Policy (CSP)
    - X-Frame-Options (Clickjacking protection)
    - X-Content-Type-Options (MIME sniffing protection)
    - Strict-Transport-Security (HTTPS enforcement)
    - X-XSS-Protection (XSS filter)
    - Referrer-Policy (Referrer control)
    - Permissions-Policy (Feature control)
    """

    def __init__(
        self,
        app,
        csp_policy: Optional[str] = None,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000
    ):
        """
        Initialize security headers middleware.

        Args:
            app: FastAPI application
            csp_policy: Custom Content Security Policy
            enable_hsts: Enable HTTP Strict Transport Security
            hsts_max_age: HSTS max age in seconds (default: 1 year)
        """
        super().__init__(app)

        # Default CSP: Restrict to same origin
        self.csp_policy = csp_policy or (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age

        logger.info("Security headers middleware initialized")

    async def dispatch(self, request: Request, call_next):
        """
        Add security headers to response.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with security headers
        """
        response = await call_next(request)

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.csp_policy

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS protection (legacy, but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (disable unnecessary features)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )

        # HSTS (only for HTTPS)
        if self.enable_hsts and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        # Remove server fingerprinting
        response.headers.pop("Server", None)

        return response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """
    Redirect HTTP requests to HTTPS in production.

    Only active when FORCE_HTTPS environment variable is set.
    """

    def __init__(self, app, force_https: bool = False):
        """
        Initialize HTTPS redirect middleware.

        Args:
            app: FastAPI application
            force_https: Force HTTPS redirects
        """
        super().__init__(app)
        self.force_https = force_https

        if force_https:
            logger.info("HTTPS redirect middleware enabled (production mode)")
        else:
            logger.info("HTTPS redirect disabled (development mode)")

    async def dispatch(self, request: Request, call_next):
        """
        Redirect HTTP to HTTPS if enabled.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response or redirect
        """
        if self.force_https and request.url.scheme == "http":
            # Build HTTPS URL
            https_url = request.url.replace(scheme="https")

            logger.info(f"Redirecting HTTP -> HTTPS: {request.url.path}")

            return RedirectResponse(
                url=str(https_url),
                status_code=301  # Permanent redirect
            )

        return await call_next(request)


class CORSSecurityMiddleware(BaseHTTPMiddleware):
    """
    Secure CORS middleware with strict origin validation.

    Alternative to FastAPI's CORSMiddleware with enhanced security.
    """

    def __init__(
        self,
        app,
        allowed_origins: list[str],
        allow_credentials: bool = True,
        allowed_methods: Optional[list[str]] = None,
        allowed_headers: Optional[list[str]] = None
    ):
        """
        Initialize CORS security middleware.

        Args:
            app: FastAPI application
            allowed_origins: List of allowed origins (exact matches)
            allow_credentials: Allow credentials (cookies, auth)
            allowed_methods: Allowed HTTP methods
            allowed_headers: Allowed request headers
        """
        super().__init__(app)

        self.allowed_origins = set(allowed_origins)
        self.allow_credentials = allow_credentials
        self.allowed_methods = allowed_methods or ["GET", "POST", "PUT", "DELETE"]
        self.allowed_headers = allowed_headers or ["Authorization", "Content-Type"]

        logger.info(
            f"CORS security middleware initialized: "
            f"origins={len(self.allowed_origins)}, "
            f"credentials={allow_credentials}"
        )

    async def dispatch(self, request: Request, call_next):
        """
        Validate CORS requests with strict origin checking.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with CORS headers or 403 Forbidden
        """
        origin = request.headers.get("Origin")

        # Handle preflight requests
        if request.method == "OPTIONS":
            if origin not in self.allowed_origins:
                logger.warning(f"CORS blocked: origin={origin}")
                return Response(status_code=403, content="Forbidden")

            headers = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": ", ".join(self.allowed_methods),
                "Access-Control-Allow-Headers": ", ".join(self.allowed_headers),
                "Access-Control-Max-Age": "3600"
            }

            if self.allow_credentials:
                headers["Access-Control-Allow-Credentials"] = "true"

            return Response(status_code=200, headers=headers)

        # Process regular request
        response = await call_next(request)

        if origin and origin in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin

            if self.allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"

        return response


def detect_xss_patterns(text: str) -> tuple[bool, Optional[str]]:
    """
    Detect XSS (Cross-Site Scripting) attack patterns.

    Args:
        text: Input text to check

    Returns:
        tuple: (is_xss, pattern_type)
    """
    xss_patterns = [
        (r'<script[^>]*>.*?</script>', 'script_tag'),
        (r'javascript:', 'javascript_protocol'),
        (r'on\w+\s*=', 'event_handler'),
        (r'<iframe[^>]*>', 'iframe_tag'),
        (r'<embed[^>]*>', 'embed_tag'),
        (r'<object[^>]*>', 'object_tag'),
        (r'eval\s*\(', 'eval_function'),
    ]

    for pattern, xss_type in xss_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning(f"XSS pattern detected: {xss_type}")
            return True, xss_type

    return False, None


def detect_path_traversal(path: str) -> bool:
    """
    Detect path traversal attack patterns.

    Args:
        path: File path to validate

    Returns:
        bool: True if path traversal detected
    """
    traversal_patterns = [
        r'\.\.',
        r'%2e%2e',
        r'\.\./',
        r'\.\.\\',
        r'%252e%252e',
    ]

    for pattern in traversal_patterns:
        if re.search(pattern, path, re.IGNORECASE):
            logger.warning(f"Path traversal detected in: {path}")
            return True

    return False
