#!/bin/bash
# Demo script for Sovereign Self Compiler v2 Phase 2 Features
# This script demonstrates all the new Phase 2 features

echo "================================================"
echo "Sovereign Self Compiler v2 - Phase 2 Demo"
echo "================================================"
echo ""

# Change to the self_compiler_v2 directory
cd "$(dirname "$0")" || exit 1

echo "1. 📋 Showing available commands..."
echo "----------------------------------------"
python3.10 src/cli.py --help
echo ""

echo "2. 🔄 Testing Continuous Mode help..."
echo "----------------------------------------"
python3.10 src/cli.py run --help | grep -A2 -B2 "continuous"
echo ""

echo "3. 💾 Testing Session Management..."
echo "----------------------------------------"
echo "Listing sessions (should be empty initially):"
python3.10 src/cli.py sessions list
echo ""

echo "4. 📊 Testing Enhanced Reporting help..."
echo "----------------------------------------"
python3.10 src/cli.py enhanced-report --help
echo ""

echo "5. 👁️  Testing Real-time Monitoring help..."
echo "----------------------------------------"
python3.10 src/cli.py monitor --help
echo ""

echo "6. 🧪 Testing Stress Test Integration..."
echo "----------------------------------------"
if python3.10 -c "import sys; sys.path.insert(0, '.'); from self_compiler_v2.src.cli import WATCHTOWER_AVAILABLE; print('Watchtower available:', WATCHTOWER_AVAILABLE)" 2>/dev/null; then
    echo "Stress test feature is available"
    python3.10 src/cli.py stress-test --help 2>/dev/null || echo "Stress test help not available (module may not be loaded)"
else
    echo "Note: Watchtower stress test requires watchtower_stress_test.py in SIMP directory"
fi
echo ""

echo "7. 🏗️  Testing CLI Structure..."
echo "----------------------------------------"
echo "Checking if sessions directory exists:"
if [ -d "sessions" ]; then
    echo "✅ sessions/ directory exists"
else
    echo "⚠️  sessions/ directory not found (will be created on first run)"
fi
echo ""

echo "8. 📁 Directory Structure..."
echo "----------------------------------------"
echo "Current directory structure:"
ls -la | grep -E "(sessions|config|src|docs|staging|traces)"
echo ""

echo "================================================"
echo "Demo Complete!"
echo "================================================"
echo ""
echo "To use Phase 2 features:"
echo "1. Run continuous mode: python3.10 src/cli.py run 'Your goal' --continuous"
echo "2. Manage sessions: python3.10 src/cli.py sessions list"
echo "3. Generate reports: python3.10 src/cli.py enhanced-report <session_id>"
echo "4. Monitor live: python3.10 src/cli.py monitor <session_id>"
echo ""
echo "For detailed documentation, see docs/PHASE2_FEATURES.md"