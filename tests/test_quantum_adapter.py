"""
Tests for Quantum Computing Adapter

These tests verify the quantum computing adapter functionality
for the SIMP ecosystem.
"""

import pytest
import sys
import os
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simp.organs.quantum import (
    QuantumBackend,
    QuantumAlgorithm,
    PortfolioOptimizationParams,
    QuantumMLParams,
    QuantumResult,
    get_quantum_adapter,
)


class TestQuantumAdapter:
    """Test quantum adapter functionality."""
    
    def test_adapter_creation(self):
        """Test creating quantum adapters for different backends."""
        # Test local simulator adapter
        adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
        assert adapter.backend == QuantumBackend.LOCAL_SIMULATOR
        assert adapter.config == {}
        
        # Test with custom config
        config = {"test_param": "value"}
        adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR, config)
        assert adapter.config == config
    
    def test_adapter_connection(self):
        """Test adapter connection/disconnection."""
        adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
        
        # Should start disconnected
        assert adapter._connected == False
        
        # Should connect successfully
        assert adapter.connect() == True
        assert adapter._connected == True
        
        # Should disconnect successfully
        assert adapter.disconnect() == True
        assert adapter._connected == False
    
    def test_execute_algorithm(self):
        """Test executing quantum algorithms."""
        adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
        adapter.connect()
        
        # Test QAOA algorithm
        result = adapter.execute_algorithm(
            algorithm=QuantumAlgorithm.QAOA,
            parameters={"test": "data"},
            shots=512
        )
        
        assert isinstance(result, QuantumResult)
        assert result.success == True
        assert result.algorithm == QuantumAlgorithm.QAOA
        assert result.backend == QuantumBackend.LOCAL_SIMULATOR
        assert result.execution_time_ms > 0
        assert "result_data" in result.__dict__
        
        adapter.disconnect()
    
    def test_portfolio_optimization(self):
        """Test quantum portfolio optimization."""
        adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
        adapter.connect()
        
        # Create test portfolio
        assets = [
            {"symbol": "TEST1", "expected_return": 0.1, "volatility": 0.15},
            {"symbol": "TEST2", "expected_return": 0.15, "volatility": 0.2},
        ]
        
        params = PortfolioOptimizationParams(
            assets=assets,
            budget=50000.0,
            risk_tolerance=0.5,
            constraints={},
            max_assets=2
        )
        
        result = adapter.optimize_portfolio(params)
        
        assert isinstance(result, QuantumResult)
        assert result.success == True
        assert result.algorithm == QuantumAlgorithm.QAOA
        
        # Check result structure
        result_data = result.result_data
        assert "optimal_solution" in result_data
        assert "optimal_value" in result_data
        
        adapter.disconnect()
    
    def test_quantum_ml_inference(self):
        """Test quantum machine learning inference."""
        adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
        adapter.connect()
        
        params = QuantumMLParams(
            model_type="qnn",
            training_data=[1, 2, 3],  # Simplified for test
            test_data=[4, 5, 6],      # Simplified for test
            hyperparameters={"learning_rate": 0.01},
            quantum_circuit_depth=2
        )
        
        result = adapter.quantum_ml_inference(params)
        
        assert isinstance(result, QuantumResult)
        assert result.success == True
        assert result.algorithm == QuantumAlgorithm.QNN
        
        adapter.disconnect()
    
    def test_job_management(self):
        """Test quantum job management."""
        adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
        adapter.connect()
        
        # Execute a job
        result = adapter.execute_algorithm(
            algorithm=QuantumAlgorithm.QAOA,
            parameters={},
            shots=256
        )
        
        # Get job metadata
        metadata = result.metadata
        assert "job_id" in metadata
        
        job_id = metadata["job_id"]
        
        # Get job status
        job = adapter.get_job_status(job_id)
        assert job.job_id == job_id
        assert job.status == "completed"
        
        # Test health check
        health = adapter.health_check()
        assert "backend" in health
        assert "connected" in health
        assert "jobs_count" in health
        
        # Clear completed jobs
        cleared = adapter.clear_completed_jobs()
        assert cleared >= 1
        
        adapter.disconnect()
    
    def test_available_algorithms(self):
        """Test getting available algorithms."""
        adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
        
        algorithms = adapter.get_available_algorithms()
        assert isinstance(algorithms, list)
        assert len(algorithms) > 0
        assert QuantumAlgorithm.QAOA in algorithms
    
    def test_error_handling(self):
        """Test error handling in quantum adapter."""
        adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
        
        # Test getting non-existent job
        with pytest.raises(ValueError):
            adapter.get_job_status("non_existent_job_id")
        
        # Test cancel non-existent job
        assert adapter.cancel_job("non_existent_job_id") == False


class TestPortfolioOptimizationParams:
    """Test portfolio optimization parameters."""
    
    def test_params_creation(self):
        """Test creating portfolio optimization parameters."""
        assets = [
            {"symbol": "AAPL", "expected_return": 0.12},
            {"symbol": "GOOGL", "expected_return": 0.15},
        ]
        
        params = PortfolioOptimizationParams(
            assets=assets,
            budget=100000.0,
            risk_tolerance=0.3,
            constraints={"max_sector_weight": 0.5},
            max_assets=2
        )
        
        assert params.assets == assets
        assert params.budget == 100000.0
        assert params.risk_tolerance == 0.3
        assert params.constraints == {"max_sector_weight": 0.5}
        assert params.max_assets == 2


class TestQuantumMLParams:
    """Test quantum ML parameters."""
    
    def test_params_creation(self):
        """Test creating quantum ML parameters."""
        params = QuantumMLParams(
            model_type="qnn",
            training_data=[1, 2, 3],
            test_data=[4, 5, 6],
            hyperparameters={"learning_rate": 0.01, "epochs": 10},
            quantum_circuit_depth=3
        )
        
        assert params.model_type == "qnn"
        assert params.training_data == [1, 2, 3]
        assert params.test_data == [4, 5, 6]
        assert params.hyperparameters == {"learning_rate": 0.01, "epochs": 10}
        assert params.quantum_circuit_depth == 3


def test_get_quantum_adapter_factory():
    """Test quantum adapter factory function."""
    # Test valid backends
    adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
    assert adapter is not None
    
    adapter = get_quantum_adapter(QuantumBackend.PENNYLANE)
    assert adapter is not None
    
    # Test with config
    config = {"api_token": "test_token"}
    adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR, config)
    assert adapter.config == config


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])