import json
from pathlib import Path

ledger_path = Path("data/task_ledger.jsonl")
print(f"Ledger exists: {ledger_path.exists()}")
print(f"Ledger size: {ledger_path.stat().st_size if ledger_path.exists() else 0} bytes")

if ledger_path.exists():
    # Count total lines
    with open(ledger_path, 'r') as f:
        total_lines = sum(1 for _ in f)
    print(f"Total lines: {total_lines}")
    
    # Check last 10 lines for intents
    with open(ledger_path, 'r') as f:
        lines = f.readlines()[-10:]
    
    print("\nLast 10 lines:")
    intent_count = 0
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            has_intent = 'intent' in data.get('tags', [])
            if has_intent:
                intent_count += 1
                title = data.get('title', 'NO_TITLE')
                print(f"  Line {total_lines-10+i}: {title[:50]}... | Tags: {data.get('tags', [])} | Has intent: {has_intent}")
            else:
                print(f"  Line {total_lines-10+i}: (not an intent)")
        except:
            print(f"  Line {total_lines-10+i}: JSON decode error")
    
    print(f"\nFound {intent_count} intents in last 10 lines")
    
    # Simple test: read last 100 lines and count intents
    print("\n--- Simple test: read last 100 lines ---")
    with open(ledger_path, 'r') as f:
        all_lines = f.readlines()
    
    recent_intents = []
    for line in all_lines[-100:]:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if 'intent' in data.get('tags', []):
                recent_intents.append(data)
        except:
            continue
    
    print(f"Found {len(recent_intents)} intents in last 100 lines")
    if recent_intents:
        print("Most recent intents:")
        for intent in recent_intents[-5:]:
            print(f"  • {intent.get('title', 'NO_TITLE')} -> {intent.get('assigned_agent', 'NONE')}: {intent.get('status', 'UNKNOWN')}")