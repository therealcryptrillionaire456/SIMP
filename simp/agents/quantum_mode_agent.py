#!/usr/bin/env python3
"""
Quantum Mode Agent for SIMP

Integrates the comprehensive Quantum Mode system with SIMP.
Routes quantum algorithm queries through the retrieval-first Quantum Mode engine
while maintaining compatibility with existing SIMP workflows.
"""

import json
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from simp.agent import SimpAgent
from simp.intent import Intent, SimpResponse
from simp.crypto import generate_agent_id

# Import Quantum Mode components
try:
    # Try relative import first
    from ...quantum_mode_engine import QuantumModeEngine
    from ...quantum_mode_schema import QuantumErrorCode
except ImportError:
    # Fall back to absolute import
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from quantum_mode_engine import QuantumModeEngine
    from quantum_mode_schema import QuantumErrorCode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class QuantumModeAgentConfig:
    """Configuration for Quantum Mode Agent."""
    
    # Paths
    config_path: Optional[Path] = None
    dataset_dir: Optional[Path] = None
    traces_dir: Optional[Path] = None
    
    # ProjectX integration
    projectx_endpoint: Optional[str] = "http://localhost:8771/judgment"
    
    # Features
    enable_learning: bool = True
    enable_risk_scoring: bool = True
    enable_tracing: bool = True
    
    # SIMP integration
    agent_id: str = "quantum_mode"
    agent_name: str = "Quantum Mode Agent"
    capabilities: List[str] = field(default_factory=lambda: [
        "quantum_algorithm_generation",
        "quantum_circuit_design",
        "quantum_simulation",
        "quantum_error_correction",
        "code_generation",
        "safety_verification"
    ])
    
    def __post_init__(self):
        """Set default paths if not provided."""
        if self.config_path is None:
            self.config_path = Path("quantum_mode_config.json")
        
        if self.dataset_dir is None:
            self.dataset_dir = Path("data/quantum_dataset")
        
        if self.traces_dir is None:
            self.traces_dir = Path("data/quantum_traces")


class QuantumModeAgent(SimpAgent):
    """SIMP agent for Quantum Mode integration."""
    
    def __init__(self, config: Optional[QuantumModeAgentConfig] = None):
        """Initialize Quantum Mode Agent."""
        # Default configuration
        if config is None:
            config = QuantumModeAgentConfig()
        
        self.config = config
        
        # Generate agent ID if not provided
        if not config.agent_id or config.agent_id == "quantum_mode":
            config.agent_id = generate_agent_id("quantum_mode")
        
        # Initialize SIMP agent
        super().__init__(
            agent_id=config.agent_id,
            agent_name=config.agent_name,
            capabilities=config.capabilities
        )
        
        # Initialize Quantum Mode Engine
        self.engine = None
        self._init_engine()
        
        # Register intent handlers
        self._register_handlers()
        
        logger.info(f"Quantum Mode Agent initialized with ID: {config.agent_id}")
    
    def _init_engine(self):
        """Initialize Quantum Mode Engine."""
        try:
            self.engine = QuantumModeEngine(
                config_path=self.config.config_path,
                dataset_dir=self.config.dataset_dir,
                projectx_endpoint=self.config.projectx_endpoint,
                enable_learning=self.config.enable_learning,
                enable_risk_scoring=self.config.enable_risk_scoring
            )
            logger.info("Quantum Mode Engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Quantum Mode Engine: {e}")
            raise
    
    def _register_handlers(self):
        """Register intent handlers."""
        # Quantum algorithm generation
        self.register_handler("quantum_algorithm", self.handle_quantum_algorithm)
        self.register_handler("quantum_circuit", self.handle_quantum_circuit)
        self.register_handler("quantum_simulation", self.handle_quantum_simulation)
        self.register_handler("quantum_error_correction", self.handle_quantum_error_correction)
        
        # Generic code generation with quantum detection
        self.register_handler("code_generation", self.handle_code_generation)
        
        # System operations
        self.register_handler("quantum_mode_metrics", self.handle_metrics)
        self.register_handler("quantum_mode_export", self.handle_export)
        self.register_handler("quantum_mode_stats", self.handle_stats)
    
    async def handle_quantum_algorithm(self, intent: Intent) -> SimpResponse:
        """Handle quantum algorithm generation intent."""
        return await self._handle_quantum_intent(intent, "quantum_algorithm")
    
    async def handle_quantum_circuit(self, intent: Intent) -> SimpResponse:
        """Handle quantum circuit design intent."""
        return await self._handle_quantum_intent(intent, "quantum_circuit")
    
    async def handle_quantum_simulation(self, intent: Intent) -> SimpResponse:
        """Handle quantum simulation intent."""
        return await self._handle_quantum_intent(intent, "quantum_simulation")
    
    async def handle_quantum_error_correction(self, intent: Intent) -> SimpResponse:
        """Handle quantum error correction intent."""
        return await self._handle_quantum_intent(intent, "quantum_error_correction")
    
    async def handle_code_generation(self, intent: Intent) -> SimpResponse:
        """Handle generic code generation with quantum detection."""
        # Extract query from intent
        query = intent.params.get("query", "")
        context = intent.params.get("context", {})
        
        # Check if this is a quantum query
        is_quantum, confidence = self.engine._config.is_quantum_query(query)
        
        if is_quantum:
            # Route to quantum mode
            logger.info(f"Quantum query detected in code_generation: {query[:50]}...")
            
            # Determine task type
            classification = self.engine._classify_task_type(query, confidence)
            task_type = classification.get("task_type", "quantum_algorithm")
            
            # Process through quantum mode
            result = self.engine.process_query(query, context)
            
            # Format response
            return self._format_quantum_response(result, intent, task_type)
        else:
            # Not a quantum query - pass through or handle normally
            logger.debug(f"Non-quantum code generation: {query[:50]}...")
            
            # For now, return a response indicating it's not quantum
            # In a full implementation, this would route to a different handler
            return SimpResponse(
                success=True,
                data={
                    "message": "Query is not quantum-related",
                    "should_exit_quantum_mode": True,
                    "confidence": confidence,
                    "suggestion": "Route to general code generation agent"
                },
                intent_id=intent.intent_id
            )
    
    async def _handle_quantum_intent(self, intent: Intent, expected_task_type: str) -> SimpResponse:
        """Handle a quantum-related intent."""
        # Extract query and context
        query = intent.params.get("query", "")
        context = intent.params.get("context", {})
        
        if not query:
            return SimpResponse(
                success=False,
                error="No query provided",
                intent_id=intent.intent_id
            )
        
        logger.info(f"Processing quantum intent: {expected_task_type} - {query[:50]}...")
        
        # Process through quantum mode engine
        result = self.engine.process_query(query, context)
        
        # Format response
        return self._format_quantum_response(result, intent, expected_task_type)
    
    def _format_quantum_response(self, result: Dict, intent: Intent, task_type: str) -> SimpResponse:
        """Format quantum mode result as SIMP response."""
        if result.get("success", False):
            # Success case
            execution_result = result.get("execution_result", {})
            
            # Extract relevant information
            response_data = {
                "task_type": task_type,
                "query": result.get("task", {}).get("query", ""),
                "success": True,
                "execution_mode": execution_result.get("execution_mode", "unknown"),
                "result": execution_result.get("output", ""),
                "explanation": execution_result.get("explanation", ""),
                "quality_score": execution_result.get("quality_score", 0.5),
                "trace_id": result.get("trace_id"),
                "retrieval_info": {
                    "examples_found": len(result.get("retrieval_result", {}).get("examples", [])),
                    "confidence": result.get("retrieval_result", {}).get("confidence_level", "unknown")
                },
                "verification_info": {
                    "status": result.get("verification_result", {}).get("verification_status", "unknown"),
                    "score": result.get("verification_result", {}).get("overall_score", 0.0)
                }
            }
            
            # Add safety information if available
            if "safety_issues" in execution_result:
                response_data["safety_issues"] = execution_result["safety_issues"]
            
            return SimpResponse(
                success=True,
                data=response_data,
                intent_id=intent.intent_id
            )
        
        else:
            # Failure case
            error_code = result.get("error_code", QuantumErrorCode.QMODE_UNEXPECTED_ERROR.value)
            error_message = result.get("error", "Unknown error")
            
            # Determine if we should block or just fail
            should_block = result.get("should_block", False)
            should_exit_quantum_mode = result.get("should_exit_quantum_mode", False)
            
            response_data = {
                "success": False,
                "error": error_message,
                "error_code": error_code,
                "should_block": should_block,
                "should_exit_quantum_mode": should_exit_quantum_mode,
                "trace_id": result.get("trace_id")
            }
            
            # Add additional context if available
            if "retrieval_result" in result:
                response_data["retrieval_result"] = result["retrieval_result"]
            
            if "verification_result" in result:
                response_data["verification_result"] = result["verification_result"]
            
            if "projectx_result" in result:
                response_data["projectx_result"] = result["projectx_result"]
            
            return SimpResponse(
                success=False,
                data=response_data,
                intent_id=intent.intent_id
            )
    
    async def handle_metrics(self, intent: Intent) -> SimpResponse:
        """Handle metrics request."""
        try:
            metrics = self.engine.get_metrics()
            
            return SimpResponse(
                success=True,
                data={
                    "metrics": metrics,
                    "timestamp": datetime.now().isoformat(),
                    "agent_id": self.config.agent_id
                },
                intent_id=intent.intent_id
            )
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return SimpResponse(
                success=False,
                error=f"Failed to get metrics: {str(e)}",
                intent_id=intent.intent_id
            )
    
    async def handle_export(self, intent: Intent) -> SimpResponse:
        """Handle data export request."""
        try:
            output_dir = intent.params.get("output_dir")
            if output_dir:
                output_dir = Path(output_dir)
            
            export_data = self.engine.export_training_data(output_dir)
            
            return SimpResponse(
                success=True,
                data={
                    "export": export_data,
                    "output_dir": str(output_dir) if output_dir else "default",
                    "timestamp": datetime.now().isoformat()
                },
                intent_id=intent.intent_id
            )
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return SimpResponse(
                success=False,
                error=f"Failed to export data: {str(e)}",
                intent_id=intent.intent_id
            )
    
    async def handle_stats(self, intent: Intent) -> SimpResponse:
        """Handle dataset statistics request."""
        try:
            # Get dataset stats from engine
            metrics = self.engine.get_metrics()
            dataset_stats = metrics.get("dataset_stats", {})
            
            # Get trace stats
            trace_stats = metrics.get("traces", {})
            
            return SimpResponse(
                success=True,
                data={
                    "dataset_stats": dataset_stats,
                    "trace_stats": trace_stats,
                    "engine_initialized": self.engine is not None,
                    "timestamp": datetime.now().isoformat()
                },
                intent_id=intent.intent_id
            )
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return SimpResponse(
                success=False,
                error=f"Failed to get stats: {str(e)}",
                intent_id=intent.intent_id
            )
    
    def get_agent_info(self) -> Dict:
        """Get agent information for registration."""
        return {
            "agent_id": self.config.agent_id,
            "agent_name": self.config.agent_name,
            "capabilities": self.config.capabilities,
            "config": {
                "config_path": str(self.config.config_path),
                "dataset_dir": str(self.config.dataset_dir),
                "projectx_endpoint": self.config.projectx_endpoint,
                "enable_learning": self.config.enable_learning,
                "enable_risk_scoring": self.config.enable_risk_scoring
            },
            "quantum_mode_version": "1.0.0",
            "status": "active" if self.engine else "inactive"
        }


async def register_with_simp(broker_url: str = "http://localhost:5555",
                           config: Optional[QuantumModeAgentConfig] = None) -> bool:
    """
    Register Quantum Mode Agent with SIMP broker.
    
    Args:
        broker_url: URL of SIMP broker
        config: Agent configuration
    
    Returns:
        True if registration successful
    """
    try:
        # Create agent
        agent = QuantumModeAgent(config)
        
        # Get agent info
        agent_info = agent.get_agent_info()
        
        # In a real implementation, this would register with the broker
        # For now, just log and return success
        logger.info(f"Quantum Mode Agent ready to register with broker: {broker_url}")
        logger.info(f"Agent info: {json.dumps(agent_info, indent=2)}")
        
        # TODO: Implement actual broker registration
        # This would involve making an HTTP request to the broker's /agents endpoint
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to register with SIMP: {e}")
        return False


def main():
    """Command-line interface for Quantum Mode Agent."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Quantum Mode Agent for SIMP")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--dataset-dir", help="Path to dataset directory")
    parser.add_argument("--traces-dir", help="Path to traces directory")
    parser.add_argument("--projectx-endpoint", help="ProjectX endpoint URL")
    parser.add_argument("--broker-url", default="http://localhost:5555",
                       help="SIMP broker URL")
    parser.add_argument("--no-learning", action="store_true",
                       help="Disable learning")
    parser.add_argument("--no-risk", action="store_true",
                       help="Disable risk scoring")
    parser.add_argument("--register", action="store_true",
                       help="Register with SIMP broker")
    parser.add_argument("--agent-id", help="Custom agent ID")
    parser.add_argument("--test", action="store_true",
                       help="Run test query")
    
    args = parser.parse_args()
    
    # Create configuration
    config = QuantumModeAgentConfig(
        config_path=Path(args.config) if args.config else None,
        dataset_dir=Path(args.dataset_dir) if args.dataset_dir else None,
        traces_dir=Path(args.traces_dir) if args.traces_dir else None,
        projectx_endpoint=args.projectx_endpoint,
        enable_learning=not args.no_learning,
        enable_risk_scoring=not args.no_risk
    )
    
    if args.agent_id:
        config.agent_id = args.agent_id
    
    if args.register:
        # Register with SIMP broker
        success = asyncio.run(register_with_simp(args.broker_url, config))
        
        if success:
            print("✅ Quantum Mode Agent registered successfully")
            print(f"   Broker: {args.broker_url}")
            print(f"   Agent ID: {config.agent_id}")
        else:
            print("❌ Failed to register Quantum Mode Agent")
            return 1
    
    elif args.test:
        # Run test query
        agent = QuantumModeAgent(config)
        
        # Create test intent
        test_intent = Intent(
            intent_id=str(uuid.uuid4()),
            intent_type="quantum_algorithm",
            source_agent="test",
            target_agent=config.agent_id,
            params={
                "query": "Create a Bell state circuit with 2 qubits",
                "context": {"test": True}
            },
            timestamp=datetime.now().isoformat()
        )
        
        # Process intent
        response = asyncio.run(agent.handle_quantum_algorithm(test_intent))
        
        print("Test Results:")
        print(json.dumps(response.to_dict(), indent=2))
        
        if response.success:
            print("\n✅ Test passed!")
            return 0
        else:
            print("\n❌ Test failed")
            return 1
    
    else:
        # Print agent info
        agent = QuantumModeAgent(config)
        agent_info = agent.get_agent_info()
        
        print("Quantum Mode Agent Information:")
        print(json.dumps(agent_info, indent=2))
        
        print("\nAvailable intent types:")
        for intent_type in ["quantum_algorithm", "quantum_circuit", "quantum_simulation",
                          "quantum_error_correction", "code_generation", "quantum_mode_metrics",
                          "quantum_mode_export", "quantum_mode_stats"]:
            print(f"  • {intent_type}")
        
        print("\nUsage:")
        print("  --register          Register with SIMP broker")
        print("  --test              Run test query")
        print("  --broker-url URL    Specify broker URL (default: http://localhost:5555)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())