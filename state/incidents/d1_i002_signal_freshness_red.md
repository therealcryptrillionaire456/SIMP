# Incident: d1_i002 — signal_freshness stage red on baseline verifier

**Sev:** 3 (expected — no signals in empty state)
**Lane:** A2 (reported), A3 (owns signals)
**Opened:** 2026-04-24T07:29:00Z
**Stage:** signal_freshness
**Detail:** no recent decision/signal in journal
**Expected behavior:** After at least one signal cycle, this goes green. No action until the system has been running with signals for a few minutes.
**Resolution:** Inject a test signal with `python3 scripts/inject_live_signal.py --asset BTC-USD --side buy --usd 1.00` (paper mode), then re-run verifier.
