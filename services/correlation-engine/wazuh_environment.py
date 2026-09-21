"""
Wazuh Environment Builder - Attack Campaign Simulator
AI-Augmented SOC

Auto-populates the simulation environment from Wazuh agent inventory.
Queries the Wazuh Manager API for registered agents, their OS,
open ports, installed packages, and vulnerability scan results.
Transforms this into the Environment model for simulation.
"""

import ipaddress
import logging
from collections import defaultdict
from typing import Dict, List, Optional

import httpx

from services.correlation_engine.environment import Environment, Host, HostDefenses, NetworkSegment, ServiceInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known package names that indicate security products
# ---------------------------------------------------------------------------

_EDR_PACKAGES = {
    "crowdstrike-falcon-sensor",
    "falcon-sensor",
    "sentinelone-sensor",
    "sentinelone",
    "carbonblack",
    "cb-sensor",
    "cbagent",
    "carbon-black",
    "cortex-xdr",
    "traps",
    "cylance",
    "cylanceprotect",
    "cybereason",
    "defender",
    "windows-defender",
    "tanium-endpoint",
    "elastic-agent",
}

_MFA_PACKAGES = {
    "duo-unix",
    "duo-authentication-proxy",
    "duo",
    "google-authenticator",
    "libpam-google-authenticator",
    "authy",
    "totp",
    "freeradius",
    "pam-radius",
}

_HIDS_PACKAGES = {
    "ossec-hids",
    "ossec-hids-agent",
    "wazuh-agent",
    "aide",
    "samhain",
    "rkhunter",
    "chkrootkit",
}

_FIREWALL_PACKAGES = {
    "iptables",
    "ufw",
    "firewalld",
    "nftables",
    "pf",
    "ipfw",
    "windows-firewall",
    "netfilter",
}

# ---------------------------------------------------------------------------
# Port → service name mapping for common services
# ---------------------------------------------------------------------------

_PORT_SERVICE_MAP: Dict[int, str] = {
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "postfix",
    53: "dns",
    80: "nginx",
    110: "pop3",
    143: "imap",
    389: "ldap",
    443: "nginx-ssl",
    445: "smb",
    465: "smtps",
    587: "submission",
    636: "ldaps",
    993: "dovecot",
    995: "pop3s",
    1433: "mssql",
    1521: "oracle",
    3306: "mysql",
    3389: "rdp",
    5432: "postgresql",
    5985: "winrm-http",
    5986: "winrm-https",
    6379: "redis",
    8080: "http-alt",
    8443: "https-alt",
    8888: "jupyter",
    9200: "elasticsearch",
    27017: "mongodb",
    88: "kerberos",
    135: "msrpc",
    137: "netbios-ns",
    138: "netbios-dgm",
    139: "netbios-ssn",
}

# Ports that are typically exposed externally
_EXTERNALLY_EXPOSED_PORTS = {21, 22, 25, 53, 80, 110, 143, 389, 443, 465, 587, 636, 993, 995, 8080, 8443}


class WazuhEnvironmentBuilder:
    """Build a simulation Environment by querying the Wazuh Manager API."""

    def __init__(
        self,
        wazuh_url: str,
        username: str,
        password: str,
        verify_ssl: bool = False,
        timeout: float = 30.0,
    ):
        self._wazuh_url = wazuh_url.rstrip("/")
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self._token: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def build_environment(self) -> Environment:
        """
        Query Wazuh API and build a complete Environment model.

        Steps:
        1. Authenticate with Wazuh API (POST /security/user/authenticate)
        2. Get all agents (GET /agents)
        3. For each agent, get open ports, packages, vulnerabilities
        4. Transform into Host objects
        5. Build network segments from IP subnets
        6. Return Environment
        """
        token = await self._authenticate()

        agents = await self._get_agents(token)
        logger.info("WazuhEnvironmentBuilder: found %d agents", len(agents))

        hosts: Dict[str, Host] = {}

        for agent in agents:
            agent_id = agent.get("id", "")
            agent_name = agent.get("name", agent_id)
            agent_ip = agent.get("ip", "")
            os_info = agent.get("os", {}) or {}
            os_platform = os_info.get("platform", "linux").lower()

            if not agent_ip or agent_ip in ("any", ""):
                logger.debug("Skipping agent %s — no IP address", agent_id)
                continue

            # Normalize OS type to linux/windows
            if "windows" in os_platform:
                os_type = "windows"
            else:
                os_type = "linux"

            logger.debug("Processing agent %s (%s, %s)", agent_name, agent_ip, os_type)

            # Parallel fetch for this agent
            ports_data = await self._get_agent_ports(token, agent_id)
            packages_data = await self._get_agent_packages(token, agent_id)
            vuln_data = await self._get_agent_vulnerabilities(token, agent_id)

            # Build service list from open ports
            services = self._build_services(ports_data, vuln_data)

            # Estimate defenses from packages
            defenses = self._estimate_defenses(packages_data)

            # Wazuh agents have wazuh_agent=True by definition
            defenses.wazuh_agent = True

            # Infer criticality from hostname patterns
            criticality = self._infer_criticality(agent_name, services)

            host = Host(
                ip=agent_ip,
                hostname=agent_name,
                os_type=os_type,
                criticality=criticality,
                services=services,
                defenses=defenses,
            )
            hosts[agent_ip] = host

        if not hosts:
            logger.warning(
                "WazuhEnvironmentBuilder: no hosts built from agents; "
                "returning empty environment"
            )

        segments = self._build_segments(hosts)

        env = Environment(
            hosts=hosts,
            segments=segments,
            name="wazuh-live-environment",
        )
        env.save_initial_state()

        logger.info(
            "WazuhEnvironmentBuilder: built environment with %d hosts, %d segments",
            len(hosts),
            len(segments),
        )
        return env

    # ------------------------------------------------------------------
    # Wazuh API helpers
    # ------------------------------------------------------------------

    async def _authenticate(self) -> str:
        """Get JWT token from Wazuh API."""
        auth_url = f"{self._wazuh_url}/security/user/authenticate"
        try:
            async with httpx.AsyncClient(verify=self._verify_ssl, timeout=self._timeout) as client:
                response = await client.post(
                    auth_url,
                    auth=(self._username, self._password),
                )
                response.raise_for_status()
                data = response.json()
                token = data["data"]["token"]
                self._token = token
                logger.info("WazuhEnvironmentBuilder: authenticated successfully")
                return token
        except httpx.HTTPError as exc:
            logger.error("WazuhEnvironmentBuilder: authentication failed: %s", exc)
            raise

    async def _get_agents(self, token: str) -> List[dict]:
        """Fetch all registered Wazuh agents."""
        url = f"{self._wazuh_url}/agents"
        params = {
            "select": "id,name,ip,os.name,os.platform,os.version",
            "limit": 500,
            "status": "active",
        }
        try:
            async with httpx.AsyncClient(verify=self._verify_ssl, timeout=self._timeout) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", {}).get("affected_items", [])
        except httpx.HTTPError as exc:
            logger.error("WazuhEnvironmentBuilder: failed to get agents: %s", exc)
            return []

    async def _get_agent_ports(self, token: str, agent_id: str) -> List[dict]:
        """Get open ports for an agent via syscollector."""
        url = f"{self._wazuh_url}/syscollector/{agent_id}/ports"
        params = {"limit": 200, "state": "listening"}
        try:
            async with httpx.AsyncClient(verify=self._verify_ssl, timeout=self._timeout) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )
                if response.status_code == 404:
                    return []
                response.raise_for_status()
                data = response.json()
                return data.get("data", {}).get("affected_items", [])
        except httpx.HTTPError as exc:
            logger.debug("WazuhEnvironmentBuilder: failed to get ports for %s: %s", agent_id, exc)
            return []

    async def _get_agent_packages(self, token: str, agent_id: str) -> List[dict]:
        """Get installed packages for an agent via syscollector."""
        url = f"{self._wazuh_url}/syscollector/{agent_id}/packages"
        params = {"limit": 500}
        try:
            async with httpx.AsyncClient(verify=self._verify_ssl, timeout=self._timeout) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )
                if response.status_code == 404:
                    return []
                response.raise_for_status()
                data = response.json()
                return data.get("data", {}).get("affected_items", [])
        except httpx.HTTPError as exc:
            logger.debug("WazuhEnvironmentBuilder: failed to get packages for %s: %s", agent_id, exc)
            return []

    async def _get_agent_vulnerabilities(self, token: str, agent_id: str) -> List[dict]:
        """Get known vulnerabilities for an agent."""
        url = f"{self._wazuh_url}/vulnerability/{agent_id}"
        params = {"limit": 500}
        try:
            async with httpx.AsyncClient(verify=self._verify_ssl, timeout=self._timeout) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )
                if response.status_code in (400, 404):
                    # Vulnerability module may not be enabled
                    return []
                response.raise_for_status()
                data = response.json()
                return data.get("data", {}).get("affected_items", [])
        except httpx.HTTPError as exc:
            logger.debug("WazuhEnvironmentBuilder: failed to get vulns for %s: %s", agent_id, exc)
            return []

    # ------------------------------------------------------------------
    # Transformation helpers
    # ------------------------------------------------------------------

    def _build_services(self, ports_data: List[dict], vuln_data: List[dict]) -> List[ServiceInfo]:
        """Build ServiceInfo list from port and vulnerability data."""
        # Map CVEs to packages (to later associate with services by port)
        # Wazuh vuln items have: cve, package.name, severity
        package_cves: Dict[str, List[str]] = defaultdict(list)
        for vuln in vuln_data:
            cve = vuln.get("cve", "")
            pkg_name = vuln.get("package", {}).get("name", "") if isinstance(vuln.get("package"), dict) else ""
            if cve and pkg_name:
                package_cves[pkg_name.lower()].append(cve)

        seen_ports = set()
        services: List[ServiceInfo] = []

        for port_entry in ports_data:
            # Wazuh syscollector port item shape:
            # { local: {port: 22, ip: "0.0.0.0"}, protocol: "tcp", state: "listening", ... }
            local = port_entry.get("local", {})
            port_num = local.get("port")
            protocol = port_entry.get("protocol", "tcp")

            if port_num is None or port_num in seen_ports:
                continue
            seen_ports.add(port_num)

            svc_name = _PORT_SERVICE_MAP.get(port_num, f"port-{port_num}")
            exposed = port_num in _EXTERNALLY_EXPOSED_PORTS

            # Associate CVEs via service name matching
            cves = list(package_cves.get(svc_name, []))

            services.append(ServiceInfo(
                name=svc_name,
                port=port_num,
                version="",
                protocol=protocol,
                exposed_externally=exposed,
                cves=cves,
            ))

        return services

    def _estimate_defenses(self, packages: List[dict]) -> HostDefenses:
        """
        Estimate host defenses from installed packages.

        Looks for: CrowdStrike, SentinelOne, Carbon Black (EDR),
        duo, google-authenticator (MFA), iptables/ufw (firewall),
        ossec/wazuh (HIDS).
        """
        pkg_names = set()
        for pkg in packages:
            name = pkg.get("name", "").lower().strip()
            if name:
                pkg_names.add(name)
                # Also match partial names by stripping version suffixes
                base = name.split("-")[0] if "-" in name else name
                pkg_names.add(base)

        edr_present = bool(pkg_names & _EDR_PACKAGES)
        mfa_enabled = bool(pkg_names & _MFA_PACKAGES)
        firewall_enabled = bool(pkg_names & _FIREWALL_PACKAGES)

        return HostDefenses(
            edr_present=edr_present,
            mfa_enabled=mfa_enabled,
            firewall_enabled=firewall_enabled,
            patched=True,  # Assume patched; no reliable signal from packages alone
            wazuh_agent=True,
        )

    def _infer_criticality(self, hostname: str, services: List[ServiceInfo]) -> str:
        """Infer host criticality from hostname patterns and services."""
        name_lower = hostname.lower()

        # Critical patterns
        if any(k in name_lower for k in ("dc", "domain-controller", "ad-server", "kdc", "ldap")):
            return "critical"
        if any(k in name_lower for k in ("db", "database", "sql", "postgres", "mysql", "oracle")):
            return "critical"

        # High patterns
        if any(k in name_lower for k in ("mail", "smtp", "exchange", "backup", "vpn", "fw", "firewall")):
            return "high"
        if any(k in name_lower for k in ("web", "app", "api", "lb", "proxy", "nginx", "apache")):
            return "high"

        # Low patterns
        if any(k in name_lower for k in ("workstation", "ws", "laptop", "desktop", "dev-")):
            return "low"

        # If host has services listening on critical ports, mark high
        critical_ports = {389, 636, 88, 1433, 1521, 3306, 5432, 27017}
        for svc in services:
            if svc.port in critical_ports:
                return "critical"

        return "medium"

    def _build_segments(self, hosts: Dict[str, Host]) -> Dict[str, NetworkSegment]:
        """
        Build network segments from host IP addresses.

        Groups hosts by /24 subnet. Assigns segment names based on
        subnet address. Assumes adjacent /24 subnets within the same
        /16 are reachable from each other.
        """
        subnet_hosts: Dict[str, List[str]] = defaultdict(list)

        for ip, host in hosts.items():
            try:
                iface = ipaddress.ip_interface(f"{ip}/24")
                subnet_key = str(iface.network.network_address)
            except ValueError:
                subnet_key = "unknown"
            subnet_hosts[subnet_key].append(ip)

        segments: Dict[str, NetworkSegment] = {}

        # Build a lookup from subnet to segment name
        subnet_to_name: Dict[str, str] = {}
        for idx, subnet in enumerate(sorted(subnet_hosts.keys())):
            # Use last two octets for a human-readable name
            parts = subnet.split(".")
            seg_name = f"net-{parts[2]}" if len(parts) >= 3 else f"segment-{idx}"
            subnet_to_name[subnet] = seg_name

        for subnet, seg_name in subnet_to_name.items():
            # Determine reachable_from: segments in the same /16
            reachable: List[str] = []
            try:
                my_net = ipaddress.ip_network(f"{subnet}/24", strict=False)
                my_16 = ipaddress.ip_network(
                    f"{'.'.join(subnet.split('.')[:2])}.0.0/16", strict=False
                )
                for other_subnet, other_name in subnet_to_name.items():
                    if other_subnet == subnet:
                        continue
                    try:
                        other_net = ipaddress.ip_network(f"{other_subnet}/24", strict=False)
                        if other_net.subnet_of(my_16):
                            reachable.append(other_name)
                    except ValueError:
                        pass
            except ValueError:
                pass

            segments[seg_name] = NetworkSegment(
                name=seg_name,
                host_ips=subnet_hosts[subnet],
                reachable_from=reachable,
            )

        return segments

    def to_dict(self, environment: Environment) -> dict:
        """Serialize an Environment built from Wazuh back to the JSON format."""
        return {
            "name": environment.name,
            "hosts": {
                ip: {
                    "hostname": h.hostname,
                    "os": h.os_type,
                    "criticality": h.criticality,
                    "services": [s.to_dict() for s in h.services],
                    "defenses": h.defenses.to_dict(),
                }
                for ip, h in environment.hosts.items()
            },
            "segments": {
                name: {
                    "hosts": seg.host_ips,
                    "reachable_from": seg.reachable_from,
                }
                for name, seg in environment.segments.items()
            },
        }
