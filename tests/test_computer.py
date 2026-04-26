"""Tests for ProjectX Computer — shell execution with safety tiers."""

import json
import pytest
from unittest.mock import MagicMock, patch
from simp.projectx.computer import ProjectXComputer, ACTION_TIERS, TaskAbortError


class TestComputerImports:
    def test_computer_imports(self) -> None:
        from simp.projectx.computer import ProjectXComputer, ACTION_TIERS, TaskAbortError
        assert ProjectXComputer is not None
        assert TaskAbortError is not None

    def test_action_tiers_is_dict(self) -> None:
        assert isinstance(ACTION_TIERS, dict)
        assert len(ACTION_TIERS) > 0


class TestComputerShell:
    def test_run_shell_echo(self) -> None:
        pc = ProjectXComputer()
        result = pc.run_shell("echo hello")
        assert result["success"] is True
        assert "hello" in result["data"]["stdout"]

    def test_run_shell_returns_result_dict(self) -> None:
        pc = ProjectXComputer()
        result = pc.run_shell("echo test")
        assert isinstance(result, dict)
        assert "success" in result
        assert "data" in result
        assert "error" in result
        assert "duration_ms" in result

    def test_run_shell_with_timeout(self) -> None:
        pc = ProjectXComputer()
        result = pc.run_shell("echo fast", timeout=5)
        assert result["success"] is True

    def test_run_shell_rejects_dangerous_commands(self) -> None:
        pc = ProjectXComputer()
        dangerous = [
            "rm -rf /",
            "rm -rf / --no-preserve-root",
            "dd if=/dev/zero of=/dev/sda",
        ]
        for cmd in dangerous:
            result = pc.run_shell(cmd)
            assert result["success"] is False, f"Expected {cmd!r} to be blocked"

    def test_run_shell_strips_semicolons(self) -> None:
        pc = ProjectXComputer()
        result = pc.run_shell("echo a; echo b")
        assert result["success"] is True

    def test_run_shell_false_command(self) -> None:
        pc = ProjectXComputer()
        result = pc.run_shell("exit 1")
        assert result["success"] is False

    def test_run_shell_data_shape(self) -> None:
        pc = ProjectXComputer()
        result = pc.run_shell("echo x")
        data = result["data"]
        assert "return_code" in data
        assert "stdout" in data
        assert "stderr" in data


class TestComputerSafeExecute:
    def test_safe_execute_accepts_step_dict(self) -> None:
        pc = ProjectXComputer()
        step = {"action": "get_screenshot", "params": {}}
        result = pc.safe_execute(step)
        assert isinstance(result, dict)
        assert "success" in result

    def test_safe_execute_rejects_unknown_action(self) -> None:
        pc = ProjectXComputer()
        step = {"action": "destroy_system", "params": {}}
        result = pc.safe_execute(step)
        assert result["success"] is False


class TestComputerConcurrent:
    def test_concurrent_calls_independent(self) -> None:
        import threading
        pc = ProjectXComputer()
        results = []

        def run_cmd(cmd):
            r = pc.run_shell(cmd)
            results.append(r)

        t1 = threading.Thread(target=run_cmd, args=("echo a",))
        t2 = threading.Thread(target=run_cmd, args=("echo b",))
        t1.start(); t2.start()
        t1.join(); t2.join()
        assert len(results) == 2
        assert all(r["success"] for r in results)


class TestTaskAbortError:
    def test_task_abort_error_is_exception(self) -> None:
        assert issubclass(TaskAbortError, Exception)
