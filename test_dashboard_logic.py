import json
from pathlib import Path

# Test the exact logic from dashboard
ledger_path = Path("data/task_ledger.jsonl")
intents = []

if ledger_path.exists():
    with open(ledger_path, 'r') as f:
        # Read last 1000 lines
        f.seek(0, 2)
        file_size = f.tell()
        chunk_size = 8192
        data = ''
        position = file_size
        
        while position > 0 and len(intents) < 100:
            position = max(0, position - chunk_size)
            f.seek(position)
            chunk = f.read(chunk_size)
            data = chunk + data
            
            lines_chunk = data.split('\n')
            for line in lines_chunk[-100:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    data_entry = json.loads(line)
                    if 'intent' in data_entry.get('tags', []):
                        title = data_entry.get('title', '')
                        intent_type = title.replace('Intent: ', '') if title.startswith('Intent: ') else 'unknown'
                        intents.append({
                            'intent_id': data_entry.get('task_id', ''),
                            'intent_type': intent_type,
                            'source_agent': 'system',
                            'target_agent': data_entry.get('assigned_agent', ''),
                            'status': data_entry.get('status', ''),
                            'timestamp': data_entry.get('created_at', ''),
                            'delivery_status': 'delivered' if data_entry.get('status') == 'completed' else 'pending',
                            'created_at': data_entry.get('created_at', ''),
                            'updated_at': data_entry.get('updated_at', '')
                        })
                except json.JSONDecodeError:
                    continue
            data = lines_chunk[0] if lines_chunk else ''

print(f"Found {len(intents)} intents using dashboard logic")
if intents:
    print("Most recent:")
    for i in intents[:5]:
        print(f"  • {i['intent_type']} -> {i['target_agent']}: {i['status']}")
else:
    print("NO INTENTS FOUND - something wrong with logic")