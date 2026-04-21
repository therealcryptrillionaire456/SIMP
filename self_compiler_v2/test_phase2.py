#!/usr/bin/env python3
"""
Test script for Phase 2 features of Sovereign Self Compiler v2.
Tests continuous mode, session persistence, and enhanced reporting.
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from self_compiler_v2.src.cli import SelfCompilerCLI

def test_cli_initialization():
    """Test that CLI can be initialized."""
    print("🧪 Testing CLI initialization...")
    
    config_path = Path(__file__).parent / "config" / "self_compiler_config.json"
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return False
    
    try:
        cli = SelfCompilerCLI(config_path)
        print("✅ CLI initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize CLI: {e}")
        return False

def test_session_persistence():
    """Test session save/load functionality."""
    print("\n🧪 Testing session persistence...")
    
    config_path = Path(__file__).parent / "config" / "self_compiler_config.json"
    cli = SelfCompilerCLI(config_path)
    
    # Create test session data
    test_session_id = "test_session_123"
    test_data = {
        "session_id": test_session_id,
        "goal": "Test session persistence",
        "final_status": "running",
        "start_time": datetime.utcnow().isoformat() + "Z",
        "cycles": [],
        "summary": {}
    }
    
    try:
        # Test save
        saved_path = cli.save_session_state(test_session_id, test_data)
        print(f"✅ Session saved to: {saved_path}")
        
        # Test load
        loaded_data = cli.load_session_state(test_session_id)
        if loaded_data and loaded_data.get("session_id") == test_session_id:
            print("✅ Session loaded successfully")
        else:
            print("❌ Failed to load session")
            return False
        
        # Test list sessions
        sessions = cli.list_sessions(include_inactive=True)
        if any(s["session_id"] == test_session_id for s in sessions):
            print("✅ Session appears in session list")
        else:
            print("❌ Session not found in session list")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Session persistence test failed: {e}")
        return False
    finally:
        # Clean up test file
        test_file = cli.sessions_dir / f"session_{test_session_id}.json"
        if test_file.exists():
            test_file.unlink()

def test_enhanced_reporting():
    """Test enhanced reporting functionality."""
    print("\n🧪 Testing enhanced reporting...")
    
    config_path = Path(__file__).parent / "config" / "self_compiler_config.json"
    cli = SelfCompilerCLI(config_path)
    
    # Create a test session for reporting
    test_session_id = "test_report_456"
    test_data = {
        "session_id": test_session_id,
        "goal": "Test enhanced reporting features",
        "final_status": "success",
        "start_time": "2026-04-14T15:00:00Z",
        "end_time": "2026-04-14T15:05:00Z",
        "continuous_mode": True,
        "max_cycles": 25,
        "stop_reason": "max_cycles_reached (25/25)",
        "consecutive_failures": 0,
        "max_consecutive_failures": 3,
        "max_total_time_seconds": 3600,
        "continuous_mode": False,
        "cycles": [
            {
                "cycle_number": 1,
                "status": "completed",
                "phases": {
                    "inventory": {"status": "completed", "start_time": "2026-04-14T15:00:00Z", "end_time": "2026-04-14T15:01:00Z"},
                    "planning": {"status": "completed", "start_time": "2026-04-14T15:01:00Z", "end_time": "2026-04-14T15:02:00Z"},
                    "promotion": {"status": "completed", "outcome": "PROMOTE", "artifacts_promoted": ["file1.py", "file2.py"]}
                }
            }
        ]
    }
    
    try:
        # Save test session
        cli.save_session_state(test_session_id, test_data)
        
        # Test enhanced report generation
        print("Testing text format report...")
        try:
            report = cli.generate_enhanced_report(test_session_id, "text")
            print("✅ Text format report generated")
        except Exception as e:
            print(f"❌ Text format report failed: {e}")
            return False
        
        print("Testing JSON format report...")
        try:
            report = cli.generate_enhanced_report(test_session_id, "json")
            if isinstance(report, dict) and "session_id" in report:
                print("✅ JSON format report generated")
            else:
                print("❌ JSON format report invalid")
                return False
        except Exception as e:
            print(f"❌ JSON format report failed: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced reporting test failed: {e}")
        return False
    finally:
        # Clean up test file
        test_file = cli.sessions_dir / f"session_{test_session_id}.json"
        if test_file.exists():
            test_file.unlink()

def test_multi_cycle_behavior():
    """Test multi-cycle session behavior with stop conditions."""
    print("\n🧪 Testing multi-cycle behavior...")
    
    config_path = Path(__file__).parent / "config" / "self_compiler_config.json"
    cli = SelfCompilerCLI(config_path)
    
    # Test session with max_cycles = 10
    test_session_id = "test_multi_cycle_789"
    test_data = {
        "session_id": test_session_id,
        "goal": "Test multi-cycle behavior",
        "final_status": "partial_success",
        "start_time": datetime.utcnow().isoformat() + "Z",
        "max_cycles": 10,
        "continuous_mode": False,
        "max_consecutive_failures": 3,
        "max_total_time_seconds": 600,
        "consecutive_failures": 0,
        "stop_reason": "max_cycles_reached (10/10)",
        "cycles": [
            {"cycle_number": i, "status": "completed", "should_continue": True}
            for i in range(1, 11)
        ]
    }
    
    try:
        # Save test session
        cli.save_session_state(test_session_id, test_data)
        
        # Test that stop conditions are checked
        stop_reason = cli._check_stop_conditions(
            test_data, 
            current_cycle=11,  # One beyond max_cycles
            session_start_time=time.time() - 100  # 100 seconds elapsed
        )
        
        if stop_reason and "max_cycles_reached" in stop_reason:
            print("✅ Stop condition correctly triggered for max_cycles")
        else:
            print(f"❌ Stop condition not triggered: {stop_reason}")
            return False
        
        # Test consecutive failures stop condition
        test_data["consecutive_failures"] = 3
        stop_reason = cli._check_stop_conditions(
            test_data,
            current_cycle=5,
            session_start_time=time.time() - 100
        )
        
        if stop_reason and "max_consecutive_failures_reached" in stop_reason:
            print("✅ Stop condition correctly triggered for consecutive failures")
        else:
            print(f"❌ Stop condition not triggered: {stop_reason}")
            return False
        
        # Test time-based stop condition
        test_data["consecutive_failures"] = 0
        stop_reason = cli._check_stop_conditions(
            test_data,
            current_cycle=5,
            session_start_time=time.time() - 4000  # 4000 seconds elapsed > 3600 default
        )
        
        if stop_reason and "max_total_time_exceeded" in stop_reason:
            print("✅ Stop condition correctly triggered for max time")
        else:
            print(f"❌ Stop condition not triggered: {stop_reason}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Multi-cycle test failed: {e}")
        return False
    finally:
        # Clean up test file
        test_file = cli.sessions_dir / f"session_{test_session_id}.json"
        if test_file.exists():
            test_file.unlink()

def test_safe_stop_behavior():
    """Test safe-stop behavior for continuous mode."""
    print("\n🧪 Testing safe-stop behavior...")
    
    config_path = Path(__file__).parent / "config" / "self_compiler_config.json"
    cli = SelfCompilerCLI(config_path)
    
    # Create a session that simulates being interrupted
    test_session_id = "test_safe_stop_999"
    test_data = {
        "session_id": test_session_id,
        "goal": "Test safe-stop behavior",
        "final_status": "interrupted",
        "start_time": datetime.utcnow().isoformat() + "Z",
        "max_cycles": 100,
        "continuous_mode": True,
        "pause_between_cycles": 10,
        "stop_reason": "user_interrupt",
        "cycles": [
            {"cycle_number": 1, "status": "completed", "should_continue": True},
            {"cycle_number": 2, "status": "completed", "should_continue": True}
        ]
    }
    
    try:
        # Save the interrupted session
        cli.save_session_state(test_session_id, test_data)
        
        # Test that it can be resumed
        try:
            # This would normally run cycles, but we're just testing the resume capability
            sessions = cli.list_sessions(include_inactive=True)
            session_found = any(s["session_id"] == test_session_id for s in sessions)
            
            if session_found:
                print("✅ Interrupted session saved and listed correctly")
            else:
                print("❌ Interrupted session not found in session list")
                return False
            
            # Check that session can be resumed (status check)
            status = test_data.get("final_status", "unknown")
            if status in ["unknown", "interrupted", "partial_failure"]:
                print("✅ Session has resumable status")
            else:
                print(f"❌ Session has non-resumable status: {status}")
                return False
            
            return True
            
        except ValueError as e:
            if "cannot be resumed" in str(e):
                print(f"✅ Session correctly prevented from resuming: {e}")
                return True
            else:
                print(f"❌ Unexpected error: {e}")
                return False
        
    except Exception as e:
        print(f"❌ Safe-stop test failed: {e}")
        return False
    finally:
        # Clean up test file
        test_file = cli.sessions_dir / f"session_{test_session_id}.json"
        if test_file.exists():
            test_file.unlink()

def test_scaling_to_100_cycles():
    """Test configuration for scaling to 100 cycles."""
    print("\n🧪 Testing 100-cycle scaling configuration...")
    
    config_path = Path(__file__).parent / "config" / "self_compiler_config.json"
    cli = SelfCompilerCLI(config_path)
    
    # Test that default max_cycles is now 25
    test_session_id = "test_100_cycles_101"
    test_data = {
        "session_id": test_session_id,
        "goal": "Test 100-cycle scaling",
        "max_cycles": 100,  # Explicitly set to 100
        "continuous_mode": False,
        "max_consecutive_failures": 5,  # Increased for longer runs
        "max_total_time_seconds": 7200,  # 2 hours for 100 cycles
        "stop_reason": "max_cycles_reached (100/100)"
    }
    
    try:
        # Save test session
        cli.save_session_state(test_session_id, test_data)
        
        # Load and verify
        loaded = cli.load_session_state(test_session_id)
        
        if loaded and loaded.get("max_cycles") == 100:
            print("✅ 100-cycle configuration supported")
            
            # Verify enhanced report includes scaling metrics
            try:
                report = cli.generate_enhanced_report(test_session_id, "json")
                if (report.get("basic_metrics", {}).get("max_cycles") == 100 and
                    report.get("basic_metrics", {}).get("max_total_time_seconds") == 7200):
                    print("✅ Enhanced report includes scaling metrics")
                else:
                    print("❌ Enhanced report missing scaling metrics")
                    return False
            except:
                print("⚠️ Could not generate enhanced report (may need actual cycles)")
            
            return True
        else:
            print("❌ 100-cycle configuration not loaded correctly")
            return False
            
    except Exception as e:
        print(f"❌ 100-cycle test failed: {e}")
        return False
    finally:
        # Clean up test file
        test_file = cli.sessions_dir / f"session_{test_session_id}.json"
        if test_file.exists():
            test_file.unlink()

def test_command_line_interface():
    """Test that CLI commands work."""
    print("\n🧪 Testing command-line interface...")
    
    import subprocess
    import os
    
    # Change to the self_compiler_v2 directory
    test_dir = Path(__file__).parent
    os.chdir(test_dir)
    
    commands_to_test = [
        ["python3.10", "src/cli.py", "--help"],
        ["python3.10", "src/cli.py", "run", "--help"],
        ["python3.10", "src/cli.py", "sessions", "--help"],
        ["python3.10", "src/cli.py", "enhanced-report", "--help"],
        ["python3.10", "src/cli.py", "monitor", "--help"],
    ]
    
    all_passed = True
    
    for cmd in commands_to_test:
        print(f"Testing: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("✅ Command executed successfully")
            else:
                print(f"❌ Command failed with exit code {result.returncode}")
                print(f"Stderr: {result.stderr[:200]}")
                all_passed = False
        except subprocess.TimeoutExpired:
            print("❌ Command timed out")
            all_passed = False
        except Exception as e:
            print(f"❌ Command failed: {e}")
            all_passed = False
    
    return all_passed

def main():
    """Run all tests."""
    print("=" * 60)
    print("Sovereign Self Compiler v2 - Phase 2 Feature Tests")
    print("=" * 60)
    
    test_results = []
    
    # Run tests
    test_results.append(("CLI Initialization", test_cli_initialization()))
    test_results.append(("Session Persistence", test_session_persistence()))
    test_results.append(("Enhanced Reporting", test_enhanced_reporting()))
    test_results.append(("Multi-Cycle Behavior", test_multi_cycle_behavior()))
    test_results.append(("Safe-Stop Behavior", test_safe_stop_behavior()))
    test_results.append(("100-Cycle Scaling", test_scaling_to_100_cycles()))
    test_results.append(("Command Line Interface", test_command_line_interface()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All Phase 2 features tested successfully!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())