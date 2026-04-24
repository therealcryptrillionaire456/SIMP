#!/usr/bin/env python3.10
"""
fix_mesh_subscribe.py
Patches quantum_signal_bridge.py, projectx_quantum_advisor.py,
and quantumarb_mesh_consumer.py to use correct broker API patterns.

Fixes:
  1. /mesh/subscribe 400 → add simp_versions + correct payload
  2. POST /mesh/poll 405 → change to GET /mesh/subscribe/{channel}

Usage:
    cd "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
    python3.10 fix_mesh_subscribe.py
"""
import re, sys, shutil
from pathlib import Path
from datetime import datetime

BACKUP_SUFFIX = f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

FIXES = []

def patch_file(fname, patches):
    """Apply a list of (description, old, new) patches to a file."""
    p = Path(fname)
    if not p.exists():
        print(f"  ⚠️  {fname} not found — skipping")
        return

    content = p.read_text()
    original = content
    applied = []

    for desc, old, new in patches:
        if old in content:
            content = content.replace(old, new, 1)
            applied.append(desc)
        elif re.search(old, content) and old.startswith('(?'):
            # regex patch
            content = re.sub(old, new, content, count=1)
            applied.append(desc)

    if content != original:
        shutil.copy2(p, str(p) + BACKUP_SUFFIX)
        p.write_text(content)
        for desc in applied:
            print(f"  ✅ {fname}: {desc}")
    else:
        print(f"  ℹ️  {fname}: no changes needed (patterns not matched)")

# ── quantum_signal_bridge.py patches ─────────────────────────────────────────
print("\n── quantum_signal_bridge.py ────────────────────────────")
patch_file("quantum_signal_bridge.py", [
    (
        "subscribe payload: add simp_versions",
        '"agent_id": ',
        '"simp_versions": ["1.0"],\n            "agent_id": ',
    ),
])
# If the above already has simp_versions, try a broader fix
content = Path("quantum_signal_bridge.py").read_text() if Path("quantum_signal_bridge.py").exists() else ""
if '"simp_versions"' not in content and Path("quantum_signal_bridge.py").exists():
    # Find subscribe calls and inject
    def add_simp_versions(m):
        block = m.group(0)
        if '"simp_versions"' not in block and "'simp_versions'" not in block:
            # Add after opening brace
            return block.replace('{', '{\n            "simp_versions": ["1.0"],', 1)
        return block
    new_content = re.sub(
        r'requests\.post\([^)]*mesh/subscribe[^)]*\)',
        lambda m: m.group(0),  # noop on the call itself
        content
    )
    # Find the data/json dict passed to subscribe
    new_content = re.sub(
        r'(\/mesh\/subscribe["\'][^{]*\{)',
        r'\1\n            "simp_versions": ["1.0"],',
        content
    )
    if new_content != content:
        Path("quantum_signal_bridge.py").write_text(new_content)
        print("  ✅ quantum_signal_bridge.py: simp_versions injected via regex")

# ── projectx_quantum_advisor.py patches ──────────────────────────────────────
print("\n── projectx_quantum_advisor.py ─────────────────────────")
patch_file("projectx_quantum_advisor.py", [
    (
        "subscribe payload: add simp_versions",
        '"agent_id": ',
        '"simp_versions": ["1.0"],\n            "agent_id": ',
    ),
])

# ── quantumarb_mesh_consumer.py — fix POST /mesh/poll → GET ──────────────────
print("\n── quantumarb_mesh_consumer.py: fix /mesh/poll ─────────")
p = Path("quantumarb_mesh_consumer.py")
if p.exists():
    content = p.read_text()
    original = content

    # Replace POST /mesh/poll with GET /mesh/subscribe/{channel}
    # Pattern: requests.post(f"{BROKER}/mesh/poll", ...)
    if '/mesh/subscribe/{channel}' + f"?agent_id={AGENT_ID}" in content:
        # Find the poll call and replace with GET subscribe
        new_content = re.sub(
            r'requests\.post\s*\(\s*[f\'"]([^"\']*)/mesh/poll[f\'"\s]*[,\)][^)]*\)',
            lambda m: f'requests.get(f"{m.group(1)}/mesh/subscribe/{{RESPONSE_CHANNEL}}?agent_id={{AGENT_ID}}", timeout=10)',
            content
        )
        if new_content == content:
            # Simpler replacement
            new_content = content.replace(
                "POST /mesh/poll",
                "GET /mesh/subscribe"
            ).replace(
                'requests.post(f"{BROKER}/mesh/poll"',
                'requests.get(f"{BROKER}/mesh/subscribe/{RESPONSE_CHANNEL}?agent_id={AGENT_ID}"',
            )

        if new_content != content:
            shutil.copy2(p, str(p) + BACKUP_SUFFIX)
            p.write_text(new_content)
            print("  ✅ quantumarb_mesh_consumer.py: /mesh/poll POST → GET subscribe")
        else:
            print("  ⚠️  Could not auto-patch /mesh/poll — showing location:")
            for i, line in enumerate(content.split('\n'), 1):
                if 'mesh/poll' in line:
                    print(f"     Line {i}: {line.strip()}")
            print("  Manual fix: change POST /mesh/poll to:")
            print("    GET /mesh/subscribe/{channel}?agent_id={AGENT_ID}")
    else:
        print("  ℹ️  /mesh/poll not found in file")

# ── Verification ──────────────────────────────────────────────────────────────
print("\n── Verification ────────────────────────────────────────")
for fname in ["quantum_signal_bridge.py", "projectx_quantum_advisor.py", "quantumarb_mesh_consumer.py"]:
    p = Path(fname)
    if p.exists():
        content = p.read_text()
        has_sv = '"simp_versions"' in content or "'simp_versions'" in content
        has_poll = '/mesh/subscribe/{channel}' + f"?agent_id={AGENT_ID}" in content
        print(f"  {'✅' if has_sv else '❌'} {fname}: simp_versions present: {has_sv}")
        if has_poll:
            print(f"  ⚠️  {fname}: still has /mesh/poll — manual fix needed")

print("\n── Next: restart affected processes ────────────────────")
print("""
pkill -f quantum_signal_bridge; sleep 1
pkill -f quantumarb_mesh_consumer; sleep 1
pkill -f projectx_quantum_advisor; sleep 1

nohup python3.10 quantum_signal_bridge.py > data/logs/goose/quantum_signal_bridge.log 2>&1 &
nohup python3.10 quantumarb_mesh_consumer.py > data/logs/goose/quantumarb_mesh_consumer.log 2>&1 &
nohup python3.10 projectx_quantum_advisor.py > data/logs/goose/projectx_quantum_advisor.log 2>&1 &
sleep 5
tail -5 data/logs/goose/quantum_signal_bridge.log
""")
