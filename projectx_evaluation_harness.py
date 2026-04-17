#!/usr/bin/env python3
"""
ProjectX Safety Evaluation Harness

Offline harness for evaluating ProjectX safety judgments on proposed actions,
intents, and changes in the SIMP ecosystem.
"""

import json
import sys
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
import hashlib

class Judgment(Enum):
    """Safety judgment categories."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"

class ActionType(Enum):
    """Types of actions that can be evaluated."""
    TRADING_INTENT = "trading_intent"
    CODE_CHANGE = "code_change"
    CONFIG_CHANGE = "config_change"
    NEW_AGENT = "new_agent"
    NEW_DATASET = "new_dataset"
    QUANTUM_TASK = "quantum_task"
    EXTERNAL_INTEGRATION = "external_integration"

class BlockCause(Enum):
    """Causes for blocking an action."""
    MISSING_RISK_LIMITS = "missing_risk_limits"
    UNKNOWN_EXCHANGE = "unknown_exchange"
    UNVERIFIED_CODE = "unverified_code"
    OUT_OF_SCOPE = "out_of_scope"
    QUANTUM_UNSUPPORTED = "quantum_unsupported"
    CONFLICTS_WITH_BRP = "conflicts_with_brp"
    EXCESSIVE_RESOURCES = "excessive_resources"
    SECURITY_CONCERN = "security_concern"
    POLICY_VIOLATION = "policy_violation"

@dataclass
class SafetyJudgment:
    """ProjectX safety judgment."""
    judgment_id: str
    timestamp: str
    system_component: str
    action_type: str
    proposed_action: Dict[str, Any]
    context_summary: str
    recommendation: str  # ALLOW, BLOCK, ESCALATE
    confidence: float  # 0.0 to 1.0
    reasons: List[str]
    referenced_rules: List[str]
    block_cause: Optional[str] = None
    escalation_reason: Optional[str] = None
    assumptions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

@dataclass
class EvaluationBundle:
    """Bundle of information for ProjectX evaluation."""
    intent: Dict[str, Any]
    context: Dict[str, Any]
    brp_state: Dict[str, Any]
    recent_logs: List[Dict[str, Any]]
    system_state: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

class ProjectXEvaluator:
    """
    ProjectX safety evaluator for SIMP ecosystem.
    
    This is an offline harness that simulates ProjectX's safety judgment
    capabilities without actually modifying the live system.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.base_dir = Path(__file__).parent
        self.config = self.load_config(config_path)
        
        # Setup paths
        self.judgments_dir = self.base_dir / "data" / "projectx_judgments"
        self.judgments_dir.mkdir(parents=True, exist_ok=True)
        
        self.training_data_dir = self.base_dir / "data" / "projectx_training"
        self.training_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load safety rules
        self.safety_rules = self.load_safety_rules()
        
        # Load system knowledge
        self.system_knowledge = self.load_system_knowledge()
        
        # Statistics
        self.stats = {
            'total_judgments': 0,
            'by_recommendation': {j.value: 0 for j in Judgment},
            'by_action_type': {a.value: 0 for a in ActionType},
            'by_block_cause': {c.value: 0 for c in BlockCause}
        }
        
        print("ProjectX Safety Evaluator initialized")
        print(f"  Safety rules: {len(self.safety_rules)}")
        print(f"  System knowledge: {len(self.system_knowledge)} categories")
    
    def load_config(self, config_path: Optional[Path]) -> Dict:
        """Load configuration."""
        default_config = {
            'default_confidence_threshold': 0.7,
            'escalate_on_uncertainty': True,
            'assume_safe_by_default': False,
            'log_all_judgments': True,
            'training_mode': False
        }
        
        if config_path and config_path.exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def load_safety_rules(self) -> Dict:
        """Load safety rules from knowledge."""
        # These would normally come from system documentation
        # For now, define core safety rules
        return {
            'sandbox-first-live-run': {
                'description': 'All live trading must start in sandbox/microscopic mode',
                'conditions': ['phase == 1', 'risk_level == microscopic'],
                'enforcement': 'hard'
            },
            'max-risk-per-trade': {
                'description': 'Maximum risk per trade must be explicitly set',
                'conditions': ['risk_params.max_loss_pct exists', 'risk_params.max_loss_pct <= 2.0'],
                'enforcement': 'hard'
            },
            'brp-enforced-required': {
                'description': 'BRP must be in ENFORCED mode for live trading',
                'conditions': ['brp_mode == ENFORCED'],
                'enforcement': 'hard'
            },
            'quantum-in-scope': {
                'description': 'Quantum tasks must be within Quantum Goose scope',
                'conditions': [
                    'algorithm in supported_algorithms',
                    'framework in [qiskit, pennylane]',
                    'qubits <= 10',
                    'verification_expected == true'
                ],
                'enforcement': 'soft'
            },
            'verified-code-only': {
                'description': 'Code changes require verification before deployment',
                'conditions': ['has_tests == true', 'verification_passed == true'],
                'enforcement': 'hard'
            },
            'known-exchanges-only': {
                'description': 'Trading only on known, configured exchanges',
                'conditions': ['exchange in configured_exchanges'],
                'enforcement': 'hard'
            }
        }
    
    def load_system_knowledge(self) -> Dict:
        """Load system knowledge about SIMP ecosystem."""
        # This would normally come from system documentation
        # For now, define basic knowledge
        return {
            'simp_architecture': {
                'components': ['broker', 'agents', 'dashboard', 'ledgers', 'BRP'],
                'trust_boundaries': ['sandbox <-> live', 'internal <-> external'],
                'data_flows': ['intents -> broker -> agents -> execution']
            },
            'brp_goals': {
                'primary': 'protect capital and prevent catastrophic losses',
                'mechanisms': ['position limits', 'risk checks', 'emergency stop'],
                'philosophy': 'conservative, prefer false positives over false negatives'
            },
            'quantum_goose_scope': {
                'in_scope': [
                    'quantum algorithm explanations',
                    'quantum code generation (Qiskit, PennyLane)',
                    'quantum circuit verification',
                    'educational quantum examples'
                ],
                'out_of_scope': [
                    'real quantum hardware execution',
                    'proprietary quantum algorithms',
                    'quantum cryptography beyond basics',
                    'unsupported frameworks (Cirq, PyQuil without setup)'
                ],
                'limits': ['max_qubits: 10', 'max_circuit_depth: 100', 'verification_required: true']
            },
            'trading_agents': {
                'quantumarb': {
                    'role': 'arbitrage detection and execution',
                    'limits': ['microscopic risk in phase 1', 'sandbox-first'],
                    'exchanges': ['testnet only initially']
                },
                'kashclaw': {
                    'role': 'multi-venue execution',
                    'limits': ['configurable risk limits', 'BRP oversight required']
                }
            }
        }
    
    def generate_judgment_id(self) -> str:
        """Generate unique judgment ID."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        random_hash = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        return f"px-{timestamp}-{random_hash}"
    
    def evaluate_trading_intent(self, bundle: EvaluationBundle) -> SafetyJudgment:
        """Evaluate a trading intent."""
        intent = bundle.intent
        context = bundle.context
        
        # Extract intent details
        market = intent.get('market', '')
        side = intent.get('side', '')
        size = intent.get('size_notional', 0.0)
        risk_params = intent.get('risk_params', {})
        
        # Initialize judgment
        judgment_id = self.generate_judgment_id()
        reasons = []
        block_cause = None
        escalation_reason = None
        assumptions = []
        
        # Check safety rules
        violations = []
        
        # Rule: Known exchanges only
        configured_exchanges = self.system_knowledge['trading_agents']['quantumarb']['exchanges']
        if market and not any(exchange in market.lower() for exchange in configured_exchanges):
            violations.append(('known-exchanges-only', f"Unknown exchange in market: {market}"))
        
        # Rule: Risk limits
        max_loss = risk_params.get('max_loss_pct', 0.0)
        if max_loss <= 0 or max_loss > 2.0:
            violations.append(('max-risk-per-trade', f"Invalid max loss percentage: {max_loss}%"))
        
        # Rule: BRP enforcement
        brp_mode = bundle.brp_state.get('mode', 'UNKNOWN')
        if brp_mode != 'ENFORCED':
            violations.append(('brp-enforced-required', f"BRP not in ENFORCED mode: {brp_mode}"))
        
        # Context checks
        phase = context.get('phase', 0)
        if phase == 1 and size > 100.0:  # Microscopic phase
            violations.append(('sandbox-first-live-run', f"Size {size} too large for phase 1"))
        
        # Make judgment
        if violations:
            recommendation = Judgment.BLOCK.value
            confidence = 0.9
            block_cause = BlockCause.POLICY_VIOLATION.value
            reasons = [f"{rule}: {reason}" for rule, reason in violations]
        else:
            # Check for uncertainty
            uncertain = False
            if not market:
                uncertain = True
                escalation_reason = "Missing market specification"
            elif size <= 0:
                uncertain = True
                escalation_reason = "Invalid size specification"
            
            if uncertain and self.config['escalate_on_uncertainty']:
                recommendation = Judgment.ESCALATE.value
                confidence = 0.6
                reasons = [escalation_reason]
            else:
                recommendation = Judgment.ALLOW.value
                confidence = 0.8
                reasons = [
                    "All safety rules satisfied",
                    f"Market: {market}, Size: {size}",
                    f"BRP mode: {brp_mode}",
                    f"Phase: {phase}"
                ]
        
        # Create judgment
        judgment = SafetyJudgment(
            judgment_id=judgment_id,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            system_component="SIMP.Trading",
            action_type=ActionType.TRADING_INTENT.value,
            proposed_action=intent,
            context_summary=f"Trading intent for {market} {side} size {size}",
            recommendation=recommendation,
            confidence=confidence,
            reasons=reasons,
            referenced_rules=[rule for rule, _ in violations] if violations else [],
            block_cause=block_cause,
            escalation_reason=escalation_reason,
            assumptions=assumptions,
            metadata={
                'phase': phase,
                'brp_mode': brp_mode,
                'risk_params': risk_params
            }
        )
        
        return judgment
    
    def evaluate_quantum_task(self, bundle: EvaluationBundle) -> SafetyJudgment:
        """Evaluate a quantum task for Quantum Goose."""
        intent = bundle.intent
        context = bundle.context
        
        # Extract task details
        algorithm = intent.get('algorithm', '')
        framework = intent.get('framework', '')
        qubits = intent.get('qubits', 0)
        require_verification = intent.get('require_verification', True)
        
        # Initialize judgment
        judgment_id = self.generate_judgment_id()
        reasons = []
        block_cause = None
        escalation_reason = None
        assumptions = []
        
        # Get Quantum Goose scope
        quantum_scope = self.system_knowledge['quantum_goose_scope']
        in_scope_algorithms = quantum_scope['in_scope']
        out_of_scope = quantum_scope['out_of_scope']
        limits = quantum_scope['limits']
        
        # Check if in scope - Bell state is definitely in scope
        in_scope = False
        algorithm_lower = algorithm.lower()
        
        # Known in-scope algorithms
        known_in_scope = ['bell', 'bell state', 'bell_state', 'deutsch', 'grover', 'qft', 
                         'quantum fourier', 'bernstein', 'vazirani', 'teleportation',
                         'superposition', 'entanglement', 'ghz', 'swap', 'vqe', 'bb84']
        
        for known_algo in known_in_scope:
            if known_algo in algorithm_lower:
                in_scope = True
                break
        
        # Also check scope items
        if not in_scope:
            for scope_item in in_scope_algorithms:
                if algorithm_lower in scope_item.lower():
                    in_scope = True
                    break
        
        # Check for out-of-scope
        out_of_scope_detected = False
        known_out_of_scope = ['cryptography breaking', 'proprietary', 'hardware execution',
                             'unsupported framework', 'real quantum hardware']
        
        for known_out in known_out_of_scope:
            if known_out in algorithm_lower:
                out_of_scope_detected = True
                break
        
        if not out_of_scope_detected:
            for scope_item in out_of_scope:
                if algorithm_lower in scope_item.lower():
                    out_of_scope_detected = True
                    break
        
        # Check limits
        max_qubits = 10  # Default from limits
        for limit in limits:
            if 'max_qubits' in limit:
                try:
                    max_qubits = int(limit.split(':')[1].strip())
                except (ValueError, IndexError):
                    pass
        
        # Make judgment
        if out_of_scope_detected:
            recommendation = Judgment.BLOCK.value
            confidence = 0.95
            block_cause = BlockCause.OUT_OF_SCOPE.value
            reasons = [f"Algorithm '{algorithm}' is out of scope for Quantum Goose"]
        elif not in_scope:
            recommendation = Judgment.ESCALATE.value
            confidence = 0.7
            escalation_reason = f"Algorithm '{algorithm}' not explicitly in scope"
            reasons = [escalation_reason, "Requires manual review"]
        elif framework not in ['qiskit', 'pennylane']:
            recommendation = Judgment.BLOCK.value
            confidence = 0.9
            block_cause = BlockCause.QUANTUM_UNSUPPORTED.value
            reasons = [f"Unsupported framework: {framework}"]
        elif qubits > max_qubits:
            recommendation = Judgment.BLOCK.value
            confidence = 0.85
            block_cause = BlockCause.EXCESSIVE_RESOURCES.value
            reasons = [f"Qubits ({qubits}) exceed limit ({max_qubits})"]
        elif not require_verification:
            recommendation = Judgment.ESCALATE.value
            confidence = 0.75
            escalation_reason = "Verification not required"
            reasons = ["Quantum tasks should require verification", escalation_reason]
        else:
            recommendation = Judgment.ALLOW.value
            confidence = 0.85
            reasons = [
                f"Algorithm '{algorithm}' is in scope",
                f"Framework '{framework}' is supported",
                f"Qubits: {qubits} (within limit)",
                "Verification required"
            ]
        
        # Create judgment
        judgment = SafetyJudgment(
            judgment_id=judgment_id,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            system_component="SIMP.QuantumGoose",
            action_type=ActionType.QUANTUM_TASK.value,
            proposed_action=intent,
            context_summary=f"Quantum task: {algorithm} in {framework} ({qubits} qubits)",
            recommendation=recommendation,
            confidence=confidence,
            reasons=reasons,
            referenced_rules=['quantum-in-scope'],
            block_cause=block_cause,
            escalation_reason=escalation_reason,
            assumptions=assumptions,
            metadata={
                'algorithm': algorithm,
                'framework': framework,
                'qubits': qubits,
                'require_verification': require_verification
            }
        )
        
        return judgment
    
    def evaluate_config_change(self, bundle: EvaluationBundle) -> SafetyJudgment:
        """Evaluate a configuration change."""
        intent = bundle.intent
        context = bundle.context
        
        # Extract change details
        change_type = intent.get('change_type', '')
        new_value = intent.get('new_value', {})
        current_value = intent.get('current_value', {})
        
        # Initialize judgment
        judgment_id = self.generate_judgment_id()
        reasons = []
        block_cause = None
        escalation_reason = None
        assumptions = []
        
        # Check change type
        if change_type == 'risk_limits':
            # Risk limit changes
            new_max_loss = new_value.get('max_loss_pct', 0.0)
            current_max_loss = current_value.get('max_loss_pct', 0.0)
            
            if new_max_loss > 5.0:  # Arbitrary safety limit
                recommendation = Judgment.BLOCK.value
                confidence = 0.9
                block_cause = BlockCause.POLICY_VIOLATION.value
                reasons = [f"Proposed max loss {new_max_loss}% exceeds safety limit of 5%"]
            elif new_max_loss > current_max_loss * 2:
                recommendation = Judgment.ESCALATE.value
                confidence = 0.8
                escalation_reason = "Large increase in risk limits"
                reasons = [f"Increase from {current_max_loss}% to {new_max_loss}% requires review"]
            else:
                recommendation = Judgment.ALLOW.value
                confidence = 0.85
                reasons = [
                    f"Risk limit change from {current_max_loss}% to {new_max_loss}%",
                    "Within acceptable bounds"
                ]
        
        elif change_type == 'brp_mode':
            # BRP mode changes
            new_mode = new_value.get('mode', '')
            if new_mode == 'DISABLED':
                recommendation = Judgment.BLOCK.value
                confidence = 1.0
                block_cause = BlockCause.POLICY_VIOLATION.value
                reasons = ["BRP cannot be disabled for safety reasons"]
            elif new_mode not in ['MONITOR', 'ENFORCED']:
                recommendation = Judgment.ESCALATE.value
                confidence = 0.7
                escalation_reason = f"Unknown BRP mode: {new_mode}"
                reasons = [escalation_reason]
            else:
                recommendation = Judgment.ALLOW.value
                confidence = 0.9
                reasons = [f"BRP mode change to {new_mode} is acceptable"]
        
        else:
            # Unknown change type
            recommendation = Judgment.ESCALATE.value
            confidence = 0.6
            escalation_reason = f"Unknown configuration change type: {change_type}"
            reasons = [escalation_reason, "Requires manual review"]
        
        # Create judgment
        judgment = SafetyJudgment(
            judgment_id=judgment_id,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            system_component="SIMP.Configuration",
            action_type=ActionType.CONFIG_CHANGE.value,
            proposed_action=intent,
            context_summary=f"Config change: {change_type}",
            recommendation=recommendation,
            confidence=confidence,
            reasons=reasons,
            referenced_rules=[],
            block_cause=block_cause,
            escalation_reason=escalation_reason,
            assumptions=assumptions,
            metadata={
                'change_type': change_type,
                'new_value': new_value,
                'current_value': current_value
            }
        )
        
        return judgment
    
    def evaluate_bundle(self, bundle: EvaluationBundle) -> SafetyJudgment:
        """Evaluate a bundle and return safety judgment."""
        intent = bundle.intent
        action_type = intent.get('action_type', '')
        
        # Route to appropriate evaluator
        if action_type == ActionType.TRADING_INTENT.value:
            judgment = self.evaluate_trading_intent(bundle)
        elif action_type == ActionType.QUANTUM_TASK.value:
            judgment = self.evaluate_quantum_task(bundle)
        elif action_type == ActionType.CONFIG_CHANGE.value:
            judgment = self.evaluate_config_change(bundle)
        else:
            # Generic evaluation for unknown action types
            judgment_id = self.generate_judgment_id()
            judgment = SafetyJudgment(
                judgment_id=judgment_id,
                timestamp=datetime.utcnow().isoformat() + 'Z',
                system_component="SIMP.Generic",
                action_type=action_type,
                proposed_action=intent,
                context_summary=f"Generic action: {action_type}",
                recommendation=Judgment.ESCALATE.value,
                confidence=0.5,
                reasons=[f"Unknown action type: {action_type}", "Requires manual review"],
                referenced_rules=[],
                escalation_reason="Unknown action type",
                assumptions=["Action type not recognized"]
            )
        
        # Update statistics
        self.stats['total_judgments'] += 1
        self.stats['by_recommendation'][judgment.recommendation] = \
            self.stats['by_recommendation'].get(judgment.recommendation, 0) + 1
        self.stats['by_action_type'][judgment.action_type] = \
            self.stats['by_action_type'].get(judgment.action_type, 0) + 1
        
        if judgment.block_cause:
            self.stats['by_block_cause'][judgment.block_cause] = \
                self.stats['by_block_cause'].get(judgment.block_cause, 0) + 1
        
        # Save judgment
        if self.config['log_all_judgments']:
            self.save_judgment(judgment)
        
        # Save to training data if in training mode
        if self.config['training_mode']:
            self.save_training_example(bundle, judgment)
        
        return judgment
    
    def save_judgment(self, judgment: SafetyJudgment):
        """Save judgment to file."""
        judgment_file = self.judgments_dir / f"{judgment.judgment_id}.json"
        with open(judgment_file, 'w') as f:
            f.write(judgment.to_json())
        
        # Also append to log file
        log_file = self.judgments_dir / "judgments_log.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(judgment.to_dict()) + '\n')
    
    def save_training_example(self, bundle: EvaluationBundle, judgment: SafetyJudgment):
        """Save as training example for ProjectX."""
        training_example = {
            'input': bundle.to_dict(),
            'output': judgment.to_dict(),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'source': 'projectx_evaluation_harness'
        }
        
        training_file = self.training_data_dir / f"training_{judgment.judgment_id}.json"
        with open(training_file, 'w') as f:
            json.dump(training_example, f, indent=2)
        
        # Also append to training log
        training_log = self.training_data_dir / "training_log.jsonl"
        with open(training_log, 'a') as f:
            f.write(json.dumps(training_example) + '\n')
    
    def get_stats(self) -> Dict:
        """Get evaluation statistics."""
        return self.stats
    
    def run_test_suite(self):
        """Run test suite with synthetic examples."""
        print("\n" + "="*60)
        print("ProjectX Evaluation Harness - Test Suite")
        print("="*60)
        
        test_cases = self._create_test_cases()
        
        for i, (bundle, description) in enumerate(test_cases, 1):
            print(f"\nTest {i}: {description}")
            print("-"*40)
            
            judgment = self.evaluate_bundle(bundle)
            
            print(f"Recommendation: {judgment.recommendation}")
            print(f"Confidence: {judgment.confidence:.2f}")
            print(f"Reasons: {', '.join(judgment.reasons[:2])}")
            if judgment.block_cause:
                print(f"Block cause: {judgment.block_cause}")
            if judgment.escalation_reason:
                print(f"Escalation: {judgment.escalation_reason}")
        
        print("\n" + "="*60)
        print("Test Suite Complete")
        print("="*60)
        print(f"\nStatistics:")
        print(f"  Total judgments: {self.stats['total_judgments']}")
        for rec, count in self.stats['by_recommendation'].items():
            if count > 0:
                print(f"  {rec}: {count}")
    
    def _create_test_cases(self) -> List[Tuple[EvaluationBundle, str]]:
        """Create test cases for evaluation."""
        test_cases = []
        
        # Test 1: Valid trading intent
        bundle1 = EvaluationBundle(
            intent={
                'action_type': 'trading_intent',
                'market': 'BTC-USDT-PERP',
                'side': 'long',
                'size_notional': 50.0,
                'risk_params': {'max_loss_pct': 1.0}
            },
            context={'phase': 1, 'risk_level': 'microscopic'},
            brp_state={'mode': 'ENFORCED', 'version': '1.0'},
            recent_logs=[]
        )
        test_cases.append((bundle1, "Valid trading intent (phase 1, microscopic)"))
        
        # Test 2: Trading intent with unknown exchange
        bundle2 = EvaluationBundle(
            intent={
                'action_type': 'trading_intent',
                'market': 'UNKNOWN-EXCHANGE',
                'side': 'short',
                'size_notional': 100.0,
                'risk_params': {'max_loss_pct': 0.5}
            },
            context={'phase': 1, 'risk_level': 'microscopic'},
            brp_state={'mode': 'ENFORCED', 'version': '1.0'},
            recent_logs=[]
        )
        test_cases.append((bundle2, "Trading intent with unknown exchange"))
        
        # Test 3: Quantum task in scope
        bundle3 = EvaluationBundle(
            intent={
                'action_type': 'quantum_task',
                'algorithm': 'bell state',
                'framework': 'qiskit',
                'qubits': 2,
                'require_verification': True
            },
            context={},
            brp_state={'mode': 'MONITOR'},
            recent_logs=[]
        )
        test_cases.append((bundle3, "Quantum task in scope (Bell state)"))
        
        # Test 4: Quantum task out of scope
        bundle4 = EvaluationBundle(
            intent={
                'action_type': 'quantum_task',
                'algorithm': 'quantum cryptography breaking',
                'framework': 'qiskit',
                'qubits': 100,
                'require_verification': False
            },
            context={},
            brp_state={'mode': 'MONITOR'},
            recent_logs=[]
        )
        test_cases.append((bundle4, "Quantum task out of scope (cryptography)"))
        
        # Test 5: Config change - risk limits
        bundle5 = EvaluationBundle(
            intent={
                'action_type': 'config_change',
                'change_type': 'risk_limits',
                'new_value': {'max_loss_pct': 3.0},
                'current_value': {'max_loss_pct': 1.0}
            },
            context={},
            brp_state={'mode': 'ENFORCED'},
            recent_logs=[]
        )
        test_cases.append((bundle5, "Config change - increase risk limits"))
        
        # Test 6: Config change - disable BRP (should block)
        bundle6 = EvaluationBundle(
            intent={
                'action_type': 'config_change',
                'change_type': 'brp_mode',
                'new_value': {'mode': 'DISABLED'},
                'current_value': {'mode': 'ENFORCED'}
            },
            context={},
            brp_state={'mode': 'ENFORCED'},
            recent_logs=[]
        )
        test_cases.append((bundle6, "Config change - disable BRP (should block)"))
        
        return test_cases

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='ProjectX Safety Evaluation Harness')
    parser.add_argument('--test', action='store_true', help='Run test suite')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--config', type=Path, help='Path to configuration file')
    parser.add_argument('--bundle', type=Path, help='Path to evaluation bundle JSON file')
    
    args = parser.parse_args()
    
    # Create evaluator
    evaluator = ProjectXEvaluator(args.config)
    
    if args.test:
        # Run test suite
        evaluator.run_test_suite()
    
    elif args.bundle:
        # Evaluate specific bundle
        if args.bundle.exists():
            with open(args.bundle, 'r') as f:
                bundle_data = json.load(f)
            
            bundle = EvaluationBundle(**bundle_data)
            judgment = evaluator.evaluate_bundle(bundle)
            
            print("\n" + "="*60)
            print("ProjectX Safety Judgment")
            print("="*60)
            print(judgment.to_json())
            print("="*60)
        else:
            print(f"Error: Bundle file not found: {args.bundle}")
    
    elif args.stats:
        # Show statistics
        stats = evaluator.get_stats()
        print("ProjectX Evaluation Statistics:")
        print(json.dumps(stats, indent=2))
    
    else:
        # Interactive mode
        print("ProjectX Safety Evaluation Harness")
        print("\nUsage:")
        print("  --test      Run test suite with synthetic examples")
        print("  --stats     Show evaluation statistics")
        print("  --bundle    Evaluate specific bundle from JSON file")
        print("\nExample test cases demonstrate ALLOW/BLOCK/ESCALATE decisions.")

if __name__ == '__main__':
    main()