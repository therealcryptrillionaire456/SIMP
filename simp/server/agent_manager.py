"""
Agent Manager: Spawns and manages SIMP agents as separate processes.

Security hardening (v0.2):
  - No hardcoded absolute paths (/sessions/… → project-relative)  (#1, #12)
  - agent args validated against allowlist before use               (#1)
  - Args passed via env vars, NOT injected into Python code strings (#1)
  - Temp files in secure tempfile.mkstemp() directory              (#12)
  - Bare except replaced with specific exception handling           (#6)
"""

import logging
import multiprocessing as mp
import os
import re
import signal
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ── project root (robust: works regardless of CWD) ───────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[3]   # …/SIMP/

# ── safe temporary directory (never world-writable /tmp directly) ─────────────
try:
    from config.config import config as _cfg
    _TMP_BASE = Path(_cfg.TMP_DIR) / "simp_agents"
except Exception:
    _TMP_BASE = Path(tempfile.gettempdir()) / "simp_agents"

_TMP_BASE.mkdir(parents=True, exist_ok=True)

# ── arg validation allowlists ─────────────────────────────────────────────────
_SAFE_ARG_KEY_RE   = re.compile(r'^[A-Za-z0-9_]{1,64}$')
_SAFE_ARG_VALUE_RE = re.compile(r'^[A-Za-z0-9_\-\.:/@ ]{0,512}$')
_SAFE_MODULE_RE    = re.compile(r'^[A-Za-z0-9_\.]{1,128}$')
_SAFE_CLASS_RE     = re.compile(r'^[A-Za-z0-9_\.]{1,64}$')
_SAFE_ID_RE        = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')

logger = logging.getLogger("SIMP.AgentManager")


# ── validation helpers ────────────────────────────────────────────────────────

def validate_agent_args(args: dict) -> dict:
    """
    Validate and sanitize agent constructor args.

    Rules:
      - Keys: alphanumeric + underscore, ≤ 64 chars
      - Values: restricted charset, ≤ 512 chars
      - Maximum 32 key-value pairs
      - Values coerced to str (int/float/bool/None allowed)

    Returns sanitized dict.  Raises TypeError / ValueError on bad input.
    """
    if not isinstance(args, dict):
        raise TypeError(f"args must be a dict, got {type(args).__name__!r}")
    if len(args) > 32:
        raise ValueError(f"Too many args ({len(args)}); maximum is 32")

    out: dict = {}
    for key, val in args.items():
        if not isinstance(key, str):
            raise TypeError(f"Arg key must be str, got {type(key).__name__!r}")
        if not _SAFE_ARG_KEY_RE.match(key):
            raise ValueError(
                f"Unsafe arg key {key!r}; allowed pattern: {_SAFE_ARG_KEY_RE.pattern}"
            )
        if val is None:
            str_val = ""
        elif isinstance(val, bool):
            str_val = str(val)
        elif isinstance(val, (int, float)):
            str_val = str(val)
        elif isinstance(val, str):
            str_val = val
        else:
            raise TypeError(
                f"Arg value for {key!r} must be str/int/float/bool/None, "
                f"got {type(val).__name__!r}"
            )
        if not _SAFE_ARG_VALUE_RE.match(str_val):
            raise ValueError(
                f"Unsafe value for arg {key!r}: contains disallowed characters"
            )
        out[key] = str_val
    return out


def _safe_env(args: dict) -> dict:
    """Build a subprocess env dict from validated args (SIMP_AGENT_* prefix)."""
    validated = validate_agent_args(args)
    env = dict(os.environ)
    for k, v in validated.items():
        env[f"SIMP_AGENT_{k.upper()}"] = v
    return env


# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class RemoteAgent:
    agent_id:      str
    agent_type:    str
    process:       Optional[mp.Process] = None
    port:          int = 0
    pid:           Optional[int] = None
    status:        str = "stopped"
    started_at:    Optional[str] = None
    error_message: Optional[str] = None
    metrics:       Dict[str, Any] = field(default_factory=dict)
    _script_path:  Optional[str] = field(default=None, repr=False)

    def is_alive(self) -> bool:
        return self.process is not None and self.process.is_alive()


class AgentManager:
    """
    Manages SIMP agents as separate processes.

    v0.2 changes:
      - Paths derived from _PROJECT_ROOT, never hardcoded
      - Args passed via env vars (no code-gen injection)
      - Bare exceptions replaced with specific handlers + logging
    """

    def __init__(self, broker_config: Dict[str, Any] = None):
        self.agents:        Dict[str, RemoteAgent] = {}
        self.broker_config: Dict[str, Any]         = broker_config or {}
        self.next_port:     int                    = 5001
        logger.info("✅ Agent Manager initialized (project root: %s)", _PROJECT_ROOT)

    # ── port allocation ───────────────────────────────────────────────────────

    def _get_next_port(self) -> int:
        port = self.next_port
        self.next_port += 1
        return port

    # ── arg / id validation ───────────────────────────────────────────────────

    def _validate_ids(self, agent_id: str, agent_type: str,
                      agent_module: str, agent_class: str) -> None:
        for name, val, pat in [
            ("agent_id",    agent_id,     _SAFE_ID_RE),
            ("agent_type",  agent_type,   _SAFE_ID_RE),
            ("agent_module", agent_module, _SAFE_MODULE_RE),
            ("agent_class", agent_class,  _SAFE_CLASS_RE),
        ]:
            if not pat.match(val):
                raise ValueError(
                    f"Invalid {name} {val!r}; must match {pat.pattern}"
                )

    # ── spawn ─────────────────────────────────────────────────────────────────

    def spawn_agent(
        self,
        agent_id:     str,
        agent_type:   str,
        agent_class:  str,
        agent_module: str,
        args:         Optional[Dict[str, Any]] = None,
    ) -> Optional["RemoteAgent"]:
        """
        Spawn an agent as a separate process.

        Args are validated and passed via SIMP_AGENT_* environment variables
        rather than being interpolated into generated Python code.
        """
        # ── validate identifiers ─────────────────────────────────────────
        try:
            self._validate_ids(agent_id, agent_type, agent_module, agent_class)
        except ValueError as exc:
            logger.error("❌ Invalid spawn arguments: %s", exc)
            return None

        if agent_id in self.agents:
            logger.error("❌ Agent '%s' already spawned", agent_id)
            return None

        # ── validate args ─────────────────────────────────────────────────
        safe_args: dict = {}
        try:
            safe_args = validate_agent_args(args or {})
        except (TypeError, ValueError) as exc:
            logger.error("❌ Invalid agent args for '%s': %s", agent_id, exc)
            return None

        port = self._get_next_port()
        logger.info("🚀 Spawning agent: %s (%s) on port %s", agent_id, agent_type, port)

        remote_agent = RemoteAgent(
            agent_id=agent_id, agent_type=agent_type,
            port=port, status="starting",
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            # ── write launcher script using safe path ─────────────────────
            script_path = self._write_launcher_script(
                agent_id, agent_type, agent_class, agent_module, port
            )
            remote_agent._script_path = script_path

            # ── build env with args (no code injection) ───────────────────
            env = _safe_env(safe_args)

            # ── spawn via multiprocessing ─────────────────────────────────
            process = mp.Process(
                target=self._run_agent_process,
                args=(script_path, agent_id, port, env),
                name=f"simp-{agent_type}-{agent_id}",
            )
            process.start()

            remote_agent.process = process
            remote_agent.pid     = process.pid
            remote_agent.status  = "running"
            self.agents[agent_id] = remote_agent

            logger.info("✅ Agent spawned: %s (PID: %s, Port: %s)",
                        agent_id, process.pid, port)
            return remote_agent

        except OSError as exc:
            logger.error("❌ OS error spawning agent '%s': %s",
                         agent_id, exc, exc_info=True)
            remote_agent.status        = "failed"
            remote_agent.error_message = str(exc)
            self.agents[agent_id]      = remote_agent
            return None
        except Exception as exc:
            logger.error("❌ Unexpected error spawning agent '%s': %s",
                         agent_id, exc, exc_info=True)
            remote_agent.status        = "failed"
            remote_agent.error_message = str(exc)
            self.agents[agent_id]      = remote_agent
            return None

    def _write_launcher_script(
        self, agent_id: str, agent_type: str,
        agent_class: str, agent_module: str, port: int
    ) -> str:
        """
        Write a minimal, injection-free launcher script.

        Args are NOT embedded in the script — they are read from SIMP_AGENT_*
        env vars at runtime, keeping the script source static and safe.
        """
        class_name = agent_class.split(".")[-1]   # safe: already validated

        # All paths relative to project root — no hardcoded absolute paths
        script_content = (
            "import os, sys, logging\n"
            f"sys.path.insert(0, {str(_PROJECT_ROOT)!r})\n"
            f"from {agent_module} import {class_name}\n"
            "from simp.server.agent_client import SimpAgentClient\n"
            "logging.basicConfig(level=logging.INFO,\n"
            "    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')\n"
            f"logger = logging.getLogger('Agent.{agent_id}')\n"
            "# Collect args from env (SIMP_AGENT_* prefix)\n"
            "agent_args = {k[11:].lower(): v for k, v in os.environ.items()\n"
            "              if k.startswith('SIMP_AGENT_')}\n"
            f"logger.info('Starting agent {agent_id} on port {port}')\n"
            "try:\n"
            f"    agent = {class_name}(agent_id={agent_id!r}, **agent_args)\n"
            f"    client = SimpAgentClient(\n"
            f"        agent_id={agent_id!r}, agent_type={agent_type!r},\n"
            f"        port={port},\n"
            "        broker_host=os.environ.get('SIMP_BROKER_HOST', '127.0.0.1'),\n"
            "        broker_port=int(os.environ.get('SIMP_BROKER_PORT', '5555')),\n"
            "    )\n"
            "    client.register()\n"
            "    client.listen(agent)\n"
            "except Exception as exc:\n"
            "    logger.error('Agent failed: %s', exc, exc_info=True)\n"
            "    sys.exit(1)\n"
        )

        # Use mkstemp for a unique, mode-600 temp file
        fd, script_path = tempfile.mkstemp(
            suffix=".py",
            prefix=f"simp_agent_{agent_id}_",
            dir=_TMP_BASE,
        )
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(script_content)
            # Restrict to owner only
            os.chmod(script_path, 0o700)
        except OSError as exc:
            logger.error("Failed to write launcher script: %s", exc,
                         exc_info=True)
            raise
        return script_path

    @staticmethod
    def _run_agent_process(script_path: str, agent_id: str,
                           port: int, env: dict) -> None:
        """Run agent in subprocess with the provided env."""
        try:
            import subprocess
            subprocess.run(
                [sys.executable, script_path],
                env=env,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            logging.error("Agent %s exited with code %s", agent_id,
                          exc.returncode)
        except OSError as exc:
            logging.error("OS error running agent %s: %s", agent_id, exc,
                          exc_info=True)
        except Exception as exc:
            logging.error("Unexpected error running agent %s: %s", agent_id,
                          exc, exc_info=True)
        finally:
            # Clean up temp script
            try:
                if os.path.exists(script_path):
                    os.unlink(script_path)
            except OSError as exc:
                logging.warning("Could not remove temp script %s: %s",
                                script_path, exc)

    # ── agent control ─────────────────────────────────────────────────────────

    def get_agent(self, agent_id: str) -> Optional[RemoteAgent]:
        return self.agents.get(agent_id)

    def list_agents(self) -> Dict[str, RemoteAgent]:
        return dict(self.agents)

    def stop_agent(self, agent_id: str, timeout: int = 5) -> bool:
        agent = self.get_agent(agent_id)
        if not agent:
            logger.warning("⚠️ Agent '%s' not found", agent_id)
            return False
        if agent.process is None or not agent.process.is_alive():
            agent.status = "stopped"
            return True
        try:
            agent.process.terminate()
            agent.process.join(timeout=timeout)
            if agent.process.is_alive():
                agent.process.kill()
                agent.process.join()
            agent.status = "stopped"
            logger.info("✅ Agent terminated: %s", agent_id)
            return True
        except OSError as exc:
            logger.error("❌ OS error stopping agent '%s': %s",
                         agent_id, exc, exc_info=True)
            return False
        except Exception as exc:
            logger.error("❌ Unexpected error stopping agent '%s': %s",
                         agent_id, exc, exc_info=True)
            return False

    def stop_all_agents(self, timeout: int = 5) -> Dict[str, bool]:
        return {aid: self.stop_agent(aid, timeout)
                for aid in list(self.agents.keys())}

    def get_health_status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {
            "total_agents": len(self.agents),
            "running": 0, "stopped": 0, "failed": 0,
            "agents": {},
        }
        for agent_id, agent in self.agents.items():
            status["agents"][agent_id] = {
                "status":    agent.status,
                "type":      agent.agent_type,
                "port":      agent.port,
                "pid":       agent.pid,
                "is_alive":  agent.is_alive(),
                "started_at": agent.started_at,
                "error":     agent.error_message,
            }
            if agent.status == "running":
                status["running"] += 1
            elif agent.status == "stopped":
                status["stopped"] += 1
            elif agent.status == "failed":
                status["failed"] += 1
        return status

    def restart_agent(self, agent_id: str) -> Optional[RemoteAgent]:
        agent = self.get_agent(agent_id)
        if not agent:
            return None
        logger.info("🔄 Restarting agent: %s", agent_id)
        self.stop_agent(agent_id)
        time.sleep(1)
        logger.warning("⚠️ Full restart requires re-calling spawn_agent()")
        return None
