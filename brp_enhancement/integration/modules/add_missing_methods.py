#!/usr/bin/env python3
"""
Add missing methods to modules for compatibility.
"""

import sys
import os
from pathlib import Path

def add_methods_to_file(file_path: Path, methods_code: str):
    """Add methods to a module file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the last method before the end of the class
    # We'll add our methods before the final class closing
    lines = content.split('\n')
    new_lines = []
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        # Check if this is a line with only whitespace and a class ending
        if line.strip() == '}' or line.strip() == '})' or line.strip().startswith('# Note:'):
            # Insert our methods before this line
            new_lines.pop()  # Remove the line we just added
            new_lines.append('\n' + methods_code + '\n')
            new_lines.append(line)
            # Add the rest of the lines
            new_lines.extend(lines[i+1:])
            break
    
    with open(file_path, 'w') as f:
        f.write('\n'.join(new_lines))

# Common methods that all modules need
common_methods = '''
    def get_status(self) -> dict:
        """Get module status."""
        return {
            'name': self.name,
            'repository': self.repository,
            'type': self.module_type,
            'initialized': self.initialized,
            'available': self.available,
            'capabilities_count': len(self.capabilities),
            'capabilities': self.capabilities
        }
    
    # Stub methods for abstract methods that might be called
    def monitor(self, data: dict) -> dict:
        """Monitor data for threats."""
        return {'error': 'Method not implemented in this module'}
    
    def analyze_threat(self, threat_data: dict) -> dict:
        """Analyze threat data."""
        return {'error': 'Method not implemented in this module'}
    
    def defend(self, threat: dict) -> dict:
        """Execute defensive action against threat."""
        return {'error': 'Method not implemented in this module'}
    
    def scan(self, target: str, parameters: dict) -> dict:
        """Scan target for vulnerabilities."""
        return {'error': 'Method not implemented in this module'}
    
    def exploit(self, vulnerability: dict) -> dict:
        """Exploit a vulnerability."""
        return {'error': 'Method not implemented in this module'}
    
    def execute_attack(self, attack_plan: dict) -> dict:
        """Execute attack plan."""
        return {'error': 'Method not implemented in this module'}
    
    def gather_intelligence(self, query: dict) -> dict:
        """Gather intelligence based on query."""
        return {'error': 'Method not implemented in this module'}
    
    def analyze_patterns(self, data: list) -> dict:
        """Analyze patterns in data."""
        return {'error': 'Method not implemented in this module'}
    
    def plan_response(self, threat: dict) -> dict:
        """Plan response to threat."""
        return {'error': 'Method not implemented in this module'}
'''

# Add to hexstrike module
hexstrike_path = Path(__file__).parent / "hexstrike_module.py"
add_methods_to_file(hexstrike_path, common_methods)
print("Added methods to hexstrike_module.py")

# Add to pentagi module
pentagi_path = Path(__file__).parent / "pentagi_module.py"

# Pentagi needs specific stubs for methods that are called
pentagi_specific_methods = '''
    def get_status(self) -> dict:
        """Get module status."""
        return {
            'name': self.name,
            'repository': self.repository,
            'type': self.module_type,
            'initialized': self.initialized,
            'available': self.available,
            'capabilities_count': len(self.capabilities),
            'capabilities': self.capabilities,
            'knowledge_graph_available': self.knowledge_graph_available
        }
    
    # Stub for _maintain_access which was called in tests
    def _maintain_access(self, parameters: dict) -> dict:
        """Maintain access after exploitation."""
        return {
            'maintain_access': 'simulated',
            'status': 'Method stub - actual implementation would maintain persistence'
        }
    
    def _lateral_movement(self, parameters: dict) -> dict:
        """Perform lateral movement."""
        return {
            'lateral_movement': 'simulated',
            'status': 'Method stub - actual implementation would move laterally'
        }
    
    def _data_exfiltration(self, parameters: dict) -> dict:
        """Perform data exfiltration."""
        return {
            'data_exfiltration': 'simulated',
            'status': 'Method stub - actual implementation would exfiltrate data'
        }
    
    # Basic implementations for abstract methods
    def scan(self, target: str, parameters: dict) -> dict:
        """Scan target for vulnerabilities."""
        return self.execute('scan_target', {'target': target, **parameters})
    
    def exploit(self, vulnerability: dict) -> dict:
        """Exploit a vulnerability."""
        return self.execute('exploit_vulnerability', vulnerability)
    
    def execute_attack(self, attack_plan: dict) -> dict:
        """Execute attack plan."""
        return {'status': 'attack_execution_simulated', 'plan': attack_plan}
    
    def gather_intelligence(self, query: dict) -> dict:
        """Gather intelligence based on query."""
        return self.execute('query_knowledge', query)
    
    def analyze_patterns(self, data: list) -> dict:
        """Analyze patterns in data."""
        return self.execute('correlate_findings', {'findings': data})
    
    def plan_response(self, threat: dict) -> dict:
        """Plan response to threat."""
        return self.execute('plan_defenses', {'threats': [threat]})
'''

add_methods_to_file(pentagi_path, pentagi_specific_methods)
print("Added methods to pentagi_module.py")

# Add to strix module
strix_path = Path(__file__).parent / "strix_module.py"
add_methods_to_file(strix_path, common_methods)
print("Added methods to strix_module.py")

print("\nMissing methods added to modules.")