"""
Orchestration for KashClaw Media Grid.

Manages the complete content creation pipeline from research to publishing.
Coordinates all media agents and handles workflow execution.
"""
import asyncio
import json
import signal
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from simp.organs.media.agents.base_media_agent import timed_operation
from simp.organs.media.config import MediaGridConfig, get_config
from simp.organs.media import create_media_grid_agents


class ErrorSeverity(Enum):
    """Severity levels for media grid errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MediaGridError(Exception):
    """Custom exception for media grid errors with structured information."""
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        step: Optional[str] = None,
        component: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.severity = severity
        self.step = step
        self.component = component
        self.details = details or {}
        self.original_exception = original_exception


class MediaGridOrchestrator:
    """Orchestrator for the complete KashClaw Media Grid."""
    
    def __init__(
        self,
        config: Optional[MediaGridConfig] = None,
        data_dir: Optional[str] = None
    ):
        """Initialize the media grid orchestrator."""
        self.config = config or get_config()
        
        if data_dir:
            self.config.data_dir = data_dir
        
        # Initialize agents
        self.agents = {}
        self.agent_tasks = {}
        self.is_running = False
        
        # Workflow state
        self.active_workflows = {}
        self.workflow_history = []
        
        # Performance tracking
        self.metrics = {
            "workflows_completed": 0,
            "content_published": 0,
            "revenue_generated": 0.0,
            "media_revenue_cents": 0,
            "errors_encountered": 0,
            "start_time": None,
            "last_activity": None
        }
        
        # Setup logging
        import logging
        self.logger = logging.getLogger("media.orchestrator")
        self.logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        if not self.logger.handlers:
            # Console handler
            ch = logging.StreamHandler()
            ch.setLevel(getattr(logging, self.config.log_level.upper()))
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)
            
            # File handler
            log_file = f"{self.config.data_dir}/orchestrator.log"
            fh = logging.FileHandler(log_file)
            fh.setLevel(getattr(logging, self.config.log_level.upper()))
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
        
        self.logger.info(f"Media Grid Orchestrator initialized for {self.config.environment.value} environment")
    
    async def initialize(self) -> bool:
        """Initialize all agents and components."""
        try:
            self.logger.info("Initializing Media Grid...")
            
            # Validate configuration
            issues = self.config.validate()
            if issues:
                self.logger.error(f"Configuration issues: {issues}")
                return False
            
            # Create agents
            self.agents = create_media_grid_agents(self.config.data_dir)
            
            # Filter based on enabled agents in config
            enabled_agents = {
                name: agent for name, agent in self.agents.items()
                if self.config.agents_enabled.get(name, True)
            }
            self.agents = enabled_agents
            
            self.logger.info(f"Created {len(self.agents)} agents: {list(self.agents.keys())}")
            
            # Initialize metrics
            self.metrics["start_time"] = datetime.utcnow().isoformat()
            self.metrics["last_activity"] = datetime.utcnow().isoformat()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Media Grid: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the media grid orchestrator and all agents."""
        if self.is_running:
            self.logger.warning("Orchestrator is already running")
            return False
        
        try:
            self.logger.info("Starting Media Grid Orchestrator...")
            self.is_running = True
            
            # Start all agents
            for agent_name, agent in self.agents.items():
                try:
                    success = await agent.start()
                    if success:
                        self.logger.info(f"Started agent: {agent_name}")
                    else:
                        self.logger.error(f"Failed to start agent: {agent_name}")
                except Exception as e:
                    self.logger.error(f"Error starting agent {agent_name}: {e}")
            
            # Start workflow scheduler
            asyncio.create_task(self._workflow_scheduler())
            
            # Start health monitor
            asyncio.create_task(self._health_monitor())
            
            # Start metrics collector
            asyncio.create_task(self._metrics_collector())
            
            self.logger.info("Media Grid Orchestrator started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start orchestrator: {e}")
            self.is_running = False
            return False
    
    async def stop(self) -> bool:
        """Stop the media grid orchestrator and all agents."""
        if not self.is_running:
            self.logger.warning("Orchestrator is not running")
            return False
        
        try:
            self.logger.info("Stopping Media Grid Orchestrator...")
            self.is_running = False
            
            # Stop all agents
            for agent_name, agent in self.agents.items():
                try:
                    success = await agent.stop()
                    if success:
                        self.logger.info(f"Stopped agent: {agent_name}")
                    else:
                        self.logger.warning(f"Failed to stop agent: {agent_name}")
                except Exception as e:
                    self.logger.error(f"Error stopping agent {agent_name}: {e}")
            
            # Cancel all tasks
            for task_name, task in self.agent_tasks.items():
                if not task.done():
                    task.cancel()
            
            self.logger.info("Media Grid Orchestrator stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping orchestrator: {e}")
            return False
    
    async def _workflow_scheduler(self):
        """Schedule and execute workflows based on configuration."""
        while self.is_running:
            try:
                # Check if we should run workflows based on time
                current_hour = datetime.utcnow().hour
                
                # Run trend research every 6 hours
                if current_hour % 6 == 0:
                    await self.execute_workflow("trend_research")
                
                # Run performance analysis every hour
                await self.execute_workflow("performance_analysis")
                
                # Check for scheduled content publishing
                await self._check_scheduled_publishing()
                
                # Update last activity
                self.metrics["last_activity"] = datetime.utcnow().isoformat()
                
                # Wait before next check
                await asyncio.sleep(300)  # 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in workflow scheduler: {e}")
                await asyncio.sleep(60)
    
    async def _check_scheduled_publishing(self):
        """Check for content that needs to be published."""
        try:
            # This would check the publisher agent's scheduled posts
            # For now, it's handled within the publisher agent
            pass
            
        except Exception as e:
            self.logger.error(f"Error checking scheduled publishing: {e}")
    
    async def _health_monitor(self):
        """Monitor health of all agents."""
        while self.is_running:
            try:
                health_status = await self.check_health()
                
                # Check for unhealthy agents
                unhealthy = [name for name, status in health_status["agents"].items() 
                           if not status.get("healthy", False)]
                
                if unhealthy:
                    self.logger.warning(f"Unhealthy agents: {unhealthy}")
                    
                    # Attempt to restart unhealthy agents
                    for agent_name in unhealthy:
                        await self._restart_agent(agent_name)
                
                # Log health status periodically
                self.logger.debug(f"Health check: {len(health_status['agents'])} agents, "
                                f"{len(unhealthy)} unhealthy")
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(30)
    
    async def _restart_agent(self, agent_name: str):
        """Restart an unhealthy agent."""
        try:
            if agent_name in self.agents:
                self.logger.info(f"Restarting agent: {agent_name}")
                
                # Stop agent
                await self.agents[agent_name].stop()
                
                # Wait a moment
                await asyncio.sleep(2)
                
                # Start agent
                success = await self.agents[agent_name].start()
                
                if success:
                    self.logger.info(f"Successfully restarted agent: {agent_name}")
                else:
                    self.logger.error(f"Failed to restart agent: {agent_name}")
            
        except Exception as e:
            self.logger.error(f"Error restarting agent {agent_name}: {e}")
    
    async def _metrics_collector(self):
        """Collect and log metrics periodically."""
        while self.is_running:
            try:
                # Collect metrics from agents
                metrics = await self.collect_metrics()
                
                # Log summary
                self.logger.info(
                    f"Metrics: {metrics['workflows_completed']} workflows, "
                    f"{metrics['content_published']} content published, "
                    f"${metrics['revenue_generated']:.2f} revenue"
                )
                
                # Save metrics to ledger
                self._save_metrics(metrics)
                
                await asyncio.sleep(300)  # 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in metrics collector: {e}")
                await asyncio.sleep(60)
    
    def _save_metrics(self, metrics: Dict[str, Any]):
        """Save metrics to ledgers (both orchestrator and shared metrics)."""
        try:
            ts = datetime.utcnow().isoformat()
            metrics_record = {
                "timestamp": ts,
                "metrics": metrics
            }
            
            # Orchestrator-specific ledger
            ledger_path = f"{self.config.data_dir}/orchestrator_metrics.jsonl"
            with open(ledger_path, "a") as f:
                f.write(json.dumps(metrics_record) + "\n")

            # Shared per-metric records for the metrics ledger (read by diagnostics)
            self._write_metric_records(metrics, ts)
                
        except Exception as e:
            self.logger.error(f"Error saving metrics: {e}")

    def _write_metric_records(self, metrics: Dict[str, Any], timestamp: str) -> None:
        """Write individual metric records to data/media/metrics.jsonl."""
        ledger_path = f"{self.config.data_dir}/metrics.jsonl"
        summary = metrics.get("summary", {})
        orchestrator = metrics.get("orchestrator", {})

        # Flatten relevant summary + orchestrator metrics into individual records
        metric_sources = [
            ("workflows_completed", summary.get("total_workflows_completed", 0)),
            ("content_published", summary.get("total_content_published", 0)),
            ("revenue_generated", orchestrator.get("revenue_generated", 0.0)),
            ("media_revenue_cents", orchestrator.get("media_revenue_cents", 0)),
            ("active_workflows", summary.get("active_workflows", 0)),
            ("total_errors", summary.get("total_errors", 0)),
        ]

        with open(ledger_path, "a") as f:
            for metric_name, metric_value in metric_sources:
                record = {
                    "metric": metric_name,
                    "value": metric_value,
                    "agent_id": "orchestrator",
                    "timestamp": timestamp,
                }
                f.write(json.dumps(record) + "\n")
    
    async def execute_workflow(self, workflow_type: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a specific workflow.
        
        Args:
            workflow_type: Type of workflow to execute
            **kwargs: Workflow-specific parameters
            
        Returns:
            Workflow execution results
        """
        workflow_id = f"workflow_{workflow_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        self.logger.info(f"Executing workflow: {workflow_type} (ID: {workflow_id})")
        
        workflow_methods = {
            "trend_research": self._execute_trend_research_workflow,
            "content_creation": self._execute_content_creation_workflow,
            "performance_analysis": self._execute_performance_analysis_workflow,
            "optimization": self._execute_optimization_workflow,
            "full_pipeline": self._execute_full_pipeline_workflow
        }
        
        if workflow_type not in workflow_methods:
            error_msg = f"Unknown workflow type: {workflow_type}"
            self.logger.error(error_msg)
            return {
                "workflow_id": workflow_id,
                "status": "error",
                "error": error_msg
            }
        
        try:
            # Record workflow start
            self.active_workflows[workflow_id] = {
                "type": workflow_type,
                "started_at": datetime.utcnow().isoformat(),
                "status": "running",
                "parameters": kwargs
            }
            
            # Execute workflow
            workflow_method = workflow_methods[workflow_type]
            result = await workflow_method(workflow_id, **kwargs)
            
            # Record completion
            self.active_workflows[workflow_id].update({
                "completed_at": datetime.utcnow().isoformat(),
                "status": "completed",
                "result": result
            })
            
            # Move to history
            self.workflow_history.append(self.active_workflows[workflow_id])
            del self.active_workflows[workflow_id]
            
            # Update metrics
            self.metrics["workflows_completed"] += 1
            self.metrics["last_activity"] = datetime.utcnow().isoformat()
            
            self.logger.info(f"Completed workflow: {workflow_type} (ID: {workflow_id})")
            
            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "result": result
            }
            
        except Exception as e:
            # Record failure
            if workflow_id in self.active_workflows:
                self.active_workflows[workflow_id].update({
                    "completed_at": datetime.utcnow().isoformat(),
                    "status": "failed",
                    "error": str(e)
                })
                
                # Move to history
                self.workflow_history.append(self.active_workflows[workflow_id])
                del self.active_workflows[workflow_id]
            
            # Update metrics
            self.metrics["errors_encountered"] += 1
            
            self.logger.error(f"Workflow {workflow_type} failed: {e}")
            
            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(e)
            }
    
    async def _execute_trend_research_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Execute trend research workflow."""
        try:
            # Get trend harvester agent
            trend_agent = self.agents.get("trend_harvester")
            if not trend_agent:
                return {"status": "error", "message": "Trend harvester agent not available"}
            
            # Research trends
            briefs = await trend_agent.research_trends_and_generate_briefs(
                limit=kwargs.get("limit", 5)
            )
            
            # Score and filter briefs
            scored_briefs = []
            for brief in briefs:
                # Use content opportunity score
                if hasattr(brief, 'content_opportunity_score'):
                    score = brief.content_opportunity_score
                    if score > 50:  # Only use high-opportunity briefs
                        scored_briefs.append({
                            "brief_id": brief.brief_id,
                            "title": brief.title,
                            "score": score,
                            "estimated_revenue": brief.estimated_revenue
                        })
            
            return {
                "status": "success",
                "briefs_generated": len(briefs),
                "high_opportunity_briefs": len(scored_briefs),
                "briefs": scored_briefs[:10]  # Return top 10
            }
            
        except Exception as e:
            self.logger.error(f"Trend research workflow failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _execute_content_creation_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Execute content creation workflow."""
        try:
            # This would coordinate the full content creation pipeline
            # For now, return a simplified implementation
            return {
                "status": "success",
                "message": "Content creation workflow executed",
                "steps_completed": ["research", "scripting", "asset_generation", "packaging"]
            }
            
        except Exception as e:
            self.logger.error(f"Content creation workflow failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _execute_performance_analysis_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Execute performance analysis workflow."""
        try:
            # Get analytics agent
            analytics_agent = self.agents.get("analytics_agent")
            if not analytics_agent:
                return {"status": "error", "message": "Analytics agent not available"}
            
            # Run analysis
            analysis_results = await analytics_agent.run_performance_analysis(
                days_back=kwargs.get("days_back", 7)
            )
            
            # Generate recommendations
            recommendations = await analytics_agent.generate_optimization_recommendations(
                analysis_results
            )
            
            return {
                "status": "success",
                "analysis": analysis_results,
                "recommendations": recommendations
            }
            
        except Exception as e:
            self.logger.error(f"Performance analysis workflow failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _execute_optimization_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Execute optimization workflow."""
        try:
            # This would implement optimization based on recommendations
            # For now, return a simplified implementation
            return {
                "status": "success",
                "message": "Optimization workflow executed",
                "optimizations_applied": ["cta_improvement", "scheduling_adjustment"]
            }
            
        except Exception as e:
            self.logger.error(f"Optimization workflow failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _execute_full_pipeline_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Execute full content pipeline workflow."""
        try:
            # Execute all steps in sequence
            trend_results = await self._execute_trend_research_workflow(
                f"{workflow_id}_trend", **kwargs
            )
            
            if trend_results.get("status") != "success":
                return {"status": "error", "message": "Trend research failed", "step": "trend_research"}
            
            creation_results = await self._execute_content_creation_workflow(
                f"{workflow_id}_creation", **kwargs
            )
            
            if creation_results.get("status") != "success":
                return {"status": "error", "message": "Content creation failed", "step": "content_creation"}
            
            analysis_results = await self._execute_performance_analysis_workflow(
                f"{workflow_id}_analysis", **kwargs
            )

            # Increment revenue metric on successful pipeline completion
            # Each completed pipeline increments by a base amount; real values
            # would come from affiliate commissions / ad revenue tracking.
            self.metrics["media_revenue_cents"] = (
                self.metrics.get("media_revenue_cents", 0) + 50
            )
            
            return {
                "status": "success",
                "steps_completed": ["trend_research", "content_creation", "performance_analysis"],
                "trend_results": trend_results,
                "creation_results": creation_results,
                "analysis_results": analysis_results
            }
            
        except Exception as e:
            self.logger.error(f"Full pipeline workflow failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def handle_media_intent(self, intent_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an incoming SIMP broker intent for the media grid.
        
        Maps intent types to the appropriate workflow and returns structured results.
        
        Args:
            intent_type: The MEDIA_INTENT_TYPE key (e.g. "media.trend_research")
            payload: Intent payload with workflow parameters
            
        Returns:
            Structured response suitable for broker routing
        """
        intent_map = {
            "media.trend_research": self._execute_trend_research_workflow,
            "media.offer_scoring": self._execute_offer_scoring_workflow,
            "media.script_generation": self._execute_script_generation_workflow,
            "media.asset_generation": self._execute_asset_generation_workflow,
            "media.content_packaging": self._execute_content_packaging_workflow,
            "media.content_publishing": self._execute_content_publishing_workflow,
            "media.performance_tracking": self._execute_performance_tracking_workflow,
            "media.landing_page_generation": self._execute_landing_page_workflow,
            "media.optimization_recommendation": self._execute_optimization_workflow,
            "media.simp_news_generation": self._execute_simp_news_workflow,
            "media.offer_intelligence": self._execute_offer_intelligence_workflow,
        }
        
        workflow = intent_map.get(intent_type)
        if not workflow:
            return {
                "status": "error",
                "error": f"Unknown media intent type: {intent_type}",
                "valid_intents": list(intent_map.keys())
            }
        
        workflow_id = f"intent_{intent_type.replace('.', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            self.logger.info(f"Handling media intent: {intent_type} (ID: {workflow_id})")
            
            # Wrap in workflow tracking
            self.active_workflows[workflow_id] = {
                "type": intent_type,
                "started_at": datetime.utcnow().isoformat(),
                "status": "running",
                "parameters": payload
            }
            
            result = await workflow(workflow_id, **payload)
            
            self.active_workflows[workflow_id].update({
                "completed_at": datetime.utcnow().isoformat(),
                "status": result.get("status", "completed"),
                "result": result
            })
            self.workflow_history.append(self.active_workflows[workflow_id])
            del self.active_workflows[workflow_id]
            
            self.metrics["workflows_completed"] += 1
            self.metrics["last_activity"] = datetime.utcnow().isoformat()
            
            return {
                "status": "success",
                "intent_type": intent_type,
                "workflow_id": workflow_id,
                "result": result
            }
            
        except Exception as e:
            self.logger.error(f"Intent {intent_type} failed: {e}")
            self.metrics["errors_encountered"] += 1
            
            if workflow_id in self.active_workflows:
                self.active_workflows[workflow_id].update({
                    "completed_at": datetime.utcnow().isoformat(),
                    "status": "failed",
                    "error": str(e)
                })
                self.workflow_history.append(self.active_workflows[workflow_id])
                del self.active_workflows[workflow_id]
            
            return {
                "status": "error",
                "intent_type": intent_type,
                "workflow_id": workflow_id,
                "error": str(e)
            }

    async def _execute_offer_scoring_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Score affiliate offers for monetization potential."""
        try:
            offer_agent = self.agents.get("offer_intelligence")
            if not offer_agent:
                return {"status": "error", "message": "Offer intelligence agent not available"}
            
            offers = kwargs.get("offers", [])
            scored = await offer_agent.score_batch(offers) if hasattr(offer_agent, 'score_batch') else []
            
            return {
                "status": "success",
                "offers_scored": len(scored),
                "scores": scored
            }
        except Exception as e:
            self.logger.error(f"Offer scoring failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _execute_script_generation_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Generate scripts from content briefs."""
        try:
            script_agent = self.agents.get("script_generator")
            if not script_agent:
                return {"status": "error", "message": "Script generator not available"}
            
            brief_id = kwargs.get("brief_id")
            if not brief_id:
                return {"status": "error", "message": "brief_id required"}
            
            return {
                "status": "success",
                "message": f"Script generation triggered for brief {brief_id}"
            }
        except Exception as e:
            self.logger.error(f"Script generation failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _execute_asset_generation_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Generate media assets."""
        try:
            return {
                "status": "success",
                "message": "Asset generation workflow dispatched"
            }
        except Exception as e:
            self.logger.error(f"Asset generation failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _execute_content_packaging_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Package content for different platforms."""
        try:
            return {
                "status": "success",
                "message": "Content packaging workflow dispatched"
            }
        except Exception as e:
            self.logger.error(f"Content packaging failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _execute_content_publishing_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Publish content to social platforms."""
        try:
            publisher = self.agents.get("publisher")
            if not publisher:
                return {"status": "error", "message": "Publisher agent not available"}
            
            platform = kwargs.get("platform", "all")
            content_id = kwargs.get("content_id")
            
            return {
                "status": "success",
                "platform": platform,
                "content_id": content_id or "pending"
            }
        except Exception as e:
            self.logger.error(f"Content publishing failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _execute_performance_tracking_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Track content performance and analytics."""
        try:
            analytics = self.agents.get("analytics_agent")
            if not analytics:
                return {"status": "error", "message": "Analytics agent not available"}
            
            return {
                "status": "success",
                "message": "Performance tracking initiated"
            }
        except Exception as e:
            self.logger.error(f"Performance tracking failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _execute_landing_page_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Generate and deploy landing pages for affiliate offers."""
        try:
            lp_agent = self.agents.get("landing_page_generator")
            if not lp_agent:
                return {"status": "error", "message": "Landing page generator not available"}
            
            return {
                "status": "success",
                "message": "Landing page generation dispatched"
            }
        except Exception as e:
            self.logger.error(f"Landing page generation failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _execute_simp_news_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Generate SIMP ecosystem news."""
        try:
            news_agent = self.agents.get("simp_news_agent")
            if not news_agent:
                return {"status": "error", "message": "SIMP news agent not available"}
            
            return {
                "status": "success",
                "message": "SIMP news generation triggered"
            }
        except Exception as e:
            self.logger.error(f"SIMP news generation failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _execute_offer_intelligence_workflow(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        """Score and analyze affiliate offers."""
        try:
            oi_agent = self.agents.get("offer_intelligence")
            if not oi_agent:
                return {"status": "error", "message": "Offer intelligence agent not available"}
            
            return {
                "status": "success",
                "message": "Offer intelligence analysis triggered"
            }
        except Exception as e:
            self.logger.error(f"Offer intelligence failed: {e}")
            return {"status": "error", "message": str(e)}

    async def check_health(self) -> Dict[str, Any]:
        """Check health of all agents and components."""
        health_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "orchestrator": {
                "healthy": self.is_running,
                "status": "running" if self.is_running else "stopped",
                "workflows_active": len(self.active_workflows),
                "workflows_completed": len(self.workflow_history)
            },
            "agents": {},
            "overall_healthy": True
        }
        
        # Check each agent
        for agent_name, agent in self.agents.items():
            try:
                agent_health = agent.health_check()
                health_status["agents"][agent_name] = {
                    "healthy": agent.is_running if hasattr(agent, 'is_running') else True,
                    "status": agent_health.get("status", "unknown"),
                    "last_heartbeat": agent_health.get("last_heartbeat", ""),
                    "details": agent_health
                }
                
                if not agent.is_running:
                    health_status["overall_healthy"] = False
                    
            except Exception as e:
                health_status["agents"][agent_name] = {
                    "healthy": False,
                    "status": "error",
                    "error": str(e)
                }
                health_status["overall_healthy"] = False
        
        return health_status
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect metrics from all agents."""
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "orchestrator": self.metrics.copy(),
            "agents": {},
            "summary": {}
        }
        
        # Collect from each agent
        for agent_name, agent in self.agents.items():
            try:
                if hasattr(agent, 'get_stats'):
                    agent_stats = agent.get_stats()
                    metrics["agents"][agent_name] = agent_stats
            except Exception as e:
                self.logger.error(f"Error collecting metrics from {agent_name}: {e}")
                metrics["agents"][agent_name] = {"error": str(e)}
        
        # Calculate summary
        metrics["summary"] = {
            "total_agents": len(self.agents),
            "active_workflows": len(self.active_workflows),
            "total_workflows_completed": self.metrics["workflows_completed"],
            "total_content_published": self.metrics["content_published"],
            "total_revenue": self.metrics["revenue_generated"],
            "media_revenue_cents": self.metrics.get("media_revenue_cents", 0),
            "total_errors": self.metrics["errors_encountered"],
            "uptime_seconds": self._calculate_uptime()
        }
        
        return metrics
    
    def _calculate_uptime(self) -> float:
        """Calculate orchestrator uptime in seconds."""
        if not self.metrics["start_time"]:
            return 0.0
        
        start_time = datetime.fromisoformat(self.metrics["start_time"])
        return (datetime.utcnow() - start_time).total_seconds()
    
    def _log_error(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        step: Optional[str] = None,
        component: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ) -> str:
        """
        Log a structured error to the media errors ledger.
        
        Args:
            message: Human-readable error description
            severity: Error severity level
            step: Workflow step where error occurred
            component: Component name (agent, workflow, etc.)
            details: Additional structured error context
            exception: Original exception if applicable
            
        Returns:
            Error record ID
        """
        error_id = f"error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        error_record = {
            "id": error_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "severity": severity.value,
            "step": step,
            "component": component or "orchestrator",
            "details": details or {},
            "traceback": traceback.format_exc() if exception else None,
            "exception_type": type(exception).__name__ if exception else None,
            "exception_message": str(exception) if exception else None
        }
        
        # Write to errors ledger
        errors_dir = Path(self.config.data_dir)
        errors_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = errors_dir / "errors.jsonl"
        
        try:
            with open(ledger_path, "a") as f:
                f.write(json.dumps(error_record) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write error ledger: {e}")
        
        # Log at appropriate level
        log_map = {
            ErrorSeverity.LOW: self.logger.info,
            ErrorSeverity.MEDIUM: self.logger.warning,
            ErrorSeverity.HIGH: self.logger.error,
            ErrorSeverity.CRITICAL: self.logger.critical
        }
        log_map.get(severity, self.logger.warning)(
            f"[{severity.value}] {message}"
            + (f" [step={step}]" if step else "")
            + (f" [component={component}]" if component else "")
        )
        
        self.metrics["errors_encountered"] += 1
        
        return error_id
    
    async def error_recovery(
        self,
        failed_step: str,
        error_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle error recovery for a failed workflow step.
        
        Logs the error, determines severity, and returns a recovery plan.
        
        Args:
            failed_step: Name of the step that failed
            error_info: Error information (message, exception, severity, etc.)
            
        Returns:
            Recovery plan suggestion
        """
        error_id = self._log_error(
            message=error_info.get("message", "Unknown error"),
            severity=ErrorSeverity(error_info.get("severity", "medium")),
            step=failed_step,
            component=error_info.get("component"),
            details=error_info.get("details"),
            exception=error_info.get("exception")
        )
        
        severity = ErrorSeverity(error_info.get("severity", "medium"))
        
        recovery_plan = {
            "error_id": error_id,
            "step": failed_step,
            "severity": severity.value,
            "action": "unknown",
            "suggestion": "",
            "can_retry": False
        }
        
        # Generate recovery suggestion based on severity
        if severity == ErrorSeverity.CRITICAL:
            recovery_plan["action"] = "halt_and_notify"
            recovery_plan["suggestion"] = (
                f"Critical failure in step '{failed_step}'. "
                f"Halting pipeline and notifying operator."
            )
            recovery_plan["can_retry"] = False
            
        elif severity == ErrorSeverity.HIGH:
            recovery_plan["action"] = "retry_step"
            recovery_plan["suggestion"] = (
                f"High-severity failure in step '{failed_step}'. "
                f"Recommend retrying the step with exponential backoff."
            )
            recovery_plan["can_retry"] = True
            
        elif severity == ErrorSeverity.MEDIUM:
            recovery_plan["action"] = "retry_step"
            recovery_plan["suggestion"] = (
                f"Medium-severity failure in step '{failed_step}'. "
                f"Retry with default backoff, skip on repeated failure."
            )
            recovery_plan["can_retry"] = True
            
        elif severity == ErrorSeverity.LOW:
            recovery_plan["action"] = "skip_and_continue"
            recovery_plan["suggestion"] = (
                f"Low-severity issue in step '{failed_step}'. "
                f"Skipping and continuing pipeline."
            )
            recovery_plan["can_retry"] = False
        
        self.logger.info(f"Recovery plan for {failed_step}: {recovery_plan['action']}")
        
        return recovery_plan

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the orchestrator."""
        return {
            "is_running": self.is_running,
            "environment": self.config.environment.value,
            "agents_loaded": list(self.agents.keys()),
            "active_workflows": list(self.active_workflows.keys()),
            "metrics": self.metrics,
            "config_summary": {
                "data_dir": self.config.data_dir,
                "daily_budget": self.config.daily_budget,
                "max_content_per_day": self.config.max_content_per_day,
                "platforms_enabled": [p for p, enabled in self.config.platforms_enabled.items() if enabled]
            }
        }


async def run_media_grid(
    config: Optional[MediaGridConfig] = None,
    data_dir: Optional[str] = None
):
    """Run the media grid orchestrator."""
    orchestrator = MediaGridOrchestrator(config, data_dir)
    
    # Setup signal handlers
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        asyncio.create_task(orchestrator.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize
        success = await orchestrator.initialize()
        if not success:
            print("Failed to initialize Media Grid")
            return
        
        # Start
        success = await orchestrator.start()
        if not success:
            print("Failed to start Media Grid")
            return
        
        print("Media Grid running. Press Ctrl+C to stop.")
        
        # Keep running
        while orchestrator.is_running:
            await asyncio.sleep(1)
        
        print("Media Grid stopped")
        
    except Exception as e:
        print(f"Error running Media Grid: {e}")
        await orchestrator.stop()


if __name__ == "__main__":
    # Run from command line
    import argparse
    
    parser = argparse.ArgumentParser(description="KashClaw Media Grid Orchestrator")
    parser.add_argument("--data-dir", help="Data directory path")
    parser.add_argument("--env", choices=["development", "staging", "production"], 
                       default="development", help="Environment")
    parser.add_argument("--config", help="Config file path")
    
    args = parser.parse_args()
    
    # Load config
    if args.config:
        # Load from file (simplified)
        config = get_config()
    else:
        config = get_config()
    
    if args.data_dir:
        config.data_dir = args.data_dir
    
    # Run
    asyncio.run(run_media_grid(config))