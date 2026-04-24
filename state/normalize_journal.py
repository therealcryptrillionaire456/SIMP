"""Decision journal entry normalizer.

Ensures canonical fill_status and policy_result.status values.
Used by backfill processes and runtime watch loops.
"""

import json
import sys
from pathlib import Path

CANONICAL_FILL_STATUS = {
    "executed", "policy_blocked", "exchange_error",
    "strategy_rejected", "stale"
}

CANONICAL_POLICY_STATUS = {"allow", "block", "shadow"}

FILL_STATUS_MAP = {
    "ok": "executed",
    "success": "executed",
    "rejected": "policy_blocked",
    "rejected_operational": "strategy_rejected",
    "rejected_strategy": "strategy_rejected",
    "insufficient_balance": "exchange_error",
    "exception": "exchange_error",
    "exception:AttributeError": "exchange_error",
    "exception:CoinbaseOperationError": "exchange_error",
    "pending": "stale",
}


def normalize_entry(entry, force=True):
    """Normalize a single decision journal entry in-place.

    Args:
        entry: A dict representing a decision journal record.
        force: If True, overwrite non-canonical values even for
               terminal entries. If False, skip terminal entries.

    Returns:
        The (possibly modified) entry.
    """
    # Normalize fill_status
    raw = entry.get("fill_status")
    if raw and raw not in CANONICAL_FILL_STATUS and raw in FILL_STATUS_MAP:
        entry["fill_status"] = FILL_STATUS_MAP[raw]
    elif raw and raw not in CANONICAL_FILL_STATUS and raw not in FILL_STATUS_MAP:
        entry["fill_status"] = "exchange_error"

    # Normalize policy_result.status
    policy = entry.get("policy_result")
    if policy and isinstance(policy, dict):
        ps = policy.get("status")
        if ps and ps not in CANONICAL_POLICY_STATUS:
            ps_lower = ps.lower()
            if ps_lower in CANONICAL_POLICY_STATUS:
                policy["status"] = ps_lower
            elif ps_lower in ("allowed", "ok", "executed", "dry_run_ok", "allow_shadow"):
                policy["status"] = "allow" if ps_lower != "allow_shadow" else "shadow"
            elif "block" in ps_lower or "deny" in ps_lower:
                policy["status"] = "block"
            else:
                policy["status"] = "shadow"

    # Ensure lineage exists
    if "lineage" not in entry:
        entry["lineage"] = {"parent_id": None, "type": "legacy"}

    return entry


def normalize_file(path, force=True):
    """Normalize all entries in a journal file in-place.

    Returns:
        (updated_count, total_count)
    """
    p = Path(path)
    if not p.exists():
        return (0, 0)

    with open(p) as f:
        lines = f.readlines()

    updated = 0
    total = 0
    with open(p, "w") as f:
        for line in lines:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                f.write(line + "\n")
                continue
            old = json.dumps(entry, sort_keys=True)
            entry = normalize_entry(entry, force=force)
            new = json.dumps(entry, sort_keys=True)
            if old != new:
                updated += 1
            f.write(json.dumps(entry) + "\n")

    return (updated, total)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "state/decision_journal.ndjson"
    updated, total = normalize_file(path)
    print(f"Normalized {path}: {updated} updated, {total} total")
