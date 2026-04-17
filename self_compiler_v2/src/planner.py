#!/usr/bin/env python3
"""
Planner for Sovereign Self Compiler v2.

Creates next-step recursive plans based on goals, inventory, and constraints.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class Goal:
    """A goal for the self-compiler."""
    goal_id: str
    description: str
    priority: str  # "low", "medium", "high", "critical"
    constraints: Dict[str, Any] = field(default_factory=dict)
    success_criteria: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class Task:
    """A decomposed task within a plan."""
    task_id: str
    description: str
    task_type: str  # "inventory", "analysis", "generation", "refactoring", "testing"
    dependencies: List[str] = field(default_factory=list)
    estimated_effort: int = 1  # 1-5 scale
    required_skills: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class Plan:
    """A complete plan for achieving a goal."""
    plan_id: str
    goal_id: str
    cycle_number: int
    tasks: List[Task] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    success_criteria: List[str] = field(default_factory=list)
    risks: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def save(self, path: str) -> None:
        """Save plan to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        logger.info(f"Plan saved to {path}")


class Planner:
    """Creates structured plans for recursive self-compilation."""
    
    # Task templates for different goal types
    TASK_TEMPLATES = {
        "inventory_scan": {
            "description": "Scan codebase and create inventory",
            "task_type": "inventory",
            "estimated_effort": 2,
            "required_skills": ["filesystem", "parsing", "classification"],
            "success_criteria": [
                "Inventory file created",
                "All relevant files discovered",
                "Components properly classified"
            ]
        },
        "code_analysis": {
            "description": "Analyze code structure and dependencies",
            "task_type": "analysis",
            "estimated_effort": 3,
            "required_skills": ["static_analysis", "dependency_tracking", "complexity_analysis"],
            "success_criteria": [
                "Dependency graph generated",
                "Complexity metrics calculated",
                "Architecture documented"
            ]
        },
        "module_generation": {
            "description": "Generate new module based on specifications",
            "task_type": "generation",
            "estimated_effort": 4,
            "required_skills": ["code_generation", "api_design", "testing"],
            "success_criteria": [
                "Module passes syntax check",
                "Tests pass",
                "Documentation generated"
            ]
        },
        "refactoring": {
            "description": "Refactor existing code for improvement",
            "task_type": "refactoring",
            "estimated_effort": 5,
            "required_skills": ["refactoring", "testing", "backward_compatibility"],
            "success_criteria": [
                "Functionality preserved",
                "Code quality improved",
                "Tests pass"
            ]
        },
        "testing": {
            "description": "Create and run tests",
            "task_type": "testing",
            "estimated_effort": 3,
            "required_skills": ["test_design", "coverage_analysis", "automation"],
            "success_criteria": [
                "Test coverage meets target",
                "All tests pass",
                "Edge cases covered"
            ]
        },
        "documentation": {
            "description": "Generate or update documentation",
            "task_type": "generation",
            "estimated_effort": 2,
            "required_skills": ["technical_writing", "formatting", "diagramming"],
            "success_criteria": [
                "Documentation complete",
                "Examples provided",
                "Formatting consistent"
            ]
        }
    }
    
    # Goal patterns and corresponding task sequences
    GOAL_PATTERNS = {
        r".*inventory.*scan.*": ["inventory_scan", "code_analysis", "documentation"],
        r".*analyze.*code.*": ["code_analysis", "documentation"],
        r".*create.*module.*": ["module_generation", "testing", "documentation"],
        r".*refactor.*": ["code_analysis", "refactoring", "testing", "documentation"],
        r".*add.*test.*": ["testing", "documentation"],
        r".*document.*": ["documentation"],
        r".*improve.*performance.*": ["code_analysis", "refactoring", "testing"],
        r".*fix.*bug.*": ["code_analysis", "refactoring", "testing"],
        r".*add.*feature.*": ["code_analysis", "module_generation", "testing", "documentation"]
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize planner with configuration."""
        self.config = config or {}
        self.max_tasks_per_plan = self.config.get("max_tasks_per_plan", 10)
        self.max_recursion_depth = self.config.get("max_recursion_depth", 3)
        
    def create_plan(self, goal: Goal, inventory: Dict, constraints: Dict) -> Plan:
        """
        Create a plan to achieve the given goal.
        
        Args:
            goal: The goal to achieve
            inventory: Current inventory snapshot
            constraints: Operator constraints
            
        Returns:
            Plan object
        """
        logger.info(f"Creating plan for goal: {goal.description}")
        
        # Generate plan ID
        plan_id = f"plan_{hashlib.md5(goal.goal_id.encode()).hexdigest()[:8]}_{int(datetime.now().timestamp())}"
        
        # Determine cycle number
        cycle_number = constraints.get("cycle_number", 1)
        
        # Check recursion depth
        if cycle_number > self.max_recursion_depth:
            raise ValueError(f"Maximum recursion depth ({self.max_recursion_depth}) exceeded")
        
        # Match goal to pattern
        task_sequence = self._match_goal_pattern(goal.description)
        
        # Create tasks
        tasks = []
        for i, task_template_key in enumerate(task_sequence):
            if len(tasks) >= self.max_tasks_per_plan:
                logger.warning(f"Reached maximum tasks per plan ({self.max_tasks_per_plan})")
                break
            
            task = self._create_task_from_template(
                task_template_key=task_template_key,
                task_number=i + 1,
                goal=goal,
                inventory=inventory,
                constraints=constraints
            )
            tasks.append(task)
        
        # Build dependency graph
        dependencies = self._build_dependency_graph(tasks)
        
        # Estimate resource requirements
        resource_requirements = self._estimate_resource_requirements(tasks, inventory)
        
        # Identify risks
        risks = self._identify_risks(tasks, inventory, constraints)
        
        # Create plan
        plan = Plan(
            plan_id=plan_id,
            goal_id=goal.goal_id,
            cycle_number=cycle_number,
            tasks=tasks,
            dependencies=dependencies,
            resource_requirements=resource_requirements,
            success_criteria=goal.success_criteria,
            risks=risks,
            metadata={
                "goal_description": goal.description,
                "goal_priority": goal.priority,
                "inventory_stats": inventory.get("summary", {}),
                "constraints_applied": constraints,
                "planning_config": {
                    "max_tasks_per_plan": self.max_tasks_per_plan,
                    "max_recursion_depth": self.max_recursion_depth
                }
            }
        )
        
        logger.info(f"Plan created with {len(tasks)} tasks")
        return plan
    
    def _match_goal_pattern(self, goal_description: str) -> List[str]:
        """Match goal description to task sequence pattern."""
        goal_lower = goal_description.lower()
        
        for pattern, task_sequence in self.GOAL_PATTERNS.items():
            import re
            if re.search(pattern, goal_lower):
                logger.debug(f"Matched goal '{goal_description}' to pattern '{pattern}'")
                return task_sequence
        
        # Default pattern for unknown goals
        logger.warning(f"No pattern matched for goal: {goal_description}, using default")
        return ["code_analysis", "module_generation", "testing", "documentation"]
    
    def _create_task_from_template(
        self,
        task_template_key: str,
        task_number: int,
        goal: Goal,
        inventory: Dict,
        constraints: Dict
    ) -> Task:
        """Create a task from template with context-specific adjustments."""
        template = self.TASK_TEMPLATES.get(task_template_key, self.TASK_TEMPLATES["code_analysis"])
        
        # Generate task ID
        task_id = f"task_{task_template_key}_{task_number}_{hashlib.md5(goal.goal_id.encode()).hexdigest()[:6]}"
        
        # Customize description based on goal
        description = template["description"]
        if "inventory" in task_template_key:
            description = f"Scan {constraints.get('target_directory', 'codebase')} and create inventory"
        elif "module" in task_template_key:
            description = f"Generate module for: {goal.description}"
        
        # Adjust effort based on inventory size
        estimated_effort = template["estimated_effort"]
        if "inventory" in task_template_key or "analysis" in task_template_key:
            total_components = inventory.get("summary", {}).get("total_components", 0)
            if total_components > 1000:
                estimated_effort = min(estimated_effort + 2, 5)
            elif total_components > 100:
                estimated_effort = min(estimated_effort + 1, 5)
        
        # Add dependencies for sequential tasks
        dependencies = []
        if task_number > 1:
            prev_task_key = list(self.TASK_TEMPLATES.keys())[
                list(self.TASK_TEMPLATES.keys()).index(task_template_key) - 1
                if task_template_key in self.TASK_TEMPLATES else 0
            ]
            dependencies.append(f"task_{prev_task_key}_{task_number-1}_{hashlib.md5(goal.goal_id.encode()).hexdigest()[:6]}")
        
        # Create task
        task = Task(
            task_id=task_id,
            description=description,
            task_type=template["task_type"],
            dependencies=dependencies,
            estimated_effort=estimated_effort,
            required_skills=template["required_skills"],
            success_criteria=template["success_criteria"],
            metadata={
                "template_key": task_template_key,
                "task_number": task_number,
                "goal_context": goal.description[:100],  # Truncate if too long
                "inventory_context": {
                    "total_components": inventory.get("summary", {}).get("total_components", 0),
                    "unique_types": inventory.get("summary", {}).get("unique_types", 0)
                }
            }
        )
        
        return task
    
    def _build_dependency_graph(self, tasks: List[Task]) -> Dict[str, List[str]]:
        """Build dependency graph from tasks."""
        graph = {}
        
        for task in tasks:
            if task.dependencies:
                graph[task.task_id] = task.dependencies
        
        return graph
    
    def _estimate_resource_requirements(self, tasks: List[Task], inventory: Dict) -> Dict[str, Any]:
        """Estimate resource requirements for the plan."""
        total_effort = sum(task.estimated_effort for task in tasks)
        
        # Estimate based on task types and inventory size
        inventory_size = inventory.get("summary", {}).get("total_components", 0)
        
        requirements = {
            "estimated_total_effort": total_effort,
            "estimated_time_minutes": total_effort * 15,  # 15 minutes per effort point
            "memory_required_mb": 512,
            "disk_space_mb": max(100, inventory_size * 0.1),  # 0.1 MB per component
            "cpu_cores": 1,
            "specialized_requirements": []
        }
        
        # Adjust based on task types
        task_types = [task.task_type for task in tasks]
        if "refactoring" in task_types:
            requirements["memory_required_mb"] = 1024
            requirements["estimated_time_minutes"] *= 1.5
        
        if "testing" in task_types:
            requirements["cpu_cores"] = 2
            requirements["estimated_time_minutes"] *= 1.2
        
        return requirements
    
    def _identify_risks(self, tasks: List[Task], inventory: Dict, constraints: Dict) -> List[Dict[str, Any]]:
        """Identify potential risks in the plan."""
        risks = []
        
        # Check for complex refactoring tasks
        refactoring_tasks = [t for t in tasks if t.task_type == "refactoring"]
        if refactoring_tasks:
            risks.append({
                "risk_id": "risk_refactoring_complexity",
                "description": "Refactoring tasks may introduce bugs or break existing functionality",
                "severity": "medium",
                "probability": 0.3,
                "mitigation": "Ensure comprehensive testing and create rollback plan"
            })
        
        # Check for large inventory
        inventory_size = inventory.get("summary", {}).get("total_components", 0)
        if inventory_size > 1000:
            risks.append({
                "risk_id": "risk_large_inventory",
                "description": f"Large inventory ({inventory_size} components) may cause performance issues",
                "severity": "low",
                "probability": 0.4,
                "mitigation": "Implement incremental processing and monitor resource usage"
            })
        
        # Check recursion depth
        cycle_number = constraints.get("cycle_number", 1)
        if cycle_number >= self.max_recursion_depth:
            risks.append({
                "risk_id": "risk_max_recursion",
                "description": f"Approaching maximum recursion depth ({cycle_number}/{self.max_recursion_depth})",
                "severity": "high",
                "probability": 0.8,
                "mitigation": "Consider alternative approaches or request operator intervention"
            })
        
        # Check for missing dependencies in inventory
        missing_deps = self._check_missing_dependencies(tasks, inventory)
        if missing_deps:
            risks.append({
                "risk_id": "risk_missing_dependencies",
                "description": f"Missing dependencies detected: {', '.join(missing_deps[:3])}",
                "severity": "medium",
                "probability": 0.5,
                "mitigation": "Verify dependency availability or adjust plan"
            })
        
        return risks
    
    def _check_missing_dependencies(self, tasks: List[Task], inventory: Dict) -> List[str]:
        """Check for missing dependencies in inventory."""
        # This is a simplified check - in practice would compare against actual inventory
        missing = []
        
        # Check for common missing dependencies based on task types
        task_types = [task.task_type for task in tasks]
        
        if "testing" in task_types and "pytest" not in str(inventory):
            missing.append("pytest")
        
        if "documentation" in task_types and "mkdocs" not in str(inventory):
            missing.append("mkdocs")
        
        return missing
    
    def validate_plan(self, plan: Plan) -> Dict[str, Any]:
        """
        Validate a plan for correctness and feasibility.
        
        Args:
            plan: Plan to validate
            
        Returns:
            Validation results
        """
        validation = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "suggestions": []
        }
        
        # Check task count
        if len(plan.tasks) > self.max_tasks_per_plan:
            validation["warnings"].append(
                f"Plan has {len(plan.tasks)} tasks, exceeding recommended maximum of {self.max_tasks_per_plan}"
            )
        
        # Check for circular dependencies
        if self._has_circular_dependencies(plan.dependencies):
            validation["errors"].append("Circular dependencies detected in plan")
            validation["is_valid"] = False
        
        # Check task dependencies exist
        for task_id, deps in plan.dependencies.items():
            for dep in deps:
                if not any(t.task_id == dep for t in plan.tasks):
                    validation["errors"].append(f"Task {task_id} depends on non-existent task {dep}")
                    validation["is_valid"] = False
        
        # Check resource requirements are reasonable
        if plan.resource_requirements.get("estimated_time_minutes", 0) > 480:  # 8 hours
            validation["warnings"].append(
                f"Plan estimated time ({plan.resource_requirements['estimated_time_minutes']} minutes) exceeds 8 hours"
            )
        
        # Check for high-risk tasks without mitigation
        high_risk_tasks = [t for t in plan.tasks if t.estimated_effort >= 4]
        if high_risk_tasks and not plan.risks:
            validation["suggestions"].append(
                "Consider adding risk assessment for high-effort tasks"
            )
        
        return validation
    
    def _has_circular_dependencies(self, dependencies: Dict[str, List[str]]) -> bool:
        """Check for circular dependencies using DFS."""
        visited = set()
        recursion_stack = set()
        
        def dfs(node: str) -> bool:
            visited.add(node)
            recursion_stack.add(node)
            
            for neighbor in dependencies.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in recursion_stack:
                    return True
            
            recursion_stack.remove(node)
            return False
        
        for node in dependencies:
            if node not in visited:
                if dfs(node):
                    return True
        
        return False
    
    def decompose_task(self, task: Task, context: Dict) -> List[Task]:
        """
        Decompose a complex task into subtasks.
        
        Args:
            task: Task to decompose
            context: Additional context for decomposition
            
        Returns:
            List of subtasks
        """
        logger.info(f"Decomposing task: {task.description}")
        
        subtasks = []
        
        if task.task_type == "refactoring":
            # Decompose refactoring into analysis, implementation, testing
            subtasks.append(Task(
                task_id=f"{task.task_id}_analysis",
                description=f"Analyze code for refactoring: {task.description}",
                task_type="analysis",
                estimated_effort=2,
                required_skills=["static_analysis", "complexity_analysis"],
                success_criteria=["Analysis report generated", "Refactoring targets identified"]
            ))
            
            subtasks.append(Task(
                task_id=f"{task.task_id}_implementation",
                description=f"Implement refactoring: {task.description}",
                task_type="refactoring",
                dependencies=[f"{task.task_id}_analysis"],
                estimated_effort=3,
                required_skills=["refactoring", "code_generation"],
                success_criteria=["Code changes implemented", "Syntax valid"]
            ))
            
            subtasks.append(Task(
                task_id=f"{task.task_id}_testing",
                description=f"Test refactored code: {task.description}",
                task_type="testing",
                dependencies=[f"{task.task_id}_implementation"],
                estimated_effort=2,
                required_skills=["testing", "validation"],
                success_criteria=["All tests pass", "Functionality preserved"]
            ))
        
        elif task.task_type == "module_generation":
            # Decompose module generation into design, implementation, testing
            subtasks.append(Task(
                task_id=f"{task.task_id}_design",
                description=f"Design module: {task.description}",
                task_type="analysis",
                estimated_effort=2,
                required_skills=["api_design", "architecture"],
                success_criteria=["Design document created", "API specification defined"]
            ))
            
            subtasks.append(Task(
                task_id=f"{task.task_id}_implementation",
                description=f"Implement module: {task.description}",
                task_type="generation",
                dependencies=[f"{task.task_id}_design"],
                estimated_effort=3,
                required_skills=["code_generation", "api_implementation"],
                success_criteria=["Module code generated", "Basic functionality working"]
            ))
            
            subtasks.append(Task(
                task_id=f"{task.task_id}_testing",
                description=f"Test module: {task.description}",
                task_type="testing",
                dependencies=[f"{task.task_id}_implementation"],
                estimated_effort=2,
                required_skills=["testing", "validation"],
                success_criteria=["Tests pass", "Edge cases covered"]
            ))
        
        else:
            # Default: return task as-is (no decomposition)
            subtasks.append(task)
        
        logger.info(f"Decomposed into {len(subtasks)} subtasks")
        return subtasks


def main():
    """Command-line interface for planner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Create plans for self-compilation goals")
    parser.add_argument("goal", help="Goal description")
    parser.add_argument("--priority", default="medium", choices=["low", "medium", "high", "critical"],
                       help="Goal priority")
    parser.add_argument("--inventory-file", help="Path to inventory JSON file")
    parser.add_argument("--output", default=".", help="Output directory for plan files")
    parser.add_argument("--cycle-number", type=int, default=1, help="Recursion cycle number")
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Load inventory if provided
    inventory = {}
    if args.inventory_file and os.path.exists(args.inventory_file):
        with open(args.inventory_file, 'r') as f:
            inventory = json.load(f)
    
    # Create goal
    goal = Goal(
        goal_id=f"goal_{hashlib.md5(args.goal.encode()).hexdigest()[:8]}",
        description=args.goal,
        priority=args.priority,
        success_criteria=[f"Complete: {args.goal}"]
    )
    
    # Create constraints
    constraints = {
        "cycle_number": args.cycle_number,
        "target_directory": inventory.get("root_directories", ["."])[0] if inventory else "."
    }
    
    # Create plan
    planner = Planner()
    plan = planner.create_plan(goal, inventory, constraints)
    
    # Validate plan
    validation = planner.validate_plan(plan)
    
    # Save plan
    plan_path = os.path.join(args.output, f"plan_{plan.plan_id}.json")
    plan.save(plan_path)
    
    print(f"✅ Plan created: {plan_path}")
    print(f"   Tasks: {len(plan.tasks)}")
    print(f"   Estimated effort: {sum(t.estimated_effort for t in plan.tasks)}")
    print(f"   Validation: {'Valid' if validation['is_valid'] else 'Invalid'}")
    
    if validation['warnings']:
        print(f"   Warnings: {len(validation['warnings'])}")
    if validation['errors']:
        print(f"   Errors: {len(validation['errors'])}")


if __name__ == "__main__":
    main()