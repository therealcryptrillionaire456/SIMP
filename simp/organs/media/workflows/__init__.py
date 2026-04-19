"""
n8n Workflow Templates for KashClaw Media Grid System

This module provides n8n workflow templates and integration for the
KashClaw Media Grid system. It includes event-driven orchestration
workflows for content pipeline automation, offer discovery, performance
optimization, compliance checking, and revenue reconciliation.

Workflows are designed to be imported into n8n and integrated with
the SIMP broker via webhooks.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

__version__ = "1.0.0"
__all__ = [
    "WorkflowManager",
    "load_workflow_template",
    "list_workflow_templates",
    "get_workflow_schema",
    "validate_workflow",
    "export_workflow",
]


class WorkflowManager:
    """Manages n8n workflow templates and state persistence."""
    
    def __init__(self, workflow_dir: Optional[Path] = None):
        """
        Initialize workflow manager.
        
        Args:
            workflow_dir: Directory containing workflow templates.
                         Defaults to module directory.
        """
        if workflow_dir is None:
            workflow_dir = Path(__file__).parent
        self.workflow_dir = workflow_dir
        self._templates = {}
        self._load_templates()
    
    def _load_templates(self) -> None:
        """Load all workflow templates from the workflow directory."""
        for file_path in self.workflow_dir.glob("*.json"):
            if file_path.name != "workflow_schema.json":
                try:
                    with open(file_path, 'r') as f:
                        template = json.load(f)
                    template_name = file_path.stem
                    self._templates[template_name] = template
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Failed to load template {file_path}: {e}")
    
    def list_templates(self) -> List[str]:
        """List available workflow template names."""
        return list(self._templates.keys())
    
    def get_template(self, name: str) -> Optional[Dict[str, Any]]:
        """Get workflow template by name."""
        return self._templates.get(name)
    
    def validate_template(self, name: str, workflow: Dict[str, Any]) -> bool:
        """
        Validate workflow against template schema.
        
        Args:
            name: Template name
            workflow: Workflow JSON to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Basic validation - check required fields
        required_fields = ["name", "nodes", "connections"]
        if not all(field in workflow for field in required_fields):
            return False
        
        # Check nodes structure
        if not isinstance(workflow.get("nodes"), list):
            return False
        
        # Check connections structure
        if not isinstance(workflow.get("connections"), dict):
            return False
        
        return True
    
    def create_custom_workflow(
        self,
        template_name: str,
        customizations: Dict[str, Any],
        output_path: Optional[Path] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a customized workflow from a template.
        
        Args:
            template_name: Name of template to customize
            customizations: Dictionary of customizations
            output_path: Optional path to save customized workflow
            
        Returns:
            Customized workflow or None if template not found
        """
        template = self.get_template(template_name)
        if not template:
            return None
        
        # Create deep copy
        import copy
        workflow = copy.deepcopy(template)
        
        # Apply customizations
        workflow.update(customizations)
        
        # Update metadata
        workflow["updatedAt"] = "customized"
        if "name" in customizations:
            workflow["name"] = customizations["name"]
        
        # Save if output path provided
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(workflow, f, indent=2)
        
        return workflow
    
    def get_workflow_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics about a workflow template.
        
        Args:
            name: Template name
            
        Returns:
            Dictionary with workflow statistics or None if not found
        """
        template = self.get_template(name)
        if not template:
            return None
        
        nodes = template.get("nodes", [])
        connections = template.get("connections", {})
        
        # Count node types
        node_types = {}
        for node in nodes:
            node_type = node.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        # Count connections
        connection_count = 0
        for source_connections in connections.values():
            for target_connections in source_connections.values():
                connection_count += len(target_connections)
        
        return {
            "name": name,
            "node_count": len(nodes),
            "connection_count": connection_count,
            "node_types": node_types,
            "has_webhook": any(node.get("type") == "n8n-nodes-base.webhook" for node in nodes),
            "has_schedule": any(node.get("type") == "n8n-nodes-base.scheduleTrigger" for node in nodes),
            "has_error_handling": any("error" in node.get("type", "").lower() for node in nodes),
        }


# Module-level convenience functions
def load_workflow_template(name: str) -> Optional[Dict[str, Any]]:
    """Load workflow template by name."""
    manager = WorkflowManager()
    return manager.get_template(name)


def list_workflow_templates() -> List[str]:
    """List all available workflow templates."""
    manager = WorkflowManager()
    return manager.list_templates()


def get_workflow_schema() -> Dict[str, Any]:
    """Get n8n workflow schema."""
    schema_path = Path(__file__).parent / "workflow_schema.json"
    if schema_path.exists():
        with open(schema_path, 'r') as f:
            return json.load(f)
    
    # Return basic schema if file doesn't exist
    return {
        "type": "object",
        "required": ["name", "nodes", "connections"],
        "properties": {
            "name": {"type": "string"},
            "nodes": {"type": "array"},
            "connections": {"type": "object"},
            "settings": {"type": "object"},
            "staticData": {"type": "object"},
            "pinData": {"type": "object"},
        }
    }


def validate_workflow(workflow: Dict[str, Any]) -> bool:
    """Validate workflow structure."""
    manager = WorkflowManager()
    return manager.validate_template("generic", workflow)


def export_workflow(
    template_name: str,
    output_path: Path,
    customizations: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Export workflow template to file.
    
    Args:
        template_name: Name of template to export
        output_path: Path to save workflow
        customizations: Optional customizations to apply
        
    Returns:
        True if successful, False otherwise
    """
    manager = WorkflowManager()
    
    if customizations:
        workflow = manager.create_custom_workflow(template_name, customizations)
    else:
        workflow = manager.get_template(template_name)
    
    if not workflow:
        return False
    
    try:
        with open(output_path, 'w') as f:
            json.dump(workflow, f, indent=2)
        return True
    except (IOError, TypeError):
        return False


# Initialize module
_workflow_manager = WorkflowManager()
"""Module-level workflow manager instance."""