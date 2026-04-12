#!/bin/bash
# Graphify SIMP - Final working version
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
cat > /tmp/graphify_simp_final.py << 'PYEOF'
#!/usr/bin/env python3
"""Run Graphify on SIMP repository and export architecture maps."""
import sys
import json
import networkx as nx
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Add Graphify to path
graphify_path = Path("/Users/kaseymarcelle/Downloads/graphify")
sys.path.insert(0, str(graphify_path))

try:
    from graphify.extract import collect_files, extract
    from graphify.build import build
except ImportError as e:
    print(f"❌ Failed to import Graphify: {e}")
    print("Make sure Graphify is installed: pip install graphifyy")
    sys.exit(1)

def analyze_graph(G):
    """Analyze graph structure."""
    analysis = {
        "central_nodes": [],
        "graph_stats": {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "density": nx.density(G) if G.number_of_nodes() > 0 else 0,
            "connected_components": nx.number_connected_components(G)
        },
        "top_modules": [],
        "file_types": defaultdict(int),
        "timestamp": datetime.now().isoformat()
    }
    
    # Calculate centrality
    if G.number_of_nodes() > 0:
        try:
            centrality = nx.degree_centrality(G)
            central_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:50]
            analysis["central_nodes"] = [
                {"node": node, "centrality": score}
                for node, score in central_nodes
            ]
        except Exception as e:
            print(f"⚠️ Centrality calculation failed: {e}")
    
    # Count file types and find modules
    dir_counts = defaultdict(int)
    for node, data in G.nodes(data=True):
        file_type = data.get("file_type", "unknown")
        analysis["file_types"][file_type] += 1
        
        # Extract module/directory from node ID
        if "source_file" in data:
            source_file = data["source_file"]
            if "/" in source_file:
                dir_path = "/".join(source_file.split("/")[:-1])
                if dir_path:
                    dir_counts[dir_path] += 1
    
    analysis["top_modules"] = sorted(dir_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    
    return analysis

def main():
    repo_root = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")
    output_dir = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/.graphify")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"🔍 Analyzing SIMP repository: {repo_root}")
    print(f"📅 Timestamp: {timestamp}")
    
    # 1. Collect files
    print("📁 Collecting files...")
    try:
        files = collect_files(repo_root)
        print(f"   Found {len(files)} total files")
        
        # Limit to Python files for now
        python_files = [f for f in files if str(f).endswith('.py')]
        print(f"   Python files: {len(python_files)}")
        
        if not python_files:
            print("❌ No Python files found")
            return
            
        files_to_process = python_files[:300]  # Increased limit
        print(f"   Processing {len(files_to_process)} Python files")
        
    except Exception as e:
        print(f"❌ Failed to collect files: {e}")
        # Fallback: manually collect Python files
        files_to_process = list(repo_root.rglob("*.py"))[:300]
        print(f"   Fallback: Found {len(files_to_process)} Python files")
    
    if not files_to_process:
        print("❌ No files to process")
        return
    
    # 2. Extract knowledge graph
    print("🧠 Extracting knowledge graph...")
    try:
        extraction = extract(files_to_process)
        print(f"   ✅ Extracted {len(extraction.get('nodes', []))} nodes")
        print(f"   ✅ Extracted {len(extraction.get('edges', []))} edges")
        
        # 3. Build graph
        print("🕸️ Building graph...")
        G = build([extraction])
        print(f"   ✅ Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        
    except Exception as e:
        print(f"❌ Graphify extraction failed: {e}")
        return
    
    if G is None or G.number_of_nodes() == 0:
        print("❌ Failed to create graph")
        return
    
    # 4. Analyze graph
    print("📈 Analyzing graph structure...")
    analysis = analyze_graph(G)
    
    print(f"   📊 Graph stats: {analysis['graph_stats']['nodes']} nodes, {analysis['graph_stats']['edges']} edges")
    print(f"   🏆 Central nodes: {len(analysis['central_nodes'])}")
    print(f"   📁 File types: {dict(analysis['file_types'])}")
    
    # 5. Export JSON graph
    print("💾 Exporting results...")
    try:
        # Convert to simple JSON format
        graph_data = {
            "metadata": {
                "timestamp": timestamp,
                "repo": str(repo_root),
                "files_processed": len(files_to_process),
                "total_files": len(python_files)
            },
            "nodes": [
                {"id": node, **data}
                for node, data in G.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **data}
                for u, v, data in G.edges(data=True)
            ]
        }
        
        # Save main graph
        json_path = output_dir / "simp_graph.json"
        with open(json_path, 'w') as f:
            json.dump(graph_data, f, indent=2)
        print(f"   ✅ JSON graph saved to: {json_path}")
        print(f"   📦 File size: {json_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        # Save analysis
        analysis_path = output_dir / "analysis.json"
        with open(analysis_path, 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"   ✅ Analysis saved to: {analysis_path}")
        
        # Create simple README
        readme_content = f"""# SIMP Architecture Graph - {timestamp}

## Statistics
- **Nodes**: {analysis['graph_stats']['nodes']}
- **Edges**: {analysis['graph_stats']['edges']}
- **Files Processed**: {len(files_to_process)}
- **Total Python Files**: {len(python_files)}

## Top 5 Central Modules
{chr(10).join(f"1. **{node['node']}** (centrality: {node['centrality']:.3f})" for node in analysis['central_nodes'][:5])}

## Top 5 Modules by File Count
{chr(10).join(f"1. **{module}** ({count} files)" for module, count in analysis['top_modules'][:5])}

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
"""
        
        readme_path = output_dir / "README.md"
        readme_path.write_text(readme_content)
        print(f"   📝 README saved to: {readme_path}")
        
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. Create simple HTML visualization
    try:
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>SIMP Architecture Graph - {timestamp}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; line-height: 1.6; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        .stats {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #3498db; }}
        .module-list {{ margin: 20px 0; }}
        .module {{ padding: 8px 12px; margin: 4px; background: #e8f4fc; border-radius: 4px; display: inline-block; }}
        .central {{ background: #fff3cd; border-left: 4px solid #ffc107; }}
        .downloads {{ margin-top: 30px; padding: 20px; background: #f1f8e9; border-radius: 8px; }}
        .highlight {{ background: #e3f2fd; padding: 2px 6px; border-radius: 3px; }}
    </style>
</head>
<body>
    <h1>📊 SIMP Architecture Graph</h1>
    <p>Generated: <span class="highlight">{timestamp}</span></p>
    
    <div class="stats">
        <h2>📈 Graph Statistics</h2>
        <p><strong>Nodes:</strong> <span class="highlight">{analysis['graph_stats']['nodes']}</span></p>
        <p><strong>Edges:</strong> <span class="highlight">{analysis['graph_stats']['edges']}</span></p>
        <p><strong>Density:</strong> <span class="highlight">{analysis['graph_stats']['density']:.4f}</span></p>
        <p><strong>Connected Components:</strong> <span class="highlight">{analysis['graph_stats']['connected_components']}</span></p>
        <p><strong>Files Processed:</strong> <span class="highlight">{len(files_to_process)}</span></p>
    </div>
    
    <div class="stats">
        <h2>🏆 Top 10 Central Modules</h2>
        <p>These are the most connected/important modules in SIMP:</p>
        <ol>
            {"".join(f'<li><strong>{node["node"]}</strong> (centrality: {node["centrality"]:.3f})</li>' for node in analysis["central_nodes"][:10])}
        </ol>
    </div>
    
    <div class="stats">
        <h2>📁 Top 10 Modules by File Count</h2>
        <ol>
            {"".join(f'<li><strong>{module}</strong> ({count} files)</li>' for module, count in analysis["top_modules"][:10])}
        </ol>
    </div>
    
    <div class="module-list">
        <h2>🔗 Sample of Graph Nodes ({analysis['graph_stats']['nodes']} total)</h2>
        <div style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 4px;">
            {"".join(f'<span class="module{" central" if node in [n["node"] for n in analysis["central_nodes"][:10]] else ""}">{node}</span>' for node in sorted([n for n in G.nodes() if len(str(n)) < 100])[:200])}
        </div>
        {f'<p>... and {analysis["graph_stats"]["nodes"] - 200} more nodes</p>' if analysis['graph_stats']['nodes'] > 200 else ''}
    </div>
    
    <div class="downloads">
        <h2>💾 Download Files</h2>
        <ul>
            <li><a href="simp_graph.json" download>simp_graph.json</a> - Complete knowledge graph ({json_path.stat().st_size // 1024} KB)</li>
            <li><a href="analysis.json" download>analysis.json</a> - Analysis and statistics</li>
            <li><a href="agent_helper.py" download>agent_helper.py</a> - Python helper for AI agents</li>
            <li><a href="README.md" download>README.md</a> - Documentation</li>
        </ul>
        
        <h3 style="margin-top: 20px;">🧠 For AI Agents</h3>
        <pre><code>from .graphify.agent_helper import SIMPGraphAnalyzer
analyzer = SIMPGraphAnalyzer()
central_modules = analyzer.get_central_modules(10)
print(f"Top modules: {[m['node'] for m in central_modules]}")</code></pre>
    </div>
    
    <footer style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666;">
        <p>Generated by Graphify SIMP snapshot tool. Use this graph to understand SIMP architecture without scanning all files.</p>
    </footer>
</body>
</html>"""
        
        html_path = output_dir / "simp_graph.html"
        html_path.write_text(html_content)
        print(f"   ✅ HTML visualization saved to: {html_path}")
        
    except Exception as e:
        print(f"⚠️ HTML export failed: {e}")
    
    # 7. Save snapshot
    snapshot_dir = output_dir / "snapshots" / f"snapshot_{timestamp}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        (snapshot_dir / "simp_graph.json").write_text(json.dumps(graph_data, indent=2))
        (snapshot_dir / "analysis.json").write_text(json.dumps(analysis, indent=2))
        print(f"   📸 Snapshot saved to: {snapshot_dir}")
    except:
        pass
    
    print("\n" + "="*50)
    print("✅ Graphify SIMP complete!")
    print(f"📊 Graph: {analysis['graph_stats']['nodes']} nodes, {analysis['graph_stats']['edges']} edges")
    print(f"📁 Output: {output_dir}")
    print("="*50)

if __name__ == "__main__":
    main()
PYEOF

# Run Graphify
echo "🚀 Running Graphify on SIMP repository..."
cd "$REPO_ROOT"
python3.10 /tmp/graphify_simp_final.py

# Copy agent helper if it doesn't exist
if [ ! -f "$OUTPUT_DIR/agent_helper.py" ]; then
    cp tools/agent_helper.py "$OUTPUT_DIR/agent_helper.py" 2>/dev/null || true
fi

echo ""
echo "================================================"
echo "✅ Graphify SIMP snapshot complete!"
echo "📁 Output directory: $OUTPUT_DIR"
echo "📊 Files generated:"
ls -la "$OUTPUT_DIR"
echo ""
echo "🧠 Try the agent helper:"
echo "python3.10 $OUTPUT_DIR/agent_helper.py"
echo "================================================"
