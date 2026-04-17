"""
Evolution API endpoints for the dashboard.
"""
import json
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Blueprint, jsonify, request

evolution_bp = Blueprint('evolution', __name__)

@evolution_bp.route('/evolution/status', methods=['GET'])
def get_evolution_status():
    """Get current evolution status."""
    try:
        dashboard_file = Path('data/evolution_dashboard.json')
        if dashboard_file.exists():
            with open(dashboard_file, 'r') as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({
                'last_updated': datetime.utcnow().isoformat() + 'Z',
                'total_experiments': 0,
                'successful_experiments': 0,
                'failed_experiments': 0,
                'average_improvement': 0,
                'recent_results': [],
                'status': 'no_data'
            })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@evolution_bp.route('/evolution/run', methods=['POST'])
def run_evolution():
    """Run evolution manually."""
    try:
        # Run evolution script
        result = subprocess.run(
            ['bash', 'tools/run_daily_evolution.sh'],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Evolution timed out after 5 minutes',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 408
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 500

@evolution_bp.route('/evolution/logs', methods=['GET'])
def get_evolution_logs():
    """Get evolution logs."""
    try:
        log_files = list(Path('logs').glob('daily_evolution_*.log'))
        if not log_files:
            return jsonify({'logs': [], 'message': 'No logs found'})
        
        # Get latest log
        latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
        with open(latest_log, 'r') as f:
            content = f.read()
        
        return jsonify({
            'log_file': latest_log.name,
            'content': content,
            'size': len(content),
            'last_modified': datetime.fromtimestamp(latest_log.stat().st_mtime).isoformat() + 'Z'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@evolution_bp.route('/evolution/reports', methods=['GET'])
def get_evolution_reports():
    """Get evolution reports."""
    try:
        report_files = list(Path('data').glob('evolution_daily_report_*.md'))
        if not report_files:
            return jsonify({'reports': [], 'message': 'No reports found'})
        
        reports = []
        for report_file in sorted(report_files, reverse=True)[:10]:  # Last 10 reports
            with open(report_file, 'r') as f:
                content = f.read()
            
            reports.append({
                'file': report_file.name,
                'date': report_file.stem.replace('evolution_daily_report_', ''),
                'size': len(content),
                'preview': content[:500] + '...' if len(content) > 500 else content
            })
        
        return jsonify({'reports': reports})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
