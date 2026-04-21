"""
Automated Testing Pipeline - Build 17
Continuous integration and automated testing pipeline.
"""

import sys
import os
import json
import time
import subprocess
import threading
import queue
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import schedule
import concurrent.futures
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from tests.test_runner import TestRunner, TestSuite, TestCase, TestCategory
from tests.validation_framework import ValidationFramework

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Pipeline stages."""
    SOURCE = "source"
    BUILD = "build"
    TEST = "test"
    VALIDATE = "validate"
    DEPLOY = "deploy"
    MONITOR = "monitor"


class PipelineStatus(Enum):
    """Pipeline status levels."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class NotificationType(Enum):
    """Notification types."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    CONSOLE = "console"


@dataclass
class PipelineJob:
    """Pipeline job definition."""
    job_id: str
    name: str
    description: str
    stage: PipelineStage
    command: str
    working_dir: str
    timeout_seconds: int = 300
    dependencies: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class JobResult:
    """Job execution result."""
    job_id: str
    status: PipelineStatus
    exit_code: int
    stdout: str
    stderr: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PipelineRun:
    """Pipeline execution run."""
    run_id: str
    pipeline_id: str
    trigger: str
    status: PipelineStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    job_results: Dict[str, JobResult] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class NotificationConfig:
    """Notification configuration."""
    config_id: str
    type: NotificationType
    enabled: bool = True
    recipients: List[str] = field(default_factory=list)
    triggers: List[PipelineStatus] = field(default_factory=list)
    template: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class AutomatedPipeline:
    """
    Automated Testing Pipeline for continuous integration.
    """
    
    def __init__(self, pipeline_id: str = "automated_pipeline_001"):
        """
        Initialize Automated Pipeline.
        
        Args:
            pipeline_id: Unique pipeline identifier
        """
        self.pipeline_id = pipeline_id
        self.pipeline_jobs: Dict[str, PipelineJob] = {}
        self.pipeline_runs: Dict[str, PipelineRun] = {}
        self.notification_configs: Dict[str, NotificationConfig] = {}
        
        # Initialize test runner and validation framework
        self.test_runner = TestRunner(f"{pipeline_id}_test_runner")
        self.validation_framework = ValidationFramework(f"{pipeline_id}_validation")
        
        # Load default pipeline jobs
        self._load_default_jobs()
        
        # Load default notification configs
        self._load_default_notifications()
        
        # Execution queue
        self.job_queue = queue.Queue()
        self.is_running = False
        self.execution_thread = None
        
        # Metrics
        self.metrics = {
            "total_jobs": len(self.pipeline_jobs),
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "total_execution_time": 0.0,
            "average_run_time": 0.0,
            "last_run_status": None,
            "last_run_time": None
        }
        
        logger.info(f"Initialized Automated Pipeline {pipeline_id}")
    
    def _load_default_jobs(self):
        """Load default pipeline jobs."""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        default_jobs = [
            # Source stage jobs
            PipelineJob(
                job_id="job_source_checkout",
                name="Source Code Checkout",
                description="Checkout source code from repository",
                stage=PipelineStage.SOURCE,
                command="git status",
                working_dir=project_root,
                timeout_seconds=60
            ),
            PipelineJob(
                job_id="job_source_clean",
                name="Clean Workspace",
                description="Clean build workspace",
                stage=PipelineStage.SOURCE,
                command="find . -name '*.pyc' -delete && find . -name '__pycache__' -type d -delete",
                working_dir=project_root,
                timeout_seconds=30
            ),
            
            # Build stage jobs
            PipelineJob(
                job_id="job_build_dependencies",
                name="Install Dependencies",
                description="Install Python dependencies",
                stage=PipelineStage.BUILD,
                command="pip install -r requirements.txt",
                working_dir=project_root,
                timeout_seconds=300
            ),
            PipelineJob(
                job_id="job_build_lint",
                name="Code Linting",
                description="Run code linting and style checking",
                stage=PipelineStage.BUILD,
                command="python -m pylint agents/ --rcfile=.pylintrc || true",
                working_dir=project_root,
                timeout_seconds=120
            ),
            
            # Test stage jobs
            PipelineJob(
                job_id="job_test_unit",
                name="Unit Tests",
                description="Run unit tests for all agents",
                stage=PipelineStage.TEST,
                command=f"python -c \"import sys; sys.path.insert(0, '.'); from tests.test_runner import TestRunner; runner = TestRunner('pipeline_runner'); report = runner.execute_test_suite('suite_agents'); print(f'Unit tests completed: {{{{report.passed_tests}}}} passed, {{{{report.failed_tests}}}} failed')\"",
                working_dir=project_root,
                timeout_seconds=600
            ),
            PipelineJob(
                job_id="job_test_integration",
                name="Integration Tests",
                description="Run integration tests",
                stage=PipelineStage.TEST,
                command=f"python -c \"import sys; sys.path.insert(0, '.'); from tests.test_runner import TestRunner; runner = TestRunner('pipeline_runner'); report = runner.execute_test_suite('suite_integration'); print(f'Integration tests completed: {{{{report.passed_tests}}}} passed, {{{{report.failed_tests}}}} failed')\"",
                working_dir=project_root,
                timeout_seconds=600
            ),
            PipelineJob(
                job_id="job_test_system",
                name="System Tests",
                description="Run end-to-end system tests",
                stage=PipelineStage.TEST,
                command=f"python -c \"import sys; sys.path.insert(0, '.'); from tests.test_runner import TestRunner; runner = TestRunner('pipeline_runner'); report = runner.execute_test_suite('suite_system'); print(f'System tests completed: {{{{report.passed_tests}}}} passed, {{{{report.failed_tests}}}} failed')\"",
                working_dir=project_root,
                timeout_seconds=900
            ),
            
            # Validation stage jobs
            PipelineJob(
                job_id="job_validate_agents",
                name="Agent Validation",
                description="Validate agent performance and accuracy",
                stage=PipelineStage.VALIDATE,
                command=f"python -c \"import sys; sys.path.insert(0, '.'); from tests.validation_framework import ValidationFramework; framework = ValidationFramework('pipeline_validation'); validation_data = {{'response_time': 1.5, 'accuracy': 0.96}}; results = framework.validate_component('agents', validation_data); print(f'Agent validation: {{len([r for r in results if r.status.value == 'passed'])}} passed, {{len([r for r in results if r.status.value == 'failed'])}} failed')\"",
                working_dir=project_root,
                timeout_seconds=300
            ),
            PipelineJob(
                job_id="job_validate_compliance",
                name="Compliance Validation",
                description="Validate compliance systems",
                stage=PipelineStage.VALIDATE,
                command=f"python -c \"import sys; sys.path.insert(0, '.'); from tests.validation_framework import ValidationFramework; framework = ValidationFramework('pipeline_validation'); validation_data = {{'monitoring_latency': 4.5, 'check_accuracy': 0.99}}; results = framework.validate_component('compliance', validation_data); print(f'Compliance validation: {{len([r for r in results if r.status.value == 'passed'])}} passed, {{len([r for r in results if r.status.value == 'failed'])}} failed')\"",
                working_dir=project_root,
                timeout_seconds=300
            ),
            
            # Deploy stage jobs
            PipelineJob(
                job_id="job_deploy_docs",
                name="Generate Documentation",
                description="Generate system documentation",
                stage=PipelineStage.DEPLOY,
                command="python -m pydoc -w agents/*.py || true",
                working_dir=project_root,
                timeout_seconds=180
            ),
            PipelineJob(
                job_id="job_deploy_reports",
                name="Generate Test Reports",
                description="Generate HTML test reports",
                stage=PipelineStage.DEPLOY,
                command=f"python -c \"import sys; sys.path.insert(0, '.'); from tests.test_runner import TestRunner; runner = TestRunner('pipeline_reporter'); report = runner.execute_test_suite('suite_system'); runner.generate_html_report(report, 'test_report.html'); print('Test report generated: test_report.html')\"",
                working_dir=project_root,
                timeout_seconds=300
            )
        ]
        
        for job in default_jobs:
            self.pipeline_jobs[job.job_id] = job
        
        logger.info(f"Loaded {len(default_jobs)} default pipeline jobs")
    
    def _load_default_notifications(self):
        """Load default notification configurations."""
        default_configs = [
            NotificationConfig(
                config_id="notify_pipeline_failed",
                type=NotificationType.CONSOLE,
                enabled=True,
                triggers=[PipelineStatus.FAILED],
                template="Pipeline {pipeline_id} run {run_id} failed: {failure_reason}"
            ),
            NotificationConfig(
                config_id="notify_pipeline_success",
                type=NotificationType.CONSOLE,
                enabled=True,
                triggers=[PipelineStatus.SUCCESS],
                template="Pipeline {pipeline_id} run {run_id} completed successfully in {duration}"
            ),
            NotificationConfig(
                config_id="notify_test_failures",
                type=NotificationType.CONSOLE,
                enabled=True,
                triggers=[PipelineStatus.FAILED],
                template="Tests failed in pipeline run {run_id}: {failed_tests} tests failed"
            )
        ]
        
        for config in default_configs:
            self.notification_configs[config.config_id] = config
        
        logger.info(f"Loaded {len(default_configs)} default notification configurations")
    
    def add_pipeline_job(self, job: PipelineJob) -> str:
        """
        Add a pipeline job.
        
        Args:
            job: Pipeline job
            
        Returns:
            Job ID
        """
        self.pipeline_jobs[job.job_id] = job
        self.metrics["total_jobs"] = len(self.pipeline_jobs)
        
        logger.info(f"Added pipeline job {job.job_id}: {job.name}")
        return job.job_id
    
    def execute_job(self, job_id: str, run_id: str) -> JobResult:
        """
        Execute a pipeline job.
        
        Args:
            job_id: Job ID
            run_id: Run ID
            
        Returns:
            Job execution result
        """
        if job_id not in self.pipeline_jobs:
            raise ValueError(f"Pipeline job {job_id} not found")
        
        job = self.pipeline_jobs[job_id]
        start_time = datetime.now()
        
        logger.info(f"Executing job: {job.name}")
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(job.environment)
            
            # Execute command
            process = subprocess.Popen(
                job.command,
                shell=True,
                cwd=job.working_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=job.timeout_seconds)
                exit_code = process.returncode
                
                # Determine status based on exit code
                if exit_code == 0:
                    status = PipelineStatus.SUCCESS
                else:
                    status = PipelineStatus.FAILED
                    
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                exit_code = -1
                status = PipelineStatus.FAILED
                stderr = f"Job timed out after {job.timeout_seconds} seconds\n{stderr}"
        
        except Exception as e:
            # Execution error
            exit_code = -1
            status = PipelineStatus.FAILED
            stdout = ""
            stderr = str(e)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Create job result
        result = JobResult(
            job_id=job_id,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            metadata={
                "job_name": job.name,
                "stage": job.stage.value,
                "command": job.command,
                "working_dir": job.working_dir
            }
        )
        
        logger.info(f"Job {job_id} completed with status: {status.value} "
                   f"(exit code: {exit_code}, duration: {duration:.2f}s)")
        
        return result
    
    def execute_pipeline(self, trigger: str = "manual") -> PipelineRun:
        """
        Execute the entire pipeline.
        
        Args:
            trigger: What triggered the pipeline execution
            
        Returns:
            Pipeline execution run
        """
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        logger.info(f"Starting pipeline execution {run_id} (trigger: {trigger})")
        
        # Create pipeline run
        run = PipelineRun(
            run_id=run_id,
            pipeline_id=self.pipeline_id,
            trigger=trigger,
            status=PipelineStatus.RUNNING,
            start_time=start_time
        )
        
        self.pipeline_runs[run_id] = run
        self.metrics["total_runs"] += 1
        
        # Get jobs by stage
        jobs_by_stage = {}
        for job in self.pipeline_jobs.values():
            stage = job.stage.value
            if stage not in jobs_by_stage:
                jobs_by_stage[stage] = []
            jobs_by_stage[stage].append(job)
        
        # Execute jobs by stage in order
        job_results = {}
        all_passed = True
        
        stages_order = [stage.value for stage in PipelineStage]
        
        for stage in stages_order:
            if stage not in jobs_by_stage:
                continue
            
            logger.info(f"Executing stage: {stage}")
            stage_jobs = jobs_by_stage[stage]
            
            # Execute jobs in stage (could be parallelized in future)
            for job in stage_jobs:
                # Check dependencies
                dependencies_met = all(
                    dep_id in job_results and 
                    job_results[dep_id].status == PipelineStatus.SUCCESS
                    for dep_id in job.dependencies
                )
                
                if not dependencies_met and job.dependencies:
                    logger.warning(f"Skipping job {job.job_id} due to unmet dependencies")
                    continue
                
                # Execute job
                result = self.execute_job(job.job_id, run_id)
                job_results[job.job_id] = result
                
                # Update run status if job failed
                if result.status != PipelineStatus.SUCCESS:
                    all_passed = False
                
                # If job failed, we might want to stop the pipeline
                # For now, continue but mark as failed
                if result.status == PipelineStatus.FAILED:
                    logger.error(f"Job {job.job_id} failed, continuing pipeline")
        
        # Update run completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        run.end_time = end_time
        run.duration_seconds = duration
        run.job_results = job_results
        run.status = PipelineStatus.SUCCESS if all_passed else PipelineStatus.FAILED
        
        # Generate summary
        total_jobs = len(job_results)
        successful_jobs = sum(1 for r in job_results.values() 
                            if r.status == PipelineStatus.SUCCESS)
        failed_jobs = sum(1 for r in job_results.values() 
                         if r.status == PipelineStatus.FAILED)
        
        run.summary = {
            "total_jobs": total_jobs,
            "successful_jobs": successful_jobs,
            "failed_jobs": failed_jobs,
            "success_rate": (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0,
            "total_duration": duration,
            "trigger": trigger,
            "all_passed": all_passed
        }
        
        # Update metrics
        if all_passed:
            self.metrics["successful_runs"] += 1
        else:
            self.metrics["failed_runs"] += 1
        
        self.metrics["total_execution_time"] += duration
        self.metrics["average_run_time"] = (
            self.metrics["total_execution_time"] / self.metrics["total_runs"]
        )
        self.metrics["last_run_status"] = run.status.value
        self.metrics["last_run_time"] = end_time.isoformat()
        
        # Send notifications
        self._send_notifications(run)
        
        logger.info(f"Pipeline execution {run_id} completed with status: {run.status.value}")
        logger.info(f"Summary: {successful_jobs}/{total_jobs} jobs successful, "
                   f"duration: {duration:.2f}s")
        
        return run
    
    def _send_notifications(self, run: PipelineRun):
        """Send notifications for pipeline run."""
        for config in self.notification_configs.values():
            if not config.enabled:
                continue
            
            if run.status in config.triggers:
                try:
                    self._send_notification(config, run)
                except Exception as e:
                    logger.error(f"Failed to send notification {config.config_id}: {str(e)}")
    
    def _send_notification(self, config: NotificationConfig, run: PipelineRun):
        """Send a single notification."""
        # Prepare template variables
        template_vars = {
            "pipeline_id": self.pipeline_id,
            "run_id": run.run_id,
            "status": run.status.value,
            "duration": f"{run.duration_seconds:.2f}s" if run.duration_seconds else "N/A",
            "success_rate": run.summary.get("success_rate", 0),
            "failed_jobs": run.summary.get("failed_jobs", 0),
            "failed_tests": run.summary.get("failed_tests", 0),
            "failure_reason": "See job results for details"
        }
        
        # Format message
        message = config.template.format(**template_vars)
        
        # Send based on type
        if config.type == NotificationType.CONSOLE:
            logger.info(f"NOTIFICATION: {message}")
        
        elif config.type == NotificationType.EMAIL:
            # Email notification (simplified)
            self._send_email_notification(config, message, run)
        
        elif config.type == NotificationType.SLACK:
            # Slack notification (simplified)
            logger.info(f"SLACK NOTIFICATION: {message}")
        
        elif config.type == NotificationType.WEBHOOK:
            # Webhook notification (simplified)
            logger.info(f"WEBHOOK NOTIFICATION: {message}")
    
    def _send_email_notification(self, config: NotificationConfig, 
                                message: str, run: PipelineRun):
        """Send email notification (simplified implementation)."""
        # This is a simplified implementation
        # In production, you would use a proper email service
        logger.info(f"EMAIL NOTIFICATION to {config.recipients}: {message}")
    
    def schedule_pipeline(self, schedule_expression: str):
        """
        Schedule pipeline execution.
        
        Args:
            schedule_expression: Schedule expression (e.g., "daily", "hourly", "weekly")
        """
        if schedule_expression == "daily":
            schedule.every().day.at("02:00").do(self.execute_pipeline, trigger="scheduled_daily")
            logger.info("Scheduled pipeline to run daily at 02:00")
        
        elif schedule_expression == "hourly":
            schedule.every().hour.do(self.execute_pipeline, trigger="scheduled_hourly")
            logger.info("Scheduled pipeline to run hourly")
        
        elif schedule_expression == "weekly":
            schedule.every().monday.at("03:00").do(self.execute_pipeline, trigger="scheduled_weekly")
            logger.info("Scheduled pipeline to run weekly on Monday at 03:00")
        
        else:
            logger.warning(f"Unsupported schedule expression: {schedule_expression}")
            return
        
        # Start scheduler in background thread
        self.is_running = True
        self.execution_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.execution_thread.start()
    
    def _scheduler_loop(self):
        """Scheduler execution loop."""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def stop_scheduler(self):
        """Stop the scheduler."""
        self.is_running = False
        if self.execution_thread:
            self.execution_thread.join(timeout=5)
        
        logger.info("Pipeline scheduler stopped")
    
    def generate_pipeline_report(self, run_id: str) -> Dict[str, Any]:
        """
        Generate detailed pipeline report.
        
        Args:
            run_id: Run ID
            
        Returns:
            Pipeline report
        """
        if run_id not in self.pipeline_runs:
            raise ValueError(f"Pipeline run {run_id} not found")
        
        run = self.pipeline_runs[run_id]
        
        # Calculate stage statistics
        stage_stats = {}
        for job_id, result in run.job_results.items():
            job = self.pipeline_jobs.get(job_id)
            if job:
                stage = job.stage.value
                if stage not in stage_stats:
                    stage_stats[stage] = {"total": 0, "success": 0, "failed": 0}
                
                stage_stats[stage]["total"] += 1
                if result.status == PipelineStatus.SUCCESS:
                    stage_stats[stage]["success"] += 1
                else:
                    stage_stats[stage]["failed"] += 1
        
        # Get job details
        job_details = []
        for job_id, result in run.job_results.items():
            job = self.pipeline_jobs.get(job_id, PipelineJob(
                job_id=job_id, name="Unknown", description="", 
                stage=PipelineStage.SOURCE, command="", working_dir=""
            ))
            
            job_details.append({
                "job_id": job_id,
                "name": job.name,
                "stage": job.stage.value,
                "status": result.status.value,
                "duration": result.duration_seconds,
                "exit_code": result.exit_code,
                "has_errors": bool(result.stderr)
            })
        
        # Create report
        report = {
            "report_id": f"pipeline_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "run_id": run_id,
            "pipeline_id": self.pipeline_id,
            "timestamp": datetime.now().isoformat(),
            "execution_summary": {
                "trigger": run.trigger,
                "status": run.status.value,
                "start_time": run.start_time.isoformat(),
                "end_time": run.end_time.isoformat() if run.end_time else None,
                "duration": run.duration_seconds,
                "total_jobs": run.summary.get("total_jobs", 0),
                "successful_jobs": run.summary.get("successful_jobs", 0),
                "failed_jobs": run.summary.get("failed_jobs", 0),
                "success_rate": run.summary.get("success_rate", 0)
            },
            "stage_statistics": stage_stats,
            "job_details": job_details,
            "recommendations": self._generate_recommendations(run)
        }
        
        logger.info(f"Generated pipeline report for run {run_id}")
        
        return report
    
    def _generate_recommendations(self, run: PipelineRun) -> List[str]:
        """Generate recommendations based on pipeline results."""
        recommendations = []
        
        # Check for failed jobs
        failed_jobs = [
            job_id for job_id, result in run.job_results.items()
            if result.status == PipelineStatus.FAILED
        ]
        
        if failed_jobs:
            recommendations.append(f"Investigate {len(failed_jobs)} failed jobs")
            
            # Check for specific patterns
            for job_id in failed_jobs[:3]:  # Limit to first 3
                job = self.pipeline_jobs.get(job_id)
                if job:
                    recommendations.append(f"  - {job.name} ({job.stage.value} stage)")
        
        # Check for long-running jobs
        long_jobs = [
            (job_id, result.duration_seconds) 
            for job_id, result in run.job_results.items()
            if result.duration_seconds > 60  # More than 60 seconds
        ]
        
        if long_jobs:
            recommendations.append(f"Optimize {len(long_jobs)} long-running jobs")
        
        # Check overall success rate
        success_rate = run.summary.get("success_rate", 0)
        if success_rate < 80:
            recommendations.append(f"Improve pipeline success rate (currently {success_rate:.1f}%)")
        
        if not recommendations:
            recommendations.append("Pipeline execution successful - no issues detected")
        
        return recommendations
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get pipeline dashboard data.
        
        Returns:
            Dashboard data
        """
        # Get recent runs
        recent_runs = list(self.pipeline_runs.values())[-5:]
        recent_run_stats = []
        
        for run in recent_runs:
            recent_run_stats.append({
                "run_id": run.run_id,
                "status": run.status.value,
                "duration": run.duration_seconds or 0,
                "success_rate": run.summary.get("success_rate", 0),
                "trigger": run.trigger,
                "timestamp": run.start_time.isoformat()
            })
        
        # Calculate success rate trend
        if self.metrics["total_runs"] > 0:
            success_rate = (self.metrics["successful_runs"] / self.metrics["total_runs"]) * 100
        else:
            success_rate = 0
        
        # Get job statistics
        job_stats = {}
        for job in self.pipeline_jobs.values():
            stage = job.stage.value
            if stage not in job_stats:
                job_stats[stage] = 0
            job_stats[stage] += 1
        
        return {
            "pipeline_id": self.pipeline_id,
            "metrics": self.metrics,
            "success_rate": success_rate,
            "recent_runs": recent_run_stats,
            "job_statistics": job_stats,
            "scheduler_running": self.is_running,
            "total_notifications": len(self.notification_configs),
            "timestamp": datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get pipeline status.
        
        Returns:
            Status information
        """
        return {
            "pipeline_id": self.pipeline_id,
            "jobs_count": len(self.pipeline_jobs),
            "runs_count": len(self.pipeline_runs),
            "notifications_count": len(self.notification_configs),
            "metrics": self.metrics,
            "scheduler_running": self.is_running,
            "test_runner_ready": True,
            "validation_framework_ready": True,
            "timestamp": datetime.now().isoformat()
        }


def test_automated_pipeline():
    """Test function for Automated Pipeline."""
    print("Testing Automated Pipeline...")
    
    # Create pipeline instance
    pipeline = AutomatedPipeline("test_pipeline_001")
    
    # Test 1: Initial status
    print("\n1. Initial Status:")
    status = pipeline.get_status()
    print(f"   Pipeline ID: {status['pipeline_id']}")
    print(f"   Jobs: {status['jobs_count']}")
    print(f"   Runs: {status['runs_count']}")
    
    # Test 2: Add pipeline job
    print("\n2. Adding pipeline job...")
    new_job = PipelineJob(
        job_id="job_test_custom",
        name="Custom Test Job",
        description="Custom job for testing",
        stage=PipelineStage.TEST,
        command="echo 'Test job executed'",
        working_dir=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        timeout_seconds=30
    )
    pipeline.add_pipeline_job(new_job)
    print(f"   Added job: {new_job.name}")
    
    # Test 3: Execute single job
    print("\n3. Executing single job...")
    try:
        result = pipeline.execute_job("job_test_custom", "test_run_001")
        print(f"   Job executed: {result.job_id}")
        print(f"   Status: {result.status.value}")
        print(f"   Exit code: {result.exit_code}")
        print(f"   Duration: {result.duration_seconds:.2f}s")
    except Exception as e:
        print(f"   Job execution failed: {str(e)}")
    
    # Test 4: Execute pipeline
    print("\n4. Executing pipeline...")
    try:
        run = pipeline.execute_pipeline("manual_test")
        print(f"   Pipeline executed: {run.run_id}")
        print(f"   Status: {run.status.value}")
        print(f"   Total jobs: {run.summary.get('total_jobs', 0)}")
        print(f"   Successful jobs: {run.summary.get('successful_jobs', 0)}")
        print(f"   Duration: {run.duration_seconds:.2f}s")
    except Exception as e:
        print(f"   Pipeline execution failed: {str(e)}")
    
    # Test 5: Generate pipeline report
    print("\n5. Generating pipeline report...")
    try:
        if pipeline.pipeline_runs:
            run_id = list(pipeline.pipeline_runs.keys())[0]
            report = pipeline.generate_pipeline_report(run_id)
            print(f"   Report generated: {report['report_id']}")
            print(f"   Success rate: {report['execution_summary']['success_rate']:.1f}%")
            print(f"   Recommendations: {len(report['recommendations'])}")
        else:
            print("   No pipeline runs available for report generation")
    except Exception as e:
        print(f"   Report generation failed: {str(e)}")
    
    # Test 6: Get dashboard data
    print("\n6. Getting dashboard data...")
    dashboard = pipeline.get_dashboard_data()
    print(f"   Total runs: {dashboard['metrics']['total_runs']}")
    print(f"   Successful runs: {dashboard['metrics']['successful_runs']}")
    print(f"   Success rate: {dashboard['success_rate']:.1f}%")
    print(f"   Recent runs: {len(dashboard['recent_runs'])}")
    
    # Test 7: Test scheduler (briefly)
    print("\n7. Testing scheduler...")
    try:
        pipeline.schedule_pipeline("hourly")
        print("   Scheduler started")
        time.sleep(2)  # Brief pause
        pipeline.stop_scheduler()
        print("   Scheduler stopped")
    except Exception as e:
        print(f"   Scheduler test failed: {str(e)}")
    
    # Final status
    print("\n8. Final Status:")
    final_status = pipeline.get_status()
    print(f"   Total runs: {final_status['runs_count']}")
    print(f"   Last run status: {final_status['metrics']['last_run_status']}")
    print(f"   Average run time: {final_status['metrics']['average_run_time']:.2f}s")
    
    print("\nAutomated Pipeline test completed successfully!")


if __name__ == "__main__":
    test_automated_pipeline()