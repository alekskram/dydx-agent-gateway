"""Demo 3: order with explicit human consent (DRY-RUN by default).

Builds a complete, ATR-based order plan via MCP tools (market_ta +
suggest_stops), prints exactly what WOULD be signed and submitted, and only
proceedes further after an explicit typed confirmation from the human.

Live submission status (2026-08-23): the official v4 client does not install
on Python 3.14 (web3 C-deps lack cp314 wheels; the PyPI wheel misses the
v4_proto package; the GitHub repo has moved). Plan: implement zero-dependency
EIP-712 order signing with `ecdsa` (already installed) + indexer
POST /v4/orders with user API credentials — see PLAN.md "signer" milestone.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from fastmcp import Client  # noqa: E402
from dydx_mcp.server import build_server  # noqa: E402


async def main(ticker="ETH-USD", side="LONG", live=False):
    mcp = build_server()
    async with Client(mcp) as c:
        det = await c.call_tool("market_detail", {"ticker": ticker})
        stops = await c.call_tool("suggest_stops",
                                    {"ticker": ticker, "side": side})
        d = det.data[0] if isinstance(det.data, list) else det.data
        s = stops.data[0] if isinstance(stops.data, list) else stops.data
        size = 100 / float(d["oraclePrice"])  # ~$100 notional for the demo
        order = {
            "market": ticker, "side": "BUY" if side == "LONG" else "SELL",
            "type": "LIMIT", "price": float(d["oraclePrice"]),
            "size": round(size, 3), "timeInForce": "GTT",
            "expiration": "now+3600s",
            "risk": {k: s[k] for k in
                     ("stop_loss", "take_profit", "breakeven_after",
                      "risk_reward")},
        }
        print("ORDER PLAN (built by agent via MCP):\n" + "=" * 36)
        for k, v in order.items():
            print(f"  {k}: {v}")
        print("\n⏸  HUMAN CONSENT REQUIRED before signing/submitting.")
        if not live:
            print("DRY-RUN: nothing was signed or sent.")
            print("Live path (pending signer milestone): "
                  "typed 'YES <confirm phrase>' → EIP-712 signature with the "
                  "user's local key → POST /v4/orders (testnet first).")
            return
        ans = input("Type 'YES' to submit on testnet: ")
        if ans.strip() != "YES":
            print("aborted by human — nothing sent.")
            return
        raise RuntimeError("signer milestone pending — see PLAN.md")


if __name__ == "__main__":
    live = "--live" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(main(*(args or []), live=live))
