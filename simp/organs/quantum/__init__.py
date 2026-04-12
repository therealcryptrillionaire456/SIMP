"""
Quantum Computing Integration for SIMP Ecosystem

This module provides quantum computing capabilities for SIMP agents,
allowing them to leverage quantum advantage for optimization, machine learning,
and complex calculations.

Integration Contract Version: 1.0.0
Compatible with: SIMP A2A Core v0.7.0
Quantum SDK: Qiskit 2.3.1, PennyLane 0.34.0
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from enum import Enum
import logging


class QuantumBackend(str, Enum):
    """Supported quantum computing backends."""
    IBM_QUANTUM = "ibm_quantum"
    IBM_SIMULATOR = "ibm_simulator"
    PENNYLANE = "pennylane"
    D_WAVE = "d_wave"
    AWS_BRAKET = "aws_braket"
    LOCAL_SIMULATOR = "local_simulator"


class QuantumAlgorithm(str, Enum):
    """Supported quantum algorithms."""
    QAOA = "qaoa"  # Quantum Approximate Optimization Algorithm
    VQE = "vqe"   # Variational Quantum Eigensolver
    QNN = "qnn"   # Quantum Neural Network
    GROVER = "grover"  # Grover's Search Algorithm
    QMC = "qmc"   # Quantum Monte Carlo
    QSVM = "qsvm"  # Quantum Support Vector Machine


@dataclass
class QuantumJob:
    """Represents a quantum computing job."""
    job_id: str
    algorithm: QuantumAlgorithm
    backend: QuantumBackend
    parameters: Dict[str, Any]
    created_at: str  # ISO 8601 timestamp
    status: str  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None


@dataclass
class PortfolioOptimizationParams:
    """Parameters for quantum portfolio optimization."""
    assets: List[Dict[str, Any]]  # List of assets with expected returns and covariance
    budget: float
    risk_tolerance: float  # 0.0 to 1.0
    constraints: Dict[str, Any]  # Additional constraints
    max_assets: Optional[int] = None  # Maximum number of assets to select


@dataclass
class QuantumMLParams:
    """Parameters for quantum machine learning."""
    model_type: str  # qnn, qsvm, etc.
    training_data: Any
    test_data: Any
    hyperparameters: Dict[str, Any]
    quantum_circuit_depth: int = 3


@dataclass
class QuantumResult:
    """Standardized result from quantum computation."""
    success: bool
    algorithm: QuantumAlgorithm
    backend: QuantumBackend
    execution_time_ms: int
    result_data: Dict[str, Any]
    metadata: Dict[str, Any]
    quantum_advantage_score: Optional[float] = None  # 0-1 score of quantum advantage


# Import adapter classes and factory function
from .quantum_adapter import (
    QuantumAdapter,
    IBMQuantumAdapter,
    PennyLaneAdapter,
    LocalSimulatorAdapter,
    get_quantum_adapter,
)

# Export main classes
__all__ = [
    'QuantumBackend',
    'QuantumAlgorithm',
    'QuantumJob',
    'PortfolioOptimizationParams',
    'QuantumMLParams',
    'QuantumResult',
    'QuantumAdapter',
    'IBMQuantumAdapter',
    'PennyLaneAdapter',
    'LocalSimulatorAdapter',
    'get_quantum_adapter',
]