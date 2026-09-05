#!/usr/bin/env python3
"""Strict lab acceptance: real traffic, SSH denial, rollback and Wazuh forwarding.

Run only after scripts/lab_stack.py up and the local SOC are healthy. All Docker
operations resolve the labeled ai-soc-lab containers; no external target is accepted.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import uuid

from dotenv import dotenv_values
import paramiko
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lab.control import container, docker, PROBE_IP


def eventually(check, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(1)
    raise AssertionError("Timed out waiting for independently observed lab behavior")


def run(state):
    config = dotenv_values(ROOT / '.env')
    headers = {'Authorization': 'Bearer ' + config['AI_SOC_API_KEY']}
    target, _ = container('target')
    probe, _ = container('probe')
    manager, _ = container('manager')
    checks = []

    def traffic():
        result = docker('exec', probe, 'python', '-c',
                        "import urllib.request; assert b'AI-SOC' in urllib.request.urlopen('http://172.30.77.10:8080', timeout=2).read()", check=False)
        return result.returncode == 0

    def ssh():
        # Pin this disposable target's public host key through the trusted local
        # Docker channel before transmitting its password.
        host_key = docker('exec', target, 'cat', '/etc/ssh/ssh_host_ed25519_key.pub').stdout
        known = state / 'known_hosts'
        known.write_text('[127.0.0.1]:18922 ' + host_key)
        client = paramiko.SSHClient()
        client.load_host_keys(str(known))
        try:
            client.connect('127.0.0.1', port=18922, username='lab-user',
                           password=(state / 'lab-password.txt').read_text().strip(),
                           timeout=5, auth_timeout=5, banner_timeout=5, look_for_keys=False, allow_agent=False)
            _, output, _ = client.exec_command('id -un', timeout=5)
            return output.read().strip() == b'lab-user'
        except paramiko.AuthenticationException:
            return False
        finally:
            client.close()

    def action(operation, payload):
        response = requests.post('http://127.0.0.1:8900/actions/' + operation,
                                 headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        assert response.json()['success'], response.text

    def passed(message):
        checks.append(message)
        print('PASS', message, flush=True)

    eventually(traffic)
    assert ssh(), 'Baseline lab SSH sign-in failed'
    passed('Probe HTTP traffic and pinned-host-key SSH sign-in work before enforcement')
    for kind, destination, observation in [('block_ip', PROBE_IP, traffic),
                                            ('isolate_host', 'lab-target', traffic),
                                            ('disable_account', 'lab-user', ssh)]:
        payload = {'action_type': kind, 'target': destination, 'operation_id': 'acceptance-' + uuid.uuid4().hex}
        try:
            action('execute', payload)
            action('verify', payload)
            eventually(lambda: not observation(), timeout=30)
            passed(kind + ' changes independently observed target behavior')
        finally:
            # A timeout can hide a completed effect; always ask the durable
            # controller to restore the recorded prior state, even on failure.
            action('rollback', payload)
        eventually(observation, timeout=30)
        passed(kind + ' rollback restores the prior behavior')

    marker = 'lab-event-' + uuid.uuid4().hex
    event = json.dumps({'ai_soc_lab': 'true', 'srcip': PROBE_IP, 'message': marker}) + '\n'
    docker('exec', '-i', target, 'python3', '-c',
           "import sys; open('/var/log/ai-soc-lab.json', 'a').write(sys.stdin.read())", data=event)
    alert = {}
    def received():
        result = docker('exec', manager, 'tail', '-n', '500', '/var/ossec/logs/alerts/alerts.json', check=False)
        for line in result.stdout.splitlines():
            if marker in line:
                candidate = json.loads(line)
                if candidate.get('rule', {}).get('id') == '100100':
                    alert.update(candidate)
                    return True
        return False
    eventually(received, timeout=180)
    def persisted():
        response = requests.get('http://127.0.0.1:8400/alerts/' + alert['id'], headers=headers, timeout=10)
        return response.status_code == 200 and response.json()['alert_id'] == alert['id']
    eventually(persisted, timeout=240)
    passed('Real Wazuh agent event reaches the manager and is forwarded through SOC triage into storage')
    return {'status': 'passed', 'verified_at': datetime.now(timezone.utc).isoformat(),
            'checks': checks, 'wazuh_alert_id': alert['id'],
            'scope': 'Disposable ai-soc-lab containers only; no production vendor validation'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=ROOT / 'work/lab')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.state_dir.resolve()), indent=2) + '\n')
