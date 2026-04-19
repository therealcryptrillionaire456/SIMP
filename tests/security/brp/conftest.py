"""
Shared fixtures for BRP (Bill Russell Protocol) tests.
"""

import pytest
import sys
from pathlib import Path

# Ensure the project root is on the path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_security_event():
    """A basic security event for testing."""
    return {
        "source_ip": "192.168.1.100",
        "dest_ip": "10.0.0.1",
        "event_type": "network_connection",
        "timestamp": "2026-04-10T12:00:00Z",
        "protocol": "tcp",
        "port": 443,
        "payload_size": 1024,
        "description": "Outbound HTTPS connection",
    }


@pytest.fixture
def sample_threat_event():
    """A suspicious event that should trigger threat detection."""
    return {
        "source_ip": "10.99.99.99",
        "dest_ip": "10.0.0.1",
        "event_type": "port_scan",
        "timestamp": "2026-04-10T12:05:00Z",
        "protocol": "tcp",
        "port": 22,
        "payload_size": 0,
        "description": "Sequential port scan detected from internal host",
    }


@pytest.fixture
def sample_log_entry():
    """A raw log entry for sigma rule testing."""
    return {
        "timestamp": "2026-04-10T12:10:00Z",
        "source": "sysmon",
        "event_id": 1,
        "process_name": "powershell.exe",
        "command_line": "powershell -enc SQBFAFgA",
        "parent_process": "cmd.exe",
        "user": "SYSTEM",
    }


@pytest.fixture
def brp_config():
    """Minimal BRP configuration for testing."""
    return {
        "threat_confidence_threshold": 0.7,
        "max_reasoning_depth": 5,
        "memory_retention_days": 90,
        "correlation_window_days": 7,
        "telegram_enabled": False,
    }
