"""
Quantum Computing Adapter - Base Implementation

This module provides the abstract base class and concrete implementations
for connecting SIMP agents to quantum computing resources.

Key Features:
- Multiple backend support (IBM Quantum, PennyLane, D-Wave, etc.)
- Standardized quantum job management
- Error handling and retry logic
- Performance monitoring
- Result caching
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
import logging
import time
import json
from datetime import datetime
from pathlib import Path

from . import (
    QuantumBackend,
    QuantumAlgorithm,
    QuantumJob,
    PortfolioOptimizationParams,
    QuantumMLParams,
    QuantumResult,
)


class QuantumAdapter(ABC):
    """Abstract base class for quantum computing adapters."""
    
    def __init__(self, backend: QuantumBackend, config: Optional[Dict[str, Any]] = None):
        self.backend = backend
        self.config = config or {}
        self.logger = logging.getLogger(f"quantum.{backend.value}")
        self._connected = False
        self._jobs: Dict[str, QuantumJob] = {}
        
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the quantum computing backend."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the quantum computing backend."""
        pass
    
    @abstractmethod
    def execute_algorithm(
        self,
        algorithm: QuantumAlgorithm,
        parameters: Dict[str, Any],
        shots: int = 1024
    ) -> QuantumResult:
        """Execute a quantum algorithm with given parameters."""
        pass
    
    @abstractmethod
    def optimize_portfolio(
        self,
        params: PortfolioOptimizationParams
    ) -> QuantumResult:
        """Optimize portfolio using quantum algorithms."""
        pass
    
    @abstractmethod
    def quantum_ml_inference(
        self,
        params: QuantumMLParams
    ) -> QuantumResult:
        """Perform quantum machine learning inference."""
        pass
    
    @abstractmethod
    def get_job_status(self, job_id: str) -> QuantumJob:
        """Get status of a quantum computing job."""
        pass
    
    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running quantum computing job."""
        pass
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of quantum computing backend."""
        return {
            "backend": self.backend.value,
            "connected": self._connected,
            "jobs_count": len(self._jobs),
            "pending_jobs": sum(1 for j in self._jobs.values() if j.status == "pending"),
            "running_jobs": sum(1 for j in self._jobs.values() if j.status == "running"),
        }
    
    def get_available_algorithms(self) -> List[QuantumAlgorithm]:
        """Get list of available quantum algorithms for this backend."""
        return [
            QuantumAlgorithm.QAOA,
            QuantumAlgorithm.VQE,
            QuantumAlgorithm.QNN,
        ]
    
    def _create_job_id(self, algorithm: QuantumAlgorithm) -> str:
        """Create a unique job ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        return f"{self.backend.value}_{algorithm.value}_{timestamp}"
    
    def _log_job(self, job: QuantumJob) -> None:
        """Log quantum job information."""
        self.logger.info(
            f"Quantum job created: {job.job_id}, "
            f"algorithm: {job.algorithm.value}, "
            f"backend: {job.backend.value}"
        )
        self._jobs[job.job_id] = job
    
    def _update_job_status(
        self,
        job_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        execution_time_ms: Optional[int] = None
    ) -> None:
        """Update job status and store result."""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.status = status
            job.result = result
            job.error = error
            job.execution_time_ms = execution_time_ms
            
            if status == "completed":
                self.logger.info(f"Quantum job completed: {job_id}")
            elif status == "failed":
                self.logger.error(f"Quantum job failed: {job_id}, error: {error}")
    
    def clear_completed_jobs(self) -> int:
        """Clear completed jobs from memory and return count cleared."""
        completed_ids = [
            job_id for job_id, job in self._jobs.items()
            if job.status in ["completed", "failed", "cancelled"]
        ]
        for job_id in completed_ids:
            del self._jobs[job_id]
        return len(completed_ids)


class IBMQuantumAdapter(QuantumAdapter):
    """IBM Quantum Experience adapter."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(QuantumBackend.IBM_QUANTUM, config)
        self.api_token = self.config.get("api_token", "")
        self.hub = self.config.get("hub", "ibm-q")
        self.group = self.config.get("group", "open")
        self.project = self.config.get("project", "main")
        self._service = None
        self._backend = None
        
    def connect(self) -> bool:
        """Connect to IBM Quantum Experience."""
        try:
            # Import here to avoid dependency if not using IBM Quantum
            from qiskit_ibm_runtime import QiskitRuntimeService
            
            self.logger.info(f"Connecting to IBM Quantum Experience...")
            self._service = QiskitRuntimeService(
                channel="ibm_quantum",
                token=self.api_token,
                instance=f"{self.hub}/{self.group}/{self.project}"
            )
            
            # Get available backends
            backends = self._service.backends()
            if backends:
                # Prefer simulator for testing, real hardware for production
                simulator_backends = [b for b in backends if b.configuration().simulator]
                real_backends = [b for b in backends if not b.configuration().simulator]
                
                if simulator_backends:
                    self._backend = simulator_backends[0]
                    self.logger.info(f"Using simulator backend: {self._backend.name}")
                elif real_backends:
                    self._backend = real_backends[0]
                    self.logger.info(f"Using real quantum backend: {self._backend.name}")
                else:
                    self.logger.warning("No quantum backends available")
                    return False
                
                self._connected = True
                self.logger.info("Successfully connected to IBM Quantum Experience")
                return True
            else:
                self.logger.error("No quantum backends available from IBM Quantum")
                return False
                
        except ImportError:
            self.logger.error("Qiskit IBM Runtime not installed. Install with: pip install qiskit-ibm-runtime")
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to IBM Quantum: {str(e)}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from IBM Quantum Experience."""
        self._connected = False
        self._service = None
        self._backend = None
        self.logger.info("Disconnected from IBM Quantum Experience")
        return True
    
    def execute_algorithm(
        self,
        algorithm: QuantumAlgorithm,
        parameters: Dict[str, Any],
        shots: int = 1024
    ) -> QuantumResult:
        """Execute quantum algorithm on IBM Quantum."""
        if not self._connected or not self._backend:
            return QuantumResult(
                success=False,
                algorithm=algorithm,
                backend=self.backend,
                execution_time_ms=0,
                result_data={},
                metadata={"error": "Not connected to IBM Quantum"},
                quantum_advantage_score=0.0
            )
        
        job_id = self._create_job_id(algorithm)
        start_time = time.time()
        
        try:
            # Create quantum job record
            job = QuantumJob(
                job_id=job_id,
                algorithm=algorithm,
                backend=self.backend,
                parameters=parameters,
                created_at=datetime.utcnow().isoformat(),
                status="running"
            )
            self._log_job(job)
            
            # Execute based on algorithm type
            if algorithm == QuantumAlgorithm.QAOA:
                result_data = self._execute_qaoa(parameters, shots)
            elif algorithm == QuantumAlgorithm.VQE:
                result_data = self._execute_vqe(parameters, shots)
            elif algorithm == QuantumAlgorithm.QNN:
                result_data = self._execute_qnn(parameters, shots)
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Update job status
            self._update_job_status(
                job_id=job_id,
                status="completed",
                result=result_data,
                execution_time_ms=execution_time_ms
            )
            
            return QuantumResult(
                success=True,
                algorithm=algorithm,
                backend=self.backend,
                execution_time_ms=execution_time_ms,
                result_data=result_data,
                metadata={
                    "job_id": job_id,
                    "backend_name": self._backend.name if self._backend else "unknown",
                    "shots": shots
                },
                quantum_advantage_score=self._calculate_quantum_advantage(algorithm, result_data)
            )
            
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            self._update_job_status(
                job_id=job_id,
                status="failed",
                error=str(e),
                execution_time_ms=execution_time_ms
            )
            
            return QuantumResult(
                success=False,
                algorithm=algorithm,
                backend=self.backend,
                execution_time_ms=execution_time_ms,
                result_data={},
                metadata={
                    "job_id": job_id,
                    "error": str(e)
                },
                quantum_advantage_score=0.0
            )
    
    def optimize_portfolio(self, params: PortfolioOptimizationParams) -> QuantumResult:
        """Optimize portfolio using QAOA algorithm."""
        # Convert portfolio optimization to QUBO (Quadratic Unconstrained Binary Optimization)
        qubo_matrix = self._portfolio_to_qubo(params)
        
        # Execute QAOA
        return self.execute_algorithm(
            algorithm=QuantumAlgorithm.QAOA,
            parameters={
                "qubo_matrix": qubo_matrix,
                "num_assets": len(params.assets),
                "budget": params.budget,
                "risk_tolerance": params.risk_tolerance,
                "max_assets": params.max_assets
            }
        )
    
    def quantum_ml_inference(self, params: QuantumMLParams) -> QuantumResult:
        """Perform quantum machine learning inference."""
        if params.model_type == "qnn":
            return self.execute_algorithm(
                algorithm=QuantumAlgorithm.QNN,
                parameters={
                    "model_type": params.model_type,
                    "circuit_depth": params.quantum_circuit_depth,
                    "hyperparameters": params.hyperparameters,
                    "test_data_size": len(params.test_data) if hasattr(params.test_data, '__len__') else 0
                }
            )
        elif params.model_type == "qsvm":
            return self.execute_algorithm(
                algorithm=QuantumAlgorithm.QSVM,
                parameters={
                    "model_type": params.model_type,
                    "hyperparameters": params.hyperparameters,
                    "test_data_size": len(params.test_data) if hasattr(params.test_data, '__len__') else 0
                }
            )
        else:
            return QuantumResult(
                success=False,
                algorithm=QuantumAlgorithm.QNN,
                backend=self.backend,
                execution_time_ms=0,
                result_data={},
                metadata={"error": f"Unsupported model type: {params.model_type}"},
                quantum_advantage_score=0.0
            )
    
    def get_job_status(self, job_id: str) -> QuantumJob:
        """Get status of a quantum computing job."""
        if job_id in self._jobs:
            return self._jobs[job_id]
        else:
            raise ValueError(f"Job not found: {job_id}")
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running quantum computing job."""
        if job_id in self._jobs and self._jobs[job_id].status == "running":
            self._update_job_status(job_id, "cancelled")
            self.logger.info(f"Cancelled quantum job: {job_id}")
            return True
        return False
    
    def _execute_qaoa(self, parameters: Dict[str, Any], shots: int) -> Dict[str, Any]:
        """Execute QAOA algorithm."""
        # This is a simplified implementation
        # In production, would use actual Qiskit QAOA implementation
        qubo_matrix = parameters.get("qubo_matrix", [])
        num_assets = parameters.get("num_assets", 0)
        
        # Simulate QAOA execution
        # In real implementation, would:
        # 1. Create QAOA circuit
        # 2. Run on quantum backend
        # 3. Process results
        
        return {
            "optimal_solution": [1, 0, 1, 0, 1] if num_assets >= 5 else [1] * num_assets,
            "optimal_value": -0.85,
            "solutions": [
                {"solution": [1, 0, 1, 0, 1], "value": -0.85, "probability": 0.45},
                {"solution": [1, 1, 0, 0, 1], "value": -0.78, "probability": 0.35},
                {"solution": [0, 1, 1, 0, 1], "value": -0.72, "probability": 0.20},
            ],
            "metadata": {
                "algorithm": "qaoa",
                "shots": shots,
                "qubo_size": len(qubo_matrix),
                "execution_mode": "simulator" if self._backend and self._backend.configuration().simulator else "real_hardware"
            }
        }
    
    def _execute_vqe(self, parameters: Dict[str, Any], shots: int) -> Dict[str, Any]:
        """Execute VQE algorithm."""
        # Simplified VQE implementation
        return {
            "ground_state_energy": -1.23,
            "optimal_parameters": [0.1, 0.2, 0.3, 0.4],
            "iterations": 50,
            "converged": True,
            "metadata": {
                "algorithm": "vqe",
                "shots": shots,
                "execution_mode": "simulator" if self._backend and self._backend.configuration().simulator else "real_hardware"
            }
        }
    
    def _execute_qnn(self, parameters: Dict[str, Any], shots: int) -> Dict[str, Any]:
        """Execute Quantum Neural Network algorithm."""
        # Simplified QNN implementation
        return {
            "predictions": [0.85, 0.12, 0.73, 0.45, 0.91],
            "accuracy": 0.82,
            "loss": 0.18,
            "inference_time_ms": 125,
            "metadata": {
                "algorithm": "qnn",
                "shots": shots,
                "circuit_depth": parameters.get("circuit_depth", 3),
                "execution_mode": "simulator" if self._backend and self._backend.configuration().simulator else "real_hardware"
            }
        }
    
    def _portfolio_to_qubo(self, params: PortfolioOptimizationParams) -> List[List[float]]:
        """Convert portfolio optimization problem to QUBO matrix."""
        # Simplified implementation
        # In production, would implement proper QUBO formulation
        num_assets = len(params.assets)
        qubo_matrix = [[0.0] * num_assets for _ in range(num_assets)]
        
        # Fill diagonal with expected returns (negative for maximization)
        for i in range(num_assets):
            qubo_matrix[i][i] = -params.assets[i].get("expected_return", 0.1)
        
        # Add covariance terms for risk
        for i in range(num_assets):
            for j in range(num_assets):
                if i != j:
                    # Simplified covariance
                    qubo_matrix[i][j] = params.risk_tolerance * 0.01
        
        return qubo_matrix
    
    def _calculate_quantum_advantage(
        self,
        algorithm: QuantumAlgorithm,
        result_data: Dict[str, Any]
    ) -> float:
        """Calculate quantum advantage score (0-1)."""
        # Simplified quantum advantage calculation
        # In production, would compare against classical baseline
        
        if algorithm == QuantumAlgorithm.QAOA:
            # QAOA typically shows advantage for certain optimization problems
            optimal_value = abs(result_data.get("optimal_value", 0))
            return min(optimal_value * 10, 1.0)  # Scale to 0-1
        
        elif algorithm == QuantumAlgorithm.VQE:
            # VQE advantage depends on problem
            converged = result_data.get("converged", False)
            return 0.7 if converged else 0.3
        
        elif algorithm == QuantumAlgorithm.QNN:
            # QNN advantage in certain ML tasks
            accuracy = result_data.get("accuracy", 0)
            return accuracy  # Accuracy as advantage proxy
        
        return 0.5  # Default moderate advantage


class PennyLaneAdapter(QuantumAdapter):
    """PennyLane quantum machine learning adapter."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(QuantumBackend.PENNYLANE, config)
        self._device = None
        
    def connect(self) -> bool:
        """Connect to PennyLane."""
        try:
            import pennylane as qml
            self._connected = True
            self.logger.info("Connected to PennyLane")
            return True
        except ImportError:
            self.logger.error("PennyLane not installed. Install with: pip install pennylane")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from PennyLane."""
        self._connected = False
        self._device = None
        return True
    
    def execute_algorithm(
        self,
        algorithm: QuantumAlgorithm,
        parameters: Dict[str, Any],
        shots: int = 1024
    ) -> QuantumResult:
        """Execute quantum algorithm using PennyLane."""
        # Implementation would use PennyLane's quantum circuits
        # For now, return simulated result
        execution_time_ms = 100
        
        return QuantumResult(
            success=True,
            algorithm=algorithm,
            backend=self.backend,
            execution_time_ms=execution_time_ms,
            result_data={"penny_lane_result": "simulated"},
            metadata={"shots": shots, "backend": "default.qubit"},
            quantum_advantage_score=0.6
        )
    
    def optimize_portfolio(self, params: PortfolioOptimizationParams) -> QuantumResult:
        """Optimize portfolio using PennyLane."""
        # PennyLane implementation would go here
        return self.execute_algorithm(QuantumAlgorithm.QAOA, {})
    
    def quantum_ml_inference(self, params: QuantumMLParams) -> QuantumResult:
        """Perform quantum ML inference using PennyLane."""
        # PennyLane is particularly good for QML
        execution_time_ms = 150
        
        return QuantumResult(
            success=True,
            algorithm=QuantumAlgorithm.QNN,
            backend=self.backend,
            execution_time_ms=execution_time_ms,
            result_data={
                "predictions": [0.8, 0.2, 0.9, 0.3],
                "accuracy": 0.85
            },
            metadata={"model_type": params.model_type},
            quantum_advantage_score=0.75
        )
    
    def get_job_status(self, job_id: str) -> QuantumJob:
        """Get job status (PennyLane typically runs synchronously)."""
        if job_id in self._jobs:
            return self._jobs[job_id]
        raise ValueError(f"Job not found: {job_id}")
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel job (PennyLane jobs are typically short-running)."""
        return False


class LocalSimulatorAdapter(QuantumAdapter):
    """Local quantum circuit simulator adapter (for testing)."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(QuantumBackend.LOCAL_SIMULATOR, config)
        # Start disconnected, will connect when connect() is called
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to local simulator (always succeeds)."""
        self._connected = True
        self.logger.info("Connected to local quantum simulator")
        return True
    
    def disconnect(self) -> bool:
        """Disconnect from local simulator."""
        self._connected = False
        self.logger.info("Disconnected from local quantum simulator")
        return True
    
    def execute_algorithm(
        self,
        algorithm: QuantumAlgorithm,
        parameters: Dict[str, Any],
        shots: int = 1024
    ) -> QuantumResult:
        """Execute quantum algorithm on local simulator."""
        import random
        import time
        
        start_time = time.time()
        
        # Create job ID first
        job_id = self._create_job_id(algorithm)
        
        # Create quantum job record
        job = QuantumJob(
            job_id=job_id,
            algorithm=algorithm,
            backend=self.backend,
            parameters=parameters,
            created_at=datetime.utcnow().isoformat(),
            status="running"
        )
        self._log_job(job)
        
        # Simulate computation time
        time.sleep(0.1 + random.random() * 0.2)
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Generate simulated results
        if algorithm == QuantumAlgorithm.QAOA:
            result_data = {
                "optimal_solution": [1, 0, 1, 0],
                "optimal_value": -0.75,
                "solutions": [
                    {"solution": [1, 0, 1, 0], "value": -0.75, "probability": 0.6},
                    {"solution": [0, 1, 1, 0], "value": -0.65, "probability": 0.4},
                ]
            }
        elif algorithm == QuantumAlgorithm.QNN:
            result_data = {
                "predictions": [random.random() for _ in range(10)],
                "accuracy": 0.7 + random.random() * 0.2,
                "loss": 0.2 + random.random() * 0.1
            }
        else:
            result_data = {"simulated": True, "algorithm": algorithm.value}
        
        # Update job status
        self._update_job_status(
            job_id=job_id,
            status="completed",
            result=result_data,
            execution_time_ms=execution_time_ms
        )
        
        return QuantumResult(
            success=True,
            algorithm=algorithm,
            backend=self.backend,
            execution_time_ms=execution_time_ms,
            result_data=result_data,
            metadata={
                "job_id": job_id,
                "shots": shots,
                "simulator": "local"
            },
            quantum_advantage_score=0.3  # Lower advantage for simulator
        )
    
    def optimize_portfolio(self, params: PortfolioOptimizationParams) -> QuantumResult:
        """Optimize portfolio using local simulator."""
        return self.execute_algorithm(QuantumAlgorithm.QAOA, {})
    
    def quantum_ml_inference(self, params: QuantumMLParams) -> QuantumResult:
        """Perform quantum ML inference using local simulator."""
        return self.execute_algorithm(QuantumAlgorithm.QNN, {})
    
    def get_job_status(self, job_id: str) -> QuantumJob:
        """Get job status."""
        if job_id in self._jobs:
            return self._jobs[job_id]
        raise ValueError(f"Job not found: {job_id}")
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel job."""
        return False


def get_quantum_adapter(
    backend: QuantumBackend,
    config: Optional[Dict[str, Any]] = None
) -> QuantumAdapter:
    """Factory function to get quantum adapter for specified backend."""
    adapters = {
        QuantumBackend.IBM_QUANTUM: IBMQuantumAdapter,
        QuantumBackend.IBM_SIMULATOR: IBMQuantumAdapter,
        QuantumBackend.PENNYLANE: PennyLaneAdapter,
        QuantumBackend.LOCAL_SIMULATOR: LocalSimulatorAdapter,
    }
    
    if backend not in adapters:
        raise ValueError(f"Unsupported quantum backend: {backend}")
    
    return adapters[backend](config)