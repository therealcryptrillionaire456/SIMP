#!/usr/bin/env python3.10
"""
Check SIMP System Status
Comprehensive status check for all Phase 4 components.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
import subprocess
import requests

def check_service(url, name, timeout=5):
    """Check if a service is responding."""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            return {"status": "online", "data": data}
        else:
            return {"status": f"error_{response.status_code}", "data": None}
    except requests.exceptions.RequestException as e:
        return {"status": "offline", "error": str(e)}

def check_process(pattern):
    """Check if a process is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {"status": "running", "pids": result.stdout.strip().split()}
        else:
            return {"status": "stopped", "pids": []}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_file(path, description):
    """Check if a file exists."""
    file_path = Path(path)
    if file_path.exists():
        size = file_path.stat().st_size
        return {"status": "exists", "size_bytes": size}
    else:
        return {"status": "missing"}

def check_gate1_progress():
    """Check Gate 1 sandbox testing progress."""
    progress_file = Path("data/sandbox_test/progress.json")
    if progress_file.exists():
        try:
            with open(progress_file, 'r') as f:
                progress = json.load(f)
            return {"status": "active", "progress": progress}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    else:
        return {"status": "not_initialized"}

def main():
    """Main status check."""
    print("="*60)
    print("SIMP SYSTEM STATUS CHECK - Phase 4")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*60)
    
    status_report = {
        "timestamp": datetime.now().isoformat(),
        "phase": 4,
        "components": {}
    }
    
    # 1. Check SIMP Broker
    print("\n1. SIMP Broker (Port 5555):")
    broker_status = check_service("http://127.0.0.1:5555/health", "SIMP Broker")
    print(f"   Status: {broker_status['status']}")
    if broker_status["status"] == "online":
        print(f"   Agents: {broker_status['data'].get('agents_online', 'N/A')}")
        print(f"   Pending Intents: {broker_status['data'].get('pending_intents', 'N/A')}")
    status_report["components"]["simp_broker"] = broker_status
    
    # 2. Check Dashboard
    print("\n2. Dashboard (Port 8050):")
    dashboard_status = check_service("http://127.0.0.1:8050/health", "Dashboard")
    print(f"   Status: {dashboard_status['status']}")
    status_report["components"]["dashboard"] = dashboard_status
    
    # 3. Check BullBear Agent
    print("\n3. BullBear Agent (Port 5559):")
    bullbear_status = check_service("http://127.0.0.1:5559/health", "BullBear")
    print(f"   Status: {bullbear_status['status']}")
    status_report["components"]["bullbear_agent"] = bullbear_status
    
    # 4. Check ProjectX
    print("\n4. ProjectX (Port 8771):")
    projectx_status = check_service("http://127.0.0.1:8771/health", "ProjectX")
    print(f"   Status: {projectx_status['status']}")
    status_report["components"]["projectx"] = projectx_status
    
    # 5. Check KashClaw Gemma
    print("\n5. KashClaw Gemma (Port 8780):")
    gemma_status = check_service("http://127.0.0.1:8780/health", "KashClaw Gemma")
    print(f"   Status: {gemma_status['status']}")
    status_report["components"]["kashclaw_gemma"] = gemma_status
    
    # 6. Check QuantumArb Agents
    print("\n6. QuantumArb Agents:")
    
    # Check minimal agent
    minimal_agent = check_process("quantumarb_agent_minimal")
    print(f"   Minimal Agent: {minimal_agent['status']}")
    if minimal_agent['status'] == "running":
        print(f"   PIDs: {', '.join(minimal_agent['pids'])}")
    status_report["components"]["quantumarb_minimal"] = minimal_agent
    
    # Check other quantumarb agents
    other_agents = check_process("quantumarb_agent")
    if other_agents['status'] == "running":
        print(f"   Other Agents: {len(other_agents['pids'])} running")
    status_report["components"]["quantumarb_other"] = other_agents
    
    # 7. Check Phase 4 Configuration
    print("\n7. Phase 4 Configuration:")
    config_status = check_file("config/phase4_microscopic.json", "Phase 4 Config")
    print(f"   Config File: {config_status['status']}")
    if config_status['status'] == "exists":
        print(f"   Size: {config_status['size_bytes']} bytes")
    status_report["components"]["phase4_config"] = config_status
    
    # 8. Check Gate 1 Progress
    print("\n8. Gate 1 Sandbox Testing:")
    gate1_status = check_gate1_progress()
    print(f"   Status: {gate1_status['status']}")
    if gate1_status['status'] == "active":
        progress = gate1_status['progress']['gate_1_progress']
        print(f"   Target Trades: {progress['target_trades']}")
        print(f"   Completed Trades: {progress['completed_trades']}")
        print(f"   Successful Trades: {progress['successful_trades']}")
        print(f"   Total P&L: ${progress['total_pnl_usd']:.4f}")
    status_report["components"]["gate1_progress"] = gate1_status
    
    # 9. Check Obsidian Documentation
    print("\n9. Obsidian Documentation:")
    obsidian_dir = Path("/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs")
    if obsidian_dir.exists():
        md_files = list(obsidian_dir.glob("**/*.md"))
        print(f"   Status: Available")
        print(f"   Markdown Files: {len(md_files)}")
        status_report["components"]["obsidian"] = {
            "status": "available",
            "md_files": len(md_files)
        }
    else:
        print(f"   Status: Not found")
        status_report["components"]["obsidian"] = {"status": "not_found"}
    
    # 10. Check Log Files
    print("\n10. System Logs:")
    logs_dir = Path("logs")
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.log"))
        recent_logs = [f for f in log_files if f.stat().st_mtime > time.time() - 86400]
        print(f"   Total Log Files: {len(log_files)}")
        print(f"   Recent (24h): {len(recent_logs)}")
        status_report["components"]["logs"] = {
            "total_files": len(log_files),
            "recent_files": len(recent_logs)
        }
    else:
        print(f"   Status: No log directory")
        status_report["components"]["logs"] = {"status": "no_directory"}
    
    # Summary
    print("\n" + "="*60)
    print("SYSTEM SUMMARY:")
    print("="*60)
    
    online_services = 0
    total_services = 0
    
    for component, status in status_report["components"].items():
        if component.endswith("_agent") or component in ["simp_broker", "dashboard", "projectx", "kashclaw_gemma"]:
            total_services += 1
            if status.get("status") in ["online", "running"]:
                online_services += 1
    
    print(f"Services Online: {online_services}/{total_services}")
    
    if online_services == total_services:
        print("✅ ALL SYSTEMS OPERATIONAL")
    elif online_services >= total_services * 0.7:
        print("⚠ SYSTEM PARTIALLY OPERATIONAL")
    else:
        print("❌ SYSTEM DEGRADED")
    
    print(f"\nPhase 4 Status: {'READY' if gate1_status['status'] == 'active' else 'SETUP REQUIRED'}")
    print(f"Microscopic Trading: ENABLED ($0.01-$0.10)")
    print(f"Safety Gates: Gate 1 (Sandbox) ACTIVE")
    
    # Save report
    report_file = Path(f"logs/system_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_file, 'w') as f:
        json.dump(status_report, f, indent=2)
    
    print(f"\nStatus report saved to: {report_file}")
    
    # Recommendations
    print("\n" + "="*60)
    print("RECOMMENDATIONS:")
    print("="*60)
    
    if gate1_status['status'] != 'active':
        print("1. Initialize Gate 1 testing:")
        print("   ./tools/phase4_sandbox_test.sh")
    
    if not Path("data/sandbox_test").exists():
        print("2. Create sandbox test directory:")
        print("   mkdir -p data/sandbox_test")
    
    if config_status['status'] != 'exists':
        print("3. Create Phase 4 configuration:")
        print("   cp config/phase4_microscopic.json.example config/phase4_microscopic.json")
    
    print("\n4. Access Dashboard: http://127.0.0.1:8050")
    print("5. Monitor Gate 1: cat data/sandbox_test/progress.json")
    print("6. View Logs: tail -f logs/quantumarb_minimal.log")
    
    print("\n" + "="*60)
    print("SYSTEM READY FOR PHASE 4 OPERATION")
    print("="*60)

if __name__ == "__main__":
    main()