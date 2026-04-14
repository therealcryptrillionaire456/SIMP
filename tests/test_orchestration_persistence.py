"""
Test OrchestrationManager persistence.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from simp.orchestration.orchestration_manager import (
    OrchestrationManager,
    OrchestrationManagerConfig,
    OrchestrationPlan,
    OrchestrationStep
)


class TestOrchestrationPersistence:
    """Test OrchestrationManager persistence features."""
    
    def test_plan_serialization_deserialization(self):
        """Test that plans can be serialized and deserialized."""
        # Create a plan
        plan = OrchestrationPlan(
            plan_id="test-plan-123",
            name="Test Plan",
            description="A test plan",
            status="completed",
            created_at="2024-04-14T12:00:00Z",
            completed_at="2024-04-14T12:05:00Z",
            error=""
        )
        
        # Add steps
        step1 = OrchestrationStep(
            step_id="step-0",
            name="Step 1",
            intent_type="ping",
            target_agent="test-agent",
            status="completed",
            result={"response": "pong"},
            started_at="2024-04-14T12:01:00Z",
            completed_at="2024-04-14T12:01:05Z"
        )
        
        step2 = OrchestrationStep(
            step_id="step-1",
            name="Step 2",
            intent_type="echo",
            target_agent="test-agent",
            status="failed",
            error="Timeout",
            started_at="2024-04-14T12:02:00Z",
            completed_at="2024-04-14T12:02:30Z"
        )
        
        plan.steps = [step1, step2]
        
        # Serialize
        plan_dict = plan.to_dict()
        
        # Deserialize
        plan_restored = OrchestrationPlan.from_dict(plan_dict)
        
        # Verify
        assert plan_restored.plan_id == plan.plan_id
        assert plan_restored.name == plan.name
        assert plan_restored.status == plan.status
        assert len(plan_restored.steps) == 2
        
        # Verify steps
        assert plan_restored.steps[0].step_id == "step-0"
        assert plan_restored.steps[0].status == "completed"
        assert plan_restored.steps[0].result == {"response": "pong"}
        
        assert plan_restored.steps[1].step_id == "step-1"
        assert plan_restored.steps[1].status == "failed"
        assert plan_restored.steps[1].error == "Timeout"
    
    def test_manager_loads_plans_from_disk(self):
        """Test that OrchestrationManager loads plans from disk on initialization."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name
            
            # Write a plan to the file
            plan_data = {
                "plan_id": "loaded-plan-123",
                "name": "Loaded Plan",
                "description": "A plan loaded from disk",
                "steps": [
                    {
                        "step_id": "step-0",
                        "name": "Loaded Step",
                        "intent_type": "ping",
                        "target_agent": "test",
                        "params": {},
                        "status": "pending",
                        "result": None,
                        "error": "",
                        "started_at": "",
                        "completed_at": ""
                    }
                ],
                "status": "pending",
                "created_at": "2024-04-14T12:00:00Z",
                "completed_at": "",
                "error": ""
            }
            f.write(json.dumps(plan_data) + "\n")
        
        try:
            # Create manager with custom config
            config = OrchestrationManagerConfig(plans_path=Path(temp_file))
            manager = OrchestrationManager(config=config)
            
            # Verify plan was loaded
            assert "loaded-plan-123" in manager._plans
            plan = manager._plans["loaded-plan-123"]
            assert plan.name == "Loaded Plan"
            assert len(plan.steps) == 1
            assert plan.steps[0].name == "Loaded Step"
            
        finally:
            os.unlink(temp_file)
    
    def test_manager_saves_plan_on_creation(self):
        """Test that OrchestrationManager saves plans to disk when created."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name
        
        try:
            # Create manager with custom config
            config = OrchestrationManagerConfig(plans_path=Path(temp_file))
            manager = OrchestrationManager(config=config)
            
            # Create a plan
            plan = manager.create_plan(
                name="Test Save Plan",
                description="Testing plan persistence",
                steps=[
                    {"name": "Step 1", "intent_type": "ping", "target_agent": "test"},
                    {"name": "Step 2", "intent_type": "echo", "target_agent": "test"},
                ]
            )
            
            # Verify plan was saved to disk
            with open(temp_file, 'r') as f:
                lines = f.readlines()
                assert len(lines) == 1
                
                saved_plan = json.loads(lines[0])
                assert saved_plan["plan_id"] == plan.plan_id
                assert saved_plan["name"] == "Test Save Plan"
                assert len(saved_plan["steps"]) == 2
            
        finally:
            os.unlink(temp_file)
    
    def test_plan_persistence_across_manager_instances(self):
        """Test that plans persist across OrchestrationManager instances."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name
        
        try:
            # Create first manager and create a plan
            config = OrchestrationManagerConfig(plans_path=Path(temp_file))
            manager1 = OrchestrationManager(config=config)
            
            plan = manager1.create_plan(
                name="Persistent Plan",
                description="Should persist across instances",
                steps=[{"name": "Step", "intent_type": "ping", "target_agent": "test"}]
            )
            
            # Update plan status
            plan.status = "running"
            manager1._update_plan_in_storage(plan)
            
            # Create second manager loading from same file
            manager2 = OrchestrationManager(config=config)
            
            # Verify plan was loaded
            assert plan.plan_id in manager2._plans
            loaded_plan = manager2._plans[plan.plan_id]
            assert loaded_plan.name == "Persistent Plan"
            assert loaded_plan.status == "running"
            
        finally:
            os.unlink(temp_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])