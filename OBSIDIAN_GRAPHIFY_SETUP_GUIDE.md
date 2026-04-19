# Obsidian + Graphify Integration Setup Guide

## 📋 **Overview**

This guide explains how to set up and use the Obsidian documentation system with Graphify visualization in the SIMP ecosystem. The system provides automated documentation synchronization, visual architecture diagrams, and intelligent knowledge management.

## 🚀 **Quick Start**

### **1. Initial Setup**
```bash
cd /Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp

# Run the integration script
python3.10 integrate_obsidian_graphify.py --sync

# Set up daily automatic updates
python3.10 integrate_obsidian_graphify.py --setup-cron
```

### **2. Open in Obsidian**
```bash
# Open the documentation vault in Obsidian
open /Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs
```

### **3. View Visualizations**
```bash
# Check generated diagrams
ls -la /Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs/Visualizations/System_Graphs/generated/
```

## 📁 **Directory Structure**

```
SIMP System (Primary)/
├── integrate_obsidian_graphify.py      # Main integration script
├── OBSIDIAN_GRAPHIFY_SETUP_GUIDE.md    # This guide
├── OBSIDIAN_GRAPHIFY_INTEGRATION_COMPLETE.md  # Completion report
└── tools/
    └── obsidian_daily_sync.sh          # Daily sync script (auto-generated)

Obsidian Documentation System/
├── .obsidian/                          # Obsidian configuration
│   ├── core-plugins.json
│   ├── app.json
│   └── plugins/obsidian-git/           # Git integration
├── sync_with_simp.py                   # Main sync script
├── analyze_simp_structure.py           # Code analyzer
├── update_documentation.py             # Documentation updater
├── generate_graphs.py                  # Diagram generator
├── INDEX.md                            # Navigation hub
├── SETUP_GUIDE.md                      # Installation guide
├── PROJECT_SUMMARY.md                  # Project report
├── README.md                           # Main documentation
└── Various documentation directories...
```

## 🔧 **Installation Steps**

### **Step 1: Verify Prerequisites**
```bash
# Check Python version
python3.10 --version

# Check for required packages
pip3 install graphviz pydot

# Check if Obsidian is installed
# Download from: https://obsidian.md
```

### **Step 2: Initial Synchronization**
```bash
cd /Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp

# Run initial sync
python3.10 integrate_obsidian_graphify.py --sync

# This will:
# 1. Analyze SIMP codebase structure
# 2. Generate documentation files
# 3. Create architecture diagrams
# 4. Set up cross-references
```

### **Step 3: Configure Obsidian**
1. Open Obsidian app
2. Click "Open folder as vault"
3. Select: `/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs`
4. Enable recommended plugins:
   - **Graph view** (for visualization)
   - **Backlinks** (for navigation)
   - **Daily notes** (for logging)
   - **Templates** (for consistency)

### **Step 4: Set Up Automation**
```bash
# Create daily sync cron job
python3.10 integrate_obsidian_graphify.py --setup-cron

# Manual cron setup (if needed)
crontab -e
# Add: 0 9 * * * /Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/tools/obsidian_daily_sync.sh
```

## 🎯 **Daily Usage**

### **Manual Synchronization**
```bash
# Full sync (recommended after major changes)
python3.10 integrate_obsidian_graphify.py --sync

# Quick sync (documentation only)
cd /Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs
python3.10 sync_with_simp.py
```

### **Viewing Documentation**
1. **Obsidian App**: Open the vault for interactive browsing
2. **Graph View**: Click the graph icon to see system relationships
3. **Search**: Use Ctrl+P to find documentation quickly
4. **Backlinks**: See what links to each document

### **Generating Visualizations**
```bash
# Manual diagram generation
cd /Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs/Visualizations/System_Graphs
python3.10 generate_graphs.py

# Available diagrams:
# - core_architecture.dot → System architecture
# - agent_interactions.dot → Agent communication
# - data_flow.dot → Information flow
```

## 📊 **Features and Benefits**

### **Automated Documentation**
- **Code Analysis**: Automatic extraction of classes, functions, and dependencies
- **Documentation Generation**: Creates Markdown files from code structure
- **Cross-referencing**: Automatic links between related topics
- **Version Tracking**: Documentation evolves with code

### **Visualization System**
- **Architecture Diagrams**: Visual representation of system components
- **Dependency Graphs**: Module relationships and dependencies
- **Agent Networks**: How agents interact and communicate
- **Data Flow**: Information movement through the system

### **Knowledge Management**
- **Graph View**: Interactive visualization of documentation relationships
- **Backlinks**: Discover connections between topics
- **Templates**: Consistent documentation format
- **Search**: Full-text search across all documentation

## 🔍 **Quality Assurance**

### **Automatic Checks**
The integration includes quality checks:
- **Broken Links**: Detection of invalid references
- **Missing Documentation**: Identification of undocumented modules
- **Content Freshness**: Check for outdated documentation
- **Completeness**: Verification of documentation coverage

### **Reports**
```bash
# Generate quality report
python3.10 integrate_obsidian_graphify.py --report

# View sync reports
ls -la /Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/reports/obsidian_graphify/
```

## 🛠 **Troubleshooting**

### **Common Issues**

#### **Issue: Sync script fails**
```bash
# Check Python version
python3.10 --version

# Check dependencies
pip3 install -r /Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs/requirements.txt

# Check file permissions
ls -la /Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs/sync_with_simp.py
```

#### **Issue: Diagrams not generating**
```bash
# Check Graphviz installation
which dot
dot -V

# Install Graphviz
# macOS: brew install graphviz
# Ubuntu: sudo apt-get install graphviz
```

#### **Issue: Obsidian plugins not working**
1. Open Obsidian Settings → Community plugins
2. Ensure plugins are enabled
3. Check for updates
4. Restart Obsidian

### **Logs and Debugging**
```bash
# View sync logs
tail -f /Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/logs/obsidian_sync_*.log

# Debug mode
cd /Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs
python3.10 sync_with_simp.py --verbose
```

## 🔄 **Integration with SIMP Workflow**

### **Development Workflow**
1. **Code Changes**: Make changes to SIMP codebase
2. **Documentation Sync**: Run sync to update documentation
3. **Review**: Check generated documentation and diagrams
4. **Commit**: Include documentation updates in commits

### **Operational Workflow**
1. **Daily Sync**: Automatic morning documentation update
2. **Quality Check**: Review sync reports
3. **Issue Tracking**: Address documentation gaps
4. **Knowledge Sharing**: Use documentation for onboarding

### **CI/CD Integration**
```yaml
# Example GitHub Actions workflow
name: Documentation Sync
on:
  push:
    branches: [ main ]
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM

jobs:
  sync-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Sync Documentation
        run: |
          cd /path/to/simp
          python3.10 integrate_obsidian_graphify.py --sync
```

## 📈 **Advanced Configuration**

### **Custom Configuration**
Create `obsidian_config.json`:
```json
{
  "auto_sync": true,
  "generate_diagrams": true,
  "update_index": true,
  "quality_checks": true,
  "backup_before_sync": true,
  "exclude_patterns": ["*.pyc", "__pycache__"],
  "include_patterns": ["*.py", "*.md", "*.json"],
  "diagram_formats": ["png", "svg", "pdf"]
}
```

Use custom config:
```bash
python3.10 integrate_obsidian_graphify.py --sync --config obsidian_config.json
```

### **Custom Templates**
Edit templates in:
```
/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs/.obsidian/templates/
```

### **Plugin Configuration**
Edit:
```
/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs/.obsidian/core-plugins.json
/Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs/.obsidian/app.json
```

## 🎓 **Training and Onboarding**

### **For New Team Members**
1. **Read this guide** for setup instructions
2. **Open Obsidian vault** to explore documentation
3. **Use Graph view** to understand system architecture
4. **Search documentation** when working on tasks

### **For Documentation Contributors**
1. **Follow templates** for consistent formatting
2. **Use backlinks** to connect related topics
3. **Update diagrams** when architecture changes
4. **Run sync regularly** to keep documentation current

### **For System Operators**
1. **Check daily sync reports** for issues
2. **Use runbooks** for operational procedures
3. **Update documentation** when processes change
4. **Train team members** using documentation

## 📞 **Support and Maintenance**

### **Regular Maintenance Tasks**
- **Daily**: Check sync reports, address any issues
- **Weekly**: Review documentation quality, update as needed
- **Monthly**: Audit documentation coverage, identify gaps
- **Quarterly**: Update diagrams for major architecture changes

### **Getting Help**
- **Documentation Issues**: Check sync logs and reports
- **Technical Problems**: Review troubleshooting section
- **Feature Requests**: Submit via SIMP issue tracker
- **Training Needs**: Contact system administrator

### **Backup and Recovery**
```bash
# Manual backup
cp -r /Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs \
      /Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs_backup_$(date +%Y%m%d)

# Restore from backup
cp -r /Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs_backup_20240414 \
      /Users/kaseymarcelle/stray_goose/SIMP-obsidian-docs
```

## 🏁 **Conclusion**

The Obsidian + Graphify integration provides a powerful documentation and visualization system for the SIMP ecosystem. With automated synchronization, visual architecture diagrams, and intelligent knowledge management, it significantly improves:

1. **Developer Productivity**: Faster onboarding and better understanding
2. **System Reliability**: Clear documentation reduces errors
3. **Knowledge Retention**: Institutional knowledge preserved
4. **Operational Excellence**: Runbooks and procedures readily available

**The system is now fully integrated and ready for daily use by the SIMP team.**

---

**Last Updated**: $(date)  
**Maintenance Contact**: Goose Agent (SIMP Builder)  
**Status**: ✅ **PRODUCTION READY**