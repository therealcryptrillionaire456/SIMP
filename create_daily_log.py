#!/usr/bin/env python3.10
"""
Create Daily Log for Phase 4 Operations
Automatically generates daily log entry in Obsidian format.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import requests

class DailyLogCreator:
    def __init__(self):
        self.simp_root = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")
        self.obsidian_root = Path("/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs")
        self.today = datetime.now()
        self.date_str = self.today.strftime("%Y-%m-%d")
        self.log_file = self.obsidian_root / f"Daily Log - {self.date_str}.md"
        
    def get_broker_status(self):
        """Get SIMP broker status."""
        try:
            response = requests.get("http://127.0.0.1:5555/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "online",
                    "agents_online": data.get("agents_online", 0),
                    "pending_intents": data.get("pending_intents", 0)
                }
        except:
            pass
        return {"status": "offline", "agents_online": 0, "pending_intents": 0}
    
    def get_dashboard_status(self):
        """Get dashboard status."""
        try:
            response = requests.get("http://127.0.0.1:8050/health", timeout=5)
            if response.status_code == 200:
                return {"status": "online"}
        except:
            pass
        return {"status": "offline"}
    
    def get_gate1_progress(self):
        """Get Gate 1 progress."""
        progress_file = self.simp_root / "data/sandbox_test/progress.json"
        if progress_file.exists():
            try:
                with open(progress_file, 'r') as f:
                    data = json.load(f)
                gate1 = data.get("gate_1_progress", {})
                
                # Calculate daily progress
                daily_progress = gate1.get("daily_progress", {})
                today_progress = daily_progress.get(self.date_str, {"trades": 0, "pnl": 0.0})
                
                return {
                    "current_trades": gate1.get("completed_trades", 0),
                    "target_trades": gate1.get("target_trades", 100),
                    "successful_trades": gate1.get("successful_trades", 0),
                    "total_pnl": gate1.get("total_pnl_usd", 0.0),
                    "today_trades": today_progress.get("trades", 0),
                    "today_pnl": today_progress.get("pnl", 0.0),
                    "completion_percentage": (gate1.get("completed_trades", 0) / gate1.get("target_trades", 100)) * 100
                }
            except Exception as e:
                print(f"Error reading progress file: {e}")
        
        return {
            "current_trades": 0,
            "target_trades": 100,
            "successful_trades": 0,
            "total_pnl": 0.0,
            "today_trades": 0,
            "today_pnl": 0.0,
            "completion_percentage": 0.0
        }
    
    def get_quantumarb_status(self):
        """Check if QuantumArb agent is running."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "quantumarb_agent_minimal"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return {"status": "running", "pids": result.stdout.strip().split()}
        except:
            pass
        return {"status": "stopped", "pids": []}
    
    def get_system_metrics(self):
        """Get basic system metrics."""
        try:
            # Get CPU usage (simplified)
            cpu_result = subprocess.run(
                ["top", "-l", "1", "-n", "0"],
                capture_output=True,
                text=True
            )
            cpu_lines = cpu_result.stdout.split('\n')
            cpu_usage = "N/A"
            for line in cpu_lines:
                if "CPU usage" in line:
                    cpu_usage = line.split(":")[1].strip()
                    break
            
            # Get memory usage
            mem_result = subprocess.run(
                ["vm_stat"],
                capture_output=True,
                text=True
            )
            memory_usage = "N/A"
            
            # Get disk space
            disk_result = subprocess.run(
                ["df", "-h", str(self.simp_root)],
                capture_output=True,
                text=True
            )
            disk_lines = disk_result.stdout.split('\n')
            disk_space = "N/A"
            if len(disk_lines) > 1:
                parts = disk_lines[1].split()
                if len(parts) >= 5:
                    disk_space = parts[4]
            
            return {
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "disk_space": disk_space
            }
        except Exception as e:
            print(f"Error getting system metrics: {e}")
            return {
                "cpu_usage": "error",
                "memory_usage": "error",
                "disk_space": "error"
            }
    
    def get_recent_logs(self):
        """Get recent log entries."""
        log_dir = self.simp_root / "logs"
        recent_entries = []
        
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log"))
            # Get most recent log file
            if log_files:
                latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
                try:
                    with open(latest_log, 'r') as f:
                        lines = f.readlines()[-20:]  # Last 20 lines
                        for line in lines:
                            if any(keyword in line.lower() for keyword in ["error", "warning", "exception", "failed"]):
                                recent_entries.append(line.strip())
                except:
                    pass
        
        return recent_entries[:5]  # Return top 5
    
    def create_progress_bar(self, current, total, width=20):
        """Create ASCII progress bar."""
        percentage = current / total
        filled = int(width * percentage)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {current}/{total} ({percentage:.1%})"
    
    def generate_log(self):
        """Generate the daily log entry."""
        # Gather data
        broker_status = self.get_broker_status()
        dashboard_status = self.get_dashboard_status()
        quantumarb_status = self.get_quantumarb_status()
        gate1_progress = self.get_gate1_progress()
        system_metrics = self.get_system_metrics()
        recent_logs = self.get_recent_logs()
        
        # Calculate yesterday's date
        yesterday = self.today - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")
        
        # Create progress bar
        progress_bar = self.create_progress_bar(
            gate1_progress["current_trades"],
            gate1_progress["target_trades"]
        )
        
        # Generate log content
        log_content = f"""---
tags: [daily-log, phase4, gate1, trading]
created: {self.date_str}
updated: {self.date_str}
---

# Daily Log - {self.date_str}

## 🟢 Morning Startup ({self.today.strftime('%H:%M')})

### System Status
- [ ] **SIMP Broker**: {broker_status['status']} ({broker_status['agents_online']} agents)
- [ ] **Dashboard**: {dashboard_status['status']}
- [ ] **QuantumArb Phase 4**: {quantumarb_status['status']}
- [ ] **BullBear Agent**: check manually
- [ ] **ProjectX**: check manually
- [ ] **KashClaw Gemma**: check manually

### Safety & Configuration
- [ ] **BRP Mode**: ENFORCED
- [ ] **Trading Mode**: Microscopic Sandbox (Gate 1)
- [ ] **Position Limits**: $0.01–$0.10
- [ ] **Daily Loss Limit**: $1.00
- [ ] **Risk Threshold**: 70%

### Gate 1 Progress (Snapshot)
- **Current**: {gate1_progress['current_trades']}/100 trades
- **P&L Cumulative**: ${gate1_progress['total_pnl']:.4f}
- **Yesterday's Trades**: check manually
- **Yesterday's P&L**: check manually
- **Open Incidents**: 0 (check manually)

### Observability Check
- [ ] **Agent Lightning**: check manually
- [ ] **Recent Traces**: check manually
- [ ] **ProjectX Health**: check manually
- [ ] **Log Files**: {'⚠ issues found' if recent_logs else '✅ clean'}

---

## 📈 Mid-Day Check (--:--)

### Trading Activity
- **Trades Executed Today**: {gate1_progress['today_trades']}
- **Current P&L Today**: ${gate1_progress['today_pnl']:.4f}
- **Win Rate Today**: calculate manually
- **Average Trade Size**: calculate manually

### Safety Events
- **BRP Blocks**: check manually
- **ProjectX Escalations**: check manually
- **Emergency Stops**: 0 (should be 0)
- **Incidents Today**: 0

### System Health
- **CPU Usage**: {system_metrics['cpu_usage']}
- **Memory Usage**: {system_metrics['memory_usage']}
- **Disk Space**: {system_metrics['disk_space']}
- **Network Latency**: check manually

### Notes & Observations
Fill in midday observations...

---

## 🌙 End of Day (--:--)

### Final Metrics

#### Trading Performance
- **Trades Today**: {gate1_progress['today_trades']}
- **Trades Cumulative**: {gate1_progress['current_trades']}/100
- **P&L Today**: ${gate1_progress['today_pnl']:.4f}
- **P&L Cumulative**: ${gate1_progress['total_pnl']:.4f}
- **Win Rate Today**: calculate manually
- **Average Trade Size**: calculate manually
- **Max Slippage Today**: calculate manually

#### Safety Metrics
- **BRP Blocks Today**: check manually
- **ProjectX Escalations**: check manually
- **Emergency Stops**: 0
- **Incidents Today**: 0
- **Incidents Resolved**: 0

#### System Metrics
- **System Uptime**: calculate manually
- **Error Rate**: calculate manually
- **Trace Completeness**: calculate manually
- **Ledger Accuracy**: 100% (verify)

### Qualitative Assessment

#### What Went Well
Fill in what went well today...

#### Issues Encountered
{'⚠ Issues found in logs' if recent_logs else '✅ No issues encountered'}

#### Patterns Observed
Fill in patterns observed...

#### QuantumArb Behavior Assessment
- **Aggressiveness**: --/10 (1=too conservative, 10=too aggressive)
- **Risk Sensitivity**: --/10
- **Execution Quality**: --/10
- **Stability**: --/10

### Changes Made Today
Fill in any changes made...

### Lessons Learned
Fill in lessons learned...

---

## 🎯 Gate 1 Progress Update

### Daily Progress
```yaml
date: {self.date_str}
gate_1:
  trades_today: {gate1_progress['today_trades']}
  trades_cumulative: {gate1_progress['current_trades']}
  pnl_today: ${gate1_progress['today_pnl']:.4f}
  pnl_cumulative: ${gate1_progress['total_pnl']:.4f}
  incidents_today: 0
  days_remaining: calculate manually
  completion_percentage: {gate1_progress['completion_percentage']:.1f}%
```

### Progress Toward 100 Trades
{progress_bar}

### Gate 1 Readiness Assessment
- [ ] **Trades Complete**: {gate1_progress['current_trades']}/100
- [ ] **Safety Incidents**: 0 (0 required)
- [ ] **Ledger Consistency**: verify manually (100% required)
- [ ] **Trace Completeness**: verify manually (100% required)
- [ ] **Behavior Stability**: --/10 (≥8 required)

### Next 10 Trades Focus
Focus on maintaining safety and consistency...

---

## 🔧 System Maintenance

### Logs Reviewed
- [ ] QuantumArb logs: {'reviewed' if recent_logs else 'pending'}
- [ ] System logs: pending
- [ ] Error logs: {'⚠ issues found' if recent_logs else '✅ clean'}
- [ ] Access logs: pending

### Backups Created
- [ ] Configuration: pending
- [ ] Ledger data: pending
- [ ] Log files: pending
- [ ] Documentation: pending

### Cleanup Performed
- [ ] Old log files: pending
- [ ] Temp files: pending
- [ ] Cache cleared: pending

---

## 📝 Notes & Observations

### Technical Observations
Fill in technical observations...

### Behavioral Observations
Fill in behavioral observations...

### Market Observations
Fill in market observations...

### Risk Observations
Fill in risk observations...

### Ideas for Improvement
Fill in improvement ideas...

---

## 🚀 Tomorrow's Plan

### Priority Tasks
1. Continue Gate 1 testing
2. Monitor system health
3. Update documentation

### Focus Areas
- **Trading**: Safety and consistency
- **Safety**: Monitor BRP and ProjectX
- **System**: Performance monitoring
- **Documentation**: Daily log completion

### Goals for Tomorrow
- **Trades Target**: 5-10 trades
- **P&L Target**: Positive or breakeven
- **System Uptime**: 100%
- **Incident Target**: 0

### Risks to Watch
- System stability
- Data consistency
- Safety system performance

---

## 🔗 Related Entries
- [[Phase 4 Daily Ops – Gate 1 (Sandbox Microscopic Trading)]]
- [[Gate 2 Criteria - Microscopic Live Trading]]
- [[Emergency Procedures - Phase 4]]
- Previous: [[Daily Log - {yesterday_str}]]
- Next: [[Daily Log - {(self.today + timedelta(days=1)).strftime('%Y-%m-%d')}]]

## 📁 File References
- Progress: `data/sandbox_test/progress.json`
- Config: `config/phase4_microscopic.json`
- Logs: `logs/quantumarb_*.log`
- Decisions: `data/quantumarb_minimal/decisions.jsonl`
- P&L Ledger: `data/phase4_pnl_ledger.jsonl`

---

## ✅ Daily Completion Checklist
- [ ] All trades recorded in ledger
- [ ] All incidents documented
- [ ] System logs reviewed
- [ ] Daily metrics calculated
- [ ] Obsidian documentation updated
- [ ] Tomorrow's plan created
- [ ] System backed up (if needed)
- [ ] Team communication complete

## 🏁 End of Day Status
- **System State**: Operational
- **Gate 1 Progress**: {gate1_progress['current_trades']}/100 ({gate1_progress['completion_percentage']:.1f}%)
- **Safety Status**: Green
- **Overall Assessment**: Progressing toward Gate 1 completion

---

*Log created: {self.today.strftime('%Y-%m-%d %H:%M')}*  
*Next update: Tomorrow morning*  
*Operator: System Operator*"""

        # Write to file
        with open(self.log_file, 'w') as f:
            f.write(log_content)
        
        print(f"✅ Daily log created: {self.log_file}")
        
        # Also update progress in Obsidian sync
        self.update_obsidian_sync()
        
        return self.log_file
    
    def update_obsidian_sync(self):
        """Update Obsidian sync with new log."""
        sync_script = self.obsidian_root / "sync_with_simp.py"
        if sync_script.exists():
            try:
                subprocess.run(
                    ["python3.10", str(sync_script)],
                    cwd=self.obsidian_root,
                    capture_output=True,
                    text=True
                )
                print("✅ Obsidian sync updated")
            except Exception as e:
                print(f"⚠ Obsidian sync failed: {e}")
    
    def run(self):
        """Main entry point."""
        print(f"Creating daily log for {self.date_str}...")
        
        if not self.obsidian_root.exists():
            print(f"❌ Obsidian directory not found: {self.obsidian_root}")
            return False
        
        log_file = self.generate_log()
        
        # Get Gate 1 progress for summary
        gate1_progress = self.get_gate1_progress()
        
        print(f"\n📊 Summary:")
        print(f"  Date: {self.date_str}")
        print(f"  Gate 1 Progress: {gate1_progress['current_trades']}/100 trades")
        print(f"  P&L Cumulative: ${gate1_progress['total_pnl']:.4f}")
        print(f"  Log File: {log_file}")
        print(f"\n✅ Daily log creation complete")
        
        return True

def main():
    """Main function."""
    creator = DailyLogCreator()
    success = creator.run()
    
    if success:
        print("\n📝 Next steps:")
        print("  1. Review the generated log file")
        print("  2. Fill in manual sections")
        print("  3. Update Gate 1 progress as needed")
        print("  4. Commit to Obsidian vault")
        print("\n🎯 Remember: Gate 1 requires 100 successful sandbox trades")
    else:
        print("\n❌ Failed to create daily log")
        sys.exit(1)

if __name__ == "__main__":
    main()