"""
patches/agent_manager_patch.py
────────────────────────────────
Drop-in replacement sections for agent_manager.py.

Issues addressed:
  #1  Code injection via unsanitized `args` string interpolation
  #6  Bare exception handlers
  #12 Hardcoded /tmp and /sessions/... paths

HOW TO APPLY:
  1. Open ~/code/SIMP/agent_manager.py in your editor.
  2. Find each "REPLACE TARGET" block and swap it for the corresponding
     "REPLACEMENT" block below.
  3. Add the imports from "NEW IMPORTS" at the top of the file.
  4. Run: pytest tests/security/test_agent_manager_security.py -v
"""

# ─────────────────────────────────────────────────────────────────────────────
# NEW IMPORTS  (add near the top of agent_manager.py, after existing imports)
# ─────────────────────────────────────────────────────────────────────────────
NEW_IMPORTS = """
import re
import sys
import tempfile
from pathlib import Path

# Project-root-relative base path (replaces all hardcoded /tmp /sessions paths)
_PROJECT_ROOT = Path(__file__).resolve().parent

try:
    from config.config import config as _simp_config
    _TMP_DIR = Path(_simp_config.TMP_DIR)
except Exception:
    _TMP_DIR = Path(tempfile.gettempdir()) / "simp"

_TMP_DIR.mkdir(parents=True, exist_ok=True)

# Allowlist for safe agent argument keys and value patterns
_SAFE_ARG_KEY_RE = re.compile(r'^[A-Za-z0-9_]{1,64}$')
_SAFE_ARG_VALUE_RE = re.compile(r'^[A-Za-z0-9_\\-\\.:/@ ]{0,512}$')
"""

# ─────────────────────────────────────────────────────────────────────────────
# REPLACE TARGET (around line 159):
#   agent_script_path = "/sessions/zealous-modest-wozniak/..."  (or similar)
#
# REPLACEMENT:
# ─────────────────────────────────────────────────────────────────────────────
HARDCODED_PATH_REPLACEMENT = """
# Derive script path relative to project root — never hardcode absolute paths
agent_script_path = str(_PROJECT_ROOT / "agents" / f"{agent_type}.py")
"""

# ─────────────────────────────────────────────────────────────────────────────
# REPLACE TARGET (around lines 177-178) — direct args interpolation:
#   code = f\"\"\"
#   import ...
#   agent = MyAgent({args})   # <-- INJECTION RISK
#   \"\"\"
#
# REPLACEMENT — use validate_agent_args() + pass args as env / JSON file:
# ─────────────────────────────────────────────────────────────────────────────
SAFE_ARGS_FUNCTIONS = '''
def validate_agent_args(args: dict) -> dict:
    """
    Validate agent args dict against an allowlist of key/value patterns.

    Raises ValueError for any key or value that fails validation.
    Returns a sanitized copy safe for use as subprocess environment variables.
    """
    if not isinstance(args, dict):
        raise TypeError(f"args must be a dict, got {type(args).__name__!r}")
    if len(args) > 32:
        raise ValueError(f"Too many args ({len(args)}); maximum is 32")

    sanitized = {}
    for key, value in args.items():
        if not isinstance(key, str):
            raise TypeError(f"arg key must be str, got {type(key).__name__!r}")
        if not _SAFE_ARG_KEY_RE.match(key):
            raise ValueError(
                f"Unsafe arg key {key!r}; must match {_SAFE_ARG_KEY_RE.pattern}"
            )
        # Allow None → empty string; coerce numbers to str
        if value is None:
            str_val = ""
        elif isinstance(value, (int, float, bool)):
            str_val = str(value)
        elif isinstance(value, str):
            str_val = value
        else:
            raise TypeError(
                f"arg value for {key!r} must be str/int/float/bool/None, "
                f"got {type(value).__name__!r}"
            )
        if not _SAFE_ARG_VALUE_RE.match(str_val):
            raise ValueError(
                f"Unsafe arg value for {key!r}; contains disallowed characters"
            )
        sanitized[key] = str_val

    return sanitized


def build_agent_subprocess_env(args: dict) -> dict:
    """
    Convert validated args into a subprocess environment dict.

    Keys are prefixed with SIMP_AGENT_ to avoid colliding with system vars.
    """
    validated = validate_agent_args(args)
    env = {**os.environ}  # inherit current env
    for k, v in validated.items():
        env[f"SIMP_AGENT_{k.upper()}"] = v
    return env


def launch_agent_process(agent_type: str, args: dict) -> subprocess.Popen:
    """
    Launch an agent subprocess SAFELY — no string interpolation of args.

    Args are passed via environment variables, not injected into Python code.
    """
    # Validate agent_type itself
    if not re.match(r'^[A-Za-z0-9_-]{1,64}$', agent_type):
        raise ValueError(f"Invalid agent_type {agent_type!r}")

    script_path = _PROJECT_ROOT / "agents" / f"{agent_type}.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Agent script not found: {script_path}")

    env = build_agent_subprocess_env(args)

    # Python executable from current interpreter — no hardcoded /usr/bin paths
    python = sys.executable

    return subprocess.Popen(
        [python, str(script_path)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
'''

# ─────────────────────────────────────────────────────────────────────────────
# REPLACE TARGET (around line 212) — bare except in import block:
#   try:
#       import some_module
#   except:
#       pass
#
# REPLACEMENT:
# ─────────────────────────────────────────────────────────────────────────────
BARE_EXCEPT_REPLACEMENT = '''
try:
    import some_module  # replace with actual module name
except ImportError as exc:
    logger.warning(
        "Optional module could not be imported: %s. "
        "Some features may be unavailable.",
        exc,
        exc_info=True,
    )
except Exception as exc:  # pragma: no cover
    logger.error(
        "Unexpected error importing module: %s",
        exc,
        exc_info=True,
    )
    raise
'''
