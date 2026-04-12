import asyncio
from simp.server.broker import SimpBroker, BrokerConfig

async def test():
    broker = SimpBroker(BrokerConfig())
    broker.start()
    
    result = await broker.route_intent({
        "intent_id": "i1",
        "source_agent": "test",
        "intent_type": "ping",
        "target_agent": "nonexistent",
    })
    
    print("Result:", result)
    print("Keys:", list(result.keys()) if isinstance(result, dict) else type(result))

if __name__ == "__main__":
    asyncio.run(test())