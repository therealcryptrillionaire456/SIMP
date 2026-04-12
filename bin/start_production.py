#!/usr/bin/env python3
"""Production launcher for SIMP broker HTTP server.

Usage:
    python3 bin/start_production.py [--workers 4] [--port 8080] [--host 0.0.0.0]

For development, continue using bin/start_server.py which runs Flask dev server.
"""

import argparse
import os
import sys
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    parser = argparse.ArgumentParser(description="SIMP Production Server")
    parser.add_argument("--workers", type=int, default=4, help="Number of gunicorn workers")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SIMP_HTTP_PORT", 8080)), help="Port")
    parser.add_argument("--host", default=os.environ.get("SIMP_HTTP_HOST", "127.0.0.1"), help="Host")
    parser.add_argument("--timeout", type=int, default=120, help="Worker timeout in seconds")
    args = parser.parse_args()

    print(f"Starting SIMP production server on {args.host}:{args.port} with {args.workers} workers...")

    # Use gunicorn with the Flask app
    cmd = [
        sys.executable, "-m", "gunicorn",
        "--workers", str(args.workers),
        "--bind", f"{args.host}:{args.port}",
        "--timeout", str(args.timeout),
        "--access-logfile", "-",
        "--error-logfile", "-",
        "--log-level", os.environ.get("SIMP_LOG_LEVEL", "info").lower(),
        "simp.server.http_server:create_app()"
    ]

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print("ERROR: gunicorn not found. Install with: pip install gunicorn")
        print("Falling back to Flask dev server...")
        from simp.server.http_server import SimpHttpServer
        server = SimpHttpServer()
        server.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
