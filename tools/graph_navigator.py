#!/usr/bin/env python3
"""
Graphify Navigator for SIMP
Creates intelligent exploration tools using the knowledge graph.
"""

import json
import networkx as nx
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import heapq

class GraphNavigator:
    """Intelligent navigation using Graphify knowledge graph."""
    
    def __init__(self, graph_dir: str = ".graphify"):
        self.graph_dir = Path(graph_dir)
        self.graph_path = self.graph_dir / "simp_graph.json"
        
        if not self.graph_path.exists():
            raise FileNotFoundError(f"Graph file not found: {self.graph_path}")
        
        print(f"📊 Loading graph from {self.graph_path}...")
        with open(self.graph_path, 'r') as f:
            self.graph_data = json.load(f)
        
        self.nodes = self.graph_data.get("nodes", [])
        self.edges = self.graph_data.get("edges", [])
        
        # Build NetworkX graph for analysis
        self.nx_graph = self._build_networkx_graph()
        
        print(f"✅ Loaded {len(self.nodes)} nodes, {len(self.edges)} edges")
        print(f"📈 NetworkX graph: {self.nx_graph.number_of_nodes()} nodes, {self.nx_graph.number_of_edges()} edges")
    
    def _build_networkx_graph(self) -> nx.Graph:
        """Build NetworkX graph from Graphify data."""
        G = nx.Graph()
        
        # Add nodes
        for node in self.nodes:
            node_id = node.get("id", "")
            if node_id:
                G.add_node(node_id, **node)
        
        # Add edges
        for edge in self.edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            if source and target:
                G.add_edge(source, target, **edge)
        
        return G
    
    def create_reading_plan(self, topic: str, depth: int = 3) -> Dict[str, Any]:
        """Create a reading plan for a specific topic."""
        print(f"📚 Creating reading plan for: {topic}")
        
        # Find nodes related to topic
        topic_nodes = []
        for node in self.nodes:
            label = node.get("label", "").lower()
            if topic.lower() in label:
                topic_nodes.append(node)
        
        if not topic_nodes:
            # Try to find related nodes
            for node in self.nodes:
                if any(keyword in node.get("label", "").lower() 
                      for keyword in self._get_related_keywords(topic)):
                    topic_nodes.append(node)
        
        if not topic_nodes:
            return {"error": f"No nodes found for topic: {topic}"}
        
        # Build reading plan
        reading_plan = {
            "topic": topic,
            "created_at": datetime.now().isoformat(),
            "total_nodes": len(topic_nodes),
            "recommended_order": [],
            "learning_paths": [],
            "prerequisites": [],
            "key_concepts": []
        }
        
        # Calculate centrality for ordering
        central_nodes = []
        for node in topic_nodes:
            node_id = node.get("id", "")
            if node_id in self.nx_graph:
                try:
                    centrality = nx.degree_centrality(self.nx_graph).get(node_id, 0)
                    central_nodes.append((centrality, node))
                except:
                    central_nodes.append((0, node))
        
        # Sort by centrality (most central first)
        central_nodes.sort(key=lambda x: x[0], reverse=True)
        
        # Create recommended reading order
        for centrality, node in central_nodes[:10]:  # Top 10 most central
            reading_plan["recommended_order"].append({
                "node_id": node.get("id", ""),
                "label": node.get("label", ""),
                "source_file": node.get("source_file", ""),
                "centrality": centrality,
                "importance": "high" if centrality > 0.1 else "medium" if centrality > 0.05 else "low"
            })
        
        # Create learning paths
        reading_plan["learning_paths"] = self._create_learning_paths(topic_nodes[:5], depth)
        
        # Extract key concepts
        reading_plan["key_concepts"] = self._extract_key_concepts(topic_nodes)
        
        # Find prerequisites
        reading_plan["prerequisites"] = self._find_prerequisites(topic_nodes[:3])
        
        return reading_plan
    
    def _create_learning_paths(self, start_nodes: List[Dict], depth: int) -> List[List[Dict]]:
        """Create learning paths from starting nodes."""
        paths = []
        
        for start_node in start_nodes[:3]:  # Create paths from top 3 nodes
            start_id = start_node.get("id", "")
            if start_id in self.nx_graph:
                # Use BFS to find related nodes
                visited = set([start_id])
                queue = [(start_id, 0)]  # (node_id, depth)
                path = [self._format_node_for_path(start_node, "start")]
                
                while queue:
                    current_id, current_depth = queue.pop(0)
                    
                    if current_depth >= depth:
                        continue
                    
                    # Get neighbors
                    neighbors = list(self.nx_graph.neighbors(current_id))
                    for neighbor_id in neighbors:
                        if neighbor_id not in visited:
                            visited.add(neighbor_id)
                            neighbor_node = next((n for n in self.nodes if n.get("id") == neighbor_id), None)
                            if neighbor_node:
                                path.append(self._format_node_for_path(neighbor_node, f"depth_{current_depth + 1}"))
                                queue.append((neighbor_id, current_depth + 1))
                
                if len(path) > 1:  # Only add if we found related nodes
                    paths.append(path)
        
        return paths
    
    def _format_node_for_path(self, node: Dict, role: str) -> Dict[str, Any]:
        """Format node for learning path."""
        return {
            "id": node.get("id", ""),
            "label": node.get("label", ""),
            "source_file": node.get("source_file", ""),
            "role": role,
            "type": node.get("file_type", "unknown")
        }
    
    def _extract_key_concepts(self, nodes: List[Dict]) -> List[str]:
        """Extract key concepts from nodes."""
        concepts = set()
        
        for node in nodes:
            label = node.get("label", "")
            # Extract meaningful concepts from labels
            words = label.replace("_", " ").replace(".", " ").split()
            for word in words:
                if len(word) > 4 and word.isalpha():  # Meaningful words
                    concepts.add(word.lower())
        
        return sorted(list(concepts))[:10]  # Top 10 concepts
    
    def _find_prerequisites(self, nodes: List[Dict]) -> List[Dict]:
        """Find prerequisite nodes."""
        prerequisites = []
        
        for node in nodes:
            node_id = node.get("id", "")
            if node_id in self.nx_graph:
                # Find nodes that this node depends on
                for edge in self.edges:
                    if edge.get("target") == node_id and edge.get("type") in ["depends_on", "imports"]:
                        source_id = edge.get("source")
                        source_node = next((n for n in self.nodes if n.get("id") == source_id), None)
                        if source_node and source_node not in nodes:  # Don't include nodes already in our list
                            prerequisites.append({
                                "id": source_id,
                                "label": source_node.get("label", ""),
                                "source_file": source_node.get("source_file", ""),
                                "relationship": edge.get("type", "depends_on")
                            })
        
        # Remove duplicates
        unique_prereqs = []
        seen_ids = set()
        for prereq in prerequisites:
            if prereq["id"] not in seen_ids:
                seen_ids.add(prereq["id"])
                unique_prereqs.append(prereq)
        
        return unique_prereqs[:5]  # Top 5 prerequisites
    
    def _get_related_keywords(self, topic: str) -> List[str]:
        """Get related keywords for a topic."""
        keyword_map = {
            "broker": ["broker", "server", "route", "intent", "message"],
            "agent": ["agent", "a2a", "compat", "card", "capability"],
            "financial": ["financial", "payment", "money", "transaction", "stripe"],
            "security": ["security", "auth", "encrypt", "protect", "audit"],
            "test": ["test", "pytest", "assert", "verify", "check"],
            "dashboard": ["dashboard", "ui", "frontend", "visual", "chart"]
        }
        
        topic_lower = topic.lower()
        for key, keywords in keyword_map.items():
            if key in topic_lower:
                return keywords
        
        return [topic.lower()]
    
    def generate_refactoring_suggestions(self, module_name: str) -> Dict[str, Any]:
        """Generate refactoring suggestions for a module."""
        print(f"🔧 Generating refactoring suggestions for: {module_name}")
        
        # Find module nodes
        module_nodes = []
        for node in self.nodes:
            source_file = node.get("source_file", "")
            if module_name.lower() in source_file.lower():
                module_nodes.append(node)
        
        if not module_nodes:
            return {"error": f"No nodes found for module: {module_name}"}
        
        suggestions = {
            "module": module_name,
            "generated_at": datetime.now().isoformat(),
            "analysis": {},
            "suggestions": [],
            "metrics": {}
        }
        
        # Analyze module structure
        analysis = self._analyze_module_structure(module_nodes)
        suggestions["analysis"] = analysis
        
        # Generate suggestions based on analysis
        suggestions["suggestions"] = self._generate_suggestions_from_analysis(analysis)
        
        # Calculate metrics
        suggestions["metrics"] = self._calculate_module_metrics(module_nodes)
        
        return suggestions
    
    def _analyze_module_structure(self, module_nodes: List[Dict]) -> Dict[str, Any]:
        """Analyze module structure for refactoring opportunities."""
        analysis = {
            "file_count": 0,
            "class_count": 0,
            "function_count": 0,
            "dependencies": set(),
            "dependents": set(),
            "circular_deps": [],
            "high_coupling": [],
            "low_cohesion": []
        }
        
        # Count nodes by type
        for node in module_nodes:
            label = node.get("label", "")
            if label.endswith(".py"):
                analysis["file_count"] += 1
            elif "class" in label.lower():
                analysis["class_count"] += 1
            elif "(" in label and ")" in label:
                analysis["function_count"] += 1
        
        # Analyze dependencies
        module_ids = [node.get("id", "") for node in module_nodes]
        for edge in self.edges:
            source_id = edge.get("source", "")
            target_id = edge.get("target", "")
            
            if source_id in module_ids and target_id not in module_ids:
                # Module depends on external node
                target_node = next((n for n in self.nodes if n.get("id") == target_id), None)
                if target_node:
                    source_file = target_node.get("source_file", "")
                    if source_file:
                        # Extract module from path
                        if "simp/" in source_file:
                            module = source_file.split("simp/")[-1].split("/")[0]
                            analysis["dependencies"].add(module)
            
            elif target_id in module_ids and source_id not in module_ids:
                # External node depends on module
                source_node = next((n for n in self.nodes if n.get("id") == source_id), None)
                if source_node:
                    source_file = source_node.get("source_file", "")
                    if source_file:
                        if "simp/" in source_file:
                            module = source_file.split("simp/")[-1].split("/")[0]
                            analysis["dependents"].add(module)
        
        # Convert sets to lists
        analysis["dependencies"] = list(analysis["dependencies"])
        analysis["dependents"] = list(analysis["dependents"])
        
        return analysis
    
    def _generate_suggestions_from_analysis(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate refactoring suggestions from analysis."""
        suggestions = []
        
        # Check for high coupling
        if len(analysis["dependencies"]) > 5:
            suggestions.append({
                "type": "reduce_coupling",
                "priority": "high",
                "description": f"Module has {len(analysis['dependencies'])} dependencies (high coupling)",
                "suggestion": "Consider extracting shared functionality into separate modules"
            })
        
        # Check for many dependents
        if len(analysis["dependents"]) > 3:
            suggestions.append({
                "type": "stabilize_interface",
                "priority": "medium",
                "description": f"Module has {len(analysis['dependents'])} dependents",
                "suggestion": "Define stable interfaces and avoid breaking changes"
            })
        
        # Check for large files
        if analysis["function_count"] > 50:
            suggestions.append({
                "type": "split_large_file",
                "priority": "medium",
                "description": f"Module has {analysis['function_count']} functions",
                "suggestion": "Consider splitting into smaller, focused files"
            })
        
        # Check for many classes in one file
        if analysis["class_count"] > 5 and analysis["file_count"] == 1:
            suggestions.append({
                "type": "separate_classes",
                "priority": "low",
                "description": f"Module has {analysis['class_count']} classes in one file",
                "suggestion": "Consider separating classes into individual files"
            })
        
        return suggestions
    
    def _calculate_module_metrics(self, module_nodes: List[Dict]) -> Dict[str, float]:
        """Calculate module quality metrics."""
        metrics = {
            "cohesion_score": 0.0,
            "coupling_score": 0.0,
            "complexity_score": 0.0,
            "maintainability_index": 0.0
        }
        
        # Simple heuristic metrics
        file_count = len([n for n in module_nodes if n.get("label", "").endswith(".py")])
        class_count = len([n for n in module_nodes if "class" in n.get("label", "").lower()])
        function_count = len([n for n in module_nodes if "(" in n.get("label", "") and ")" in n.get("label", "")])
        
        if file_count > 0:
            # Cohesion: higher when functions/classes are related
            metrics["cohesion_score"] = min(1.0, (class_count + function_count) / (file_count * 10))
            
            # Coupling: lower is better (simplified)
            metrics["coupling_score"] = min(1.0, len(self._analyze_module_structure(module_nodes)["dependencies"]) / 10)
            
            # Complexity: based on size
            metrics["complexity_score"] = min(1.0, (class_count * 2 + function_count) / 100)
            
            # Maintainability index (simplified)
            metrics["maintainability_index"] = max(0.0, 100 - (
                metrics["complexity_score"] * 30 +
                metrics["coupling_score"] * 40 +
                (1 - metrics["cohesion_score"]) * 30
            ))
        
        return metrics
    
    def create_interactive_explorer(self) -> Dict[str, Any]:
        """Create data for interactive graph explorer."""
        print("🕸️ Creating interactive explorer data...")
        
        # Prepare nodes for visualization
        viz_nodes = []
        for node in self.nodes[:100]:  # Limit to 100 nodes for performance
            viz_nodes.append({
                "id": node.get("id", ""),
                "label": node.get("label", ""),
                "group": self._get_node_group(node),
                "size": self._calculate_node_size(node),
                "title": f"{node.get('label', '')}<br>File: {node.get('source_file', '')}"
            })
        
        # Prepare edges for visualization
        viz_edges = []
        for edge in self.edges[:200]:  # Limit to 200 edges
            viz_edges.append({
                "from": edge.get("source", ""),
                "to": edge.get("target", ""),
                "label": edge.get("type", ""),
                "arrows": "to"
            })
        
        explorer_data = {
            "nodes": viz_nodes,
            "edges": viz_edges,
            "generated_at": datetime.now().isoformat(),
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "modules": self._extract_module_list()[:20]
        }
        
        return explorer_data
    
    def _get_node_group(self, node: Dict) -> int:
        """Get group for node visualization."""
        label = node.get("label", "").lower()
        source_file = node.get("source_file", "").lower()
        
        if label.endswith(".py"):
            return 1  # Files
        elif "class" in label:
            return 2  # Classes
        elif "(" in label and ")" in label:
            return 3  # Functions
        elif "test" in source_file:
            return 4  # Tests
        else:
            return 5  # Other
    
    def _calculate_node_size(self, node: Dict) -> int:
        """Calculate node size for visualization."""
        label = node.get("label", "")
        
        if label.endswith(".py"):
            return 20
        elif "class" in label.lower():
            return 15
        elif "(" in label and ")" in label:
            return 10
        else:
            return 5
    
    def _extract_module_list(self) -> List[str]:
        """Extract list of modules from graph."""
        modules = set()
        
        for node in self.nodes:
            source_file = node.get("source_file", "")
            if source_file and "simp/" in source_file:
                module = source_file.split("simp/")[-1].split("/")[0]
                modules.add(module)
        
        return sorted(list(modules))
    
    def export_navigation_data(self, output_dir: str = "navigation") -> Dict[str, str]:
        """Export all navigation data."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create reading plans for common topics
        topics = ["broker", "agent", "financial", "security", "test", "dashboard"]
        reading_plans = {}
        
        for topic in topics:
            plan = self.create_reading_plan(topic)
            if "error" not in plan:
                reading_plans[topic] = plan
        
        # Save reading plans
        plans_path = output_path / f"reading_plans_{timestamp}.json"
        with open(plans_path, 'w') as f:
            json.dump(reading_plans, f, indent=2)
        
        # Generate refactoring suggestions for top modules
        modules = self._extract_module_list()[:5]
        refactoring_suggestions = {}
        
        for module in modules:
            suggestions = self.generate_refactoring_suggestions(module)
            if "error" not in suggestions:
                refactoring_suggestions[module] = suggestions
        
        # Save refactoring suggestions
        refactoring_path = output_path / f"refactoring_suggestions_{timestamp}.json"
        with open(refactoring_path, 'w') as f:
            json.dump(refactoring_suggestions, f, indent=2)
        
        # Create interactive explorer data
        explorer_data = self.create_interactive_explorer()
        explorer_path = output_path / f"explorer_data_{timestamp}.json"
        with open(explorer_path, 'w') as f:
            json.dump(explorer_data, f, indent=2)
        
        print(f"✅ Exported navigation data to {output_path}/")
        print(f"   📚 Reading plans: {len(reading_plans)} topics")
        print(f"   🔧 Refactoring suggestions: {len(refactoring_suggestions)} modules")
        print(f"   🕸️ Explorer data: {len(explorer_data['nodes'])} nodes, {len(explorer_data['edges'])} edges")
        
        return {
            "reading_plans": str(plans_path),
            "refactoring_suggestions": str(refactoring_path),
            "explorer_data": str(explorer_path)
        }

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Graphify Navigator for SIMP")
    parser.add_argument("--reading-plan", help="Create reading plan for topic")
    parser.add_argument("--refactoring", help="Generate refactoring suggestions for module")
    parser.add_argument("--explorer", action="store_true", help="Create interactive explorer data")
    parser.add_argument("--export", action="store_true", help="Export all navigation data")
    parser.add_argument("--output-dir", default="navigation", help="Output directory")
    
    args = parser.parse_args()
    
    try:
        navigator = GraphNavigator()
        
        if args.reading_plan:
            print(f"📚 Creating reading plan for: {args.reading_plan}")
            plan = navigator.create_reading_plan(args.reading_plan)
            print(json.dumps(plan, indent=2))
        
        elif args.refactoring:
            print(f"🔧 Generating refactoring suggestions for: {args.refactoring}")
            suggestions = navigator.generate_refactoring_suggestions(args.refactoring)
            print(json.dumps(suggestions, indent=2))
        
        elif args.explorer:
            print("🕸️ Creating interactive explorer data...")
            explorer_data = navigator.create_interactive_explorer()
            print(f"✅ Created explorer with {len(explorer_data['nodes'])} nodes, {len(explorer_data['edges'])} edges")
            
            # Save to file
            output_path = Path(args.output_dir)
            output_path.mkdir(exist_ok=True)
            file_path = output_path / "explorer_data.json"
            with open(file_path, 'w') as f:
                json.dump(explorer_data, f, indent=2)
            print(f"💾 Saved to {file_path}")
        
        elif args.export:
            print("📤 Exporting all navigation data...")
            exports = navigator.export_navigation_data(args.output_dir)
            print(f"✅ Exported to {args.output_dir}/")
        
        else:
            # Show available features
            print("🎯 Graphify Navigator - Available Features:")
            print("  --reading-plan TOPIC    Create reading plan for topic")
            print("  --refactoring MODULE    Generate refactoring suggestions")
            print("  --explorer              Create interactive explorer data")
            print("  --export                Export all navigation data")
            print("")
            print("📊 Graph Statistics:")
            print(f"  Nodes: {len(navigator.nodes)}")
            print(f"  Edges: {len(navigator.edges)}")
            print(f"  NetworkX graph: {navigator.nx_graph.number_of_nodes()} nodes, {navigator.nx_graph.number_of_edges()} edges")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
