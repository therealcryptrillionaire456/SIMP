#!/usr/bin/env python3.10
"""
Test Risk Framework Integration

Re-run sandbox with exact risk limits enforced to ensure the code matches the risk spec.
This script tests the risk framework integration with the QuantumArb agent.
"""

import json
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import risk framework
from risk_framework_config import RiskFramework, RiskLevel, AssetClass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('risk_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RiskFrameworkTester:
    """Test the risk framework integration."""
    
    def __init__(self, config_file: str = "risk_config_conservative.json"):
        self.risk_framework = RiskFramework(config_file)
        self.test_results = []
        self.trade_history = []
        
    def simulate_trading_day(self, num_trades: int = 50) -> Dict:
        """Simulate a trading day with the risk framework."""
        logger.info(f"Simulating trading day with {num_trades} potential trades")
        
        day_results = {
            "date": datetime.now().isoformat(),
            "config_file": self.risk_framework.risk_params.risk_level,
            "account_size": self.risk_framework.risk_params.account_size_usd,
            "trades_attempted": 0,
            "trades_allowed": 0,
            "trades_blocked": 0,
            "blocked_reasons": {},
            "daily_pnl": 0.0,
            "max_exposure": 0.0,
            "risk_limits_triggered": []
        }
        
        # Reset daily counters
        self.risk_framework.reset_daily()
        
        # Simulate trades
        symbols = ["BTC-USD", "ETH-USD", "SOL-USD", "SPY", "AAPL", "EUR-USD"]
        asset_classes = {
            "BTC-USD": AssetClass.CRYPTO,
            "ETH-USD": AssetClass.CRYPTO,
            "SOL-USD": AssetClass.CRYPTO,
            "SPY": AssetClass.STOCKS,
            "AAPL": AssetClass.STOCKS,
            "EUR-USD": AssetClass.FOREX
        }
        
        for i in range(num_trades):
            symbol = random.choice(symbols)
            asset_class = asset_classes[symbol]
            
            # Generate random trade parameters
            stop_loss_percent = random.uniform(1.0, 10.0)
            position_size = self.risk_framework.calculate_position_size(
                symbol, stop_loss_percent, asset_class
            )
            
            # Randomly decide if this is a buy or sell
            is_buy = random.random() > 0.3
            if not is_buy:
                position_size = -position_size  # Negative for sells
            
            day_results["trades_attempted"] += 1
            
            # Check if trade is allowed
            allowed, reason = self.risk_framework.check_trade_allowed(
                symbol, abs(position_size), asset_class
            )
            
            if allowed:
                day_results["trades_allowed"] += 1
                
                # Simulate trade execution with random P&L
                pnl = random.uniform(-position_size * 0.1, position_size * 0.15)
                
                # Record trade
                self.risk_framework.record_trade(symbol, abs(position_size), pnl)
                day_results["daily_pnl"] += pnl
                
                # Track max exposure
                current_exposure = sum(self.risk_framework.current_exposure.values())
                day_results["max_exposure"] = max(day_results["max_exposure"], current_exposure)
                
                # Log trade
                trade = {
                    "symbol": symbol,
                    "position_size": position_size,
                    "pnl": pnl,
                    "timestamp": datetime.now().isoformat(),
                    "allowed": True
                }
                self.trade_history.append(trade)
                
                # Check if any risk limits were triggered
                if self.risk_framework.emergency_stop_triggered:
                    day_results["risk_limits_triggered"].append("Emergency stop triggered")
                    logger.warning(f"Emergency stop triggered at trade {i+1}")
                    break
                    
                if self.risk_framework.daily_pnl <= -self.risk_framework.risk_params.daily_loss_limit_usd:
                    day_results["risk_limits_triggered"].append("Daily loss limit reached")
                    logger.warning(f"Daily loss limit reached at trade {i+1}")
                    break
                    
            else:
                day_results["trades_blocked"] += 1
                day_results["blocked_reasons"][reason] = day_results["blocked_reasons"].get(reason, 0) + 1
                
                # Log blocked trade
                trade = {
                    "symbol": symbol,
                    "position_size": position_size,
                    "timestamp": datetime.now().isoformat(),
                    "allowed": False,
                    "reason": reason
                }
                self.trade_history.append(trade)
            
            # Random delay between trades
            time.sleep(0.01)  # Small delay for simulation
        
        # Calculate statistics
        day_results["success_rate"] = day_results["trades_allowed"] / max(day_results["trades_attempted"], 1)
        day_results["exposure_percent"] = (day_results["max_exposure"] / self.risk_framework.risk_params.account_size_usd) * 100
        
        logger.info(f"Day complete: {day_results['trades_allowed']}/{day_results['trades_attempted']} trades allowed")
        logger.info(f"Daily P&L: ${day_results['daily_pnl']:.2f}")
        logger.info(f"Max exposure: ${day_results['max_exposure']:.2f} ({day_results['exposure_percent']:.1f}%)")
        
        return day_results
    
    def test_position_sizing(self):
        """Test position sizing calculations."""
        logger.info("Testing position sizing calculations...")
        
        test_cases = [
            ("BTC-USD", AssetClass.CRYPTO, 5.0),
            ("ETH-USD", AssetClass.CRYPTO, 3.0),
            ("SPY", AssetClass.STOCKS, 2.0),
            ("AAPL", AssetClass.STOCKS, 4.0),
            ("EUR-USD", AssetClass.FOREX, 1.5),
        ]
        
        results = []
        for symbol, asset_class, stop_loss in test_cases:
            position_size = self.risk_framework.calculate_position_size(
                symbol, stop_loss, asset_class
            )
            
            # Check against limits
            max_risk = min(
                self.risk_framework.risk_params.max_risk_per_trade_usd,
                self.risk_framework.risk_params.account_size_usd * 
                self.risk_framework.risk_params.max_risk_per_trade_percent / 100
            )
            
            # Expected position size based on risk
            expected_size = max_risk / (stop_loss / 100)
            
            # Apply volatility multiplier
            if asset_class in self.risk_framework.asset_class_limits:
                multiplier = self.risk_framework.asset_class_limits[asset_class].volatility_multiplier
                expected_size *= multiplier
            
            # Apply slippage and fee buffer
            expected_size *= (1 - self.risk_framework.risk_params.fee_buffer_percent / 100)
            expected_size *= (1 - self.risk_framework.risk_params.max_slippage_percent / 100)
            
            # Check individual symbol limits
            if symbol in self.risk_framework.position_limits:
                limit = self.risk_framework.position_limits[symbol]
                expected_size = min(expected_size, limit.max_position_usd)
            
            expected_size = round(expected_size, 2)
            
            result = {
                "symbol": symbol,
                "asset_class": asset_class.value,
                "stop_loss_percent": stop_loss,
                "calculated_position": position_size,
                "expected_position": expected_size,
                "match": abs(position_size - expected_size) < 0.01,
                "max_risk_per_trade": max_risk
            }
            results.append(result)
            
            logger.info(f"{symbol}: stop_loss={stop_loss}% -> position=${position_size:.2f} "
                       f"(expected=${expected_size:.2f}, match={result['match']})")
        
        return results
    
    def test_risk_limits(self):
        """Test that risk limits are properly enforced."""
        logger.info("Testing risk limit enforcement...")
        
        # Test 1: Daily loss limit
        logger.info("Test 1: Daily loss limit")
        self.risk_framework.reset_daily()
        
        # Simulate losses until limit is reached
        symbol = "BTC-USD"
        asset_class = AssetClass.CRYPTO
        position_size = 100.0
        
        losses = []
        while True:
            allowed, reason = self.risk_framework.check_trade_allowed(
                symbol, position_size, asset_class
            )
            
            if not allowed:
                logger.info(f"Trade blocked: {reason}")
                losses.append({
                    "daily_pnl": self.risk_framework.daily_pnl,
                    "loss_limit": self.risk_framework.risk_params.daily_loss_limit_usd,
                    "blocked": True,
                    "reason": reason
                })
                break
            
            # Record a loss
            loss = -position_size * 0.1  # 10% loss
            self.risk_framework.record_trade(symbol, position_size, loss)
            losses.append({
                "daily_pnl": self.risk_framework.daily_pnl,
                "loss_limit": self.risk_framework.risk_params.daily_loss_limit_usd,
                "blocked": False
            })
        
        # Test 2: Max concurrent positions
        logger.info("Test 2: Max concurrent positions")
        self.risk_framework.reset_daily()
        self.risk_framework.current_exposure.clear()
        
        max_positions = self.risk_framework.risk_params.max_concurrent_positions
        symbols = [f"TEST{i}" for i in range(max_positions + 2)]
        
        position_checks = []
        for i, symbol in enumerate(symbols):
            allowed, reason = self.risk_framework.check_trade_allowed(
                symbol, 100.0, AssetClass.CRYPTO
            )
            
            if allowed:
                self.risk_framework.current_exposure[symbol] = 100.0
            
            position_checks.append({
                "symbol": symbol,
                "position_count": len(self.risk_framework.current_exposure),
                "max_positions": max_positions,
                "allowed": allowed,
                "reason": reason if not allowed else None
            })
            
            logger.info(f"Position {i+1}: {symbol} - allowed={allowed}, "
                       f"positions={len(self.risk_framework.current_exposure)}/{max_positions}")
        
        return {
            "daily_loss_test": losses,
            "concurrent_positions_test": position_checks
        }
    
    def run_comprehensive_test(self):
        """Run comprehensive risk framework tests."""
        logger.info("=" * 80)
        logger.info("RUNNING COMPREHENSIVE RISK FRAMEWORK TESTS")
        logger.info("=" * 80)
        
        test_results = {
            "timestamp": datetime.now().isoformat(),
            "risk_level": self.risk_framework.risk_params.risk_level,
            "account_size": self.risk_framework.risk_params.account_size_usd,
            "tests": {}
        }
        
        try:
            # Test 1: Position sizing
            logger.info("\n" + "=" * 60)
            logger.info("TEST 1: POSITION SIZING CALCULATIONS")
            logger.info("=" * 60)
            sizing_results = self.test_position_sizing()
            test_results["tests"]["position_sizing"] = sizing_results
            
            # Check if all calculations match
            all_match = all(r["match"] for r in sizing_results)
            if all_match:
                logger.info("✅ All position sizing calculations correct")
            else:
                logger.warning("❌ Some position sizing calculations incorrect")
            
            # Test 2: Risk limit enforcement
            logger.info("\n" + "=" * 60)
            logger.info("TEST 2: RISK LIMIT ENFORCEMENT")
            logger.info("=" * 60)
            limit_results = self.test_risk_limits()
            test_results["tests"]["risk_limits"] = limit_results
            
            # Test 3: Simulated trading day
            logger.info("\n" + "=" * 60)
            logger.info("TEST 3: SIMULATED TRADING DAY")
            logger.info("=" * 60)
            trading_day = self.simulate_trading_day(100)
            test_results["tests"]["trading_day"] = trading_day
            
            # Test 4: Emergency stop
            logger.info("\n" + "=" * 60)
            logger.info("TEST 4: EMERGENCY STOP FUNCTIONALITY")
            logger.info("=" * 60)
            
            # Trigger emergency stop via excessive drawdown
            self.risk_framework.reset_daily()
            self.risk_framework.current_exposure.clear()
            
            # Simulate large loss to trigger emergency stop
            # We need to record trades to trigger the emergency stop check
            symbol = "BTC-USD"
            asset_class = AssetClass.CRYPTO
            
            # First, record a positive trade to set max_daily_pnl
            self.risk_framework.record_trade(symbol, 10.0, 1000.0)  # $1000 profit
            
            # Then record a large loss that exceeds max drawdown
            # max_drawdown_usd = 1000.0 in conservative config
            # We need a loss that makes drawdown >= 1000.0
            # Current: max_daily_pnl = 1000.0, daily_pnl = 1000.0
            # Record loss of 1500.0: daily_pnl = -500.0, drawdown = 1500.0
            self.risk_framework.record_trade(symbol, 10.0, -1500.0)
            
            # Now check if emergency stop was triggered
            allowed, reason = self.risk_framework.check_trade_allowed(
                symbol, 5.0, asset_class  # Use small position within limits
            )
            
            emergency_test = {
                "emergency_stop_triggered": self.risk_framework.emergency_stop_triggered,
                "trade_allowed": allowed,
                "reason": reason,
                "expected": not allowed and "Emergency stop" in reason
            }
            
            test_results["tests"]["emergency_stop"] = emergency_test
            
            if emergency_test["expected"]:
                logger.info("✅ Emergency stop functionality working")
            else:
                logger.warning("❌ Emergency stop functionality not working as expected")
            
            # Generate summary
            logger.info("\n" + "=" * 80)
            logger.info("TEST SUMMARY")
            logger.info("=" * 80)
            
            summary = self.generate_summary(test_results)
            test_results["summary"] = summary
            
            # Save results
            report_file = f"risk_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w') as f:
                json.dump(test_results, f, indent=2, default=str)
            
            logger.info(f"\nDetailed report saved to: {report_file}")
            
            return test_results
            
        except Exception as e:
            logger.error(f"Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def generate_summary(self, test_results: Dict) -> Dict:
        """Generate test summary."""
        summary = {
            "overall_passed": True,
            "issues_found": [],
            "recommendations": []
        }
        
        # Check position sizing
        sizing_tests = test_results["tests"].get("position_sizing", [])
        if sizing_tests:
            failed = [r for r in sizing_tests if not r["match"]]
            if failed:
                summary["overall_passed"] = False
                summary["issues_found"].append(
                    f"{len(failed)} position sizing calculations incorrect"
                )
        
        # Check trading day results
        trading_day = test_results["tests"].get("trading_day", {})
        if trading_day:
            success_rate = trading_day.get("success_rate", 0)
            if success_rate < 0.5:
                summary["issues_found"].append(
                    f"Low trade success rate: {success_rate:.1%}"
                )
            
            exposure_percent = trading_day.get("exposure_percent", 0)
            max_allowed = self.risk_framework.risk_params.max_gross_exposure_percent
            if exposure_percent > max_allowed:
                summary["overall_passed"] = False
                summary["issues_found"].append(
                    f"Exposure exceeded limits: {exposure_percent:.1f}% > {max_allowed}%"
                )
        
        # Check emergency stop
        emergency_test = test_results["tests"].get("emergency_stop", {})
        if not emergency_test.get("expected", False):
            summary["overall_passed"] = False
            summary["issues_found"].append("Emergency stop not working correctly")
        
        # Generate recommendations
        if summary["overall_passed"]:
            summary["recommendations"].append(
                "Risk framework passed all tests - ready for integration with QuantumArb agent"
            )
            summary["recommendations"].append(
                "Proceed to Phase 3: Harden monitoring and alerting"
            )
        else:
            summary["recommendations"].append(
                "Address issues before integrating with production system"
            )
            summary["recommendations"].append(
                "Review risk parameters and adjust as needed"
            )
        
        # Log summary
        logger.info(f"Overall passed: {summary['overall_passed']}")
        
        if summary["issues_found"]:
            logger.info("Issues found:")
            for issue in summary["issues_found"]:
                logger.info(f"  - {issue}")
        
        if summary["recommendations"]:
            logger.info("Recommendations:")
            for rec in summary["recommendations"]:
                logger.info(f"  - {rec}")
        
        return summary

def main():
    """Main entry point."""
    print("=" * 80)
    print("PHASE 2: RISK FRAMEWORK TESTING")
    print("=" * 80)
    print("Testing risk limits and position sizing calculations.")
    print("This ensures the code matches the risk specification before real capital.")
    print("=" * 80)
    
    # Auto-select conservative for testing
    print("\nUsing conservative risk configuration for testing...")
    config_file = "risk_config_conservative.json"
    
    if not os.path.exists(config_file):
        print(f"\nConfig file {config_file} not found.")
        print("First run: python3.10 risk_framework_config.py to create config files.")
        return
    
    print(f"\nUsing config: {config_file}")
    print("=" * 80)
    
    # Run tests
    tester = RiskFrameworkTester(config_file)
    results = tester.run_comprehensive_test()
    
    if results:
        summary = results.get("summary", {})
        if summary.get("overall_passed", False):
            print("\n✅ RISK FRAMEWORK PASSED ALL TESTS")
            print("The system is ready for integration with QuantumArb agent.")
        else:
            print("\n❌ RISK FRAMEWORK HAS ISSUES")
            print("Review the test report and address issues before proceeding.")
    else:
        print("\n❌ TEST FAILED")
        print("Check risk_test.log for details.")

if __name__ == "__main__":
    main()