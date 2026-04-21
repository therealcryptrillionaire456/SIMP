#!/usr/bin/env python3
"""
Simple fix for module inheritance issues.
Updates all modules to use proper inheritance.
"""

import sys
import os
from pathlib import Path

# Update hexstrike_module
hexstrike_path = Path(__file__).parent / "hexstrike_module.py"
with open(hexstrike_path, 'r') as f:
    content = f.read()

# Replace the class definition
content = content.replace(
    'class HexstrikeModule(DefensiveModule, OffensiveModule):',
    'class HexstrikeModule:'
)

# Replace __init__ method
import re
content = re.sub(
    r'def __init__\(self\):\s*# Initialize as both defensive and offensive module\s*DefensiveModule\.__init__\(self, "hexstrike", "hexstrike-ai"\)\s*OffensiveModule\.__init__\(self, "hexstrike", "hexstrike-ai"\)\s*self\.module_type = \'hybrid\'',
    '''def __init__(self):
        # Initialize as hybrid module
        self.name = "hexstrike"
        self.repository = "hexstrike-ai"
        self.module_type = 'hybrid'
        self.initialized = False
        self.available = False
        self.capabilities = []''',
    content,
    flags=re.DOTALL
)

with open(hexstrike_path, 'w') as f:
    f.write(content)

print("Fixed hexstrike_module.py")

# Update pentagi_module
pentagi_path = Path(__file__).parent / "pentagi_module.py"
with open(pentagi_path, 'r') as f:
    content = f.read()

content = content.replace(
    'class PentagiModule(OffensiveModule, IntelligenceModule):',
    'class PentagiModule:'
)

content = re.sub(
    r'def __init__\(self\):\s*# Initialize as both offensive and intelligence module\s*OffensiveModule\.__init__\(self, "pentagi", "pentagi"\)\s*IntelligenceModule\.__init__\(self, "pentagi", "pentagi"\)\s*self\.module_type = \'hybrid\'',
    '''def __init__(self):
        # Initialize as hybrid module
        self.name = "pentagi"
        self.repository = "pentagi"
        self.module_type = 'hybrid'
        self.initialized = False
        self.available = False
        self.capabilities = []''',
    content,
    flags=re.DOTALL
)

with open(pentagi_path, 'w') as f:
    f.write(content)

print("Fixed pentagi_module.py")

# Update strix_module
strix_path = Path(__file__).parent / "strix_module.py"
with open(strix_path, 'r') as f:
    content = f.read()

content = content.replace(
    'class StrixModule(DefensiveModule, IntelligenceModule):',
    'class StrixModule:'
)

content = re.sub(
    r'def __init__\(self\):\s*# Initialize as both defensive and intelligence module\s*DefensiveModule\.__init__\(self, "strix", "strix"\)\s*IntelligenceModule\.__init__\(self, "strix", "strix"\)\s*self\.module_type = \'hybrid\'',
    '''def __init__(self):
        # Initialize as hybrid module
        self.name = "strix"
        self.repository = "strix"
        self.module_type = 'hybrid'
        self.initialized = False
        self.available = False
        self.capabilities = []''',
    content,
    flags=re.DOTALL
)

with open(strix_path, 'w') as f:
    f.write(content)

print("Fixed strix_module.py")

print("\nAll modules fixed. Now they should initialize properly.")