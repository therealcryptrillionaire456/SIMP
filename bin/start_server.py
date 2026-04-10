#!/usr/bin/env python3
"""
Start SIMP Protocol Server

Usage:
    python bin/start_server.py [--host HOST] [--port PORT] [--debug]
"""

import sys
import argparse
import logging
import os

# Add parent directory to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simp.server.http_server import create_http_server


def main():
    """Start SIMP HTTP server"""
    parser = argparse.ArgumentParser(
        description="Start SIMP Protocol Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start on default host/port (127.0.0.1:5555)
  python bin/start_server.py

  # Start on custom port
  python bin/start_server.py --port 8080

  # Start with debug logging
  python bin/start_server.py --debug

  # Start on all interfaces (WARNING: not recommended for production)
  python bin/start_server.py --host 0.0.0.0
        """
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5555,
        help="Port to bind to (default: 5555)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    print("""
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║              SIMP Protocol Server v0.1                         ║
║                                                                ║
║          Standardized Inter-agent Message Protocol             ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
    """)

    print(f"📡 Starting SIMP Server...")
    print(f"   Host: {args.host}")
    print(f"   Port: {args.port}")
    print(f"   Debug: {args.debug}")
    print()

    # Create server
    server = create_http_server(
        host=args.host,
        port=args.port,
        debug=args.debug
    )

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger = logging.getLogger("SIMP")

    # BRP startup check
    try:
        from simp.security.brp_bridge import BRPBridge
        _brp = BRPBridge()
        print(f"[BRP] Bill Russell Protocol initialized in shadow mode (data: {_brp.data_dir})")
        del _brp
    except Exception as brp_err:
        print(f"[BRP] Bill Russell Protocol not available (import failed: {brp_err})")

    print("\n🎯 Available Endpoints:")
    print(f"   GET    http://{args.host}:{args.port}/health")
    print(f"   GET    http://{args.host}:{args.port}/status")
    print(f"   POST   http://{args.host}:{args.port}/agents/register")
    print(f"   GET    http://{args.host}:{args.port}/agents")
    print(f"   POST   http://{args.host}:{args.port}/intents/route")
    print(f"   GET    http://{args.host}:{args.port}/stats")

    print("\n📚 Documentation:")
    print("   - See SIMP_SERVER.md for detailed API documentation")
    print("   - Run: python bin/test_protocol.py to validate")
    print("   - Run: python bin/demo_pentagram.py to see live demo")

    print("\n✅ Server ready. Press Ctrl+C to stop.\n")

    try:
        server.run(host=args.host, port=args.port)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
