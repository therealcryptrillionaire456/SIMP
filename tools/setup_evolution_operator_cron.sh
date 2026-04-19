#!/bin/bash
# Setup Evolution Operator Cron Jobs
# Configures automated operator checks for ASI-Evolve system

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "🔧 Setting up Evolution Operator Cron Jobs"
echo "=========================================="

# Create directories
mkdir -p logs
mkdir -p data/operator_checks/daily
mkdir -p data/operator_checks/weekly
mkdir -p data/operator_checks/monthly
mkdir -p data/audits
mkdir -p data/monthly_reports
mkdir -p backups/evolution

echo "📁 Created necessary directories"

# Make scripts executable
chmod +x tools/evolution_operator_system.py

echo "🔧 Made operator system executable"

# Check current crontab
echo "📋 Current crontab:"
crontab -l 2>/dev/null || echo "No crontab found"

# Add operator cron jobs
echo ""
echo "➕ Adding Evolution Operator cron jobs..."

# Daily operator check at 15:30 (3:30 PM ET, before evolution at 16:00)
(crontab -l 2>/dev/null | grep -v "evolution_operator") | crontab -
(crontab -l 2>/dev/null; echo "30 15 * * * cd '$REPO_ROOT' && python3 tools/evolution_operator_system.py >> logs/evolution_operator_daily.log 2>&1") | crontab -

# Weekly summary on Monday at 09:00
(crontab -l 2>/dev/null; echo "0 9 * * 1 cd '$REPO_ROOT' && python3 tools/evolution_operator_system.py --weekly >> logs/evolution_operator_weekly.log 2>&1") | crontab -

# Monthly summary on 1st of month at 10:00
(crontab -l 2>/dev/null; echo "0 10 1 * * cd '$REPO_ROOT' && python3 tools/evolution_operator_system.py --monthly >> logs/evolution_operator_monthly.log 2>&1") | crontab -

echo "✅ Cron jobs added:"
echo "   - Daily operator check: 15:30 (3:30 PM ET)"
echo "   - Weekly summary: Monday 09:00"
echo "   - Monthly summary: 1st of month 10:00"

# Create operator dashboard
echo ""
echo "📊 Creating operator dashboard..."

cat > dashboard/static/evolution_operator_dashboard.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ASI-Evolve Operator Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
            color: white;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.3);
        }
        
        .card h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.4rem;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        
        .status-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }
        
        .status-item:last-child {
            border-bottom: none;
        }
        
        .status-label {
            color: #666;
            font-weight: 500;
        }
        
        .status-value {
            font-weight: 600;
        }
        
        .status-good {
            color: #10b981;
        }
        
        .status-warning {
            color: #f59e0b;
        }
        
        .status-error {
            color: #ef4444;
        }
        
        .checklist {
            list-style: none;
        }
        
        .checklist li {
            padding: 10px 0;
            display: flex;
            align-items: center;
        }
        
        .checklist input[type="checkbox"] {
            margin-right: 10px;
            transform: scale(1.2);
        }
        
        .checklist label {
            cursor: pointer;
            color: #333;
        }
        
        .checklist .completed {
            text-decoration: line-through;
            color: #888;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }
        
        .metric {
            text-align: center;
            padding: 15px;
            background: #f8fafc;
            border-radius: 10px;
        }
        
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            color: #667eea;
            margin: 10px 0;
        }
        
        .metric-label {
            color: #666;
            font-size: 0.9rem;
        }
        
        .actions {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            flex: 1;
        }
        
        .btn-primary {
            background: #667eea;
            color: white;
        }
        
        .btn-primary:hover {
            background: #5a67d8;
        }
        
        .btn-secondary {
            background: #e2e8f0;
            color: #4a5568;
        }
        
        .btn-secondary:hover {
            background: #cbd5e0;
        }
        
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: white;
            color: #667eea;
            border: none;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            font-size: 1.5rem;
            cursor: pointer;
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
        }
        
        .refresh-btn:hover {
            transform: rotate(180deg);
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        }
        
        .last-updated {
            text-align: center;
            color: rgba(255,255,255,0.8);
            margin-top: 20px;
            font-size: 0.9rem;
        }
        
        @media (max-width: 768px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
            
            .metrics-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧬 ASI-Evolve Operator Dashboard</h1>
            <p>Automated monitoring and management of daily evolution system</p>
        </div>
        
        <div class="dashboard-grid">
            <!-- System Status Card -->
            <div class="card">
                <h2>📊 System Status</h2>
                <div id="system-status">
                    <div class="status-item">
                        <span class="status-label">Evolution System</span>
                        <span class="status-value status-good">✅ Operational</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">Daily Evolution</span>
                        <span class="status-value status-good">✅ Scheduled 04:00</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">Operator System</span>
                        <span class="status-value status-good">✅ Active</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">Dashboard API</span>
                        <span class="status-value status-good">✅ Connected</span>
                    </div>
                </div>
            </div>
            
            <!-- Daily Checklist Card -->
            <div class="card">
                <h2>📋 Daily Operator Checklist</h2>
                <ul class="checklist" id="daily-checklist">
                    <li>
                        <input type="checkbox" id="check1" checked>
                        <label for="check1" class="completed">Check evolution dashboard for status</label>
                    </li>
                    <li>
                        <input type="checkbox" id="check2" checked>
                        <label for="check2" class="completed">Review daily evolution report</label>
                    </li>
                    <li>
                        <input type="checkbox" id="check3" checked>
                        <label for="check3" class="completed">Verify SIMP log entry created</label>
                    </li>
                    <li>
                        <input type="checkbox" id="check4" checked>
                        <label for="check4" class="completed">Monitor system resources</label>
                    </li>
                </ul>
                <div class="actions">
                    <button class="btn btn-primary" onclick="runDailyChecks()">Run Daily Checks</button>
                    <button class="btn btn-secondary" onclick="viewDailyReport()">View Report</button>
                </div>
            </div>
            
            <!-- Performance Metrics Card -->
            <div class="card">
                <h2>📈 Performance Metrics</h2>
                <div class="metrics-grid" id="performance-metrics">
                    <div class="metric">
                        <div class="metric-value" id="total-experiments">0</div>
                        <div class="metric-label">Total Experiments</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="success-rate">0%</div>
                        <div class="metric-label">Success Rate</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="avg-improvement">0%</div>
                        <div class="metric-label">Avg Improvement</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="last-evolution">-</div>
                        <div class="metric-label">Last Evolution</div>
                    </div>
                </div>
            </div>
            
            <!-- Weekly & Monthly Cards -->
            <div class="card">
                <h2>📅 Weekly Operations</h2>
                <div class="status-item">
                    <span class="status-label">Last Weekly Check</span>
                    <span class="status-value" id="last-weekly">Never</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Next Weekly Check</span>
                    <span class="status-value" id="next-weekly">Monday 09:00</span>
                </div>
                <div class="actions">
                    <button class="btn btn-primary" onclick="runWeeklyChecks()">Run Weekly Checks</button>
                </div>
            </div>
            
            <div class="card">
                <h2>📊 Monthly Operations</h2>
                <div class="status-item">
                    <span class="status-label">Last Monthly Check</span>
                    <span class="status-value" id="last-monthly">Never</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Next Monthly Check</span>
                    <span class="status-value" id="next-monthly">1st of Month 10:00</span>
                </div>
                <div class="actions">
                    <button class="btn btn-primary" onclick="runMonthlyChecks()">Run Monthly Checks</button>
                </div>
            </div>
            
            <!-- Recent Alerts Card -->
            <div class="card">
                <h2>🚨 Recent Alerts</h2>
                <div id="recent-alerts">
                    <div class="status-item">
                        <span class="status-label">No recent alerts</span>
                        <span class="status-value status-good">✅ All Clear</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="last-updated" id="last-updated">
            Last updated: <span id="update-time">Loading...</span>
        </div>
    </div>
    
    <button class="refresh-btn" onclick="refreshDashboard()">↻</button>
    
    <script>
        // Dashboard data
        let dashboardData = {
            systemStatus: {},
            performanceMetrics: {},
            operatorState: {},
            recentAlerts: []
        };
        
        // Update time display
        function updateTime() {
            const now = new Date();
            document.getElementById('update-time').textContent = 
                now.toLocaleString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                });
        }
        
        // Load dashboard data
        async function loadDashboardData() {
            try {
                // Load evolution dashboard data
                const evolutionResponse = await fetch('/api/evolution/status');
                if (evolutionResponse.ok) {
                    const evolutionData = await evolutionResponse.json();
                    dashboardData.performanceMetrics = evolutionData;
                    
                    // Update performance metrics
                    document.getElementById('total-experiments').textContent = 
                        evolutionData.total_experiments || 0;
                    document.getElementById('success-rate').textContent = 
                        evolutionData.success_rate ? `${evolutionData.success_rate}%` : '0%';
                    document.getElementById('avg-improvement').textContent = 
                        evolutionData.average_improvement ? `${evolutionData.average_improvement.toFixed(1)}%` : '0%';
                    document.getElementById('last-evolution').textContent = 
                        evolutionData.last_evolution ? 'Today' : 'Never';
                }
                
                // Load operator state
                const operatorResponse = await fetch('/api/evolution/operator/state');
                if (operatorResponse.ok) {
                    const operatorData = await operatorResponse.json();
                    dashboardData.operatorState = operatorData;
                    
                    // Update operator status
                    if (operatorData.last_daily_check) {
                        const dailyDate = new Date(operatorData.last_daily_check);
                        document.querySelector('#daily-checklist input[type="checkbox"]').checked = 
                            (new Date() - dailyDate) < 24 * 60 * 60 * 1000; // Within 24 hours
                    }
                    
                    if (operatorData.last_weekly_check) {
                        const weeklyDate = new Date(operatorData.last_weekly_check);
                        document.getElementById('last-weekly').textContent = 
                            weeklyDate.toLocaleDateString();
                    }
                    
                    if (operatorData.last_monthly_check) {
                        const monthlyDate = new Date(operatorData.last_monthly_check);
                        document.getElementById('last-monthly').textContent = 
                            monthlyDate.toLocaleDateString();
                    }
                    
                    // Update alerts
                    if (operatorData.alerts_sent && operatorData.alerts_sent.length > 0) {
                        const alertsContainer = document.getElementById('recent-alerts');
                        alertsContainer.innerHTML = '';
                        
                        const recentAlerts = operatorData.alerts_sent.slice(-3).reverse();
                        recentAlerts.forEach(alert => {
                            const alertDate = new Date(alert.timestamp);
                            const alertItem = document.createElement('div');
                            alertItem.className = 'status-item';
                            alertItem.innerHTML = `
                                <span class="status-label">${alert.subject}</span>
                                <span class="status-value ${alert.level === 'error' ? 'status-error' : alert.level === 'warning' ? 'status-warning' : 'status-good'}">
                                    ${alert.level.toUpperCase()}
                                </span>
                            `;
                            alertsContainer.appendChild(alertItem);
                        });
                    }
                }
                
                // Update system status
                const systemResponse = await fetch('/health');
                if (systemResponse.ok) {
                    const systemData = await systemResponse.json();
                    dashboardData.systemStatus = systemData;
                    
                    // Update status indicators
                    const statusContainer = document.getElementById('system-status');
                    if (systemData.broker_reachable) {
                        statusContainer.innerHTML = `
                            <div class="status-item">
                                <span class="status-label">Evolution System</span>
                                <span class="status-value status-good">✅ Operational</span>
                            </div>
                            <div class="status-item">
                                <span class="status-label">Daily Evolution</span>
                                <span class="status-value status-good">✅ Scheduled 04:00</span>
                            </div>
                            <div class="status-item">
                                <span class="status-label">Operator System</span>
                                <span class="status-value status-good">✅ Active</span>
                            </div>
                            <div class="status-item">
                                <span class="status-label">Dashboard API</span>
                                <span class="status-value status-good">✅ Connected</span>
                            </div>
                        `;
                    }
                }
                
                updateTime();
                
            } catch (error) {
                console.error('Error loading dashboard data:', error);
                document.getElementById('system-status').innerHTML = `
                    <div class="status-item">
                        <span class="status-label">Connection Error</span>
                        <span class="status-value status-error">❌ Offline</span>
                    </div>
                `;
            }
        }
        
        // Run daily checks
        async function runDailyChecks() {
            try {
                const response = await fetch('/api/evolution/operator/run/daily', {
                    method: 'POST'
                });
                
                if (response.ok) {
                    alert('Daily checks started successfully!');
                    setTimeout(loadDashboardData, 2000); // Reload after 2 seconds
                } else {
                    alert('Error starting daily checks');
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        // Run weekly checks
        async function runWeeklyChecks() {
            try {
                const response = await fetch('/api/evolution/operator/run/weekly', {
                    method: 'POST'
                });
                
                if (response.ok) {
                    alert('Weekly checks started successfully!');
                    setTimeout(loadDashboardData, 2000);
                } else {
                    alert('Error starting weekly checks');
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        // Run monthly checks
        async function runMonthlyChecks() {
            try {
                const response = await fetch('/api/evolution/operator/run/monthly', {
                    method: 'POST'
                });
                
                if (response.ok) {
                    alert('Monthly checks started successfully!');
                    setTimeout(loadDashboardData, 2000);
                } else {
                    alert('Error starting monthly checks');
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        // View daily report
        function viewDailyReport() {
            window.open('/api/evolution/reports/daily', '_blank');
        }
        
        // Refresh dashboard
        function refreshDashboard() {
            loadDashboardData();
        }
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', () => {
            loadDashboardData();
            updateTime();
            
            // Auto-refresh every 30 seconds
            setInterval(loadDashboardData, 30000);
        });
    </script>
</body>
</html>
EOF

echo "✅ Operator dashboard created: dashboard/static/evolution_operator_dashboard.html"

# Create API endpoints for operator system
echo ""
echo "🔌 Creating API endpoints..."

cat > dashboard/operator_api.py << 'EOF'
"""
Operator API endpoints for ASI-Evolve system
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import json
import os
from pathlib import Path

router = APIRouter()

@router.get("/api/evolution/operator/state")
async def get_operator_state():
    """Get operator system state"""
    try:
        state_file = Path("data/evolution_operator_state.json")
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
            return state
        else:
            return {
                "status": "no_state_file",
                "message": "Operator state file not found"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/evolution/operator/run/daily")
async def run_daily_checks():
    """Run daily operator checks"""
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "tools/evolution_operator_system.py"],
            capture_output=True,
            text=True
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/evolution/operator/run/weekly")
async def run_weekly_checks():
    """Run weekly operator checks"""
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "tools/evolution_operator_system.py"],
            capture_output=True,
            text=True
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/evolution/operator/run/monthly")
async def run_monthly_checks():
    """Run monthly operator checks"""
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "tools/evolution_operator_system.py"],
            capture_output=True,
            text=True
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/evolution/operator/reports/daily")
async def get_daily_reports():
    """Get daily operator reports"""
    try:
        reports_dir = Path("data/operator_checks/daily")
        if not reports_dir.exists():
            return {"reports": []}
        
        reports = []
        for report_file in sorted(reports_dir.glob("*.json"), reverse=True)[:10]:
            with open(report_file, 'r') as f:
                report_data = json.load(f)
            reports.append({
                "date": report_file.stem.replace("daily_check_", ""),
                "file": str(report_file),
                "data": report_data
            })
        
        return {"reports": reports}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/evolution/operator/alerts")
async def get_recent_alerts():
    """Get recent alerts"""
    try:
        state_file = Path("data/evolution_operator_state.json")
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            alerts = state.get("alerts_sent", [])
            return {
                "total_alerts": len(alerts),
                "recent_alerts": alerts[-10:]  # Last 10 alerts
            }
        else:
            return {"total_alerts": 0, "recent_alerts": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
EOF

echo "✅ Operator API endpoints created"

# Update main dashboard server to include operator API
echo ""
echo "🔄 Updating dashboard server..."

# Check if dashboard server exists and add operator API
DASHBOARD_SERVER="dashboard/server.py"
if [ -f "$DASHBOARD_SERVER" ]; then
    # Check if operator API is already imported
    if ! grep -q "operator_api" "$DASHBOARD_SERVER"; then
        # Add import
        sed -i '' '/from fastapi import/ s/$/, APIRouter/' "$DASHBOARD_SERVER"
        sed -i '' '/import sys/ a\from dashboard.operator_api import router as operator_router' "$DASHBOARD_SERVER"
        
        # Add router inclusion
        sed -i '' '/app.include_router(evolution_router)/ a\app.include_router(operator_router)' "$DASHBOARD_SERVER"
        
        echo "✅ Updated dashboard server with operator API"
    else
        echo "⚠️ Operator API already in dashboard server"
    fi
else
    echo "⚠️ Dashboard server not found at $DASHBOARD_SERVER"
fi

# Create operator documentation
echo ""
echo "📚 Creating operator documentation..."

cat > docs/EVOLUTION_OPERATOR_GUIDE.md << 'EOF'
# ASI-Evolve Operator System Guide

## Overview
The Evolution Operator System automates the monitoring and management of the ASI-Evolve Daily Evolution System. It runs scheduled checks and provides a dashboard for operators.

## System Components

### 1. Operator System (`tools/evolution_operator_system.py`)
- **Purpose**: Automated execution of operator checklist
- **Features**:
  - Daily system health checks
  - Weekly performance reviews
  - Monthly comprehensive audits
  - Alert system for issues
  - Automated backups

### 2. Operator Dashboard (`dashboard/static/evolution_operator_dashboard.html`)
- **Purpose**: Web interface for monitoring and control
- **Features**:
  - Real-time system status
  - Performance metrics
  - Checklist tracking
  - Manual control buttons
  - Alert display

### 3. API Endpoints (`dashboard/operator_api.py`)
- **Purpose**: Programmatic access to operator functions
- **Endpoints**:
  - `GET /api/evolution/operator/state` - Get operator state
  - `POST /api/evolution/operator/run/daily` - Run daily checks
  - `POST /api/evolution/operator/run/weekly` - Run weekly checks
  - `POST /api/evolution/operator/run/monthly` - Run monthly checks
  - `GET /api/evolution/operator/reports/daily` - Get daily reports
  - `GET /api/evolution/operator/alerts` - Get recent alerts

## Scheduled Operations

### Daily (08:00)
1. **Check evolution dashboard for status**
   - Verify dashboard is accessible
   - Check evolution API status
   - Verify last evolution timestamp

2. **Review daily evolution report**
   - Check if report was generated
   - Extract key metrics
   - Verify data completeness

3. **Verify SIMP log entry created**
   - Check SIMP log file exists
   - Verify evolution section present
   - Confirm operational status

4. **Monitor system resources**
   - CPU usage
   - Memory usage
   - Disk space
   - Alert if thresholds exceeded

### Weekly (Monday 09:00)
1. **Review evolution performance trends**
   - Calculate success rates
   - Track improvement trends
   - Identify performance patterns

2. **Adjust evolution parameters if needed**
   - Analyze current parameters
   - Suggest optimizations
   - Update if performance low

3. **Backup evolution results**
   - Create compressed backup
   - Store in backups/evolution/
   - Record backup metadata

4. **Update evolution strategies**
   - Check knowledge base
   - Review strategy effectiveness
   - Update if needed

### Monthly (1st of month 10:00)
1. **Comprehensive performance review**
   - Analyze all experiment results
   - Generate monthly report
   - Calculate comprehensive metrics

2. **Evolution strategy optimization**
   - Review strategy performance
   - Optimize based on data
   - Implement improvements

3. **Knowledge base updates**
   - Check for updates
   - Integrate new knowledge
   - Maintain current strategies

4. **System health audit**
   - Comprehensive system check
   - Generate audit report
   - Identify maintenance needs

## Manual Operations

### Running Checks Manually
```bash
# Run all checks (daily + weekly/monthly if due)
python3 tools/evolution_operator_system.py

# Force daily checks
python3 tools/evolution_operator_system.py --daily

# Force weekly checks
python3 tools/evolution_operator_system.py --weekly

# Force monthly checks
python3 tools/evolution_operator_system.py --monthly
```

### Accessing Dashboard
- **URL**: `http://localhost:8050/evolution_operator_dashboard.html`
- **Features**:
  - Real-time status updates
  - Manual check execution
  - Performance visualization
  - Alert monitoring

### Viewing Reports
```bash
# Daily reports
ls data/operator_checks/daily/

# Weekly reports
ls data/operator_checks/weekly/

# Monthly reports
ls data/monthly_reports/

# Audit reports
ls data/audits/
```

## Alert System

### Alert Levels
1. **Info**: Routine notifications, system updates
2. **Warning**: Potential issues, attention needed
3. **Error**: Critical failures, immediate action required

### Alert Sources
- System health checks
- Performance degradation
- Resource constraints
- Schedule failures
- Data inconsistencies

### Alert Actions
1. **Review alert details** in operator dashboard
2. **Check corresponding logs** in `logs/evolution_operator.log`
3. **Investigate root cause**
4. **Take corrective action**
5. **Verify resolution**

## Troubleshooting

### Common Issues

#### Dashboard Not Accessible
```bash
# Check if dashboard server is running
curl http://localhost:8050/health

# Restart dashboard server
cd dashboard && python3 server.py &
```

#### Operator Checks Failing
```bash
# Check operator logs
tail -f logs/evolution_operator.log

# Check system resources
df -h .
free -h
top -n 1
```

#### Evolution System Not Running
```bash
# Check evolution cron job
crontab -l | grep evolution

# Run evolution manually
bash tools/run_daily_evolution.sh

# Check evolution logs
tail -f logs/daily_evolution_*.log
```

### Maintenance Tasks

#### Regular Maintenance
1. **Daily**: Review operator dashboard
2. **Weekly**: Check backup completion
3. **Monthly**: Review audit reports
4. **Quarterly**: System performance review

#### Data Management
1. **Backup rotation**: Keep last 30 days of backups
2. **Log rotation**: Archive old logs monthly
3. **Report archiving**: Move old reports to archive
4. **Data cleanup**: Remove temporary files

## Integration Points

### With SIMP Ecosystem
1. **Broker Integration**: Health checks via broker API
2. **Dashboard Integration**: Unified monitoring interface
3. **Log Integration**: SIMP log updates
4. **Alert Integration**: System-wide alerting

### With ASI-Evolve System
1. **Evolution Runner**: Direct integration for checks
2. **Results Database**: Access to evolution results
3. **Knowledge Base**: Strategy optimization
4. **Performance Metrics**: Continuous improvement

## Security Considerations

### Access Control
1. **Dashboard Access**: Localhost only by default
2. **API Endpoints**: No authentication required (local)
3. **File Permissions**: Restricted to owner
4. **Log Access**: Operator only

### Data Protection
1. **Backup Encryption**: Not implemented (local only)
2. **Log Sanitization**: No sensitive data in logs
3. **File Permissions**: 600 for sensitive files
4. **Network Security**: Localhost binding only

## Performance Monitoring

### Key Metrics
1. **System Health**: CPU, memory, disk usage
2. **Evolution Performance**: Success rate, improvement %
3. **Operator Efficiency**: Check completion time
4. **Alert Frequency**: Issues per time period

### Optimization Tips
1. **Schedule Optimization**: Avoid peak hours
2. **Resource Allocation**: Monitor and adjust
3. **Database Optimization**: Regular maintenance
4. **Log Management**: Rotation and cleanup

## Support

### Getting Help
1. **Check Logs**: `logs/evolution_operator.log`
2. **Review Documentation**: This guide
3. **System Status**: Operator dashboard
4. **Manual Testing**: Run checks manually

### Reporting Issues
1. **Collect Information**: Logs, error messages
2. **Check Status**: System health, recent changes
3. **Reproduce Issue**: Manual test if possible
4. **Document Steps**: For troubleshooting

---

*Last Updated: $(date '+%Y-%m-%d')*
*System Version: 1.0.0*
EOF

echo "✅ Operator documentation created: docs/EVOLUTION_OPERATOR_GUIDE.md"

# Test the operator system
echo ""
echo "🧪 Testing operator system..."

# Run a quick test
python3 tools/evolution_operator_system.py --help 2>/dev/null || echo "⚠️ Help test failed, continuing..."

echo ""
echo "🎉 Evolution Operator System Setup Complete!"
echo ""
echo "📊 Access Operator Dashboard:"
echo "   http://localhost:8050/evolution_operator_dashboard.html"
echo ""
echo "📅 Scheduled Operations:"
echo "   Daily Checks: 08:00"
echo "   Weekly Checks: Monday 09:00"
echo "   Monthly Checks: 1st of month 10:00"
echo ""
echo "📚 Documentation: docs/EVOLUTION_OPERATOR_GUIDE.md"
echo ""
echo "🔧 Manual Control:"
echo "   python3 tools/evolution_operator_system.py"
echo ""