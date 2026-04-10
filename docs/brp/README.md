# Bill Russell Protocol (BRP) Documentation

Defensive security protocol for SIMP, named after the greatest defensive basketball player ever.

## Documents

| Document | Description |
|----------|-------------|
| [OVERVIEW.md](OVERVIEW.md) | High-level protocol overview and architecture |
| [FINAL_DELIVERABLE.md](FINAL_DELIVERABLE.md) | Complete deliverable specification |
| [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md) | Implementation details and results |
| [TECHNICAL_APPENDIX.md](TECHNICAL_APPENDIX.md) | Technical deep-dive and API reference |
| [INVENTION_DISCLOSURE.md](INVENTION_DISCLOSURE.md) | SIMP invention disclosure with BRP enhancements |
| [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) | Recursive development work log |

## Core Capabilities

1. **Pattern Recognition at Depth** - Detects attack signatures before completion
2. **Autonomous Reasoning Chains** - Threat assessment without human review
3. **Memory Across Time** - Correlates security events weeks apart
4. **Cyber Capability Detection** - Zero-day vulnerability discovery
5. **Cross-domain Synthesis** - Connects disparate threat signals

## Architecture

```
simp/security/brp/          # Core protocol modules
simp/security/brp_bridge.py # Bridge to SIMP broker (Mother Goose)
simp/security/brp_models.py # Typed BRP event schemas
simp/agents/brp_agent.py    # BRP agent for SIMP broker
simp/integrations/brp/      # Log ingestion, alerts, sigma rules, ML pipeline
simp/orchestration/          # BRP integration orchestration
simp/data_acquisition/       # Security dataset collection
scripts/brp/                 # ML training and deployment scripts
config/brp/                  # BRP configuration files
```

## Quick Start

See [OVERVIEW.md](OVERVIEW.md) for getting started with BRP.
