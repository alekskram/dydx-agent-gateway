"""Auto-watchdog: monthly data-quality report from the latest leaderboard
run + identity residuals + standing gotchas list. Timer: 1st of month."""
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
BASE = Path(__file__).parent

GOTCHAS = [
    "`netTransfers` in historical-pnl is a per-period flow, NOT cumulative "
    "(the naive interpretation would show a phantom 79.5% drawdown vs the real 11.9%).",
    "`priceChange24H` in perpetualMarkets does not match the candle-derived "
    "price change — compute from candles.",
    "Per-fill PnL in /v4/fills is absent on mainnet — winrate only via the "
    "historical-pnl curve.",
    "The price subticks field is `subticksPerTick` (not subticksPerBase): "
    "price_subticks = price / tickSize * subticksPerTick.",
    "/v4/candles and historical-pnl return newest-first (normalized in the "
    "gateway API layer). /v4/historicalFunding on mainnet — 404.",
]


def generate() -> Path:
    a = sqlite3.connect(BASE / "data" / "analytics.sqlite")
    a.row_factory = sqlite3.Row
    run = a.execute("SELECT * FROM leaderboard_runs ORDER BY id DESC LIMIT 1").fetchone()
    rows = a.execute("SELECT identity_residual, farmer_flag FROM leaderboard_rows WHERE run_id=?",
                     (run["id"],)).fetchall() if run else []
    res = [r["identity_residual"] or 0 for r in rows]
    zero = sum(1 for x in res if x < 0.01)
    reg = sqlite3.connect(BASE / "data" / "registry.sqlite")
    total = reg.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
    usage = a.execute("SELECT COUNT(*) FROM usage").fetchone()[0]
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    md = f"""# dYdX Data-Quality Watchdog — {month}

Period: {run['computed_at'] if run else 'n/a'} · generator: watchdog.py (automatic, timer on the 1st of the month)

## PnL identity check (equity−Δ = Δpnl + ΣnetTransfers)

- Accounts checked: {len(rows)}
- Residual < $0.01: **{zero}/{len(rows)}** · maximum: ${max(res, default=0):.4f}

## Registry and load

- Addresses in the registry (block scanner): {total}
- Tool calls since deployment: {usage}

## Persistent indexer API quirks

""" + "\n".join(f"{i}. {g}" for i, g in enumerate(GOTCHAS, 1)) + "\n"
    out = BASE / "reports" / f"data-quality-{month}.md"
    out.write_text(md, encoding="utf-8")
    return out


if __name__ == "__main__":
    print("written:", generate())
