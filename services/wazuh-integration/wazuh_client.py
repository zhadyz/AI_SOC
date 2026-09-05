"""
Wazuh Client - Wazuh Integration Service
AI-Augmented SOC

Handles authentication and API requests to Wazuh Manager.
"""

import httpx
import structlog
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from services.wazuh_integration.config import Settings

logger = structlog.get_logger()


class WazuhClient:
    """Client for Wazuh Manager REST API"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.wazuh_manager_url
        self.username = settings.wazuh_username
        self.password = settings.wazuh_password
        self.verify_ssl = settings.wazuh_verify_ssl

        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

        logger.info(
            "wazuh_client_initialized",
            manager_url=self.base_url,
            username=self.username
        )

    async def _authenticate(self) -> str:
        """
        Authenticate with Wazuh API and get JWT token.

        Returns:
            JWT token string
        """
        # Check if we have a valid cached token
        if self._token and self._token_expiry:
            if datetime.utcnow() < self._token_expiry:
                return self._token

        auth_url = f"{self.base_url}/security/user/authenticate"

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    auth_url,
                    auth=(self.username, self.password),
                    timeout=self.settings.wazuh_api_timeout
                )
                response.raise_for_status()

                data = response.json()
                self._token = data["data"]["token"]

                # Wazuh tokens typically expire in 15 minutes
                # Cache for 14 minutes to be safe
                self._token_expiry = datetime.utcnow() + timedelta(minutes=14)

                logger.info("wazuh_authentication_success")
                return self._token

        except httpx.HTTPError as e:
            logger.error(
                "wazuh_authentication_failed",
                error=str(e),
                url=auth_url
            )
            raise

    async def get_alerts(
        self,
        min_level: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
        time_range: Optional[str] = "1h"
    ) -> List[Dict[str, Any]]:
        """
        Fetch alerts from Wazuh Manager.

        Args:
            min_level: Minimum rule level (0-15). Uses config default if None.
            limit: Maximum number of alerts to return
            offset: Offset for pagination
            time_range: Time range (e.g., "1h", "24h", "7d")

        Returns:
            List of Wazuh alert dictionaries
        """
        token = await self._authenticate()

        if min_level is None:
            min_level = self.settings.min_severity

        # Build query parameters
        params = {
            "limit": limit,
            "offset": offset,
            "rule.level": f">={min_level}",
            "sort": "-timestamp"  # Most recent first
        }

        if time_range:
            params["time_range"] = time_range

        alerts_url = f"{self.base_url}/alerts"

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    alerts_url,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                    timeout=self.settings.wazuh_api_timeout
                )
                response.raise_for_status()

                data = response.json()
                alerts = data.get("data", {}).get("affected_items", [])

                logger.info(
                    "wazuh_alerts_fetched",
                    count=len(alerts),
                    min_level=min_level,
                    time_range=time_range
                )

                return alerts

        except httpx.HTTPError as e:
            logger.error(
                "wazuh_alerts_fetch_failed",
                error=str(e),
                url=alerts_url
            )
            raise

    async def get_alert_by_id(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific alert by ID.

        Args:
            alert_id: Wazuh alert ID

        Returns:
            Alert dictionary or None if not found
        """
        token = await self._authenticate()
        alert_url = f"{self.base_url}/alerts/{alert_id}"

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    alert_url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self.settings.wazuh_api_timeout
                )

                if response.status_code == 404:
                    logger.warning("wazuh_alert_not_found", alert_id=alert_id)
                    return None

                response.raise_for_status()
                data = response.json()

                return data.get("data", {}).get("affected_items", [None])[0]

        except httpx.HTTPError as e:
            logger.error(
                "wazuh_alert_fetch_by_id_failed",
                error=str(e),
                alert_id=alert_id
            )
            raise

    async def health_check(self) -> bool:
        """
        Check if Wazuh Manager API is accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            token = await self._authenticate()

            # Try basic API call
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.base_url}/?pretty=true",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self.settings.wazuh_api_timeout
                )
                response.raise_for_status()

                logger.info("wazuh_health_check_passed")
                return True

        except Exception as e:
            logger.error("wazuh_health_check_failed", error=str(e))
            return False
