#!/usr/bin/env python3
"""
QuantumArb Evolution Module
Evolves QuantumArb trading algorithms for the ASI-Evolve system.
"""

import sys
import json
import random
import statistics
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add SIMP path to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Initialize availability flags
QUANTUMARB_AVAILABLE = False
TRADE_EXECUTOR_AVAILABLE = False

# Try to import QuantumArb modules with graceful fallback
try:
    # Try basic imports first
    from simp.organs.quantumarb.arb_detector import ArbDetector, ArbOpportunity, ArbType
    from simp.organs.quantumarb.exchange_connector import ExchangeConnector, StubExchangeConnector
    
    # Try to import TradeExecutor
    try:
        from simp.organs.quantumarb.executor import TradeExecutor
        TRADE_EXECUTOR_AVAILABLE = True
    except ImportError:
        logger.warning("TradeExecutor not available, using simulation mode")
        # Create dummy classes for simulation
        class TradeExecutor:
            def __init__(self, *args, **kwargs):
                pass
        
        class TradeRequest:
            def __init__(self, *args, **kwargs):
                pass
    
    # Try to import QuantumEnhancedArbDetector
    try:
        from simp.organs.quantumarb.quantum_enhanced_arb import QuantumEnhancedArbDetector
    except ImportError:
        logger.warning("QuantumEnhancedArbDetector not available")
        QuantumEnhancedArbDetector = None
    
    QUANTUMARB_AVAILABLE = True
    logger.info("QuantumArb modules loaded successfully")
    
except ImportError as e:
    logger.warning(f"QuantumArb modules not available: {e}")
    logger.info("Running in simulation-only mode")


class QuantumArbEvolution:
    """Evolves QuantumArb trading algorithms."""
    
    def __init__(self, population_size: int = 4, rounds: int = 5):
        """
        Initialize QuantumArb evolution.
        
        Args:
            population_size: Number of algorithms in each generation
            rounds: Number of evolution rounds
        """
        self.population_size = population_size
        self.rounds = rounds
        self.results_dir = Path("data/evolution_results")
        self.results_dir.mkdir(exist_ok=True)
        
        # Evolution parameters to optimize
        self.param_ranges = {
            "threshold_bps": (5.0, 50.0),      # Minimum spread in basis points
            "min_confidence": (0.5, 0.95),     # Minimum confidence score
            "max_position_per_market": (1000.0, 50000.0),  # Max position size
            "risk_tolerance": (0.1, 0.9),      # Risk tolerance (higher = more aggressive)
            "liquidity_weight": (0.1, 0.9),    # Weight given to liquidity in scoring
            "execution_speed_weight": (0.1, 0.9),  # Weight given to execution speed
        }
        
        # Initialize population
        self.population = self._initialize_population()
        
        # Track best performer
        self.best_algorithm = None
        self.best_score = -float('inf')
        
        # Simulation data (in production, this would be real/historical data)
        self.simulation_data = self._generate_simulation_data()
    
    def _initialize_population(self) -> List[Dict[str, float]]:
        """Initialize random population of algorithms."""
        population = []
        for _ in range(self.population_size):
            algorithm = {}
            for param, (min_val, max_val) in self.param_ranges.items():
                if param == "threshold_bps":
                    # Prefer lower thresholds for more opportunities
                    algorithm[param] = random.uniform(min_val, min_val * 2)
                elif param == "min_confidence":
                    # Start with moderate confidence
                    algorithm[param] = random.uniform(0.6, 0.8)
                elif param == "max_position_per_market":
                    # Start with moderate position sizes
                    algorithm[param] = random.uniform(5000.0, 15000.0)
                else:
                    algorithm[param] = random.uniform(min_val, max_val)
            population.append(algorithm)
        return population
    
    def _generate_simulation_data(self) -> List[Dict[str, Any]]:
        """Generate simulation data for testing evolution."""
        # In production, this would load historical market data
        # For now, generate synthetic opportunities
        opportunities = []
        
        # Generate 100 simulated arbitrage opportunities
        for i in range(100):
            opportunity = {
                "id": f"sim_opp_{i}",
                "type": random.choice(["cross_exchange", "triangular", "statistical"]),
                "spread_bps": random.uniform(5.0, 100.0),
                "confidence": random.uniform(0.3, 0.95),
                "liquidity_usd": random.uniform(1000.0, 100000.0),
                "execution_complexity": random.uniform(0.1, 0.9),
                "estimated_profit_usd": random.uniform(10.0, 1000.0),
                "risk_score": random.uniform(0.1, 0.8),
                "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 24))).isoformat()
            }
            opportunities.append(opportunity)
        
        return opportunities
    
    def _evaluate_algorithm(self, algorithm: Dict[str, float]) -> float:
        """
        Evaluate an algorithm's performance.
        
        Returns a fitness score (higher is better).
        """
        try:
            # Simulate trading with this algorithm
            total_profit = 0.0
            trades_executed = 0
            missed_opportunities = 0
            
            threshold_bps = algorithm["threshold_bps"]
            min_confidence = algorithm["min_confidence"]
            risk_tolerance = algorithm["risk_tolerance"]
            liquidity_weight = algorithm["liquidity_weight"]
            execution_speed_weight = algorithm["execution_speed_weight"]
            
            for opportunity in self.simulation_data:
                # Check if opportunity meets thresholds
                if opportunity["spread_bps"] < threshold_bps:
                    missed_opportunities += 1
                    continue
                
                if opportunity["confidence"] < min_confidence:
                    missed_opportunities += 1
                    continue
                
                # Calculate composite score
                risk_adjusted_profit = opportunity["estimated_profit_usd"] * (1 - opportunity["risk_score"])
                liquidity_score = min(1.0, opportunity["liquidity_usd"] / 50000.0)
                execution_score = 1.0 - opportunity["execution_complexity"]
                
                composite_score = (
                    risk_adjusted_profit * (1 - risk_tolerance) +
                    liquidity_score * liquidity_weight +
                    execution_score * execution_speed_weight
                )
                
                # Only execute if composite score is positive
                if composite_score > 0:
                    # Simulate profit with some noise
                    actual_profit = opportunity["estimated_profit_usd"] * random.uniform(0.8, 1.2)
                    total_profit += actual_profit
                    trades_executed += 1
            
            # Calculate fitness score
            if trades_executed == 0:
                return -100.0  # Penalize algorithms that don't trade
            
            # Average profit per trade
            avg_profit = total_profit / trades_executed
            
            # Success rate (opportunities captured)
            total_opportunities = len(self.simulation_data)
            success_rate = trades_executed / total_opportunities
            
            # Risk-adjusted return
            risk_adjusted_return = avg_profit * success_rate
            
            # Diversity bonus (capture different types of opportunities)
            # This encourages algorithms that work in various market conditions
            
            # Final fitness score
            fitness = risk_adjusted_return * 100  # Scale for readability
            
            # Add small random noise to break ties
            fitness += random.uniform(-0.01, 0.01)
            
            return fitness
            
        except Exception as e:
            logger.error(f"Error evaluating algorithm: {e}")
            return -float('inf')
    
    def _select_parents(self, scores: List[float]) -> List[Dict[str, float]]:
        """Select parents for next generation using tournament selection."""
        parents = []
        
        # Tournament selection
        tournament_size = min(3, len(self.population))
        for _ in range(self.population_size):
            # Randomly select tournament participants
            tournament_indices = random.sample(range(len(self.population)), tournament_size)
            tournament_scores = [scores[i] for i in tournament_indices]
            
            # Select the best from tournament
            best_index = tournament_indices[tournament_scores.index(max(tournament_scores))]
            parents.append(self.population[best_index])
        
        return parents
    
    def _crossover(self, parent1: Dict[str, float], parent2: Dict[str, float]) -> Dict[str, float]:
        """Create child algorithm through crossover."""
        child = {}
        
        # Uniform crossover
        for param in self.param_ranges.keys():
            if random.random() < 0.5:
                child[param] = parent1[param]
            else:
                child[param] = parent2[param]
        
        return child
    
    def _mutate(self, algorithm: Dict[str, float], mutation_rate: float = 0.1) -> Dict[str, float]:
        """Apply mutation to an algorithm."""
        mutated = algorithm.copy()
        
        for param, (min_val, max_val) in self.param_ranges.items():
            if random.random() < mutation_rate:
                # Gaussian mutation around current value
                current = mutated[param]
                std_dev = (max_val - min_val) * 0.1  # 10% of range
                new_value = current + random.gauss(0, std_dev)
                
                # Clamp to valid range
                mutated[param] = max(min_val, min(max_val, new_value))
        
        return mutated
    
    def evolve(self) -> Dict[str, Any]:
        """
        Run evolution process.
        
        Returns:
            Dictionary with evolution results
        """
        logger.info(f"Starting QuantumArb evolution with population {self.population_size}, rounds {self.rounds}")
        
        evolution_history = []
        
        for round_num in range(self.rounds):
            logger.info(f"Round {round_num + 1}/{self.rounds}")
            
            # Evaluate current population
            scores = []
            for i, algorithm in enumerate(self.population):
                score = self._evaluate_algorithm(algorithm)
                scores.append(score)
                logger.debug(f"  Algorithm {i+1}: score = {score:.2f}")
            
            # Update best performer
            best_round_score = max(scores)
            best_round_index = scores.index(best_round_score)
            
            if best_round_score > self.best_score:
                self.best_score = best_round_score
                self.best_algorithm = self.population[best_round_index].copy()
                logger.info(f"  New best algorithm found: score = {self.best_score:.2f}")
            
            # Record round results
            round_result = {
                "round": round_num + 1,
                "best_score": best_round_score,
                "average_score": statistics.mean(scores),
                "score_std": statistics.stdev(scores) if len(scores) > 1 else 0.0,
                "best_algorithm": self.population[best_round_index].copy(),
                "timestamp": datetime.utcnow().isoformat()
            }
            evolution_history.append(round_result)
            
            # Create next generation (except last round)
            if round_num < self.rounds - 1:
                # Select parents
                parents = self._select_parents(scores)
                
                # Create new population through crossover and mutation
                new_population = []
                
                # Elitism: keep best algorithm
                new_population.append(self.population[best_round_index])
                
                # Fill rest with offspring
                while len(new_population) < self.population_size:
                    parent1 = random.choice(parents)
                    parent2 = random.choice(parents)
                    child = self._crossover(parent1, parent2)
                    child = self._mutate(child)
                    new_population.append(child)
                
                self.population = new_population
        
        # Prepare final results
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "component": "quantumarb_trading",
            "experiment": "daily_quantumarb_evolution",
            "results": {
                "success": True,
                "final_best_score": self.best_score,
                "rounds_completed": self.rounds,
                "best_algorithm": self.best_algorithm,
                "evolution_history": evolution_history,
                "improvement_percent": 0.0,  # Will be calculated by comparison
                "parameters_optimized": list(self.param_ranges.keys())
            }
        }
        
        # Save results
        self._save_results(results)
        
        logger.info(f"Evolution completed. Best score: {self.best_score:.2f}")
        return results
    
    def _save_results(self, results: Dict[str, Any]) -> None:
        """Save evolution results to file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        filename = f"quantumarb_trading_daily_quantumarb_evolution_{timestamp}.json"
        filepath = self.results_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results saved to {filepath}")
    
    def get_algorithm_description(self, algorithm: Dict[str, float]) -> str:
        """Get human-readable description of an algorithm."""
        desc = []
        desc.append("QuantumArb Trading Algorithm:")
        desc.append(f"  - Threshold: {algorithm.get('threshold_bps', 0):.1f} bps")
        desc.append(f"  - Min Confidence: {algorithm.get('min_confidence', 0):.2f}")
        desc.append(f"  - Max Position: ${algorithm.get('max_position_per_market', 0):.0f}")
        desc.append(f"  - Risk Tolerance: {algorithm.get('risk_tolerance', 0):.2f}")
        desc.append(f"  - Liquidity Weight: {algorithm.get('liquidity_weight', 0):.2f}")
        desc.append(f"  - Execution Speed Weight: {algorithm.get('execution_speed_weight', 0):.2f}")
        return "\n".join(desc)


def run_quantumarb_evolution(
    population_size: int = 4,
    rounds: int = 5,
    save_results: bool = True
) -> Dict[str, Any]:
    """
    Run QuantumArb evolution.
    
    Args:
        population_size: Number of algorithms per generation
        rounds: Number of evolution rounds
        save_results: Whether to save results to file
        
    Returns:
        Evolution results
    """
    if not QUANTUMARB_AVAILABLE:
        logger.error("QuantumArb modules not available. Cannot run evolution.")
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "component": "quantumarb_trading",
            "experiment": "daily_quantumarb_evolution",
            "results": {
                "success": False,
                "error": "QuantumArb modules not available",
                "final_best_score": 0.0,
                "rounds_completed": 0
            }
        }
    
    try:
        # Initialize evolution
        evolution = QuantumArbEvolution(
            population_size=population_size,
            rounds=rounds
        )
        
        # Run evolution
        results = evolution.evolve()
        
        # Log best algorithm
        if results["results"]["success"] and results["results"]["best_algorithm"]:
            best_algo = results["results"]["best_algorithm"]
            logger.info("Best algorithm found:")
            logger.info(evolution.get_algorithm_description(best_algo))
        
        return results
        
    except Exception as e:
        logger.error(f"Error running QuantumArb evolution: {e}")
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "component": "quantumarb_trading",
            "experiment": "daily_quantumarb_evolution",
            "results": {
                "success": False,
                "error": str(e),
                "final_best_score": 0.0,
                "rounds_completed": 0
            }
        }


def main():
    """Main function for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run QuantumArb evolution")
    parser.add_argument("--population", type=int, default=4, help="Population size")
    parser.add_argument("--rounds", type=int, default=5, help="Number of evolution rounds")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("🧬 QuantumArb Evolution System")
    print("=" * 50)
    
    results = run_quantumarb_evolution(
        population_size=args.population,
        rounds=args.rounds
    )
    
    if results["results"]["success"]:
        print(f"✅ Evolution successful!")
        print(f"   Best score: {results['results']['final_best_score']:.2f}")
        print(f"   Rounds completed: {results['results']['rounds_completed']}")
        
        # Show best algorithm parameters
        if results["results"]["best_algorithm"]:
            evolution = QuantumArbEvolution()
            print("\n🏆 Best Algorithm:")
            print(evolution.get_algorithm_description(results["results"]["best_algorithm"]))
    else:
        print(f"❌ Evolution failed: {results['results'].get('error', 'Unknown error')}")
    
    return 0 if results["results"]["success"] else 1


if __name__ == "__main__":
    sys.exit(main())