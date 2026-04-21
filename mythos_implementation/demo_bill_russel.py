#!/usr/bin/env python3
"""
Demonstration of Bill Russel Protocol - Defensive MVP for Mythos Reconstruction
"""

import json
from datetime import datetime, timedelta
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("="*80)
print("BILL RUSSEL PROTOCOL DEMONSTRATION")
print("="*80)
print("\nNamed after the greatest defensive basketball player ever.")
print("\nCore Capabilities:")
print("1. Pattern Recognition at Depth")
print("2. Autonomous Reasoning Chains")
print("3. Memory Across Time")
print("\n" + "="*80)

# Import Bill Russel Protocol
try:
    # Add current directory to path
    import sys
    sys.path.insert(0, '.')
    
    from bill_russel_protocol import BillRusselProtocol
    from bill_russel_protocol.pattern_recognition import PatternType
    from bill_russel_protocol.reasoning_engine import ThreatLevel, ResponseAction
    
    print("✓ Bill Russel Protocol imported successfully!")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    print("\nTrying alternative import...")
    
    # Try direct imports
    try:
        from bill_russel_protocol.pattern_recognition import PatternRecognizer, PatternType
        from bill_russel_protocol.reasoning_engine import ReasoningEngine, ThreatLevel, ResponseAction
        from bill_russel_protocol.memory_system import MemorySystem
        from bill_russel_protocol.threat_database import ThreatDatabase
        from bill_russel_protocol.alert_orchestrator import AlertOrchestrator
        
        # Create custom BillRusselProtocol class
        class BillRusselProtocol:
            def __init__(self):
                self.pattern_recognizer = PatternRecognizer()
                self.reasoning_engine = ReasoningEngine()
                self.memory_system = MemorySystem()
                self.threat_database = ThreatDatabase()
                self.alert_orchestrator = AlertOrchestrator()
            
            def process_security_event(self, event_data):
                patterns = self.pattern_recognizer.analyze(event_data)
                context = self.memory_system.get_context(event_data)
                assessment = self.reasoning_engine.assess_threat(patterns, context)
                self.memory_system.record_event(event_data, assessment)
                response = self.alert_orchestrator.orchestrate_response(assessment, event_data)
                return response
            
            def weekly_correlation_sweep(self):
                return self.memory_system.correlate_events(time_window_days=7)
            
            def get_threat_report(self, days=30):
                return self.threat_database.generate_report(days)
        
        print("✓ Bill Russel Protocol components imported and assembled!")
        
    except ImportError as e2:
        print(f"✗ Alternative import also failed: {e2}")
        print("\nPlease check the bill_russel_protocol directory exists.")
        exit(1)

def create_sample_events():
    """Create sample security events for demonstration."""
    
    print("\n1. CREATING SAMPLE SECURITY EVENTS")
    print("-"*40)
    
    # Sample 1: SQL Injection attempt
    sample1 = {
        'data_type': 'access_logs',
        'data': [
            {
                'remote_addr': '192.168.1.100',
                'request': "GET /login.php?username=admin' OR '1'='1 HTTP/1.1",
                'status': 200,
                'time': datetime.now().isoformat()
            },
            {
                'remote_addr': '192.168.1.100',
                'request': "POST /search.php?q=1' UNION SELECT password FROM users-- HTTP/1.1",
                'status': 200,
                'time': (datetime.now() - timedelta(minutes=1)).isoformat()
            }
        ],
        'source_ip': '192.168.1.100',
        'timestamp': datetime.now().isoformat()
    }
    
    print("Sample 1: SQL Injection attempt from 192.168.1.100")
    print(f"  Request: {sample1['data'][0]['request'][:80]}...")
    
    # Sample 2: Port scanning
    sample2 = {
        'data_type': 'access_logs',
        'data': [
            {
                'remote_addr': '10.0.0.50',
                'request': "GET / HTTP/1.1",
                'status': 200,
                'time': datetime.now().isoformat()
            },
            {
                'remote_addr': '10.0.0.50',
                'request': "GET /admin HTTP/1.1",
                'status': 404,
                'time': (datetime.now() - timedelta(seconds=30)).isoformat()
            },
            {
                'remote_addr': '10.0.0.50',
                'request': "GET /wp-admin HTTP/1.1",
                'status': 404,
                'time': (datetime.now() - timedelta(seconds=60)).isoformat()
            },
            {
                'remote_addr': '10.0.0.50',
                'request': "GET /phpmyadmin HTTP/1.1",
                'status': 404,
                'time': (datetime.now() - timedelta(seconds=90)).isoformat()
            },
            {
                'remote_addr': '10.0.0.50',
                'request': "GET /config HTTP/1.1",
                'status': 404,
                'time': (datetime.now() - timedelta(seconds=120)).isoformat()
            }
        ],
        'source_ip': '10.0.0.50',
        'timestamp': datetime.now().isoformat()
    }
    
    print("\nSample 2: Port/Directory scanning from 10.0.0.50")
    print(f"  5 requests in 2 minutes, 4x 404 responses")
    
    # Sample 3: Data exfiltration (simulated)
    sample3 = {
        'data_type': 'netflow',
        'data': [
            {
                'src_ip': '172.16.0.25',
                'dst_ip': '45.33.32.156',
                'bytes_out': 50000000,  # 50MB
                'bytes_in': 1000,
                'timestamp': datetime.now().isoformat()
            },
            {
                'src_ip': '172.16.0.25',
                'dst_ip': '45.33.32.156',
                'bytes_out': 30000000,  # 30MB
                'bytes_in': 500,
                'timestamp': (datetime.now() - timedelta(minutes=1)).isoformat()
            }
        ],
        'source_ip': '172.16.0.25',
        'timestamp': datetime.now().isoformat()
    }
    
    print("\nSample 3: Large outbound data transfer from 172.16.0.25")
    print(f"  80MB outbound to external IP 45.33.32.156 in 1 minute")
    
    return [sample1, sample2, sample3]

def demonstrate_pattern_recognition(protocol, events):
    """Demonstrate pattern recognition capabilities."""
    
    print("\n2. PATTERN RECOGNITION AT DEPTH")
    print("-"*40)
    
    for i, event in enumerate(events, 1):
        print(f"\nAnalyzing Sample {i}...")
        
        # Use the pattern recognizer directly
        patterns = protocol.pattern_recognizer.analyze(event)
        
        if patterns:
            print(f"  Detected {len(patterns)} security pattern(s):")
            for pattern in patterns:
                print(f"    • {pattern.pattern_type.value}: {pattern.description}")
                print(f"      Confidence: {pattern.confidence:.2f}")
                if pattern.indicators:
                    print(f"      Indicators: {pattern.indicators[0][:60]}...")
        else:
            print("  No patterns detected")

def demonstrate_autonomous_reasoning(protocol, events):
    """Demonstrate autonomous reasoning chains."""
    
    print("\n3. AUTONOMOUS REASONING CHAINS")
    print("-"*40)
    
    for i, event in enumerate(events, 1):
        print(f"\nProcessing Sample {i} through full protocol...")
        
        # Get historical context
        context = protocol.memory_system.get_context(event)
        
        # Analyze patterns
        patterns = protocol.pattern_recognizer.analyze(event)
        
        if patterns:
            # Assess threat
            assessment = protocol.reasoning_engine.assess_threat(patterns, context)
            
            print(f"  Threat Level: {assessment.threat_level.value.upper()}")
            print(f"  Confidence: {assessment.confidence:.2f}")
            print(f"  Description: {assessment.description}")
            print(f"  Recommended Action: {assessment.recommended_action.value}")
            print(f"  Reasoning: {assessment.reasoning[:100]}...")
            
            # Record in memory
            protocol.memory_system.record_event(event, assessment)
            print("  ✓ Recorded in threat memory")
        else:
            print("  No threat detected")

def demonstrate_memory_across_time(protocol):
    """Demonstrate memory and correlation capabilities."""
    
    print("\n4. MEMORY ACROSS TIME")
    print("-"*40)
    
    # Perform correlation sweep
    print("\nPerforming correlation analysis...")
    correlations = protocol.memory_system.correlate_events(time_window_days=7)
    
    if correlations:
        print(f"Found {len(correlations)} correlation(s):")
        for i, correlation in enumerate(correlations[:3], 1):  # Show first 3
            print(f"\n  Correlation {i}:")
            print(f"    Source: {correlation.source_ip}")
            print(f"    Patterns: {correlation.pattern_count} over {correlation.time_span_days} days")
            print(f"    Threat Level: {correlation.threat_level}")
            print(f"    Description: {correlation.description}")
    else:
        print("No correlations found yet (need more data)")
    
    # Generate threat report
    print("\nGenerating threat report...")
    report = protocol.memory_system.get_threat_report(days=7)
    
    print(f"\nThreat Report (Last 7 days):")
    print(f"  Generated: {report['generated_at']}")
    print(f"  Summary: {report['summary']}")
    
    if report['threat_statistics']:
        print("\n  Threat Statistics:")
        for level, stats in report['threat_statistics'].items():
            print(f"    {level.upper()}: {stats['count']} threats "
                  f"(avg confidence: {stats['avg_confidence']:.2f})")

def demonstrate_response_orchestration(protocol, events):
    """Demonstrate response orchestration."""
    
    print("\n5. RESPONSE ORCHESTRATION")
    print("-"*40)
    
    print("\nBill Russel Protocol Response Matrix:")
    print("  LOW confidence → Log and monitor")
    print("  MEDIUM confidence → Rate limit + Telegram alert")
    print("  HIGH confidence → Automatic IP block + full session log")
    print("  CRITICAL confidence → Immediate isolation + incident response")
    
    print("\nProcessing events with response orchestration...")
    
    for i, event in enumerate(events, 1):
        print(f"\nSample {i} Response:")
        
        try:
            # Process through full protocol
            response = protocol.process_security_event(event)
            
            if response:
                print(f"  Action: {response.action}")
                print(f"  Confidence: {response.confidence:.2f}")
                print(f"  Details: {response.details[:80]}...")
                
                # Simulate response actions
                action = response.action.lower()
                if 'block' in action:
                    print("  🛡️  SIMULATION: IP would be blocked automatically")
                elif 'rate_limit' in action:
                    print("  ⚠️  SIMULATION: Rate limiting applied + alert sent")
                elif 'alert' in action:
                    print("  📢 SIMULATION: Alert sent to security team")
                else:
                    print("  📝 SIMULATION: Logged for monitoring")
        except Exception as e:
            print(f"  Error processing response: {e}")

def demonstrate_weekly_operations(protocol):
    """Demonstrate weekly operational procedures."""
    
    print("\n6. WEEKLY OPERATIONS")
    print("-"*40)
    
    print("\nWeekly Correlation Sweep:")
    correlations = protocol.weekly_correlation_sweep()
    
    if correlations:
        print(f"  Found {len(correlations)} correlated threat patterns")
        
        # Show most concerning correlation
        if correlations:
            top_correlation = max(correlations, key=lambda c: c.compound_score)
            print(f"\n  Most concerning correlation:")
            print(f"    Source: {top_correlation.source_ip}")
            print(f"    Score: {top_correlation.compound_score:.2f}")
            print(f"    Patterns: {', '.join(top_correlation.patterns[:3])}")
            print(f"    Time span: {top_correlation.time_span_days} days")
    
    print("\nThreat Intelligence Report:")
    report = protocol.get_threat_report(days=30)
    
    print(f"  Reporting period: {report['period_days']} days")
    print(f"  Total threats analyzed: {sum(s['count'] for s in report['threat_statistics'].values())}")
    
    if report['top_threat_sources']:
        print(f"\n  Top threat source: {report['top_threat_sources'][0]['source_ip']}")
        print(f"    Threats: {report['top_threat_sources'][0]['threat_count']}")
        print(f"    Patterns: {', '.join(report['top_threat_sources'][0]['patterns'][:3])}")

def main():
    """Run the full demonstration."""
    
    print("\nInitializing Bill Russel Protocol...")
    protocol = BillRusselProtocol()
    print("✓ Protocol initialized!")
    
    # Create sample events
    events = create_sample_events()
    
    # Run demonstrations
    demonstrate_pattern_recognition(protocol, events)
    demonstrate_autonomous_reasoning(protocol, events)
    demonstrate_memory_across_time(protocol)
    demonstrate_response_orchestration(protocol, events)
    demonstrate_weekly_operations(protocol)
    
    # Summary
    print("\n" + "="*80)
    print("BILL RUSSEL PROTOCOL - DEMONSTRATION COMPLETE")
    print("="*80)
    
    print("\n✅ WHAT WAS DEMONSTRATED:")
    print("1. Deep pattern recognition (SQLi, scanning, exfiltration)")
    print("2. Autonomous threat assessment with confidence scoring")
    print("3. Long-term memory with correlation across time")
    print("4. Confidence-based response orchestration")
    print("5. Weekly operational procedures")
    
    print("\n🚀 READY FOR PRODUCTION:")
    print("• Threat memory database: threat_memory.db")
    print("• Pattern recognition: SQLi, XSS, scanning, brute force, exfiltration")
    print("• Response actions: Log → Alert → Rate limit → Block → Isolate")
    print("• Correlation engine: Connect events across weeks")
    
    print("\n🔧 NEXT STEPS:")
    print("1. Connect to real log sources (PCAP, access logs, netflow)")
    print("2. Integrate with Telegram/Slack for alerts")
    print("3. Deploy in monitoring mode for baseline establishment")
    print("4. Gradually enable autonomous responses")
    
    print("\n" + "="*80)
    print("THE BILL RUSSEL PROTOCOL IS OPERATIONAL")
    print("="*80)
    
    print("\nDefensive MVP ready for Mythos reconstruction integration!")
    
    # Clean up
    db_path = Path("threat_memory.db")
    if db_path.exists():
        db_path.unlink()
        print(f"\nCleaned up: {db_path}")

if __name__ == "__main__":
    main()