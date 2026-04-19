#!/usr/bin/env python3.10
"""
Integrate Agent Lightning safety rules with BRP (Bill Russell Protocol)
Phase 4: Safety & Monitoring - Step 1
"""

import json
import os
import yaml
from datetime import datetime
from pathlib import Path

class BRPSafetyRuleIntegrator:
    """Integrate Agent Lightning safety rules with BRP"""
    
    def __init__(self):
        self.brp_rules_file = "/tmp/brp_enhanced_rules.json"
        self.projectx_monitoring_file = "/tmp/projectx_enhanced_monitoring.json"
        self.brp_config_dir = "config/brp"
        self.sigma_rules_dir = os.path.join(self.brp_config_dir, "sigma_rules")
        self.brp_config_file = os.path.join(self.brp_config_dir, "config.yaml")
        
        # Ensure directories exist
        os.makedirs(self.sigma_rules_dir, exist_ok=True)
        
    def load_generated_rules(self):
        """Load the rules generated from Agent Lightning traces"""
        print("📂 Loading generated safety rules...")
        
        if not os.path.exists(self.brp_rules_file):
            print(f"❌ BRP rules file not found: {self.brp_rules_file}")
            return None
            
        if not os.path.exists(self.projectx_monitoring_file):
            print(f"❌ ProjectX monitoring file not found: {self.projectx_monitoring_file}")
            return None
            
        try:
            with open(self.brp_rules_file, 'r') as f:
                brp_rules = json.load(f)
                
            with open(self.projectx_monitoring_file, 'r') as f:
                projectx_monitors = json.load(f)
                
            print(f"✅ Loaded {len(brp_rules.get('new_rules', []))} BRP rules")
            print(f"✅ Loaded {len(projectx_monitors.get('new_monitors', []))} ProjectX monitors")
            
            return {
                "brp_rules": brp_rules,
                "projectx_monitors": projectx_monitors
            }
        except Exception as e:
            print(f"❌ Error loading rules: {e}")
            return None
    
    def convert_to_sigma_rules(self, brp_rules):
        """Convert BRP rules to Sigma rule format"""
        print("\n🔄 Converting BRP rules to Sigma format...")
        
        sigma_rules = []
        
        for rule in brp_rules.get("new_rules", []):
            sigma_rule = {
                "title": f"Agent Lightning: {rule['description']}",
                "id": rule["rule_id"],
                "status": "experimental",
                "description": f"Generated from Agent Lightning trace analysis. Pattern: {rule.get('source_pattern', 'unknown')}",
                "author": "Agent Lightning Safety Analyzer",
                "date": datetime.now().strftime("%Y/%m/%d"),
                "modified": datetime.now().strftime("%Y/%m/%d"),
                "logsource": {
                    "category": "agent_behavior",
                    "product": "simp"
                },
                "detection": {
                    "condition": "all of them",
                    "selection": self._parse_brp_condition(rule.get("condition", ""))
                },
                "level": self._map_severity_to_level(rule.get("severity", "medium")),
                "tags": ["agent-lightning", "safety", "brp", rule.get("agents_applicable", ["general"])[0]]
            }
            sigma_rules.append(sigma_rule)
            
        print(f"✅ Converted {len(sigma_rules)} rules to Sigma format")
        return sigma_rules
    
    def _parse_brp_condition(self, condition_str):
        """Parse BRP condition string into Sigma selection format"""
        # This is a simplified parser - in production would need more robust parsing
        selection = {}
        
        if "file_path MATCHES" in condition_str:
            selection["operation_type"] = "file_write"
            # Extract file patterns
            if "/etc/*" in condition_str:
                selection["file_path"] = ["/etc/*", "/usr/bin/*", "broker.py", "config.py"]
        elif "operation_count > 5" in condition_str:
            selection["operation_count"] = "> 5"
            selection["time_window"] = "< 2s"
            if "quantumarb" in condition_str:
                selection["agent_type"] = "quantumarb"
        elif "tool_abstraction_violation == True" in condition_str:
            selection["tool_abstraction_violation"] = True
        elif "agent_uncertainty_score > 0.7" in condition_str:
            selection["agent_uncertainty_score"] = "> 0.7"
            selection["operation_type"] = "financial"
        elif "operation_modifies_ledger == True" in condition_str:
            selection["operation_modifies_ledger"] = True
            selection["rollback_plan_present"] = False
            
        return selection
    
    def _map_severity_to_level(self, severity):
        """Map BRP severity to Sigma rule level"""
        severity_map = {
            "CRITICAL": "critical",
            "HIGH": "high", 
            "MEDIUM": "medium",
            "LOW": "low"
        }
        return severity_map.get(severity.upper(), "medium")
    
    def save_sigma_rules(self, sigma_rules):
        """Save Sigma rules to BRP configuration directory"""
        print("\n💾 Saving Sigma rules to BRP configuration...")
        
        for i, rule in enumerate(sigma_rules):
            rule_file = os.path.join(self.sigma_rules_dir, f"agent_lightning_{rule['id']}.yml")
            
            try:
                with open(rule_file, 'w') as f:
                    yaml.dump(rule, f, default_flow_style=False, sort_keys=False)
                print(f"  ✅ Saved: {rule['id']}")
            except Exception as e:
                print(f"  ❌ Error saving rule {rule['id']}: {e}")
                
        print(f"✅ Saved {len(sigma_rules)} Sigma rules to {self.sigma_rules_dir}")
        
        # Create a summary file
        summary_file = os.path.join(self.sigma_rules_dir, "agent_lightning_summary.json")
        summary = {
            "integration_time": datetime.now().isoformat(),
            "total_rules": len(sigma_rules),
            "rule_ids": [r["id"] for r in sigma_rules],
            "source": "Agent Lightning Trace Analysis"
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
            
        print(f"📋 Summary saved to: {summary_file}")
    
    def update_brp_config(self, brp_rules):
        """Update BRP configuration to include Agent Lightning rules"""
        print("\n⚙️ Updating BRP configuration...")
        
        if not os.path.exists(self.brp_config_file):
            print(f"❌ BRP config file not found: {self.brp_config_file}")
            return False
            
        try:
            with open(self.brp_config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Add Agent Lightning configuration section if not exists
            if "agent_lightning" not in config:
                config["agent_lightning"] = {}
                
            config["agent_lightning"].update({
                "enabled": True,
                "integration_time": datetime.now().isoformat(),
                "rules_count": len(brp_rules.get("new_rules", [])),
                "rules_source": "trace_analysis",
                "sigma_rules_dir": "sigma_rules/agent_lightning_*.yml",
                "auto_update": True,
                "update_frequency": "daily"
            })
            
            # Save updated config
            with open(self.brp_config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                
            print(f"✅ Updated BRP configuration: {self.brp_config_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating BRP config: {e}")
            return False
    
    def create_projectx_integration(self, projectx_monitors):
        """Create ProjectX monitoring integration"""
        print("\n👁️ Creating ProjectX monitoring integration...")
        
        projectx_config = {
            "agent_lightning_monitors": {
                "enabled": True,
                "integration_time": datetime.now().isoformat(),
                "monitors": projectx_monitors.get("new_monitors", []),
                "alert_thresholds": projectx_monitors.get("alert_thresholds", {}),
                "monitoring_categories": projectx_monitors.get("monitoring_categories", {})
            }
        }
        
        # Save ProjectX configuration
        projectx_config_file = os.path.join(self.brp_config_dir, "projectx_agent_lightning.json")
        
        with open(projectx_config_file, 'w') as f:
            json.dump(projectx_config, f, indent=2)
            
        print(f"✅ ProjectX monitoring configuration saved: {projectx_config_file}")
        
        # Create integration script for ProjectX
        integration_script = self._create_projectx_integration_script(projectx_monitors)
        script_file = os.path.join(self.brp_config_dir, "integrate_with_projectx.py")
        
        with open(script_file, 'w') as f:
            f.write(integration_script)
            
        os.system(f"chmod +x {script_file}")
        print(f"📜 ProjectX integration script created: {script_file}")
        
        return projectx_config_file
    
    def _create_projectx_integration_script(self, projectx_monitors):
        """Create script to integrate with ProjectX"""
        return '''#!/usr/bin/env python3.10
"""
Integrate Agent Lightning monitors with ProjectX
"""

import json
import os
import sys
from pathlib import Path

def integrate_with_projectx():
    """Integrate Agent Lightning monitors with ProjectX"""
    
    print("🔗 Integrating Agent Lightning monitors with ProjectX...")
    
    # ProjectX configuration path
    projectx_config_path = "/Users/kaseymarcelle/ProjectX/config"
    monitors_file = "config/brp/projectx_agent_lightning.json"
    
    if not os.path.exists(monitors_file):
        print(f"❌ Monitors file not found: {monitors_file}")
        return False
        
    try:
        with open(monitors_file, 'r') as f:
            monitors_config = json.load(f)
            
        # Create ProjectX monitors directory if it doesn't exist
        projectx_monitors_dir = os.path.join(projectx_config_path, "monitors")
        os.makedirs(projectx_monitors_dir, exist_ok=True)
        
        # Save individual monitor files
        monitors = monitors_config.get("agent_lightning_monitors", {}).get("monitors", [])
        
        for monitor in monitors:
            monitor_id = monitor.get("monitor_id", "unknown")
            monitor_file = os.path.join(projectx_monitors_dir, f"{monitor_id}.json")
            
            with open(monitor_file, 'w') as f:
                json.dump(monitor, f, indent=2)
                
        print(f"✅ Created {len(monitors)} monitor files in {projectx_monitors_dir}")
        
        # Create integration summary
        summary = {
            "integration_time": monitors_config.get("agent_lightning_monitors", {}).get("integration_time"),
            "total_monitors": len(monitors),
            "source": "Agent Lightning Trace Analysis"
        }
        
        summary_file = os.path.join(projectx_monitors_dir, "integration_summary.json")
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
            
        print(f"📋 Integration summary saved: {summary_file}")
        
        # Instructions for ProjectX
        print("\n🎯 NEXT STEPS FOR PROJECTX INTEGRATION:")
        print("1. Restart ProjectX to load new monitors")
        print("2. Verify monitors are active in ProjectX dashboard")
        print("3. Test monitor alerts with simulated agent behavior")
        print("4. Review alert thresholds and adjust as needed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error integrating with ProjectX: {e}")
        return False

if __name__ == "__main__":
    success = integrate_with_projectx()
    sys.exit(0 if success else 1)
'''
    
    def create_verification_script(self):
        """Create script to verify BRP rule integration"""
        verification_script = '''#!/bin/bash
# 🧪 VERIFY AGENT LIGHTNING BRP INTEGRATION

echo "================================================================"
echo "🧪 VERIFYING AGENT LIGHTNING BRP INTEGRATION"
echo "================================================================"

# Colors
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
RED='\\033[0;31m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

BRP_CONFIG="config/brp"
SIGMA_RULES="$BRP_CONFIG/sigma_rules"
PROJECTX_CONFIG="$BRP_CONFIG/projectx_agent_lightning.json"

echo -e "${YELLOW}🔍 Step 1: Check BRP Configuration${NC}"
echo ""

if [ -f "$BRP_CONFIG/config.yaml" ]; then
    echo -e "${GREEN}✅ BRP config file exists${NC}"
    
    # Check for Agent Lightning section
    if grep -q "agent_lightning" "$BRP_CONFIG/config.yaml"; then
        echo -e "${GREEN}✅ Agent Lightning section found in BRP config${NC}"
    else
        echo -e "${RED}❌ Agent Lightning section NOT found in BRP config${NC}"
    fi
else
    echo -e "${RED}❌ BRP config file not found${NC}"
fi

echo ""
echo -e "${YELLOW}🔍 Step 2: Check Sigma Rules${NC}"
echo ""

if [ -d "$SIGMA_RULES" ]; then
    RULE_COUNT=$(find "$SIGMA_RULES" -name "agent_lightning_*.yml" | wc -l)
    echo -e "${GREEN}✅ Sigma rules directory exists${NC}"
    echo -e "${BLUE}📊 Found $RULE_COUNT Agent Lightning Sigma rules${NC}"
    
    if [ $RULE_COUNT -gt 0 ]; then
        echo "   Sample rules:"
        find "$SIGMA_RULES" -name "agent_lightning_*.yml" | head -3 | while read rule; do
            rule_name=$(basename "$rule")
            echo -e "   • $rule_name"
        done
    fi
else
    echo -e "${RED}❌ Sigma rules directory not found${NC}"
fi

echo ""
echo -e "${YELLOW}🔍 Step 3: Check ProjectX Integration${NC}"
echo ""

if [ -f "$PROJECTX_CONFIG" ]; then
    echo -e "${GREEN}✅ ProjectX configuration exists${NC}"
    
    MONITOR_COUNT=$(python3 -c "
import json
try:
    with open('$PROJECTX_CONFIG', 'r') as f:
        data = json.load(f)
    monitors = data.get('agent_lightning_monitors', {}).get('monitors', [])
    print(len(monitors))
except:
    print(0)
")
    
    echo -e "${BLUE}📊 Found $MONITOR_COUNT ProjectX monitors${NC}"
else
    echo -e "${RED}❌ ProjectX configuration not found${NC}"
fi

echo ""
echo -e "${YELLOW}🔍 Step 4: System Integration Status${NC}"
echo ""

echo -e "${BLUE}📋 INTEGRATION SUMMARY:${NC}"
echo "   • BRP Configuration: $( [ -f "$BRP_CONFIG/config.yaml" ] && echo "✅" || echo "❌" )"
echo "   • Sigma Rules: $( [ $RULE_COUNT -gt 0 ] && echo "✅ ($RULE_COUNT rules)" || echo "❌" )"
echo "   • ProjectX Monitors: $( [ -f "$PROJECTX_CONFIG" ] && echo "✅ ($MONITOR_COUNT monitors)" || echo "❌" )"

echo ""
echo -e "${YELLOW}🎯 NEXT STEPS:${NC}"
echo "1. Restart BRP service to load new rules"
echo "2. Test Sigma rules with simulated agent behavior"
echo "3. Integrate ProjectX monitors with ProjectX server"
echo "4. Monitor system for safety rule effectiveness"

echo ""
echo -e "${GREEN}================================================================"
echo "🧪 VERIFICATION COMPLETE"
echo "================================================================"
echo -e "${NC}"
'''
        
        script_file = "verify_brp_integration.sh"
        with open(script_file, 'w') as f:
            f.write(verification_script)
            
        os.system(f"chmod +x {script_file}")
        print(f"🧪 Verification script created: {script_file}")
        return script_file
    
    def run(self):
        """Run the complete integration process"""
        print("=" * 80)
        print("🔗 INTEGRATING AGENT LIGHTNING SAFETY RULES WITH BRP")
        print("=" * 80)
        
        # Step 1: Load generated rules
        print("\n1. 📂 Loading generated safety rules...")
        rules_data = self.load_generated_rules()
        
        if not rules_data:
            print("❌ Failed to load rules. Exiting.")
            return False
            
        brp_rules = rules_data["brp_rules"]
        projectx_monitors = rules_data["projectx_monitors"]
        
        # Step 2: Convert to Sigma rules
        print("\n2. 🔄 Converting to Sigma rules...")
        sigma_rules = self.convert_to_sigma_rules(brp_rules)
        
        if not sigma_rules:
            print("❌ No Sigma rules generated. Exiting.")
            return False
            
        # Step 3: Save Sigma rules
        print("\n3. 💾 Saving Sigma rules...")
        self.save_sigma_rules(sigma_rules)
        
        # Step 4: Update BRP configuration
        print("\n4. ⚙️ Updating BRP configuration...")
        self.update_brp_config(brp_rules)
        
        # Step 5: Create ProjectX integration
        print("\n5. 👁️ Creating ProjectX integration...")
        self.create_projectx_integration(projectx_monitors)
        
        # Step 6: Create verification script
        print("\n6. 🧪 Creating verification script...")
        verification_script = self.create_verification_script()
        
        print("\n" + "=" * 80)
        print("🎉 BRP SAFETY RULE INTEGRATION COMPLETE!")
        print("=" * 80)
        
        print("\n📋 INTEGRATION SUMMARY:")
        print(f"   • Sigma rules created: {len(sigma_rules)}")
        print(f"   • BRP configuration updated")
        print(f"   • ProjectX monitors configured")
        print(f"   • Verification script: {verification_script}")
        
        print("\n🚀 NEXT STEPS:")
        print("   1. Run verification script: ./verify_brp_integration.sh")
        print("   2. Restart BRP service to load new rules")
        print("   3. Test rules with simulated agent behavior")
        print("   4. Monitor system for safety improvements")
        
        print("\n🎯 VALUE OF INTEGRATION:")
        print("   • Proactive safety from actual agent behavior")
        print("   • Data-driven rule creation (not guesswork)")
        print("   • Continuous safety evolution as agents learn")
        print("   • Early warning system from ProjectX monitoring")
        
        print("\n📈 AGENT LIGHTNING ROI:")
        print("   • Traces provide visibility into agent behavior")
        print("   • Patterns reveal safety gaps before incidents")
        print("   • Enables continuous safety improvement")
        print("   • Turns agent learning into safety learning")
        print("=" * 80)
        
        return True

def main():
    """Main function"""
    integrator = BRPSafetyRuleIntegrator()
    success = integrator.run()
    
    if success:
        print("\n✅ Integration successful!")
        print("   Run: ./verify_brp_integration.sh")
    else:
        print("\n❌ Integration failed!")
        
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())