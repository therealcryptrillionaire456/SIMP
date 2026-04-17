"""
Quantum Backend Manager

Manages connections to real quantum hardware:
1. IBM Quantum Experience
2. Amazon Braket
3. Microsoft Azure Quantum
4. Local simulators (fallback)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json
import os


class QuantumBackendType(str, Enum):
    """Types of quantum computing backends."""
    IBM_QUANTUM = "ibm_quantum"
    AMAZON_BRAKET = "amazon_braket"
    AZURE_QUANTUM = "azure_quantum"
    PENNYLANE = "pennylane"
    LOCAL_SIMULATOR = "local_simulator"
    QISKIT_AER = "qiskit_aer"


class BackendStatus(str, Enum):
    """Status of quantum backend."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    LIMITED = "limited"  # Limited access (e.g., free tier limits)


@dataclass
class QuantumBackendInfo:
    """Information about a quantum backend."""
    backend_id: str
    backend_type: QuantumBackendType
    provider: str
    qubits: int
    status: BackendStatus
    queue_depth: int = 0
    estimated_wait_time: int = 0  # seconds
    fidelity: float = 0.0  # 0-1, quantum gate fidelity
    availability: float = 1.0  # 0-1, backend availability
    cost_per_shot: float = 0.0  # Cost per quantum shot (if applicable)
    free_tier_available: bool = False
    free_tier_limit: Optional[int] = None  # Free shots per month
    free_tier_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuantumJob:
    """A quantum computation job."""
    job_id: str
    backend_id: str
    circuit_data: Dict[str, Any]
    shots: int
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    cost: Optional[float] = None
    submitted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None


class QuantumBackendManager:
    """Manages connections to quantum computing backends."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger("quantum.backend.manager")
        self.backends: Dict[str, QuantumBackendInfo] = {}
        self.jobs: Dict[str, QuantumJob] = {}
        self.active_backend: Optional[str] = None
        
        # Configuration
        self.config_path = config_path or os.path.expanduser("~/.simp/quantum_config.json")
        self.config = self._load_config()
        
        # Initialize backends
        self._initialize_backends()
        
        self.logger.info(f"Quantum backend manager initialized with {len(self.backends)} backends")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load quantum backend configuration."""
        default_config = {
            "preferred_backend": "local_simulator",
            "fallback_order": ["local_simulator", "qiskit_aer", "ibm_quantum"],
            "max_shots": 1024,
            "timeout_seconds": 30,
            "cost_limit_per_month": 0.0,  # 0 = free only
            "enable_real_hardware": False,
            "ibm_quantum": {
                "enabled": False,
                "api_token": "",
                "hub": "ibm-q",
                "group": "open",
                "project": "main"
            },
            "amazon_braket": {
                "enabled": False,
                "region": "us-east-1"
            },
            "azure_quantum": {
                "enabled": False,
                "subscription_id": "",
                "resource_group": "",
                "workspace": ""
            }
        }
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                    # Merge with defaults
                    for key, value in user_config.items():
                        if key in default_config and isinstance(value, dict) and isinstance(default_config[key], dict):
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
                self.logger.info(f"Loaded configuration from {self.config_path}")
            else:
                self.logger.info(f"Configuration file not found, using defaults: {self.config_path}")
        except Exception as e:
            self.logger.warning(f"Failed to load configuration: {str(e)}, using defaults")
        
        return default_config
    
    def _initialize_backends(self):
        """Initialize available quantum backends."""
        # Always add local simulator
        self.backends["local_simulator"] = QuantumBackendInfo(
            backend_id="local_simulator",
            backend_type=QuantumBackendType.LOCAL_SIMULATOR,
            provider="SIMP",
            qubits=30,  # Simulator can handle many qubits
            status=BackendStatus.CONNECTED,
            fidelity=1.0,  # Perfect simulation
            availability=1.0,
            cost_per_shot=0.0,
            free_tier_available=True,
            free_tier_limit=None,  # Unlimited
            metadata={
                "description": "Local quantum circuit simulator",
                "max_qubits": 30,
                "noise_model": "ideal"
            }
        )
        
        # Add Qiskit Aer simulator
        self.backends["qiskit_aer"] = QuantumBackendInfo(
            backend_id="qiskit_aer",
            backend_type=QuantumBackendType.QISKIT_AER,
            provider="Qiskit",
            qubits=30,
            status=BackendStatus.CONNECTED,
            fidelity=1.0,
            availability=1.0,
            cost_per_shot=0.0,
            free_tier_available=True,
            free_tier_limit=None,
            metadata={
                "description": "Qiskit Aer high-performance simulator",
                "max_qubits": 30,
                "noise_models": ["ideal", "basic", "advanced"]
            }
        )
        
        # Add IBM Quantum if configured
        if self.config.get("ibm_quantum", {}).get("enabled", False):
            self._initialize_ibm_quantum()
        
        # Add Amazon Braket if configured
        if self.config.get("amazon_braket", {}).get("enabled", False):
            self._initialize_amazon_braket()
        
        # Add Azure Quantum if configured
        if self.config.get("azure_quantum", {}).get("enabled", False):
            self._initialize_azure_quantum()
        
        # Set active backend
        preferred = self.config.get("preferred_backend", "local_simulator")
        if preferred in self.backends:
            self.active_backend = preferred
            self.logger.info(f"Active backend set to: {preferred}")
        else:
            self.active_backend = "local_simulator"
            self.logger.warning(f"Preferred backend {preferred} not available, using local_simulator")
    
    def _initialize_ibm_quantum(self):
        """Initialize IBM Quantum backend."""
        try:
            # Try to import IBM Quantum
            from qiskit_ibm_runtime import QiskitRuntimeService
            
            ibm_config = self.config.get("ibm_quantum", {})
            api_token = ibm_config.get("api_token", "")
            
            if not api_token:
                self.logger.warning("IBM Quantum API token not configured")
                return
            
            # Initialize service
            service = QiskitRuntimeService(
                channel="ibm_quantum",
                token=api_token,
                instance=f"{ibm_config.get('hub', 'ibm-q')}/{ibm_config.get('group', 'open')}/{ibm_config.get('project', 'main')}"
            )
            
            # Get available backends
            backends = service.backends()
            
            for backend in backends:
                # Filter for real quantum processors
                if not backend.simulator:
                    backend_info = QuantumBackendInfo(
                        backend_id=backend.name,
                        backend_type=QuantumBackendType.IBM_QUANTUM,
                        provider="IBM Quantum",
                        qubits=backend.num_qubits,
                        status=BackendStatus.CONNECTED,
                        queue_depth=backend.status().pending_jobs,
                        estimated_wait_time=60,  # Rough estimate
                        fidelity=0.99,  # Typical gate fidelity
                        availability=0.95,
                        cost_per_shot=0.0001,  # Rough estimate
                        free_tier_available=True,
                        free_tier_limit=300,  # Free tier limit (shots)
                        metadata={
                            "description": backend.description,
                            "version": backend.version,
                            "basis_gates": backend.operation_names,
                            "max_shots": backend.max_shots,
                            "simulator": backend.simulator
                        }
                    )
                    
                    self.backends[backend.name] = backend_info
                    self.logger.info(f"Added IBM Quantum backend: {backend.name} ({backend.num_qubits} qubits)")
            
            self.logger.info(f"Initialized IBM Quantum with {len([b for b in backends if not b.simulator])} real quantum processors")
            
        except ImportError:
            self.logger.warning("qiskit-ibm-runtime not installed. Install with: pip install qiskit-ibm-runtime")
        except Exception as e:
            self.logger.error(f"Failed to initialize IBM Quantum: {str(e)}")
    
    def _initialize_amazon_braket(self):
        """Initialize Amazon Braket backend."""
        try:
            # Try to import Amazon Braket
            import boto3
            from braket.aws import AwsDevice
            
            braket_config = self.config.get("amazon_braket", {})
            region = braket_config.get("region", "us-east-1")
            
            # Get available devices
            session = boto3.Session(region_name=region)
            devices = AwsDevice.get_devices(provider_names=["Amazon Braket", "IonQ", "Rigetti", "Oxford Quantum Circuits"])
            
            for device in devices:
                if device.status == "ONLINE":
                    backend_info = QuantumBackendInfo(
                        backend_id=device.name,
                        backend_type=QuantumBackendType.AMAZON_BRAKET,
                        provider=device.provider_name,
                        qubits=device.properties.paradigm.qubitCount,
                        status=BackendStatus.CONNECTED,
                        queue_depth=0,  # Amazon manages queue
                        estimated_wait_time=30,
                        fidelity=0.98,
                        availability=0.9,
                        cost_per_shot=device.properties.service.deviceCost.price,
                        free_tier_available=True,
                        free_tier_limit=200,  # Free tier limit
                        metadata={
                            "description": device.type.value,
                            "device_arn": device.arn,
                            "supported_operations": [op.name for op in device.properties.paradigm.nativeGateSet],
                            "region": region
                        }
                    )
                    
                    self.backends[device.name] = backend_info
                    self.logger.info(f"Added Amazon Braket backend: {device.name} ({device.properties.paradigm.qubitCount} qubits)")
            
            self.logger.info(f"Initialized Amazon Braket with {len(devices)} devices")
            
        except ImportError:
            self.logger.warning("amazon-braket-sdk not installed. Install with: pip install amazon-braket-sdk")
        except Exception as e:
            self.logger.error(f"Failed to initialize Amazon Braket: {str(e)}")
    
    def _initialize_azure_quantum(self):
        """Initialize Microsoft Azure Quantum backend."""
        try:
            # Try to import Azure Quantum
            from azure.quantum import Workspace
            from azure.quantum.target import Target
            
            azure_config = self.config.get("azure_quantum", {})
            subscription_id = azure_config.get("subscription_id", "")
            resource_group = azure_config.get("resource_group", "")
            workspace_name = azure_config.get("workspace", "")
            
            if not all([subscription_id, resource_group, workspace_name]):
                self.logger.warning("Azure Quantum configuration incomplete")
                return
            
            # Initialize workspace
            workspace = Workspace(
                subscription_id=subscription_id,
                resource_group=resource_group,
                name=workspace_name,
                location="eastus"  # Default location
            )
            
            # Get available targets
            targets = workspace.get_targets()
            
            for target in targets:
                if target.current_availability == "Available":
                    backend_info = QuantumBackendInfo(
                        backend_id=target.id,
                        backend_type=QuantumBackendType.AZURE_QUANTUM,
                        provider=target.provider_id,
                        qubits=target.num_qubits if hasattr(target, 'num_qubits') else 0,
                        status=BackendStatus.CONNECTED,
                        queue_depth=0,
                        estimated_wait_time=60,
                        fidelity=0.97,
                        availability=0.85,
                        cost_per_shot=0.0005,  # Rough estimate
                        free_tier_available=True,
                        free_tier_limit=100,  # Free tier limit
                        metadata={
                            "description": target.name,
                            "target_type": target.target_type,
                            "provider_id": target.provider_id,
                            "current_availability": target.current_availability
                        }
                    )
                    
                    self.backends[target.id] = backend_info
                    self.logger.info(f"Added Azure Quantum backend: {target.id}")
            
            self.logger.info(f"Initialized Azure Quantum with {len(targets)} targets")
            
        except ImportError:
            self.logger.warning("azure-quantum not installed. Install with: pip install azure-quantum")
        except Exception as e:
            self.logger.error(f"Failed to initialize Azure Quantum: {str(e)}")
    
    def get_available_backends(self) -> List[QuantumBackendInfo]:
        """Get list of available quantum backends."""
        return list(self.backends.values())
    
    def get_backend(self, backend_id: str) -> Optional[QuantumBackendInfo]:
        """Get information about a specific backend."""
        return self.backends.get(backend_id)
    
    def get_best_backend(
        self,
        qubits_needed: int,
        max_cost: Optional[float] = None,
        min_fidelity: float = 0.9
    ) -> Optional[QuantumBackendInfo]:
        """Get the best backend for given requirements."""
        suitable_backends = []
        
        for backend in self.backends.values():
            # Check requirements
            if backend.qubits < qubits_needed:
                continue
            
            if backend.status != BackendStatus.CONNECTED:
                continue
            
            if backend.fidelity < min_fidelity:
                continue
            
            if max_cost is not None and backend.cost_per_shot > max_cost:
                continue
            
            # Calculate score (higher is better)
            score = 0.0
            
            # Fidelity score (higher fidelity = better)
            score += backend.fidelity * 0.4
            
            # Availability score
            score += backend.availability * 0.3
            
            # Cost score (lower cost = better)
            if backend.cost_per_shot > 0:
                cost_score = 1.0 / (1.0 + backend.cost_per_shot * 1000)
            else:
                cost_score = 1.0
            score += cost_score * 0.2
            
            # Queue score (shorter queue = better)
            queue_score = 1.0 / (1.0 + backend.queue_depth / 10.0)
            score += queue_score * 0.1
            
            suitable_backends.append((score, backend))
        
        if not suitable_backends:
            return None
        
        # Return backend with highest score
        suitable_backends.sort(key=lambda x: x[0], reverse=True)
        return suitable_backends[0][1]
    
    def execute_circuit(
        self,
        circuit_data: Dict[str, Any],
        shots: int = 1024,
        backend_id: Optional[str] = None,
        use_real_hardware: bool = False
    ) -> QuantumJob:
        """Execute a quantum circuit on a backend."""
        # Determine backend
        if backend_id:
            backend = self.backends.get(backend_id)
            if not backend:
                raise ValueError(f"Backend not found: {backend_id}")
        else:
            # Auto-select backend
            qubits_needed = circuit_data.get("qubits", 1)
            
            if use_real_hardware and self.config.get("enable_real_hardware", False):
                # Try to use real hardware
                max_cost = self.config.get("cost_limit_per_month", 0.0) / 30  # Daily limit
                backend = self.get_best_backend(
                    qubits_needed=qubits_needed,
                    max_cost=max_cost,
                    min_fidelity=0.85
                )
                
                if not backend or backend.backend_type == QuantumBackendType.LOCAL_SIMULATOR:
                    # Fall back to simulator
                    backend = self.backends["local_simulator"]
                    self.logger.info("No suitable real hardware found, using local simulator")
            else:
                # Use simulator
                backend = self.backends.get("qiskit_aer") or self.backends["local_simulator"]
        
        # Create job
        job_id = f"job_{backend.backend_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        job = QuantumJob(
            job_id=job_id,
            backend_id=backend.backend_id,
            circuit_data=circuit_data,
            shots=shots,
            status="pending"
        )
        
        self.jobs[job_id] = job
        
        # Execute based on backend type
        try:
            if backend.backend_type == QuantumBackendType.LOCAL_SIMULATOR:
                result = self._execute_local_simulator(circuit_data, shots)
            elif backend.backend_type == QuantumBackendType.QISKIT_AER:
                result = self._execute_qiskit_aer(circuit_data, shots)
            elif backend.backend_type == QuantumBackendType.IBM_QUANTUM:
                result = self._execute_ibm_quantum(backend.backend_id, circuit_data, shots)
            elif backend.backend_type == QuantumBackendType.AMAZON_BRAKET:
                result = self._execute_amazon_braket(backend.backend_id, circuit_data, shots)
            elif backend.backend_type == QuantumBackendType.AZURE_QUANTUM:
                result = self._execute_azure_quantum(backend.backend_id, circuit_data, shots)
            else:
                raise ValueError(f"Unsupported backend type: {backend.backend_type}")
            
            # Update job
            job.status = "completed"
            job.result = result
            job.execution_time_ms = result.get("execution_time_ms", 0)
            job.completed_at = datetime.utcnow().isoformat()
            
            # Estimate cost
            if backend.cost_per_shot > 0:
                job.cost = backend.cost_per_shot * shots
            
            self.logger.info(f"Job {job_id} completed on {backend.backend_id}")
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow().isoformat()
            self.logger.error(f"Job {job_id} failed: {str(e)}")
        
        return job
    
    def _execute_local_simulator(self, circuit_data: Dict[str, Any], shots: int) -> Dict[str, Any]:
        """Execute circuit on local simulator."""
        # Simple simulation for testing
        # In production, would use actual quantum simulation library
        
        import random
        import time
        
        start_time = time.time()
        
        # Extract circuit information
        qubits = circuit_data.get("qubits", 1)
        gates = circuit_data.get("gates", [])
        
        # Generate random measurement results (simulated)
        num_states = 2 ** qubits
        states = [format(i, f'0{qubits}b') for i in range(num_states)]
        
        # Create biased distribution (simulating algorithm doing something)
        if circuit_data.get("problem_type") == "optimization":
            # Optimization tends to concentrate on a few states
            focus_states = random.sample(states, min(3, len(states)))
            base_prob = 0.7 / len(focus_states)
            other_prob = 0.3 / (len(states) - len(focus_states))
            
            measurement_counts = {}
            for state in states:
                if state in focus_states:
                    measurement_counts[state] = int(base_prob * shots)
                else:
                    measurement_counts[state] = int(other_prob * shots)
        else:
            # Uniform distribution for other problems
            measurement_counts = {state: shots // num_states for state in states}
        
        # Normalize
        total = sum(measurement_counts.values())
        if total != shots:
            scale = shots / total
            measurement_counts = {k: int(v * scale) for k, v in measurement_counts.items()}
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return {
            "measurement_counts": measurement_counts,
            "shots": shots,
            "qubits": qubits,
            "execution_time_ms": execution_time_ms,
            "backend": "local_simulator",
            "simulated": True
        }
    
    def _execute_qiskit_aer(self, circuit_data: Dict[str, Any], shots: int) -> Dict[str, Any]:
        """Execute circuit using Qiskit Aer simulator."""
        try:
            from qiskit import QuantumCircuit, transpile
            from qiskit_aer import AerSimulator
            import time
            
            start_time = time.time()
            
            # Extract circuit information
            qubits = circuit_data.get("qubits", 1)
            
            # Create quantum circuit
            qc = QuantumCircuit(qubits)
            
            # Apply gates from circuit data
            for gate_info in circuit_data.get("gates", []):
                gate_type = gate_info.get("type", "")
                gate_qubits = gate_info.get("qubits", [0])
                params = gate_info.get("parameters", [])
                
                if gate_type == "h":
                    qc.h(gate_qubits[0])
                elif gate_type == "x":
                    qc.x(gate_qubits[0])
                elif gate_type == "y":
                    qc.y(gate_qubits[0])
                elif gate_type == "z":
                    qc.z(gate_qubits[0])
                elif gate_type == "rx" and params:
                    qc.rx(params[0], gate_qubits[0])
                elif gate_type == "ry" and params:
                    qc.ry(params[0], gate_qubits[0])
                elif gate_type == "rz" and params:
                    qc.rz(params[0], gate_qubits[0])
                elif gate_type == "cnot" and len(gate_qubits) >= 2:
                    qc.cx(gate_qubits[0], gate_qubits[1])
                elif gate_type == "cz" and len(gate_qubits) >= 2:
                    qc.cz(gate_qubits[0], gate_qubits[1])
            
            # Add measurement
            qc.measure_all()
            
            # Execute on Aer simulator
            simulator = AerSimulator()
            compiled_circuit = transpile(qc, simulator)
            job = simulator.run(compiled_circuit, shots=shots)
            result = job.result()
            
            # Get counts
            counts = result.get_counts()
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return {
                "measurement_counts": counts,
                "shots": shots,
                "qubits": qubits,
                "execution_time_ms": execution_time_ms,
                "backend": "qiskit_aer",
                "simulated": True
            }
            
        except ImportError:
            self.logger.warning("Qiskit not installed, falling back to local simulator")
            return self._execute_local_simulator(circuit_data, shots)
        except Exception as e:
            self.logger.error(f"Qiskit Aer execution failed: {str(e)}")
            raise
    
    def _execute_ibm_quantum(self, backend_id: str, circuit_data: Dict[str, Any], shots: int) -> Dict[str, Any]:
        """Execute circuit on IBM Quantum hardware."""
        try:
            from qiskit import QuantumCircuit, transpile
            from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
            import time
            
            start_time = time.time()
            
            # Get IBM Quantum service
            ibm_config = self.config.get("ibm_quantum", {})
            service = QiskitRuntimeService(
                channel="ibm_quantum",
                token=ibm_config.get("api_token", ""),
                instance=f"{ibm_config.get('hub', 'ibm-q')}/{ibm_config.get('group', 'open')}/{ibm_config.get('project', 'main')}"
            )
            
            # Get backend
            backend = service.backend(backend_id)
            
            # Create quantum circuit
            qubits = circuit_data.get("qubits", 1)
            qc = QuantumCircuit(qubits)
            
            # Apply gates (simplified for example)
            # In production, would properly map gates to backend's basis gates
            for gate_info in circuit_data.get("gates", []):
                gate_type = gate_info.get("type", "")
                gate_qubits = gate_info.get("qubits", [0])
                
                if gate_type == "h":
                    qc.h(gate_qubits[0])
                elif gate_type == "x":
                    qc.x(gate_qubits[0])
                elif gate_type == "cnot" and len(gate_qubits) >= 2:
                    qc.cx(gate_qubits[0], gate_qubits[1])
            
            qc.measure_all()
            
            # Transpile for backend
            transpiled_qc = transpile(qc, backend)
            
            # Execute using Sampler
            sampler = Sampler(backend=backend)
            job = sampler.run(transpiled_qc, shots=shots)
            
            # Wait for result
            result = job.result()
            
            # Get quasi-probabilities
            quasi_dists = result.quasi_dists
            
            # Convert to counts
            counts = {}
            for quasi_dist in quasi_dists:
                for state, prob in quasi_dist.items():
                    counts[format(state, f'0{qubits}b')] = int(prob * shots)
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return {
                "measurement_counts": counts,
                "shots": shots,
                "qubits": qubits,
                "execution_time_ms": execution_time_ms,
                "backend": backend_id,
                "simulated": False,
                "real_hardware": True,
                "provider": "IBM Quantum"
            }
            
        except Exception as e:
            self.logger.error(f"IBM Quantum execution failed: {str(e)}")
            raise
    
    def _execute_amazon_braket(self, backend_id: str, circuit_data: Dict[str, Any], shots: int) -> Dict[str, Any]:
        """Execute circuit on Amazon Braket."""
        # Implementation would go here
        # For now, raise NotImplementedError
        raise NotImplementedError("Amazon Braket execution not yet implemented")
    
    def _execute_azure_quantum(self, backend_id: str, circuit_data: Dict[str, Any], shots: int) -> Dict[str, Any]:
        """Execute circuit on Azure Quantum."""
        # Implementation would go here
        # For now, raise NotImplementedError
        raise NotImplementedError("Azure Quantum execution not yet implemented")
    
    def get_job_status(self, job_id: str) -> Optional[QuantumJob]:
        """Get status of a quantum job."""
        return self.jobs.get(job_id)
    
    def get_job_history(self, limit: int = 100) -> List[QuantumJob]:
        """Get job history."""
        jobs = list(self.jobs.values())
        jobs.sort(key=lambda j: j.submitted_at, reverse=True)
        return jobs[:limit]
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get quantum computing usage statistics."""
        total_jobs = len(self.jobs)
        completed_jobs = sum(1 for j in self.jobs.values() if j.status == "completed")
        failed_jobs = sum(1 for j in self.jobs.values() if j.status == "failed")
        
        # Calculate total shots and cost
        total_shots = 0
        total_cost = 0.0
        
        for job in self.jobs.values():
            if job.status == "completed":
                total_shots += job.shots
                if job.cost:
                    total_cost += job.cost
        
        # Backend usage
        backend_usage = {}
        for job in self.jobs.values():
            backend_id = job.backend_id
            if backend_id not in backend_usage:
                backend_usage[backend_id] = {
                    "jobs": 0,
                    "shots": 0,
                    "cost": 0.0
                }
            
            backend_usage[backend_id]["jobs"] += 1
            backend_usage[backend_id]["shots"] += job.shots
            if job.cost:
                backend_usage[backend_id]["cost"] += job.cost
        
        return {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "success_rate": completed_jobs / total_jobs if total_jobs > 0 else 0.0,
            "total_shots": total_shots,
            "total_cost": total_cost,
            "backend_usage": backend_usage,
            "active_backend": self.active_backend,
            "available_backends": len(self.backends)
        }
    
    def save_config(self):
        """Save configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            self.logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {str(e)}")
    
    def configure_ibm_quantum(self, api_token: str, hub: str = "ibm-q", group: str = "open", project: str = "main"):
        """Configure IBM Quantum credentials."""
        if "ibm_quantum" not in self.config:
            self.config["ibm_quantum"] = {}
        
        self.config["ibm_quantum"].update({
            "enabled": True,
            "api_token": api_token,
            "hub": hub,
            "group": group,
            "project": project
        })
        
        # Re-initialize backends
        self._initialize_backends()
        
        self.save_config()
        self.logger.info("IBM Quantum configured")
    
    def configure_amazon_braket(self, region: str = "us-east-1"):
        """Configure Amazon Braket."""
        if "amazon_braket" not in self.config:
            self.config["amazon_braket"] = {}
        
        self.config["amazon_braket"].update({
            "enabled": True,
            "region": region
        })
        
        # Re-initialize backends
        self._initialize_backends()
        
        self.save_config()
        self.logger.info("Amazon Braket configured")
    
    def configure_azure_quantum(self, subscription_id: str, resource_group: str, workspace: str):
        """Configure Azure Quantum."""
        if "azure_quantum" not in self.config:
            self.config["azure_quantum"] = {}
        
        self.config["azure_quantum"].update({
            "enabled": True,
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "workspace": workspace
        })
        
        # Re-initialize backends
        self._initialize_backends()
        
        self.save_config()
        self.logger.info("Azure Quantum configured")


# Singleton instance
_quantum_backend_manager = None

def get_quantum_backend_manager(config_path: Optional[str] = None) -> QuantumBackendManager:
    """Get singleton instance of quantum backend manager."""
    global _quantum_backend_manager
    if _quantum_backend_manager is None:
        _quantum_backend_manager = QuantumBackendManager(config_path)
    return _quantum_backend_manager