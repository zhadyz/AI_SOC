"""
JWT Authentication System - Common Utilities
AI-Augmented SOC - Production Security

Implements JWT-based authentication for all API endpoints.
Provides secure token generation, validation, and refresh mechanisms.

Author: LOVELESS (Elite Security Specialist)
Mission: OPERATION SECURITY-FORTRESS
Date: 2025-10-23
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
import secrets

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token security
security = HTTPBearer()


class JWTAuthManager:
    """
    JWT Authentication Manager for FastAPI services.

    Handles:
    - Token generation and validation
    - API key management
    - Token refresh
    - User authentication
    """

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7
    ):
        """
        Initialize JWT authentication manager.

        Args:
            secret_key: Secret key for JWT signing (use 32+ byte random string)
            algorithm: JWT signing algorithm (default: HS256)
            access_token_expire_minutes: Access token lifetime in minutes
            refresh_token_expire_days: Refresh token lifetime in days
        """
        if len(secret_key) < 32:
            raise ValueError("Secret key must be at least 32 characters")

        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

        # In-memory API key store (production: use Redis or database)
        self.api_keys: Dict[str, Dict[str, Any]] = {}

        logger.info("JWT Auth Manager initialized")

    def generate_api_key(
        self,
        user_id: str,
        scopes: list[str] = None,
        expires_days: int = 365
    ) -> str:
        """
        Generate a new API key for a user.

        Args:
            user_id: User identifier
            scopes: List of permission scopes
            expires_days: API key expiration in days

        Returns:
            str: Generated API key
        """
        api_key = f"aisoc_{secrets.token_urlsafe(32)}"

        self.api_keys[api_key] = {
            "user_id": user_id,
            "scopes": scopes or ["read", "write"],
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=expires_days),
            "is_active": True
        }

        logger.info(f"Generated API key for user: {user_id}")
        return api_key

    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an API key.

        Args:
            api_key: API key to validate

        Returns:
            Optional[Dict]: API key metadata if valid, None otherwise
        """
        if api_key not in self.api_keys:
            logger.warning(f"Invalid API key attempted")
            return None

        key_data = self.api_keys[api_key]

        # Check expiration
        if datetime.utcnow() > key_data["expires_at"]:
            logger.warning(f"Expired API key used: {key_data['user_id']}")
            return None

        # Check if active
        if not key_data["is_active"]:
            logger.warning(f"Inactive API key used: {key_data['user_id']}")
            return None

        return key_data

    def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke an API key.

        Args:
            api_key: API key to revoke

        Returns:
            bool: True if revoked successfully
        """
        if api_key in self.api_keys:
            self.api_keys[api_key]["is_active"] = False
            logger.info(f"Revoked API key for user: {self.api_keys[api_key]['user_id']}")
            return True
        return False

    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT access token.

        Args:
            data: Data to encode in token (e.g., {"sub": "user_id"})
            expires_delta: Custom expiration time

        Returns:
            str: Encoded JWT token
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        Create a JWT refresh token.

        Args:
            data: Data to encode in token

        Returns:
            str: Encoded refresh token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token to verify

        Returns:
            Optional[Dict]: Decoded token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain-text password

        Returns:
            str: Hashed password
        """
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.

        Args:
            plain_password: Plain-text password to verify
            hashed_password: Hashed password to compare against

        Returns:
            bool: True if password matches
        """
        return pwd_context.verify(plain_password, hashed_password)


# Global authentication manager (initialized in main.py)
auth_manager: Optional[JWTAuthManager] = None


def init_auth_manager(secret_key: str, **kwargs) -> JWTAuthManager:
    """
    Initialize global authentication manager.

    Args:
        secret_key: JWT secret key
        **kwargs: Additional configuration options

    Returns:
        JWTAuthManager: Initialized auth manager
    """
    global auth_manager
    auth_manager = JWTAuthManager(secret_key, **kwargs)
    return auth_manager


async def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency for JWT token verification.

    Usage:
        @app.get("/protected")
        async def protected_endpoint(token_data: dict = Depends(verify_jwt_token)):
            return {"user": token_data["sub"]}

    Args:
        credentials: HTTP Bearer credentials from request

    Returns:
        Dict: Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    if auth_manager is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system not initialized"
        )

    token = credentials.credentials
    payload = auth_manager.verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    return payload


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency for API key verification.

    Supports both JWT tokens and API keys.

    Args:
        credentials: HTTP Bearer credentials from request

    Returns:
        Dict: User/API key metadata

    Raises:
        HTTPException: If authentication fails
    """
    if auth_manager is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system not initialized"
        )

    token = credentials.credentials

    # Try JWT first
    if not token.startswith("aisoc_"):
        return await verify_jwt_token(credentials)

    # Validate as API key
    key_data = auth_manager.validate_api_key(token)

    if key_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return key_data


def require_scopes(required_scopes: list[str]):
    """
    Decorator to require specific scopes for endpoint access.

    Usage:
        @app.get("/admin")
        @require_scopes(["admin"])
        async def admin_endpoint():
            return {"status": "admin access"}

    Args:
        required_scopes: List of required permission scopes

    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, token_data: dict = Security(verify_api_key), **kwargs):
            user_scopes = token_data.get("scopes", [])

            if not any(scope in user_scopes for scope in required_scopes):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {required_scopes}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Production: Use environment variables or secure vault
def generate_secret_key() -> str:
    """
    Generate a secure random secret key for JWT signing.

    WARNING: In production, generate this ONCE and store securely.
    Never regenerate on server restart or tokens will be invalidated.

    Returns:
        str: 64-character random secret key
    """
    return secrets.token_urlsafe(64)


# Development: Default API keys for testing
# TODO: Remove in production
DEVELOPMENT_API_KEYS = {
    "aisoc_dev_admin": {
        "user_id": "admin",
        "scopes": ["read", "write", "admin"],
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=365),
        "is_active": True
    },
    "aisoc_dev_readonly": {
        "user_id": "readonly",
        "scopes": ["read"],
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=365),
        "is_active": True
    }
}
