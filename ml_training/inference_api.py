"""Local IDS inference using a validated, atomically loaded model bundle."""

import logging
import os
import pickle
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Dict, List

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, FiniteFloat
from services.common.model_integrity import verified_bytes

logger = logging.getLogger(__name__)
MODEL_PATH = Path(os.getenv("MODEL_PATH", str(Path(__file__).resolve().parent.parent / "models")))
FEATURE_COUNT = 77
MODEL_NAMES = ("random_forest", "xgboost", "decision_tree")
models = {}
scaler = None
label_encoder = None
feature_names = None


class NetworkFlow(BaseModel):
    features: List[FiniteFloat] = Field(min_length=FEATURE_COUNT, max_length=FEATURE_COUNT)
    model_name: str = "random_forest"


class NetworkFlowDict(BaseModel):
    features: Dict[str, FiniteFloat]
    model_name: str = "random_forest"


class PredictionResponse(BaseModel):
    prediction: str
    confidence: float = Field(ge=0, le=1)
    probabilities: Dict[str, float]
    model_used: str
    inference_time_ms: float
    timestamp: str


def load_models():
    """Validate the entire bundle before replacing the last working snapshot.

    Pickle files must come from a trusted local training pipeline. Never accept
    serialized model uploads from API callers.
    """
    global models, scaler, label_encoder, feature_names
    # A promoted bundle is selected atomically by a small pointer file.
    bundle_dir = MODEL_PATH
    pointer = MODEL_PATH / "active.json"
    if pointer.exists():
        import json
        bundle_dir = (MODEL_PATH / json.loads(pointer.read_text())["bundle"]).resolve()
        if not bundle_dir.is_relative_to(MODEL_PATH.resolve()):
            raise ValueError("Model bundle must be inside MODEL_PATH")
    objects = {}
    artifacts = verified_bytes(bundle_dir, os.getenv("AI_SOC_MODEL_SIGNING_KEY"),
                               require_signature=bundle_dir.resolve() != MODEL_PATH.resolve())
    for name in (*MODEL_NAMES, "scaler", "label_encoder", "feature_names"):
        filename = f"{name}_ids.pkl" if name in MODEL_NAMES else f"{name}.pkl"
        objects[name] = pickle.loads(artifacts[filename])
    names = list(objects["feature_names"])
    if len(names) != FEATURE_COUNT or len(set(names)) != FEATURE_COUNT:
        raise ValueError(f"Bundle must contain {FEATURE_COUNT} unique feature names")
    new_scaler = objects["scaler"]
    encoder = objects["label_encoder"]
    if new_scaler.n_features_in_ != FEATURE_COUNT:
        raise ValueError("Scaler feature count differs from the API contract")
    # Smoke each model with the scaler mean (a finite, valid input), checking
    # output dimensions and encoded class order before publishing any of them.
    probe = new_scaler.transform(np.asarray(new_scaler.mean_).reshape(1, -1))
    expected_classes = np.arange(len(encoder.classes_))
    for name in MODEL_NAMES:
        model = objects[name]
        if model.n_features_in_ != FEATURE_COUNT:
            raise ValueError(f"{name}: incompatible feature count")
        if not np.array_equal(model.classes_, expected_classes):
            raise ValueError(f"{name}: incompatible class encoding")
        probabilities = model.predict_proba(probe)
        if probabilities.shape != (1, len(expected_classes)) or not np.isfinite(probabilities).all():
            raise ValueError(f"{name}: invalid prediction output")
    # This function has no await points; requests cannot see a partial update.
    models = {name: objects[name] for name in MODEL_NAMES}
    scaler, label_encoder, feature_names = new_scaler, encoder, names
    logger.info("Loaded validated model bundle: %s", bundle_dir)
    return True


@asynccontextmanager
async def lifespan(app):
    load_models()
    yield


app = FastAPI(title="CICIDS2017 Intrusion Detection API", version="1.1.0", lifespan=lifespan)


from services.common.api_security import protect_app
protect_app(app)

@app.get("/")
async def root():
    return {"service": app.title, "version": app.version, "models_loaded": list(models),
            "endpoints": {"predict": "/predict", "named_features": "/predict/named",
                          "health": "/health", "models": "/models"}}


@app.get("/health")
async def health_check():
    if len(models) != len(MODEL_NAMES) or scaler is None or label_encoder is None:
        raise HTTPException(503, "Model bundle unavailable")
    return {"status": "healthy", "models_loaded": len(models), "available_models": list(models)}


@app.get("/models")
async def list_models():
    return {"total_models": len(models),
            "models": {name: {"name": name, "type": type(model).__name__, "loaded": True}
                       for name, model in models.items()},
            "feature_count": len(feature_names or []), "feature_names": feature_names or [],
            "label_classes": label_encoder.classes_.tolist() if label_encoder is not None else []}


@app.post("/models/reload")
async def reload_models():
    try:
        load_models()
    except Exception:
        logger.exception("Rejected invalid model bundle; keeping current models")
        raise HTTPException(503, "Invalid model bundle; previous models remain active")
    return {"status": "success", "models_loaded": list(models)}


@app.post("/predict", response_model=PredictionResponse)
async def predict(flow: NetworkFlow):
    await health_check()
    start = time.perf_counter()
    name = flow.model_name.lower()
    if name not in models:
        raise HTTPException(400, f"Unknown model. Choose from: {list(models)}")
    try:
        scaled = scaler.transform(np.asarray(flow.features).reshape(1, -1))
        if not np.isfinite(scaled).all():
            raise HTTPException(422, "Feature values exceed the scaler's numeric range")
        model = models[name]
        encoded = model.predict(scaled)[0]
        probabilities = model.predict_proba(scaled)[0]
        return PredictionResponse(
            prediction=str(label_encoder.inverse_transform([encoded])[0]),
            confidence=float(np.max(probabilities)),
            probabilities={str(label_encoder.classes_[int(c)]): float(p)
                           for c, p in zip(model.classes_, probabilities)},
            model_used=name, inference_time_ms=round((time.perf_counter() - start) * 1000, 4),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Prediction failed")
        raise HTTPException(500, "Prediction failed")


@app.post("/predict/named", response_model=PredictionResponse)
async def predict_named(flow: NetworkFlowDict):
    await health_check()
    missing = set(feature_names) - flow.features.keys()
    extra = flow.features.keys() - set(feature_names)
    if missing or extra:
        raise HTTPException(422, {"missing_features": sorted(missing), "unknown_features": sorted(extra)})
    return await predict(NetworkFlow(features=[flow.features[n] for n in feature_names], model_name=flow.model_name))


@app.post("/predict/batch")
async def predict_batch(flows: Annotated[List[NetworkFlow], Field(min_length=1, max_length=1000)]):
    start = time.perf_counter()
    results = []
    for index, flow in enumerate(flows):
        try:
            results.append((await predict(flow)).model_dump())
        except HTTPException as exc:
            results.append({"error": exc.detail, "status_code": exc.status_code, "flow_index": index})
    elapsed = (time.perf_counter() - start) * 1000
    return {"total_predictions": len(results), "total_time_ms": round(elapsed, 2),
            "avg_time_per_prediction_ms": round(elapsed / len(flows), 4), "results": results}


def run_server(host="0.0.0.0", port=8000):
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
