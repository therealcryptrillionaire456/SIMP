# Incident: d1_i001 — processes stage red on baseline verifier

**Sev:** 2 (expected — broker not running in fresh state)
**Lane:** A2 (reported), A1 (owns)
**Opened:** 2026-04-24T07:29:00Z
**Stage:** processes
**Detail:** missing: broker,http_server,orchestration_loop
**Expected behavior:** All three processes go green after `bash startall.sh` brings up the system.
**Resolution:** Run startall.sh in a terminal, then re-run verifier.
