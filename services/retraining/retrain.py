"""Train candidates from independently reviewed, complete flow records.

Exploratory training never replaces serving artifacts. Promotion additionally
requires an independent labeled holdout CSV and an explicit --promote flag.
"""

import argparse
import hashlib
import json
import logging
import os
import pickle
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

logger = logging.getLogger("retraining")
MODEL_DIR = Path(
    os.getenv("MODEL_DIR", str(Path(__file__).resolve().parents[2] / "models"))
)
DATABASE_URL = os.getenv(
    "FEEDBACK_DATABASE_URL", "postgresql://ai_soc:ai_soc_password@localhost:5435/ai_soc"
)
ML_INFERENCE_URL = os.getenv("ML_INFERENCE_URL", "http://localhost:8500")
RETRAIN_THRESHOLD = int(os.getenv("RETRAIN_THRESHOLD", "100"))
MIN_IMPROVEMENT = float(os.getenv("MIN_IMPROVEMENT", "0.005"))
MODEL_NAMES = ("random_forest", "xgboost", "decision_tree")


def active_directory():
    pointer = MODEL_DIR / "active.json"
    directory = MODEL_DIR
    if pointer.exists():
        directory = (MODEL_DIR / json.loads(pointer.read_text())["bundle"]).resolve()
        if not directory.is_relative_to(MODEL_DIR.resolve()):
            raise ValueError("Invalid model bundle pointer")
    return directory


def load_feature_names():
    with (active_directory() / "feature_names.pkl").open("rb") as stream:
        return list(pickle.load(stream))


def load_current_models():
    return {
        name: pickle.loads((active_directory() / f"{name}_ids.pkl").read_bytes())
        for name in MODEL_NAMES
    }


def load_feedback_data():
    import psycopg2

    query = """
        WITH reviewed AS (
            SELECT f.*, r.approved AS review_approved, r.reviewer_id
            FROM feedback f JOIN feedback_reviews r ON r.feedback_id = f.id
            WHERE r.approved AND r.reviewer_id <> f.analyst_id
              AND f.true_label IN ('BENIGN', 'ATTACK')
        ), unambiguous AS (
            SELECT alert_id FROM reviewed GROUP BY alert_id HAVING count(DISTINCT true_label) = 1
        )
        SELECT DISTINCT ON (a.alert_id) a.alert_id, a.raw_alert_json,
            f.true_label, f.is_false_positive, f.analyst_id, f.review_approved, f.reviewer_id
        FROM alerts a JOIN reviewed f ON f.alert_id = a.alert_id
        JOIN unambiguous u ON u.alert_id = a.alert_id
        ORDER BY a.alert_id, f.created_at DESC
    """
    with psycopg2.connect(DATABASE_URL.replace("+asyncpg", "")) as connection:
        return pd.read_sql_query(query, connection)


def extract_features_from_feedback(frame):
    names = load_feature_names()
    samples, ambiguous = {}, set()
    if len(names) != 77:
        raise ValueError("Incompatible feature contract")
    for _, row in frame.iterrows():
        if (
            row.get("review_approved") != True
            or not row.get("reviewer_id")
            or row.get("reviewer_id") == row.get("analyst_id")
        ):
            continue
        label = row.get("true_label")
        if label not in {"BENIGN", "ATTACK"} or (
            row.get("is_false_positive") and label == "ATTACK"
        ):
            continue
        raw = row.get("raw_alert_json")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                continue
        if not isinstance(raw, dict):
            continue
        log = raw.get("full_log", {})
        flow = log.get("network_flow", log) if isinstance(log, dict) else {}
        if not isinstance(flow, dict) or not set(names).issubset(flow):
            continue
        try:
            values = np.asarray([flow[name] for name in names], dtype=float)
        except (ValueError, TypeError):
            continue
        if not np.isfinite(values).all():
            continue
        fingerprint = hashlib.sha256(values.tobytes()).hexdigest()
        if fingerprint in samples and samples[fingerprint][1] != label:
            ambiguous.add(fingerprint)
        samples[fingerprint] = (values, label)
    accepted = [sample for key, sample in samples.items() if key not in ambiguous]
    features = [sample[0] for sample in accepted]
    labels = [sample[1] for sample in accepted]
    return np.asarray(features, dtype=float).reshape(-1, 77), np.asarray(labels)


def train_models(
    X_train: np.ndarray,
    y_train: np.ndarray,
    scaler: StandardScaler,
    label_encoder: LabelEncoder,
) -> Dict:
    """Train new candidate models."""
    logger.info("Training candidate models...")

    X_scaled = scaler.transform(X_train)
    y_encoded = label_encoder.transform(y_train)

    models = {}

    # Random Forest
    logger.info("Training Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        n_jobs=-1,
        random_state=42,
    )
    rf.fit(X_scaled, y_encoded)
    models["random_forest"] = rf

    # Decision Tree
    logger.info("Training Decision Tree...")
    dt = DecisionTreeClassifier(
        max_depth=20,
        class_weight="balanced",
        random_state=42,
    )
    dt.fit(X_scaled, y_encoded)
    models["decision_tree"] = dt

    # XGBoost (optional, may not be installed)
    try:
        from xgboost import XGBClassifier

        logger.info("Training XGBoost...")
        unique, counts = np.unique(y_encoded, return_counts=True)
        if len(unique) > 1:
            scale_pos = counts[0] / counts[1] if counts[1] > 0 else 1.0
        else:
            scale_pos = 1.0

        xgb = XGBClassifier(
            max_depth=10,
            scale_pos_weight=scale_pos,
            objective="binary:logistic",
            eval_metric="logloss",
            use_label_encoder=False,
            random_state=42,
        )
        xgb.fit(X_scaled, y_encoded)
        models["xgboost"] = xgb
    except ImportError:
        logger.warning("XGBoost not available, skipping")

    return models


def evaluate_models(
    models: Dict,
    X_test: np.ndarray,
    y_test: np.ndarray,
    scaler: StandardScaler,
    label_encoder: LabelEncoder,
) -> Dict[str, Dict]:
    """Evaluate models on test set."""
    X_scaled = scaler.transform(X_test)
    y_encoded = label_encoder.transform(y_test)

    results = {}
    for name, model in models.items():
        y_pred = model.predict(X_scaled)
        results[name] = {
            "accuracy": accuracy_score(y_encoded, y_pred),
            "precision": precision_score(
                y_encoded, y_pred, average="weighted", zero_division=0
            ),
            "recall": recall_score(
                y_encoded, y_pred, average="weighted", zero_division=0
            ),
            "f1": f1_score(y_encoded, y_pred, average="weighted", zero_division=0),
        }
        logger.info(
            f"  {name}: accuracy={results[name]['accuracy']:.4f}, "
            f"f1={results[name]['f1']:.4f}"
        )

    return results


def champion_challenger(current_results, candidate_results):
    decisions = {}
    for name, candidate in candidate_results.items():
        current = current_results[name]
        improved = (
            candidate["accuracy"] - current["accuracy"] >= MIN_IMPROVEMENT
            and candidate["f1"] >= current["f1"]
            and candidate["recall"] >= current["recall"]
        )
        decisions[name] = "promote" if improved else "keep"
    return decisions


def save_models(models, scaler, label_encoder, *, activate=False, metadata=None):
    """Write a complete immutable bundle; publish its pointer only when requested."""
    if set(models) != set(MODEL_NAMES):
        raise ValueError("Promotion requires a complete model bundle")
    names = load_feature_names()
    if scaler.n_features_in_ != len(names):
        raise ValueError("Scaler and feature contract disagree")
    probe = scaler.transform(np.asarray(scaler.mean_).reshape(1, -1))
    for name, model in models.items():
        if model.n_features_in_ != len(names) or not np.array_equal(
            model.classes_, np.arange(len(label_encoder.classes_))
        ):
            raise ValueError(f"Incompatible candidate: {name}")
        if not np.isfinite(model.predict_proba(probe)).all():
            raise ValueError(f"Invalid candidate output: {name}")
    directory = MODEL_DIR / "bundles" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    objects = {f"{name}_ids": model for name, model in models.items()}
    objects.update(scaler=scaler, label_encoder=label_encoder, feature_names=names)
    for name, obj in objects.items():
        with (directory / f"{name}.pkl").open("wb") as stream:
            pickle.dump(obj, stream)
            stream.flush()
            os.fsync(stream.fileno())
    (directory / "evaluation.json").write_text(json.dumps(metadata or {}, indent=2))
    if activate:
        pointer = {"bundle": str(directory.relative_to(MODEL_DIR))}
        temporary = MODEL_DIR / f".active-{uuid.uuid4().hex}.json"
        with temporary.open("w") as stream:
            json.dump(pointer, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, MODEL_DIR / "active.json")
    return directory


def trigger_reload():
    import requests

    key = os.getenv("AI_SOC_API_KEY", "")
    response = requests.post(
        f"{ML_INFERENCE_URL}/models/reload",
        timeout=30,
        headers={"Authorization": f"Bearer {key}"} if key else {},
    )
    response.raise_for_status()


def load_holdout(path, training_features):
    frame = pd.read_csv(path)
    names = load_feature_names()
    if not set(names + ["Label"]).issubset(frame.columns):
        raise ValueError("Holdout needs all 77 named features and a Label column")
    values = frame[names].to_numpy(dtype=float)
    labels = frame["Label"].to_numpy()
    if (
        not len(values)
        or not np.isfinite(values).all()
        or set(labels) != {"BENIGN", "ATTACK"}
    ):
        raise ValueError("Holdout must be finite and contain both binary classes")
    training_hashes = {
        hashlib.sha256(row.tobytes()).digest() for row in training_features
    }
    if any(hashlib.sha256(row.tobytes()).digest() in training_hashes for row in values):
        raise ValueError("Holdout overlaps training data")
    return values, labels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow exploratory training below the usual sample threshold",
    )
    parser.add_argument("--evaluate-only", action="store_true")
    parser.add_argument(
        "--holdout", type=Path, help="Independent 77-feature + Label CSV"
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Explicitly activate winners evaluated on --holdout",
    )
    args = parser.parse_args()
    if args.promote and not args.holdout:
        parser.error("--promote requires an independent --holdout CSV")
    frame = load_feedback_data()
    X, y = extract_features_from_feedback(frame)
    if len(X) < RETRAIN_THRESHOLD and not args.force:
        logger.info(
            "Only %d eligible complete reviewed flows; need %d",
            len(X),
            RETRAIN_THRESHOLD,
        )
        return
    _, counts = np.unique(y, return_counts=True)
    if len(counts) != 2 or min(counts) < 5:
        raise ValueError(
            "At least five reviewed, unique flow samples per class are required"
        )
    directory = active_directory()
    scaler = pickle.loads((directory / "scaler.pkl").read_bytes())
    encoder = pickle.loads((directory / "label_encoder.pkl").read_bytes())
    # Freeze serving preprocessing so all candidate/champion comparisons use the
    # exact same representation. Never refit a scaler underneath old models.
    if args.holdout:
        X_train, y_train = X, y
        X_test, y_test = load_holdout(args.holdout, X_train)
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, stratify=y, test_size=0.2, random_state=42
        )
    current = load_current_models()
    baseline = evaluate_models(current, X_test, y_test, scaler, encoder)
    if args.evaluate_only:
        print(json.dumps(baseline, indent=2))
        return
    candidates = train_models(X_train, y_train, scaler, encoder)
    candidate_scores = evaluate_models(candidates, X_test, y_test, scaler, encoder)
    decisions = champion_challenger(baseline, candidate_scores)
    selected = {
        name: candidates[name] if decisions.get(name) == "promote" else current[name]
        for name in MODEL_NAMES
    }
    metadata = {
        "baseline": baseline,
        "candidate": candidate_scores,
        "decisions": decisions,
        "training_samples": len(X_train),
        "holdout_samples": len(X_test),
        "independent_holdout": str(args.holdout) if args.holdout else None,
    }
    activate = args.promote and "promote" in decisions.values()
    bundle = save_models(
        selected, scaler, encoder, activate=activate, metadata=metadata
    )
    logger.info("Saved %s; activated=%s", bundle, activate)
    if activate:
        trigger_reload()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
