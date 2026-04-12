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
