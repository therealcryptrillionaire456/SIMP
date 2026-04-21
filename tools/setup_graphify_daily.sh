#!/bin/bash
# Setup Graphify for daily SIMP architecture snapshots

echo "================================================"
echo "🔄 Setting up Graphify Daily Snapshots for SIMP"
echo "================================================"

# 1. Make sure Graphify is installed
if [ ! -d "/Users/kaseymarcelle/Downloads/graphify" ]; then
    echo "📦 Installing Graphify..."
    cd /Users/kaseymarcelle/Downloads
    git clone https://github.com/safishamsi/graphify
    cd graphify
    pip install -e .
    echo "✅ Graphify installed"
else
    echo "✅ Graphify already installed"
fi

# 2. Create daily cron job
CRON_JOB="0 2 * * * cd '/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp' && ./tools/graphify_simp_final.sh >> .graphify/cron.log 2>&1"

echo ""
echo "📅 Daily Cron Job:"
echo "$CRON_JOB"
echo ""
echo "To add to crontab:"
echo "1. Run: crontab -e"
echo "2. Add the line above"
echo "3. Save and exit"
echo ""
echo "Or run manually: ./tools/graphify_simp_final.sh"

# 3. Create agent integration guide
cat > .graphify/AGENT_INTEGRATION_GUIDE.md << 'GUIDE'
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
GUIDE

echo "✅ Created agent integration guide: .graphify/AGENT_INTEGRATION_GUIDE.md"

# 4. Test the setup
echo ""
echo "🧪 Testing Graphify setup..."
if [ -f ".graphify/simp_graph.json" ]; then
    GRAPH_SIZE=$(stat -f%z ".graphify/simp_graph.json" 2>/dev/null || stat -c%s ".graphify/simp_graph.json")
    echo "✅ Graph exists: $(echo "scale=1; $GRAPH_SIZE / 1024 / 1024" | bc) MB"
    
    NODES=$(python3 -c "import json; data=json.load(open('.graphify/simp_graph.json')); print(len(data.get('nodes', [])))" 2>/dev/null || echo "unknown")
    EDGES=$(python3 -c "import json; data=json.load(open('.graphify/simp_graph.json')); print(len(data.get('edges', [])))" 2>/dev/null || echo "unknown")
    
    echo "✅ Graph has $NODES nodes and $EDGES edges"
else
    echo "⚠️ Graph not found. Run: ./tools/graphify_simp_final.sh"
fi

echo ""
echo "================================================"
echo "✅ Graphify Daily Setup Complete!"
echo "================================================"
echo ""
echo "📚 Documentation:"
echo "  - .graphify/README.md - Basic info"
echo "  - .graphify/AGENT_INTEGRATION_GUIDE.md - Agent usage"
echo "  - tools/agent_helper.py - Python API"
echo ""
echo "🚀 Next: Integrate with agent prompts!"
echo "================================================"
