#!/usr/bin/env python3
"""
Stray Goose Quantum Mode Integration

Bridges Stray Goose's planning and analysis with the Quantum Mode system.
Provides hooks for quantum query detection, routing, and result integration.
"""

import json
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class QuantumIntegrationConfig:
    """Configuration for Quantum Mode integration."""
    
    # Detection settings
    detection_enabled: bool = True
    confidence_threshold: float = 0.5
    auto_route_quantum: bool = True
    
    # Routing settings
    fallback_to_normal: bool = True
    require_confirmation: bool = False
    
    # Integration settings
    preserve_context: bool = True
    add_metadata: bool = True
    log_interactions: bool = True
    
    # Paths
    config_path: Optional[Path] = None
    dataset_dir: Optional[Path] = None
    log_dir: Optional[Path] = None
    
    def __post_init__(self):
        """Set default paths."""
        if self.config_path is None:
            self.config_path = Path("quantum_mode_config.json")
        
        if self.dataset_dir is None:
            self.dataset_dir = Path("data/quantum_dataset")
        
        if self.log_dir is None:
            self.log_dir = Path("data/quantum_integration_logs")


class StrayGooseQuantumIntegration:
    """
    Integrates Quantum Mode with Stray Goose.
    
    Provides:
    1. Quantum query detection
    2. Automatic routing to Quantum Mode
    3. Result integration with Stray Goose workflows
    4. Mode switching between quantum and normal operation
    """
    
    def __init__(self, config: Optional[QuantumIntegrationConfig] = None):
        """Initialize integration."""
        self.config = config or QuantumIntegrationConfig()
        
        # Initialize Quantum Mode Engine
        self.engine = None
        self._init_engine()
        
        # State tracking
        self.in_quantum_mode = False
        self.interaction_history: List[Dict] = []
        
        # Create log directory
        self.config.log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Stray Goose Quantum Integration initialized")
    
    def _init_engine(self):
        """Initialize Quantum Mode Engine."""
        try:
            # Import here to avoid circular imports
            from quantum_mode_engine import QuantumModeEngine
            
            self.engine = QuantumModeEngine(
                config_path=self.config.config_path,
                dataset_dir=self.config.dataset_dir,
                enable_learning=True,
                enable_risk_scoring=True
            )
            logger.info("Quantum Mode Engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Quantum Mode Engine: {e}")
            # Continue without engine - will use detection only
    
    def detect_quantum_query(self, query: str, context: Optional[Dict] = None) -> Tuple[bool, float, Dict]:
        """
        Detect if a query is quantum-related.
        
        Args:
            query: User query string
            context: Optional context dictionary
            
        Returns:
            Tuple of (is_quantum, confidence, detection_info)
        """
        if not self.config.detection_enabled:
            return False, 0.0, {"detection_disabled": True}
        
        if not self.engine:
            # Fallback detection without engine
            return self._fallback_detection(query, context)
        
        try:
            # Use engine's detection
            is_quantum, confidence = self.engine._config.is_quantum_query(query)
            
            detection_info = {
                "detection_method": "engine",
                "confidence": confidence,
                "threshold": self.config.confidence_threshold,
                "engine_available": True
            }
            
            # Check against threshold
            is_quantum = is_quantum and confidence >= self.config.confidence_threshold
            
            return is_quantum, confidence, detection_info
            
        except Exception as e:
            logger.error(f"Error in quantum detection: {e}")
            # Fallback to simple detection
            return self._fallback_detection(query, context)
    
    def _fallback_detection(self, query: str, context: Optional[Dict] = None) -> Tuple[bool, float, Dict]:
        """Fallback detection without Quantum Mode Engine."""
        # Simple keyword-based detection
        quantum_keywords = [
            "quantum", "qubit", "superposition", "entanglement",
            "quantum algorithm", "quantum computing", "quantum circuit",
            "quantum gate", "hadamard", "cnot", "toffoli", "grover",
            "shor", "quantum fourier", "quantum teleportation",
            "bell state", "quantum error", "quantum simulation"
        ]
        
        query_lower = query.lower()
        
        # Count keyword matches
        matches = sum(1 for keyword in quantum_keywords if keyword in query_lower)
        
        # Calculate confidence
        confidence = min(1.0, matches * 0.2)  # 0.2 per keyword, max 1.0
        
        detection_info = {
            "detection_method": "fallback_keyword",
            "keyword_matches": matches,
            "confidence": confidence,
            "threshold": self.config.confidence_threshold,
            "engine_available": False
        }
        
        is_quantum = confidence >= self.config.confidence_threshold
        
        return is_quantum, confidence, detection_info
    
    def process_query(self, query: str, context: Optional[Dict] = None,
                     force_quantum: bool = False) -> Dict:
        """
        Process a query through the appropriate system.
        
        Args:
            query: User query string
            context: Optional context dictionary
            force_quantum: Force quantum mode regardless of detection
            
        Returns:
            Processing result dictionary
        """
        # Log interaction
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "query": query[:200],  # Truncate for logging
            "context": context,
            "force_quantum": force_quantum
        }
        
        # Detect if quantum
        if force_quantum:
            is_quantum = True
            confidence = 1.0
            detection_info = {"forced": True}
        else:
            is_quantum, confidence, detection_info = self.detect_quantum_query(query, context)
        
        interaction.update({
            "is_quantum": is_quantum,
            "confidence": confidence,
            "detection_info": detection_info
        })
        
        if is_quantum and self.engine and self.config.auto_route_quantum:
            # Route to Quantum Mode
            logger.info(f"Routing quantum query to Quantum Mode: {query[:50]}...")
            
            try:
                result = self.engine.process_query(query, context)
                
                interaction.update({
                    "routed_to": "quantum_mode",
                    "success": result.get("success", False),
                    "trace_id": result.get("trace_id"),
                    "error": result.get("error") if not result.get("success") else None
                })
                
                # Update mode state
                self.in_quantum_mode = True
                
                # Format result for Stray Goose
                formatted_result = self._format_for_stray_goose(result, query, context)
                
                interaction["formatted_result"] = formatted_result
                
            except Exception as e:
                logger.error(f"Error processing quantum query: {e}")
                
                interaction.update({
                    "routed_to": "quantum_mode",
                    "success": False,
                    "error": str(e)
                })
                
                # Fallback to normal processing if configured
                if self.config.fallback_to_normal:
                    logger.info("Falling back to normal processing")
                    formatted_result = self._fallback_processing(query, context)
                else:
                    formatted_result = {
                        "success": False,
                        "error": f"Quantum Mode error: {str(e)}",
                        "should_exit_quantum_mode": True
                    }
        
        else:
            # Not quantum or routing disabled
            if is_quantum and not self.config.auto_route_quantum:
                logger.info(f"Quantum query detected but auto-routing disabled: {query[:50]}...")
                interaction["routed_to"] = "normal (auto-routing disabled)"
            else:
                logger.debug(f"Non-quantum query: {query[:50]}...")
                interaction["routed_to"] = "normal"
            
            # Process normally (placeholder - would integrate with Stray Goose's normal processing)
            formatted_result = self._normal_processing(query, context)
            
            # Update mode state
            self.in_quantum_mode = False
        
        # Add integration metadata
        if self.config.add_metadata:
            formatted_result["quantum_integration"] = {
                "detected_quantum": is_quantum,
                "confidence": confidence,
                "in_quantum_mode": self.in_quantum_mode,
                "interaction_id": len(self.interaction_history)
            }
        
        interaction["result"] = formatted_result
        
        # Log interaction
        self.interaction_history.append(interaction)
        
        if self.config.log_interactions:
            self._log_interaction(interaction)
        
        return formatted_result
    
    def _format_for_stray_goose(self, quantum_result: Dict, query: str,
                               context: Optional[Dict] = None) -> Dict:
        """Format Quantum Mode result for Stray Goose integration."""
        if quantum_result.get("success", False):
            # Success case
            execution_result = quantum_result.get("execution_result", {})
            
            # Extract key information
            result_text = execution_result.get("output", "")
            explanation = execution_result.get("explanation", "")
            
            # Combine result and explanation
            if explanation and result_text:
                combined = f"{explanation}\n\n```python\n{result_text}\n```"
            elif result_text:
                combined = result_text
            else:
                combined = explanation
            
            formatted = {
                "success": True,
                "result": combined,
                "source": "quantum_mode",
                "metadata": {
                    "execution_mode": execution_result.get("execution_mode", "unknown"),
                    "quality_score": execution_result.get("quality_score", 0.5),
                    "trace_id": quantum_result.get("trace_id"),
                    "task_type": quantum_result.get("task", {}).get("task_type", "unknown"),
                    "verification_score": quantum_result.get("verification_result", {}).get("overall_score", 0.0)
                }
            }
            
            # Add safety information if available
            if "safety_issues" in execution_result:
                formatted["metadata"]["safety_issues"] = execution_result["safety_issues"]
                formatted["metadata"]["has_safety_issues"] = len(execution_result["safety_issues"]) > 0
            
            # Preserve context if configured
            if self.config.preserve_context and context:
                formatted["context"] = context
            
            return formatted
        
        else:
            # Failure case
            formatted = {
                "success": False,
                "error": quantum_result.get("error", "Unknown error"),
                "source": "quantum_mode",
                "metadata": {
                    "error_code": quantum_result.get("error_code", "UNKNOWN"),
                    "should_block": quantum_result.get("should_block", False),
                    "should_exit_quantum_mode": quantum_result.get("should_exit_quantum_mode", False),
                    "trace_id": quantum_result.get("trace_id")
                }
            }
            
            # Add additional context for debugging
            if "retrieval_result" in quantum_result:
                formatted["metadata"]["retrieval_info"] = {
                    "examples_found": len(quantum_result["retrieval_result"].get("examples", [])),
                    "confidence": quantum_result["retrieval_result"].get("confidence_level", "unknown")
                }
            
            if "verification_result" in quantum_result:
                formatted["metadata"]["verification_info"] = {
                    "status": quantum_result["verification_result"].get("verification_status", "unknown"),
                    "score": quantum_result["verification_result"].get("overall_score", 0.0)
                }
            
            return formatted
    
    def _normal_processing(self, query: str, context: Optional[Dict] = None) -> Dict:
        """Placeholder for normal Stray Goose processing."""
        # In a real integration, this would call Stray Goose's normal processing
        # For now, return a placeholder result
        
        return {
            "success": True,
            "result": f"Normal processing for: {query}",
            "source": "stray_goose_normal",
            "metadata": {
                "processing_method": "normal",
                "quantum_detected": False
            }
        }
    
    def _fallback_processing(self, query: str, context: Optional[Dict] = None) -> Dict:
        """Fallback processing when Quantum Mode fails."""
        # Simple fallback - provide basic guidance
        
        guidance = f"""
## Quantum Query Detected but Processing Failed

**Query**: {query}

**Status**: The Quantum Mode system encountered an error while processing this query.

**Suggested Actions**:
1. Try rephrasing the query to be more specific
2. Check if the query requires quantum computing (vs classical computing)
3. Consider using a simpler quantum algorithm or circuit
4. Verify that quantum computing libraries are available

**Example quantum queries that work well**:
- "Create a Bell state circuit with 2 qubits"
- "Implement Grover's search algorithm for 3 qubits"
- "Show me a quantum circuit for entanglement"
- "How to create a superposition state in Qiskit"

**Note**: This is a fallback response. The Quantum Mode system should be investigated.
"""
        
        return {
            "success": False,
            "result": guidance,
            "source": "quantum_mode_fallback",
            "metadata": {
                "processing_method": "fallback",
                "quantum_detected": True,
                "fallback_reason": "Quantum Mode error"
            }
        }
    
    def _log_interaction(self, interaction: Dict):
        """Log interaction to file."""
        try:
            log_file = self.config.log_dir / f"interaction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(log_file, 'w') as f:
                json.dump(interaction, f, indent=2, default=str)
            
            logger.debug(f"Logged interaction to {log_file}")
        except Exception as e:
            logger.error(f"Failed to log interaction: {e}")
    
    def get_integration_status(self) -> Dict:
        """Get integration status."""
        return {
            "engine_available": self.engine is not None,
            "in_quantum_mode": self.in_quantum_mode,
            "interaction_count": len(self.interaction_history),
            "config": {
                "detection_enabled": self.config.detection_enabled,
                "auto_route_quantum": self.config.auto_route_quantum,
                "fallback_to_normal": self.config.fallback_to_normal
            },
            "recent_interactions": [
                {
                    "timestamp": i["timestamp"],
                    "query_preview": i["query"][:50] + "..." if len(i["query"]) > 50 else i["query"],
                    "is_quantum": i["is_quantum"],
                    "success": i.get("success", False)
                }
                for i in self.interaction_history[-5:]  # Last 5 interactions
            ]
        }
    
    def export_interaction_data(self, output_dir: Optional[Path] = None) -> Dict:
        """Export interaction data for analysis."""
        if output_dir is None:
            output_dir = self.config.log_dir / "exports"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = output_dir / f"interaction_export_{timestamp}.json"
        
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "interaction_count": len(self.interaction_history),
            "integration_status": self.get_integration_status(),
            "interactions": self.interaction_history
        }
        
        try:
            with open(export_file, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Exported {len(self.interaction_history)} interactions to {export_file}")
            
            return {
                "success": True,
                "export_file": str(export_file),
                "interaction_count": len(self.interaction_history),
                "file_size": export_file.stat().st_size if export_file.exists() else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to export interaction data: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def create_quantum_work_packet(query: str, context: Optional[Dict] = None) -> Dict:
    """
    Create a work packet for SIMP Goose from a quantum query.
    
    This is the interface that Stray Goose would use to turn
    quantum queries into executable work packets.
    
    Args:
        query: Quantum query
        context: Optional context
        
    Returns:
        Work packet dictionary
    """
    # Initialize integration
    integration = StrayGooseQuantumIntegration()
    
    # Process query
    result = integration.process_query(query, context)
    
    # Create work packet based on result
    if result.get("success", False):
        # Successful quantum processing
        work_packet = {
            "type": "quantum_algorithm_generation",
            "status": "completed",
            "result": result["result"],
            "metadata": result.get("metadata", {}),
            "source": "quantum_mode",
            "execution_time": datetime.now().isoformat()
        }
    else:
        # Failed or non-quantum
        work_packet = {
            "type": "analysis",
            "status": "requires_review",
            "query": query,
            "result": result.get("result", result.get("error", "Unknown")),
            "metadata": {
                "quantum_detected": result.get("metadata", {}).get("detected_quantum", False),
                "error": result.get("error"),
                "requires_manual_review": True
            },
            "source": "quantum_integration",
            "execution_time": datetime.now().isoformat()
        }
    
    return work_packet


def main():
    """Command-line interface for Stray Goose Quantum Integration."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Stray Goose Quantum Mode Integration"
    )
    
    parser.add_argument("query", nargs="?", help="Query to process")
    parser.add_argument("--detect-only", action="store_true",
                       help="Only detect if query is quantum")
    parser.add_argument("--force-quantum", action="store_true",
                       help="Force quantum mode processing")
    parser.add_argument("--status", action="store_true",
                       help="Show integration status")
    parser.add_argument("--export", action="store_true",
                       help="Export interaction data")
    parser.add_argument("--work-packet", action="store_true",
                       help="Create work packet from query")
    
    args = parser.parse_args()
    
    # Initialize integration
    integration = StrayGooseQuantumIntegration()
    
    if args.status:
        # Show status
        status = integration.get_integration_status()
        print("Integration Status:")
        print(json.dumps(status, indent=2))
        
    elif args.export:
        # Export data
        result = integration.export_interaction_data()
        print("Export Result:")
        print(json.dumps(result, indent=2))
        
    elif args.query:
        # Process query
        if args.detect_only:
            # Detect only
            is_quantum, confidence, info = integration.detect_quantum_query(args.query)
            
            print("Detection Results:")
            print(f"  Query: {args.query[:100]}...")
            print(f"  Is Quantum: {is_quantum}")
            print(f"  Confidence: {confidence:.2f}")
            print(f"  Method: {info.get('detection_method', 'unknown')}")
            
            if is_quantum:
                print("  ✅ Quantum query detected")
            else:
                print("  ⚠️  Not a quantum query (or below threshold)")
                
        elif args.work_packet:
            # Create work packet
            work_packet = create_quantum_work_packet(args.query)
            
            print("Work Packet:")
            print(json.dumps(work_packet, indent=2))
            
        else:
            # Full processing
            result = integration.process_query(
                args.query,
                force_quantum=args.force_quantum
            )
            
            print("Processing Results:")
            print(json.dumps(result, indent=2))
            
    else:
        # No query provided
        parser.print_help()
        
        print("\nExamples:")
        print('  python stray_goose_quantum_integration.py "Create a quantum circuit"')
        print('  python stray_goose_quantum_integration.py "What is quantum computing?" --detect-only')
        print('  python stray_goose_quantum_integration.py --status')
        print('  python stray_goose_quantum_integration.py "Grover algorithm" --work-packet')
    
    return 0


if __name__ == "__main__":
    sys.exit(main())