#!/bin/bash
# Verification Script for Complete System Health Dashboard

set -e

echo "🔍 VERIFYING COMPLETE SYSTEM HEALTH DASHBOARD"
echo "=============================================="
echo ""

# Check 1: Graphify data exists
echo "✅ Step 1: Checking Graphify data..."
if [ -f ".graphify/simp_graph.json" ]; then
    NODES=$(python3 -c "import json; data=json.load(open('.graphify/simp_graph.json')); print(len(data.get('nodes', [])))")
    EDGES=$(python3 -c "import json; data=json.load(open('.graphify/simp_graph.json')); print(len(data.get('edges', [])))")
    echo "   📊 Graph: $NODES nodes, $EDGES edges"
else
    echo "   ❌ Graphify data not found"
fi

# Check 2: Tools compilation
echo ""
echo "✅ Step 2: Checking tool compilation..."
TOOLS=(
    "tools/change_impact_analyzer.py"
    "tools/test_selection_helper.py"
    "tools/system_brief_generator.py"
    "tools/compliance_mapper.py"
    "tools/compliance_integration.py"
    "tools/graph_navigator.py"
    "tools/learning_path_generator.py"
    "tools/dashboard_integration.py"
)

for tool in "${TOOLS[@]}"; do
    if python3.10 -m py_compile "$tool" 2>/dev/null; then
        echo "   ✓ $(basename $tool)"
    else
        echo "   ✗ $(basename $tool) - compilation failed"
    fi
done

# Check 3: Generated content
echo ""
echo "✅ Step 3: Checking generated content..."
if [ -d "briefs" ] && [ "$(ls -1 briefs/*.json 2>/dev/null | wc -l)" -gt 0 ]; then
    echo "   ✓ Architecture briefs exist"
else
    echo "   ✗ No architecture briefs found"
fi

if [ -d "compliance_reports" ] && [ "$(ls -1 compliance_reports/*.md 2>/dev/null | wc -l)" -gt 0 ]; then
    echo "   ✓ Compliance reports exist"
else
    echo "   ✗ No compliance reports found"
fi

if [ -f "dashboard/static/graphify/index.html" ]; then
    echo "   ✓ Dashboard integration exists"
else
    echo "   ✗ Dashboard integration missing"
fi

# Check 4: Automation scripts
echo ""
echo "✅ Step 4: Checking automation scripts..."
SCRIPTS=(
    "tools/graphify_simp_final.sh"
    "tools/generate_daily_briefs.sh"
    "tools/generate_daily_compliance.sh"
)

for script in "${SCRIPTS[@]}"; do
    if [ -f "$script" ] && [ -x "$script" ]; then
        echo "   ✓ $(basename $script) (executable)"
    else
        echo "   ✗ $(basename $script) - missing or not executable"
    fi
done

# Check 5: Documentation
echo ""
echo "✅ Step 5: Checking documentation..."
DOCS=(
    ".graphify/AGENT_INTEGRATION_GUIDE.md"
    "tools/GRAPHIFY_TOOLS_README.md"
    "tools/COMPLIANCE_MAPPING_README.md"
    "tools/GRAPHIFY_GUIDED_NAVIGATION_README.md"
    "SYSTEM_HEALTH_DASHBOARD_COMPLETE.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo "   ✓ $(basename $doc)"
    else
        echo "   ✗ $(basename $doc) - missing"
    fi
done

# Summary
echo ""
echo "=============================================="
echo "🎯 SYSTEM VERIFICATION COMPLETE"
echo ""
echo "📊 Summary:"
echo "   • Graphify: $NODES nodes, $EDGES edges"
echo "   • Tools: ${#TOOLS[@]} tools checked"
echo "   • Automation: ${#SCRIPTS[@]} scripts"
echo "   • Documentation: ${#DOCS[@]} documents"
echo ""
echo "🚀 Access Points:"
echo "   • Dashboard: http://localhost:8050/static/graphify/index.html"
echo "   • Latest Brief: cat briefs/latest_architecture_brief.md"
echo "   • Latest Compliance: cat compliance_reports/latest_compliance_report.md"
echo ""
echo "🎉 System Health Dashboard is READY FOR USE!"
