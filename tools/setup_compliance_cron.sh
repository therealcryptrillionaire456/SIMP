#!/bin/bash
# Setup Compliance Cron Job
# Adds compliance pipeline to daily automation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "🔧 Setting up daily compliance cron job..."

# Compliance runs at 3:00 AM daily (after Graphify at 2:00 and Briefs at 2:30)
CRON_LINE_COMPLIANCE="0 3 * * * cd '$REPO_ROOT' && bash tools/generate_daily_compliance.sh >> logs/compliance_cron.log 2>&1"

# Remove existing compliance cron if present
(crontab -l 2>/dev/null | grep -v "generate_daily_compliance.sh") | crontab -

# Add new compliance cron
(crontab -l 2>/dev/null; echo "$CRON_LINE_COMPLIANCE") | crontab -

echo "✅ Daily compliance cron job added!"
echo ""
echo "📅 Complete Daily Schedule:"
echo "   2:00 AM: Graphify updates knowledge graph"
echo "   2:30 AM: Brief generator creates architecture briefs"
echo "   3:00 AM: Compliance pipeline maps requirements"
echo ""
echo "📁 Output directories:"
echo "   .graphify/     - Knowledge graph"
echo "   briefs/        - Architecture briefs"
echo "   compliance_reports/ - Compliance reports"
echo "   logs/          - Log files"
echo ""
echo "🔍 To view cron jobs:"
echo "   crontab -l"
echo ""
echo "🚀 To run manually:"
echo "   bash tools/generate_daily_compliance.sh"
echo ""
echo "📊 To check latest compliance reports:"
echo "   ls -la compliance_reports/latest*"
