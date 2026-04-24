# SIMP Architecture Graph - 20260424_110819

## Statistics
- **Nodes**: 4556
- **Edges**: 11727
- **Files Processed**: 300
- **Total Python Files**: 26184

## Top 5 Central Modules
1. **base_command** (centrality: 0.080)
1. **exceptions_usererror** (centrality: 0.031)
1. **exceptions_agentsexception** (centrality: 0.030)
1. **tool_functiontool** (centrality: 0.028)
1. **agent_agent** (centrality: 0.028)

## Top 5 Modules by File Count
1. **/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/brp_enhancement/repos/CAI/src/cai/repl/commands** (714 files)
1. **/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/brp_enhancement/integration/modules** (627 files)
1. **/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/brp_enhancement/repos/CAI/src/cai/sdk/agents** (486 files)
1. **/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/agents** (387 files)
1. **/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/brp_enhancement/repos/CAI/src/cai/sdk/agents/tracing** (244 files)

## Usage
This graph can be used by AI agents to understand SIMP architecture without scanning all files.

### For Goose/Stray Goose:
```python
from .graphify.agent_helper import SIMPGraphAnalyzer
analyzer = SIMPGraphAnalyzer()
graph = analyzer.load_graph()
analysis = analyzer.load_analysis()
```

### File List
- `simp_graph.json` - Complete knowledge graph
- `analysis.json` - Analysis and statistics
- `agent_helper.py` - Helper for AI agents
- `simp_graph.html` - Simple visualization
