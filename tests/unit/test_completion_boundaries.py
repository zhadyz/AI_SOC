"""Recovery, real-flow normalization and lab scope regressions."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services.alert_triage.ml_client import CICIDS2017_FEATURES, MLInferenceClient
from services.common.flow_schema import CICIDS_COLUMN_ALIASES
from services.retraining import retrain


def test_original_cicids_columns_are_mapped_without_inventing_protocol():
    reverse = {canonical: alias for alias, canonical in CICIDS_COLUMN_ALIASES.items()}
    flow = {" " + reverse.get(name, name): float(index) for index, name in enumerate(CICIDS2017_FEATURES)}
    client = MLInferenceClient()
    alert = SimpleNamespace(full_log={"network_flow": flow})
    assert client._extract_network_features(alert)["features"] == list(range(77))
    flow.pop(" Protocol")
    assert client._extract_network_features(alert) is None


def test_conflicting_feature_aliases_are_rejected():
    flow = dict.fromkeys(CICIDS2017_FEATURES, 0.0)
    flow["Total Fwd Packets"] = 10.0
    assert MLInferenceClient()._extract_network_features(SimpleNamespace(full_log=flow)) is None


@pytest.mark.parametrize("existing", [False, True])
def test_failed_promotion_restores_disk_and_serving_pointer(tmp_path, monkeypatch, existing):
    monkeypatch.setattr(retrain, "MODEL_DIR", tmp_path)
    pointer = tmp_path / "active.json"
    before = json.dumps({"bundle": "bundles/old"}).encode()
    if existing:
        pointer.write_bytes(before)
    reload = Mock(side_effect=[TimeoutError("response lost"), None])
    monkeypatch.setattr(retrain, "trigger_reload", reload)
    with pytest.raises(TimeoutError):
        retrain.activate_bundle(tmp_path / "bundles/new")
    assert reload.call_count == 2
    assert pointer.read_bytes() == before if existing else not pointer.exists()


def test_lab_controller_rejects_targets_outside_owned_scope(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_SOC_LAB_STATE", str(tmp_path))
    from lab.control import Action, validate_action
    for kind, target in [("block_ip", "8.8.8.8"), ("block_ip", "127.0.0.1"),
                         ("isolate_host", "production-server"), ("disable_account", "root")]:
        with pytest.raises(ValueError):
            validate_action(Action(action_type=kind, target=target, operation_id="test"))


async def test_lab_adapter_requires_durable_operation_id():
    from services.response_orchestrator.adapters.lab import LabAdapter
    result = await LabAdapter("firewall", "http://127.0.0.1:8900").execute("block_ip", "172.30.77.20")
    assert not result.success and result.error == "missing_operation_id"
