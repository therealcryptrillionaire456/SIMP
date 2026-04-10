# A2A Consumer Mapping Guide

## Overview

This document guides agent developers (QuantumArb, KashClaw, Kloutbot) on how to produce `AgentDecisionSummary` objects that feed into the A2A (Agent-to-Agent) execution pipeline. It provides examples, field mappings, and expected behaviors for each agent type.

## Core Schema

All agents must produce `AgentDecisionSummary` objects with these required fields:

```python
@dataclass
class AgentDecisionSummary:
    agent_name: str           # e.g., "quantumarb", "kashclaw", "kloutbot"
    instrument: str           # e.g., "BTC-USD", "ETH-USD", "SOL-USD"
    side: Side                # BUY, SELL, or HOLD
    quantity: float           # Positive amount to trade
    units: str               # e.g., "USD", "BTC", "shares"
    
    # Optional but recommended
    confidence: Optional[float] = None      # 0.0 to 1.0
    horizon_days: Optional[int] = None      # Time horizon
    volatility_posture: Optional[str] = None # "low", "medium", "high"
    timesfm_used: bool = False              # Whether TimesFM was used
    rationale: Optional[str] = None         # Human-readable explanation
    timestamp: str = field(default_factory=...)  # ISO 8601
```

## Agent-Specific Guidelines

### QuantumArb (Arbitrage Detection)

**Purpose**: Detect and execute cross-exchange arbitrage opportunities.

**Field Mapping**:
- `agent_name`: "quantumarb"
- `instrument`: Use format "ASSET-QUOTE" (e.g., "BTC-USD", "ETH-USDT")
- `side`: BUY on undervalued exchange, SELL on overvalued exchange
- `quantity`: Size limited by available liquidity and risk limits
- `units`: Quote currency (e.g., "USD", "USDT")
- `confidence`: High (0.8+) for clear arb opportunities
- `horizon_days`: 0-1 (arb opportunities are short-lived)
- `volatility_posture`: "medium" to "high" (arb often in volatile markets)
- `timesfm_used`: True (arb detection uses TimesFM for timing)
- `rationale`: Include spread percentage and exchange names

**Example 1: Typical BTC Arbitrage**

```json
{
  "agent_name": "quantumarb",
  "instrument": "BTC-USD",
  "side": "BUY",
  "quantity": 5000.0,
  "units": "USD",
  "confidence": 0.85,
  "horizon_days": 0,
  "volatility_posture": "medium",
  "timesfm_used": true,
  "rationale": "Arbitrage detected: Binance $65,100 vs Coinbase $65,500 (0.6% spread)",
  "timestamp": "2024-04-09T10:30:00Z"
}
```

**Example 2: Small, Fast Arb Opportunity**

```json
{
  "agent_name": "quantumarb",
  "instrument": "ETH-USDT",
  "side": "SELL",
  "quantity": 2500.0,
  "units": "USDT",
  "confidence": 0.92,
  "horizon_days": 0,
  "volatility_posture": "high",
  "timesfm_used": true,
  "rationale": "Flash arb: Kraken $3,520 vs FTX $3,550 (0.85% spread, high liquidity)",
  "timestamp": "2024-04-09T11:15:00Z"
}
```

**Resulting A2APlan Characteristics**:
- High confidence → May trigger AGGRESSIVE risk posture
- Large single-instrument exposure → May fail concentration check (>30%)
- Typically requires fast execution (horizon_days=0)

### KashClaw (Technical Analysis & Risk Management)

**Purpose**: Technical analysis, trend following, and risk-managed position sizing.

**Field Mapping**:
- `agent_name`: "kashclaw"
- `instrument`: Use format "ASSET-QUOTE"
- `side`: Based on technical indicators (MACD, RSI, support/resistance)
- `quantity`: Risk-adjusted position size (e.g., 1-2% of portfolio)
- `units`: Quote currency
- `confidence`: Moderate (0.6-0.8) for technical signals
- `horizon_days`: 3-7 (medium-term technical trades)
- `volatility_posture`: Varies with market conditions
- `timesfm_used`: Optional (for volatility forecasting)
- `rationale`: Include key technical levels and indicators

**Example 1: Trend Following Signal**

```json
{
  "agent_name": "kashclaw",
  "instrument": "BTC-USD",
  "side": "BUY",
  "quantity": 2000.0,
  "units": "USD",
  "confidence": 0.75,
  "horizon_days": 5,
  "volatility_posture": "low",
  "timesfm_used": false,
  "rationale": "Bullish MACD crossover above zero, price above 200-day MA at $64,800",
  "timestamp": "2024-04-09T09:45:00Z"
}
```

**Example 2: Risk-Off Recommendation**

```json
{
  "agent_name": "kashclaw",
  "instrument": "SOL-USD",
  "side": "SELL",
  "quantity": 800.0,
  "units": "USD",
  "confidence": 0.68,
  "horizon_days": 3,
  "volatility_posture": "high",
  "timesfm_used": true,
  "rationale": "RSI overbought at 78, rejection at resistance $180, stop loss at $165",
  "timestamp": "2024-04-09T14:20:00Z"
}
```

**Resulting A2APlan Characteristics**:
- Moderate confidence → Typically NEUTRAL risk posture
- Well-sized positions → Often passes concentration checks
- Medium time horizon → Suitable for both simulated and live execution

### Kloutbot (Social Sentiment & Narrative Analysis)

**Purpose**: Analyze social media sentiment, news flow, and market narratives.

**Field Mapping**:
- `agent_name`: "kloutbot"
- `instrument`: Use format "ASSET-QUOTE"
- `side`: Based on sentiment polarity and strength
- `quantity`: Smaller sizes (sentiment-driven moves are higher risk)
- `units`: Quote currency
- `confidence`: Lower (0.5-0.7) for sentiment-based signals
- `horizon_days`: 1-3 (sentiment can change quickly)
- `volatility_posture`: Often "high" (sentiment-driven markets are volatile)
- `timesfm_used`: False (sentiment analysis doesn't use TimesFM)
- `rationale`: Include sentiment score, key topics, and source mentions

**Example 1: Positive Social Sentiment**

```json
{
  "agent_name": "kloutbot",
  "instrument": "DOGE-USD",
  "side": "BUY",
  "quantity": 500.0,
  "units": "USD",
  "confidence": 0.62,
  "horizon_days": 2,
  "volatility_posture": "high",
  "timesfm_used": false,
  "rationale": "Positive sentiment spike on Twitter/X: +35% sentiment score, 'Elon' mentions up 3x",
  "timestamp": "2024-04-09T12:30:00Z"
}
```

**Example 2: Negative News Flow**

```json
{
  "agent_name": "kloutbot",
  "instrument": "ADA-USD",
  "side": "SELL",
  "quantity": 300.0,
  "units": "USD",
  "confidence": 0.55,
  "horizon_days": 1,
  "volatility_posture": "medium",
  "timesfm_used": false,
  "rationale": "Negative developer sentiment: -22% sentiment, concerns about Cardano roadmap delays",
  "timestamp": "2024-04-09T16:45:00Z"
}
```

**Resulting A2APlan Characteristics**:
- Lower confidence → Often CONSERVATIVE risk posture
- Small position sizes → Usually passes safety checks
- Short time horizon → Best for simulated execution initially

## Multi-Agent Scenario Examples

### Scenario 1: Consensus (All Agents Agree)

```python
decisions = [
    # QuantumArb: BTC arb opportunity
    AgentDecisionSummary(
        agent_name="quantumarb",
        instrument="BTC-USD",
        side=Side.BUY,
        quantity=4000.0,
        units="USD",
        confidence=0.88,
        rationale="Arb: 0.5% spread Coinbase vs Binance"
    ),
    
    # KashClaw: Technical buy signal
    AgentDecisionSummary(
        agent_name="kashclaw", 
        instrument="BTC-USD",
        side=Side.BUY,
        quantity=1500.0,
        units="USD",
        confidence=0.72,
        rationale="Bullish breakout above $66,000 resistance"
    ),
    
    # Kloutbot: Positive sentiment
    AgentDecisionSummary(
        agent_name="kloutbot",
        instrument="BTC-USD", 
        side=Side.BUY,
        quantity=800.0,
        units="USD",
        confidence=0.65,
        rationale="ETF approval sentiment +42% on Crypto Twitter"
    )
]

plan = build_a2a_plan(decisions)
```

**Resulting A2APlan**:
- `execution_allowed`: Likely True (if concentration ≤ 30%)
- `risk_posture`: AGGRESSIVE (high confidence + consensus)
- `aggregate_exposure`: {"BTC-USD": 6300.0}
- `safety_checks_passed`: ["Agent consensus", "Confidence threshold"]
- Potential failure: Concentration check if BTC > 30% of total portfolio

### Scenario 2: Conflict (Agents Disagree)

```python
decisions = [
    # QuantumArb: Buy (arb opportunity)
    AgentDecisionSummary(
        agent_name="quantumarb",
        instrument="ETH-USD",
        side=Side.BUY,
        quantity=3000.0,
        units="USD",
        confidence=0.85
    ),
    
    # KashClaw: Sell (technical breakdown)
    AgentDecisionSummary(
        agent_name="kashclaw",
        instrument="ETH-USD", 
        side=Side.SELL,
        quantity=2500.0,
        units="USD",
        confidence=0.70
    )
]

plan = build_a2a_plan(decisions)
```

**Resulting A2APlan**:
- `execution_allowed`: False (conflicting signals)
- `execution_reason`: "Execution blocked: conflicting agent directions"
- `risk_posture`: NEUTRAL (mixed signals)
- `aggregate_exposure`: {"ETH-USD": 500.0} (net: 3000 - 2500 = 500 BUY)
- `safety_checks_failed`: ["Agent consensus"]

## Safety Check Implications

### Concentration Limits
- Single instrument exposure > 30% → Blocked
- Example: QuantumArb recommending $50,000 BTC when total portfolio is $100,000

### Confidence Thresholds
- Any decision with confidence < 0.3 → Blocked
- Example: Kloutbot with 0.25 confidence due to mixed sentiment

### Agent Consensus
- BUY and SELL on same instrument with significant size → Blocked
- Example: QuantumArb BUY $10,000 BTC, KashClaw SELL $8,000 BTC

## Integration Best Practices

### 1. Field Consistency
- Use consistent `instrument` naming (always "ASSET-QUOTE")
- Normalize `units` to quote currency (USD, USDT, etc.)
- Include `timestamp` in ISO 8601 format

### 2. Confidence Calibration
- QuantumArb: 0.8+ for clear arb, 0.7-0.8 for marginal
- KashClaw: 0.6-0.8 based on signal strength
- Kloutbot: 0.5-0.7 based on sentiment strength and volume

### 3. Position Sizing
- Consider total portfolio exposure when setting `quantity`
- Use risk-adjusted sizing (e.g., 1-2% per trade for KashClaw)
- For arb: size based on available liquidity

### 4. Rationale Quality
- Include key numbers (prices, percentages, scores)
- Mention data sources and timeframes
- Keep concise but informative

## Testing Your Integration

### Unit Test Template
```python
def test_agent_decision_to_a2a_plan():
    """Test that your agent's decisions produce valid A2APlans."""
    from simp.financial.a2a_schema import AgentDecisionSummary, Side
    from simp.financial.a2a_aggregator import build_a2a_plan
    
    # Create your agent's decision
    decision = AgentDecisionSummary(
        agent_name="your_agent",
        instrument="BTC-USD",
        side=Side.BUY,
        quantity=1000.0,
        units="USD",
        confidence=0.75,
        rationale="Your agent's reasoning"
    )
    
    # Build plan
    plan = build_a2a_plan([decision])
    
    # Verify
    assert plan is not None
    assert len(plan.decisions) == 1
    assert plan.decisions[0].agent_name == "your_agent"
    
    # Check safety checks
    print(f"Execution allowed: {plan.execution_allowed}")
    print(f"Reason: {plan.execution_reason}")
    print(f"Failed checks: {plan.safety_checks_failed}")
```

### Common Integration Issues

1. **Missing Fields**: Ensure all required fields are populated
2. **Invalid Values**: Confidence outside 0.0-1.0, negative quantity
3. **Mixed Units**: Different agents using different units for same instrument
4. **Timestamp Format**: Must be ISO 8601 (e.g., "2024-04-09T10:30:00Z")

## Next Steps for Agent Developers

1. **Start with Simulation**: Set `execution_mode` to `SIMULATED_ONLY`
2. **Monitor Safety Checks**: Review which checks pass/fail for your decisions
3. **Adjust Sizing**: If concentration checks fail, reduce position sizes
4. **Calibrate Confidence**: Ensure confidence scores reflect true signal strength
5. **Test Edge Cases**: Try conflicting scenarios, extreme sizes, missing data

## Migration Paths for Existing Agents

### Phase 1: Schema Compliance
Ensure your agent produces valid `AgentDecisionSummary` objects:
1. Validate all required fields are populated
2. Ensure confidence is between 0.0 and 1.0
3. Use correct `Side` enum values (BUY/SELL/HOLD)
4. Include ISO 8601 timestamps

### Phase 2: Safety Calibration  
Test your decisions through the aggregator:
1. Start with small quantities to avoid concentration blocks
2. Calibrate confidence scores to realistic levels
3. Monitor which safety checks pass/fail
4. Adjust position sizing based on concentration limits

### Phase 3: Integration Testing
Test with other agents:
1. Create test scenarios with multiple agents
2. Verify conflict detection works correctly
3. Test edge cases (missing fields, extreme values)
4. Run through the full pipeline (aggregator → safety → simulator)

### Phase 4: Production Readiness
1. Set `execution_mode = SIMULATED_ONLY` initially
2. Monitor plan outcomes vs expected results
3. Gradually increase position sizes
4. Request operator review for live promotion

## Common Integration Patterns

### Pattern 1: Agent Wrapper
Wrap existing agent logic to produce A2A-compliant decisions:

```python
class A2ACompliantAgent:
    """Wrapper that converts agent output to AgentDecisionSummary."""
    
    def __init__(self, original_agent):
        self.agent = original_agent
    
    def get_decision(self, instrument: str) -> AgentDecisionSummary:
        # Get original agent's recommendation
        raw_rec = self.agent.analyze(instrument)
        
        # Convert to A2A format
        return AgentDecisionSummary(
            agent_name=self.agent.name,
            instrument=instrument,
            side=self._convert_side(raw_rec.signal),
            quantity=self._calculate_size(raw_rec),
            units="USD",
            confidence=raw_rec.confidence,
            horizon_days=raw_rec.horizon,
            rationale=raw_rec.reason,
            timestamp=datetime.utcnow().isoformat()
        )
```

### Pattern 2: Batch Processing
Process multiple instruments in batch:

```python
def batch_analyze_instruments(agent, instruments: List[str]) -> List[AgentDecisionSummary]:
    """Analyze multiple instruments and return A2A decisions."""
    decisions = []
    
    for instrument in instruments:
        try:
            decision = agent.get_decision(instrument)
            decisions.append(decision)
        except Exception as e:
            # Log but continue with other instruments
            logger.warning(f"Failed to analyze {instrument}: {e}")
    
    return decisions
```

### Pattern 3: Decision Caching
Cache decisions to avoid redundant analysis:

```python
class CachedAgent:
    """Agent with decision caching."""
    
    def __init__(self, ttl_seconds: int = 300):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get_decision(self, instrument: str) -> AgentDecisionSummary:
        now = time.time()
        
        # Check cache
        if instrument in self.cache:
            cached_decision, timestamp = self.cache[instrument]
            if now - timestamp < self.ttl:
                return cached_decision
        
        # Generate new decision
        decision = self._analyze(instrument)
        self.cache[instrument] = (decision, now)
        
        return decision
```

## Error Handling Guidelines

### Validation Errors
If your `AgentDecisionSummary` fails validation:
1. Check field types (quantity must be float, not int)
2. Ensure confidence is within 0.0-1.0 range
3. Verify `side` is a valid `Side` enum value
4. Check for negative quantities (not allowed for BUY/SELL)

### Safety Check Failures
If your plans are being blocked:
1. **Concentration failure**: Reduce position sizes or add more instruments
2. **Confidence failure**: Increase confidence scores or filter low-confidence decisions
3. **Consensus failure**: Coordinate with other agents or accept HOLD position
4. **Posture mismatch**: Adjust confidence or accept more conservative posture

### Integration Testing Checklist
- [ ] Agent produces valid `AgentDecisionSummary` objects
- [ ] Decisions pass schema validation
- [ ] Single-agent plans pass safety checks (with appropriate sizing)
- [ ] Multi-agent scenarios handled correctly
- [ ] Edge cases (empty decisions, extreme values) don't crash
- [ ] Timestamps are ISO 8601 format
- [ ] Rationale is informative and actionable

## Performance Considerations

### Decision Frequency
- **QuantumArb**: High frequency (seconds/minutes) for arb opportunities
- **KashClaw**: Medium frequency (hours/days) for technical signals  
- **Kloutbot**: Variable frequency (minutes/hours) based on sentiment changes

### Batch Size Limits
The aggregator can handle:
- Up to 100 decisions per plan (practical limit)
- Up to 50 unique instruments per plan
- Decision lists exceeding 1MB may impact performance

### Memory Usage
- Each `AgentDecisionSummary` ≈ 1KB in memory
- Each `A2APlan` ≈ 2-5KB depending on decision count
- Consider batching if generating many decisions

## Monitoring and Observability

### Key Metrics to Track
1. **Decision volume**: Number of decisions per agent per hour
2. **Safety check pass rate**: Percentage of plans passing all checks
3. **Common failures**: Which safety checks fail most often
4. **Execution outcomes**: Simulated vs expected results
5. **Latency**: Time from decision to plan generation

### Logging Recommendations
```python
import logging

logger = logging.getLogger(__name__)

def log_decision_flow(decisions: List[AgentDecisionSummary], plan: A2APlan):
    """Log the full decision-to-plan flow."""
    logger.info(f"Generated {len(decisions)} decisions")
    logger.info(f"Execution allowed: {plan.execution_allowed}")
    logger.info(f"Risk posture: {plan.portfolio_posture.risk_posture}")
    
    if plan.safety_checks_failed:
        logger.warning(f"Safety checks failed: {plan.safety_checks_failed}")
    
    # Log aggregate exposure
    for instrument, exposure in plan.portfolio_posture.aggregate_exposure.items():
        logger.debug(f"{instrument}: {exposure:,.2f}")
```

## Support

For integration questions:
- Review the `a2a_schema.py` source for validation rules
- Check `test_financial_a2a_schema.py` for example usage
- Run the pipeline tests in `test_financial_a2a_pipeline.py`

Remember: The A2A pipeline is designed to be safe by default. Execution is blocked unless all safety checks pass, protecting the system from erroneous or risky decisions.

## Appendix: Quick Reference

### Field Requirements
| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `agent_name` | Yes | str | Unique agent identifier |
| `instrument` | Yes | str | Format: "ASSET-QUOTE" |
| `side` | Yes | Side | BUY, SELL, or HOLD |
| `quantity` | Yes | float | Positive, >0 for BUY/SELL |
| `units` | Yes | str | e.g., "USD", "BTC" |
| `confidence` | No | float | 0.0-1.0, default None |
| `horizon_days` | No | int | Time horizon in days |
| `rationale` | No | str | Human-readable explanation |
| `timestamp` | No | str | ISO 8601, auto-generated |

### Safety Thresholds
| Check | Threshold | Configurable |
|-------|-----------|--------------|
| Concentration | 30% | Yes |
| Confidence | 30% | Yes |
| High Confidence | 80% | Yes |
| Aggressive Posture | 50% | Yes |

### Common Error Messages
- `"agent_name must be a non-empty string"`: Missing agent name
- `"quantity must be positive for BUY/SELL"`: Zero or negative quantity
- `"confidence must be between 0.0 and 1.0"`: Invalid confidence value
- `"Execution blocked: X safety check(s) failed"`: Safety check failure