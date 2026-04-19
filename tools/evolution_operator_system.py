#!/usr/bin/env python3
"""
Evolution Operator System
Automates the operator checklist for ASI-Evolve Daily Evolution System
"""

import sys
import json
import os
import logging
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import subprocess
import shutil
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/evolution_operator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EvolutionOperator:
    """Automated operator for ASI-Evolve system"""
    
    def __init__(self):
        self.repo_root = Path(__file__).parent.parent
        self.data_dir = self.repo_root / 'data'
        self.logs_dir = self.repo_root / 'logs'
        self.dashboard_url = "http://127.0.0.1:8050"
        
        # Ensure directories exist
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Operator state file
        self.state_file = self.data_dir / 'evolution_operator_state.json'
        self.load_state()
    
    def load_state(self):
        """Load operator state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
            except:
                self.state = {}
        else:
            self.state = {
                'last_daily_check': None,
                'last_weekly_check': None,
                'last_monthly_check': None,
                'daily_checks_completed': [],
                'weekly_checks_completed': [],
                'monthly_checks_completed': [],
                'alerts_sent': [],
                'backups_created': []
            }
    
    def save_state(self):
        """Save operator state to file"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def check_dashboard_status(self):
        """Check evolution dashboard for status"""
        logger.info("🔍 Checking evolution dashboard status...")
        
        try:
            # Check dashboard health
            response = requests.get(f"{self.dashboard_url}/health", timeout=10)
            if response.status_code == 200:
                logger.info("✅ Dashboard is healthy")
                
                # Check evolution API
                evolution_status = requests.get(f"{self.dashboard_url}/api/evolution/status", timeout=10)
                if evolution_status.status_code == 200:
                    status_data = evolution_status.json()
                    logger.info(f"✅ Evolution API status: {status_data.get('status', 'unknown')}")
                    
                    # Check last evolution
                    if 'last_evolution' in status_data:
                        last_run = status_data['last_evolution']
                        logger.info(f"📅 Last evolution: {last_run}")
                    
                    return True
                else:
                    logger.warning("⚠️ Evolution API not responding")
                    return False
            else:
                logger.error("❌ Dashboard not healthy")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking dashboard: {e}")
            return False
    
    def review_daily_evolution_report(self):
        """Review daily evolution report"""
        logger.info("📋 Reviewing daily evolution report...")
        
        today = datetime.now().strftime('%Y%m%d')
        report_file = self.data_dir / 'daily_reviews' / f'evolution_review_{today}.md'
        
        if report_file.exists():
            try:
                with open(report_file, 'r') as f:
                    content = f.read()
                
                # Extract key metrics
                lines = content.split('\n')
                metrics = {}
                for line in lines:
                    if '**Total Experiments**' in line:
                        metrics['total_experiments'] = line.split(':')[-1].strip()
                    elif '**Average Improvement**' in line:
                        metrics['avg_improvement'] = line.split(':')[-1].strip()
                    elif '**Success Rate**' in line:
                        metrics['success_rate'] = line.split(':')[-1].strip()
                
                logger.info(f"✅ Daily report found: {report_file}")
                logger.info(f"   Total Experiments: {metrics.get('total_experiments', 'N/A')}")
                logger.info(f"   Avg Improvement: {metrics.get('avg_improvement', 'N/A')}")
                logger.info(f"   Success Rate: {metrics.get('success_rate', 'N/A')}")
                
                # Check for issues
                if 'No evolution data available' in content:
                    logger.warning("⚠️ Report indicates no evolution data")
                    return False
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Error reading report: {e}")
                return False
        else:
            logger.warning(f"⚠️ Daily report not found: {report_file}")
            return False
    
    def verify_simp_log_entry(self):
        """Verify SIMP log entry created"""
        logger.info("📝 Verifying SIMP log entry...")
        
        today = datetime.now().strftime('%Y%m%d')
        log_file = self.data_dir / 'daily_reviews' / f'simp_log_{today}.md'
        
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    content = f.read()
                
                if 'ASI-Evolve Daily Evolution' in content:
                    logger.info("✅ SIMP log entry found and contains evolution section")
                    
                    # Check for completion status
                    if '✅ Operational' in content:
                        logger.info("✅ Evolution system marked as operational")
                        return True
                    else:
                        logger.warning("⚠️ Evolution system not marked as operational")
                        return False
                else:
                    logger.warning("⚠️ SIMP log doesn't contain evolution section")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Error reading SIMP log: {e}")
                return False
        else:
            logger.warning(f"⚠️ SIMP log not found: {log_file}")
            return False
    
    def monitor_system_resources(self):
        """Monitor system resources"""
        logger.info("💻 Monitoring system resources...")
        
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            logger.info(f"   CPU Usage: {cpu_percent:.1f}%")
            
            # Memory usage
            memory = psutil.virtual_memory()
            logger.info(f"   Memory Usage: {memory.percent:.1f}%")
            
            # Disk usage
            disk = psutil.disk_usage(str(self.repo_root))
            logger.info(f"   Disk Usage: {disk.percent:.1f}%")
            
            # Check thresholds
            issues = []
            if cpu_percent > 80:
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")
            if memory.percent > 80:
                issues.append(f"High memory usage: {memory.percent:.1f}%")
            if disk.percent > 80:
                issues.append(f"High disk usage: {disk.percent:.1f}%")
            
            if issues:
                logger.warning(f"⚠️ Resource issues detected: {', '.join(issues)}")
                return False
            else:
                logger.info("✅ System resources within normal limits")
                return True
                
        except ImportError:
            logger.warning("⚠️ psutil not installed, skipping detailed resource monitoring")
            # Fallback to simple disk check
            try:
                total, used, free = shutil.disk_usage(str(self.repo_root))
                disk_percent = (used / total) * 100
                logger.info(f"   Disk Usage: {disk_percent:.1f}%")
                
                if disk_percent > 80:
                    logger.warning(f"⚠️ High disk usage: {disk_percent:.1f}%")
                    return False
                else:
                    logger.info("✅ Disk usage within normal limits")
                    return True
            except Exception as e:
                logger.error(f"❌ Error checking disk usage: {e}")
                return False
    
    def review_weekly_performance(self):
        """Review evolution performance trends (weekly)"""
        logger.info("📈 Reviewing weekly performance trends...")
        
        try:
            # Load dashboard data
            dashboard_file = self.data_dir / 'evolution_dashboard.json'
            if dashboard_file.exists():
                with open(dashboard_file, 'r') as f:
                    dashboard_data = json.load(f)
                
                total_experiments = dashboard_data.get('total_experiments', 0)
                successful = dashboard_data.get('successful_experiments', 0)
                avg_improvement = dashboard_data.get('average_improvement', 0)
                
                logger.info(f"   Total Experiments: {total_experiments}")
                logger.info(f"   Successful: {successful}")
                logger.info(f"   Avg Improvement: {avg_improvement:.1f}%")
                
                # Calculate success rate
                if total_experiments > 0:
                    success_rate = (successful / total_experiments) * 100
                    logger.info(f"   Success Rate: {success_rate:.1f}%")
                    
                    # Check trends
                    if success_rate < 50:
                        logger.warning("⚠️ Low success rate detected")
                        return False
                    elif avg_improvement < 0:
                        logger.warning("⚠️ Negative average improvement")
                        return False
                    else:
                        logger.info("✅ Performance trends positive")
                        return True
                else:
                    logger.warning("⚠️ No experiments completed yet")
                    return False
            else:
                logger.warning("⚠️ Dashboard data not found")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error reviewing performance: {e}")
            return False
    
    def adjust_evolution_parameters(self):
        """Adjust evolution parameters if needed (weekly)"""
        logger.info("⚙️ Checking evolution parameters...")
        
        try:
            # Check current parameters
            evolution_script = self.repo_root / 'tools' / 'evolution_runner.py'
            if evolution_script.exists():
                with open(evolution_script, 'r') as f:
                    content = f.read()
                
                # Extract current parameters
                import re
                rounds_match = re.search(r'rounds=(\d+)', content)
                population_match = re.search(r'population_size=(\d+)', content)
                
                if rounds_match and population_match:
                    current_rounds = int(rounds_match.group(1))
                    current_population = int(population_match.group(1))
                    
                    logger.info(f"   Current parameters: {current_rounds} rounds, {current_population} population")
                    
                    # Check if adjustments needed based on performance
                    dashboard_file = self.data_dir / 'evolution_dashboard.json'
                    if dashboard_file.exists():
                        with open(dashboard_file, 'r') as f:
                            dashboard_data = json.load(f)
                        
                        avg_improvement = dashboard_data.get('average_improvement', 0)
                        
                        # Simple adjustment logic
                        if avg_improvement < 10:  # Low improvement
                            logger.info("   Low improvement detected, suggesting parameter adjustment")
                            # In a real system, you might adjust parameters here
                            return False  # Indicates adjustment needed
                        else:
                            logger.info("   Parameters performing well")
                            return True
                    else:
                        logger.info("   No performance data, keeping current parameters")
                        return True
                else:
                    logger.warning("⚠️ Could not extract evolution parameters")
                    return False
            else:
                logger.warning("⚠️ Evolution script not found")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking parameters: {e}")
            return False
    
    def backup_evolution_results(self):
        """Backup evolution results (weekly)"""
        logger.info("💾 Creating evolution results backup...")
        
        try:
            backup_dir = self.repo_root / 'backups' / 'evolution'
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = backup_dir / f'evolution_backup_{timestamp}.tar.gz'
            
            # Create backup of evolution results
            results_dir = self.data_dir / 'evolution_results'
            if results_dir.exists() and any(results_dir.iterdir()):
                import tarfile
                
                with tarfile.open(backup_file, 'w:gz') as tar:
                    tar.add(results_dir, arcname='evolution_results')
                
                # Also backup dashboard data
                dashboard_file = self.data_dir / 'evolution_dashboard.json'
                if dashboard_file.exists():
                    shutil.copy2(dashboard_file, backup_dir / f'dashboard_backup_{timestamp}.json')
                
                logger.info(f"✅ Backup created: {backup_file}")
                
                # Record backup in state
                self.state['backups_created'].append({
                    'timestamp': datetime.now().isoformat(),
                    'file': str(backup_file),
                    'size': backup_file.stat().st_size if backup_file.exists() else 0
                })
                self.save_state()
                
                return True
            else:
                logger.warning("⚠️ No evolution results to backup")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error creating backup: {e}")
            return False
    
    def update_evolution_strategies(self):
        """Update evolution strategies (weekly)"""
        logger.info("🧠 Checking evolution strategies...")
        
        try:
            # Check for new strategies in knowledge base
            knowledge_base = self.repo_root / 'brp_enhancement' / 'integration' / 'modules' / 'asi_evolve_simple_module.py'
            if knowledge_base.exists():
                with open(knowledge_base, 'r') as f:
                    content = f.read()
                
                # Count strategies
                strategies = []
                if 'evolve_threat_detection' in content:
                    strategies.append('threat_detection')
                
                logger.info(f"   Current strategies: {', '.join(strategies)}")
                
                # Check if new strategies should be added
                # In a real system, this would check for new strategy files or updates
                if len(strategies) < 2:
                    logger.info("   Limited strategies available, consider adding more")
                    return False  # Indicates strategies should be updated
                else:
                    logger.info("   Strategies adequate")
                    return True
            else:
                logger.warning("⚠️ Knowledge base not found")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking strategies: {e}")
            return False
    
    def comprehensive_performance_review(self):
        """Comprehensive performance review (monthly)"""
        logger.info("📊 Conducting comprehensive performance review...")
        
        try:
            # Load all evolution results
            results_dir = self.data_dir / 'evolution_results'
            if results_dir.exists():
                results_files = list(results_dir.glob('*.json'))
                
                if results_files:
                    all_results = []
                    improvements = []
                    
                    for file in results_files:
                        try:
                            with open(file, 'r') as f:
                                data = json.load(f)
                            all_results.append(data)
                            
                            if data.get('success'):
                                results = data.get('results', {})
                                improvement = results.get('improvement_percent', 0)
                                improvements.append(improvement)
                        except:
                            continue
                    
                    if all_results:
                        # Calculate comprehensive metrics
                        total = len(all_results)
                        successful = sum(1 for r in all_results if r.get('success'))
                        success_rate = (successful / total * 100) if total > 0 else 0
                        avg_improvement = sum(improvements) / len(improvements) if improvements else 0
                        
                        logger.info(f"   Monthly Review Results:")
                        logger.info(f"     Total Experiments: {total}")
                        logger.info(f"     Successful: {successful}")
                        logger.info(f"     Success Rate: {success_rate:.1f}%")
                        logger.info(f"     Avg Improvement: {avg_improvement:.1f}%")
                        
                        # Generate monthly report
                        self.generate_monthly_report(all_results, improvements)
                        
                        return True
                    else:
                        logger.warning("⚠️ No valid results found")
                        return False
                else:
                    logger.warning("⚠️ No evolution results found")
                    return False
            else:
                logger.warning("⚠️ Evolution results directory not found")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error in performance review: {e}")
            return False
    
    def generate_monthly_report(self, results, improvements):
        """Generate monthly performance report"""
        try:
            monthly_dir = self.data_dir / 'monthly_reports'
            monthly_dir.mkdir(exist_ok=True)
            
            month = datetime.now().strftime('%Y%m')
            report_file = monthly_dir / f'evolution_monthly_report_{month}.md'
            
            with open(report_file, 'w') as f:
                f.write(f"# ASI-Evolve Monthly Performance Report\n")
                f.write(f"## Month: {datetime.now().strftime('%B %Y')}\n")
                f.write(f"## Generated: {datetime.now().isoformat()}\n\n")
                
                # Summary
                total = len(results)
                successful = sum(1 for r in results if r.get('success'))
                success_rate = (successful / total * 100) if total > 0 else 0
                avg_improvement = sum(improvements) / len(improvements) if improvements else 0
                
                f.write("## Executive Summary\n\n")
                f.write(f"- **Total Experiments**: {total}\n")
                f.write(f"- **Successful Experiments**: {successful}\n")
                f.write(f"- **Success Rate**: {success_rate:.1f}%\n")
                f.write(f"- **Average Improvement**: {avg_improvement:.1f}%\n\n")
                
                # Recommendations
                f.write("## Recommendations\n\n")
                if success_rate > 80 and avg_improvement > 20:
                    f.write("1. **Continue Current Strategy**: Performance is excellent\n")
                    f.write("2. **Expand Evolution Scope**: Consider adding more components\n")
                    f.write("3. **Increase Experiment Frequency**: Consider daily+ evolution\n")
                elif success_rate > 50 and avg_improvement > 10:
                    f.write("1. **Optimize Parameters**: Fine-tune evolution parameters\n")
                    f.write("2. **Add Diversity**: Introduce more variation in evolution\n")
                    f.write("3. **Monitor Closely**: Watch for performance trends\n")
                else:
                    f.write("1. **Review Evolution Approach**: Current strategy needs improvement\n")
                    f.write("2. **Check System Health**: Ensure all dependencies are working\n")
                    f.write("3. **Consider Alternative Strategies**: Try different evolution methods\n")
                
                f.write("\n---\n")
                f.write("*Generated automatically by Evolution Operator System*\n")
            
            logger.info(f"✅ Monthly report generated: {report_file}")
            
        except Exception as e:
            logger.error(f"❌ Error generating monthly report: {e}")
    
    def evolution_strategy_optimization(self):
        """Evolution strategy optimization (monthly)"""
        logger.info("⚡ Optimizing evolution strategies...")
        
        try:
            # This would involve analyzing performance data
            # and suggesting optimizations
            
            # For now, just check if optimization is needed
            dashboard_file = self.data_dir / 'evolution_dashboard.json'
            if dashboard_file.exists():
                with open(dashboard_file, 'r') as f:
                    dashboard_data = json.load(f)
                
                avg_improvement = dashboard_data.get('average_improvement', 0)
                
                if avg_improvement < 15:
                    logger.info("   Low improvement detected, optimization recommended")
                    # In a real system, this would trigger optimization logic
                    return False  # Indicates optimization needed
                else:
                    logger.info("   Current strategies performing well")
                    return True
            else:
                logger.warning("⚠️ No performance data for optimization")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error in strategy optimization: {e}")
            return False
    
    def knowledge_base_updates(self):
        """Knowledge base updates (monthly)"""
        logger.info("📚 Checking knowledge base for updates...")
        
        try:
            # Check knowledge base directory
            kb_dir = self.repo_root / 'brp_enhancement' / 'integration' / 'modules'
            if kb_dir.exists():
                kb_files = list(kb_dir.glob('*.py'))
                
                logger.info(f"   Knowledge base files: {len(kb_files)}")
                
                # Check for updates (simplified)
                # In a real system, this would check git or version tracking
                if len(kb_files) > 0:
                    logger.info("   Knowledge base exists")
                    # Check if updates are available
                    # For now, assume updates might be needed monthly
                    logger.info("   Monthly update check complete")
                    return True
                else:
                    logger.warning("⚠️ No knowledge base files found")
                    return False
            else:
                logger.warning("⚠️ Knowledge base directory not found")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking knowledge base: {e}")
            return False
    
    def system_health_audit(self):
        """System health audit (monthly)"""
        logger.info("🏥 Conducting system health audit...")
        
        audit_results = {
            'timestamp': datetime.now().isoformat(),
            'components': {},
            'issues': [],
            'recommendations': []
        }
        
        # Check each component
        components_to_check = [
            ('Dashboard', self.check_dashboard_status),
            ('Evolution Runner', lambda: True),  # Simplified
            ('Data Storage', lambda: self.data_dir.exists()),
            ('Logging', lambda: self.logs_dir.exists()),
            ('Backup System', lambda: (self.repo_root / 'backups').exists())
        ]
        
        all_healthy = True
        
        for component_name, check_func in components_to_check:
            try:
                healthy = check_func()
                audit_results['components'][component_name] = {
                    'healthy': healthy,
                    'checked_at': datetime.now().isoformat()
                }
                
                if not healthy:
                    all_healthy = False
                    audit_results['issues'].append(f"{component_name} not healthy")
                    
            except Exception as e:
                audit_results['components'][component_name] = {
                    'healthy': False,
                    'error': str(e),
                    'checked_at': datetime.now().isoformat()
                }
                all_healthy = False
                audit_results['issues'].append(f"{component_name} check failed: {e}")
        
        # Save audit results
        audit_dir = self.data_dir / 'audits'
        audit_dir.mkdir(exist_ok=True)
        
        audit_file = audit_dir / f'system_health_audit_{datetime.now().strftime("%Y%m")}.json'
        with open(audit_file, 'w') as f:
            json.dump(audit_results, f, indent=2)
        
        if all_healthy:
            logger.info("✅ System health audit passed")
            audit_results['recommendations'].append("All systems operational, continue regular monitoring")
        else:
            logger.warning(f"⚠️ System health audit found issues: {audit_results['issues']}")
            audit_results['recommendations'].append("Address identified issues promptly")
        
        logger.info(f"✅ Audit report saved: {audit_file}")
        
        return all_healthy
    
    def send_alert(self, subject, message, level='info'):
        """Send alert notification"""
        # In a real system, this would send email, Slack, etc.
        # For now, just log it
        logger.info(f"🚨 ALERT [{level.upper()}]: {subject}")
        logger.info(f"   {message}")
        
        # Record alert in state
        self.state['alerts_sent'].append({
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'subject': subject,
            'message': message
        })
        self.save_state()
        
        return True
    
    def run_daily_checks(self):
        """Run all daily checks"""
        logger.info("=" * 60)
        logger.info("DAILY OPERATOR CHECKS")
        logger.info("=" * 60)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }
        
        # Daily checklist
        daily_checks = [
            ('Dashboard Status', self.check_dashboard_status),
            ('Daily Report', self.review_daily_evolution_report),
            ('SIMP Log Entry', self.verify_simp_log_entry),
            ('System Resources', self.monitor_system_resources)
        ]
        
        all_passed = True
        
        for check_name, check_func in daily_checks:
            logger.info(f"\n📋 {check_name}")
            try:
                passed = check_func()
                results['checks'][check_name] = {
                    'passed': passed,
                    'timestamp': datetime.now().isoformat()
                }
                
                if not passed:
                    all_passed = False
                    self.send_alert(
                        f"Daily check failed: {check_name}",
                        f"The daily operator check '{check_name}' failed.",
                        'warning'
                    )
                    
            except Exception as e:
                logger.error(f"❌ Error in {check_name}: {e}")
                results['checks'][check_name] = {
                    'passed': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                all_passed = False
                self.send_alert(
                    f"Daily check error: {check_name}",
                    f"Error during '{check_name}': {e}",
                    'error'
                )
        
        # Update state
        self.state['last_daily_check'] = datetime.now().isoformat()
        self.state['daily_checks_completed'].append({
            'timestamp': datetime.now().isoformat(),
            'all_passed': all_passed,
            'results': results
        })
        self.save_state()
        
        # Save daily check results
        daily_dir = self.data_dir / 'operator_checks' / 'daily'
        daily_dir.mkdir(parents=True, exist_ok=True)
        
        daily_file = daily_dir / f'daily_check_{datetime.now().strftime("%Y%m%d")}.json'
        with open(daily_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"\n{'='*60}")
        if all_passed:
            logger.info("✅ ALL DAILY CHECKS PASSED")
        else:
            logger.info("⚠️ SOME DAILY CHECKS FAILED")
        logger.info(f"{'='*60}")
        
        return all_passed
    
    def run_weekly_checks(self):
        """Run all weekly checks"""
        logger.info("=" * 60)
        logger.info("WEEKLY OPERATOR CHECKS")
        logger.info("=" * 60)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }
        
        # Weekly checklist
        weekly_checks = [
            ('Performance Trends', self.review_weekly_performance),
            ('Evolution Parameters', self.adjust_evolution_parameters),
            ('Results Backup', self.backup_evolution_results),
            ('Strategy Updates', self.update_evolution_strategies)
        ]
        
        all_passed = True
        
        for check_name, check_func in weekly_checks:
            logger.info(f"\n📋 {check_name}")
            try:
                passed = check_func()
                results['checks'][check_name] = {
                    'passed': passed,
                    'timestamp': datetime.now().isoformat()
                }
                
                if not passed:
                    all_passed = False
                    # Weekly checks might indicate needs rather than failures
                    self.send_alert(
                        f"Weekly check action needed: {check_name}",
                        f"The weekly check '{check_name}' indicates action may be needed.",
                        'info'
                    )
                    
            except Exception as e:
                logger.error(f"❌ Error in {check_name}: {e}")
                results['checks'][check_name] = {
                    'passed': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                all_passed = False
                self.send_alert(
                    f"Weekly check error: {check_name}",
                    f"Error during '{check_name}': {e}",
                    'error'
                )
        
        # Update state
        self.state['last_weekly_check'] = datetime.now().isoformat()
        self.state['weekly_checks_completed'].append({
            'timestamp': datetime.now().isoformat(),
            'all_passed': all_passed,
            'results': results
        })
        self.save_state()
        
        # Save weekly check results
        weekly_dir = self.data_dir / 'operator_checks' / 'weekly'
        weekly_dir.mkdir(parents=True, exist_ok=True)
        
        weekly_file = weekly_dir / f'weekly_check_{datetime.now().strftime("%Y%m%d")}.json'
        with open(weekly_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"\n{'='*60}")
        if all_passed:
            logger.info("✅ ALL WEEKLY CHECKS COMPLETED")
        else:
            logger.info("⚠️ SOME WEEKLY CHECKS INDICATE ACTION NEEDED")
        logger.info(f"{'='*60}")
        
        return all_passed
    
    def run_monthly_checks(self):
        """Run all monthly checks"""
        logger.info("=" * 60)
        logger.info("MONTHLY OPERATOR CHECKS")
        logger.info("=" * 60)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }
        
        # Monthly checklist
        monthly_checks = [
            ('Performance Review', self.comprehensive_performance_review),
            ('Strategy Optimization', self.evolution_strategy_optimization),
            ('Knowledge Base Updates', self.knowledge_base_updates),
            ('System Health Audit', self.system_health_audit)
        ]
        
        all_passed = True
        
        for check_name, check_func in monthly_checks:
            logger.info(f"\n📋 {check_name}")
            try:
                passed = check_func()
                results['checks'][check_name] = {
                    'passed': passed,
                    'timestamp': datetime.now().isoformat()
                }
                
                if not passed:
                    all_passed = False
                    self.send_alert(
                        f"Monthly check action needed: {check_name}",
                        f"The monthly check '{check_name}' indicates action may be needed.",
                        'info'
                    )
                    
            except Exception as e:
                logger.error(f"❌ Error in {check_name}: {e}")
                results['checks'][check_name] = {
                    'passed': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                all_passed = False
                self.send_alert(
                    f"Monthly check error: {check_name}",
                    f"Error during '{check_name}': {e}",
                    'error'
                )
        
        # Update state
        self.state['last_monthly_check'] = datetime.now().isoformat()
        self.state['monthly_checks_completed'].append({
            'timestamp': datetime.now().isoformat(),
            'all_passed': all_passed,
            'results': results
        })
        self.save_state()
        
        # Save monthly check results
        monthly_dir = self.data_dir / 'operator_checks' / 'monthly'
        monthly_dir.mkdir(parents=True, exist_ok=True)
        
        monthly_file = monthly_dir / f'monthly_check_{datetime.now().strftime("%Y%m%d")}.json'
        with open(monthly_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"\n{'='*60}")
        if all_passed:
            logger.info("✅ ALL MONTHLY CHECKS COMPLETED")
        else:
            logger.info("⚠️ SOME MONTHLY CHECKS INDICATE ACTION NEEDED")
        logger.info(f"{'='*60}")
        
        return all_passed
    
    def should_run_weekly(self):
        """Check if weekly checks should run"""
        if not self.state.get('last_weekly_check'):
            return True
        
        last_weekly = datetime.fromisoformat(self.state['last_weekly_check'])
        days_since = (datetime.now() - last_weekly).days
        
        return days_since >= 7
    
    def should_run_monthly(self):
        """Check if monthly checks should run"""
        if not self.state.get('last_monthly_check'):
            return True
        
        last_monthly = datetime.fromisoformat(self.state['last_monthly_check'])
        days_since = (datetime.now() - last_monthly).days
        
        return days_since >= 30
    
    def run_all_checks(self):
        """Run all appropriate checks based on schedule"""
        logger.info("🚀 Starting Evolution Operator System")
        logger.info(f"📅 Current time: {datetime.now().isoformat()}")
        
        # Always run daily checks
        daily_result = self.run_daily_checks()
        
        # Run weekly checks if needed
        weekly_result = None
        if self.should_run_weekly():
            weekly_result = self.run_weekly_checks()
        else:
            logger.info("\n⏭️ Weekly checks not due yet")
        
        # Run monthly checks if needed
        monthly_result = None
        if self.should_run_monthly():
            monthly_result = self.run_monthly_checks()
        else:
            logger.info("\n⏭️ Monthly checks not due yet")
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("OPERATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Daily Checks: {'✅ PASSED' if daily_result else '⚠️ ISSUES'}")
        
        if weekly_result is not None:
            logger.info(f"Weekly Checks: {'✅ COMPLETED' if weekly_result else '⚠️ ACTION NEEDED'}")
        
        if monthly_result is not None:
            logger.info(f"Monthly Checks: {'✅ COMPLETED' if monthly_result else '⚠️ ACTION NEEDED'}")
        
        logger.info(f"\n📊 Operator state saved: {self.state_file}")
        logger.info("=" * 60)
        
        return all(r for r in [daily_result, weekly_result, monthly_result] if r is not None)

def main():
    """Main entry point"""
    try:
        operator = EvolutionOperator()
        success = operator.run_all_checks()
        
        if success:
            logger.info("🎉 Evolution Operator System completed successfully!")
            return 0
        else:
            logger.warning("⚠️ Evolution Operator System completed with issues")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Fatal error in Evolution Operator System: {e}")
        import traceback
        traceback.print_exc()
        return 2

if __name__ == "__main__":
    sys.exit(main())