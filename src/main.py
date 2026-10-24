"""This module serves as the entry point for the Garmin MCP server."""
import sys

import config
from mcp_server import server

if __name__ == "__main__":
    # Check before the server starts reading stdio: a missing .env must end in a
    # readable hint instead of a process that silently waits for a client.
    try:
        config.require_credentials()
    except ValueError as exc:
        print(f"Cannot start the Garmin MCP server: {exc}", file=sys.stderr)
        sys.exit(1)

    server.run()
