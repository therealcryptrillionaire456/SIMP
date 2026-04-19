"""Tests for the cowork bridge — prompt builder and response format."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_bridge_script_exists():
    path = os.path.join(os.path.dirname(__file__), "..", "bin", "cowork_bridge.py")
    assert os.path.exists(path)

def test_bridge_compiles():
    import py_compile
    path = os.path.join(os.path.dirname(__file__), "..", "bin", "cowork_bridge.py")
    py_compile.compile(path, doraise=True)

def test_build_prompt_code_task():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cowork_bridge",
        os.path.join(os.path.dirname(__file__), "..", "bin", "cowork_bridge.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    prompt = mod.build_prompt({
        "intent_id": "test:123",
        "intent_type": "code_task",
        "params": {"task": "Add logging to broker.py"},
        "source_agent": "simp_router",
    })
    assert "Add logging" in prompt
    assert "code_task" in prompt

def test_launchd_dir_exists():
    path = os.path.join(os.path.dirname(__file__), "..", "launchd")
    assert os.path.exists(path)

def test_install_script_exists():
    path = os.path.join(os.path.dirname(__file__), "..", "launchd", "install.sh")
    assert os.path.exists(path)
