#!/usr/bin/env python3
"""
Agent Integration Example for System Brief Generator
Shows how agents can use the brief generator in their workflows.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

class AgentBriefIntegration:
    """Example integration for agents using system briefs."""
    
    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
        self.briefs_dir = self.repo_root / "briefs"
        self.onboarding_dir = self.repo_root / "onboarding"
        
    def get_latest_brief(self) -> Optional[Dict[str, Any]]:
        """Get the latest architecture brief."""
        latest_json = self.briefs_dir / "latest_architecture_brief.json"
        if latest_json.exists() and latest_json.is_symlink():
            actual_path = latest_json.resolve()
            with open(actual_path, 'r') as f:
                return json.load(f)
        
        # Fallback: find most recent brief
        brief_files = list(self.briefs_dir.glob("architecture_brief_*.json"))
        if not brief_files:
            return None
        
        latest_file = max(brief_files, key=lambda p: p.stat().st_mtime)
        with open(latest_file, 'r') as f:
            return json.load(f)
    
    def get_onboarding_pack(self, role: str = "agent") -> Optional[Dict[str, Any]]:
        """Get onboarding pack for a specific role."""
        symlink_name = f"latest_{role}_guide.md"
        symlink_path = self.onboarding_dir / symlink_name
        
        if symlink_path.exists() and symlink_path.is_symlink():
            # Get the JSON version
            actual_md = symlink_path.resolve()
            json_path = actual_md.with_suffix(".json")
            if json_path.exists():
                with open(json_path, 'r') as f:
                    return json.load(f)
        
        # Fallback: find most recent
        pack_files = list(self.onboarding_dir.glob(f"onboarding_{role}_*.json"))
        if not pack_files:
            return None
        
        latest_file = max(pack_files, key=lambda p: p.stat().st_mtime)
        with open(latest_file, 'r') as f:
            return json.load(f)
    
    def analyze_change_with_brief(self, changed_files: List[str]) -> Dict[str, Any]:
        """
        Analyze code changes using architecture brief.
        Example agent workflow.
        """
        brief = self.get_latest_brief()
        if not brief:
            return {"error": "No architecture brief found"}
        
        analysis = {
            "changed_files": changed_files,
            "impact_analysis": [],
            "test_recommendations": [],
            "review_guidance": []
        }
        
        # Get module overview from brief
        modules = brief.get("modules", {})
        
        # For each changed file, find affected modules
        for file_path in changed_files:
            # Simple heuristic: find module containing this file
            affected_module = None
            for module_name, module_data in modules.items():
                # Check if file is in this module's path
                if module_name.lower() in file_path.lower():
                    affected_module = module_name
                    break
            
            if affected_module:
                module_info = modules[affected_module]
                analysis["impact_analysis"].append({
                    "file": file_path,
                    "module": affected_module,
                    "centrality": module_info.get("centrality", 0),
                    "dependencies": module_info.get("dependencies", []),
                    "dependents": module_info.get("dependents", []),
                    "risk_level": "HIGH" if module_info.get("centrality", 0) > 0.2 else "MEDIUM" if module_info.get("centrality", 0) > 0.1 else "LOW"
                })
        
        # Get recommendations from brief
        recommendations = brief.get("recommendations", [])
        relevant_recs = []
        for rec in recommendations:
            rec_module = rec.get("module") or (rec.get("modules", [""])[0] if rec.get("modules") else "")
            for impact in analysis["impact_analysis"]:
                if rec_module == impact["module"]:
                    relevant_recs.append(rec)
                    break
        
        analysis["review_guidance"] = relevant_recs
        
        # Generate test recommendations based on module dependencies
        for impact in analysis["impact_analysis"]:
            module = impact["module"]
            # In a real implementation, this would query the test map
            analysis["test_recommendations"].append({
                "module": module,
                "suggested_tests": f"tests/test_{module.lower().replace('.', '_')}*.py",
                "priority": "HIGH" if impact["risk_level"] == "HIGH" else "MEDIUM"
            })
        
        return analysis
    
    def generate_agent_context(self) -> Dict[str, Any]:
        """Generate context for agent prompts."""
        brief = self.get_latest_brief()
        agent_pack = self.get_onboarding_pack("agent")
        
        context = {
            "system_overview": {},
            "agent_guidelines": [],
            "current_state": {},
            "recommended_actions": []
        }
        
        if brief:
            summary = brief.get("summary", {})
            context["system_overview"] = {
                "total_files": summary.get("total_files", 0),
                "total_modules": summary.get("total_modules", 0),
                "most_central_modules": summary.get("most_central_modules", [])[:3]
            }
            
            # Add recommendations
            for rec in brief.get("recommendations", [])[:3]:
                context["recommended_actions"].append({
                    "type": rec.get("type", ""),
                    "description": rec.get("suggestion", ""),
                    "priority": "HIGH" if "high_priority" in rec.get("type", "") else "MEDIUM"
                })
        
        if agent_pack:
            context["agent_guidelines"] = agent_pack.get("agent_rules", [])
            context["current_state"] = {
                "broker_endpoint": agent_pack.get("agent_integration", {}).get("broker_endpoint", "http://localhost:5555"),
                "dashboard_endpoint": agent_pack.get("agent_integration", {}).get("dashboard_endpoint", "http://localhost:8050")
            }
        
        return context
    
    def format_for_agent_prompt(self) -> str:
        """Format brief information for agent prompts."""
        context = self.generate_agent_context()
        
        prompt = "# SIMP Agent Context\n\n"
        
        # System overview
        prompt += "## 🏗️ System Overview\n"
        overview = context["system_overview"]
        prompt += f"- **Total Files**: {overview.get('total_files', 0):,}\n"
        prompt += f"- **Total Modules**: {overview.get('total_modules', 0):,}\n"
        
        if overview.get("most_central_modules"):
            prompt += "- **Key Modules**:\n"
            for module in overview["most_central_modules"]:
                prompt += f"  - {module.get('name', '')} (centrality: {module.get('centrality', 0):.3f})\n"
        
        # Agent guidelines
        if context["agent_guidelines"]:
            prompt += "\n## 📜 Agent Guidelines\n"
            for i, rule in enumerate(context["agent_guidelines"][:5], 1):
                prompt += f"{i}. {rule}\n"
        
        # Recommended actions
        if context["recommended_actions"]:
            prompt += "\n## 🎯 Recommended Actions\n"
            for action in context["recommended_actions"]:
                priority_emoji = "🔴" if action["priority"] == "HIGH" else "🟡"
                prompt += f"{priority_emoji} **{action['type'].replace('_', ' ').title()}**: {action['description']}\n"
        
        # Current state
        prompt += "\n## 🌐 Current State\n"
        state = context["current_state"]
        prompt += f"- **Broker**: {state.get('broker_endpoint', 'Not available')}\n"
        prompt += f"- **Dashboard**: {state.get('dashboard_endpoint', 'Not available')}\n"
        
        prompt += "\n---\n"
        prompt += "*Generated from latest architecture brief*\n"
        
        return prompt

def main():
    """Example usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent integration with system briefs")
    parser.add_argument("--context", action="store_true", help="Generate agent context")
    parser.add_argument("--analyze", nargs="+", help="Analyze changed files")
    parser.add_argument("--prompt", action="store_true", help="Generate prompt context")
    
    args = parser.parse_args()
    
    integration = AgentBriefIntegration()
    
    if args.context:
        context = integration.generate_agent_context()
        print(json.dumps(context, indent=2))
    
    elif args.analyze:
        analysis = integration.analyze_change_with_brief(args.analyze)
        print(json.dumps(analysis, indent=2))
    
    elif args.prompt:
        prompt = integration.format_for_agent_prompt()
        print(prompt)
    
    else:
        # Show available briefs
        brief = integration.get_latest_brief()
        if brief:
            print("✅ Latest architecture brief found!")
            print(f"   Generated: {brief.get('generated_at', 'Unknown')}")
            print(f"   Modules: {brief.get('summary', {}).get('total_modules', 0):,}")
            print(f"   Recommendations: {len(brief.get('recommendations', []))}")
        else:
            print("❌ No architecture briefs found. Run generate_daily_briefs.sh first.")
        
        print("\n📚 Available commands:")
        print("  python tools/agent_brief_integration.py --context")
        print("  python tools/agent_brief_integration.py --analyze path/to/file.py")
        print("  python tools/agent_brief_integration.py --prompt")

if __name__ == "__main__":
    main()
