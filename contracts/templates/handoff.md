# Shift Handoff — {{shift_id}}

**Shift:** Day {{day}} / Shift {{shift_num}} ({{start_utc}} → {{end_utc}})
**Closing agent set:** A0..A9
**Mode at close:** {{mode}}

## Runtime snapshot at close
- verifier: {{green|yellow|red}}  (pass rate 6h: {{pct}})
- last_signal_age_s: {{n}}
- last_fill_age_s: {{n|null}}
- bridge_rtt_ms_p95: {{n}}
- budget_remaining_usd: {{n}}
- policy_block_rate_1h: {{pct}}

## Objective status
- Day objective: {{one line}}
- Completed: {{bullets}}
- In progress: {{bullets}}
- Blocked: {{bullets with reasons}}

## Open incidents
| ID | Sev | Lane | Opened | Summary |
|----|-----|------|--------|---------|
| ... |

## Lane summaries
- A1 Runtime: {{one line}}
- A2 Revenue: {{one line}}
- A3 Decision: {{one line}}
- A4 Protocol: {{one line}}
- A5 Safety: {{one line}}
- A6 Observability: {{one line}}
- A7 Repo Hygiene: {{one line}}
- A8 Docs Brain: {{one line}}

## A9 truth verdict
{{pass | mixed | regressed}} — pointer to `state/shift_truth_report.md`

## Do-not-touch list for next shift
- {{file/path}} — {{why}}

## Top 3 for next shift (A0 proposed)
1.
2.
3.
