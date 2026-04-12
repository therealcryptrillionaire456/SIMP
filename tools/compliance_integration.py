#!/usr/bin/env python3
"""
Compliance Integration for SIMP
Integrates compliance mapping with Graphify and system briefs.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

class ComplianceIntegrator:
    """Integrates compliance data with existing SIMP systems."""
    
    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
        self.compliance_db_path = self.repo_root / "data" / "compliance_mapping.json"
        self.briefs_dir = self.repo_root / "briefs"
        self.graph_dir = self.repo_root / ".graphify"
        
        # Load compliance database
        if self.compliance_db_path.exists():
            with open(self.compliance_db_path, 'r') as f:
                self.compliance_db = json.load(f)
        else:
            self.compliance_db = {}
    
    def enhance_architecture_brief(self, brief_path: Optional[str] = None) -> Dict[str, Any]:
        """Enhance architecture brief with compliance data."""
        # Find latest brief if not specified
        if not brief_path:
            brief_files = list(self.briefs_dir.glob("architecture_brief_*.json"))
            if not brief_files:
                print("❌ No architecture briefs found")
                return {}
            brief_path = max(brief_files, key=lambda p: p.stat().st_mtime)
        
        # Load brief
        with open(brief_path, 'r') as f:
            brief = json.load(f)
        
        # Get compliance data
        compliance_status = self.compliance_db.get("compliance_status", {})
        module_mappings = self.compliance_db.get("module_mappings", {})
        
        # Enhance modules with compliance info
        enhanced_modules = {}
        for module_name, module_data in brief.get("modules", {}).items():
            compliance_info = compliance_status.get(module_name, {})
            mappings = module_mappings.get(module_name, {}).get("requirements", [])
            
            enhanced_module = module_data.copy()
            enhanced_module["compliance"] = {
                "status": compliance_info.get("status", "unknown"),
                "requirement_count": compliance_info.get("requirement_count", 0),
                "average_confidence": compliance_info.get("average_confidence", 0),
                "requirements": mappings[:5]  # Include top 5 requirements
            }
            
            enhanced_modules[module_name] = enhanced_module
        
        # Add compliance summary
        compliance_summary = {
            "total_modules_mapped": len(compliance_status),
            "high_priority": sum(1 for s in compliance_status.values() if s.get("status") == "high_priority"),
            "medium_priority": sum(1 for s in compliance_status.values() if s.get("status") == "medium_priority"),
            "low_priority": sum(1 for s in compliance_status.values() if s.get("status") == "low_priority"),
            "total_requirements": sum(len(m.get("requirements", [])) for m in module_mappings.values())
        }
        
        # Create enhanced brief
        enhanced_brief = brief.copy()
        enhanced_brief["modules"] = enhanced_modules
        enhanced_brief["compliance_summary"] = compliance_summary
        enhanced_brief["enhanced_at"] = datetime.now().isoformat()
        
        # Save enhanced brief
        enhanced_path = brief_path.with_name(f"{brief_path.stem}_with_compliance.json")
        with open(enhanced_path, 'w') as f:
            json.dump(enhanced_brief, f, indent=2)
        
        print(f"✅ Enhanced brief saved to {enhanced_path}")
        
        return enhanced_brief
    
    def generate_compliance_dashboard_data(self) -> Dict[str, Any]:
        """Generate data for compliance dashboard."""
        compliance_status = self.compliance_db.get("compliance_status", {})
        module_mappings = self.compliance_db.get("module_mappings", {})
        legal_requirements = self.compliance_db.get("legal_requirements", {})
        
        # Prepare dashboard data
        dashboard_data = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "modules": len(compliance_status),
                "requirements": sum(len(m.get("requirements", [])) for m in module_mappings.values()),
                "legal_documents": len(legal_requirements),
                "high_risk_modules": sum(1 for s in compliance_status.values() if s.get("status") == "high_priority")
            },
            "modules": [],
            "requirements_by_category": {},
            "timeline": self.compliance_db.get("audit_log", [])[-10:]  # Last 10 audit entries
        }
        
        # Prepare module data
        for module_name, status in compliance_status.items():
            mappings = module_mappings.get(module_name, {})
            module_data = {
                "name": module_name,
                "status": status.get("status", "unknown"),
                "requirement_count": status.get("requirement_count", 0),
                "confidence": status.get("average_confidence", 0),
                "requirements": mappings.get("requirements", [])[:3]  # Top 3 requirements
            }
            dashboard_data["modules"].append(module_data)
        
        # Count requirements by category
        for module_name, mappings in module_mappings.items():
            for req in mappings.get("requirements", []):
                category = req.get("category", "unknown")
                if category not in dashboard_data["requirements_by_category"]:
                    dashboard_data["requirements_by_category"][category] = 0
                dashboard_data["requirements_by_category"][category] += 1
        
        # Sort modules by priority
        dashboard_data["modules"].sort(key=lambda x: {
            "high_priority": 0,
            "medium_priority": 1,
            "low_priority": 2,
            "unknown": 3
        }.get(x["status"], 3))
        
        return dashboard_data
    
    def create_compliance_test_suggestions(self, module_name: str) -> List[Dict[str, Any]]:
        """Create test suggestions based on compliance requirements."""
        module_mappings = self.compliance_db.get("module_mappings", {}).get(module_name, {})
        
        if not module_mappings:
            return []
        
        suggestions = []
        requirements = module_mappings.get("requirements", [])
        
        for req in requirements:
            req_text = req.get("text", "")
            category = req.get("category", "")
            
            # Generate test suggestion based on requirement
            test_suggestion = {
                "requirement_id": req.get("id"),
                "requirement_text": req_text[:100] + "..." if len(req_text) > 100 else req_text,
                "category": category,
                "test_type": self._suggest_test_type(category, req_text),
                "test_description": self._generate_test_description(category, req_text),
                "priority": "high" if req.get("confidence", 0) > 0.7 else "medium"
            }
            
            suggestions.append(test_suggestion)
        
        return suggestions
    
    def _suggest_test_type(self, category: str, requirement: str) -> str:
        """Suggest test type based on requirement category."""
        mapping = {
            "security": "security_test",
            "privacy": "privacy_test", 
            "financial": "financial_test",
            "data_management": "data_test",
            "audit": "audit_test",
            "access_control": "auth_test",
            "general_compliance": "compliance_test",
            "regulatory": "regulatory_test",
            "policy": "policy_test"
        }
        return mapping.get(category, "compliance_test")
    
    def _generate_test_description(self, category: str, requirement: str) -> str:
        """Generate test description from requirement."""
        base_descriptions = {
            "security": f"Verify security requirement: {requirement[:50]}...",
            "privacy": f"Test privacy compliance for: {requirement[:50]}...",
            "financial": f"Validate financial requirement: {requirement[:50]}...",
            "data_management": f"Check data handling: {requirement[:50]}...",
            "audit": f"Audit logging test: {requirement[:50]}...",
            "access_control": f"Access control test: {requirement[:50]}..."
        }
        return base_descriptions.get(category, f"Compliance test: {requirement[:50]}...")
    
    def integrate_with_agent_prompts(self) -> str:
        """Generate compliance context for agent prompts."""
        compliance_status = self.compliance_db.get("compliance_status", {})
        
        if not compliance_status:
            return "# Compliance Context\n\nNo compliance data available. Run compliance mapper first.\n"
        
        # Count by status
        high_priority = sum(1 for s in compliance_status.values() if s.get("status") == "high_priority")
        medium_priority = sum(1 for s in compliance_status.values() if s.get("status") == "medium_priority")
        
        prompt = "# 📜 SIMP Compliance Context\n\n"
        
        prompt += "## 🎯 Compliance Status\n"
        prompt += f"- **High Priority Modules**: {high_priority}\n"
        prompt += f"- **Medium Priority Modules**: {medium_priority}\n"
        prompt += f"- **Total Modules Mapped**: {len(compliance_status)}\n\n"
        
        if high_priority > 0:
            prompt += "## 🔴 High Priority Modules (Review Needed)\n"
            for module_name, status in compliance_status.items():
                if status.get("status") == "high_priority":
                    req_count = status.get("requirement_count", 0)
                    prompt += f"- **{module_name}**: {req_count} requirements\n"
            prompt += "\n"
        
        prompt += "## 💡 Agent Guidance\n"
        prompt += "1. **When modifying high-priority modules**: Check compliance requirements first\n"
        prompt += "2. **When adding new features**: Consider relevant compliance categories\n"
        prompt += "3. **When writing tests**: Include compliance-related test cases\n"
        prompt += "4. **When documenting**: Reference compliance requirements\n\n"
        
        prompt += "---\n"
        prompt += "*Generated from compliance mapping database*\n"
        
        return prompt

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SIMP Compliance Integrator")
    parser.add_argument("--enhance-brief", action="store_true", help="Enhance architecture brief with compliance")
    parser.add_argument("--dashboard", action="store_true", help="Generate dashboard data")
    parser.add_argument("--test-suggestions", help="Generate test suggestions for module")
    parser.add_argument("--agent-prompt", action="store_true", help="Generate agent prompt context")
    
    args = parser.parse_args()
    
    integrator = ComplianceIntegrator()
    
    try:
        if args.enhance_brief:
            print("🎨 Enhancing architecture brief with compliance data...")
            enhanced_brief = integrator.enhance_architecture_brief()
            print(f"✅ Brief enhanced with {len(enhanced_brief.get('modules', {}))} modules")
        
        if args.dashboard:
            print("📊 Generating dashboard data...")
            dashboard_data = integrator.generate_compliance_dashboard_data()
            print(f"✅ Dashboard data: {dashboard_data['summary']}")
            
            # Save dashboard data
            output_path = Path("compliance_reports") / "dashboard_data.json"
            output_path.parent.mkdir(exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(dashboard_data, f, indent=2)
            print(f"💾 Saved to {output_path}")
        
        if args.test_suggestions:
            print(f"🧪 Generating test suggestions for {args.test_suggestions}...")
            suggestions = integrator.create_compliance_test_suggestions(args.test_suggestions)
            print(f"✅ Generated {len(suggestions)} test suggestions")
            for suggestion in suggestions[:3]:  # Show first 3
                print(f"  - {suggestion['test_type']}: {suggestion['test_description']}")
        
        if args.agent_prompt:
            print("🤖 Generating agent prompt context...")
            prompt = integrator.integrate_with_agent_prompts()
            print(prompt)
        
        if not any([args.enhance_brief, args.dashboard, args.test_suggestions, args.agent_prompt]):
            # Default: show status
            if integrator.compliance_db:
                print("✅ Compliance database loaded")
                status = integrator.compliance_db.get("compliance_status", {})
                print(f"📊 Modules mapped: {len(status)}")
                print(f"📅 Last updated: {integrator.compliance_db.get('updated_at', 'Never')}")
            else:
                print("❌ No compliance database found. Run compliance_mapper.py first.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
