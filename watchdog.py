"""Auto-watchdog: monthly data-quality report from the latest leaderboard
run + identity residuals + standing gotchas list. Timer: 1st of month."""
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
BASE = Path(__file__).parent

GOTCHAS = [
    "`netTransfers` в historical-pnl — поток за период, НЕ кумулятив "
    "(наивная интерпретация дала бы фантомную просадку 79.5% vs реальные 11.9%).",
    "`priceChange24H` в perpetualMarkets не соответствует изменению цены "
    "по свечам — считать по свечам.",
    "Per-fill PnL в /v4/fills на мейннете отсутствует — винрейт только "
    "через кривую historical-pnl.",
    "Поле субтиков цены — `subticksPerTick` (не subticksPerBase): "
    "price_subticks = price / tickSize * subticksPerTick.",
    "/v4/candles и historical-pnl возвращают newest-first (нормализовано "
    "в api-слое шлюза). /v4/historicalFunding на мейннете — 404.",
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

Период: {run['computed_at'] if run else 'n/a'} · генератор: watchdog.py (авто, таймер 1-го числа)

## Сверка тождества PnL (equity−Δ = Δpnl + ΣnetTransfers)

- Проверено аккаунтов: {len(rows)}
- Остаток < $0.01: **{zero}/{len(rows)}** · максимум: ${max(res, default=0):.4f}

## Реестр и нагрузка

- Адресов в реестре (блочный сканер): {total}
- Вызовов инструментов с деплоя: {usage}

## Постоянные особенности indexer API

""" + "\n".join(f"{i}. {g}" for i, g in enumerate(GOTCHAS, 1)) + "\n"
    out = BASE / "reports" / f"data-quality-{month}.md"
    out.write_text(md, encoding="utf-8")
    return out


if __name__ == "__main__":
    print("written:", generate())
