"""
Quantum-Enhanced QuantumArb Agent

This module integrates quantum intelligence with the QuantumArb agent,
providing quantum-enhanced arbitrage detection and execution.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json

from .arb_detector import ArbDetector, ArbOpportunity, create_detector
from .executor import TradeExecutor, TradeRequest, TradeResult, create_executor
from .pnl_ledger import PnLLedger
from ..quantum_intelligence import (
    QuantumIntelligentAgent,
    QuantumProblemType,
    CircuitDesignStrategy
)


class QuantumEnhancedArbDetector:
    """Quantum-enhanced arbitrage detector."""
    
    def __init__(
        self,
        exchange_configs: List[Dict[str, Any]],
        quantum_agent_id: str = "quantum_arb_enhanced",
        quantum_intelligence_level: str = "quantum_aware"
    ):
        self.logger = logging.getLogger("quantum.enhanced.arb")
        
        # Initialize traditional arb detector
        # Note: For now, we'll create a minimal detector for testing
        # In production, we would need actual exchange connectors
        from .exchange_connector import create_stub_connector
        
        # Create mock exchanges for testing
        exchanges = {}
        for config in exchange_configs:
            exchange_id = config.get("exchange_id", f"exchange_{len(exchanges)}")
            # Create a stub exchange connector
            exchanges[exchange_id] = create_stub_connector(
                name=exchange_id,
                prices={market: 100.0 for market in config.get("markets", [])},  # Default prices
                fee_rate=0.001,
                balances={"USD": 10000.0, "BTC": 1.0}
            )
        
        self.traditional_detector = create_detector(
            exchanges=exchanges,
            threshold_bps=5.0,  # Minimum spread in basis points
            min_confidence=0.7,
            max_position_per_market=1000.0
        )
        
        # Initialize quantum intelligent agent
        self.quantum_agent = QuantumIntelligentAgent(
            agent_id=quantum_agent_id,
            initial_level=quantum_intelligence_level
        )
        
        # Performance tracking
        self.quantum_enhancements_applied = 0
        self.quantum_advantage_history: List[float] = []
        self.enhanced_decisions: List[Dict[str, Any]] = []
        
        self.logger.info(f"Created quantum-enhanced arb detector with {quantum_intelligence_level} intelligence")
    
    def scan_markets_with_quantum_enhancement(
        self,
        markets: List[str],
        capital: float = 10000.0,
        risk_tolerance: float = 0.3,
        use_quantum: bool = True
    ) -> Dict[str, Any]:
        """Scan markets with quantum-enhanced opportunity detection."""
        self.logger.info(f"Scanning {len(markets)} markets with quantum enhancement: {use_quantum}")
        
        # Step 1: Traditional arbitrage detection
        # Get exchange names from detector
        exchange_names = list(self.traditional_detector.exchanges.keys())
        
        traditional_opportunities = self.traditional_detector.scan_markets(
            markets=markets,
            exchanges=exchange_names,
            quantity=1.0  # Reference quantity
        )
        
        if not traditional_opportunities:
            return {
                "opportunities": [],
                "quantum_enhanced": False,
                "quantum_advantage": 0.0,
                "message": "No arbitrage opportunities found"
            }
        
        if not use_quantum:
            # Return traditional opportunities without quantum enhancement
            return {
                "opportunities": [opp.to_dict() for opp in traditional_opportunities],
                "quantum_enhanced": False,
                "quantum_advantage": 0.0,
                "message": "Traditional arbitrage detection only"
            }
        
        # Step 2: Quantum enhancement
        quantum_result = self._apply_quantum_enhancement(
            traditional_opportunities=traditional_opportunities,
            capital=capital,
            risk_tolerance=risk_tolerance
        )
        
        # Step 3: Combine results
        enhanced_opportunities = self._create_enhanced_opportunities(
            traditional_opportunities,
            quantum_result
        )
        
        # Track performance
        self.quantum_enhancements_applied += 1
        self.quantum_advantage_history.append(quantum_result["quantum_advantage"])
        self.enhanced_decisions.append({
            "timestamp": datetime.utcnow().isoformat(),
            "opportunity_count": len(traditional_opportunities),
            "quantum_advantage": quantum_result["quantum_advantage"],
            "recommendations": quantum_result["quantum_allocation"]
        })
        
        result = {
            "opportunities": enhanced_opportunities,
            "quantum_enhanced": True,
            "quantum_advantage": quantum_result["quantum_advantage"],
            "quantum_recommendations": quantum_result["quantum_allocation"],
            "quantum_insights": [insight.insight_text for insight in quantum_result.get("insights", [])],
            "traditional_opportunities": [opp.to_dict() for opp in traditional_opportunities],
            "message": f"Found {len(traditional_opportunities)} opportunities, quantum advantage: {quantum_result['quantum_advantage']:.3f}"
        }
        
        self.logger.info(f"Quantum enhancement applied: {quantum_result['quantum_advantage']:.3f} advantage")
        
        return result
    
    def execute_quantum_enhanced_arbitrage(
        self,
        opportunity: Dict[str, Any],
        executor: TradeExecutor,
        use_quantum_recommendation: bool = True
    ) -> Dict[str, Any]:
        """Execute arbitrage with quantum-enhanced parameters."""
        self.logger.info(f"Executing quantum-enhanced arbitrage for {opportunity.get('pair', 'unknown')}")
        
        # Extract execution parameters
        pair = opportunity.get("pair", "")
        exchange_a = opportunity.get("exchange_a", "")
        exchange_b = opportunity.get("exchange_b", "")
        spread_bps = opportunity.get("spread_bps", 0.0)
        quantity = opportunity.get("recommended_quantity", opportunity.get("quantity", 0.0))
        
        # Apply quantum timing optimization if available
        execution_timing = "immediate"
        if use_quantum_recommendation and "quantum_timing" in opportunity:
            execution_timing = opportunity["quantum_timing"]
            self.logger.info(f"Using quantum timing optimization: {execution_timing}")
        
        # Apply quantum risk adjustment if available
        risk_adjustment = 1.0
        if use_quantum_recommendation and "quantum_risk_adjustment" in opportunity:
            risk_adjustment = opportunity["quantum_risk_adjustment"]
            quantity = quantity * risk_adjustment
            self.logger.info(f"Applying quantum risk adjustment: {risk_adjustment:.3f}")
        
        # Create trade request
        trade_request = TradeRequest(
            pair=pair,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            quantity=quantity,
            expected_profit_bps=spread_bps
        )
        
        # Execute trade
        try:
            trade_result = executor.execute_trade(trade_request)
            
            # Learn from execution outcome
            self._learn_from_execution(
                opportunity=opportunity,
                trade_result=trade_result,
                used_quantum=use_quantum_recommendation
            )
            
            execution_result = {
                "success": True,
                "trade_result": trade_result.to_dict() if hasattr(trade_result, 'to_dict') else vars(trade_result),
                "quantum_enhanced": use_quantum_recommendation,
                "quantum_parameters_applied": {
                    "timing": execution_timing,
                    "risk_adjustment": risk_adjustment,
                    "quantity_adjusted": quantity != opportunity.get("quantity", 0.0)
                },
                "execution_time": datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Quantum-enhanced execution successful: {trade_result.profit_usd:.2f} USD profit")
            
        except Exception as e:
            self.logger.error(f"Quantum-enhanced execution failed: {str(e)}")
            
            # Learn from failure
            self._learn_from_failure(opportunity, str(e), use_quantum_recommendation)
            
            execution_result = {
                "success": False,
                "error": str(e),
                "quantum_enhanced": use_quantum_recommendation,
                "execution_time": datetime.utcnow().isoformat()
            }
        
        return execution_result
    
    def optimize_portfolio_with_quantum(
        self,
        opportunities: List[Dict[str, Any]],
        capital: float,
        risk_tolerance: float = 0.3,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Optimize arbitrage portfolio using quantum intelligence."""
        self.logger.info(f"Optimizing portfolio with {len(opportunities)} opportunities, capital: ${capital:,.2f}")
        
        constraints = constraints or {
            "max_positions": 5,
            "min_diversification": 0.3,
            "max_risk_per_trade": 0.2
        }
        
        # Convert opportunities to quantum problem
        quantum_result = self.quantum_agent.generate_quantum_arb_recommendations(
            arbitrage_opportunities=opportunities,
            capital=capital,
            risk_tolerance=risk_tolerance
        )
        
        # Extract portfolio allocation
        portfolio_allocation = quantum_result["quantum_allocation"]
        
        # Calculate portfolio metrics
        portfolio_metrics = self._calculate_portfolio_metrics(
            portfolio_allocation,
            opportunities,
            capital
        )
        
        # Create optimized portfolio
        optimized_portfolio = {
            "allocations": portfolio_allocation,
            "metrics": portfolio_metrics,
            "quantum_advantage": quantum_result["quantum_advantage"],
            "insights": quantum_result.get("insights", []),
            "risk_assessment": quantum_result.get("risk_assessment", {}),
            "constraints": constraints,
            "optimization_time": datetime.utcnow().isoformat()
        }
        
        # Learn from portfolio optimization
        learning_experience = self.quantum_agent.evolver.learn_from_experience(
            skill_id="portfolio_optimization",
            problem_type=QuantumProblemType.ARBITRAGE,
            outcome="success",
            performance_score=quantum_result["quantum_advantage"],
            quantum_advantage=quantum_result["quantum_advantage"],
            insights=[insight.insight_text for insight in quantum_result.get("insights", [])],
            metadata={
                "opportunity_count": len(opportunities),
                "capital": capital,
                "risk_tolerance": risk_tolerance,
                "portfolio_metrics": portfolio_metrics
            }
        )
        
        self.logger.info(f"Portfolio optimized with {len(portfolio_allocation)} allocations, "
                        f"expected return: {portfolio_metrics.get('expected_return', 0):.3%}")
        
        return optimized_portfolio
    
    def get_quantum_intelligence_state(self) -> Dict[str, Any]:
        """Get current state of quantum intelligence."""
        agent_state = self.quantum_agent.get_current_state()
        
        return {
            "agent_id": agent_state.agent_id,
            "intelligence_level": agent_state.intelligence_level.value,
            "quantum_intuition": agent_state.quantum_intuition_score,
            "skill_count": len(agent_state.quantum_skills),
            "average_skill_level": sum(s.skill_level for s in agent_state.quantum_skills) / len(agent_state.quantum_skills) if agent_state.quantum_skills else 0,
            "circuit_designs": len(agent_state.circuit_designs),
            "insights_generated": len(agent_state.insights),
            "quantum_enhancements_applied": self.quantum_enhancements_applied,
            "average_quantum_advantage": sum(self.quantum_advantage_history) / len(self.quantum_advantage_history) if self.quantum_advantage_history else 0,
            "enhanced_decisions_count": len(self.enhanced_decisions)
        }
    
    def evolve_quantum_skills(self, focus_area: Optional[str] = None) -> Dict[str, Any]:
        """Evolve quantum skills for arbitrage."""
        self.logger.info(f"Evolving quantum skills for arbitrage, focus: {focus_area or 'general'}")
        
        evolution_result = self.quantum_agent.optimize_quantum_skills(
            problem_type=QuantumProblemType.ARBITRAGE,
            target_intelligence_level="quantum_fluent"
        )
        
        # Track skill evolution
        skill_evolution = {
            "timestamp": datetime.utcnow().isoformat(),
            "focus_area": focus_area,
            "skill_gaps": evolution_result["skill_gaps"],
            "patterns_identified": evolution_result["patterns_identified"],
            "optimized_strategy": evolution_result["optimized_strategy"],
            "novel_algorithm": evolution_result["novel_algorithm"].circuit_id if evolution_result["novel_algorithm"] else None
        }
        
        self.logger.info(f"Quantum skills evolved, found {len(evolution_result['skill_gaps'].get('missing_skills', []))} missing skills")
        
        return skill_evolution
    
    def _apply_quantum_enhancement(
        self,
        traditional_opportunities: List[ArbOpportunity],
        capital: float,
        risk_tolerance: float
    ) -> Dict[str, Any]:
        """Apply quantum enhancement to traditional arbitrage opportunities."""
        # Convert opportunities to dictionary format
        opportunities_dict = []
        for opp in traditional_opportunities:
            opp_dict = opp.to_dict()
            # Add additional fields for quantum analysis
            opp_dict.update({
                "estimated_profit_usd": opp.estimated_profit_usd,
                "risk_score": self._calculate_risk_score(opp),
                "liquidity_score": self._calculate_liquidity_score(opp),
                "execution_complexity": self._calculate_execution_complexity(opp)
            })
            opportunities_dict.append(opp_dict)
        
        # Apply quantum intelligence
        quantum_result = self.quantum_agent.generate_quantum_arb_recommendations(
            arbitrage_opportunities=opportunities_dict,
            capital=capital,
            risk_tolerance=risk_tolerance
        )
        
        return quantum_result
    
    def _create_enhanced_opportunities(
        self,
        traditional_opportunities: List[ArbOpportunity],
        quantum_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create enhanced opportunities by combining traditional and quantum insights."""
        enhanced_opportunities = []
        quantum_allocations = quantum_result.get("quantum_allocation", [])
        
        # Create mapping from opportunity index to quantum allocation
        allocation_map = {}
        for alloc in quantum_allocations:
            idx = alloc.get("opportunity_index")
            if idx is not None:
                allocation_map[idx] = alloc
        
        for i, opp in enumerate(traditional_opportunities):
            opp_dict = opp.to_dict()
            
            # Add quantum enhancement data if available
            if i in allocation_map:
                quantum_alloc = allocation_map[i]
                opp_dict.update({
                    "quantum_enhanced": True,
                    "quantum_allocation_amount": quantum_alloc.get("allocation_amount", 0),
                    "quantum_selection_confidence": quantum_alloc.get("selection_confidence", 0.5),
                    "quantum_expected_return": quantum_alloc.get("expected_return", 0),
                    "quantum_risk_adjustment": self._calculate_risk_adjustment(quantum_alloc),
                    "quantum_timing": self._determine_optimal_timing(opp, quantum_alloc)
                })
            else:
                opp_dict["quantum_enhanced"] = False
            
            enhanced_opportunities.append(opp_dict)
        
        return enhanced_opportunities
    
    def _learn_from_execution(
        self,
        opportunity: Dict[str, Any],
        trade_result: TradeResult,
        used_quantum: bool
    ):
        """Learn from execution outcome to improve quantum intelligence."""
        # Calculate performance metrics
        performance_score = self._calculate_execution_performance(opportunity, trade_result)
        quantum_advantage = opportunity.get("quantum_advantage", 0.0) if used_quantum else 0.0
        
        # Extract insights
        insights = []
        if trade_result.profit_usd > 0:
            insights.append(f"Successful arbitrage execution: ${trade_result.profit_usd:.2f} profit")
        else:
            insights.append(f"Unsuccessful execution: ${trade_result.profit_usd:.2f} profit")
        
        # Learn from experience
        if used_quantum:
            self.quantum_agent.evolver.learn_from_experience(
                skill_id="arbitrage_execution",
                problem_type=QuantumProblemType.ARBITRAGE,
                outcome="success" if trade_result.profit_usd > 0 else "failure",
                performance_score=performance_score,
                quantum_advantage=quantum_advantage,
                insights=insights,
                metadata={
                    "opportunity": opportunity.get("pair", ""),
                    "profit_usd": trade_result.profit_usd,
                    "execution_time_ms": getattr(trade_result, 'execution_time_ms', 0),
                    "used_quantum": used_quantum
                }
            )
    
    def _learn_from_failure(
        self,
        opportunity: Dict[str, Any],
        error_message: str,
        used_quantum: bool
    ):
        """Learn from execution failure."""
        if used_quantum:
            self.quantum_agent.evolver.learn_from_experience(
                skill_id="arbitrage_execution",
                problem_type=QuantumProblemType.ARBITRAGE,
                outcome="failure",
                performance_score=0.1,  # Low score for failure
                quantum_advantage=0.0,
                insights=[f"Execution failed: {error_message}"],
                metadata={
                    "opportunity": opportunity.get("pair", ""),
                    "error": error_message,
                    "used_quantum": used_quantum
                }
            )
    
    def _calculate_portfolio_metrics(
        self,
        allocations: List[Dict[str, Any]],
        opportunities: List[Dict[str, Any]],
        capital: float
    ) -> Dict[str, Any]:
        """Calculate portfolio performance metrics."""
        if not allocations:
            return {
                "expected_return": 0.0,
                "risk_score": 0.0,
                "diversification": 0.0,
                "capital_utilization": 0.0
            }
        
        total_allocated = sum(alloc.get("allocation_amount", 0) for alloc in allocations)
        capital_utilization = total_allocated / capital if capital > 0 else 0.0
        
        # Calculate expected return
        expected_return = 0.0
        for alloc in allocations:
            idx = alloc.get("opportunity_index")
            if idx is not None and idx < len(opportunities):
                opportunity = opportunities[idx]
                allocation_amount = alloc.get("allocation_amount", 0)
                spread = opportunity.get("spread", 0.0)
                expected_return += allocation_amount * spread * 0.8  # Assume 80% of spread achievable
        
        expected_return_rate = expected_return / total_allocated if total_allocated > 0 else 0.0
        
        # Calculate risk score (simplified)
        risk_scores = []
        for alloc in allocations:
            idx = alloc.get("opportunity_index")
            if idx is not None and idx < len(opportunities):
                risk_score = opportunities[idx].get("risk_score", 0.5)
                weight = alloc.get("allocation_amount", 0) / total_allocated if total_allocated > 0 else 0
                risk_scores.append(risk_score * weight)
        
        portfolio_risk = sum(risk_scores) if risk_scores else 0.5
        
        # Calculate diversification
        position_count = len(allocations)
        max_positions = min(10, len(opportunities))
        diversification = position_count / max_positions if max_positions > 0 else 0.0
        
        return {
            "expected_return": expected_return_rate,
            "risk_score": portfolio_risk,
            "diversification": diversification,
            "capital_utilization": capital_utilization,
            "total_allocated": total_allocated,
            "position_count": position_count
        }
    
    def _calculate_risk_score(self, opportunity: ArbOpportunity) -> float:
        """Calculate risk score for an opportunity."""
        # Simplified risk calculation
        risk_factors = []
        
        # Spread-based risk (higher spread = higher risk)
        spread_risk = min(1.0, opportunity.spread_bps / 50.0)  # Normalize to 0-1
        risk_factors.append(spread_risk * 0.4)
        
        # Liquidity risk (lower liquidity = higher risk)
        liquidity_risk = 0.5  # Default
        if hasattr(opportunity, 'volume_usd'):
            if opportunity.volume_usd < 10000:
                liquidity_risk = 0.8
            elif opportunity.volume_usd < 50000:
                liquidity_risk = 0.6
            else:
                liquidity_risk = 0.3
        risk_factors.append(liquidity_risk * 0.3)
        
        # Execution complexity risk
        complexity_risk = 0.5  # Default
        if opportunity.exchange_a != opportunity.exchange_b:
            complexity_risk = 0.7  # Cross-exchange adds complexity
        risk_factors.append(complexity_risk * 0.3)
        
        return sum(risk_factors)
    
    def _calculate_liquidity_score(self, opportunity: ArbOpportunity) -> float:
        """Calculate liquidity score for an opportunity."""
        # Simplified liquidity calculation
        if hasattr(opportunity, 'volume_usd'):
            if opportunity.volume_usd > 100000:
                return 0.9
            elif opportunity.volume_usd > 50000:
                return 0.7
            elif opportunity.volume_usd > 10000:
                return 0.5
            else:
                return 0.3
        
        return 0.5  # Default
    
    def _calculate_execution_complexity(self, opportunity: ArbOpportunity) -> float:
        """Calculate execution complexity for an opportunity."""
        complexity = 0.5  # Base complexity
        
        # Cross-exchange adds complexity
        if opportunity.exchange_a != opportunity.exchange_b:
            complexity += 0.3
        
        # Large quantity adds complexity
        if hasattr(opportunity, 'quantity') and opportunity.quantity > 100:
            complexity += 0.2
        
        return min(1.0, complexity)
    
    def _calculate_risk_adjustment(self, quantum_allocation: Dict[str, Any]) -> float:
        """Calculate risk adjustment factor from quantum allocation."""
        confidence = quantum_allocation.get("selection_confidence", 0.5)
        # Higher confidence = less risk adjustment (closer to 1.0)
        risk_adjustment = 0.5 + (confidence * 0.5)  # Map 0-1 confidence to 0.5-1.0 adjustment
        return risk_adjustment
    
    def _determine_optimal_timing(
        self,
        opportunity: ArbOpportunity,
        quantum_allocation: Dict[str, Any]
    ) -> str:
        """Determine optimal execution timing based on quantum analysis."""
        confidence = quantum_allocation.get("selection_confidence", 0.5)
        
        if confidence > 0.8:
            return "immediate"  # High confidence = execute immediately
        elif confidence > 0.6:
            return "aggressive"  # Moderate confidence = aggressive timing
        else:
            return "conservative"  # Low confidence = conservative timing
    
    def _calculate_execution_performance(
        self,
        opportunity: Dict[str, Any],
        trade_result: TradeResult
    ) -> float:
        """Calculate execution performance score."""
        # Simplified performance calculation
        expected_profit = opportunity.get("estimated_profit_usd", 0)
        actual_profit = trade_result.profit_usd
        
        if expected_profit > 0:
            performance_ratio = actual_profit / expected_profit
            # Cap at 1.0 (100% of expected profit)
            performance_score = min(1.0, performance_ratio)
        else:
            performance_score = 0.5  # Default for unknown expected profit
        
        # Adjust for execution time
        execution_time_ms = getattr(trade_result, 'execution_time_ms', 1000)
        if execution_time_ms < 500:
            performance_score *= 1.1  # Bonus for fast execution
        elif execution_time_ms > 2000:
            performance_score *= 0.9  # Penalty for slow execution
        
        return max(0.0, min(1.0, performance_score))


def create_quantum_enhanced_detector(
    exchange_configs: List[Dict[str, Any]],
    quantum_agent_id: str = "quantum_arb_enhanced",
    quantum_intelligence_level: str = "quantum_aware"
) -> QuantumEnhancedArbDetector:
    """Create a quantum-enhanced arbitrage detector."""
    return QuantumEnhancedArbDetector(
        exchange_configs=exchange_configs,
        quantum_agent_id=quantum_agent_id,
        quantum_intelligence_level=quantum_intelligence_level
    )