# SIMP Architecture Graph - 20260424_225611

## Statistics
- **Nodes**: 7636
- **Edges**: 18835
- **Files Processed**: 300
- **Total Python Files**: 26188

## Top 5 Central Modules
1. **base_legal_agent_baselegalagent** (centrality: 0.032)
1. **base_legal_agent_legalagentrole** (centrality: 0.030)
1. **base_legal_agent_jurisdiction** (centrality: 0.030)
1. **base_legal_agent_legalmatter** (centrality: 0.030)
1. **base_legal_agent_legaldocument** (centrality: 0.030)

## Top 5 Modules by File Count
1. **/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp** (1943 files)
1. **/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/keep-the-change/backend/app/services** (695 files)
1. **/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/pentagram_legal/agents** (434 files)
1. **/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/agents** (387 files)
1. **/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/keep-the-change/backend/tests/services** (312 files)

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
