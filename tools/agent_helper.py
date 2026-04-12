#!/usr/bin/env python3
"""
Agent Helper for SIMP Graph Analysis
Use this module to load and analyze SIMP architecture graphs.
"""
import json
from pathlib import Path
import networkx as nx
from collections import defaultdict

class SIMPGraphAnalyzer:
    """Helper for agents to analyze SIMP architecture."""
    
    def __init__(self, graph_dir=None):
        if graph_dir is None:
            # Try to find .graphify directory
            current = Path(__file__).parent
            graph_dir = current / ".graphify"
            if not graph_dir.exists():
                graph_dir = current.parent / ".graphify"
        
        self.graph_dir = Path(graph_dir)
        self.graph = None
        self.analysis = None
        self._node_cache = {}
        
    def load_graph(self):
        """Load the SIMP graph from JSON."""
        graph_path = self.graph_dir / "simp_graph.json"
        if not graph_path.exists():
            raise FileNotFoundError(f"Graph file not found: {graph_path}")
        
        print(f"📂 Loading graph from: {graph_path}")
        with open(graph_path) as f:
            graph_data = json.load(f)
        
        # Convert to NetworkX graph
        G = nx.Graph()
        
        # Add nodes
        for node in graph_data.get("nodes", []):
            node_id = node.pop("id", None)
            if node_id:
                G.add_node(node_id, **node)
                self._node_cache[node_id] = node
        
        # Add edges
        for edge in graph_data.get("edges", []):
            source = edge.pop("source", None)
            target = edge.pop("target", None)
            if source and target:
                G.add_edge(source, target, **edge)
        
        self.graph = G
        print(f"✅ Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        return G
    
    def load_analysis(self):
        """Load the analysis data."""
        analysis_path = self.graph_dir / "analysis.json"
        if not analysis_path.exists():
            raise FileNotFoundError(f"Analysis file not found: {analysis_path}")
        
        print(f"📊 Loading analysis from: {analysis_path}")
        with open(analysis_path) as f:
            self.analysis = json.load(f)
        
        print(f"✅ Loaded analysis with {len(self.analysis.get('central_nodes', []))} central nodes")
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
                "degree": len(neighbors),
                "is_central": module_name in [n["node"] for n in self.get_central_modules(50)]
            }
        return None
    
    def search_modules(self, keyword):
        """Search for modules containing keyword."""
        if self.graph is None:
            self.load_graph()
        
        results = []
        keyword_lower = keyword.lower()
        
        for node in self.graph.nodes():
            if keyword_lower in node.lower():
                neighbors = list(self.graph.neighbors(node))
                results.append({
                    "module": node,
                    "degree": len(neighbors),
                    "neighbors": neighbors[:5]  # First 5 neighbors
                })
        
        # Sort by degree (most connected first)
        results.sort(key=lambda x: x["degree"], reverse=True)
        return results
    
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
        
        central = self.get_central_modules(10)
        
        if topic:
            # Filter modules related to topic
            topic_lower = topic.lower()
            topic_modules = [
                mod for mod in central 
                if topic_lower in mod["node"].lower()
            ]
            
            # Also search all nodes for topic
            if self.graph is None:
                self.load_graph()
            
            additional = self.search_modules(topic)
            additional_modules = [
                {"node": mod["module"], "centrality": mod["degree"] / self.graph.number_of_nodes()}
                for mod in additional[:5]
            ]
            
            all_topic = topic_modules + additional_modules
            # Remove duplicates
            seen = set()
            unique = []
            for mod in all_topic:
                if mod["node"] not in seen:
                    seen.add(mod["node"])
                    unique.append(mod)
            
            if unique:
                return [mod["node"] for mod in unique[:5]]
        
        return [mod["node"] for mod in central[:5]]
    
    def get_architecture_overview(self):
        """Get a high-level overview of SIMP architecture."""
        if self.analysis is None:
            self.load_analysis()
        
        overview = {
            "stats": self.analysis.get("graph_stats", {}),
            "top_central": self.get_central_modules(5),
            "top_modules": self.get_module_hierarchy()[:5],
            "file_types": self.analysis.get("file_types", {}),
            "timestamp": self.analysis.get("timestamp", "unknown")
        }
        
        return overview
    
    def export_for_agent(self, format="simple"):
        """Export graph data in a format suitable for AI agents."""
        if self.graph is None:
            self.load_graph()
        if self.analysis is None:
            self.load_analysis()
        
        if format == "simple":
            return {
                "architecture_overview": self.get_architecture_overview(),
                "key_modules": [
                    {
                        "module": mod["node"],
                        "centrality": mod["centrality"],
                        "info": self.find_module(mod["node"])
                    }
                    for mod in self.get_central_modules(10)
                ]
            }
        elif format == "minimal":
            return {
                "central_modules": [mod["node"] for mod in self.get_central_modules(10)],
                "module_counts": dict(self.get_module_hierarchy()[:10]),
                "stats": self.analysis.get("graph_stats", {})
            }

# Command-line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SIMP Graph Analyzer for AI Agents")
    parser.add_argument("--graph-dir", help="Directory containing graph files")
    parser.add_argument("--central", type=int, default=10, help="Number of central modules to show")
    parser.add_argument("--search", help="Search for modules containing keyword")
    parser.add_argument("--module", help="Get info about specific module")
    parser.add_argument("--overview", action="store_true", help="Show architecture overview")
    parser.add_argument("--export", choices=["simple", "minimal"], help="Export for agent consumption")
    
    args = parser.parse_args()
    
    analyzer = SIMPGraphAnalyzer(args.graph_dir)
    
    try:
        if args.search:
            print(f"🔍 Searching for modules containing: {args.search}")
            results = analyzer.search_modules(args.search)
            print(f"Found {len(results)} modules:")
            for i, result in enumerate(results[:10], 1):
                print(f"{i}. {result['module']} (connections: {result['degree']})")
                if result['neighbors']:
                    print(f"   Neighbors: {', '.join(result['neighbors'][:3])}")
        
        elif args.module:
            print(f"📁 Getting info for module: {args.module}")
            info = analyzer.find_module(args.module)
            if info:
                print(f"Module: {info['module']}")
                print(f"Degree: {info['degree']} connections")
                print(f"Central: {'Yes' if info['is_central'] else 'No'}")
                if info['neighbors']:
                    print(f"Top neighbors: {', '.join(info['neighbors'][:5])}")
                if 'source_file' in info['data']:
                    print(f"Source file: {info['data']['source_file']}")
            else:
                print(f"Module not found: {args.module}")
        
        elif args.overview:
            print("📊 SIMP Architecture Overview")
            overview = analyzer.get_architecture_overview()
            print(f"Timestamp: {overview['timestamp']}")
            print(f"Nodes: {overview['stats'].get('nodes', 'N/A')}")
            print(f"Edges: {overview['stats'].get('edges', 'N/A')}")
            print(f"Density: {overview['stats'].get('density', 'N/A'):.4f}")
            
            print("\n🏆 Top Central Modules:")
            for i, mod in enumerate(overview['top_central'], 1):
                print(f"{i}. {mod['node']} (centrality: {mod['centrality']:.3f})")
            
            print("\n📁 Top Modules by File Count:")
            for i, (module, count) in enumerate(overview['top_modules'], 1):
                print(f"{i}. {module} ({count} files)")
        
        elif args.export:
            data = analyzer.export_for_agent(args.export)
            print(json.dumps(data, indent=2))
        
        else:
            # Default: show central modules
            analyzer.load_graph()
            analyzer.load_analysis()
            
            print("📊 SIMP Graph Analysis")
            print(f"Nodes: {analyzer.graph.number_of_nodes()}")
            print(f"Edges: {analyzer.graph.number_of_edges()}")
            
            print(f"\n🏆 Top {args.central} Central Modules:")
            for i, module in enumerate(analyzer.get_central_modules(args.central), 1):
                print(f"{i}. {module['node']} (centrality: {module['centrality']:.3f})")
            
            print(f"\n📁 Top 5 Modules by File Count:")
            for i, (module, count) in enumerate(analyzer.get_module_hierarchy()[:5], 1):
                print(f"{i}. {module} ({count} files)")
            
            print(f"\n💡 Try:")
            print(f"  python agent_helper.py --search quantumarb")
            print(f"  python agent_helper.py --module simp/server/broker.py")
            print(f"  python agent_helper.py --overview")
            print(f"  python agent_helper.py --export minimal")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"📁 Graph directory: {analyzer.graph_dir}")
        print(f"Files in directory: {list(analyzer.graph_dir.glob('*')) if analyzer.graph_dir.exists() else 'Directory not found'}")
