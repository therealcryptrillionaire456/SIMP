#!/bin/bash
# Graphify SIMP - Daily architecture snapshot
# Creates knowledge graphs of the SIMP repository for agent reasoning

set -e  # Exit on error

# Configuration
REPO_ROOT="/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
GRAPHIFY_ROOT="/Users/kaseymarcelle/Downloads/graphify"
OUTPUT_DIR="$REPO_ROOT/.graphify"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "================================================"
echo "📊 Graphify SIMP Architecture Snapshot"
echo "Timestamp: $TIMESTAMP"
echo "Repo: $REPO_ROOT"
echo "Output: $OUTPUT_DIR"
echo "================================================"

# Create output directory
mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/snapshots"

# Check if Graphify is available
if [ ! -d "$GRAPHIFY_ROOT" ]; then
    echo "❌ Graphify not found at: $GRAPHIFY_ROOT"
    echo "Please clone: git clone https://github.com/safishamsi/graphify"
    exit 1
fi

# Create Python script to run Graphify
cat > /tmp/graphify_simp.py << 'PYEOF'
#!/usr/bin/env python3
"""Run Graphify on SIMP repository and export architecture maps."""
import sys
import json
from pathlib import Path

# Add Graphify to path
graphify_path = Path("/Users/kaseymarcelle/Downloads/graphify")
sys.path.insert(0, str(graphify_path))

try:
    from graphify.extract import collect_files, extract
    from graphify.build import build
    from graphify.export import to_json, to_html
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
except ImportError as e:
    print(f"❌ Failed to import Graphify: {e}")
    print("Make sure Graphify is installed: pip install graphifyy")
    sys.exit(1)

def main():
    repo_root = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")
    output_dir = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/.graphify")
    
    print(f"🔍 Analyzing SIMP repository: {repo_root}")
    
    # 1. Collect files
    print("📁 Collecting files...")
    try:
        files = collect_files(repo_root)
        print(f"   Found {len(files)} files")
    except Exception as e:
        print(f"❌ Failed to collect files: {e}")
        # Fallback: manually collect Python files
        files = list(repo_root.rglob("*.py"))
        print(f"   Fallback: Found {len(files)} Python files")
    
    if not files:
        print("❌ No files found")
        return
    
    # 2. Extract knowledge graph
    print("🧠 Extracting knowledge graph...")
    try:
        extraction = extract(files[:100])  # Limit to 100 files for speed
        print(f"   Extracted {len(extraction.get('nodes', []))} nodes")
        print(f"   Extracted {len(extraction.get('edges', []))} edges")
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        print("   Creating minimal graph...")
        # Create a minimal graph with directory structure
        extraction = {
            "nodes": [
                {"id": "simp_root", "label": "SIMP Root", "source_file": "ROOT", "source_location": "ROOT"}
            ],
            "edges": []
        }
    
    # 3. Build graph
    print("🕸️ Building graph...")
    try:
        G = build([extraction])
        print(f"   Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    except Exception as e:
        print(f"❌ Graph building failed: {e}")
        print("   Creating empty graph...")
        import networkx as nx
        G = nx.Graph()
    
    # 4. Analyze graph
    print("📈 Analyzing graph structure...")
    try:
        central_nodes = god_nodes(G)
        surprising = surprising_connections(G)
        questions = suggest_questions(G)
        
        analysis = {
            "central_nodes": central_nodes[:10],  # Top 10
            "surprising_connections": surprising[:10],
            "suggested_questions": questions[:10],
            "graph_stats": {
                "nodes": G.number_of_nodes(),
                "edges": G.number_of_edges(),
                "density": nx.density(G) if G.number_of_nodes() > 0 else 0
            }
        }
        
        print(f"   Found {len(central_nodes)} central nodes")
        print(f"   Found {len(surprising)} surprising connections")
        print(f"   Generated {len(questions)} suggested questions")
        
    except Exception as e:
        print(f"⚠️ Graph analysis failed: {e}")
        analysis = {"error": str(e)}
    
    # 5. Export
    print("💾 Exporting results...")
    
    # Export JSON graph
    try:
        json_output = to_json(G)
        (output_dir / "simp_graph.json").write_text(json_output)
        print(f"   ✅ JSON graph saved to: {output_dir / 'simp_graph.json'}")
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
    
    # Export HTML visualization
    try:
        html_output = to_html(G)
        (output_dir / "simp_graph.html").write_text(html_output)
        print(f"   ✅ HTML visualization saved to: {output_dir / 'simp_graph.html'}")
    except Exception as e:
        print(f"❌ HTML export failed: {e}")
    
    # Save analysis
    (output_dir / "analysis.json").write_text(json.dumps(analysis, indent=2))
    print(f"   ✅ Analysis saved to: {output_dir / 'analysis.json'}")
    
    # Save snapshot with timestamp
    snapshot_dir = output_dir / "snapshots" / f"snapshot_{sys.argv[1] if len(sys.argv) > 1 else 'latest'}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "simp_graph.json").write_text(json_output if 'json_output' in locals() else '{}')
    (snapshot_dir / "analysis.json").write_text(json.dumps(analysis, indent=2))
    print(f"   📸 Snapshot saved to: {snapshot_dir}")
    
    print("\n✅ Graphify SIMP complete!")
    print(f"📊 Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"📁 Output: {output_dir}")

if __name__ == "__main__":
    main()
PYEOF

# Run Graphify
echo "🚀 Running Graphify on SIMP repository..."
cd "$REPO_ROOT"
python3 /tmp/graphify_simp.py "$TIMESTAMP"

# Create a simple README
cat > "$OUTPUT_DIR/README.md" << 'README'
# SIMP Architecture Maps

This directory contains automatically generated knowledge graphs of the SIMP repository.

## Files

- `simp_graph.json` - Latest knowledge graph in JSON format
- `simp_graph.html` - Interactive HTML visualization
- `analysis.json` - Graph analysis (central nodes, surprising connections, etc.)
- `snapshots/` - Historical snapshots with timestamps

## Usage

### For Agents (Goose/Stray Goose):
When reasoning about SIMP architecture, consult these files instead of scanning raw code:

```python
# Example: Load the graph
import json
with open('.graphify/simp_graph.json') as f:
    graph = json.load(f)
    
# Find central modules
with open('.graphify/analysis.json') as f:
    analysis = json.load(f)
    central_nodes = analysis.get('central_nodes', [])
```

### For Developers:
- Open `simp_graph.html` in browser to explore interactively
- Check `analysis.json` for architectural insights
- Compare snapshots to see how architecture evolves

## Regeneration

Run manually:
```bash
./tools/graphify_simp.sh
```

Or schedule daily (add to crontab):
```bash
# Daily at 2 AM
0 2 * * * /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp/tools/graphify_simp.sh
```

## Graph Contents

The knowledge graph includes:
- Python modules and their relationships
- Classes, functions, and their dependencies
- Import relationships
- Call graphs (where available)
- Community structure (clusters of related code)

README

echo ""
echo "================================================"
echo "✅ Graphify SIMP snapshot complete!"
echo "📁 Output directory: $OUTPUT_DIR"
echo "📊 Files generated:"
ls -la "$OUTPUT_DIR"
echo "================================================"
