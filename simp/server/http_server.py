"""
SIMP HTTP Server

REST API for SIMP broker, making it easy to test and interact with.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify
from threading import Thread
import time

from simp.server.broker import SimpBroker, BrokerConfig
from simp.memory.conversation_archive import ConversationArchive
from simp.memory.task_memory import TaskMemory
from simp.memory.knowledge_index import KnowledgeIndex
from simp.memory.session_bootstrap import SessionBootstrap


class SimpHttpServer:
    """
    HTTP REST API wrapper for SIMP Broker

    Provides endpoints for:
    - Agent registration
    - Intent routing
    - Response handling
    - Status/metrics
    - Memory layer (conversations, tasks, knowledge index, context packs)
    """

    def __init__(self, broker_config: Optional[BrokerConfig] = None, debug: bool = False):
        """Initialize HTTP server"""
        self.app = Flask("SIMP")
        self.broker = SimpBroker(broker_config or BrokerConfig())
        self.debug = debug

        # Memory layer components
        self.conversation_archive = ConversationArchive()
        self.task_memory = TaskMemory()
        self.knowledge_index = KnowledgeIndex()
        self.session_bootstrap = SessionBootstrap(
            task_memory=self.task_memory,
            conversation_archive=self.conversation_archive,
            knowledge_index=self.knowledge_index,
            task_ledger=self.broker.task_ledger,
        )
        self.logger = logging.getLogger("SIMP.HTTP")

        # Setup logging
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        self._setup_routes()
        self.logger.info("✅ SIMP HTTP Server initialized")

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.app.route("/health", methods=["GET"])
        def health():
            """Health check endpoint"""
            return jsonify(self.broker.health_check()), 200

        @self.app.route("/agents/register", methods=["POST"])
        def register_agent():
            """Register a new agent"""
            data = request.get_json() or {}

            agent_id = data.get("agent_id")
            agent_type = data.get("agent_type")
            endpoint = data.get("endpoint")
            metadata = data.get("metadata", {})

            if not all([agent_id, agent_type, endpoint]):
                return (
                    jsonify({
                        "status": "error",
                        "error": "Missing required fields: agent_id, agent_type, endpoint"
                    }),
                    400,
                )

            success = self.broker.register_agent(agent_id, agent_type, endpoint, metadata)

            if success:
                return (
                    jsonify({
                        "status": "success",
                        "agent_id": agent_id,
                        "message": f"Agent '{agent_id}' registered"
                    }),
                    201,
                )
            else:
                return (
                    jsonify({
                        "status": "error",
                        "error": f"Failed to register agent '{agent_id}'"
                    }),
                    400,
                )

        @self.app.route("/agents", methods=["GET"])
        def list_agents():
            """List all registered agents"""
            agents = self.broker.list_agents()
            return jsonify({
                "status": "success",
                "count": len(agents),
                "agents": agents
            }), 200

        @self.app.route("/agents/<agent_id>", methods=["GET"])
        def get_agent(agent_id):
            """Get agent details"""
            agent = self.broker.get_agent(agent_id)
            if agent:
                return jsonify({"status": "success", "agent": agent}), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Agent '{agent_id}' not found"
                }), 404

        @self.app.route("/agents/<agent_id>", methods=["DELETE"])
        def deregister_agent(agent_id):
            """Deregister an agent"""
            success = self.broker.deregister_agent(agent_id)
            if success:
                return jsonify({
                    "status": "success",
                    "message": f"Agent '{agent_id}' deregistered"
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Agent '{agent_id}' not found"
                }), 404

        @self.app.route("/intents/route", methods=["POST"])
        def route_intent():
            """Route an intent to a target agent"""
            import asyncio

            data = request.get_json() or {}

            # Validate intent
            if "target_agent" not in data:
                return (
                    jsonify({
                        "status": "error",
                        "error": "Missing required field: target_agent"
                    }),
                    400,
                )

            # Route intent
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self.broker.route_intent(data))
                return jsonify(result), 200
            finally:
                loop.close()

        @self.app.route("/intents/<intent_id>", methods=["GET"])
        def get_intent_status(intent_id):
            """Get status of an intent"""
            status = self.broker.get_intent_status(intent_id)
            if status:
                return jsonify({"status": "success", "intent": status}), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Intent '{intent_id}' not found"
                }), 404

        @self.app.route("/intents/<intent_id>/response", methods=["POST"])
        def record_response(intent_id):
            """Record response to an intent"""
            data = request.get_json() or {}
            execution_time = data.get("execution_time_ms", 0.0)

            success = self.broker.record_response(
                intent_id,
                data.get("response", {}),
                execution_time
            )

            if success:
                return jsonify({
                    "status": "success",
                    "message": "Response recorded"
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Intent '{intent_id}' not found"
                }), 404

        @self.app.route("/intents/<intent_id>/error", methods=["POST"])
        def record_error(intent_id):
            """Record error for an intent"""
            data = request.get_json() or {}
            error_msg = data.get("error", "Unknown error")
            execution_time = data.get("execution_time_ms", 0.0)

            success = self.broker.record_error(intent_id, error_msg, execution_time)

            if success:
                return jsonify({
                    "status": "success",
                    "message": "Error recorded"
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Intent '{intent_id}' not found"
                }), 404

        @self.app.route("/stats", methods=["GET"])
        def get_stats():
            """Get broker statistics"""
            return jsonify({
                "status": "success",
                "stats": self.broker.get_statistics()
            }), 200

        @self.app.route("/status", methods=["GET"])
        def get_status():
            """Get broker status"""
            return jsonify({
                "status": "success",
                "broker": {
                    "state": self.broker.state.value,
                    "health": self.broker.health_check(),
                    "stats": self.broker.get_statistics()
                }
            }), 200

        @self.app.route("/control/start", methods=["POST"])
        def start_broker():
            """Start the broker"""
            self.broker.start()
            return jsonify({
                "status": "success",
                "message": "Broker started"
            }), 200

        @self.app.route("/control/stop", methods=["POST"])
        def stop_broker():
            """Stop the broker"""
            self.broker.stop()
            return jsonify({
                "status": "success",
                "message": "Broker stopped"
            }), 200

        # ----- Task Ledger Endpoints (GET-only, read-safe) -----

        @self.app.route("/tasks", methods=["GET"])
        def list_tasks():
            """List tasks from the ledger with optional filters."""
            status_filter = request.args.get("status")
            agent_filter = request.args.get("agent")
            type_filter = request.args.get("task_type")
            tasks = self.broker.task_ledger.list_tasks(
                status=status_filter,
                agent=agent_filter,
                task_type=type_filter,
            )
            return jsonify({
                "status": "success",
                "count": len(tasks),
                "tasks": tasks,
                "failure_stats": self.broker.task_ledger.get_failure_stats(),
                "status_counts": self.broker.task_ledger.get_status_counts(),
            }), 200

        @self.app.route("/tasks/<task_id>", methods=["GET"])
        def get_task(task_id):
            """Get a single task by ID."""
            task = self.broker.task_ledger.get_task(task_id)
            if task:
                return jsonify({"status": "success", "task": task}), 200
            return jsonify({
                "status": "error",
                "error": f"Task '{task_id}' not found",
            }), 404

        @self.app.route("/tasks/queue", methods=["GET"])
        def get_task_queue():
            """Get unclaimed tasks ordered by priority."""
            queue = self.broker.task_ledger.get_queue()
            return jsonify({
                "status": "success",
                "count": len(queue),
                "queue": queue,
            }), 200

        @self.app.route("/routing/policy", methods=["GET"])
        def get_routing_policy():
            """Return the current routing policy."""
            if self.broker.builder_pool:
                policy = self.broker.builder_pool.policy
                pool_status = self.broker.builder_pool.get_pool_status()
                return jsonify({
                    "status": "success",
                    "policy": policy,
                    "pool_status": pool_status,
                }), 200
            return jsonify({
                "status": "success",
                "policy": {},
                "pool_status": {},
                "message": "Builder pool not configured",
            }), 200

        # ----- Memory Layer Endpoints -----

        @self.app.route("/memory/conversations", methods=["GET"])
        def list_conversations():
            """List conversations with optional filters."""
            topic = request.args.get("topic")
            tag = request.args.get("tag")
            participant = request.args.get("participant")
            convos = self.conversation_archive.list_conversations(
                topic=topic, tag=tag, participant=participant,
            )
            return jsonify({
                "status": "success",
                "count": len(convos),
                "conversations": convos,
            }), 200

        @self.app.route("/memory/conversations/<conv_id>", methods=["GET"])
        def get_conversation(conv_id):
            """Get a single conversation by ID."""
            conv = self.conversation_archive.get_conversation(conv_id)
            if conv:
                return jsonify({"status": "success", "conversation": conv}), 200
            return jsonify({
                "status": "error",
                "error": f"Conversation '{conv_id}' not found",
            }), 404

        @self.app.route("/memory/conversations", methods=["POST"])
        def save_conversation():
            """Save a new conversation record."""
            data = request.get_json() or {}
            if not data.get("topic"):
                return jsonify({
                    "status": "error",
                    "error": "Missing required field: topic",
                }), 400
            conv_id = self.conversation_archive.save_conversation(data)
            return jsonify({
                "status": "success",
                "conversation_id": conv_id,
            }), 201

        @self.app.route("/memory/tasks", methods=["GET"])
        def list_memory_tasks():
            """List task memory files."""
            tasks = self.task_memory.list_tasks()
            return jsonify({
                "status": "success",
                "count": len(tasks),
                "tasks": tasks,
            }), 200

        @self.app.route("/memory/tasks/<slug>", methods=["GET"])
        def get_memory_task(slug):
            """Get a task memory file by slug."""
            task = self.task_memory.get_task(slug)
            if task:
                return jsonify({"status": "success", "task": task}), 200
            return jsonify({
                "status": "error",
                "error": f"Task memory '{slug}' not found",
            }), 404

        @self.app.route("/memory/index", methods=["GET"])
        def get_knowledge_index():
            """Get the full knowledge index."""
            return jsonify({
                "status": "success",
                "index": self.knowledge_index.get_full_index(),
            }), 200

        @self.app.route("/memory/context-pack", methods=["GET"])
        def get_context_pack():
            """Generate a context pack."""
            task_id = request.args.get("task_id")
            topic = request.args.get("topic")
            agent_id = request.args.get("agent_id")
            if not any([task_id, topic, agent_id]):
                return jsonify({
                    "status": "error",
                    "error": "Provide at least one of: task_id, topic, agent_id",
                }), 400
            pack = self.session_bootstrap.generate_context_pack(
                task_id=task_id, topic=topic, agent_id=agent_id,
            )
            return jsonify({"status": "success", "context_pack": pack}), 200

    def run(self, host: str = "127.0.0.1", port: int = 5555, threaded: bool = True):
        """
        Run the HTTP server

        Args:
            host: Host to bind to
            port: Port to bind to
            threaded: Run in threaded mode
        """
        self.broker.start()
        self.logger.info(f"🚀 SIMP HTTP Server starting on {host}:{port}")
        self.app.run(host=host, port=port, debug=self.debug, threaded=threaded)

    def run_in_background(self, host: str = "127.0.0.1", port: int = 5555):
        """Run server in background thread"""
        thread = Thread(
            target=self.run,
            args=(host, port),
            daemon=True,
            name="SIMP-HTTP-Server"
        )
        thread.start()
        self.logger.info(f"✅ Server started in background thread")
        return thread


def create_http_server(
    host: str = "127.0.0.1",
    port: int = 5555,
    debug: bool = False
) -> SimpHttpServer:
    """Factory function to create HTTP server"""
    config = BrokerConfig(host=host, port=port)
    return SimpHttpServer(config, debug=debug)
