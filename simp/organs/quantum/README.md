# Quantum Computing Integration for SIMP Ecosystem

## Overview

This module provides quantum computing capabilities for the SIMP multi-agent system, allowing agents to leverage quantum advantage for optimization, machine learning, and complex calculations. The integration supports multiple quantum backends including IBM Quantum Experience, PennyLane, and local simulators.

## Features

- **Multiple Backend Support**: IBM Quantum, PennyLane, D-Wave, AWS Braket, local simulators
- **Quantum Algorithms**: QAOA, VQE, Quantum Neural Networks, Grover's Search
- **Portfolio Optimization**: Quantum-enhanced portfolio selection for arbitrage opportunities
- **Quantum ML**: Quantum machine learning for prediction and classification
- **Risk Assessment**: Quantum Monte Carlo simulations for risk analysis
- **Execution Timing**: Quantum optimization of trade execution timing

## Installation

### 1. Install Quantum Computing Libraries

```bash
# Core quantum computing libraries
pip install qiskit qiskit-ibm-runtime pennylane

# Optional: Additional backends
pip install amazon-braket-sdk dwave-ocean-sdk

# For development and testing
pip install pytest pytest-asyncio
```

### 2. Set Up IBM Quantum Experience (Free Tier)

1. Sign up at [IBM Quantum Experience](https://quantum-computing.ibm.com/)
2. Get your API token from Account Settings
3. Configure the adapter:

```python
config = {
    "api_token": "your_ibm_quantum_api_token",
    "hub": "ibm-q",
    "group": "open",
    "project": "main"
}
```

### 3. Verify Installation

```bash
# Run tests
python -m pytest tests/test_quantum_adapter.py -v

# Run demo
python simp/organs/quantum/demo.py

# Run QuantumArb integration demo
python simp/organs/quantum/quantum_arb_integration.py
```

## Quick Start

### Basic Usage

```python
from simp.organs.quantum import (
    QuantumBackend,
    QuantumAlgorithm,
    PortfolioOptimizationParams,
    get_quantum_adapter,
)

# Create quantum adapter
adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)

# Connect to quantum backend
adapter.connect()

# Execute quantum algorithm
result = adapter.execute_algorithm(
    algorithm=QuantumAlgorithm.QAOA,
    parameters={"test": "data"},
    shots=1024
)

print(f"Success: {result.success}")
print(f"Execution Time: {result.execution_time_ms} ms")
print(f"Quantum Advantage: {result.quantum_advantage_score}")

# Disconnect
adapter.disconnect()
```

### Portfolio Optimization

```python
from simp.organs.quantum import PortfolioOptimizationParams

# Define portfolio assets
assets = [
    {"symbol": "AAPL", "expected_return": 0.12, "volatility": 0.18},
    {"symbol": "GOOGL", "expected_return": 0.15, "volatility": 0.22},
]

# Create optimization parameters
params = PortfolioOptimizationParams(
    assets=assets,
    budget=100000.0,
    risk_tolerance=0.3,
    constraints={"sector_diversification": True},
    max_assets=2
)

# Optimize portfolio
result = adapter.optimize_portfolio(params)
```

### QuantumArb Integration

```python
from simp.organs.quantum.quantum_arb_integration import QuantumEnhancedArb

# Create quantum-enhanced arb instance
quantum_arb = QuantumEnhancedArb(QuantumBackend.LOCAL_SIMULATOR)
quantum_arb.connect()

# Optimize arbitrage portfolio
opportunities = [
    {
        "exchange_a": "Coinbase",
        "exchange_b": "Binance", 
        "pair": "BTC-USD",
        "spread": 0.015,
        "volume": 50000,
        "risk_score": 0.3,
    }
]

portfolio_result = quantum_arb.optimize_arbitrage_portfolio(
    opportunities=opportunities,
    capital=100000.0,
    risk_tolerance=0.3
)

quantum_arb.disconnect()
```

## Architecture

### Core Components

1. **QuantumAdapter**: Abstract base class for all quantum backends
2. **IBMQuantumAdapter**: IBM Quantum Experience integration
3. **PennyLaneAdapter**: PennyLane quantum machine learning
4. **LocalSimulatorAdapter**: Local simulator for testing
5. **QuantumJob**: Job management and tracking
6. **QuantumResult**: Standardized result format

### Data Flow

```
SIMP Agent → Quantum Intent → Quantum Adapter → 
Quantum Backend (IBM/PennyLane/etc.) → Results → Agent Response
```

### Supported Algorithms

| Algorithm | Use Case | Backends |
|-----------|----------|----------|
| QAOA | Portfolio Optimization | All |
| VQE | Risk Assessment | All |
| QNN | Machine Learning | PennyLane, IBM |
| Grover | Database Search | IBM, Simulators |
| QMC | Monte Carlo Simulation | All |

## Integration with SIMP Agents

### QuantumArb Agent Enhancement

The quantum computing module provides several enhancements for QuantumArb:

1. **Portfolio Optimization**: Select optimal arbitrage opportunities given capital constraints
2. **Risk Assessment**: Quantum Monte Carlo simulations for trade risk
3. **Execution Timing**: Optimize when to execute trades
4. **Confidence Boosting**: Enhance decision confidence with quantum insights

### Example: Enhanced QuantumArb Decision

```python
from simp.organs.quantumarb import QuantumArbDecisionSummary
from simp.organs.quantum.quantum_arb_integration import QuantumEnhancedArb

# Original QuantumArb decision
decision = QuantumArbDecisionSummary(...)

# Enhance with quantum computing
quantum_arb = QuantumEnhancedArb()
enhanced = quantum_arb.enhance_quantumarb_decision(decision)

print(f"Original confidence: {enhanced['original_confidence']}")
print(f"Enhanced confidence: {enhanced['final_confidence']}")
```

## Configuration

### Backend Configuration

```python
# IBM Quantum Configuration
ibm_config = {
    "api_token": "your_token_here",
    "hub": "ibm-q",
    "group": "open",
    "project": "main",
    "backend": "ibmq_quito"  # Optional: specific backend
}

# PennyLane Configuration
pennylane_config = {
    "device": "default.qubit",
    "shots": 1024,
}

# Local Simulator Configuration
simulator_config = {
    "noise_model": None,  # Optional: add noise for realistic simulation
    "seed": 42,  # Random seed for reproducibility
}
```

### Environment Variables

```bash
# IBM Quantum
export IBM_QUANTUM_TOKEN="your_token_here"
export IBM_QUANTUM_HUB="ibm-q"
export IBM_QUANTUM_GROUP="open"
export IBM_QUANTUM_PROJECT="main"

# AWS Braket
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export AWS_REGION="us-east-1"

# D-Wave
export DWAVE_API_TOKEN="your_token"
export DWAVE_SOLVER="Advantage_system4.1"
```

## Performance Considerations

### Quantum Advantage

The system calculates a `quantum_advantage_score` (0-1) for each computation:
- **0.0-0.3**: Minimal advantage (simulator or small problems)
- **0.3-0.7**: Moderate advantage (hybrid quantum-classical)
- **0.7-1.0**: Significant advantage (real quantum hardware)

### Execution Times

| Backend | Typical Execution Time | Cost |
|---------|----------------------|------|
| Local Simulator | 100-500 ms | Free |
| IBM Simulator | 1-5 seconds | Free |
| IBM Real Hardware | 30-300 seconds | Free tier: 10 min/month |
| AWS Braket | 10-60 seconds | $0.30-$3.00 per task-hour |
| D-Wave Leap | 5-30 seconds | Free: 1 min/month |

### Error Handling

The system includes comprehensive error handling:
- Connection failures
- Job timeouts
- Quantum hardware errors
- Result validation

## Testing

### Running Tests

```bash
# Run all quantum tests
python -m pytest tests/test_quantum_adapter.py -v

# Run with coverage
python -m pytest tests/test_quantum_adapter.py --cov=simp.organs.quantum

# Run integration tests
python -m pytest tests/test_quantum_arb_integration.py -v
```

### Test Structure

- **Unit Tests**: Individual component testing
- **Integration Tests**: Backend integration testing
- **Performance Tests**: Execution time and advantage measurement
- **Error Tests**: Failure scenario testing

## Deployment

### Production Considerations

1. **API Key Management**: Use environment variables or secret management
2. **Rate Limiting**: Respect quantum backend rate limits
3. **Result Caching**: Cache quantum results for repeated queries
4. **Fallback Strategies**: Fall back to classical algorithms if quantum fails
5. **Monitoring**: Track quantum job success rates and execution times

### Scaling

- **Batch Processing**: Queue multiple quantum jobs
- **Parallel Execution**: Use multiple quantum backends simultaneously
- **Hybrid Computing**: Combine quantum and classical computation
- **Result Aggregation**: Combine results from multiple quantum runs

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure quantum libraries are installed
2. **Connection Failures**: Check API tokens and network connectivity
3. **Job Timeouts**: Reduce problem size or use simulator
4. **Result Errors**: Validate input parameters and algorithm compatibility

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

adapter = get_quantum_adapter(QuantumBackend.LOCAL_SIMULATOR)
adapter.connect()
```

## Roadmap

### Phase 1: Foundation (Complete)
- [x] Basic quantum adapter architecture
- [x] Local simulator implementation
- [x] Core quantum algorithms
- [x] Basic testing framework

### Phase 2: Integration (Current)
- [ ] IBM Quantum Experience integration
- [ ] PennyLane quantum ML integration
- [ ] QuantumArb agent enhancement
- [ ] Performance benchmarking

### Phase 3: Advanced Features
- [ ] Multiple backend support (AWS Braket, D-Wave)
- [ ] Quantum error correction
- [ ] Quantum circuit optimization
- [ ] Advanced quantum algorithms

### Phase 4: Production
- [ ] Production deployment
- [ ] Monitoring and alerting
- [ ] Cost optimization
- [ ] User documentation

## Contributing

### Development Setup

1. Clone the repository
2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Set up quantum computing accounts
4. Run tests:
   ```bash
   python -m pytest tests/ -v
   ```

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Write comprehensive docstrings
- Include unit tests for new features

### Pull Request Process

1. Create a feature branch
2. Add tests for new functionality
3. Ensure all tests pass
4. Update documentation
5. Submit pull request

## License

This module is part of the SIMP ecosystem and follows the same licensing terms.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review test cases for usage examples
3. Contact the SIMP development team
4. Refer to quantum computing platform documentation

## References

- [IBM Quantum Documentation](https://quantum-computing.ibm.com/docs/)
- [PennyLane Documentation](https://pennylane.ai/docs/)
- [Qiskit Documentation](https://qiskit.org/documentation/)
- [Quantum Algorithm Zoo](https://quantumalgorithmzoo.org/)

---

*Last Updated: 2026-04-12*
*Version: 1.0.0*
*Compatible with: SIMP A2A Core v0.7.0*