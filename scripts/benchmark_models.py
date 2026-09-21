#!/usr/bin/env python3
"""Train/evaluate fresh multiclass IDS models on a reproducible CICIDS2017 sample.

The input archive is a checksum-pinned public mirror of the published dataset.
Duplicate feature vectors and conflicting labels are removed before splitting.
The holdout measures this dataset only, not deployment generalization.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import pickle
import sqlite3
import sys
import tempfile
import time
import zipfile

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from services.common.model_integrity import verified_bytes, write_manifest
from services.common.flow_schema import CICIDS_COLUMN_ALIASES

ARCHIVE_SHA256 = "7bdbef286f8893f31c6db12105fa097fa5c2dcc6733179037a08129d150ea27a"
SOURCE = "https://huggingface.co/datasets/bencorn/CICIDS2017/blob/main/csvs/GeneratedLabelledFlows.zip"


def prepare(archive, names, max_per_class):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Dataset archive checksum mismatch")
    counts, reservoirs, labels = Counter(), {}, {}
    invalid = 0
    with tempfile.TemporaryDirectory() as scratch, sqlite3.connect(Path(scratch) / "seen.sqlite") as seen, zipfile.ZipFile(archive) as z:
        seen.execute("CREATE TABLE hashes (h BLOB PRIMARY KEY, labels INTEGER NOT NULL) WITHOUT ROWID")
        for filename in sorted(z.namelist()):
            if not filename.endswith(".csv"):
                continue
            with z.open(filename) as stream:
                for frame in pd.read_csv(stream, chunksize=50000, encoding="cp1252", low_memory=False):
                    frame.columns = frame.columns.str.strip()
                    frame = frame.rename(columns=CICIDS_COLUMN_ALIASES)
                    if set(names) - set(frame.columns):
                        raise ValueError("Dataset lacks the serving feature contract")
                    frame = frame[names + ["Label"]].copy()
                    frame["Label"] = frame["Label"].astype(str).str.strip()
                    values = frame[names].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float64)
                    finite = np.isfinite(values).all(axis=1)
                    invalid += int((~finite).sum())
                    frame = pd.DataFrame(values[finite], columns=names).assign(Label=frame.loc[finite, "Label"].to_numpy())
                    frame["hash"] = pd.util.hash_pandas_object(frame[names], index=False).to_numpy()
                    for label, group in frame.groupby("Label"):
                        counts[label] += len(group)
                        labels.setdefault(label, len(labels))
                        mask = 1 << labels[label]
                        unique = group.drop_duplicates("hash")
                        seen.executemany("INSERT INTO hashes VALUES (?,?) ON CONFLICT(h) DO UPDATE SET labels=hashes.labels | excluded.labels",
                                         ((int(h).to_bytes(8, "big"), mask) for h in unique["hash"]))
                        reservoirs[label] = pd.concat([reservoirs.get(label, pd.DataFrame()), unique]).drop_duplicates("hash").nsmallest(max_per_class, "hash")
            seen.commit()
            print(f"Read {Path(filename).name}: {sum(counts.values())} finite flows so far", flush=True)
        sample = pd.concat(reservoirs.values(), ignore_index=True)
        clean = []
        for h in sample["hash"]:
            mask = seen.execute("SELECT labels FROM hashes WHERE h=?", (int(h).to_bytes(8, "big"),)).fetchone()[0]
            clean.append(mask.bit_count() == 1)
        conflicts = int((~np.asarray(clean)).sum())
        sample = sample.loc[clean].drop_duplicates("hash")
    # Fixed independent holdout within every supported class. Sorting by a
    # second hash prevents selecting contiguous flow sequences from the CSV.
    train, test, excluded = [], [], {}
    for label, group in sample.groupby("Label"):
        if len(group) < 2:
            excluded[label] = "Fewer than two unique, unambiguous flows"
            continue
        ranked = group.assign(split_rank=[hashlib.sha256(str(int(h)).encode()).hexdigest() for h in group["hash"]]).sort_values("split_rank")
        n = max(1, int(len(ranked) * 0.2))
        test.append(ranked.iloc[:n])
        train.append(ranked.iloc[n:])
    return pd.concat(train), pd.concat(test), {"finite_source_label_counts": dict(counts), "nonfinite_rows_rejected": invalid,
        "conflicting_sample_rows_rejected": conflicts, "excluded_classes": excluded, "max_unique_flows_per_class": max_per_class}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--max-per-class", type=int, default=5000)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a fresh output directory")
    base = verified_bytes(ROOT / "models")
    names = list(pickle.loads(base["feature_names.pkl"]))
    train, test, data_report = prepare(args.archive, names, args.max_per_class)
    overlap = set(train["hash"]) & set(test["hash"])
    if overlap:
        raise ValueError("Training/holdout feature overlap")
    scaler = StandardScaler().fit(train[names].to_numpy())
    encoder = LabelEncoder().fit(train["Label"])
    X_train = scaler.transform(train[names].to_numpy()).astype(np.float32)
    X_test = scaler.transform(test[names].to_numpy()).astype(np.float32)
    y_train = encoder.transform(train["Label"])
    y_test = encoder.transform(test["Label"])
    models = {"random_forest": RandomForestClassifier(n_estimators=150, max_depth=24, min_samples_leaf=2, class_weight="balanced", n_jobs=2, random_state=42),
              "decision_tree": DecisionTreeClassifier(max_depth=24, min_samples_leaf=2, class_weight="balanced", random_state=42),
              "xgboost": XGBClassifier(n_estimators=150, max_depth=6, learning_rate=0.1, n_jobs=2, random_state=42, objective="multi:softprob", eval_metric="mlogloss")}
    scores = {}
    for name, model in models.items():
        started = time.monotonic()
        model.fit(X_train, y_train)
        prediction = model.predict(X_test)
        scores[name] = {"accuracy": float(accuracy_score(y_test, prediction)), "macro_f1": float(f1_score(y_test, prediction, average="macro")),
            "per_class": classification_report(y_test, prediction, labels=np.arange(len(encoder.classes_)), target_names=encoder.classes_, output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(y_test, prediction, labels=np.arange(len(encoder.classes_))).tolist(), "training_seconds": round(time.monotonic() - started, 2)}
        print(name, {k: scores[name][k] for k in ("accuracy", "macro_f1", "training_seconds")}, flush=True)
    args.output.mkdir(parents=True)
    objects = {f"{name}_ids": model for name, model in models.items()}
    objects.update(scaler=scaler, label_encoder=encoder, feature_names=names)
    for name, obj in objects.items():
        (args.output / f"{name}.pkl").write_bytes(pickle.dumps(obj))
    from dotenv import dotenv_values
    signing_key = os.getenv("AI_SOC_MODEL_SIGNING_KEY") or dotenv_values(ROOT / ".env").get("AI_SOC_MODEL_SIGNING_KEY")
    write_manifest(args.output, signing_key)
    train[names + ["Label"]].to_csv(args.output / "training.csv", index=False)
    test[names + ["Label"]].to_csv(args.output / "holdout.csv", index=False)
    result = {"dataset": "CICIDS2017", "original_source": "https://www.unb.ca/cic/datasets/ids-2017.html", "mirror": SOURCE,
        "archive_sha256": ARCHIVE_SHA256, "feature_count": len(names), "classes": encoder.classes_.tolist(),
        "training_samples": len(train), "holdout_samples": len(test), "feature_overlap": len(overlap), **data_report,
        "models": scores, "bundle": str(args.output), "serving_bundle_changed": False,
        "limits": ["Holdout is within CICIDS2017, not an independent deployment capture.", "Small rare-class supports are shown explicitly; these metrics do not prove operational detection quality.", "Published labels are benchmark labels, not genuine analyst feedback."]}
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    (args.output / "evaluation.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
