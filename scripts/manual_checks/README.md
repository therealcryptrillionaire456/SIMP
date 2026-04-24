# Manual Checks

These files are operator-run live checks and incident probes. They are not part of the normal `pytest` suite and do not belong at repo root.

Run them from the repo root, for example:

```bash
python3.10 scripts/manual_checks/test_qip_issue.py
python3.10 scripts/manual_checks/test_brp_audit.py
python3.10 scripts/manual_checks/test_all_apis.py
```

Conventions:

- `scripts/manual_checks/`: one-off or live-environment checks that may hit real services
- `tests/`: automated test suite intended for `pytest`
- `scripts/diagnostics/`: reusable diagnostics tied to current ops workflows
- `scripts/recovery/`: repair or incident-response scripts
