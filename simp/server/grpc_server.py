"""
gRPC Server for SIMP — provides a high-performance binary transport layer.

Runs alongside the Flask HTTP broker (same process, different port).
Shares the same SimpBroker instance for all agent/intent state.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent import futures
from datetime import datetime, timezone
from typing import Optional

import grpc

from simp.server.grpc_proto import simp_pb2, simp_pb2_grpc

logger = logging.getLogger("SIMP.gRPC")


class SimpGrpcServicer(simp_pb2_grpc.SimpServiceServicer):
    """
    gRPC service implementation backed by the shared SimpBroker instance.

    Thread-safe: all broker calls are protected by the broker's own locks.
    """

    def __init__(self, broker, lifecycle_manager, ws_bridge=None):
        self._broker = broker
        self._lifecycle = lifecycle_manager
        self._ws = ws_bridge
        self._start_time = time.time()
        logger.info("SimpGrpcServicer initialised")

    # ── Agent Management ──────────────────────────────────────────────────────

    def RegisterAgent(self, request, context):
        """Register a new agent via gRPC."""
        try:
            # Map proto fields to broker.register_agent signature
            metadata = dict(
                capabilities=list(request.capabilities),
                name=request.name,
                grpc=True,
            )
            ok = self._broker.register_agent(
                agent_id=request.agent_id or request.name,
                agent_type=request.agent_type or "generic",
                endpoint=request.endpoint or "",
                metadata=metadata,
            )
            if ok:
                # Build response with a placeholder token (JWT issued via HTTP /auth/token)
                return simp_pb2.RegisterAgentResponse(
                    success=True,
                    message=f"Agent '{request.agent_id}' registered",
                    token="",  # Agents obtain JWT via HTTP /auth/token
                )
            return simp_pb2.RegisterAgentResponse(
                success=False,
                message="Registration failed — agent may already exist or limit reached",
                token="",
            )
        except Exception as exc:
            logger.error("RegisterAgent error: %s", exc)
            return simp_pb2.RegisterAgentResponse(success=False, message=str(exc), token="")

    def DeregisterAgent(self, request, context):
        """Deregister an agent via gRPC."""
        try:
            ok = self._broker.deregister_agent(request.agent_id)
            if ok:
                self._broker._log_event(
                    "agent_deregistered_grpc",
                    f"Agent deregistered via gRPC: {request.agent_id}",
                    agent_id=request.agent_id,
                )
                return simp_pb2.DeregisterAgentResponse(success=True, message="Deregistered")
            return simp_pb2.DeregisterAgentResponse(success=False, message="Agent not found")
        except Exception as exc:
            logger.error("DeregisterAgent error: %s", exc)
            return simp_pb2.DeregisterAgentResponse(success=False, message=str(exc))

    def Heartbeat(self, request, context):
        """Record a heartbeat for an agent."""
        try:
            ok = self._broker.record_heartbeat(request.agent_id)
            agent = self._broker.get_agent(request.agent_id)
            count = agent.get("heartbeat_count", 0) if agent else 0
            return simp_pb2.HeartbeatResponse(
                alive=ok,
                count=count,
                server_time=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            logger.error("Heartbeat error: %s", exc)
            return simp_pb2.HeartbeatResponse(alive=False, count=0, server_time="")

    def ListAgents(self, request, context):
        """List registered agents."""
        try:
            agents_data = self._broker.list_agents()
            agents = []
            for a in agents_data:
                if request.active_only and a.get("stale"):
                    continue
                agents.append(simp_pb2.AgentInfo(
                    agent_id=a.get("agent_id", ""),
                    name=a.get("name", ""),
                    agent_type=a.get("agent_type", ""),
                    state=a.get("lifecycle_state", "active"),
                    status=a.get("status", ""),
                    last_heartbeat=a.get("last_heartbeat", ""),
                    heartbeat_count=a.get("heartbeat_count", 0),
                    stale=a.get("stale", False),
                    registered_at=a.get("registered_at", ""),
                    endpoint=a.get("endpoint", ""),
                    capabilities=a.get("capabilities", []),
                ))
            return simp_pb2.ListAgentsResponse(agents=agents)
        except Exception as exc:
            logger.error("ListAgents error: %s", exc)
            return simp_pb2.ListAgentsResponse(agents=[])

    def GetAgent(self, request, context):
        """Get a single agent by ID."""
        try:
            a = self._broker.get_agent(request.agent_id)
            if not a:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Agent '{request.agent_id}' not found")
                return simp_pb2.AgentInfo()
            return simp_pb2.AgentInfo(
                agent_id=a.get("agent_id", ""),
                name=a.get("name", ""),
                agent_type=a.get("agent_type", ""),
                state=a.get("lifecycle_state", "active"),
                status=a.get("status", ""),
                last_heartbeat=a.get("last_heartbeat", ""),
                heartbeat_count=a.get("heartbeat_count", 0),
                stale=a.get("stale", False),
                registered_at=a.get("registered_at", ""),
                endpoint=a.get("endpoint", ""),
                capabilities=a.get("capabilities", []),
            )
        except Exception as exc:
            logger.error("GetAgent error: %s", exc)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return simp_pb2.AgentInfo()

    def SetAgentLifecycle(self, request, context):
        """Set an agent's lifecycle state (active/paused/draining/terminated)."""
        try:
            valid_states = {"active", "paused", "draining", "terminated"}
            if request.state not in valid_states:
                return simp_pb2.SetAgentLifecycleResponse(
                    success=False,
                    message=f"Invalid state '{request.state}'. Must be one of: {valid_states}",
                    new_state="",
                )
            ok = self._broker.set_agent_lifecycle(request.agent_id, request.state, request.reason)
            new_state = request.state if ok else ""
            msg = f"Lifecycle set to '{request.state}'" if ok else "Failed — agent not found"
            # Push lifecycle change to WS agents
            if ok and self._ws:
                self._ws.push_to_channel(
                    "lifecycle_events",
                    {
                        "event": "agent_lifecycle_changed",
                        "agent_id": request.agent_id,
                        "state": request.state,
                        "reason": request.reason,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            return simp_pb2.SetAgentLifecycleResponse(success=ok, message=msg, new_state=new_state)
        except AttributeError:
            # Broker doesn't have set_agent_lifecycle yet — skip
            return simp_pb2.SetAgentLifecycleResponse(
                success=False, message="set_agent_lifecycle not implemented", new_state=""
            )
        except Exception as exc:
            logger.error("SetAgentLifecycle error: %s", exc)
            return simp_pb2.SetAgentLifecycleResponse(success=False, message=str(exc), new_state="")

    # ── Intent Handling ────────────────────────────────────────────────────────

    def SubmitIntent(self, request, context):
        """Submit an intent to the broker via gRPC."""
        try:
            intent = request.intent
            import json
            payload = {}
            if intent.payload_json:
                try:
                    payload = json.loads(intent.payload_json)
                except Exception:
                    payload = {"raw": intent.payload_json}

            # Route synchronously for gRPC (non-blocking)
            intent_id, accepted = self._broker.route_intent(
                intent_type=intent.intent_type,
                payload=payload,
                source_agent=intent.source_agent,
                target_agent=intent.target_agent or None,
                priority=intent.priority or "normal",
            )
            self._broker._log_event(
                "intent_submitted_grpc",
                f"Intent submitted via gRPC: {intent.intent_type}",
                agent_id=intent.source_agent,
                extra={"intent_id": intent_id},
            )
            return simp_pb2.SubmitIntentResponse(
                accepted=accepted,
                intent_id=intent_id or "",
                message="Accepted" if accepted else "Rejected",
            )
        except Exception as exc:
            logger.error("SubmitIntent error: %s", exc)
            return simp_pb2.SubmitIntentResponse(accepted=False, intent_id="", message=str(exc))

    def GetIntentStatus(self, request, context):
        """Get the status of a submitted intent."""
        try:
            status = self._broker.get_intent_status(request.intent_id)
            if not status:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Intent '{request.intent_id}' not found")
                return simp_pb2.GetIntentStatusResponse()
            return simp_pb2.GetIntentStatusResponse(
                status=simp_pb2.IntentStatus(
                    intent_id=status.get("intent_id", ""),
                    state=status.get("state", ""),
                    result_json=json.dumps(status.get("result")) if status.get("result") else "",
                    updated_at=status.get("updated_at", ""),
                    error=status.get("error", ""),
                )
            )
        except Exception as exc:
            logger.error("GetIntentStatus error: %s", exc)
            return simp_pb2.GetIntentStatusResponse()

    # ── System ─────────────────────────────────────────────────────────────────

    def GetStats(self, request, context):
        """Return broker statistics."""
        try:
            stats = self._broker.get_statistics()
            uptime = time.time() - self._start_time
            return simp_pb2.BrokerStats(
                agents_registered=stats.get("agents_registered", 0),
                intents_received=stats.get("intents_received", 0),
                intents_routed=stats.get("intents_routed", 0),
                intents_failed=stats.get("intents_failed", 0),
                uptime_seconds=int(uptime),
                state=stats.get("broker_state", "unknown"),
                version="SIMP-1.0",
            )
        except Exception as exc:
            logger.error("GetStats error: %s", exc)
            return simp_pb2.BrokerStats()

    def Health(self, request, context):
        """Return broker health status."""
        try:
            hc = self._broker.health_check()
            issues = []
            if not hc.get("healthy"):
                issues.append(hc.get("message", "unhealthy"))
            return simp_pb2.HealthResponse(
                healthy=hc.get("healthy", False),
                state=hc.get("state", "unknown"),
                version="SIMP-1.0",
                issues=issues,
            )
        except Exception as exc:
            logger.error("Health error: %s", exc)
            return simp_pb2.HealthResponse(
                healthy=False, state="error", version="SIMP-1.0", issues=[str(exc)]
            )

    def StreamLogs(self, request, context):
        """Server-streaming log endpoint."""
        try:
            limit = max(1, min(request.limit or 50, 500))
            logs = self._broker.get_logs(limit=limit)
            for log in logs:
                yield simp_pb2.StreamLogsResponse(
                    logs=[
                        simp_pb2.LogEntry(
                            timestamp=log.get("timestamp", ""),
                            event=log.get("event", ""),
                            agent_id=log.get("agent_id", ""),
                            message=log.get("message", ""),
                        )
                    ]
                )
        except Exception as exc:
            logger.error("StreamLogs error: %s", exc)


class GrpcServer:
    """
    Manages the gRPC server lifecycle (start/stop) in a background thread.

    Shares the same broker/lifecycle/ws-bridge instances as the HTTP broker.
    """

    def __init__(
        self,
        broker,
        lifecycle_manager,
        ws_bridge=None,
        host: str = "127.0.0.1",
        port: int = 50051,
        max_workers: int = 10,
    ):
        self._broker = broker
        self._lifecycle = lifecycle_manager
        self._ws = ws_bridge
        self._host = host
        self._port = port
        self._max_workers = max_workers
        self._server: Optional[grpc.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started = False

    @property
    def port(self) -> int:
        return self._port

    @property
    def address(self) -> str:
        return f"{self._host}:{self._port}"

    def start_in_thread(self):
        """Alias for start() — starts gRPC server in a background thread."""
        self.start()

    @property
    def is_running(self) -> bool:
        """Return True if the gRPC server is started and active."""
        return self._started

    def start(self):
        """Start gRPC server in a background thread."""
        if self._started:
            logger.warning("gRPC server already started")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="grpc-server")
        self._thread.start()
        self._started = True
        logger.info("gRPC server starting on %s (background thread)", self.address)

    def _run(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=self._max_workers))
        servicer = SimpGrpcServicer(self._broker, self._lifecycle, self._ws)
        simp_pb2_grpc.add_SimpServiceServicer_to_server(servicer, server)
        server.add_insecure_port(self.address)
        server.start()
        logger.info("gRPC server listening on %s", self.address)
        self._server = server
        try:
            self._stop_event.wait()
        except KeyboardInterrupt:
            pass
        finally:
            server.stop(grace=5)
            logger.info("gRPC server stopped")

    def stop(self):
        """Signal the gRPC server to stop."""
        if not self._started:
            return
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self._started = False
        logger.info("gRPC server signalled to stop")
