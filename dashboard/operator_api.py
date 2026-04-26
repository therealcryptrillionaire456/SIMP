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


# T31.3/E8: Strategy Health endpoint
@router.get("/api/health/strategy")
async def get_strategy_health():
    """Get strategy health scores from StrategyHealthMonitor"""
    try:
        from simp.organs.quantumarb.strategy_health import StrategyHealthMonitor
        monitor = StrategyHealthMonitor()
        summary = monitor.evaluate()
        return summary.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/health/strategy/{strategy_name}")
async def get_strategy_health_detail(strategy_name: str):
    """Get detailed health score for a specific strategy"""
    try:
        from simp.organs.quantumarb.strategy_health import StrategyHealthMonitor
        monitor = StrategyHealthMonitor()
        summary = monitor.evaluate()
        if strategy_name in summary.strategy_scores:
            score = summary.strategy_scores[strategy_name]
            return score.__dict__ if hasattr(score, '__dict__') else str(score)
        return {"error": "Strategy not found", "available": list(summary.strategy_scores.keys())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
