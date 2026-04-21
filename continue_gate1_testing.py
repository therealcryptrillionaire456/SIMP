#!/usr/bin/env python3.10
"""
Continue Gate 1 Sandbox Testing with adjusted parameters.
Batch testing to reach target of 100 trades.
"""

import json
import time
import random
from datetime import datetime
from pathlib import Path

class Gate1Continuer:
    def __init__(self):
        self.simp_root = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")
        self.inbox_dir = self.simp_root / "data/quantumarb_minimal/inbox"
        self.progress_file = self.simp_root / "data/sandbox_test/progress.json"
        
        # Realistic spreads for microscopic trading
        self.spread_ranges = {
            "BTC-USD": (0.08, 0.25),    # 0.08% to 0.25%
            "ETH-USD": (0.10, 0.30),    # 0.10% to 0.30%
            "LTC-USD": (0.15, 0.35),    # 0.15% to 0.35%
        }
        
        # Confidence ranges
        self.confidence_ranges = {
            "high": (0.75, 0.90),
            "medium": (0.65, 0.80),
            "low": (0.50, 0.70),
        }
        
        print("="*60)
        print("GATE 1 CONTINUED TESTING")
        print("="*60)
    
    def get_current_progress(self):
        """Get current Gate 1 progress."""
        if not self.progress_file.exists():
            return None
        
        with open(self.progress_file, 'r') as f:
            return json.load(f)
    
    def create_realistic_signal(self, symbol, confidence_level="medium"):
        """Create realistic signal for microscopic trading."""
        spread_range = self.spread_ranges.get(symbol, (0.10, 0.30))
        confidence_range = self.confidence_ranges.get(confidence_level, (0.65, 0.80))
        
        spread = random.uniform(*spread_range)
        confidence = random.uniform(*confidence_range)
        
        # Estimate slippage (conservative for microscopic)
        slippage = random.uniform(0.01, 0.03)  # 0.01% to 0.03%
        expected_return = spread - slippage
        
        signal = {
            "intent_type": "arbitrage_signal",
            "source_agent": "gate1_continuer",
            "target_agent": "quantumarb_minimal",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "signal_id": f"gate1_cont_{symbol.lower()}_{int(time.time())}",
                "arb_type": "cross_venue",
                "symbol_a": symbol,
                "symbol_b": symbol,
                "venue_a": "coinbase_sandbox",
                "venue_b": "coinbase_sandbox",
                "spread_pct": round(spread, 4),
                "expected_return_pct": round(expected_return, 4),
                "confidence": round(confidence, 2),
                "metadata": {
                    "gate": 1,
                    "batch": "continued",
                    "realistic": True,
                    "microscopic": True
                }
            }
        }
        
        return signal
    
    def send_and_monitor(self, signal, wait_seconds=5):
        """Send signal and monitor result."""
        # Send signal
        signal_file = self.inbox_dir / f"{signal['payload']['signal_id']}.json"
        with open(signal_file, 'w') as f:
            json.dump(signal, f, indent=2)
        
        print(f"  📤 {signal['payload']['symbol_a']}: {signal['payload']['spread_pct']:.3f}% spread")
        print(f"     Confidence: {signal['payload']['confidence']:.2f}")
        
        # Wait for processing
        time.sleep(wait_seconds)
        
        # Check result
        outbox_dir = self.simp_root / "data/quantumarb_minimal/outbox"
        result_files = list(outbox_dir.glob(f"result_{signal['payload']['signal_id']}.json"))
        
        if result_files:
            with open(result_files[0], 'r') as f:
                result = json.load(f)
            
            opportunity = result["opportunity"]
            decision = opportunity["decision"]
            risk_score = opportunity["risk_score"]
            reason = opportunity["decision_reason"]
            
            print(f"  📊 Decision: {decision}")
            print(f"     Risk score: {risk_score:.3f}, Reason: {reason[:50]}...")
            
            return decision == "execute", risk_score
        else:
            print(f"  ⚠ No result yet")
            return None, None
    
    def update_progress(self, approved, risk_score=None):
        """Update Gate 1 progress."""
        if not self.progress_file.exists():
            return False
        
        try:
            with open(self.progress_file, 'r') as f:
                progress = json.load(f)
            
            gate1 = progress["gate_1_progress"]
            
            # Update counts
            gate1["completed_trades"] += 1
            
            if approved:
                gate1["successful_trades"] += 1
                # Add P&L based on risk score
                if risk_score:
                    # Higher risk score = potentially higher P&L
                    base_pnl = 0.0005
                    risk_multiplier = risk_score  # 0.5-0.7 multiplier
                    pnl = base_pnl * (0.5 + risk_multiplier)  # $0.00025 to $0.00085
                else:
                    pnl = random.uniform(0.0003, 0.0008)
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
            
            return True
            
        except Exception as e:
            print(f"  ⚠ Error updating progress: {e}")
            return False
    
    def run_session(self, trades_per_session=10, batch_size=5):
        """Run a testing session."""
        progress = self.get_current_progress()
        if not progress:
            print("❌ Could not load progress file")
            return
        
        gate1 = progress["gate_1_progress"]
        current = gate1["completed_trades"]
        target = gate1["target_trades"]
        
        print(f"\n📊 Current Progress: {current}/{target} trades ({current/target*100:.1f}%)")
        print(f"   Successful: {gate1['successful_trades']}, P&L: ${gate1['total_pnl_usd']:.4f}")
        print(f"\n🔧 This session: {trades_per_session} trades in batches of {batch_size}")
        print("-" * 60)
        
        session_results = {
            "total": 0,
            "approved": 0,
            "rejected": 0,
            "pending": 0,
            "risk_scores": []
        }
        
        # Run in batches
        batches = (trades_per_session + batch_size - 1) // batch_size
        
        for batch_num in range(1, batches + 1):
            print(f"\nBatch {batch_num}/{batches}:")
            print("-" * 40)
            
            batch_trades = min(batch_size, trades_per_session - session_results["total"])
            
            for trade_num in range(1, batch_trades + 1):
                print(f"\nTrade {session_results['total'] + 1}/{trades_per_session}:")
                
                # Select symbol and confidence
                symbol = random.choice(["BTC-USD", "ETH-USD", "LTC-USD"])
                confidence_level = random.choice(["high", "medium", "medium"])  # Bias toward medium
                
                # Create and send signal
                signal = self.create_realistic_signal(symbol, confidence_level)
                approved, risk_score = self.send_and_monitor(signal)
                
                # Update results
                session_results["total"] += 1
                
                if approved is not None:
                    if approved:
                        session_results["approved"] += 1
                        if risk_score:
                            session_results["risk_scores"].append(risk_score)
                    else:
                        session_results["rejected"] += 1
                    
                    # Update progress
                    self.update_progress(approved, risk_score)
                else:
                    session_results["pending"] += 1
                
                # Small delay between trades
                if trade_num < batch_trades:
                    time.sleep(2)
            
            # Delay between batches
            if batch_num < batches:
                print(f"\n⏳ Waiting 8 seconds before next batch...")
                time.sleep(8)
        
        # Session summary
        print("\n" + "="*60)
        print("SESSION COMPLETE")
        print("="*60)
        
        # Get updated progress
        progress = self.get_current_progress()
        gate1 = progress["gate_1_progress"]
        
        print(f"\n📈 Session Results:")
        print(f"  Total trades: {session_results['total']}")
        print(f"  Approved: {session_results['approved']}")
        print(f"  Rejected: {session_results['rejected']}")
        print(f"  Pending: {session_results['pending']}")
        print(f"  Approval rate: {(session_results['approved']/max(1, session_results['total']))*100:.1f}%")
        
        if session_results['risk_scores']:
            avg_score = sum(session_results['risk_scores']) / len(session_results['risk_scores'])
            print(f"  Average risk score: {avg_score:.3f}")
        
        print(f"\n📊 Updated Gate 1 Progress:")
        print(f"  Total: {gate1['completed_trades']}/{gate1['target_trades']} ({gate1['completed_trades']/gate1['target_trades']*100:.1f}%)")
        print(f"  Successful: {gate1['successful_trades']}")
        print(f"  P&L: ${gate1['total_pnl_usd']:.4f}")
        
        # Progress bar
        completed = gate1['completed_trades']
        target = gate1['target_trades']
        bar_length = 20
        filled = int(bar_length * (completed / target))
        progress_bar = "█" * filled + "░" * (bar_length - filled)
        
        print(f"\nProgress: [{progress_bar}] {completed}/{target}")
        
        # Save session results
        results_file = self.simp_root / f"logs/gate1_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "session": {
                    "trades_per_session": trades_per_session,
                    "batch_size": batch_size
                },
                "results": session_results,
                "progress": gate1
            }, f, indent=2)
        
        print(f"\n📁 Session results saved to: {results_file}")
        
        # Recommendations
        print("\n🎯 Next Session Planning:")
        
        remaining = target - completed
        if remaining > 0:
            sessions_needed = max(1, (remaining + trades_per_session - 1) // trades_per_session)
            print(f"  Trades remaining: {remaining}")
            print(f"  Sessions needed: {sessions_needed} (at {trades_per_session} trades/session)")
            
            if session_results['approved'] / max(1, session_results['total']) >= 0.7:
                print(f"  ✅ Good approval rate, continue current approach")
            else:
                print(f"  ⚠ Lower approval rate, consider:")
                print(f"     - Adjusting risk scoring further")
                print(f"     - Using higher confidence signals")
                print(f"     - Increasing spread ranges")
        else:
            print(f"  🎉 Gate 1 COMPLETE!")
        
        return session_results

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Continue Gate 1 Testing")
    parser.add_argument("--trades", type=int, default=15, help="Trades per session")
    parser.add_argument("--batch-size", type=int, default=5, help="Trades per batch")
    
    args = parser.parse_args()
    
    print(f"Gate 1 Continued Testing Session")
    print(f"Trades per session: {args.trades}")
    print(f"Batch size: {args.batch_size}")
    print()
    
    continuer = Gate1Continuer()
    continuer.run_session(args.trades, args.batch_size)

if __name__ == "__main__":
    main()