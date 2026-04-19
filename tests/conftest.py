"""
Shared fixtures for AgentRegistry test isolation.
"""

import pytest
import tempfile
import os
from simp.server.broker import SimpBroker, BrokerConfig
from simp.server.agent_registry import AgentRegistryConfig


@pytest.fixture
def isolated_broker():
    """
    Create a broker with isolated AgentRegistry using temporary file.
    
    This fixture ensures tests don't interfere with each other due to
    AgentRegistry disk persistence.
    """
    # Create temporary file for agent registry
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_file = f.name
    
    # Create broker config with custom AgentRegistry config
    registry_config = AgentRegistryConfig(path=temp_file)
    config = BrokerConfig(
        max_agents=100, 
        health_check_interval=60,
        agent_registry_config=registry_config
    )
    
    broker = SimpBroker(config)
    
    # Store temp file path for cleanup
    broker._test_temp_file = temp_file
    
    yield broker
    
    # Cleanup
    try:
        os.unlink(temp_file)
    except:
        pass


@pytest.fixture
def broker(isolated_broker):
    """
    Alias for isolated_broker for backward compatibility.
    
    Tests can use `broker` fixture and get isolated instance.
    """
    return isolated_broker


@pytest.fixture
def isolated_orchestration_manager():
    """
    Create an OrchestrationManager with isolated persistence using temporary files.
    """
    import tempfile
    import os
    from pathlib import Path
    from simp.orchestration.orchestration_manager import (
        OrchestrationManager,
        OrchestrationManagerConfig
    )
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f1:
        log_file = f1.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f2:
        plans_file = f2.name
    
    # Create config with temporary files
    config = OrchestrationManagerConfig(
        log_path=Path(log_file),
        plans_path=Path(plans_file)
    )
    
    # Create manager
    manager = OrchestrationManager(config=config)
    
    # Store temp file paths for cleanup
    manager._test_temp_files = [log_file, plans_file]
    
    yield manager
    
    # Cleanup
    for temp_file in manager._test_temp_files:
        try:
            os.unlink(temp_file)
        except:
            pass


@pytest.fixture
def orchestration_manager(isolated_orchestration_manager):
    """
    Alias for isolated_orchestration_manager for backward compatibility.
    """
    return isolated_orchestration_manager