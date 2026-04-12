#!/usr/bin/env python3
"""
Architecture Brief Generator for SIMP
Automatically generates comprehensive architecture briefs from Graphify knowledge graph.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

class ArchitectureBriefGenerator:
    """Generates architecture briefs from Graphify knowledge graph."""
    
    def __init__(self, graph_dir: str = ".graphify"):
        """Initialize with Graphify data directory."""
        self.graph_dir = Path(graph_dir)
        self.graph = None
        self.analysis = None
        self.test_map = None
        
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
                    
            # Load test map
            test_map_path = self.graph_dir / "test_map.json"
            if test_map_path.exists():
                with open(test_map_path, 'r') as f:
                    self.test_map = json.load(f)
                    
            print(f"✅ Loaded: {len(self.graph.get('nodes', []))} nodes, {len(self.graph.get('edges', []))} edges")
            return True
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return False
    
    def generate_architecture_brief(self, output_dir: str = "docs/architecture") -> Dict[str, Any]:
        """Generate comprehensive architecture brief."""
        if not self.load_data():
            return {}
            
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Collect all data for the brief
        brief = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "graph_stats": self._get_graph_statistics(),
            "module_hierarchy": self._get_module_hierarchy(),
            "key_modules": self._get_key_modules(),
            "system_overview": self._get_system_overview(),
            "agent_ecosystem": self._get_agent_ecosystem(),
            "revenue_organs": self._get_revenue_organs(),
            "test_coverage": self._get_test_coverage(),
            "architecture_patterns": self._get_architecture_patterns(),
            "development_workflow": self._get_development_workflow(),
            "onboarding_checklist": self._get_onboarding_checklist(),
        }
        
        # Generate markdown brief
        markdown = self._generate_markdown_brief(brief)
        
        # Save files
        markdown_path = output_path / "ARCHITECTURE_BRIEF.md"
        json_path = output_path / "architecture_brief.json"
        
        with open(markdown_path, 'w') as f:
            f.write(markdown)
            
        with open(json_path, 'w') as f:
            json.dump(brief, f, indent=2)
            
        print(f"✅ Generated architecture brief:")
        print(f"   📄 {markdown_path}")
        print(f"   📊 {json_path}")
        
        return brief
    
    def _get_graph_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        if not self.graph:
            return {}
            
        nodes = self.graph.get("nodes", [])
        edges = self.graph.get("edges", [])
        
        # Count by type
        node_types = {}
        for node in nodes:
            node_type = node.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
            
        # Count by module
        modules = {}
        for node in nodes:
            module = node.get("module", "unknown")
            modules[module] = modules.get(module, 0) + 1
            
        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": node_types,
            "top_modules": dict(sorted(modules.items(), key=lambda x: x[1], reverse=True)[:10]),
        }
    
    def _get_module_hierarchy(self) -> Dict[str, Any]:
        """Extract module hierarchy from graph."""
        if not self.graph:
            return {}
            
        hierarchy = {}
        nodes = self.graph.get("nodes", [])
        
        for node in nodes:
            if node.get("type") == "module":
                module_path = node.get("id", "")
                parts = module_path.split(".")
                
                # Build hierarchy
                current = hierarchy
                for part in parts:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                    
                # Add module info
                current["_info"] = {
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "file_count": node.get("file_count", 0),
                    "function_count": node.get("function_count", 0),
                    "class_count": node.get("class_count", 0),
                }
                
        return hierarchy
    
    def _get_key_modules(self) -> List[Dict[str, Any]]:
        """Identify key modules based on centrality and connections."""
        if not self.graph or not self.analysis:
            return []
            
        nodes = self.graph.get("nodes", [])
        
        # Get centrality from analysis if available
        centrality = {}
        if self.analysis and "centrality" in self.analysis:
            centrality = self.analysis["centrality"]
            
        # Find modules with most connections
        module_connections = {}
        for node in nodes:
            if node.get("type") == "module":
                module_id = node.get("id", "")
                # Count connections from edges
                connections = 0
                for edge in self.graph.get("edges", []):
                    if edge.get("source") == module_id or edge.get("target") == module_id:
                        connections += 1
                module_connections[module_id] = connections
                
        # Sort by connections
        sorted_modules = sorted(module_connections.items(), key=lambda x: x[1], reverse=True)[:20]
        
        key_modules = []
        for module_id, connections in sorted_modules:
            # Find node info
            node_info = next((n for n in nodes if n.get("id") == module_id), {})
            
            key_modules.append({
                "id": module_id,
                "name": node_info.get("name", ""),
                "description": node_info.get("description", ""),
                "connections": connections,
                "centrality": centrality.get(module_id, 0),
                "file_count": node_info.get("file_count", 0),
                "function_count": node_info.get("function_count", 0),
                "class_count": node_info.get("class_count", 0),
            })
            
        return key_modules
    
    def _get_system_overview(self) -> Dict[str, Any]:
        """Generate system overview."""
        return {
            "name": "SIMP (Structured Intent Messaging Protocol)",
            "description": "The HTTP of Agentic AI - broker-based protocol for typed intent routing between agents",
            "version": "0.7.0",
            "core_components": [
                "Broker (port 5555) - Central message bus",
                "Dashboard (port 8050) - Operator console",
                "A2A Compatibility Layer - External agent interop",
                "FinancialOps - Simulated payment system",
                "ProjectX (port 8771) - Native maintenance kernel",
                "BullBear - Universal prediction engine",
                "QuantumArb - Arbitrage detection & execution",
            ],
            "architecture_style": "Microservices with central broker",
            "communication": "HTTP/REST with typed intents",
            "data_persistence": "JSONL append-only ledgers",
            "security": "API keys, rate limiting, audit logging",
        }
    
    def _get_agent_ecosystem(self) -> List[Dict[str, Any]]:
        """Get information about registered agents."""
        # This would ideally come from the broker, but we'll extract from graph
        agents = []
        
        # Look for agent-related modules
        agent_nodes = [n for n in self.graph.get("nodes", []) 
                      if "agent" in n.get("id", "").lower() or "agent" in n.get("name", "").lower()]
        
        for node in agent_nodes[:15]:  # Top 15
            agents.append({
                "name": node.get("name", ""),
                "id": node.get("id", ""),
                "description": node.get("description", ""),
                "type": node.get("type", ""),
                "connections": len([e for e in self.graph.get("edges", []) 
                                   if e.get("source") == node.get("id") or e.get("target") == node.get("id")]),
            })
            
        return agents
    
    def _get_revenue_organs(self) -> List[Dict[str, Any]]:
        """Get information about revenue-generating organs."""
        revenue_keywords = ["quantumarb", "trading", "financial", "payment", "revenue", "profit", "arbitrage"]
        
        revenue_modules = []
        for node in self.graph.get("nodes", []):
            node_id = node.get("id", "").lower()
            node_name = node.get("name", "").lower()
            
            if any(keyword in node_id or keyword in node_name for keyword in revenue_keywords):
                revenue_modules.append({
                    "name": node.get("name", ""),
                    "id": node.get("id", ""),
                    "description": node.get("description", ""),
                    "type": node.get("type", ""),
                    "status": "active" if "quantumarb" in node_id else "planned",
                })
                
        return revenue_modules
    
    def _get_test_coverage(self) -> Dict[str, Any]:
        """Get test coverage information."""
        if not self.test_map:
            return {"total_tests": 0, "test_map_available": False}
            
        return {
            "total_tests": len(self.test_map.get("tests", [])),
            "modules_with_tests": len(self.test_map.get("module_test_map", {})),
            "test_map_available": True,
            "test_distribution": self._get_test_distribution(),
        }
    
    def _get_test_distribution(self) -> Dict[str, int]:
        """Get distribution of tests by module."""
        if not self.test_map:
            return {}
            
        distribution = {}
        for test in self.test_map.get("tests", []):
            module = test.get("module", "unknown")
            distribution[module] = distribution.get(module, 0) + 1
            
        return dict(sorted(distribution.items(), key=lambda x: x[1], reverse=True)[:10])
    
    def _get_architecture_patterns(self) -> List[Dict[str, Any]]:
        """Identify common architecture patterns."""
        patterns = [
            {
                "name": "Broker Pattern",
                "description": "Central message bus routing typed intents between agents",
                "components": ["SimpBroker", "IntentDeliveryEngine", "RoutingEngine"],
                "location": "simp/server/",
            },
            {
                "name": "Adapter Pattern",
                "description": "A2A compatibility layer translating between SIMP and external protocols",
                "components": ["AgentCardGenerator", "TaskMap", "CapabilityMap"],
                "location": "simp/compat/",
            },
            {
                "name": "Ledger Pattern",
                "description": "Append-only JSONL persistence for audit trail",
                "components": ["IntentLedger", "LiveSpendLedger", "SecurityAuditLog"],
                "location": "data/*.jsonl files",
            },
            {
                "name": "Gate Pattern",
                "description": "Progressive promotion through safety gates",
                "components": ["GateManager", "ApprovalQueue", "BudgetMonitor"],
                "location": "simp/compat/gate_manager.py",
            },
            {
                "name": "Organ Pattern",
                "description": "Revenue-generating modules as independent organs",
                "components": ["QuantumArb", "SpotTradingOrgan", "KashClaw organs"],
                "location": "simp/organs/",
            },
        ]
        
        return patterns
    
    def _get_development_workflow(self) -> Dict[str, Any]:
        """Describe development workflow."""
        return {
            "branch": "feat/public-readonly-dashboard",
            "python_version": "3.10",
            "test_command": "SIMP_REQUIRE_API_KEY=false python3.10 -m pytest tests/ -v --tb=short",
            "compile_check": "python3.10 -m py_compile <file.py>",
            "broker_check": "curl -s http://127.0.0.1:5555/health",
            "commit_format": "feat: <area> — <short description>",
            "protected_files": [
                "simp/server/broker.py",
                "simp/server/http_server.py", 
                "simp/models/canonical_intent.py",
                "config/config.py",
            ],
            "jsonl_ledgers": [
                "data/task_ledger.jsonl",
                "data/financial_ops_proposals.jsonl",
                "data/live_spend_ledger.jsonl",
                "data/gate_log.jsonl",
            ],
        }
    
    def _get_onboarding_checklist(self) -> List[Dict[str, Any]]:
        """Generate onboarding checklist."""
        return [
            {"task": "Read ARCHITECTURE_BRIEF.md", "priority": "high", "estimated_time": "15m"},
            {"task": "Set up Python 3.10 environment", "priority": "high", "estimated_time": "30m"},
            {"task": "Run test suite to verify setup", "priority": "high", "estimated_time": "10m"},
            {"task": "Start broker: python3.10 -m simp.server.broker", "priority": "high", "estimated_time": "5m"},
            {"task": "Explore dashboard at http://127.0.0.1:8050", "priority": "medium", "estimated_time": "20m"},
            {"task": "Review A2A compatibility layer", "priority": "medium", "estimated_time": "30m"},
            {"task": "Study FinancialOps simulation", "priority": "medium", "estimated_time": "45m"},
            {"task": "Examine QuantumArb organ", "priority": "low", "estimated_time": "60m"},
            {"task": "Create first test for a module", "priority": "low", "estimated_time": "45m"},
        ]
    
    def _generate_markdown_brief(self, brief: Dict[str, Any]) -> str:
        """Generate markdown format brief."""
        markdown = f"""# SIMP Architecture Brief

*Generated: {brief['generated_at']}*

## 📊 System Overview

**Name**: {brief['system_overview']['name']}  
**Version**: {brief['system_overview']['version']}  
**Description**: {brief['system_overview']['description']}

### Core Components:
"""
        
        for component in brief['system_overview']['core_components']:
            markdown += f"- {component}\n"
            
        markdown += f"""
### Architecture:
- **Style**: {brief['system_overview']['architecture_style']}
- **Communication**: {brief['system_overview']['communication']}
- **Data Persistence**: {brief['system_overview']['data_persistence']}
- **Security**: {brief['system_overview']['security']}

## 📈 Graph Statistics

**Total Nodes**: {brief['graph_stats']['total_nodes']:,}  
**Total Edges**: {brief['graph_stats']['total_edges']:,}

### Node Types:
"""
        
        for node_type, count in brief['graph_stats']['node_types'].items():
            markdown += f"- **{node_type}**: {count:,}\n"
            
        markdown += f"""
### Top Modules by File Count:
"""
        
        for module, count in brief['graph_stats']['top_modules'].items():
            markdown += f"- `{module}`: {count:,} files\n"
            
        markdown += """
## 🎯 Key Modules (Most Connected)

These modules form the core of the SIMP system:
"""
        
        for i, module in enumerate(brief['key_modules'][:10], 1):
            markdown += f"""
### {i}. `{module['id']}`
- **Name**: {module['name']}
- **Connections**: {module['connections']:,}
- **Files**: {module['file_count']:,}
- **Functions**: {module['function_count']:,}
- **Classes**: {module['class_count']:,}
- **Description**: {module['description'][:200]}{'...' if len(module['description']) > 200 else ''}
"""
            
        markdown += """
## 🤖 Agent Ecosystem

Registered agents in the SIMP system:
"""
        
        for agent in brief['agent_ecosystem'][:10]:
            markdown += f"- **{agent['name']}** ({agent['type']}): {agent['description'][:100]}{'...' if len(agent['description']) > 100 else ''} ({agent['connections']} connections)\n"
            
        markdown += """
## 💰 Revenue Organs

Revenue-generating components:
"""
        
        for organ in brief['revenue_organs']:
            markdown += f"- **{organ['name']}** ({organ['status']}): {organ['description'][:150]}{'...' if len(organ['description']) > 150 else ''}\n"
            
        markdown += f"""
## 🧪 Test Coverage

**Total Tests**: {brief['test_coverage']['total_tests']:,}  
**Modules with Tests**: {brief['test_coverage']['modules_with_tests']:,}

### Test Distribution:
"""
        
        if brief['test_coverage'].get('test_distribution'):
            for module, count in brief['test_coverage']['test_distribution'].items():
                markdown += f"- `{module}`: {count:,} tests\n"
                
        markdown += """
## 🏗️ Architecture Patterns

### 1. Broker Pattern
**Description**: {brief['architecture_patterns'][0]['description']}  
**Components**: {', '.join(brief['architecture_patterns'][0]['components'])}  
**Location**: {brief['architecture_patterns'][0]['location']}

### 2. Adapter Pattern  
**Description**: {brief['architecture_patterns'][1]['description']}  
**Components**: {', '.join(brief['architecture_patterns'][1]['components'])}  
**Location**: {brief['architecture_patterns'][1]['location']}

### 3. Ledger Pattern
**Description**: {brief['architecture_patterns'][2]['description']}  
**Location**: {brief['architecture_patterns'][2]['location']}

### 4. Gate Pattern
**Description**: {brief['architecture_patterns'][3]['description']}  
**Components**: {', '.join(brief['architecture_patterns'][3]['components'])}  
**Location**: {brief['architecture_patterns'][3]['location']}

### 5. Organ Pattern
**Description**: {brief['architecture_patterns'][4]['description']}  
**Components**: {', '.join(brief['architecture_patterns'][4]['components'])}  
**Location**: {brief['architecture_patterns'][4]['location']}

## 🛠️ Development Workflow

**Branch**: `{brief['development_workflow']['branch']}`  
**Python**: {brief['development_workflow']['python_version']}

### Commands:
- **Test**: `{brief['development_workflow']['test_command']}`
- **Compile Check**: `{brief['development_workflow']['compile_check']}`
- **Broker Health**: `{brief['development_workflow']['broker_check']}`

### Commit Format:
```
{brief['development_workflow']['commit_format']}
```

### Protected Files (Never modify without explicit instruction):
"""
        
        for file in brief['development_workflow']['protected_files']:
            markdown += f"- `{file}`\n"
            
        markdown += """
### JSONL Ledgers (Append-only, never delete):
"""
        
        for ledger in brief['development_workflow']['jsonl_ledgers']:
            markdown += f"- `{ledger}`\n"
            
        markdown += """
## 🚀 Onboarding Checklist

| Task | Priority | Estimated Time |
|------|----------|----------------|
"""
        
        for item in brief['onboarding_checklist']:
            markdown += f"| {item['task']} | {item['priority']} | {item['estimated_time']} |\n"
            
        markdown += f"""
## 📁 Module Hierarchy (Simplified)

```
{brief['module_hierarchy']}
```

---

*This brief was automatically generated from the Graphify knowledge graph.*  
*Update frequency: Daily at 2 AM*  
*Graph stats: {brief['graph_stats']['total_nodes']:,} nodes, {brief['graph_stats']['total_edges']:,} edges*
"""
        
        return markdown


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate SIMP architecture brief from Graphify knowledge graph")
    parser.add_argument("--output-dir", default="docs/architecture", help="Output directory for brief files")
    parser.add_argument("--graph-dir", default=".graphify", help="Graphify data directory")
    
    args = parser.parse_args()
    
    print("🏗️  SIMP Architecture Brief Generator")
    print("=" * 50)
    
    generator = ArchitectureBriefGenerator(graph_dir=args.graph_dir)
    brief = generator.generate_architecture_brief(output_dir=args.output_dir)
    
    if brief:
        print("\n✅ Architecture brief generated successfully!")
        print(f"📊 Graph: {brief['graph_stats']['total_nodes']:,} nodes, {brief['graph_stats']['total_edges']:,} edges")
        print(f"🎯 Key modules: {len(brief['key_modules'])} identified")
        print(f"🤖 Agents: {len(brief['agent_ecosystem'])} in ecosystem")
        print(f"💰 Revenue organs: {len(brief['revenue_organs'])} identified")
    else:
        print("\n❌ Failed to generate architecture brief")
        sys.exit(1)


if __name__ == "__main__":
    main()