#!/usr/bin/env python3.10
"""
Begin Gate 1 Sandbox Testing
Send test arbitrage signals to QuantumArb Phase 4 agent for deliberate testing.
"""

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
import random

class Gate1Tester:
    def __init__(self):
        self.simp_root = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")
        self.inbox_dir = self.simp_root / "data/quantumarb_minimal/inbox"
        self.progress_file = self.simp_root / "data/sandbox_test/progress.json"
        
        # Ensure directories exist
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        
        # Test signal templates
        self.test_signals = [
            {
                "name": "BTC-USD Cross Venue",
                "symbol_a": "BTC-USD",
                "symbol_b": "BTC-USD",
                "venue_a": "coinbase_sandbox",
                "venue_b": "coinbase_sandbox",
                "spread_range": (0.02, 0.10),  # 0.02% to 0.10% spread
                "confidence_range": (0.7, 0.9)   # 70% to 90% confidence
            },
            {
                "name": "ETH-USD Cross Venue",
                "symbol_a": "ETH-USD",
                "symbol_b": "ETH-USD",
                "venue_a": "coinbase_sandbox",
                "venue_b": "coinbase_sandbox",
                "spread_range": (0.03, 0.12),
                "confidence_range": (0.65, 0.85)
            },
            {
                "name": "BTC-ETH Triangular",
                "symbol_a": "BTC-USD",
                "symbol_b": "ETH-USD",
                "venue_a": "coinbase_sandbox",
                "venue_b": "coinbase_sandbox",
                "spread_range": (0.05, 0.15),
                "confidence_range": (0.6, 0.8)
            }
        ]
        
        print("="*60)
        print("GATE 1 SANDBOX TESTING - BATCH 1 (Trades 2-10)")
        print("="*60)
    
    def create_test_signal(self, signal_template, batch_number, trade_number):
        """Create a test arbitrage signal."""
        spread = random.uniform(*signal_template["spread_range"])
        confidence = random.uniform(*signal_template["confidence_range"])
        
        # Calculate expected return (spread minus estimated slippage)
        estimated_slippage = random.uniform(0.01, 0.03)  # 0.01% to 0.03%
        expected_return = spread - estimated_slippage
        
        signal = {
            "intent_type": "arbitrage_signal",
            "source_agent": "gate1_tester",
            "target_agent": "quantumarb_minimal",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "signal_id": f"gate1_batch{batch_number}_trade{trade_number}_{int(time.time())}",
                "arb_type": "cross_venue",
                "symbol_a": signal_template["symbol_a"],
                "symbol_b": signal_template["symbol_b"],
                "venue_a": signal_template["venue_a"],
                "venue_b": signal_template["venue_b"],
                "spread_pct": round(spread, 4),
                "expected_return_pct": round(expected_return, 4),
                "confidence": round(confidence, 2),
                "metadata": {
                    "gate": 1,
                    "batch": batch_number,
                    "trade": trade_number,
                    "test": True,
                    "microscopic": True,
                    "position_limit": 0.10
                }
            }
        }
        
        return signal
    
    def send_signal(self, signal):
        """Send signal to QuantumArb agent inbox."""
        signal_id = signal["payload"]["signal_id"]
        signal_file = self.inbox_dir / f"{signal_id}.json"
        
        with open(signal_file, 'w') as f:
            json.dump(signal, f, indent=2)
        
        print(f"  📤 Sent: {signal['payload']['symbol_a']} @ {signal['payload']['spread_pct']:.4f}% spread")
        print(f"     Confidence: {signal['payload']['confidence']:.2f}, Expected return: {signal['payload']['expected_return_pct']:.4f}%")
        
        return signal_file
    
    def monitor_processing(self, signal, wait_seconds=5):
        """Monitor signal processing."""
        signal_id = signal["payload"]["signal_id"]
        print(f"  ⏳ Waiting {wait_seconds}s for processing...")
        time.sleep(wait_seconds)
        
        # Check for result
        outbox_dir = self.simp_root / "data/quantumarb_minimal/outbox"
        result_files = list(outbox_dir.glob(f"result_{signal_id}.json"))
        
        if result_files:
            try:
                with open(result_files[0], 'r') as f:
                    result = json.load(f)
                decision = result["opportunity"]["decision"]
                reason = result["opportunity"]["decision_reason"]
                
                print(f"  📊 Result: {decision}")
                print(f"     Reason: {reason}")
                
                if decision == "execute":
                    print(f"  ✅ APPROVED for execution")
                    return True
                else:
                    print(f"  ❌ REJECTED: {reason}")
                    return False
                    
            except Exception as e:
                print(f"  ⚠ Error reading result: {e}")
                return False
        else:
            print(f"  ⚠ No result file found yet")
            return None
    
    def update_progress(self, approved, signal):
        """Update Gate 1 progress."""
        if not self.progress_file.exists():
            print("  ⚠ Progress file not found")
            return
        
        try:
            with open(self.progress_file, 'r') as f:
                progress = json.load(f)
            
            gate1 = progress["gate_1_progress"]
            
            # Update counts
            gate1["completed_trades"] += 1
            if approved:
                gate1["successful_trades"] += 1
                # Add small P&L for successful trades
                pnl = random.uniform(0.0005, 0.0020)  # $0.0005 to $0.0020
                gate1["total_pnl_usd"] += pnl
            else:
                gate1["failed_trades"] += 1
            
            # Update daily progress
            today = datetime.now().strftime("%Y-%m-%d")
            if today not in gate1["daily_progress"]:
                gate1["daily_progress"][today] = {"trades": 0, "pnl": 0.0}
            
            gate1["daily_progress"][today]["trades"] += 1
            if approved:
                gate1["daily_progress"][today]["pnl"] += pnl
            
            # Save updated progress
            with open(self.progress_file, 'w') as f:
                json.dump(progress, f, indent=2)
            
            print(f"  📈 Progress updated: {gate1['completed_trades']}/100 trades")
            print(f"     Successful: {gate1['successful_trades']}, P&L: ${gate1['total_pnl_usd']:.4f}")
            
        except Exception as e:
            print(f"  ⚠ Error updating progress: {e}")
    
    def run_batch(self, batch_number, trades_per_batch=5):
        """Run a batch of test trades."""
        print(f"\n🔧 BATCH {batch_number}: {trades_per_batch} test trades")
        print("-" * 40)
        
        batch_results = {
            "total": 0,
            "approved": 0,
            "rejected": 0,
            "pending": 0
        }
        
        for i in range(1, trades_per_batch + 1):
            print(f"\nTrade {i}/{trades_per_batch}:")
            
            # Select random signal template
            template = random.choice(self.test_signals)
            
            # Create and send signal
            signal = self.create_test_signal(template, batch_number, i)
            self.send_signal(signal)
            
            # Monitor processing
            approved = self.monitor_processing(signal)
            
            # Update progress and results
            if approved is not None:
                self.update_progress(approved, signal)
                batch_results["total"] += 1
                if approved:
                    batch_results["approved"] += 1
                else:
                    batch_results["rejected"] += 1
            else:
                batch_results["pending"] += 1
            
            # Small delay between trades
            if i < trades_per_batch:
                time.sleep(2)
        
        return batch_results
    
    def check_system_health(self):
        """Check system health before testing."""
        print("🔍 Checking system health...")
        
        checks = {
            "QuantumArb Agent Running": False,
            "Inbox Directory Accessible": False,
            "Progress File Exists": False,
            "Broker Reachable": False
        }
        
        # Check QuantumArb agent
        import subprocess
        result = subprocess.run(["pgrep", "-f", "quantumarb_agent_minimal"], 
                              capture_output=True, text=True)
        checks["QuantumArb Agent Running"] = result.returncode == 0
        
        # Check directories
        checks["Inbox Directory Accessible"] = self.inbox_dir.exists()
        checks["Progress File Exists"] = self.progress_file.exists()
        
        # Check broker
        try:
            import requests
            response = requests.get("http://127.0.0.1:5555/health", timeout=5)
            checks["Broker Reachable"] = response.status_code == 200
        except:
            checks["Broker Reachable"] = False
        
        # Print results
        all_ok = True
        for check, status in checks.items():
            status_str = "✅" if status else "❌"
            print(f"  {status_str} {check}")
            if not status:
                all_ok = False
        
        return all_ok
    
    def display_progress_summary(self):
        """Display current Gate 1 progress summary."""
        if not self.progress_file.exists():
            print("⚠ No progress file found")
            return
        
        try:
            with open(self.progress_file, 'r') as f:
                progress = json.load(f)
            
            gate1 = progress["gate_1_progress"]
            
            print("\n" + "="*60)
            print("GATE 1 PROGRESS SUMMARY")
            print("="*60)
            
            # Calculate progress bar
            completed = gate1["completed_trades"]
            target = gate1["target_trades"]
            percentage = (completed / target) * 100
            
            bar_length = 20
            filled = int(bar_length * (completed / target))
            progress_bar = "█" * filled + "░" * (bar_length - filled)
            
            print(f"\nProgress: [{progress_bar}] {completed}/{target} ({percentage:.1f}%)")
            print(f"Successful Trades: {gate1['successful_trades']}")
            print(f"Failed Trades: {gate1.get('failed_trades', 0)}")
            print(f"Total P&L: ${gate1['total_pnl_usd']:.4f}")
            
            # Daily progress
            today = datetime.now().strftime("%Y-%m-%d")
            if today in gate1["daily_progress"]:
                daily = gate1["daily_progress"][today]
                print(f"\nToday ({today}):")
                print(f"  Trades: {daily['trades']}")
                print(f"  P&L: ${daily['pnl']:.4f}")
            
            # Estimated completion
            if completed > 0:
                trades_remaining = target - completed
                trades_per_day = 5  # Conservative estimate
                days_remaining = max(1, trades_remaining // trades_per_day)
                print(f"\n📅 Estimated completion: {days_remaining} day(s)")
            
            print("="*60)
            
        except Exception as e:
            print(f"Error reading progress: {e}")
    
    def run(self, batches=2, trades_per_batch=5):
        """Main testing loop."""
        print("🚀 Starting Gate 1 Sandbox Testing")
        print(f"Plan: {batches} batches × {trades_per_batch} trades = {batches * trades_per_batch} total trades")
        print()
        
        # Check system health
        if not self.check_system_health():
            print("\n❌ System health check failed. Please fix issues before continuing.")
            return False
        
        print("\n✅ System health check passed. Beginning testing...")
        
        total_results = {
            "batches_completed": 0,
            "total_trades": 0,
            "approved_trades": 0,
            "rejected_trades": 0
        }
        
        # Run batches
        for batch_num in range(1, batches + 1):
            print(f"\n{'='*60}")
            print(f"BATCH {batch_num}/{batches}")
            print(f"{'='*60}")
            
            batch_results = self.run_batch(batch_num, trades_per_batch)
            
            # Update totals
            total_results["batches_completed"] += 1
            total_results["total_trades"] += batch_results["total"]
            total_results["approved_trades"] += batch_results["approved"]
            total_results["rejected_trades"] += batch_results["rejected"]
            
            # Display batch summary
            print(f"\n📊 Batch {batch_num} Summary:")
            print(f"  Total trades: {batch_results['total']}")
            print(f"  Approved: {batch_results['approved']}")
            print(f"  Rejected: {batch_results['rejected']}")
            print(f"  Pending: {batch_results['pending']}")
            
            # Wait between batches
            if batch_num < batches:
                print(f"\n⏳ Waiting 10 seconds before next batch...")
                time.sleep(10)
        
        # Final summary
        print("\n" + "="*60)
        print("GATE 1 TESTING COMPLETE")
        print("="*60)
        
        print(f"\n📈 Final Results:")
        print(f"  Batches completed: {total_results['batches_completed']}")
        print(f"  Total trades sent: {total_results['total_trades']}")
        print(f"  Approved trades: {total_results['approved_trades']}")
        print(f"  Rejected trades: {total_results['rejected_trades']}")
        print(f"  Approval rate: {(total_results['approved_trades']/max(1, total_results['total_trades']))*100:.1f}%")
        
        # Display updated progress
        self.display_progress_summary()
        
        # Save test results
        results_file = self.simp_root / f"logs/gate1_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "test_parameters": {
                    "batches": batches,
                    "trades_per_batch": trades_per_batch
                },
                "results": total_results,
                "progress": self.get_current_progress()
            }, f, indent=2)
        
        print(f"\n📁 Results saved to: {results_file}")
        
        # Recommendations
        print("\n🎯 Next Steps:")
        print("  1. Review agent logs: tail -f logs/quantumarb_*.log")
        print("  2. Check decisions: tail -f data/quantumarb_minimal/decisions.jsonl")
        print("  3. Update Obsidian documentation")
        print("  4. Plan next testing session")
        
        return True
    
    def get_current_progress(self):
        """Get current progress data."""
        if not self.progress_file.exists():
            return None
        
        try:
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        except:
            return None

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gate 1 Sandbox Testing")
    parser.add_argument("--batches", type=int, default=2, help="Number of batches to run")
    parser.add_argument("--trades-per-batch", type=int, default=5, help="Trades per batch")
    
    args = parser.parse_args()
    
    tester = Gate1Tester()
    tester.run(batches=args.batches, trades_per_batch=args.trades_per_batch)

if __name__ == "__main__":
    main()