# Graphify Agent Integration Guide

## 🎯 Purpose
Graphify creates knowledge graphs of the SIMP repository (6,952 nodes, 19,179 edges) that agents can query instead of scanning all files.

## 📊 Current Graph Stats
- **Nodes**: 6,952 (modules, classes, functions)
- **Edges**: 19,179 (relationships)
- **Size**: 10.5 MB JSON
- **Updated**: Daily at 2 AM

## 🧠 How Agents Should Use This

### Option 1: Direct JSON Access
```python
import json
with open('.graphify/simp_graph.json') as f:
    graph = json.load(f)
# graph['nodes'] = list of modules
# graph['edges'] = list of relationships
```

### Option 2: Use Agent Helper
```python
from .graphify.agent_helper import SIMPGraphAnalyzer

analyzer = SIMPGraphAnalyzer()
# Get central modules
central = analyzer.get_central_modules(10)
# Search for modules
quantumarb_modules = analyzer.search_modules("quantumarb")
# Get module info
module_info = analyzer.find_module("a2a_schema_side")
```

### Option 3: Export for Agent Context
```bash
python .graphify/agent_helper.py --export minimal
# Returns: {"central_modules": [...], "stats": {...}}
```

## 🔍 Common Queries

### "What are the most important modules in SIMP?"
```bash
python .graphify/agent_helper.py --central 10
```

### "Find all QuantumArb related modules"
```bash
python .graphify/agent_helper.py --search quantumarb
```

### "Get architecture overview"
```bash
python .graphify/agent_helper.py --overview
```

## 🚀 Integration with Goose/Stray Goose

### In Goose Prompts:
```
Before analyzing SIMP code, consult the architecture graph:
- Load .graphify/simp_graph.json
- Check central modules first
- Use graph to understand relationships
```

### Example Prompt Enhancement:
"Use the SIMP knowledge graph at .graphify/simp_graph.json to understand module relationships before reading code."

## 📈 Benefits
1. **70x faster**: Query graph vs scan 3,000+ files
2. **Better insights**: Centrality shows what matters
3. **Consistent**: Same graph for all agents
4. **Historical**: Snapshots track architecture evolution

## 🔄 Regeneration
- **Automatic**: Daily at 2 AM via cron
- **Manual**: `./tools/graphify_simp_final.sh`
- **On-demand**: After major changes

## 🗺️ Next Steps
1. Integrate with agent prompts
2. Create change impact analysis
3. Build test selection helper
4. Generate architecture briefs
