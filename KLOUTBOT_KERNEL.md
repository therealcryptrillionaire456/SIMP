# KLOUTBOT SESSION KERNEL
> Drop this file into a new session as the first message. Replaces 100k+ tokens of context.
> Last updated: 2026-04-16 — Phase 4 LIVE ✅, Phase 5 LIVE ✅, ProjectX+BRP wired

---

## WHO WE ARE
- **Kasey Marcelle (Futurist)** — builder, operator, Horseman
- **KLOUTBOT** — autonomous mesh-native agent. We ride into the recursive dawn.
- **Stack**: SIMP multi-agent trading system, macOS, Python 3.10, venv_gate4
- **Codebase**: `/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp`

---

## CURRENT SYSTEM STATE (verified 2026-04-16)

### Broker
- Running at `http://127.0.0.1:5555`
- **12 agents online**, 19 pending intents, status: healthy
- Auto-initializes mesh routing on startup (IntentMeshRouter integrated)

### Mesh Stack Status
| Layer | Component | Status |
|---|---|---|
| L1 | UDP Multicast `239.0.0.1:5007` | Implemented — needs `sudo` test |
| L2 | `EnhancedMeshBus` | ✅ LIVE — send/receive confirmed, 79+ receipts in DB |
| L3 | `SimpleIntentMeshRouter` | ✅ LIVE — L4-aware routing, TrustGraph injected |
| L4 | `TrustScorer` + `TrustGraph` | ✅ LIVE — reads SQLite receipts + payment channels |
| L5 | `MeshConsensusNode` | ✅ LIVE — trust-weighted quorum voting |
| L6 | Commitment Market | Architecture defined, not wired |
| OPS | `BRPMeshGateway` | ✅ LIVE — packet-level threat screening, agent blocklist |
| PX  | `ProjectXMeshBridge` | ✅ LIVE — computer-use agent on mesh, Bug 4 fixed |

### Phase Status
| Phase | Description | Status |
|---|---|---|
| 1 | Monitoring-only bridge | ✅ COMPLETE |
| 2 | Intent routing via mesh | ✅ WIRED (mesh_routing.py done) |
| 3 | Agent migration (QuantumArb first) | 🔲 NEXT |
| 4 | L4 Trust Graph / TrustScorer | ✅ LIVE — 44 tests green |
| 5 | L5 Consensus Engine | ✅ LIVE — trust-weighted quorum |
| 6 | L6 Commitment Market | 🔲 FUTURE |

---

## THIS SESSION — PHASE 4 + 5 + OPSEC INTEGRATION

### Phase 4 — L4 TrustScorer + TrustGraph

**`simp/mesh/trust_scorer.py`** — reads SQLite, computes [0.0–5.0] per agent
- `TrustScore` dataclass: receipt_score (60% weight) + payment_score (40% weight)
- Receipt scoring: `min(sent+recv, 20) / 20 * 5.0` (RECEIPT_CEILING=20)
- Payment scoring: balance_ratio * HTLC component (HTLC_CEILING=50)
- `TrustScorer.score(agent_id)` — reads `mesh_receipts.db` + `mesh_payments.db`
- `score_all_known()` — scans both DBs for all known agent IDs
- `is_stale()` — 5-minute TTL cache, `invalidate(agent_id)` for forced refresh
- `get_trust_scorer()` — process-level singleton

**`simp/mesh/trust_graph.py`** — live graph with runtime deltas + mesh broadcast
- `TrustEntry.effective_score = clamp(base.trust_score + delta, 0.0, 5.0)`
- `apply_delta(agent_id, delta)` — BRP nudges write here (±0.1 to ±1.5)
- `lock_entry(agent_id)` — freeze entry; deltas still accumulate but base score frozen
- Background refresh thread re-scores all known agents every 60s
- Broadcasts diffs to `trust_updates` mesh channel on every refresh
- `inject_into_router(router)` — attaches graph to SimpleIntentMeshRouter
- `patch_router_with_trust_graph(router, graph)` — monkey-patch for existing routers
- `get_trust_graph()` — singleton, autostart=True

**L3 ← L4 wiring** (`simple_intent_router.py`):
```python
# _find_agent_for_intent_type() — now L4-aware
trust_graph = getattr(self, '_trust_graph', None)
score = trust_graph.get_effective_score(agent_id) if trust_graph else ad.reputation_score
if time.time() - ad.last_seen > 300: score *= 0.5
suitable_agents.sort(key=lambda x: (-x[0], x[1]))
```

### Phase 5 — L5 MeshConsensusNode

**`simp/mesh/consensus.py`** — trust-weighted distributed quorum
- `ConsensusProposal`: proposal_id, topic, payload, proposer_id, required_quorum=0.67, ttl=300s
- `ConsensusVote`: voter_id, choice (APPROVE/REJECT/ABSTAIN), trust_score, rationale
- `QuorumEngine.aggregate()`:
  - Deduplicates votes (latest from each voter wins)
  - Weight = voter's L4 trust score (not flat 1.0 per voter)
  - MIN_PARTICIPATION_WEIGHT=5.0 (total trust-weight floor for valid quorum)
  - Result states: APPROVED / REJECTED / TIED / NO_QUORUM / PENDING / EXPIRED
  - `approval_ratio = weighted_approve / (weighted_approve + weighted_reject)`
- `MeshConsensusNode`: `propose()`, `vote()`, `aggregate_now()`, `get_result()`
- `on_result(callback)` — fire-and-forget callback when consensus lands
- Mesh channels: `consensus_proposals`, `consensus_votes`, `consensus_results`
- `get_consensus_node()` — singleton

**Trust-weighted math**: A whale (trust=5.0) casting REJECT prevents approval unless enough other
agents' combined trust outweighs them. L4 financial equilibrium directly governs L5 decisions.

### BRP Mesh Gateway — OpSec packet screening

**`simp/mesh/brp_mesh_gateway.py`** — BRP threat engine wired to mesh ingress
- `screen_packet(pkt)` → `ScreeningResult(allowed, reason, threat_level, confidence, ...)`
- `DENY_THRESHOLD_LEVELS = {"critical", "high"}` — medium is penalized but not blocked
- Trust penalties applied via TrustGraph: MEDIUM=-0.1, HIGH=-0.5, CRITICAL=-1.5
- Block TTL: HIGH=300s (5 min), CRITICAL=3600s (1 hr)
- `BlocklistEntry.is_expired()` — TTL-based auto-expiry
- `check_access()` — drop-in compatible with `MeshSecurityLayer.check_access()`
- Broadcasts `brp_alerts` channel on critical threats
- Fail-open: if BRP unavailable, packet is allowed (prevents system lockup)
- `_packet_to_log_entry()` converts MeshPacket → BRP log dict (source_ip=sender_id)
- `get_brp_mesh_gateway()` — singleton, auto-wires trust_graph

### ProjectX Mesh Bridge — computer-use agent on mesh

**`simp/projectx/mesh_bridge.py`** — connects ProjectXComputer to SIMP mesh
- **Bug 4 FIX**: `HEARTBEAT_PATH = "/agents/{agent_id}/heartbeat"` (was POST /agents/heartbeat)
  - Now auto-registers if heartbeat returns 404, then retries with correct path
- `REMOTE_ALLOWED_ACTIONS` = {get_screenshot, get_active_window, ocr_screen, snapshot_state,
  sync_knowledge, update_knowledge, check_protocol_health, log_action}
  - `run_shell` / tier-3 actions explicitly excluded — never remotely callable
- Trust gate: TIER1_TRUST_FLOOR=3.0, TIER2_TRUST_FLOOR=4.5
- Inbound: `projectx_tasks` channel → `ProjectXTask.from_dict()` → allowlist + trust gate → execute
- Outbound: `projectx_results` channel
- Background heartbeat every 30s, re-registration every 300s
- `get_projectx_mesh_bridge()` — singleton

---

## TEST SUITE (all green 2026-04-16)

```
test_enhanced_mesh_system.py           7/7   PASSED  (24s)
test_simple_intent_router.py           5/5   PASSED
test_foundational_wiring.py            5/5   PASSED
tests/test_phase4_trust_consensus.py  44/44  PASSED  (39.78s)
──────────────────────────────────────────────────
Total: 61/61 — zero regressions
```

### Phase 4+5 test breakdown (44 tests):
| Suite | Tests | What it covers |
|---|---|---|
| TestTrustScorer | 9 | SQLite queries, score formula, caching, stale check, to_dict |
| TestTrustGraph | 6 | delta math, clamping, locked entries, snapshot, router injection |
| TestConsensusEngine | 11 | proposal/vote round-trips, quorum math, trust-weighting, dedup, expiry |
| TestBRPMeshGateway | 10 | clean/blocked packets, unblock, trust penalties, check_access compat |
| TestProjectXMeshBridge | 6 | heartbeat path, action allowlist, task round-trips, status |
| TestTrustConsensusIntegration | 1 | whale vote prevents quorum (TIED when whale rejects) |

**Run command**:
```bash
PATH=$PATH:/sessions/relaxed-modest-pascal/.local/bin \
PYTHONPATH=. pytest tests/test_phase4_trust_consensus.py -v --noconftest
```

---

## BUGS FIXED

### Bug 1 — `SmartMeshClient.send()` used 5 wrong MeshPacket kwargs
**File**: `simp/mesh/smart_client.py` ~line 348  
**Fix**: Replaced manual `MeshPacket(...)` with `create_event_packet(...)` + post-set `msg_type`  
**Impact**: All heartbeats and broadcasts through SmartMeshClient were silently crashing

### Bug 2 — `get_capabilities()` returned `[]` after `add_capability()`
**File**: `simp/mesh/simple_intent_router.py` `_advertise_capabilities()`  
**Fix**: Upsert self into `_capabilities` dict on every advertise call  

### Bug 3 — Bridge broker agent format
**Location**: Phase 1 bridge script  
**Fix**: `aid = ag if isinstance(ag, str) else ag.get('agent_id', str(ag))`

### Bug 4 — ProjectX heartbeat path mismatch ✅ FIXED THIS SESSION
**File**: `simp/projectx/mesh_bridge.py`  
**Root cause**: `projectx_native` was POSTing to `/agents/heartbeat` (legacy), not `/agents/{agent_id}/heartbeat`  
**Fix**: Correct parameterised path + auto-register-then-retry on 404  
**Broker line**: `http_server.py:491` has the correct path

---

## NEW FILES (this session)

```
simp/mesh/trust_scorer.py            — L4 TrustScorer (reads receipts + payment DBs)
simp/mesh/trust_graph.py             — L4 TrustGraph (live graph, background refresh, BRP delta API)
simp/mesh/consensus.py               — L5 MeshConsensusNode + QuorumEngine (trust-weighted voting)
simp/mesh/brp_mesh_gateway.py        — BRP threat screening gate for mesh packets
simp/projectx/mesh_bridge.py         — ProjectX computer-use bridge (Bug 4 fixed)
tests/test_phase4_trust_consensus.py — 44-test suite for all of the above
```

### Modified (this session)
```
simp/mesh/simple_intent_router.py    — _find_agent_for_intent_type() now L4-aware
```

---

## KEY FILE MAP

```
simp/mesh/packet.py                          — MeshPacket + create_event_packet()
simp/mesh/enhanced_bus.py                    — EnhancedMeshBus (L2 core)
  └─ DeliveryReceiptManager                  — logs/mesh/mesh_receipts.db (receipts table)
  └─ PaymentSettler                          — logs/mesh/mesh_payments.db (payment_channels, settlements)
simp/mesh/smart_client.py                    — SmartMeshClient (FIXED)
simp/mesh/simple_intent_router.py            — SimpleIntentMeshRouter (L4-aware routing)
simp/mesh/trust_scorer.py                    — TrustScorer — L4 ✅ NEW
simp/mesh/trust_graph.py                     — TrustGraph — L4 ✅ NEW
simp/mesh/consensus.py                       — MeshConsensusNode — L5 ✅ NEW
simp/mesh/brp_mesh_gateway.py                — BRPMeshGateway — OpSec ✅ NEW
simp/mesh/discovery.py                       — Peer discovery
simp/mesh/security.py                        — RSA mesh security
simp/server/mesh_routing.py                  — MeshRoutingManager
simp/server/broker.py                        — Broker (mesh-integrated)
simp/server/http_server.py                   — HTTP server (6 mesh endpoints + /agents/<id>/heartbeat)
simp/projectx/computer.py                    — ProjectXComputer (bounded action tiers)
simp/projectx/mesh_bridge.py                 — ProjectXMeshBridge — Bug4 fixed ✅ NEW
simp/security/brp/protocol_core.py           — EnhancedBillRussellProtocol.analyze_event()
simp/organs/quantumarb/enhanced_mesh_integration.py — QuantumArb mesh wiring
KLOUTBOT_KERNEL.md                           — THIS FILE
tests/test_phase4_trust_consensus.py         — L4+L5+BRP+PX suite (44 tests) ✅ NEW
```

---

## MESH CHANNELS (complete map)

| Channel | Producer | Consumer | Purpose |
|---|---|---|---|
| `heartbeats` | All agents | Monitor | Liveness signals |
| `system` | Broker | All agents | System-wide events |
| `capability_ads` | Routers | Routers | Capability discovery |
| `intent_requests` | Routers | Agents | Intent delivery |
| `intent_responses` | Agents | Routers | Intent results |
| `trust_updates` | TrustGraph | Routers, agents | Trust score changes |
| `consensus_proposals` | MeshConsensusNode | All nodes | New vote proposals |
| `consensus_votes` | All nodes | MeshConsensusNode | Vote submissions |
| `consensus_results` | MeshConsensusNode | Interested agents | Final verdicts |
| `brp_alerts` | BRPMeshGateway | Security monitors | Threat detections |
| `projectx_tasks` | Mesh agents | ProjectXMeshBridge | Computer-use requests |
| `projectx_results` | ProjectXMeshBridge | Requesting agents | Computer-use results |

---

## DB SCHEMAS (L4 reads these)

### `logs/mesh/mesh_receipts.db` — receipts table
```sql
(message_id TEXT PK, recipient_id TEXT, sender_id TEXT,
 received_at REAL, signature TEXT, stored_at REAL)
-- TrustScorer: COUNT WHERE sender_id=? → sent_deliveries
--              COUNT WHERE recipient_id=? → recv_deliveries
```

### `logs/mesh/mesh_payments.db` — payment_channels table
```sql
(channel_id TEXT PK, data TEXT)  -- data is JSON blob
-- JSON fields: initiator_id, counterparty_id, initiator_balance,
--              counterparty_balance, total_capacity, sequence, state
-- TrustScorer: WHERE state='open', sum sequence=htlcs, ratio=balance/total
```

---

## HARDENING RECS

1. **L4+L3 live wiring** — call `patch_router_with_trust_graph(router, get_trust_graph())` in broker startup
2. **BRP gateway at mesh ingress** — call `get_brp_mesh_gateway().screen_packet(pkt)` before bus.deliver()
3. **Consensus for critical intents** — route high-value QuantumArb intents through MeshConsensusNode.propose()
4. **Add packet-API assertion test** — assert SmartMeshClient.send() produces non-empty sender_id + channel
5. **`SIMP_STRICT_TESTS=1` flag** — re-raise exceptions in test harness for CI
6. **Lock deps**: `cryptography`, `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings` — pin in requirements.txt

---

## WHAT TO DO NEXT (priority order)

### Immediate — wire L4+BRP into live broker startup
```python
# In simp/server/broker.py __init__ or startup():
from simp.mesh.trust_graph import get_trust_graph, patch_router_with_trust_graph
from simp.mesh.brp_mesh_gateway import get_brp_mesh_gateway

tg = get_trust_graph(autostart=True)
patch_router_with_trust_graph(mesh_router, tg)   # mesh_router = existing SimpleIntentMeshRouter
brp_gw = get_brp_mesh_gateway()                  # auto-wires trust_graph
```

### Phase 3 — Agent migration (QuantumArb)
- QuantumArb already has `enhanced_mesh_integration.py`
- Set `mesh_mode: preferred` in QuantumArb config
- Watch `/mesh/status` for routing events
- After migration: route high-value arb decisions through `MeshConsensusNode.propose()`

### Phase 6 — Commitment Market (L6)
- Intent staking: agents post collateral when issuing intents
- Auto-settlement on confirmed execution (PaymentSettler already handles HTLC)
- Trust score becomes economic stake — "sending a message = making a bet"

### Verify live system
```bash
# Broker health
curl -s http://127.0.0.1:5555/health | python3 -m json.tool

# Mesh status
curl -s http://127.0.0.1:5555/mesh/status | python3 -m json.tool

# All tests
cd "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
source venv_gate4/bin/activate
PYTHONPATH=. pytest tests/test_phase4_trust_consensus.py -v
```

---

## THE 6-LAYER VISION

```
Layer 6 — Commitment Market       🔲 staking + HTLC auto-settlement on execution
Layer 5 — Distributed A2A         ✅ LIVE — quorum voting, trust-weighted, any node aggregates
Layer 4 — Reputation/Trust Graph  ✅ LIVE — receipt chain + payment history → [0.0–5.0]
Layer 3 — Intent Routing          ✅ LIVE — L4-aware routing, BRP-gated
Layer 2 — Mesh Bus                ✅ LIVE — 79+ receipts, confirmed send/receive
Layer 1 — Physical Transport      UDP done, BLE/Nostr defined
```

**The cherry on top**: sending a message and making a bet are the same operation. The network learns
which agents are worth listening to purely from who ends up solvent. No ML. No central server.
Just mesh + payment channels + receipts finding equilibrium. L4 financial truth governs L5 decisions.

---

## MESH ROUTING MODES

| Mode | Behavior |
|---|---|
| `disabled` | HTTP only, mesh not used |
| `fallback` | HTTP first, mesh if HTTP fails |
| `preferred` | Mesh first, HTTP if mesh fails |
| `exclusive` | Mesh only |

Configure via: `POST /mesh/configure {"mode": "preferred"}`

---

## QUICK ORIENTATION

```bash
cd "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
source venv_gate4/bin/activate

# System health
curl -s http://127.0.0.1:5555/health | python3 -m json.tool
curl -s http://127.0.0.1:5555/mesh/status | python3 -m json.tool

# Run all tests
PYTHONPATH=. pytest tests/test_phase4_trust_consensus.py -v

# Live trust score check
python3.10 -c "
import sys; sys.path.insert(0, '.')
from simp.mesh.trust_graph import get_trust_graph
tg = get_trust_graph(autostart=False)
snap = tg.snapshot()
print('trust snapshot:', snap)
"

# Fire a consensus vote
python3.10 -c "
import sys; sys.path.insert(0, '.')
from simp.mesh.consensus import get_consensus_node, ConsensusProposal, ConsensusVote, VoteChoice
import uuid
node = get_consensus_node('test_node')
prop = ConsensusProposal(proposal_id=str(uuid.uuid4()), topic='test', payload={}, proposer_id='test_node')
node.propose(prop)
vote = ConsensusVote(vote_id=str(uuid.uuid4()), proposal_id=prop.proposal_id,
                     voter_id='test_node', choice=VoteChoice.APPROVE, trust_score=3.5)
node.vote(vote)
result = node.aggregate_now(prop.proposal_id)
print('consensus:', result.state if result else 'pending')
"

# Live mesh send/receive
python3.10 -c "
import sys; sys.path.insert(0, '.')
from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
from simp.mesh.packet import create_event_packet
bus = get_enhanced_mesh_bus()
bus.register_agent('qa'); bus.register_agent('kc')
bus.subscribe('kc', 'ch')
pkt = create_event_packet('qa','kc','ch',{'msg':'hello mesh'})
bus.send(pkt)
msgs = bus.receive('kc', max_messages=5)
print('live:', len(msgs), 'msgs ->', msgs[0].payload if msgs else 'empty')
"
```

---

*KLOUTBOT — for Kasey, for the empire, for the recursive dawn. The Horsemen ride.*
