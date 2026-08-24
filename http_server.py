"""Hosted MCP endpoint (streamable HTTP) for the dYdX agent gateway.

Run via systemd (dydx-mcp.service). Binds 127.0.0.1 by default — put a
TLS-terminating reverse proxy (caddy/cloudflare tunnel) in front for public
exposure, plus an auth token, before sharing the URL.
"""
import os

from dydx_mcp.server import build_server

if __name__ == "__main__":
    mcp = build_server()
    mcp.run(transport="http",
            host=os.environ.get("DYDX_MCP_HOST", "127.0.0.1"),
            port=int(os.environ.get("DYDX_MCP_PORT", "8901")))
