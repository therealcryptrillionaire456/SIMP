#!/usr/bin/env python3
"""
Learning Path Generator for SIMP
Creates personalized learning paths for new contributors.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

class LearningPathGenerator:
    """Generates personalized learning paths."""
    
    def __init__(self, repo_root: str = ".", graph_dir: str = ".graphify"):
        self.repo_root = Path(repo_root)
        self.graph_dir = Path(graph_dir)
        self.graph_path = self.graph_dir / "simp_graph.json"
        self.briefs_dir = self.repo_root / "briefs"
        
        # Load graph if available
        self.graph = None
        if self.graph_path.exists():
            with open(self.graph_path, 'r') as f:
                self.graph = json.load(f)
    
    def generate_learning_path(self, role: str, experience: str = "beginner", focus: str = "") -> Dict[str, Any]:
        """Generate personalized learning path."""
        print(f"🎓 Generating learning path for {role} ({experience})...")
        
        learning_path = {
            "role": role,
            "experience": experience,
            "focus": focus,
            "generated_at": datetime.now().isoformat(),
            "overview": self._get_role_overview(role),
            "learning_objectives": self._get_learning_objectives(role, experience),
            "modules": self._get_recommended_modules(role, focus),
            "resources": self._get_recommended_resources(role),
            "milestones": self._get_milestones(role, experience),
            "estimated_timeline": self._get_estimated_timeline(experience),
            "checkpoints": self._get_checkpoints(role)
        }
        
        return learning_path
    
    def _get_role_overview(self, role: str) -> str:
        """Get overview for role."""
        overviews = {
            "developer": "Learn SIMP architecture, contribute code, write tests, and understand the development workflow.",
            "agent": "Understand agent integration, learn SIMP rules, use agent tools, and contribute as an AI agent.",
            "operator": "Learn system operations, monitoring, troubleshooting, and maintaining SIMP infrastructure.",
            "contributor": "General contribution path covering code, documentation, testing, and community engagement."
        }
        return overviews.get(role, "Learn about SIMP system and contribute effectively.")
    
    def _get_learning_objectives(self, role: str, experience: str) -> List[str]:
        """Get learning objectives for role and experience."""
        objectives = {
            "developer": {
                "beginner": [
                    "Understand SIMP architecture basics",
                    "Set up development environment",
                    "Run existing tests",
                    "Make simple code changes",
                    "Create basic documentation"
                ],
                "intermediate": [
                    "Understand A2A compatibility layer",
                    "Contribute to core modules",
                    "Write comprehensive tests",
                    "Debug complex issues",
                    "Review pull requests"
                ],
                "advanced": [
                    "Design new features",
                    "Refactor complex modules",
                    "Optimize performance",
                    "Mentor other developers",
                    "Lead technical decisions"
                ]
            },
            "agent": {
                "beginner": [
                    "Understand agent rules and constraints",
                    "Use agent helper tools",
                    "Make simple code changes",
                    "Run agent workflows",
                    "Follow SIMP protocols"
                ],
                "intermediate": [
                    "Integrate with SIMP broker",
                    "Handle complex agent tasks",
                    "Use Graphify for analysis",
                    "Generate compliance-aware code",
                    "Collaborate with other agents"
                ],
                "advanced": [
                    "Design agent capabilities",
                    "Optimize agent performance",
                    "Handle edge cases",
                    "Train other agents",
                    "Lead agent development"
                ]
            }
        }
        
        role_obj = objectives.get(role, {})
        if not role_obj:
            # Default objectives for unknown roles
            return [
                "Understand SIMP architecture basics",
                "Set up development environment",
                "Make meaningful contributions",
                "Follow SIMP protocols and guidelines"
            ]
        return role_obj.get(experience, role_obj.get("beginner", []))
    
    def _get_recommended_modules(self, role: str, focus: str) -> List[Dict[str, Any]]:
        """Get recommended modules for role and focus."""
        modules = []
        
        # Base modules for all roles
        base_modules = [
            {"name": "simp/server", "priority": "high", "reason": "Core broker system"},
            {"name": "simp/compat", "priority": "high", "reason": "A2A compatibility layer"},
            {"name": "tests", "priority": "medium", "reason": "Test suite and examples"}
        ]
        
        # Role-specific modules
        role_modules = {
            "developer": [
                {"name": "dashboard", "priority": "medium", "reason": "Operator interface"},
                {"name": "tools", "priority": "medium", "reason": "Development utilities"},
                {"name": "docs", "priority": "low", "reason": "Documentation"}
            ],
            "agent": [
                {"name": "agents", "priority": "high", "reason": "Agent implementations"},
                {"name": "tools/agent_helper.py", "priority": "high", "reason": "Agent utilities"},
                {"name": ".graphify", "priority": "medium", "reason": "Knowledge graph"}
            ],
            "operator": [
                {"name": "dashboard", "priority": "high", "reason": "Monitoring interface"},
                {"name": "logs", "priority": "medium", "reason": "System logs"},
                {"name": "data", "priority": "medium", "reason": "System data"}
            ]
        }
        
        modules.extend(base_modules)
        modules.extend(role_modules.get(role, []))
        
        # Add focus-specific modules if provided
        if focus:
            focus_modules = self._get_focus_modules(focus)
            modules.extend(focus_modules)
        
        return modules
    
    def _get_focus_modules(self, focus: str) -> List[Dict[str, Any]]:
        """Get modules for specific focus area."""
        focus_map = {
            "security": [
                {"name": "simp/security", "priority": "high", "reason": "Security modules"},
                {"name": "pentagram_legal/security", "priority": "medium", "reason": "Security compliance"}
            ],
            "financial": [
                {"name": "simp/organs/quantumarb", "priority": "high", "reason": "Financial arbitrage"},
                {"name": "simp/compat/financial_ops.py", "priority": "high", "reason": "Financial operations"}
            ],
            "testing": [
                {"name": "tests", "priority": "high", "reason": "Test suite"},
                {"name": "tools/test_selection_helper.py", "priority": "high", "reason": "Test utilities"}
            ],
            "dashboard": [
                {"name": "dashboard", "priority": "high", "reason": "Dashboard code"},
                {"name": "dashboard/static", "priority": "medium", "reason": "Frontend assets"}
            ]
        }
        
        return focus_map.get(focus.lower(), [])
    
    def _get_recommended_resources(self, role: str) -> List[Dict[str, Any]]:
        """Get recommended resources for role."""
        resources = [
            {"type": "documentation", "name": "SPRINT_LOG.md", "description": "Development history and decisions"},
            {"type": "documentation", "name": "PROTOCOL_CONFORMANCE.md", "description": "SIMP protocol standards"},
            {"type": "tool", "name": "system_brief_generator.py", "description": "Generate architecture briefs"},
            {"type": "tool", "name": "change_impact_analyzer.py", "description": "Analyze code change impact"}
        ]
        
        role_resources = {
            "developer": [
                {"type": "guide", "name": "Developer onboarding pack", "description": "Role-specific guidance"},
                {"type": "tool", "name": "test_selection_helper.py", "description": "Select relevant tests"}
            ],
            "agent": [
                {"type": "guide", "name": "Agent onboarding pack", "description": "Agent rules and workflows"},
                {"type": "tool", "name": "agent_brief_integration.py", "description": "Agent context generation"}
            ],
            "operator": [
                {"type": "guide", "name": "Operator onboarding pack", "description": "Operational procedures"},
                {"type": "tool", "name": "dashboard/server.py", "description": "Dashboard interface"}
            ]
        }
        
        resources.extend(role_resources.get(role, []))
        return resources
    
    def _get_milestones(self, role: str, experience: str) -> List[Dict[str, Any]]:
        """Get learning milestones."""
        milestones = []
        
        if experience == "beginner":
            milestones = [
                {"week": 1, "goal": "Setup and first contribution", "success_criteria": ["Environment working", "First PR submitted"]},
                {"week": 2, "goal": "Understand core architecture", "success_criteria": ["Can explain SIMP components", "Navigate codebase"]},
                {"week": 3, "goal": "Make meaningful contributions", "success_criteria": ["Fix bugs", "Add tests", "Update docs"]},
                {"week": 4, "goal": "Become productive contributor", "success_criteria": ["Independent work", "Code reviews", "Mentor others"]}
            ]
        elif experience == "intermediate":
            milestones = [
                {"week": 1, "goal": "Deep dive into specialty", "success_criteria": ["Expert in focus area", "Can debug complex issues"]},
                {"week": 2, "goal": "Lead small features", "success_criteria": ["Design implementations", "Coordinate with team"]},
                {"week": 3, "goal": "Improve system quality", "success_criteria": ["Refactor code", "Add tests", "Optimize performance"]},
                {"week": 4, "goal": "Mentor and guide", "success_criteria": ["Help newcomers", "Share knowledge", "Improve processes"]}
            ]
        
        return milestones
    
    def _get_estimated_timeline(self, experience: str) -> Dict[str, Any]:
        """Get estimated timeline based on experience."""
        timelines = {
            "beginner": {
                "total_weeks": 4,
                "weekly_hours": 10,
                "phases": [
                    {"phase": "Onboarding", "weeks": 1, "focus": "Setup and basics"},
                    {"phase": "Learning", "weeks": 1, "focus": "Core concepts"},
                    {"phase": "Contributing", "weeks": 1, "focus": "Practical work"},
                    {"phase": "Proficiency", "weeks": 1, "focus": "Independent work"}
                ]
            },
            "intermediate": {
                "total_weeks": 4,
                "weekly_hours": 15,
                "phases": [
                    {"phase": "Specialization", "weeks": 1, "focus": "Deep dive"},
                    {"phase": "Leadership", "weeks": 1, "focus": "Feature ownership"},
                    {"phase": "Improvement", "weeks": 1, "focus": "Quality enhancement"},
                    {"phase": "Mentorship", "weeks": 1, "focus": "Team contribution"}
                ]
            },
            "advanced": {
                "total_weeks": 4,
                "weekly_hours": 20,
                "phases": [
                    {"phase": "Architecture", "weeks": 1, "focus": "System design"},
                    {"phase": "Innovation", "weeks": 1, "focus": "New features"},
                    {"phase": "Optimization", "weeks": 1, "focus": "Performance"},
                    {"phase": "Leadership", "weeks": 1, "focus": "Team direction"}
                ]
            }
        }
        
        return timelines.get(experience, timelines["beginner"])
    
    def _get_checkpoints(self, role: str) -> List[Dict[str, Any]]:
        """Get learning checkpoints."""
        checkpoints = [
            {"checkpoint": "Environment setup", "verification": "Run tests successfully", "resources": ["README.md", ".env.example"]},
            {"checkpoint": "First contribution", "verification": "PR merged", "resources": ["CONTRIBUTING.md", "SPRINT_LOG.md"]},
            {"checkpoint": "Architecture understanding", "verification": "Explain SIMP components", "resources": ["architecture briefs", ".graphify/"]},
            {"checkpoint": "Independent work", "verification": "Complete feature independently", "resources": ["tools/", "docs/"]}
        ]
        
        return checkpoints
    
    def export_learning_path(self, role: str, experience: str = "beginner", focus: str = "", 
                           output_dir: str = "learning_paths") -> str:
        """Export learning path to file."""
        learning_path = self.generate_learning_path(role, experience, focus)
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"learning_path_{role}_{experience}_{timestamp}.json"
        if focus:
            filename = f"learning_path_{role}_{experience}_{focus}_{timestamp}.json"
        
        file_path = output_path / filename
        
        with open(file_path, 'w') as f:
            json.dump(learning_path, f, indent=2)
        
        # Also create Markdown version
        md_path = file_path.with_suffix(".md")
        self._export_learning_path_markdown(md_path, learning_path)
        
        print(f"✅ Learning path exported to {file_path}")
        print(f"📝 Markdown version: {md_path}")
        
        return str(file_path)
    
    def _export_learning_path_markdown(self, file_path: Path, learning_path: Dict[str, Any]) -> None:
        """Export learning path as Markdown."""
        with open(file_path, 'w') as f:
            f.write(f"# SIMP Learning Path: {learning_path['role'].title()} ({learning_path['experience'].title()})\n\n")
            
            if learning_path['focus']:
                f.write(f"**Focus Area**: {learning_path['focus'].title()}\n\n")
            
            f.write(f"*Generated: {learning_path['generated_at']}*\n\n")
            
            # Overview
            f.write("## 🎯 Overview\n\n")
            f.write(f"{learning_path['overview']}\n\n")
            
            # Learning Objectives
            f.write("## 📚 Learning Objectives\n\n")
            for i, objective in enumerate(learning_path['learning_objectives'], 1):
                f.write(f"{i}. {objective}\n")
            f.write("\n")
            
            # Recommended Modules
            f.write("## 🏗️ Recommended Modules\n\n")
            for module in learning_path['modules']:
                priority_emoji = "🔴" if module['priority'] == "high" else "🟡" if module['priority'] == "medium" else "🟢"
                f.write(f"{priority_emoji} **{module['name']}** - {module['reason']}\n")
            f.write("\n")
            
            # Resources
            f.write("## 📖 Resources\n\n")
            for resource in learning_path['resources']:
                f.write(f"- **{resource['type'].title()}**: {resource['name']} - {resource['description']}\n")
            f.write("\n")
            
            # Timeline
            f.write("## ⏱️ Estimated Timeline\n\n")
            timeline = learning_path['estimated_timeline']
            f.write(f"- **Total weeks**: {timeline['total_weeks']}\n")
            f.write(f"- **Weekly hours**: {timeline['weekly_hours']}\n\n")
            
            f.write("### Phases:\n")
            for phase in timeline['phases']:
                f.write(f"- **{phase['phase']}** ({phase['weeks']} week{'s' if phase['weeks'] > 1 else ''}): {phase['focus']}\n")
            f.write("\n")
            
            # Milestones
            f.write("## 🎯 Milestones\n\n")
            for milestone in learning_path['milestones']:
                f.write(f"### Week {milestone['week']}: {milestone['goal']}\n")
                f.write("Success criteria:\n")
                for criteria in milestone['success_criteria']:
                    f.write(f"- {criteria}\n")
                f.write("\n")
            
            # Checkpoints
            f.write("## ✅ Checkpoints\n\n")
            for checkpoint in learning_path['checkpoints']:
                f.write(f"### {checkpoint['checkpoint']}\n")
                f.write(f"**Verification**: {checkpoint['verification']}\n")
                f.write("**Resources**:\n")
                for resource in checkpoint['resources']:
                    f.write(f"- {resource}\n")
                f.write("\n")
            
            f.write("---\n")
            f.write("*Generated by SIMP Learning Path Generator*\n")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SIMP Learning Path Generator")
    parser.add_argument("--role", choices=["developer", "agent", "operator", "contributor"], 
                       default="developer", help="Role for learning path")
    parser.add_argument("--experience", choices=["beginner", "intermediate", "advanced"], 
                       default="beginner", help="Experience level")
    parser.add_argument("--focus", help="Focus area (security, financial, testing, dashboard)")
    parser.add_argument("--export", action="store_true", help="Export learning path to file")
    parser.add_argument("--output-dir", default="learning_paths", help="Output directory")
    
    args = parser.parse_args()
    
    generator = LearningPathGenerator()
    
    try:
        if args.export:
            print(f"📤 Exporting learning path for {args.role} ({args.experience})...")
            if args.focus:
                print(f"   Focus area: {args.focus}")
            
            file_path = generator.export_learning_path(
                args.role, args.experience, args.focus, args.output_dir
            )
            print(f"✅ Exported to {file_path}")
        
        else:
            # Generate and display
            print(f"🎓 Generating learning path for {args.role} ({args.experience})...")
            if args.focus:
                print(f"   Focus area: {args.focus}")
            
            learning_path = generator.generate_learning_path(
                args.role, args.experience, args.focus
            )
            
            print("\n" + "="*60)
            print(f"📚 LEARNING PATH: {learning_path['role'].upper()} ({learning_path['experience'].upper()})")
            if learning_path['focus']:
                print(f"🎯 FOCUS: {learning_path['focus'].upper()}")
            print("="*60)
            
            print(f"\n🎯 Overview: {learning_path['overview']}")
            
            print("\n📚 Learning Objectives:")
            for i, objective in enumerate(learning_path['learning_objectives'], 1):
                print(f"  {i}. {objective}")
            
            print("\n🏗️ Recommended Modules:")
            for module in learning_path['modules'][:5]:  # Show top 5
                priority_emoji = "🔴" if module['priority'] == "high" else "🟡" if module['priority'] == "medium" else "🟢"
                print(f"  {priority_emoji} {module['name']}: {module['reason']}")
            
            timeline = learning_path['estimated_timeline']
            print(f"\n⏱️ Timeline: {timeline['total_weeks']} weeks, {timeline['weekly_hours']} hours/week")
            
            print("\n💡 Tip: Use --export to save full learning path with resources, milestones, and checkpoints.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
