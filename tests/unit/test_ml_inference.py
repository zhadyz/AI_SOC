"""Exercise the actual bundled models and public inference contract."""
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ml_training import inference_api as api
from services.alert_triage.ml_client import CICIDS2017_FEATURES


@pytest.fixture(scope="module")
def client():
    with TestClient(api.app) as instance:
        yield instance


@pytest.mark.parametrize("name", api.MODEL_NAMES)
def test_real_model_prediction(client, name):
    result = client.post("/predict", json={"features": api.scaler.mean_.tolist(), "model_name": name})
    assert result.status_code == 200
    data = result.json()
    assert data["prediction"] in {"BENIGN", "ATTACK"}
    assert sum(data["probabilities"].values()) == pytest.approx(1, abs=1e-6)
    assert data["model_used"] == name


def test_feature_order_matches_training_artifact(client):
    contract = client.get("/models").json()
    assert contract["feature_count"] == 77
    assert contract["feature_names"] == CICIDS2017_FEATURES


@pytest.mark.parametrize("count", [0, 50, 76, 78, 100])
def test_wrong_feature_count(client, count):
    assert client.post("/predict", json={"features": [0.0] * count}).status_code == 422


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_rejected_before_inference(value):
    with pytest.raises(ValidationError):
        api.NetworkFlow(features=[value] * 77)


def test_null_model_rejected(client):
    assert client.post("/predict", json={"features": [0.0] * 77, "model_name": None}).status_code == 422


def test_unknown_model_rejected(client):
    assert client.post("/predict", json={"features": [0.0] * 77, "model_name": "unknown"}).status_code == 400


def test_named_features_are_reordered(client):
    features = dict(reversed(list(zip(api.feature_names, api.scaler.mean_.tolist()))))
    named = client.post("/predict/named", json={"features": features})
    ordered = client.post("/predict", json={"features": api.scaler.mean_.tolist()})
    assert named.status_code == 200
    assert named.json()["probabilities"] == ordered.json()["probabilities"]
    features.pop(next(iter(features)))
    assert client.post("/predict/named", json={"features": features}).status_code == 422


def test_batch_has_individual_errors_and_rejects_empty(client):
    assert client.post("/predict/batch", json=[]).status_code == 422
    response = client.post("/predict/batch", json=[{"features": [0.0]*77},
                        {"features": [0.0]*77, "model_name": "unknown"}])
    assert response.status_code == 200
    assert response.json()["results"][1]["status_code"] == 400
    assert "prediction" in response.json()["results"][0]


def test_failed_reload_keeps_working_bundle(client, tmp_path, monkeypatch):
    before = api.models
    monkeypatch.setattr(api, "MODEL_PATH", tmp_path)
    assert client.post("/models/reload").status_code == 503
    assert api.models is before
    assert client.post("/predict", json={"features": [0.0]*77}).status_code == 200


def test_reload_rejects_incompatible_scaler(client, tmp_path, monkeypatch):
    import pickle
    import shutil
    for filename in Path(api.MODEL_PATH).glob("*.pkl"):
        shutil.copy(filename, tmp_path / filename.name)
    broken_scaler = pickle.loads(pickle.dumps(api.scaler))
    broken_scaler.n_features_in_ = 78
    (tmp_path / "scaler.pkl").write_bytes(pickle.dumps(broken_scaler))
    before = api.models
    monkeypatch.setattr(api, "MODEL_PATH", tmp_path)
    assert client.post("/models/reload").status_code == 503
    assert api.models is before
