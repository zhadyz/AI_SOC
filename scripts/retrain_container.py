#!/usr/bin/env python3
"""Run reviewed-feedback retraining against the running container deployment.

Candidates and the atomic pointer use the same named volume as inference.
Independent holdout input is copied into a temporary maintenance container.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.container_stack import command
from scripts.docker_control import start_container


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluate-only', action='store_true')
    parser.add_argument('--holdout', type=Path)
    parser.add_argument('--promote', action='store_true')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--skip-build', action='store_true')
    args = parser.parse_args()
    if args.promote and (args.evaluate_only or not args.holdout):
        parser.error('--promote requires --holdout and cannot be combined with --evaluate-only')
    if args.holdout and not args.holdout.is_file():
        parser.error('Holdout file does not exist')
    config = json.loads(command('docker', 'compose', '--profile', 'maintenance', 'config', '--format', 'json'))
    service = config['services']['retraining']
    running = command('docker', 'compose', 'ps', '-q', 'ml-inference')
    if not running:
        raise RuntimeError('Start the container stack before container retraining')
    if not args.skip_build:
        print('Building the retraining image', flush=True)
        command('docker', 'compose', '--profile', 'maintenance', 'build', 'retraining', timeout=900)
    container = 'ai-soc-retrain-' + uuid.uuid4().hex[:12]
    state = ROOT / 'work/maintenance'
    state.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=state) as staging:
        env_file = Path(staging) / 'environment'
        env_file.write_text(''.join(f'{key}={value}\n' for key, value in service['environment'].items()))
        os.chmod(env_file, 0o600)
        network = config['networks']['default']['name']
        volume = config['volumes']['model-data']['name']
        training_args = [flag for flag, enabled in [('--evaluate-only', args.evaluate_only),
                         ('--promote', args.promote), ('--force', args.force)] if enabled]
        if args.holdout:
            training_args += ['--holdout', '/app/data/holdout.csv']
        command('docker', 'create', '--name', container, '--label', 'ai-soc.maintenance=true',
                '--env-file', str(env_file), '--network', network,
                '--mount', f'type=volume,src={volume},dst=/app/models',
                config['name'] + '-retraining', 'python', '-m', 'services.retraining.retrain', *training_args)
    try:
        if args.holdout:
            # A private staging directory holds a copy readable by the image's
            # unprivileged user. The original host file's modes are unchanged.
            with tempfile.TemporaryDirectory(dir=state) as staging:
                readable = Path(staging) / 'holdout.csv'
                readable.write_bytes(args.holdout.read_bytes())
                readable.chmod(0o644)
                command('docker', 'cp', str(readable), container + ':/app/data/holdout.csv', timeout=180)
        start_container(container)
        code = command('docker', 'wait', container, timeout=3600)
        logs = subprocess.run(['docker', 'logs', container], cwd=ROOT, capture_output=True, text=True, timeout=30)
        print(logs.stdout + logs.stderr)
        if code != '0':
            raise RuntimeError('Retraining failed; the serving bundle was not accepted')
    finally:
        command('docker', 'rm', '-f', container)


if __name__ == '__main__':
    main()
