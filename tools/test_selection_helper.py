#!/usr/bin/env python3
"""
Test Selection Helper for SIMP
Uses Graphify knowledge graph to select relevant tests for changes.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict
import networkx as nx

class TestSelectionHelper:
    """Select tests based on code changes using SIMP knowledge graph."""
    
    def __init__(self, graph_dir=None):
        if graph_dir is None:
            graph_dir = Path(__file__).parent.parent / ".graphify"
        self.graph_dir = Path(graph_dir)
        self.graph = None
        self.test_map = None
        self._load_graph()
        self._build_test_map()
    
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
    
    def _build_test_map(self):
        """Build mapping from modules to related tests."""
        print("🗺️ Building test map...")
        
        test_nodes = []
        module_to_tests = defaultdict(list)
        test_to_modules = defaultdict(list)
        
        # Find all test nodes
        for node in self.graph.nodes():
            node_lower = node.lower()
            node_data = self.graph.nodes[node]
            source_file = node_data.get("source_file", "")
            
            is_test = False
            if "test" in node_lower:
                is_test = True
            elif source_file and "test" in source_file.lower():
                is_test = True
            
            if is_test:
                test_nodes.append(node)
                
                # Find modules this test connects to
                neighbors = list(self.graph.neighbors(node))
                for neighbor in neighbors:
                    # Check if neighbor is a non-test module
                    neighbor_lower = neighbor.lower()
                    neighbor_data = self.graph.nodes.get(neighbor, {})
                    neighbor_file = neighbor_data.get("source_file", "")
                    
                    if ("test" not in neighbor_lower and 
                        not (neighbor_file and "test" in neighbor_file.lower())):
                        module_to_tests[neighbor].append({
                            "test": node,
                            "distance": 1,  # Direct connection
                            "connection_type": "direct"
                        })
                        test_to_modules[node].append(neighbor)
        
        # Also find indirect connections (up to 2 hops)
        for test in test_nodes:
            # BFS up to 2 hops
            visited = {test}
            queue = [(test, 0)]
            
            while queue:
                current, distance = queue.pop(0)
                
                if distance >= 2:  # Max 2 hops
                    continue
                
                for neighbor in self.graph.neighbors(current):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, distance + 1))
                        
                        # If neighbor is a non-test module
                        neighbor_lower = neighbor.lower()
                        neighbor_data = self.graph.nodes.get(neighbor, {})
                        neighbor_file = neighbor_data.get("source_file", "")
                        
                        if ("test" not in neighbor_lower and 
                            not (neighbor_file and "test" in neighbor_file.lower())):
                            if neighbor not in [t["test"] for t in module_to_tests.get(neighbor, [])]:
                                module_to_tests[neighbor].append({
                                    "test": test,
                                    "distance": distance + 1,
                                    "connection_type": f"indirect_{distance+1}_hop"
                                })
                                test_to_modules[test].append(neighbor)
        
        self.test_map = {
            "test_nodes": test_nodes,
            "module_to_tests": dict(module_to_tests),
            "test_to_modules": dict(test_to_modules),
            "stats": {
                "total_tests": len(test_nodes),
                "modules_with_tests": len(module_to_tests),
                "avg_tests_per_module": len(test_nodes) / max(1, len(module_to_tests))
            }
        }
        
        print(f"✅ Test map built: {len(test_nodes)} tests, {len(module_to_tests)} modules with tests")
        
        # Save test map for future use
        test_map_path = self.graph_dir / "test_map.json"
        with open(test_map_path, 'w') as f:
            json.dump(self.test_map, f, indent=2)
        print(f"💾 Test map saved to: {test_map_path}")
    
    def find_tests_for_changes(self, changed_files, strategy="smart"):
        """
        Find relevant tests for changed files.
        
        Args:
            changed_files: List of file paths that changed
            strategy: "smart" (graph-based), "direct" (only direct connections),
                     "broad" (include indirect connections)
        
        Returns:
            Dictionary with test recommendations
        """
        print(f"🔍 Finding tests for {len(changed_files)} changed files...")
        
        # Find modules corresponding to changed files
        changed_modules = set()
        file_to_modules = {}
        
        for file_path in changed_files:
            file_path = Path(file_path)
            modules = self._find_modules_by_file(file_path)
            if modules:
                changed_modules.update(modules)
                file_to_modules[str(file_path)] = modules
                print(f"  📄 {file_path}: {len(modules)} modules")
            else:
                print(f"  ⚠️ {file_path}: No matching modules found")
        
        if not changed_modules:
            print("❌ No matching modules found")
            return {"error": "No matching modules found"}
        
        # Find tests for changed modules
        test_recommendations = []
        
        for module in changed_modules:
            if module in self.test_map["module_to_tests"]:
                tests = self.test_map["module_to_tests"][module]
                
                for test_info in tests:
                    # Apply strategy filter
                    if strategy == "direct" and test_info["distance"] > 1:
                        continue
                    if strategy == "broad" or strategy == "smart":
                        # Smart strategy: include all, but weight by distance
                        test_recommendations.append({
                            "test": test_info["test"],
                            "module": module,
                            "distance": test_info["distance"],
                            "connection_type": test_info["connection_type"],
                            "weight": 1.0 / test_info["distance"]  # Closer = higher weight
                        })
        
        # Remove duplicates and sort by weight
        unique_tests = {}
        for rec in test_recommendations:
            test = rec["test"]
            if test not in unique_tests or rec["weight"] > unique_tests[test]["weight"]:
                unique_tests[test] = rec
        
        # Sort by weight (highest first)
        sorted_tests = sorted(
            unique_tests.values(),
            key=lambda x: x["weight"],
            reverse=True
        )
        
        # Categorize tests
        test_categories = self._categorize_tests(sorted_tests)
        
        # Generate pytest command
        pytest_command = self._generate_pytest_command(sorted_tests)
        
        return {
            "changed_files": changed_files,
            "changed_modules": list(changed_modules),
            "recommended_tests": sorted_tests[:50],  # Limit output
            "test_categories": test_categories,
            "pytest_command": pytest_command,
            "stats": {
                "changed_modules": len(changed_modules),
                "recommended_tests": len(sorted_tests),
                "unique_tests": len(unique_tests),
                "coverage_estimate": f"{min(100, len(unique_tests) * 100 // max(1, len(changed_modules)))}%"
            }
        }
    
    def _find_modules_by_file(self, file_path):
        """Find graph nodes corresponding to a file."""
        file_path = str(file_path)
        modules = []
        
        for node in self.graph.nodes():
            node_data = self.graph.nodes[node]
            source_file = node_data.get("source_file", "")
            
            # Check if file_path matches or is contained in source_file
            if file_path in source_file or source_file in file_path:
                modules.append(node)
        
        return modules
    
    def _categorize_tests(self, tests):
        """Categorize tests by type and location."""
        categories = defaultdict(list)
        
        for test in tests:
            test_node = test["test"]
            
            # Categorize by test type
            if "unit" in test_node.lower():
                categories["unit"].append(test)
            elif "integration" in test_node.lower():
                categories["integration"].append(test)
            elif "functional" in test_node.lower():
                categories["functional"].append(test)
            else:
                categories["other"].append(test)
            
            # Categorize by location
            test_data = self.graph.nodes.get(test_node, {})
            source_file = test_data.get("source_file", "")
            if source_file:
                if "/tests/" in source_file:
                    categories["tests_dir"].append(test)
                elif "test_" in source_file:
                    categories["test_files"].append(test)
        
        return {
            category: {
                "tests": tests[:10],  # Limit per category
                "count": len(tests)
            }
            for category, tests in categories.items()
        }
    
    def _generate_pytest_command(self, tests):
        """Generate pytest command for recommended tests."""
        if not tests:
            return "pytest"  # Default: run all tests
        
        # Extract test names (simplified)
        test_names = []
        for test in tests[:20]:  # Limit to 20 tests for command length
            test_node = test["test"]
            # Try to extract a reasonable test name
            if "::" in test_node:
                # Already has pytest format
                test_names.append(test_node)
            else:
                # Use node as-is
                test_names.append(test_node)
        
        if len(test_names) <= 10:
            # Use -k pattern matching
            patterns = " or ".join(test_names[:10])
            return f'pytest -k "{patterns}" -v'
        else:
            # Too many tests, run by directory
            test_dirs = set()
            for test in tests[:10]:
                test_data = self.graph.nodes.get(test["test"], {})
                source_file = test_data.get("source_file", "")
                if source_file:
                    test_dir = str(Path(source_file).parent)
                    test_dirs.add(test_dir)
            
            if test_dirs:
                dirs_str = " ".join(sorted(test_dirs)[:3])
                return f'pytest {dirs_str} -v'
            else:
                return "pytest tests/ -v"  # Fallback
    
    def export_for_agent(self, analysis):
        """Export analysis in agent-friendly format."""
        return {
            "summary": f"Found {analysis['stats']['recommended_tests']} tests for {analysis['stats']['changed_modules']} changed modules",
            "pytest_command": analysis["pytest_command"],
            "top_tests": [
                test["test"]
                for test in analysis["recommended_tests"][:10]
            ],
            "test_categories": {
                cat: info["count"]
                for cat, info in analysis["test_categories"].items()
            }
        }

def main():
    """Command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Selection Helper for SIMP")
    parser.add_argument("files", nargs="+", help="Changed files to find tests for")
    parser.add_argument("--strategy", choices=["smart", "direct", "broad"], default="smart",
                       help="Test selection strategy")
    parser.add_argument("--export", action="store_true", help="Export agent-friendly format")
    parser.add_argument("--graph-dir", help="Directory containing graph files")
    parser.add_argument("--build-map", action="store_true", help="Rebuild test map")
    
    args = parser.parse_args()
    
    helper = TestSelectionHelper(args.graph_dir)
    
    if args.build_map:
        # Already built during init
        print("✅ Test map built")
        return
    
    try:
        analysis = helper.find_tests_for_changes(args.files, args.strategy)
        
        if args.export:
            agent_format = helper.export_for_agent(analysis)
            print(json.dumps(agent_format, indent=2))
        else:
            # Pretty print
            print("\n" + "="*60)
            print("🧪 TEST SELECTION HELPER")
            print("="*60)
            
            print(f"\n📁 Changed Files: {len(analysis['changed_files'])}")
            for file in analysis['changed_files'][:3]:
                print(f"  • {file}")
            if len(analysis['changed_files']) > 3:
                print(f"  ... and {len(analysis['changed_files']) - 3} more")
            
            print(f"\n📈 Test Recommendations:")
            print(f"  • Recommended tests: {analysis['stats']['recommended_tests']}")
            print(f"  • Unique tests: {analysis['stats']['unique_tests']}")
            print(f"  • Coverage estimate: {analysis['stats']['coverage_estimate']}")
            
            print(f"\n🏷️ Test Categories:")
            for category, info in analysis['test_categories'].items():
                print(f"  • {category}: {info['count']} tests")
            
            print(f"\n🚀 Top 5 Recommended Tests:")
            for i, test in enumerate(analysis['recommended_tests'][:5], 1):
                print(f"  {i}. {test['test']}")
                print(f"     → Connected to: {test['module']} (distance: {test['distance']})")
            
            print(f"\n💻 Pytest Command:")
            print(f"  {analysis['pytest_command']}")
            
            print(f"\n📋 Full Command:")
            print(f"  cd '/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp'")
            print(f"  {analysis['pytest_command']}")
            
            print("\n" + "="*60)
            print("💡 Tip: Use --export for agent-friendly JSON format")
            print("="*60)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
