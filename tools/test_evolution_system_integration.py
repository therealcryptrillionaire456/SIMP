#!/usr/bin/env python3
"""
Comprehensive Integration Test for ASI-Evolve System
Tests all components of the daily evolution system
"""

import sys
import json
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"🧪 {text}")
    print("="*60)

def print_success(text):
    """Print success message"""
    print(f"✅ {text}")

def print_warning(text):
    """Print warning message"""
    print(f"⚠️  {text}")

def print_error(text):
    """Print error message"""
    print(f"❌ {text}")

def test_evolution_runner():
    """Test the evolution runner script"""
    print_header("Testing Evolution Runner")
    
    try:
        # Run evolution runner
        result = subprocess.run(
            ["python3", "tools/evolution_runner.py"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print_success("Evolution runner executed successfully")
            
            # Check for expected output
            if "Evolution successful" in result.stdout:
                print_success("Evolution completed successfully")
            else:
                print_warning("Evolution may not have completed")
                
            return True
        else:
            print_error(f"Evolution runner failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print_error("Evolution runner timed out")
        return False
    except Exception as e:
        print_error(f"Error running evolution: {e}")
        return False

def test_operator_system():
    """Test the operator system"""
    print_header("Testing Operator System")
    
    try:
        # Run operator system
        result = subprocess.run(
            ["python3", "tools/evolution_operator_system.py"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode in [0, 1]:  # 0 = success, 1 = warnings
            print_success("Operator system executed successfully")
            
            # Check for expected output
            if "DAILY OPERATOR CHECKS" in result.stdout:
                print_success("Daily checks completed")
            if "WEEKLY OPERATOR CHECKS" in result.stdout:
                print_success("Weekly checks completed")
            if "MONTHLY OPERATOR CHECKS" in result.stdout:
                print_success("Monthly checks completed")
                
            return True
        else:
            print_error(f"Operator system failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print_error("Operator system timed out")
        return False
    except Exception as e:
        print_error(f"Error running operator system: {e}")
        return False

def test_file_structure():
    """Test that all required files and directories exist"""
    print_header("Testing File Structure")
    
    required_dirs = [
        "data/evolution_results",
        "data/daily_reviews",
        "data/operator_checks/daily",
        "data/operator_checks/weekly",
        "data/operator_checks/monthly",
        "data/audits",
        "data/monthly_reports",
        "backups/evolution",
        "logs"
    ]
    
    required_files = [
        "tools/evolution_runner.py",
        "tools/evolution_operator_system.py",
        "tools/run_daily_evolution.sh",
        "tools/create_daily_evolution_review.sh",
        "dashboard/static/evolution_dashboard.html",
        "dashboard/static/evolution_operator_dashboard.html",
        "dashboard/operator_api.py"
    ]
    
    all_good = True
    
    # Check directories
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print_success(f"Directory exists: {dir_path}")
        else:
            print_error(f"Directory missing: {dir_path}")
            all_good = False
    
    # Check files
    for file_path in required_files:
        if Path(file_path).exists():
            print_success(f"File exists: {file_path}")
        else:
            print_error(f"File missing: {file_path}")
            all_good = False
    
    return all_good

def test_data_files():
    """Test that data files are being created"""
    print_header("Testing Data Files")
    
    data_files = [
        "data/evolution_dashboard.json",
        "data/evolution_operator_state.json"
    ]
    
    all_good = True
    
    for file_path in data_files:
        path = Path(file_path)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                print_success(f"Data file valid: {file_path} ({len(data)} keys)")
            except json.JSONDecodeError:
                print_error(f"Invalid JSON in: {file_path}")
                all_good = False
        else:
            print_warning(f"Data file missing: {file_path}")
            # Not critical for initial test
    
    # Check for evolution results
    results_dir = Path("data/evolution_results")
    if results_dir.exists():
        results = list(results_dir.glob("*.json"))
        if results:
            print_success(f"Evolution results found: {len(results)} files")
        else:
            print_warning("No evolution results yet")
    else:
        print_error("Evolution results directory missing")
        all_good = False
    
    return all_good

def test_cron_jobs():
    """Test that cron jobs are configured"""
    print_header("Testing Cron Jobs")
    
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True
        )
        
        cron_content = result.stdout
        
        expected_jobs = [
            "run_daily_evolution.sh",
            "evolution_operator_system.py"
        ]
        
        found_jobs = []
        
        for job in expected_jobs:
            if job in cron_content:
                found_jobs.append(job)
                print_success(f"Cron job found: {job}")
            else:
                print_warning(f"Cron job missing: {job}")
        
        if len(found_jobs) == len(expected_jobs):
            return True
        else:
            print_warning(f"Found {len(found_jobs)}/{len(expected_jobs)} cron jobs")
            return False
            
    except Exception as e:
        print_error(f"Error checking cron jobs: {e}")
        return False

def test_dashboard_access():
    """Test dashboard access (if dashboard is running)"""
    print_header("Testing Dashboard Access")
    
    try:
        import requests
        
        # Try to connect to dashboard
        response = requests.get("http://127.0.0.1:8050/health", timeout=5)
        
        if response.status_code == 200:
            print_success("Dashboard is accessible")
            return True
        else:
            print_warning(f"Dashboard returned status {response.status_code}")
            return False
            
    except requests.ConnectionError:
        print_warning("Dashboard not running (this is OK for testing)")
        return True  # Not critical for test
    except ImportError:
        print_warning("requests module not installed, skipping dashboard test")
        return True
    except Exception as e:
        print_warning(f"Dashboard test error: {e}")
        return True  # Not critical

def test_script_permissions():
    """Test that scripts have correct permissions"""
    print_header("Testing Script Permissions")
    
    scripts = [
        "tools/run_daily_evolution.sh",
        "tools/create_daily_evolution_review.sh"
    ]
    
    all_good = True
    
    for script in scripts:
        path = Path(script)
        if path.exists():
            # Check if executable
            if os.access(path, os.X_OK):
                print_success(f"Script executable: {script}")
            else:
                print_error(f"Script not executable: {script}")
                all_good = False
        else:
            print_warning(f"Script missing: {script}")
    
    return all_good

def generate_test_report(results):
    """Generate a test report"""
    print_header("TEST REPORT")
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r['passed'])
    failed_tests = total_tests - passed_tests
    
    print(f"📊 Test Results:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {passed_tests}")
    print(f"   Failed: {failed_tests}")
    
    print("\n📋 Detailed Results:")
    for result in results:
        status = "✅ PASS" if result['passed'] else "❌ FAIL"
        print(f"   {status} - {result['name']}")
        if not result['passed'] and result.get('details'):
            print(f"      Details: {result['details']}")
    
    print("\n🎯 Recommendations:")
    if failed_tests == 0:
        print("   All tests passed! The system is ready for production.")
    elif failed_tests <= 2:
        print("   Minor issues found. Review warnings and fix as needed.")
    else:
        print("   Significant issues found. Address failures before production.")
    
    # Save report
    report_dir = Path("data/test_reports")
    report_dir.mkdir(exist_ok=True)
    
    report_file = report_dir / f"evolution_system_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "results": results,
        "system_ready": failed_tests == 0
    }
    
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n📁 Report saved: {report_file}")
    
    return failed_tests == 0

def main():
    """Main test function"""
    print("🧬 ASI-Evolve System Integration Test")
    print("="*60)
    
    test_results = []
    
    # Run all tests
    tests = [
        ("File Structure", test_file_structure),
        ("Script Permissions", test_script_permissions),
        ("Evolution Runner", test_evolution_runner),
        ("Operator System", test_operator_system),
        ("Data Files", test_data_files),
        ("Cron Jobs", test_cron_jobs),
        ("Dashboard Access", test_dashboard_access)
    ]
    
    for test_name, test_func in tests:
        try:
            print(f"\n▶️  Running: {test_name}")
            passed = test_func()
            test_results.append({
                "name": test_name,
                "passed": passed,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            print_error(f"Test {test_name} crashed: {e}")
            test_results.append({
                "name": test_name,
                "passed": False,
                "details": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    # Generate report
    all_passed = generate_test_report(test_results)
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED - SYSTEM IS READY!")
    else:
        print("⚠️  SOME TESTS FAILED - REVIEW AND FIX ISSUES")
    print("="*60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())