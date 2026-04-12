"""
Main entry point for the Scrapling Query Tool.
"""

import sys
from .server import run_server


def main():
    """Main entry point."""
    try:
        run_server()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()