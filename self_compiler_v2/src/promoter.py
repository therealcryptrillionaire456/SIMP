#!/usr/bin/env python3
"""
Promoter for Sovereign Self Compiler v2.

Handles staging vs promotion decisions with safety checks,
ProjectX integration, and rollback guarantees.
"""

import json
import logging
import shutil
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PromotionOutcome(Enum):
    """Promotion decision outcomes."""
    PROMOTE = "PROMOTE"
    REJECT = "REJECT"
    REVISE = "REVISE"
    ESCALATE = "ESCALATE"


class ProjectXJudgment(Enum):
    """ProjectX safety judgments."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


@dataclass
class RollbackPlan:
    """Plan for rolling back a promotion."""
    rollback_id: str
    promotion_id: str
    backup_paths: Dict[str, str]  # target_path -> backup_path
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def save(self, output_path: Path) -> None:
        """Save rollback plan to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


@dataclass
class PromotionResult:
    """Result of a promotion decision."""
    promotion_id: str
    evaluation_id: str
    execution_id: str
    prompt_id: str
    outcome: str  # PROMOTE, REJECT, REVISE, ESCALATE
    timestamp: str
    artifacts_promoted: List[str] = field(default_factory=list)
    artifacts_rejected: List[str] = field(default_factory=list)
    target_paths: Dict[str, str] = field(default_factory=dict)  # artifact -> target
    rollback_plan: Optional[RollbackPlan] = None
    projectx_judgment: Optional[str] = None
    projectx_reason: Optional[str] = None
    operator_approval_required: bool = False
    operator_approved: Optional[bool] = None
    feedback: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        if self.rollback_plan:
            result["rollback_plan"] = self.rollback_plan.to_dict()
        return result
    
    def save(self, output_path: Path) -> None:
        """Save promotion result to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class ProjectXClient:
    """Client for ProjectX safety review."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ProjectX client.
        
        Args:
            config: ProjectX configuration from self_compiler_config.json
        """
        self.enabled = config.get("enabled", True)
        self.endpoint = config.get("endpoint", "http://localhost:8771")
        self.timeout = config.get("timeout_seconds", 30)
        self.cache_judgments = config.get("cache_judgments", True)
        self.cache_ttl = config.get("cache_ttl_seconds", 3600)
        
        # Simple in-memory cache
        self.judgment_cache: Dict[str, Tuple[str, str, float]] = {}
        
        logger.info(f"ProjectX client initialized (enabled: {self.enabled})")
    
    def review_promotion(
        self, artifacts: List[str], target_paths: Dict[str, str], context: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Request ProjectX review for promotion.
        
        Args:
            artifacts: List of artifact paths to promote
            target_paths: Mapping of artifact -> target path
            context: Additional context for review
            
        Returns:
            Tuple of (judgment, reason)
        """
        if not self.enabled:
            return ProjectXJudgment.ALLOW.value, "ProjectX disabled"
        
        # Create cache key
        cache_key = self._create_cache_key(artifacts, target_paths)
        
        # Check cache
        if self.cache_judgments and cache_key in self.judgment_cache:
            judgment, reason, timestamp = self.judgment_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                logger.info(f"Using cached ProjectX judgment: {judgment}")
                return judgment, reason
        
        try:
            # Prepare request
            request_data = {
                "artifacts": artifacts,
                "target_paths": target_paths,
                "context": context,
                "request_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            # Send request to ProjectX
            response = requests.post(
                f"{self.endpoint}/review/promotion",
                json=request_data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                judgment = result.get("judgment", ProjectXJudgment.ESCALATE.value)
                reason = result.get("reason", "No reason provided")
                
                # Cache result
                if self.cache_judgments:
                    self.judgment_cache[cache_key] = (judgment, reason, time.time())
                
                logger.info(f"ProjectX judgment: {judgment} - {reason}")
                return judgment, reason
            else:
                logger.warning(f"ProjectX request failed: {response.status_code}")
                return ProjectXJudgment.ESCALATE.value, f"ProjectX error: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"ProjectX connection failed: {e}")
            return ProjectXJudgment.ESCALATE.value, f"Connection failed: {str(e)}"
        except Exception as e:
            logger.error(f"ProjectX review failed: {e}")
            return ProjectXJudgment.ESCALATE.value, f"Review failed: {str(e)}"
    
    def _create_cache_key(self, artifacts: List[str], target_paths: Dict[str, str]) -> str:
        """Create cache key for artifacts and target paths."""
        import hashlib
        
        key_data = {
            "artifacts": sorted(artifacts),
            "targets": sorted(target_paths.items())
        }
        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_json.encode()).hexdigest()


class Promoter:
    """Promoter for handling artifact promotion decisions."""
    
    def __init__(self, config: Dict[str, Any], staging_root: Path, promotion_root: Path):
        """
        Initialize promoter with configuration.
        
        Args:
            config: Promoter configuration from self_compiler_config.json
            staging_root: Root directory for staging artifacts
            promotion_root: Root directory for promoted artifacts
        """
        self.config = config
        self.staging_root = staging_root
        self.promotion_root = promotion_root
        self.backup_root = promotion_root.parent / "backups"
        
        # Promotion settings
        self.auto_promote = config.get("auto_promote", False)
        self.require_operator_approval = config.get("require_operator_approval", True)
        self.create_backups = config.get("create_backups", True)
        self.generate_rollback_plan = config.get("generate_rollback_plan", True)
        
        # Sensitive actions requiring ProjectX
        self.sensitive_actions = config.get("sensitive_actions_require_projectx", [])
        
        # Initialize ProjectX client
        projectx_config = config.get("projectx", {})
        self.projectx = ProjectXClient(projectx_config)
        
        # Ensure directories exist
        self.promotion_root.mkdir(parents=True, exist_ok=True)
        self.backup_root.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Promoter initialized with staging: {staging_root}, promotion: {promotion_root}")
    
    def make_promotion_decision(
        self,
        evaluation_result: Dict[str, Any],
        execution_result: Dict[str, Any],
        prompt: Dict[str, Any],
        operator_approved: Optional[bool] = None
    ) -> PromotionResult:
        """
        Make promotion decision based on evaluation.
        
        Args:
            evaluation_result: Evaluation result from evaluator
            execution_result: Execution result from executor
            prompt: Original prompt specification
            operator_approved: Optional operator approval status
            
        Returns:
            PromotionResult with decision and details
        """
        promotion_id = str(uuid.uuid4())
        evaluation_id = evaluation_result.get("evaluation_id", "unknown")
        execution_id = execution_result.get("execution_id", "unknown")
        prompt_id = prompt.get("prompt_id", "unknown")
        
        logger.info(f"Making promotion decision {promotion_id} for evaluation {evaluation_id}")
        
        # Get evaluation details
        recommendation = evaluation_result.get("promotion_recommendation", "REJECT")
        overall_score = evaluation_result.get("overall_score", 0.0)
        gate_results = evaluation_result.get("gate_results", [])
        
        # Get artifacts
        artifacts_created = execution_result.get("artifacts_created", [])
        expected_artifacts = prompt.get("expected_artifacts", [])
        
        # Create initial result
        result = PromotionResult(
            promotion_id=promotion_id,
            evaluation_id=evaluation_id,
            execution_id=execution_id,
            prompt_id=prompt_id,
            outcome=recommendation,
            timestamp=datetime.utcnow().isoformat() + "Z",
            artifacts_rejected=artifacts_created.copy()  # Start with all rejected
        )
        
        # Check if we should proceed
        if recommendation == "REJECT":
            result.feedback = "Evaluation recommends rejection"
            return result
        
        # Determine target paths for artifacts
        target_paths = self._determine_target_paths(artifacts_created, expected_artifacts, prompt)
        result.target_paths = target_paths
        
        # Check for sensitive paths
        requires_projectx = self._requires_projectx_review(target_paths.values(), prompt)
        
        if requires_projectx:
            # Get ProjectX judgment
            context = {
                "prompt": prompt,
                "evaluation": evaluation_result,
                "execution": execution_result
            }
            
            judgment, reason = self.projectx.review_promotion(
                list(target_paths.keys()),
                target_paths,
                context
            )
            
            result.projectx_judgment = judgment
            result.projectx_reason = reason
            
            if judgment == ProjectXJudgment.BLOCK.value:
                result.outcome = "REJECT"
                result.feedback = f"ProjectX blocked promotion: {reason}"
                return result
            elif judgment == ProjectXJudgment.ESCALATE.value:
                result.outcome = "ESCALATE"
                result.feedback = f"ProjectX escalation required: {reason}"
                return result
            # ALLOW continues below
        
        # Check operator approval
        if self.require_operator_approval and operator_approved is None:
            result.outcome = "ESCALATE"
            result.operator_approval_required = True
            result.feedback = "Operator approval required"
            return result
        
        if self.require_operator_approval and operator_approved is False:
            result.outcome = "REJECT"
            result.operator_approved = False
            result.feedback = "Operator rejected promotion"
            return result
        
        # All checks passed - proceed with promotion
        if recommendation == "PROMOTE":
            # Execute promotion
            promoted_artifacts, rollback_plan = self._execute_promotion(
                promotion_id, target_paths, prompt
            )
            
            result.outcome = "PROMOTE"
            result.artifacts_promoted = promoted_artifacts
            result.artifacts_rejected = [
                a for a in artifacts_created if a not in promoted_artifacts
            ]
            result.rollback_plan = rollback_plan
            result.operator_approved = operator_approved if self.require_operator_approval else None
            result.feedback = f"Promoted {len(promoted_artifacts)} artifacts"
            
        elif recommendation == "REVISE":
            result.outcome = "REVISE"
            result.feedback = evaluation_result.get("feedback_summary", "Revision required")
        
        elif recommendation == "ESCALATE":
            result.outcome = "ESCALATE"
            result.feedback = "Escalation required for manual review"
        
        return result
    
    def _determine_target_paths(
        self, artifacts_created: List[str], expected_artifacts: List[str], prompt: Dict[str, Any]
    ) -> Dict[str, str]:
        """Determine target paths for artifacts."""
        target_paths = {}
        
        # Get context from prompt
        context = prompt.get("context", {})
        constraints = context.get("constraints", {})
        
        # Simple mapping: if artifact matches expected pattern, use it
        for artifact_path in artifacts_created:
            artifact = Path(artifact_path)
            if not artifact.exists():
                continue
            
            # Find matching expected artifact
            target_path = None
            for expected in expected_artifacts:
                if artifact.name == Path(expected).name:
                    # Use expected path relative to promotion root
                    target_path = self.promotion_root / expected
                    break
            
            # If no match, place in generic location
            if not target_path:
                # Create organized directory structure
                artifact_type = self._classify_artifact(artifact)
                target_dir = self.promotion_root / artifact_type / prompt.get("prompt_id", "unknown")
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / artifact.name
            
            target_paths[artifact_path] = str(target_path)
        
        return target_paths
    
    def _classify_artifact(self, artifact: Path) -> str:
        """Classify artifact by type."""
        suffix = artifact.suffix.lower()
        
        if suffix == '.py':
            return "python_modules"
        elif suffix == '.md':
            return "documentation"
        elif suffix in ['.json', '.yaml', '.yml', '.toml']:
            return "configurations"
        elif suffix in ['.txt', '.log']:
            return "text_files"
        else:
            return "other"
    
    def _requires_projectx_review(self, target_paths: List[str], prompt: Dict[str, Any]) -> bool:
        """Check if promotion requires ProjectX review."""
        # Check based on policy level
        policy_level = prompt.get("evaluation_requirements", {}).get("policy_check", "basic")
        
        if policy_level in ["sensitive", "strict"]:
            return True
        
        # Check for sensitive paths
        for target_path in target_paths:
            target_str = str(target_path)
            
            # Check against sensitive path patterns
            for sensitive_pattern in self.sensitive_actions:
                if sensitive_pattern in target_str:
                    return True
            
            # Check for production paths
            if any(prod in target_str.lower() for prod in ["production", "prod/", "/prod/"]):
                return True
        
        return False
    
    def _execute_promotion(
        self, promotion_id: str, target_paths: Dict[str, str], prompt: Dict[str, Any]
    ) -> Tuple[List[str], Optional[RollbackPlan]]:
        """Execute promotion of artifacts."""
        promoted_artifacts = []
        backup_paths = {}
        
        # Create rollback plan if enabled
        rollback_plan = None
        if self.generate_rollback_plan:
            rollback_plan = RollbackPlan(
                rollback_id=str(uuid.uuid4()),
                promotion_id=promotion_id,
                backup_paths={},
                timestamp=datetime.utcnow().isoformat() + "Z",
                metadata={"prompt": prompt.get("prompt_id", "unknown")}
            )
        
        for artifact_path, target_path in target_paths.items():
            artifact = Path(artifact_path)
            target = Path(target_path)
            
            if not artifact.exists():
                logger.warning(f"Artifact not found: {artifact_path}")
                continue
            
            try:
                # Ensure target directory exists
                target.parent.mkdir(parents=True, exist_ok=True)
                
                # Create backup if target exists and backups enabled
                if target.exists() and self.create_backups:
                    backup_path = self._create_backup(target, promotion_id)
                    backup_paths[str(target)] = str(backup_path)
                    
                    if rollback_plan:
                        rollback_plan.backup_paths[str(target)] = str(backup_path)
                
                # Copy artifact to target
                shutil.copy2(artifact, target)
                promoted_artifacts.append(artifact_path)
                
                logger.info(f"Promoted {artifact_path} -> {target_path}")
                
            except Exception as e:
                logger.error(f"Failed to promote {artifact_path}: {e}")
                # If backup exists, restore it
                if str(target) in backup_paths:
                    self._restore_backup(target, Path(backup_paths[str(target)]))
        
        # Save rollback plan
        if rollback_plan and rollback_plan.backup_paths:
            rollback_path = self.backup_root / f"rollback_{promotion_id}.json"
            rollback_plan.save(rollback_path)
        
        return promoted_artifacts, rollback_plan
    
    def _create_backup(self, target: Path, promotion_id: str) -> Path:
        """Create backup of target file."""
        backup_dir = self.backup_root / promotion_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backup_path = backup_dir / target.name
        
        # Add timestamp to avoid collisions
        if backup_path.exists():
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{target.stem}_{timestamp}{target.suffix}"
        
        shutil.copy2(target, backup_path)
        logger.info(f"Created backup: {target} -> {backup_path}")
        
        return backup_path
    
    def _restore_backup(self, target: Path, backup: Path) -> bool:
        """Restore target from backup."""
        try:
            if backup.exists():
                shutil.copy2(backup, target)
                logger.info(f"Restored from backup: {backup} -> {target}")
                return True
            else:
                logger.warning(f"Backup not found: {backup}")
                return False
        except Exception as e:
            logger.error(f"Failed to restore backup {backup}: {e}")
            return False
    
    def execute_rollback(self, rollback_plan_path: Path) -> bool:
        """
        Execute rollback using a rollback plan.
        
        Args:
            rollback_plan_path: Path to rollback plan JSON file
            
        Returns:
            True if rollback successful, False otherwise
        """
        try:
            with open(rollback_plan_path, 'r') as f:
                plan_data = json.load(f)
            
            rollback_plan = RollbackPlan(**plan_data)
            
            logger.info(f"Executing rollback {rollback_plan.rollback_id} "
                       f"for promotion {rollback_plan.promotion_id}")
            
            success_count = 0
            total_count = len(rollback_plan.backup_paths)
            
            for target_path, backup_path in rollback_plan.backup_paths.items():
                target = Path(target_path)
                backup = Path(backup_path)
                
                if self._restore_backup(target, backup):
                    success_count += 1
            
            success_rate = success_count / total_count if total_count > 0 else 1.0
            
            if success_rate >= 0.8:
                logger.info(f"Rollback completed: {success_count}/{total_count} files restored")
                return True
            else:
                logger.warning(f"Rollback partial: {success_count}/{total_count} files restored")
                return False
                
        except Exception as e:
            logger.error(f"Rollback execution failed: {e}")
            return False
    
    def cleanup_backups(self, older_than_days: int = 7) -> int:
        """
        Clean up old backup directories.
        
        Args:
            older_than_days: Remove backups older than this many days
            
        Returns:
            Number of backup directories removed
        """
        import time
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        removed_count = 0
        
        for item in self.backup_root.iterdir():
            if item.is_dir():
                # Parse promotion ID timestamp if possible
                try:
                    # Check modification time as fallback
                    stat = item.stat()
                    mod_time = datetime.fromtimestamp(stat.st_mtime)
                    
                    if mod_time < cutoff_date:
                        shutil.rmtree(item)
                        removed_count += 1
                        logger.info(f"Removed old backup directory: {item}")
                except Exception as e:
                    logger.error(f"Failed to remove {item}: {e}")
        
        return removed_count


# Example usage
if __name__ == "__main__":
    import time
    
    # Load configuration
    config_path = Path(__file__).parent.parent / "config" / "self_compiler_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    # Create directories
    staging_root = Path(__file__).parent.parent / "staging"
    promotion_root = Path(__file__).parent.parent / "promoted"
    staging_root.mkdir(parents=True, exist_ok=True)
    promotion_root.mkdir(parents=True, exist_ok=True)
    
    # Create promoter
    promoter = Promoter(config["promotion"], staging_root, promotion_root)
    
    # Create test artifact
    test_artifact = staging_root / "test_module.py"
    test_artifact.write_text("print('Hello from promoted module!')\n")
    
    # Example evaluation result
    example_evaluation = {
        "evaluation_id": "eval_123",
        "execution_id": "exec_456",
        "prompt_id": "prompt_789",
        "promotion_recommendation": "PROMOTE",
        "overall_score": 0.95,
        "gate_results": [],
        "feedback_summary": "All tests passed"
    }
    
    # Example execution result
    example_execution = {
        "execution_id": "exec_456",
        "artifacts_created": [str(test_artifact)]
    }
    
    # Example prompt
    example_prompt = {
        "prompt_id": "prompt_789",
        "expected_artifacts": ["test_module.py"],
        "evaluation_requirements": {
            "policy_check": "basic"
        }
    }
    
    # Make promotion decision
    result = promoter.make_promotion_decision(
        example_evaluation,
        example_execution,
        example_prompt,
        operator_approved=True  # Simulate operator approval
    )
    
    print(f"Promotion decision: {result.outcome}")
    print(f"Artifacts promoted: {len(result.artifacts_promoted)}")
    print(f"Artifacts rejected: {len(result.artifacts_rejected)}")
    
    if result.rollback_plan:
        print(f"Rollback plan created: {result.rollback_plan.rollback_id}")
    
    # Clean up
    test_promoted = promotion_root / "test_module.py"
    if test_promoted.exists():
        test_promoted.unlink()
    
    # Clean up backups
    promoter.cleanup_backups(older_than_days=0)  # Clean up test backups