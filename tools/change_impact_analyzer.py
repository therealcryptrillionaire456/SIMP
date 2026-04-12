#!/usr/bin/env python3
"""
Change Impact Analyzer for SIMP
Uses Graphify knowledge graph to analyze impact of code changes.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict, deque
import networkx as nx

class ChangeImpactAnalyzer:
    """Analyze impact of code changes using SIMP knowledge graph."""
    
    def __init__(self, graph_dir=None):
        if graph_dir is None:
            graph_dir = Path(__file__).parent.parent / ".graphify"
        self.graph_dir = Path(graph_dir)
        self.graph = None
        self._load_graph()
    
    def _load_graph(self):
        """Load the SIMP graph."""
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
        print(f"📊 Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        return G
    
    def find_module_by_path(self, file_path):
        """Find graph node(s) corresponding to a file path."""
        file_path = str(file_path)
        matches = []
        
        for node in self.graph.nodes():
            node_data = self.graph.nodes[node]
            source_file = node_data.get("source_file", "")
            
            # Check if file_path matches or is contained in source_file
            if file_path in source_file or source_file in file_path:
                matches.append({
                    "node": node,
                    "data": node_data,
                    "degree": self.graph.degree(node)
                })
        
        return matches
    
    def analyze_impact(self, changed_files, max_depth=3):
        """
        Analyze impact of changes to given files.
        
        Args:
            changed_files: List of file paths that changed
            max_depth: How many hops away to consider for impact
        
        Returns:
            Dictionary with impact analysis
        """
        print(f"🔍 Analyzing impact of changes to {len(changed_files)} files...")
        
        # Find affected nodes
        affected_nodes = set()
        node_to_file = {}
        
        for file_path in changed_files:
            file_path = Path(file_path)
            matches = self.find_module_by_path(file_path)
            
            if matches:
                print(f"  📄 {file_path}: Found {len(matches)} graph nodes")
                for match in matches:
                    affected_nodes.add(match["node"])
                    node_to_file[match["node"]] = str(file_path)
            else:
                print(f"  ⚠️ {file_path}: No matching graph nodes found")
        
        if not affected_nodes:
            print("❌ No matching nodes found in graph")
            return {"error": "No matching nodes found"}
        
        # Find downstream dependencies (BFS)
        downstream = set()
        impact_chains = []
        
        for start_node in affected_nodes:
            # BFS to find reachable nodes
            visited = {start_node}
            queue = deque([(start_node, 0, [start_node])])  # (node, depth, path)
            
            while queue:
                node, depth, path = queue.popleft()
                
                if depth > max_depth:
                    continue
                
                for neighbor in self.graph.neighbors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        downstream.add(neighbor)
                        
                        # Record impact chain
                        impact_chains.append({
                            "source": start_node,
                            "target": neighbor,
                            "depth": depth + 1,
                            "path": path + [neighbor]
                        })
                        
                        if depth + 1 < max_depth:
                            queue.append((neighbor, depth + 1, path + [neighbor]))
        
        # Categorize impacted modules
        impacted_modules = self._categorize_impact(list(downstream))
        
        # Find potentially broken tests
        broken_tests = self._find_related_tests(affected_nodes | downstream)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            affected_nodes, downstream, broken_tests
        )
        
        return {
            "changed_files": changed_files,
            "directly_affected_nodes": list(affected_nodes),
            "downstream_impact": list(downstream),
            "impact_chains": impact_chains[:20],  # Limit output
            "impacted_modules": impacted_modules,
            "potentially_broken_tests": broken_tests,
            "recommendations": recommendations,
            "stats": {
                "direct_nodes": len(affected_nodes),
                "downstream_nodes": len(downstream),
                "total_impact": len(affected_nodes) + len(downstream),
                "impact_chains_count": len(impact_chains)
            }
        }
    
    def _categorize_impact(self, nodes):
        """Categorize impacted nodes by module/type."""
        categories = defaultdict(list)
        
        for node in nodes:
            node_data = self.graph.nodes[node]
            source_file = node_data.get("source_file", "")
            
            # Extract module from file path
            if "/" in source_file:
                parts = source_file.split("/")
                if "simp" in parts:
                    simp_index = parts.index("simp")
                    if simp_index + 1 < len(parts):
                        module = parts[simp_index + 1]
                        categories[module].append(node)
            
            # Categorize by node type if available
            node_type = node_data.get("type", "unknown")
            categories[f"type:{node_type}"].append(node)
        
        # Sort by count
        sorted_categories = sorted(
            categories.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        return [
            {"category": cat, "nodes": nodes[:10], "count": len(nodes)}
            for cat, nodes in sorted_categories[:10]  # Top 10 categories
        ]
    
    def _find_related_tests(self, affected_nodes):
        """Find test files related to affected nodes."""
        test_nodes = []
        
        for node in affected_nodes:
            node_lower = node.lower()
            if "test" in node_lower:
                test_nodes.append(node)
            else:
                # Check if node is referenced in test files
                node_data = self.graph.nodes[node]
                source_file = node_data.get("source_file", "")
                if source_file and "test" in source_file.lower():
                    test_nodes.append(node)
        
        # Also find tests that import/use affected nodes
        test_candidates = []
        for node in self.graph.nodes():
            if "test" in node.lower():
                # Check if this test connects to affected nodes
                neighbors = set(self.graph.neighbors(node))
                if neighbors & affected_nodes:
                    test_candidates.append({
                        "test_node": node,
                        "connected_to": list(neighbors & affected_nodes),
                        "connection_count": len(neighbors & affected_nodes)
                    })
        
        # Sort by connection count
        test_candidates.sort(key=lambda x: x["connection_count"], reverse=True)
        
        return {
            "direct_test_nodes": test_nodes[:20],
            "connected_tests": test_candidates[:20]
        }
    
    def _generate_recommendations(self, affected, downstream, broken_tests):
        """Generate actionable recommendations."""
        recommendations = []
        
        # 1. Test recommendations
        if broken_tests["connected_tests"]:
            test_list = [t["test_node"] for t in broken_tests["connected_tests"][:5]]
            recommendations.append({
                "type": "testing",
                "priority": "high",
                "action": "Run these tests first:",
                "details": test_list,
                "reason": "These tests are directly connected to changed modules"
            })
        
        # 2. Review recommendations
        downstream_modules = set()
        for node in downstream:
            node_data = self.graph.nodes[node]
            source_file = node_data.get("source_file", "")
            if "/" in source_file and "simp" in source_file:
                parts = source_file.split("/")
                simp_index = parts.index("simp")
                if simp_index + 2 < len(parts):
                    module = f"{parts[simp_index + 1]}/{parts[simp_index + 2]}"
                    downstream_modules.add(module)
        
        if downstream_modules:
            recommendations.append({
                "type": "review",
                "priority": "medium",
                "action": "Review these modules:",
                "details": list(downstream_modules)[:10],
                "reason": "Downstream dependencies may be affected"
            })
        
        # 3. Integration recommendations
        if len(downstream) > 50:
            recommendations.append({
                "type": "integration",
                "priority": "high",
                "action": "Run full integration test suite",
                "details": ["All integration tests"],
                "reason": f"Large impact: {len(downstream)} downstream nodes affected"
            })
        
        return recommendations
    
    def export_for_agent(self, analysis):
        """Export analysis in agent-friendly format."""
        return {
            "summary": f"Impact analysis: {analysis['stats']['direct_nodes']} direct, {analysis['stats']['downstream_nodes']} downstream nodes affected",
            "top_impacted_categories": [
                f"{cat['category']} ({cat['count']} nodes)"
                for cat in analysis["impacted_modules"][:3]
            ],
            "test_recommendations": [
                rec["details"][0] if rec["type"] == "testing" and rec["details"] else None
                for rec in analysis["recommendations"]
                if rec["type"] == "testing"
            ],
            "action_items": [
                {
                    "priority": rec["priority"],
                    "action": rec["action"],
                    "details": rec["details"][:3] if isinstance(rec["details"], list) else rec["details"]
                }
                for rec in analysis["recommendations"]
            ]
        }

def main():
    """Command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Change Impact Analyzer for SIMP")
    parser.add_argument("files", nargs="+", help="Changed files to analyze")
    parser.add_argument("--depth", type=int, default=3, help="Impact analysis depth")
    parser.add_argument("--export", action="store_true", help="Export agent-friendly format")
    parser.add_argument("--graph-dir", help="Directory containing graph files")
    
    args = parser.parse_args()
    
    analyzer = ChangeImpactAnalyzer(args.graph_dir)
    
    try:
        analysis = analyzer.analyze_impact(args.files, args.depth)
        
        if args.export:
            agent_format = analyzer.export_for_agent(analysis)
            print(json.dumps(agent_format, indent=2))
        else:
            # Pretty print
            print("\n" + "="*60)
            print("📊 CHANGE IMPACT ANALYSIS")
            print("="*60)
            
            print(f"\n📁 Changed Files: {len(analysis['changed_files'])}")
            for file in analysis['changed_files'][:5]:
                print(f"  • {file}")
            if len(analysis['changed_files']) > 5:
                print(f"  ... and {len(analysis['changed_files']) - 5} more")
            
            print(f"\n📈 Impact Statistics:")
            print(f"  • Directly affected nodes: {analysis['stats']['direct_nodes']}")
            print(f"  • Downstream impact: {analysis['stats']['downstream_nodes']}")
            print(f"  • Total impacted: {analysis['stats']['total_impact']}")
            
            print(f"\n🏷️ Top Impacted Categories:")
            for cat in analysis['impacted_modules'][:5]:
                print(f"  • {cat['category']}: {cat['count']} nodes")
            
            print(f"\n🧪 Test Impact:")
            if analysis['potentially_broken_tests']['connected_tests']:
                print(f"  • {len(analysis['potentially_broken_tests']['connected_tests'])} tests connected to changes")
                for test in analysis['potentially_broken_tests']['connected_tests'][:3]:
                    print(f"    - {test['test_node']} ({test['connection_count']} connections)")
            
            print(f"\n🚀 Recommendations:")
            for rec in analysis['recommendations']:
                print(f"  [{rec['priority'].upper()}] {rec['action']}")
                if rec['details']:
                    if isinstance(rec['details'], list):
                        for detail in rec['details'][:2]:
                            print(f"    • {detail}")
                        if len(rec['details']) > 2:
                            print(f"    • ... and {len(rec['details']) - 2} more")
                    else:
                        print(f"    • {rec['details']}")
            
            print("\n" + "="*60)
            print("💡 Tip: Use --export for agent-friendly JSON format")
            print("="*60)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
