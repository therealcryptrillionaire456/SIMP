#!/usr/bin/env python3
"""
Simple SIMP Integration Test
Tests basic functionality of the 3-agent ecosystem.
"""

import json
import requests
import time
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class TestResult:
    test_name: str
    passed: bool
    duration_ms: float
    error: str = None

class SIMPIntegrationTester:
    def __init__(self, broker_url: str = "http://127.0.0.1:5555"):
        self.broker_url = broker_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
    
    def test_broker_health(self) -> TestResult:
        """Test broker health endpoint."""
        start = time.time()
        try:
            response = requests.get(f"{self.broker_url}/health", timeout=5)
            duration = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    return TestResult(
                        test_name="broker_health",
                        passed=True,
                        duration_ms=duration
                    )
            
            return TestResult(
                test_name="broker_health",
                passed=False,
                duration_ms=duration,
                error=f"Status {response.status_code}: {response.text[:100]}"
            )
        except Exception as e:
            return TestResult(
                test_name="broker_health",
                passed=False,
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    def test_agent_registration(self) -> TestResult:
        """Test that all 3 agents are registered."""
        start = time.time()
        try:
            response = requests.get(f"{self.broker_url}/agents", timeout=5)
            duration = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                agents = data.get("agents", {})
                count = data.get("count", 0)
                
                expected_agents = {"test_agent_1", "projectx_native", "kashclaw_gemma"}
                actual_agents = set(agents.keys())
                
                if len(expected_agents) == count and expected_agents.issubset(actual_agents):
                    return TestResult(
                        test_name="agent_registration",
                        passed=True,
                        duration_ms=duration
                    )
                
                missing = expected_agents - actual_agents
                return TestResult(
                    test_name="agent_registration",
                    passed=False,
                    duration_ms=duration,
                    error=f"Missing agents: {missing}, count: {count}"
                )
            
            return TestResult(
                test_name="agent_registration",
                passed=False,
                duration_ms=duration,
                error=f"Status {response.status_code}"
            )
        except Exception as e:
            return TestResult(
                test_name="agent_registration",
                passed=False,
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    def test_intent_routing(self, target_agent: str, intent_type: str = "planning") -> TestResult:
        """Test intent routing to a specific agent."""
        start = time.time()
        try:
            intent_data = {
                "intent_type": intent_type,
                "source_agent": "integration_tester",
                "target_agent": target_agent,
                "params": {"test": True},
                "intent_id": f"test_{int(time.time())}",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            
            response = requests.post(
                f"{self.broker_url}/intents/route",
                headers=self.headers,
                json=intent_data,
                timeout=10
            )
            duration = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") in ["success", "delivered", "routed"]:
                    return TestResult(
                        test_name=f"intent_routing_{target_agent}",
                        passed=True,
                        duration_ms=duration
                    )
                
                return TestResult(
                    test_name=f"intent_routing_{target_agent}",
                    passed=False,
                    duration_ms=duration,
                    error=f"Intent not delivered: {data.get('status')}"
                )
            
            return TestResult(
                test_name=f"intent_routing_{target_agent}",
                passed=False,
                duration_ms=duration,
                error=f"Status {response.status_code}: {response.text[:100]}"
            )
        except Exception as e:
            return TestResult(
                test_name=f"intent_routing_{target_agent}",
                passed=False,
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    def test_dashboard_health(self) -> TestResult:
        """Test dashboard health endpoint."""
        start = time.time()
        try:
            response = requests.get("http://127.0.0.1:8050/health", timeout=5)
            duration = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy" and data.get("broker_reachable") == True:
                    return TestResult(
                        test_name="dashboard_health",
                        passed=True,
                        duration_ms=duration
                    )
            
            return TestResult(
                test_name="dashboard_health",
                passed=False,
                duration_ms=duration,
                error=f"Status {response.status_code}: {response.text[:100]}"
            )
        except Exception as e:
            return TestResult(
                test_name="dashboard_health",
                passed=False,
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    def run_all_tests(self) -> List[TestResult]:
        """Run all integration tests."""
        tests = [
            self.test_broker_health,
            self.test_agent_registration,
            self.test_dashboard_health,
            lambda: self.test_intent_routing("test_agent_1", "planning"),
            lambda: self.test_intent_routing("projectx_native", "planning"),
            lambda: self.test_intent_routing("kashclaw_gemma", "research"),
        ]
        
        results = []
        for test in tests:
            result = test()
            results.append(result)
            print(f"{'✅' if result.passed else '❌'} {result.test_name}: "
                  f"{'PASS' if result.passed else 'FAIL'} "
                  f"({result.duration_ms:.1f}ms)")
            if result.error:
                print(f"   Error: {result.error}")
        
        return results

def main():
    """Main test runner."""
    print("=" * 60)
    print("SIMP Integration Test Suite")
    print("Testing 3-agent ecosystem functionality")
    print("=" * 60)
    
    tester = SIMPIntegrationTester()
    results = tester.run_all_tests()
    
    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("✅ All integration tests passed!")
        return 0
    else:
        print("❌ Some integration tests failed")
        return 1

if __name__ == "__main__":
    exit(main())