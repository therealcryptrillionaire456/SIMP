# ProjectX Economic Mastery: 4-Tranche Training Roadmap

## Summary
ProjectX already has solid foundations (RAG, learning loop, safety, multimodal).
The path to financial mastery requires training across 4 tranches, each building
capabilities that compound on the last.

**Status**: Tranche 1 Phase 1 (SFT) — RUNNING on Modal A10G

---

## Tranche 1: Foundation Phase (Phases 7-9)
Objective: Memory consolidation, world modeling, tool synthesis.
Turns ProjectX from "static prompt optimizer" to "living operational mind."

| Phase | Focus | Source | Format | Status |
|-------|-------|--------|--------|--------|
| 7 | Memory | SIMP traces, Mesh events, task sequences | Episode pairs | 🔜 |
| 8 | World Model | Service dependencies, causal chains | Causal graphs | 🔜 |
| 9 | Tool Ecology | Tool descriptions, capability gaps | Tool spec + validation pairs | 🔜 |

**Running Now**: SFT on finance-alpaca (68k) + DPO on ProjectX preferences (821 pairs)
**Output Model**: `automationkasey/projectx-economic-brain-dpo`

---

## Tranche 2: Truth & Self-Correction (Phases 10-12)
Objective: Rigorous eval framework, self-repair, synthetic data pipeline.

| Phase | Focus | Source | Format | Status |
|-------|-------|--------|--------|--------|
| 10 | Evals | Adversarial scenarios, regression tests | (task, expected, score) | 🔜 |
| 11 | Self-Repair | Invariant violations, drift patterns | (symptom→fix) pairs | 🔜 |
| 12 | Data Foundry | Hard examples from failures | SFT + preference pairs | 🔜 |

---

## Tranche 3: Market Cognition (Phases 13-15)
Objective: Separate market intelligence from general reasoning. Revenue multiplier.

| Phase | Focus | Source | Format | Status |
|-------|-------|--------|--------|--------|
| 13 | Market Layer | Regime detection, narrative tracking | (market_state→strategy) | 🔜 |
| 14 | Org Compiler | Goal decomposition, queue planning | (goal→executable_plan) | 🔜 |
| 15 | Multimodal | Screenshots, charts, dashboard anomalies | Vision + text alignment | 🔜 |

---

## Tranche 4: Durability & Autonomy (Phases 16-20)
Objective: Federated minds, economic assets, quantum optimization, governance.

| Phase | Focus | Source | Format | Status |
|-------|-------|--------|--------|--------|
| 16 | Federation | Model routing, specialist coordination | (task→best_model) | 🔜 |
| 17 | Economic Assets | Product opportunities, IP discovery | (capability→product) | 🔜 |
| 18 | Self-Experimentation | Hypothesis testing, A/B results | (hypothesis→outcome) | 🔜 |
| 19 | Quantum | QAOA circuits, portfolio allocation | (problem→classical_vs_quantum) | 🔜 |
| 20 | Constitutional | Self-modification rules, governance proofs | (proposal→approved) | 🔜 |

---

## Training Data Pipeline
- **Tranche 1** → Real operational traces (Mesh events, task sequences)
- **Tranche 2** → Generated adversarial + synthetic hard examples
- **Tranche 3** → Market-specific (trades, regimes, dashboards)
- **Tranche 4** → Meta-level (coordination, governance, self-reference)

## Hardware
| Tranche | GPU | Duration | Status |
|---------|-----|----------|--------|
| T1 (SFT + DPO) | A10G-large | 30-60 min/phase | **🟢 SFT Running** |
| T2 (Evals + Self-Repair) | T4 | 1-2 hrs | 🔜 |
| T3 (Market + Multi) | A10G-large | 3-4 hrs | 🔜 |
| T4 (Meta + Constitutional) | T4 | 1-2 hrs | 🔜 |

## Success Definition
ProjectX achieves financial mastery when:
- ✅ Market regime calls with >85% accuracy
- ✅ Self-repairs within 1hr of any failure
- ✅ Generates new tools without human intervention
- ✅ Operates autonomously for 30+ days without founder input
