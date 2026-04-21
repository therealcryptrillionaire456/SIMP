"""
patches/agent_client_patch.py
───────────────────────────────
Drop-in replacement sections for agent_client.py.

Issues addressed:
  #2  Missing signature enforcement (client side)
  #6  Bare exception handlers (line 272)
  #8  No TLS for socket communication
  #11 No timeout on socket.connect()
"""

# ─────────────────────────────────────────────────────────────────────────────
# NEW IMPORTS (add near top of agent_client.py)
# ─────────────────────────────────────────────────────────────────────────────
NEW_IMPORTS = """
import ssl
import socket

try:
    from config.config import config as _cfg
    _CONNECT_TIMEOUT = _cfg.SOCKET_CONNECT_TIMEOUT
    _RECV_TIMEOUT    = _cfg.SOCKET_RECV_TIMEOUT
    _ENABLE_TLS      = _cfg.ENABLE_TLS
    _TLS_CERT        = _cfg.TLS_CERT_PATH
    _TLS_KEY         = _cfg.TLS_KEY_PATH
    _TLS_CA          = _cfg.TLS_CA_BUNDLE
except Exception:
    import os
    _CONNECT_TIMEOUT = float(os.environ.get("SIMP_SOCKET_CONNECT_TIMEOUT", "10"))
    _RECV_TIMEOUT    = float(os.environ.get("SIMP_SOCKET_RECV_TIMEOUT", "30"))
    _ENABLE_TLS      = os.environ.get("SIMP_ENABLE_TLS", "false").lower() == "true"
    _TLS_CERT        = os.environ.get("SIMP_TLS_CERT", "")
    _TLS_KEY         = os.environ.get("SIMP_TLS_KEY", "")
    _TLS_CA          = os.environ.get("SIMP_TLS_CA", "")
"""

# ─────────────────────────────────────────────────────────────────────────────
# REPLACEMENT for connect_to_broker() / __init__ socket setup
# Drop this in where the raw socket is currently created and connected.
# ─────────────────────────────────────────────────────────────────────────────
CONNECT_WITH_TLS_AND_TIMEOUT = '''
def _build_ssl_context(self) -> ssl.SSLContext:
    """
    Build an SSL context from config.  Called only when TLS is enabled.
    Uses mutual TLS when both cert+key are provided.
    """
    ctx = ssl.create_default_context(
        cafile=_TLS_CA if _TLS_CA else None
    )
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    if _TLS_CERT and _TLS_KEY:
        ctx.load_cert_chain(certfile=_TLS_CERT, keyfile=_TLS_KEY)
    return ctx


def _create_socket(self) -> socket.socket:
    """
    Create a connected socket to the broker with:
      - configurable connect timeout
      - configurable recv timeout
      - optional TLS wrapping
    """
    raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw.settimeout(_CONNECT_TIMEOUT)          # timeout for connect()

    try:
        raw.connect((self.broker_host, self.broker_port))
    except socket.timeout as exc:
        raw.close()
        self.logger.error(
            "Timed out connecting to broker %s:%s after %.1fs: %s",
            self.broker_host, self.broker_port, _CONNECT_TIMEOUT, exc,
        )
        raise
    except (socket.error, OSError) as exc:
        raw.close()
        self.logger.error(
            "Failed to connect to broker %s:%s: %s",
            self.broker_host, self.broker_port, exc, exc_info=True,
        )
        raise

    raw.settimeout(_RECV_TIMEOUT)             # timeout for recv/send

    if _ENABLE_TLS:
        try:
            ctx = self._build_ssl_context()
            sock = ctx.wrap_socket(raw, server_hostname=self.broker_host)
            self.logger.info(
                "TLS connection established to %s:%s (cipher=%s)",
                self.broker_host, self.broker_port,
                sock.cipher()[0] if sock.cipher() else "unknown",
            )
            return sock
        except ssl.SSLError as exc:
            raw.close()
            self.logger.error(
                "TLS handshake failed with broker: %s", exc, exc_info=True,
            )
            raise
    else:
        self.logger.debug(
            "Plain TCP connection to %s:%s (TLS disabled)",
            self.broker_host, self.broker_port,
        )
        return raw
'''

# ─────────────────────────────────────────────────────────────────────────────
# REPLACEMENT for the bare `except: pass` at agent_client.py line ~272
# Typically inside a stop() or cleanup method.
# ─────────────────────────────────────────────────────────────────────────────
BARE_EXCEPT_STOP_REPLACEMENT = '''
def stop(self):
    """Gracefully shut down the agent client."""
    self._running = False
    if self.socket:
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except (socket.error, OSError) as exc:
            # Socket may already be closed; this is expected
            self.logger.debug("Socket shutdown during stop (expected): %s", exc)
        except Exception as exc:
            self.logger.error(
                "Unexpected error shutting down socket: %s", exc, exc_info=True
            )
        finally:
            try:
                self.socket.close()
            except (socket.error, OSError, ssl.SSLError) as exc:
                self.logger.debug("Socket close during stop (expected): %s", exc)
            except Exception as exc:
                self.logger.error(
                    "Unexpected error closing socket: %s", exc, exc_info=True
                )
            self.socket = None
    self.logger.info("Agent client stopped.")
'''

# ─────────────────────────────────────────────────────────────────────────────
# Helper: sign outgoing intents (add to SimpAgentClient or equivalent class)
# ─────────────────────────────────────────────────────────────────────────────
SIGN_INTENT_METHOD = '''
def _sign_intent(self, intent_data: dict) -> dict:
    """
    Attach a cryptographic signature to an intent dict before sending.

    Requires self.private_key to be set (loaded at agent startup).
    If no private key is configured, returns the dict unchanged and
    logs a warning (unless REQUIRE_SIGNATURES is True, in which case raises).
    """
    try:
        from simp.crypto import SimpCrypto  # adjust import to actual module
    except ImportError:
        self.logger.warning("simp.crypto not available; intent will be unsigned")
        return intent_data

    if not hasattr(self, "private_key") or not self.private_key:
        msg = "No private key configured for signing"
        try:
            from config.config import config
            if config.REQUIRE_SIGNATURES:
                raise RuntimeError(msg)
        except ImportError:
            pass
        self.logger.warning(msg)
        return intent_data

    try:
        signed = dict(intent_data)
        signed["signature"] = SimpCrypto.sign(intent_data, self.private_key)
        return signed
    except Exception as exc:
        self.logger.error("Failed to sign intent: %s", exc, exc_info=True)
        raise
'''
