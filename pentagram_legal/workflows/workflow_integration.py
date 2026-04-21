"""
Workflow Integration Module.
Integrates workflow orchestrator with agents, document processing, and other systems.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import logging
import json
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowIntegration:
    """
    Integration layer for workflow orchestrator.
    Connects workflows with agents, document processing, knowledge graph, etc.
    """
    
    def __init__(self, orchestrator, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Workflow Integration.
        
        Args:
            orchestrator: WorkflowOrchestrator instance
            config: Integration configuration
        """
        self.orchestrator = orchestrator
        self.config = config or self._default_config()
        
        # Integration handlers
        self.agent_handlers: Dict[str, Callable] = {}
        self.document_handlers: Dict[str, Callable] = {}
        self.knowledge_graph_handlers: Dict[str, Callable] = {}
        self.external_handlers: Dict[str, Callable] = {}
        
        # Integration state
        self.integration_state: Dict[str, Any] = {
            "connected_systems": [],
            "last_sync": {},
            "error_count": 0
        }
        
        logger.info("Initialized Workflow Integration")
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default integration configuration."""
        return {
            "agent_integration": {
                "enabled": True,
                "auto_assign_tasks": True,
                "agent_capabilities": {
                    "legal_analyst": ["contract_review", "research", "document_analysis"],
                    "risk_analyst": ["risk_assessment", "compliance_check"],
                    "attorney": ["document_drafting", "legal_advice", "negotiation"],
                    "compliance_officer": ["regulatory_check", "policy_review"],
                    "senior_attorney": ["senior_review", "approval"],
                    "legal_director": ["final_approval", "strategic_decision"]
                }
            },
            "document_processing": {
                "enabled": True,
                "auto_process_documents": True,
                "supported_formats": ["pdf", "docx", "txt", "json"],
                "processing_timeout": 300  # seconds
            },
            "knowledge_graph": {
                "enabled": True,
                "auto_index_documents": True,
                "graph_name": "legal_knowledge_graph",
                "relationship_types": ["cites", "interprets", "amends", "contradicts"]
            },
            "external_systems": {
                "enabled": False,
                "systems": ["pacer", "sec_edgar", "uspto", "courtlistener"],
                "api_timeout": 30
            },
            "error_handling": {
                "max_retries": 3,
                "retry_delay": 60,  # seconds
                "fallback_enabled": True
            }
        }
    
    def register_agent_handler(self, agent_type: str, handler: Callable):
        """
        Register handler for agent integration.
        
        Args:
            agent_type: Type of agent (e.g., "legal_analyst", "attorney")
            handler: Function to handle agent tasks
        """
        self.agent_handlers[agent_type] = handler
        logger.info(f"Registered agent handler for {agent_type}")
    
    def register_document_handler(self, handler_type: str, handler: Callable):
        """
        Register handler for document processing.
        
        Args:
            handler_type: Type of document handler
            handler: Function to handle document processing
        """
        self.document_handlers[handler_type] = handler
        logger.info(f"Registered document handler for {handler_type}")
    
    def register_knowledge_graph_handler(self, operation: str, handler: Callable):
        """
        Register handler for knowledge graph operations.
        
        Args:
            operation: Type of operation (e.g., "add_node", "query")
            handler: Function to handle knowledge graph operations
        """
        self.knowledge_graph_handlers[operation] = handler
        logger.info(f"Registered knowledge graph handler for {operation}")
    
    def integrate_workflow_start(self, workflow_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Integrate workflow start with other systems.
        
        Args:
            workflow_id: Workflow definition ID
            context: Workflow context
            
        Returns:
            Integration results
        """
        integration_results = {
            "workflow_id": workflow_id,
            "integrations": [],
            "errors": [],
            "warnings": []
        }
        
        try:
            # 1. Document processing integration
            if self.config["document_processing"]["enabled"] and "documents" in context:
                doc_results = self._process_documents(context.get("documents", []))
                integration_results["integrations"].append({
                    "system": "document_processing",
                    "results": doc_results
                })
            
            # 2. Knowledge graph integration
            if self.config["knowledge_graph"]["enabled"]:
                kg_results = self._index_to_knowledge_graph(workflow_id, context)
                integration_results["integrations"].append({
                    "system": "knowledge_graph",
                    "results": kg_results
                })
            
            # 3. External systems integration
            if self.config["external_systems"]["enabled"]:
                ext_results = self._query_external_systems(context)
                integration_results["integrations"].append({
                    "system": "external_systems",
                    "results": ext_results
                })
            
            logger.info(f"Integrated workflow {workflow_id} start with {len(integration_results['integrations'])} systems")
            
        except Exception as e:
            logger.error(f"Error integrating workflow start: {str(e)}")
            integration_results["errors"].append(str(e))
        
        return integration_results
    
    def integrate_task_assignment(self, task_id: str, assignee: str, 
                                 task_type: str) -> Dict[str, Any]:
        """
        Integrate task assignment with agent systems.
        
        Args:
            task_id: Task ID
            assignee: User/agent assigned
            task_type: Type of task
            
        Returns:
            Integration results
        """
        integration_results = {
            "task_id": task_id,
            "assignee": assignee,
            "integrations": [],
            "errors": []
        }
        
        try:
            # Determine agent type from assignee or task type
            agent_type = self._determine_agent_type(assignee, task_type)
            
            # Check if we have a handler for this agent type
            if agent_type in self.agent_handlers:
                handler = self.agent_handlers[agent_type]
                
                # Get task details
                task = self.orchestrator.workflow_tasks.get(task_id)
                if task:
                    # Prepare task data for agent
                    task_data = {
                        "task_id": task_id,
                        "task_name": task.name,
                        "task_description": task.description,
                        "workflow_instance_id": task.instance_id,
                        "inputs": task.inputs,
                        "due_date": task.due_date.isoformat() if task.due_date else None,
                        "priority": task.priority.value
                    }
                    
                    # Call agent handler
                    agent_result = handler(task_data)
                    
                    integration_results["integrations"].append({
                        "system": "agent",
                        "agent_type": agent_type,
                        "results": agent_result
                    })
                    
                    logger.info(f"Integrated task {task_id} assignment to {agent_type}")
                else:
                    integration_results["errors"].append(f"Task {task_id} not found")
            else:
                integration_results["warnings"] = [f"No handler for agent type {agent_type}"]
                logger.warning(f"No agent handler for {agent_type}")
        
        except Exception as e:
            logger.error(f"Error integrating task assignment: {str(e)}")
            integration_results["errors"].append(str(e))
        
        return integration_results
    
    def integrate_task_completion(self, task_id: str, outputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Integrate task completion with other systems.
        
        Args:
            task_id: Task ID
            outputs: Task outputs
            
        Returns:
            Integration results
        """
        integration_results = {
            "task_id": task_id,
            "integrations": [],
            "errors": []
        }
        
        try:
            # Get task details
            task = self.orchestrator.workflow_tasks.get(task_id)
            if not task:
                integration_results["errors"].append(f"Task {task_id} not found")
                return integration_results
            
            # 1. Knowledge graph integration for completed work
            if self.config["knowledge_graph"]["enabled"]:
                kg_results = self._add_task_results_to_knowledge_graph(task, outputs)
                integration_results["integrations"].append({
                    "system": "knowledge_graph",
                    "results": kg_results
                })
            
            # 2. Document processing for any generated documents
            if self.config["document_processing"]["enabled"] and "documents" in outputs:
                doc_results = self._process_documents(outputs.get("documents", []))
                integration_results["integrations"].append({
                    "system": "document_processing",
                    "results": doc_results
                })
            
            # 3. Update external systems if needed
            if self.config["external_systems"]["enabled"] and "external_updates" in outputs:
                ext_results = self._update_external_systems(outputs.get("external_updates", {}))
                integration_results["integrations"].append({
                    "system": "external_systems",
                    "results": ext_results
                })
            
            logger.info(f"Integrated task {task_id} completion with {len(integration_results['integrations'])} systems")
        
        except Exception as e:
            logger.error(f"Error integrating task completion: {str(e)}")
            integration_results["errors"].append(str(e))
        
        return integration_results
    
    def integrate_workflow_completion(self, instance_id: str) -> Dict[str, Any]:
        """
        Integrate workflow completion with other systems.
        
        Args:
            instance_id: Workflow instance ID
            
        Returns:
            Integration results
        """
        integration_results = {
            "instance_id": instance_id,
            "integrations": [],
            "errors": []
        }
        
        try:
            # Get workflow instance
            instance = self.orchestrator.get_workflow_instance(instance_id)
            if not instance:
                integration_results["errors"].append(f"Workflow instance {instance_id} not found")
                return integration_results
            
            # Get all tasks for this instance
            tasks = self.orchestrator.get_instance_tasks(instance_id)
            
            # 1. Archive workflow data
            archive_results = self._archive_workflow_data(instance, tasks)
            integration_results["integrations"].append({
                "system": "archive",
                "results": archive_results
            })
            
            # 2. Update knowledge graph with workflow results
            if self.config["knowledge_graph"]["enabled"]:
                kg_results = self._add_workflow_to_knowledge_graph(instance, tasks)
                integration_results["integrations"].append({
                    "system": "knowledge_graph",
                    "results": kg_results
                })
            
            # 3. Generate reports
            report_results = self._generate_workflow_reports(instance, tasks)
            integration_results["integrations"].append({
                "system": "reporting",
                "results": report_results
            })
            
            # 4. Notify stakeholders
            if "notifications" in self.config and self.config.get("notifications", {}).get("workflow_completion", False):
                notify_results = self._notify_stakeholders(instance, tasks)
                integration_results["integrations"].append({
                    "system": "notifications",
                    "results": notify_results
                })
            
            logger.info(f"Integrated workflow {instance_id} completion with {len(integration_results['integrations'])} systems")
        
        except Exception as e:
            logger.error(f"Error integrating workflow completion: {str(e)}")
            integration_results["errors"].append(str(e))
        
        return integration_results
    
    def _process_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process documents through document processing pipeline."""
        results = {
            "processed": 0,
            "failed": 0,
            "document_results": []
        }
        
        if "process_document" in self.document_handlers:
            handler = self.document_handlers["process_document"]
            
            for doc in documents:
                try:
                    doc_result = handler(doc)
                    results["document_results"].append(doc_result)
                    results["processed"] += 1
                except Exception as e:
                    logger.error(f"Error processing document: {str(e)}")
                    results["failed"] += 1
        
        return results
    
    def _index_to_knowledge_graph(self, workflow_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Index workflow data to knowledge graph."""
        results = {
            "nodes_added": 0,
            "relationships_added": 0,
            "errors": []
        }
        
        if "add_node" in self.knowledge_graph_handlers and "add_relationship" in self.knowledge_graph_handlers:
            add_node_handler = self.knowledge_graph_handlers["add_node"]
            add_rel_handler = self.knowledge_graph_handlers["add_relationship"]
            
            try:
                # Add workflow node
                workflow_node = {
                    "node_id": f"workflow_{workflow_id}",
                    "node_type": "workflow",
                    "label": f"Workflow: {workflow_id}",
                    "properties": {
                        "type": "legal_workflow",
                        "context": json.dumps(context),
                        "created_at": datetime.now().isoformat()
                    }
                }
                
                node_result = add_node_handler(workflow_node)
                if node_result.get("success", False):
                    results["nodes_added"] += 1
                
                # Add relationships to related entities
                if "entities" in context:
                    for entity in context.get("entities", []):
                        rel_data = {
                            "source_node_id": f"workflow_{workflow_id}",
                            "target_node_id": entity.get("id", ""),
                            "relationship_type": "involves",
                            "properties": {
                                "role": entity.get("role", "participant")
                            }
                        }
                        
                        rel_result = add_rel_handler(rel_data)
                        if rel_result.get("success", False):
                            results["relationships_added"] += 1
                
            except Exception as e:
                logger.error(f"Error indexing to knowledge graph: {str(e)}")
                results["errors"].append(str(e))
        
        return results
    
    def _query_external_systems(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Query external systems for relevant data."""
        results = {
            "systems_queried": [],
            "data_retrieved": {},
            "errors": []
        }
        
        # Mock implementation
        # In production, would query actual external systems
        
        if "case_references" in context:
            results["systems_queried"].append("pacer")
            results["data_retrieved"]["pacer"] = {
                "case_count": len(context.get("case_references", [])),
                "status": "mock_query_completed"
            }
        
        if "company_names" in context:
            results["systems_queried"].append("sec_edgar")
            results["data_retrieved"]["sec_edgar"] = {
                "filings_found": 3,  # Mock
                "status": "mock_query_completed"
            }
        
        return results
    
    def _determine_agent_type(self, assignee: str, task_type: str) -> str:
        """Determine agent type from assignee and task type."""
        # Simple mapping for now
        # In production, would use more sophisticated logic
        
        agent_capabilities = self.config["agent_integration"]["agent_capabilities"]
        
        # Check if assignee matches a known agent type
        for agent_type, capabilities in agent_capabilities.items():
            if agent_type in assignee.lower():
                return agent_type
        
        # Map task type to agent type
        task_to_agent = {
            "contract_review": "legal_analyst",
            "risk_assessment": "risk_analyst",
            "document_drafting": "attorney",
            "compliance_check": "compliance_officer",
            "senior_review": "senior_attorney",
            "final_approval": "legal_director"
        }
        
        for task_pattern, agent_type in task_to_agent.items():
            if task_pattern in task_type.lower():
                return agent_type
        
        # Default
        return "legal_analyst"
    
    def _add_task_results_to_knowledge_graph(self, task: Any, outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Add task results to knowledge graph."""
        results = {
            "nodes_added": 0,
            "relationships_added": 0,
            "errors": []
        }
        
        if "add_node" in self.knowledge_graph_handlers:
            handler = self.knowledge_graph_handlers["add_node"]
            
            try:
                # Add task node
                task_node = {
                    "node_id": f"task_{task.task_id}",
                    "node_type": "task",
                    "label": f"Task: {task.name}",
                    "properties": {
                        "workflow_instance_id": task.instance_id,
                        "status": task.status.value,
                        "completed_at": task.completion_date.isoformat() if task.completion_date else None,
                        "outputs_summary": json.dumps(outputs)[:500]  # Truncate if too long
                    }
                }
                
                node_result = handler(task_node)
                if node_result.get("success", False):
                    results["nodes_added"] += 1
                
            except Exception as e:
                logger.error(f"Error adding task to knowledge graph: {str(e)}")
                results["errors"].append(str(e))
        
        return results
    
    def _update_external_systems(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update external systems."""
        results = {
            "systems_updated": [],
            "update_results": {},
            "errors": []
        }
        
        # Mock implementation
        for system, update_data in updates.items():
            results["systems_updated"].append(system)
            results["update_results"][system] = {
                "status": "mock_update_completed",
                "timestamp": datetime.now().isoformat()
            }
        
        return results
    
    def _archive_workflow_data(self, instance: Any, tasks: List[Any]) -> Dict[str, Any]:
        """Archive workflow data."""
        results = {
            "archived": False,
            "archive_location": None,
            "size_bytes": 0,
            "errors": []
        }
        
        try:
            # Prepare archive data
            archive_data = {
                "workflow_instance": self._instance_to_dict(instance),
                "tasks": [self._task_to_dict(task) for task in tasks],
                "archived_at": datetime.now().isoformat()
            }
            
            # In production, would save to database or file system
            # For now, just return mock results
            results["archived"] = True
            results["archive_location"] = f"archive/workflow_{instance.instance_id}.json"
            results["size_bytes"] = len(json.dumps(archive_data))
            
            logger.info(f"Archived workflow {instance.instance_id}")
            
        except Exception as e:
            logger.error(f"Error archiving workflow data: {str(e)}")
            results["errors"].append(str(e))
        
        return results
    
    def _add_workflow_to_knowledge_graph(self, instance: Any, tasks: List[Any]) -> Dict[str, Any]:
        """Add completed workflow to knowledge graph."""
        results = {
            "workflow_indexed": False,
            "tasks_indexed": 0,
            "errors": []
        }
        
        if "add_node" in self.knowledge_graph_handlers:
            handler = self.knowledge_graph_handlers["add_node"]
            
            try:
                # Add completed workflow node
                workflow_node = {
                    "node_id": f"completed_workflow_{instance.instance_id}",
                    "node_type": "completed_workflow",
                    "label": f"Completed: {instance.name}",
                    "properties": {
                        "workflow_type": instance.workflow_id,
                        "status": instance.status.value,
                        "start_date": instance.start_date.isoformat(),
                        "completion_date": instance.completion_date.isoformat() if instance.completion_date else None,
                        "sla_days": instance.sla_days,
                        "tasks_completed": len([t for t in tasks if t.status.value == "completed"])
                    }
                }
                
                node_result = handler(workflow_node)
                if node_result.get("success", False):
                    results["workflow_indexed"] = True
                    results["tasks_indexed"] = len(tasks)
                
            except Exception as e:
                logger.error(f"Error adding workflow to knowledge graph: {str(e)}")
                results["errors"].append(str(e))
        
        return results
    
    def _generate_workflow_reports(self, instance: Any, tasks: List[Any]) -> Dict[str, Any]:
        """Generate workflow completion reports."""
        results = {
            "reports_generated": [],
            "report_locations": {},
            "errors": []
        }
        
        try:
            # Generate metrics report
            metrics = self.orchestrator.get_workflow_metrics(instance.instance_id)
            if metrics:
                metrics_report = {
                    "workflow_id": instance.instance_id,
                    "workflow_name": instance.name,
                    "completion_date": instance.completion_date.isoformat() if instance.completion_date else None,
                    "total_tasks": metrics.total_tasks,
                    "completed_tasks": metrics.completed_tasks,
                    "pending_tasks": metrics.pending_tasks,
                    "overdue_tasks": metrics.overdue_tasks,
                    "total_hours_estimated": metrics.total_hours_estimated,
                    "total_hours_actual": metrics.total_hours_actual,
                    "sla_compliance": metrics.sla_compliance,
                    "average_completion_time": metrics.average_completion_time
                }
                
                results["reports_generated"].append("metrics_report")
                results["report_locations"]["metrics_report"] = f"reports/{instance.instance_id}_metrics.json"
            
            # Generate task summary report
            task_summary = []
            for task in tasks:
                task_summary.append({
                    "task_id": task.task_id,
                    "name": task.name,
                    "status": task.status.value,
                    "assigned_to": task.assigned_to,
                    "start_date": task.start_date.isoformat() if task.start_date else None,
                    "completion_date": task.completion_date.isoformat() if task.completion_date else None,
                    "estimated_hours": task.estimated_hours,
                    "actual_hours": task.actual_hours
                })
            
            results["reports_generated"].append("task_summary")
            results["report_locations"]["task_summary"] = f"reports/{instance.instance_id}_tasks.json"
            
            logger.info(f"Generated {len(results['reports_generated'])} reports for workflow {instance.instance_id}")
            
        except Exception as e:
            logger.error(f"Error generating workflow reports: {str(e)}")
            results["errors"].append(str(e))
        
        return results
    
    def _notify_stakeholders(self, instance: Any, tasks: List[Any]) -> Dict[str, Any]:
        """Notify stakeholders of workflow completion."""
        results = {
            "notifications_sent": 0,
            "recipients": [],
            "errors": []
        }
        
        try:
            # Get unique assignees from completed tasks
            assignees = set()
            for task in tasks:
                if task.assigned_to:
                    assignees.add(task.assigned_to)
            
            # Add workflow creator
            assignees.add(instance.created_by)
            
            # Mock notification sending
            results["recipients"] = list(assignees)
            results["notifications_sent"] = len(assignees)
            
            logger.info(f"Sent completion notifications to {len(assignees)} stakeholders")
            
        except Exception as e:
            logger.error(f"Error notifying stakeholders: {str(e)}")
            results["errors"].append(str(e))
        
        return results
    
    def _instance_to_dict(self, instance: Any) -> Dict[str, Any]:
        """Convert workflow instance to dictionary."""
        return {
            "instance_id": instance.instance_id,
            "workflow_id": instance.workflow_id,
            "name": instance.name,
            "status": instance.status.value,
            "created_by": instance.created_by,
            "completion_date": instance.completion_date.isoformat() if instance.completion_date else None
        }
    
    def _task_to_dict(self, task: Any) -> Dict[str, Any]:
        """Convert workflow task to dictionary."""
        return {
            "task_id": task.task_id,
            "name": task.name,
            "status": task.status.value,
            "assigned_to": task.assigned_to,
            "completion_date": task.completion_date.isoformat() if task.completion_date else None
        }
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status."""
        return {
            "config": self.config,
            "state": self.integration_state,
            "handlers_registered": {
                "agent_handlers": len(self.agent_handlers),
                "document_handlers": len(self.document_handlers),
                "knowledge_graph_handlers": len(self.knowledge_graph_handlers),
                "external_handlers": len(self.external_handlers)
            },
            "timestamp": datetime.now().isoformat()
        }


def test_workflow_integration():
    """Test function for Workflow Integration."""
    print("Testing Workflow Integration...")
    
    # Create mock orchestrator
    class MockOrchestrator:
        def __init__(self):
            self.workflow_tasks = {}
            self.workflow_instances = {}
        
        def get_workflow_instance(self, instance_id):
            return self.workflow_instances.get(instance_id)
        
        def get_instance_tasks(self, instance_id):
            return []
        
        def get_workflow_metrics(self, instance_id):
            return None
    
    # Create integration
    orchestrator = MockOrchestrator()
    integration = WorkflowIntegration(orchestrator)
    
    # Test 1: Get integration status
    print("\n1. Testing integration status...")
    
    status = integration.get_integration_status()
    print(f"Integration status: {status['handlers_registered']}")
    
    # Test 2: Test workflow start integration
    print("\n2. Testing workflow start integration...")
    
    context = {
        "documents": [
            {"id": "doc_001", "type": "contract", "filename": "agreement.pdf"}
        ],
        "entities": [
            {"id": "entity_001", "type": "company", "role": "party_a"}
        ],
        "case_references": ["Smith v. Jones"],
        "company_names": ["ABC Corporation"]
    }
    
    results = integration.integrate_workflow_start("contract_review_v1", context)
    print(f"Workflow start integration: {len(results['integrations'])} systems integrated")
    
    # Test 3: Test task assignment integration
    print("\n3. Testing task assignment integration...")
    
    # Register a mock agent handler
    def mock_agent_handler(task_data):
        return {"status": "assigned", "agent_response": "Task accepted"}
    
    integration.register_agent_handler("legal_analyst", mock_agent_handler)
    
    results = integration.integrate_task_assignment("task_001", "legal_analyst_001", "contract_review")
    print(f"Task assignment integration: {results}")
    
    # Test 4: Test workflow completion integration
    print("\n4. Testing workflow completion integration...")
    
    # Create mock workflow instance
    class MockInstance:
        def __init__(self):
            self.instance_id = "wf_inst_001"
            self.workflow_id = "contract_review_v1"
            self.name = "Contract Review"
            self.status = "completed"
            self.created_by = "user_001"
            self.completion_date = datetime.now()
    
    orchestrator.workflow_instances["wf_inst_001"] = MockInstance()
    
    results = integration.integrate_workflow_completion("wf_inst_001")
    print(f"Workflow completion integration: {len(results['integrations'])} systems integrated")
    
    print("\nWorkflow Integration test completed successfully!")


if __name__ == "__main__":
    test_workflow_integration()