#!/usr/bin/env python3
"""
Prompt Compiler for Sovereign Self Compiler v2.

Compiles structured self-prompts from plans and context.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
import hashlib
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class CompiledPrompt:
    """A compiled prompt ready for execution."""
    prompt_id: str
    goal_id: str
    cycle_number: int
    task_summary: str
    prompt_text: str
    expected_artifacts: List[str]
    execution_mode: str  # "python", "bash", "document_transform", "analysis_only"
    evaluation_requirements: Dict[str, Any]
    max_recursion_depth: int
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def save(self, path: str) -> None:
        """Save prompt to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        logger.info(f"Prompt saved to {path}")


class PromptCompiler:
    """Compiles structured prompts from plans and context."""
    
    # Prompt templates for different task types
    PROMPT_TEMPLATES = {
        "inventory": {
            "template": """Create a Python module that scans a codebase directory and creates a structured inventory.

Requirements:
1. Scan directory: {target_directory}
2. Maximum recursion depth: {max_depth}
3. Exclude patterns: {exclude_patterns}
4. Classify files by type and purpose
5. Generate JSON output with: file path, size, modified time, classification, dependencies
6. Include dependency analysis

Output files:
- {module_name}.py: The inventory scanner module
- inventory_config.json: Configuration for the scanner
- README.md: Documentation for the scanner

Constraints:
- Use Python standard library where possible
- Handle large directories efficiently
- Provide progress reporting
- Include error handling

Example output format:
{{
  "inventory_id": "inv_abc123",
  "timestamp": "2026-04-14T13:37:00Z",
  "total_components": 150,
  "components_by_type": {{"python": 100, "config": 20, "documentation": 30}},
  "components": [
    {{
      "path": "simp/server/broker.py",
      "component_type": "server",
      "size_bytes": 1500,
      "modified_time": "2026-04-14T12:00:00Z",
      "language": "python",
      "dependencies": ["flask", "json", "threading"],
      "classification": "simp_broker"
    }}
  ]
}}

Write clean, well-documented code with appropriate error handling.""",
            "execution_mode": "python",
            "expected_artifacts": ["{module_name}.py", "inventory_config.json", "README.md"],
            "evaluation_requirements": {
                "schema_validation": True,
                "syntax_check": True,
                "tests_run": ["test_basic_scan", "test_classification"],
                "policy_check": "basic",
                "performance_requirements": {
                    "max_execution_time_seconds": 30,
                    "max_memory_mb": 256
                }
            }
        },
        
        "analysis": {
            "template": """Analyze the codebase structure and dependencies for: {analysis_target}

Requirements:
1. Analyze: {analysis_target}
2. Focus on: {analysis_focus}
3. Generate metrics for: {metrics}
4. Identify patterns and issues
5. Provide recommendations

Output files:
- analysis_report.json: Structured analysis results
- dependency_graph.json: Dependency relationships
- recommendations.md: Actionable recommendations

Analysis should include:
- Code complexity metrics
- Dependency relationships
- Architecture patterns
- Potential issues
- Improvement opportunities

Example metrics:
- Cyclomatic complexity
- Lines of code
- Dependency count
- Test coverage (if available)
- Code duplication

Provide actionable insights and prioritize recommendations.""",
            "execution_mode": "analysis_only",
            "expected_artifacts": ["analysis_report.json", "dependency_graph.json", "recommendations.md"],
            "evaluation_requirements": {
                "schema_validation": True,
                "syntax_check": False,
                "policy_check": "basic",
                "completeness_check": True
            }
        },
        
        "generation": {
            "template": """Create a Python module for: {module_purpose}

Module purpose: {module_purpose}
Requirements: {requirements}
Design constraints: {constraints}

Output files:
- {module_name}.py: The main module
- test_{module_name}.py: Unit tests
- README.md: Documentation
- example_usage.py: Example usage

Code requirements:
- Follow Python best practices
- Include type hints
- Add comprehensive docstrings
- Implement error handling
- Write unit tests with good coverage
- Make it reusable and extensible

Design considerations:
- API design should be intuitive
- Configuration should be flexible
- Logging should be comprehensive
- Performance should be considered

Example structure:
```
# {module_name}.py
\"\"\"
{module_purpose}

Example usage:
    from {module_name} import {class_name}
    instance = {class_name}(config)
    result = instance.process(data)
\"\"\"

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Config:
    \"\"\"Configuration for {class_name}.\"\"\"
    param1: str = "default"
    param2: int = 100

class {class_name}:
    \"\"\"Main class for {module_purpose}.\"\"\"
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def process(self, data: Dict) -> Dict:
        \"\"\"Process data according to configuration.\"\"\"
        try:
            # Implementation here
            result = {{"status": "success", "data": data}}
            self.logger.info("Processing completed")
            return result
        except Exception as e:
            self.logger.error(f"Processing failed: {{e}}")
            raise
```

Write production-ready code with comprehensive documentation and tests.""",
            "execution_mode": "python",
            "expected_artifacts": ["{module_name}.py", "test_{module_name}.py", "README.md", "example_usage.py"],
            "evaluation_requirements": {
                "schema_validation": True,
                "syntax_check": True,
                "tests_run": ["test_{module_name}"],
                "policy_check": "basic",
                "performance_requirements": {
                    "max_execution_time_seconds": 60,
                    "max_memory_mb": 512
                }
            }
        },
        
        "refactoring": {
            "template": """Refactor the following code/file for improvement: {refactoring_target}

Current issues: {issues}
Refactoring goals: {goals}
Constraints: {constraints}

Requirements:
1. Preserve all existing functionality
2. Improve code quality and maintainability
3. Follow Python best practices
4. Add/update tests as needed
5. Update documentation

Output files:
- refactored_{file_name}: Refactored code
- refactoring_report.md: Summary of changes
- test_refactored_{module_name}.py: Updated tests

Refactoring techniques to consider:
- Extract functions/methods
- Simplify complex logic
- Improve naming
- Add type hints
- Enhance error handling
- Improve documentation
- Optimize performance

Before refactoring, ensure:
1. Existing tests pass
2. Functionality is understood
3. Dependencies are identified
4. Rollback plan is available

Provide clear before/after comparisons and justification for changes.""",
            "execution_mode": "python",
            "expected_artifacts": ["refactored_{file_name}", "refactoring_report.md", "test_refactored_{module_name}.py"],
            "evaluation_requirements": {
                "schema_validation": True,
                "syntax_check": True,
                "tests_run": ["test_refactored_{module_name}"],
                "policy_check": "strict",
                "backward_compatibility": True,
                "performance_requirements": {
                    "max_execution_time_seconds": 120,
                    "max_memory_mb": 512
                }
            }
        },
        
        "testing": {
            "template": """Create comprehensive tests for: {test_target}

Test target: {test_target}
Test types needed: {test_types}
Coverage goals: {coverage_goals}
Testing framework: {test_framework}

Output files:
- test_{module_name}.py: Test suite
- test_config.json: Test configuration
- coverage_report.md: Coverage analysis

Test requirements:
- Unit tests for all public functions
- Integration tests for key workflows
- Edge case testing
- Performance testing if applicable
- Mock external dependencies
- Use pytest fixtures appropriately
- Include parameterized tests

Test structure should follow:
```
# test_{module_name}.py
\"\"\"Tests for {module_name} module.\"\"\"

import pytest
from {module_name} import {class_name}, Config

class Test{class_name}:
    \"\"\"Test suite for {class_name}.\"\"\"
    
    @pytest.fixture
    def config(self):
        return Config(param1="test", param2=42)
    
    @pytest.fixture
    def instance(self, config):
        return {class_name}(config)
    
    def test_initialization(self, instance):
        \"\"\"Test that instance initializes correctly.\"\"\"
        assert instance.config.param1 == "test"
        assert instance.config.param2 == 42
    
    def test_process_success(self, instance):
        \"\"\"Test successful processing.\"\"\"
        data = {{"key": "value"}}
        result = instance.process(data)
        assert result["status"] == "success"
        assert "data" in result
    
    @pytest.mark.parametrize("invalid_data", [
        None,
        {{}},
        "not_a_dict",
        123
    ])
    def test_process_invalid_input(self, instance, invalid_data):
        \"\"\"Test processing with invalid input.\"\"\"
        with pytest.raises((ValueError, TypeError)):
            instance.process(invalid_data)
```

Aim for >80% test coverage and include both happy path and error cases.""",
            "execution_mode": "python",
            "expected_artifacts": ["test_{module_name}.py", "test_config.json", "coverage_report.md"],
            "evaluation_requirements": {
                "schema_validation": True,
                "syntax_check": True,
                "tests_run": ["test_{module_name}"],
                "policy_check": "basic",
                "coverage_requirement": 0.8,
                "performance_requirements": {
                    "max_execution_time_seconds": 90,
                    "max_memory_mb": 256
                }
            }
        },
        
        "documentation": {
            "template": """Create comprehensive documentation for: {documentation_target}

Documentation target: {documentation_target}
Audience: {audience}
Documentation types: {doc_types}
Style guide: {style_guide}

Output files:
- README.md: Main documentation
- API_REFERENCE.md: API documentation
- EXAMPLES.md: Usage examples
- ARCHITECTURE.md: Architecture overview

Documentation requirements:
- Clear, concise writing
- Code examples for all major features
- Installation and setup instructions
- API reference with type hints
- Troubleshooting guide
- Contribution guidelines
- Version compatibility notes

Structure should include:
1. Overview and purpose
2. Installation instructions
3. Quick start guide
4. Detailed usage examples
5. API reference
6. Architecture and design decisions
7. Contributing guidelines
8. License information

Use markdown formatting with code blocks, tables, and links as appropriate.
Include diagrams if helpful (describe them textually).

Example README structure:
```
# {module_name}

{one_line_description}

## Features
- Feature 1: Description
- Feature 2: Description
- Feature 3: Description

## Installation
```bash
pip install {module_name}
```

## Quick Start
```python
from {module_name} import {class_name}

# Initialize
instance = {class_name}(config={{...}})

# Use
result = instance.process(data)
```

## Documentation
- [API Reference](API_REFERENCE.md)
- [Examples](EXAMPLES.md)
- [Architecture](ARCHITECTURE.md)

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md)

## License
MIT
```

Create professional, comprehensive documentation suitable for open-source projects.""",
            "execution_mode": "document_transform",
            "expected_artifacts": ["README.md", "API_REFERENCE.md", "EXAMPLES.md", "ARCHITECTURE.md"],
            "evaluation_requirements": {
                "schema_validation": False,
                "syntax_check": True,  # Check markdown syntax
                "policy_check": "basic",
                "completeness_check": True,
                "readability_check": True
            }
        }
    }
    
    # Context extractors for different task types
    CONTEXT_EXTRACTORS = {
        "inventory": lambda task, context: {
            "target_directory": context.get("target_directory", "."),
            "max_depth": context.get("max_depth", 5),
            "exclude_patterns": context.get("exclude_patterns", [".git/", "__pycache__/"]),
            "module_name": self._extract_module_name(task.description)
        },
        "analysis": lambda task, context: {
            "analysis_target": self._extract_analysis_target(task.description),
            "analysis_focus": context.get("analysis_focus", "code quality and dependencies"),
            "metrics": context.get("metrics", ["complexity", "dependencies", "patterns"])
        },
        "generation": lambda task, context: {
            "module_purpose": task.description,
            "requirements": context.get("requirements", "Follow Python best practices"),
            "constraints": context.get("constraints", "Use standard library where possible"),
            "module_name": self._extract_module_name(task.description),
            "class_name": self._module_to_class_name(self._extract_module_name(task.description))
        },
        "refactoring": lambda task, context: {
            "refactoring_target": self._extract_refactoring_target(task.description),
            "issues": context.get("issues", ["code complexity", "poor naming", "lack of documentation"]),
            "goals": context.get("goals", ["improve maintainability", "add tests", "enhance documentation"]),
            "constraints": context.get("constraints", "preserve existing functionality"),
            "file_name": self._extract_file_name(task.description),
            "module_name": self._extract_module_name(task.description)
        },
        "testing": lambda task, context: {
            "test_target": self._extract_test_target(task.description),
            "test_types": context.get("test_types", ["unit", "integration", "edge cases"]),
            "coverage_goals": context.get("coverage_goals", ">80% coverage"),
            "test_framework": context.get("test_framework", "pytest"),
            "module_name": self._extract_module_name(task.description),
            "class_name": self._module_to_class_name(self._extract_module_name(task.description))
        },
        "documentation": lambda task, context: {
            "documentation_target": self._extract_documentation_target(task.description),
            "audience": context.get("audience", "developers and users"),
            "doc_types": context.get("doc_types", ["README", "API reference", "examples", "architecture"]),
            "style_guide": context.get("style_guide", "clear, concise, with code examples"),
            "module_name": self._extract_module_name(task.description),
            "class_name": self._module_to_class_name(self._extract_module_name(task.description)),
            "one_line_description": self._extract_one_line_description(task.description)
        }
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize prompt compiler with configuration."""
        self.config = config or {}
        
    def compile_prompt(self, plan: Dict, context: Dict) -> CompiledPrompt:
        """
        Compile a structured prompt from a plan and context.
        
        Args:
            plan: Plan dictionary (from planner)
            context: Additional context including inventory, constraints, etc.
            
        Returns:
            CompiledPrompt object
        """
        logger.info(f"Compiling prompt for plan: {plan.get('plan_id', 'unknown')}")
        
        # Extract task from plan (for now, use first task)
        tasks = plan.get("tasks", [])
        if not tasks:
            raise ValueError("Plan has no tasks")
        
        task = tasks[0]  # For MVP, use first task
        task_type = task.get("task_type", "generation")
        
        # Generate prompt ID
        prompt_id = f"prompt_{hashlib.md5(str(plan.get('plan_id', '')).encode()).hexdigest()[:8]}_{int(datetime.now().timestamp())}"
        
        # Get template for task type
        template_info = self.PROMPT_TEMPLATES.get(task_type, self.PROMPT_TEMPLATES["generation"])
        
        # Extract context for this task type
        context_extractor = self.CONTEXT_EXTRACTORS.get(task_type, lambda t, c: {})
        template_context = context_extractor(task, context)
        
        # Compile prompt text
        prompt_text = self._compile_template(template_info["template"], template_context)
        
        # Compile expected artifacts
        expected_artifacts = [
            self._compile_template(artifact, template_context)
            for artifact in template_info["expected_artifacts"]
        ]
        
        # Compile evaluation requirements
        evaluation_requirements = template_info["evaluation_requirements"].copy()
        if "tests_run" in evaluation_requirements:
            evaluation_requirements["tests_run"] = [
                self._compile_template(test, template_context)
                for test in evaluation_requirements["tests_run"]
            ]
        
        # Create compiled prompt
        prompt = CompiledPrompt(
            prompt_id=prompt_id,
            goal_id=plan.get("goal_id", ""),
            cycle_number=plan.get("cycle_number", 1),
            task_summary=task.get("description", ""),
            prompt_text=prompt_text,
            expected_artifacts=expected_artifacts,
            execution_mode=template_info["execution_mode"],
            evaluation_requirements=evaluation_requirements,
            max_recursion_depth=plan.get("metadata", {}).get("planning_config", {}).get("max_recursion_depth", 3),
            context={
                "plan_context": {
                    "plan_id": plan.get("plan_id"),
                    "goal_description": plan.get("metadata", {}).get("goal_description", ""),
                    "task_details": task
                },
                "inventory_context": context.get("inventory", {}),
                "learning_context": context.get("previous_traces", []),
                "constraints": context.get("constraints", {})
            },
            metadata={
                "template_used": task_type,
                "template_context": template_context,
                "compilation_time": datetime.utcnow().isoformat() + 'Z',
                "compiler_version": "1.0.0",
                "task_metadata": task.get("metadata", {})
            }
        )
        
        logger.info(f"Prompt compiled with {len(expected_artifacts)} expected artifacts")
        return prompt
    
    def _compile_template(self, template: str, context: Dict) -> str:
        """Compile a template string with context."""
        try:
            return template.format(**context)
        except KeyError as e:
            logger.warning(f"Missing context key {e} in template, using placeholder")
            # Replace missing keys with placeholders
            compiled = template
            for key in context:
                compiled = compiled.replace(f"{{{key}}}", str(context[key]))
            # Replace any remaining {key} with "unknown"
            compiled = re.sub(r'\{[^}]*\}', 'unknown', compiled)
            return compiled
    
    def _extract_module_name(self, description: str) -> str:
        """Extract module name from task description."""
        # Look for patterns like "create inventory module" or "inventory scanner"
        words = description.lower().split()
        
        # Common module name patterns
        for i, word in enumerate(words):
            if word in ["module", "scanner", "analyzer", "generator", "manager", "engine"]:
                if i > 0:
                    return f"{words[i-1]}_{word}"
        
        # Default: use first meaningful word + "_module"
        for word in words:
            if len(word) > 3 and word not in ["create", "generate", "build", "make", "for", "the", "and"]:
                return f"{word}_module"
        
        return "unknown_module"
    
    def _module_to_class_name(self, module_name: str) -> str:
        """Convert module name to class name (snake_case to PascalCase)."""
        if "_" in module_name:
            parts = module_name.split("_")
            return "".join(part.capitalize() for part in parts)
        return module_name.capitalize()
    
    def _extract_analysis_target(self, description: str) -> str:
        """Extract analysis target from task description."""
        # Look for patterns like "analyze code structure" or "analysis of dependencies"
        if "analyze" in description.lower() or "analysis" in description.lower():
            # Return the part after "analyze" or "analysis of"
            import re
            match = re.search(r'(?:analyze|analysis of)\s+(.+)', description.lower())
            if match:
                return match.group(1).capitalize()
        
        return "codebase structure and dependencies"
    
    def _extract_refactoring_target(self, description: str) -> str:
        """Extract refactoring target from task description."""
        # Look for patterns like "refactor inventory module" or "refactoring of server.py"
        if "refactor" in description.lower():
            import re
            match = re.search(r'refactor\s+(.+)', description.lower())
            if match:
                return match.group(1)
        
        return "specified code"
    
    def _extract_file_name(self, description: str) -> str:
        """Extract file name from task description."""
        # Look for .py files in description
        import re
        match = re.search(r'(\w+\.py)', description)
        if match:
            return match.group(1)
        
        # Otherwise use module name
        module_name = self._extract_module_name(description)
        return f"{module_name}.py"
    
    def _extract_test_target(self, description: str) -> str:
        """Extract test target from task description."""
        # Look for patterns like "test inventory module" or "testing for server.py"
        if "test" in description.lower():
            import re
            match = re.search(r'test\s+(.+)', description.lower())
            if match:
                return match.group(1)
        
        return "specified module"
    
    def _extract_documentation_target(self, description: str) -> str:
        """Extract documentation target from task description."""
        # Look for patterns like "document inventory module" or "documentation for API"
        if "document" in description.lower():
            import re
            match = re.search(r'document\s+(.+)', description.lower())
            if match:
                return match.group(1)
        
        return "specified system or module"
    
    def _extract_one_line_description(self, description: str) -> str:
        """Extract one-line description from task description."""
        # Take first sentence or first 100 characters
        sentences = description.split('.')
        if sentences and sentences[0]:
            return sentences[0].strip()
        
        return description[:100].strip() + ("..." if len(description) > 100 else "")
    
    def validate_prompt(self, prompt: CompiledPrompt) -> Dict[str, Any]:
        """
        Validate a compiled prompt for correctness.
        
        Args:
            prompt: CompiledPrompt to validate
            
        Returns:
            Validation results
        """
        validation = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "suggestions": []
        }
        
        # Check prompt text length
        if len(prompt.prompt_text) < 100:
            validation["warnings"].append("Prompt text is very short (< 100 characters)")
        elif len(prompt.prompt_text) > 10000:
            validation["warnings"].append("Prompt text is very long (> 10,000 characters)")
        
        # Check expected artifacts
        if not prompt.expected_artifacts:
            validation["errors"].append("No expected artifacts specified")
            validation["is_valid"] = False
        
        # Check for valid file extensions in artifacts
        valid_extensions = [".py", ".md", ".json", ".yaml", ".yml", ".txt", ".toml"]
        for artifact in prompt.expected_artifacts:
            if not any(artifact.endswith(ext) for ext in valid_extensions):
                validation["warnings"].append(
                    f"Artifact '{artifact}' has unusual extension (expected: {', '.join(valid_extensions)})"
                )
        
        # Check execution mode
        valid_modes = ["python", "bash", "document_transform", "analysis_only"]
        if prompt.execution_mode not in valid_modes:
            validation["errors"].append(f"Invalid execution mode: {prompt.execution_mode}")
            validation["is_valid"] = False
        
        # Check evaluation requirements
        if not prompt.evaluation_requirements:
            validation["warnings"].append("No evaluation requirements specified")
        
        # Check recursion depth
        if prompt.max_recursion_depth > 10:
            validation["warnings"].append(f"High max recursion depth: {prompt.max_recursion_depth}")
        
        # Check context completeness
        if not prompt.context:
            validation["warnings"].append("No context provided")
        
        return validation
    
    def version_prompt(self, prompt: CompiledPrompt, version_scheme: str = "semantic") -> CompiledPrompt:
        """
        Version a prompt according to specified scheme.
        
        Args:
            prompt: Prompt to version
            version_scheme: Versioning scheme ("semantic", "timestamp", "incremental")
            
        Returns:
            Versioned prompt (new instance)
        """
        import copy
        
        # Create a copy of the prompt
        versioned_prompt = copy.deepcopy(prompt)
        
        # Update metadata with version info
        current_version = prompt.metadata.get("prompt_version", "1.0.0")
        
        if version_scheme == "semantic":
            # Simple semantic version bump (patch level)
            import re
            match = re.match(r'(\d+)\.(\d+)\.(\d+)', current_version)
            if match:
                major, minor, patch = map(int, match.groups())
                new_version = f"{major}.{minor}.{patch + 1}"
            else:
                new_version = "1.0.1"
        
        elif version_scheme == "timestamp":
            # Use timestamp as version
            new_version = datetime.utcnow().strftime("%Y%m%d.%H%M%S")
        
        elif version_scheme == "incremental":
            # Simple incremental version
            if "_v" in current_version:
                base, num = current_version.rsplit("_v", 1)
                try:
                    new_num = int(num) + 1
                    new_version = f"{base}_v{new_num}"
                except ValueError:
                    new_version = f"{current_version}_v2"
            else:
                new_version = f"{current_version}_v2"
        
        else:
            new_version = current_version
        
        # Update prompt metadata
        versioned_prompt.metadata["prompt_version"] = new_version
        versioned_prompt.metadata["version_scheme"] = version_scheme
        versioned_prompt.metadata["previous_version"] = current_version
        versioned_prompt.metadata["versioned_at"] = datetime.utcnow().isoformat() + 'Z'
        
        # Update prompt ID to reflect version
        versioned_prompt.prompt_id = f"{prompt.prompt_id}_v{new_version.replace('.', '_')}"
        
        logger.info(f"Prompt versioned: {current_version} -> {new_version}")
        return versioned_prompt


def main():
    """Command-line interface for prompt compiler."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Compile prompts from plans")
    parser.add_argument("plan_file", help="Path to plan JSON file")
    parser.add_argument("--context-file", help="Path to context JSON file")
    parser.add_argument("--output", default=".", help="Output directory for prompt files")
    parser.add_argument("--validate", action="store_true", help="Validate the compiled prompt")
    parser.add_argument("--version", action="store_true", help="Version the prompt")
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Load plan
    if not os.path.exists(args.plan_file):
        print(f"Error: Plan file not found: {args.plan_file}")
        return
    
    with open(args.plan_file, 'r') as f:
        plan = json.load(f)
    
    # Load context if provided
    context = {}
    if args.context_file and os.path.exists(args.context_file):
        with open(args.context_file, 'r') as f:
            context = json.load(f)
    
    # Compile prompt
    compiler = PromptCompiler()
    prompt = compiler.compile_prompt(plan, context)
    
    # Validate if requested
    if args.validate:
        validation = compiler.validate_prompt(prompt)
        print(f"Validation: {'Valid' if validation['is_valid'] else 'Invalid'}")
        if validation['warnings']:
            print(f"Warnings: {len(validation['warnings'])}")
            for warning in validation['warnings'][:3]:
                print(f"  - {warning}")
        if validation['errors']:
            print(f"Errors: {len(validation['errors'])}")
            for error in validation['errors']:
                print(f"  - {error}")
    
    # Version if requested
    if args.version:
        prompt = compiler.version_prompt(prompt)
        print(f"Versioned: {prompt.metadata['prompt_version']}")
    
    # Save prompt
    prompt_path = os.path.join(args.output, f"prompt_{prompt.prompt_id}.json")
    prompt.save(prompt_path)
    
    print(f"✅ Prompt compiled: {prompt_path}")
    print(f"   Task: {prompt.task_summary}")
    print(f"   Execution mode: {prompt.execution_mode}")
    print(f"   Expected artifacts: {len(prompt.expected_artifacts)}")
    print(f"   Prompt length: {len(prompt.prompt_text)} characters")


if __name__ == "__main__":
    main()