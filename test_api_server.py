"""
Standalone test script for the new Hermes Agent API endpoints.

Starts the API server on port 8643 (different from Desktop's 8642)
so you can test security mode, sandbox, and workdir endpoints
without interrupting the current conversation.

Usage:
    cd "G:/hermes agent/hermes-agent"
    python test_api_server.py

Then open another terminal and test:
    curl http://127.0.0.1:8643/api/security/mode
    curl http://127.0.0.1:8643/api/sandbox
    curl http://127.0.0.1:8643/api/workdir
"""

import asyncio
import sys
import os

# Ensure the project root is on sys.path so imports resolve correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gateway.platforms.api_server import APIServerAdapter
from gateway.config import Platform, PlatformConfig


async def main():
    # Create a minimal config for the test API server
    # Use port 8643 to avoid conflict with Desktop's port 8642
    config = PlatformConfig(
        enabled=True,
        extra={
            "host": "127.0.0.1",
            "port": 8643,
        },
    )

    server = APIServerAdapter(config)
    result = await server.connect()

    if result:
        print("=" * 60)
        print("Test API server is running!")
        print()
        print("  http://127.0.0.1:8643")
        print()
        print("Available test endpoints:")
        print("  GET  /api/security/mode")
        print("  POST /api/security/mode")
        print("  GET  /api/sandbox")
        print("  POST /api/sandbox")
        print("  GET  /api/workdir")
        print("  POST /api/workdir")
        print()
        print("Test commands (open another terminal):")
        print('  curl http://127.0.0.1:8643/api/security/mode')
        print('  curl http://127.0.0.1:8643/api/sandbox')
        print('  curl http://127.0.0.1:8643/api/workdir')
        print()
        print("Press Ctrl+C to stop.")
        print("=" * 60)

        # Keep running until interrupted
        while True:
            await asyncio.sleep(3600)
    else:
        print("Failed to start test API server. Check the logs above.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest API server stopped.")
