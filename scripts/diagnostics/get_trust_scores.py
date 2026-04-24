#!/usr/bin/env python3
"""
Get trust scores in JSON format.
"""

import json
import sys
sys.path.insert(0, '.')

from simp.mesh.trust_scorer import get_trust_scorer

def main():
    scorer = get_trust_scorer()
    profiles = scorer.compute()
    
    # Convert to simple dict
    scores = {}
    for agent_id, profile in profiles.items():
        scores[agent_id] = {
            "score": profile.score,
            "total_receipts": profile.total_receipts,
            "delivery_rate": profile.breakdown.get("delivery_rate", 0),
            "avg_latency_ms": profile.breakdown.get("avg_latency_ms", 0),
            "payments_settled": profile.payments_settled,
            "payments_attempted": profile.payments_attempted,
            "recency_score": profile.breakdown.get("recency_score", 0),
        }
    
    print(json.dumps(scores, indent=2))

if __name__ == "__main__":
    main()