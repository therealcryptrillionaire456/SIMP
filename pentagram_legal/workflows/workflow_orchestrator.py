"""
Workflow Orchestration System - Build 13 Part 1
Coordinates legal workflows, task assignments, approvals, and deadlines.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
import uuid
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class TaskStatus(Enum):
    """Task status."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class ApprovalStatus(Enum):
    """Approval status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISED = "revised"
    ESCALATED = "escalated"


class WorkflowType(Enum):
    """Types of legal workflows."""
    CONTRACT_REVIEW = "contract_review"
    DOCUMENT_DRAFTING = "document_drafting"
    COMPLIANCE_CHECK = "compliance_check"
    LITIGATION_SUPPORT = "litigation_support"
    MERGER_ACQUISITION = "merger_acquisition"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    CORPORATE_GOVERNANCE = "corporate_governance"
    REGULATORY_FILING = "regulatory_filing"
    RISK_ASSESSMENT = "risk_assessment"
    GENERAL = "general"


class PriorityLevel(Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class WorkflowDefinition:
    """Workflow definition/template."""
    workflow_id: str
    name: str
    workflow_type: WorkflowType
    description: str
    version: str = "1.0"
    steps: List[Dict[str, Any]] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    approvals_required: List[Dict[str, Any]] = field(default_factory=list)
    sla_days: int = 30
    default_assignee: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowInstance:
    """Instance of a workflow."""
    instance_id: str
    workflow_id: str
    name: str
    status: WorkflowStatus
    priority: PriorityLevel
    created_by: str
    assigned_to: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    current_step: int = 0
    steps_completed: int = 0
    total_steps: int = 0
    start_date: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    completion_date: Optional[datetime] = None
    sla_days: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowTask:
    """Task within a workflow."""
    task_id: str
    instance_id: str
    step_number: int
    name: str
    description: str
    status: TaskStatus
    assigned_to: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    estimated_hours: float = 1.0
    actual_hours: Optional[float] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    completion_date: Optional[datetime] = None
    priority: PriorityLevel = PriorityLevel.MEDIUM
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowApproval:
    """Approval within a workflow."""
    approval_id: str
    instance_id: str
    task_id: str
    approver: str
    status: ApprovalStatus
    approval_type: str = "standard"
    comments: Optional[str] = None
    required: bool = True
    escalation_path: List[str] = field(default_factory=list)
    requested_at: datetime = field(default_factory=datetime.now)
    responded_at: Optional[datetime] = None
    due_date: Optional[datetime] = None


@dataclass
class WorkflowEvent:
    """Event in workflow execution."""
    event_id: str
    instance_id: str
    event_type: str
    description: str
    task_id: Optional[str] = None
    severity: str = "info"  # info, warning, error, critical
    details: Dict[str, Any] = field(default_factory=dict)
    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowMetrics:
    """Workflow performance metrics."""
    instance_id: str
    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    overdue_tasks: int
    total_hours_estimated: float
    total_hours_actual: Optional[float] = None
    sla_compliance: Optional[float] = None  # Percentage
    average_completion_time: Optional[float] = None  # Hours
    calculated_at: datetime = field(default_factory=datetime.now)


class WorkflowOrchestrator:
    """
    Workflow Orchestration System.
    Manages legal workflows, tasks, approvals, and deadlines.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Workflow Orchestrator.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or self._default_config()
        
        # Storage
        self.workflow_definitions: Dict[str, WorkflowDefinition] = {}
        self.workflow_instances: Dict[str, WorkflowInstance] = {}
        self.workflow_tasks: Dict[str, WorkflowTask] = {}
        self.workflow_approvals: Dict[str, WorkflowApproval] = {}
        self.workflow_events: Dict[str, WorkflowEvent] = {}
        
        # Indexes
        self.instance_tasks: Dict[str, Set[str]] = {}  # instance_id -> set of task_ids
        self.user_tasks: Dict[str, Set[str]] = {}  # user_id -> set of task_ids
        self.user_approvals: Dict[str, Set[str]] = {}  # user_id -> set of approval_ids
        
        # Statistics
        self.stats = {
            "workflow_definitions": 0,
            "workflow_instances": 0,
            "active_instances": 0,
            "completed_instances": 0,
            "total_tasks": 0,
            "completed_tasks": 0,
            "overdue_tasks": 0,
            "total_approvals": 0,
            "pending_approvals": 0,
            "sla_compliance_rate": 100.0
        }
        
        # Load default workflows
        self._load_default_workflows()
        
        logger.info("Initialized Workflow Orchestrator")
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "workflow": {
                "auto_start": True,
                "auto_assign": True,
                "default_sla_days": 30,
                "escalation_enabled": True,
                "escalation_hours": 24
            },
            "tasks": {
                "auto_create": True,
                "dependency_checking": True,
                "deadline_notifications": True,
                "overdue_escalation": True
            },
            "approvals": {
                "required_for_completion": True,
                "auto_escalate": True,
                "escalation_path": ["manager", "director", "vp"],
                "reminder_hours": 12
            },
            "notifications": {
                "enabled": True,
                "channels": ["email", "in_app"],
                "task_assignment": True,
                "deadline_approaching": True,
                "overdue": True,
                "approval_request": True,
                "workflow_completion": True
            },
            "persistence": {
                "auto_save": True,
                "save_interval_minutes": 5,
                "backup_enabled": True
            },
            "integration": {
                "agent_integration": True,
                "document_processing": True,
                "knowledge_graph": True,
                "external_systems": False
            }
        }
    
    def _load_default_workflows(self):
        """Load default workflow definitions."""
        # Contract Review Workflow
        contract_review = WorkflowDefinition(
            workflow_id="contract_review_v1",
            name="Standard Contract Review",
            workflow_type=WorkflowType.CONTRACT_REVIEW,
            description="Standard workflow for reviewing legal contracts",
            version="1.0",
            steps=[
                {
                    "step": 1,
                    "name": "Initial Review",
                    "description": "Initial legal review of contract",
                    "assignee_role": "legal_analyst",
                    "estimated_hours": 2,
                    "approval_required": False
                },
                {
                    "step": 2,
                    "name": "Risk Assessment",
                    "description": "Assess legal and business risks",
                    "assignee_role": "risk_analyst",
                    "estimated_hours": 4,
                    "approval_required": False
                },
                {
                    "step": 3,
                    "name": "Compliance Check",
                    "description": "Check regulatory compliance",
                    "assignee_role": "compliance_officer",
                    "estimated_hours": 3,
                    "approval_required": False
                },
                {
                    "step": 4,
                    "name": "Senior Review",
                    "description": "Senior attorney review",
                    "assignee_role": "senior_attorney",
                    "estimated_hours": 2,
                    "approval_required": True
                },
                {
                    "step": 5,
                    "name": "Final Approval",
                    "description": "Final approval by legal department head",
                    "assignee_role": "legal_director",
                    "estimated_hours": 1,
                    "approval_required": True
                }
            ],
            sla_days=10
        )
        
        self.create_workflow_definition(contract_review)
        
        # Document Drafting Workflow
        document_drafting = WorkflowDefinition(
            workflow_id="document_drafting_v1",
            name="Legal Document Drafting",
            workflow_type=WorkflowType.DOCUMENT_DRAFTING,
            description="Workflow for drafting legal documents",
            version="1.0",
            steps=[
                {
                    "step": 1,
                    "name": "Requirements Gathering",
                    "description": "Gather document requirements",
                    "assignee_role": "legal_analyst",
                    "estimated_hours": 3,
                    "approval_required": False
                },
                {
                    "step": 2,
                    "name": "Initial Draft",
                    "description": "Create initial document draft",
                    "assignee_role": "attorney",
                    "estimated_hours": 8,
                    "approval_required": False
                },
                {
                    "step": 3,
                    "name": "Internal Review",
                    "description": "Internal team review",
                    "assignee_role": "senior_attorney",
                    "estimated_hours": 4,
                    "approval_required": True
                },
                {
                    "step": 4,
                    "name": "Client Review",
                    "description": "Client review and feedback",
                    "assignee_role": "client_contact",
                    "estimated_hours": 24,  # Client time
                    "approval_required": True
                },
                {
                    "step": 5,
                    "name": "Final Revisions",
                    "description": "Incorporate feedback and finalize",
                    "assignee_role": "attorney",
                    "estimated_hours": 4,
                    "approval_required": False
                },
                {
                    "step": 6,
                    "name": "Final Approval",
                    "description": "Final approval and sign-off",
                    "assignee_role": "legal_director",
                    "estimated_hours": 1,
                    "approval_required": True
                }
            ],
            sla_days=15
        )
        
        self.create_workflow_definition(document_drafting)
        
        logger.info(f"Loaded {len(self.workflow_definitions)} default workflow definitions")
    
    def create_workflow_definition(self, definition: WorkflowDefinition) -> bool:
        """
        Create a new workflow definition.
        
        Args:
            definition: Workflow definition
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate ID if not provided
            if not definition.workflow_id:
                definition.workflow_id = f"wf_def_{uuid.uuid4().hex[:16]}"
            
            # Check if already exists
            if definition.workflow_id in self.workflow_definitions:
                logger.warning(f"Workflow definition {definition.workflow_id} already exists")
                return False
            
            # Validate steps
            if not definition.steps:
                logger.error("Workflow definition must have at least one step")
                return False
            
            # Sort steps by step number
            definition.steps.sort(key=lambda x: x.get("step", 0))
            
            # Store definition
            self.workflow_definitions[definition.workflow_id] = definition
            
            # Update statistics
            self.stats["workflow_definitions"] += 1
            
            # Log event
            self._log_event(
                instance_id=None,
                event_type="workflow_definition_created",
                description=f"Created workflow definition: {definition.name}",
                details={"workflow_id": definition.workflow_id, "type": definition.workflow_type.value}
            )
            
            logger.info(f"Created workflow definition {definition.workflow_id}: {definition.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating workflow definition: {str(e)}")
            return False
    
    def start_workflow(self, workflow_id: str, created_by: str, 
                      context: Dict[str, Any], priority: PriorityLevel = PriorityLevel.MEDIUM) -> Optional[WorkflowInstance]:
        """
        Start a new workflow instance.
        
        Args:
            workflow_id: Workflow definition ID
            created_by: User who created the workflow
            context: Workflow context data
            priority: Workflow priority
            
        Returns:
            Workflow instance or None if failed
        """
        try:
            # Check if workflow definition exists
            if workflow_id not in self.workflow_definitions:
                logger.error(f"Workflow definition {workflow_id} not found")
                return None
            
            definition = self.workflow_definitions[workflow_id]
            
            # Create instance ID
            instance_id = f"wf_inst_{uuid.uuid4().hex[:16]}"
            
            # Calculate due date based on SLA
            due_date = datetime.now() + timedelta(days=definition.sla_days)
            
            # Create workflow instance
            instance = WorkflowInstance(
                instance_id=instance_id,
                workflow_id=workflow_id,
                name=definition.name,
                status=WorkflowStatus.ACTIVE,
                priority=priority,
                created_by=created_by,
                context=context,
                total_steps=len(definition.steps),
                due_date=due_date,
                sla_days=definition.sla_days,
                metadata={
                    "definition_version": definition.version,
                    "started_at": datetime.now().isoformat()
                }
            )
            
            # Store instance
            self.workflow_instances[instance_id] = instance
            
            # Create tasks
            tasks_created = self._create_tasks_for_instance(instance, definition)
            
            if not tasks_created:
                logger.error(f"Failed to create tasks for workflow instance {instance_id}")
                instance.status = WorkflowStatus.ERROR
                return instance
            
            # Update statistics
            self.stats["workflow_instances"] += 1
            self.stats["active_instances"] += 1
            
            # Log event
            self._log_event(
                instance_id=instance_id,
                event_type="workflow_started",
                description=f"Started workflow: {definition.name}",
                details={
                    "created_by": created_by,
                    "priority": priority.value,
                    "sla_days": definition.sla_days,
                    "task_count": len(definition.steps)
                }
            )
            
            logger.info(f"Started workflow instance {instance_id} with {len(definition.steps)} tasks")
            return instance
            
        except Exception as e:
            logger.error(f"Error starting workflow: {str(e)}")
            return None
    
    def _create_tasks_for_instance(self, instance: WorkflowInstance, 
                                  definition: WorkflowDefinition) -> bool:
        """Create tasks for a workflow instance."""
        try:
            task_ids = []
            
            for step_def in definition.steps:
                step_number = step_def.get("step", 0)
                task_name = step_def.get("name", f"Step {step_number}")
                
                # Create task ID
                task_id = f"task_{uuid.uuid4().hex[:16]}"
                
                # Calculate due date for task (distribute across SLA)
                total_steps = len(definition.steps)
                step_sla_days = definition.sla_days / total_steps
                task_due_date = instance.start_date + timedelta(days=step_sla_days * step_number)
                
                # Create task
                task = WorkflowTask(
                    task_id=task_id,
                    instance_id=instance.instance_id,
                    step_number=step_number,
                    name=task_name,
                    description=step_def.get("description", ""),
                    status=TaskStatus.PENDING,
                    estimated_hours=step_def.get("estimated_hours", 1.0),
                    due_date=task_due_date,
                    priority=instance.priority,
                    inputs={}  # Will be populated as workflow progresses
                )
                
                # Store task
                self.workflow_tasks[task_id] = task
                
                # Update indexes
                if instance.instance_id not in self.instance_tasks:
                    self.instance_tasks[instance.instance_id] = set()
                self.instance_tasks[instance.instance_id].add(task_id)
                
                task_ids.append(task_id)
                
                # Create approval if required
                if step_def.get("approval_required", False):
                    self._create_approval_for_task(task, step_def)
            
            # Set up task dependencies
            self._setup_task_dependencies(instance.instance_id, task_ids, definition)
            
            # Update statistics
            self.stats["total_tasks"] += len(task_ids)
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating tasks: {str(e)}")
            return False
    
    def _create_approval_for_task(self, task: WorkflowTask, step_def: Dict[str, Any]):
        """Create approval for a task."""
        try:
            approval_id = f"approval_{uuid.uuid4().hex[:16]}"
            
            # Determine approver (in production, would look up based on role)
            approver = step_def.get("assignee_role", "approver")
            
            # Create approval
            approval = WorkflowApproval(
                approval_id=approval_id,
                instance_id=task.instance_id,
                task_id=task.task_id,
                approver=approver,
                status=ApprovalStatus.PENDING,
                approval_type="task_completion",
                due_date=task.due_date
            )
            
            # Store approval
            self.workflow_approvals[approval_id] = approval
            
            # Update indexes
            if approver not in self.user_approvals:
                self.user_approvals[approver] = set()
            self.user_approvals[approver].add(approval_id)
            
            # Update statistics
            self.stats["total_approvals"] += 1
            self.stats["pending_approvals"] += 1
            
        except Exception as e:
            logger.error(f"Error creating approval: {str(e)}")
    
    def _setup_task_dependencies(self, instance_id: str, task_ids: List[str], 
                                definition: WorkflowDefinition):
        """Set up task dependencies based on workflow definition."""
        try:
            # Simple linear dependencies for now
            # In production, would parse dependency definitions
            
            for i, task_id in enumerate(task_ids):
                if i > 0:  # All tasks depend on previous task
                    task = self.workflow_tasks[task_id]
                    prev_task_id = task_ids[i-1]
                    task.dependencies.append(prev_task_id)
                    
                    # Update task
                    self.workflow_tasks[task_id] = task
            
        except Exception as e:
            logger.error(f"Error setting up dependencies: {str(e)}")
    
    def assign_task(self, task_id: str, assignee: str) -> bool:
        """
        Assign a task to a user.
        
        Args:
            task_id: Task ID
            assignee: User to assign to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if task exists
            if task_id not in self.workflow_tasks:
                logger.error(f"Task {task_id} not found")
                return False
            
            task = self.workflow_tasks[task_id]
            
            # Check if task can be assigned
            if task.status not in [TaskStatus.PENDING, TaskStatus.BLOCKED]:
                logger.error(f"Task {task_id} cannot be assigned (status: {task.status.value})")
                return False
            
            # Check dependencies
            for dep_id in task.dependencies:
                if dep_id in self.workflow_tasks:
                    dep_task = self.workflow_tasks[dep_id]
                    if dep_task.status != TaskStatus.COMPLETED:
                        logger.error(f"Task {task_id} has unmet dependencies")
                        task.status = TaskStatus.BLOCKED
                        self.workflow_tasks[task_id] = task
                        return False
            
            # Update task
            task.assigned_to = assignee
            task.status = TaskStatus.ASSIGNED
            task.start_date = datetime.now()
            task.updated_at = datetime.now()
            
            self.workflow_tasks[task_id] = task
            
            # Update indexes
            if assignee not in self.user_tasks:
                self.user_tasks[assignee] = set()
            self.user_tasks[assignee].add(task_id)
            
            # Log event
            self._log_event(
                instance_id=task.instance_id,
                task_id=task_id,
                event_type="task_assigned",
                description=f"Task assigned to {assignee}",
                details={"task_name": task.name, "assignee": assignee}
            )
            
            logger.info(f"Assigned task {task_id} to {assignee}")
            return True
            
        except Exception as e:
            logger.error(f"Error assigning task: {str(e)}")
            return False
    
    def update_task_status(self, task_id: str, status: TaskStatus, 
                          outputs: Optional[Dict[str, Any]] = None,
                          actual_hours: Optional[float] = None) -> bool:
        """
        Update task status.
        
        Args:
            task_id: Task ID
            status: New status
            outputs: Task outputs
            actual_hours: Actual hours spent
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if task exists
            if task_id not in self.workflow_tasks:
                logger.error(f"Task {task_id} not found")
                return False
            
            task = self.workflow_tasks[task_id]
            
            # Validate status transition
            if not self._validate_status_transition(task.status, status):
                logger.error(f"Invalid status transition: {task.status.value} -> {status.value}")
                return False
            
            # Update task
            task.status = status
            task.updated_at = datetime.now()
            
            if status == TaskStatus.COMPLETED:
                task.completion_date = datetime.now()
                if actual_hours:
                    task.actual_hours = actual_hours
            
            if outputs:
                task.outputs.update(outputs)
            
            self.workflow_tasks[task_id] = task
            
            # Update workflow instance if task completed
            if status == TaskStatus.COMPLETED:
                self._update_workflow_on_task_completion(task)
            
            # Update statistics
            if status == TaskStatus.COMPLETED:
                self.stats["completed_tasks"] += 1
            
            # Log event
            self._log_event(
                instance_id=task.instance_id,
                task_id=task_id,
                event_type="task_status_updated",
                description=f"Task status updated to {status.value}",
                details={"task_name": task.name, "old_status": task.status.value, "new_status": status.value}
            )
            
            logger.info(f"Updated task {task_id} status to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating task status: {str(e)}")
            return False
    
    def _update_workflow_on_task_completion(self, task: WorkflowTask):
        """Update workflow instance when a task is completed."""
        try:
            instance_id = task.instance_id
            
            if instance_id not in self.workflow_instances:
                return
            
            instance = self.workflow_instances[instance_id]
            
            # Update steps completed
            instance.steps_completed += 1
            instance.current_step = task.step_number + 1  # Move to next step
            instance.updated_at = datetime.now()
            
            # Check if workflow is complete
            if instance.steps_completed >= instance.total_steps:
                instance.status = WorkflowStatus.COMPLETED
                instance.completion_date = datetime.now()
                
                # Update statistics
                self.stats["completed_instances"] += 1
                self.stats["active_instances"] -= 1
                
                # Log completion event
                self._log_event(
                    instance_id=instance_id,
                    event_type="workflow_completed",
                    description="Workflow completed successfully",
                    details={
                        "total_tasks": instance.total_steps,
                        "completion_date": instance.completion_date.isoformat()
                    }
                )
            
            self.workflow_instances[instance_id] = instance
            
        except Exception as e:
            logger.error(f"Error updating workflow on task completion: {str(e)}")
    
    def process_approval(self, approval_id: str, status: ApprovalStatus, 
                        comments: Optional[str] = None) -> bool:
        """
        Process an approval request.
        
        Args:
            approval_id: Approval ID
            status: Approval decision
            comments: Comments from approver
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if approval exists
            if approval_id not in self.workflow_approvals:
                logger.error(f"Approval {approval_id} not found")
                return False
            
            approval = self.workflow_approvals[approval_id]
            
            # Check if approval is still pending
            if approval.status != ApprovalStatus.PENDING:
                logger.error(f"Approval {approval_id} already processed")
                return False
            
            # Update approval
            approval.status = status
            approval.comments = comments
            approval.responded_at = datetime.now()
            
            self.workflow_approvals[approval_id] = approval
            
            # Update statistics
            if status == ApprovalStatus.APPROVED:
                self.stats["pending_approvals"] -= 1
            
            # If rejected, may need to escalate or notify
            if status == ApprovalStatus.REJECTED and self.config["approvals"]["auto_escalate"]:
                self._escalate_approval(approval)
            
            # Update related task if this is a task completion approval
            if approval.task_id and approval.task_id in self.workflow_tasks:
                task = self.workflow_tasks[approval.task_id]
                
                if status == ApprovalStatus.APPROVED:
                    # Mark task as completed if approval was the last requirement
                    self.update_task_status(task.task_id, TaskStatus.COMPLETED)
                elif status == ApprovalStatus.REJECTED:
                    # Mark task as blocked or send back for revision
                    task.status = TaskStatus.BLOCKED
                    task.errors.append(f"Approval rejected: {comments}")
                    self.workflow_tasks[task.task_id] = task
            
            # Log event
            self._log_event(
                instance_id=approval.instance_id,
                task_id=approval.task_id,
                event_type="approval_processed",
                description=f"Approval {status.value}",
                details={
                    "approver": approval.approver,
                    "comments": comments,
                    "approval_type": approval.approval_type
                }
            )
            
            logger.info(f"Processed approval {approval_id}: {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing approval: {str(e)}")
            return False
    
    def _escalate_approval(self, approval: WorkflowApproval):
        """Escalate an approval to the next level."""
        try:
            escalation_path = self.config["approvals"]["escalation_path"]
            
            if not escalation_path or len(escalation_path) == 0:
                return
            
            # Find current approver in escalation path
            current_index = -1
            for i, level in enumerate(escalation_path):
                if level == approval.approver:
                    current_index = i
                    break
            
            # If not in path or at the end, can't escalate
            if current_index == -1 or current_index >= len(escalation_path) - 1:
                logger.warning(f"Cannot escalate approval {approval.approval_id}")
                return
            
            # Get next approver
            next_approver = escalation_path[current_index + 1]
            
            # Create new approval
            new_approval_id = f"approval_{uuid.uuid4().hex[:16]}"
            
            new_approval = WorkflowApproval(
                approval_id=new_approval_id,
                instance_id=approval.instance_id,
                task_id=approval.task_id,
                approver=next_approver,
                status=ApprovalStatus.PENDING,
                approval_type="escalated",
                comments=f"Escalated from {approval.approver}",
                escalation_path=approval.escalation_path + [approval.approver],
                due_date=approval.due_date
            )
            
            # Store new approval
            self.workflow_approvals[new_approval_id] = new_approval
            
            # Update indexes
            if next_approver not in self.user_approvals:
                self.user_approvals[next_approver] = set()
            self.user_approvals[next_approver].add(new_approval_id)
            
            # Update statistics
            self.stats["total_approvals"] += 1
            self.stats["pending_approvals"] += 1
            
            # Log escalation event
            self._log_event(
                instance_id=approval.instance_id,
                task_id=approval.task_id,
                event_type="approval_escalated",
                description=f"Approval escalated to {next_approver}",
                details={
                    "from_approver": approval.approver,
                    "to_approver": next_approver,
                    "reason": "Rejection"
                }
            )
            
            logger.info(f"Escalated approval {approval.approval_id} to {next_approver}")
            
        except Exception as e:
            logger.error(f"Error escalating approval: {str(e)}")
    
    def get_workflow_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """Get workflow instance by ID."""
        return self.workflow_instances.get(instance_id)
    
    def get_instance_tasks(self, instance_id: str) -> List[WorkflowTask]:
        """Get all tasks for a workflow instance."""
        if instance_id not in self.instance_tasks:
            return []
        
        tasks = []
        for task_id in self.instance_tasks[instance_id]:
            if task_id in self.workflow_tasks:
                tasks.append(self.workflow_tasks[task_id])
        
        return sorted(tasks, key=lambda t: t.step_number)
    
    def get_user_tasks(self, user_id: str, status: Optional[TaskStatus] = None) -> List[WorkflowTask]:
        """Get tasks assigned to a user."""
        if user_id not in self.user_tasks:
            return []
        
        tasks = []
        for task_id in self.user_tasks[user_id]:
            if task_id in self.workflow_tasks:
                task = self.workflow_tasks[task_id]
                if status is None or task.status == status:
                    tasks.append(task)
        
        return sorted(tasks, key=lambda t: t.due_date or datetime.max)
    
    def get_user_approvals(self, user_id: str, status: Optional[ApprovalStatus] = None) -> List[WorkflowApproval]:
        """Get approvals pending for a user."""
        if user_id not in self.user_approvals:
            return []
        
        approvals = []
        for approval_id in self.user_approvals[user_id]:
            if approval_id in self.workflow_approvals:
                approval = self.workflow_approvals[approval_id]
                if status is None or approval.status == status:
                    approvals.append(approval)
        
        return sorted(approvals, key=lambda a: a.due_date or datetime.max)
    
    def get_workflow_metrics(self, instance_id: str) -> Optional[WorkflowMetrics]:
        """Get metrics for a workflow instance."""
        if instance_id not in self.workflow_instances:
            return None
        
        tasks = self.get_instance_tasks(instance_id)
        if not tasks:
            return None
        
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        pending_tasks = sum(1 for t in tasks if t.status in [TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS])
        
        # Check for overdue tasks
        now = datetime.now()
        overdue_tasks = sum(1 for t in tasks if t.due_date and t.due_date < now and t.status != TaskStatus.COMPLETED)
        
        # Calculate hours
        total_hours_estimated = sum(t.estimated_hours for t in tasks)
        total_hours_actual = sum(t.actual_hours for t in tasks if t.actual_hours is not None)
        
        # Calculate SLA compliance
        instance = self.workflow_instances[instance_id]
        sla_compliance = None
        
        if instance.completion_date and instance.due_date:
            if instance.completion_date <= instance.due_date:
                sla_compliance = 100.0
            else:
                # Calculate percentage (simplified)
                sla_compliance = max(0.0, 100.0 - ((instance.completion_date - instance.due_date).days * 10))
        
        # Calculate average completion time
        average_completion_time = None
        completed_with_times = [t for t in tasks if t.completion_date and t.start_date]
        if completed_with_times:
            total_time = sum((t.completion_date - t.start_date).total_seconds() / 3600 for t in completed_with_times)
            average_completion_time = total_time / len(completed_with_times)
        
        return WorkflowMetrics(
            instance_id=instance_id,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            pending_tasks=pending_tasks,
            overdue_tasks=overdue_tasks,
            total_hours_estimated=total_hours_estimated,
            total_hours_actual=total_hours_actual,
            sla_compliance=sla_compliance,
            average_completion_time=average_completion_time
        )
    
    def check_deadlines(self) -> Dict[str, Any]:
        """
        Check for approaching and overdue deadlines.
        
        Returns:
            Dictionary with deadline information
        """
        now = datetime.now()
        approaching_threshold = timedelta(hours=24)  # 24 hours
        overdue_threshold = timedelta(hours=0)  # Already overdue
        
        approaching_tasks = []
        overdue_tasks = []
        approaching_approvals = []
        overdue_approvals = []
        
        # Check tasks
        for task_id, task in self.workflow_tasks.items():
            if task.due_date and task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                time_until = task.due_date - now
                
                if time_until <= overdue_threshold:
                    overdue_tasks.append({
                        "task_id": task_id,
                        "name": task.name,
                        "due_date": task.due_date.isoformat(),
                        "assigned_to": task.assigned_to,
                        "instance_id": task.instance_id
                    })
                    
                    # Update task status if overdue
                    if task.status != TaskStatus.OVERDUE:
                        task.status = TaskStatus.OVERDUE
                        self.workflow_tasks[task_id] = task
                        self.stats["overdue_tasks"] += 1
                        
                elif time_until <= approaching_threshold:
                    approaching_tasks.append({
                        "task_id": task_id,
                        "name": task.name,
                        "due_date": task.due_date.isoformat(),
                        "hours_until": time_until.total_seconds() / 3600,
                        "assigned_to": task.assigned_to
                    })
        
        # Check approvals
        for approval_id, approval in self.workflow_approvals.items():
            if approval.due_date and approval.status == ApprovalStatus.PENDING:
                time_until = approval.due_date - now
                
                if time_until <= overdue_threshold:
                    overdue_approvals.append({
                        "approval_id": approval_id,
                        "approver": approval.approver,
                        "due_date": approval.due_date.isoformat(),
                        "instance_id": approval.instance_id
                    })
                elif time_until <= approaching_threshold:
                    approaching_approvals.append({
                        "approval_id": approval_id,
                        "approver": approval.approver,
                        "due_date": approval.due_date.isoformat(),
                        "hours_until": time_until.total_seconds() / 3600
                    })
        
        return {
            "approaching_tasks": approaching_tasks,
            "overdue_tasks": overdue_tasks,
            "approaching_approvals": approaching_approvals,
            "overdue_approvals": overdue_approvals,
            "checked_at": now.isoformat()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        # Calculate SLA compliance rate
        completed_instances = [i for i in self.workflow_instances.values() if i.status == WorkflowStatus.COMPLETED]
        
        sla_compliant = 0
        for instance in completed_instances:
            if instance.completion_date and instance.due_date:
                if instance.completion_date <= instance.due_date:
                    sla_compliant += 1
        
        sla_compliance_rate = (sla_compliant / len(completed_instances) * 100) if completed_instances else 100.0
        
        self.stats["sla_compliance_rate"] = sla_compliance_rate
        
        return {
            "orchestrator_config": self.config,
            "statistics": self.stats,
            "timestamp": datetime.now().isoformat()
        }
    
    def export_workflow_data(self, instance_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Export workflow data.
        
        Args:
            instance_ids: List of instance IDs (all if None)
            
        Returns:
            Export data
        """
        if instance_ids is None:
            instance_ids = list(self.workflow_instances.keys())
        
        export_data = {
            "metadata": {
                "export_date": datetime.now().isoformat(),
                "instance_count": len(instance_ids),
                "orchestrator_version": "1.0.0"
            },
            "workflow_definitions": [],
            "workflow_instances": [],
            "workflow_tasks": [],
            "workflow_approvals": [],
            "workflow_events": []
        }
        
        # Export definitions
        for definition in self.workflow_definitions.values():
            export_data["workflow_definitions"].append(self._definition_to_dict(definition))
        
        # Export instances
        for instance_id in instance_ids:
            if instance_id in self.workflow_instances:
                instance = self.workflow_instances[instance_id]
                export_data["workflow_instances"].append(self._instance_to_dict(instance))
                
                # Export tasks for this instance
                tasks = self.get_instance_tasks(instance_id)
                for task in tasks:
                    export_data["workflow_tasks"].append(self._task_to_dict(task))
                
                # Export approvals for this instance
                # (would need to filter approvals by instance)
        
        return export_data
    
    def _validate_status_transition(self, old_status: TaskStatus, new_status: TaskStatus) -> bool:
        """Validate task status transition."""
        valid_transitions = {
            TaskStatus.PENDING: [TaskStatus.ASSIGNED, TaskStatus.BLOCKED, TaskStatus.CANCELLED],
            TaskStatus.ASSIGNED: [TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.CANCELLED],
            TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.BLOCKED, TaskStatus.CANCELLED],
            TaskStatus.BLOCKED: [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
            TaskStatus.COMPLETED: [],  # Cannot transition from completed
            TaskStatus.CANCELLED: [],  # Cannot transition from cancelled
            TaskStatus.OVERDUE: [TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.CANCELLED]
        }
        
        return new_status in valid_transitions.get(old_status, [])
    
    def _log_event(self, instance_id: Optional[str], event_type: str, 
                  description: str, details: Dict[str, Any], 
                  task_id: Optional[str] = None, severity: str = "info"):
        """Log a workflow event."""
        try:
            event_id = f"event_{uuid.uuid4().hex[:16]}"
            
            event = WorkflowEvent(
                event_id=event_id,
                instance_id=instance_id,
                task_id=task_id,
                event_type=event_type,
                description=description,
                severity=severity,
                details=details
            )
            
            self.workflow_events[event_id] = event
            
        except Exception as e:
            logger.error(f"Error logging event: {str(e)}")
    
    def _definition_to_dict(self, definition: WorkflowDefinition) -> Dict[str, Any]:
        """Convert workflow definition to dictionary."""
        return {
            "workflow_id": definition.workflow_id,
            "name": definition.name,
            "workflow_type": definition.workflow_type.value,
            "description": definition.description,
            "version": definition.version,
            "steps": definition.steps,
            "sla_days": definition.sla_days,
            "created_at": definition.created_at.isoformat(),
            "updated_at": definition.updated_at.isoformat()
        }
    
    def _instance_to_dict(self, instance: WorkflowInstance) -> Dict[str, Any]:
        """Convert workflow instance to dictionary."""
        return {
            "instance_id": instance.instance_id,
            "workflow_id": instance.workflow_id,
            "name": instance.name,
            "status": instance.status.value,
            "priority": instance.priority.value,
            "created_by": instance.created_by,
            "assigned_to": instance.assigned_to,
            "current_step": instance.current_step,
            "steps_completed": instance.steps_completed,
            "total_steps": instance.total_steps,
            "start_date": instance.start_date.isoformat(),
            "due_date": instance.due_date.isoformat() if instance.due_date else None,
            "completion_date": instance.completion_date.isoformat() if instance.completion_date else None,
            "sla_days": instance.sla_days,
            "created_at": instance.created_at.isoformat(),
            "updated_at": instance.updated_at.isoformat()
        }
    
    def _task_to_dict(self, task: WorkflowTask) -> Dict[str, Any]:
        """Convert workflow task to dictionary."""
        return {
            "task_id": task.task_id,
            "instance_id": task.instance_id,
            "step_number": task.step_number,
            "name": task.name,
            "description": task.description,
            "status": task.status.value,
            "assigned_to": task.assigned_to,
            "dependencies": task.dependencies,
            "estimated_hours": task.estimated_hours,
            "actual_hours": task.actual_hours,
            "start_date": task.start_date.isoformat() if task.start_date else None,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "completion_date": task.completion_date.isoformat() if task.completion_date else None,
            "priority": task.priority.value,
            "errors": task.errors,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat()
        }


def test_workflow_orchestrator():
    """Test function for Workflow Orchestrator."""
    print("Testing Workflow Orchestrator...")
    
    # Create orchestrator
    orchestrator = WorkflowOrchestrator()
    
    # Test 1: Get default workflows
    print("\n1. Testing default workflows...")
    
    stats = orchestrator.get_statistics()
    print(f"Default workflow definitions: {stats['statistics']['workflow_definitions']}")
    
    # Test 2: Start a workflow
    print("\n2. Testing workflow start...")
    
    context = {
        "contract_id": "contract_123",
        "contract_type": "employment",
        "parties": ["Company Inc.", "John Doe"],
        "value": 100000
    }
    
    instance = orchestrator.start_workflow(
        workflow_id="contract_review_v1",
        created_by="user_001",
        context=context,
        priority=PriorityLevel.HIGH
    )
    
    if instance:
        print(f"Started workflow instance: {instance.instance_id}")
        print(f"Workflow name: {instance.name}")
        print(f"Status: {instance.status.value}")
        print(f"Total steps: {instance.total_steps}")
        print(f"Due date: {instance.due_date}")
    else:
        print("Failed to start workflow")
        return
    
    # Test 3: Get instance tasks
    print("\n3. Testing task retrieval...")
    
    tasks = orchestrator.get_instance_tasks(instance.instance_id)
    print(f"Created {len(tasks)} tasks")
    
    for task in tasks[:3]:  # Show first 3 tasks
        print(f"  Task: {task.name} (Step {task.step_number}, Status: {task.status.value})")
    
    # Test 4: Assign and complete tasks
    print("\n4. Testing task assignment and completion...")
    
    if tasks:
        # Assign first task
        task1 = tasks[0]
        if orchestrator.assign_task(task1.task_id, "legal_analyst_001"):
            print(f"Assigned task '{task1.name}' to legal_analyst_001")
            
            # Complete the task
            if orchestrator.update_task_status(task1.task_id, TaskStatus.COMPLETED, 
                                              outputs={"review_notes": "Contract looks standard"},
                                              actual_hours=1.5):
                print(f"Completed task '{task1.name}'")
        
        # Assign second task
        if len(tasks) > 1:
            task2 = tasks[1]
            if orchestrator.assign_task(task2.task_id, "risk_analyst_001"):
                print(f"Assigned task '{task2.name}' to risk_analyst_001")
    
    # Test 5: Get user tasks
    print("\n5. Testing user task retrieval...")
    
    user_tasks = orchestrator.get_user_tasks("risk_analyst_001")
    print(f"risk_analyst_001 has {len(user_tasks)} assigned tasks")
    
    # Test 6: Check deadlines
    print("\n6. Testing deadline checking...")
    
    deadlines = orchestrator.check_deadlines()
    print(f"Approaching tasks: {len(deadlines['approaching_tasks'])}")
    print(f"Overdue tasks: {len(deadlines['overdue_tasks'])}")
    
    # Test 7: Get workflow metrics
    print("\n7. Testing workflow metrics...")
    
    metrics = orchestrator.get_workflow_metrics(instance.instance_id)
    if metrics:
        print(f"Workflow metrics:")
        print(f"  Total tasks: {metrics.total_tasks}")
        print(f"  Completed tasks: {metrics.completed_tasks}")
        print(f"  Pending tasks: {metrics.pending_tasks}")
        print(f"  Overdue tasks: {metrics.overdue_tasks}")
        print(f"  Estimated hours: {metrics.total_hours_estimated}")
    
    # Test 8: Get final statistics
    print("\n8. Testing final statistics...")
    
    final_stats = orchestrator.get_statistics()
    print(f"Final statistics:")
    print(f"  Workflow instances: {final_stats['statistics']['workflow_instances']}")
    print(f"  Active instances: {final_stats['statistics']['active_instances']}")
    print(f"  Total tasks: {final_stats['statistics']['total_tasks']}")
    print(f"  Completed tasks: {final_stats['statistics']['completed_tasks']}")
    print(f"  SLA compliance: {final_stats['statistics']['sla_compliance_rate']:.1f}%")
    
    print("\nWorkflow Orchestrator test completed successfully!")


if __name__ == "__main__":
    test_workflow_orchestrator()