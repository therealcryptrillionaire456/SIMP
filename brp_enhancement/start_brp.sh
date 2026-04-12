#!/bin/bash
# Enhanced BRP Startup Script

BRP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHONPATH="$BRP_DIR:$PYTHONPATH"

echo "Starting Enhanced Bill Russell Protocol..."
echo "Mode: $1 (default: defensive)"

MODE="${1:-defensive}"
python3 -c "
import sys
sys.path.append('$BRP_DIR')
from integration.brp_enhanced_framework import BRPEnhancedFramework

brp = BRPEnhancedFramework(mode='$MODE')
print('Enhanced BRP Framework Started')
print('==============================')
print(f'Mode: {brp.mode}')
print(f'Modules: {len(brp.modules)}')
print(f'Database: {brp.db_path}')
print('')
print('Ready for operations. Use the framework API to interact.')
print('')
print('Example:')
print('  from integration.brp_enhanced_framework import BRPEnhancedFramework')
print('  brp = BRPEnhancedFramework(mode=\"defensive\")')
print('  result = brp.process_event({\"type\": \"test\", \"data\": \"test event\"})')
"
