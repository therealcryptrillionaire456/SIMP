#!/usr/bin/env python3
"""Test quantum consensus system."""
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

from quantum_consensus import QuantumConsensusEngine, ConsensusProposal, ConsensusVote, VoteChoice
import time

def main():
    engine = QuantumConsensusEngine()
    
    # Submit a proposal
    proposal = ConsensusProposal(
        proposal_id="trade_001",
        intent_type="execute_trade",
        payload={
            "symbol": "BTC-USD",
            "action": "BUY",
            "amount": 0.001,
            "reason": "Quantum arbitrage signal"
        },
        proposer_agent="quantumarb_real",
    )
    engine.submit_proposal(proposal)
    print(f"✓ Proposal submitted: {proposal.proposal_id}")
    
    # Submit votes from different agents
    votes = [
        ConsensusVote(
            proposal_id="trade_001",
            agent_id="quantumarb_real",
            vote=VoteChoice.APPROVE,
            trust_score=4.2,
            confidence=0.9,
            reasoning="High confidence in quantum signal"
        ),
        ConsensusVote(
            proposal_id="trade_001",
            agent_id="gate4_real",
            vote=VoteChoice.APPROVE,
            trust_score=3.8,
            confidence=0.7,
            reasoning="Portfolio alignment"
        ),
        ConsensusVote(
            proposal_id="trade_001",
            agent_id="risk_manager",
            vote=VoteChoice.REJECT,
            trust_score=4.5,
            confidence=0.6,
            reasoning="Risk threshold exceeded"
        ),
        ConsensusVote(
            proposal_id="trade_001",
            agent_id="analyst_bot",
            vote=VoteChoice.APPROVE,
            trust_score=3.0,
            confidence=0.8,
            reasoning="Technical indicators positive"
        ),
    ]
    
    for vote in votes:
        engine.submit_vote(vote)
        print(f"✓ Vote submitted: {vote.agent_id} -> {vote.vote.value}")
    
    # Compute consensus
    print("\nComputing consensus...")
    result = engine.compute_consensus("trade_001")
    
    if result:
        print(f"\n✓ Consensus Result:")
        print(f"  Proposal: {result.proposal_id}")
        print(f"  Outcome: {result.outcome.value}")
        print(f"  Quantum Confidence: {result.quantum_confidence:.2f}")
        print(f"  Weighted Approve: {result.weighted_approve:.2f}")
        print(f"  Weighted Total: {result.weighted_total:.2f}")
        print(f"  Participation Rate: {result.participation_rate:.2f}")
        print(f"  Total Votes: {len(result.votes)}")
        
        print(f"\n  Vote Breakdown:")
        for vote in result.votes:
            weight = vote.trust_score * vote.confidence
            print(f"    - {vote.agent_id}: {vote.vote.value} (trust: {vote.trust_score}, conf: {vote.confidence:.1f}, weight: {weight:.2f})")
    else:
        print("✗ No consensus result")

if __name__ == "__main__":
    main()
