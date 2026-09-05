"""Real response adapter for the repository's isolated Linux/Wazuh lab."""
from services.common.api_security import service_client
from services.response_orchestrator.adapters.base import BaseAdapter, AdapterResult


class LabAdapter(BaseAdapter):
    ACTIONS = {"firewall": {"block_ip"}, "network": {"isolate_host"},
               "edr": {"isolate_host"}, "identity": {"disable_account"}}

    def __init__(self, name, url):
        super().__init__(name)
        self.url = url.rstrip("/")

    async def _call(self, operation, action_type, target, params):
        if action_type not in self.ACTIONS.get(self.name, set()):
            return AdapterResult(False, action_type, target, self.name, "Action is unsupported by the Linux lab", error="unsupported_action", rollback_capable=False)
        params = params or {}
        operation_id = params.get("operation_id")
        if not operation_id:
            return AdapterResult(False, action_type, target, self.name, "A durable operation ID is required", error="missing_operation_id", rollback_capable=False)
        try:
            async with service_client(timeout=45) as client:
                response = await client.post(f"{self.url}/actions/{operation}", json={"action_type": action_type, "target": target, "operation_id": operation_id})
                response.raise_for_status()
                data = response.json()
            return AdapterResult(data["success"], action_type, target, self.name, data["detail"],
                                 raw_response=data, rollback_capable=data["rollback_capable"])
        except Exception:
            return AdapterResult(False, action_type, target, self.name, "Lab state unavailable; reconcile before retrying", error="lab_unavailable", rollback_capable=False)

    async def execute(self, action_type, target, params=None):
        return await self._call("execute", action_type, target, params)

    async def verify(self, action_type, target, params=None):
        return await self._call("verify", action_type, target, params)

    async def rollback(self, action_type, target, params=None):
        return await self._call("rollback", action_type, target, params)

    async def health_check(self):
        try:
            async with service_client(timeout=5) as client:
                return (await client.get(self.url + "/health")).status_code == 200
        except Exception:
            return False
