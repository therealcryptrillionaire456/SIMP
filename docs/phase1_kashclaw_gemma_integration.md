# Phase 1: kashclaw_gemma Integration Plan

## Overview
This document details the implementation plan for Phase 1 of the Agent Ecosystem Expansion, focusing on integrating kashclaw_gemma (port 8780) as the first pilot agent.

## 1. Current State Analysis

### 1.1 kashclaw_gemma Agent Status
- **Location**: `/Users/kaseymarcelle/bullbear/agents/kashclaw_gemma_agent.py`
- **Port**: 8780 (as per .goosehints)
- **Capabilities**: Planning, research, summarization, classification
- **Current Status**: Available but not systematically registered with SIMP broker

### 1.2 Existing Infrastructure
- **Broker Registration**: `simp/server/broker.py` has `register_agent()` method
- **HTTP Server**: `simp/server/http_server.py` has `/agents/register` endpoint
- **Agent Manager**: `simp/server/agent_manager.py` can spawn agents
- **Health Checks**: Broker has health check loop for registered agents

## 2. Integration Requirements

### 2.1 Functional Requirements
1. **Verification**: Verify kashclaw_gemma is running on port 8780
2. **Registration**: Register agent with SIMP broker using proper capabilities
3. **Routing**: Update routing policy to include kashclaw_gemma
4. **Monitoring**: Implement health checks and status monitoring
5. **Testing**: Create integration tests for end-to-end validation

### 2.2 Non-Functional Requirements
1. **Safety**: No automatic process spawning without verification
2. **Reliability**: Graceful handling of agent unavailability
3. **Performance**: Response time < 5 seconds for LLM queries
4. **Maintainability**: Clear documentation and error handling

## 3. Implementation Steps

### Step 1: Agent Verification Script
Create a verification script to check kashclaw_gemma availability:

```python
# File: tools/verify_kashclaw_gemma.py
"""
Verification script for kashclaw_gemma agent on port 8780
"""
import requests
import json
import sys
from typing import Dict, Optional

def verify_kashclaw_gemma(port: int = 8780, timeout: int = 10) -> Dict:
    """Verify kashclaw_gemma agent is running and healthy."""
    base_url = f"http://localhost:{port}"
    
    checks = {
        "reachable": False,
        "health_endpoint": False,
        "capabilities": False,
        "sample_query": False
    }
    
    try:
        # Check if port is open and responding
        response = requests.get(f"{base_url}/health", timeout=timeout)
        if response.status_code == 200:
            checks["reachable"] = True
            checks["health_endpoint"] = True
            
            health_data = response.json()
            print(f"✓ Health endpoint OK: {health_data}")
            
            # Check capabilities (if endpoint exists)
            try:
                caps_response = requests.get(f"{base_url}/capabilities", timeout=timeout)
                if caps_response.status_code == 200:
                    checks["capabilities"] = True
                    print(f"✓ Capabilities: {caps_response.json()}")
            except:
                print("⚠ Capabilities endpoint not available")
                
            # Test with sample query
            test_payload = {
                "intent_type": "ping",
                "source_agent": "verification_script",
                "params": {"message": "verification test"}
            }
            
            test_response = requests.post(
                f"{base_url}/handle",
                json=test_payload,
                timeout=timeout
            )
            
            if test_response.status_code == 200:
                checks["sample_query"] = True
                print(f"✓ Sample query successful: {test_response.json()}")
                
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to kashclaw_gemma on port {port}")
    except requests.exceptions.Timeout:
        print(f"✗ Timeout connecting to kashclaw_gemma on port {port}")
    except Exception as e:
        print(f"✗ Verification error: {e}")
    
    return checks

if __name__ == "__main__":
    print("Verifying kashclaw_gemma agent...")
    results = verify_kashclaw_gemma()
    
    print("\nVerification Summary:")
    for check, status in results.items():
        status_symbol = "✓" if status else "✗"
        print(f"  {status_symbol} {check}")
    
    if all(results.values()):
        print("\n✅ kashclaw_gemma verification PASSED")
        sys.exit(0)
    else:
        print("\n❌ kashclaw_gemma verification FAILED")
        sys.exit(1)
```

### Step 2: Enhanced Agent Registration Module
Create an enhanced registration module with verification:

```python
# File: simp/agent_registration.py
"""
Enhanced agent registration with verification
"""
import json
import requests
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class AgentVerificationResult:
    """Results of agent verification."""
    agent_id: str
    endpoint: str
    reachable: bool
    health_status: Optional[Dict] = None
    capabilities: Optional[List[str]] = None
    response_time_ms: Optional[float] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    @property
    def passed(self) -> bool:
        """Check if verification passed all critical checks."""
        return self.reachable and self.health_status is not None

class AgentRegistrar:
    """Handles agent registration with verification."""
    
    def __init__(self, broker_url: str = "http://localhost:5555", api_key: Optional[str] = None):
        self.broker_url = broker_url.rstrip("/")
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["X-API-Key"] = api_key
    
    def verify_agent(self, agent_id: str, endpoint: str, timeout: int = 10) -> AgentVerificationResult:
        """Verify an agent before registration."""
        import time
        
        result = AgentVerificationResult(
            agent_id=agent_id,
            endpoint=endpoint,
            reachable=False
        )
        
        try:
            # Check health endpoint
            start_time = time.time()
            health_url = f"{endpoint}/health" if endpoint != "(file-based)" else endpoint
            
            if endpoint == "(file-based)":
                # File-based agent verification
                result.reachable = True
                result.health_status = {"type": "file-based", "status": "available"}
            else:
                # HTTP-based agent verification
                response = requests.get(health_url, timeout=timeout)
                result.response_time_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    result.reachable = True
                    result.health_status = response.json()
                    
                    # Try to get capabilities
                    try:
                        caps_response = requests.get(f"{endpoint}/capabilities", timeout=timeout)
                        if caps_response.status_code == 200:
                            result.capabilities = caps_response.json().get("capabilities", [])
                    except:
                        logger.debug(f"Capabilities endpoint not available for {agent_id}")
                        
                else:
                    result.errors.append(f"Health check failed with status {response.status_code}")
                    
        except requests.exceptions.ConnectionError:
            result.errors.append(f"Cannot connect to agent at {endpoint}")
        except requests.exceptions.Timeout:
            result.errors.append(f"Timeout connecting to agent at {endpoint}")
        except Exception as e:
            result.errors.append(f"Verification error: {e}")
        
        return result
    
    def register_agent(self, agent_id: str, agent_type: str, endpoint: str, 
                      capabilities: List[str], verify: bool = True) -> Dict:
        """Register an agent with the broker after verification."""
        
        if verify:
            verification = self.verify_agent(agent_id, endpoint)
            if not verification.passed:
                raise ValueError(
                    f"Agent verification failed for {agent_id}: {verification.errors}"
                )
            
            # Use discovered capabilities if available
            if verification.capabilities:
                capabilities = verification.capabilities
        
        registration_payload = {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "endpoint": endpoint,
            "capabilities": capabilities
        }
        
        try:
            response = requests.post(
                f"{self.broker_url}/agents/register",
                json=registration_payload,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully registered agent {agent_id}")
                return response.json()
            else:
                logger.error(f"Registration failed for {agent_id}: {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Registration error for {agent_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def register_kashclaw_gemma(self, port: int = 8780) -> Dict:
        """Specialized registration for kashclaw_gemma agent."""
        return self.register_agent(
            agent_id="kashclaw_gemma",
            agent_type="llm_planner",
            endpoint=f"http://localhost:{port}",
            capabilities=["planning", "research", "summarization", "classification"],
            verify=True
        )
```

### Step 3: Update Routing Policy
Update `docs/routing_policy.json` to include kashclaw_gemma:

```json
{
  "intent_type": "planning",
  "primary_agent": "kashclaw_gemma",
  "fallback_chain": ["gemma4_local", "perplexity_research"],
  "required_capability": "planning",
  "description": "Strategic and operational planning tasks"
},
{
  "intent_type": "research",
  "primary_agent": "kashclaw_gemma",
  "fallback_chain": ["perplexity_research", "gemma4_local"],
  "required_capability": "research",
  "description": "Research and information gathering"
},
{
  "intent_type": "summarization",
  "primary_agent": "kashclaw_gemma",
  "fallback_chain": ["gemma4_local"],
  "required_capability": "summarization",
  "description": "Document and content summarization"
},
{
  "intent_type": "classification",
  "primary_agent": "kashclaw_gemma",
  "fallback_chain": ["gemma4_local"],
  "required_capability": "classification",
  "description": "Content classification and categorization"
}
```

### Step 4: Create Integration Tests

```python
# File: tests/test_kashclaw_gemma_integration.py
"""
Integration tests for kashclaw_gemma agent
"""
import pytest
import requests
import time
from unittest.mock import Mock, patch
from simp.agent_registration import AgentRegistrar, AgentVerificationResult

class TestKashclawGemmaIntegration:
    
    @pytest.fixture
    def registrar(self):
        return AgentRegistrar(broker_url="http://localhost:5555")
    
    def test_verification_kashclaw_gemma(self):
        """Test verification of kashclaw_gemma agent."""
        registrar = AgentRegistrar()
        
        with patch('requests.get') as mock_get:
            # Mock successful health response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy", "model": "gemma4:e2b"}
            mock_get.return_value = mock_response
            
            result = registrar.verify_agent(
                agent_id="kashclaw_gemma",
                endpoint="http://localhost:8780"
            )
            
            assert result.agent_id == "kashclaw_gemma"
            assert result.endpoint == "http://localhost:8780"
            assert result.reachable is True
            assert result.health_status == {"status": "healthy", "model": "gemma4:e2b"}
    
    def test_registration_kashclaw_gemma(self):
        """Test registration of kashclaw_gemma agent."""
        registrar = AgentRegistrar()
        
        with patch('requests.post') as mock_post:
            # Mock successful registration
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "agent_id": "kashclaw_gemma",
                "registered_at": "2024-01-01T00:00:00Z"
            }
            mock_post.return_value = mock_response
            
            # Mock verification to succeed
            with patch.object(registrar, 'verify_agent') as mock_verify:
                mock_verify.return_value = AgentVerificationResult(
                    agent_id="kashclaw_gemma",
                    endpoint="http://localhost:8780",
                    reachable=True,
                    health_status={"status": "healthy"},
                    capabilities=["planning", "research"]
                )
                
                result = registrar.register_kashclaw_gemma(port=8780)
                
                assert result["success"] is True
                assert result["agent_id"] == "kashclaw_gemma"
    
    def test_intent_routing_to_kashclaw_gemma(self, broker):
        """Test that planning intents route to kashclaw_gemma."""
        # Register the agent
        broker.register_agent(
            agent_id="kashclaw_gemma",
            agent_type="llm_planner",
            endpoint="http://localhost:8780",
            capabilities=["planning", "research"]
        )
        
        # Create a planning intent
        intent_data = {
            "intent_type": "planning",
            "source_agent": "test_runner",
            "params": {
                "goal": "Create a trading strategy for BTC",
                "timeframe": "1 week"
            }
        }
        
        # Route the intent
        result = broker.route_intent(intent_data)
        
        # Verify routing
        assert "target_agent" in result
        assert result["target_agent"] == "kashclaw_gemma"
        assert "delivery_method" in result
    
    @pytest.mark.integration
    def test_live_kashclaw_gemma_integration(self):
        """
        Live integration test with actual kashclaw_gemma agent.
        This test requires kashclaw_gemma to be running on port 8780.
        """
        # Skip if agent is not running
        try:
            response = requests.get("http://localhost:8780/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("kashclaw_gemma not running on port 8780")
        except:
            pytest.skip("kashclaw_gemma not running on port 8780")
        
        # Test verification
        registrar = AgentRegistrar()
        verification = registrar.verify_agent(
            agent_id="kashclaw_gemma",
            endpoint="http://localhost:8780"
        )
        
        assert verification.passed, f"Verification failed: {verification.errors}"
        print(f"✓ kashclaw_gemma verification passed in {verification.response_time_ms:.0f}ms")
        
        # Test sample query
        test_payload = {
            "intent_type": "planning",
            "source_agent": "integration_test",
            "params": {
                "task": "Create a simple plan for testing",
                "complexity": "low"
            }
        }
        
        response = requests.post(
            "http://localhost:8780/handle",
            json=test_payload,
            timeout=30
        )
        
        assert response.status_code == 200, f"Query failed: {response.status_code}"
        result = response.json()
        assert "response" in result or "result" in result
        print(f"✓ Sample query successful: {result}")
```

### Step 5: Create Deployment Script

```python
# File: bin/deploy_kashclaw_gemma.py
"""
Deployment script for kashclaw_gemma integration
"""
import argparse
import logging
import sys
from pathlib import Path

# Add simp to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from simp.agent_registration import AgentRegistrar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def deploy_kashclaw_gemma(port: int = 8780, broker_url: str = "http://localhost:5555", 
                         api_key: Optional[str] = None, skip_verification: bool = False):
    """
    Deploy kashclaw_gemma integration.
    
    Args:
        port: Port where kashclaw_gemma is running
        broker_url: SIMP broker URL
        api_key: API key for broker authentication
        skip_verification: Skip agent verification (not recommended)
    """
    print("=" * 60)
    print("kashclaw_gemma Integration Deployment")
    print("=" * 60)
    
    registrar = AgentRegistrar(broker_url=broker_url, api_key=api_key)
    
    # Step 1: Verification
    if not skip_verification:
        print("\n[1/3] Verifying kashclaw_gemma agent...")
        verification = registrar.verify_agent(
            agent_id="kashclaw_gemma",
            endpoint=f"http://localhost:{port}"
        )
        
        if not verification.passed:
            print(f"\n❌ Verification FAILED:")
            for error in verification.errors:
                print(f"  - {error}")
            print("\nPlease ensure kashclaw_gemma is running on port {port}")
            print("Start it with: python /Users/kaseymarcelle/bullbear/agents/kashclaw_gemma_agent.py")
            sys.exit(1)
        
        print(f"✓ Agent reachable: {verification.reachable}")
        print(f"✓ Health status: {verification.health_status}")
        if verification.capabilities:
            print(f"✓ Capabilities: {', '.join(verification.capabilities)}")
        print(f"✓ Response time: {verification.response_time_ms:.0f}ms")
    else:
        print("\n⚠ Skipping verification (not recommended)")
    
    # Step 2: Registration
    print("\n[2/3] Registering with SIMP broker...")
    registration_result = registrar.register_kashclaw_gemma(port=port)
    
    if registration_result.get("success"):
        print(f"✓ Successfully registered kashclaw_gemma")
        print(f"  Agent ID: {registration_result.get('agent_id')}")
        print(f"  Registered at: {registration_result.get('registered_at', 'N/A')}")
    else:
        print(f"❌ Registration failed: {registration_result.get('error')}")
        sys.exit(1)
    
    # Step 3: Test integration
    print("\n[3/3] Testing integration...")
    try:
        import requests
        test_payload = {
            "intent_type": "ping",
            "source_agent": "deployment_script",
            "target_agent": "kashclaw_gemma",
            "params": {"message": "integration test"}
        }
        
        response = requests.post(
            f"{broker_url}/intents/route",
            json=test_payload,
            headers={"X-API-Key": api_key} if api_key else {},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✓ Integration test passed")
            result = response.json()
            print(f"  Delivery method: {result.get('delivery_method')}")
            print(f"  Intent ID: {result.get('intent_id')}")
        else:
            print(f"⚠ Integration test returned status {response.status_code}")
            
    except Exception as e:
        print(f"⚠ Integration test error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ kashclaw_gemma integration COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Check agent status: curl http://localhost:5555/agents")
    print("2. Test routing: Use the dashboard or API to send planning intents")
    print("3. Monitor health: Watch broker logs for agent heartbeats")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy kashclaw_gemma integration")
    parser.add_argument("--port", type=int, default=8780, help="kashclaw_gemma port")
    parser.add_argument("--broker", default="http://localhost:5555", help="SIMP broker URL")
    parser.add_argument("--api-key", help="Broker API key")
    parser.add_argument("--skip-verification", action="store_true", help="Skip agent verification")
    
    args = parser.parse_args()
    
    deploy_kashclaw_gemma(
        port=args.port,
        broker_url=args.broker,
        api_key=args.api_key,
        skip_verification=args.skip_verification
    )
```

## 4. Validation Checklist

### Pre-Integration Validation
- [ ] kashclaw_gemma agent is running on port 8780
- [ ] Health endpoint responds with 200 OK
- [ ] Agent can handle sample queries
- [ ] SIMP broker is running on port 5555
- [ ] Broker health endpoint is accessible

### Integration Validation
- [ ] Agent verification script passes all checks
- [ ] Registration with broker succeeds
- [ ] Agent appears in `/agents` endpoint
- [ ] Routing policy updated with kashclaw_gemma
- [ ] Planning intents route to kashclaw_gemma

### Post-Integration Validation
- [ ] Integration tests pass
- [ ] Health checks are running
- [ ] Dashboard shows agent status
- [ ] Sample workflows execute successfully
- [ ] Error handling works correctly

## 5. Rollback Plan

### If Integration Fails:
1. **Immediate**: Deregister agent from broker
2. **Cleanup**: Remove routing policy updates
3. **Verification**: Run pre-integration tests to confirm baseline
4. **Documentation**: Record failure details for analysis

### Rollback Commands:
```bash
# Deregister agent
curl -X DELETE http://localhost:5555/agents/kashclaw_gemma -H "X-API-Key: $SIMP_API_KEY"

# Restore original routing policy
cp docs/routing_policy.json.backup docs/routing_policy.json

# Verify system state
curl http://localhost:5555/health
curl http://localhost:5555/agents
```

## 6. Success Metrics

### Immediate (Day 1)
- [ ] kashclaw_gemma registered with broker
- [ ] Health checks operational
- [ ] Basic planning intents work
- [ ] Integration tests pass

### Short-term (Week 1)
- [ ] Agent handles 95% of planning intents successfully
- [ ] Response time < 5 seconds for 90% of requests
- [ ] No critical errors in production
- [ ] Dashboard integration complete

### Long-term (Month 1)
- [ ] Agent uptime > 99.5%
- [ ] Used in production workflows
- [ ] Performance metrics meeting SLAs
- [ ] Positive operator feedback

## 7. Next Steps After Phase 1

1. **Documentation**: Update system documentation with kashclaw_gemma integration
2. **Monitoring**: Enhance monitoring and alerting for the new agent
3. **Optimization**: Performance tuning based on real usage
4. **Phase 2 Planning**: Begin planning for projectx_native integration

This plan provides a complete, safe approach to integrating kashclaw_gemma as the first agent in the ecosystem expansion, with proper verification, testing, and rollback capabilities.