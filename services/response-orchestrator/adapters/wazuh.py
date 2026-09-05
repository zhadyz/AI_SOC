"""Scoped Wazuh 4.x Active Response submission.

API acknowledgement proves submission, not successful enforcement on the host.
The agent IDs and configured command name must be supplied by the operator.
See https://documentation.wazuh.com/current/user-manual/api/reference.html
"""

import ipaddress
from datetime import datetime, timedelta

import httpx

from services.response_orchestrator.adapters.base import BaseAdapter, AdapterResult


class WazuhAdapter(BaseAdapter):
    def __init__(
        self,
        api_url="https://wazuh-manager:55000",
        username="wazuh-wui",
        password="",
        verify_ssl=True,
        block_command="",
    ):
        super().__init__("wazuh")
        self.api_url = api_url.rstrip("/")
        self.username, self.password = username, password
        self.verify_ssl, self.block_command = verify_ssl, block_command
        self._token = None
        self._token_expiry = None

    async def _get_token(self):
        if (
            self._token
            and self._token_expiry
            and datetime.utcnow() < self._token_expiry
        ):
            return self._token
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_url}/security/user/authenticate",
                auth=(self.username, self.password),
                timeout=10,
            )
            response.raise_for_status()
            token = response.json()["data"]["token"]
            if not token:
                raise ValueError("Wazuh returned an empty authentication token")
            self._token, self._token_expiry = (
                token,
                datetime.utcnow() + timedelta(minutes=14),
            )
            return token

    async def _api_call(self, method, endpoint, json_body=None, params=None):
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.request(
                method,
                f"{self.api_url}{endpoint}",
                headers={"Authorization": f"Bearer {await self._get_token()}"},
                json=json_body,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("error", 0) or data.get("data", {}).get(
                "total_failed_items", 0
            ):
                raise ValueError("Wazuh reported a failed or partially failed command")
            return data

    def _failure(self, action_type, target, message):
        return AdapterResult(
            False,
            action_type,
            target,
            self.name,
            message,
            error=message,
            rollback_capable=False,
        )

    async def execute(self, action_type, target, params=None):
        params = params or {}
        if action_type != "block_ip":
            return self._failure(
                action_type,
                target,
                "This action requires an implemented, site-specific Wazuh integration",
            )
        agents = params.get("agent_list", [])
        if (
            not agents
            or not isinstance(agents, list)
            or any(
                not isinstance(a, str) or not a.isdigit() or a == "000" for a in agents
            )
        ):
            return self._failure(
                action_type,
                target,
                "Explicit monitored agent IDs are required; all-agent scope is disabled",
            )
        if not self.block_command or not self.password:
            return self._failure(
                action_type,
                target,
                "Wazuh credentials and configured block command are required",
            )
        try:
            address = ipaddress.ip_address(target)
            if address.is_unspecified or address.is_loopback or address.is_multicast:
                raise ValueError("A concrete, non-loopback unicast target is required")
            result = await self._api_call(
                "PUT",
                "/active-response",
                json_body={
                    "command": self.block_command,
                    "alert": {"data": {"srcip": target}},
                },
                params={"agents_list": ",".join(agents), "wait_for_complete": "true"},
            )
            affected = result.get("data", {}).get("affected_items", [])
            if not set(agents).issubset(set(affected)):
                raise ValueError("Wazuh did not acknowledge every requested agent")
            return AdapterResult(
                True,
                action_type,
                target,
                self.name,
                f"Block command submitted to agents {agents}; host enforcement is unverified",
                raw_response=result,
                rollback_capable=False,
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            return self._failure(action_type, target, str(exc))

    async def dry_run(self, action_type, target, params=None):
        return AdapterResult(
            True,
            action_type,
            target,
            self.name,
            f"[DRY RUN] Propose {action_type} on {target}; no command sent",
            raw_response={
                "simulated": True,
                "parameters": params or {},
                "live_supported": action_type == "block_ip"
                and bool(self.block_command),
            },
            rollback_capable=False,
        )

    async def verify(self, action_type, target, params=None):
        return self._failure(
            action_type, target, "Host enforcement requires independent telemetry"
        )

    async def rollback(self, action_type, target, params=None):
        return self._failure(
            action_type,
            target,
            "Rollback requires a tested site-specific command or configured Wazuh timeout",
        )

    async def health_check(self):
        if not self.password:
            return False
        try:
            await self._get_token()
            return True
        except (httpx.HTTPError, ValueError, KeyError):
            return False
