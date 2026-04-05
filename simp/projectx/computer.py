"""
ProjectX Computer-Use Agent — bounded action execution layer.

Provides a safe, auditable interface for AI agents to interact with
the host computer via screenshot observation, GUI actions, and shell
execution. Designed for SIMP protocol integration.

Architecture notes:
- Flat policy: no internal planner, the calling agent decides each step
- Bounded action space: 14 methods, no arbitrary code from GUI path
- Tiered risk: Tier 0 (read-only), Tier 1 (GUI), Tier 2 (shell), Tier 3 (approval-required)
- Every action logged with pre/post state for bBoN-compatible traces

See SPRINT_LOG.md "ProjectX Computer-Use Design Review" for full design rationale.
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TaskAbortError(Exception):
    """Raised when a computer-use task is explicitly aborted."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Task aborted: {reason}")


# Action tier classification
ACTION_TIERS = {
    "get_screenshot": 0,
    "get_active_window": 0,
    "ocr_screen": 0,
    "snapshot_state": 0,
    "click": 1,
    "double_click": 1,
    "type_text": 1,
    "press": 1,
    "scroll": 1,
    "focus_app": 1,
    "run_shell": 2,
    "log_action": -1,   # cross-tier, always allowed
    "safe_execute": -1,  # wrapper, always allowed
    "abort": -1,         # control, always allowed
}

# Maximum allowed tier without explicit approval
DEFAULT_MAX_TIER = 2


class ProjectXComputer:
    """
    Bounded computer-use execution layer for ProjectX.

    All GUI and shell interactions go through this class, which enforces
    action validation, tiered risk gating, and audit logging.
    """

    def __init__(
        self,
        log_dir: Optional[str] = None,
        max_tier: int = DEFAULT_MAX_TIER,
        screen_resolution: Optional[Tuple[int, int]] = None,
    ):
        """
        Initialize the ProjectX computer-use layer.

        Args:
            log_dir: Directory for action JSONL logs. Defaults to ./projectx_logs/
            max_tier: Maximum action tier allowed without approval (0-3). Default 2.
            screen_resolution: Override screen resolution (width, height). Auto-detected if None.
        """
        self.log_dir = Path(log_dir or "./projectx_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_tier = max_tier
        self._screen_resolution = screen_resolution
        self._action_log_path = self.log_dir / "actions.jsonl"
        self._action_count = 0
        logger.info(
            f"ProjectXComputer initialized (max_tier={max_tier}, log_dir={self.log_dir})"
        )

    # ── Tier 0: Observation (read-only, always allowed) ──────────────

    def get_screenshot(self) -> bytes:
        """Capture the current screen as PNG bytes."""
        try:
            import pyautogui
            import io
            img = pyautogui.screenshot()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as exc:
            logger.warning(f"Screenshot capture failed: {exc}")
            # Return a minimal 1x1 transparent PNG as fallback
            return self._fallback_png()

    @staticmethod
    def _fallback_png() -> bytes:
        """Return a minimal valid PNG (1x1 transparent pixel) for headless environments."""
        import struct, zlib
        def _chunk(chunk_type, data):
            c = chunk_type + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        raw = zlib.compress(b"\x00\x00\x00\x00\x00")
        idat = _chunk(b"IDAT", raw)
        iend = _chunk(b"IEND", b"")
        return sig + ihdr + idat + iend

    def get_active_window(self) -> str:
        """Return the name and title of the currently focused window."""
        import platform
        system = platform.system()
        try:
            if system == "Darwin":
                result = subprocess.run(
                    ["osascript", "-e",
                     'tell application "System Events" to get name of first application process whose frontmost is true'],
                    capture_output=True, text=True, timeout=5
                )
                app_name = result.stdout.strip() or "Unknown"
                # Get window title
                result2 = subprocess.run(
                    ["osascript", "-e",
                     f'tell application "System Events" to get title of front window of (first application process whose frontmost is true)'],
                    capture_output=True, text=True, timeout=5
                )
                title = result2.stdout.strip() or ""
                return f"{app_name}: {title}" if title else app_name
            elif system == "Linux":
                result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True, text=True, timeout=5
                )
                return result.stdout.strip() or "Unknown"
            else:
                return f"Unsupported platform: {system}"
        except Exception as exc:
            logger.warning(f"Active window detection failed: {exc}")
            return "Unknown (detection failed)"

    def ocr_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> List[Dict[str, Any]]:
        """Run OCR on the current screen or a region."""
        try:
            import pyautogui
            img = pyautogui.screenshot(region=region)
            return self._run_ocr(img)
        except ImportError:
            logger.warning("pyautogui not available — returning empty OCR")
            return []
        except Exception as exc:
            logger.warning(f"OCR failed: {exc}")
            return []

    def _run_ocr(self, image) -> List[Dict[str, Any]]:
        """Run OCR on a PIL Image. Tries pytesseract first, then basic fallback."""
        try:
            import pytesseract
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            results = []
            for i in range(len(data["text"])):
                text = data["text"][i].strip()
                if text and data["conf"][i] > 0:
                    results.append({
                        "text": text,
                        "bbox": [data["left"][i], data["top"][i],
                                 data["width"][i], data["height"][i]],
                        "confidence": float(data["conf"][i]) / 100.0,
                    })
            return results
        except ImportError:
            logger.warning("pytesseract not available — OCR disabled")
            return []

    def snapshot_state(self) -> Dict[str, Any]:
        """Capture a full observation: screenshot + active window + OCR text."""
        screenshot = self.get_screenshot()
        active_window = self.get_active_window()

        # Run OCR from screenshot bytes rather than taking a second screenshot
        ocr_text = []
        try:
            import io
            from PIL import Image
            img = Image.open(io.BytesIO(screenshot))
            ocr_text = self._run_ocr(img)
        except Exception:
            ocr_text = []

        resolution = self._screen_resolution
        if resolution is None:
            try:
                import pyautogui
                size = pyautogui.size()
                resolution = (size.width, size.height)
            except Exception:
                resolution = (0, 0)

        return {
            "screenshot": screenshot,
            "active_window": active_window,
            "ocr_text": ocr_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "screen_resolution": resolution,
        }

    # ── Tier 1: GUI Actions (low-risk, reversible) ───────────────────

    def click(self, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        """Click at screen coordinates."""
        raise NotImplementedError("Sprint 12")

    def double_click(self, x: int, y: int) -> Dict[str, Any]:
        """Double-click at screen coordinates."""
        raise NotImplementedError("Sprint 12")

    def type_text(self, text: str) -> Dict[str, Any]:
        """Type text at the current cursor position."""
        raise NotImplementedError("Sprint 12")

    def press(self, keys: str) -> Dict[str, Any]:
        """Press a key or key combination (e.g., 'command+c', 'enter')."""
        raise NotImplementedError("Sprint 12")

    def scroll(self, dx: int, dy: int) -> Dict[str, Any]:
        """Scroll by (dx, dy) units."""
        raise NotImplementedError("Sprint 12")

    def focus_app(self, app_name: str) -> Dict[str, Any]:
        """Bring the named application to the foreground."""
        raise NotImplementedError("Sprint 12")

    # ── Tier 2: Shell Execution (medium-risk, logged) ────────────────

    def run_shell(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a shell command with timeout and output capture."""
        raise NotImplementedError("Sprint 12")

    # ── Cross-tier: Logging & Control ────────────────────────────────

    def log_action(self, action: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Append an action+result entry to the JSONL audit log."""
        raise NotImplementedError("Sprint 13")

    def safe_execute(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Primary entry point: validate, execute, log, return.

        Args:
            step: {"action": "click", "params": {"x": 100, "y": 200}}

        Returns:
            {"success": bool, "data": ..., "error": str|None, "duration_ms": int}
        """
        raise NotImplementedError("Sprint 13")

    def abort(self, reason: str) -> None:
        """Abort the current task with a logged reason."""
        raise NotImplementedError("Sprint 13")
