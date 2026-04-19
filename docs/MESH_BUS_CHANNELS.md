# SIMP Agent Mesh Bus - Core Channels Specification

## Overview

The SIMP Agent Mesh Bus provides structured, channel-based messaging between agents. This document specifies the core channels that all agents should use for standardized communication.

## Core Channels

### 1. `safety_alerts` - Safety & Security Events
**Purpose**: Critical safety and security notifications that require immediate attention.

**Producers**:
- `brp` - Behavioral Risk Profiler (risk thresholds, anomalies)
- `projectx` - Security scanner findings
- `watchtower` - Real-time monitoring alerts
- `quantumarb` - Trading safety violations
- Any agent detecting security issues

**Consumers**:
- `projectx` - Primary interpreter and decision maker
- `watchtower` - Real-time dashboard display
- `dashboard` - Operator console
- All agents (auto-subscribed for critical alerts)

**Message Format**:
```json
{
  "alert_type": "brp_high_risk|risk_limit|connector_error|config_issue",
  "severity": "INFO|WARNING|CRITICAL",
  "message": "Human-readable description",
  "risk_score": 0.0-1.0,
  "agent_id": "source_agent",
  "timestamp": "ISO8601",
  "recommended_action": "pause_trading|review_config|investigate"
}
```

### 2. `trade_updates` - Trading Activity
**Purpose**: Real-time trading updates, positions, and execution events.

**Producers**:
- `quantumarb` - Arbitrage opportunities and executions
- `execution_engine` - Trade confirmations
- `risk_monitor` - Position updates and risk metrics
- `kashclaw` - Multi-venue execution results

**Consumers**:
- `risk_monitor` - Risk calculation and limits
- `dashboard` - Trading dashboard display
- `projectx` - Trading pattern analysis
- `pnl_ledger` - Profit/loss tracking

**Message Format**:
```json
{
  "action": "opportunity_detected|order_placed|order_filled|position_update",
  "symbol": "BTC-USD|ETH-USD",
  "quantity": 0.1,
  "price": 50000.0,
  "exchange": "coinbase|binance",
  "timestamp": "ISO8601",
  "pnl_impact": 25.50,
  "risk_metrics": {"var": 100.0, "exposure": 5000.0}
}
```

### 3. `system_heartbeats` - Agent Health
**Purpose**: Regular health status updates from all agents.

**Producers**: All registered agents (automatic)

**Consumers**:
- `projectx` - Health monitoring and alerting
- `dashboard` - Agent status display
- `watchtower` - Availability monitoring
- `orchestration_manager` - Task routing decisions

**Message Format**:
```json
{
  "status": "HEALTHY|DEGRADED|UNHEALTHY",
  "agent_id": "agent_name",
  "timestamp": "ISO8601",
  "metrics": {
    "cpu_percent": 15.5,
    "memory_mb": 128.0,
    "queue_depth": 5,
    "last_intent_processed": "ISO8601"
  },
  "capabilities": ["trading", "analysis", "monitoring"]
}
```

### 4. `maintenance_events` - System Maintenance
**Purpose**: System maintenance recommendations, configuration changes, and operational actions.

**Producers**:
- `projectx` - Maintenance recommendations
- `ops_scripts` - Automated maintenance tasks
- `dashboard` - Operator-initiated actions
- `security_audit` - Security remediation steps

**Consumers**:
- All agents (for system-wide changes)
- `dashboard` - Maintenance console
- `projectx` - Action tracking
- `orchestration_manager` - Workflow coordination

**Message Format**:
```json
{
  "kind": "pause_suggested|config_drift|restart_recommended|update_available",
  "severity": "INFO|WARNING|CRITICAL",
  "details": {
    "agent": "target_agent",
    "reason": "Human-readable reason",
    "suggested_action": "action_to_take",
    "timestamp": "ISO8601"
  },
  "source": "projectx|ops|security"
}
```

### 5. `orchestration_commands` - Workflow Control
**Purpose**: Commands for orchestrating multi-agent workflows.

**Producers**:
- `orchestration_manager` - Workflow steps
- `projectx` - Automated task sequences
- `dashboard` - Operator commands

**Consumers**:
- Target agents for workflow steps
- `orchestration_manager` - State tracking
- `projectx` - Execution monitoring

**Message Format**:
```json
{
  "command": "start_workflow|next_step|pause_workflow|complete",
  "workflow_id": "uuid",
  "step": 1,
  "target_agent": "agent_name",
  "parameters": {"key": "value"},
  "timestamp": "ISO8601"
}
```

## Channel Subscription Guidelines

### Automatic Subscriptions
1. All agents are automatically subscribed to `safety_alerts` upon registration
2. Agents should subscribe to channels relevant to their role
3. The broker manages channel subscriptions via the MeshBus

### Subscription Patterns
```python
# Example: ProjectX subscribing to core channels
from simp.mesh.client import MeshClient

client = MeshClient(agent_id="projectx", broker_url="http://localhost:5555")

# Subscribe to all core channels
for channel in ["safety_alerts", "maintenance_events", "system_heartbeats"]:
    client.subscribe(channel)
```

### Wildcard Subscriptions
- Use `*` to subscribe to all channels (not recommended for production)
- Use `trade_*` to subscribe to all trade-related channels

## Message Priority Levels

1. **HIGH**: Safety alerts, critical errors, system failures
2. **NORMAL**: Trading updates, maintenance events, workflow commands
3. **LOW**: Heartbeats, status updates, informational messages

## Implementation Examples

### Sending a Safety Alert
```python
from simp.mesh.client import MeshClient
from simp.mesh.packet import create_event_packet

client = MeshClient(agent_id="brp", broker_url="http://localhost:5555")

# Create and send safety alert
packet = create_event_packet(
    sender_id="brp",
    recipient_id="*",  # Broadcast to all subscribers
    channel="safety_alerts",
    payload={
        "alert_type": "risk_limit",
        "severity": "CRITICAL",
        "message": "Risk limit exceeded for quantumarb",
        "risk_score": 0.95,
        "recommended_action": "pause_trading"
    },
    priority="high"
)

client.send(packet)
```

### Receiving and Processing Messages
```python
from simp.mesh.client import MeshClient

client = MeshClient(agent_id="projectx", broker_url="http://localhost:5555")
client.subscribe("safety_alerts")

# Poll for messages
messages = client.poll(max_messages=10)
for packet in messages:
    if packet.channel == "safety_alerts":
        handle_safety_alert(packet.payload)
```

## Best Practices

1. **Use Structured Payloads**: Always use the specified JSON formats
2. **Include Timestamps**: All messages must include ISO8601 timestamps
3. **Set Appropriate Priority**: Use HIGH only for critical alerts
4. **Include Trace IDs**: For correlating related events across systems
5. **Handle Offline Agents**: Messages are stored for offline agents
6. **Respect TTL**: Messages expire based on TTL settings

## Integration with Existing Systems

### ProjectX Integration
ProjectX serves as the primary consumer and interpreter of mesh traffic:
- Analyzes `safety_alerts` for pattern detection
- Emits `maintenance_events` based on analysis
- Monitors `system_heartbeats` for agent health
- Correlates events using trace IDs

### Dashboard Integration
The dashboard displays real-time mesh activity:
- Shows active channels and message rates
- Displays safety alerts prominently
- Visualizes agent health status
- Provides message history and search

### Agent Lightning Integration
Agent Lightning uses mesh events for:
- Correlating LLM traces with mesh events
- Understanding system context for decisions
- Providing explanations for mesh-based actions

## Next Steps

1. **Standardize Additional Channels**: As new use cases emerge
2. **Implement Channel Statistics**: Monitor channel health and usage
3. **Add Encryption Layer**: For sensitive message content
4. **Develop Channel Management UI**: For operators to manage subscriptions
5. **Create Channel Templates**: For common message patterns

## Version History

- **v1.0** (2024-04-14): Initial specification with 5 core channels
- **Future**: Add analytics, prediction_markets, affiliate channels

---

*This document is maintained by the SIMP protocol team. Last updated: 2024-04-14*