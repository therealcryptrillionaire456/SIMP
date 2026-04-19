"""
Workflow Orchestration System Package.
"""

from workflows.workflow_orchestrator import (
    WorkflowOrchestrator, WorkflowDefinition, WorkflowInstance,
    WorkflowTask, WorkflowApproval, WorkflowEvent, WorkflowMetrics,
    WorkflowStatus, TaskStatus, ApprovalStatus, WorkflowType, PriorityLevel
)

from workflows.workflow_integration import WorkflowIntegration

__version__ = "1.0.0"
__author__ = "Pentagram Legal Department"
__description__ = "Workflow Orchestration System for coordinating legal workflows"

__all__ = [
    # Main orchestrator
    "WorkflowOrchestrator",
    
    # Data classes
    "WorkflowDefinition",
    "WorkflowInstance",
    "WorkflowTask",
    "WorkflowApproval",
    "WorkflowEvent",
    "WorkflowMetrics",
    
    # Enums
    "WorkflowStatus",
    "TaskStatus",
    "ApprovalStatus",
    "WorkflowType",
    "PriorityLevel",
    
    # Integration
    "WorkflowIntegration"
]