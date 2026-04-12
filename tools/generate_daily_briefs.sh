#!/bin/bash
# Daily Brief Generation Script
# Runs after Graphify updates to generate fresh architecture briefs
# and onboarding packs.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "🚀 Starting daily brief generation..."
echo "📅 Date: $(date)"
echo "📁 Repository: $REPO_ROOT"

# Create directories
mkdir -p briefs
mkdir -p onboarding
mkdir -p logs

LOG_FILE="logs/daily_brief_$(date +%Y%m%d).log"
echo "📝 Logging to: $LOG_FILE"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check if Graphify data exists
if [ ! -f ".graphify/simp_graph.json" ]; then
    log "❌ Graphify data not found. Running Graphify first..."
    if [ -f "tools/graphify_simp_final.sh" ]; then
        bash tools/graphify_simp_final.sh 2>&1 | tee -a "$LOG_FILE"
    else
        log "❌ Graphify script not found. Exiting."
        exit 1
    fi
fi

# Generate architecture brief
log "🎯 Generating architecture brief..."
python3.10 tools/system_brief_generator.py --brief --output-dir briefs 2>&1 | tee -a "$LOG_FILE"

# Generate onboarding packs
log "🎯 Generating developer onboarding pack..."
python3.10 tools/system_brief_generator.py --onboarding developer --output-dir onboarding 2>&1 | tee -a "$LOG_FILE"

log "🎯 Generating agent onboarding pack..."
python3.10 tools/system_brief_generator.py --onboarding agent --output-dir onboarding 2>&1 | tee -a "$LOG_FILE"

log "🎯 Generating operator onboarding pack..."
python3.10 tools/system_brief_generator.py --onboarding operator --output-dir onboarding 2>&1 | tee -a "$LOG_FILE"

# Generate summary report
log "📊 Generating summary report..."
cat > briefs/daily_summary_$(date +%Y%m%d).md << SUMMARY
# Daily Brief Summary - $(date +%Y-%m-%d)

## 📊 Generation Statistics
- **Generated at**: $(date)
- **Architecture briefs**: $(find briefs -name "*$(date +%Y%m%d)*" -type f | wc -l)
- **Onboarding packs**: $(find onboarding -name "*$(date +%Y%m%d)*" -type f | wc -l)
- **Total files generated**: $(find briefs onboarding -name "*$(date +%Y%m%d)*" -type f | wc -l)

## 🏗️ Architecture Snapshot
Based on Graphify data from: $(stat -f "%Sm" .graphify/simp_graph.json)

### File Counts
$(python3.10 -c "
import json, os, sys
try:
    with open('.graphify/simp_graph.json', 'r') as f:
        data = json.load(f)
    nodes = data.get('nodes', [])
    files = [n for n in nodes if n.get('type') == 'file']
    modules = [n for n in nodes if n.get('type') == 'module']
    classes = [n for n in nodes if n.get('type') == 'class']
    functions = [n for n in nodes if n.get('type') == 'function']
    print(f'- Files: {len(files):,}')
    print(f'- Modules: {len(modules):,}')
    print(f'- Classes: {len(classes):,}')
    print(f'- Functions: {len(functions):,}')
    print(f'- Total Nodes: {len(nodes):,}')
    print(f'- Edges: {len(data.get(\"edges\", [])):,}')
except Exception as e:
    print(f'- Error: {e}')
")

## 📁 Generated Files

### Architecture Briefs
$(find briefs -name "*$(date +%Y%m%d)*" -type f -exec basename {} \; | sed 's/^/- /')

### Onboarding Packs
$(find onboarding -name "*$(date +%Y%m%d)*" -type f -exec basename {} \; | sed 's/^/- /')

## 🎯 Next Actions
1. Review the latest architecture brief
2. Check for new recommendations
3. Update onboarding materials if needed
4. Share insights with the team

---
*Generated automatically by SIMP Daily Brief Generator*
SUMMARY

# Create latest symlinks
log "🔗 Creating latest symlinks..."
ln -sf "$(find briefs -name "*$(date +%Y%m%d)*.json" | head -1)" briefs/latest_architecture_brief.json 2>/dev/null || true
ln -sf "$(find briefs -name "*$(date +%Y%m%d)*.md" | head -1)" briefs/latest_architecture_brief.md 2>/dev/null || true
ln -sf "$(find onboarding -name "*developer_$(date +%Y%m%d)*.md" | head -1)" onboarding/latest_developer_guide.md 2>/dev/null || true
ln -sf "$(find onboarding -name "*agent_$(date +%Y%m%d)*.md" | head -1)" onboarding/latest_agent_guide.md 2>/dev/null || true

log "✅ Daily brief generation complete!"
log "📁 Output directory: briefs/"
log "👥 Onboarding directory: onboarding/"
log "📋 Summary: briefs/daily_summary_$(date +%Y%m%d).md"

echo ""
echo "🎉 Daily briefs generated successfully!"
echo "📊 Check the latest briefs:"
echo "   ls -la briefs/latest*"
echo "   ls -la onboarding/latest*"
