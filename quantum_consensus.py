#!/usr/bin/env python3
"""
L5 Quantum Consensus — File-based multi-agent voting with quantum majority.

Agents submit votes on trade decisions via file inboxes.
QIP computes quantum majority using amplitude estimation.
Returns consensus decisions with quantum confidence scores.

Usage:
    python3.10 quantum_consensus.py --collect-votes
    python3.10 quantum_consensus.py --compute-consensus --proposal-id trade_001
    python3.10 quantum_consensus.py --run-daemon
"""

import sys
import os
import json
import time
import logging
import argparse
import threading
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

# Allow running from simp root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s %(message)s'
)
logger = logging.getLogger("quantum_consensus")

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INBOX_DIR = DATA_DIR / "inboxes"
CONSENSUS_VOTES_DIR = INBOX_DIR / "consensus_votes"
CONSENSUS_PROPOSALS_DIR = INBOX_DIR / "consensus_proposals"
CONSENSUS_RESULTS_DIR = INBOX_DIR / "consensus_results"
QIP_INBOX_DIR = INBOX_DIR / "quantum_intelligence_prime"

# Create directories
for dir_path in [CONSENSUS_VOTES_DIR, CONSENSUS_PROPOSALS_DIR, 
                 CONSENSUS_RESULTS_DIR, QIP_INBOX_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ── Data Models ──────────────────────────────────────────────────────────────

class VoteChoice(Enum):
    """Vote choices for consensus proposals."""
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


@dataclass
class ConsensusProposal:
    """A proposal for agents to vote on."""
    proposal_id: str
    intent_type: str  # e.g., "execute_trade", "allocate_capital", "adjust_risk"
    payload: Dict[str, Any]  # Proposal details
    proposer_agent: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl_seconds: float = 300.0  # Time to live
    required_quorum: float = 0.67  # 2/3 weighted approval
    min_participation_weight: float = 5.0  # Minimum total trust weight
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "intent_type": self.intent_type,
            "payload": self.payload,
            "proposer_agent": self.proposer_agent,
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
            "required_quorum": self.required_quorum,
            "min_participation_weight": self.min_participation_weight,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsensusProposal":
        return cls(
            proposal_id=data["proposal_id"],
            intent_type=data["intent_type"],
            payload=data["payload"],
            proposer_agent=data["proposer_agent"],
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            ttl_seconds=data.get("ttl_seconds", 300.0),
            required_quorum=data.get("required_quorum", 0.67),
            min_participation_weight=data.get("min_participation_weight", 5.0),
        )


@dataclass
class ConsensusVote:
    """A vote from an agent on a proposal."""
    proposal_id: str
    agent_id: str
    vote: VoteChoice
    trust_score: float  # L4 trust score (0.0-5.0)
    confidence: float  # Agent's confidence in vote (0.0-1.0)
    reasoning: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "agent_id": self.agent_id,
            "vote": self.vote.value,
            "trust_score": self.trust_score,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsensusVote":
        return cls(
            proposal_id=data["proposal_id"],
            agent_id=data["agent_id"],
            vote=VoteChoice(data["vote"]),
            trust_score=data["trust_score"],
            confidence=data["confidence"],
            reasoning=data.get("reasoning"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class ConsensusResult:
    """Final consensus result for a proposal."""
    proposal_id: str
    outcome: VoteChoice  # Final decision
    quantum_confidence: float  # QIP's confidence in the outcome (0.0-1.0)
    weighted_approve: float  # Total trust weight of approve votes
    weighted_total: float  # Total trust weight of all non-abstain votes
    participation_rate: float  # weighted_total / total_possible_weight
    votes: List[ConsensusVote]  # All votes cast
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "outcome": self.outcome.value,
            "quantum_confidence": self.quantum_confidence,
            "weighted_approve": self.weighted_approve,
            "weighted_total": self.weighted_total,
            "participation_rate": self.participation_rate,
            "votes": [vote.to_dict() for vote in self.votes],
            "timestamp": self.timestamp,
        }


# ── Quantum Consensus Engine ─────────────────────────────────────────────────

class QuantumConsensusEngine:
    """Engine for quantum-enhanced consensus voting."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._active_proposals: Dict[str, ConsensusProposal] = {}
        self._pending_votes: Dict[str, List[ConsensusVote]] = {}
        
    def submit_proposal(self, proposal: ConsensusProposal) -> bool:
        """Submit a new proposal for voting."""
        with self._lock:
            # Write proposal to file
            proposal_path = CONSENSUS_PROPOSALS_DIR / f"{proposal.proposal_id}.json"
            with open(proposal_path, "w") as f:
                json.dump(proposal.to_dict(), f, indent=2)
            
            self._active_proposals[proposal.proposal_id] = proposal
            self._pending_votes[proposal.proposal_id] = []
            
            logger.info(f"Proposal submitted: {proposal.proposal_id} by {proposal.proposer_agent}")
            return True
    
    def submit_vote(self, vote: ConsensusVote) -> bool:
        """Submit a vote on a proposal."""
        with self._lock:
            # Check if proposal exists
            if vote.proposal_id not in self._active_proposals:
                logger.warning(f"Proposal not found: {vote.proposal_id}")
                return False
            
            # Write vote to file
            vote_id = f"{vote.proposal_id}_{vote.agent_id}_{int(time.time())}"
            vote_path = CONSENSUS_VOTES_DIR / f"{vote_id}.json"
            with open(vote_path, "w") as f:
                json.dump(vote.to_dict(), f, indent=2)
            
            # Add to pending votes
            self._pending_votes[vote.proposal_id].append(vote)
            
            logger.info(f"Vote submitted: {vote.agent_id} voted {vote.vote.value} on {vote.proposal_id}")
            return True
    
    def collect_votes(self, proposal_id: str) -> List[ConsensusVote]:
        """Collect all votes for a proposal from file system."""
        votes = []
        
        # Read from pending votes in memory
        if proposal_id in self._pending_votes:
            votes.extend(self._pending_votes[proposal_id])
        
        # Also scan files for any votes we might have missed
        for vote_file in CONSENSUS_VOTES_DIR.glob(f"{proposal_id}_*.json"):
            try:
                with open(vote_file, "r") as f:
                    vote_data = json.load(f)
                    vote = ConsensusVote.from_dict(vote_data)
                    votes.append(vote)
            except Exception as e:
                logger.error(f"Failed to read vote file {vote_file}: {e}")
        
        return votes
    
    def compute_classical_consensus(self, proposal_id: str, votes: List[ConsensusVote]) -> Tuple[VoteChoice, float, float, float]:
        """Compute classical consensus (weighted voting)."""
        if not votes:
            return VoteChoice.ABSTAIN, 0.0, 0.0, 0.0
        
        weighted_approve = 0.0
        weighted_reject = 0.0
        weighted_abstain = 0.0
        
        for vote in votes:
            weight = vote.trust_score * vote.confidence
            if vote.vote == VoteChoice.APPROVE:
                weighted_approve += weight
            elif vote.vote == VoteChoice.REJECT:
                weighted_reject += weight
            else:  # ABSTAIN
                weighted_abstain += weight
        
        weighted_total = weighted_approve + weighted_reject  # Exclude abstain
        
        if weighted_total == 0:
            return VoteChoice.ABSTAIN, 0.0, 0.0, 0.0
        
        approval_ratio = weighted_approve / weighted_total
        
        # Get proposal to check quorum requirements
        proposal = self._active_proposals.get(proposal_id)
        if proposal:
            if weighted_total < proposal.min_participation_weight:
                logger.warning(f"Insufficient participation: {weighted_total} < {proposal.min_participation_weight}")
                return VoteChoice.ABSTAIN, approval_ratio, weighted_approve, weighted_total
            
            if approval_ratio >= proposal.required_quorum:
                return VoteChoice.APPROVE, approval_ratio, weighted_approve, weighted_total
            else:
                return VoteChoice.REJECT, approval_ratio, weighted_approve, weighted_total
        else:
            # Default quorum: 2/3
            if approval_ratio >= 0.67:
                return VoteChoice.APPROVE, approval_ratio, weighted_approve, weighted_total
            else:
                return VoteChoice.REJECT, approval_ratio, weighted_approve, weighted_total
    
    def send_to_qip_for_quantum_enhancement(self, proposal_id: str, votes: List[ConsensusVote], 
                                          classical_outcome: VoteChoice, classical_confidence: float) -> float:
        """Send votes to QIP for quantum majority computation."""
        # Prepare quantum consensus request
        qip_request = {
            "intent": "quantum_consensus",
            "proposal_id": proposal_id,
            "votes": [vote.to_dict() for vote in votes],
            "classical_outcome": classical_outcome.value,
            "classical_confidence": classical_confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": f"consensus_{proposal_id}_{int(time.time())}"
        }
        
        # Write to QIP inbox
        qip_file = QIP_INBOX_DIR / f"consensus_{proposal_id}_{int(time.time())}.json"
        with open(qip_file, "w") as f:
            json.dump(qip_request, f, indent=2)
        
        logger.info(f"Sent consensus request to QIP: {proposal_id}")
        
        # In stub mode, return enhanced confidence (classical + quantum boost)
        # In real mode, QIP would process and write response to its outbox
        quantum_boost = 0.1  # Stub: 10% quantum enhancement
        return min(1.0, classical_confidence + quantum_boost)
    
    def compute_consensus(self, proposal_id: str) -> Optional[ConsensusResult]:
        """Compute final consensus for a proposal."""
        with self._lock:
            # Check if proposal exists
            if proposal_id not in self._active_proposals:
                logger.warning(f"Proposal not found: {proposal_id}")
                return None
            
            # Collect votes
            votes = self.collect_votes(proposal_id)
            if not votes:
                logger.info(f"No votes for proposal: {proposal_id}")
                return None
            
            # Compute classical consensus
            classical_outcome, approval_ratio, weighted_approve, weighted_total = \
                self.compute_classical_consensus(proposal_id, votes)
            
            # Get quantum-enhanced confidence
            quantum_confidence = self.send_to_qip_for_quantum_enhancement(
                proposal_id, votes, classical_outcome, approval_ratio
            )
            
            # Calculate participation rate
            proposal = self._active_proposals[proposal_id]
            total_possible_weight = len(votes) * 5.0  # Max trust score is 5.0
            participation_rate = weighted_total / total_possible_weight if total_possible_weight > 0 else 0.0
            
            # Create result
            result = ConsensusResult(
                proposal_id=proposal_id,
                outcome=classical_outcome,
                quantum_confidence=quantum_confidence,
                weighted_approve=weighted_approve,
                weighted_total=weighted_total,
                participation_rate=participation_rate,
                votes=votes,
            )
            
            # Write result to file
            result_path = CONSENSUS_RESULTS_DIR / f"{proposal_id}_result.json"
            with open(result_path, "w") as f:
                json.dump(result.to_dict(), f, indent=2)
            
            # Clean up
            del self._active_proposals[proposal_id]
            del self._pending_votes[proposal_id]
            
            logger.info(f"Consensus computed: {proposal_id} -> {classical_outcome.value} "
                       f"(quantum confidence: {quantum_confidence:.2f})")
            
            return result
    
    def run_daemon(self, interval_seconds: int = 30):
        """Run consensus daemon that periodically processes proposals."""
        logger.info(f"Starting Quantum Consensus Daemon (interval: {interval_seconds}s)")
        
        while True:
            try:
                # Process all active proposals
                proposal_ids = list(self._active_proposals.keys())
                for proposal_id in proposal_ids:
                    # Check if proposal has expired
                    proposal = self._active_proposals[proposal_id]
                    proposal_time = datetime.fromisoformat(proposal.timestamp.replace('Z', '+00:00'))
                    age_seconds = (datetime.now(timezone.utc) - proposal_time).total_seconds()
                    
                    if age_seconds > proposal.ttl_seconds:
                        logger.info(f"Proposal expired: {proposal_id}")
                        del self._active_proposals[proposal_id]
                        if proposal_id in self._pending_votes:
                            del self._pending_votes[proposal_id]
                        continue
                    
                    # Compute consensus if we have votes
                    if proposal_id in self._pending_votes and self._pending_votes[proposal_id]:
                        self.compute_consensus(proposal_id)
                
                # Scan for new proposal files
                for proposal_file in CONSENSUS_PROPOSALS_DIR.glob("*.json"):
                    proposal_id = proposal_file.stem
                    if proposal_id not in self._active_proposals:
                        try:
                            with open(proposal_file, "r") as f:
                                proposal_data = json.load(f)
                                proposal = ConsensusProposal.from_dict(proposal_data)
                                self._active_proposals[proposal_id] = proposal
                                self._pending_votes[proposal_id] = []
                                logger.info(f"Loaded proposal from file: {proposal_id}")
                        except Exception as e:
                            logger.error(f"Failed to load proposal {proposal_file}: {e}")
                
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Consensus daemon stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in consensus daemon: {e}")
                time.sleep(interval_seconds)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="L5 Quantum Consensus Engine")
    parser.add_argument("--collect-votes", action="store_true", 
                       help="Collect votes from file system")
    parser.add_argument("--compute-consensus", action="store_true",
                       help="Compute consensus for a proposal")
    parser.add_argument("--proposal-id", type=str,
                       help="Proposal ID to compute consensus for")
    parser.add_argument("--run-daemon", action="store_true",
                       help="Run consensus daemon")
    parser.add_argument("--interval", type=int, default=30,
                       help="Daemon interval in seconds (default: 30)")
    parser.add_argument("--submit-proposal", action="store_true",
                       help="Submit a test proposal")
    parser.add_argument("--submit-vote", action="store_true",
                       help="Submit a test vote")
    
    args = parser.parse_args()
    engine = QuantumConsensusEngine()
    
    if args.collect_votes:
        if not args.proposal_id:
            print("Error: --proposal-id required for --collect-votes")
            return
        
        votes = engine.collect_votes(args.proposal_id)
        print(f"Collected {len(votes)} votes for proposal {args.proposal_id}:")
        for vote in votes:
            print(f"  - {vote.agent_id}: {vote.vote.value} (trust: {vote.trust_score}, confidence: {vote.confidence})")
    
    elif args.compute_consensus:
        if not args.proposal_id:
            print("Error: --proposal-id required for --compute-consensus")
            return
        
        result = engine.compute_consensus(args.proposal_id)
        if result:
            print(f"Consensus result for {args.proposal_id}:")
            print(f"  Outcome: {result.outcome.value}")
            print(f"  Quantum Confidence: {result.quantum_confidence:.2f}")
            print(f"  Weighted Approve: {result.weighted_approve:.2f}")
            print(f"  Weighted Total: {result.weighted_total:.2f}")
            print(f"  Participation Rate: {result.participation_rate:.2f}")
            print(f"  Votes: {len(result.votes)}")
        else:
            print(f"No consensus result for {args.proposal_id}")
    
    elif args.submit_proposal:
        # Submit a test proposal
        proposal = ConsensusProposal(
            proposal_id=f"test_proposal_{int(time.time())}",
            intent_type="execute_trade",
            payload={
                "symbol": "BTC-USD",
                "action": "BUY",
                "amount": 0.001,
                "reason": "Quantum signal detected arbitrage opportunity"
            },
            proposer_agent="quantumarb_real",
        )
        engine.submit_proposal(proposal)
        print(f"Test proposal submitted: {proposal.proposal_id}")
    
    elif args.submit_vote:
        if not args.proposal_id:
            print("Error: --proposal-id required for --submit-vote")
            return
        
        # Submit a test vote
        vote = ConsensusVote(
            proposal_id=args.proposal_id,
            agent_id="test_agent",
            vote=VoteChoice.APPROVE,
            trust_score=3.5,
            confidence=0.8,
            reasoning="Agree with quantum analysis"
        )
        engine.submit_vote(vote)
        print(f"Test vote submitted for {args.proposal_id}")
    
    elif args.run_daemon:
        engine.run_daemon(interval_seconds=args.interval)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()