"""Identity planning boundary; real account changes require a vendor adapter."""
from services.response_orchestrator.adapters.base import UnavailableAdapter


class IdentityAdapter(UnavailableAdapter):
    supported_actions = ("disable_account", "revoke_credentials", "enable_mfa")

    def __init__(self, provider="unconfigured", api_url="", api_key=""):
        super().__init__("identity")
        self.provider = provider
        self.api_url = api_url
        self.api_key = api_key
