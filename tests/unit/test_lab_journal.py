"""Exercise lab effect/retry boundaries without touching Docker or a real account."""
import pytest
from lab import control


@pytest.fixture
def lab(monkeypatch, tmp_path):
    state = {'active': False, 'container_id': 'owned-original'}
    effects = []
    monkeypatch.setattr(control, 'DB', tmp_path / 'actions.sqlite')
    monkeypatch.setattr(control, 'observe', lambda action: dict(state))
    monkeypatch.setattr(control, 'container', lambda service: ('owned', {}))
    def docker(*args, **kwargs):
        assert args[:4] == ('exec', 'owned', 'usermod', '-L') or args[:4] == ('exec', 'owned', 'usermod', '-U')
        effects.append(args)
        state['active'] = args[3] == '-L'
    monkeypatch.setattr(control, 'docker', docker)
    return state, effects


def action(operation='test-operation'):
    return control.Action(action_type='disable_account', target='lab-user', operation_id=operation)


def test_isolation_alias_cannot_claim_a_second_rollback_lease():
    target = control.Action(action_type='isolate_host', target=control.TARGET_IP, operation_id='alias')
    control.validate_action(target)
    assert target.target == 'lab-target'


def test_effect_retry_and_rollback_are_idempotent(lab):
    state, effects = lab
    for _ in range(2):
        assert control.perform(action(), 'execute')['success']
    assert len(effects) == 1 and state['active']
    assert control.perform(action(), 'verify')['success']
    for _ in range(2):
        assert control.perform(action(), 'rollback')['success']
    assert len(effects) == 2 and not state['active']
    with pytest.raises(ValueError, match='replayed'):
        control.perform(action(), 'execute')


def test_rollback_preserves_preexisting_account_lock(lab):
    state, effects = lab
    state['active'] = True
    assert control.perform(action(), 'execute')['success']
    assert control.perform(action(), 'rollback')['success']
    assert state['active'] and effects == []


def test_uncertain_operation_keeps_ownership_and_recreated_target_is_rejected(lab):
    state, effects = lab
    control.perform(action(), 'execute')
    with control.connect() as db:
        db.execute("UPDATE actions SET phase='uncertain'")
    with pytest.raises(ValueError, match='Another active operation'):
        control.perform(action('second'), 'execute')
    state['container_id'] = 'different-container'
    with pytest.raises(ValueError, match='recreated'):
        control.perform(action(), 'rollback')
    assert len(effects) == 1


def test_interrupted_effect_is_observed_before_retry(lab, monkeypatch):
    state, effects = lab
    normal = control.docker
    def interrupted(*args, **kwargs):
        normal(*args, **kwargs)
        raise RuntimeError('Connection lost after effect')
    monkeypatch.setattr(control, 'docker', interrupted)
    with pytest.raises(RuntimeError):
        control.perform(action(), 'execute')
    assert state['active']
    with control.connect() as db:
        assert db.execute('SELECT phase FROM actions').fetchone()[0] == 'intent'
    monkeypatch.setattr(control, 'docker', normal)
    assert control.perform(action(), 'execute')['success']
    assert len(effects) == 1
    assert control.perform(action(), 'rollback')['success']
    assert not state['active']
