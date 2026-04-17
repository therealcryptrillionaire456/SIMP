#!/usr/bin/env python3
"""
Simple test for Sovereign Self Compiler v2.
Tests basic functionality without requiring external dependencies.
"""

import json
import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_config_loading():
    """Test that configuration loads correctly."""
    print("Testing configuration loading...")
    
    config_path = Path(__file__).parent / "config" / "self_compiler_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    assert "version" in config
    assert config["version"] == "2.0.0"
    assert "recursion" in config
    assert "execution" in config
    assert "evaluation" in config
    assert "promotion" in config
    
    print(f"✓ Configuration loaded: {config['version']}")
    return True

def test_schema_validation():
    """Test that schemas are valid JSON Schema."""
    print("\nTesting schema validation...")
    
    # Test prompt task schema
    prompt_schema_path = Path(__file__).parent / "schemas" / "prompt_task.schema.json"
    with open(prompt_schema_path) as f:
        prompt_schema = json.load(f)
    
    assert prompt_schema["title"] == "PromptTask"
    assert "properties" in prompt_schema
    assert "prompt_id" in prompt_schema["properties"]
    
    # Test execution result schema
    exec_schema_path = Path(__file__).parent / "schemas" / "execution_result.schema.json"
    with open(exec_schema_path) as f:
        exec_schema = json.load(f)
    
    assert exec_schema["title"] == "ExecutionResult"
    assert "properties" in exec_schema
    assert "execution_id" in exec_schema["properties"]
    
    print("✓ Schemas are valid JSON Schema")
    return True

def test_module_imports():
    """Test that all modules can be imported."""
    print("\nTesting module imports...")
    
    modules = [
        "inventory",
        "planner", 
        "prompt_compiler",
        "executor",
        "evaluator",
        "promoter",
        "trace_logger",
        "cli"
    ]
    
    for module_name in modules:
        try:
            module = __import__(f"src.{module_name}", fromlist=[""])
            print(f"  ✓ {module_name}.py imports successfully")
        except ImportError as e:
            print(f"  ✗ Failed to import {module_name}: {e}")
            return False
    
    print("✓ All modules import successfully")
    return True

def test_directory_structure():
    """Test that required directories exist."""
    print("\nTesting directory structure...")
    
    base_dir = Path(__file__).parent
    required_dirs = [
        base_dir / "config",
        base_dir / "schemas",
        base_dir / "src",
        base_dir / "traces",
        base_dir / "staging",
        base_dir / "docs"
    ]
    
    for dir_path in required_dirs:
        if dir_path.exists() and dir_path.is_dir():
            print(f"  ✓ Directory exists: {dir_path.name}")
        else:
            print(f"  ✗ Missing directory: {dir_path.name}")
            return False
    
    print("✓ All required directories exist")
    return True

def test_documentation():
    """Test that documentation files exist."""
    print("\nTesting documentation...")
    
    base_dir = Path(__file__).parent
    required_docs = [
        base_dir / "INVENTORY_REPORT.md",
        base_dir / "LEGACY_POSTMORTEM.md",
        base_dir / "ARCHITECTURE.md",
        base_dir / "docs" / "RUNBOOK.md",
        base_dir / "FINAL_REPORT.md"
    ]
    
    for doc_path in required_docs:
        if doc_path.exists() and doc_path.is_file():
            size_kb = doc_path.stat().st_size / 1024
            print(f"  ✓ Documentation exists: {doc_path.name} ({size_kb:.1f} KB)")
        else:
            print(f"  ✗ Missing documentation: {doc_path.name}")
            return False
    
    print("✓ All documentation exists")
    return True

def test_example_prompt():
    """Test creating an example prompt."""
    print("\nTesting example prompt creation...")
    
    example_prompt = {
        "prompt_id": "test_prompt_001",
        "goal_id": "test_goal_001",
        "cycle_number": 1,
        "task_summary": "Create a simple test module for the self-compiler",
        "prompt_text": "Write a Python module called test_hello.py that prints 'Hello from self-compiler v2!'",
        "expected_artifacts": ["test_hello.py"],
        "execution_mode": "python",
        "evaluation_requirements": {
            "schema_validation": True,
            "syntax_check": True,
            "policy_check": "basic"
        },
        "max_recursion_depth": 1
    }
    
    # Save example prompt
    example_path = Path(__file__).parent / "staging" / "example_prompt.json"
    example_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(example_path, 'w') as f:
        json.dump(example_prompt, f, indent=2)
    
    print(f"✓ Example prompt created: {example_path}")
    return True

def test_cli_help():
    """Test that CLI help works."""
    print("\nTesting CLI help...")
    
    import subprocess
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0 and "Sovereign Self Compiler v2" in result.stdout:
            print("✓ CLI help works correctly")
            return True
        else:
            print(f"✗ CLI help failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ CLI test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Sovereign Self Compiler v2 - System Test")
    print("=" * 60)
    
    tests = [
        test_config_loading,
        test_schema_validation,
        test_module_imports,
        test_directory_structure,
        test_documentation,
        test_example_prompt,
        test_cli_help
    ]
    
    results = []
    for test_func in tests:
        try:
            success = test_func()
            results.append((test_func.__name__, success))
        except Exception as e:
            print(f"✗ {test_func.__name__} raised exception: {e}")
            results.append((test_func.__name__, False))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - System is ready!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install psutil requests")
        print("2. Run a test session: python -m src.cli run 'Test goal' --cycles 1")
        print("3. Check traces: python -m src.cli traces --limit 5")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Review issues above")
        return 1

if __name__ == "__main__":
    sys.exit(main())