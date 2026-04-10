# SIMP System Overview

## Architecture Vision

SIMP (Structured Intent Messaging Protocol) is designed as "The HTTP of Agentic AI" — a broker-based protocol that routes typed intents between registered agents. The system enables A2A (Agent-to-Agent) compatibility, FinancialOps simulation, and uses ProjectX as the native self-maintaining kernel.

## Core Architecture Flow

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│                 │    │                      │    │                 │
│   Agents        │────▶   DecisionSummary    │────▶    A2APlan      │
│   (QuantumArb,  │    │   (Aggregator)       │    │   (Builder)     │
│   KashClaw,     │    │                      │    │                 │
│   KloutBot)     │    └──────────────────────┘    └────────┬────────┘
│                 │                                         │
└─────────────────┘                                         │
                                                            ▼
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│                 │    │                      │    │                 │
│   Broker &      │◀───│   A2A Safety &       │◀───│   Dashboard &   │
│   Dashboard     │    │   Simulator          │    │   Monitoring    │
│   (Current)     │    │   (Risk Evaluation)  │    │   (Operator)    │
│                 │    │                      │    │                 │
└─────────────────┘    └──────────────────────┘    └─────────────────┘
```

## Component Descriptions

### 1. Agents Layer
**Purpose:** Generate trading decisions and strategies based on market analysis.

**Current Agents:**
- **QuantumArb:** Arbitrage detection across venues (analysis-only, no execution)
  - Location: `simp/agents/quantumarb_agent.py`
  - Status: Scaffolded with safety gates, dry-run enforcement
  - Capabilities: arbitrage, cross_venue, latency_arbitrage
  
- **KloutBot:** Long-horizon strategy generation with TimesFM integration
  - Location: `simp/agents/kloutbot_agent.py`
  - Status: Horizon system development, compiler interface complete
  - Capabilities: strategy generation, horizon planning
  
- **KashClaw Gemma:** Local LLM reasoning worker (Gemma4 via Ollama)
  - Location: External bridge at port 8780
  - Status: HTTP agent, currently degraded (endpoint unreachable)
  - Capabilities: research, planning, code_task, summarization
  
- **ProjectX Native:** Self-maintaining kernel agent
  - Location: External at port 8771
  - Status: Active (34 intents received, 29 completed)
  - Capabilities: native_agent_repo_scan, health_check, code_maintenance

**Output:** `AgentDecisionSummary` objects containing:
- Instrument identification
- Trading side (BUY/SELL/HOLD)
- Quantity and units
- Confidence score
- Agent metadata

### 2. DecisionSummary Aggregator
**Purpose:** Collect and normalize decisions from multiple agents into a coherent view.

**Key Functions:**
- Normalize confidence scores across agents
- Resolve conflicting recommendations
- Apply agent weighting (future capability)
- Generate unified decision summary

**Location:** `simp/financial/a2a_aggregator.py` (495 lines, 13 functions)
**Status:** Implemented with comprehensive test coverage

### 3. A2APlan Builder
**Purpose:** Transform aggregated decisions into executable trading plans.

**Key Functions:**
- Convert decisions to specific trade instructions
- Apply portfolio constraints
- Set execution parameters
- Generate `A2APlan` with risk posture classification

**Output Structure (from `simp/financial/a2a_schema.py`):**
```python
@dataclass
class A2APlan:
    trades: List[TradeInstruction]
    risk_posture: RiskPosture  # conservative/neutral/aggressive
    execution_mode: ExecutionMode  # simulated_only/live_candidate
    generated_at: str  # ISO8601 timestamp
```

**Status:** Core schema implemented (389 lines, 6 classes, 15 functions)

### 4. A2A Safety & Simulator
**Purpose:** Evaluate plans for risk and simulate execution before live deployment.

**Safety Components:**
- **Risk Evaluation:** Check plans against safety thresholds
- **Blocking Logic:** Prevent unsafe plans from proceeding
- **Stub Simulation:** Simulate trade execution without real funds
- **Result Interpretation:** Analyze simulation outcomes

**Workflows:**
1. **Safety Evaluation Only:** Risk assessment without simulation
2. **Full Simulation Pipeline:** End-to-end simulation including trade execution
3. **Batch Scenario Testing:** Multiple scenario parameter sweeps

**Location:** `simp/financial/a2a_safety.py` (261 lines) and `a2a_simulator.py` (349 lines)
**Status:** Implemented with 9/9 tests passing

### 5. TimesFM Integration
**Purpose:** Provide shared, policy-gated forecasting capability to all SIMP agents.

**Key Features:**
- Time-series forecasting using Google's TimesFM model
- Safety controls and audit logging
- Feature-flag driven behavior
- Shadow mode for development safety

**Components:**
- **TimesFM Service:** `simp/integrations/timesfm_service.py` (664 lines, 6 classes)
- **Policy Engine:** `simp/integrations/timesfm_policy_engine.py` (293 lines, 3 classes)
- **KashClaw Shim:** `simp/integrations/kashclaw_shim.py` (600 lines, 2 classes)

**Integration Points:**
- KloutBot horizon advice (8/16/32 step forecasts)
- QuantumArb opportunity timing
- KashClaw execution scheduling

**Service Design:**
- `ForecastRequest`/`ForecastResponse` data classes
- Cache-aware forecasting with series_id keys
- Environment variable controls for safety

### 6. Dashboard (Current Implementation)
**Purpose:** Operator console for system monitoring and control.

**Current Implementation:**
- **Server:** `dashboard/server.py` (1670 lines, FastAPI on port 8050)
- **Frontend:** `dashboard/static/app.js` (2031 lines) + HTML/CSS
- **Broker Integration:** Recent commits show dashboard → broker data flow

**Current Capabilities:**
- Real-time system status display via WebSocket
- Task filtering and search (50 tasks per page)
- Activity charts (Chart.js integration)
- Security headers and error handling
- ProjectX action routing through broker

**Recent Enhancements (Sprints 20-21):**
- SSE task streaming implementation
- `/skills` endpoint addition
- Dashboard remediation and capability-gap handling
- Operator docs overview integration

### 7. Broker System (Current)
**Purpose:** Central message bus for intent routing between agents.

**Current State:**
- **Location:** `simp/server/broker.py` (1362 lines, Flask on port 5555)
- **Status:** Active with 6 registered agents
- **Health:** `{"status":"ok","agents_online":6,"simp_version":"1.0"}`

**Key Features:**
- Intent routing with policy-based fallback
- Agent registration and heartbeat monitoring
- Security audit logging
- Rate limiting and request guards
- File-based and HTTP agent support

**Recent Enhancements:**
- SSE (Server-Sent Events) for real-time updates
- KloutBotAgent self-spawning capability
- Dashboard fallback panels from broker data
- Enhanced security with control token authentication

## Data Flow Example

### Scenario: Arbitrage Opportunity Detection
```
1. Market Signal → BullBear Pipeline
2. BullBear → SIMP Router → QuantumArb
3. QuantumArb → Arbitrage Analysis → AgentDecisionSummary
4. Multiple Agents → DecisionSummary Aggregator
5. Aggregated Decisions → A2APlan Builder
6. A2APlan → A2A Safety Evaluation
7. Safety Pass → Stub Simulation
8. Simulation Results → Human/KashClaw Review
9. Approved → Live Execution (future)
```

## Safety Architecture

### Core Principles
1. **Safety-by-Default:** All plans are blocked unless explicitly allowed
2. **Pure Functions:** Core logic is side-effect-free and deterministic
3. **Feature Flags:** Live capabilities require explicit enablement
4. **Audit Logging:** All decisions and simulations are logged

### Safety Gates
1. **QuantumArb:** Dry-run only until triple-verification
2. **TimesFM:** Shadow mode for development, policy-gated forecasts
3. **A2A Safety:** Risk thresholds and blocking logic
4. **Execution:** Simulated-only until explicit promotion

## Integration Patterns

### 1. Agent → Core Integration
- Agents emit `AgentDecisionSummary` objects
- Pure data structures (no side effects)
- Standardized field names and types
- Timestamped for auditability

### 2. Core → Safety Integration
- `A2APlan` objects passed to safety layer
- Risk evaluation returns blocking decisions
- Simulation produces realistic outcomes
- Results feed back to planning

### 3. External Service Integration (TimesFM)
- Policy-gated service calls
- Cache-aware request/response
- Feature flag controls
- Shadow mode for safety

### 4. Dashboard → Broker Integration
- Broker provides real-time data via SSE
- Dashboard actions route through broker
- Fallback panels use broker data when needed
- WebSocket for live updates

## Current State vs Vision

### Implemented (Now)
- A2A core schemas and data structures (389 lines, 6 classes)
- Safety evaluation logic (261 lines + 349 lines simulator)
- KloutBot compiler interface (907 lines agent)
- TimesFM service design (664 lines service + 293 lines policy)
- QuantumArb agent scaffold (913 lines)
- Broker functionality (1362 lines + 816 lines HTTP server)
- Dashboard with WebSocket (1670 lines server + 2031 lines JS)

### In Progress
- KloutBot horizon system integration
- TimesFM service implementation
- QuantumArb verification protocols
- Dashboard requirements definition

### Future Vision
- Full A2A protocol compatibility
- Multi-scheme authentication
- Live revenue generation
- Recursive self-improvement
- Enterprise readiness

## Key Design Decisions

### ADR-001: Single Funnel Design
All agent decisions flow through a single aggregation → planning → safety funnel for consistency and auditability.

### ADR-002: Safety-by-Default
Blocking logic applied before any simulation or execution, with explicit allow-lists rather than deny-lists.

### ADR-003: Schema Evolution
Forward/backward compatibility patterns for data structure evolution without breaking existing integrations.

### ADR-004: Horizon Buckets
KloutBot uses 8/16/32 step horizons from TimesFM advice for consistent long-horizon planning.

## System Characteristics

### Deterministic
Core logic uses pure functions with no side effects for testability and reproducibility.

### Auditable
All decisions, plans, and simulations are logged with timestamps and agent metadata.

### Safe
Multiple layers of safety gates prevent unintended live execution.

### Extensible
Modular design allows new agents and components to be added without disrupting existing functionality.

### Observable
Dashboard provides real-time monitoring with WebSocket updates and activity charts.

## Test Coverage Status
- **Total Tests:** 832 passing, 10 skipped (47.35s runtime)
- **A2A Core:** 110/110 tests passing
- **A2A Safety:** 32/32 tests passing
- **Security:** Comprehensive test suite
- **Integration:** Multiple test files for each component

## Terminology Standards

### Component Names
- **A2A Core** - Core schemas and aggregation logic
- **A2A Safety** - Risk evaluation and blocking system
- **KloutBot** - Strategy generation agent (camel case)
- **TimesFM** - Forecasting service
- **QuantumArb** - Arbitrage detection agent (no space)
- **KashClaw** - Multi-venue execution agent
- **Dashboard** - Operator console
- **Broker** - Message routing system

### Field Names (A2A Schema)
- `risk_posture` - Risk classification (conservative/neutral/aggressive)
- `quantity` - Trade amount (not "size")
- `side` - Trading action (BUY/SELL/HOLD, not "direction")
- `confidence` - Agent certainty score (0.0-1.0)
- `horizon_steps` - Forecast steps ahead (8/16/32)

### Workflow Terms
- **Safety Evaluation** - Comprehensive risk assessment including blocking
- **Simulation** - Stub execution of trades (not "stub execution")
- **A2APlan** - Aggregated trading plan from multiple agents
- **Decision Tree** - KloutBot strategy output
- **Forecast** - TimesFM time-series prediction (not "prediction")

### Execution States
- **blocked** - Prevented by safety checks (not "rejected")
- **passed** - Approved by safety checks (not "approved")
- **live** - Ready for real execution (matches `ExecutionMode.LIVE_CANDIDATE`)
- **simulated** - Test execution only (matches `ExecutionMode.SIMULATED_ONLY`)

## Next Architecture Milestones

1. **TimesFM Integration Completion** - Service implementation and testing
2. **QuantumArb Verification** - Triple-verification protocol definition
3. **Dashboard MVP** - Minimum feature set implementation
4. **Full A2A Compatibility** - AgentCard system and protocol conformance
5. **Revenue Generation** - Live trading with safety controls

---
**Document Version:** 2.1  
**Last Updated:** 2026-04-09  
**Maintained By:** Goose #8 (Docs Consolidator & ISO)  
**Lines of Code Analyzed:** ~20K across SIMP core components  
**Test Status:** 832 passing, 10 skipped  
**Broker Status:** Active on port 5555 with 6 agents  
**Terminology Status:** Standardized per audit recommendations