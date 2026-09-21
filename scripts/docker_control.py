"""Small local Docker Engine control calls without CLI attachment streams."""
import os
import json
import subprocess
from urllib.parse import quote


def start_container(name, timeout=10, attempts=3):
    endpoint = os.getenv('DOCKER_HOST')
    if not endpoint:
        endpoint = subprocess.check_output(
            ['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}'], text=True, timeout=15).strip()
    if not endpoint.startswith('unix://'):
        # Preserve Docker's configured transport and TLS handling for remote contexts.
        subprocess.run(['docker', 'start', name], check=True, timeout=timeout)
        return
    version = subprocess.check_output(['docker', 'version', '--format', '{{.Server.APIVersion}}'], text=True, timeout=15).strip()
    def state():
        return json.loads(subprocess.check_output(['docker', 'inspect', name, '--format', '{{json .State}}'],
                                                 text=True, timeout=15))
    before = state()
    if before['Running']:
        return
    # Desktop can leave a newly created container waiting after a timed-out
    # start request. Retrying start on that SAME container is safe: the Engine
    # returns 304 if it is already running. Never recreate it on uncertainty.
    for attempt in range(attempts):
        result = subprocess.run(['curl', '--silent', '--show-error', '--max-time', str(timeout),
                                 '--unix-socket', endpoint.removeprefix('unix://'), '-X', 'POST',
                                 'http://localhost/v' + version + '/containers/' + quote(name, safe='') + '/start',
                                 '-w', '\n%{http_code}'], capture_output=True, text=True, timeout=timeout + 5)
        if result.returncode:
            observed = state()
            if observed['Running'] or observed['StartedAt'] != before['StartedAt']:
                # A one-shot process may have completed before the response was
                # lost. Let the caller check its exit code; never execute it twice.
                return
            if attempt + 1 < attempts:
                continue
            raise RuntimeError('Docker start transport failed: ' + result.stderr[:400])
        body, _, status = result.stdout.rpartition('\n')
        if status not in {'204', '304'}:
            raise RuntimeError(f'Docker start failed for {name}: HTTP {status}: {body[:400]}')
        return
