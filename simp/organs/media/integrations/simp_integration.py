"""
SIMP broker integration for media agents.

Provides client for communicating with SIMP broker, webhook server for n8n integration,
and dashboard data providers for media metrics.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from urllib.parse import urljoin

import httpx
from flask import Flask, request, jsonify

from ..config import MediaIntentType, MediaAgentConfig, MediaGridConfig
from ..models import (
    ContentBrief, ScriptPackage, GeneratedAsset, PublishedPost,
    PerformanceMetrics, ContentOpportunityScore
)


class SimpMediaError(Exception):
    """Base exception for SIMP media integration errors."""
    pass


class BrokerConnectionError(SimpMediaError):
    """Failed to connect to SIMP broker."""
    pass


class IntentDeliveryError(SimpMediaError):
    """Failed to deliver intent to broker."""
    pass


class WebhookValidationError(SimpMediaError):
    """Webhook validation failed."""
    pass


@dataclass
class IntentResponse:
    """Response from SIMP broker for an intent."""
    
    intent_id: str
    status: str  # "delivered", "queued", "failed"
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


@dataclass
class WebhookEvent:
    """Webhook event from n8n or other external systems."""
    
    event_id: str
    event_type: str
    source: str
    payload: Dict[str, Any]
    timestamp: str = ""
    signature: Optional[str] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


class SimpMediaClient:
    """
    Client for communicating with SIMP broker for media operations.
    
    Handles agent registration, heartbeat, intent routing, and response tracking.
    """
    
    def __init__(self, config: MediaAgentConfig):
        self.config = config
        self.agent_id = config.agent_id
        self.broker_url = config.broker_url.rstrip('/')
        self.api_key = config.api_key
        self.max_retries = config.max_retries
        self.retry_delay = config.retry_delay
        
        self._session = httpx.Client(timeout=30.0)
        self._session.headers.update({
            "User-Agent": f"SIMP-Media-Agent/{self.agent_id}",
            "Content-Type": "application/json"
        })
        if self.api_key:
            self._session.headers["X-API-Key"] = self.api_key
        
        self._registered = False
        self._last_heartbeat = 0
        self._lock = threading.RLock()
        self._logger = logging.getLogger(f"simp.media.client.{self.agent_id}")
        
        # Response tracking
        self._pending_intents: Dict[str, IntentResponse] = {}
        self._response_ledger_path = Path(config.data_dir) / "intent_responses.jsonl"
        self._response_ledger_path.parent.mkdir(parents=True, exist_ok=True)
    
    def register(self) -> bool:
        """Register agent with SIMP broker."""
        with self._lock:
            try:
                registration_data = {
                    "agent_id": self.agent_id,
                    "agent_type": self.config.agent_type.value,
                    "capabilities": self.config.capabilities,
                    "endpoint": f"(file-based)",  # Media agents are file-based
                    "heartbeat_interval": self.config.heartbeat_interval
                }
                
                response = self._session.post(
                    f"{self.broker_url}/agents/register",
                    json=registration_data
                )
                
                if response.status_code == 200:
                    self._registered = True
                    self._last_heartbeat = time.time()
                    self._logger.info(f"Agent {self.agent_id} registered successfully")
                    return True
                else:
                    self._logger.error(f"Registration failed: {response.status_code} - {response.text}")
                    return False
                    
            except Exception as e:
                self._logger.error(f"Registration error: {e}")
                raise BrokerConnectionError(f"Failed to register agent: {e}")
    
    def send_heartbeat(self) -> bool:
        """Send heartbeat to SIMP broker."""
        with self._lock:
            if not self._registered:
                self._logger.warning("Agent not registered, attempting registration")
                return self.register()
            
            try:
                response = self._session.post(
                    f"{self.broker_url}/agents/{self.agent_id}/heartbeat"
                )
                
                if response.status_code == 200:
                    self._last_heartbeat = time.time()
                    return True
                elif response.status_code == 404:
                    # Agent not found, re-register
                    self._registered = False
                    return self.register()
                else:
                    self._logger.warning(f"Heartbeat failed: {response.status_code}")
                    return False
                    
            except Exception as e:
                self._logger.error(f"Heartbeat error: {e}")
                return False
    
    def send_intent(self, intent_type: MediaIntentType, intent_data: Dict[str, Any],
                   target_agent: str = "auto") -> IntentResponse:
        """
        Send intent to SIMP broker for routing.
        
        Args:
            intent_type: Type of media intent
            intent_data: Intent payload
            target_agent: Target agent ID or "auto" for automatic routing
            
        Returns:
            IntentResponse with delivery status
        """
        with self._lock:
            # Ensure we're registered
            if not self._registered:
                if not self.register():
                    raise BrokerConnectionError("Failed to register agent before sending intent")
            
            intent_id = f"media_{intent_type.value}_{int(time.time() * 1000)}"
            
            full_intent = {
                "intent_id": intent_id,
                "intent_type": intent_type.value,
                "source_agent": self.agent_id,
                "target_agent": target_agent,
                "intent_data": intent_data,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            self._logger.debug(f"Sending intent {intent_id}: {intent_type.value}")
            
            # Try with retries
            for attempt in range(self.max_retries):
                try:
                    response = self._session.post(
                        f"{self.broker_url}/intents/route",
                        json=full_intent
                    )
                    
                    if response.status_code == 200:
                        resp_data = response.json()
                        intent_response = IntentResponse(
                            intent_id=intent_id,
                            status=resp_data.get("status", "delivered"),
                            response_data=resp_data.get("response"),
                            error_message=resp_data.get("error")
                        )
                        
                        # Track the response
                        self._track_response(intent_response)
                        self._pending_intents[intent_id] = intent_response
                        
                        self._logger.info(f"Intent {intent_id} delivered successfully")
                        return intent_response
                        
                    else:
                        error_msg = f"Broker returned {response.status_code}: {response.text}"
                        self._logger.warning(f"Intent delivery failed (attempt {attempt + 1}): {error_msg}")
                        
                except Exception as e:
                    self._logger.warning(f"Intent delivery error (attempt {attempt + 1}): {e}")
                
                # Wait before retry
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
            
            # All retries failed
            error_response = IntentResponse(
                intent_id=intent_id,
                status="failed",
                error_message="All delivery attempts failed"
            )
            self._track_response(error_response)
            raise IntentDeliveryError(f"Failed to deliver intent {intent_id} after {self.max_retries} attempts")
    
    def get_intent_status(self, intent_id: str) -> Optional[IntentResponse]:
        """Get status of a previously sent intent."""
        with self._lock:
            # Check pending intents first
            if intent_id in self._pending_intents:
                return self._pending_intents[intent_id]
            
            # Check broker
            try:
                response = self._session.get(
                    f"{self.broker_url}/intents/{intent_id}/status"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return IntentResponse(
                        intent_id=intent_id,
                        status=data.get("status", "unknown"),
                        response_data=data.get("response_data"),
                        error_message=data.get("error_message"),
                        timestamp=data.get("timestamp", "")
                    )
                    
            except Exception as e:
                self._logger.error(f"Failed to get intent status: {e}")
            
            return None
    
    def generate_content(self, brief: ContentBrief, target_platforms: List[str]) -> IntentResponse:
        """Send content generation intent."""
        intent_data = {
            "brief": asdict(brief),
            "target_platforms": target_platforms,
            "priority": "normal"
        }
        
        return self.send_intent(MediaIntentType.MEDIA_CONTENT_GENERATE, intent_data)
    
    def publish_content(self, asset: GeneratedAsset, platforms: List[str]) -> IntentResponse:
        """Send content publishing intent."""
        intent_data = {
            "asset": asdict(asset),
            "platforms": platforms,
            "schedule_time": None,  # Immediate
            "metadata": {}
        }
        
        return self.send_intent(MediaIntentType.MEDIA_CONTENT_PUBLISH, intent_data)
    
    def analyze_trends(self, topics: List[str], timeframe_days: int = 7) -> IntentResponse:
        """Send trend analysis intent."""
        intent_data = {
            "topics": topics,
            "timeframe_days": timeframe_days,
            "max_results": 20
        }
        
        return self.send_intent(MediaIntentType.MEDIA_TREND_ANALYZE, intent_data)
    
    def start_campaign(self, campaign_id: str, campaign_data: Dict[str, Any]) -> IntentResponse:
        """Send campaign start intent."""
        intent_data = {
            "campaign_id": campaign_id,
            "campaign_data": campaign_data,
            "start_immediately": True
        }
        
        return self.send_intent(MediaIntentType.MEDIA_CAMPAIGN_START, intent_data)
    
    def get_campaign_status(self, campaign_id: str) -> IntentResponse:
        """Get campaign status."""
        intent_data = {
            "campaign_id": campaign_id
        }
        
        return self.send_intent(MediaIntentType.MEDIA_CAMPAIGN_STATUS, intent_data)
    
    def fetch_metrics(self, platform: str, metric_types: List[str], 
                     start_date: str, end_date: str) -> IntentResponse:
        """Fetch performance metrics."""
        intent_data = {
            "platform": platform,
            "metric_types": metric_types,
            "start_date": start_date,
            "end_date": end_date
        }
        
        return self.send_intent(MediaIntentType.MEDIA_METRICS_FETCH, intent_data)
    
    def _track_response(self, response: IntentResponse) -> None:
        """Track intent response in ledger."""
        try:
            with open(self._response_ledger_path, 'a') as f:
                f.write(json.dumps(asdict(response)) + '\n')
        except Exception as e:
            self._logger.error(f"Failed to track response: {e}")
    
    def get_response_history(self, limit: int = 100) -> List[IntentResponse]:
        """Get recent intent responses from ledger."""
        responses = []
        try:
            if self._response_ledger_path.exists():
                with open(self._response_ledger_path, 'r') as f:
                    lines = f.readlines()[-limit:]
                    for line in lines:
                        try:
                            data = json.loads(line.strip())
                            responses.append(IntentResponse(**data))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            self._logger.error(f"Failed to read response history: {e}")
        
        return list(reversed(responses))  # Most recent first
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        with self._lock:
            health = {
                "agent_id": self.agent_id,
                "registered": self._registered,
                "last_heartbeat": self._last_heartbeat,
                "time_since_heartbeat": time.time() - self._last_heartbeat if self._last_heartbeat else None,
                "pending_intents": len(self._pending_intents),
                "broker_reachable": False
            }
            
            # Check broker connection
            try:
                response = self._session.get(f"{self.broker_url}/health", timeout=5.0)
                health["broker_reachable"] = response.status_code == 200
                if response.status_code == 200:
                    health["broker_health"] = response.json()
            except Exception as e:
                health["broker_error"] = str(e)
            
            return health
    
    def close(self):
        """Close client and cleanup."""
        self._session.close()


class MediaWebhookServer:
    """
    Webhook server for receiving events from n8n and other external systems.
    
    Provides endpoints for:
    - n8n workflow triggers
    - External campaign updates
    - Performance metric webhooks
    - Content approval workflows
    """
    
    def __init__(self, config: MediaGridConfig, simp_client: SimpMediaClient):
        self.config = config
        self.simp_client = simp_client
        self.webhook_secret = config.n8n_webhook_url  # Using URL as identifier
        
        self.app = Flask(__name__)
        self._setup_routes()
        
        self._logger = logging.getLogger("simp.media.webhook")
        self._webhook_ledger_path = Path("data/media/webhooks.jsonl")
        self._webhook_ledger_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._event_handlers: Dict[str, List[Callable]] = {
            "campaign_trigger": [],
            "content_approval": [],
            "metric_update": [],
            "platform_alert": []
        }
    
    def _setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/webhook/n8n', methods=['POST'])
        def handle_n8n_webhook():
            """Handle n8n workflow webhooks."""
            try:
                event = self._validate_webhook(request)
                self._log_webhook(event)
                
                # Process based on event type
                if event.event_type == "campaign_trigger":
                    return self._handle_campaign_trigger(event)
                elif event.event_type == "content_ready":
                    return self._handle_content_ready(event)
                elif event.event_type == "metrics_update":
                    return self._handle_metrics_update(event)
                else:
                    return jsonify({"status": "ignored", "reason": "unknown_event_type"}), 200
                    
            except WebhookValidationError as e:
                self._logger.error(f"Webhook validation failed: {e}")
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                self._logger.error(f"Webhook processing error: {e}")
                return jsonify({"error": "Internal server error"}), 500
        
        @self.app.route('/webhook/campaign/<campaign_id>', methods=['POST'])
        def handle_campaign_webhook(campaign_id):
            """Handle campaign-specific webhooks."""
            try:
                event = self._validate_webhook(request)
                event.payload["campaign_id"] = campaign_id
                self._log_webhook(event)
                
                # Forward to campaign orchestration
                response = self.simp_client.send_intent(
                    MediaIntentType.MEDIA_WEBHOOK_RECEIVE,
                    {"campaign_id": campaign_id, "webhook_event": asdict(event)}
                )
                
                return jsonify(asdict(response)), 200
                
            except WebhookValidationError as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                self._logger.error(f"Campaign webhook error: {e}")
                return jsonify({"error": "Internal server error"}), 500
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint."""
            return jsonify({
                "status": "healthy",
                "service": "media_webhook_server",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
    
    def _validate_webhook(self, request) -> WebhookEvent:
        """Validate incoming webhook request."""
        # Basic validation
        if not request.is_json:
            raise WebhookValidationError("Request must be JSON")
        
        data = request.get_json()
        if not data:
            raise WebhookValidationError("Empty request body")
        
        # Check required fields
        required = ["event_type", "source", "payload"]
        for field in required:
            if field not in data:
                raise WebhookValidationError(f"Missing required field: {field}")
        
        # Create event
        event = WebhookEvent(
            event_id=data.get("event_id", f"webhook_{int(time.time() * 1000)}"),
            event_type=data["event_type"],
            source=data["source"],
            payload=data["payload"],
            signature=data.get("signature")
        )
        
        # TODO: Add signature verification if webhook_secret is provided
        
        return event
    
    def _log_webhook(self, event: WebhookEvent) -> None:
        """Log webhook event to ledger."""
        try:
            with open(self._webhook_ledger_path, 'a') as f:
                f.write(json.dumps(asdict(event)) + '\n')
        except Exception as e:
            self._logger.error(f"Failed to log webhook: {e}")
    
    def _handle_campaign_trigger(self, event: WebhookEvent) -> tuple:
        """Handle campaign trigger webhook."""
        campaign_id = event.payload.get("campaign_id")
        if not campaign_id:
            return jsonify({"error": "Missing campaign_id"}), 400
        
        # Start campaign via SIMP broker
        try:
            response = self.simp_client.start_campaign(campaign_id, event.payload)
            return jsonify(asdict(response)), 200
        except Exception as e:
            self._logger.error(f"Failed to start campaign: {e}")
            return jsonify({"error": str(e)}), 500
    
    def _handle_content_ready(self, event: WebhookEvent) -> tuple:
        """Handle content ready webhook."""
        # Forward to content publishing
        try:
            # Extract asset data from payload
            asset_data = event.payload.get("asset", {})
            platforms = event.payload.get("platforms", [])
            
            # Create GeneratedAsset from data
            asset = GeneratedAsset(**asset_data)
            
            response = self.simp_client.publish_content(asset, platforms)
            return jsonify(asdict(response)), 200
        except Exception as e:
            self._logger.error(f"Failed to publish content: {e}")
            return jsonify({"error": str(e)}), 500
    
    def _handle_metrics_update(self, event: WebhookEvent) -> tuple:
        """Handle metrics update webhook."""
        # Store metrics and trigger alerts if needed
        try:
            # Log metrics for dashboard
            metrics_path = Path("data/media/metrics.jsonl")
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(metrics_path, 'a') as f:
                f.write(json.dumps(event.payload) + '\n')
            
            # Check for alert conditions
            self._check_alerts(event.payload)
            
            return jsonify({"status": "processed"}), 200
        except Exception as e:
            self._logger.error(f"Failed to process metrics: {e}")
            return jsonify({"error": str(e)}), 500
    
    def _check_alerts(self, metrics: Dict[str, Any]) -> None:
        """Check metrics for alert conditions."""
        # TODO: Implement alert logic based on metrics
        pass
    
    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """Register custom event handler."""
        if event_type in self._event_handlers:
            self._event_handlers[event_type].append(handler)
        else:
            self._logger.warning(f"Unknown event type: {event_type}")
    
    def run(self, host: str = "0.0.0.0", port: int = 8081, debug: bool = False):
        """Run the webhook server."""
        self._logger.info(f"Starting webhook server on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)


class MediaDashboardProvider:
    """
    Provides data for the SIMP dashboard to display media metrics and status.
    
    Integrates with the dashboard via data providers that expose:
    - Campaign status and metrics
    - Content performance
    - Agent health and activity
    - Trend analysis results
    """
    
    def __init__(self, config: MediaGridConfig, simp_client: SimpMediaClient):
        self.config = config
        self.simp_client = simp_client
        self.dashboard_url = config.dashboard_url
        
        self._logger = logging.getLogger("simp.media.dashboard")
        self._data_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        self._last_update = 0
        self._update_interval = 60  # seconds
        
    def get_campaign_data(self) -> Dict[str, Any]:
        """Get data for all campaigns."""
        with self._cache_lock:
            # Check cache
            cache_key = "campaigns"
            if (cache_key in self._data_cache and 
                time.time() - self._last_update < self._update_interval):
                return self._data_cache[cache_key]
            
            # Fetch fresh data
            campaigns_data = []
            for campaign in self.config.campaigns:
                try:
                    # Get campaign status from broker
                    response = self.simp_client.get_campaign_status(campaign.campaign_id)
                    
                    campaign_info = {
                        "id": campaign.campaign_id,
                        "name": campaign.name,
                        "description": campaign.description,
                        "status": response.status if response else "unknown",
                        "platforms": campaign.target_platforms,
                        "metrics": self._get_campaign_metrics(campaign.campaign_id),
                        "last_updated": datetime.utcnow().isoformat() + "Z"
                    }
                    campaigns_data.append(campaign_info)
                    
                except Exception as e:
                    self._logger.error(f"Failed to get data for campaign {campaign.campaign_id}: {e}")
                    campaigns_data.append({
                        "id": campaign.campaign_id,
                        "name": campaign.name,
                        "status": "error",
                        "error": str(e)
                    })
            
            data = {
                "campaigns": campaigns_data,
                "total_campaigns": len(campaigns_data),
                "active_campaigns": sum(1 for c in campaigns_data if c.get("status") == "active"),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            # Update cache
            self._data_cache[cache_key] = data
            self._last_update = time.time()
            
            return data
    
    def get_agent_data(self) -> Dict[str, Any]:
        """Get data for all media agents."""
        agents_data = []
        
        for agent_config in self.config.agents:
            try:
                # Create client for agent to check health
                agent_client = SimpMediaClient(agent_config)
                health = agent_client.health_check()
                agent_client.close()
                
                agent_info = {
                    "id": agent_config.agent_id,
                    "type": agent_config.agent_type.value,
                    "registered": health.get("registered", False),
                    "broker_reachable": health.get("broker_reachable", False),
                    "last_heartbeat": health.get("last_heartbeat"),
                    "pending_intents": health.get("pending_intents", 0),
                    "capabilities": agent_config.capabilities
                }
                agents_data.append(agent_info)
                
            except Exception as e:
                self._logger.error(f"Failed to get data for agent {agent_config.agent_id}: {e}")
                agents_data.append({
                    "id": agent_config.agent_id,
                    "type": agent_config.agent_type.value,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "agents": agents_data,
            "total_agents": len(agents_data),
            "healthy_agents": sum(1 for a in agents_data if a.get("registered", False)),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    def get_content_metrics(self, limit: int = 50) -> Dict[str, Any]:
        """Get content performance metrics."""
        try:
            # Read from metrics ledger
            metrics_path = Path("data/media/metrics.jsonl")
            if not metrics_path.exists():
                return {"metrics": [], "total": 0, "timestamp": datetime.utcnow().isoformat() + "Z"}
            
            metrics = []
            with open(metrics_path, 'r') as f:
                lines = f.readlines()[-limit:]
                for line in lines:
                    try:
                        metrics.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
            
            # Calculate aggregates
            total_engagement = sum(m.get("engagement", 0) for m in metrics)
            avg_engagement = total_engagement / len(metrics) if metrics else 0
            
            return {
                "metrics": metrics[-limit:],  # Most recent first
                "total": len(metrics),
                "aggregates": {
                    "total_engagement": total_engagement,
                    "average_engagement": avg_engagement,
                    "top_performing": sorted(metrics, key=lambda x: x.get("engagement", 0), reverse=True)[:5]
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
        except Exception as e:
            self._logger.error(f"Failed to get content metrics: {e}")
            return {
                "metrics": [],
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    def get_trend_data(self) -> Dict[str, Any]:
        """Get trend analysis data."""
        try:
            # Read from trend ledger
            trend_path = Path("data/media/trends.jsonl")
            if not trend_path.exists():
                return {"trends": [], "total": 0, "timestamp": datetime.utcnow().isoformat() + "Z"}
            
            trends = []
            with open(trend_path, 'r') as f:
                lines = f.readlines()[-20:]  # Last 20 trend analyses
                for line in lines:
                    try:
                        trends.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
            
            # Extract top trends
            top_trends = []
            for trend in trends:
                if "top_keywords" in trend:
                    for keyword in trend["top_keywords"][:5]:  # Top 5 per analysis
                        top_trends.append({
                            "keyword": keyword.get("keyword"),
                            "volume": keyword.get("volume", 0),
                            "sentiment": keyword.get("sentiment", "neutral"),
                            "timestamp": trend.get("timestamp", "")
                        })
            
            return {
                "trends": trends[-5:],  # Last 5 analyses
                "top_keywords": sorted(top_trends, key=lambda x: x.get("volume", 0), reverse=True)[:10],
                "total_analyses": len(trends),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
        except Exception as e:
            self._logger.error(f"Failed to get trend data: {e}")
            return {
                "trends": [],
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    def _get_campaign_metrics(self, campaign_id: str) -> Dict[str, Any]:
        """Get metrics for a specific campaign."""
        try:
            metrics_path = Path(f"data/media/campaigns/{campaign_id}/metrics.jsonl")
            if not metrics_path.exists():
                return {"total_posts": 0, "total_engagement": 0, "average_engagement": 0}
            
            metrics = []
            with open(metrics_path, 'r') as f:
                for line in f:
                    try:
                        metrics.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
            
            if not metrics:
                return {"total_posts": 0, "total_engagement": 0, "average_engagement": 0}
            
            total_posts = len(metrics)
            total_engagement = sum(m.get("engagement", 0) for m in metrics)
            avg_engagement = total_engagement / total_posts if total_posts > 0 else 0
            
            return {
                "total_posts": total_posts,
                "total_engagement": total_engagement,
                "average_engagement": avg_engagement,
                "last_post": metrics[-1].get("timestamp") if metrics else None
            }
            
        except Exception as e:
            self._logger.error(f"Failed to get campaign metrics for {campaign_id}: {e}")
            return {"error": str(e)}
    
    def update_dashboard(self) -> bool:
        """Push updates to dashboard."""
        try:
            # Get all data
            campaign_data = self.get_campaign_data()
            agent_data = self.get_agent_data()
            content_metrics = self.get_content_metrics()
            trend_data = self.get_trend_data()
            
            # Combine into dashboard payload
            dashboard_payload = {
                "media_grid": {
                    "campaigns": campaign_data,
                    "agents": agent_data,
                    "content_metrics": content_metrics,
                    "trends": trend_data,
                    "last_updated": datetime.utcnow().isoformat() + "Z"
                }
            }
            
            # TODO: Implement actual dashboard update
            # This would typically involve:
            # 1. WebSocket push to dashboard
            # 2. REST API call to dashboard backend
            # 3. Writing to shared data store
            
            self._logger.debug("Dashboard data updated")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to update dashboard: {e}")
            return False