"""
Quantum Computing Demo for SIMP Ecosystem

This demo shows how to use quantum computing capabilities within SIMP agents.
It demonstrates portfolio optimization, quantum ML, and integration patterns.
"""

import logging
from typing import Dict, Any
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from simp.organs.quantum import (
    QuantumBackend,
    QuantumAlgorithm,
    PortfolioOptimizationParams,
    QuantumMLParams,
    get_quantum_adapter,
)


def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def demo_portfolio_optimization():
    """Demo quantum portfolio optimization."""
    print("\n" + "="*60)
    print("DEMO: Quantum Portfolio Optimization")
    print("="*60)
    
    # Create sample portfolio data
    assets = [
        {"symbol": "AAPL", "expected_return": 0.12, "volatility": 0.18},
        {"symbol": "GOOGL", "expected_return": 0.15, "volatility": 0.22},
        {"symbol": "MSFT", "expected_return": 0.10, "volatility": 0.16},
        {"symbol": "TSLA", "expected_return": 0.25, "volatility": 0.35},
        {"symbol": "AMZN", "expected_return": 0.14, "volatility": 0.24},
    ]
    
    # Create portfolio optimization parameters
    params = PortfolioOptimizationParams(
        assets=assets,
        budget=100000.0,
        risk_tolerance=0.3,  # Moderate risk
        constraints={"sector_diversification": True},
        max_assets=3  # Select at most 3 assets
    )
    
    # Get quantum adapter (using local simulator for demo)
    print("\n1. Connecting to quantum backend...")
    adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
    
    if not adapter.connect():
        print("Failed to connect to quantum backend")
        return
    
    print("2. Performing quantum portfolio optimization...")
    result = adapter.optimize_portfolio(params)
    
    print("\n3. Optimization Results:")
    print(f"   Success: {result.success}")
    print(f"   Algorithm: {result.algorithm.value}")
    print(f"   Backend: {result.backend.value}")
    print(f"   Execution Time: {result.execution_time_ms} ms")
    print(f"   Quantum Advantage Score: {result.quantum_advantage_score:.2f}")
    
    if result.success and "optimal_solution" in result.result_data:
        optimal_solution = result.result_data["optimal_solution"]
        print(f"\n4. Optimal Portfolio Selection:")
        for i, selected in enumerate(optimal_solution):
            if selected == 1 and i < len(assets):
                asset = assets[i]
                print(f"   ✓ {asset['symbol']}: Expected Return: {asset['expected_return']:.1%}")
        
        if "optimal_value" in result.result_data:
            print(f"\n5. Portfolio Value: ${result.result_data['optimal_value']:.2f}")
    
    # Show health check
    print("\n6. Quantum Backend Health:")
    health = adapter.health_check()
    for key, value in health.items():
        print(f"   {key}: {value}")
    
    adapter.disconnect()


def demo_quantum_ml():
    """Demo quantum machine learning."""
    print("\n" + "="*60)
    print("DEMO: Quantum Machine Learning")
    print("="*60)
    
    # Create sample ML parameters
    params = QuantumMLParams(
        model_type="qnn",
        training_data=[],  # In real implementation, would have actual data
        test_data=[],      # In real implementation, would have actual data
        hyperparameters={
            "learning_rate": 0.01,
            "num_layers": 3,
            "batch_size": 32
        },
        quantum_circuit_depth=3
    )
    
    # Get quantum adapter
    print("\n1. Connecting to quantum backend...")
    adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
    
    if not adapter.connect():
        print("Failed to connect to quantum backend")
        return
    
    print("2. Performing quantum ML inference...")
    result = adapter.quantum_ml_inference(params)
    
    print("\n3. ML Inference Results:")
    print(f"   Success: {result.success}")
    print(f"   Algorithm: {result.algorithm.value}")
    print(f"   Backend: {result.backend.value}")
    print(f"   Execution Time: {result.execution_time_ms} ms")
    print(f"   Quantum Advantage Score: {result.quantum_advantage_score:.2f}")
    
    if result.success:
        result_data = result.result_data
        if "accuracy" in result_data:
            print(f"\n4. Model Accuracy: {result_data['accuracy']:.2%}")
        if "predictions" in result_data:
            print(f"   Sample Predictions: {result_data['predictions'][:5]}")
    
    adapter.disconnect()


def demo_quantum_arb_integration():
    """Demo how quantum computing integrates with QuantumArb agent."""
    print("\n" + "="*60)
    print("DEMO: QuantumArb Integration")
    print("="*60)
    
    print("\n1. Simulating QuantumArb decision enhancement...")
    
    # Sample arbitrage opportunities
    opportunities = [
        {"exchange_a": "Coinbase", "exchange_b": "Binance", "pair": "BTC-USD", "spread": 0.015},
        {"exchange_a": "Kraken", "exchange_b": "Gemini", "pair": "ETH-USD", "spread": 0.008},
        {"exchange_a": "FTX", "exchange_b": "Coinbase", "pair": "SOL-USD", "spread": 0.022},
    ]
    
    # Quantum optimization could help:
    # 1. Select best opportunities given capital constraints
    # 2. Optimize execution timing
    # 3. Manage risk across multiple arbitrage trades
    
    print("\n2. Quantum algorithms can enhance QuantumArb by:")
    print("   • Portfolio optimization across multiple arbitrage opportunities")
    print("   • Risk assessment using quantum Monte Carlo")
    print("   • Execution timing optimization")
    print("   • Cross-exchange correlation analysis")
    
    print("\n3. Example workflow:")
    print("   QuantumArb detects opportunities → Quantum optimization → Optimal trade execution")


def demo_ibm_quantum_setup():
    """Demo IBM Quantum Experience setup (requires API token)."""
    print("\n" + "="*60)
    print("DEMO: IBM Quantum Experience Setup")
    print("="*60)
    
    print("\n1. To use IBM Quantum Experience:")
    print("   • Sign up at: https://quantum-computing.ibm.com/")
    print("   • Get API token from Account Settings")
    print("   • Install: pip install qiskit qiskit-ibm-runtime")
    
    print("\n2. Configuration example:")
    print("""
    config = {
        "api_token": "your_ibm_quantum_api_token",
        "hub": "ibm-q",
        "group": "open", 
        "project": "main"
    }
    
    adapter = get_quantum_adapter(QuantumBackend.IBM_QUANTUM, config)
    adapter.connect()
    """)
    
    print("\n3. Available backends:")
    print("   • ibmq_quito (7 qubits)")
    print("   • ibmq_lima (5 qubits)")
    print("   • ibmq_belem (5 qubits)")
    print("   • Simulators (32+ qubits)")


def main():
    """Run all demos."""
    setup_logging()
    
    print("="*60)
    print("QUANTUM COMPUTING INTEGRATION DEMO")
    print("SIMP Multi-Agent System")
    print("="*60)
    
    try:
        # Run demos
        demo_portfolio_optimization()
        demo_quantum_ml()
        demo_quantum_arb_integration()
        demo_ibm_quantum_setup()
        
        print("\n" + "="*60)
        print("DEMO COMPLETE")
        print("="*60)
        print("\nNext steps:")
        print("1. Install quantum computing libraries:")
        print("   pip install qiskit pennylane")
        print("\n2. Get IBM Quantum API token:")
        print("   https://quantum-computing.ibm.com/")
        print("\n3. Integrate with QuantumArb agent:")
        print("   See simp/organs/quantum/quantum_arb_integration.py")
        
    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()