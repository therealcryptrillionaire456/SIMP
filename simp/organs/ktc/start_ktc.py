#!/usr/bin/env python3
"""
Start Keep the Change (KTC) System

This script starts the KTC API server and registers the agent with SIMP broker.
"""

import os
import sys
import time
import logging
import argparse
from pathlib import Path
import subprocess
import threading

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from simp.organs.ktc.agent.ktc_agent import create_ktc_agent
from simp.organs.ktc.api.app import start_server as start_api_server


def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("ktc_startup.log")
        ]
    )
    return logging.getLogger("ktc_startup")


def check_simp_broker(simp_url: str = "http://localhost:5555") -> bool:
    """Check if SIMP broker is running"""
    import requests
    
    try:
        response = requests.get(f"{simp_url}/health", timeout=5)
        return response.status_code == 200
    except Exception as e:
        return False


def register_with_simp(agent_id: str, endpoint: str, simp_url: str = "http://localhost:5555") -> bool:
    """Register KTC agent with SIMP broker"""
    import requests
    import json
    
    logger = logging.getLogger("ktc_startup")
    
    registration_data = {
        "agent_id": agent_id,
        "endpoint": endpoint,
        "capabilities": [
            "receipt_processing",
            "price_comparison",
            "savings_calculation",
            "crypto_investment",
            "wallet_management"
        ],
        "metadata": {
            "service": "Keep the Change (KTC)",
            "version": "1.0.0",
            "description": "Grocery savings to crypto investment platform"
        }
    }
    
    try:
        logger.info(f"Registering agent {agent_id} with SIMP broker at {simp_url}")
        
        # Try to register with SIMP broker
        response = requests.post(
            f"{simp_url}/agents/register",
            json=registration_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"Successfully registered agent {agent_id}")
            logger.info(f"Response: {response.json()}")
            return True
        else:
            logger.warning(f"Failed to register agent: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error registering with SIMP broker: {str(e)}")
        return False


def start_ktc_api(host: str = "127.0.0.1", port: int = 8765, debug: bool = False):
    """Start KTC API server in a separate thread"""
    logger = logging.getLogger("ktc_startup")
    
    def run_server():
        try:
            logger.info(f"Starting KTC API server on {host}:{port}")
            from simp.organs.ktc.api.app import start_server
            start_server(host=host, port=port, debug=debug)
        except Exception as e:
            logger.error(f"API server error: {str(e)}")
    
    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Give server time to start
    time.sleep(2)
    
    # Check if server is running
    import requests
    try:
        response = requests.get(f"http://{host}:{port}/health", timeout=5)
        if response.status_code == 200:
            logger.info(f"KTC API server is running at http://{host}:{port}")
            return True
        else:
            logger.error(f"KTC API server returned status {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Failed to connect to KTC API server: {str(e)}")
        return False


def create_agent_instance():
    """Create and test KTC agent instance"""
    logger = logging.getLogger("ktc_startup")
    
    try:
        logger.info("Creating KTC agent instance...")
        agent = create_ktc_agent()
        
        # Test agent health
        health = agent.health()
        logger.info(f"Agent created: {health.get('agent_id')}")
        logger.info(f"Capabilities: {', '.join(health.get('capabilities', []))}")
        
        return agent
    except Exception as e:
        logger.error(f"Failed to create agent: {str(e)}")
        return None


def main():
    """Main startup function"""
    parser = argparse.ArgumentParser(description="Start Keep the Change (KTC) System")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind API server to")
    parser.add_argument("--port", type=int, default=8765, help="Port for API server")
    parser.add_argument("--simp-url", default="http://localhost:5555", help="SIMP broker URL")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-simp", action="store_true", help="Don't register with SIMP broker")
    parser.add_argument("--test-only", action="store_true", help="Run tests only, don't start server")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    
    print("\n" + "=" * 60)
    print("KEEP THE CHANGE (KTC) SYSTEM STARTUP")
    print("=" * 60)
    
    # Check if test-only mode
    if args.test_only:
        logger.info("Running in test-only mode...")
        
        # Run agent tests
        test_script = Path(__file__).parent / "tests" / "test_ktc_agent.py"
        if test_script.exists():
            logger.info(f"Running tests from {test_script}")
            result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
        else:
            logger.error(f"Test script not found: {test_script}")
        
        return
    
    # Check SIMP broker
    if not args.no_simp:
        logger.info(f"Checking SIMP broker at {args.simp_url}...")
        if check_simp_broker(args.simp_url):
            logger.info("✅ SIMP broker is running")
        else:
            logger.warning("⚠️  SIMP broker is not running. Some features may be limited.")
            logger.warning("   Start SIMP broker with: python bin/start_server.py")
    
    # Create agent instance
    agent = create_agent_instance()
    if not agent:
        logger.error("Failed to create agent. Exiting.")
        return
    
    # Start API server
    if not start_ktc_api(host=args.host, port=args.port, debug=args.debug):
        logger.error("Failed to start API server. Exiting.")
        return
    
    # Register with SIMP broker
    if not args.no_simp:
        agent_endpoint = f"http://{args.host}:{args.port}"
        if register_with_simp("ktc_agent", agent_endpoint, args.simp_url):
            logger.info("✅ Successfully integrated with SIMP system")
        else:
            logger.warning("⚠️  Could not register with SIMP broker. Running in standalone mode.")
    
    # Print startup summary
    print("\n" + "=" * 60)
    print("STARTUP COMPLETE")
    print("=" * 60)
    print(f"📡 KTC API Server: http://{args.host}:{args.port}")
    print(f"🤖 KTC Agent ID: ktc_agent")
    print(f"🔗 SIMP Broker: {args.simp_url}")
    print(f"💾 Database: data/ktc.db")
    print("\nAvailable Endpoints:")
    print(f"  GET  http://{args.host}:{args.port}/health")
    print(f"  POST http://{args.host}:{args.port}/api/receipts/process")
    print(f"  POST http://{args.host}:{args.port}/api/prices/compare")
    print(f"  POST http://{args.host}:{args.port}/api/investments/create")
    print(f"  GET  http://{args.host}:{args.port}/api/users/<user_id>/stats")
    print(f"  POST http://{args.host}:{args.port}/api/simp/route")
    print("\nNext Steps:")
    print("1. Test the API with curl or Postman")
    print("2. Develop frontend application")
    print("3. Integrate with real OCR service")
    print("4. Connect to live crypto trading via QuantumArb")
    print("\nPress Ctrl+C to stop the server.")
    print("=" * 60)
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down KTC system...")
        if agent:
            agent.close()
        logger.info("KTC system stopped.")


if __name__ == "__main__":
    main()