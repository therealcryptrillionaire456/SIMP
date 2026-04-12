# Dashboard Operator Console Specification

## Overview

The SIMP Dashboard Operator Console is a comprehensive monitoring interface that provides system-wide observability through safe, GET-only API routes. This document specifies the current implementation, data contracts, and future enhancement roadmap.

## Current Implementation (v2.0)

### Screen Inventory

#### 1. System Overview Section
**Purpose**: High-level system health and protocol status at a glance.

**Current Components**:
- **Broker Status**: Health and state of the SIMP broker
- **Agents Online**: Count of active agents
- **Intent Statistics**: Received, routed, pending, failed counts
- **ProjectX Native**: ProjectX kernel health
- **Gemma4 Planner**: Local LLM agent status
- **KashClaw Dashboard**: Dashboard self-status
- **Protocol Updates**: Last protocol update timestamp
- **Average Route Time**: Performance metric

#### 2. ProjectX Integration Section
**Purpose**: Monitor the native SIMP kernel (ProjectX) health and activity.

**Current Components**:
- **Processes Table**: Service status, category, health, ports
- **Recent Actions**: ProjectX maintenance and audit actions
- **System Overview**: Protocol documentation and component summaries
- **Protocol Facts**: Version, intent/agent definitions, safety policies
- **ProjectX Chat**: Interactive query interface with allowlisted audit jobs

#### 3. Agent Observability Section
**Purpose**: Monitor agent activity, status, and delivery health.

**Current Display**:
- **Registered Agents Table**: All agents with capabilities, status, metrics
- **Capability Map**: Visual mapping of capabilities to agents
- **Agent Smoke Tests**: Reachability test results with latency
- **Delivery Status**: Detailed delivery statistics and network topology

#### 4. Task & Orchestration Section
**Purpose**: Monitor task execution and orchestration flows.

**Current Components**:
- **Task Queue**: Queued, claimed, in-progress, completed, failed, deferred counts
- **Task Table**: Detailed task view with priority and status
- **Orchestration Status**: Loop health monitoring
- **Computer Use**: ProjectX computer use status
- **Planner/Executor Flows**: Flow tracking with planner-executor relationships

#### 5. Activity & Analytics Section
**Purpose**: Real-time activity monitoring and historical analysis.

**Current Components**:
- **Activity Charts**: Intent flow and task distribution visualizations
- **Task Search/Filter**: Searchable task interface with status filtering
- **Recent Activity Feed**: Live broker intent events
- **Structured Logs**: System event logging with levels
- **Failed Intents**: Diagnostic breakdown with status and target analysis

#### 6. Memory & Conversations Section
**Purpose**: Track system memory and conversation history.

**Current Components**:
- **Task Memory**: Persistent task state tracking
- **Recent Conversations**: Conversation history with participants

#### 7. Routing & Failure Analysis
**Purpose**: System routing behavior and failure diagnostics.

**Current Components**:
- **Routing Policy**: Visual policy mapping
- **Failure Stats**: Delivery failure breakdown
- **Failed Intents Table**: Detailed failure analysis with correlation IDs

## Data Contracts

### Endpoint Inventory (30+ GET endpoints)

#### Core System
- `/api/health` - System health status
- `/api/stats` - Broker statistics and metrics
- `/api/agents` - Registered agent metadata
- `/api/activity` - Recent system activity feed
- `/api/intents/recent` - Recent intent deliveries
- `/api/intents/failed` - Failed intent aggregates
- `/api/intents/{intent_id}` - Intent detail view
- `/api/capabilities` - Capability-to-agent mapping
- `/api/topology` - Network topology visualization
- `/api/agents/smoke` - Agent reachability tests

#### Task & Orchestration
- `/api/tasks` - Task management interface
- `/api/tasks/queue` - Task queue status
- `/api/routing` - Routing policy display
- `/api/orchestration` - Orchestration loop status
- `/api/computer-use` - ProjectX computer use status
- `/api/flows` - Planner/executor flow tracking

#### ProjectX Integration
- `/api/projectx/system` - ProjectX system status
- `/api/projectx/processes` - ProjectX process monitoring
- `/api/projectx/actions` - ProjectX recent actions
- `/api/projectx/protocol-facts` - Protocol documentation
- `/api/projectx/events` - ProjectX event stream
- `/api/projectx/chat/history` - Chat history
- `/api/projectx/chat` - Interactive chat interface

#### Memory & Analytics
- `/api/memory/tasks` - Task memory persistence
- `/api/memory/conversations` - Conversation history
- `/api/logs` - Structured system logs

#### WebSocket
- `/ws` - Real-time updates for dashboard

### Response Schema Examples

#### `/api/agents` Response:
```json
{
  "status": "success" | "unreachable",
  "broker_url_reachable": "boolean",
  "agents": [
    {
      "agent_id": "string",
      "status": "online" | "offline" | "degraded" | "unknown",
      "capabilities": ["string"],
      "endpoint": "string | null",
      "connection_mode": "http" | "file-based",
      "stale": "boolean | null",
      "received_count": "integer",
      "completed_count": "integer",
      "registered_at": "ISO8601"
    }
  ],
  "count": "integer"
}
```

#### `/api/intents/failed` Response:
```json
{
  "status": "success" | "unreachable",
  "summary": {
    "by_status": {"string": "integer"},
    "by_target_agent": {"string": "integer"},
    "latest_failure_at": "ISO8601 | null"
  },
  "intents": [
    {
      "intent_id": "string",
      "source_agent": "string",
      "target_agent": "string",
      "delivery_status": "string",
      "error": "string | null",
      "timestamp": "ISO8601",
      "correlation_id": "string | null"
    }
  ],
  "count": "integer"
}
```

#### `/api/projectx/processes` Response:
```json
{
  "status": "success",
  "processes": [
    {
      "service": "string",
      "category": "string",
      "status": "running" | "stopped" | "error",
      "health": "healthy" | "degraded" | "unhealthy",
      "port": "integer | null",
      "log_path": "string | null"
    }
  ]
}
```

## Safety & Override Controls

### Read-Only Enforcement
- **All endpoints**: GET-only methods enforced
- **No state changes**: Dashboard cannot modify system state
- **Safe redaction**: Sensitive data (API keys, trade details) redacted at backend
- **Validation**: Input validation on all parameters

### ProjectX Chat Safety
- **Allowlisted jobs only**: Health check, repo scan, task audit, security audit
- **No shell access**: ProjectX runs with `allowShell=false`
- **Read-only by default**: `readOnlyByDefault=true`
- **No file writes**: `allowFileWrites=false`

### Error Handling
1. **Endpoint Unavailable**: Show "unreachable" state with fallback data
2. **Partial Data**: Render available tiles, show loading/error for missing data
3. **Schema Mismatch**: Graceful degradation with console warnings
4. **Rate Limiting**: Respect broker rate limits with exponential backoff

## Integration Interfaces

### Frontend Data Flow
```
Dashboard Load → Promise.all([
  /api/health,
  /api/stats,
  /api/agents,
  /api/activity,
  /api/intents/failed,
  /api/capabilities,
  /api/agents/smoke,
  /api/projectx/system,
  /api/projectx/processes,
  /api/tasks,
  /api/flows,
  ...
]) → Render Functions → DOM Updates
```

### WebSocket Real-time Updates
```
WebSocket Connection → Subscribe to events → Live updates for:
- Agent status changes
- Intent deliveries
- Task state changes
- System health updates
```

### Mock Data for Testing
```javascript
// Example mock for dashboard integration tests
const mockDashboardData = {
  health: {
    status: "success",
    broker: "healthy",
    timestamp: "2024-01-15T10:30:00Z"
  },
  agents: {
    status: "success",
    agents: [
      {
        agent_id: "quantumarb",
        status: "online",
        capabilities: ["arbitrage", "trade_execution"],
        endpoint: "http://localhost:5556",
        received_count: 42,
        completed_count: 40
      }
    ],
    count: 1
  },
  projectx_system: {
    status: "success",
    system: {
      version: "1.0.0",
      uptime: "5d 3h 12m",
      health: "healthy"
    }
  }
};
```

## Design Principles

1. **Comprehensive Observability**: Single pane of glass for entire SIMP ecosystem
2. **Real-time Updates**: WebSocket for live system monitoring
3. **Progressive Enhancement**: Works with partial data; unavailable endpoints show graceful fallbacks
4. **Operator-First**: Each section answers specific operator questions
5. **Minimal Dependencies**: Leverages existing broker endpoints; no new backend logic required
6. **Security First**: Read-only access, safe redaction, input validation

## Current Grouping Structure

### Section 1: System Overview
- Broker health and statistics
- Agent counts and performance metrics
- Protocol version and updates

### Section 2: ProjectX Kernel
- Process monitoring
- Maintenance actions
- Protocol documentation
- Interactive chat

### Section 3: Agent Ecosystem
- Registered agents table
- Capability mapping
- Smoke test results
- Delivery statistics

### Section 4: Task Execution
- Task queue management
- Orchestration status
- Planner/executor flows
- Computer use monitoring

### Section 5: Activity & Analytics
- Real-time charts
- Task search and filtering
- Activity feed
- Structured logs

### Section 6: Diagnostics
- Failed intent analysis
- Routing policy visualization
- Memory and conversation tracking

## Implementation Notes

### Current Tech Stack
- **Frontend**: Vanilla JavaScript, Chart.js for visualizations, CSS Grid/Flexbox
- **Backend**: FastAPI (Python 3.10) with WebSocket support
- **Data Sources**: SIMP broker endpoints + ProjectX integration
- **Styling**: Dark observability theme with semantic color coding
- **Real-time**: WebSocket for live updates, auto-refresh fallback

### Testing Strategy
- Unit tests for data parsing and rendering logic
- Integration tests for endpoint compatibility
- Policy tests enforcing GET-only routes
- Visual regression tests for UI consistency
- WebSocket connection and reconnection tests

## Maintenance Guidelines

### Adding New Tiles/Sections
1. Identify operator question to answer
2. Map to existing endpoint data or create minimal new endpoint
3. Implement frontend rendering with graceful fallbacks
4. Add tests for data parsing and error states
5. Document in this specification

### Data Source Changes
1. Update affected tile implementations
2. Maintain backward compatibility where possible
3. Update data contract documentation
4. Run full dashboard test suite

### Security Updates
1. Review redaction logic for new data fields
2. Validate input parameters on all endpoints
3. Update allowlists for ProjectX chat jobs
4. Test error handling and boundary conditions

## Future Enhancements Roadmap

### Phase 2: Enhanced Analytics (Q1 2024)
1. **Predictive Analytics**: ML-based anomaly detection for system metrics
2. **Performance Benchmarking**: Historical comparison and trend analysis
3. **Capacity Planning**: Resource utilization forecasts
4. **Custom Dashboards**: Operator-configurable widget layouts

### Phase 3: Advanced Diagnostics (Q2 2024)
1. **Root Cause Analysis**: Automated failure correlation and diagnosis
2. **Intent Replay**: Safe replay of failed intents (requires new POST endpoint)
3. **Agent Maintenance Mode**: Temporary agent suspension (requires control endpoints)
4. **Diagnostic Tools**: One-click system diagnostics and health checks

### Phase 4: Enterprise Features (Q3 2024)
1. **Multi-tenant Views**: Role-based dashboard customization
2. **Audit Trail**: Comprehensive operator action logging
3. **Compliance Reporting**: Automated regulatory compliance checks
4. **Integration API**: External system integration points

### Phase 5: Autonomous Operations (Q4 2024)
1. **Self-healing Recommendations**: AI-driven system optimization suggestions
2. **Predictive Maintenance**: Proactive issue detection and resolution
3. **Workflow Automation**: Automated operator task execution
4. **Knowledge Base Integration**: Context-aware help and documentation

## Version History

### v2.0 (Current)
- Comprehensive ProjectX integration
- Real-time WebSocket updates
- Task and orchestration monitoring
- Memory and conversation tracking
- Advanced analytics and diagnostics

### v1.0 (Previous)
- Basic broker monitoring
- Agent status and capability display
- Simple activity feed
- Basic failure analysis

---

*Last Updated: 2024-01-15*
*Version: 2.0*
*Maintainer: Dashboard Worker 5*