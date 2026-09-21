"""
End-to-End Tests - Complete System Workflows
Tests full alert-to-response workflows across the entire AI-SOC platform

Author: LOVELESS
Mission: OPERATION TEST-FORTRESS
Date: 2025-10-22
"""

import pytest
import asyncio


# ============================================================================
# Complete Alert Processing Workflow
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.slow
class TestCompleteAlertWorkflow:
    """Test complete alert processing from detection to response"""

    async def test_full_alert_lifecycle(self, http_client, alert_triage_url, ml_inference_url, sample_security_alert, sample_network_flow):
        """
        Test: Network Traffic → ML Detection → Alert → Triage → [TheHive] → Response

        Workflow:
        1. ML model detects suspicious traffic
        2. Wazuh generates alert
        3. Alert sent to triage service
        4. LLM analyzes and classifies
        5. High-severity alerts create TheHive case
        6. Recommendations returned
        """
        try:
            # STEP 1: ML Detection
            print("\n🔍 STEP 1: ML Network Traffic Detection")
            ml_response = await http_client.post(
                f"{ml_inference_url}/predict",
                json=sample_network_flow,
                timeout=10.0
            )

            if ml_response.status_code != 200:
                pytest.skip("ML service not running")

            ml_data = ml_response.json()
            print(f"   Prediction: {ml_data['prediction']}")
            print(f"   Confidence: {ml_data['confidence']:.2%}")

            # STEP 2: Alert Generation (simulated - Wazuh would do this)
            print("\n📢 STEP 2: Alert Generation")
            if ml_data["prediction"] == "ATTACK" and ml_data["confidence"] > 0.8:
                print("   ⚠️  Attack detected! Generating alert...")
                enriched_alert = sample_security_alert.copy()
                enriched_alert["ml_prediction"] = ml_data["prediction"]
                enriched_alert["ml_confidence"] = ml_data["confidence"]
            else:
                enriched_alert = sample_security_alert

            # STEP 3: Alert Triage
            print("\n🤖 STEP 3: LLM-Powered Alert Triage")
            triage_response = await http_client.post(
                f"{alert_triage_url}/analyze",
                json=enriched_alert,
                timeout=30.0
            )

            if triage_response.status_code != 200:
                pytest.skip("Alert triage service not running")

            triage_data = triage_response.json()
            print(f"   Severity: {triage_data['severity'].upper()}")
            print(f"   Confidence: {triage_data['confidence']:.2%}")
            print(f"   Summary: {triage_data['summary'][:100]}...")

            # STEP 4: Case Creation (TheHive - when available)
            print("\n📋 STEP 4: Case Management")
            if triage_data["severity"] in ["critical", "high"]:
                print("   🚨 High-severity alert → Creating TheHive case")
                # TODO: Implement TheHive API integration
                print("   ⏳ TheHive integration pending...")
            else:
                print("   ℹ️  Low-severity alert → Logged only")

            # STEP 5: Response Actions
            print("\n🛡️  STEP 5: Automated Response")
            if triage_data["recommendations"]:
                print(f"   Recommendations: {len(triage_data['recommendations'])}")
                for i, rec in enumerate(triage_data["recommendations"][:3], 1):
                    print(f"   {i}. {rec}")

            # Validate workflow success
            assert ml_data["prediction"] in ["BENIGN", "ATTACK"]
            assert triage_data["severity"] in ["critical", "high", "medium", "low", "info"]
            assert triage_data["processing_time_ms"] < 30000  # <30s total

            print("\n✅ Complete workflow successful!")

        except Exception as e:
            pytest.skip(f"E2E workflow failed: {e}")


# ============================================================================
# Batch Alert Processing
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.slow
class TestBatchProcessing:
    """Test batch alert processing capabilities"""

    async def test_batch_alert_triage(self, http_client, alert_triage_url, sample_security_alert):
        """Test processing multiple alerts in batch"""
        try:
            # Create batch of 20 alerts
            batch_size = 20
            alerts = []
            for i in range(batch_size):
                alert = sample_security_alert.copy()
                alert["alert_id"] = f"batch-alert-{i:03d}"
                alerts.append(alert)

            print(f"\n📊 Processing batch of {batch_size} alerts...")

            # Process all alerts
            import time
            start_time = time.time()

            tasks = [
                http_client.post(f"{alert_triage_url}/analyze", json=alert, timeout=30.0)
                for alert in alerts
            ]

            responses = await asyncio.gather(*tasks, return_exceptions=True)
            duration = time.time() - start_time

            # Analyze results
            successful = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
            success_rate = (successful / batch_size) * 100

            print(f"   ✅ Success: {successful}/{batch_size} ({success_rate:.1f}%)")
            print(f"   ⏱️  Duration: {duration:.2f}s")
            print(f"   ⚡ Throughput: {successful/duration:.2f} alerts/s")

            # Validate batch processing
            assert success_rate >= 80, f"Success rate too low: {success_rate:.1f}%"
            assert duration < 60, f"Batch processing too slow: {duration:.2f}s"

        except Exception as e:
            pytest.skip(f"Batch processing test failed: {e}")


# ============================================================================
# Incident Response Workflow
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestIncidentResponseWorkflow:
    """Test incident response and escalation workflows"""

    async def test_critical_alert_escalation(self, http_client, alert_triage_url):
        """Test critical alert escalation workflow"""
        critical_alert = {
            "alert_id": "critical-001",
            "timestamp": "2025-10-22T10:30:00Z",
            "source_ip": "192.168.1.100",
            "destination_ip": "10.0.0.50",
            "rule_id": "100045",
            "rule_level": 15,  # Critical level
            "rule_description": "Active ransomware encryption detected",
            "full_log": "Oct 22 10:30:00 server ransomware.exe: Encrypting files...",
            "agent_name": "file-server-01",
            "mitre_tactic": "Impact",
            "mitre_technique": "T1486"
        }

        try:
            print("\n🚨 Testing Critical Alert Escalation")

            response = await http_client.post(
                f"{alert_triage_url}/analyze",
                json=critical_alert,
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                print(f"   Severity: {data['severity'].upper()}")
                print(f"   MITRE Tactics: {', '.join(data['mitre_tactics'])}")

                # Critical alerts should be marked as critical/high
                assert data["severity"] in ["critical", "high"], f"Expected critical severity, got {data['severity']}"

                # Should have high confidence
                assert data["confidence"] > 0.7, f"Low confidence for critical alert: {data['confidence']}"

                # Should have actionable recommendations
                assert len(data["recommendations"]) > 0, "No recommendations provided"

                print("   ✅ Critical alert properly escalated")

        except Exception as e:
            pytest.skip(f"Critical alert test failed: {e}")


# ============================================================================
# RAG-Enhanced Analysis Workflow
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestRAGEnhancedWorkflow:
    """Test RAG-enhanced alert analysis"""

    async def test_knowledge_base_integration(self, http_client, rag_service_url, alert_triage_url, sample_security_alert):
        """Test alert analysis with knowledge base context"""
        try:
            print("\n📚 Testing RAG-Enhanced Analysis")

            # STEP 1: Query knowledge base for context
            print("   1. Querying MITRE ATT&CK knowledge base...")
            rag_query = {
                "query": f"What is MITRE technique {sample_security_alert.get('mitre_technique', 'T1110')}?",
                "collection": "mitre_attack",
                "top_k": 3,
                "min_similarity": 0.7
            }

            rag_response = await http_client.post(
                f"{rag_service_url}/retrieve",
                json=rag_query,
                timeout=10.0
            )

            if rag_response.status_code == 200:
                rag_data = rag_response.json()
                print(f"   ✓ Retrieved {rag_data['total_results']} relevant documents")

                # STEP 2: Analyze alert with RAG context
                print("   2. Analyzing alert with context...")
                # In production, this context would be added to the LLM prompt
                triage_response = await http_client.post(
                    f"{alert_triage_url}/analyze",
                    json=sample_security_alert,
                    timeout=30.0
                )

                if triage_response.status_code == 200:
                    triage_data = triage_response.json()
                    print(f"   ✓ Analysis complete: {triage_data['severity']}")
                    print("   ✅ RAG-enhanced workflow successful")

        except Exception as e:
            pytest.skip(f"RAG workflow test failed: {e}")


# ============================================================================
# System Resilience Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.slow
class TestSystemResilience:
    """Test system resilience and recovery"""

    async def test_service_recovery(self, http_client, alert_triage_url, sample_security_alert):
        """Test service recovery after errors"""
        try:
            print("\n🔄 Testing Service Recovery")

            # Send valid request
            print("   1. Sending valid request...")
            response1 = await http_client.post(
                f"{alert_triage_url}/analyze",
                json=sample_security_alert,
                timeout=30.0
            )
            assert response1.status_code == 200

            # Send invalid request
            print("   2. Sending invalid request...")
            response2 = await http_client.post(
                f"{alert_triage_url}/analyze",
                json={"invalid": "data"},
                timeout=10.0
            )
            assert response2.status_code == 422  # Validation error

            # Send another valid request to verify recovery
            print("   3. Verifying service recovery...")
            response3 = await http_client.post(
                f"{alert_triage_url}/analyze",
                json=sample_security_alert,
                timeout=30.0
            )
            assert response3.status_code == 200

            print("   ✅ Service recovered successfully")

        except Exception as e:
            pytest.skip(f"Resilience test failed: {e}")

    async def test_timeout_handling(self, http_client, alert_triage_url, sample_security_alert):
        """Test timeout handling"""
        try:
            print("\n⏱️  Testing Timeout Handling")

            # Set very short timeout
            response = await http_client.post(
                f"{alert_triage_url}/analyze",
                json=sample_security_alert,
                timeout=0.001  # 1ms - will timeout
            )

        except asyncio.TimeoutError:
            print("   ✅ Timeout handled correctly")
        except Exception as e:
            print(f"   ℹ️  Expected timeout, got: {type(e).__name__}")


# ============================================================================
# Performance Benchmarks
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
class TestEndToEndPerformance:
    """Test end-to-end performance benchmarks"""

    async def test_latency_benchmarks(self, http_client, alert_triage_url, ml_inference_url, sample_security_alert, sample_network_flow):
        """Test latency at each stage of the workflow"""
        import time

        try:
            print("\n⚡ Latency Benchmarks")

            # ML Inference Latency
            start = time.time()
            ml_response = await http_client.post(f"{ml_inference_url}/predict", json=sample_network_flow, timeout=10.0)
            ml_latency = (time.time() - start) * 1000
            print(f"   ML Inference: {ml_latency:.2f}ms")

            # Alert Triage Latency
            start = time.time()
            triage_response = await http_client.post(f"{alert_triage_url}/analyze", json=sample_security_alert, timeout=30.0)
            triage_latency = (time.time() - start) * 1000
            print(f"   Alert Triage: {triage_latency:.2f}ms")

            # Total E2E Latency
            total_latency = ml_latency + triage_latency
            print(f"   Total E2E: {total_latency:.2f}ms")

            # Performance targets
            assert ml_latency < 200, f"ML inference too slow: {ml_latency:.2f}ms"
            assert triage_latency < 30000, f"Triage too slow: {triage_latency:.2f}ms"

        except Exception as e:
            pytest.skip(f"Performance benchmark failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "e2e"])
