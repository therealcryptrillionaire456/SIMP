"""
Port utility — finds free ports so agents never conflict.
Usage in any agent:  from tools.port_utils import find_free_port
Usage in bash:       python3 tools/port_utils.py 8769
"""
import socket
import sys

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True

def find_free_port(preferred: int, max_search: int = 50) -> int:
    """Return preferred port if free, else next available port."""
    for port in range(preferred, preferred + max_search):
        if not is_port_in_use(port):
            return port
    raise RuntimeError(f"No free port found in range {preferred}–{preferred + max_search}")

if __name__ == "__main__":
    preferred = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    port = find_free_port(preferred)
    if port != preferred:
        print(f"WARNING: port {preferred} in use, using {port} instead", file=sys.stderr)
    print(port)