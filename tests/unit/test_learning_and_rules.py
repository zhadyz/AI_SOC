"""Regression tests for data eligibility, rule matching and durable review state."""

import importlib
import pickle

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from services.feedback_service.models import FeedbackSubmission
from services.rule_generator.sigma import backtest, parse_rule
from services.rule_generator.store import RuleStore

retrain = importlib.import_module("services.retraining.retrain")
RULE = """title: Test failed logon
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 4625
    TargetUserName|startswith: admin
  filter:
    IpAddress: 127.0.0.1
  condition: selection and not filter
"""


def test_sigma_backtest_measures_false_positives_against_benign_events():
    events = [
        {
            "event": {
                "EventID": 4625,
                "TargetUserName": "admin",
                "IpAddress": "203.0.113.4",
            },
            "label": "ATTACK",
        },
        {
            "event": {
                "EventID": 4625,
                "TargetUserName": "administrator",
                "IpAddress": "203.0.113.5",
            },
            "label": "BENIGN",
        },
        {
            "event": {
                "EventID": 4625,
                "TargetUserName": "admin",
                "IpAddress": "127.0.0.1",
            },
            "label": "BENIGN",
        },
    ]
    result = backtest(RULE, events)
    assert result["matches"] == 2
    assert result["false_positives"] == 1
    assert result["false_positive_rate"] == 0.5
    assert (
        backtest(RULE, [{"event": {}, "label": "ATTACK"}])["false_positive_rate"]
        is None
    )


@pytest.mark.parametrize(
    "replacement",
    [
        "selection | count() > 3",
        "unknown",
        "selection and",
        "(selection",
        "all of absent*",
    ],
)
def test_unsupported_sigma_is_rejected(replacement):
    with pytest.raises(ValueError):
        parse_rule(RULE.replace("selection and not filter", replacement))


def test_unknown_sigma_modifier_is_not_silently_approximated():
    with pytest.raises(ValueError, match="Unsupported"):
        parse_rule(RULE.replace("startswith", "re"))


def test_rule_review_survives_restart(tmp_path):
    path = tmp_path / "rules.sqlite"
    store = RuleStore(path)
    store["r1"] = {"rule_text": RULE, "status": "pending"}
    updated = store["r1"]
    updated.update(status="approved", reviewed_by="analyst")
    store["r1"] = updated
    assert RuleStore(path)["r1"]["reviewed_by"] == "analyst"


def test_feedback_rejects_conflicting_binary_label():
    with pytest.raises(ValidationError):
        FeedbackSubmission(analyst_id="a", is_false_positive=True, true_label="ATTACK")
    with pytest.raises(ValidationError):
        FeedbackSubmission(analyst_id="a", true_label="arbitrary poison label")


def test_only_reviewed_complete_finite_flow_data_is_trainable(monkeypatch):
    names = [f"f{i}" for i in range(77)]
    monkeypatch.setattr(retrain, "load_feature_names", lambda: names)
    valid = {
        "review_approved": True,
        "analyst_id": "a",
        "reviewer_id": "b",
        "true_label": "ATTACK",
        "raw_alert_json": {"full_log": {"network_flow": dict.fromkeys(names, 1.0)}},
    }
    incomplete = {**valid, "raw_alert_json": {"rule_level": 12, "dest_port": 443}}
    unreviewed = {**valid, "review_approved": False}
    self_review = {**valid, "reviewer_id": "a"}
    nonfinite = {
        **valid,
        "raw_alert_json": {
            "full_log": {"network_flow": dict.fromkeys(names, float("inf"))}
        },
    }
    X, y = retrain.extract_features_from_feedback(
        pd.DataFrame([valid, incomplete, unreviewed, self_review, nonfinite])
    )
    assert X.shape == (1, 77)
    assert list(y) == ["ATTACK"]


def test_partial_model_promotion_is_rejected():
    with pytest.raises(ValueError, match="complete model bundle"):
        retrain.save_models({"random_forest": object()}, None, None, activate=True)


def test_conflicting_labels_for_identical_flows_are_excluded(monkeypatch):
    names = [f"f{i}" for i in range(77)]
    monkeypatch.setattr(retrain, "load_feature_names", lambda: names)
    row = {
        "review_approved": True,
        "analyst_id": "a",
        "reviewer_id": "b",
        "raw_alert_json": {"full_log": {"network_flow": dict.fromkeys(names, 1)}},
    }
    X, y = retrain.extract_features_from_feedback(
        pd.DataFrame([{**row, "true_label": "ATTACK"}, {**row, "true_label": "BENIGN"}])
    )
    assert X.shape == (0, 77) and len(y) == 0


def test_holdout_overlap_is_rejected(tmp_path, monkeypatch):
    names = [f"f{i}" for i in range(77)]
    monkeypatch.setattr(retrain, "load_feature_names", lambda: names)
    path = tmp_path / "holdout.csv"
    frame = pd.DataFrame([dict.fromkeys(names, 1.0), dict.fromkeys(names, 2.0)])
    frame["Label"] = ["BENIGN", "ATTACK"]
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="overlaps"):
        retrain.load_holdout(path, np.ones((1, 77)))
