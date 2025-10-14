"""
Ollama Client - Common Utilities
AI-Augmented SOC

Reusable Ollama API client with error handling, retries, and fallback logic.
Can be imported by any service needing LLM access.
"""

import logging
from typing import Optional, Dict, Any, List
import httpx
import asyncio

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Universal Ollama API client for all AI services.

    Features:
    - Automatic retries with exponential backoff
    - Model fallback chain
    - Connection pooling
    - Timeout handling
    - Structured JSON output parsing
    """

    def __init__(
        self,
        host: str = "http://ollama:11434",
        primary_model: str = "llama3.1:8b",
        fallback_models: Optional[List[str]] = None,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        Initialize Ollama client.

        Args:
            host: Ollama API endpoint
            primary_model: Default model to use
            fallback_models: Fallback model chain
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.host = host
        self.primary_model = primary_model
        self.fallback_models = fallback_models or []
        self.timeout = timeout
        self.max_retries = max_retries

        logger.info(f"OllamaClient initialized: {host}, model={primary_model}")

    async def check_health(self) -> bool:
        """
        Check if Ollama service is reachable.

        Returns:
            bool: True if Ollama is available
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.host}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """
        List available models.

        Returns:
            List of model names
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.host}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [model['name'] for model in data.get('models', [])]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
        return []

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        json_format: bool = True,
        system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate completion from Ollama.

        Args:
            prompt: Input prompt
            model: Model to use (defaults to primary_model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            json_format: Request JSON output
            system_prompt: Optional system prompt

        Returns:
            Optional[str]: Generated text or None on failure
        """
        model = model or self.primary_model

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        if json_format:
            payload["format"] = "json"

        if system_prompt:
            payload["system"] = system_prompt

        # Try primary model with retries
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.debug(f"Ollama request: model={model}, attempt={attempt+1}")
                    response = await client.post(
                        f"{self.host}/api/generate",
                        json=payload
                    )

                    if response.status_code == 200:
                        result = response.json()
                        return result.get("response")
                    else:
                        logger.warning(f"Ollama error: {response.status_code} - {response.text}")

            except httpx.TimeoutException:
                logger.warning(f"Ollama timeout (attempt {attempt+1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                logger.error(f"Ollama request failed: {e}")
                break

        # Try fallback models
        for fallback_model in self.fallback_models:
            logger.info(f"Trying fallback model: {fallback_model}")
            payload["model"] = fallback_model
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.host}/api/generate",
                        json=payload
                    )
                    if response.status_code == 200:
                        result = response.json()
                        return result.get("response")
            except Exception as e:
                logger.error(f"Fallback model {fallback_model} failed: {e}")

        logger.error("All models failed")
        return None

    async def embed(self, text: str, model: str = "all-minilm") -> Optional[List[float]]:
        """
        Generate embeddings for text.

        Args:
            text: Input text
            model: Embedding model

        Returns:
            Optional[List[float]]: Embedding vector or None
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.host}/api/embeddings",
                    json={"model": model, "prompt": text}
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("embedding")
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
        return None

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1
    ) -> Optional[str]:
        """
        Chat completion (multi-turn conversation).

        Args:
            messages: List of {"role": "user/assistant", "content": "..."}
            model: Model to use
            temperature: Sampling temperature

        Returns:
            Optional[str]: Assistant response or None
        """
        model = model or self.primary_model

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.host}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": temperature}
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("message", {}).get("content")
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
        return None


# TODO: Week 5 - Add streaming support for long responses
# async def generate_stream(self, prompt: str, model: str) -> AsyncIterator[str]:
#     """Stream responses token by token"""
#     pass
