#!/usr/bin/env python3
"""
quantumarb_file_consumer.py — File-based consumer for quantumarb_real

Reads QIP arbitrage signals from file inbox, converts to trade intents,
writes to quantumarb_real inbox for execution.

This is a file-based alternative to mesh communication.
"""
import sys
import os
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quantumarb_file_consumer")

# Paths
QIP_INBOX_DIR = Path("data/inboxes/quantum_intelligence_prime")
QUANTUMARB_INBOX_DIR = Path("data/inboxes/quantumarb_real")
PROCESSED_DIR = Path("data/processed/quantumarb_signals")

# Create directories
QIP_INBOX_DIR.mkdir(parents=True, exist_ok=True)
QUANTUMARB_INBOX_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def process_arb_signal(signal_file: Path) -> Optional[Dict[str, Any]]:
    """Convert QIP arb signal file to quantumarb trade intent."""
    try:
        with open(signal_file, 'r') as f:
            signal = json.load(f)
        
        # Extract signal data
        signal_type = signal.get("signal_type", "")
        if "arbitrage" not in signal_type.lower():
            logger.debug(f"Skipping non-arb signal: {signal_type}")
            return None
        
        # Create trade intent
        trade_intent = {
            "intent_type": "execute_trade",
            "source_agent": "quantum_intelligence_prime",
            "target_agent": "quantumarb_real",
            "timestamp": time.time(),
            "payload": {
                "action": signal.get("action", "BUY"),
                "symbol": signal.get("symbol", "BTC-USD"),
                "amount": signal.get("amount", 0.001),
                "confidence": signal.get("quantum_confidence", signal.get("confidence", 0.0)),
                "signal_id": signal.get("signal_id", ""),
                "signal_type": signal_type,
                "exchange_pair": signal.get("exchange_pair", ""),
                "spread_percent": signal.get("spread_percent", 0.0),
                "estimated_profit": signal.get("estimated_profit", 0.0),
            },
            "metadata": {
                "quantum_enhanced": True,
                "source_file": signal_file.name,
                "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        }
        
        return trade_intent
        
    except Exception as e:
        logger.error(f"Error processing signal file {signal_file}: {e}")
        return None

def main():
    """Main loop - monitor QIP inbox for arb signals."""
    logger.info("QuantumArb file consumer started")
    logger.info(f"Monitoring: {QIP_INBOX_DIR}")
    logger.info(f"Output to: {QUANTUMARB_INBOX_DIR}")
    
    processed_files = set()
    
    try:
        while True:
            # Check for new files in QIP inbox
            for signal_file in QIP_INBOX_DIR.glob("*.json"):
                if signal_file.name in processed_files:
                    continue
                
                logger.info(f"Found new signal: {signal_file.name}")
                
                # Process the signal
                trade_intent = process_arb_signal(signal_file)
                
                if trade_intent:
                    # Write to quantumarb_real inbox
                    output_file = QUANTUMARB_INBOX_DIR / f"quantumarb_intent_{int(time.time())}.json"
                    with open(output_file, 'w') as f:
                        json.dump(trade_intent, f, indent=2)
                    
                    logger.info(f"Created trade intent: {output_file.name}")
                    
                    # Move processed file
                    processed_file = PROCESSED_DIR / signal_file.name
                    shutil.move(signal_file, processed_file)
                    logger.info(f"Moved to processed: {processed_file.name}")
                else:
                    # Move to processed even if not an arb signal
                    processed_file = PROCESSED_DIR / signal_file.name
                    shutil.move(signal_file, processed_file)
                    logger.debug(f"Moved non-arb signal to processed: {processed_file.name}")
                
                processed_files.add(signal_file.name)
            
            # Sleep before next check
            time.sleep(5)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")

if __name__ == "__main__":
    main()
