"""Leaderboard batch: registry -> equity probe -> PnL stats -> analytics db.

Run on demand or via timer. Each run also records equity snapshots
(equity_jump detector source). Farmer flag = heuristic v0:
maker>=90% & avg fill <=$300 & >=50 fills in sample (rewards-farming pattern).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dydx_mcp import api, registry, analytics
from dydx_mcp.pnl_engine import pnl_stats

MIN_EQUITY = 50.0
CANDIDATES = 40


def run():
    cands = registry.recent(CANDIDATES, max_hits=100)
    seen = []
    for x in cands:
        if x["address"] not in [s for s in seen]:
            seen.append(x["address"])
    con = analytics.con()
    run_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    funded, rows = 0, []
    for addr in seen:
        try:
            acct = api.account(addr)
            eq = max((float(s.get("equity", 0) or 0)
                      for s in acct.get("subaccounts", [])), default=0.0)
        except Exception:  # noqa: BLE001
            continue
        # equity_jump event vs previous snapshot
        prev = con.execute("SELECT equity FROM equity_snapshots WHERE address=? "
                           "ORDER BY ts DESC LIMIT 1", (addr,)).fetchone()
        con.execute("INSERT INTO equity_snapshots VALUES(?,?,?)", (addr, run_ts, eq))
        if prev and prev["equity"] > 500 and abs(eq - prev["equity"]) / prev["equity"] > 0.25:
            analytics.add_event("equity_jump", addr, {
                "from": round(prev["equity"], 2), "to": round(eq, 2),
                "pct": round((eq / prev["equity"] - 1) * 100, 1)}, con)
        if eq < MIN_EQUITY:
            continue
        funded += 1
        stats = pnl_stats(addr)
        fills = api.fills(addr, 0, 100)
        maker = sum(1 for f in fills if f.get("liquidity") == "MAKER")
        vol = sum(float(f.get("size", 0) or 0) * float(f.get("price", 0) or 0) for f in fills)
        avg_fill = vol / len(fills) if fills else 0
        farmer = int(maker >= 90 and avg_fill <= 300 and len(fills) >= 50)
        rows.append((addr, round(eq, 2), stats.get("totalPnl_now"),
                     stats.get("totalPnl_delta_window"), stats.get("day_winrate_pct"),
                     stats.get("max_drawdown_pct"),
                     round(maker / len(fills) * 100, 1) if fills else None,
                     round(avg_fill, 2), farmer,
                     stats.get("identity_max_residual_usd")))
        print(f"  {addr[:14]}… eq=${eq:,.0f} pnlWin={stats.get('totalPnl_delta_window')} "
              f"wr={stats.get('day_winrate_pct')}% farmer={farmer}", flush=True)
    cur = con.execute("INSERT INTO leaderboard_runs VALUES(NULL,?,?,?)",
                      (run_ts, len(seen), funded))
    run_id = cur.lastrowid
    con.executemany("INSERT INTO leaderboard_rows VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    [(run_id, *r) for r in rows])
    con.commit()
    con.close()
    print(f"done: {len(seen)} candidates, {funded} funded, run #{run_id}")
    return run_id, rows


if __name__ == "__main__":
    run()
