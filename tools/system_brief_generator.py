#!/usr/bin/env python3
"""
System Brief Generator for SIMP
Automatically generates architecture briefs and onboarding packs
using the Graphify knowledge graph.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import textwrap

class SystemBriefGenerator:
    """Generates system briefs from Graphify knowledge graph."""
    
    def __init__(self, graph_dir: str = ".graphify"):
        self.graph_dir = Path(graph_dir)
        self.graph_path = self.graph_dir / "simp_graph.json"
        self.analysis_path = self.graph_dir / "analysis.json"
        
        if not self.graph_path.exists():
            raise FileNotFoundError(f"Graph file not found: {self.graph_path}")
        
        print(f"📊 Loading graph from {self.graph_path}...")
        with open(self.graph_path, 'r') as f:
            self.graph = json.load(f)
        
        if self.analysis_path.exists():
            with open(self.analysis_path, 'r') as f:
                self.analysis = json.load(f)
        else:
            self.analysis = {}
        
        self.nodes = self.graph.get("nodes", [])
        self.edges = self.graph.get("edges", [])
        print(f"✅ Loaded {len(self.nodes)} nodes, {len(self.edges)} edges")
    
    def generate_architecture_brief(self, output_dir: str = "briefs") -> Dict[str, Any]:
        """Generate comprehensive architecture brief."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        brief = {
            "generated_at": datetime.now().isoformat(),
            "graph_version": self.analysis.get("generated_at", "unknown"),
            "summary": self._generate_summary(),
            "modules": self._generate_module_overview(),
            "agents": self._generate_agent_overview(),
            "tests": self._generate_test_overview(),
            "dependencies": self._generate_dependency_overview(),
            "recommendations": self._generate_recommendations(),
            "quick_start": self._generate_quick_start_guide()
        }
        
        # Save JSON
        json_path = output_path / f"architecture_brief_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(brief, f, indent=2)
        
        # Save Markdown
        md_path = output_path / f"architecture_brief_{timestamp}.md"
        self._save_markdown_brief(md_path, brief)
        
        # Save HTML
        html_path = output_path / f"architecture_brief_{timestamp}.html"
        self._save_html_brief(html_path, brief)
        
        print(f"✅ Generated architecture brief:")
        print(f"   📄 JSON: {json_path}")
        print(f"   📝 Markdown: {md_path}")
        print(f"   🌐 HTML: {html_path}")
        
        return brief
    
    def generate_onboarding_pack(self, role: str = "developer", output_dir: str = "onboarding") -> Dict[str, Any]:
        """Generate role-specific onboarding pack."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if role == "developer":
            pack = self._generate_developer_onboarding()
        elif role == "agent":
            pack = self._generate_agent_onboarding()
        elif role == "operator":
            pack = self._generate_operator_onboarding()
        else:
            pack = self._generate_general_onboarding()
        
        pack["generated_at"] = datetime.now().isoformat()
        pack["role"] = role
        
        # Save pack
        pack_path = output_path / f"onboarding_{role}_{timestamp}.json"
        with open(pack_path, 'w') as f:
            json.dump(pack, f, indent=2)
        
        # Save guide
        guide_path = output_path / f"onboarding_{role}_{timestamp}.md"
        self._save_onboarding_guide(guide_path, pack, role)
        
        print(f"✅ Generated {role} onboarding pack:")
        print(f"   📄 JSON: {pack_path}")
        print(f"   📝 Guide: {guide_path}")
        
        return pack
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate system summary."""
        # Count different types of nodes based on Graphify structure
        code_files = [n for n in self.nodes if n.get("file_type") == "code" and n.get("label", "").endswith(".py")]
        class_nodes = [n for n in self.nodes if n.get("file_type") == "code" and "class" in n.get("label", "").lower()]
        function_nodes = [n for n in self.nodes if n.get("file_type") == "code" and "(" in n.get("label", "") and ")" in n.get("label", "")]
        
        # Extract modules from file paths
        modules = {}
        for node in self.nodes:
            if node.get("file_type") == "code" and node.get("source_file"):
                path = node.get("source_file", "")
                # Extract module from path
                if "simp/" in path:
                    # Get path relative to simp directory
                    rel_path = path.split("simp/")[-1]
                    # Get directory structure
                    parts = rel_path.split("/")
                    if len(parts) > 1:
                        module_name = parts[0]
                        if module_name not in modules:
                            modules[module_name] = {
                                "file_count": 0,
                                "class_count": 0,
                                "function_count": 0
                            }
        
        # Count files per module
        for node in self.nodes:
            if node.get("file_type") == "code" and node.get("source_file"):
                path = node.get("source_file", "")
                if "simp/" in path:
                    rel_path = path.split("simp/")[-1]
                    parts = rel_path.split("/")
                    if len(parts) > 1:
                        module_name = parts[0]
                        if module_name in modules:
                            # Check if this is a file node (ends with .py in label)
                            if node.get("label", "").endswith(".py"):
                                modules[module_name]["file_count"] += 1
                            # Check if class
                            elif "class" in node.get("label", "").lower():
                                modules[module_name]["class_count"] += 1
                            # Check if function
                            elif "(" in node.get("label", "") and ")" in node.get("label", ""):
                                modules[module_name]["function_count"] += 1
        
        # Find most important modules (by file count)
        important_modules = []
        for module_name, counts in modules.items():
            if counts["file_count"] > 0:
                # Calculate importance score (simple heuristic)
                importance = counts["file_count"] * 0.5 + counts["class_count"] * 0.3 + counts["function_count"] * 0.2
                important_modules.append({
                    "name": module_name,
                    "importance": importance,
                    "file_count": counts["file_count"],
                    "class_count": counts["class_count"],
                    "function_count": counts["function_count"]
                })
        
        important_modules.sort(key=lambda x: x["importance"], reverse=True)
        
        return {
            "total_files": len(code_files),
            "total_modules": len(modules),
            "total_classes": len(class_nodes),
            "total_functions": len(function_nodes),
            "total_edges": len(self.edges),
            "most_important_modules": important_modules[:10],
            "graph_density": len(self.edges) / (len(self.nodes) * (len(self.nodes) - 1)) if len(self.nodes) > 1 else 0,
            "node_types": {
                "code_files": len(code_files),
                "classes": len(class_nodes),
                "functions": len(function_nodes),
                "total_nodes": len(self.nodes)
            }
        }
    
    def _generate_module_overview(self) -> Dict[str, Any]:
        """Generate module overview."""
        modules = {}
        
        # First pass: identify all modules from file paths
        for node in self.nodes:
            if node.get("file_type") == "code" and node.get("source_file"):
                path = node.get("source_file", "")
                if "simp/" in path:
                    rel_path = path.split("simp/")[-1]
                    parts = rel_path.split("/")
                    if len(parts) > 1:
                        module_name = parts[0]
                        if module_name not in modules:
                            modules[module_name] = {
                                "file_count": 0,
                                "class_count": 0,
                                "function_count": 0,
                                "dependencies": set(),
                                "dependents": set()
                            }
        
        # Second pass: count files, classes, functions per module
        for node in self.nodes:
            if node.get("file_type") == "code" and node.get("source_file"):
                path = node.get("source_file", "")
                if "simp/" in path:
                    rel_path = path.split("simp/")[-1]
                    parts = rel_path.split("/")
                    if len(parts) > 1:
                        module_name = parts[0]
                        if module_name in modules:
                            label = node.get("label", "")
                            # File node (ends with .py)
                            if label.endswith(".py"):
                                modules[module_name]["file_count"] += 1
                            # Class node
                            elif "class" in label.lower():
                                modules[module_name]["class_count"] += 1
                            # Function node (has parentheses)
                            elif "(" in label and ")" in label:
                                modules[module_name]["function_count"] += 1
        
        # Third pass: find dependencies from edges
        for edge in self.edges:
            edge_type = edge.get("type", "")
            source_id = edge.get("source")
            target_id = edge.get("target")
            
            # Find source and target modules
            source_module = None
            target_module = None
            
            # Find source node
            source_node = next((n for n in self.nodes if n.get("id") == source_id), None)
            if source_node and source_node.get("source_file"):
                path = source_node.get("source_file", "")
                if "simp/" in path:
                    rel_path = path.split("simp/")[-1]
                    parts = rel_path.split("/")
                    if len(parts) > 1:
                        source_module = parts[0]
            
            # Find target node
            target_node = next((n for n in self.nodes if n.get("id") == target_id), None)
            if target_node and target_node.get("source_file"):
                path = target_node.get("source_file", "")
                if "simp/" in path:
                    rel_path = path.split("simp/")[-1]
                    parts = rel_path.split("/")
                    if len(parts) > 1:
                        target_module = parts[0]
            
            # Add dependency if both modules found and different
            if source_module and target_module and source_module != target_module:
                if edge_type in ["depends_on", "calls", "imports"]:
                    modules[source_module]["dependencies"].add(target_module)
                    modules[target_module]["dependents"].add(source_module)
        
        # Convert sets to lists for JSON serialization
        for module_name in modules:
            modules[module_name]["dependencies"] = list(modules[module_name]["dependencies"])
            modules[module_name]["dependents"] = list(modules[module_name]["dependents"])
            
            # Calculate importance score
            counts = modules[module_name]
            importance = counts["file_count"] * 0.5 + counts["class_count"] * 0.3 + counts["function_count"] * 0.2
            modules[module_name]["importance"] = importance
        
        return modules
    
    def _generate_agent_overview(self) -> Dict[str, Any]:
        """Generate agent overview."""
        agents = {}
        
        # Find agent-related modules
        for node in self.nodes:
            if node.get("type") == "module" and "agent" in node.get("name", "").lower():
                agents[node.get("name")] = {
                    "id": node.get("id"),
                    "centrality": node.get("centrality", 0),
                    "capabilities": [],
                    "dependencies": [],
                    "dependents": []
                }
        
        # Add known agents from analysis
        if "agents" in self.analysis:
            for agent_name, agent_data in self.analysis["agents"].items():
                if agent_name not in agents:
                    agents[agent_name] = {
                        "id": f"agent_{agent_name}",
                        "centrality": 0,
                        "capabilities": agent_data.get("capabilities", []),
                        "dependencies": [],
                        "dependents": []
                    }
        
        return agents
    
    def _generate_test_overview(self) -> Dict[str, Any]:
        """Generate test overview."""
        test_files = [n for n in self.nodes if n.get("type") == "file" and "test" in n.get("name", "").lower()]
        
        return {
            "total_test_files": len(test_files),
            "test_files_by_module": self._group_tests_by_module(test_files),
            "test_coverage": self._estimate_test_coverage()
        }
    
    def _group_tests_by_module(self, test_files: List[Dict]) -> Dict[str, List[str]]:
        """Group test files by the modules they test."""
        test_map = {}
        
        for test_file in test_files:
            test_name = test_file.get("name", "")
            
            # Find what this test depends on
            dependencies = []
            for edge in self.edges:
                if edge.get("source") == test_file.get("id") and edge.get("type") == "depends_on":
                    target_node = next((n for n in self.nodes if n.get("id") == edge.get("target")), None)
                    if target_node and target_node.get("type") == "module":
                        module_name = target_node.get("name", "")
                        if module_name not in test_map:
                            test_map[module_name] = []
                        if test_name not in test_map[module_name]:
                            test_map[module_name].append(test_name)
        
        return test_map
    
    def _estimate_test_coverage(self) -> Dict[str, Any]:
        """Estimate test coverage based on dependencies."""
        total_modules = len([n for n in self.nodes if n.get("type") == "module"])
        tested_modules = set()
        
        for node in self.nodes:
            if node.get("type") == "file" and "test" in node.get("name", "").lower():
                # Find modules this test depends on
                for edge in self.edges:
                    if edge.get("source") == node.get("id") and edge.get("type") == "depends_on":
                        target_node = next((n for n in self.nodes if n.get("id") == edge.get("target")), None)
                        if target_node and target_node.get("type") == "module":
                            tested_modules.add(target_node.get("name", ""))
        
        coverage_percent = (len(tested_modules) / total_modules * 100) if total_modules > 0 else 0
        
        return {
            "total_modules": total_modules,
            "tested_modules": len(tested_modules),
            "coverage_percent": round(coverage_percent, 2),
            "untested_modules": total_modules - len(tested_modules)
        }
    
    def _generate_dependency_overview(self) -> Dict[str, Any]:
        """Generate dependency overview."""
        dependencies = {}
        
        for edge in self.edges:
            if edge.get("type") == "depends_on":
                source_id = edge.get("source")
                target_id = edge.get("target")
                
                source_node = next((n for n in self.nodes if n.get("id") == source_id), None)
                target_node = next((n for n in self.nodes if n.get("id") == target_id), None)
                
                if source_node and target_node:
                    source_name = source_node.get("name", "")
                    target_name = target_node.get("name", "")
                    
                    if source_name not in dependencies:
                        dependencies[source_name] = []
                    
                    if target_name not in dependencies[source_name]:
                        dependencies[source_name].append(target_name)
        
        # Calculate dependency metrics
        dependency_counts = {name: len(deps) for name, deps in dependencies.items()}
        most_dependent = sorted(dependency_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "dependency_graph": dependencies,
            "most_dependent_modules": most_dependent,
            "total_dependencies": sum(dependency_counts.values()),
            "average_dependencies": sum(dependency_counts.values()) / len(dependency_counts) if dependency_counts else 0
        }
    
    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate architecture recommendations."""
        recommendations = []
        
        # Check for high centrality modules with few tests
        modules = self._generate_module_overview()
        test_map = self._generate_test_overview()["test_files_by_module"]
        
        for module_name, module_data in modules.items():
            centrality = module_data.get("centrality", 0)
            test_count = len(test_map.get(module_name, []))
            
            if centrality > 0.2 and test_count == 0:
                recommendations.append({
                    "type": "high_priority_testing",
                    "module": module_name,
                    "centrality": centrality,
                    "reason": f"High centrality module ({centrality:.3f}) has no tests",
                    "suggestion": f"Add comprehensive tests for {module_name}"
                })
        
        # Check for circular dependencies
        dependencies = self._generate_dependency_overview()["dependency_graph"]
        for module, deps in dependencies.items():
            for dep in deps:
                if dep in dependencies and module in dependencies.get(dep, []):
                    recommendations.append({
                        "type": "circular_dependency",
                        "modules": [module, dep],
                        "reason": "Circular dependency detected",
                        "suggestion": f"Break circular dependency between {module} and {dep}"
                    })
        
        # Check for modules with too many dependencies
        for module, deps in dependencies.items():
            if len(deps) > 10:  # Arbitrary threshold
                recommendations.append({
                    "type": "high_coupling",
                    "module": module,
                    "dependency_count": len(deps),
                    "reason": f"Module has {len(deps)} dependencies (high coupling)",
                    "suggestion": f"Refactor {module} to reduce dependencies"
                })
        
        return recommendations[:10]  # Limit to top 10
    
    def _generate_quick_start_guide(self) -> Dict[str, Any]:
        """Generate quick start guide."""
        return {
            "setup": [
                "1. Clone repository",
                "2. Install dependencies: pip install -r requirements.txt",
                "3. Set environment variables (see .env.example)",
                "4. Start broker: python -m simp.server.broker",
                "5. Access dashboard: http://localhost:8050"
            ],
            "common_commands": [
                "Run tests: python -m pytest tests/ -v",
                "Generate brief: python tools/system_brief_generator.py",
                "Analyze impact: python tools/change_impact_analyzer.py <files>",
                "Select tests: python tools/test_selection_helper.py <files>"
            ],
            "key_files": [
                "simp/server/broker.py - Main broker",
                "simp/compat/ - A2A compatibility layer",
                "dashboard/server.py - Dashboard",
                "tests/ - Test suite"
            ],
            "troubleshooting": [
                "Broker not starting: Check port 5555 is free",
                "Tests failing: Run with SIMP_REQUIRE_API_KEY=false",
                "Import errors: Check Python version (3.10 required)"
            ]
        }
    
    def _generate_developer_onboarding(self) -> Dict[str, Any]:
        """Generate developer onboarding pack."""
        return {
            "welcome": "Welcome to SIMP Development!",
            "architecture": self._generate_summary(),
            "key_modules": self._get_key_modules_for_developers(),
            "development_workflow": [
                "1. Read the code before writing (Rule 1)",
                "2. Write to disk, compile, test (Rules 2-4)",
                "3. Follow existing patterns (Rule 6)",
                "4. Use python3.10 for everything",
                "5. Run full test suite before committing"
            ],
            "tools": [
                "change_impact_analyzer.py - Predict impact of changes",
                "test_selection_helper.py - Select relevant tests",
                "system_brief_generator.py - Generate architecture briefs",
                "graphify_simp_final.sh - Update knowledge graph"
            ],
            "common_pitfalls": [
                "Using python3 instead of python3.10",
                "Modifying protected files without permission",
                "Forgetting to compile before testing",
                "Not reading source files before writing tests"
            ],
            "resources": [
                "docs/ - Documentation",
                ".graphify/ - Architecture maps",
                "SPRINT_LOG.md - Development history",
                "PROTOCOL_CONFORMANCE.md - Standards"
            ]
        }
    
    def _generate_agent_onboarding(self) -> Dict[str, Any]:
        """Generate agent onboarding pack."""
        return {
            "welcome": "Welcome to SIMP Agent Integration!",
            "agent_architecture": self._generate_agent_overview(),
            "agent_tools": [
                "agent_helper.py - Query knowledge graph",
                "change_impact_analyzer.py - Analyze code changes",
                "test_selection_helper.py - Select tests",
                "system_brief_generator.py - Generate briefs"
            ],
            "agent_rules": [
                "Rule 1: Read before write",
                "Rule 2: Always write to disk",
                "Rule 3: Always compile and test",
                "Rule 4: Fix failures immediately",
                "Rule 5: Explain deviations",
                "Rule 6: Protected files (never modify without permission)",
                "Rule 7: Append-only ledgers",
                "Rule 8: Financial safety (simulated only)",
                "Rule 9: Git discipline",
                "Rule 10: Namespace (x-simp)"
            ],
            "common_agent_tasks": [
                "Writing tests for new modules",
                "Creating new organs (revenue modules)",
                "Integrating with external services",
                "Improving dashboard functionality"
            ],
            "agent_integration": {
                "broker_endpoint": "http://localhost:5555",
                "dashboard_endpoint": "http://localhost:8050",
                "projectx_endpoint": "http://localhost:8771",
                "a2a_compatibility": "simp/compat/"
            }
        }
    
    def _generate_operator_onboarding(self) -> Dict[str, Any]:
        """Generate operator onboarding pack."""
        return {
            "welcome": "Welcome to SIMP Operations!",
            "system_overview": self._generate_summary(),
            "monitoring": [
                "Broker health: http://localhost:5555/health",
                "Dashboard: http://localhost:8050",
                "Agents: http://localhost:5555/agents",
                "Stats: http://localhost:5555/stats"
            ],
            "operational_commands": [
                "Start broker: python -m simp.server.broker",
                "Start dashboard: python dashboard/server.py",
                "Check logs: tail -f logs/broker.log",
                "View ledgers: cat data/*.jsonl | tail -20"
            ],
            "troubleshooting": {
                "broker_down": "Check port 5555, restart broker",
                "dashboard_down": "Check port 8050, restart dashboard",
                "agent_unresponsive": "Check agent heartbeat",
                "tests_failing": "Run with SIMP_REQUIRE_API_KEY=false"
            },
            "safety_protocols": [
                "Financial ops are SIMULATED (FINANCIAL_OPS_LIVE_ENABLED=false)",
                "Never modify protected files without approval",
                "Always backup before major changes",
                "Use feature flags for new functionality"
            ]
        }
    
    def _generate_general_onboarding(self) -> Dict[str, Any]:
        """Generate general onboarding pack."""
        return {
            "welcome": "Welcome to SIMP!",
            "what_is_simp": "Structured Intent Messaging Protocol - The HTTP of Agentic AI",
            "core_components": {
                "broker": "Central message bus (port 5555)",
                "dashboard": "Operator console (port 8050)",
                "agents": "Specialized AI agents",
                "compat": "A2A compatibility layer",
                "organs": "Revenue-generating modules"
            },
            "getting_started": self._generate_quick_start_guide()["setup"],
            "resources": [
                "docs/ - Documentation",
                ".graphify/ - Architecture maps",
                "tools/ - Development tools",
                "tests/ - Test suite"
            ]
        }
    
    def _get_key_modules_for_developers(self) -> List[Dict[str, Any]]:
        """Get key modules for developers."""
        modules = self._generate_module_overview()
        
        # Sort by centrality and importance
        key_modules = []
        for name, data in modules.items():
            if data["centrality"] > 0.1 or data["file_count"] > 10:
                key_modules.append({
                    "name": name,
                    "centrality": data["centrality"],
                    "files": data["file_count"],
                    "classes": data["class_count"],
                    "functions": data["function_count"]
                })
        
        key_modules.sort(key=lambda x: x["centrality"], reverse=True)
        return key_modules[:15]
    
    def _save_markdown_brief(self, path: Path, brief: Dict[str, Any]) -> None:
        """Save brief as Markdown."""
        with open(path, 'w') as f:
            f.write(f"# SIMP Architecture Brief\n\n")
            f.write(f"*Generated: {brief['generated_at']}*\n")
            f.write(f"*Graph Version: {brief['graph_version']}*\n\n")
            
            # Summary
            f.write("## 📊 System Summary\n\n")
            summary = brief["summary"]
            f.write(f"- **Total Files**: {summary['total_files']:,}\n")
            f.write(f"- **Total Modules**: {summary['total_modules']:,}\n")
            f.write(f"- **Total Classes**: {summary['total_classes']:,}\n")
            f.write(f"- **Total Functions**: {summary['total_functions']:,}\n")
            f.write(f"- **Total Edges**: {summary['total_edges']:,}\n")
            f.write(f"- **Graph Density**: {summary['graph_density']:.6f}\n\n")
            
            f.write("### Most Important Modules\n")
            for module in summary.get("most_important_modules", [])[:5]:
                f.write(f"- **{module['name']}** (importance: {module['importance']:.2f}, files: {module['file_count']}, classes: {module['class_count']})\n")
            f.write("\n")
            
            # Modules
            f.write("## 🏗️ Module Overview\n\n")
            modules = brief["modules"]
            for name, data in sorted(modules.items(), key=lambda x: x[1].get("importance", 0), reverse=True)[:20]:
                f.write(f"### {name}\n")
                f.write(f"- Importance: {data.get('importance', 0):.2f}\n")
                f.write(f"- Files: {data.get('file_count', 0)}, Classes: {data.get('class_count', 0)}, Functions: {data.get('function_count', 0)}\n")
                deps = data.get('dependencies', [])
                if deps:
                    f.write(f"- Dependencies: {', '.join(deps[:5])}")
                    if len(deps) > 5:
                        f.write(f" (+{len(deps) - 5} more)")
                    f.write("\n")
                f.write("\n")
            
            # Recommendations
            if brief["recommendations"]:
                f.write("## 🚨 Recommendations\n\n")
                for rec in brief["recommendations"]:
                    f.write(f"### {rec['type'].replace('_', ' ').title()}\n")
                    f.write(f"- **Module**: {rec.get('module', rec.get('modules', ['N/A']))}\n")
                    f.write(f"- **Reason**: {rec['reason']}\n")
                    f.write(f"- **Suggestion**: {rec['suggestion']}\n\n")
            
            # Quick Start
            f.write("## 🚀 Quick Start Guide\n\n")
            for step in brief["quick_start"]["setup"]:
                f.write(f"{step}\n")
            f.write("\n")
    
    def _save_html_brief(self, path: Path, brief: Dict[str, Any]) -> None:
        """Save brief as HTML."""
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SIMP Architecture Brief</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; line-height: 1.6; }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #444; margin-top: 30px; border-bottom: 1px solid #ddd; padding-bottom: 5px; }}
        h3 {{ color: #555; }}
        .summary {{ background: #f5f5f5; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        .module {{ background: #fff; border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        .recommendation {{ background: #fff8e1; border-left: 4px solid #ffc107; padding: 15px; margin: 10px 0; }}
        .metric {{ display: inline-block; background: #4CAF50; color: white; padding: 5px 10px; margin: 5px; border-radius: 3px; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>🏗️ SIMP Architecture Brief</h1>
    <div class="timestamp">Generated: {brief['generated_at']} | Graph Version: {brief['graph_version']}</div>
    
    <h2>📊 System Summary</h2>
    <div class="summary">
"""
        
        summary = brief["summary"]
        html += f"""
        <div class="metric">📁 {summary['total_files']:,} Files</div>
        <div class="metric">📦 {summary['total_modules']:,} Modules</div>
        <div class="metric">🏛️ {summary['total_classes']:,} Classes</div>
        <div class="metric">⚙️ {summary['total_functions']:,} Functions</div>
        <div class="metric">🔗 {summary['total_edges']:,} Edges</div>
        <div class="metric">📈 Density: {summary['graph_density']:.6f}</div>
        
        <h3>Most Central Modules</h3>
        <ul>
"""
        
        for module in summary.get("most_important_modules", [])[:5]:
            html += f'<li><strong>{module["name"]}</strong> (importance: {module.get("importance", 0):.2f}, files: {module.get("file_count", 0)})</li>\n'
        
        html += """
        </ul>
    </div>
    
    <h2>🏗️ Top Modules</h2>
"""
        
        modules = brief["modules"]
        for name, data in sorted(modules.items(), key=lambda x: x[1].get("importance", 0), reverse=True)[:15]:
            html += f"""
    <div class="module">
        <h3>{name}</h3>
        <p>Importance: {data.get('importance', 0):.2f} | Files: {data.get('file_count', 0)} | Classes: {data.get('class_count', 0)} | Functions: {data.get('function_count', 0)}</p>
"""
            
            if data['dependencies']:
                html += f"<p><strong>Dependencies:</strong> {', '.join(data['dependencies'][:3])}"
                if len(data['dependencies']) > 3:
                    html += f" (+{len(data['dependencies']) - 3} more)"
                html += "</p>"
            
            html += "</div>\n"
        
        if brief["recommendations"]:
            html += """
    <h2>🚨 Recommendations</h2>
"""
            for rec in brief["recommendations"][:5]:
                html += f"""
    <div class="recommendation">
        <h3>{rec['type'].replace('_', ' ').title()}</h3>
        <p><strong>Module:</strong> {rec.get('module', rec.get('modules', ['N/A']))}</p>
        <p><strong>Reason:</strong> {rec['reason']}</p>
        <p><strong>Suggestion:</strong> {rec['suggestion']}</p>
    </div>
"""
        
        html += """
    <h2>🚀 Quick Start</h2>
    <ol>
"""
        
        for step in brief["quick_start"]["setup"]:
            html += f"<li>{step}</li>\n"
        
        html += """
    </ol>
    
    <footer style="margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; color: #666;">
        <p>Generated by SIMP System Brief Generator | Using Graphify Architecture Maps</p>
    </footer>
</body>
</html>
"""
        
        with open(path, 'w') as f:
            f.write(html)
    
    def _save_onboarding_guide(self, path: Path, pack: Dict[str, Any], role: str) -> None:
        """Save onboarding guide as Markdown."""
        with open(path, 'w') as f:
            f.write(f"# SIMP Onboarding Guide for {role.title()}s\n\n")
            f.write(f"*Generated: {pack['generated_at']}*\n\n")
            
            f.write(f"## 👋 Welcome!\n\n")
            f.write(f"{pack.get('welcome', 'Welcome to SIMP!')}\n\n")
            
            if "architecture" in pack:
                f.write("## 📊 Architecture Overview\n\n")
                arch = pack["architecture"]
                f.write(f"- **Total Files**: {arch['total_files']:,}\n")
                f.write(f"- **Total Modules**: {arch['total_modules']:,}\n")
                f.write(f"- **Total Classes**: {arch['total_classes']:,}\n")
                f.write(f"- **Total Functions**: {arch['total_functions']:,}\n\n")
            
            if "key_modules" in pack:
                f.write("## 🗝️ Key Modules\n\n")
                for module in pack["key_modules"][:10]:
                    f.write(f"### {module['name']}\n")
                    f.write(f"- Centrality: {module['centrality']:.3f}\n")
                    f.write(f"- Files: {module['files']}, Classes: {module['classes']}, Functions: {module['functions']}\n\n")
            
            if "development_workflow" in pack:
                f.write("## 🔧 Development Workflow\n\n")
                for step in pack["development_workflow"]:
                    f.write(f"1. {step}\n")
                f.write("\n")
            
            if "agent_rules" in pack:
                f.write("## 📜 Agent Rules\n\n")
                for i, rule in enumerate(pack["agent_rules"], 1):
                    f.write(f"{i}. {rule}\n")
                f.write("\n")
            
            if "tools" in pack:
                f.write("## 🛠️ Available Tools\n\n")
                for tool in pack["tools"]:
                    f.write(f"- `{tool}`\n")
                f.write("\n")
            
            if "resources" in pack:
                f.write("## 📚 Resources\n\n")
                for resource in pack["resources"]:
                    f.write(f"- `{resource}`\n")
                f.write("\n")
            
            f.write("## 🎯 Next Steps\n\n")
            f.write("1. Explore the repository structure\n")
            f.write("2. Run the test suite to ensure everything works\n")
            f.write("3. Check out the dashboard at http://localhost:8050\n")
            f.write("4. Review the architecture briefs in the `briefs/` directory\n")
            f.write("5. Join the development community!\n")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate SIMP system briefs and onboarding packs")
    parser.add_argument("--brief", action="store_true", help="Generate architecture brief")
    parser.add_argument("--onboarding", choices=["developer", "agent", "operator", "general"], 
                       help="Generate onboarding pack for specific role")
    parser.add_argument("--output-dir", default="briefs", help="Output directory")
    parser.add_argument("--graph-dir", default=".graphify", help="Graphify directory")
    
    args = parser.parse_args()
    
    try:
        generator = SystemBriefGenerator(args.graph_dir)
        
        if args.brief:
            print("🎯 Generating architecture brief...")
            brief = generator.generate_architecture_brief(args.output_dir)
            print("✅ Architecture brief generated successfully!")
            
        elif args.onboarding:
            print(f"🎯 Generating {args.onboarding} onboarding pack...")
            pack = generator.generate_onboarding_pack(args.onboarding, args.output_dir)
            print(f"✅ {args.onboarding} onboarding pack generated successfully!")
            
        else:
            # Default: generate both
            print("🎯 Generating architecture brief...")
            generator.generate_architecture_brief(args.output_dir)
            print("\n🎯 Generating developer onboarding pack...")
            generator.generate_onboarding_pack("developer", args.output_dir)
            print("\n🎯 Generating agent onboarding pack...")
            generator.generate_onboarding_pack("agent", args.output_dir)
            print("\n✅ All briefs and packs generated successfully!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
