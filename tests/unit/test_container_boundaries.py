"""Container retry, durable seeding and model publication boundaries."""
import json
from subprocess import CompletedProcess
from unittest.mock import Mock

import pytest

from scripts import docker_control, container_stack
from services.retraining import retrain


def docker_context(monkeypatch, states):
    monkeypatch.setenv('DOCKER_HOST', 'unix:///local-test.sock')
    states = iter(states)
    def output(args, **kwargs):
        return '1.54' if args[1] == 'version' else json.dumps(next(states))
    monkeypatch.setattr(docker_control.subprocess, 'check_output', output)


CREATED = {'Running': False, 'StartedAt': 'never'}


def test_start_retries_same_container_after_transport_timeout(monkeypatch):
    docker_context(monkeypatch, [CREATED, CREATED])
    run = Mock(side_effect=[CompletedProcess([], 28, '\n000', 'timeout'), CompletedProcess([], 0, '\n204', '')])
    monkeypatch.setattr(docker_control.subprocess, 'run', run)
    docker_control.start_container('owned-container')
    assert run.call_count == 2
    assert run.call_args_list[0].args == run.call_args_list[1].args


@pytest.mark.parametrize('running', [True, False])
def test_lost_start_response_does_not_replay_a_started_process(monkeypatch, running):
    docker_context(monkeypatch, [CREATED, {'Running': running, 'StartedAt': 'new-start'}])
    run = Mock(return_value=CompletedProcess([], 28, '\n000', 'timeout'))
    monkeypatch.setattr(docker_control.subprocess, 'run', run)
    docker_control.start_container('one-shot')
    assert run.call_count == 1


def test_daemon_rejection_is_not_retried(monkeypatch):
    docker_context(monkeypatch, [CREATED])
    run = Mock(return_value=CompletedProcess([], 0, 'permission denied\n403', ''))
    monkeypatch.setattr(docker_control.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='403'):
        docker_control.start_container('owned-container')
    assert run.call_count == 1


def test_existing_volumes_are_never_reseeded(monkeypatch, tmp_path):
    names = ['model-data', 'identity-data', 'rag-model-cache', 'triage-data', 'rule-data', 'simulation-history', 'ollama-data']
    folders = ['models', 'identity', 'rag', 'triage', 'rules', 'simulation', 'ollama']
    def command(*args, **kwargs):
        if args[:2] == ('docker', 'cp'):
            assert args[2].endswith(':/tmp/empty.json')
            from pathlib import Path
            Path(args[3]).write_text(json.dumps(dict.fromkeys(folders, False)))
        return '0'
    monkeypatch.setattr(container_stack, 'command', command)
    monkeypatch.setattr(container_stack, 'start_container', lambda _: None)
    copy = Mock(side_effect=AssertionError('Existing data must not be overwritten'))
    monkeypatch.setattr(container_stack, 'copy_to', copy)
    container_stack.seed_volumes(tmp_path, {}, {'volumes': {name: {'name': 'owned-' + name} for name in names}}, True)
    copy.assert_not_called()


def test_successful_http_reload_with_wrong_artifacts_is_rejected(monkeypatch):
    import requests
    response = Mock()
    response.json.return_value = {'status': 'success', 'bundle_fingerprint': 'wrong-volume'}
    monkeypatch.setattr(requests, 'post', Mock(return_value=response))
    monkeypatch.setattr(retrain, 'load_artifacts', lambda: {'artifact': b'expected'})
    with pytest.raises(RuntimeError, match='Serving bundle differs'):
        retrain.trigger_reload()
