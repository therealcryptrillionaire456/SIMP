"""
SIMP Agent Client — Client library for agents to communicate with SIMP broker.

Security hardening (v0.2):
  - Socket connect timeout (configurable, default 10s)             (#11)
  - Recv timeout already present; now also set on connect          (#11)
  - Optional TLS via ssl module (SIMP_ENABLE_TLS=true)            (#8)
  - Bare `except: pass` in stop() replaced with explicit handlers  (#6)
  - Intent signing before send (when private key configured)       (#2)
  - Config-driven settings (env vars / config module)             (#19)
"""

import json
import logging
import os
import queue
import socket
import ssl
import time
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

# ── config ────────────────────────────────────────────────────────────────────
try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from config.config import config as _cfg
    _CONNECT_TIMEOUT = _cfg.SOCKET_CONNECT_TIMEOUT
    _RECV_TIMEOUT    = _cfg.SOCKET_RECV_TIMEOUT
    _ENABLE_TLS      = _cfg.ENABLE_TLS
    _TLS_CERT        = _cfg.TLS_CERT_PATH
    _TLS_KEY         = _cfg.TLS_KEY_PATH
    _TLS_CA          = _cfg.TLS_CA_BUNDLE
except Exception:
    _CONNECT_TIMEOUT = float(os.environ.get("SIMP_SOCKET_CONNECT_TIMEOUT", "10"))
    _RECV_TIMEOUT    = float(os.environ.get("SIMP_SOCKET_RECV_TIMEOUT",    "30"))
    _ENABLE_TLS      = os.environ.get("SIMP_ENABLE_TLS", "false").lower() == "true"
    _TLS_CERT        = os.environ.get("SIMP_TLS_CERT", "")
    _TLS_KEY         = os.environ.get("SIMP_TLS_KEY",  "")
    _TLS_CA          = os.environ.get("SIMP_TLS_CA",   "")


class SimpAgentClient:
    """
    Client for SIMP agents to communicate with broker.

    v0.2 security additions:
      - All socket operations have explicit timeouts (connect + recv)
      - TLS wrapping available when SIMP_ENABLE_TLS=true
      - stop() no longer swallows all exceptions silently
      - Outgoing intents can be cryptographically signed
    """

    def __init__(
        self,
        agent_id:    str,
        agent_type:  str,
        port:        int,
        broker_host: str = "127.0.0.1",
        broker_port: int = 5555,
        private_key: Optional[Any] = None,   # loaded private key for signing
    ):
        self.agent_id    = agent_id
        self.agent_type  = agent_type
        self.port        = port
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.private_key = private_key

        self.logger = logging.getLogger(f"SIMP.Client.{agent_id}")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(h)

        self.socket:    Optional[socket.socket] = None
        self.connected: bool = False
        self.running:   bool = False
        self._recv_buffer = b""

        self.intent_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.intents_received = 0
        self.responses_sent   = 0

        self.logger.info("✅ SIMP Agent Client initialized: %s (%s)",
                         agent_id, agent_type)
        self.logger.info("   TLS: %s  connect_timeout: %.1fs  recv_timeout: %.1fs",
                         "ENABLED" if _ENABLE_TLS else "disabled",
                         _CONNECT_TIMEOUT, _RECV_TIMEOUT)

    # ── socket setup ──────────────────────────────────────────────────────────

    def _build_ssl_context(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context(cafile=_TLS_CA or None)
        ctx.check_hostname = True
        ctx.verify_mode    = ssl.CERT_REQUIRED
        if _TLS_CERT and _TLS_KEY:
            ctx.load_cert_chain(certfile=_TLS_CERT, keyfile=_TLS_KEY)
        return ctx

    def connect_to_broker(self) -> bool:
        """Connect to broker with explicit timeouts and optional TLS."""
        self.logger.info("📡 Connecting to broker at %s:%s (TLS=%s)",
                         self.broker_host, self.broker_port,
                         "on" if _ENABLE_TLS else "off")
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.settimeout(_CONNECT_TIMEOUT)

        try:
            raw.connect((self.broker_host, self.broker_port))
        except socket.timeout as exc:
            raw.close()
            self.logger.error(
                "❌ Connect timeout to broker %s:%s after %.1fs: %s",
                self.broker_host, self.broker_port, _CONNECT_TIMEOUT, exc,
            )
            self.connected = False
            return False
        except (socket.error, OSError) as exc:
            raw.close()
            self.logger.error(
                "❌ Failed to connect to broker %s:%s: %s",
                self.broker_host, self.broker_port, exc, exc_info=True,
            )
            self.connected = False
            return False

        raw.settimeout(_RECV_TIMEOUT)

        if _ENABLE_TLS:
            try:
                ctx  = self._build_ssl_context()
                sock = ctx.wrap_socket(raw, server_hostname=self.broker_host)
                self.logger.info("✅ TLS established (cipher=%s)",
                                 sock.cipher()[0] if sock.cipher() else "?")
                self.socket    = sock
                self.connected = True
                return True
            except ssl.SSLError as exc:
                raw.close()
                self.logger.error("❌ TLS handshake failed: %s", exc,
                                  exc_info=True)
                self.connected = False
                return False
        else:
            self.socket    = raw
            self.connected = True
            self.logger.info("✅ Connected to broker (plain TCP)")
            return True

    # ── registration ──────────────────────────────────────────────────────────

    def register(self) -> bool:
        if not self.connected:
            if not self.connect_to_broker():
                return False
        try:
            register_msg = {
                "type":       "register",
                "agent_id":   self.agent_id,
                "agent_type": self.agent_type,
                "port":       self.port,
                "endpoint":   f"localhost:{self.port}",
                "timestamp":  datetime.now(timezone.utc).isoformat(),
            }
            self._send_message(register_msg)
            self.logger.info("✅ Registration message sent")
            return True
        except (socket.error, OSError) as exc:
            self.logger.error("❌ Registration failed (socket): %s", exc,
                              exc_info=True)
            return False
        except Exception as exc:
            self.logger.error("❌ Registration failed: %s", exc, exc_info=True)
            return False

    # ── listen loop ───────────────────────────────────────────────────────────

    def listen(self, agent) -> None:
        self.running = True
        self.logger.info("▶️ Listening for intents…")
        try:
            while self.running:
                intent = self._receive_message()
                if not intent:
                    time.sleep(0.1)
                    continue
                self.logger.info("📨 Received intent: %s (%s)",
                                 intent.get("intent_id"),
                                 intent.get("intent_type"))
                self.intents_received += 1
                try:
                    response = self._handle_intent(agent, intent)
                    self._send_response(intent.get("intent_id"), response)
                    self.responses_sent += 1
                except Exception as exc:
                    self.logger.error("❌ Error handling intent: %s", exc,
                                      exc_info=True)
                    self._send_response(intent.get("intent_id"), {
                        "status":       "error",
                        "error_code":   "HANDLER_ERROR",
                        "error_message": str(exc),
                    })
        except KeyboardInterrupt:
            self.logger.info("⏹️ Interrupted")
        finally:
            self.stop()

    # ── intent handling ───────────────────────────────────────────────────────

    def _handle_intent(self, agent, intent: Dict[str, Any]) -> Dict[str, Any]:
        import asyncio
        intent_type = intent.get("intent_type")
        params      = intent.get("params", {})
        handler_name = "handle_" + str(intent_type)
        if hasattr(agent, handler_name):
            handler = getattr(agent, handler_name)
            if asyncio.iscoroutinefunction(handler):
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(handler(params))
            return handler(params)
        return {
            "status":        "error",
            "error_code":    "HANDLER_NOT_FOUND",
            "error_message": f"No handler for intent type: {intent_type}",
        }

    # ── signing ───────────────────────────────────────────────────────────────

    def _sign_intent(self, intent_data: dict) -> dict:
        """Attach a cryptographic signature when a private key is configured."""
        if not self.private_key:
            return intent_data
        try:
            from simp.crypto import SimpCrypto   # adjust path as needed
            signed = dict(intent_data)
            signed["signature"] = SimpCrypto.sign(intent_data, self.private_key)
            return signed
        except ImportError:
            self.logger.warning("simp.crypto unavailable; sending unsigned intent")
            return intent_data
        except Exception as exc:
            self.logger.error("Failed to sign intent: %s", exc, exc_info=True)
            raise

    # ── send / receive ────────────────────────────────────────────────────────

    def _send_message(self, msg: Dict[str, Any]) -> None:
        if not self.socket:
            raise RuntimeError("Not connected to broker")
        msg_bytes = (json.dumps(msg) + "\n").encode()
        try:
            self.socket.sendall(msg_bytes)
        except (socket.timeout, ssl.SSLError) as exc:
            self.logger.error("Send timeout/SSL error: %s", exc, exc_info=True)
            raise
        except (socket.error, OSError) as exc:
            self.logger.error("Send socket error: %s", exc, exc_info=True)
            raise

    def _receive_message(self) -> Optional[Dict[str, Any]]:
        if not self.socket:
            return None

        message = self._pop_framed_message()
        if message is not None:
            return message

        try:
            self.socket.settimeout(1.0)
            data = self.socket.recv(4096)
            if not data:
                return None
            self._recv_buffer += data
            if len(self._recv_buffer) > 64 * 1024:
                self.logger.warning("Receive buffer exceeded 64KB; dropping buffered data")
                self._recv_buffer = b""
                return None
            return self._pop_framed_message()
        except socket.timeout:
            return None
        except (socket.error, OSError) as exc:
            self.logger.error("Receive socket error: %s", exc, exc_info=True)
            return None
        except json.JSONDecodeError as exc:
            self.logger.warning("Received malformed JSON: %s", exc)
            return None
        except Exception as exc:
            self.logger.error("Unexpected receive error: %s", exc, exc_info=True)
            return None

    def _pop_framed_message(self) -> Optional[Dict[str, Any]]:
        """Read one newline-delimited JSON message from the receive buffer."""
        while b"\n" in self._recv_buffer:
            line, remainder = self._recv_buffer.split(b"\n", 1)
            self._recv_buffer = remainder
            if not line.strip():
                continue
            try:
                return json.loads(line.decode())
            except json.JSONDecodeError as exc:
                self.logger.warning("Received malformed JSON frame: %s", exc)
                continue
        return None

    def _send_response(self, intent_id: str, response: Dict[str, Any]) -> None:
        msg = {
            "type":      "response",
            "intent_id": intent_id,
            "agent_id":  self.agent_id,
            "response":  response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._send_message(msg)
        self.logger.info("📤 Response sent for intent: %s (%s)",
                         intent_id, response.get("status"))

    def send_intent(
        self, target_agent: str, intent_type: str, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        intent_msg = {
            "type":         "intent",
            "intent_id":    f"intent:{self.agent_id}:{time.time()}",
            "source_agent": self.agent_id,
            "target_agent": target_agent,
            "intent_type":  intent_type,
            "params":       params,
            "timestamp":    datetime.now(timezone.utc).isoformat(),
        }
        # Sign before sending
        intent_msg = self._sign_intent(intent_msg)

        try:
            self._send_message(intent_msg)
            self.logger.info("📤 Intent sent: %s → %s", intent_type, target_agent)
            return self._receive_message()
        except (socket.error, OSError, ssl.SSLError) as exc:
            self.logger.error("❌ Socket error sending intent: %s", exc,
                              exc_info=True)
            return None
        except Exception as exc:
            self.logger.error("❌ Unexpected error sending intent: %s", exc,
                              exc_info=True)
            return None

    # ── shutdown ──────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """
        Gracefully stop the client.

        Replaces the original `except: pass` with specific exception handlers
        that log unexpected conditions without hiding them.
        """
        self.running   = False
        self.connected = False

        if self.socket:
            # Try a graceful shutdown first
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except (socket.error, OSError):
                # Socket may already be in a closed/error state — expected
                pass
            except ssl.SSLError:
                # TLS teardown on an already-closed socket — expected
                pass
            except Exception as exc:
                # Truly unexpected — log but don't propagate so stop() completes
                self.logger.error("Unexpected error during socket shutdown: %s",
                                  exc, exc_info=True)

            try:
                self.socket.close()
            except (socket.error, OSError, ssl.SSLError):
                pass   # close() on a dead socket is non-fatal
            except Exception as exc:
                self.logger.error("Unexpected error closing socket: %s",
                                  exc, exc_info=True)
            finally:
                self.socket = None

        self.logger.info("✅ Client stopped")

    # ── stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        return {
            "agent_id":         self.agent_id,
            "agent_type":       self.agent_type,
            "connected":        self.connected,
            "tls_enabled":      _ENABLE_TLS,
            "intents_received": self.intents_received,
            "responses_sent":   self.responses_sent,
            "timestamp":        datetime.now(timezone.utc).isoformat(),
        }
