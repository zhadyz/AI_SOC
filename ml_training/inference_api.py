"""
CICIDS2017 IDS - Real-Time Inference API

FastAPI endpoint for real-time network intrusion detection using trained ML models.
Provides prediction endpoint with confidence scores and model selection.

Integration: Alert-Triage Service Architecture
Endpoint: POST /predict
Target Latency: <100ms per prediction

Author: HOLLOWED_EYES
Mission: OPERATION ML-BASELINE
Date: 2025-10-13
"""

import os
import pickle
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Constants
# Support both local and Docker paths
MODEL_PATH_ENV = os.getenv("MODEL_PATH", "/app/models")
MODEL_PATH = Path(MODEL_PATH_ENV)

# Initialize FastAPI
app = FastAPI(
    title="CICIDS2017 Intrusion Detection API",
    description="Real-time network intrusion detection using ML models",
    version="1.0.0"
)

# Global model storage
models = {}
scaler = None
label_encoder = None
feature_names = None


class NetworkFlow(BaseModel):
    """Network flow features for prediction"""
    features: List[float] = Field(
        ...,
        description="List of 78 network flow features (after dropping non-predictive columns)",
        min_items=78,
        max_items=78
    )
    model_name: Optional[str] = Field(
        default="random_forest",
        description="Model to use for prediction: random_forest, xgboost, or decision_tree"
    )

    class Config:
        schema_extra = {
            "example": {
                "features": [0.0] * 78,  # Example placeholder
                "model_name": "random_forest"
            }
        }


class NetworkFlowDict(BaseModel):
    """Network flow features as dictionary (feature_name: value)"""
    flow_duration: float = 0.0
    total_fwd_packet: float = 0.0
    total_bwd_packets: float = 0.0
    # Add more fields as needed - this is a simplified example
    model_name: Optional[str] = "random_forest"


class PredictionResponse(BaseModel):
    """Prediction response with confidence and metadata"""
    prediction: str = Field(..., description="Predicted class: BENIGN or ATTACK")
    confidence: float = Field(..., description="Confidence score (0-1)")
    probabilities: Dict[str, float] = Field(..., description="Class probabilities")
    model_used: str = Field(..., description="Model used for prediction")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")
    timestamp: str = Field(..., description="Prediction timestamp")


def load_models():
    """Load all trained models and preprocessing objects"""
    global models, scaler, label_encoder, feature_names

    print("Loading models and artifacts...")

    artifacts = {
        'random_forest': MODEL_PATH / 'random_forest_ids.pkl',
        'xgboost': MODEL_PATH / 'xgboost_ids.pkl',
        'decision_tree': MODEL_PATH / 'decision_tree_ids.pkl',
        'scaler': MODEL_PATH / 'scaler.pkl',
        'label_encoder': MODEL_PATH / 'label_encoder.pkl',
        'feature_names': MODEL_PATH / 'feature_names.pkl'
    }

    for name, path in artifacts.items():
        if not path.exists():
            print(f"WARNING: {name} not found at {path}")
            continue

        try:
            with open(path, 'rb') as f:
                obj = pickle.load(f)

            if name in ['random_forest', 'xgboost', 'decision_tree']:
                models[name] = obj
                print(f"  Loaded model: {name}")
            elif name == 'scaler':
                scaler = obj
                print(f"  Loaded scaler")
            elif name == 'label_encoder':
                label_encoder = obj
                print(f"  Loaded label encoder: {label_encoder.classes_}")
            elif name == 'feature_names':
                feature_names = obj
                print(f"  Loaded feature names: {len(obj)} features")

        except Exception as e:
            print(f"ERROR loading {name}: {e}")

    if not models:
        raise RuntimeError("No models loaded successfully")

    print(f"Models loaded: {list(models.keys())}")
    return True


@app.on_event("startup")
async def startup_event():
    """Load models on startup"""
    load_models()


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": "CICIDS2017 Intrusion Detection API",
        "version": "1.0.0",
        "status": "operational",
        "models_loaded": list(models.keys()),
        "endpoints": {
            "predict": "/predict",
            "health": "/health",
            "models": "/models"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "models_loaded": len(models),
        "available_models": list(models.keys())
    }


@app.get("/models")
async def list_models():
    """List available models and their info"""
    model_info = {}

    for name, model in models.items():
        try:
            model_bytes = len(pickle.dumps(model))
            size_mb = model_bytes / (1024 * 1024)
        except:
            size_mb = None

        model_info[name] = {
            "name": name,
            "type": type(model).__name__,
            "size_mb": round(size_mb, 2) if size_mb else "unknown",
            "loaded": True
        }

    return {
        "total_models": len(models),
        "models": model_info,
        "feature_count": len(feature_names) if feature_names else "unknown",
        "label_classes": label_encoder.classes_.tolist() if label_encoder else []
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict(flow: NetworkFlow):
    """
    Predict intrusion detection for a network flow

    Args:
        flow: NetworkFlow object with 78 features and optional model selection

    Returns:
        PredictionResponse with prediction, confidence, and metadata
    """
    from datetime import datetime

    start_time = time.time()

    # Validate model selection
    model_name = flow.model_name.lower()
    if model_name not in models:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_name}' not available. Choose from: {list(models.keys())}"
        )

    # Validate feature count
    if len(flow.features) != len(feature_names):
        raise HTTPException(
            status_code=400,
            detail=f"Expected {len(feature_names)} features, got {len(flow.features)}"
        )

    try:
        # Prepare features
        X = np.array(flow.features).reshape(1, -1)

        # Scale features
        if scaler:
            X_scaled = scaler.transform(X)
        else:
            X_scaled = X

        # Get model
        model = models[model_name]

        # Make prediction
        y_pred = model.predict(X_scaled)[0]
        y_pred_proba = model.predict_proba(X_scaled)[0]

        # Decode prediction
        predicted_class = label_encoder.inverse_transform([y_pred])[0]
        confidence = float(np.max(y_pred_proba))

        # Build probability dictionary
        probabilities = {
            label_encoder.classes_[i]: float(y_pred_proba[i])
            for i in range(len(label_encoder.classes_))
        }

        inference_time_ms = (time.time() - start_time) * 1000

        return PredictionResponse(
            prediction=predicted_class,
            confidence=confidence,
            probabilities=probabilities,
            model_used=model_name,
            inference_time_ms=round(inference_time_ms, 4),
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction error: {str(e)}"
        )


@app.post("/predict/batch")
async def predict_batch(flows: List[NetworkFlow]):
    """
    Batch prediction for multiple network flows

    Args:
        flows: List of NetworkFlow objects

    Returns:
        List of PredictionResponse objects
    """
    from datetime import datetime

    if len(flows) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Batch size limited to 1000 flows"
        )

    start_time = time.time()
    results = []

    for i, flow in enumerate(flows):
        try:
            # Use the single prediction endpoint
            result = await predict(flow)
            results.append(result.dict())
        except Exception as e:
            results.append({
                "error": str(e),
                "flow_index": i
            })

    total_time_ms = (time.time() - start_time) * 1000
    avg_time_ms = total_time_ms / len(flows)

    return {
        "total_predictions": len(results),
        "total_time_ms": round(total_time_ms, 2),
        "avg_time_per_prediction_ms": round(avg_time_ms, 4),
        "results": results
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": str(request.url)
        }
    )


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server"""
    print(f"\nStarting CICIDS2017 IDS Inference API...")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Docs: http://{host}:{port}/docs")
    print(f"Redoc: http://{host}:{port}/redoc")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
