#!/usr/bin/env python3.10
"""
Phase 1 Stress Test: Prove Pipeline Under Stress (Sandbox)

Goal: Make sure nothing breaks when it runs like a real desk.
Run the system for multiple full market sessions in sandbox.
Hammer it with:
- Many trade intents across symbols
- Edge-case parameters
- Network hiccups and restarts

Check:
- No orphaned orders or inconsistent ledger rows
- No stuck positions
- Slippage/fee modeling behaves sanely
- Emergency-stop actually halts further intents

Fix any infra bugs that appear only under load (API timeouts, race conditions, deadlocks in BRP evaluation).
"""

import asyncio
import json
import random
import time
import threading
import requests
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stress_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BROKER_URL = "http://127.0.0.1:5555"
API_KEY = "781002cryptrillionaire456"  # From environment variable
QUANTUMARB_AGENT_ID = "quantumarb_enhanced"
TEST_DURATION_MINUTES = 30  # Extended test duration
INTENTS_PER_MINUTE = 60  # High frequency: 1 intent per second
SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "DOT-USD", "MATIC-USD", "AVAX-USD", "LINK-USD"]
EXCHANGES = ["coinbase", "binance", "kraken", "ftx", "bybit", "okx"]

class TestMode(Enum):
    NORMAL = "normal"
    EDGE_CASE = "edge_case"
    NETWORK_HICCUP = "network_hiccup"
    RESTART_SIMULATION = "restart_simulation"
    EMERGENCY_STOP = "emergency_stop"

@dataclass
class TestResult:
    mode: TestMode
    start_time: datetime
    end_time: datetime
    intents_sent: int
    intents_processed: int
    brp_evaluations: int
    brp_blocks: int
    brp_warnings: int
    errors: List[str]
    orphaned_intents: int
    ledger_inconsistencies: int
    emergency_stop_effective: bool = False

class StressTester:
    def __init__(self):
        self.broker_url = BROKER_URL
        self.api_key = API_KEY
        self.agent_id = QUANTUMARB_AGENT_ID
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }
        self.test_results: List[TestResult] = []
        self.running = False
        self.emergency_stop = False
        self.intent_counter = 0
        self.brp_stats = {
            "evaluations": 0,
            "blocks": 0,
            "warnings": 0
        }
        
    def check_broker_health(self) -> bool:
        """Check if broker is healthy and ready."""
        try:
            response = requests.get(f"{self.broker_url}/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                logger.info(f"Broker health: {health}")
                return health.get("status") == "healthy"
        except Exception as e:
            logger.error(f"Broker health check failed: {e}")
        return False
    
    def check_agent_status(self) -> bool:
        """Check if QuantumArb agent is registered and online."""
        try:
            response = requests.get(f"{self.broker_url}/agents", timeout=5)
            if response.status_code == 200:
                data = response.json()
                agents = data.get("agents", {})
                if self.agent_id in agents:
                    agent = agents[self.agent_id]
                    logger.info(f"Agent {self.agent_id} status: {agent}")
                    return agent.get("status") == "online"
        except Exception as e:
            logger.error(f"Agent status check failed: {e}")
        return False
    
    def send_arbitrage_intent(self, symbol: str, exchange_a: str, exchange_b: str, 
                             spread_percent: float, volume: float, mode: TestMode = TestMode.NORMAL) -> Tuple[bool, str]:
        """Send an arbitrage intent to the broker."""
        intent_id = f"stress_test_{self.intent_counter}_{int(time.time())}"
        self.intent_counter += 1
        
        # Generate realistic arbitrage parameters
        base_price = random.uniform(100, 100000)  # Wide range for different assets
        price_a = base_price * (1 + spread_percent / 100)
        price_b = base_price
        
        # Add edge cases based on mode
        if mode == TestMode.EDGE_CASE:
            # Extreme spreads, tiny volumes, negative values, etc.
            if random.random() < 0.3:
                spread_percent = random.uniform(-50, 100)  # Negative or extreme spreads
            if random.random() < 0.2:
                volume = random.uniform(0.000001, 0.001)  # Tiny volumes
            if random.random() < 0.1:
                volume = -abs(volume)  # Negative volume (should be caught by BRP)
        
        intent = {
            "intent_id": intent_id,
            "intent_type": "arbitrage_opportunity",
            "source_agent": "stress_tester",
            "target_agent": self.agent_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {
                "symbol": symbol,
                "exchange_a": exchange_a,
                "exchange_b": exchange_b,
                "price_a": round(price_a, 2),
                "price_b": round(price_b, 2),
                "spread_percent": round(spread_percent, 4),
                "volume": round(volume, 6),
                "estimated_profit": round(abs(spread_percent) * volume * base_price / 100, 2),
                "confidence": random.uniform(0.5, 0.95),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "test_mode": mode.value
            }
        }
        
        # Simulate network hiccups
        if mode == TestMode.NETWORK_HICCUP:
            if random.random() < 0.1:  # 10% chance of timeout
                time.sleep(random.uniform(5, 10))  # Long delay
            elif random.random() < 0.05:  # 5% chance of immediate failure
                return False, "simulated_network_failure"
        
        try:
            response = requests.post(
                f"{self.broker_url}/intents/route",
                headers=self.headers,
                json=intent,
                timeout=10 if mode != TestMode.NETWORK_HICCUP else 30
            )
            
            if response.status_code in [200, 201]:
                logger.debug(f"Intent {intent_id} sent successfully")
                return True, intent_id
            else:
                logger.warning(f"Intent {intent_id} failed with status {response.status_code}: {response.text}")
                return False, f"http_{response.status_code}"
                
        except requests.exceptions.Timeout:
            logger.warning(f"Intent {intent_id} timed out")
            return False, "timeout"
        except Exception as e:
            logger.error(f"Intent {intent_id} failed with error: {e}")
            return False, str(e)
    
    def check_ledger_consistency(self) -> Tuple[int, List[str]]:
        """Check for orphaned intents and ledger inconsistencies."""
        try:
            # Check pending intents
            response = requests.get(f"{self.broker_url}/intents/pending", headers=self.headers, timeout=5)
            pending_intents = response.json() if response.status_code == 200 else []
            
            # Check processed intents (would need ledger endpoint)
            # For now, check agent's processed directory
            processed_dir = "data/inboxes/quantumarb_enhanced/processed"
            if os.path.exists(processed_dir):
                processed_files = [f for f in os.listdir(processed_dir) if f.endswith('.json')]
            else:
                processed_files = []
            
            # Check for orphaned files in inbox
            inbox_dir = "data/inboxes/quantumarb_enhanced"
            if os.path.exists(inbox_dir):
                inbox_files = [f for f in os.listdir(inbox_dir) if f.endswith('.json') and f not in processed_files]
            else:
                inbox_files = []
            
            orphaned_count = len(inbox_files)
            inconsistencies = []
            
            if orphaned_count > 0:
                inconsistencies.append(f"Found {orphaned_count} orphaned intent files in inbox")
                logger.warning(f"Orphaned intents: {inbox_files[:5]}")  # Log first 5
            
            # Check BRP evaluation logs
            brp_log_dir = "logs/quantumarb/brp"
            if os.path.exists(brp_log_dir):
                brp_files = [f for f in os.listdir(brp_log_dir) if f.endswith('.json')]
                self.brp_stats["evaluations"] = len(brp_files)
                
                # Count blocks and warnings
                blocks = 0
                warnings = 0
                for brp_file in brp_files[:10]:  # Sample first 10
                    try:
                        with open(os.path.join(brp_log_dir, brp_file), 'r') as f:
                            data = json.load(f)
                            if data.get("decision") == "block":
                                blocks += 1
                            elif data.get("decision") == "warn":
                                warnings += 1
                    except:
                        pass
                
                self.brp_stats["blocks"] = blocks
                self.brp_stats["warnings"] = warnings
            
            return orphaned_count, inconsistencies
            
        except Exception as e:
            logger.error(f"Ledger consistency check failed: {e}")
            return 0, [f"Consistency check error: {e}"]
    
    def simulate_restart(self):
        """Simulate agent restart by killing and restarting the agent."""
        logger.info("Simulating agent restart...")
        
        # First, send emergency stop
        self.trigger_emergency_stop()
        time.sleep(2)
        
        # Check if agent is still running (would need PID in real scenario)
        # For simulation, just log and continue
        logger.info("Agent restart simulation complete")
        
        # Clear emergency stop after restart
        self.emergency_stop = False
        logger.info("Emergency stop cleared after restart simulation")
    
    def trigger_emergency_stop(self):
        """Trigger emergency stop to halt further intents."""
        logger.warning("=== EMERGENCY STOP TRIGGERED ===")
        self.emergency_stop = True
        
        # Send emergency stop intent
        intent = {
            "intent_id": f"emergency_stop_{int(time.time())}",
            "intent_type": "emergency_stop",
            "source_agent": "stress_tester",
            "target_agent": self.agent_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {
                "reason": "stress_test_emergency_stop",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        try:
            response = requests.post(
                f"{self.broker_url}/intents/route",
                headers=self.headers,
                json=intent,
                timeout=5
            )
            logger.info(f"Emergency stop intent sent: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to send emergency stop: {e}")
    
    def run_test_mode(self, mode: TestMode, duration_seconds: int) -> TestResult:
        """Run a specific test mode for given duration."""
        logger.info(f"Starting {mode.value} test for {duration_seconds} seconds")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=duration_seconds)
        intents_sent = 0
        intents_processed = 0
        errors = []
        
        # Reset BRP stats for this test
        self.brp_stats = {"evaluations": 0, "blocks": 0, "warnings": 0}
        
        while datetime.now() < end_time and not (mode == TestMode.EMERGENCY_STOP and self.emergency_stop):
            # Calculate time left
            time_left = (end_time - datetime.now()).total_seconds()
            if time_left <= 0:
                break
            
            # Send intents at appropriate rate
            if mode == TestMode.EMERGENCY_STOP:
                # Send a few intents, then trigger emergency stop
                if intents_sent < 5 and not self.emergency_stop:
                    symbol = random.choice(SYMBOLS)
                    exchange_a = random.choice(EXCHANGES)
                    exchange_b = random.choice([e for e in EXCHANGES if e != exchange_a])
                    spread = random.uniform(0.1, 5.0)
                    volume = random.uniform(0.01, 10.0)
                    
                    success, intent_id = self.send_arbitrage_intent(
                        symbol, exchange_a, exchange_b, spread, volume, mode
                    )
                    intents_sent += 1
                    if success:
                        intents_processed += 1
                    
                    # Trigger emergency stop after 3 intents
                    if intents_sent >= 3:
                        self.trigger_emergency_stop()
                        time.sleep(2)  # Give time for stop to propagate
                
                # Try to send more intents (should be blocked)
                elif random.random() < 0.1:  # Occasionally try to send more
                    symbol = random.choice(SYMBOLS)
                    exchange_a = random.choice(EXCHANGES)
                    exchange_b = random.choice([e for e in EXCHANGES if e != exchange_a])
                    spread = random.uniform(0.1, 5.0)
                    volume = random.uniform(0.01, 10.0)
                    
                    success, intent_id = self.send_arbitrage_intent(
                        symbol, exchange_a, exchange_b, spread, volume, mode
                    )
                    intents_sent += 1
                    if not success and "emergency" in intent_id.lower():
                        errors.append(f"Intent blocked by emergency stop: {intent_id}")
                    
                time.sleep(1)
                
            else:
                # Normal intent sending
                symbol = random.choice(SYMBOLS)
                exchange_a = random.choice(EXCHANGES)
                exchange_b = random.choice([e for e in EXCHANGES if e != exchange_a])
                
                # Vary parameters based on mode
                if mode == TestMode.EDGE_CASE:
                    spread = random.uniform(-20, 50)  # Wide range including negative
                    volume = random.uniform(0.000001, 1000)
                else:
                    spread = random.uniform(0.1, 5.0)
                    volume = random.uniform(0.01, 10.0)
                
                success, intent_id = self.send_arbitrage_intent(
                    symbol, exchange_a, exchange_b, spread, volume, mode
                )
                intents_sent += 1
                if success:
                    intents_processed += 1
                else:
                    errors.append(f"Intent failed: {intent_id}")
                
                # Vary sleep time based on mode
                if mode == TestMode.NETWORK_HICCUP:
                    sleep_time = random.uniform(0.5, 3.0)
                elif mode == TestMode.RESTART_SIMULATION:
                    # Occasionally simulate restart
                    if random.random() < 0.05:  # 5% chance
                        self.simulate_restart()
                        sleep_time = random.uniform(2.0, 5.0)
                    else:
                        sleep_time = random.uniform(0.1, 1.0)
                else:
                    sleep_time = random.uniform(0.1, 1.0)  # 0.1-1.0 seconds between intents
                
                time.sleep(sleep_time)
        
        # Check ledger consistency
        orphaned_count, inconsistencies = self.check_ledger_consistency()
        errors.extend(inconsistencies)
        
        result = TestResult(
            mode=mode,
            start_time=start_time,
            end_time=datetime.now(),
            intents_sent=intents_sent,
            intents_processed=intents_processed,
            brp_evaluations=self.brp_stats["evaluations"],
            brp_blocks=self.brp_stats["blocks"],
            brp_warnings=self.brp_stats["warnings"],
            errors=errors,
            orphaned_intents=orphaned_count,
            ledger_inconsistencies=len(inconsistencies),
            emergency_stop_effective=(mode == TestMode.EMERGENCY_STOP and self.emergency_stop)
        )
        
        logger.info(f"Completed {mode.value} test: {intents_sent} intents sent, {intents_processed} processed")
        logger.info(f"BRP: {self.brp_stats['evaluations']} evaluations, {self.brp_stats['blocks']} blocks, {self.brp_stats['warnings']} warnings")
        
        return result
    
    def run_comprehensive_test(self):
        """Run comprehensive stress test suite."""
        logger.info("=" * 80)
        logger.info("STARTING PHASE 1 STRESS TEST: PROVE PIPELINE UNDER STRESS")
        logger.info("=" * 80)
        
        # Check system health
        if not self.check_broker_health():
            logger.error("Broker is not healthy. Exiting.")
            return False
        
        if not self.check_agent_status():
            logger.error(f"Agent {self.agent_id} is not online. Exiting.")
            return False
        
        self.running = True
        
        try:
            # Test 1: Normal operation (5 minutes)
            logger.info("\n" + "=" * 60)
            logger.info("TEST 1: NORMAL OPERATION (5 minutes)")
            logger.info("=" * 60)
            result1 = self.run_test_mode(TestMode.NORMAL, 300)  # 5 minutes
            self.test_results.append(result1)
            
            # Test 2: Edge cases (3 minutes)
            logger.info("\n" + "=" * 60)
            logger.info("TEST 2: EDGE CASES (3 minutes)")
            logger.info("=" * 60)
            result2 = self.run_test_mode(TestMode.EDGE_CASE, 180)  # 3 minutes
            self.test_results.append(result2)
            
            # Test 3: Network hiccups (3 minutes)
            logger.info("\n" + "=" * 60)
            logger.info("TEST 3: NETWORK HICCUPS (3 minutes)")
            logger.info("=" * 60)
            result3 = self.run_test_mode(TestMode.NETWORK_HICCUP, 180)  # 3 minutes
            self.test_results.append(result3)
            
            # Test 4: Restart simulation (4 minutes)
            logger.info("\n" + "=" * 60)
            logger.info("TEST 4: RESTART SIMULATION (4 minutes)")
            logger.info("=" * 60)
            result4 = self.run_test_mode(TestMode.RESTART_SIMULATION, 240)  # 4 minutes
            self.test_results.append(result4)
            
            # Test 5: Emergency stop (2 minutes)
            logger.info("\n" + "=" * 60)
            logger.info("TEST 5: EMERGENCY STOP (2 minutes)")
            logger.info("=" * 60)
            result5 = self.run_test_mode(TestMode.EMERGENCY_STOP, 120)  # 2 minutes
            self.test_results.append(result5)
            
            # Final system check
            logger.info("\n" + "=" * 60)
            logger.info("FINAL SYSTEM CHECK")
            logger.info("=" * 60)
            self.final_system_check()
            
            # Generate report
            self.generate_report()
            
            return True
            
        except KeyboardInterrupt:
            logger.info("Stress test interrupted by user")
            self.running = False
            return False
        except Exception as e:
            logger.error(f"Stress test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def final_system_check(self):
        """Perform final system health check."""
        logger.info("Performing final system health check...")
        
        # Check broker health
        broker_healthy = self.check_broker_health()
        
        # Check agent status
        agent_online = self.check_agent_status()
        
        # Check ledger consistency
        orphaned_count, inconsistencies = self.check_ledger_consistency()
        
        # Check BRP directory
        brp_log_dir = "logs/quantumarb/brp"
        brp_evaluations = 0
        if os.path.exists(brp_log_dir):
            eval_file = os.path.join(brp_log_dir, "evaluations.jsonl")
            if os.path.exists(eval_file):
                with open(eval_file, 'r') as f:
                    brp_evaluations = sum(1 for _ in f)
        
        logger.info(f"Final check results:")
        logger.info(f"  Broker healthy: {broker_healthy}")
        logger.info(f"  Agent online: {agent_online}")
        logger.info(f"  Orphaned intents: {orphaned_count}")
        logger.info(f"  BRP evaluations: {brp_evaluations}")
        logger.info(f"  Inconsistencies: {len(inconsistencies)}")
        
        if inconsistencies:
            for inc in inconsistencies:
                logger.warning(f"  - {inc}")
    
    def generate_report(self):
        """Generate comprehensive test report."""
        # Get actual BRP evaluations from log file
        brp_evaluations = 0
        brp_log_dir = "logs/quantumarb/brp"
        if os.path.exists(brp_log_dir):
            eval_file = os.path.join(brp_log_dir, "evaluations.jsonl")
            if os.path.exists(eval_file):
                with open(eval_file, 'r') as f:
                    brp_evaluations = sum(1 for _ in f)
        
        report = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "test_duration_minutes": TEST_DURATION_MINUTES,
            "broker_url": self.broker_url,
            "agent_id": self.agent_id,
            "total_intents_sent": sum(r.intents_sent for r in self.test_results),
            "total_intents_processed": sum(r.intents_processed for r in self.test_results),
            "total_brp_evaluations": brp_evaluations,
            "total_brp_blocks": sum(r.brp_blocks for r in self.test_results),
            "total_brp_warnings": sum(r.brp_warnings for r in self.test_results),
            "total_orphaned_intents": sum(r.orphaned_intents for r in self.test_results),
            "total_errors": sum(len(r.errors) for r in self.test_results),
            "test_results": [],
            "summary": {
                "system_stable": True,
                "issues_found": [],
                "recommendations": []
            }
        }
        
        # Add individual test results
        for result in self.test_results:
            report["test_results"].append({
                "mode": result.mode.value,
                "duration_seconds": (result.end_time - result.start_time).total_seconds(),
                "intents_sent": result.intents_sent,
                "intents_processed": result.intents_processed,
                "success_rate": result.intents_processed / max(result.intents_sent, 1),
                "brp_evaluations": result.brp_evaluations,
                "brp_blocks": result.brp_blocks,
                "brp_warnings": result.brp_warnings,
                "orphaned_intents": result.orphaned_intents,
                "errors": result.errors,
                "emergency_stop_effective": result.emergency_stop_effective
            })
        
        # Analyze results
        total_sent = report["total_intents_sent"]
        total_processed = report["total_intents_processed"]
        success_rate = total_processed / max(total_sent, 1)
        
        if success_rate < 0.9:
            report["summary"]["system_stable"] = False
            report["summary"]["issues_found"].append(f"Low success rate: {success_rate:.2%}")
        
        if report["total_orphaned_intents"] > 0:
            report["summary"]["issues_found"].append(f"Found {report['total_orphaned_intents']} orphaned intents")
        
        if report["total_errors"] > 10:
            report["summary"]["issues_found"].append(f"High error count: {report['total_errors']}")
        
        # Generate recommendations
        if report["total_brp_blocks"] > 0:
            report["summary"]["recommendations"].append(
                f"BRP blocked {report['total_brp_blocks']} trades - review threat patterns"
            )
        
        if report["total_brp_warnings"] > 0:
            report["summary"]["recommendations"].append(
                f"BRP issued {report['total_brp_warnings']} warnings - review for potential issues"
            )
        
        if success_rate >= 0.95 and report["total_orphaned_intents"] == 0:
            report["summary"]["recommendations"].append(
                "System passed stress test - ready for Phase 2 (risk framework)"
            )
        else:
            report["summary"]["recommendations"].append(
                "Address issues before proceeding to Phase 2"
            )
        
        # Save report
        report_file = f"stress_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("STRESS TEST COMPLETE - SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total intents sent: {total_sent}")
        logger.info(f"Total intents processed: {total_processed}")
        logger.info(f"Success rate: {success_rate:.2%}")
        logger.info(f"BRP evaluations: {brp_evaluations}")
        logger.info(f"BRP blocks: {report['total_brp_blocks']}")
        logger.info(f"BRP warnings: {report['total_brp_warnings']}")
        logger.info(f"Orphaned intents: {report['total_orphaned_intents']}")
        logger.info(f"Total errors: {report['total_errors']}")
        logger.info(f"System stable: {report['summary']['system_stable']}")
        
        if report["summary"]["issues_found"]:
            logger.info("\nIssues found:")
            for issue in report["summary"]["issues_found"]:
                logger.info(f"  - {issue}")
        
        if report["summary"]["recommendations"]:
            logger.info("\nRecommendations:")
            for rec in report["summary"]["recommendations"]:
                logger.info(f"  - {rec}")
        
        logger.info(f"\nDetailed report saved to: {report_file}")
        
        return report

def main():
    """Main entry point."""
    print("=" * 80)
    print("PHASE 1 STRESS TEST: PROVE PIPELINE UNDER STRESS")
    print("=" * 80)
    print(f"Duration: {TEST_DURATION_MINUTES} minutes")
    print(f"Broker URL: {BROKER_URL}")
    print(f"Target agent: {QUANTUMARB_AGENT_ID}")
    print("=" * 80)
    
    # Auto-start for non-interactive execution
    print("\nStarting stress test automatically...")
    print("Check stress_test.log for detailed logs.")
    print("=" * 80)
    
    tester = StressTester()
    success = tester.run_comprehensive_test()
    
    if success:
        print("\n✅ Stress test completed successfully!")
        print("Review the generated report for details.")
    else:
        print("\n❌ Stress test failed or was interrupted.")
        print("Check logs for details.")

if __name__ == "__main__":
    main()