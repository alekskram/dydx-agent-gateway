"""Autonomous mini-agent example: connects to the dYdX Agent Gateway over
streamable HTTP and runs a full workflow with zero setup:

    latest events -> funding heatmap -> top leaderboard -> daily digest

Run:  python examples/python-agent.py  [gateway_url]
"""
import asyncio
import sys

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8901/mcp"


def first(r):
    """fastmcp may wrap list results; normalize to the actual payload."""
    d = r.data
    if isinstance(d, list) and len(d) == 1 and isinstance(d[0], (list, dict)):
        return d[0]
    return d


async def main():
    async with Client(StreamableHttpTransport(url=URL)) as c:
        print(f"connected to {URL}; tools: {len(await c.list_tools())}")

        events = first(await c.call_tool("latest_events", {"limit": 5}))
        print("\n== latest detector events ==")
        if isinstance(events, list) and events:
            for e in events:
                print(f"  {e['kind']:20} {e['subject']:12} {str(e['payload'])[:80]}")
        else:
            print("  (all quiet)")

        heat = first(await c.call_tool(
            "funding_heatmap", {"limit": 5, "min_oi_usd": 100000}))
        print("\n== funding heatmap (OI >= $100k) ==")
        print(" ", heat["summary"])
        for r in heat["top"][:3]:
            side = "LONGS PAY" if "longs_pay" in r else "SHORTS PAY"
            print(f"  {r['ticker']:10} {r['funding_pct_1h']:+}%/1h "
                  f"(ann {r['funding_pct_annualized']:+}%) OI ${r['oi_usd']:,.0f} {side}")

        lb = first(await c.call_tool("leaderboard", {"limit": 3}))
        print("\n== verified leaderboard (~42d window) ==")
        for r in lb["top"]:
            print(f"  {r['address'][:12]}… winPnL ${r['pnl_window']:>+10,.0f} | "
                  f"eq ${r['equity']:>10,.0f} | wr {r['day_winrate']}% | "
                  f"farmer={'yes' if r['farmer_flag'] else 'no'}")

        print("\n(digest ready — the same set the agent would push to Telegram/webhook)")


if __name__ == "__main__":
    asyncio.run(main())
