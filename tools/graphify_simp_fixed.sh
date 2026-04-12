#!/bin/bash
# Graphify SIMP - Fixed version with proper Graphify usage
# Creates knowledge graphs of the SIMP repository for agent reasoning

set -e  # Exit on error

# Configuration
REPO_ROOT="/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
GRAPHIFY_ROOT="/Users/kaseymarcelle/Downloads/graphify"
OUTPUT_DIR="$REPO_ROOT/.graphify"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "================================================"
echo "📊 Graphify SIMP Architecture Snapshot (Fixed)"
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
cat > /tmp/graphify_simp_fixed.py << 'PYEOF'
#!/usr/bin/env python3
"""Run Graphify on SIMP repository and export architecture maps."""
import sys
import json
import networkx as nx
from pathlib import Path
from collections import defaultdict

# Add Graphify to path
graphify_path = Path("/Users/kaseymarcelle/Downloads/graphify")
sys.path.insert(0, str(graphify_path))

try:
    from graphify.extract import collect_files, extract
    from graphify.build import build
    from graphify.export import to_json, to_html, to_graphml
    from graphify.analyze import god_nodes, surprising_connections
except ImportError as e:
    print(f"❌ Failed to import Graphify: {e}")
    print("Make sure Graphify is installed: pip install graphifyy")
    sys.exit(1)

def create_simple_graph_from_files(files):
    """Create a simple graph from file structure when extraction fails."""
    G = nx.Graph()
    
    # Add nodes for each file
    for file_path in files:
        node_id = str(file_path.relative_to(repo_root))
        G.add_node(node_id, label=node_id, source_file=str(file_path), file_type="file")
    
    # Add edges based on directory structure
    for i, file1 in enumerate(files):
        for file2 in files[i+1:]:
            # Connect files in same directory
            if file1.parent == file2.parent:
                node1 = str(file1.relative_to(repo_root))
                node2 = str(file2.relative_to(repo_root))
                G.add_edge(node1, node2, relation="same_directory", confidence="INFERRED")
    
    return G

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
        "file_types": defaultdict(int)
    }
    
    # Calculate centrality
    if G.number_of_nodes() > 0:
        try:
            centrality = nx.degree_centrality(G)
            central_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:20]
            analysis["central_nodes"] = [
                {"node": node, "centrality": score}
                for node, score in central_nodes
            ]
        except:
            pass
    
    # Count file types
    for node, data in G.nodes(data=True):
        file_type = data.get("file_type", "unknown")
        analysis["file_types"][file_type] += 1
    
    # Find top modules (directories)
    dir_counts = defaultdict(int)
    for node in G.nodes():
        if "/" in node:
            dir_path = "/".join(node.split("/")[:-1])
            if dir_path:
                dir_counts[dir_path] += 1
    
    analysis["top_modules"] = sorted(dir_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return analysis

def main():
    global repo_root
    repo_root = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")
    output_dir = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/.graphify")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🔍 Analyzing SIMP repository: {repo_root}")
    
    # 1. Collect files
    print("📁 Collecting files...")
    try:
        files = collect_files(repo_root)
        print(f"   Found {len(files)} files")
        
        # Limit to Python files for now
        python_files = [f for f in files if str(f).endswith('.py')]
        print(f"   Python files: {len(python_files)}")
        
        if not python_files:
            print("❌ No Python files found")
            return
            
        files_to_process = python_files[:200]  # Limit for speed
        print(f"   Processing {len(files_to_process)} files")
        
    except Exception as e:
        print(f"❌ Failed to collect files: {e}")
        # Fallback: manually collect Python files
        files_to_process = list(repo_root.rglob("*.py"))[:200]
        print(f"   Fallback: Found {len(files_to_process)} Python files")
    
    if not files_to_process:
        print("❌ No files to process")
        return
    
    # 2. Try to extract knowledge graph
    print("🧠 Extracting knowledge graph...")
    G = None
    
    try:
        extraction = extract(files_to_process)
        print(f"   Extracted {len(extraction.get('nodes', []))} nodes")
        print(f"   Extracted {len(extraction.get('edges', []))} edges")
        
        # 3. Build graph
        print("🕸️ Building graph...")
        G = build([extraction])
        print(f"   Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        
    except Exception as e:
        print(f"⚠️ Graphify extraction failed: {e}")
        print("   Creating simple file structure graph...")
        G = create_simple_graph_from_files(files_to_process)
        print(f"   Created simple graph with {G.number_of_nodes()} nodes")
    
    if G is None or G.number_of_nodes() == 0:
        print("❌ Failed to create graph")
        return
    
    # 4. Analyze graph
    print("📈 Analyzing graph structure...")
    analysis = analyze_graph(G)
    
    print(f"   Graph stats: {analysis['graph_stats']['nodes']} nodes, {analysis['graph_stats']['edges']} edges")
    print(f"   Central nodes: {len(analysis['central_nodes'])}")
    print(f"   File types: {dict(analysis['file_types'])}")
    
    # 5. Export
    print("💾 Exporting results...")
    
    # Export JSON graph (custom format)
    try:
        # Convert to simple JSON format
        graph_data = {
            "nodes": [
                {"id": node, **data}
                for node, data in G.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **data}
                for u, v, data in G.edges(data=True)
            ]
        }
        
        json_path = output_dir / "simp_graph.json"
        json_path.write_text(json.dumps(graph_data, indent=2))
        print(f"   ✅ JSON graph saved to: {json_path}")
        
        # Also save analysis
        analysis_path = output_dir / "analysis.json"
        analysis_path.write_text(json.dumps(analysis, indent=2))
        print(f"   ✅ Analysis saved to: {analysis_path}")
        
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
    
    # Export GraphML (for tools like Gephi)
    try:
        graphml_path = output_dir / "simp_graph.graphml"
        nx.write_graphml(G, graphml_path)
        print(f"   ✅ GraphML saved to: {graphml_path}")
    except Exception as e:
        print(f"❌ GraphML export failed: {e}")
    
    # Create simple HTML visualization
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SIMP Architecture Graph</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                .stats {{ background: #f5f5f5; padding: 20px; border-radius: 5px; }}
                .node-list {{ margin-top: 20px; }}
                .node {{ padding: 5px; margin: 2px; background: #e0e0e0; display: inline-block; }}
                .central {{ background: #ffcc00; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>📊 SIMP Architecture Graph</h1>
            <p>Generated: {TIMESTAMP}</p>
            
            <div class="stats">
                <h2>Graph Statistics</h2>
                <p>Nodes: {analysis['graph_stats']['nodes']}</p>
                <p>Edges: {analysis['graph_stats']['edges']}</p>
                <p>Density: {analysis['graph_stats']['density']:.4f}</p>
                <p>Connected Components: {analysis['graph_stats']['connected_components']}</p>
            </div>
            
            <div class="stats">
                <h2>Top 10 Central Modules</h2>
                <ol>
                    {"".join(f'<li>{node["node"]} (centrality: {node["centrality"]:.3f})</li>' for node in analysis["central_nodes"][:10])}
                </ol>
            </div>
            
            <div class="stats">
                <h2>Top Modules by File Count</h2>
                <ol>
                    {"".join(f'<li>{module} ({count} files)</li>' for module, count in analysis["top_modules"][:10])}
                </ol>
            </div>
            
            <div class="node-list">
                <h2>All Nodes ({analysis['graph_stats']['nodes']} total)</h2>
                {"".join(f'<span class="node">{"🔗 " if node in [n["node"] for n in analysis["central_nodes"][:5]] else ""}{node}</span>' for node in sorted(G.nodes())[:100])}
                {f'<p>... and {analysis["graph_stats"]["nodes"] - 100} more nodes</p>' if analysis['graph_stats']['nodes'] > 100 else ''}
            </div>
            
            <div style="margin-top: 40px;">
                <h3>Download</h3>
                <ul>
                    <li><a href="simp_graph.json">JSON Graph</a></li>
                    <li><a href="simp_graph.graphml">GraphML (for Gephi)</a></li>
                    <li><a href="analysis.json">Analysis Data</a></li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        html_path = output_dir / "simp_graph.html"
        html_path.write_text(html_content)
        print(f"   ✅ HTML visualization saved to: {html_path}")
        
    except Exception as e:
        print(f"❌ HTML export failed: {e}")
    
    # Save snapshot
    snapshot_dir = output_dir / "snapshots" / f"snapshot_{TIMESTAMP}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    
    if 'graph_data' in locals():
        (snapshot_dir / "simp_graph.json").write_text(json.dumps(graph_data, indent=2))
    (snapshot_dir / "analysis.json").write_text(json.dumps(analysis, indent=2))
    print(f"   📸 Snapshot saved to: {snapshot_dir}")
    
    print("\n✅ Graphify SIMP complete!")
    print(f"📊 Graph: {analysis['graph_stats']['nodes']} nodes, {analysis['graph_stats']['edges']} edges")
    print(f"📁 Output: {output_dir}")

if __name__ == "__main__":
    main()
PYEOF

# Run Graphify
echo "🚀 Running Graphify on SIMP repository..."
cd "$REPO_ROOT"
python3.10 /tmp/graphify_simp_fixed.py

# Create agent helper script
cat > "$OUTPUT_DIR/agent_helper.py" << 'AGENTPY'
#!/usr/bin/env python3
"""
Agent Helper for SIMP Graph Analysis
Use this module to load and analyze SIMP architecture graphs.
"""
import json
from pathlib import Path
import networkx as nx

class SIMPGraphAnalyzer:
    """Helper for agents to analyze SIMP architecture."""
    
    def __init__(self, graph_dir=None):
        if graph_dir is None:
            graph_dir = Path(__file__).parent
        self.graph_dir = Path(graph_dir)
        self.graph = None
        self.analysis = None
        
    def load_graph(self):
        """Load the SIMP graph from JSON."""
        graph_path = self.graph_dir / "simp_graph.json"
        if not graph_path.exists():
            raise FileNotFoundError(f"Graph file not found: {graph_path}")
        
        with open(graph_path) as f:
            graph_data = json.load(f)
        
        # Convert to NetworkX graph
        G = nx.Graph()
        for node in graph_data.get("nodes", []):
            node_id = node.pop("id", None)
            if node_id:
                G.add_node(node_id, **node)
        
        for edge in graph_data.get("edges", []):
            source = edge.pop("source", None)
            target = edge.pop("target", None)
            if source and target:
                G.add_edge(source, target, **edge)
        
        self.graph = G
        return G
    
    def load_analysis(self):
        """Load the analysis data."""
        analysis_path = self.graph_dir / "analysis.json"
        if not analysis_path.exists():
            raise FileNotFoundError(f"Analysis file not found: {analysis_path}")
        
        with open(analysis_path) as f:
            self.analysis = json.load(f)
        
        return self.analysis
    
    def get_central_modules(self, limit=10):
        """Get the most central modules in SIMP."""
        if self.analysis is None:
            self.load_analysis()
        
        return self.analysis.get("central_nodes", [])[:limit]
    
    def find_module(self, module_name):
        """Find information about a specific module."""
        if self.graph is None:
            self.load_graph()
        
        if module_name in self.graph:
            node_data = self.graph.nodes[module_name]
            neighbors = list(self.graph.neighbors(module_name))
            return {
                "module": module_name,
                "data": node_data,
                "neighbors": neighbors,
                "degree": len(neighbors)
            }
        return None
    
    def get_downstream_dependencies(self, module_name):
        """Get modules that depend on the given module."""
        if self.graph is None:
            self.load_graph()
        
        if module_name not in self.graph:
            return []
        
        # Simple heuristic: neighbors in the graph
        return list(self.graph.neighbors(module_name))
    
    def get_module_hierarchy(self):
        """Get the module hierarchy (directory structure)."""
        if self.analysis is None:
            self.load_analysis()
        
        return self.analysis.get("top_modules", [])
    
    def suggest_reading_order(self, topic=None):
        """
        Suggest reading order for understanding SIMP.
        If topic is provided, focus on related modules.
        """
        if self.analysis is None:
            self.load_analysis()
        
        central = self.get_central_modules(5)
        
        if topic:
            # Filter modules related to topic
            topic_modules = [
                mod for mod in central 
                if topic.lower() in mod["node"].lower()
            ]
            if topic_modules:
                return [mod["node"] for mod in topic_modules]
        
        return [mod["node"] for mod in central]

# Example usage for agents
if __name__ == "__main__":
    analyzer = SIMPGraphAnalyzer()
    
    try:
        analyzer.load_graph()
        analyzer.load_analysis()
        
        print("📊 SIMP Graph Analysis")
        print(f"Nodes: {analyzer.graph.number_of_nodes()}")
        print(f"Edges: {analyzer.graph.number_of_edges()}")
        
        print("\n🏆 Top 5 Central Modules:")
        for i, module in enumerate(analyzer.get_central_modules(5), 1):
            print(f"{i}. {module['node']} (centrality: {module['centrality']:.3f})")
        
        print("\n📁 Top 5 Modules by File Count:")
        for i, (module, count) in enumerate(analyzer.get_module_hierarchy()[:5], 1):
            print(f"{i}. {module} ({count} files)")
            
    except Exception as e:
        print(f"Error: {e}")
AGENTPY

chmod +x "$OUTPUT_DIR/agent_helper.py"

echo ""
echo "================================================"
echo "✅ Graphify SIMP snapshot complete!"
echo "📁 Output directory: $OUTPUT_DIR"
echo "📊 Files generated:"
ls -la "$OUTPUT_DIR"
echo ""
echo "🧠 Agent helper script: $OUTPUT_DIR/agent_helper.py"
echo "================================================"
