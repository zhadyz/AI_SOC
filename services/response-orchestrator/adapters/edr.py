"""EDR planning boundary; never report a synthetic live containment."""
from services.response_orchestrator.adapters.base import UnavailableAdapter


class EDRAdapter(UnavailableAdapter):
    supported_actions = ("isolate_host", "deploy_edr", "kill_process", "restore_backup")

    def __init__(self, platform="unconfigured", api_url="", api_key=""):
        super().__init__("edr")
        self.platform = platform
        self.api_url = api_url
        self.api_key = api_key
