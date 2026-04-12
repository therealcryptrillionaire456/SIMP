#!/usr/bin/env python3
"""
Enhanced BRP Framework Startup Script
Properly handles mode conversion from string to OperationMode enum.
"""

import sys
import argparse
from integration.brp_enhanced_framework import BRPEnhancedFramework, OperationMode

def parse_mode(mode_str: str) -> OperationMode:
    """Convert string mode to OperationMode enum."""
    mode_map = {
        'defensive': OperationMode.DEFENSIVE,
        'offensive': OperationMode.OFFENSIVE,
        'hybrid': OperationMode.HYBRID,
        'intelligence': OperationMode.INTELLIGENCE
    }
    
    mode_lower = mode_str.lower()
    if mode_lower not in mode_map:
        print(f"⚠️  Warning: Unknown mode '{mode_str}'. Using 'defensive' mode.")
        return OperationMode.DEFENSIVE
    
    return mode_map[mode_lower]

def main():
    """Start the Enhanced BRP Framework."""
    parser = argparse.ArgumentParser(description='Start Enhanced BRP Framework')
    parser.add_argument('mode', nargs='?', default='defensive',
                       choices=['defensive', 'offensive', 'hybrid', 'intelligence'],
                       help='Operation mode (default: defensive)')
    parser.add_argument('--demo', action='store_true',
                       help='Run demonstration mode')
    
    args = parser.parse_args()
    
    try:
        # Convert mode string to enum
        operation_mode = parse_mode(args.mode)
        
        print("="*60)
        print("🏀 Enhanced BRP Framework Startup")
        print("="*60)
        print(f"Mode: {args.mode} ({operation_mode.value})")
        print("Philosophy: 'Defend everything, score when necessary' - Bill Russell")
        print("="*60)
        
        # Initialize framework
        print(f"\n🚀 Initializing BRP Enhanced Framework in {args.mode} mode...")
        brp = BRPEnhancedFramework(mode=operation_mode)
        
        print(f"✓ Framework initialized successfully!")
        print(f"✓ Integrated repositories: {len(brp.defensive_modules) + len(brp.offensive_modules) + len(brp.intelligence_modules)}")
        print(f"✓ Database: {brp.db_path}")
        
        if args.demo:
            print("\n🎯 Running demonstration...")
            # Submit test events
            from datetime import datetime
            
            test_events = [
                {
                    'event_type': 'system_startup',
                    'source': 'brp_framework',
                    'data': {'mode': args.mode, 'version': '2.0.0'},
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                },
                {
                    'event_type': 'health_check',
                    'source': 'monitoring',
                    'data': {'status': 'healthy', 'components': 5},
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }
            ]
            
            for event in test_events:
                brp.submit_event(event)
                print(f"  ✓ Submitted: {event['event_type']}")
            
            # Run defensive scan
            print("\n🔍 Running defensive scan...")
            scan_results = brp.run_defensive_scan()
            print(f"  ✓ Scan completed")
            print(f"  ✓ Threats detected: {len(scan_results.get('threats_detected', []))}")
            
            # Get system status
            print("\n📊 System status:")
            status = brp.get_system_status()
            print(f"  ✓ Mode: {status.get('mode', 'unknown')}")
            print(f"  ✓ Events processed: {status.get('events_processed', 0)}")
            
            print("\n✅ Demonstration completed successfully!")
        
        print("\n" + "="*60)
        print("🏀 BRP Framework Ready for Operations")
        print("="*60)
        print("\nAvailable commands:")
        print("  brp.submit_event(event_dict)     # Submit security event")
        print("  brp.run_defensive_scan()         # Run defensive scan")
        print("  brp.test_offensive_capability()  # Test offensive capability")
        print("  brp.get_system_status()          # Get system status")
        print("\nPress Ctrl+C to exit")
        print("="*60)
        
        # Keep the framework running
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down BRP Framework...")
            print("✓ Framework shutdown complete")
        
    except Exception as e:
        print(f"\n❌ Error starting BRP Framework: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())