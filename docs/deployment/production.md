# Production Deployment Guide for AI-SOC

## Executive Summary

This guide provides a comprehensive production deployment strategy for AI-SOC, incorporating high-availability architectures, disaster recovery procedures, deployment patterns (blue-green, canary), observability best practices, and SLA/SLO definitions for Security Operations Centers.

Based on 2025 industry standards and production-grade practices from leading organizations deploying LLMs at scale.

---

## Table of Contents

1. [High Availability Architecture](#1-high-availability-architecture)
2. [Disaster Recovery Strategy](#2-disaster-recovery-strategy)
3. [Deployment Patterns](#3-deployment-patterns)
4. [Observability & Monitoring](#4-observability-monitoring)
5. [SLA/SLO/SLI Definitions](#5-slaslosli-definitions)
6. [Production Checklist](#6-production-checklist)

---

## 1. High Availability Architecture

### 1.1 Multi-Zone Kubernetes Deployment

**Architecture Diagram**:
```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (CloudFlare + NGINX)        │
└────────────┬────────────────────────────┬────────────────────┘
             │                            │
     ┌───────▼────────┐           ┌──────▼─────────┐
     │   Zone A       │           │   Zone B       │
     │  (us-east-1a)  │           │  (us-east-1b)  │
     │                │           │                │
     │  ┌──────────┐  │           │  ┌──────────┐  │
     │  │ LLM Pods │  │           │  │ LLM Pods │  │
     │  │  x3      │  │           │  │  x3      │  │
     │  └──────────┘  │           │  └──────────┘  │
     │  ┌──────────┐  │           │  ┌──────────┐  │
     │  │ API Pods │  │           │  │ API Pods │  │
     │  │  x5      │  │           │  │  x5      │  │
     │  └──────────┘  │           │  └──────────┘  │
     └────────┬───────┘           └────────┬───────┘
              │                            │
     ┌────────▼────────────────────────────▼───────┐
     │         OpenSearch Cluster (3 masters)      │
     │  Master-1 (Zone A) | Master-2 (Zone B)      │
     │  Data-1,2 (Zone A) | Data-3,4 (Zone B)      │
     └──────────────────────────────────────────────┘
              │
     ┌────────▼────────────────────────────────────┐
     │  Persistent Storage (EBS/EFS with snapshots)│
     └─────────────────────────────────────────────┘
```

### 1.2 Kubernetes HA Configuration

```yaml
# k8s-deployment/llm-service-ha.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-service
  namespace: ai-soc
spec:
  replicas: 6  # Minimum 6 replicas across zones
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2
      maxUnavailable: 1  # Always maintain at least 5 running pods

  selector:
    matchLabels:
      app: llm-service

  template:
    metadata:
      labels:
        app: llm-service
    spec:
      # Topology spread for HA across zones
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: llm-service

      # Anti-affinity: Don't schedule on same node
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchExpressions:
                  - key: app
                    operator: In
                    values:
                      - llm-service
              topologyKey: kubernetes.io/hostname

      containers:
        - name: llm-container
          image: ai-soc-llm:1.0.0
          resources:
            requests:
              cpu: "2"
              memory: "8Gi"
            limits:
              cpu: "4"
              memory: "16Gi"

          # Liveness probe: restart if unhealthy
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 60
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 3

          # Readiness probe: remove from load balancer if not ready
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 2

          # Startup probe: allow slow startup
          startupProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 0
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 30  # 5 minutes to start

---
apiVersion: v1
kind: Service
metadata:
  name: llm-service
  namespace: ai-soc
spec:
  type: LoadBalancer
  selector:
    app: llm-service
  ports:
    - port: 80
      targetPort: 8000
  sessionAffinity: ClientIP  # Sticky sessions for conversation continuity
```

### 1.3 Control Plane HA (Multi-Master)

```yaml
# kubeadm-config.yaml (for self-hosted Kubernetes)
apiVersion: kubeadm.k8s.io/v1beta3
kind: ClusterConfiguration
kubernetesVersion: v1.28.0
controlPlaneEndpoint: "k8s-api.ai-soc.local:6443"

# High Availability etcd
etcd:
  external:
    endpoints:
      - https://etcd-1.ai-soc.local:2379
      - https://etcd-2.ai-soc.local:2379
      - https://etcd-3.ai-soc.local:2379
    caFile: /etc/kubernetes/pki/etcd/ca.crt
    certFile: /etc/kubernetes/pki/apiserver-etcd-client.crt
    keyFile: /etc/kubernetes/pki/apiserver-etcd-client.key

# Load balancer for API servers
apiServer:
  certSANs:
    - "k8s-api.ai-soc.local"
    - "10.0.0.100"  # Load balancer IP
  extraArgs:
    enable-admission-plugins: NodeRestriction,PodSecurityPolicy
    audit-log-path: /var/log/kubernetes/audit.log
    audit-log-maxage: "30"
```

**Expected Availability**:
- Single master: ~99.5% (4.3 hours downtime/month)
- Multi-master (3 nodes): **99.95%** (22 minutes downtime/month)
- Multi-master + multi-zone: **99.99%** (4.3 minutes downtime/month)

### 1.4 Database HA (OpenSearch Cluster)

```yaml
# opensearch-cluster-ha.yaml
apiVersion: opensearch.opster.io/v1
kind: OpenSearchCluster
metadata:
  name: ai-soc-logs
  namespace: ai-soc
spec:
  general:
    version: 2.11.0
    httpPort: 9200
    serviceName: ai-soc-logs

  # Dedicated master nodes (3 for quorum)
  nodePools:
    - component: masters
      replicas: 3
      diskSize: 50Gi
      roles:
        - cluster_manager
      resources:
        requests:
          cpu: 2
          memory: 8Gi
        limits:
          cpu: 4
          memory: 16Gi

      # Spread masters across zones
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule

    # Data nodes (4 for redundancy + performance)
    - component: data
      replicas: 4
      diskSize: 500Gi
      roles:
        - data
        - ingest
      resources:
        requests:
          cpu: 4
          memory: 32Gi
        limits:
          cpu: 8
          memory: 64Gi

  # HA configuration
  dashboards:
    enable: true
    replicas: 2  # Redundant dashboards

  security:
    tls:
      transport:
        generate: true
      http:
        generate: true
```

### 1.5 Network HA with Load Balancing

```nginx
# nginx-ha.conf
upstream llm_backend {
    least_conn;  # Route to least busy server

    # Health checks
    server llm-1.ai-soc.local:8000 max_fails=3 fail_timeout=30s;
    server llm-2.ai-soc.local:8000 max_fails=3 fail_timeout=30s;
    server llm-3.ai-soc.local:8000 max_fails=3 fail_timeout=30s;
    server llm-4.ai-soc.local:8000 max_fails=3 fail_timeout=30s;
    server llm-5.ai-soc.local:8000 max_fails=3 fail_timeout=30s;
    server llm-6.ai-soc.local:8000 max_fails=3 fail_timeout=30s;

    # Backup server (if all fail)
    server llm-backup.ai-soc.local:8000 backup;

    # Connection pooling
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name api.ai-soc.local;

    ssl_certificate /etc/nginx/ssl/ai-soc.crt;
    ssl_certificate_key /etc/nginx/ssl/ai-soc.key;

    # SSL optimization
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Health check endpoint
    location /nginx-health {
        access_log off;
        return 200 "healthy\n";
    }

    location / {
        proxy_pass http://llm_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Timeouts
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Retry on failure
        proxy_next_upstream error timeout http_502 http_503 http_504;
        proxy_next_upstream_tries 3;
    }
}
```

---

## 2. Disaster Recovery Strategy

### 2.1 Backup Strategy

**3-2-1 Backup Rule**:
- **3** copies of data
- **2** different storage media (EBS snapshots + S3)
- **1** offsite backup (different region)

```yaml
# velero-backup-schedule.yaml
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: ai-soc-daily-backup
  namespace: velero
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM UTC
  template:
    includedNamespaces:
      - ai-soc
    includeClusterResources: true
    storageLocation: default
    volumeSnapshotLocations:
      - default
    ttl: 720h  # Retain for 30 days

---
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: ai-soc-weekly-backup
  namespace: velero
spec:
  schedule: "0 3 * * 0"  # Weekly on Sunday at 3 AM
  template:
    includedNamespaces:
      - ai-soc
    includeClusterResources: true
    storageLocation: s3-backup
    ttl: 2160h  # Retain for 90 days
```

**OpenSearch Snapshots**:

```python
# backup/opensearch_snapshots.py
from opensearchpy import OpenSearch
import datetime

os_client = OpenSearch(['https://opensearch:9200'])

# Register snapshot repository (S3)
os_client.snapshot.create_repository(
    repository='ai-soc-backups',
    body={
        "type": "s3",
        "settings": {
            "bucket": "ai-soc-opensearch-backups",
            "region": "us-east-1",
            "base_path": "snapshots",
            "compress": True,
            "server_side_encryption": True
        }
    }
)

# Create daily snapshot
def create_daily_snapshot():
    """Create incremental snapshot of all indices"""
    snapshot_name = f"snapshot-{datetime.date.today()}"

    os_client.snapshot.create(
        repository='ai-soc-backups',
        snapshot=snapshot_name,
        body={
            "indices": "logs-*,alerts-*,threats-*",
            "ignore_unavailable": True,
            "include_global_state": False
        },
        wait_for_completion=False  # Async
    )

    print(f"Snapshot {snapshot_name} initiated")

# Automated retention
def cleanup_old_snapshots(retention_days: int = 30):
    """Delete snapshots older than retention period"""
    snapshots = os_client.snapshot.get(
        repository='ai-soc-backups',
        snapshot='*'
    )

    cutoff = datetime.datetime.now() - datetime.timedelta(days=retention_days)

    for snapshot in snapshots['snapshots']:
        start_time = datetime.datetime.fromtimestamp(snapshot['start_time_in_millis'] / 1000)

        if start_time < cutoff:
            os_client.snapshot.delete(
                repository='ai-soc-backups',
                snapshot=snapshot['snapshot']
            )
            print(f"Deleted old snapshot: {snapshot['snapshot']}")
```

### 2.2 Recovery Procedures

**Recovery Time Objective (RTO)**: 1 hour
**Recovery Point Objective (RPO)**: 24 hours

**Kubernetes Cluster Recovery**:

```bash
#!/bin/bash
# disaster-recovery/restore-cluster.sh

set -e

echo "=== AI-SOC Disaster Recovery ==="
echo "Restoring from backup..."

# 1. Restore Kubernetes resources with Velero
velero restore create ai-soc-restore \
  --from-backup ai-soc-daily-backup-20251022 \
  --wait

# 2. Verify pods are running
kubectl wait --for=condition=ready pod \
  -l app=llm-service \
  -n ai-soc \
  --timeout=300s

# 3. Restore OpenSearch data
python3 restore_opensearch.py --snapshot snapshot-2025-10-22

# 4. Verify services
kubectl get pods -n ai-soc
kubectl get svc -n ai-soc

# 5. Run smoke tests
python3 smoke-tests.py

echo "=== Recovery Complete ==="
```

**OpenSearch Restore**:

```python
# disaster-recovery/restore_opensearch.py
def restore_opensearch_snapshot(snapshot_name: str):
    """Restore OpenSearch data from snapshot"""

    # Close indices before restore
    indices_to_restore = ["logs-*", "alerts-*", "threats-*"]

    for index_pattern in indices_to_restore:
        os_client.indices.close(index=index_pattern)

    # Restore snapshot
    os_client.snapshot.restore(
        repository='ai-soc-backups',
        snapshot=snapshot_name,
        body={
            "indices": ",".join(indices_to_restore),
            "ignore_unavailable": True,
            "include_global_state": False
        },
        wait_for_completion=True
    )

    # Reopen indices
    for index_pattern in indices_to_restore:
        os_client.indices.open(index=index_pattern)

    print(f"Restored snapshot: {snapshot_name}")
```

### 2.3 Disaster Recovery Testing

```yaml
# .github/workflows/dr-test.yml
name: Disaster Recovery Test

on:
  schedule:
    - cron: '0 4 1 * *'  # Monthly on 1st at 4 AM

jobs:
  dr-test:
    runs-on: ubuntu-latest
    steps:
      - name: Backup Production
        run: |
          velero backup create dr-test-backup \
            --from-schedule ai-soc-daily-backup

      - name: Deploy Test Cluster
        run: |
          terraform apply -var="environment=dr-test"

      - name: Restore to Test Cluster
        run: |
          velero restore create dr-test-restore \
            --from-backup dr-test-backup \
            --wait

      - name: Run Validation Tests
        run: |
          python3 dr-validation-tests.py

      - name: Measure RTO/RPO
        run: |
          python3 measure-recovery-time.py

      - name: Cleanup Test Environment
        run: |
          terraform destroy -var="environment=dr-test" -auto-approve

      - name: Report Results
        run: |
          python3 send-dr-report.py
```

---

## 3. Deployment Patterns

### 3.1 Blue-Green Deployment

**Use Case**: Zero-downtime releases with instant rollback capability

```yaml
# deployment-patterns/blue-green.yaml
---
# Blue environment (current production)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-service-blue
  namespace: ai-soc
spec:
  replicas: 6
  selector:
    matchLabels:
      app: llm-service
      version: blue
  template:
    metadata:
      labels:
        app: llm-service
        version: blue
    spec:
      containers:
        - name: llm-container
          image: ai-soc-llm:1.0.0  # Current version

---
# Green environment (new version)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-service-green
  namespace: ai-soc
spec:
  replicas: 6
  selector:
    matchLabels:
      app: llm-service
      version: green
  template:
    metadata:
      labels:
        app: llm-service
        version: green
    spec:
      containers:
        - name: llm-container
          image: ai-soc-llm:2.0.0  # New version

---
# Service (switch between blue and green)
apiVersion: v1
kind: Service
metadata:
  name: llm-service
  namespace: ai-soc
spec:
  selector:
    app: llm-service
    version: blue  # Change to "green" to switch traffic
  ports:
    - port: 80
      targetPort: 8000
```

**Deployment Script**:

```bash
#!/bin/bash
# deployment-patterns/blue-green-deploy.sh

set -e

NAMESPACE="ai-soc"
SERVICE_NAME="llm-service"
NEW_VERSION="2.0.0"

echo "=== Blue-Green Deployment ==="

# 1. Deploy green environment
echo "Deploying green environment (version $NEW_VERSION)..."
kubectl apply -f llm-service-green.yaml

# 2. Wait for green pods to be ready
echo "Waiting for green pods to be ready..."
kubectl wait --for=condition=ready pod \
  -l app=llm-service,version=green \
  -n $NAMESPACE \
  --timeout=300s

# 3. Run smoke tests on green
echo "Running smoke tests on green environment..."
GREEN_POD=$(kubectl get pod -l version=green -n $NAMESPACE -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n $NAMESPACE $GREEN_POD -- python3 /app/smoke-tests.py

if [ $? -ne 0 ]; then
  echo "Smoke tests failed! Aborting deployment."
  exit 1
fi

# 4. Switch traffic to green
echo "Switching traffic from blue to green..."
kubectl patch service $SERVICE_NAME -n $NAMESPACE \
  -p '{"spec":{"selector":{"version":"green"}}}'

echo "Traffic switched to green!"

# 5. Monitor for 10 minutes
echo "Monitoring green environment for 10 minutes..."
sleep 600

# 6. Check error rates
ERROR_RATE=$(curl -s "http://prometheus:9090/api/v1/query?query=rate(llm_requests_total{status=\"error\"}[5m])" | jq -r '.data.result[0].value[1]')

if (( $(echo "$ERROR_RATE > 0.05" | bc -l) )); then
  echo "High error rate detected! Rolling back to blue..."
  kubectl patch service $SERVICE_NAME -n $NAMESPACE \
    -p '{"spec":{"selector":{"version":"blue"}}}'
  exit 1
fi

# 7. Success! Scale down blue
echo "Deployment successful! Scaling down blue environment..."
kubectl scale deployment llm-service-blue -n $NAMESPACE --replicas=0

echo "=== Deployment Complete ==="
```

### 3.2 Canary Deployment

**Use Case**: Gradual rollout to minimize risk (5% → 25% → 50% → 100%)

```yaml
# deployment-patterns/canary.yaml
---
# Stable deployment (95% of traffic)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-service-stable
  namespace: ai-soc
spec:
  replicas: 19  # 95% of 20 total pods
  selector:
    matchLabels:
      app: llm-service
      track: stable
  template:
    metadata:
      labels:
        app: llm-service
        track: stable
    spec:
      containers:
        - name: llm-container
          image: ai-soc-llm:1.0.0

---
# Canary deployment (5% of traffic)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-service-canary
  namespace: ai-soc
spec:
  replicas: 1  # 5% of 20 total pods
  selector:
    matchLabels:
      app: llm-service
      track: canary
  template:
    metadata:
      labels:
        app: llm-service
        track: canary
    spec:
      containers:
        - name: llm-container
          image: ai-soc-llm:2.0.0  # New version

---
# Service (routes to both stable and canary)
apiVersion: v1
kind: Service
metadata:
  name: llm-service
  namespace: ai-soc
spec:
  selector:
    app: llm-service  # Selects both stable and canary
  ports:
    - port: 80
      targetPort: 8000
```

**Automated Canary Progression**:

```python
# deployment-patterns/canary-controller.py
import time
import requests

class CanaryController:
    def __init__(self, namespace: str, service: str):
        self.namespace = namespace
        self.service = service
        self.stages = [5, 25, 50, 100]  # Percentage of traffic
        self.stage_duration = 600  # 10 minutes per stage

    def deploy_canary(self, new_version: str):
        """Progressively increase canary traffic"""

        total_replicas = 20

        for stage_pct in self.stages:
            canary_replicas = int(total_replicas * stage_pct / 100)
            stable_replicas = total_replicas - canary_replicas

            print(f"\n=== Canary Stage: {stage_pct}% ===")
            print(f"Canary replicas: {canary_replicas}")
            print(f"Stable replicas: {stable_replicas}")

            # Scale deployments
            self.scale_deployment("llm-service-canary", canary_replicas)
            self.scale_deployment("llm-service-stable", stable_replicas)

            # Wait for pods to be ready
            self.wait_for_ready("llm-service-canary", canary_replicas)

            # Monitor for duration
            print(f"Monitoring for {self.stage_duration}s...")
            time.sleep(self.stage_duration)

            # Check metrics
            if not self.check_canary_health():
                print("Canary health check failed! Rolling back...")
                self.rollback()
                return False

            print(f"Stage {stage_pct}% successful!")

        print("\n=== Canary deployment complete! ===")
        # Cleanup: delete stable deployment
        self.delete_deployment("llm-service-stable")
        return True

    def check_canary_health(self) -> bool:
        """Check if canary is healthy compared to stable"""

        # Query Prometheus for error rates
        canary_error_rate = self.get_error_rate("track=canary")
        stable_error_rate = self.get_error_rate("track=stable")

        print(f"Canary error rate: {canary_error_rate:.4f}")
        print(f"Stable error rate: {stable_error_rate:.4f}")

        # Canary must not have >2x error rate of stable
        if canary_error_rate > stable_error_rate * 2:
            return False

        # Canary must have <5% error rate absolute
        if canary_error_rate > 0.05:
            return False

        return True

    def get_error_rate(self, label_filter: str) -> float:
        """Query Prometheus for error rate"""
        query = f'rate(llm_requests_total{{status="error",{label_filter}}}[5m]) / rate(llm_requests_total{{{label_filter}}}[5m])'
        response = requests.get(
            f"http://prometheus:9090/api/v1/query",
            params={"query": query}
        )
        result = response.json()
        if result['data']['result']:
            return float(result['data']['result'][0]['value'][1])
        return 0.0

    def rollback(self):
        """Rollback canary deployment"""
        self.scale_deployment("llm-service-canary", 0)
        self.scale_deployment("llm-service-stable", 20)
        print("Rolled back to stable version")

# Usage
controller = CanaryController("ai-soc", "llm-service")
controller.deploy_canary("2.0.0")
```

---

## 4. Observability & Monitoring

### 4.1 OpenTelemetry Integration

**Comprehensive observability with logs, metrics, and traces**:

```python
# observability/opentelemetry_config.py
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

# Configure resource attributes
resource = Resource(attributes={
    "service.name": "ai-soc-llm-service",
    "service.version": "2.0.0",
    "deployment.environment": "production"
})

# Setup tracing
trace_provider = TracerProvider(resource=resource)
otlp_span_exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317")
trace_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
trace.set_tracer_provider(trace_provider)

# Setup metrics
metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint="http://otel-collector:4317"),
    export_interval_millis=60000
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

# Instrument FastAPI
app = FastAPI()
FastAPIInstrumentor.instrument_app(app)

# Create custom metrics
meter = metrics.get_meter(__name__)
llm_latency_histogram = meter.create_histogram(
    name="llm.inference.duration",
    description="LLM inference duration in seconds",
    unit="s"
)

# Create tracer
tracer = trace.get_tracer(__name__)

# Usage in application
@app.post("/analyze")
async def analyze_threat(prompt: str):
    with tracer.start_as_current_span("llm.inference") as span:
        span.set_attribute("llm.model", "Foundation-Sec-8B")
        span.set_attribute("llm.prompt_length", len(prompt))

        start = time.time()
        result = await llm_service.generate(prompt)
        duration = time.time() - start

        # Record metrics
        llm_latency_histogram.record(duration, {"model": "Foundation-Sec-8B"})

        span.set_attribute("llm.response_length", len(result))
        span.set_attribute("llm.duration_ms", duration * 1000)

        return {"result": result}
```

### 4.2 Distributed Tracing

**Trace requests across microservices**:

```python
# observability/distributed_tracing.py
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

tracer = trace.get_tracer(__name__)
propagator = TraceContextTextMapPropagator()

@app.post("/analyze-alert")
async def analyze_alert(alert_data: dict, request: Request):
    """
    Endpoint with distributed tracing

    Trace propagates: API Gateway -> LLM Service -> ChromaDB -> OpenSearch
    """
    # Extract trace context from incoming request
    ctx = propagator.extract(carrier=dict(request.headers))

    with tracer.start_as_current_span("analyze_alert", context=ctx) as span:
        span.set_attribute("alert.type", alert_data.get("type"))
        span.set_attribute("alert.severity", alert_data.get("severity"))

        # 1. Query threat intel from ChromaDB (span propagates)
        with tracer.start_as_current_span("chromadb.query") as db_span:
            threat_context = await chromadb_client.query(alert_data["description"])
            db_span.set_attribute("chromadb.results", len(threat_context))

        # 2. LLM analysis (span propagates)
        with tracer.start_as_current_span("llm.analyze") as llm_span:
            analysis = await llm_service.analyze(alert_data, threat_context)
            llm_span.set_attribute("llm.tokens", analysis["tokens_used"])

        # 3. Log to OpenSearch (span propagates)
        with tracer.start_as_current_span("opensearch.index") as os_span:
            await opensearch_client.index(analysis)

        return analysis
```

### 4.3 Prometheus Metrics

**RED Metrics (Rate, Errors, Duration)**:

```python
# observability/prometheus_metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time

# Rate: Request throughput
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# Errors: Error rate
llm_errors_total = Counter(
    'llm_errors_total',
    'Total LLM errors',
    ['error_type', 'model']
)

# Duration: Latency distribution
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

llm_inference_duration_seconds = Histogram(
    'llm_inference_duration_seconds',
    'LLM inference duration',
    ['model', 'quantization'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Custom business metrics
active_conversations = Gauge(
    'llm_active_conversations',
    'Number of active LLM conversations'
)

chromadb_index_size = Gauge(
    'chromadb_index_size',
    'Number of vectors in ChromaDB'
)

# Middleware for automatic metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    method = request.method
    endpoint = request.url.path

    start = time.time()

    try:
        response = await call_next(request)

        # Record metrics
        duration = time.time() - start
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)

        return response

    except Exception as e:
        # Record error
        llm_errors_total.labels(
            error_type=type(e).__name__,
            model="Foundation-Sec-8B"
        ).inc()
        raise
```

### 4.4 Log Aggregation (Structured JSON Logs)

```python
# observability/structured_logging.py
import logging
import json
import sys
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """Format logs as JSON for easy parsing"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "@timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "ai-soc-llm-service",
            "environment": "production"
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add custom fields
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        return json.dumps(log_data)

# Configure logger
logger = logging.getLogger("ai-soc")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# Usage with request context
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start = time.time()

    logger.info(
        "Request started",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "user_id": get_user_id(request)
        }
    )

    response = await call_next(request)

    duration_ms = (time.time() - start) * 1000

    logger.info(
        "Request completed",
        extra={
            "request_id": request_id,
            "status_code": response.status_code,
            "duration_ms": duration_ms
        }
    )

    return response
```

---

## 5. SLA/SLO/SLI Definitions

### 5.1 Service Level Indicators (SLIs)

**What we measure**:

| SLI | Description | Measurement |
|-----|-------------|-------------|
| **Availability** | % of time service is reachable | `(successful_requests / total_requests) * 100` |
| **Latency (P95)** | 95th percentile response time | `histogram_quantile(0.95, http_request_duration_seconds)` |
| **Error Rate** | % of requests returning errors | `(error_requests / total_requests) * 100` |
| **Throughput** | Requests per second | `rate(http_requests_total[1m])` |
| **MTTD** | Mean Time To Detect threats | Average time from alert creation to detection |
| **MTTR** | Mean Time To Respond | Average time from detection to response |

### 5.2 Service Level Objectives (SLOs)

**What we promise internally**:

```yaml
# slo-definitions.yaml
slos:
  availability:
    target: 99.9%  # 43 minutes downtime per month
    measurement_window: 30d
    error_budget: 0.1%  # 43 minutes per month

  latency_p95:
    target: 2s  # 95% of requests < 2s
    measurement_window: 30d

  error_rate:
    target: 1%  # <1% of requests fail
    measurement_window: 30d

  llm_inference_latency:
    target: 3s  # P95 inference < 3s
    measurement_window: 7d

  alert_processing_latency:
    target: 30s  # P95 alert analysis < 30s
    measurement_window: 7d

  mttd:
    target: 2h  # Detect threats within 2 hours
    measurement_window: 30d

  mttr:
    target: 4h  # Respond to high-severity threats within 4 hours
    measurement_window: 30d
```

**Prometheus Queries for SLOs**:

```promql
# Availability SLO (99.9%)
(
  sum(rate(http_requests_total{status=~"2.."}[30d]))
  /
  sum(rate(http_requests_total[30d]))
) * 100 > 99.9

# Latency P95 SLO (<2s)
histogram_quantile(0.95,
  rate(http_request_duration_seconds_bucket[30d])
) < 2

# Error Rate SLO (<1%)
(
  sum(rate(http_requests_total{status=~"5.."}[30d]))
  /
  sum(rate(http_requests_total[30d]))
) * 100 < 1
```

### 5.3 Service Level Agreements (SLAs)

**What we promise customers**:

```markdown
# AI-SOC Service Level Agreement (SLA)

## Covered Services
- LLM-powered threat analysis
- Alert triage and prioritization
- Threat intelligence enrichment
- Security recommendations

## Availability Commitment
- **99.5% uptime** (3.6 hours downtime/month)
- Measured on a monthly basis
- Excludes planned maintenance windows (notified 7 days in advance)

## Performance Commitments
- **API Response Time**: 95% of requests complete within 5 seconds
- **Alert Analysis**: 95% of alerts analyzed within 60 seconds
- **Threat Detection**: High-severity threats detected within 4 hours

## Support Response Times
| Severity | First Response | Resolution Target |
|----------|---------------|-------------------|
| P0 - Critical (service down) | 15 minutes | 4 hours |
| P1 - High (degraded) | 1 hour | 24 hours |
| P2 - Medium | 4 hours | 72 hours |
| P3 - Low | 24 hours | 7 days |

## Service Credits
If we fail to meet our SLA commitments:

| Uptime Achievement | Service Credit |
|-------------------|---------------|
| < 99.5% but >= 99.0% | 10% of monthly fee |
| < 99.0% but >= 95.0% | 25% of monthly fee |
| < 95.0% | 50% of monthly fee |

## Exclusions
SLA does not apply to:
- Customer misconfigurations
- Third-party service failures (cloud provider outages)
- DDoS attacks or security incidents
- Planned maintenance (with notice)
- Beta features marked as "experimental"

## Measurement & Reporting
- Uptime calculated from successful health checks every 60 seconds
- Monthly SLA reports provided via customer dashboard
- Real-time status page: status.ai-soc.example.com
```

### 5.4 Error Budget Policy

```python
# slo/error_budget_policy.py
class ErrorBudgetPolicy:
    """
    Error budget determines how much risk we can take

    99.9% SLO = 0.1% error budget = 43 minutes/month downtime
    """

    def __init__(self, slo_target: float, window_days: int = 30):
        self.slo_target = slo_target  # e.g., 0.999 for 99.9%
        self.error_budget = 1 - slo_target
        self.window_seconds = window_days * 24 * 3600

    def calculate_remaining_budget(self, current_availability: float) -> dict:
        """Calculate remaining error budget"""

        # Time spent in error state
        error_rate = 1 - current_availability
        error_budget_consumed = error_rate / self.error_budget

        # Time remaining
        remaining_budget = 1 - error_budget_consumed

        # Time in seconds
        budget_seconds = self.window_seconds * self.error_budget
        consumed_seconds = budget_seconds * error_budget_consumed
        remaining_seconds = budget_seconds * remaining_budget

        return {
            "error_budget": self.error_budget,
            "consumed_pct": error_budget_consumed * 100,
            "remaining_pct": remaining_budget * 100,
            "consumed_seconds": consumed_seconds,
            "remaining_seconds": remaining_seconds,
            "status": self.get_status(error_budget_consumed)
        }

    def get_status(self, consumed: float) -> str:
        """Determine deployment policy based on error budget"""
        if consumed < 0.5:
            return "HEALTHY - Safe to deploy"
        elif consumed < 0.75:
            return "WARNING - Slow down deployments"
        elif consumed < 1.0:
            return "CRITICAL - Freeze non-critical deployments"
        else:
            return "EXHAUSTED - Emergency freeze, focus on reliability"

# Usage
policy = ErrorBudgetPolicy(slo_target=0.999, window_days=30)
current_availability = 0.9985  # 99.85% (below 99.9% SLO)

budget_status = policy.calculate_remaining_budget(current_availability)
print(f"Error budget consumed: {budget_status['consumed_pct']:.2f}%")
print(f"Status: {budget_status['status']}")

# If budget exhausted, block risky changes
if budget_status['consumed_pct'] > 75:
    print("⚠️ Deployment blocked due to error budget policy")
    sys.exit(1)
```

---

## 6. Production Checklist

```markdown
# AI-SOC Production Deployment Checklist

## High Availability
- [ ] Multi-zone Kubernetes cluster (3+ zones)
- [ ] Multi-master control plane (3+ masters)
- [ ] Pod anti-affinity configured
- [ ] Topology spread constraints applied
- [ ] HPA configured for dynamic scaling
- [ ] VPA configured for resource optimization
- [ ] Pod Disruption Budgets defined
- [ ] Load balancer health checks configured
- [ ] Database clustering (OpenSearch 3+ masters)
- [ ] Network redundancy (multiple subnets/AZs)

## Disaster Recovery
- [ ] Velero backups automated (daily + weekly)
- [ ] OpenSearch snapshots to S3 (daily)
- [ ] Backup retention policy defined (30/90 days)
- [ ] DR runbooks documented
- [ ] RTO/RPO targets defined and tested
- [ ] Cross-region backup replication
- [ ] DR testing scheduled (monthly)
- [ ] Recovery procedures validated

## Deployment Strategy
- [ ] Blue-green deployment pipeline configured
- [ ] Canary deployment automation ready
- [ ] Rollback procedures tested
- [ ] Smoke tests automated
- [ ] Feature flags implemented
- [ ] Database migration strategy defined
- [ ] Zero-downtime deployment verified

## Observability
- [ ] OpenTelemetry instrumentation complete
- [ ] Distributed tracing enabled
- [ ] Prometheus metrics exported
- [ ] Grafana dashboards created
- [ ] Log aggregation (OpenSearch/ELK)
- [ ] Structured JSON logging
- [ ] Alert rules configured
- [ ] On-call rotation established
- [ ] Incident response playbooks created

## SLA/SLO/SLI
- [ ] SLIs defined and measured
- [ ] SLOs set with error budgets
- [ ] SLAs documented for customers
- [ ] Error budget policy enforced
- [ ] Service status page public
- [ ] Monthly SLA reports automated
- [ ] Performance baselines established

## Security (from security-hardening.md)
- [ ] OAuth2 authentication enabled
- [ ] MFA enforced for admins
- [ ] Secrets in HashiCorp Vault
- [ ] Rate limiting configured
- [ ] Network segmentation applied
- [ ] TLS 1.3 enforced
- [ ] Audit logging enabled
- [ ] Security scanning automated

## Performance (from performance-optimization.md)
- [ ] LLM quantization enabled
- [ ] vLLM continuous batching
- [ ] ChromaDB HNSW tuned
- [ ] OpenSearch indexing optimized
- [ ] Docker resources limited
- [ ] Resource requests/limits set
- [ ] Performance benchmarks met

## Documentation
- [ ] Architecture diagrams updated
- [ ] API documentation complete
- [ ] Runbooks for common scenarios
- [ ] Troubleshooting guides
- [ ] On-call procedures
- [ ] Change management process
```

---

## 7. Conclusion

This production deployment guide provides a comprehensive framework for deploying AI-SOC with enterprise-grade reliability:

- **99.99% availability** through multi-zone HA architecture
- **<1 hour RTO, <24 hour RPO** disaster recovery
- **Zero-downtime deployments** with blue-green and canary strategies
- **Comprehensive observability** with OpenTelemetry, Prometheus, and structured logging
- **Customer-facing SLAs** with 99.5% uptime commitment

**Recommended Implementation Timeline**:
- **Weeks 1-4**: HA architecture setup (Kubernetes multi-zone, database clustering)
- **Weeks 5-6**: Disaster recovery (backups, DR testing)
- **Weeks 7-8**: Deployment automation (blue-green, canary pipelines)
- **Weeks 9-10**: Observability (OpenTelemetry, dashboards, alerts)
- **Weeks 11-12**: SLA/SLO implementation, final testing, production cutover

---

*Document Version*: 1.0
*Last Updated*: 2025-10-22
*Author*: The Didact (AI Research Specialist)
*Classification*: Internal Use
