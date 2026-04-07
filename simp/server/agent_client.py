"""
SIMP Agent Client

Client library for agents to communicate with SIMP broker.
Handles registration, intent receiving, and response sending.
"""

import socket
import struct
import json
import logging
import time
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import queue

# Length-prefix header: 4-byte unsigned big-endian integer
_HEADER_FORMAT = "!I"
_HEADER_SIZE = struct.calcsize(_HEADER_FORMAT)
_MAX_MESSAGE_SIZE = 16 * 1024 * 1024  # 16 MB max message


class SimpAgentClient:
    """
    Client for SIMP agents to communicate with broker

    Handles:
    - Registration with broker
    - Listening for incoming intents
    - Sending responses back to broker
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        port: int,
        broker_host: str = "127.0.0.1",
        broker_port: int = 5555,
    ):
        """Initialize SIMP agent client"""
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.port = port
        self.broker_host = broker_host
        self.broker_port = broker_port

        self.logger = logging.getLogger(f"SIMP.Client.{agent_id}")
        self.logger.setLevel(logging.INFO)

        # Communication
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.running = False

        # Intent queue
        self.intent_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()

        # Stats
        self.intents_received = 0
        self.responses_sent = 0

        self.logger.info(
            f"SIMP Agent Client initialized: {agent_id} ({agent_type})"
        )

    def connect_to_broker(self) -> bool:
        """Connect to SIMP broker"""
        try:
            self.logger.info(
                f"Connecting to broker at {self.broker_host}:{self.broker_port}"
            )

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.broker_host, self.broker_port))
            self.connected = True

            self.logger.info("Connected to broker")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to broker: {e}")
            self.connected = False
            return False

    def register(self) -> bool:
        """Register this agent with the broker"""
        if not self.connected:
            if not self.connect_to_broker():
                return False

        try:
            # Send registration message
            register_msg = {
                "type": "register",
                "agent_id": self.agent_id,
                "agent_type": self.agent_type,
                "port": self.port,
                "endpoint": f"localhost:{self.port}",
                "timestamp": datetime.utcnow().isoformat(),
            }

            self._send_message(register_msg)
            self.logger.info(f"Registration message sent")
            return True

        except Exception as e:
            self.logger.error(f"Registration failed: {e}")
            return False

    def listen(self, agent) -> None:
        """
        Listen for incoming intents from broker

        Args:
            agent: SIMP agent instance with handler methods
        """
        self.running = True
        self.logger.info("Listening for intents...")

        try:
            while self.running:
                # Receive intent from broker
                intent = self._receive_message()

                if not intent:
                    time.sleep(0.1)
                    continue

                self.logger.info(
                    f"Received intent: {intent.get('intent_id')} "
                    f"({intent.get('intent_type')})"
                )

                self.intents_received += 1

                # Handle intent with agent
                try:
                    response = self._handle_intent(agent, intent)

                    # Send response back to broker
                    self._send_response(intent.get("intent_id"), response)
                    self.responses_sent += 1

                except Exception as e:
                    self.logger.error(f"Error handling intent: {e}")
                    error_response = {
                        "status": "error",
                        "error_code": "HANDLER_ERROR",
                        "error_message": str(e),
                    }
                    self._send_response(intent.get("intent_id"), error_response)

        except KeyboardInterrupt:
            self.logger.info("Interrupted")
        finally:
            self.stop()

    def _handle_intent(self, agent, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an intent using the agent"""
        import asyncio

        intent_type = intent.get("intent_type")
        params = intent.get("params", {})

        # Get handler from agent
        if hasattr(agent, "handle_" + intent_type):
            handler = getattr(agent, "handle_" + intent_type)

            # Handle async handlers
            if asyncio.iscoroutinefunction(handler):
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(handler(params))
                finally:
                    loop.close()
            else:
                result = handler(params)

            return result
        else:
            return {
                "status": "error",
                "error_code": "HANDLER_NOT_FOUND",
                "error_message": f"No handler for intent type: {intent_type}",
            }

    @staticmethod
    def _recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
        """Receive exactly num_bytes from socket, or raise on disconnect."""
        buf = bytearray()
        while len(buf) < num_bytes:
            chunk = sock.recv(num_bytes - len(buf))
            if not chunk:
                raise ConnectionError("Connection closed while reading")
            buf.extend(chunk)
        return bytes(buf)

    def _send_message(self, msg: Dict[str, Any]) -> None:
        """Send length-prefixed message to broker"""
        if not self.socket:
            raise RuntimeError("Not connected to broker")

        msg_json = json.dumps(msg)
        msg_bytes = msg_json.encode()

        if len(msg_bytes) > _MAX_MESSAGE_SIZE:
            raise ValueError(f"Message too large: {len(msg_bytes)} > {_MAX_MESSAGE_SIZE}")

        # Length-prefix header + payload
        header = struct.pack(_HEADER_FORMAT, len(msg_bytes))
        self.socket.sendall(header + msg_bytes)

    def _receive_message(self) -> Optional[Dict[str, Any]]:
        """Receive length-prefixed message from broker"""
        if not self.socket:
            return None

        try:
            # Set timeout to avoid hanging
            self.socket.settimeout(1.0)

            # Read length header
            header = self._recv_exact(self.socket, _HEADER_SIZE)
            msg_len = struct.unpack(_HEADER_FORMAT, header)[0]

            if msg_len > _MAX_MESSAGE_SIZE:
                self.logger.error(f"Message too large: {msg_len}")
                return None

            # Read exact payload
            data = self._recv_exact(self.socket, msg_len)
            msg = json.loads(data.decode())
            return msg

        except socket.timeout:
            return None
        except ConnectionError:
            self.logger.warning("Connection closed by broker")
            self.connected = False
            return None
        except Exception as e:
            self.logger.error(f"Error receiving message: {e}")
            return None

    def _send_response(self, intent_id: str, response: Dict[str, Any]) -> None:
        """Send response to broker"""
        response_msg = {
            "type": "response",
            "intent_id": intent_id,
            "agent_id": self.agent_id,
            "response": response,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._send_message(response_msg)
        self.logger.info(
            f"Response sent for intent: {intent_id} ({response.get('status')})"
        )

    def send_intent(
        self, target_agent: str, intent_type: str, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Send an intent to another agent via broker

        Args:
            target_agent: Target agent ID
            intent_type: Type of intent
            params: Intent parameters

        Returns:
            Response from target agent (or None if failed)
        """
        intent_msg = {
            "type": "intent",
            "intent_id": f"intent:{self.agent_id}:{time.time()}",
            "source_agent": self.agent_id,
            "target_agent": target_agent,
            "intent_type": intent_type,
            "params": params,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            self._send_message(intent_msg)
            self.logger.info(
                f"Intent sent: {intent_type} to {target_agent}"
            )

            # Wait for response (simple implementation)
            response = self._receive_message()
            return response

        except Exception as e:
            self.logger.error(f"Error sending intent: {e}")
            return None

    def stop(self) -> None:
        """Stop the client"""
        self.running = False

        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        self.connected = False
        self.logger.info("Client stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "connected": self.connected,
            "intents_received": self.intents_received,
            "responses_sent": self.responses_sent,
            "timestamp": datetime.utcnow().isoformat(),
        }
