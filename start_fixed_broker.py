#!/usr/bin/env python3.10
"""Start the fixed SIMP broker with heartbeat endpoint fix."""

import sys
import os

# Clear module cache to ensure we load fresh code
for module in list(sys.modules.keys()):
    if module.startswith('simp.'):
        del sys.modules[module]

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run
from simp.server.http_server import create_http_server

if __name__ == "__main__":
    server = create_http_server(host="127.0.0.1", port=5555, debug=False)
    server.run(host="127.0.0.1", port=5555)