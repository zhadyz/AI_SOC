#!/usr/bin/env python3
"""Configure/start/stop the isolated Wazuh and Linux response lab."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import shutil
import tempfile
import time
import subprocess
import sys
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.docker_control import start_container
from scripts.configure_local import configure as configure_soc
from scripts.local_stack import occupied, wait_http


def configure(state):
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state, 0o700)
    config = configure_soc()
    env_file = state / "lab.env"
    if not env_file.exists():
        env_file.write_text(f"LAB_WAZUH_PASSWORD=Soc9!{secrets.token_urlsafe(24)}\nLAB_STATE_DIR={state}\n")
        os.chmod(env_file, 0o600)
    if not (state / "lab-password.txt").exists():
        (state / "lab-password.txt").write_text(secrets.token_urlsafe(24))
        os.chmod(state / "lab-password.txt", 0o600)
    if not (state / "server.crt").exists():
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:3072", "-nodes", "-days", "365",
                        "-keyout", str(state / "server.key"), "-out", str(state / "server.crt"),
                        "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,DNS:wazuh.manager,IP:127.0.0.1"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.chmod(state / "server.key", 0o600)
    (state / "manager.conf").write_text(f"""<ossec_config>
  <global><jsonout_output>yes</jsonout_output><alerts_log>yes</alerts_log><email_notification>no</email_notification></global>
  <alerts><log_alert_level>3</log_alert_level></alerts>
  <remote><connection>secure</connection><port>1514</port><protocol>tcp</protocol></remote>
  <auth><disabled>no</disabled><port>1515</port><use_source_ip>no</use_source_ip><purge>yes</purge><use_password>no</use_password></auth>
  <ruleset><decoder_dir>ruleset/decoders</decoder_dir><rule_dir>ruleset/rules</rule_dir><rule_dir>etc/rules</rule_dir></ruleset>
  <command><name>firewall-drop</name><executable>firewall-drop</executable><timeout_allowed>yes</timeout_allowed></command>
  <integration><name>custom-ai-soc</name><hook_url>http://host.docker.internal:8002/webhook/async</hook_url><api_key>{escape(config['AI_SOC_API_KEY'])}</api_key><rule_id>100100</rule_id><alert_format>json</alert_format></integration>
</ossec_config>\n""")
    os.chmod(state / "manager.conf", 0o600)
    (state / "local_rules.xml").write_text('''<group name="ai_soc_lab,">
  <rule id="100100" level="10"><decoded_as>json</decoded_as><field name="ai_soc_lab">^true$</field>
    <description>AI-SOC controlled lab security event</description><mitre><id>T1110</id></mitre></rule>
</group>\n''')
    (state / "agent.conf").write_text('''<ossec_config>
  <client><server><address>172.30.77.2</address><port>1514</port><protocol>tcp</protocol></server>
    <config-profile>linux</config-profile><enrollment><enabled>yes</enabled><agent_name>lab-target</agent_name></enrollment></client>
  <client_buffer><disabled>no</disabled><queue_size>5000</queue_size><events_per_second>500</events_per_second></client_buffer>
  <localfile><log_format>json</log_format><location>/var/log/ai-soc-lab.json</location></localfile>
  <active-response><disabled>no</disabled><ca_store>etc/wpk_root.pem</ca_store><ca_verification>yes</ca_verification></active-response>
</ossec_config>\n''')
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["configure", "up", "down", "status"])
    parser.add_argument("--state-dir", type=Path, default=ROOT / "work/lab")
    parser.add_argument("--skip-build", action="store_true", help="Reuse the existing lab target image")
    args = parser.parse_args()
    state = args.state_dir.resolve()
    config = configure(state)
    command = ["docker", "compose", "--env-file", str(state / "lab.env"), "-f", str(ROOT / "lab/compose.yaml")]
    record_path = state / "controller.json"
    if args.action == "configure":
        print(f"Configured disposable lab in {state}")
    elif args.action == "status":
        subprocess.run([*command, "ps"], check=True)
    elif args.action == "up":
        if occupied(8900):
            raise RuntimeError("Port 8900 is in use; no existing controller was changed")
        subprocess.run([*command, "create", *([] if args.skip_build else ["--build"])], cwd=ROOT, check=True, timeout=600)
        manager = subprocess.check_output([*command, "ps", "-aq", "manager"], text=True).strip()
        target = subprocess.check_output([*command, "ps", "-aq", "target"], text=True).strip()
        manager = subprocess.check_output(["docker", "inspect", manager, "--format", "{{.Name}}"], text=True).strip().lstrip("/")
        target = subprocess.check_output(["docker", "inspect", target, "--format", "{{.Name}}"], text=True).strip().lstrip("/")
        # Provision the disposable containers without depending on Desktop host
        # filesystem sharing. Secrets stay out of image layers and command args.
        with tempfile.TemporaryDirectory(dir=state) as staging:
            staging = Path(staging)
            for service, cid, source in [("manager", manager, state / "manager.conf"), ("target", target, state / "agent.conf")]:
                mount = staging / service / "wazuh-config-mount"
                (mount / "etc").mkdir(parents=True)
                shutil.copy2(source, mount / "etc/ossec.conf")
                if service == "manager":
                    (mount / "etc/rules").mkdir()
                    shutil.copy2(state / "local_rules.xml", mount / "etc/rules/local_rules.xml")
                subprocess.run(["docker", "cp", str(mount), cid + ":/"], check=True, timeout=30)
            secrets_dir = staging / "secrets"
            secrets_dir.mkdir()
            shutil.copy2(state / "lab-password.txt", secrets_dir / "lab_password")
            subprocess.run(["docker", "cp", str(secrets_dir), target + ":/run/"], check=True, timeout=30)
        for service in ("manager", "probe", "target"):
            cid = subprocess.check_output([*command, "ps", "-aq", service], text=True).strip()
            name = subprocess.check_output(["docker", "inspect", cid, "--format", "{{.Name}}"], text=True).strip().lstrip("/")
            running = subprocess.check_output(["docker", "inspect", name, "--format", "{{.State.Running}}"], text=True).strip()
            if running != "true":
                start_container(name)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            status = subprocess.run(["docker", "exec", manager, "/var/ossec/bin/wazuh-control", "status"], capture_output=True, text=True, timeout=30)
            if "wazuh-analysisd is running" in status.stdout and "wazuh-apid is running" in status.stdout:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Wazuh manager did not become ready; inspect its container logs")
        for source, destination in [(state / "server.crt", "/var/ossec/api/configuration/ssl/server.crt"),
                                    (state / "server.key", "/var/ossec/api/configuration/ssl/server.key"),
                                    (state / "manager.conf", "/var/ossec/etc/ossec.conf"),
                                    (state / "local_rules.xml", "/var/ossec/etc/rules/local_rules.xml"),
                                    (ROOT / "lab/custom-ai-soc", "/var/ossec/integrations/custom-ai-soc")]:
            subprocess.run(["docker", "cp", str(source), manager + ":" + destination], check=True, timeout=30)
            subprocess.run(["docker", "exec", manager, "chown", "root:wazuh", destination], check=True, timeout=30)
            subprocess.run(["docker", "exec", manager, "chmod", "750" if "integrations" in destination else "640", destination], check=True, timeout=30)
        subprocess.run(["docker", "exec", manager, "/var/ossec/bin/wazuh-control", "restart"], check=True, timeout=120)
        # The manager's durable registration survives target image replacement.
        # Restore ONLY this disposable agent's key through the trusted Docker
        # channel. Key material never appears in argv, logs or image layers.
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            registered = subprocess.check_output(["docker", "exec", manager,
                "/var/ossec/framework/python/bin/python3", "-c",
                "from pathlib import Path; print(''.join(line for line in Path('/var/ossec/etc/client.keys').read_text().splitlines(True) if len(line.split())==4 and line.split()[1]=='lab-target'),end='')"], text=True, timeout=30)
            if registered.strip():
                if len(registered.strip().splitlines()) != 1:
                    raise RuntimeError("Ambiguous lab agent registration")
                break
            time.sleep(2)
        else:
            raise RuntimeError("Lab target did not enroll with the manager; inspect agent logs")
        with tempfile.TemporaryDirectory(dir=state) as staging:
            key_file = Path(staging) / "client.keys"
            key_file.write_text(registered)
            key_file.chmod(0o600)
            for source, destination in [(key_file, "/var/ossec/etc/client.keys"),
                                        (state / "agent.conf", "/var/ossec/etc/ossec.conf")]:
                subprocess.run(["docker", "cp", str(source), target + ":" + destination], check=True, timeout=30)
                subprocess.run(["docker", "exec", target, "chown", "root:wazuh", destination], check=True, timeout=30)
                subprocess.run(["docker", "exec", target, "chmod", "640", destination], check=True, timeout=30)
        subprocess.run(["docker", "exec", target, "/var/ossec/bin/wazuh-control", "restart"], check=True, timeout=120)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            agents = subprocess.check_output(["docker", "exec", manager, "/var/ossec/bin/agent_control", "-lc"], text=True, timeout=30)
            if any("lab-target" in line and "Active" in line for line in agents.splitlines()):
                break
            time.sleep(2)
        else:
            raise RuntimeError("Lab agent registration exists but the target did not connect")
        env = {**os.environ, **config, "PYTHONPATH": str(ROOT), "AI_SOC_LAB_STATE": str(state)}
        with (state / "controller.log").open("a") as log:
            process = subprocess.Popen([str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "lab.control:app", "--host", "127.0.0.1", "--port", "8900"],
                                       cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        record_path.write_text(json.dumps({"pid": process.pid}))
        wait_http("http://127.0.0.1:8900/health", 120)
        print("Lab controller: http://127.0.0.1:8900; Wazuh API: https://localhost:15500")
    else:
        if record_path.exists():
            pid = json.loads(record_path.read_text())["pid"]
            result = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
            if "lab.control:app" in result.stdout:
                os.killpg(pid, signal.SIGTERM)
            record_path.unlink()
        subprocess.run([*command, "stop"], check=True)


if __name__ == "__main__":
    main()
