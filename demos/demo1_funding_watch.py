"""Demo 1: agent watches funding rates and reports extremes.

Every call goes through the MCP layer (in-process client) — exactly what a
remote agent does over stdio/HTTP. Output is tweet-ready alert text.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from fastmcp import Client  # noqa: E402
from dydx_mcp.server import build_server  # noqa: E402


async def main(threshold_annual: float = 300.0):
    mcp = build_server()
    async with Client(mcp) as c:
        r = await c.call_tool("funding_heatmap", {"limit": 10})
        data = r.data if hasattr(r, "data") else r
        d = data[0] if isinstance(data, list) else data
        print("AGENT FUNDING WATCH — dYdX v4\n" + "=" * 34)
        print(d["summary"], "\n")
        alerts = [x for x in d["top"]
                  if abs(x["funding_pct_annualized"]) >= threshold_annual]
        if not alerts:
            print("nothing extreme right now; watch continues.")
            return
        for a in alerts:
            who = "LONGS PAY SHORTS" if "longs_pay" in a else "SHORTS PAY LONGS"
            print(f"⚠️  {a['ticker']}: funding {a['funding_pct_1h']:+}%/1h "
                  f"(≈{a['funding_pct_annualized']:+}% ann.) — {who} "
                  f"@ ${a['oraclePrice']}")
        print("\n(crowded side is paying; agents can fade or harvest — "
              "not financial advice)")


if __name__ == "__main__":
    asyncio.run(main())
