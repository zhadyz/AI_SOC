"""
ML Inference Client - Alert Triage Service
AI-Augmented SOC

Handles communication with the ML Inference API for network intrusion detection.
Extracts CICIDS2017 features from network flow data and provides honest confidence
reporting when full flow data is not available.

Author: HOLLOWED_EYES + MENDICANT_BIAS (Opus 4.6 completion)
"""

import logging
import math
import httpx
from services.common.api_security import service_client
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# All 77 CICIDS2017 features in training order.
# Models were trained on these exact features from the CICIDS2017 Improved dataset.
CICIDS2017_FEATURES = [
    "Protocol",
    "Flow Duration",
    "Total Fwd Packet",
    "Total Bwd packets",
    "Total Length of Fwd Packet",
    "Total Length of Bwd Packet",
    "Fwd Packet Length Max",
    "Fwd Packet Length Min",
    "Fwd Packet Length Mean",
    "Fwd Packet Length Std",
    "Bwd Packet Length Max",
    "Bwd Packet Length Min",
    "Bwd Packet Length Mean",
    "Bwd Packet Length Std",
    "Flow Bytes/s",
    "Flow Packets/s",
    "Flow IAT Mean",
    "Flow IAT Std",
    "Flow IAT Max",
    "Flow IAT Min",
    "Fwd IAT Total",
    "Fwd IAT Mean",
    "Fwd IAT Std",
    "Fwd IAT Max",
    "Fwd IAT Min",
    "Bwd IAT Total",
    "Bwd IAT Mean",
    "Bwd IAT Std",
    "Bwd IAT Max",
    "Bwd IAT Min",
    "Fwd PSH Flags",
    "Bwd PSH Flags",
    "Fwd URG Flags",
    "Bwd URG Flags",
    "Fwd Header Length",
    "Bwd Header Length",
    "Fwd Packets/s",
    "Bwd Packets/s",
    "Packet Length Min",
    "Packet Length Max",
    "Packet Length Mean",
    "Packet Length Std",
    "Packet Length Variance",
    "FIN Flag Count",
    "SYN Flag Count",
    "RST Flag Count",
    "PSH Flag Count",
    "ACK Flag Count",
    "URG Flag Count",
    "CWR Flag Count",
    "ECE Flag Count",
    "Down/Up Ratio",
    "Average Packet Size",
    "Fwd Segment Size Avg",
    "Bwd Segment Size Avg",
    "Fwd Bytes/Bulk Avg",
    "Fwd Packet/Bulk Avg",
    "Fwd Bulk Rate Avg",
    "Bwd Bytes/Bulk Avg",
    "Bwd Packet/Bulk Avg",
    "Bwd Bulk Rate Avg",
    "Subflow Fwd Packets",
    "Subflow Fwd Bytes",
    "Subflow Bwd Packets",
    "Subflow Bwd Bytes",
    "FWD Init Win Bytes",
    "Bwd Init Win Bytes",
    "Fwd Act Data Pkts",
    "Fwd Seg Size Min",
    "Active Mean",
    "Active Std",
    "Active Max",
    "Active Min",
    "Idle Mean",
    "Idle Std",
    "Idle Max",
    "Idle Min",
]

# Normalized feature name lookup for flexible key matching
_FEATURE_INDEX = {}
for _i, _name in enumerate(CICIDS2017_FEATURES):
    _FEATURE_INDEX[_name] = _i
    _FEATURE_INDEX[_name.lower()] = _i
    _FEATURE_INDEX[_name.lower().replace(" ", "_")] = _i
    _FEATURE_INDEX[_name.lower().replace(" ", "_").replace("/", "_per_")] = _i
from services.common.flow_schema import CICIDS_COLUMN_ALIASES
for _alias, _canonical in CICIDS_COLUMN_ALIASES.items():
    _FEATURE_INDEX[_alias.lower()] = CICIDS2017_FEATURES.index(_canonical)


class MLPrediction(BaseModel):
    """ML prediction response"""

    prediction: str
    confidence: float
    probabilities: Dict[str, float]
    model_used: str
    inference_time_ms: float
    feature_source: str = "unknown"
    features_populated: int = 0


class MLInferenceClient:
    """
    Client for ML inference API integration.

    Features:
    - Full CICIDS2017 feature extraction from network flow data
    - Honest confidence reporting based on data completeness
    - ML model prediction with fallback logic
    - Attack type classification
    """

    def __init__(
        self,
        ml_api_url: str = "http://ml-inference:8001",
        timeout: int = 10,
        enabled: bool = True,
    ):
        self.ml_api_url = ml_api_url
        self.timeout = timeout
        self.enabled = enabled
        logger.info(f"MLInferenceClient initialized: {ml_api_url}, enabled={enabled}")

    async def check_health(self) -> bool:
        """Check if ML inference API is reachable."""
        if not self.enabled:
            return False

        try:
            async with service_client(timeout=5.0) as client:
                response = await client.get(f"{self.ml_api_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"ML API health check failed: {e}")
            return False

    def _extract_network_features(self, alert: Any) -> Optional[Dict[str, Any]]:
        """Require all actual training features; alert metadata is not flow data."""
        log = getattr(alert, "full_log", None)
        if not isinstance(log, dict):
            return None
        flow = log.get("network_flow", log)
        if not isinstance(flow, dict):
            return None
        features = [None] * 77
        for key, value in flow.items():
            if not isinstance(key, str):
                continue
            key = key.strip()
            index = _FEATURE_INDEX.get(key)
            if index is None:
                index = _FEATURE_INDEX.get(key.lower())
            if index is not None:
                try:
                    measured = float(value)
                    if features[index] is not None and features[index] != measured:
                        return None  # Conflicting aliases are ambiguous evidence.
                    features[index] = measured
                except (TypeError, ValueError):
                    return None
        if any(value is None or not math.isfinite(value) for value in features):
            return None
        return {"features": features, "source": "network_flow", "populated": 77}

    async def predict_attack_type(
        self, alert: Any, model_name: str = "random_forest"
    ) -> Optional[MLPrediction]:
        """
        Predict attack type using ML inference API.

        Returns prediction with honest confidence based on data quality.
        Incomplete flows return no prediction; no measurements are fabricated.
        """
        if not self.enabled:
            logger.debug("ML predictions disabled")
            return None

        extraction = self._extract_network_features(alert)
        if extraction is None:
            logger.debug("Cannot extract features - skipping ML prediction")
            return None

        features = extraction["features"]
        source = extraction["source"]
        populated = extraction["populated"]

        try:
            async with service_client(timeout=self.timeout) as client:
                payload = {"features": features, "model_name": model_name}

                logger.debug(
                    f"Calling ML API: model={model_name}, "
                    f"source={source}, features_populated={populated}/77"
                )
                response = await client.post(f"{self.ml_api_url}/predict", json=payload)

                if response.status_code == 200:
                    result = response.json()
                    raw_confidence = result["confidence"]

                    adjusted_confidence = raw_confidence

                    prediction = MLPrediction(
                        prediction=result["prediction"],
                        confidence=round(adjusted_confidence, 4),
                        probabilities=result["probabilities"],
                        model_used=result["model_used"],
                        inference_time_ms=result["inference_time_ms"],
                        feature_source=source,
                        features_populated=populated,
                    )
                    logger.info(
                        f"ML prediction: {prediction.prediction} "
                        f"(confidence={prediction.confidence:.2f}, "
                        f"source={source}, features={populated}/77)"
                    )
                    return prediction
                else:
                    logger.error(
                        f"ML API error: {response.status_code} - {response.text}"
                    )
                    return None

        except httpx.TimeoutException:
            logger.warning(f"ML API timeout after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"ML API request failed: {e}")
            return None

    async def predict_with_fallback(self, alert: Any) -> Optional[MLPrediction]:
        """
        Predict with automatic model fallback.

        Tries models in order: random_forest -> xgboost -> decision_tree
        """
        models = ["random_forest", "xgboost", "decision_tree"]

        for model in models:
            prediction = await self.predict_attack_type(alert, model)
            if prediction:
                return prediction
            logger.debug(f"Model {model} failed, trying next...")

        logger.warning("All ML models failed")
        return None


def enrich_llm_prompt_with_ml(
    base_prompt: str, ml_prediction: Optional[MLPrediction]
) -> str:
    """
    Enhance LLM prompt with ML prediction context.

    Provides the LLM with ML model output and data quality context
    so it can weigh the prediction appropriately.
    """
    if ml_prediction is None:
        return base_prompt

    # Confidence qualifier based on feature source
    if ml_prediction.feature_source == "network_flow":
        quality_note = (
            f"Based on {ml_prediction.features_populated}/77 real network flow features. "
            "This is a high-quality prediction from actual traffic data."
        )
    elif ml_prediction.feature_source == "alert_metadata":
        quality_note = (
            f"Based on {ml_prediction.features_populated}/77 features derived from alert metadata. "
            "This is a LOW-CONFIDENCE prediction — treat as supplementary context only. "
            "The ML model was trained on network flow data, not alert metadata."
        )
    else:
        quality_note = "Feature source unknown — treat prediction with caution."

    ml_context = f"""
**ML MODEL PREDICTION:**
- Prediction: {ml_prediction.prediction}
- Confidence: {ml_prediction.confidence:.2%}
- Model: {ml_prediction.model_used}
- Inference Time: {ml_prediction.inference_time_ms:.2f}ms
- Data Source: {ml_prediction.feature_source} ({ml_prediction.features_populated}/77 features)

**Data Quality:** {quality_note}

**Attack Type Probabilities:**
{chr(10).join(f"  - {attack}: {prob:.2%}" for attack, prob in ml_prediction.probabilities.items())}

---

"""

    return ml_context + base_prompt
