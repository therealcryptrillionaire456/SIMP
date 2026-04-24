#!/usr/bin/env python3
"""
ProjectX DPO Dataset Converter
Transforms ProjectX operational logs into preference pairs for DPO training.

Creates chosen/rejected pairs based on:
- Cost efficiency (cheap = better when quality comparable)
- Task success (completed = better than failed)
- Risk-adjusted outcomes (low risk + high reward = best)
"""

import json
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
from datasets import Dataset

@dataclass
class PreferencePair:
    prompt: str
    chosen: str
    rejected: str
    rationale: str

def load_trade_data(path: str) -> List[Dict]:
    """Load and parse trade ledger."""
    trades = []
    with open(path) as f:
        for line in f:
            trades.append(json.loads(line))
    return trades

def load_task_data(path: str) -> List[Dict]:
    """Load and parse task ledger."""
    tasks = []
    with open(path) as f:
        for line in f:
            tasks.append(json.loads(line))
    return tasks

def load_cost_data(path: str) -> List[Dict]:
    """Load and parse cost ledger."""
    costs = []
    with open(path) as f:
        for line in f:
            costs.append(json.loads(line))
    return costs

def generate_cost_optimization_pairs(cost_data: List[Dict]) -> List[PreferencePair]:
    """Generate preference pairs for cost optimization decisions."""
    pairs = []
    
    by_model = {}
    for entry in cost_data:
        model = entry.get("model", "unknown")
        if model not in by_model:
            by_model[model] = []
        by_model[model].append(entry)
    
    for model, entries in by_model.items():
        if len(entries) < 2:
            continue
        
        for i, entry in enumerate(entries):
            for j, other in enumerate(entries):
                if i >= j:
                    continue
                    
                prompt = f"""You are the ProjectX Economic Brain. A task requires analysis.

Task context: {entry.get('description', 'General analysis task')}
Token count: {entry.get('total_tokens', 0)}

Which model choice is more cost-effective?

A) Use {entry.get('model', 'current model')} at ${entry.get('estimated_cost', 0):.4f} total cost
B) Use {other.get('model', 'alternative')} at ${other.get('estimated_cost', 0):.4f} total cost

Choose the more cost-efficient option while maintaining quality."""
                
                if entry.get("estimated_cost", 999) <= other.get("estimated_cost", 0):
                    chosen = "A"
                else:
                    chosen = "B"
                
                pairs.append(PreferencePair(
                    prompt=prompt,
                    chosen=chosen,
                    rejected="B" if chosen == "A" else "A",
                    rationale="Cost efficiency comparison"
                ))
    
    return pairs

def generate_trade_risk_pairs(trade_data: List[Dict]) -> List[PreferencePair]:
    """Generate preference pairs for trade risk decisions."""
    pairs = []
    
    symbols = set(t.get("symbol") for t in trade_data)
    
    for symbol in symbols:
        symbol_trades = [t for t in trade_data if t.get("symbol") == symbol]
        
        for i, trade in enumerate(symbol_trades):
            for j, other in enumerate(symbol_trades):
                if i >= j:
                    continue
                    
                notional_1 = trade.get("notional_usd", 0)
                notional_2 = other.get("notional_usd", 0)
                
                prompt = f"""You are the ProjectX Economic Brain managing crypto trading risk.

Current position analysis for {symbol}:
Trade 1: ${notional_1:.2f} notional
Trade 2: ${notional_2:.2f} notional

Risk constraints: Max $500 notional per trade, Max $5000 total exposure

Which trade size is more appropriate for risk-adjusted returns?"""
                
                if notional_1 <= notional_2 and notional_1 <= 500:
                    chosen = "Trade 1 - smaller position reduces risk exposure"
                    rejected = "Trade 2 - larger position increases exposure"
                elif notional_2 <= 500:
                    chosen = "Trade 2 - smaller position reduces risk exposure"
                    rejected = "Trade 1 - larger position increases exposure"
                else:
                    chosen = f"Trade 1 at ${notional_1:.2f}"
                    rejected = f"Trade 2 at ${notional_2:.2f}"
                
                pairs.append(PreferencePair(
                    prompt=prompt,
                    chosen=chosen,
                    rejected=rejected,
                    rationale="Risk-adjusted position sizing"
                ))
    
    return pairs

def generate_task_routing_pairs(task_data: List[Dict]) -> List[PreferencePair]:
    """Generate preference pairs for task routing decisions."""
    pairs = []
    
    agent_outcomes = {}
    for task in task_data:
        agent = task.get("assigned_agent", "unknown")
        status = task.get("status", "unknown")
        if agent not in agent_outcomes:
            agent_outcomes[agent] = {"success": 0, "failed": 0}
        if status == "completed":
            agent_outcomes[agent]["success"] += 1
        elif status == "failed":
            agent_outcomes[agent]["failed"] += 1
    
    agents = list(agent_outcomes.keys())
    
    for i, agent_a in enumerate(agents):
        for agent_b in agents[i+1:]:
            outcome_a = agent_outcomes[agent_a]
            outcome_b = agent_outcomes[agent_b]
            
            total_a = outcome_a["success"] + outcome_a["failed"]
            total_b = outcome_b["success"] + outcome_b["failed"]
            
            rate_a = outcome_a["success"] / total_a if total_a > 0 else 0
            rate_b = outcome_b["success"] / total_b if total_b > 0 else 0
            
            prompt = f"""You are the ProjectX Economic Brain optimizing task routing.

Agent performance comparison:
Agent A ({agent_a}): {outcome_a["success"]} successes, {outcome_a["failed"]} failures ({rate_a:.1%} success rate)
Agent B ({agent_b}): {outcome_b["success"]} successes, {outcome_b["failed"]} failures ({rate_b:.1%} success rate)

Which agent should handle the next similar task?"""
            
            if rate_a >= rate_b:
                chosen = f"Agent A ({agent_a}) - higher success rate of {rate_a:.1%}"
                rejected = f"Agent B ({agent_b}) - success rate of {rate_b:.1%}"
            else:
                chosen = f"Agent B ({agent_b}) - higher success rate of {rate_b:.1%}"
                rejected = f"Agent A ({agent_a}) - success rate of {rate_a:.1%}"
            
            pairs.append(PreferencePair(
                prompt=prompt,
                chosen=chosen,
                rejected=rejected,
                rationale="Agent routing based on historical success rates"
            ))
    
    return pairs

def generate_revenue_pairs() -> List[PreferencePair]:
    """Generate synthetic revenue optimization reasoning pairs."""
    
    return [
        PreferencePair(
            prompt="""You are the ProjectX Economic Brain. A new model API costs 10x more per token but processes tasks 5x faster.

Context: Your system handles 1000 tasks/day. Current cost is $10/day. The new API would cost $100/day but save 4 hours of compute time.

What should ProjectX do?""",
            chosen="Consider the new API if the 4 hours of compute time has >$90/day opportunity cost. Track ROI over 30 days before full adoption.",
            rejected="Immediately switch to save time - cost savings matter more.",
            rationale="Balanced cost-benefit analysis"
        ),
        
        PreferencePair(
            prompt="""You are the ProjectX Economic Brain. Two trading strategies are available:

Strategy A: 80% win rate, 1:1 risk/reward, 10 trades/day
Strategy B: 50% win rate, 3:1 risk/reward, 3 trades/day

Both have similar expected value. Which is better for ProjectX?""",
            chosen="Strategy A - higher win rate provides more consistent returns and lower variance, better for systematic capital deployment.",
            rejected="Strategy B - higher risk/reward ratio maximizes returns when wins occur.",
            rationale="Balanced decision-making prefers consistency"
        ),
        
        PreferencePair(
            prompt="""You are the ProjectX Economic Brain. Budget allows upgrading one system:

Option 1: Faster model inference (2x speed, same cost)
Option 2: Better context window (4x context, 2x cost)

Current bottleneck: Complex multi-step tasks timing out.

What maximizes revenue generation?""",
            chosen="Option 2 - larger context windows prevent task failures on complex operations, which have higher revenue impact than speed.",
            rejected="Option 1 - faster inference means more tasks completed per hour.",
            rationale="Revenue impact > raw throughput"
        ),
        
        PreferencePair(
            prompt="""You are the ProjectX Economic Brain. A new integration costs $500/month and is expected to generate $300/month in savings.

Should ProjectX approve this integration?""",
            chosen="Reject - negative ROI. Better to allocate budget to positive-ROI initiatives or optimize existing workflows first.",
            rejected="Approve - any automation saves time and reduces human error costs.",
            rationale="Strict ROI discipline for sustainable growth"
        ),
        
        PreferencePair(
            prompt="""You are the ProjectX Economic Brain. Current usage: 40% of API budget. Response time: 200ms avg.

A scale-up would cost 2x more but handle 5x more volume. Current revenue: $1000/month.

When should we scale up?""",
            chosen="Scale when current capacity reaches 70-80% OR when wait times exceed 500ms, whichever comes first. Premature scaling wastes capital.",
            rejected="Scale now to capture market opportunity faster.",
            rationale="Capacity planning based on utilization metrics"
        ),
    ]

def create_huggingface_dataset(pairs: List[PreferencePair], output_path: str):
    """Convert pairs to HuggingFace dataset format for DPO."""
    
    dataset_dict = {
        "prompt": [],
        "chosen": [],
        "rejected": [],
    }
    
    for pair in pairs:
        dataset_dict["prompt"].append(pair.prompt)
        dataset_dict["chosen"].append(pair.chosen)
        dataset_dict["rejected"].append(pair.rejected)
    
    dataset = Dataset.from_dict(dataset_dict)
    dataset.save_to_disk(output_path)
    print(f"Dataset saved to {output_path}")
    print(f"Total pairs: {len(pairs)}")
    
    return dataset

def main():
    data_dir = Path("data")
    
    print("ProjectX DPO Dataset Converter")
    print("=" * 50)
    
    all_pairs = []
    
    trade_data = []
    task_data = []
    cost_data = []
    
    if (data_dir / "phase4_pnl_ledger.jsonl").exists():
        trade_data = load_trade_data(data_dir / "phase4_pnl_ledger.jsonl")
        print(f"Loaded {len(trade_data)} trades")
    
    if (data_dir / "task_ledger.jsonl").exists():
        task_data = load_task_data(data_dir / "task_ledger.jsonl")
        print(f"Loaded {len(task_data)} tasks")
    
    if (data_dir / "cost_ledger.jsonl").exists():
        cost_data = load_cost_data(data_dir / "cost_ledger.jsonl")
        print(f"Loaded {len(cost_data)} cost entries")
    
    print("\nGenerating preference pairs...")
    
    if cost_data:
        cost_pairs = generate_cost_optimization_pairs(cost_data)
        all_pairs.extend(cost_pairs)
        print(f"  + Cost optimization pairs: {len(cost_pairs)}")
    
    if trade_data:
        trade_pairs = generate_trade_risk_pairs(trade_data)
        all_pairs.extend(trade_pairs)
        print(f"  + Trade risk pairs: {len(trade_pairs)}")
    
    if task_data:
        task_pairs = generate_task_routing_pairs(task_data)
        all_pairs.extend(task_pairs)
        print(f"  + Task routing pairs: {len(task_pairs)}")
    
    reasoning_pairs = generate_revenue_pairs()
    all_pairs.extend(reasoning_pairs)
    print(f"  + Revenue reasoning pairs: {len(reasoning_pairs)}")
    
    print(f"\nCreating dataset with {len(all_pairs)} total pairs...")
    dataset = create_huggingface_dataset(all_pairs, "scripts/training/projectx_dpo_dataset")
    
    print("\nSample pair:")
    sample = all_pairs[0]
    print(f"  Prompt: {sample.prompt[:100]}...")
    print(f"  Chosen: {sample.chosen[:80]}...")
    
    return dataset

if __name__ == "__main__":
    main()
