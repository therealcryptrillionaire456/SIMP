"""
Basic integration tests for SIMP agent ecosystem.

Tests core functionality with available agents.
"""

import json
import time
import unittest
import requests
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestBasicAgentIntegration(unittest.TestCase):
    """Basic integration tests focusing on available agents."""
    
    BROKER_URL = "http://127.0.0.1:5555"
    API_KEY = os.environ.get("SIMP_API_KEY", "test-key")
    
    @classmethod
    def setUpClass(cls):
        """Check if broker is available."""
        cls.broker_available = False
        try:
            response = requests.get(f"{cls.BROKER_URL}/health", timeout=3)
            if response.status_code == 200:
                cls.broker_available = True
                print(f"✓ Broker available at {cls.BROKER_URL}")
        except:
            print(f"✗ Broker not available at {cls.BROKER_URL}")
    
    def setUp(self):
        """Set up test."""
        if not self.broker_available:
            self.skipTest("Broker not available")
        
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.API_KEY
        }
    
    def test_01_broker_basics(self):
        """Test basic broker endpoints."""
        # Test health endpoint
        response = requests.get(f"{self.BROKER_URL}/health", timeout=5)
        self.assertEqual(response.status_code, 200)
        health_data = response.json()
        self.assertEqual(health_data["status"], "healthy")
        print(f"Broker health: {health_data}")
        
        # Test stats endpoint
        response = requests.get(f"{self.BROKER_URL}/stats", timeout=5)
        self.assertEqual(response.status_code, 200)
        stats_data = response.json()
        self.assertIn("agents_online", stats_data)
        print(f"Broker stats: {stats_data}")
    
    def test_02_list_agents(self):
        """Test listing registered agents."""
        response = requests.get(f"{self.BROKER_URL}/agents", timeout=5)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        agents = data.get("agents", {})
        agent_count = data.get("count", 0)
        
        print(f"Found {agent_count} registered agents:")
        for agent_id, agent_info in agents.items():
            status = agent_info.get("status", "unknown")
            endpoint = agent_info.get("endpoint", "none")
            print(f"  - {agent_id}: {status} at {endpoint}")
        
        self.assertGreater(agent_count, 0, "Should have at least one agent registered")
    
    def test_03_ping_available_agents(self):
        """Test ping intent to all available agents."""
        # Get list of agents
        response = requests.get(f"{self.BROKER_URL}/agents", timeout=5)
        agents = response.json()["agents"]
        
        successful_pings = 0
        
        for agent_id, agent_info in agents.items():
            # Skip file-based agents
            if agent_info.get("file_based", False):
                print(f"Skipping file-based agent: {agent_id}")
                continue
            
            endpoint = agent_info.get("endpoint", "")
            if endpoint == "(file-based)":
                print(f"Skipping file-based endpoint: {agent_id}")
                continue
            
            print(f"Testing ping to {agent_id}...")
            
            intent_data = {
                "intent_type": "ping",
                "source_agent": "integration_test",
                "target_agent": agent_id,
                "payload": {
                    "test": "integration",
                    "agent": agent_id,
                    "timestamp": time.time()
                }
            }
            
            try:
                response = requests.post(
                    f"{self.BROKER_URL}/intents/route",
                    headers=self.headers,
                    data=json.dumps(intent_data),
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    status = result.get("routing_result", {}).get("status", "unknown")
                    
                    if status == "routed":
                        successful_pings += 1
                        print(f"  ✓ Ping to {agent_id} routed successfully")
                    else:
                        print(f"  ✗ Ping to {agent_id} failed with status: {status}")
                else:
                    print(f"  ✗ Ping to {agent_id} failed with HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"  ✗ Ping to {agent_id} raised exception: {e}")
        
        print(f"\nSuccessful pings: {successful_pings}/{len(agents)}")
        
        # We should have at least one successful ping
        self.assertGreater(successful_pings, 0, "Should have at least one successful ping")
    
    def test_04_echo_intent_workflow(self):
        """Test echo intent workflow with available agents."""
        # Find an agent that supports echo capability
        response = requests.get(f"{self.BROKER_URL}/agents", timeout=5)
        agents = response.json()["agents"]
        
        echo_agent = None
        for agent_id, agent_info in agents.items():
            metadata = agent_info.get("metadata", {})
            capabilities = metadata.get("capabilities", [])
            if "echo" in capabilities:
                echo_agent = agent_id
                break
        
        if not echo_agent:
            print("No agent with echo capability found, skipping test")
            self.skipTest("No agent with echo capability")
        
        print(f"Testing echo with agent: {echo_agent}")
        
        test_message = f"Integration test at {time.time()}"
        
        intent_data = {
            "intent_type": "echo",
            "source_agent": "integration_test",
            "target_agent": echo_agent,
            "payload": {
                "message": test_message,
                "repeat": 1
            }
        }
        
        response = requests.post(
            f"{self.BROKER_URL}/intents/route",
            headers=self.headers,
            data=json.dumps(intent_data),
            timeout=10
        )
        
        self.assertEqual(response.status_code, 200)
        
        result = response.json()
        print(f"Echo result: {result}")
        
        # Check routing was successful
        self.assertEqual(result["routing_result"]["status"], "routed")
    
    def test_05_agent_health_monitoring(self):
        """Test agent health monitoring features."""
        # Get agent status
        response = requests.get(f"{self.BROKER_URL}/agents", timeout=5)
        agents = response.json()["agents"]
        
        for agent_id, agent_info in agents.items():
            status = agent_info.get("status", "unknown")
            last_seen = agent_info.get("last_seen", "never")
            heartbeat_count = agent_info.get("heartbeat_count", 0)
            stale = agent_info.get("stale", False)
            
            print(f"Agent {agent_id}:")
            print(f"  Status: {status}")
            print(f"  Last seen: {last_seen}")
            print(f"  Heartbeats: {heartbeat_count}")
            print(f"  Stale: {stale}")
            
            # Basic health checks
            if status in ["active", "online"]:
                self.assertFalse(stale, f"Active agent {agent_id} should not be stale")
                self.assertGreater(heartbeat_count, 0, f"Agent {agent_id} should have heartbeats")
    
    def test_06_error_scenarios(self):
        """Test error handling scenarios."""
        # Test 1: Non-existent agent
        intent_data = {
            "intent_type": "ping",
            "source_agent": "integration_test",
            "target_agent": "non_existent_agent_xyz123",
            "payload": {"test": "error"}
        }
        
        response = requests.post(
            f"{self.BROKER_URL}/intents/route",
            headers=self.headers,
            data=json.dumps(intent_data),
            timeout=10
        )
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        
        # Should fail to route
        self.assertEqual(result["routing_result"]["status"], "failed")
        print(f"Non-existent agent test: {result['routing_result'].get('error', 'no error')}")
        
        # Test 2: Missing API key
        bad_headers = {"Content-Type": "application/json"}
        intent_data = {
            "intent_type": "ping",
            "source_agent": "integration_test",
            "target_agent": "test_agent_1",
            "payload": {"test": "auth"}
        }
        
        response = requests.post(
            f"{self.BROKER_URL}/intents/route",
            headers=bad_headers,
            data=json.dumps(intent_data),
            timeout=10
        )
        
        # Should get 401 or 400
        self.assertIn(response.status_code, [400, 401, 403])
        print(f"Missing API key test: HTTP {response.status_code}")
    
    def test_07_concurrent_operations(self):
        """Test simple concurrent operations."""
        import threading
        
        results = []
        
        def send_test_ping(thread_id):
            """Send a test ping."""
            intent_data = {
                "intent_type": "ping",
                "source_agent": f"thread_{thread_id}",
                "target_agent": "test_agent_1",
                "payload": {
                    "thread": thread_id,
                    "timestamp": time.time()
                }
            }
            
            try:
                response = requests.post(
                    f"{self.BROKER_URL}/intents/route",
                    headers=self.headers,
                    data=json.dumps(intent_data),
                    timeout=15
                )
                results.append((thread_id, response.status_code))
            except Exception as e:
                results.append((thread_id, f"Error: {e}"))
        
        # Send 3 concurrent requests
        threads = []
        for i in range(3):
            thread = threading.Thread(target=send_test_ping, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        print(f"Concurrent test results: {results}")
        
        success_count = sum(1 for _, status in results if status == 200)
        print(f"Successful concurrent requests: {success_count}/3")
        
        # Should have at least some successes
        self.assertGreater(success_count, 0)
    
    def test_08_system_state_persistence(self):
        """Test that system state persists across operations."""
        # Get initial state
        initial_response = requests.get(f"{self.BROKER_URL}/agents", timeout=5)
        initial_agents = initial_response.json()["agents"]
        initial_count = len(initial_agents)
        
        print(f"Initial agent count: {initial_count}")
        
        # Perform some operations
        self.test_03_ping_available_agents()
        
        # Get state again
        final_response = requests.get(f"{self.BROKER_URL}/agents", timeout=5)
        final_agents = final_response.json()["agents"]
        final_count = len(final_agents)
        
        print(f"Final agent count: {final_count}")
        
        # Count should be the same
        self.assertEqual(initial_count, final_count, "Agent count should not change")
        
        # Check agent IDs are the same
        initial_ids = set(initial_agents.keys())
        final_ids = set(final_agents.keys())
        
        self.assertEqual(initial_ids, final_ids, "Agent IDs should not change")
    
    def test_09_document_interoperability_issues(self):
        """Document any interoperability issues found."""
        print("\n" + "="*60)
        print("INTEROPERABILITY ISSUES DOCUMENTATION")
        print("="*60)
        
        # Get agent info
        response = requests.get(f"{self.BROKER_URL}/agents", timeout=5)
        agents = response.json()["agents"]
        
        issues = []
        
        for agent_id, agent_info in agents.items():
            status = agent_info.get("status", "unknown")
            endpoint = agent_info.get("endpoint", "none")
            stale = agent_info.get("stale", False)
            health_failures = agent_info.get("health_check_failures", 0)
            
            # Check for potential issues
            if stale:
                issues.append(f"Agent {agent_id} is marked as stale")
            
            if health_failures > 0:
                issues.append(f"Agent {agent_id} has {health_failures} health check failures")
            
            if status not in ["active", "online"]:
                issues.append(f"Agent {agent_id} has unusual status: {status}")
            
            if endpoint in ["(file-based)", ""]:
                issues.append(f"Agent {agent_id} has unusual endpoint: {endpoint}")
        
        # Report issues
        if issues:
            print(f"Found {len(issues)} potential issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("No interoperability issues detected!")
        
        print("="*60)
        
        # This test doesn't fail, just documents issues
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main(verbosity=2)