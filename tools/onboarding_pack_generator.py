#!/usr/bin/env python3
"""
Onboarding Pack Generator for SIMP
Creates personalized onboarding packs for new developers based on Graphify knowledge graph.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

class OnboardingPackGenerator:
    """Generates personalized onboarding packs for SIMP developers."""
    
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
    
    def generate_onboarding_pack(self, 
                                 developer_name: str,
                                 focus_area: str = "general",
                                 output_dir: str = "onboarding_packs") -> Dict[str, Any]:
        """Generate personalized onboarding pack."""
        if not self.load_data():
            return {}
            
        # Create output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pack_dir = Path(output_dir) / f"{developer_name.lower().replace(' ', '_')}_{timestamp}"
        pack_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎯 Generating onboarding pack for: {developer_name}")
        print(f"   Focus area: {focus_area}")
        print(f"   Output: {pack_dir}")
        
        # Generate pack components
        pack = {
            "developer": developer_name,
            "focus_area": focus_area,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "pack_directory": str(pack_dir),
            "components": {
                "welcome_guide": self._generate_welcome_guide(developer_name, focus_area),
                "quick_start": self._generate_quick_start(),
                "focus_modules": self._get_focus_modules(focus_area),
                "learning_path": self._generate_learning_path(focus_area),
                "key_files": self._get_key_files(focus_area),
                "common_tasks": self._get_common_tasks(focus_area),
                "troubleshooting": self._generate_troubleshooting(),
                "resources": self._get_resources(),
            }
        }
        
        # Generate all files
        self._generate_pack_files(pack_dir, pack)
        
        print(f"\n✅ Onboarding pack generated successfully!")
        print(f"📁 Location: {pack_dir}")
        
        return pack
    
    def _generate_welcome_guide(self, developer_name: str, focus_area: str) -> Dict[str, Any]:
        """Generate welcome guide."""
        return {
            "title": f"Welcome to SIMP, {developer_name}!",
            "subtitle": "Structured Intent Messaging Protocol",
            "tagline": "The HTTP of Agentic AI",
            "mission": "Build, test, and maintain SIMP subsystems autonomously",
            "focus_description": self._get_focus_description(focus_area),
            "system_stats": self._get_system_stats(),
        }
    
    def _get_focus_description(self, focus_area: str) -> str:
        """Get description for focus area."""
        focus_descriptions = {
            "general": "Full-stack SIMP development",
            "broker": "Core message routing and delivery",
            "a2a": "Agent-to-Agent compatibility layer",
            "financial": "FinancialOps simulation and payment systems",
            "trading": "QuantumArb and trading organs",
            "dashboard": "Operator console and visualization",
            "testing": "Test framework and coverage",
            "security": "Security audit and compliance",
            "documentation": "Documentation and guides",
        }
        
        return focus_descriptions.get(focus_area, "General SIMP development")
    
    def _get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        if not self.graph:
            return {}
            
        nodes = self.graph.get("nodes", [])
        edges = self.graph.get("edges", [])
        
        # Count by type
        file_count = len([n for n in nodes if n.get("type") == "file"])
        module_count = len([n for n in nodes if n.get("type") == "module"])
        class_count = len([n for n in nodes if n.get("type") == "class"])
        function_count = len([n for n in nodes if n.get("type") == "function"])
        
        return {
            "files": file_count,
            "modules": module_count,
            "classes": class_count,
            "functions": function_count,
            "edges": len(edges),
        }
    
    def _generate_quick_start(self) -> Dict[str, Any]:
        """Generate quick start guide."""
        return {
            "steps": [
                {
                    "title": "Environment Setup",
                    "commands": [
                        "cd /Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp",
                        "python3.10 --version  # Should be 3.10.x",
                    ]
                },
                {
                    "title": "Run Tests",
                    "commands": [
                        "SIMP_REQUIRE_API_KEY=false python3.10 -m pytest tests/ -v --tb=short",
                        "# Run specific test: python3.10 -m pytest tests/test_broker_delivery.py -v",
                    ]
                },
                {
                    "title": "Start Broker",
                    "commands": [
                        "python3.10 -m simp.server.broker",
                        "# Check health: curl -s http://127.0.0.1:5555/health",
                    ]
                },
                {
                    "title": "Open Dashboard",
                    "commands": [
                        "# Dashboard runs automatically with broker",
                        "open http://127.0.0.1:8050  # or visit in browser",
                    ]
                },
            ]
        }
    
    def _get_focus_modules(self, focus_area: str) -> List[Dict[str, Any]]:
        """Get modules relevant to focus area."""
        if not self.graph:
            return []
            
        nodes = self.graph.get("nodes", [])
        
        # Map focus areas to keywords
        focus_keywords = {
            "general": ["simp", "server", "compat", "organs"],
            "broker": ["broker", "server", "routing", "delivery", "ledger"],
            "a2a": ["compat", "a2a", "agent", "card", "task"],
            "financial": ["financial", "payment", "ops", "ledger", "gate"],
            "trading": ["quantumarb", "trading", "exchange", "arb", "organ"],
            "dashboard": ["dashboard", "ui", "static", "server"],
            "testing": ["test", "pytest", "fixture", "coverage"],
            "security": ["security", "audit", "auth", "policy"],
            "documentation": ["docs", "readme", "guide", "protocol"],
        }
        
        keywords = focus_keywords.get(focus_area, focus_keywords["general"])
        
        # Find relevant modules
        relevant_modules = []
        for node in nodes:
            if node.get("type") == "module":
                node_id = node.get("id", "").lower()
                node_name = node.get("name", "").lower()
                
                if any(keyword in node_id or keyword in node_name for keyword in keywords):
                    # Count connections
                    connections = len([e for e in self.graph.get("edges", []) 
                                      if e.get("source") == node.get("id") or e.get("target") == node.get("id")])
                    
                    relevant_modules.append({
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "description": node.get("description", ""),
                        "connections": connections,
                        "file_count": node.get("file_count", 0),
                        "function_count": node.get("function_count", 0),
                        "class_count": node.get("class_count", 0),
                        "relevance_score": self._calculate_relevance_score(node, keywords),
                    })
        
        # Sort by relevance and connections
        relevant_modules.sort(key=lambda x: (x["relevance_score"], x["connections"]), reverse=True)
        
        return relevant_modules[:15]  # Top 15 modules
    
    def _calculate_relevance_score(self, node: Dict[str, Any], keywords: List[str]) -> int:
        """Calculate relevance score for a node."""
        score = 0
        node_id = node.get("id", "").lower()
        node_name = node.get("name", "").lower()
        
        for keyword in keywords:
            if keyword in node_id:
                score += 3
            if keyword in node_name:
                score += 2
                
        return score
    
    def _generate_learning_path(self, focus_area: str) -> List[Dict[str, Any]]:
        """Generate learning path for focus area."""
        # Define learning paths for each focus area
        learning_paths = {
            "general": [
                {"day": 1, "topic": "SIMP Architecture", "duration": "2h", "resources": ["ARCHITECTURE_BRIEF.md"]},
                {"day": 2, "topic": "Broker & Routing", "duration": "3h", "resources": ["simp/server/broker.py", "simp/server/routing_engine.py"]},
                {"day": 3, "topic": "A2A Compatibility", "duration": "3h", "resources": ["simp/compat/"]},
                {"day": 4, "topic": "FinancialOps", "duration": "2h", "resources": ["simp/compat/financial_ops.py"]},
                {"day": 5, "topic": "QuantumArb Organ", "duration": "3h", "resources": ["simp/organs/quantumarb/"]},
                {"day": 6, "topic": "Testing Framework", "duration": "2h", "resources": ["tests/"]},
                {"day": 7, "topic": "First Contribution", "duration": "4h", "resources": ["Create a test or fix a bug"]},
            ],
            "broker": [
                {"day": 1, "topic": "Broker Architecture", "duration": "2h", "resources": ["simp/server/broker.py"]},
                {"day": 2, "topic": "Intent Delivery", "duration": "3h", "resources": ["simp/server/delivery.py"]},
                {"day": 3, "topic": "Routing Engine", "duration": "2h", "resources": ["simp/server/routing_engine.py"]},
                {"day": 4, "topic": "Intent Ledger", "duration": "2h", "resources": ["simp/server/intent_ledger.py"]},
                {"day": 5, "topic": "HTTP Server", "duration": "2h", "resources": ["simp/server/http_server.py"]},
                {"day": 6, "topic": "Broker Tests", "duration": "3h", "resources": ["tests/test_broker_*.py"]},
                {"day": 7, "topic": "Extend Broker", "duration": "4h", "resources": ["Add a new endpoint or feature"]},
            ],
            "trading": [
                {"day": 1, "topic": "QuantumArb Overview", "duration": "2h", "resources": ["simp/organs/quantumarb/"]},
                {"day": 2, "topic": "Arb Detector", "duration": "3h", "resources": ["simp/organs/quantumarb/arb_detector.py"]},
                {"day": 3, "topic": "Exchange Connectors", "duration": "3h", "resources": ["simp/organs/quantumarb/exchange_connector.py"]},
                {"day": 4, "topic": "Trading Safety", "duration": "2h", "resources": ["FinancialOps gates and limits"]},
                {"day": 5, "topic": "Testnet Execution", "duration": "3h", "resources": ["Test with simulated exchanges"]},
                {"day": 6, "topic": "P&L Tracking", "duration": "2h", "resources": ["P&L ledger implementation"]},
                {"day": 7, "topic": "Enhance Arb Logic", "duration": "4h", "resources": ["Improve detection or execution"]},
            ],
        }
        
        return learning_paths.get(focus_area, learning_paths["general"])
    
    def _get_key_files(self, focus_area: str) -> List[Dict[str, Any]]:
        """Get key files for focus area."""
        if not self.graph:
            return []
            
        nodes = self.graph.get("nodes", [])
        
        # Get files with highest centrality/connections
        file_nodes = [n for n in nodes if n.get("type") == "file"]
        
        # Score files based on connections
        scored_files = []
        for node in file_nodes:
            file_path = node.get("id", "")
            
            # Check if file matches focus area
            if self._file_matches_focus(file_path, focus_area):
                # Count connections
                connections = len([e for e in self.graph.get("edges", []) 
                                  if e.get("source") == node.get("id") or e.get("target") == node.get("id")])
                
                scored_files.append({
                    "path": file_path,
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "connections": connections,
                    "size": node.get("size", 0),
                    "lines": node.get("lines", 0),
                })
        
        # Sort by connections
        scored_files.sort(key=lambda x: x["connections"], reverse=True)
        
        return scored_files[:20]  # Top 20 files
    
    def _file_matches_focus(self, file_path: str, focus_area: str) -> bool:
        """Check if file matches focus area."""
        focus_patterns = {
            "general": True,  # All files
            "broker": lambda p: "server" in p and "broker" in p,
            "a2a": lambda p: "compat" in p,
            "financial": lambda p: "financial" in p or "payment" in p or "ops" in p,
            "trading": lambda p: "quantumarb" in p or "trading" in p,
            "dashboard": lambda p: "dashboard" in p,
            "testing": lambda p: "test" in p,
            "security": lambda p: "security" in p or "audit" in p,
            "documentation": lambda p: "docs" in p or "readme" in p or "guide" in p,
        }
        
        pattern = focus_patterns.get(focus_area, lambda p: True)
        return pattern(file_path.lower())
    
    def _get_common_tasks(self, focus_area: str) -> List[Dict[str, Any]]:
        """Get common tasks for focus area."""
        common_tasks = {
            "general": [
                {"task": "Add a new test", "difficulty": "easy", "time": "30m"},
                {"task": "Fix a failing test", "difficulty": "medium", "time": "1h"},
                {"task": "Add logging to a module", "difficulty": "easy", "time": "45m"},
                {"task": "Update documentation", "difficulty": "easy", "time": "1h"},
                {"task": "Add a new intent type", "difficulty": "medium", "time": "2h"},
            ],
            "broker": [
                {"task": "Add broker health endpoint", "difficulty": "easy", "time": "1h"},
                {"task": "Implement rate limiting", "difficulty": "medium", "time": "2h"},
                {"task": "Add intent validation", "difficulty": "medium", "time": "1.5h"},
                {"task": "Improve error handling", "difficulty": "medium", "time": "2h"},
                {"task": "Add broker metrics", "difficulty": "hard", "time": "3h"},
            ],
            "trading": [
                {"task": "Add new exchange connector", "difficulty": "medium", "time": "3h"},
                {"task": "Improve arb detection logic", "difficulty": "hard", "time": "4h"},
                {"task": "Add P&L tracking", "difficulty": "medium", "time": "2h"},
                {"task": "Implement safety limits", "difficulty": "medium", "time": "2h"},
                {"task": "Add trading tests", "difficulty": "easy", "time": "1.5h"},
            ],
            "a2a": [
                {"task": "Add new A2A capability", "difficulty": "medium", "time": "2h"},
                {"task": "Improve task translation", "difficulty": "hard", "time": "3h"},
                {"task": "Add agent discovery", "difficulty": "medium", "time": "2h"},
                {"task": "Implement event streaming", "difficulty": "hard", "time": "4h"},
                {"task": "Add A2A tests", "difficulty": "easy", "time": "1h"},
            ],
        }
        
        return common_tasks.get(focus_area, common_tasks["general"])
    
    def _generate_troubleshooting(self) -> Dict[str, Any]:
        """Generate troubleshooting guide."""
        return {
            "common_issues": [
                {
                    "issue": "Python 3.10 not found",
                    "solution": "Install Python 3.10: `brew install python@3.10` or use pyenv",
                    "command": "python3.10 --version"
                },
                {
                    "issue": "Tests failing with API key error",
                    "solution": "Set environment variable: `export SIMP_REQUIRE_API_KEY=false`",
                    "command": "SIMP_REQUIRE_API_KEY=false python3.10 -m pytest tests/ -v"
                },
                {
                    "issue": "Broker won't start",
                    "solution": "Check port 5555 is free: `lsof -i :5555`",
                    "command": "kill -9 $(lsof -ti:5555)  # If port is in use"
                },
                {
                    "issue": "Import errors",
                    "solution": "Add repo root to PYTHONPATH: `export PYTHONPATH=$PWD:$PYTHONPATH`",
                    "command": "cd /Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
                },
                {
                    "issue": "JSONL file permissions",
                    "solution": "Check write permissions in data/ directory",
                    "command": "ls -la data/ && chmod 664 data/*.jsonl"
                },
            ],
            "debug_commands": [
                "curl -s http://127.0.0.1:5555/health",
                "curl -s http://127.0.0.1:5555/agents",
                "python3.10 -m py_compile <file.py>  # Syntax check",
                "tail -n 20 data/task_ledger.jsonl  # Recent intents",
                "grep -r \"ERROR\|WARNING\" logs/  # Find errors",
            ]
        }
    
    def _get_resources(self) -> Dict[str, List[str]]:
        """Get learning resources."""
        return {
            "documentation": [
                "docs/ARCHITECTURE_BRIEF.md",
                "docs/FINANCIAL_OPS.md",
                "docs/A2A_DEMO.md",
                "docs/PROTOCOL_CONFORMANCE.md",
                "docs/SECURITY_CHECKLIST.md",
            ],
            "code_reviews": [
                "simp/server/broker.py  # Core broker",
                "simp/compat/agent_card.py  # A2A compatibility",
                "simp/organs/quantumarb/arb_detector.py  # Trading logic",
                "tests/test_protocol_conformance.py  # Test patterns",
            ],
            "tools": [
                "tools/change_impact_analyzer.py  # Impact analysis",
                "tools/test_selection_helper.py  # Test optimization",
                "tools/architecture_brief_generator.py  # Documentation",
                ".graphify/agent_helper.py  # Graph queries",
            ],
            "external": [
                "https://fastapi.tiangolo.com/  # FastAPI (dashboard)",
                "https://flask.palletsprojects.com/  # Flask (broker)",
                "https://docs.pytest.org/  # Testing framework",
            ]
        }
    
    def _generate_pack_files(self, pack_dir: Path, pack: Dict[str, Any]) -> None:
        """Generate all pack files."""
        # 1. Main README
        readme_content = self._generate_readme(pack)
        (pack_dir / "README.md").write_text(readme_content)
        
        # 2. Quick start guide
        quick_start_content = self._generate_quick_start_markdown(pack["components"]["quick_start"])
        (pack_dir / "QUICK_START.md").write_text(quick_start_content)
        
        # 3. Focus modules
        modules_content = self._generate_modules_markdown(pack["components"]["focus_modules"])
        (pack_dir / "FOCUS_MODULES.md").write_text(modules_content)
        
        # 4. Learning path
        learning_path_content = self._generate_learning_path_markdown(pack["components"]["learning_path"])
        (pack_dir / "LEARNING_PATH.md").write_text(learning_path_content)
        
        # 5. Key files
        key_files_content = self._generate_key_files_markdown(pack["components"]["key_files"])
        (pack_dir / "KEY_FILES.md").write_text(key_files_content)
        
        # 6. Common tasks
        tasks_content = self._generate_tasks_markdown(pack["components"]["common_tasks"])
        (pack_dir / "COMMON_TASKS.md").write_text(tasks_content)
        
        # 7. Troubleshooting
        troubleshooting_content = self._generate_troubleshooting_markdown(pack["components"]["troubleshooting"])
        (pack_dir / "TROUBLESHOOTING.md").write_text(troubleshooting_content)
        
        # 8. Resources
        resources_content = self._generate_resources_markdown(pack["components"]["resources"])
        (pack_dir / "RESOURCES.md").write_text(resources_content)
        
        # 9. Pack metadata
        metadata = {
            "developer": pack["developer"],
            "focus_area": pack["focus_area"],
            "generated_at": pack["generated_at"],
            "system_stats": pack["components"]["welcome_guide"]["system_stats"],
        }
        (pack_dir / "pack_metadata.json").write_text(json.dumps(metadata, indent=2))
        
        # 10. Copy architecture brief if exists
        arch_brief = Path("docs/architecture/ARCHITECTURE_BRIEF.md")
        if arch_brief.exists():
            shutil.copy(arch_brief, pack_dir / "ARCHITECTURE_BRIEF.md")
    
    def _generate_readme(self, pack: Dict[str, Any]) -> str:
        """Generate main README."""
        welcome = pack["components"]["welcome_guide"]
        
        return f"""# Welcome to SIMP, {pack['developer']}! 🎉

## 🎯 Your Onboarding Pack

**Focus Area**: {pack['focus_area']}  
**Generated**: {pack['generated_at']}  
**System**: {welcome['title']}

### 📋 What's in this pack:

1. **QUICK_START.md** - Get running in 15 minutes
2. **FOCUS_MODULES.md** - Key modules for your focus area
3. **LEARNING_PATH.md** - 7-day learning plan
4. **KEY_FILES.md** - Most important files to study
5. **COMMON_TASKS.md** - Practical tasks to start with
6. **TROUBLESHOOTING.md** - Solutions to common issues
7. **RESOURCES.md** - Documentation and tools
8. **ARCHITECTURE_BRIEF.md** - System overview

### 🚀 Quick Start

```bash
# 1. Navigate to SIMP directory
cd /Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp

# 2. Run tests to verify setup
SIMP_REQUIRE_API_KEY=false python3.10 -m pytest tests/ -v --tb=short

# 3. Start the broker
python3.10 -m simp.server.broker

# 4. Open dashboard
open http://127.0.0.1:8050
```

### 📊 System Stats

- **Files**: {welcome['system_stats']['files']:,}
- **Modules**: {welcome['system_stats']['modules']:,}
- **Classes**: {welcome['system_stats']['classes']:,}
- **Functions**: {welcome['system_stats']['functions']:,}
- **Connections**: {welcome['system_stats']['edges']:,}

### 🎯 Your Focus: {pack['focus_area']}

{welcome['focus_description']}

### 📁 Next Steps

1. Read **QUICK_START.md** to get running
2. Review **FOCUS_MODULES.md** for key components
3. Follow **LEARNING_PATH.md** for structured learning
4. Pick a task from **COMMON_TASKS.md** to start contributing

---

*This pack was automatically generated from the Graphify knowledge graph.*  
*Happy coding! 🚀*
"""
    
    def _generate_quick_start_markdown(self, quick_start: Dict[str, Any]) -> str:
        """Generate quick start markdown."""
        markdown = "# Quick Start Guide ⚡\n\n"
        markdown += "Get SIMP running in 15 minutes:\n\n"
        
        for step in quick_start["steps"]:
            markdown += f"## {step['title']}\n\n"
            for command in step["commands"]:
                markdown += f"```bash\n{command}\n```\n\n"
                
        return markdown
    
    def _generate_modules_markdown(self, modules: List[Dict[str, Any]]) -> str:
        """Generate focus modules markdown."""
        markdown = "# Focus Modules 🎯\n\n"
        markdown += "These are the most important modules for your focus area:\n\n"
        
        for i, module in enumerate(modules, 1):
            markdown += f"## {i}. `{module['id']}`\n\n"
            markdown += f"**Name**: {module['name']}\n\n"
            markdown += f"**Description**: {module['description']}\n\n"
            markdown += f"**Stats**:\n"
            markdown += f"- Files: {module['file_count']:,}\n"
            markdown += f"- Functions: {module['function_count']:,}\n"
            markdown += f"- Classes: {module['class_count']:,}\n"
            markdown += f"- Connections: {module['connections']:,}\n"
            markdown += f"- Relevance: {module['relevance_score']}/10\n\n"
            
        return markdown
    
    def _generate_learning_path_markdown(self, learning_path: List[Dict[str, Any]]) -> str:
        """Generate learning path markdown."""
        markdown = "# 7-Day Learning Path 📚\n\n"
        markdown += "Structured learning plan for your first week:\n\n"
        
        markdown += "| Day | Topic | Duration | Resources |\n"
        markdown += "|-----|-------|----------|-----------|\n"
        
        for day in learning_path:
            resources = ", ".join([f"`{r}`" for r in day["resources"]])
            markdown += f"| {day['day']} | {day['topic']} | {day['duration']} | {resources} |\n"
            
        markdown += "\n## Daily Breakdown\n\n"
        
        for day in learning_path:
            markdown += f"### Day {day['day']}: {day['topic']}\n\n"
            markdown += f"**Duration**: {day['duration']}\n\n"
            markdown += "**Resources**:\n"
            for resource in day["resources"]:
                markdown += f"- {resource}\n"
            markdown += "\n"
            
        return markdown
    
    def _generate_key_files_markdown(self, key_files: List[Dict[str, Any]]) -> str:
        """Generate key files markdown."""
        markdown = "# Key Files to Study 📄\n\n"
        markdown += "These files have the most connections and are central to the system:\n\n"
        
        for i, file in enumerate(key_files, 1):
            markdown += f"## {i}. `{file['path']}`\n\n"
            markdown += f"**Name**: {file['name']}\n\n"
            markdown += f"**Description**: {file['description']}\n\n"
            markdown += f"**Stats**:\n"
            markdown += f"- Connections: {file['connections']:,}\n"
            markdown += f"- Size: {file['size']:,} bytes\n"
            markdown += f"- Lines: {file['lines']:,}\n\n"
            
        return markdown
    
    def _generate_tasks_markdown(self, tasks: List[Dict[str, Any]]) -> str:
        """Generate common tasks markdown."""
        markdown = "# Common Tasks to Start With 🛠️\n\n"
        markdown += "Practical tasks to get hands-on experience:\n\n"
        
        markdown += "| Task | Difficulty | Estimated Time |\n"
        markdown += "|------|------------|----------------|\n"
        
        for task in tasks:
            markdown += f"| {task['task']} | {task['difficulty']} | {task['time']} |\n"
            
        markdown += "\n## Task Details\n\n"
        
        for task in tasks:
            markdown += f"### {task['task']}\n\n"
            markdown += f"**Difficulty**: {task['difficulty']}\n"
            markdown += f"**Time**: {task['time']}\n\n"
            
        return markdown
    
    def _generate_troubleshooting_markdown(self, troubleshooting: Dict[str, Any]) -> str:
        """Generate troubleshooting markdown."""
        markdown = "# Troubleshooting Guide 🔧\n\n"
        markdown += "Solutions to common issues:\n\n"
        
        markdown += "## Common Issues\n\n"
        for issue in troubleshooting["common_issues"]:
            markdown += f"### {issue['issue']}\n\n"
            markdown += f"**Solution**: {issue['solution']}\n\n"
            markdown += f"```bash\n{issue['command']}\n```\n\n"
            
        markdown += "## Debug Commands\n\n"
        for command in troubleshooting["debug_commands"]:
            markdown += f"```bash\n{command}\n```\n\n"
            
        return markdown
    
    def _generate_resources_markdown(self, resources: Dict[str, List[str]]) -> str:
        """Generate resources markdown."""
        markdown = "# Learning Resources 📚\n\n"
        
        for category, items in resources.items():
            markdown += f"## {category.title()}\n\n"
            for item in items:
                markdown += f"- {item}\n"
            markdown += "\n"
            
        return markdown


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate personalized onboarding pack for SIMP developers")
    parser.add_argument("--name", required=True, help="Developer name")
    parser.add_argument("--focus", default="general", 
                       choices=["general", "broker", "a2a", "financial", "trading", 
                               "dashboard", "testing", "security", "documentation"],
                       help="Focus area for onboarding")
    parser.add_argument("--output-dir", default="onboarding_packs", help="Output directory for packs")
    parser.add_argument("--graph-dir", default=".graphify", help="Graphify data directory")
    
    args = parser.parse_args()
    
    print("🎓 SIMP Onboarding Pack Generator")
    print("=" * 50)
    
    generator = OnboardingPackGenerator(graph_dir=args.graph_dir)
    pack = generator.generate_onboarding_pack(
        developer_name=args.name,
        focus_area=args.focus,
        output_dir=args.output_dir
    )
    
    if pack:
        print(f"\n✅ Onboarding pack generated for {args.name}!")
        print(f"📁 Location: {pack['pack_directory']}")
        print(f"🎯 Focus: {pack['focus_area']}")
        print(f"📊 Modules: {len(pack['components']['focus_modules'])} key modules identified")
        print(f"📄 Files: {len(pack['components']['key_files'])} key files identified")
        print(f"🛠️ Tasks: {len(pack['components']['common_tasks'])} common tasks suggested")
    else:
        print("\n❌ Failed to generate onboarding pack")
        sys.exit(1)


if __name__ == "__main__":
    main()