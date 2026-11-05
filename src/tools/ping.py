"""Health-check tool for the MCP server."""
from server_instance import server


@server.tool()
def ping() -> str:
    """Health check tool to verify the MCP server responds."""
    return "pong"
