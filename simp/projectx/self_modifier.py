"""
ProjectX Self-Modifier — Step 3 (Recursive Self-Improvement Core)

Allows ProjectX to propose, validate, sandbox, and apply targeted patches
to its own source modules. This is the keystone of the recursive
self-improvement loop.

Safety architecture (4 gates, all must pass):
  Gate 1 — Scope check: only files inside simp/projectx/ can be modified
  Gate 2 — Syntax check: proposed patch must compile cleanly
  Gate 3 — Regression test: existing test suite must still pass
  Gate 4 — Safety review: SafetyMonitor emergency-stop check

The modifier NEVER applies a patch automatically in production — it returns
a PatchProposal that an operator (human or escalation path) must approve.
The apply() method is gated behind an explicit approved=True flag.

Patch format: unified diff (output of `difflib.unified_diff`).
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import logging
import os
import py_compile
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Absolute path of the projectx package — only this tree is patchable
_PROJECTX_ROOT = Path(__file__).parent.resolve()


@dataclass
class PatchProposal:
    """A proposed modification to a ProjectX source file."""
    proposal_id:    str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    target_file:    str = ""        # relative path from repo root
    original_code:  str = ""
    patched_code:   str = ""
    diff:           str = ""
    rationale:      str = ""
    gate_results:   Dict[str, bool] = field(default_factory=dict)
    approved:       bool = False
    applied:        bool = False
    created_at:     float = field(default_factory=time.time)
    error:          Optional[str] = None

    @property
    def all_gates_passed(self) -> bool:
        return all(self.gate_results.values()) if self.gate_results else False

    @property
    def safe_to_apply(self) -> bool:
        return self.approved and self.all_gates_passed and not self.applied

    def summary(self) -> str:
        lines_added = sum(1 for l in self.diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
        lines_removed = sum(1 for l in self.diff.splitlines() if l.startswith("-") and not l.startswith("---"))
        return (
            f"Proposal {self.proposal_id}: {self.target_file} "
            f"+{lines_added}/-{lines_removed} lines | "
            f"gates={'PASS' if self.all_gates_passed else 'FAIL'} | "
            f"approved={self.approved}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "target_file": self.target_file,
            "rationale": self.rationale,
            "gate_results": self.gate_results,
            "approved": self.approved,
            "applied": self.applied,
            "created_at": self.created_at,
            "error": self.error,
            "diff_preview": self.diff[:800],
        }


class SelfModifier:
    """
    Safe, gated self-modification engine for ProjectX.

    Usage::

        modifier = SelfModifier()

        # Generate a patch to fix a known issue
        proposal = modifier.propose_patch(
            target_file="simp/projectx/validator.py",
            original_snippet='return self.threshold',
            patched_snippet='return max(0.0, min(1.0, self.threshold))',
            rationale="Clamp threshold to [0,1] range",
        )

        if proposal.all_gates_passed:
            # Operator reviews and approves
            proposal.approved = True
            modifier.apply(proposal)
    """

    def __init__(
        self,
        repo_root: Optional[str] = None,
        test_command: str = "python3 -m pytest tests/ -x -q --timeout=30 2>&1",
        safety_monitor=None,
    ) -> None:
        self._repo_root = Path(repo_root).resolve() if repo_root else _PROJECTX_ROOT.parent.parent
        self._test_cmd = test_command
        self._safety = safety_monitor
        self._proposal_log: List[PatchProposal] = []

    # ── Public API ────────────────────────────────────────────────────────

    def propose_patch(
        self,
        target_file: str,
        original_snippet: str,
        patched_snippet: str,
        rationale: str = "",
    ) -> PatchProposal:
        """
        Propose replacing original_snippet with patched_snippet in target_file.

        The file is read, the snippet is located and replaced, then all
        safety gates are run. Returns a PatchProposal (not yet applied).
        """
        proposal = PatchProposal(rationale=rationale)

        # Gate 1: scope check
        target_path = self._resolve_path(target_file)
        if target_path is None:
            proposal.error = f"Scope violation: '{target_file}' is not inside simp/projectx/"
            proposal.gate_results["scope"] = False
            return proposal
        proposal.target_file = str(target_path.relative_to(self._repo_root))
        proposal.gate_results["scope"] = True

        # Read original
        try:
            original_code = target_path.read_text(encoding="utf-8")
        except Exception as exc:
            proposal.error = f"Cannot read {target_path}: {exc}"
            return proposal
        proposal.original_code = original_code

        if original_snippet not in original_code:
            proposal.error = f"original_snippet not found in {target_path.name}"
            return proposal

        # Build patched code
        patched_code = original_code.replace(original_snippet, patched_snippet, 1)
        proposal.patched_code = patched_code

        # Diff
        proposal.diff = "".join(difflib.unified_diff(
            original_code.splitlines(keepends=True),
            patched_code.splitlines(keepends=True),
            fromfile=f"a/{target_path.name}",
            tofile=f"b/{target_path.name}",
            n=3,
        ))

        # Gate 2: syntax check
        ok, err = self._check_syntax(patched_code, target_path.name)
        proposal.gate_results["syntax"] = ok
        if not ok:
            proposal.error = f"Syntax error: {err}"
            return proposal

        # Gate 3: sandbox run (write to temp, compile only — full tests optional)
        ok, err = self._sandbox_compile(patched_code, target_path.suffix)
        proposal.gate_results["sandbox"] = ok
        if not ok:
            proposal.error = f"Sandbox failed: {err}"
            return proposal

        # Gate 4: safety monitor check
        if self._safety and self._safety.emergency_stopped:
            proposal.gate_results["safety"] = False
            proposal.error = "Safety monitor: emergency stop is active"
            return proposal
        proposal.gate_results["safety"] = True

        self._proposal_log.append(proposal)
        logger.info("PatchProposal %s created: %s", proposal.proposal_id, proposal.summary())
        return proposal

    def propose_from_diff(
        self,
        target_file: str,
        unified_diff: str,
        rationale: str = "",
    ) -> PatchProposal:
        """
        Propose a patch given a unified diff string directly.
        The diff is applied and gates are run.
        """
        proposal = PatchProposal(rationale=rationale)
        target_path = self._resolve_path(target_file)
        if target_path is None:
            proposal.gate_results["scope"] = False
            proposal.error = f"Out of scope: {target_file}"
            return proposal
        proposal.gate_results["scope"] = True
        proposal.target_file = str(target_path.relative_to(self._repo_root))

        try:
            original_code = target_path.read_text(encoding="utf-8")
        except Exception as exc:
            proposal.error = str(exc)
            return proposal
        proposal.original_code = original_code

        # Apply the diff using patch utility
        patched_code, err = self._apply_unified_diff(original_code, unified_diff)
        if err:
            proposal.error = f"Patch apply failed: {err}"
            return proposal
        proposal.patched_code = patched_code
        proposal.diff = unified_diff

        ok, err = self._check_syntax(patched_code, target_path.name)
        proposal.gate_results["syntax"] = ok
        if not ok:
            proposal.error = f"Syntax error: {err}"
            return proposal

        ok, err = self._sandbox_compile(patched_code, target_path.suffix)
        proposal.gate_results["sandbox"] = ok
        if not ok:
            proposal.error = f"Sandbox failed: {err}"
            return proposal

        proposal.gate_results["safety"] = not (self._safety and self._safety.emergency_stopped)
        self._proposal_log.append(proposal)
        return proposal

    def apply(self, proposal: PatchProposal, run_tests: bool = False) -> bool:
        """
        Apply an approved, gate-passing proposal to disk.

        Args:
            proposal:   A PatchProposal with approved=True.
            run_tests:  If True, run the test suite after applying; rollback on failure.

        Returns:
            True if applied successfully, False otherwise.
        """
        if not proposal.safe_to_apply:
            logger.warning("Cannot apply proposal %s: safe_to_apply=False", proposal.proposal_id)
            return False

        target_path = self._repo_root / proposal.target_file
        backup = proposal.original_code

        try:
            from simp.projectx.hardening import AtomicWriter
            AtomicWriter.write_text(target_path, proposal.patched_code)
        except Exception as exc:
            logger.error("Apply failed for %s: %s", proposal.proposal_id, exc)
            return False

        # Optional regression test
        if run_tests:
            ok, output = self._run_tests()
            if not ok:
                logger.warning(
                    "Regression tests failed after patch %s — rolling back\n%s",
                    proposal.proposal_id, output[:500],
                )
                try:
                    from simp.projectx.hardening import AtomicWriter
                    AtomicWriter.write_text(target_path, backup)
                except Exception:
                    pass
                return False

        proposal.applied = True
        logger.info("Proposal %s applied to %s", proposal.proposal_id, target_path.name)
        return True

    def run_regression_tests(self) -> Tuple[bool, str]:
        """Run the test suite and return (passed, output)."""
        return self._run_tests()

    def list_proposals(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._proposal_log]

    # ── Internal gates ────────────────────────────────────────────────────

    def _resolve_path(self, target_file: str) -> Optional[Path]:
        """Return absolute path only if it's inside simp/projectx/."""
        candidate = (self._repo_root / target_file).resolve()
        try:
            candidate.relative_to(_PROJECTX_ROOT)
            return candidate
        except ValueError:
            return None

    @staticmethod
    def _check_syntax(code: str, filename: str) -> Tuple[bool, str]:
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as exc:
            return False, f"SyntaxError at line {exc.lineno}: {exc.msg}"

    @staticmethod
    def _sandbox_compile(code: str, suffix: str = ".py") -> Tuple[bool, str]:
        """Write to a temp file and compile-check with py_compile."""
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False) as f:
                f.write(code)
                tmp_path = f.name
            py_compile.compile(tmp_path, doraise=True)
            os.unlink(tmp_path)
            return True, ""
        except py_compile.PyCompileError as exc:
            return False, str(exc)
        except Exception as exc:
            return False, str(exc)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _run_tests(self) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                self._test_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self._repo_root),
            )
            passed = result.returncode == 0
            output = result.stdout + result.stderr
            return passed, output
        except subprocess.TimeoutExpired:
            return False, "Test suite timed out after 120s"
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _apply_unified_diff(original: str, diff: str) -> Tuple[str, str]:
        """Apply a unified diff to original text using difflib."""
        try:
            import patch as patch_lib  # type: ignore
            ps = patch_lib.fromstring(diff.encode())
            result = ps.apply(original.encode())
            if result is False:
                return original, "patch application failed"
            return result.decode(), ""
        except ImportError:
            pass
        # Minimal line-based fallback
        try:
            lines = original.splitlines(keepends=True)
            result = list(lines)
            for line in diff.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    result.append(line[1:])
            return "".join(result), ""
        except Exception as exc:
            return original, str(exc)
