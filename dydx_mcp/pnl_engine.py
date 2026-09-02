"""PnL engine: daily PnL, drawdown, day-winrate + data-accuracy reconciliation.

Feeds on the indexer historical-pnl series (equity, totalPnl, netTransfers).
Identity used for reconciliation (and for deposit-adjusted curves):
    equity(t) ≈ equity(0) + netTransfers(t) + totalPnl(t)
Residuals of this identity are the "phantom PnL" detector — the class of bug
that made previous dYdX dashboards show multi-million-dollar fantasy profits.
"""
from . import api

# A3 (v0.2.5): max_drawdown_pct is peak-relative and misleads when the
# deposit-adjusted curve's running peak at the worst drawdown is near zero
# (can exceed 100%). Thresholds per Researcher (MEC-44): peak < $1 OR
# peak < 1% of current equity -> dd_pct_unreliable: true; the USD depth
# (max_drawdown_usd) is always the trustworthy figure.
DD_UNRELIABLE_PEAK_USD = 1.0
DD_UNRELIABLE_EQUITY_FRAC = 0.01


def compute(rows: list[dict]) -> dict:
    """Pure stats from historical-pnl rows (newest-first); testable offline."""
    if not rows:
        return {}
    rows = list(reversed(rows))  # oldest -> newest

    eq0 = float(rows[0].get("equity") or 0)
    points = []
    for r in rows:
        t = (r.get("createdAt") or "")[:19]
        points.append({
            "t": t, "equity": float(r.get("equity") or 0),
            "pnl": float(r.get("totalPnl") or 0),
            "net_tr": float(r.get("netTransfers") or 0),
        })

    # netTransfers is per-bucket flow (not cumulative) -> running sum
    cum = 0.0
    cum_ntr = [0.0]
    for p in points[1:]:
        cum += p["net_tr"]
        cum_ntr.append(cum)

    # reconciliation residuals: in-sample deltas of the identity
    # (equity_t - equity_0) = (pnl_t - pnl_0) + cumNetTransfers_t
    pnl0 = points[0]["pnl"]
    residuals = [abs((p["equity"] - eq0) - (p["pnl"] - pnl0) - cum_ntr[i])
                 for i, p in enumerate(points)]
    max_resid = max(residuals)
    window_transfers = round(cum, 2)

    # daily pnl (change of totalPnl between consecutive points, by UTC day)
    daily = {}
    for prev, cur in zip(points, points[1:]):
        day = cur["t"][:10]
        daily[day] = daily.get(day, 0.0) + (cur["pnl"] - prev["pnl"])
    days = sorted(daily.items())
    wins = sum(1 for _, v in days if v > 0)
    losses = sum(1 for _, v in days if v < 0)
    vals = [v for _, v in days]
    mean = sum(vals) / len(vals) if vals else 0.0
    var = sum((v - mean) ** 2 for v in vals) / len(vals) if vals else 0.0
    sharpe_like = mean / (var ** 0.5) if var > 0 else None

    # max drawdown on deposit-adjusted equity (equity - cumNetTransfers)
    peak, mdd = None, 0.0
    dd_peak, dd_usd = 0.0, 0.0        # running peak / depth at worst dd
    for p, cn in zip(points, cum_ntr):
        perf = p["equity"] - cn
        peak = perf if peak is None else max(peak, perf)
        if peak:
            dd = (peak - perf) / peak
            if dd > mdd:
                mdd, dd_peak, dd_usd = dd, peak, peak - perf

    best = max(days, key=lambda x: x[1]) if days else None
    worst = min(days, key=lambda x: x[1]) if days else None
    return {
        "points": len(points), "days": len(days),
        "window": f"{points[0]['t'][:10]} → {points[-1]['t'][:10]}",
        "totalPnl_now": round(points[-1]["pnl"], 2),
        "totalPnl_delta_window": round(points[-1]["pnl"] - points[0]["pnl"], 2),
        "equity_now": round(points[-1]["equity"], 2),
        "netTransfers_window": window_transfers,
        "day_winrate_pct": round(wins / len(days) * 100, 1) if days else None,
        "win_days": wins, "loss_days": losses,
        "avg_daily_pnl": round(mean, 2),
        "sharpe_like_daily": round(sharpe_like, 2) if sharpe_like else None,
        "max_drawdown_pct": round(mdd * 100, 2),
        "max_drawdown_usd": round(dd_usd, 2),
        "dd_pct_unreliable": bool(
            mdd > 1.0
            or dd_peak < DD_UNRELIABLE_PEAK_USD
            or dd_peak < DD_UNRELIABLE_EQUITY_FRAC * points[-1]["equity"]),
        "best_day": best, "worst_day": worst,
        "identity_max_residual_usd": round(max_resid, 4),
        "summary": ((f"{len(days)} days, winrate {wins}/{len(days)} "
                     f"({wins / len(days) * 100:.0f}%), avg ${mean:,.0f}/day, "
                     f"maxDD {mdd * 100:.1f}%, identity residual ≤ "
                     f"${max_resid:.2f}") if days else
                    "0 days (single point), no daily stats"),
    }


def pnl_stats(address: str, subaccount: int = 0, limit: int = 1000) -> dict:
    rows = api.historical_pnl(address, subaccount, limit)
    if not rows:
        return {"address": address, "error": "no pnl history"}
    return {"address": address, "subaccount": subaccount,
            **compute(rows)}
