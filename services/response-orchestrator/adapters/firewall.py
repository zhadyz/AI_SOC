"""Firewall planning boundary; live vendor integration remains explicit."""
from services.response_orchestrator.adapters.base import UnavailableAdapter


class FirewallAdapter(UnavailableAdapter):
    supported_actions = ("block_ip", "network_segment", "sinkhole_domain")

    def __init__(self, firewall_type="unconfigured", api_url="", api_key=""):
        super().__init__("firewall")
        self.firewall_type = firewall_type
        self.api_url = api_url
        self.api_key = api_key
