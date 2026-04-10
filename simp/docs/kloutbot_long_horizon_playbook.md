# Kloutbot Long-Horizon Strategy Playbook

## Overview

This playbook guides operators through understanding, validating, and acting upon Kloutbot's horizon advice. It covers both normal operations and troubleshooting scenarios.

## 1. Understanding Horizon Advice

### 1.1 Horizon Summary Fields

Every Kloutbot strategy includes a `horizon_summary` field:

```json
{
  "horizon_summary": {
    "label": "long",
    "steps": 32,
    "applied": true,
    "rationale": "TimesFM affinity forecast: long horizon (32 steps)...",
    "source": "timesfm"
  }
}
```

**Key fields to check:**
- `label`: Should be "short", "medium", or "long"
- `applied`: True if TimesFM was used, False if fallback
- `source`: "timesfm" or "fallback"
- `rationale`: Explains why this horizon was chosen

### 1.2 What Each Horizon Means

| Horizon | Steps | Typical Use | Risk Profile | Action Required |
|---------|-------|-------------|--------------|-----------------|
| **Short** | 8 | Immediate execution | Higher risk, faster moves | Review within 15 minutes |
| **Medium** | 16 | Near-term planning | Moderate risk | Review within 1 hour |
| **Long** | 32 | Strategic positioning | Lower risk, slower moves | Review within 4 hours |

## 2. Operator Workflow

### 2.1 Daily Check (5 minutes)

1. **Check horizon distribution** (Dashboard → Kloutbot → Horizon Stats):
   - Expected: Mix of all three horizons
   - Warning: >70% in one bucket
   - Critical: 100% fallback (TimesFM offline)

2. **Review recent long-horizon strategies**:
   ```bash
   # Get last 5 long-horizon strategies
   curl -s "http://localhost:5555/agents/kloutbot/history?horizon=long&limit=5"
   ```

3. **Verify TimesFM health**:
   ```bash
   # Check TimesFM service status
   curl -s "http://localhost:5555/integrations/timesfm/health"
   ```

### 2.2 Strategy Review Checklist

When reviewing a specific strategy:

✅ **Horizon Validation**
- [ ] Horizon label matches expectations for current market
- [ ] Rationale makes sense (check affinity persistence)
- [ ] TimesFM was applied (not fallback)
- [ ] Step count appropriate for recommended action

✅ **Strategy Coherence**
- [ ] Horizon matches strategy complexity
- [ ] Action parameters appropriate for horizon
- [ ] Confidence level aligns with horizon
- [ ] No contradictions in decision tree

✅ **Risk Assessment**
- [ ] Position size appropriate for horizon
- [ ] Slippage tolerance matches horizon
- [ ] Time-in-force aligns with step count
- [ ] Fallback plan exists if horizon wrong

### 2.3 Decision Framework

**Short Horizon (8 steps):**
- Question: "Would I take this trade today?"
- Focus: Immediate market conditions
- Action: Quick review, potential immediate execution

**Medium Horizon (16 steps):**
- Question: "Does this make sense for tomorrow?"
- Focus: Overnight risk, next session
- Action: Review with daily planning

**Long Horizon (32 steps):**
- Question: "Is this a good weekly position?"
- Focus: Trend persistence, macro factors
- Action: Strategic review, capital allocation

## 3. Troubleshooting

### 3.1 Common Issues

#### Issue: All strategies show "fallback" source
**Symptoms:**
- `horizon_summary.source` = "fallback" for all strategies
- `horizon_summary.applied` = false
- Rationale mentions "TimesFM unavailable"

**Diagnosis:**
```bash
# Check TimesFM service
curl -s "http://localhost:5555/integrations/timesfm/health"

# Check Kloutbot affinity buffer
curl -s "http://localhost:5555/agents/kloutbot/status" | jq '.affinity_buffer_length'
```

**Resolution:**
1. Restart TimesFM service if unhealthy
2. Wait for affinity buffer to fill (>16 observations)
3. Check network connectivity to TimesFM

#### Issue: Horizon oscillating wildly
**Symptoms:**
- Horizon jumps between short/long frequently
- No clear pattern in rationale

**Diagnosis:**
```bash
# Check affinity buffer quality
curl -s "http://localhost:5555/agents/kloutbot/status" | jq '.affinity_buffer'

# Check market volatility
# (Use external market data tools)
```

**Resolution:**
1. Check if market is unusually volatile
2. Verify affinity signal quality
3. Consider increasing persistence threshold temporarily

#### Issue: All strategies same horizon
**Symptoms:**
- 100% short, medium, or long horizons
- No variation despite changing market

**Diagnosis:**
```bash
# Check TimesFM forecast patterns
curl -s "http://localhost:5555/integrations/timesfm/debug" | jq '.last_forecasts'
```

**Resolution:**
1. Check TimesFM model calibration
2. Verify input data quality
3. Review affinity calculation logic

### 3.2 Emergency Procedures

#### TimesFM Complete Failure
1. **Immediate action**: Monitor for fallback behavior
2. **Check**: All strategies should use medium horizon (16 steps)
3. **Impact**: Reduced horizon precision, but strategies still generated
4. **Recovery**: Restart TimesFM service, verify forecasts resume

#### Horizon Advice Stuck
1. **Immediate action**: Manual horizon override via API
   ```bash
   curl -X POST "http://localhost:5555/agents/kloutbot/override" \
     -H "Content-Type: application/json" \
     -d '{"horizon": "medium", "reason": "manual override"}'
   ```
2. **Duration**: Override lasts 1 hour
3. **Follow-up**: Diagnose root cause, fix, remove override

## 4. Monitoring & Alerts

### 4.1 Key Metrics to Monitor

| Metric | Normal Range | Warning | Critical | Action |
|--------|--------------|---------|----------|--------|
| TimesFM success rate | >95% | 80-95% | <80% | Check service |
| Fallback rate | <5% | 5-20% | >20% | Investigate |
| Horizon distribution | Mixed | 70% one bucket | 90% one bucket | Review market |
| Strategy coherence | >90% | 70-90% | <70% | Check logic |

### 4.2 Dashboard Views

1. **Horizon Distribution Pie Chart**
   - Shows % of short/medium/long strategies
   - Color-coded (green=normal, yellow=warning, red=critical)

2. **TimesFM Health Panel**
   - Success rate over time
   - Forecast latency
   - Error rate

3. **Strategy Coherence Matrix**
   - Horizon vs action type
   - Horizon vs confidence
   - Horizon vs position size

### 4.3 Automated Alerts

Configure alerts for:
- TimesFM success rate < 80% for 5 minutes
- Fallback rate > 20% for 10 minutes
- 100% same horizon for 30 minutes
- Strategy generation failure rate > 10%

## 5. Advanced Operations

### 5.1 Horizon Calibration

If horizons consistently seem wrong:

1. **Collect calibration data**:
   ```bash
   # Export recent strategies for analysis
   curl -s "http://localhost:5555/agents/kloutbot/history?limit=100" > horizon_calibration.json
   ```

2. **Analyze persistence thresholds**:
   - Compare actual market moves vs forecast persistence
   - Adjust 0.5 threshold if needed
   - Consider market regime-specific thresholds

3. **Test adjustments**:
   ```python
   # In test environment
   NEW_THRESHOLD = 0.55  # More conservative
   # Run backtest with historical data
   ```

### 5.2 A2A Integration Testing

When integrating with other agents:

1. **Verify horizon mapping**:
   - Short → immediate execution agents
   - Medium → planning pipeline  
   - Long → strategic review agents

2. **Test handoff scenarios**:
   - Kloutbot → QuantumArb (short horizon)
   - Kloutbot → CapitalAllocator (long horizon)
   - Kloutbot → RiskManager (all horizons)

3. **Monitor A2A compatibility**:
   ```bash
   # Check A2A agent cards for horizon support
   curl -s "http://localhost:5555/a2a/agents" | jq '.[] | select(.capabilities | contains("horizon"))'
   ```

## 6. Training Scenarios

### 6.1 Scenario: Volatile Market

**Situation**: Market volatility spikes, horizons oscillating
**Action**:
1. Check if oscillation is reasonable given volatility
2. Consider temporary horizon smoothing
3. Monitor position sizes (should be smaller in volatility)
4. Review more frequently

### 6.2 Scenario: Trending Market

**Situation**: Strong trend, persistent long horizons
**Action**:
1. Verify trend strength matches horizon persistence
2. Check position sizing (can be larger in trends)
3. Monitor for trend exhaustion signals
4. Consider trailing stops for long-horizon positions

### 6.3 Scenario: Range-bound Market

**Situation**: Market ranging, mostly short horizons
**Action**:
1. Verify range boundaries
2. Check if short horizons make sense (quick mean reversion)
3. Monitor for breakout signals
4. Smaller position sizes appropriate

## 7. Appendices

### 7.1 Quick Reference

| Command | Purpose |
|---------|---------|
| `curl -s "http://localhost:5555/agents/kloutbot/status"` | Kloutbot status |
| `curl -s "http://localhost:5555/integrations/timesfm/health"` | TimesFM health |
| `curl -s "http://localhost:5555/agents/kloutbot/history?horizon=long&limit=10"` | Recent long-horizon strategies |
| `curl -X POST "http://localhost:5555/agents/kloutbot/override" -d '{"horizon":"medium"}'` | Manual horizon override |

### 7.2 Contact Matrix

| Issue | Primary Contact | Secondary Contact | Escalation Path |
|-------|-----------------|-------------------|-----------------|
| TimesFM service down | System Operator | DevOps | Infrastructure Team |
| Horizon logic errors | Kloutbot Developer | AI/ML Engineer | Architecture Team |
| A2A integration issues | Integration Engineer | Protocol Specialist | Protocol Team |
| Trading impact | Trading Ops | Risk Manager | Head of Trading |

---

*Playbook Version: 1.0*  
*Last Updated: 2026-04-09*  
*Maintainer: Trading Operations Team*