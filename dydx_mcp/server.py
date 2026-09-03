"""dYdX Agent Gateway — MCP server.

Analytics-only by design: lets any AI agent read dYdX v4 market data &
trader analytics. All tools are read-only and keyless. The zero-heavy-dep
EIP-712 signer (dydx_mcp/signer.py) remains an unwired offline-tested
library — it is not exposed as an MCP tool.
"""
import math

from . import api
from . import ta_ext
from typing import Literal


def _fmt(x, step=2):
    try:
        return float(f"{float(x):.{step}f}")
    except (TypeError, ValueError):
        return x


def _fmt_price(x, step=2):
    """Adaptive price formatting (A2, v0.2.5): never fewer decimals than the
    legacy `step`, but at least 6 significant digits for sub-cent assets, so
    that level geometry (SL < entry < TP) and ATR multipliers remain readable
    from the printed fields alone (e.g. DOGE entry 0.08148, not 0.08). The
    digit count comes from the order of magnitude (log10), which is immune
    to binary-float noise like 0.08078000000000001."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return x
    if x == 0 or not math.isfinite(x):
        return _fmt(x, step)
    msd = math.floor(math.log10(abs(x)))   # power of ten of the leading digit
    return _fmt(x, max(step, 5 - msd))     # 6 significant digits -> decimals


# ---------------------------------------------------------------- public data


def _require_ticker(ticker: str) -> None:
    """Validate a ticker against the live markets list (60s-cached).

    Raises ValueError (-> MCP isError) with an actionable message on
    unknown, delisted or wrongly formatted tickers, pointing the caller
    to list_markets for the valid set (format: ETH-USD)."""
    if ticker in api.markets():
        return
    sample = ", ".join(sorted(api.markets())[:5])
    raise ValueError(
        f"unknown or delisted ticker {ticker!r} (format: 'ETH-USD'). "
        f"Call list_markets for the full set; examples: {sample}")


def list_markets(
    limit: int = 20,
    sort: Literal["volume", "oi"] = "volume",
    offset: int = 0,
) -> dict:
    """All dYdX v4 perpetual markets: oracle price, 24h volume, open interest,
    next funding rate. Sorted by 24h USD volume by default (or 'oi').
    Each row: ticker, oraclePrice, volume24h_USD, openInterest_USD
    (size x oracle price) and nextFundingRate_pct_1h (pct per hour).
    Returns {"count_total", "count", "offset", "has_more", "next_offset",
    "markets", "summary"}; only ACTIVE markets — delisted/settled ones are
    excluded. Page with offset when has_more is true.
    Example: list_markets(limit=20, sort="volume")"""
    ms = api.markets()
    rows = []
    for t, m in ms.items():
        rows.append({
            "ticker": t,
            "oraclePrice": _fmt(m.get("oraclePrice")),
            "volume24h_USD": _fmt(float(m.get("volume24H", 0) or 0), 0),
            "openInterest_USD": _fmt(float(m.get("openInterest", 0) or 0)
                                     * float(m.get("oraclePrice") or 0), 0),
            "nextFundingRate_pct_1h": _fmt(float(m.get("nextFundingRate", 0) or 0) * 100, 5),
        })
    key = "volume24h_USD" if sort == "volume" else "openInterest_USD"
    rows.sort(key=lambda r: -(r[key] or 0))
    top = rows[max(offset, 0):max(offset, 0) + limit]
    has_more = offset + limit < len(rows)
    return {
        "count_total": len(rows),
        "count": len(top),
        "offset": offset,
        "has_more": has_more,
        "next_offset": offset + limit if has_more else None,
        "markets": top,
        "summary": f"{len(rows)} active markets; top by {sort}: "
                   + ", ".join(r["ticker"] for r in top[:5]),
    }


def market_detail(ticker: str) -> dict:
    """One perpetual market in depth: prices, 24h stats computed from candles
    (the raw API priceChange field is unreliable), OI, funding.
    Returns oraclePrice, openInterest, nextFundingRate_pct_1h (pct/hour),
    volume24h_USD, change24h_pct_from_candles (24h pct change, computed
    from 25 x 1h candles), trades24h, basis_pct (mark-vs-oracle deviation
    in pct: (last candle close - oraclePrice) / oraclePrice x 100), and
    the latest three 1h candles (t/open/close/usdVolume). An unknown or
    delisted ticker raises an error (MCP isError) — settled markets are
    not served.
    Example: market_detail(ticker="BTC-USD")"""
    _require_ticker(ticker)
    m = api.markets()[ticker]
    cnd = api.candles(ticker, "1HOUR", 25)
    change24h = None
    if len(cnd) >= 25:
        now, past = float(cnd[-1]["close"]), float(cnd[-25]["close"])
        if past:
            change24h = _fmt((now / past - 1) * 100, 3)
    oracle = float(m.get("oraclePrice") or 0)
    last_1m = api.candles(ticker, "1MIN", 1)
    basis_pct = None
    if last_1m and oracle:
        basis_pct = _fmt(
            (float(last_1m[-1]["close"]) - oracle) / oracle * 100, 3)
    return {
        "ticker": ticker,
        "oraclePrice": _fmt(m.get("oraclePrice")),
        "openInterest": m.get("openInterest"),
        "nextFundingRate_pct_1h": _fmt(float(m.get("nextFundingRate", 0) or 0) * 100, 5),
        "volume24h_USD": _fmt(float(m.get("volume24H", 0) or 0), 0),
        "change24h_pct_from_candles": change24h,
        "basis_pct": basis_pct,
        "trades24h": m.get("trades24H"),
        "candles_1h_latest": [
            {"t": c.get("startedAt"), "open": _fmt(c.get("open")),
             "close": _fmt(c.get("close")), "usdVolume": _fmt(c.get("usdVolume"), 0)}
            for c in cnd[-3:]],
    }


def candles(
    ticker: str,
    resolution: Literal["1MIN", "5MIN", "15MIN", "30MIN",
                        "1HOUR", "4HOURS", "1DAY"] = "1HOUR",
    limit: int = 100,
) -> list:
    """OHLCV candles with open interest for a market.
    resolution: 1MIN|5MIN|15MIN|30MIN|1HOUR|4HOURS|1DAY.
    Each candle: startedAt, open/high/low/close (price), baseTokenVolume
    (base-coin size), usdVolume (USD), startingOpenInterest. Rows are
    ordered oldest -> newest (the
    indexer sends newest-first; we normalize). limit is capped at 1000.
    Example: candles(ticker="ETH-USD", resolution="1HOUR", limit=100)"""
    _require_ticker(ticker)
    return api.candles(ticker, resolution, min(limit, 1000))


def recent_trades(ticker: str, limit: int = 30) -> list:
    """Latest public trades of a market (price, side, size, type, time).
    Newest first; limit capped at 100. side is BUY/SELL, size in base coin.
    Example: recent_trades(ticker="BTC-USD", limit=30)"""
    _require_ticker(ticker)
    return api.market_trades(ticker, min(limit, 100))


def trader_profile(address: str, subaccount: int = 0) -> dict:
    """Snapshot of any trader's subaccount: equity, open positions, and PnL
    curve statistics (all-time window from up to 1000 history points).
    Returns equity_now / totalPnl_now / totalPnl_delta_window (USD),
    window_start / window_end, and open_positions (market, side, size,
    entry, unrealizedPnl in USD). Pair with trader_pnl_stats for deeper
    statistics.
    Example: trader_profile(address="dydx1m9hg73dtn5ku8ulmj8rjmdqh0hk7uuhawc69cn")"""
    acct = api.account(address)
    pnl = api.historical_pnl(address, subaccount)
    stats = {}
    if pnl:
        newest, oldest = pnl[0], pnl[-1]  # indexer returns newest-first
        eq_now, pnl_now = float(newest.get("equity", 0)), float(newest.get("totalPnl", 0))
        pnl_old = float(oldest.get("totalPnl", 0))
        stats = {
            "window_start": oldest.get("createdAt"), "window_end": newest.get("createdAt"),
            "equity_now": _fmt(eq_now),
            "totalPnl_now": _fmt(pnl_now),
            "totalPnl_delta_window": _fmt(pnl_now - pnl_old),
        }
    open_perps = api.perpetual_positions(address, subaccount)
    open_list = [p for p in open_perps if p.get("status") == "OPEN"]
    return {
        "address": address, "subaccount": subaccount,
        **stats,
        "open_positions": [
            {"market": p.get("market"), "side": p.get("side"),
             "size": p.get("size"), "entry": _fmt(p.get("entryPrice")),
             "unrealizedPnl": _fmt(p.get("unrealizedPnl"))}
            for p in open_list],
        "summary": (f"equity {stats.get('equity_now')}; "
                    f"open positions: {len(open_list)}"),
    }


def trader_pnl_stats(address: str, subaccount: int = 0,
                     limit: int = 1000) -> dict:
    """Deep PnL statistics from the equity curve: daily PnL, day-winrate,
    max drawdown (deposit-adjusted), Sharpe-like daily ratio, and the
    data-accuracy reconciliation residual (phantom-PnL detector).
    Key fields: day_winrate_pct (0-100), max_drawdown_pct (pct, net of
        deposits/withdrawals) with max_drawdown_usd (same drawdown in USD)
        and dd_pct_unreliable (true when the deposit-adjusted peak at the
        worst drawdown was near zero — trust the USD figure then),
        avg_daily_pnl / best_day / worst_day (USD per
    UTC day), sharpe_like_daily, identity_max_residual_usd (expect < $1
    on clean data). limit: history depth in points — 1000 ≈ 42 days
    (default, fast), 5000 ≈ 7 months (slower, multi-page fetch).
    Example: trader_pnl_stats(address="dydx1m9hg73dtn5ku8ulmj8rjmdqh0hk7uuhawc69cn", limit=5000)"""
    from .pnl_engine import pnl_stats
    return pnl_stats(address, subaccount, max(100, min(limit, 5000)))


def registry_stats() -> dict:
    """Live stats of our on-chain address registry (block scanner):
    how many active addresses collected, scan height, freshness.
    Returns addresses_total, scanned_up_to_height (last ingested dYdX
    block), seen_last_24h (addresses seen in the last 24h) and the sqlite
    path. On hosts where the optional scanner has not run, returns a
    note instead — market/trader tools still work via the public indexer.
    Example: registry_stats()"""
    from . import registry
    return registry.stats()


def list_traders(limit: int = 10, max_hits: int = 100,
                 offset: int = 0) -> dict:
    """Recently active trader addresses from the block-scanner registry
    (high-frequency validator committers filtered out by max_hits).
    Each row: address, hits (chain appearances), first_seen / last_seen,
    last_height. Returns {"total", "count", "offset", "has_more",
    "next_offset", "traders"}; traders == [] when the registry is not
    built on this host. Page with offset when has_more is true.
    Feed an address into trader_profile / trader_pnl_stats next.
    Example: list_traders(limit=10, max_hits=100)"""
    from . import registry
    return registry.recent(limit, max_hits, max(offset, 0))


def discover_traders(limit: int = 5, min_equity: float = 100.0) -> list[dict]:
    """Screener: funded, recently active traders discovered from the chain —
    registry candidates probed for live equity. Start here, then analyze
    each with trader_profile. Each row: address, equity (USD, >=
    min_equity), registry_hits, last_seen.
    Example: discover_traders(limit=5, min_equity=100.0)"""
    from . import registry
    return registry.discover(limit, min_equity)


def leaderboard(
    limit: int = 20,
    metric: Literal["pnl_window", "pnl_total", "equity",
                    "day_winrate"] = "pnl_window",
    offset: int = 0,
) -> dict:
    """Verified trader leaderboard from our registry + PnL engine
    (batch-computed). metric: pnl_window | pnl_total | equity | day_winrate.
    Farmer flags mark likely rewards-farming bots (heuristic v0).
    Each row (USD where monetary): address, equity, pnl_total, pnl_window,
    day_winrate (pct 0-100), max_dd (pct), maker_share, avg_fill,
    farmer_flag (bool), identity_residual. Requires a batch run — otherwise
    returns {"error": "no leaderboard run yet — run leaderboard.py first"}.
    Example: leaderboard(limit=20, metric="pnl_window")"""
    from . import analytics
    return analytics.leaderboard(limit, metric, max(offset, 0))


def latest_events(
    limit: int = 20,
    kind: Literal["funding_extreme", "oi_spike_no_price",
                  "equity_jump", "liq_cascade_signature"] | None = None,
    offset: int = 0,
) -> list[dict]:
    """Latest anomaly events from our detectors: funding_extreme,
    oi_spike_no_price, equity_jump, liq_cascade_signature. Each row: ts,
    kind, subject (ticker or address) and payload (dict of detector
    numbers). Optional kind filter; offset pages past the newest slice
    (events are pruned at 5000 — offset+limit beyond that returns []).
    Subscribe via webhooks/Telegram (alerts).
    Example: latest_events(limit=20, kind="funding_extreme")"""
    from . import analytics
    return analytics.latest_events(limit, kind, max(offset, 0))


def market_digest() -> dict:
    """One-call market briefing: latest detector events + funding extremes
    (liquid markets only) + verified leaderboard top. The daily briefing
    an agent (or human) needs before anything else.
    Returns: events (up to 5, payload flattened into each row), funding
    (top-5 funding rows, markets with >= $100k OI) and leaderboard_top
    (top-3 by pnl_window: address, pnl_window, equity, day_winrate).
    Example: market_digest()"""
    heat = funding_heatmap(5, min_oi_usd=100_000.0)
    lb = leaderboard(3, "pnl_window")
    from . import analytics
    ev = analytics.latest_events(5)
    events = [{"kind": e["kind"], "subject": e["subject"],
               **e["payload"]} for e in ev]
    lb_top = lb.get("top")
    if lb_top:
        addr = lb_top[0]["address"][:10]
        lb_first = (f"{addr}… +${lb_top[0]['pnl_window']:,.0f}"
                    if lb_top[0]["pnl_window"] is not None
                    else f"{addr}… (no pnl window)")
    else:
        lb_first = "n/a"
    return {
        "events": events,
        "funding": heat["top"],
        "leaderboard_top": [{k: r[k] for k in
                             ("address", "pnl_window", "equity", "day_winrate")}
                            for r in lb.get("top", [])],
        "summary": (f"events: {len(events)} | extreme funding: "
                    + (heat["top"][0]["ticker"] + " "
                       + str(heat["top"][0]["funding_pct_annualized"]) + "% ann"
                       if heat["top"] else "none")
                    + f" | leaderboard #1: " + lb_first),
    }


def usage_stats() -> dict:
    """Tool-call counters since deployment (traction/uptime metrics).
    Returns calls_total, calls_24h, calls_7d and top_tools (top-5
    (tool, count) pairs) recorded by this gateway instance.
    Example: usage_stats()"""
    from . import analytics
    return analytics.usage_stats()


def height() -> dict:
    """Current dYdX chain height and time — use for liveness checks.
    Returns {"height": current block number, "time": block timestamp}.
    Example: height()"""
    return api.height()


# ------------------------------------------- analytics toolkit ("best of" ideas)

def funding_heatmap(limit: int = 15, min_oi_usd: float = 10_000.0,
                    offset: int = 0) -> dict:
    """All markets ranked by |next funding rate| (1h, annualized). Shows which
    sides pay: positive = longs pay shorts. Rows carry OI so agents can
    ignore micro-markets; raise min_oi_usd to filter noise.
    Each row: ticker, funding_pct_1h (pct per hour), funding_pct_annualized
    (1h rate x 24 x 365), oi_usd, oraclePrice, and exactly one of
    longs_pay / shorts_pay = True. Zero-rate markets and markets below
    min_oi_usd are skipped. Returns {"count_nonzero", "top", "summary",
    "offset", "has_more"} — page with offset when has_more is true.
    Example: funding_heatmap(limit=15, min_oi_usd=100000.0)"""
    if offset < 0:
        offset = 0
    ms = api.markets()
    rows = []
    for t, m in ms.items():
        f1h = float(m.get("nextFundingRate", 0) or 0)
        if f1h == 0:
            continue
        oi_usd = float(m.get("openInterest", 0) or 0) * float(m.get("oraclePrice") or 0)
        if oi_usd < min_oi_usd:
            continue
        rows.append({
            "ticker": t,
            "funding_pct_1h": _fmt(f1h * 100, 5),
            "funding_pct_annualized": _fmt(f1h * 100 * 24 * 365, 1),
            "oi_usd": _fmt(oi_usd, 0),
            "longs_pay" if f1h > 0 else "shorts_pay": True,
            "oraclePrice": _fmt(m.get("oraclePrice")),
        })
    rows.sort(key=lambda r: -abs(r["funding_pct_1h"]))
    top = rows[offset:offset + limit]
    side = ", ".join(f"{r['ticker']} {r['funding_pct_1h']:+}%/1h"
                     for r in top[:3])
    return {"count_nonzero": len(rows), "top": top,
            "summary": f"most extreme funding: {side}",
            "offset": offset, "has_more": offset + limit < len(rows)}


def _ema(xs, n):
    k, e = 2 / (n + 1), xs[0]
    for x in xs[1:]:
        e = x * k + e * (1 - k)
    return e


def _rsi(closes, n=14):
    if len(closes) < n + 1:
        return None
    gains = losses = 0.0
    for a, b in zip(closes[:n], closes[1:n + 1]):
        d = b - a
        gains += max(d, 0)
        losses += max(-d, 0)
    ag, al = gains / n, losses / n
    for a, b in zip(closes[n:], closes[n + 1:]):
        d = b - a
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
    return 100 - 100 / (1 + ag / al) if al else 100.0


def _atr(candles, n=14):
    if len(candles) < n + 1:
        return None
    trs = []
    for prev, cur in zip(candles, candles[1:]):
        h, l = float(cur["high"]), float(cur["low"])
        pc = float(prev["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(trs[:n]) / n
    for tr in trs[n:]:
        a = (a * (n - 1) + tr) / n
    return a


def market_ta(ticker: str, resolution: str = "1HOUR") -> dict:
    """Technical snapshot computed from dYdX candles: RSI(14), EMA20/EMA50
    trend, ATR(14) volatility, Bollinger(20,2) position, MACD(12,26,9),
    VWAP(20) and annualized realized vol. Pure local math — no external
    TA library.
    Key fields: price, trend_ema20_50 ("up"/"down"), rsi14 (0-100) and
    rsi_zone (overbought >70 / oversold <30 / neutral), atr14 (absolute)
    and atr_pct_of_price (pct), bollinger_pctB (0 = lower band, 1 = upper
    band), macd_line/signal_line/macd_hist (classic 12/26/9; hist > 0 =
    bullish momentum), vwap_20 (volume-weighted average price over the
    last 20 candles: typical price (H+L+C)/3 weighted by usdVolume) and
    realized_vol_annualized_pct (population std of log returns x
    sqrt(candles-per-year), scaled by resolution). Needs >=55 candles;
    returns {"error": ...} for thin markets.
    Example: market_ta(ticker="BTC-USD", resolution="1HOUR")"""
    _require_ticker(ticker)
    cnd = api.candles(ticker, resolution, 120)
    if len(cnd) < 55:
        return {"error": f"not enough candles for {ticker} {resolution}"}
    closes = [float(c["close"]) for c in cnd]
    price = closes[-1]
    e20, e50 = _ema(closes[-50:], 20), _ema(closes, 50)
    rsi = _rsi(closes)
    atr = _atr(cnd)
    win = closes[-20:]
    sma = sum(win) / len(win)
    var = sum((x - sma) ** 2 for x in win) / len(win)
    bb_lo, bb_hi = sma - 2 * var ** 0.5, sma + 2 * var ** 0.5
    pct_b = (price - bb_lo) / (bb_hi - bb_lo) if bb_hi > bb_lo else None
    trend = "up" if e20 > e50 else "down"
    zone = ("overbought" if rsi and rsi > 70 else
            "oversold" if rsi and rsi < 30 else "neutral")
    bb_s = f"{pct_b:.2f}" if pct_b is not None else "n/a"
    macd = ta_ext.macd(closes)
    try:
        vwap = ta_ext.vwap(cnd[-20:])
    except (KeyError, TypeError, ValueError):
        vwap = None          # candle feed without volume fields
    rvol = (ta_ext.realized_vol(closes[-168:],
                                ta_ext.periods_per_year(resolution))
            if len(closes) >= 2 else None)
    macd_s = f"MACD hist {macd['hist']:+.4g}" if macd else "MACD n/a"
    vwap_s = (f"VWAP20 {_fmt_price(vwap, 4):.6g}"
              if vwap is not None else "VWAP n/a")
    rvol_s = f"rVol {rvol * 100:.1f}% ann" if rvol is not None else "rVol n/a"
    return {
        "ticker": ticker, "resolution": resolution, "price": _fmt_price(price),
        "trend_ema20_50": trend, "rsi14": _fmt(rsi, 1), "rsi_zone": zone,
        "atr14": _fmt_price(atr, 4), "atr_pct_of_price": _fmt(atr / price * 100, 2),
        "bollinger_pctB": _fmt(pct_b, 2),
        "macd_line": macd["macd"] if macd else None,
        "signal_line": macd["signal"] if macd else None,
        "macd_hist": macd["hist"] if macd else None,
        "vwap_20": _fmt_price(vwap, 4) if vwap is not None else None,
        "realized_vol_annualized_pct": _fmt(rvol * 100, 2)
        if rvol is not None else None,
        "summary": (f"{ticker}: {trend} trend, RSI {rsi:.0f} ({zone}), "
                    f"ATR {atr / price * 100:.2f}% of price, BB%B {bb_s}, "
                    f"{macd_s}, {vwap_s}, {rvol_s}"),
    }


def suggest_stops(ticker: str, side: str, entry: float | None = None,
                  atr_mult_sl: float = 1.5, atr_mult_tp: float = 2.5,
                  resolution: str = "1HOUR") -> dict:
    """ATR-based risk plan: stop-loss, take-profit, breakeven trigger and
    trailing level for a long/short entry. Agent-managed position helper.
    Unknown ticker (no oracle price) raises an error (MCP isError);
    returns {"error": ...} when no ATR is available (thin market).
    All output prices are in market price units: stop_loss / take_profit
    sit atr_mult_sl / atr_mult_tp x ATR(14) from entry (entry defaults to
    the current oracle price); breakeven_after is the price at +1 ATR in
    profit (then move SL to entry and trail by 1 ATR); risk_reward =
    TP distance / SL distance.
    Example: suggest_stops(ticker="BTC-USD", side="LONG", atr_mult_sl=1.5)"""
    _require_ticker(ticker)
    m = api.markets().get(ticker, {})
    entry = float(entry or m.get("oraclePrice") or 0)
    if not entry:
        raise ValueError(f"no price available for {ticker}")
    ta = market_ta(ticker, resolution)
    atr = ta.get("atr14")
    if not atr:
        return {"error": ta.get("error", "no ATR")}
    d = 1 if side.upper() == "LONG" else -1
    sl = entry - d * atr_mult_sl * atr
    tp = entry + d * atr_mult_tp * atr
    be_trigger = entry + d * 1.0 * atr      # after 1 ATR in profit -> move SL to BE
    trail = entry + d * 1.0 * atr           # then trail by 1 ATR
    rr = abs(tp - entry) / abs(entry - sl)
    return {
        "ticker": ticker, "side": side.upper(), "entry": _fmt_price(entry),
        "atr14": _fmt_price(atr, 4), "atr_pct": ta["atr_pct_of_price"],
        "stop_loss": _fmt_price(sl, 4), "take_profit": _fmt_price(tp, 4),
        "breakeven_after": _fmt_price(be_trigger, 4),
        "trail_by_atr": 1.0, "risk_reward": _fmt(rr, 2),
        "summary": (f"{side.upper()} {ticker} @ {entry:.4g}: SL {sl:.4g} / "
                    f"TP {tp:.4g} (RR {rr:.1f}), BE after ±1 ATR, then trail 1 ATR"),
    }


def fills_review(address: str, subaccount: int = 0, limit: int = 100) -> dict:
    """Execution review from the latest fills: maker/taker split, per-market
    distribution, traded volume, avg fill size. (Per-fill PnL is not exposed
    by the indexer; use trader_pnl_stats for win-rate.)
    Key fields: fills_sampled (count), maker_share_pct (0-100),
    sampled_volume_USD, avg_fill_USD, top_markets (top 5 by fill count).
    Returns {"summary": "no fills"} for accounts with no fills.
    Example: fills_review(address="dydx1m9hg73dtn5ku8ulmj8rjmdqh0hk7uuhawc69cn")"""
    fs = api.fills(address, subaccount, limit)
    if not fs:
        return {"address": address, "summary": "no fills"}
    maker = sum(1 for f in fs if f.get("liquidity") == "MAKER")
    vol = sum(float(f.get("size", 0) or 0) * float(f.get("price", 0) or 0)
              for f in fs)
    by_mkt = {}
    for f in fs:
        by_mkt[f.get("market")] = by_mkt.get(f.get("market"), 0) + 1
    top_mkts = sorted(by_mkt.items(), key=lambda x: -x[1])[:5]
    return {
        "address": address, "fills_sampled": len(fs),
        "maker_share_pct": _fmt(maker / len(fs) * 100, 1),
        "sampled_volume_USD": _fmt(vol, 0),
        "avg_fill_USD": _fmt(vol / len(fs), 0),
        "top_markets": top_mkts,
        "summary": (f"{len(fs)} fills, maker {maker / len(fs) * 100:.0f}%, "
                    f"vol ${vol:,.0f}, top: " + ", ".join(m for m, _ in top_mkts[:3])),
    }


def historical_funding(ticker: str, limit: int = 168) -> dict:
    """Raw 1h funding rate history of a market (as realized, not the
    next-rate preview in market_detail): each point is the rate actually
    paid that hour; annualized_pct = rate x 24 x 365 for scale. Default
    168 points = 7 days. Points are ordered oldest -> newest (candles
    convention); limit capped at 500.
    Positive = longs paid shorts. An unknown or delisted ticker raises an
    error (MCP isError) — call list_markets for the valid set (format:
    'ETH-USD').
    Example: historical_funding(ticker="ETH-USD", limit=168)"""
    _require_ticker(ticker)
    hist = api.historical_funding(ticker, min(limit, 500))
    points = [{"t": p.get("effectiveAt"),
               "rate_1h": _fmt(float(p.get("rate", 0) or 0), 8),
               "annualized_pct": _fmt(
                   float(p.get("rate", 0) or 0) * 100 * 24 * 365, 2)}
              for p in reversed(hist)]          # newest-first -> oldest-first
    summary = "no funding history"
    if points:
        last = points[-1]
        rates = [p["rate_1h"] for p in points]
        summary = (f"latest 1h rate {last['rate_1h']:+} "
                   f"({last['annualized_pct']:+}% ann), mean {sum(rates) / len(rates):+.8f}, "
                   f"max |rate| {max(rates, key=abs):+.8f}, {len(points)} points")
    return {"ticker": ticker, "points": points, "summary": summary}


def raw_fills(address: str, subaccount: int = 0, limit: int = 200) -> dict:
    """Raw execution tape for a subaccount — every field the indexer
    gives, unchanged — for agents doing their own execution-quality
    math (the aggregated view lives in fills_review). Each fill: t
    (createdAt), market, side, liquidity (MAKER/TAKER), type, price,
    size (base coin), usd_notional (price x size), fee, and the
    position context (positionSideBefore / positionSizeBefore /
    entryPriceBefore). Newest first; limit capped at 1000. Addresses
    come from discover_traders / leaderboard / list_traders.
    Example: raw_fills(address="dydx1m9hg73dtn5ku8ulmj8rjmdqh0hk7uuhawc69cn")"""
    fs = api.fills(address, subaccount, min(limit, 1000))
    # printed fields must be self-consistent (A2 lesson): usd_notional is
    # recomputable from the printed price x size; sub-cent prices keep
    # 6 significant digits instead of rounding to 0.0
    fills = [{"t": f.get("createdAt"), "market": f.get("market"),
              "side": f.get("side"), "liquidity": f.get("liquidity"),
              "type": f.get("type"), "price": _fmt_price(f.get("price")),
              "size": _fmt(f.get("size"), 6),
              "usd_notional": _fmt_price(
                  float(f.get("price", 0) or 0)
                  * float(f.get("size", 0) or 0), 2),
              "fee": _fmt(f.get("fee")),
              "positionSideBefore": f.get("positionSideBefore"),
              "positionSizeBefore": _fmt(f.get("positionSizeBefore")),
              "entryPriceBefore": _fmt_price(f.get("entryPriceBefore")),
              }
             for f in fs]
    summary = "no fills"
    if fills:
        mkts = sorted({f["market"] for f in fills if f["market"]})
        summary = (f"{len(fills)} fills, markets: "
                   + ", ".join(mkts[:5]) + ("…" if len(mkts) > 5 else ""))
    return {"address": address, "subaccount": subaccount, "fills": fills,
            "summary": summary}


def cvd(ticker: str, trades_limit: int = 500) -> dict:
    """Cumulative Volume Delta from the latest public trades: running
    sum of +size on BUY / -size on SELL, oldest -> newest within the
    sample. Rising CVD = aggressive buying dominating. Volumes are in
    the base coin. Returns cvd_final (net aggressive flow),
    buy_volume / sell_volume, trade window bounds (t_first / t_last),
    trades_sampled and cvd_series_last (the last 50 running values —
    full series stays out of the response to keep it compact).
    An unknown or delisted ticker raises an error (MCP isError) — call
    list_markets for the valid set (format: 'ETH-USD').
    Example: cvd(ticker="BTC-USD", trades_limit=500)"""
    _require_ticker(ticker)
    trades = api.market_trades(ticker, min(trades_limit, 1000))
    if not trades:
        return {"error": "no trades"}
    c = ta_ext.cvd(trades)          # handles newest-first internally
    oldest, newest = trades[-1], trades[0]
    return {
        "ticker": ticker, "trades_sampled": len(trades),
        "t_first": oldest.get("createdAt"), "t_last": newest.get("createdAt"),
        "buy_volume": c["buy_volume"], "sell_volume": c["sell_volume"],
        "cvd_final": c["final"],
        "cvd_series_last": c["series"][-50:],
        "summary": (f"CVD {c['final']:+} over {len(trades)} trades "
                    f"(buy {c['buy_volume']:,.6g} / sell "
                    f"{c['sell_volume']:,.6g} base units)"),
    }


def correlation(ticker_a: str, ticker_b: str,
                resolution: str = "1HOUR", limit: int = 168) -> dict:
    """Pearson correlation of two markets' log returns over candles:
    r in [-1, 1] plus beta(a|b) — the sensitivity of a to b (a moves
    beta x b's move, both in log space). Candle series are JOINED by
    startedAt (only candles with the same timestamp on both sides are
    compared), so partially-overlapping histories pair correctly.
    Both tickers are validated; call list_markets for the valid set
    (format: 'ETH-USD'). Returns {"error": ...} when there is
    insufficient or constant data.
    Example: correlation(ticker_a="BTC-USD", ticker_b="ETH-USD")"""
    _require_ticker(ticker_a)
    _require_ticker(ticker_b)
    want = min(limit, 1000)
    ca = api.candles(ticker_a, resolution, want)
    cb = api.candles(ticker_b, resolution, want)
    by_ts = {c["startedAt"]: float(c["close"]) for c in cb}
    joined = [(float(c["close"]), by_ts[c["startedAt"]])
              for c in ca if c["startedAt"] in by_ts]
    a = [p for p, _ in joined]
    b = [q for _, q in joined]
    n = len(joined)
    res = ta_ext.pearson_log_returns(a, b)
    if res is None:
        return {"ticker_a": ticker_a, "ticker_b": ticker_b,
                "resolution": resolution, "candles": n,
                "error": "insufficient or constant data"}
    return {
        "ticker_a": ticker_a, "ticker_b": ticker_b,
        "resolution": resolution, "candles": n,
        "r": _fmt(res["r"], 3), "beta_a_over_b": _fmt(res["beta"], 3),
        "summary": (f"r={_fmt(res['r'], 3)}, "
                    f"beta(a|b)={_fmt(res['beta'], 3)} over {n} "
                    f"{resolution} candles"),
    }


# ------------------------------------------------------- trading (removed)
# v0.2.3: analytics-only by design — trading tools (place_order /
# cancel_all / my_positions) were removed from the public gateway.
# The offline-tested EIP-712 signer remains in dydx_mcp/signer.py
# as a library for anyone building their own execution layer.


# ------------------------------------------------------------------ MCP wire

def build_server():
    from fastmcp import FastMCP
    from fastmcp.server.middleware import Middleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    class UsageLogger(Middleware):
        """Records every tool call into analytics.usage (usage metrics)."""

        async def on_call_tool(self, context, call_next):
            from . import analytics
            # context.message is CallToolRequestParams with .name
            analytics.log_usage(getattr(context.message, "name", None) or "unknown")
            return await call_next(context)

    mcp = FastMCP(
        "dydx-agent-gateway",
        version="0.3.0",
        instructions=(
            "Tickers come from list_markets (format 'ETH-USD'); trader addresses from discover_traders/leaderboard. Start with market_digest for a briefing (events + funding extremes "
            "+ leaderboard). To evaluate a trader: trader_profile then "
            "trader_pnl_stats (limit up to 5000 = ~7 months of history). "
            "To find traders: discover_traders (funded, on-chain) or "
            "list_traders (recent registry addresses). Funding rows carry "
            "oi_usd — ignore markets below ~$100k OI as noise. suggest_stops "
            "gives an ATR-based risk plan. latest_events returns detector "
            "output (funding_extreme / oi_spike_no_price / "
            "liq_cascade_signature / equity_jump). Deeper analytics: "
            "historical_funding (realized 1h funding history), raw_fills "
            "(raw execution tape), cvd (aggressive buy/sell flow), "
            "correlation (r + beta between two markets); market_ta adds "
            "MACD/VWAP/realized vol and trader_pnl_stats a sortino-like "
            "downside ratio."),
    )
    mcp.add_middleware(UsageLogger())

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "service": "dydx-agent-gateway"})
    # read-only by design; destructiveHint explicit False (spec default is
    # true, which would mislabel this analytics-only gateway)
    RO = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True}
    RO_IDEM = {"readOnlyHint": True, "destructiveHint": False,
               "idempotentHint": True, "openWorldHint": True}
    # sqlite-backed tools: no external-world interaction
    RO_LOCAL = {"readOnlyHint": True, "destructiveHint": False,
                "idempotentHint": True, "openWorldHint": False}

    mcp.tool(list_markets, annotations=RO)
    mcp.tool(market_detail, annotations=RO)
    mcp.tool(candles, annotations=RO)
    mcp.tool(recent_trades, annotations=RO)
    mcp.tool(trader_profile, annotations=RO)
    mcp.tool(height, annotations=RO_IDEM)
    mcp.tool(funding_heatmap, annotations=RO)
    mcp.tool(market_ta, annotations=RO)
    mcp.tool(suggest_stops, annotations=RO)
    mcp.tool(fills_review, annotations=RO)
    mcp.tool(historical_funding, annotations=RO)
    mcp.tool(raw_fills, annotations=RO)
    mcp.tool(cvd, annotations=RO)
    mcp.tool(correlation, annotations=RO)
    mcp.tool(trader_pnl_stats, annotations=RO)
    mcp.tool(registry_stats, annotations=RO_LOCAL)
    mcp.tool(list_traders, annotations=RO)
    mcp.tool(discover_traders, annotations=RO)
    mcp.tool(leaderboard, annotations=RO)
    mcp.tool(latest_events, annotations=RO_LOCAL)
    mcp.tool(market_digest, annotations=RO_LOCAL)
    mcp.tool(usage_stats, annotations=RO_LOCAL)
    return mcp


def main():
    """Console entry point (dydx-agent-gateway). stdio by default —
    for local agents (Claude Desktop/Codex); --http for the hosted form."""
    import argparse
    ap = argparse.ArgumentParser(prog="dydx-agent-gateway")
    ap.add_argument("--http", action="store_true", help="streamable HTTP instead of stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8901)
    a = ap.parse_args()
    mcp = build_server()
    if a.http:
        mcp.run(transport="http", host=a.host, port=a.port, show_banner=False)
    else:
        mcp.run(show_banner=False)  # stdio: no banner noise in user logs


if __name__ == "__main__":
    main()
