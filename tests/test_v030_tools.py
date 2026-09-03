"""MEC-50 (v0.3.0 analyst pack) regressions for the new tools.

- historical_funding / raw_fills / cvd / correlation server tools on
  mocked indexer data (monkeypatch srv.api, pattern of test_a2 /
  test_server), every number recomputed by hand here.
- Enrichments: market_ta MACD/VWAP/realized vol, market_detail
  basis_pct, pnl_engine sortino_like_daily.
- Ticker guards: unknown tickers raise ValueError (-> MCP isError).

Correlation note: a perfectly co-moving pair with beta(a|b) = 0.5 needs
b's log returns to be exactly 2x a's — i.e. closes_b = closes_a ** 2
(a multiplicative 2x on prices alone gives beta = 1, since log returns
would be identical).
"""
import math
import statistics

import pytest

from dydx_mcp import server as srv
from dydx_mcp.pnl_engine import compute


# ---------------------------------------------------------------- helpers

def _cndl(closes, vol=1000.0):
    """Candles from closes with high = close+1, low = close-1, constant
    offset volume (typical price = close exactly)."""
    return [{"startedAt": f"2026-01-01T{i // 24:02d}:{i % 24:02d}:00Z",
             "open": str(c), "close": str(c),
             "high": str(c + 1), "low": str(c - 1),
             "usdVolume": str(vol)}
            for i, c in enumerate(closes)]


def _no_markets(monkeypatch):
    monkeypatch.setattr(srv.api, "markets", lambda: {})


# ------------------------------------------------------- historical_funding

def test_historical_funding_points_math_and_order(monkeypatch):
    monkeypatch.setattr(srv.api, "markets", lambda: {"ETH-USD": {}})
    monkeypatch.setattr(srv.api, "historical_funding", lambda t, l: [
        {"effectiveAt": "2026-01-02T00:00:00Z", "rate": "0.0002"},   # newest
        {"effectiveAt": "2026-01-01T23:00:00Z", "rate": "0.0001"},
    ])
    h = srv.historical_funding("ETH-USD", 168)
    # oldest -> newest (candles convention)
    assert h["points"][0]["t"] == "2026-01-01T23:00:00Z"
    assert h["points"][1]["t"] == "2026-01-02T00:00:00Z"
    for p, rate in zip(h["points"], ("0.0001", "0.0002")):
        r = float(rate)
        assert p["rate_1h"] == float(f"{r:.8f}")            # manual recompute
        assert p["annualized_pct"] == float(               # rate*100*24*365
            f"{r * 100 * 24 * 365:.2f}")
    # summary carries the point count and the latest annualized figure
    assert "2 points" in h["summary"]
    assert str(h["points"][-1]["annualized_pct"]) in h["summary"]


def test_historical_funding_ticker_guard(monkeypatch):
    _no_markets(monkeypatch)
    monkeypatch.setattr(srv.api, "historical_funding",
                        lambda t, l: pytest.fail("must not be called"))
    with pytest.raises(ValueError):
        srv.historical_funding("NOPE-USD")


# ---------------------------------------------------------------- raw_fills

def test_raw_fills_fields_order_and_notional(monkeypatch):
    fills = [  # newest first, as the indexer returns
        {"createdAt": "2026-01-02T00:00:00Z", "market": "B-USD",
         "side": "SELL", "liquidity": "TAKER", "type": "FILL",
         "price": "2000", "size": "0.5"},
        {"createdAt": "2026-01-01T00:00:00Z", "market": "A-USD",
         "side": "BUY", "liquidity": "MAKER", "type": "FILL",
         "price": "100", "size": "2"},
    ]
    monkeypatch.setattr(srv.api, "fills", lambda a, s=0, l=200: fills)
    r = srv.raw_fills("dydx1" + "a" * 38)
    assert r["fills"][0]["market"] == "B-USD"      # order preserved
    assert r["fills"][0]["side"] == "SELL" and r["fills"][0]["liquidity"] == "TAKER"
    for f, raw in zip(r["fills"], fills):
        px, sz = float(raw["price"]), float(raw["size"])
        assert f["price"] == px and f["size"] == sz
        assert f["usd_notional"] == float(f"{px * sz:.2f}")   # manual
    assert "2 fills" in r["summary"] and "A-USD" in r["summary"]


def test_raw_fills_empty(monkeypatch):
    monkeypatch.setattr(srv.api, "fills", lambda a, s=0, l=200: [])
    r = srv.raw_fills("dydx1" + "a" * 38)
    assert r["fills"] == [] and r["summary"] == "no fills"


# --------------------------------------------------------------------- cvd

def test_cvd_manual_recompute(monkeypatch):
    monkeypatch.setattr(srv.api, "markets", lambda: {"X-USD": {}})
    # newest-first tape: oldest -> newest is SELL 2, BUY 3, BUY 1
    monkeypatch.setattr(srv.api, "market_trades", lambda t, l=500: [
        {"side": "BUY", "size": "1", "createdAt": "2026-01-01T00:02:00Z"},
        {"side": "BUY", "size": "3", "createdAt": "2026-01-01T00:01:00Z"},
        {"side": "SELL", "size": "2", "createdAt": "2026-01-01T00:00:00Z"},
    ])
    c = srv.cvd("X-USD")
    assert c["trades_sampled"] == 3
    assert c["buy_volume"] == 4.0 and c["sell_volume"] == 2.0
    assert c["cvd_final"] == 4.0 - 2.0 == 2.0
    assert c["cvd_series_last"] == [-2.0, 1.0, 2.0]  # running sum, oldest->newest
    assert c["t_first"] == "2026-01-01T00:00:00Z"    # oldest trade ts
    assert c["t_last"] == "2026-01-01T00:02:00Z"     # newest trade ts
    assert len(c["cvd_series_last"]) <= 50           # compact response


def test_cvd_no_trades(monkeypatch):
    monkeypatch.setattr(srv.api, "markets", lambda: {"X-USD": {}})
    monkeypatch.setattr(srv.api, "market_trades", lambda t, l=500: [])
    assert srv.cvd("X-USD") == {"error": "no trades"}


def test_cvd_ticker_guard(monkeypatch):
    _no_markets(monkeypatch)
    with pytest.raises(ValueError):
        srv.cvd("NOPE-USD")


# ------------------------------------------------------------- correlation

def _closes_api(monkeypatch, by_ticker):
    monkeypatch.setattr(srv.api, "markets", lambda: set(by_ticker) and
                        {t: {} for t in by_ticker})
    monkeypatch.setattr(srv.api, "candles",
                        lambda t, r, l: _cndl(by_ticker[t]))


def test_correlation_perfect_pair_manual_beta(monkeypatch):
    # closes_b = closes_a ** 2 -> log returns exactly 2x a's:
    # r = 1.0, beta(a|b) = cov(ra, 2ra)/var(2ra) = 0.5
    a = [100.0, 101.0, 102.0, 103.5, 104.0, 106.0, 107.25, 108.0]
    _closes_api(monkeypatch, {"A-USD": a, "B-USD": [x ** 2 for x in a]})
    c = srv.correlation("A-USD", "B-USD")
    assert c["candles"] == len(a)
    assert abs(c["r"] - 1.0) < 1e-6            # fields rounded to 3dp
    assert abs(c["beta_a_over_b"] - 0.5) < 1e-6
    assert "r=1.0" in c["summary"]


def test_correlation_constant_returns_error(monkeypatch):
    _closes_api(monkeypatch, {"A-USD": [5.0] * 6, "B-USD": [7.0, 7.1, 7.2, 7.3, 7.4, 7.5]})
    c = srv.correlation("A-USD", "B-USD")
    assert "error" in c   # constant closes on one side


def test_correlation_joins_by_started_at(monkeypatch):
    # b carries two EXTRA candles with timestamps outside a's window:
    # join-by-startedAt must drop them, keeping the 5 paired candles
    a = [10.0, 11.0, 12.0, 13.0, 14.0]
    a_ts = [f"2026-01-01T00:{i:02d}:00Z" for i in range(5)]
    extra_ts = ["2025-12-31T23:58:00Z", "2025-12-31T23:59:00Z"]

    def candles(t, r, l):
        if t == "A-USD":
            return _cndl(a)
        rows = [{"startedAt": ts, "open": "3", "close": "3",
                 "high": "4", "low": "2", "usdVolume": "1"}
                for ts in extra_ts]
        rows += [{"startedAt": ts, "open": str(x ** 2), "close": str(x ** 2),
                  "high": str(x ** 2 + 1), "low": str(x ** 2 - 1),
                  "usdVolume": "1"}
                 for x, ts in zip(a, a_ts)]
        return rows

    monkeypatch.setattr(srv.api, "markets",
                        lambda: {"A-USD": {}, "B-USD": {}})
    monkeypatch.setattr(srv.api, "candles", candles)
    c = srv.correlation("A-USD", "B-USD")
    assert c["candles"] == 5                       # extras dropped by join
    assert abs(c["r"] - 1.0) < 1e-6 and abs(c["beta_a_over_b"] - 0.5) < 1e-6


def test_correlation_guard_on_second_ticker(monkeypatch):
    monkeypatch.setattr(srv.api, "markets", lambda: {"A-USD": {}})
    monkeypatch.setattr(srv.api, "candles",
                        lambda t, r, l: pytest.fail("must not be called"))
    with pytest.raises(ValueError):
        srv.correlation("A-USD", "NOPE-USD")


# ---------------------------------------------------- market_ta enrichment

def _gen_candles(n):
    """Arithmetically growing closes, high >= close >= low, real volumes."""
    return [{"startedAt": f"2026-01-01T{i // 24:02d}:{i % 24:02d}:00Z",
             "open": str(100 + i), "close": str(100 + i),
             "high": str(101 + i), "low": str(99 + i),
             "usdVolume": str(1000 + i)}
            for i in range(n)]


def test_market_ta_macd_vwap_rvol_manual(monkeypatch):
    monkeypatch.setattr(srv.api, "markets", lambda: {"X-USD": {}})
    cnd = _gen_candles(120)
    monkeypatch.setattr(srv.api, "candles", lambda t, r, l: cnd)
    ta = srv.market_ta("X-USD")

    closes = [float(c["close"]) for c in cnd]

    # MACD: numeric and consistent with the ta_ext convention
    assert isinstance(ta["macd_hist"], float) and math.isfinite(ta["macd_hist"])
    assert ta["macd_hist"] == pytest.approx(
        ta["macd_line"] - ta["signal_line"], abs=1e-9)

    # VWAP(20): manual recompute, typical price x usdVolume, last 20 candles
    last20 = cnd[-20:]
    pv = sum((float(c["high"]) + float(c["low"]) + float(c["close"])) / 3
             * float(c["usdVolume"]) for c in last20)
    v = sum(float(c["usdVolume"]) for c in last20)
    assert ta["vwap_20"] == pytest.approx(pv / v, abs=5e-5)  # 4dp rounding

    # realized vol: pstdev of log returns (last 168 closes -> all 120)
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    manual = statistics.pstdev(rets) * math.sqrt(8760) * 100
    assert ta["realized_vol_annualized_pct"] == pytest.approx(
        manual, abs=5e-3)                                   # 2dp rounding

    # summary carries the new compact block
    assert "MACD" in ta["summary"] and "VWAP" in ta["summary"] and "rVol" in ta["summary"]


# -------------------------------------------------- market_detail basis_pct

def test_market_detail_basis_pct_manual(monkeypatch):
    monkeypatch.setattr(srv.api, "markets",
                        lambda: {"X-USD": {"oraclePrice": "100"}})

    def candles(t, r, l):
        return _gen_candles(25) if r == "1HOUR" else _cndl([101.0])

    monkeypatch.setattr(srv.api, "candles", candles)
    d = srv.market_detail("X-USD")
    # (101 - 100) / 100 * 100 = 1.0, 3dp
    assert d["basis_pct"] == float(f"{(101.0 - 100.0) / 100.0 * 100:.3f}")


def test_market_detail_basis_pct_none_without_candles(monkeypatch):
    monkeypatch.setattr(srv.api, "markets",
                        lambda: {"X-USD": {"oraclePrice": "100"}})

    def candles(t, r, l):
        return _gen_candles(25) if r == "1HOUR" else []

    monkeypatch.setattr(srv.api, "candles", candles)
    assert srv.market_detail("X-USD")["basis_pct"] is None


# ------------------------------------------------- pnl_engine: sortino-like

def _row(day, eq, pnl):
    return {"createdAt": f"2026-01-{day:02d}T00:00:00Z", "equity": str(eq),
            "totalPnl": str(pnl), "netTransfers": "0"}


def test_compute_sortino_manual():
    # oldest -> newest pnl 0, 10, 5, 15, 10 -> daily [+10, -5, +10, -5]
    rows = [_row(5, 110, 10), _row(4, 115, 15), _row(3, 120, 5),
            _row(2, 110, 10), _row(1, 100, 0)]      # newest-first
    d = compute(rows)
    # mean 2.5 / sqrt((25 + 25) / 4) = 2.5 / sqrt(12.5), rounded 2dp
    assert d["sortino_like_daily"] == round(2.5 / math.sqrt(12.5), 2)
    assert d["sortino_like_daily"] == 0.71


def test_compute_sortino_none_without_losses():
    rows = [_row(4, 130, 30), _row(3, 120, 20), _row(2, 110, 10),
            _row(1, 100, 0)]                          # all days positive
    assert compute(rows)["sortino_like_daily"] is None
