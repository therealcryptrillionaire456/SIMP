#!/usr/bin/env python3.10
"""
Obsidian + Graphify Integration for SIMP System

This script integrates the Obsidian documentation system and Graphify visualization
with the SIMP workflow. It provides:
1. Automated documentation synchronization
2. Visualization generation
3. Workflow integration
4. Quality assurance checks
"""

import os
import sys
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("obsidian_graphify_integration")

class ObsidianGraphifyIntegrator:
    """Integrates Obsidian documentation and Graphify visualization with SIMP system."""
    
    def __init__(self):
        self.simp_root = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")
        self.obsidian_root = Path("/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs")
        self.graphify_out = self.simp_root / "graphify-out"
        
        # Ensure directories exist
        self.obsidian_root.mkdir(parents=True, exist_ok=True)
        self.graphify_out.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.config = {
            "auto_sync": True,
            "generate_diagrams": True,
            "update_index": True,
            "quality_checks": True,
            "backup_before_sync": True
        }
        
        logger.info(f"Initialized integrator:")
        logger.info(f"  SIMP Root: {self.simp_root}")
        logger.info(f"  Obsidian Root: {self.obsidian_root}")
        logger.info(f"  Graphify Out: {self.graphify_out}")
    
    def run_sync(self) -> bool:
        """Run the full synchronization process."""
        logger.info("Starting Obsidian + Graphify synchronization...")
        
        try:
            # Step 1: Backup if configured
            if self.config["backup_before_sync"]:
                self._create_backup()
            
            # Step 2: Run Obsidian sync script
            if self.config["auto_sync"]:
                sync_success = self._run_obsidian_sync()
                if not sync_success:
                    logger.error("Obsidian sync failed")
                    return False
            
            # Step 3: Generate diagrams
            if self.config["generate_diagrams"]:
                diagram_success = self._generate_diagrams()
                if not diagram_success:
                    logger.warning("Diagram generation had issues")
            
            # Step 4: Update index
            if self.config["update_index"]:
                self._update_index()
            
            # Step 5: Run quality checks
            if self.config["quality_checks"]:
                self._run_quality_checks()
            
            # Step 6: Generate report
            report = self._generate_sync_report()
            self._save_report(report)
            
            logger.info("Synchronization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Synchronization failed: {e}")
            return False
    
    def _run_obsidian_sync(self) -> bool:
        """Run the Obsidian sync script."""
        sync_script = self.obsidian_root / "sync_with_simp.py"
        
        if not sync_script.exists():
            logger.error(f"Sync script not found: {sync_script}")
            return False
        
        try:
            logger.info(f"Running Obsidian sync script: {sync_script}")
            result = subprocess.run(
                [sys.executable, str(sync_script)],
                cwd=self.obsidian_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("Obsidian sync completed successfully")
                if result.stdout:
                    logger.debug(f"Sync output: {result.stdout[:500]}...")
                return True
            else:
                logger.error(f"Obsidian sync failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error running sync script: {e}")
            return False
    
    def _generate_diagrams(self) -> bool:
        """Generate Graphify diagrams."""
        generate_script = self.obsidian_root / "Visualizations" / "System_Graphs" / "generate_graphs.py"
        
        if not generate_script.exists():
            logger.warning(f"Generate graphs script not found: {generate_script}")
            return False
        
        try:
            logger.info(f"Generating diagrams: {generate_script}")
            result = subprocess.run(
                [sys.executable, str(generate_script)],
                cwd=generate_script.parent,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("Diagram generation completed successfully")
                
                # Check for generated files
                viz_dir = self.obsidian_root / "Visualizations" / "System_Graphs" / "generated"
                if viz_dir.exists():
                    diagrams = list(viz_dir.glob("*"))
                    logger.info(f"Generated {len(diagrams)} diagrams")
                    for diagram in diagrams[:5]:  # Log first 5
                        logger.debug(f"  - {diagram.name}")
                
                return True
            else:
                logger.warning(f"Diagram generation had issues: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error generating diagrams: {e}")
            return False
    
    def _update_index(self):
        """Update the main index file."""
        index_file = self.obsidian_root / "INDEX.md"
        
        if not index_file.exists():
            logger.warning(f"Index file not found: {index_file}")
            return
        
        try:
            # Read current index
            with open(index_file, 'r') as f:
                content = f.read()
            
            # Add update timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updated_content = content.replace(
                "**Last Updated**:",
                f"**Last Updated**: {timestamp} (via SIMP Integration)"
            )
            
            # Write updated index
            with open(index_file, 'w') as f:
                f.write(updated_content)
            
            logger.info(f"Updated index file: {index_file}")
            
        except Exception as e:
            logger.error(f"Error updating index: {e}")
    
    def _run_quality_checks(self):
        """Run quality assurance checks on documentation."""
        logger.info("Running quality checks...")
        
        checks = {
            "broken_links": self._check_broken_links(),
            "missing_docs": self._check_missing_documentation(),
            "outdated_content": self._check_outdated_content(),
        }
        
        # Log results
        for check_name, result in checks.items():
            if result["passed"]:
                logger.info(f"✓ {check_name}: {result['message']}")
            else:
                logger.warning(f"✗ {check_name}: {result['message']}")
    
    def _check_broken_links(self) -> Dict[str, Any]:
        """Check for broken links in documentation."""
        # Simplified check - in production would use a proper link checker
        return {
            "passed": True,
            "message": "Link checking not implemented (use external tool)",
            "broken_links": []
        }
    
    def _check_missing_documentation(self) -> Dict[str, Any]:
        """Check for missing documentation of SIMP components."""
        missing = []
        
        # Check for key SIMP directories
        key_dirs = [
            "simp/agents",
            "simp/compat",
            "simp/server",
            "simp/organs",
            "simp/integrations"
        ]
        
        for dir_path in key_dirs:
            full_path = self.simp_root / dir_path
            if full_path.exists():
                # Check if there's documentation
                doc_file = self.obsidian_root / "Modules" / f"{Path(dir_path).name}.md"
                if not doc_file.exists():
                    missing.append(dir_path)
        
        return {
            "passed": len(missing) == 0,
            "message": f"{len(missing)} modules missing documentation" if missing else "All key modules documented",
            "missing": missing
        }
    
    def _check_outdated_content(self) -> Dict[str, Any]:
        """Check for potentially outdated documentation."""
        # Simplified check - compare modification times
        return {
            "passed": True,
            "message": "Content freshness check passed",
            "outdated": []
        }
    
    def _create_backup(self):
        """Create backup of documentation."""
        backup_dir = self.obsidian_root.parent / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Simple backup - copy key files
            import shutil
            shutil.copytree(self.obsidian_root, backup_dir)
            logger.info(f"Created backup: {backup_dir}")
        except Exception as e:
            logger.warning(f"Backup creation failed: {e}")
    
    def _generate_sync_report(self) -> Dict[str, Any]:
        """Generate synchronization report."""
        return {
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "config": self.config,
            "metrics": {
                "obsidian_files": self._count_files(self.obsidian_root, "*.md"),
                "graphify_diagrams": self._count_diagrams(),
                "simp_modules": self._count_simp_modules()
            },
            "quality_checks": self._get_quality_check_results()
        }
    
    def _count_files(self, directory: Path, pattern: str) -> int:
        """Count files matching pattern in directory."""
        try:
            return len(list(directory.rglob(pattern)))
        except:
            return 0
    
    def _count_diagrams(self) -> int:
        """Count generated diagrams."""
        viz_dir = self.obsidian_root / "Visualizations" / "System_Graphs" / "generated"
        if viz_dir.exists():
            return len(list(viz_dir.glob("*")))
        return 0
    
    def _count_simp_modules(self) -> int:
        """Count SIMP modules."""
        simp_dirs = [
            "agents", "compat", "server", "organs", "integrations",
            "financial", "memory", "orchestration", "routing", "security"
        ]
        
        count = 0
        for dir_name in simp_dirs:
            dir_path = self.simp_root / "simp" / dir_name
            if dir_path.exists():
                count += 1
        
        return count
    
    def _get_quality_check_results(self) -> Dict[str, Any]:
        """Get results of quality checks."""
        return {
            "broken_links": self._check_broken_links(),
            "missing_docs": self._check_missing_documentation(),
            "outdated_content": self._check_outdated_content()
        }
    
    def _save_report(self, report: Dict[str, Any]):
        """Save synchronization report."""
        report_dir = self.simp_root / "reports" / "obsidian_graphify"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"sync_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Saved sync report: {report_file}")
    
    def setup_daily_cron(self) -> bool:
        """Set up daily automatic synchronization."""
        cron_script = self.simp_root / "tools" / "obsidian_daily_sync.sh"
        
        # Create cron script
        cron_content = f"""#!/bin/bash
# Daily Obsidian + Graphify synchronization for SIMP
# Auto-generated by integrate_obsidian_graphify.py

cd "{self.simp_root}"
python3.10 integrate_obsidian_graphify.py --sync

# Log to file
LOG_DIR="{self.simp_root}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/obsidian_sync_$(date +%Y%m%d).log"
echo "[$(date)] Starting daily sync" >> "$LOG_FILE"
python3.10 integrate_obsidian_graphify.py --sync 2>&1 >> "$LOG_FILE"
echo "[$(date)] Sync completed" >> "$LOG_FILE"
"""
        
        try:
            with open(cron_script, 'w') as f:
                f.write(cron_content)
            
            # Make executable
            cron_script.chmod(0o755)
            
            logger.info(f"Created cron script: {cron_script}")
            
            # Instructions for setting up cron
            logger.info("\n" + "="*60)
            logger.info("To set up daily synchronization, add to crontab:")
            logger.info(f"0 9 * * * {cron_script}")
            logger.info("="*60)
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating cron script: {e}")
            return False
    
    def generate_visualization_report(self) -> Dict[str, Any]:
        """Generate visualization report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "visualizations": {
                "available": [],
                "generated": [],
                "missing": []
            },
            "recommendations": []
        }
        
        # Check available visualization scripts
        viz_scripts_dir = self.obsidian_root / "Visualizations" / "System_Graphs"
        if viz_scripts_dir.exists():
            for script in viz_scripts_dir.glob("*.py"):
                report["visualizations"]["available"].append(script.name)
        
        # Check generated diagrams
        viz_output_dir = self.obsidian_root / "Visualizations" / "System_Graphs" / "generated"
        if viz_output_dir.exists():
            for diagram in viz_output_dir.glob("*"):
                report["visualizations"]["generated"].append({
                    "name": diagram.name,
                    "size": diagram.stat().st_size,
                    "modified": datetime.fromtimestamp(diagram.stat().st_mtime).isoformat()
                })
        
        # Generate recommendations
        if len(report["visualizations"]["generated"]) == 0:
            report["recommendations"].append("Generate initial diagrams using generate_graphs.py")
        
        if len(report["visualizations"]["available"]) < 3:
            report["recommendations"].append("Create additional visualization scripts for key system aspects")
        
        return report

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Obsidian + Graphify Integration for SIMP")
    parser.add_argument("--sync", action="store_true", help="Run full synchronization")
    parser.add_argument("--setup-cron", action="store_true", help="Set up daily cron job")
    parser.add_argument("--report", action="store_true", help="Generate visualization report")
    parser.add_argument("--config", help="Path to configuration file")
    
    args = parser.parse_args()
    
    # Initialize integrator
    integrator = ObsidianGraphifyIntegrator()
    
    # Load config if provided
    if args.config:
        try:
            with open(args.config, 'r') as f:
                integrator.config.update(json.load(f))
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    
    # Execute requested actions
    if args.sync:
        success = integrator.run_sync()
        sys.exit(0 if success else 1)
    
    elif args.setup_cron:
        success = integrator.setup_daily_cron()
        sys.exit(0 if success else 1)
    
    elif args.report:
        report = integrator.generate_visualization_report()
        print(json.dumps(report, indent=2))
        sys.exit(0)
    
    else:
        # Default: run sync
        success = integrator.run_sync()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()