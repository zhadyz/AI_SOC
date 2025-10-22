"""
Load Testing - Locust Configuration
Performance and stress testing for AI-SOC services

Author: LOVELESS
Mission: OPERATION TEST-FORTRESS
Date: 2025-10-22

Usage:
    locust -f locustfile.py --host=http://localhost:8100
    locust -f locustfile.py --headless -u 100 -r 10 --run-time 5m
"""

from locust import HttpUser, task, between, events
import random
import json


# ============================================================================
# Test Data Generators
# ============================================================================

def generate_security_alert():
    """Generate random security alert"""
    alert_types = [
        ("Failed SSH login", "T1110.001", "Credential Access", 8),
        ("Suspicious file modification", "T1486", "Impact", 12),
        ("Port scan detected", "T1046", "Discovery", 6),
        ("Malware detected", "T1204", "Execution", 15),
        ("Privilege escalation attempt", "T1068", "Privilege Escalation", 10)
    ]

    alert_type = random.choice(alert_types)
    alert_id = f"load-test-{random.randint(1000, 9999)}"

    return {
        "alert_id": alert_id,
        "timestamp": "2025-10-22T10:30:00Z",
        "source_ip": f"192.168.1.{random.randint(1, 254)}",
        "destination_ip": f"10.0.0.{random.randint(1, 254)}",
        "rule_id": str(random.randint(10000, 99999)),
        "rule_level": alert_type[3],
        "rule_description": alert_type[0],
        "full_log": f"Oct 22 10:30:00 server: {alert_type[0]}",
        "agent_name": f"server-{random.randint(1, 10):02d}",
        "mitre_tactic": alert_type[2],
        "mitre_technique": alert_type[1]
    }


def generate_network_flow():
    """Generate random network flow for ML inference"""
    # Generate 78 random features
    features = [random.uniform(0, 1000) for _ in range(78)]

    return {
        "features": features,
        "model_name": random.choice(["random_forest", "xgboost", "decision_tree"])
    }


# ============================================================================
# Alert Triage Service Load Test
# ============================================================================

class AlertTriageUser(HttpUser):
    """Simulated user for Alert Triage Service"""

    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    host = "http://localhost:8100"

    @task(10)
    def analyze_alert(self):
        """Analyze security alert (main workflow)"""
        alert = generate_security_alert()

        with self.client.post(
            "/analyze",
            json=alert,
            catch_response=True,
            name="/analyze"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "severity" in data and "confidence" in data:
                    response.success()
                else:
                    response.failure("Invalid response structure")
            elif response.status_code == 503:
                response.failure("Service unavailable (Ollama)")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def health_check(self):
        """Health check endpoint"""
        with self.client.get("/health", catch_response=True, name="/health") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(1)
    def get_metrics(self):
        """Get Prometheus metrics"""
        with self.client.get("/metrics", catch_response=True, name="/metrics") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Metrics failed: {response.status_code}")

    def on_start(self):
        """Called when user starts"""
        print(f"🚀 Starting load test for Alert Triage Service")


# ============================================================================
# ML Inference API Load Test
# ============================================================================

class MLInferenceUser(HttpUser):
    """Simulated user for ML Inference API"""

    wait_time = between(0.1, 0.5)  # Faster requests for ML inference
    host = "http://localhost:8500"

    @task(20)
    def predict(self):
        """Single prediction request"""
        flow = generate_network_flow()

        with self.client.post(
            "/predict",
            json=flow,
            catch_response=True,
            name="/predict"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "prediction" in data and "confidence" in data:
                    # Track inference latency
                    if data.get("inference_time_ms", 0) > 100:
                        response.failure(f"Slow inference: {data['inference_time_ms']}ms")
                    else:
                        response.success()
                else:
                    response.failure("Invalid response structure")
            else:
                response.failure(f"Prediction failed: {response.status_code}")

    @task(2)
    def list_models(self):
        """List available models"""
        with self.client.get("/models", catch_response=True, name="/models") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Models endpoint failed: {response.status_code}")

    @task(1)
    def health_check(self):
        """Health check"""
        with self.client.get("/health", catch_response=True, name="/health") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")


# ============================================================================
# RAG Service Load Test
# ============================================================================

class RAGServiceUser(HttpUser):
    """Simulated user for RAG Service"""

    wait_time = between(1, 2)
    host = "http://localhost:8300"

    @task(10)
    def retrieve_context(self):
        """Retrieve context from knowledge base"""
        queries = [
            "What is MITRE ATT&CK technique T1110?",
            "How to detect brute force attacks?",
            "Ransomware incident response procedures",
            "SQL injection attack patterns",
            "Privilege escalation techniques"
        ]

        query_data = {
            "query": random.choice(queries),
            "collection": "mitre_attack",
            "top_k": 3,
            "min_similarity": 0.7
        }

        with self.client.post(
            "/retrieve",
            json=query_data,
            catch_response=True,
            name="/retrieve"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "results" in data:
                    response.success()
                else:
                    response.failure("Invalid response structure")
            else:
                response.failure(f"Retrieval failed: {response.status_code}")

    @task(2)
    def list_collections(self):
        """List available collections"""
        with self.client.get("/collections", catch_response=True, name="/collections") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Collections failed: {response.status_code}")


# ============================================================================
# Load Test Event Handlers
# ============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts"""
    print("\n" + "="*70)
    print("🔥 LOAD TEST STARTING - AI-SOC PLATFORM")
    print("="*70)
    print(f"Target: {environment.host}")
    print(f"Users: {environment.parsed_options.num_users if environment.parsed_options else 'N/A'}")
    print("="*70 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops"""
    print("\n" + "="*70)
    print("🏁 LOAD TEST COMPLETE")
    print("="*70)

    stats = environment.stats
    print(f"\n📊 RESULTS SUMMARY:")
    print(f"   Total Requests: {stats.total.num_requests}")
    print(f"   Failures: {stats.total.num_failures}")
    print(f"   Success Rate: {((stats.total.num_requests - stats.total.num_failures) / stats.total.num_requests * 100):.2f}%")
    print(f"   Average Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"   Max Response Time: {stats.total.max_response_time:.2f}ms")
    print(f"   Requests/sec: {stats.total.total_rps:.2f}")
    print("="*70 + "\n")


# ============================================================================
# Custom Load Test Scenarios
# ============================================================================

class SpikeLoadUser(HttpUser):
    """Simulate spike/burst traffic"""

    wait_time = between(0.01, 0.1)  # Very fast requests
    host = "http://localhost:8100"

    @task
    def spike_analyze(self):
        """Rapid-fire alert analysis"""
        alert = generate_security_alert()
        self.client.post("/analyze", json=alert, name="spike-analyze")


class SustainedLoadUser(HttpUser):
    """Simulate sustained load over time"""

    wait_time = between(2, 5)  # Steady requests
    host = "http://localhost:8100"

    @task
    def sustained_analyze(self):
        """Steady alert analysis"""
        alert = generate_security_alert()
        self.client.post("/analyze", json=alert, name="sustained-analyze")


# ============================================================================
# Performance Benchmarks
# ============================================================================

"""
Performance Targets:
- Alert Triage: <30s per request (with LLM)
- ML Inference: <100ms per prediction
- RAG Retrieval: <2s per query
- Throughput: 10+ alerts/second
- Success Rate: >95%

Load Test Scenarios:
1. Normal Load: 10 users, 2s wait time
   locust -f locustfile.py --headless -u 10 -r 2 --run-time 5m

2. High Load: 50 users, 1s wait time
   locust -f locustfile.py --headless -u 50 -r 5 --run-time 10m

3. Spike Load: 100 users, 0.1s wait time
   locust -f locustfile.py --headless -u 100 -r 20 --run-time 2m

4. Endurance Test: 20 users, 30 minutes
   locust -f locustfile.py --headless -u 20 -r 2 --run-time 30m
"""
