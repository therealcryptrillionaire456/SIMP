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

    # ── Helper: Standard result wrapper ────────────────────────────────

    def _make_result(
        self, success: bool, data: Any = None, error: Optional[str] = None,
        start_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Build a standard action result dict."""
        duration_ms = int((time.time() - start_time) * 1000) if start_time else 0
        return {
            "success": success,
            "data": data,
            "error": error,
            "duration_ms": duration_ms,
        }

    # ── Tier 1: GUI Actions (low-risk, reversible) ───────────────────

    def click(self, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        """Click at screen coordinates."""
        start = time.time()
        try:
            import pyautogui
            pyautogui.click(x=x, y=y, button=button)
            return self._make_result(True, {"x": x, "y": y, "button": button}, start_time=start)
        except Exception as exc:
            return self._make_result(False, error=str(exc), start_time=start)

    def double_click(self, x: int, y: int) -> Dict[str, Any]:
        """Double-click at screen coordinates."""
        start = time.time()
        try:
            import pyautogui
            pyautogui.doubleClick(x=x, y=y)
            return self._make_result(True, {"x": x, "y": y}, start_time=start)
        except Exception as exc:
            return self._make_result(False, error=str(exc), start_time=start)

    def type_text(self, text: str) -> Dict[str, Any]:
        """Type text at the current cursor position."""
        start = time.time()
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.02)
            return self._make_result(True, {"text_length": len(text)}, start_time=start)
        except Exception as exc:
            return self._make_result(False, error=str(exc), start_time=start)

    def press(self, keys: str) -> Dict[str, Any]:
        """Press a key or key combination (e.g., 'command+c', 'enter')."""
        start = time.time()
        try:
            import pyautogui
            if "+" in keys:
                parts = [k.strip() for k in keys.split("+")]
                pyautogui.hotkey(*parts)
            else:
                pyautogui.press(keys.strip())
            return self._make_result(True, {"keys": keys}, start_time=start)
        except Exception as exc:
            return self._make_result(False, error=str(exc), start_time=start)

    def scroll(self, dx: int, dy: int) -> Dict[str, Any]:
        """Scroll by (dx, dy) units. Positive dy = scroll up."""
        start = time.time()
        try:
            import pyautogui
            if dy != 0:
                pyautogui.scroll(dy)
            if dx != 0:
                pyautogui.hscroll(dx)
            return self._make_result(True, {"dx": dx, "dy": dy}, start_time=start)
        except Exception as exc:
            return self._make_result(False, error=str(exc), start_time=start)

    def focus_app(self, app_name: str) -> Dict[str, Any]:
        """Bring the named application to the foreground."""
        start = time.time()
        import platform
        try:
            if platform.system() == "Darwin":
                result = subprocess.run(
                    ["osascript", "-e", f'tell application "{app_name}" to activate'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return self._make_result(True, {"app": app_name}, start_time=start)
                else:
                    return self._make_result(
                        False, error=result.stderr.strip() or "osascript failed",
                        start_time=start
                    )
            elif platform.system() == "Linux":
                result = subprocess.run(
                    ["wmctrl", "-a", app_name],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return self._make_result(True, {"app": app_name}, start_time=start)
                else:
                    return self._make_result(False, error="wmctrl failed", start_time=start)
            else:
                return self._make_result(False, error=f"Unsupported platform: {platform.system()}", start_time=start)
        except Exception as exc:
            return self._make_result(False, error=str(exc), start_time=start)

    # ── Tier 2: Shell Execution (medium-risk, logged) ────────────────

    def run_shell(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute a shell command with timeout and output capture.

        Returns standard result with data containing stdout, stderr, return_code.
        """
        start = time.time()
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return self._make_result(
                success=(result.returncode == 0),
                data={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                    "command": command,
                },
                start_time=start,
            )
        except subprocess.TimeoutExpired:
            return self._make_result(
                False, error=f"Command timed out after {timeout}s", start_time=start
            )
        except Exception as exc:
            return self._make_result(False, error=str(exc), start_time=start)

    # ── Cross-tier: Logging & Control ────────────────────────────────

    def log_action(self, action: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Append an action+result entry to the JSONL audit log.

        Each log line is a self-contained JSON object with:
        - action_index: sequential counter
        - timestamp: ISO 8601 UTC
        - action: the action dict (method name + params)
        - result: the result dict (success, data, error, duration_ms)
        - pre_state: snapshot before action (if available in result)
        - post_state: snapshot after action (if available in result)
        """
        self._action_count += 1
        entry = {
            "action_index": self._action_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "result": {
                k: v for k, v in result.items()
                if k != "pre_state" and k != "post_state"
            },
        }
        # Include pre/post state references (not full screenshots — too large for JSONL)
        if "pre_state" in result:
            entry["pre_state"] = {
                "active_window": result["pre_state"].get("active_window", ""),
                "timestamp": result["pre_state"].get("timestamp", ""),
                "screen_resolution": result["pre_state"].get("screen_resolution", (0, 0)),
                "ocr_summary": len(result["pre_state"].get("ocr_text", [])),
            }
        if "post_state" in result:
            entry["post_state"] = {
                "active_window": result["post_state"].get("active_window", ""),
                "timestamp": result["post_state"].get("timestamp", ""),
                "screen_resolution": result["post_state"].get("screen_resolution", (0, 0)),
                "ocr_summary": len(result["post_state"].get("ocr_text", [])),
            }

        try:
            with open(self._action_log_path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            logger.error(f"Failed to write action log: {exc}")

    def safe_execute(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Primary entry point: validate, execute, log, return.

        Args:
            step: {"action": "click", "params": {"x": 100, "y": 200}}

        Returns:
            {"success": bool, "data": ..., "error": str|None, "duration_ms": int}
        """
        start = time.time()
        action_name = step.get("action", "")
        params = step.get("params", {})

        # 1. Validate action exists in the allowlist
        if action_name not in ACTION_TIERS:
            error = f"Unknown action: '{action_name}'. Allowed: {sorted(k for k, v in ACTION_TIERS.items() if v >= 0)}"
            result = self._make_result(False, error=error, start_time=start)
            self.log_action(step, result)
            return result

        # 2. Check tier
        tier = ACTION_TIERS[action_name]
        if tier > self.max_tier:
            error = f"Action '{action_name}' requires tier {tier} but max allowed is {self.max_tier}"
            result = self._make_result(False, error=error, start_time=start)
            self.log_action(step, result)
            return result

        # 3. Get the method
        method = getattr(self, action_name, None)
        if method is None or not callable(method):
            error = f"Action '{action_name}' not implemented"
            result = self._make_result(False, error=error, start_time=start)
            self.log_action(step, result)
            return result

        # 4. Capture pre-state for tier 1+ actions
        pre_state = None
        if tier >= 1:
            try:
                pre_state = self.snapshot_state()
            except Exception:
                pre_state = None

        # 5. Execute
        try:
            result = method(**params)
            if not isinstance(result, dict):
                result = self._make_result(True, data=result, start_time=start)
        except TaskAbortError:
            raise  # Let abort propagate
        except Exception as exc:
            result = self._make_result(False, error=str(exc), start_time=start)

        # 6. Capture post-state for tier 1+ actions
        post_state = None
        if tier >= 1:
            try:
                post_state = self.snapshot_state()
            except Exception:
                post_state = None

        # 7. Enrich result with states and log
        if pre_state:
            result["pre_state"] = pre_state
        if post_state:
            result["post_state"] = post_state

        self.log_action(step, result)
        return result

    def abort(self, reason: str) -> None:
        """
        Abort the current task with a logged reason.

        Logs the abort event and raises TaskAbortError for the SIMP task ledger
        to catch and record as a task failure.
        """
        self.log_action(
            {"action": "abort", "params": {"reason": reason}},
            self._make_result(False, error=f"Task aborted: {reason}"),
        )
        logger.warning(f"ProjectX task aborted: {reason}")
        raise TaskAbortError(reason)
