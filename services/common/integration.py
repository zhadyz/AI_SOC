"""
Service Integration Utilities
==============================

Common utilities for inter-service communication, error handling,
and resilience patterns.

Author: HOLLOWED_EYES
Mission: OPERATION PIPELINE-INTEGRATION
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, TypeVar, Awaitable
from datetime import datetime, timedelta
from functools import wraps
import httpx

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# Retry Decorator
# ============================================================================

def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Async retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Backoff multiplier for exponential delay
        exceptions: Tuple of exceptions to catch and retry

    Example:
        @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
        async def call_api():
            return await client.get("/endpoint")
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )

            raise last_exception

        return wrapper
    return decorator


# ============================================================================
# Timeout Decorator
# ============================================================================

def async_timeout(seconds: float):
    """
    Async timeout decorator.

    Args:
        seconds: Timeout duration in seconds

    Example:
        @async_timeout(30.0)
        async def long_operation():
            await asyncio.sleep(60)
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"{func.__name__} timed out after {seconds}s")
                raise

        return wrapper
    return decorator


# ============================================================================
# Service Client Base
# ============================================================================

class ServiceClient:
    """
    Base class for service-to-service communication.

    Provides common functionality:
    - HTTP client with connection pooling
    - Retry logic
    - Timeout handling
    - Error logging
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_connections: int = 10,
        verify_ssl: bool = False
    ):
        self.base_url = base_url
        self.timeout = timeout

        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=5
            ),
            verify=verify_ssl
        )

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """
        GET request with retry logic.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            httpx.Response object
        """
        response = await self.client.get(endpoint, params=params)
        response.raise_for_status()
        return response

    @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """
        POST request with retry logic.

        Args:
            endpoint: API endpoint path
            data: Form data
            json: JSON body

        Returns:
            httpx.Response object
        """
        response = await self.client.post(endpoint, data=data, json=json)
        response.raise_for_status()
        return response

    @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
    async def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """
        PUT request with retry logic.

        Args:
            endpoint: API endpoint path
            data: Form data
            json: JSON body

        Returns:
            httpx.Response object
        """
        response = await self.client.put(endpoint, data=data, json=json)
        response.raise_for_status()
        return response

    async def health_check(self) -> bool:
        """
        Check service health.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = await self.client.get("/health", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed for {self.base_url}: {e}")
            return False


# ============================================================================
# Specific Service Clients
# ============================================================================

class MLInferenceClient(ServiceClient):
    """ML Inference API client"""

    def __init__(self, base_url: str = "http://ml-inference:8000"):
        super().__init__(base_url)

    async def predict(self, features: list, model_name: str = "random_forest") -> Dict[str, Any]:
        """
        Get ML prediction for network flow.

        Args:
            features: List of 78 network flow features
            model_name: Model to use (random_forest, xgboost, decision_tree)

        Returns:
            Prediction response with confidence scores
        """
        response = await self.post("/predict", json={
            "features": features,
            "model_name": model_name
        })
        return response.json()

    async def batch_predict(self, flows: list) -> Dict[str, Any]:
        """
        Batch prediction for multiple flows.

        Args:
            flows: List of flow dictionaries

        Returns:
            Batch prediction response
        """
        response = await self.post("/predict/batch", json=flows)
        return response.json()


class AlertTriageClient(ServiceClient):
    """Alert Triage Service client"""

    def __init__(self, base_url: str = "http://alert-triage:8000"):
        super().__init__(base_url)

    async def analyze_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze security alert with LLM.

        Args:
            alert: Alert dictionary with required fields

        Returns:
            Triage response with severity and recommendations
        """
        response = await self.post("/analyze", json=alert)
        return response.json()


class RAGServiceClient(ServiceClient):
    """RAG Service client"""

    def __init__(self, base_url: str = "http://rag-service:8000"):
        super().__init__(base_url)

    async def retrieve(
        self,
        query: str,
        collection: str = "mitre_attack",
        top_k: int = 3
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context from knowledge base.

        Args:
            query: Search query
            collection: Knowledge base collection
            top_k: Number of results to return

        Returns:
            Retrieval response with documents and scores
        """
        response = await self.post("/retrieve", json={
            "query": query,
            "collection": collection,
            "top_k": top_k
        })
        return response.json()


class TheHiveClient(ServiceClient):
    """TheHive case management client"""

    def __init__(self, base_url: str = "http://thehive:9000", api_key: Optional[str] = None):
        super().__init__(base_url)
        self.api_key = api_key
        if api_key:
            self.client.headers.update({"Authorization": f"Bearer {api_key}"})

    async def create_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create alert in TheHive.

        Args:
            alert_data: Alert data conforming to TheHive schema

        Returns:
            Created alert response
        """
        response = await self.post("/api/alert", json=alert_data)
        return response.json()

    async def create_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create case in TheHive.

        Args:
            case_data: Case data conforming to TheHive schema

        Returns:
            Created case response
        """
        response = await self.post("/api/case", json=case_data)
        return response.json()

    async def search_alerts(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search alerts in TheHive.

        Args:
            query: Search query

        Returns:
            Search results
        """
        response = await self.post("/api/alert/_search", json=query)
        return response.json()


# ============================================================================
# Graceful Degradation
# ============================================================================

class FallbackHandler:
    """
    Handler for graceful degradation when services fail.
    """

    @staticmethod
    async def ml_fallback(alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback when ML service is unavailable.

        Uses rule-based detection as backup.
        """
        logger.warning("ML service unavailable, using rule-based fallback")

        # Simple rule-based classification
        severity = "medium"
        if any(keyword in str(alert).lower() for keyword in ["ransomware", "cryptolocker", "exploit"]):
            severity = "critical"
        elif any(keyword in str(alert).lower() for keyword in ["brute", "force", "scan"]):
            severity = "high"

        return {
            "prediction": "ATTACK" if severity in ["critical", "high"] else "BENIGN",
            "confidence": 0.6,
            "fallback": True,
            "severity": severity
        }

    @staticmethod
    async def llm_fallback(alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback when LLM service is unavailable.

        Uses template-based analysis.
        """
        logger.warning("LLM service unavailable, using template-based fallback")

        return {
            "severity": "medium",
            "confidence": 0.5,
            "analysis": "Automated analysis unavailable. Manual review recommended.",
            "recommendations": ["Review alert manually", "Check system logs"],
            "fallback": True
        }


# ============================================================================
# Event Bus (Simple In-Memory)
# ============================================================================

class EventBus:
    """
    Simple in-memory event bus for service notifications.

    Note: For production, use Redis Pub/Sub or RabbitMQ.
    """

    def __init__(self):
        self.subscribers: Dict[str, list] = {}

    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to an event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    async def publish(self, event_type: str, data: Dict[str, Any]):
        """Publish an event to all subscribers"""
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"Event handler error for {event_type}: {e}")


# Global event bus instance
event_bus = EventBus()
