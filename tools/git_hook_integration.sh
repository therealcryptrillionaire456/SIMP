#!/bin/bash
# Git Hook Integration for Graphify
# Adds pre-commit and post-commit hooks for automatic impact analysis

set -e

HOOKS_DIR=".git/hooks"
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "================================================"
echo "🔗 Git Hook Integration for Graphify"
echo "================================================"

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Not a git repository"
    exit 1
fi

# Create hooks directory if it doesn't exist
mkdir -p "$HOOKS_DIR"

# 1. Pre-commit hook: Analyze changes before committing
cat > "$HOOKS_DIR/pre-commit" << 'PRE_COMMIT'
#!/bin/bash
# Pre-commit hook for Graphify impact analysis

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
TOOLS_DIR="$REPO_ROOT/tools"
GRAPHIFY_DIR="$REPO_ROOT/.graphify"

echo "🔍 Graphify Pre-commit Analysis"
echo "================================"

# Get staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(py|md|txt|yaml|yml|json)$' || true)

if [ -z "$STAGED_FILES" ]; then
    echo "✅ No relevant files staged"
    exit 0
fi

echo "📁 Staged files: $(echo "$STAGED_FILES" | wc -l | tr -d ' ')"

# Check if Graphify is available
if [ ! -f "$TOOLS_DIR/change_impact_analyzer.py" ]; then
    echo "⚠️ Graphify tools not found, skipping analysis"
    exit 0
fi

# Run impact analysis
echo "📊 Running impact analysis..."
cd "$REPO_ROOT"

# Convert staged files to array for Python
FILE_LIST=""
for file in $STAGED_FILES; do
    FILE_LIST="$FILE_LIST \"$file\""
done

# Run analysis
python3 "$TOOLS_DIR/change_impact_analyzer.py" $FILE_LIST --depth 2 2>/dev/null || true

echo ""
echo "💡 Review the impact analysis above before committing."
echo "   To skip analysis: git commit --no-verify"
echo "================================"

exit 0
PRE_COMMIT

chmod +x "$HOOKS_DIR/pre-commit"
echo "✅ Created pre-commit hook"

# 2. Post-commit hook: Update Graphify after commit
cat > "$HOOKS_DIR/post-commit" << 'POST_COMMIT'
#!/bin/bash
# Post-commit hook for Graphify updates

REPO_ROOT="$(git rev-parse --show-toplevel)"
TOOLS_DIR="$REPO_ROOT/tools"
GRAPHIFY_DIR="$REPO_ROOT/.graphify"

echo "🔄 Graphify Post-commit Update"
echo "================================"

# Check if Graphify is available
if [ ! -f "$TOOLS_DIR/graphify_simp_final.sh" ]; then
    echo "⚠️ Graphify not available, skipping update"
    exit 0
fi

# Only update Graphify for significant commits
# Check commit message for keywords that indicate architectural changes
COMMIT_MSG=$(git log -1 --pretty=%B | head -1)

if [[ "$COMMIT_MSG" =~ (feat:|fix:|refactor:|architecture|broker|agent|simp|major) ]]; then
    echo "📈 Significant commit detected: '$COMMIT_MSG'"
    echo "🔄 Updating Graphify snapshot..."
    
    # Run in background to not block commit
    cd "$REPO_ROOT"
    nohup "$TOOLS_DIR/graphify_simp_final.sh" > /dev/null 2>&1 &
    
    echo "✅ Graphify update started in background"
    echo "   Check .graphify/ for updated architecture maps"
else
    echo "✅ Routine commit, skipping Graphify update"
fi

echo "================================"
exit 0
POST_COMMIT

chmod +x "$HOOKS_DIR/post-commit"
echo "✅ Created post-commit hook"

# 3. Prepare-commit-msg hook: Suggest tests
cat > "$HOOKS_DIR/prepare-commit-msg" << 'PREPARE_COMMIT'
#!/bin/bash
# Prepare-commit-msg hook: Suggest tests based on changes

REPO_ROOT="$(git rev-parse --show-toplevel)"
TOOLS_DIR="$REPO_ROOT/tools"
COMMIT_MSG_FILE="$1"
COMMIT_SOURCE="$2"

# Only run for normal commits, not merges or other operations
if [ "$COMMIT_SOURCE" != "message" ] && [ -n "$COMMIT_SOURCE" ]; then
    exit 0
fi

echo "🧪 Graphify Test Suggestions"
echo "================================"

# Get changed files
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.py$' || true)

if [ -z "$CHANGED_FILES" ]; then
    echo "✅ No Python files changed"
    exit 0
fi

# Check if test selection helper is available
if [ ! -f "$TOOLS_DIR/test_selection_helper.py" ]; then
    echo "⚠️ Test selection helper not found"
    exit 0
fi

echo "📁 Changed Python files: $(echo "$CHANGED_FILES" | wc -l | tr -d ' ')"

# Run test selection
cd "$REPO_ROOT"

# Convert to array for Python
FILE_LIST=""
for file in $CHANGED_FILES; do
    FILE_LIST="$FILE_LIST \"$file\""
done

# Get test suggestions
SUGGESTIONS=$(python3 "$TOOLS_DIR/test_selection_helper.py" $FILE_LIST --export 2>/dev/null || echo "{}")

if [ "$SUGGESTIONS" != "{}" ]; then
    echo "🚀 Suggested test command:"
    CMD=$(echo "$SUGGESTIONS" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('pytest_command', 'pytest'))")
    echo "   $CMD"
    
    # Add to commit message template
    if [ -f "$COMMIT_MSG_FILE" ]; then
        echo "" >> "$COMMIT_MSG_FILE"
        echo "# Suggested tests:" >> "$COMMIT_MSG_FILE"
        echo "# $CMD" >> "$COMMIT_MSG_FILE"
    fi
fi

echo "================================"
exit 0
PREPARE_COMMIT

chmod +x "$HOOKS_DIR/prepare-commit-msg"
echo "✅ Created prepare-commit-msg hook"

# 4. Create a hook management script
cat > "$TOOLS_DIR/manage_graphify_hooks.sh" << 'HOOK_MGMT'
#!/bin/bash
# Manage Graphify Git hooks

HOOKS_DIR=".git/hooks"
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"

case "$1" in
    install)
        echo "Installing Graphify Git hooks..."
        "$TOOLS_DIR/git_hook_integration.sh"
        ;;
    uninstall)
        echo "Removing Graphify Git hooks..."
        rm -f "$HOOKS_DIR/pre-commit" "$HOOKS_DIR/post-commit" "$HOOKS_DIR/prepare-commit-msg"
        echo "✅ Graphify hooks removed"
        ;;
    status)
        echo "Graphify Git hooks status:"
        if [ -f "$HOOKS_DIR/pre-commit" ]; then
            echo "✅ pre-commit: Installed"
        else
            echo "❌ pre-commit: Not installed"
        fi
        if [ -f "$HOOKS_DIR/post-commit" ]; then
            echo "✅ post-commit: Installed"
        else
            echo "❌ post-commit: Not installed"
        fi
        if [ -f "$HOOKS_DIR/prepare-commit-msg" ]; then
            echo "✅ prepare-commit-msg: Installed"
        else
            echo "❌ prepare-commit-msg: Not installed"
        fi
        ;;
    *)
        echo "Usage: $0 {install|uninstall|status}"
        exit 1
        ;;
esac
HOOK_MGMT

chmod +x "$TOOLS_DIR/manage_graphify_hooks.sh"
echo "✅ Created hook management script"

# 5. Create agent integration examples
cat > "$TOOLS_DIR/agent_integration_examples.py" << 'AGENT_EXAMPLES'
#!/usr/bin/env python3
"""
Agent Integration Examples for Graphify Tools
Examples of how agents can use Graphify for code change analysis.
"""
import subprocess
import json
from pathlib import Path

def analyze_changes_with_agent(changed_files):
    """
    Example: Agent analyzes impact of changes.
    
    Args:
        changed_files: List of file paths that changed
    
    Returns:
        Analysis results for agent to use
    """
    repo_root = Path(__file__).parent.parent
    
    # Run change impact analyzer
    cmd = [
        "python3", str(repo_root / "tools" / "change_impact_analyzer.py"),
        *changed_files,
        "--export"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {"error": result.stderr}
    except Exception as e:
        return {"error": str(e)}

def get_test_recommendations(changed_files):
    """
    Example: Agent gets test recommendations for changes.
    
    Args:
        changed_files: List of file paths that changed
    
    Returns:
        Test recommendations for agent to use
    """
    repo_root = Path(__file__).parent.parent
    
    # Run test selection helper
    cmd = [
        "python3", str(repo_root / "tools" / "test_selection_helper.py"),
        *changed_files,
        "--strategy", "smart",
        "--export"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {"error": result.stderr}
    except Exception as e:
        return {"error": str(e)}

def agent_workflow_example():
    """
    Example workflow for an agent making changes to SIMP.
    """
    print("🤖 Agent Workflow with Graphify")
    print("="*50)
    
    # Simulate agent changing some files
    changed_files = [
        "simp/server/broker.py",
        "simp/agents/kloutbotagent.py"
    ]
    
    print(f"📁 Agent is changing: {changed_files}")
    
    # 1. Analyze impact
    print("\n1. 📊 Analyzing impact...")
    impact = analyze_changes_with_agent(changed_files)
    if "error" not in impact:
        print(f"   Summary: {impact.get('summary', 'N/A')}")
        print(f"   Top impacted: {', '.join(impact.get('top_impacted_categories', []))}")
        print(f"   Action items: {len(impact.get('action_items', []))}")
    else:
        print(f"   ❌ Error: {impact['error']}")
    
    # 2. Get test recommendations
    print("\n2. 🧪 Getting test recommendations...")
    tests = get_test_recommendations(changed_files)
    if "error" not in tests:
        print(f"   Pytest command: {tests.get('pytest_command', 'N/A')}")
        print(f"   Top tests: {', '.join(tests.get('top_tests', [])[:3])}")
    else:
        print(f"   ❌ Error: {tests['error']}")
    
    # 3. Generate agent prompt
    print("\n3. 📝 Generated agent prompt:")
    prompt = f"""
    I'm making changes to: {', '.join(changed_files)}
    
    Based on Graphify analysis:
    - Impact: {impact.get('summary', 'Unknown impact')}
    - Tests to run: {tests.get('pytest_command', 'pytest')}
    - Key tests: {', '.join(tests.get('top_tests', [])[:3])}
    
    Before committing, I should:
    1. Run the suggested tests
    2. Review impacted modules
    3. Check for breaking changes
    """
    print(prompt)
    
    print("\n✅ Agent workflow complete!")
    print("="*50)

if __name__ == "__main__":
    agent_workflow_example()
AGENT_EXAMPLES

chmod +x "$TOOLS_DIR/agent_integration_examples.py"

echo ""
echo "================================================"
echo "✅ Git Hook Integration Complete!"
echo "================================================"
echo ""
echo "📋 Installed hooks:"
echo "  • pre-commit: Impact analysis before committing"
echo "  • post-commit: Graphify updates after significant commits"
echo "  • prepare-commit-msg: Test suggestions in commit messages"
echo ""
echo "🔧 Management:"
echo "  ./tools/manage_graphify_hooks.sh status"
echo "  ./tools/manage_graphify_hooks.sh uninstall"
echo ""
echo "🤖 Agent Integration Examples:"
echo "  python3 tools/agent_integration_examples.py"
echo ""
echo "🚀 Next: Test the hooks with a sample change!"
echo "================================================"
