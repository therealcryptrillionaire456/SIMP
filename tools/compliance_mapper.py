#!/usr/bin/env python3
"""
Compliance Mapper for SIMP
Links code modules to legal/regulatory requirements.
Integrates with Graphify knowledge graph and system briefs.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

class ComplianceMapper:
    """Maps code modules to legal requirements."""
    
    def __init__(self, repo_root: str = ".", graph_dir: str = ".graphify"):
        self.repo_root = Path(repo_root)
        self.graph_dir = Path(graph_dir)
        self.graph_path = self.graph_dir / "simp_graph.json"
        self.compliance_db_path = self.repo_root / "data" / "compliance_mapping.json"
        self.legal_docs_dir = self.repo_root / "pentagram_legal"
        
        # Ensure directories exist
        self.repo_root.mkdir(exist_ok=True)
        (self.repo_root / "data").mkdir(exist_ok=True)
        
        # Load or initialize compliance database
        if self.compliance_db_path.exists():
            with open(self.compliance_db_path, 'r') as f:
                self.compliance_db = json.load(f)
        else:
            self.compliance_db = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "legal_requirements": {},
                "module_mappings": {},
                "compliance_status": {},
                "audit_log": []
            }
        
        # Load graph if available
        self.graph = None
        if self.graph_path.exists():
            with open(self.graph_path, 'r') as f:
                self.graph = json.load(f)
    
    def scan_legal_documents(self) -> Dict[str, Any]:
        """Scan legal documents for requirements."""
        requirements = {}
        
        # Check for legal documents
        legal_files = list(self.legal_docs_dir.rglob("*.md")) + list(self.legal_docs_dir.rglob("*.txt"))
        
        print(f"🔍 Scanning {len(legal_files)} legal documents...")
        
        for file_path in legal_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Extract requirements from document
                doc_requirements = self._extract_requirements_from_doc(content, str(file_path))
                
                if doc_requirements:
                    rel_path = str(file_path.relative_to(self.repo_root))
                    requirements[rel_path] = {
                        "file": rel_path,
                        "requirements": doc_requirements,
                        "scan_time": datetime.now().isoformat()
                    }
                    
            except Exception as e:
                print(f"⚠️  Error scanning {file_path}: {e}")
        
        # Update database
        self.compliance_db["legal_requirements"] = requirements
        self.compliance_db["updated_at"] = datetime.now().isoformat()
        
        print(f"✅ Found {len(requirements)} documents with requirements")
        
        return requirements
    
    def _extract_requirements_from_doc(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract legal requirements from document content."""
        requirements = []
        
        # Look for requirement patterns
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Look for requirement indicators
            if any(indicator in line.lower() for indicator in [
                "must", "shall", "required", "requirement", "compliance", 
                "regulation", "standard", "policy", "obligation", "mandatory"
            ]):
                # Get context (previous and next lines)
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 3)
                context = '\n'.join(lines[context_start:context_end])
                
                # Categorize requirement
                category = self._categorize_requirement(line, file_path)
                
                requirement = {
                    "id": f"req_{len(requirements) + 1:04d}",
                    "text": line,
                    "context": context,
                    "category": category,
                    "source_file": file_path,
                    "line_number": i + 1,
                    "extracted_at": datetime.now().isoformat()
                }
                
                requirements.append(requirement)
        
        return requirements
    
    def _categorize_requirement(self, text: str, file_path: str) -> str:
        """Categorize a legal requirement."""
        text_lower = text.lower()
        file_lower = file_path.lower()
        
        # Category mapping
        if any(word in text_lower for word in ["security", "secure", "protect", "confidential"]):
            return "security"
        elif any(word in text_lower for word in ["privacy", "personal data", "gdpr", "ccpa"]):
            return "privacy"
        elif any(word in text_lower for word in ["financial", "payment", "transaction", "money"]):
            return "financial"
        elif any(word in text_lower for word in ["data", "storage", "retention", "backup"]):
            return "data_management"
        elif any(word in text_lower for word in ["audit", "log", "record", "documentation"]):
            return "audit"
        elif any(word in text_lower for word in ["access", "permission", "authorization"]):
            return "access_control"
        elif "compliance" in text_lower:
            return "general_compliance"
        elif "regulation" in text_lower:
            return "regulatory"
        elif "policy" in text_lower:
            return "policy"
        else:
            return "other"
    
    def map_modules_to_requirements(self) -> Dict[str, Any]:
        """Map SIMP modules to legal requirements."""
        if not self.graph:
            print("❌ No graph available. Run Graphify first.")
            return {}
        
        modules = self._extract_modules_from_graph()
        requirements = self.compliance_db.get("legal_requirements", {})
        
        mappings = {}
        
        print(f"🗺️  Mapping {len(modules)} modules to requirements...")
        
        for module_name, module_info in modules.items():
            module_mappings = []
            
            # Check each requirement against module
            for req_file, req_data in requirements.items():
                for requirement in req_data.get("requirements", []):
                    req_text = requirement.get("text", "").lower()
                    req_category = requirement.get("category", "")
                    
                    # Check if module is relevant to requirement
                    if self._is_module_relevant(module_name, module_info, req_text, req_category):
                        mapping = {
                            "requirement_id": requirement["id"],
                            "requirement_text": requirement["text"],
                            "category": req_category,
                            "source_file": req_file,
                            "confidence": self._calculate_relevance_confidence(module_name, req_text, req_category),
                            "mapped_at": datetime.now().isoformat()
                        }
                        module_mappings.append(mapping)
            
            if module_mappings:
                mappings[module_name] = {
                    "module_info": module_info,
                    "requirements": module_mappings,
                    "total_requirements": len(module_mappings)
                }
        
        # Update database
        self.compliance_db["module_mappings"] = mappings
        self.compliance_db["updated_at"] = datetime.now().isoformat()
        
        print(f"✅ Mapped {len(mappings)} modules to requirements")
        
        return mappings
    
    def _extract_modules_from_graph(self) -> Dict[str, Any]:
        """Extract modules from Graphify graph."""
        modules = {}
        
        if not self.graph:
            return modules
        
        nodes = self.graph.get("nodes", [])
        
        # Group nodes by module (directory)
        for node in nodes:
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
                                "files": []
                            }
                        
                        # Count file if it's a .py file
                        label = node.get("label", "")
                        if label.endswith(".py"):
                            modules[module_name]["file_count"] += 1
                            modules[module_name]["files"].append(label)
                        elif "class" in label.lower():
                            modules[module_name]["class_count"] += 1
                        elif "(" in label and ")" in label:
                            modules[module_name]["function_count"] += 1
        
        return modules
    
    def _is_module_relevant(self, module_name: str, module_info: Dict, req_text: str, req_category: str) -> bool:
        """Check if a module is relevant to a requirement."""
        module_lower = module_name.lower()
        
        # Keyword-based matching
        keywords = {
            "security": ["security", "auth", "encrypt", "protect", "secure"],
            "privacy": ["privacy", "gdpr", "ccpa", "personal", "data"],
            "financial": ["financial", "payment", "money", "transaction", "trade"],
            "data_management": ["data", "storage", "database", "retention"],
            "audit": ["audit", "log", "record", "track"],
            "access_control": ["access", "permission", "authorization", "role"]
        }
        
        # Check category-specific keywords
        if req_category in keywords:
            for keyword in keywords[req_category]:
                if keyword in module_lower or keyword in req_text:
                    return True
        
        # Check module name against requirement
        module_keywords = module_name.split("_")
        for keyword in module_keywords:
            if keyword.lower() in req_text and len(keyword) > 3:
                return True
        
        # Special cases
        if module_name == "financial" and req_category == "financial":
            return True
        elif module_name == "security" and req_category == "security":
            return True
        elif module_name == "compat" and "compliance" in req_text:
            return True
        
        return False
    
    def _calculate_relevance_confidence(self, module_name: str, req_text: str, req_category: str) -> float:
        """Calculate confidence score for module-requirement mapping."""
        confidence = 0.0
        
        # Exact module name in requirement
        if module_name.lower() in req_text:
            confidence += 0.4
        
        # Category match
        module_lower = module_name.lower()
        if req_category == "security" and any(word in module_lower for word in ["security", "auth", "encrypt"]):
            confidence += 0.3
        elif req_category == "financial" and any(word in module_lower for word in ["financial", "payment", "money"]):
            confidence += 0.3
        elif req_category == "privacy" and any(word in module_lower for word in ["privacy", "data", "gdpr"]):
            confidence += 0.3
        
        # Keyword matching
        keywords = module_name.split("_")
        for keyword in keywords:
            if len(keyword) > 3 and keyword.lower() in req_text:
                confidence += 0.1
        
        return min(confidence, 1.0)
    
    def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate compliance report."""
        mappings = self.compliance_db.get("module_mappings", {})
        requirements = self.compliance_db.get("legal_requirements", {})
        
        # Calculate statistics
        total_modules = len(mappings)
        total_requirements = sum(len(data["requirements"]) for data in mappings.values())
        
        # Group by category
        categories = {}
        for module_name, module_data in mappings.items():
            for req in module_data["requirements"]:
                category = req["category"]
                if category not in categories:
                    categories[category] = {
                        "modules": set(),
                        "requirements": []
                    }
                categories[category]["modules"].add(module_name)
                categories[category]["requirements"].append(req)
        
        # Calculate compliance status
        compliance_status = {}
        for module_name, module_data in mappings.items():
            req_count = len(module_data["requirements"])
            avg_confidence = sum(req["confidence"] for req in module_data["requirements"]) / req_count if req_count > 0 else 0
            
            if avg_confidence > 0.7:
                status = "high_priority"
            elif avg_confidence > 0.4:
                status = "medium_priority"
            else:
                status = "low_priority"
            
            compliance_status[module_name] = {
                "requirement_count": req_count,
                "average_confidence": avg_confidence,
                "status": status,
                "last_updated": datetime.now().isoformat()
            }
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_modules_mapped": total_modules,
                "total_requirements": total_requirements,
                "categories": len(categories),
                "high_priority_modules": sum(1 for status in compliance_status.values() if status["status"] == "high_priority"),
                "medium_priority_modules": sum(1 for status in compliance_status.values() if status["status"] == "medium_priority"),
                "low_priority_modules": sum(1 for status in compliance_status.values() if status["status"] == "low_priority")
            },
            "categories": {cat: {
                "module_count": len(data["modules"]),
                "requirement_count": len(data["requirements"])
            } for cat, data in categories.items()},
            "compliance_status": compliance_status,
            "top_modules_by_requirements": sorted(
                [(name, len(data["requirements"])) for name, data in mappings.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
        
        # Update database
        self.compliance_db["compliance_status"] = compliance_status
        self.compliance_db["updated_at"] = datetime.now().isoformat()
        
        # Add to audit log
        self.compliance_db["audit_log"].append({
            "timestamp": datetime.now().isoformat(),
            "action": "generate_compliance_report",
            "report_summary": report["summary"]
        })
        
        return report
    
    def save_database(self):
        """Save compliance database to file."""
        self.compliance_db["updated_at"] = datetime.now().isoformat()
        
        with open(self.compliance_db_path, 'w') as f:
            json.dump(self.compliance_db, f, indent=2)
        
        print(f"💾 Saved compliance database to {self.compliance_db_path}")
    
    def export_report(self, format: str = "markdown", output_dir: str = "compliance_reports") -> str:
        """Export compliance report in specified format."""
        report = self.generate_compliance_report()
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "markdown":
            file_path = output_path / f"compliance_report_{timestamp}.md"
            self._export_markdown_report(file_path, report)
        elif format == "json":
            file_path = output_path / f"compliance_report_{timestamp}.json"
            with open(file_path, 'w') as f:
                json.dump(report, f, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        print(f"📄 Exported {format} report to {file_path}")
        return str(file_path)
    
    def _export_markdown_report(self, file_path: Path, report: Dict[str, Any]) -> None:
        """Export report as Markdown."""
        with open(file_path, 'w') as f:
            f.write(f"# SIMP Compliance Report\n\n")
            f.write(f"*Generated: {report['generated_at']}*\n")
            f.write(f"*Database: {self.compliance_db['updated_at']}*\n\n")
            
            # Summary
            f.write("## 📊 Executive Summary\n\n")
            summary = report["summary"]
            f.write(f"- **Modules Mapped**: {summary['total_modules_mapped']}\n")
            f.write(f"- **Total Requirements**: {summary['total_requirements']}\n")
            f.write(f"- **Categories**: {summary['categories']}\n")
            f.write(f"- **High Priority Modules**: {summary['high_priority_modules']}\n")
            f.write(f"- **Medium Priority Modules**: {summary['medium_priority_modules']}\n")
            f.write(f"- **Low Priority Modules**: {summary['low_priority_modules']}\n\n")
            
            # Categories
            f.write("## 🏷️ Requirements by Category\n\n")
            for category, data in report["categories"].items():
                f.write(f"### {category.replace('_', ' ').title()}\n")
                f.write(f"- Modules: {data['module_count']}\n")
                f.write(f"- Requirements: {data['requirement_count']}\n\n")
            
            # Top modules
            f.write("## 🏆 Top Modules by Requirements\n\n")
            for module_name, req_count in report["top_modules_by_requirements"]:
                status = report["compliance_status"][module_name]["status"]
                status_emoji = "🔴" if status == "high_priority" else "🟡" if status == "medium_priority" else "🟢"
                f.write(f"{status_emoji} **{module_name}**: {req_count} requirements ({status.replace('_', ' ')})\n")
            f.write("\n")
            
            # Recommendations
            f.write("## 🎯 Recommendations\n\n")
            high_priority = [name for name, status in report["compliance_status"].items() 
                           if status["status"] == "high_priority"]
            
            if high_priority:
                f.write("### High Priority Review Needed\n")
                for module in high_priority[:5]:
                    f.write(f"- **{module}**: Review {report['compliance_status'][module]['requirement_count']} requirements\n")
                f.write("\n")
            
            f.write("### Next Steps\n")
            f.write("1. Review high priority modules for compliance gaps\n")
            f.write("2. Update module documentation with requirements\n")
            f.write("3. Run compliance tests for critical modules\n")
            f.write("4. Schedule regular compliance audits\n")
            f.write("\n---\n")
            f.write("*Generated by SIMP Compliance Mapper*\n")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SIMP Compliance Mapper")
    parser.add_argument("--scan", action="store_true", help="Scan legal documents")
    parser.add_argument("--map", action="store_true", help="Map modules to requirements")
    parser.add_argument("--report", action="store_true", help="Generate compliance report")
    parser.add_argument("--export", choices=["markdown", "json"], help="Export report format")
    parser.add_argument("--output-dir", default="compliance_reports", help="Output directory")
    
    args = parser.parse_args()
    
    mapper = ComplianceMapper()
    
    try:
        if args.scan:
            print("🔍 Scanning legal documents...")
            requirements = mapper.scan_legal_documents()
            mapper.save_database()
            print(f"✅ Scanned {len(requirements)} documents")
        
        if args.map:
            print("🗺️  Mapping modules to requirements...")
            mappings = mapper.map_modules_to_requirements()
            mapper.save_database()
            print(f"✅ Mapped {len(mappings)} modules")
        
        if args.report:
            print("📊 Generating compliance report...")
            report = mapper.generate_compliance_report()
            mapper.save_database()
            print(f"✅ Generated report: {report['summary']}")
        
        if args.export:
            print(f"📄 Exporting {args.export} report...")
            file_path = mapper.export_report(args.export, args.output_dir)
            print(f"✅ Exported to {file_path}")
        
        if not any([args.scan, args.map, args.report, args.export]):
            # Default: run full pipeline
            print("🚀 Running full compliance mapping pipeline...")
            mapper.scan_legal_documents()
            mapper.map_modules_to_requirements()
            report = mapper.generate_compliance_report()
            mapper.save_database()
            mapper.export_report("markdown", args.output_dir)
            print("✅ Full pipeline completed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
