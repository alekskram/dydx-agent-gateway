"""Track C: LIVE integration (real indexer API + local services).
Marker: online — run explicitly:  pytest -m online
"""
import asyncio

import pytest

pytestmark = pytest.mark.online

MM = "dydx1m9hg73dtn5ku8ulmj8rjmdqh0hk7uuhawc69cn"  # known active trader
URL = "http://127.0.0.1:8901/mcp"


def _run(coro):
    return asyncio.run(coro)


def _first(r):
    d = r.data
    if isinstance(d, list) and len(d) == 1 and isinstance(d[0], (list, dict)):
        return d[0]
    return d


def test_http_all_tools_live():
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    async def go():
        async with Client(StreamableHttpTransport(url=URL)) as c:
            tools = await c.list_tools()
            names = {t.name for t in tools}
            assert len(tools) == 21
            r = await c.call_tool("market_digest", {})
            d = _first(r)
            assert "leaderboard_top" in d and d["events"] is not None
            p = _first(await c.call_tool("trader_pnl_stats", {"address": MM}))
            assert p["equity_now"] >= 0
            assert 0 <= p["day_winrate_pct"] <= 100
            assert p["identity_max_residual_usd"] < 1.0
    _run(go())


def test_bad_ticker_is_tool_error_not_protocol():
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport
    from fastmcp.exceptions import ToolError

    async def go():
        async with Client(StreamableHttpTransport(url=URL)) as c:
            with pytest.raises(ToolError):  # isError result, not protocol error
                await c.call_tool("market_detail", {"ticker": "NOPE-USD"})
    _run(go())


def test_freshness_registry_cursor_lag():
    import sqlite3
    from pathlib import Path
    from dydx_mcp import api
    prod = Path("/root/ventures/dydx-grant/agent-gateway/data/registry.sqlite")
    h = int(api.height()["height"])
    with sqlite3.connect(prod) as c:
        cur = int(c.execute("SELECT v FROM meta WHERE k='cursor'").fetchone()[0])
    assert 0 <= h - cur < 120  # scanner follows the tip (1s blocks)


def test_live_pagination_monotonic_no_dupes():
    from dydx_mcp import api
    rows = api.historical_pnl(MM, 0, 2500)
    assert len(rows) >= 2000
    ts = [r["createdAt"] for r in rows]  # newest-first
    assert len(set(ts)) == len(ts)       # no duplicates
    assert ts == sorted(ts, reverse=True)  # strictly monotonic newest-first


def test_stdio_transport_live():
    import os
    import sys
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    async def go():
        tr = StdioTransport(
            sys.executable, args=["-m", "dydx_mcp.server"],
            env={**os.environ, "PYTHONPATH": os.getcwd()})
        async with Client(tr) as c:
            tools = await c.list_tools()
            assert len(tools) == 21
    _run(go())
