import sys
import asyncio
import pytest
sys.path.insert(0, '..')

from simp import Intent, SimpResponse, Agent, SimpCrypto, SimpAgent

def test_intent_creation():
    """Test creating an intent"""
    agent = Agent(
        id="test:agent",
        organization="test.local",
        public_key="test_key"
    )
    intent = Intent(
        source_agent=agent,
        intent_type="test_type",
        params={"key": "value"}
    )
    assert intent.intent_type == "test_type"
    assert intent.params["key"] == "value"
    print("✅ test_intent_creation passed")

def test_crypto_signing():
    """Test cryptographic signing"""
    private_key, public_key = SimpCrypto.generate_keypair()

    intent_dict = {
        "id": "test",
        "type": "trade",
        "params": {"amount": 10}
    }

    signature = SimpCrypto.sign_intent(intent_dict, private_key)
    assert signature is not None
    assert len(signature) > 0
    print("✅ test_crypto_signing passed")

def test_response_creation():
    """Test creating a response"""
    response = SimpResponse(
        intent_id="intent_123",
        status="success",
        data={"result": "ok"}
    )
    assert response.status == "success"
    assert response.data["result"] == "ok"
    print("✅ test_response_creation passed")

@pytest.mark.asyncio
async def test_simp_agent():
    """Test a SIMP agent"""
    class TestAgent(SimpAgent):
        def __init__(self):
            super().__init__("test:agent", "test.local")
            self.register_handler("test", self.handle_test)

        async def handle_test(self, params):
            return {"ok": True}

    agent = TestAgent()
    intent = agent.create_intent("test", {})
    response = await agent.handle_intent(intent)
    assert response.status == "success"
    assert response.data["ok"] is True
    print("✅ test_simp_agent passed")

if __name__ == "__main__":
    # Run tests
    print("Running tests...\n")
    test_intent_creation()
    test_crypto_signing()
    test_response_creation()
    asyncio.run(test_simp_agent())
    print("\n🎉 ALL TESTS PASSED")
