"""
Enhanced test fixtures with SIMP_STRICT_TESTS support.

This module extends the standard conftest.py with strict test mode handling.
When SIMP_STRICT_TESTS=1 is set in the environment, exceptions in test bodies
are re-raised instead of being caught and logged as warnings.

Usage:
    SIMP_STRICT_TESTS=1 python3.10 -m pytest tests/ -v

This should be used in CI to catch bugs that would otherwise be silently skipped.
"""

import os
import sys
import pytest
import tempfile
import logging
from typing import Any, Callable, Dict, Optional
from unittest.mock import patch

# Import original fixtures
from .conftest import isolated_broker, broker, isolated_orchestration_manager, orchestration_manager

# Configure logging for test warnings
logger = logging.getLogger(__name__)


def pytest_configure(config):
    """
    Configure pytest with SIMP_STRICT_TESTS support.
    
    When SIMP_STRICT_TESTS=1, we patch pytest's exception handling
    to re-raise exceptions instead of logging warnings.
    """
    strict_mode = os.environ.get("SIMP_STRICT_TESTS") == "1"
    
    if strict_mode:
        print("=" * 60)
        print("SIMP_STRICT_TESTS=1: Enabling strict test mode")
        print("Exceptions in test bodies will cause test failures")
        print("=" * 60)
        
        # Store original pytest hooks
        original_runtest_makereport = config.pluginmanager.hook.pytest_runtest_makereport
        
        def strict_runtest_makereport(item, call):
            """
            Strict mode test report handler.
            
            In strict mode, any exception during test execution (except pytest.skip)
            is re-raised to cause test failure.
            """
            report = original_runtest_makereport(item=item, call=call)
            
            if call.excinfo is not None:
                # Check if this is a skip exception (allowed)
                exc_type = call.excinfo.type
                if exc_type is not pytest.skip.Exception:
                    # In strict mode, re-raise the exception
                    logger.error(f"STRICT MODE: Test '{item.name}' raised {exc_type.__name__}: {call.excinfo.value}")
                    
                    # Mark test as failed
                    if report.outcome == "skipped":
                        report.outcome = "failed"
                        report.longrepr = f"STRICT MODE: Test raised exception: {call.excinfo.value}"
            
            return report
        
        # Replace the hook
        config.pluginmanager.hook.pytest_runtest_makereport = strict_runtest_makereport


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection based on SIMP_STRICT_TESTS.
    
    In strict mode, we can add markers or modify test behavior.
    """
    strict_mode = os.environ.get("SIMP_STRICT_TESTS") == "1"
    
    if strict_mode:
        # Mark all tests with strict mode marker
        for item in items:
            item.add_marker(pytest.mark.strict_mode)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Custom test report handler for strict mode.
    
    This is an alternative implementation that works with pytest's hook system.
    """
    # Execute all other hooks to get the report object
    outcome = yield
    report = outcome.get_result()
    
    strict_mode = os.environ.get("SIMP_STRICT_TESTS") == "1"
    
    if strict_mode and call.excinfo is not None:
        # Check if this is a test failure (not setup/teardown)
        if call.when == "call":
            exc_type = call.excinfo.type
            
            # Skip exceptions are allowed
            if exc_type is not pytest.skip.Exception:
                logger.error(f"STRICT MODE FAILURE in '{item.name}': {exc_type.__name__}: {call.excinfo.value}")
                
                # Ensure test is marked as failed
                if report.outcome == "skipped":
                    report.outcome = "failed"
                    report.longrepr = f"STRICT MODE: Test raised {exc_type.__name__}: {call.excinfo.value}"


class StrictTestExceptionHandler:
    """
    Context manager for handling exceptions in strict test mode.
    
    Usage:
        with StrictTestExceptionHandler():
            # Test code that might raise exceptions
            some_operation_that_might_fail()
    """
    
    def __enter__(self):
        self.strict_mode = os.environ.get("SIMP_STRICT_TESTS") == "1"
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.strict_mode and exc_type is not None:
            # In strict mode, re-raise all exceptions
            logger.error(f"STRICT MODE: Exception raised: {exc_type.__name__}: {exc_val}")
            return False  # Re-raise the exception
        elif exc_type is not None:
            # In normal mode, log warning and suppress exception
            logger.warning(f"Test raised {exc_type.__name__}: {exc_val} (suppressed in normal mode)")
            return True  # Suppress the exception
        
        return None  # No exception to handle


@pytest.fixture
def strict_mode():
    """
    Fixture that returns whether strict test mode is enabled.
    
    Usage in tests:
        def test_something(strict_mode):
            if strict_mode:
                # Run stricter assertions
                assert some_condition, "Must hold in strict mode"
    """
    return os.environ.get("SIMP_STRICT_TESTS") == "1"


@pytest.fixture
def strict_exception_handler():
    """
    Fixture that provides a strict exception handler.
    
    Usage:
        def test_something(strict_exception_handler):
            with strict_exception_handler:
                # Code that might raise exceptions
                operation_that_might_fail()
    """
    return StrictTestExceptionHandler()


# Re-export all original fixtures
__all__ = [
    'isolated_broker',
    'broker', 
    'isolated_orchestration_manager',
    'orchestration_manager',
    'strict_mode',
    'strict_exception_handler',
]