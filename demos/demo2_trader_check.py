"""Demo 2: due-diligence on a trader before copying/following them.

Takes an address (default: a real active trader from our block-registry),
calls trader_profile + fills_review through the MCP layer, prints an EN
due-diligence card an agent (or human) can act on.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from fastmcp import Client  # noqa: E402
from dydx_mcp.server import build_server  # noqa: E402

DEFAULT_ADDR = "dydx1m9hg73dtn5ku8ulmj8rjmdqh0hk7uuhawc69cn"


async def main(addr: str = None):
    addr = addr or DEFAULT_ADDR
    mcp = build_server()
    async with Client(mcp) as c:
        prof = await c.call_tool("trader_profile", {"address": addr})
        fills = await c.call_tool("fills_review", {"address": addr})
        p = prof.data[0] if isinstance(prof.data, list) else prof.data
        f = fills.data[0] if isinstance(fills.data, list) else fills.data
        print(f"TRADER CHECK — {addr}\n" + "=" * 48)
        print(f"equity:        ${p['equity_now']:,}")
        print(f"total PnL:     ${p['totalPnl_now']:,}")
        print(f"PnL (window):  ${p['totalPnl_delta_window']:,}"
              f"  [{p['window_start'][:10]} → {p['window_end'][:10]}]")
        print(f"open positions: {len(p['open_positions'])}")
        for pos in p["open_positions"][:4]:
            print(f"   {pos['side']:5} {pos['market']:10} "
                  f"size {pos['size']:>10} @ {pos['entry']} "
                  f"uPnL {pos['unrealizedPnl']}")
        print(f"\nexecution: {f['summary']}")
        print("\nAGENT VERDICT FORMAT: profile ->", p["summary"])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
