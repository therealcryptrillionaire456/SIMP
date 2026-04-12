# KashClaw Execution Mapping Specification

## Overview

KashClaw Execution Mapping is the bridge between agent decision summaries (from QuantumArb, BullBear, etc.) and executable trade parameters for KashClaw organs. It handles:

1. **Asset class detection** - Automatically determines asset class from instrument
2. **Organ selection** - Maps asset class to appropriate trading organ
3. **Parameter generation** - Creates execution-ready trade parameters
4. **Normalization** - Standardizes instrument formats and units

## Architecture

```
AgentDecisionSummary
        ↓
KashClawExecutionMapper
        ↓
ExecutionMappingResult
        ↓
Trade Parameters → KashClaw Organ → Execution
```

## Core Components

### 1. AgentDecisionSummary
Input structure from agents like QuantumArb, BullBear, KloutBot:

```python
@dataclass
class AgentDecisionSummary:
    agent_name: str           # "quantumarb", "bullbear", "kloutbot"
    instrument: str           # "BTC-USD", "AAPL", "KALSHI-2024-ELECTION"
    side: Side                # BUY or SELL
    quantity: float           # Amount to trade
    units: str                # "USD", "BTC", "shares"
    confidence: Optional[float] = None      # 0.0 to 1.0
    horizon_days: Optional[int] = None      # Time horizon
    volatility_posture: Optional[str] = None # "high", "medium", "low"
    timesfm_used: bool = False              # Whether TimesFM was used
    rationale: Optional[str] = None         # Decision rationale
    timestamp: str = ""       # ISO 8601 timestamp
```

### 2. KashClawExecutionMapper
Main mapping class with the following responsibilities:

- **Validation** - Validates decision summaries
- **Asset class detection** - Determines asset class from instrument patterns
- **Organ selection** - Maps asset class to organ type
- **Parameter generation** - Creates trade parameters
- **Normalization** - Standardizes formats

### 3. ExecutionMappingResult
Output structure with mapping results:

```python
@dataclass
class ExecutionMappingResult:
    success: bool                    # Whether mapping succeeded
    trade_params: Optional[Dict]     # Generated trade parameters
    organ_id: Optional[str]          # Selected organ ID
    organ_type: Optional[OrganType]  # Selected organ type
    warnings: List[str]              # Any warnings
    error_message: Optional[str]     # Error if failed
```

## Asset Class Detection

The mapper automatically detects asset classes using pattern matching:

| Pattern | Asset Class | Example Instruments |
|---------|-------------|---------------------|
| `BTC-.*\|ETH-.*\|SOL-.*` | Crypto | `BTC-USD`, `ETH-USDC`, `SOL-USD` |
| `AAPL\|TSLA\|SPY\|QQQ` | Stocks | `AAPL`, `TSLA`, `SPY` |
| `ES.*\|NQ.*\|YM.*` | Futures | `ESM4`, `NQM4`, `YMH4` |
| `.*CALL$\|.*PUT$` | Options | `AAPL240419C200`, `TSLA240419P180` |
| `KALSHI-.*` | Prediction Markets | `KALSHI-2024-ELECTION` |
| `POLYMARKET-.*` | Prediction Markets | `POLYMARKET-BITCOIN-100K` |
| `.*-USD` (with dash) | Crypto | `BTC-USD`, `ETH-USD` |
| `.*/USD` (with slash) | Crypto | `BTC/USD`, `ETH/USDC` |

## Organ Type Mapping

Each asset class maps to a specific organ type:

| Asset Class | Organ Type | Default Organ ID |
|-------------|------------|------------------|
| Crypto | `OrganType.SPOT_TRADING` | `spot:001` |
| Stocks | `OrganType.SPOT_TRADING` | `spot:001` |
| Futures | `OrganType.FUTURES_TRADING` | `futures:001` |
| Options | `OrganType.OPTIONS_TRADING` | `options:001` |
| Prediction Markets | `OrganType.PREDICTION_MARKET` | `prediction:001` |
| Real Estate | `OrganType.REAL_ESTATE` | `real_estate:001` |
| Unknown | `OrganType.SPOT_TRADING` | `spot:001` |

## Execution Venue Mapping

Each asset class has a default execution venue:

| Asset Class | Default Venue | Notes |
|-------------|---------------|-------|
| Crypto | `ExecutionVenue.COINBASE` | Coinbase Pro API |
| Stocks | `ExecutionVenue.ALPACA` | Alpaca Markets API |
| Futures | `ExecutionVenue.ALPACA` | Alpaca Futures |
| Options | `ExecutionVenue.ALPACA` | Alpaca Options |
| Prediction Markets | `ExecutionVenue.KALSHI` | Kalshi API |
| Real Estate | `ExecutionVenue.SIMULATED` | Simulated execution |

## Parameter Generation

### Crypto Parameters
```python
{
    "slippage_tolerance": 0.01,      # 1% default
    "venue": "coinbase",
    "order_type": "market",          # Market order
    "time_in_force": "gtc",          # Good till cancelled
}
```

### Stock Parameters
```python
{
    "slippage_tolerance": 0.005,     # 0.5% default
    "venue": "alpaca",
    "order_type": "market",
    "time_in_force": "day",          # Day order
    "notional": quantity * 100,      # Example calculation
}
```

### Prediction Market Parameters
```python
{
    "slippage_tolerance": 0.02,      # 2% default
    "venue": "kalshi",
    "order_type": "limit",           # Usually limit orders
    "time_in_force": "gtc",
    "max_position_size": 100,        # Default limit
}
```

## Usage Examples

### Basic Usage
```python
from simp.integrations.kashclaw_execution_mapping import map_decision_to_trade
from simp.financial.a2a_schema import AgentDecisionSummary, Side

# Create a decision summary
decision = AgentDecisionSummary(
    agent_name="quantumarb",
    instrument="BTC-USD",
    side=Side.BUY,
    quantity=0.1,
    units="BTC",
    confidence=0.75,
    rationale="Arbitrage opportunity detected",
    timestamp="2024-04-09T12:34:56.789Z"
)

# Map to trade parameters
result = map_decision_to_trade(decision)

if result.success:
    print(f"Organ ID: {result.organ_id}")
    print(f"Trade params: {result.trade_params}")
else:
    print(f"Error: {result.error_message}")
```

### With Available Organs
```python
# Provide available organs for selection
available_organs = {
    "spot:001": OrganType.SPOT_TRADING,
    "spot:002": OrganType.SPOT_TRADING,
    "futures:001": OrganType.FUTURES_TRADING,
}

result = map_decision_to_trade(decision, available_organs)
```

### Using the Mapper Directly
```python
from simp.integrations.kashclaw_execution_mapping import KashClawExecutionMapper

mapper = KashClawExecutionMapper()
result = mapper.map_decision_to_trade(decision)

# Get execution summary
summary = mapper.get_execution_summary(decision, result)
print(f"Execution summary: {summary}")
```

## Integration with KashClaw Shim

### Enhanced handle_trade Method
The execution mapping integrates with the existing `handle_trade` method in `kashclaw_shim.py`:

```python
async def handle_trade_from_decision(
    self,
    decision: AgentDecisionSummary
) -> Dict[str, Any]:
    """
    Execute trade from AgentDecisionSummary.
    """
    # Map decision to trade parameters
    mapper = get_execution_mapper()
    mapping_result = mapper.map_decision_to_trade(
        decision,
        available_organs=self.organs  # Pass available organs
    )
    
    if not mapping_result.success:
        return {
            "status": "error",
            "error_code": "MAPPING_FAILED",
            "error_message": mapping_result.error_message
        }
    
    # Add organ_id to trade parameters
    trade_params = mapping_result.trade_params
    trade_params["organ_id"] = mapping_result.organ_id
    
    # Execute using existing handle_trade method
    return await self.handle_trade(trade_params)
```

## Validation Rules

### Required Fields
1. `agent_name` - Must not be empty
2. `instrument` - Must not be empty
3. `side` - Must be valid Side enum
4. `quantity` - Must be > 0
5. `units` - Must not be empty

### Optional Field Validation
1. `confidence` - Must be between 0.0 and 1.0 if provided
2. `horizon_days` - Must be > 0 if provided
3. `timestamp` - Should be valid ISO 8601 format

## Error Handling

### Common Errors
| Error Code | Description | Resolution |
|------------|-------------|------------|
| `MISSING_AGENT_NAME` | agent_name is empty | Provide agent name |
| `MISSING_INSTRUMENT` | instrument is empty | Provide instrument |
| `INVALID_QUANTITY` | quantity <= 0 | Provide positive quantity |
| `INVALID_CONFIDENCE` | confidence out of range | Use 0.0 to 1.0 |
| `NO_AVAILABLE_ORGAN` | No organ for asset class | Register appropriate organ |

### Warnings
1. **Unknown asset class** - When instrument doesn't match known patterns
2. **Low confidence** - When confidence < 0.3
3. **Missing volatility posture** - When TimesFM used but no posture provided
4. **Large quantity** - When quantity exceeds typical ranges

## Testing

### Unit Tests
```python
# Test basic mapping
def test_crypto_mapping():
    decision = AgentDecisionSummary(...)
    result = map_decision_to_trade(decision)
    assert result.success
    assert result.organ_type == OrganType.SPOT_TRADING
    assert "BTC/USDC" in result.trade_params["asset_pair"]

# Test validation
def test_invalid_decision():
    decision = AgentDecisionSummary(quantity=-1, ...)
    result = map_decision_to_trade(decision)
    assert not result.success
    assert "Invalid quantity" in result.error_message

# Test asset class detection
def test_asset_class_detection():
    mapper = KashClawExecutionMapper()
    assert mapper._determine_asset_class("BTC-USD") == AssetClass.CRYPTO
    assert mapper._determine_asset_class("AAPL") == AssetClass.STOCKS
    assert mapper._determine_asset_class("KALSHI-ELECTION") == AssetClass.PREDICTION_MARKETS
```

### Integration Tests
```python
# Test with actual KashClaw shim
async def test_integration():
    agent = KashClawSimpAgent(...)
    decision = AgentDecisionSummary(...)
    
    result = await agent.handle_trade_from_decision(decision)
    assert result["status"] == "success"
    assert "execution" in result
```

## Performance Considerations

### Caching
- Asset class detection patterns are compiled once
- Organ selection uses efficient dictionary lookups
- Singleton mapper instance reduces initialization overhead

### Memory Usage
- Mapper maintains minimal state
- ExecutionMappingResult is lightweight
- Trade parameters dictionary is optimized for KashClaw

### Thread Safety
- Mapper is thread-safe for concurrent use
- No shared mutable state between calls
- Each mapping operation is independent

## Monitoring and Logging

### Execution Summary
The mapper generates detailed execution summaries for monitoring:

```json
{
  "timestamp": "2024-04-09T12:34:56.789Z",
  "agent_name": "quantumarb",
  "instrument": "BTC-USD",
  "original_side": "BUY",
  "original_quantity": 0.1,
  "original_units": "BTC",
  "mapping_success": true,
  "mapped_organ_id": "spot:001",
  "mapped_organ_type": "spot_trading",
  "mapped_asset_pair": "BTC/USDC",
  "mapped_side": "BUY",
  "confidence": 0.75,
  "volatility_posture": "medium",
  "timesfm_used": true,
  "warnings": []
}
```

### Metrics
Key metrics to monitor:
1. **Mapping success rate** - Percentage of successful mappings
2. **Asset class distribution** - Distribution of detected asset classes
3. **Average mapping time** - Time taken for mapping operations
4. **Warning frequency** - Frequency of different warning types

## Extension Points

### Adding New Asset Classes
1. Add to `AssetClass` enum
2. Add pattern to `ASSET_CLASS_PATTERNS`
3. Add mapping to `ASSET_TO_ORGAN_TYPE`
4. Add mapping to `ASSET_TO_VENUE`
5. Add parameter generation method

### Custom Organ Selection
Override `_select_organ_id` method for custom logic:
- Load balancing across multiple organs
- Organ health checks
- Capacity-based selection
- Geographic optimization

### Custom Parameter Generation
Override `_generate_trade_params` or asset-specific methods:
- Custom slippage calculations
- Dynamic order types
- Venue-specific parameters
- Risk-based quantity adjustments

## Related Documents

1. [KashClaw Shim](../simp/integrations/kashclaw_shim.py)
2. [Trading Organ](../simp/integrations/trading_organ.py)
3. [AgentDecisionSummary Schema](../simp/financial/a2a_schema.py)
4. [QuantumArb Integration Contract](./quantumarb_integration_contract.md)
5. [BullBear Signal Format](../../bullbear/docs/signal_format_spec.md)

## Change Log

### v1.0.0 (2024-04-09)
- Initial execution mapping specification
- Support for all major asset classes
- Integration with existing KashClaw shim
- Comprehensive validation and error handling
- Detailed monitoring and logging