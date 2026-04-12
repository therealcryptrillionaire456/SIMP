#!/bin/bash
# Setup Daily Briefs Cron Job
# Adds brief generation to the existing Graphify daily pipeline

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "🔧 Setting up daily briefs cron job..."

# Check if Graphify cron already exists
CRON_LINE_GRAPHIFY="0 2 * * * cd '$REPO_ROOT' && bash tools/graphify_simp_final.sh >> logs/graphify_cron.log 2>&1"
CRON_LINE_BRIEFS="30 2 * * * cd '$REPO_ROOT' && bash tools/generate_daily_briefs.sh >> logs/briefs_cron.log 2>&1"

# Remove existing briefs cron if present
(crontab -l 2>/dev/null | grep -v "generate_daily_briefs.sh") | crontab -

# Add new briefs cron (30 minutes after Graphify)
(crontab -l 2>/dev/null; echo "$CRON_LINE_BRIEFS") | crontab -

echo "✅ Daily briefs cron job added!"
echo ""
echo "📅 Cron schedule:"
echo "   Graphify: 2:00 AM daily"
echo "   Briefs:   2:30 AM daily"
echo ""
echo "📁 Output directories:"
echo "   briefs/     - Architecture briefs"
echo "   onboarding/ - Onboarding packs"
echo "   logs/       - Log files"
echo ""
echo "🔍 To view cron jobs:"
echo "   crontab -l"
echo ""
echo "🚀 To run manually:"
echo "   bash tools/generate_daily_briefs.sh"
echo ""
echo "📊 To check latest briefs:"
echo "   ls -la briefs/latest*"
echo "   ls -la onboarding/latest*"
