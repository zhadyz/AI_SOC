# ML Inference API Reference

Machine Learning inference service for network intrusion detection using Random Forest classification on CICIDS2017-trained models.

---

## Service Overview

| Property | Value |
|----------|-------|
| **Base URL** | `http://ml-inference:8001` (internal), `https://api.ai-soc.example.com:8500` (external) |
| **Protocol** | HTTP/HTTPS (REST) |
| **Content Type** | `application/json` |
| **Authentication** | API Key (Bearer token) or JWT |
| **Model** | Random Forest (99.28% accuracy, 0.25% FPR) |
| **Latency** | <1ms average, p99 <2ms |
| **Throughput** | 1,250 predictions/sec (single-threaded), 8,200 predictions/sec (8 cores) |

---

## Authentication

All endpoints except `/health` and `/metrics` require authentication.

### API Key Authentication

```http
POST /predict HTTP/1.1
Host: ml-inference:8001
Authorization: Bearer aisoc_<your-api-key>
Content-Type: application/json
```

### JWT Authentication

```http
POST /predict HTTP/1.1
Host: ml-inference:8001
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

---

## Endpoints

### GET /health

Health check endpoint for monitoring and load balancer integration.

#### Request

```http
GET /health HTTP/1.1
Host: ml-inference:8001
```

#### Response

**Status**: `200 OK`

```json
{
  "status": "healthy",
  "service": "ml-inference-api",
  "version": "1.0.0",
  "model_loaded": true,
  "model_name": "random_forest_cicids2017",
  "model_version": "v1.2",
  "uptime_seconds": 3600,
  "last_prediction": "2025-10-24T10:15:30Z"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Service health status: `healthy`, `degraded`, `unhealthy` |
| `service` | string | Service identifier |
| `version` | string | API version |
| `model_loaded` | boolean | Whether ML model is loaded in memory |
| `model_name` | string | Active model identifier |
| `model_version` | string | Model training version |
| `uptime_seconds` | integer | Service uptime in seconds |
| `last_prediction` | string | ISO 8601 timestamp of last prediction |

---

### GET /metrics

Prometheus metrics endpoint for monitoring.

#### Request

```http
GET /metrics HTTP/1.1
Host: ml-inference:8001
```

#### Response

**Status**: `200 OK`
**Content-Type**: `text/plain; version=0.0.4`

```
# HELP ml_predictions_total Total number of ML predictions
# TYPE ml_predictions_total counter
ml_predictions_total{status="success"} 125043
ml_predictions_total{status="failed"} 12

# HELP ml_inference_duration_seconds ML inference latency
# TYPE ml_inference_duration_seconds histogram
ml_inference_duration_seconds_bucket{le="0.001"} 112430
ml_inference_duration_seconds_bucket{le="0.002"} 124890
ml_inference_duration_seconds_bucket{le="0.005"} 125020
ml_inference_duration_seconds_bucket{le="+Inf"} 125043
ml_inference_duration_seconds_sum 98.234
ml_inference_duration_seconds_count 125043

# HELP ml_prediction_confidence Confidence scores distribution
# TYPE ml_prediction_confidence histogram
ml_prediction_confidence_bucket{le="0.8"} 2340
ml_prediction_confidence_bucket{le="0.9"} 15670
ml_prediction_confidence_bucket{le="0.95"} 45230
ml_prediction_confidence_bucket{le="0.99"} 110234
ml_prediction_confidence_bucket{le="+Inf"} 125043
```

**Metrics Exposed:**

- `ml_predictions_total{status}`: Counter of predictions by outcome
- `ml_inference_duration_seconds`: Histogram of inference latency
- `ml_prediction_confidence`: Distribution of confidence scores
- `ml_model_accuracy`: Current model accuracy on validation set
- `ml_false_positive_rate`: False positive rate

---

### POST /predict

Perform binary classification on network flow features (BENIGN vs ATTACK).

#### Request

```http
POST /predict HTTP/1.1
Host: ml-inference:8001
Authorization: Bearer aisoc_<your-api-key>
Content-Type: application/json

{
  "features": [
    1.5, 3200.0, 150.5, 75.2, ...  // 78 CICIDS2017 features
  ],
  "flow_id": "optional-correlation-id"
}
```

**Request Body Schema:**

```json
{
  "features": {
    "type": "array",
    "items": {"type": "number"},
    "minItems": 78,
    "maxItems": 78,
    "description": "78 CICIDS2017 network flow features in order"
  },
  "flow_id": {
    "type": "string",
    "description": "Optional correlation ID for tracking"
  }
}
```

**Required Features (in order):**

| Index | Feature Name | Type | Description |
|-------|-------------|------|-------------|
| 0 | Flow Duration | float | Total flow duration (microseconds) |
| 1 | Flow Bytes/s | float | Bytes per second throughput |
| 2 | Flow Packets/s | float | Packets per second rate |
| 3 | Fwd Packet Length Mean | float | Forward packet size average |
| 4 | Bwd Packet Length Mean | float | Backward packet size average |
| 5 | Fwd IAT Total | float | Forward inter-arrival time total |
| 6 | Active Mean | float | Active time average |
| 7 | Idle Mean | float | Idle time average |
| 8 | Subflow Fwd Bytes | float | Forward bytes in subflow |
| 9 | Destination Port | integer | TCP/UDP destination port |
| ... | ... | ... | (68 additional features) |

See [Feature Specification](../experiments/feature-engineering.md) for complete feature list.

#### Response (Success)

**Status**: `200 OK`

```json
{
  "prediction": "ATTACK",
  "confidence": 0.9856,
  "probabilities": {
    "BENIGN": 0.0144,
    "ATTACK": 0.9856
  },
  "model_used": "random_forest_cicids2017_v1.2",
  "inference_time_ms": 0.72,
  "flow_id": "optional-correlation-id",
  "feature_importance": {
    "top_3_features": [
      {"name": "Flow Bytes/s", "importance": 0.128},
      {"name": "Flow Packets/s", "importance": 0.113},
      {"name": "Fwd Packet Length Mean", "importance": 0.152}
    ]
  }
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `prediction` | string | Classification result: `BENIGN` or `ATTACK` |
| `confidence` | float | Prediction confidence (0.0-1.0) |
| `probabilities` | object | Probability distribution over classes |
| `model_used` | string | Model identifier |
| `inference_time_ms` | float | Prediction latency in milliseconds |
| `flow_id` | string | Correlation ID (if provided in request) |
| `feature_importance` | object | Top contributing features for this prediction |

#### Response (Validation Error)

**Status**: `400 Bad Request`

```json
{
  "error": "Invalid feature vector",
  "detail": "Expected 78 features, received 45",
  "required_features": 78,
  "received_features": 45
}
```

#### Response (Model Error)

**Status**: `503 Service Unavailable`

```json
{
  "error": "Model unavailable",
  "detail": "ML model failed to load - service degraded",
  "retry_after": 30
}
```

---

### POST /batch

Batch prediction for high-throughput processing (up to 1000 flows per request).

#### Request

```http
POST /batch HTTP/1.1
Host: ml-inference:8001
Authorization: Bearer aisoc_<your-api-key>
Content-Type: application/json

{
  "flows": [
    {
      "features": [1.5, 3200.0, ...],
      "flow_id": "flow-001"
    },
    {
      "features": [2.1, 4500.0, ...],
      "flow_id": "flow-002"
    }
  ]
}
```

**Request Constraints:**

- Maximum 1000 flows per batch
- Total request size <10MB
- Individual feature vectors: 78 features each

#### Response

**Status**: `200 OK`

```json
{
  "predictions": [
    {
      "flow_id": "flow-001",
      "prediction": "ATTACK",
      "confidence": 0.9856,
      "inference_time_ms": 0.45
    },
    {
      "flow_id": "flow-002",
      "prediction": "BENIGN",
      "confidence": 0.9923,
      "inference_time_ms": 0.42
    }
  ],
  "total_flows": 2,
  "successful_predictions": 2,
  "failed_predictions": 0,
  "total_inference_time_ms": 0.87,
  "average_confidence": 0.9890
}
```

**Batch Performance:**

- 100 flows: 45ms total (0.45ms per prediction)
- 1000 flows: 380ms total (0.38ms per prediction)

---

## Error Codes

| HTTP Status | Error Code | Description |
|-------------|-----------|-------------|
| 400 | `invalid_features` | Feature vector validation failed |
| 401 | `unauthorized` | Missing or invalid authentication |
| 429 | `rate_limit_exceeded` | Request quota exhausted |
| 503 | `model_unavailable` | ML model failed to load |
| 500 | `internal_error` | Unexpected server error |

---

## Rate Limiting

| Profile | Limit | Window |
|---------|-------|--------|
| Strict | 10 req/min | 60 seconds |
| Moderate | 30 req/min | 60 seconds |
| Permissive | 100 req/min | 60 seconds |

**Rate Limit Headers:**

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1698765432
```

---

## Example Usage

### Python (requests)

```python
import requests

url = "http://ml-inference:8001/predict"
headers = {
    "Authorization": "Bearer aisoc_your_api_key",
    "Content-Type": "application/json"
}

# Example feature vector (78 features)
features = [
    125000.0,  # Flow Duration
    3200.5,    # Flow Bytes/s
    45.2,      # Flow Packets/s
    512.3,     # Fwd Packet Length Mean
    # ... 74 additional features
]

payload = {
    "features": features,
    "flow_id": "network-flow-12345"
}

response = requests.post(url, json=payload, headers=headers)

if response.status_code == 200:
    result = response.json()
    print(f"Prediction: {result['prediction']}")
    print(f"Confidence: {result['confidence']:.4f}")
    print(f"Latency: {result['inference_time_ms']}ms")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### cURL

```bash
curl -X POST http://ml-inference:8001/predict \
  -H "Authorization: Bearer aisoc_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "features": [125000.0, 3200.5, 45.2, 512.3, ...],
    "flow_id": "network-flow-12345"
  }'
```

### JavaScript (fetch)

```javascript
const response = await fetch('http://ml-inference:8001/predict', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer aisoc_your_api_key',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    features: [125000.0, 3200.5, 45.2, 512.3, /* 74 more */],
    flow_id: 'network-flow-12345'
  })
});

const result = await response.json();
console.log(`Prediction: ${result.prediction}`);
console.log(`Confidence: ${result.confidence}`);
```

---

## Model Information

### Training Dataset

- **Dataset**: CICIDS2017
- **Total Samples**: 2,830,743 labeled network flows
- **Split**: 80/20 train/test stratified
- **Classes**: Binary (BENIGN, ATTACK)

### Performance Metrics

| Metric | Value |
|--------|-------|
| **Accuracy** | 99.28% |
| **Precision** | 99.29% |
| **Recall** | 99.28% |
| **F1-Score** | 99.28% |
| **False Positive Rate** | 0.25% |
| **False Negative Rate** | 0.85% |
| **Training Time** | 2.57s |
| **Model Size** | 2.93MB |

### Feature Importance (Top 10)

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | Fwd Packet Length Mean | 15.2% |
| 2 | Flow Bytes/s | 12.8% |
| 3 | Flow Packets/s | 11.3% |
| 4 | Bwd Packet Length Mean | 9.7% |
| 5 | Flow Duration | 8.4% |
| 6 | Fwd IAT Total | 7.2% |
| 7 | Active Mean | 6.9% |
| 8 | Idle Mean | 5.8% |
| 9 | Subflow Fwd Bytes | 5.3% |
| 10 | Destination Port | 4.7% |

See [ML Performance Report](../experiments/ml-performance.md) for comprehensive evaluation.

---

## Production Considerations

### Scaling

**Horizontal Scaling:**
```yaml
# docker-compose.yml
services:
  ml-inference:
    deploy:
      replicas: 4
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
```

**Throughput per Instance:**
- Single-threaded: 1,250 predictions/sec
- Multi-threaded (4 cores): 4,500 predictions/sec
- Multi-threaded (8 cores): 8,200 predictions/sec

### Monitoring

**Prometheus Queries:**

```promql
# Request rate
rate(ml_predictions_total[5m])

# Average latency
rate(ml_inference_duration_seconds_sum[5m]) / rate(ml_inference_duration_seconds_count[5m])

# p99 latency
histogram_quantile(0.99, ml_inference_duration_seconds_bucket)

# Error rate
rate(ml_predictions_total{status="failed"}[5m])
```

### Backup Models

The service implements fallback logic:

1. **Primary**: Random Forest (99.28% accuracy)
2. **Fallback 1**: XGBoost (99.21% accuracy, faster inference)
3. **Fallback 2**: Decision Tree (99.10% accuracy, interpretable)

If primary model fails, the service automatically falls back to alternative models.

---

## Changelog

### Version 1.0.0 (Current)

- Initial production release
- Random Forest model trained on CICIDS2017
- Binary classification (BENIGN vs ATTACK)
- <1ms average inference latency
- Batch prediction support (up to 1000 flows)
- Prometheus metrics integration

### Future Roadmap

**v1.1.0 (Planned)**:
- Multi-class classification (14 attack types)
- Explainability via SHAP values
- Model versioning API
- A/B testing framework

**v2.0.0 (Planned)**:
- Deep learning model option (LSTM/Transformer)
- Online learning capabilities
- Adaptive model retraining
- Multi-dataset support (UNSW-NB15, CICIoT2023)

---

## Support

**API Issues**: api-support@ai-soc.example.com
**Model Questions**: ml-team@ai-soc.example.com
**Documentation**: https://docs.ai-soc.example.com/api/ml-inference

---

**Document Version**: 1.0
**Last Updated**: October 24, 2025
**Maintained By**: AI-SOC ML Team
