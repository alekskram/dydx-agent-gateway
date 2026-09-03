"""TA extensions (v0.3.0): pure math for the analyst pack — MACD, VWAP,
realized vol, CVD, correlation, sortino-like. Stdlib only; candles/trades
shapes per dydx_mcp.api."""
import math
import statistics


def macd(closes: list[float], fast: int = 12, slow: int = 26,
         signal: int = 9) -> dict | None:
    """Classic MACD over close (oldest -> newest).

    EMA per server._ema convention: seeded with the first value,
    k = 2/(n+1). Returns the last {macd, signal, hist}
    (hist = macd - signal) or None when len(closes) < slow + signal.
    """
    if len(closes) < slow + signal:
        return None

    def _ema(xs, n):
        k, e = 2 / (n + 1), xs[0]
        for x in xs[1:]:
            e = x * k + e * (1 - k)
        return e

    macd_line = [_ema(closes[:i], fast) - _ema(closes[:i], slow)
                 for i in range(slow, len(closes) + 1)]
    sig = _ema(macd_line, signal)
    m = macd_line[-1]
    return {"macd": m, "signal": sig, "hist": m - sig}


def vwap(candles: list[dict]) -> float | None:
    """VWAP over the candle window: sum(typical * usdVolume) / sum(usdVolume),
    typical = (high+low+close)/3. None when total volume <= 0."""
    pv = v = 0.0
    for c in candles:
        typical = (float(c["high"]) + float(c["low"]) + float(c["close"])) / 3
        vol = float(c["usdVolume"])
        pv += typical * vol
        v += vol
    return pv / v if v > 0 else None


def realized_vol(closes: list[float], periods_per_year: int) -> float | None:
    """Annualized realized vol: population std of log returns ln(p_t/p_{t-1})
    (var = sum((x-mean)^2)/n, like the rest of the project) scaled by
    sqrt(periods_per_year). None when < 2 closes or any close <= 0."""
    if len(closes) < 2 or any(c <= 0 for c in closes):
        return None
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    return statistics.pstdev(rets) * math.sqrt(periods_per_year)


def cvd(trades: list[dict]) -> dict:
    """Cumulative volume delta from indexer trades (newest-first): reversed
    to oldest->newest, BUY adds +size, SELL subtracts. Unknown side raises
    ValueError. Returns {series, final, buy_volume, sell_volume}."""
    series, cum = [], 0.0
    buy = sell = 0.0
    for t in reversed(trades):
        size = float(t["size"])
        side = t["side"]
        if side == "BUY":
            cum += size
            buy += size
        elif side == "SELL":
            cum -= size
            sell += size
        else:
            raise ValueError(f"unknown trade side: {side!r}")
        series.append(cum)
    return {"series": series, "final": cum,
            "buy_volume": buy, "sell_volume": sell}


def pearson_log_returns(closes_a: list[float],
                        closes_b: list[float]) -> dict | None:
    """Pearson r and beta of log returns (both series oldest->newest,
    equal length, n >= 3). Different lengths -> ValueError; n < 3, non-
    positive prices, or zero std on either side -> None. Population
    moments; beta(a|b) = cov(ra, rb)/var(rb) — sensitivity of a to b."""
    if len(closes_a) != len(closes_b):
        raise ValueError("series must have equal length")
    n = len(closes_a)
    if n < 3 or any(c <= 0 for c in closes_a) or any(c <= 0 for c in closes_b):
        return None
    ra = [math.log(b / a) for a, b in zip(closes_a, closes_a[1:])]
    rb = [math.log(b / a) for a, b in zip(closes_b, closes_b[1:])]
    sa, sb = statistics.pstdev(ra), statistics.pstdev(rb)
    if sa == 0 or sb == 0:
        return None
    r = statistics.correlation(ra, rb)
    return {"r": r, "beta": r * sa / sb}


def sortino_like(daily_pnls: list[float]) -> float | None:
    """Sortino-like ratio (zero risk-free, crypto convention): mean /
    downside_dev, downside_dev = sqrt(mean(min(x, 0)^2)) over deviations
    from zero. None when empty or downside_dev == 0 (no losses)."""
    if not daily_pnls:
        return None
    dd = math.sqrt(sum(min(x, 0.0) ** 2 for x in daily_pnls) / len(daily_pnls))
    if dd == 0:
        return None
    return (sum(daily_pnls) / len(daily_pnls)) / dd


def periods_per_year(resolution: str) -> int:
    """Candles per year for a resolution string; unknown -> ValueError."""
    table = {"1MIN": 525600, "5MIN": 105120, "15MIN": 35040,
             "30MIN": 17520, "1HOUR": 8760, "4HOURS": 2190, "1DAY": 365}
    try:
        return table[resolution]
    except KeyError:
        raise ValueError(f"unknown resolution: {resolution!r}") from None
