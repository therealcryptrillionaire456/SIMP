#!/usr/bin/env python3
"""
Module Documentation Generator for SIMP
Generates comprehensive documentation for modules using Graphify knowledge graph.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
import argparse
import re

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

class ModuleDocumentationGenerator:
    """Generates documentation for SIMP modules from Graphify knowledge graph."""
    
    def __init__(self, graph_dir: str = ".graphify"):
        """Initialize with Graphify data directory."""
        self.graph_dir = Path(graph_dir)
        self.graph = None
        self.analysis = None
        
    def load_data(self) -> bool:
        """Load Graphify data files."""
        try:
            # Load main graph
            graph_path = self.graph_dir / "simp_graph.json"
            if not graph_path.exists():
                print(f"❌ Graph file not found: {graph_path}")
                return False
                
            print(f"📊 Loading graph from {graph_path}...")
            with open(graph_path, 'r') as f:
                self.graph = json.load(f)
                
            # Load analysis
            analysis_path = self.graph_dir / "analysis.json"
            if analysis_path.exists():
                with open(analysis_path, 'r') as f:
                    self.analysis = json.load(f)
                    
            print(f"✅ Loaded: {len(self.graph.get('nodes', []))} nodes, {len(self.graph.get('edges', []))} edges")
            return True
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return False
    
    def generate_module_docs(self, 
                            module_path: str = "all",
                            output_dir: str = "docs/modules",
                            include_tests: bool = True,
                            include_examples: bool = True) -> Dict[str, Any]:
        """Generate documentation for one or all modules."""
        if not self.load_data():
            return {}
            
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Get all module nodes
        module_nodes = [n for n in self.graph.get("nodes", []) if n.get("type") == "module"]
        
        if module_path == "all":
            print(f"📚 Generating documentation for all {len(module_nodes)} modules...")
            results = []
            
            for module_node in module_nodes:
                module_id = module_node.get("id")
                print(f"  📄 Processing: {module_id}")
                
                module_docs = self._generate_single_module_docs(
                    module_node, 
                    include_tests=include_tests,
                    include_examples=include_examples
                )
                
                if module_docs:
                    # Save module documentation
                    module_slug = module_id.replace(".", "_").replace("/", "_")
                    doc_path = output_path / f"{module_slug}.md"
                    
                    with open(doc_path, 'w') as f:
                        f.write(module_docs["markdown"])
                    
                    # Save JSON data
                    json_path = output_path / f"{module_slug}.json"
                    with open(json_path, 'w') as f:
                        json.dump(module_docs["data"], f, indent=2)
                    
                    results.append({
                        "module": module_id,
                        "markdown_file": str(doc_path),
                        "json_file": str(json_path),
                        "stats": module_docs["data"]["stats"],
                    })
            
            # Generate index
            index_markdown = self._generate_module_index(results)
            index_path = output_path / "INDEX.md"
            with open(index_path, 'w') as f:
                f.write(index_markdown)
            
            print(f"\n✅ Generated documentation for {len(results)} modules")
            print(f"📁 Output: {output_path}")
            print(f"📄 Index: {index_path}")
            
            return {
                "total_modules": len(results),
                "output_directory": str(output_path),
                "modules": results,
            }
            
        else:
            # Generate for specific module
            module_node = next((n for n in module_nodes if n.get("id") == module_path), None)
            
            if not module_node:
                print(f"❌ Module not found: {module_path}")
                # Try to find by partial match
                matching = [n for n in module_nodes if module_path in n.get("id", "")]
                if matching:
                    print(f"   Similar modules found:")
                    for m in matching[:5]:
                        print(f"   - {m.get('id')}")
                return {}
            
            print(f"📚 Generating documentation for: {module_path}")
            
            module_docs = self._generate_single_module_docs(
                module_node,
                include_tests=include_tests,
                include_examples=include_examples
            )
            
            if module_docs:
                # Save module documentation
                module_slug = module_path.replace(".", "_").replace("/", "_")
                doc_path = output_path / f"{module_slug}.md"
                
                with open(doc_path, 'w') as f:
                    f.write(module_docs["markdown"])
                
                # Save JSON data
                json_path = output_path / f"{module_slug}.json"
                with open(json_path, 'w') as f:
                    json.dump(module_docs["data"], f, indent=2)
                
                print(f"\n✅ Generated documentation for {module_path}")
                print(f"📄 Markdown: {doc_path}")
                print(f"📊 JSON: {json_path}")
                
                return {
                    "module": module_path,
                    "markdown_file": str(doc_path),
                    "json_file": str(json_path),
                    "data": module_docs["data"],
                }
            
            return {}
    
    def _generate_single_module_docs(self, 
                                    module_node: Dict[str, Any],
                                    include_tests: bool = True,
                                    include_examples: bool = True) -> Dict[str, Any]:
        """Generate documentation for a single module."""
        module_id = module_node.get("id")
        
        # Get related nodes and edges
        related_data = self._get_related_module_data(module_id)
        
        # Build documentation data
        doc_data = {
            "module": {
                "id": module_id,
                "name": module_node.get("name", ""),
                "description": module_node.get("description", ""),
                "type": module_node.get("type", ""),
            },
            "stats": {
                "file_count": module_node.get("file_count", 0),
                "function_count": module_node.get("function_count", 0),
                "class_count": module_node.get("class_count", 0),
                "line_count": module_node.get("line_count", 0),
            },
            "structure": self._get_module_structure(module_id),
            "dependencies": related_data["dependencies"],
            "dependents": related_data["dependents"],
            "key_classes": related_data["key_classes"],
            "key_functions": related_data["key_functions"],
            "usage_patterns": self._get_usage_patterns(module_id),
            "test_coverage": self._get_test_coverage(module_id) if include_tests else {},
            "examples": self._get_examples(module_id) if include_examples else [],
            "architecture_context": self._get_architecture_context(module_id),
        }
        
        # Generate markdown
        markdown = self._generate_module_markdown(doc_data)
        
        return {
            "data": doc_data,
            "markdown": markdown,
        }
    
    def _get_related_module_data(self, module_id: str) -> Dict[str, Any]:
        """Get data related to a module."""
        if not self.graph:
            return {}
            
        edges = self.graph.get("edges", [])
        nodes = self.graph.get("nodes", [])
        
        # Find edges where this module is source or target
        module_edges = [e for e in edges if e.get("source") == module_id or e.get("target") == module_id]
        
        dependencies = set()
        dependents = set()
        
        for edge in module_edges:
            source = edge.get("source")
            target = edge.get("target")
            relation = edge.get("relation", "")
            
            if source == module_id:
                # Module depends on target
                if target != module_id:  # Skip self-references
                    dependencies.add((target, relation))
            elif target == module_id:
                # Module is depended on by source
                if source != module_id:  # Skip self-references
                    dependents.add((source, relation))
        
        # Get key classes and functions in this module
        key_classes = []
        key_functions = []
        
        for node in nodes:
            node_module = node.get("module", "")
            if node_module == module_id:
                if node.get("type") == "class":
                    key_classes.append({
                        "name": node.get("name", ""),
                        "description": node.get("description", ""),
                        "methods": node.get("method_count", 0),
                        "properties": node.get("property_count", 0),
                    })
                elif node.get("type") == "function":
                    key_functions.append({
                        "name": node.get("name", ""),
                        "description": node.get("description", ""),
                        "parameters": node.get("parameter_count", 0),
                        "returns": node.get("return_type", ""),
                    })
        
        return {
            "dependencies": [{"module": m, "relation": r} for m, r in dependencies],
            "dependents": [{"module": m, "relation": r} for m, r in dependents],
            "key_classes": sorted(key_classes, key=lambda x: x["methods"], reverse=True)[:10],
            "key_functions": sorted(key_functions, key=lambda x: x["parameters"], reverse=True)[:10],
        }
    
    def _get_module_structure(self, module_id: str) -> Dict[str, Any]:
        """Get module file structure."""
        if not self.graph:
            return {}
            
        nodes = self.graph.get("nodes", [])
        
        # Find files in this module
        module_files = [n for n in nodes if n.get("module") == module_id and n.get("type") == "file"]
        
        structure = {
            "files": [],
            "submodules": set(),
        }
        
        for file_node in module_files:
            file_path = file_node.get("id", "")
            file_name = file_node.get("name", "")
            
            structure["files"].append({
                "path": file_path,
                "name": file_name,
                "description": file_node.get("description", ""),
                "lines": file_node.get("lines", 0),
                "size": file_node.get("size", 0),
            })
            
            # Check for submodules
            if "." in file_path:
                # Extract potential submodule
                parts = file_path.split(".")
                if len(parts) > 1:
                    # Look for module nodes that might be submodules
                    for node in nodes:
                        if node.get("type") == "module" and node.get("id").startswith(module_id + "."):
                            structure["submodules"].add(node.get("id"))
        
        # Sort files by lines (largest first)
        structure["files"].sort(key=lambda x: x["lines"], reverse=True)
        
        return structure
    
    def _get_usage_patterns(self, module_id: str) -> List[Dict[str, Any]]:
        """Get usage patterns for the module."""
        if not self.graph:
            return []
            
        edges = self.graph.get("edges", [])
        
        # Find import/usage patterns
        usage_patterns = []
        
        for edge in edges:
            if edge.get("target") == module_id and edge.get("relation") in ["imports", "uses", "calls"]:
                source = edge.get("source")
                relation = edge.get("relation")
                
                # Find source node
                source_node = next((n for n in self.graph.get("nodes", []) if n.get("id") == source), None)
                
                if source_node:
                    usage_patterns.append({
                        "source": source,
                        "source_type": source_node.get("type", ""),
                        "relation": relation,
                        "context": edge.get("context", ""),
                    })
        
        # Group by source type and relation
        grouped_patterns = {}
        for pattern in usage_patterns:
            key = f"{pattern['source_type']}_{pattern['relation']}"
            if key not in grouped_patterns:
                grouped_patterns[key] = []
            grouped_patterns[key].append(pattern)
        
        # Convert to list
        result = []
        for key, patterns in grouped_patterns.items():
            source_type, relation = key.split("_", 1)
            result.append({
                "pattern": f"{relation.capitalize()} by {source_type}s",
                "count": len(patterns),
                "examples": patterns[:3],  # Top 3 examples
            })
        
        return sorted(result, key=lambda x: x["count"], reverse=True)
    
    def _get_test_coverage(self, module_id: str) -> Dict[str, Any]:
        """Get test coverage information for module."""
        # Try to load test map
        test_map_path = self.graph_dir / "test_map.json"
        if not test_map_path.exists():
            return {"test_map_available": False}
            
        try:
            with open(test_map_path, 'r') as f:
                test_map = json.load(f)
        except:
            return {"test_map_available": False}
        
        # Find tests for this module
        module_tests = []
        for test in test_map.get("tests", []):
            test_module = test.get("module", "")
            if module_id in test_module or test_module in module_id:
                module_tests.append({
                    "test_file": test.get("file", ""),
                    "test_name": test.get("name", ""),
                    "test_type": test.get("type", ""),
                    "coverage": test.get("coverage", ""),
                })
        
        return {
            "test_map_available": True,
            "total_tests": len(module_tests),
            "tests": module_tests[:10],  # Top 10 tests
            "test_files": len(set(t["test_file"] for t in module_tests)),
        }
    
    def _get_examples(self, module_id: str) -> List[Dict[str, Any]]:
        """Get example usage for module."""
        # This would ideally extract from docstrings or example files
        # For now, generate generic examples based on module type
        
        examples = []
        
        if "broker" in module_id:
            examples.append({
                "title": "Starting the broker",
                "code": """python3.10 -m simp.server.broker""",
                "description": "Starts the SIMP broker on port 5555",
            })
            examples.append({
                "title": "Checking broker health",
                "code": """curl -s http://127.0.0.1:5555/health""",
                "description": "Returns broker health status",
            })
            
        elif "compat" in module_id:
            examples.append({
                "title": "Getting agent card",
                "code": """curl -s http://127.0.0.1:5555/a2a/agents/kashclaw/agent.json""",
                "description": "Retrieves A2A agent card for kashclaw agent",
            })
            
        elif "quantumarb" in module_id:
            examples.append({
                "title": "Running arb detection",
                "code": """from simp.organs.quantumarb import ArbDetector
detector = ArbDetector()
opportunities = detector.detect_arbitrage()""",
                "description": "Detects arbitrage opportunities across exchanges",
            })
            
        return examples
    
    def _get_architecture_context(self, module_id: str) -> Dict[str, Any]:
        """Get architecture context for module."""
        # Determine module's role in architecture
        context = {
            "layer": self._determine_architecture_layer(module_id),
            "responsibility": self._determine_responsibility(module_id),
            "criticality": self._determine_criticality(module_id),
            "stability": self._determine_stability(module_id),
        }
        
        return context
    
    def _determine_architecture_layer(self, module_id: str) -> str:
        """Determine which architecture layer the module belongs to."""
        layer_patterns = {
            "infrastructure": ["server", "broker", "delivery", "routing", "ledger"],
            "compatibility": ["compat", "a2a", "agent_card", "task_map"],
            "business": ["organs", "quantumarb", "trading", "financial"],
            "presentation": ["dashboard", "ui", "static"],
            "testing": ["test", "pytest", "fixture"],
            "tooling": ["tools", "graphify", "analyzer"],
        }
        
        for layer, patterns in layer_patterns.items():
            if any(pattern in module_id for pattern in patterns):
                return layer
        
        return "utility"
    
    def _determine_responsibility(self, module_id: str) -> str:
        """Determine module's primary responsibility."""
        if "broker" in module_id:
            return "Message routing and delivery"
        elif "compat" in module_id:
            return "External protocol adaptation"
        elif "financial" in module_id:
            return "Payment simulation and safety"
        elif "quantumarb" in module_id:
            return "Arbitrage detection and execution"
        elif "dashboard" in module_id:
            return "Operator interface and visualization"
        elif "test" in module_id:
            return "Quality assurance and validation"
        else:
            return "Core system functionality"
    
    def _determine_criticality(self, module_id: str) -> str:
        """Determine how critical the module is."""
        critical_modules = [
            "simp.server.broker",
            "simp.server.delivery",
            "simp.server.routing_engine",
            "simp.compat.agent_card",
            "simp.compat.financial_ops",
        ]
        
        if any(critical in module_id for critical in critical_modules):
            return "high"
        elif "test" in module_id or "tools" in module_id:
            return "low"
        else:
            return "medium"
    
    def _determine_stability(self, module_id: str) -> str:
        """Determine module stability."""
        if "test" in module_id:
            return "stable"
        elif "experimental" in module_id or "prototype" in module_id:
            return "experimental"
        elif "quantumarb" in module_id:
            return "evolving"
        else:
            return "stable"
    
    def _generate_module_markdown(self, doc_data: Dict[str, Any]) -> str:
        """Generate markdown documentation for a module."""
        module = doc_data["module"]
        stats = doc_data["stats"]
        
        markdown = f"""# {module['name']}

*Module: `{module['id']}`*  
*Generated: {datetime.utcnow().isoformat() + 'Z'}*

## 📋 Overview

**Description**: {module['description']}  
**Type**: {module['type']}

## 📊 Statistics

| Metric | Value |
|--------|-------|
| Files | {stats['file_count']:,} |
| Functions | {stats['function_count']:,} |
| Classes | {stats['class_count']:,} |
| Lines | {stats['line_count']:,} |

## 🏗️ Architecture Context

**Layer**: {doc_data['architecture_context']['layer']}  
**Responsibility**: {doc_data['architecture_context']['responsibility']}  
**Criticality**: {doc_data['architecture_context']['criticality']}  
**Stability**: {doc_data['architecture_context']['stability']}

## 📁 Structure

### Files ({len(doc_data['structure']['files'])})
"""
        
        for file in doc_data["structure"]["files"][:10]:  # Top 10 files
            markdown += f"- `{file['path']}` ({file['lines']:,} lines) - {file['description']}\n"
            
        if len(doc_data["structure"]["files"]) > 10:
            markdown += f"- ... and {len(doc_data['structure']['files']) - 10} more files\n"
            
        if doc_data["structure"]["submodules"]:
            markdown += f"\n### Submodules ({len(doc_data['structure']['submodules'])})\n"
            for submodule in sorted(doc_data["structure"]["submodules"]):
                markdown += f"- `{submodule}`\n"
        
        markdown += """
## 🔗 Dependencies

### This module depends on:
"""
        
        if doc_data["dependencies"]:
            for dep in doc_data["dependencies"][:10]:  # Top 10 dependencies
                markdown += f"- `{dep['module']}` ({dep['relation']})\n"
            if len(doc_data["dependencies"]) > 10:
                markdown += f"- ... and {len(doc_data['dependencies']) - 10} more dependencies\n"
        else:
            markdown += "*No dependencies found*\n"
            
        markdown += """
### Modules that depend on this:
"""
        
        if doc_data["dependents"]:
            for dep in doc_data["dependents"][:10]:  # Top 10 dependents
                markdown += f"- `{dep['module']}` ({dep['relation']})\n"
            if len(doc_data["dependents"]) > 10:
                markdown += f"- ... and {len(doc_data['dependents']) - 10} more dependents\n"
        else:
            markdown += "*No dependents found*\n"
        
        markdown += """
## 🎯 Key Components

### Classes ({len(doc_data['key_classes'])})
"""
        
        if doc_data["key_classes"]:
            for cls in doc_data["key_classes"]:
                markdown += f"#### `{cls['name']}`\n"
                markdown += f"{cls['description']}\n"
                markdown += f"- Methods: {cls['methods']:,}\n"
                markdown += f"- Properties: {cls['properties']:,}\n\n"
        else:
            markdown += "*No classes found*\n"
            
        markdown += f"""
### Functions ({len(doc_data['key_functions'])})
"""
        
        if doc_data["key_functions"]:
            for func in doc_data["key_functions"]:
                markdown += f"#### `{func['name']}`\n"
                markdown += f"{func['description']}\n"
                markdown += f"- Parameters: {func['parameters']:,}\n"
                if func['returns']:
                    markdown += f"- Returns: {func['returns']}\n"
                markdown += "\n"
        else:
            markdown += "*No functions found*\n"
        
        markdown += """
## 🔄 Usage Patterns
"""
        
        if doc_data["usage_patterns"]:
            for pattern in doc_data["usage_patterns"]:
                markdown += f"### {pattern['pattern']} ({pattern['count']} occurrences)\n"
                for example in pattern["examples"]:
                    markdown += f"- `{example['source']}` - {example['context'][:100]}{'...' if len(example['context']) > 100 else ''}\n"
                markdown += "\n"
        else:
            markdown += "*No usage patterns found*\n"
        
        if doc_data.get("test_coverage", {}).get("test_map_available"):
            markdown += f"""
## 🧪 Test Coverage

**Total Tests**: {doc_data['test_coverage']['total_tests']:,}  
**Test Files**: {doc_data['test_coverage']['test_files']:,}

### Example Tests:
"""
            
            for test in doc_data["test_coverage"]["tests"][:5]:
                markdown += f"- `{test['test_file']}` - {test['test_name']} ({test['test_type']})\n"
        
        if doc_data.get("examples"):
            markdown += """
## 💡 Examples
"""
            
            for example in doc_data["examples"]:
                markdown += f"### {example['title']}\n"
                markdown += f"{example['description']}\n\n"
                markdown += f"```python\n{example['code']}\n```\n\n"
        
        markdown += f"""
---

*This documentation was automatically generated from the Graphify knowledge graph.*  
*Module ID: `{module['id']}`*  
*Graph: {len(self.graph.get('nodes', [])) if self.graph else 0:,} nodes, {len(self.graph.get('edges', [])) if self.graph else 0:,} edges*
"""
        
        return markdown
    
    def _generate_module_index(self, modules: List[Dict[str, Any]]) -> str:
        """Generate index of all modules."""
        markdown = """# SIMP Module Documentation Index

*Generated: {datetime}*  
*Total Modules: {count}*

## 📋 Modules by Category

### 🏗️ Infrastructure
| Module | Files | Functions | Classes | Documentation |
|--------|-------|-----------|---------|---------------|
""".format(
    datetime=datetime.utcnow().isoformat() + "Z",
    count=len(modules)
)
        
        # Group modules by category
        infrastructure = []
        compatibility = []
        business = []
        presentation = []
        other = []
        
        for module in modules:
            module_id = module["module"]
            
            if "server" in module_id or "broker" in module_id:
                infrastructure.append(module)
            elif "compat" in module_id or "a2a" in module_id:
                compatibility.append(module)
            elif "organs" in module_id or "financial" in module_id or "trading" in module_id:
                business.append(module)
            elif "dashboard" in module_id or "ui" in module_id:
                presentation.append(module)
            else:
                other.append(module)
        
        # Add infrastructure modules
        for module in sorted(infrastructure, key=lambda x: x["module"]):
            stats = module["stats"]
            slug = module["module"].replace(".", "_").replace("/", "_")
            markdown += f"| `{module['module']}` | {stats['file_count']:,} | {stats['function_count']:,} | {stats['class_count']:,} | [{slug}.md]({slug}.md) |\n"
        
        markdown += """
### 🔄 Compatibility
| Module | Files | Functions | Classes | Documentation |
|--------|-------|-----------|---------|---------------|
"""
        
        for module in sorted(compatibility, key=lambda x: x["module"]):
            stats = module["stats"]
            slug = module["module"].replace(".", "_").replace("/", "_")
            markdown += f"| `{module['module']}` | {stats['file_count']:,} | {stats['function_count']:,} | {stats['class_count']:,} | [{slug}.md]({slug}.md) |\n"
        
        markdown += """
### 💰 Business/Revenue
| Module | Files | Functions | Classes | Documentation |
|--------|-------|-----------|---------|---------------|
"""
        
        for module in sorted(business, key=lambda x: x["module"]):
            stats = module["stats"]
            slug = module["module"].replace(".", "_").replace("/", "_")
            markdown += f"| `{module['module']}` | {stats['file_count']:,} | {stats['function_count']:,} | {stats['class_count']:,} | [{slug}.md]({slug}.md) |\n"
        
        markdown += """
### 🎨 Presentation
| Module | Files | Functions | Classes | Documentation |
|--------|-------|-----------|---------|---------------|
"""
        
        for module in sorted(presentation, key=lambda x: x["module"]):
            stats = module["stats"]
            slug = module["module"].replace(".", "_").replace("/", "_")
            markdown += f"| `{module['module']}` | {stats['file_count']:,} | {stats['function_count']:,} | {stats['class_count']:,} | [{slug}.md]({slug}.md) |\n"
        
        markdown += """
### 🛠️ Other Modules
| Module | Files | Functions | Classes | Documentation |
|--------|-------|-----------|---------|---------------|
"""
        
        for module in sorted(other, key=lambda x: x["module"]):
            stats = module["stats"]
            slug = module["module"].replace(".", "_").replace("/", "_")
            markdown += f"| `{module['module']}` | {stats['file_count']:,} | {stats['function_count']:,} | {stats['class_count']:,} | [{slug}.md]({slug}.md) |\n"
        
        markdown += f"""
## 📊 Statistics

**Total Modules**: {len(modules):,}  
**Total Files**: {sum(m['stats']['file_count'] for m in modules):,}  
**Total Functions**: {sum(m['stats']['function_count'] for m in modules):,}  
**Total Classes**: {sum(m['stats']['class_count'] for m in modules):,}

## 🚀 How to Use

1. **Browse modules** by category above
2. **Click on module name** to view detailed documentation
3. **Use search** in your editor to find specific modules
4. **Check dependencies** to understand relationships

---

*This index was automatically generated from the Graphify knowledge graph.*  
*Update frequency: Daily at 2 AM*
"""
        
        return markdown


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate documentation for SIMP modules from Graphify knowledge graph")
    parser.add_argument("--module", default="all", help="Module path to document (or 'all' for all modules)")
    parser.add_argument("--output-dir", default="docs/modules", help="Output directory for documentation")
    parser.add_argument("--no-tests", action="store_true", help="Exclude test coverage information")
    parser.add_argument("--no-examples", action="store_true", help="Exclude example code")
    parser.add_argument("--graph-dir", default=".graphify", help="Graphify data directory")
    
    args = parser.parse_args()
    
    print("📚 SIMP Module Documentation Generator")
    print("=" * 50)
    
    generator = ModuleDocumentationGenerator(graph_dir=args.graph_dir)
    result = generator.generate_module_docs(
        module_path=args.module,
        output_dir=args.output_dir,
        include_tests=not args.no_tests,
        include_examples=not args.no_examples,
    )
    
    if result:
        if args.module == "all":
            print(f"\n✅ Generated documentation for {result['total_modules']} modules!")
            print(f"📁 Output: {result['output_directory']}")
            print(f"📄 Files: {len(result['modules'])} markdown + JSON pairs")
        else:
            print(f"\n✅ Generated documentation for {args.module}!")
            print(f"📄 Markdown: {result['markdown_file']}")
            print(f"📊 JSON: {result['json_file']}")
    else:
        print("\n❌ Failed to generate documentation")
        sys.exit(1)


if __name__ == "__main__":
    main()