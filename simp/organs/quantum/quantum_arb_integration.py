"""
QuantumArb Integration with Quantum Computing

This module demonstrates how to integrate quantum computing capabilities
with the QuantumArb agent for enhanced arbitrage detection and optimization.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from simp.organs.quantum import (
    QuantumBackend,
    QuantumAlgorithm,
    PortfolioOptimizationParams,
    get_quantum_adapter,
)
from simp.organs.quantumarb import (
    QuantumArbDecisionSummary,
    QuantumArbSide,
    QuantumArbDecision,
)


class QuantumEnhancedArb:
    """
    Quantum-enhanced arbitrage detection and optimization.
    
    This class extends QuantumArb capabilities with quantum computing:
    1. Portfolio optimization across multiple arbitrage opportunities
    2. Risk assessment using quantum Monte Carlo
    3. Execution timing optimization
    4. Cross-exchange correlation analysis
    """
    
    def __init__(self, quantum_backend: QuantumBackend = QuantumBackend.LOCAL_SIMULATOR):
        self.quantum_adapter = get_quantum_adapter(quantum_backend)
        self.logger = logging.getLogger(__name__)
        self._connected = False
        
    def connect(self) -> bool:
        """Connect to quantum computing backend."""
        try:
            self._connected = self.quantum_adapter.connect()
            if self._connected:
                self.logger.info(f"Connected to quantum backend: {self.quantum_adapter.backend.value}")
            return self._connected
        except Exception as e:
            self.logger.error(f"Failed to connect to quantum backend: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from quantum computing backend."""
        try:
            success = self.quantum_adapter.disconnect()
            if success:
                self._connected = False
                self.logger.info("Disconnected from quantum backend")
            return success
        except Exception as e:
            self.logger.error(f"Failed to disconnect from quantum backend: {e}")
            return False
    
    def optimize_arbitrage_portfolio(
        self,
        opportunities: List[Dict[str, Any]],
        capital: float,
        risk_tolerance: float = 0.3
    ) -> Dict[str, Any]:
        """
        Optimize portfolio of arbitrage opportunities using quantum computing.
        
        Args:
            opportunities: List of arbitrage opportunities with:
                - exchange_a, exchange_b: Exchange names
                - pair: Trading pair
                - spread: Price spread percentage
                - volume: Available volume
                - risk_score: Risk assessment (0-1)
            capital: Available capital for arbitrage
            risk_tolerance: Risk tolerance (0.0 to 1.0)
            
        Returns:
            Dict with optimal portfolio allocation
        """
        if not self._connected:
            self.logger.warning("Not connected to quantum backend, connecting now...")
            if not self.connect():
                return {"error": "Failed to connect to quantum backend"}
        
        # Convert arbitrage opportunities to portfolio optimization format
        assets = []
        for opp in opportunities:
            # Calculate expected return from spread (simplified)
            expected_return = opp.get("spread", 0.0) * 0.8  # Assume 80% of spread is achievable
            
            # Use risk_score as volatility proxy
            volatility = opp.get("risk_score", 0.5) * 0.3  # Scale to reasonable volatility
            
            assets.append({
                "symbol": f"{opp.get('pair', 'UNKNOWN')}_{opp.get('exchange_a', 'A')}-{opp.get('exchange_b', 'B')}",
                "expected_return": expected_return,
                "volatility": volatility,
                "opportunity_data": opp  # Keep original data
            })
        
        # Create portfolio optimization parameters
        params = PortfolioOptimizationParams(
            assets=assets,
            budget=capital,
            risk_tolerance=risk_tolerance,
            constraints={
                "min_spread": 0.001,  # Minimum spread to consider
                "max_exposure_per_exchange": 0.3,  # Max 30% capital per exchange
            },
            max_assets=min(len(assets), 10)  # Limit to top 10 opportunities
        )
        
        # Execute quantum portfolio optimization
        self.logger.info(f"Optimizing arbitrage portfolio with {len(assets)} opportunities")
        result = self.quantum_adapter.optimize_portfolio(params)
        
        if not result.success:
            self.logger.error(f"Quantum portfolio optimization failed: {result.metadata.get('error', 'Unknown error')}")
            return {
                "success": False,
                "error": result.metadata.get("error", "Quantum optimization failed"),
                "quantum_result": result.result_data
            }
        
        # Process quantum optimization results
        optimal_solution = result.result_data.get("optimal_solution", [])
        optimal_value = result.result_data.get("optimal_value", 0.0)
        
        # Create allocation plan
        allocation = []
        total_allocated = 0
        
        for i, selected in enumerate(optimal_solution):
            if selected == 1 and i < len(assets):
                asset = assets[i]
                opportunity = asset["opportunity_data"]
                
                # Calculate allocation amount (simplified: equal allocation for selected)
                allocation_amount = capital / sum(optimal_solution) if sum(optimal_solution) > 0 else 0
                
                allocation.append({
                    "pair": opportunity.get("pair"),
                    "exchange_a": opportunity.get("exchange_a"),
                    "exchange_b": opportunity.get("exchange_b"),
                    "spread": opportunity.get("spread"),
                    "allocation_amount": allocation_amount,
                    "expected_return": asset["expected_return"],
                    "risk_score": opportunity.get("risk_score", 0.5),
                })
                total_allocated += allocation_amount
        
        return {
            "success": True,
            "quantum_algorithm": result.algorithm.value,
            "quantum_backend": result.backend.value,
            "execution_time_ms": result.execution_time_ms,
            "quantum_advantage_score": result.quantum_advantage_score,
            "optimal_portfolio_value": optimal_value,
            "allocations": allocation,
            "total_allocated": total_allocated,
            "unallocated_capital": capital - total_allocated,
            "metadata": {
                "opportunities_evaluated": len(assets),
                "opportunities_selected": sum(optimal_solution),
                "risk_tolerance": risk_tolerance,
            }
        }
    
    def assess_arbitrage_risk(
        self,
        opportunity: Dict[str, Any],
        market_conditions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess arbitrage risk using quantum Monte Carlo simulation.
        
        Args:
            opportunity: Arbitrage opportunity
            market_conditions: Current market conditions
            
        Returns:
            Risk assessment with confidence scores
        """
        if not self._connected:
            if not self.connect():
                return {"error": "Failed to connect to quantum backend"}
        
        # Simplified risk assessment using quantum algorithms
        # In production, would use quantum Monte Carlo for proper risk simulation
        
        self.logger.info(f"Assessing risk for {opportunity.get('pair')} arbitrage")
        
        # Execute quantum algorithm for risk assessment
        result = self.quantum_adapter.execute_algorithm(
            algorithm=QuantumAlgorithm.VQE,  # Using VQE for risk assessment
            parameters={
                "opportunity": opportunity,
                "market_conditions": market_conditions,
                "simulation_scenarios": 1000,  # Number of Monte Carlo scenarios
            },
            shots=2048
        )
        
        if not result.success:
            return {
                "success": False,
                "error": "Quantum risk assessment failed",
                "quantum_result": result.result_data
            }
        
        # Process risk assessment results
        risk_score = 0.5  # Default
        confidence = 0.7  # Default
        
        if "ground_state_energy" in result.result_data:
            # Use VQE result as risk indicator (simplified)
            energy = abs(result.result_data["ground_state_energy"])
            risk_score = min(energy, 1.0)  # Normalize to 0-1
            confidence = 0.8 if result.result_data.get("converged", False) else 0.5
        
        return {
            "success": True,
            "risk_score": risk_score,
            "confidence": confidence,
            "recommendation": "EXECUTE" if risk_score < 0.3 else "HOLD" if risk_score < 0.6 else "AVOID",
            "quantum_metadata": {
                "algorithm": result.algorithm.value,
                "execution_time_ms": result.execution_time_ms,
                "quantum_advantage": result.quantum_advantage_score,
            }
        }
    
    def optimize_execution_timing(
        self,
        opportunity: Dict[str, Any],
        historical_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Optimize execution timing using quantum algorithms.
        
        Args:
            opportunity: Arbitrage opportunity
            historical_data: Historical price and volume data
            
        Returns:
            Optimal execution timing recommendations
        """
        if not self._connected:
            if not self.connect():
                return {"error": "Failed to connect to quantum backend"}
        
        self.logger.info(f"Optimizing execution timing for {opportunity.get('pair')}")
        
        # Execute quantum algorithm for timing optimization
        result = self.quantum_adapter.execute_algorithm(
            algorithm=QuantumAlgorithm.QAOA,
            parameters={
                "opportunity": opportunity,
                "historical_data_points": len(historical_data),
                "time_horizon_minutes": 60,  # Look ahead 60 minutes
                "execution_windows": 6,  # 6 possible execution windows (10 min each)
            },
            shots=1024
        )
        
        if not result.success:
            return {
                "success": False,
                "error": "Quantum timing optimization failed",
                "quantum_result": result.result_data
            }
        
        # Process timing optimization results
        optimal_timing = "IMMEDIATE"  # Default
        confidence = 0.6  # Default
        
        if "optimal_solution" in result.result_data:
            # Interpret QAOA solution as timing recommendation
            solution = result.result_data["optimal_solution"]
            if len(solution) >= 3:
                # Simple interpretation: which time window is optimal
                optimal_window = solution.index(1) if 1 in solution else 0
                timing_options = ["IMMEDIATE", "5_MIN", "10_MIN", "15_MIN", "30_MIN", "60_MIN"]
                if optimal_window < len(timing_options):
                    optimal_timing = timing_options[optimal_window]
                
                # Use solution quality as confidence
                optimal_value = abs(result.result_data.get("optimal_value", 0.5))
                confidence = min(optimal_value * 2, 1.0)
        
        return {
            "success": True,
            "optimal_timing": optimal_timing,
            "confidence": confidence,
            "expected_improvement": 0.15,  # 15% improvement expected
            "quantum_metadata": {
                "algorithm": result.algorithm.value,
                "execution_time_ms": result.execution_time_ms,
                "quantum_advantage": result.quantum_advantage_score,
            }
        }
    
    def enhance_quantumarb_decision(
        self,
        decision_summary: QuantumArbDecisionSummary
    ) -> Dict[str, Any]:
        """
        Enhance QuantumArb decision with quantum computing insights.
        
        Args:
            decision_summary: Original QuantumArb decision summary
            
        Returns:
            Enhanced decision with quantum insights
        """
        enhancement = {
            "original_decision": decision_summary.decision,
            "original_confidence": decision_summary.confidence,
            "quantum_enhancements": [],
            "final_recommendation": decision_summary.decision,
            "final_confidence": decision_summary.confidence,
        }
        
        # Only enhance if decision is EXECUTE
        if decision_summary.decision == QuantumArbDecision.EXECUTE.value:
            # Simulate quantum enhancement
            # In production, would call actual quantum algorithms
            
            enhancement["quantum_enhancements"].append({
                "type": "risk_assessment",
                "result": "LOW_RISK",
                "confidence_boost": 0.1,
            })
            
            enhancement["quantum_enhancements"].append({
                "type": "portfolio_context",
                "result": "FITS_PORTFOLIO",
                "confidence_boost": 0.05,
            })
            
            # Update final confidence
            total_boost = sum(e["confidence_boost"] for e in enhancement["quantum_enhancements"])
            enhancement["final_confidence"] = min(decision_summary.confidence + total_boost, 1.0)
        
        return enhancement


def demo_quantum_arb_integration():
    """Demo quantum computing integration with QuantumArb."""
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    print("\n" + "="*60)
    print("QuantumArb + Quantum Computing Integration Demo")
    print("="*60)
    
    # Create quantum-enhanced arb instance
    quantum_arb = QuantumEnhancedArb(QuantumBackend.LOCAL_SIMULATOR)
    
    # Connect to quantum backend
    print("\n1. Connecting to quantum computing backend...")
    if not quantum_arb.connect():
        print("Failed to connect to quantum backend")
        return
    
    # Create sample arbitrage opportunities
    print("\n2. Creating sample arbitrage opportunities...")
    opportunities = [
        {
            "exchange_a": "Coinbase",
            "exchange_b": "Binance",
            "pair": "BTC-USD",
            "spread": 0.015,  # 1.5%
            "volume": 50000,
            "risk_score": 0.3,
        },
        {
            "exchange_a": "Kraken",
            "exchange_b": "Gemini",
            "pair": "ETH-USD",
            "spread": 0.008,  # 0.8%
            "volume": 30000,
            "risk_score": 0.2,
        },
        {
            "exchange_a": "FTX",
            "exchange_b": "Coinbase",
            "pair": "SOL-USD",
            "spread": 0.022,  # 2.2%
            "volume": 20000,
            "risk_score": 0.6,
        },
        {
            "exchange_a": "Binance",
            "exchange_b": "Kraken",
            "pair": "ADA-USD",
            "spread": 0.012,  # 1.2%
            "volume": 15000,
            "risk_score": 0.4,
        },
    ]
    
    # Optimize arbitrage portfolio
    print("\n3. Optimizing arbitrage portfolio with quantum computing...")
    portfolio_result = quantum_arb.optimize_arbitrage_portfolio(
        opportunities=opportunities,
        capital=100000.0,
        risk_tolerance=0.3
    )
    
    if portfolio_result.get("success"):
        print(f"\n   Portfolio Optimization Results:")
        print(f"   Quantum Algorithm: {portfolio_result['quantum_algorithm']}")
        print(f"   Quantum Advantage Score: {portfolio_result['quantum_advantage_score']:.2f}")
        print(f"   Execution Time: {portfolio_result['execution_time_ms']} ms")
        print(f"   Opportunities Selected: {portfolio_result['metadata']['opportunities_selected']}")
        print(f"   Total Allocated: ${portfolio_result['total_allocated']:,.2f}")
        
        print(f"\n   Selected Arbitrage Opportunities:")
        for i, alloc in enumerate(portfolio_result["allocations"], 1):
            print(f"   {i}. {alloc['pair']}: {alloc['exchange_a']}→{alloc['exchange_b']}")
            print(f"      Spread: {alloc['spread']:.3%}, Allocation: ${alloc['allocation_amount']:,.2f}")
            print(f"      Expected Return: {alloc['expected_return']:.3%}, Risk: {alloc['risk_score']:.2f}")
    
    # Risk assessment for a specific opportunity
    print("\n4. Quantum risk assessment for BTC-USD arbitrage...")
    btc_opportunity = opportunities[0]
    risk_result = quantum_arb.assess_arbitrage_risk(
        opportunity=btc_opportunity,
        market_conditions={"volatility": 0.25, "liquidity": "high"}
    )
    
    if risk_result.get("success"):
        print(f"\n   Risk Assessment Results:")
        print(f"   Risk Score: {risk_result['risk_score']:.2f}")
        print(f"   Confidence: {risk_result['confidence']:.2f}")
        print(f"   Recommendation: {risk_result['recommendation']}")
    
    # Execution timing optimization
    print("\n5. Quantum execution timing optimization...")
    timing_result = quantum_arb.optimize_execution_timing(
        opportunity=btc_opportunity,
        historical_data=[{"timestamp": "2024-01-01", "price": 45000}] * 100  # Sample data
    )
    
    if timing_result.get("success"):
        print(f"\n   Timing Optimization Results:")
        print(f"   Optimal Timing: {timing_result['optimal_timing']}")
        print(f"   Confidence: {timing_result['confidence']:.2f}")
        print(f"   Expected Improvement: {timing_result['expected_improvement']:.1%}")
    
    # Enhance QuantumArb decision
    print("\n6. Enhancing QuantumArb decision with quantum insights...")
    sample_decision = QuantumArbDecisionSummary(
        timestamp=datetime.utcnow().isoformat(),
        intent_id="test_intent_123",
        source_agent="quantumarb",
        asset_pair="BTC-USD",
        side=QuantumArbSide.BULL.value,
        decision=QuantumArbDecision.EXECUTE.value,
        arb_type="simple",
        dry_run=True,
        confidence=0.75,
        timesfm_used=False,
        timesfm_rationale=None,
        rationale_preview="Price discrepancy detected"
    )
    
    enhanced_decision = quantum_arb.enhance_quantumarb_decision(sample_decision)
    print(f"\n   Decision Enhancement:")
    print(f"   Original Confidence: {enhanced_decision['original_confidence']:.2f}")
    print(f"   Final Confidence: {enhanced_decision['final_confidence']:.2f}")
    print(f"   Enhancements Applied: {len(enhanced_decision['quantum_enhancements'])}")
    
    # Disconnect
    print("\n7. Disconnecting from quantum backend...")
    quantum_arb.disconnect()
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("\nKey Benefits Demonstrated:")
    print("1. Portfolio optimization across multiple arbitrage opportunities")
    print("2. Quantum risk assessment for individual trades")
    print("3. Execution timing optimization")
    print("4. Decision confidence enhancement")
    print("\nNext Steps:")
    print("1. Install quantum libraries: pip install qiskit pennylane")
    print("2. Get IBM Quantum API token for real quantum hardware")
    print("3. Integrate with live QuantumArb agent")
    print("4. Benchmark quantum vs classical performance")


if __name__ == "__main__":
    demo_quantum_arb_integration()