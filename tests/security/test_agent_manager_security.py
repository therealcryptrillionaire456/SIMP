"""Security tests for SIMP AgentManager."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from simp.server.agent_manager import AgentManager, validate_agent_args


class TestHardcodedPaths:
    """Verify that hardcoded-path injection vectors are handled safely."""

    def test_no_sessions_path_in_args(self):
        """Args containing '/sessions/' paths should be accepted by validation.

        The value regex allows slashes so absolute paths pass validation.
        The security guarantee comes from args being passed via env vars
        (not interpolated into code), making path values safe.
        """
        args = {"data_dir": "/sessions/agent1"}
        result = validate_agent_args(args)
        assert result == {"data_dir": "/sessions/agent1"}

    def test_reject_shell_injection_in_args(self):
        """Values with shell metacharacters must be rejected."""
        with pytest.raises(ValueError):
            validate_agent_args({"cmd": "$(rm -rf /)"})

    def test_reject_non_dict_args(self):
        """Non-dict args must raise TypeError."""
        with pytest.raises(TypeError):
            validate_agent_args("not a dict")

    def test_reject_too_many_args(self):
        """More than 32 args must be rejected."""
        args = {f"key{i}": "val" for i in range(33)}
        with pytest.raises(ValueError):
            validate_agent_args(args)

    def test_reject_unsafe_key(self):
        """Keys with special characters must be rejected."""
        with pytest.raises(ValueError):
            validate_agent_args({"key;drop": "value"})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
