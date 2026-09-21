#!/usr/bin/env python3
"""Provision and start the Compose stack with durable named volumes.

Uses explicit create/copy/start steps without requiring host bind mounts or
attached Docker streams. Existing data volumes are never overwritten by seeding.
Stop the native stack before using up. No other Compose project is modified.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.docker_control import start_container
from scripts.configure_local import configure
from scripts.local_stack import occupied, SERVICES
from services.common.model_integrity import verified_bytes


def command(*args, timeout=120):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{args[0]} {args[1]} failed: {result.stderr[:1500]}')
    return result.stdout.strip()


def copy_to(source, cid, destination):
    command('docker', 'cp', str(source), cid + ':' + destination, timeout=180)


def snapshot_sqlite(source, destination):
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)
    os.chmod(destination, 0o600)


def seed_volumes(state, config, compose, import_native):
    paths = {'model-data': 'models', 'identity-data': 'identity', 'rag-model-cache': 'rag',
             'triage-data': 'triage', 'rule-data': 'rules', 'simulation-history': 'simulation', 'ollama-data': 'ollama'}
    mounts = []
    for volume, folder in paths.items():
        name = compose['volumes'][volume]['name']
        command('docker', 'volume', 'create', name)
        mounts += ['--mount', f'type=volume,src={name},dst=/seed/{folder}']
    # The helper accesses only these application volumes, with no host mounts or
    # Docker socket. Its only process fixes ownership for the non-root app user.
    ownership = "import os,json; from pathlib import Path; Path('/tmp/empty.json').write_text(json.dumps({p.name:not any(p.iterdir()) for p in Path('/seed').iterdir()})); [(os.chown(p,1000,1000),[(os.chown(os.path.join(p,n),1000,1000)) for n in files+dirs]) for root in ['/seed/'+n for n in ['models','identity','rag','triage','rules','simulation']] for p,dirs,files in os.walk(root)]"
    cid = 'ai-soc-seed-' + uuid.uuid4().hex[:12]
    command('docker', 'create', '--name', cid,
                  '--label', 'ai-soc.bootstrap=true', *mounts, 'python:3.11-slim', 'python', '-c', ownership)
    try:
        with tempfile.TemporaryDirectory(dir=state) as temp:
            temp = Path(temp)
            start_container(cid)
            if command('docker', 'wait', cid) != '0':
                raise RuntimeError('Volume inspection failed')
            command('docker', 'cp', cid + ':/tmp/empty.json', str(temp / 'empty.json'))
            empty = json.loads((temp / 'empty.json').read_text())
            if empty['models']:
                verified_bytes(ROOT / 'models')
                models = temp / 'models'
                models.mkdir()
                for source in [*(ROOT / 'models').glob('*.pkl'), ROOT / 'models/manifest.json']:
                    shutil.copy2(source, models / source.name)
                pointer = ROOT / 'models/active.json'
                if pointer.exists():
                    relative = json.loads(pointer.read_text())['bundle']
                    bundle = (ROOT / 'models' / relative).resolve()
                    if not bundle.is_relative_to((ROOT / 'models').resolve()):
                        raise ValueError('Active bundle escapes the model directory')
                    verified_bytes(bundle, config['AI_SOC_MODEL_SIGNING_KEY'], require_signature=True)
                    target = models / relative
                    target.mkdir(parents=True)
                    for source in [*bundle.glob('*.pkl'), bundle / 'manifest.json']:
                        shutil.copy2(source, target / source.name)
                    shutil.copy2(pointer, models / 'active.json')
                copy_to(str(models) + '/.', cid, '/seed/models/')
            if empty['identity']:
                source = Path(config['AI_SOC_IDENTITY_DIR']) / 'identity.sqlite'
                snapshot_sqlite(source, temp / 'identity.sqlite')
                copy_to(temp / 'identity.sqlite', cid, '/seed/identity/identity.sqlite')
            if import_native:
                for folder, source_name, target_name in [('triage', 'triage-jobs.sqlite', 'triage-jobs.sqlite'), ('rules', 'rules.sqlite', 'rules.sqlite')]:
                    if empty[folder] and (state / source_name).exists():
                        snapshot_sqlite(state / source_name, temp / source_name)
                        copy_to(temp / source_name, cid, '/seed/' + folder + '/' + target_name)
                for folder, sources in [('rag', ['chroma', 'embedding-model']), ('simulation', ['simulation']), ('ollama', ['ollama-models'])]:
                    if not empty[folder]:
                        continue
                    for source_name in sources:
                        source = state / source_name
                        if source.exists():
                            destination = '/seed/' + folder + '/'
                            if source_name == 'simulation':
                                source = str(source) + '/.'
                            elif source_name == 'ollama-models':
                                destination += 'models'
                            copy_to(source, cid, destination)
            print('Seeded empty application volumes; existing volume contents preserved', flush=True)
        start_container(cid)
        exit_code = command('docker', 'wait', cid)
        if exit_code != '0':
            raise RuntimeError('Volume ownership setup failed')
    finally:
        command('docker', 'rm', '-f', cid)


def start_service(name, cid, completed=False, timeout=240):
    current = json.loads(command('docker', 'inspect', cid, '--format', '{{json .State}}'))
    if not current['Running']:
        start_container(cid)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = json.loads(command('docker', 'inspect', cid, '--format', '{{json .State}}'))
        if completed and state['Status'] == 'exited':
            if state['ExitCode'] != 0:
                raise RuntimeError(f'{name} failed; inspect docker compose logs {name}')
            return
        if not completed and state.get('Health', {}).get('Status') == 'healthy':
            print('Ready:', name, flush=True)
            return
        if state['Status'] in {'dead', 'exited'} or state.get('Health', {}).get('Status') == 'unhealthy':
            raise RuntimeError(f'{name} did not become healthy; inspect docker compose logs {name}')
        time.sleep(1)
    raise RuntimeError(f'Timed out waiting for {name}; inspect its container logs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['up', 'down', 'status'])
    parser.add_argument('--state-dir', type=Path, default=ROOT / 'work/runtime')
    parser.add_argument('--import-native-state', action='store_true', help='Seed empty volumes from a stopped native deployment; never overwrite existing volume data')
    parser.add_argument('--skip-build', action='store_true')
    args = parser.parse_args()
    if args.action != 'up':
        print(command('docker', 'compose', 'stop' if args.action == 'down' else 'ps'))
        return
    ports = [5050, 11434] + [port for _, port in SERVICES.values()]
    owned = command('docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=ai-soc').split()
    owned_ports = set()
    if owned:
        for container in json.loads(command('docker', 'inspect', *owned)):
            # Desktop can omit NetworkSettings.Ports after a replacement even
            # while its host forwarding is active. Use the running container's
            # declared bindings; startup still validates actual service health.
            for bindings in container['HostConfig']['PortBindings'].values():
                owned_ports.update(int(binding['HostPort']) for binding in bindings or [])
    if any(occupied(port) and port not in owned_ports for port in ports):
        raise ValueError('Stop the native application or conflicting listener before container startup; no running process was changed')
    state = args.state_dir.resolve()
    state.mkdir(parents=True, exist_ok=True)
    config = configure(state_dir=state)
    compose = json.loads(command('docker', 'compose', 'config', '--format', 'json'))
    if not args.skip_build:
        print('Building application images', flush=True)
        command('docker', 'compose', 'build', timeout=900)
    print('Creating application containers and checking persistent volumes', flush=True)
    command('docker', 'compose', 'create', timeout=600)
    seed_volumes(state, config, compose, args.import_native_state)
    for name in ['postgres', 'ollama', 'model-init', 'ml-inference', 'feedback-service', 'rag-service',
                 'correlation-engine', 'alert-triage', 'rule-generator', 'response-orchestrator', 'wazuh-integration', 'dashboard']:
        cid = command('docker', 'compose', 'ps', '-aq', name)
        cid = command('docker', 'inspect', cid, '--format', '{{.Name}}').lstrip('/')
        start_service(name, cid, completed=name == 'model-init', timeout=600 if name in {'model-init','rag-service'} else 240)
    print('Dashboard: http://localhost:5050', flush=True)


if __name__ == '__main__':
    main()
