#!/usr/bin/env python3.10
"""
Start the QuantumArb agent to process file-based intents.
"""

import os
import sys
import json
import time
import threading
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from simp.agents.quantumarb_agent import QuantumArbAgent

class QuantumArbAgentRunner:
    """Runner for QuantumArb agent that processes file-based intents."""
    
    def __init__(self, agent_id="quantumarb"):
        self.agent_id = agent_id
        self.inbox_dir = project_root / "data" / "inboxes" / agent_id
        self.outbox_dir = project_root / "data" / "inboxes"
        self.agent = None
        self.running = False
        
    def setup_directories(self):
        """Create necessary directories."""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        print(f"Inbox directory: {self.inbox_dir}")
        print(f"Outbox directory: {self.outbox_dir}")
    
    def start_agent(self):
        """Start the QuantumArb agent."""
        print("Starting QuantumArb agent...")
        
        # Create agent instance
        self.agent = QuantumArbAgent(poll_interval=2.0)
        
        # Initialize agent
        self.agent.initialize()
        print("✓ QuantumArb agent initialized")
        
        # Start processing loop in background thread
        self.running = True
        self.process_thread = threading.Thread(target=self.process_loop, daemon=True)
        self.process_thread.start()
        print("✓ QuantumArb agent processing loop started")
        
        return True
    
    def process_loop(self):
        """Process file-based intents in a loop."""
        print("Processing loop started...")
        
        while self.running:
            try:
                # Check for new intent files
                intent_files = list(self.inbox_dir.glob("*.json"))
                
                for intent_file in intent_files:
                    try:
                        with open(intent_file, "r") as f:
                            intent_data = json.load(f)
                        
                        print(f"Processing intent: {intent_data.get('intent_id', 'unknown')}")
                        
                        # Process the intent
                        response = self.agent.process_intent(intent_data)
                        
                        # Write response to outbox
                        if response and "source_agent" in intent_data:
                            source_agent = intent_data["source_agent"]
                            outbox_path = self.outbox_dir / source_agent
                            outbox_path.mkdir(exist_ok=True)
                            
                            response_file = outbox_path / f"response_{intent_data['intent_id']}.json"
                            with open(response_file, "w") as f:
                                json.dump(response, f, indent=2)
                            
                            print(f"✓ Response written to: {response_file}")
                        
                        # Remove processed intent file
                        intent_file.unlink()
                        print(f"✓ Processed and removed: {intent_file.name}")
                        
                    except Exception as e:
                        print(f"✗ Error processing {intent_file}: {e}")
                
                # Sleep before next check
                time.sleep(5)
                
            except Exception as e:
                print(f"✗ Error in process loop: {e}")
                time.sleep(10)
    
    def stop(self):
        """Stop the agent."""
        print("Stopping QuantumArb agent...")
        self.running = False
        if hasattr(self, 'process_thread') and self.process_thread:
            self.process_thread.join(timeout=5)
        print("QuantumArb agent stopped")
    
    def send_test_intent(self):
        """Send a test intent to the agent."""
        test_intent = {
            "intent_id": f"test_execution_{int(time.time())}",
            "intent_type": "arbitrage_execution",
            "source_agent": "tester",
            "target_agent": self.agent_id,
            "payload": {
                "symbol": "BTC-USD",
                "venue_a": "testnet_exchange_a",
                "venue_b": "testnet_exchange_b",
                "price_a": 50000.0,
                "price_b": 50100.0,
                "spread": 100.0,
                "spread_percent": 0.2,
                "amount": 0.001,
                "max_slippage": 0.1,
                "arb_type": "cross_venue",
                "confidence": 0.85,
                "timestamp": time.time(),
                "test_mode": True,
                "sandbox": True
            },
            "metadata": {
                "test": True,
                "sandbox": True,
                "emergency_stop_available": True
            },
            "timestamp": time.time()
        }
        
        intent_file = self.inbox_dir / f"{test_intent['intent_id']}.json"
        with open(intent_file, "w") as f:
            json.dump(test_intent, f, indent=2)
        
        print(f"✓ Test intent written to: {intent_file}")
        return test_intent["intent_id"]
    
    def check_response(self, intent_id, timeout=30):
        """Check for response to a specific intent."""
        start_time = time.time()
        outbox_path = self.outbox_dir / "tester"
        
        while time.time() - start_time < timeout:
            response_files = list(outbox_path.glob(f"*{intent_id}*"))
            if response_files:
                for response_file in response_files:
                    with open(response_file, "r") as f:
                        response = json.load(f)
                    print(f"✓ Response received: {response}")
                    return response
            
            time.sleep(2)
        
        print("✗ No response received within timeout")
        return None

def main():
    """Main function to run the QuantumArb agent."""
    print("="*80)
    print("QUANTUMARB AGENT RUNNER")
    print("="*80)
    
    runner = QuantumArbAgentRunner()
    
    try:
        # Setup directories
        runner.setup_directories()
        
        # Start agent
        if not runner.start_agent():
            print("Failed to start agent")
            return 1
        
        # Send test intent
        print("\nSending test intent...")
        intent_id = runner.send_test_intent()
        
        # Wait for response
        print(f"\nWaiting for response to intent: {intent_id}")
        response = runner.check_response(intent_id, timeout=60)
        
        if response:
            print("\n✅ SUCCESS: QuantumArb agent is processing intents!")
            print(f"Response: {json.dumps(response, indent=2)}")
            
            # Keep running to process more intents
            print("\nAgent is running. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping agent...")
        
        else:
            print("\n⚠️  WARNING: No response received. Agent may need debugging.")
            return 1
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        runner.stop()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())