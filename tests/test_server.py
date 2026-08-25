"""B4: server tools — TA math vectors, heatmap OI filter, stops math,
trader_profile on mocked newest-first data."""
from dydx_mcp import server as srv


# ---------------------------------------------------------------- TA math

def test_ema_vector():
    # EMA3 over [1..5] (k=0.5): 1 -> 1.5 -> 2.25 -> 3.125 -> 4.0625
    assert srv._ema([1, 2, 3, 4, 5], 3) == 4.0625


def test_rsi_extremes():
    up = [float(i) for i in range(1, 25)]
    down = [float(25 - i) for i in range(24)]
    flat = [5.0] * 25
    assert srv._rsi(up) == 100.0        # all gains
    assert srv._rsi(down) == 0.0        # all losses
    assert srv._rsi(flat) == 100.0      # documented convention (al == 0)
    assert srv._rsi([1.0] * 5) is None  # not enough data


def test_atr_constant_range():
    cnd = [{"high": str(11), "low": str(10), "close": str(10.5)} for _ in range(20)]
    assert abs(srv._atr(cnd) - 1.0) < 1e-9


# ---------------------------------------------------------------- heatmap

def _mkts():
    return {
        "BIG-USD": {"oraclePrice": "2", "volume24H": "1", "openInterest": "100000",
                    "nextFundingRate": "0.004"},
        "TINY-USD": {"oraclePrice": "2", "volume24H": "1", "openInterest": "10",
                     "nextFundingRate": "0.004"},
    }


def test_funding_heatmap_oi_filter(monkeypatch):
    monkeypatch.setattr(srv.api, "markets", _mkts)
    h = srv.funding_heatmap(limit=5, min_oi_usd=100_000)
    tickers = [r["ticker"] for r in h["top"]]
    assert tickers == ["BIG-USD"] and h["top"][0]["oi_usd"] == 200000.0


# ---------------------------------------------------------------- stops

def _cnd(n, px):
    return [{"startedAt": f"2026-01-01T00:{i:02d}:00Z", "open": str(px),
             "close": str(px), "high": str(px + 1), "low": str(px - 1)}
            for i in range(n)]


def test_suggest_stops_math(monkeypatch):
    monkeypatch.setattr(srv.api, "markets",
                        lambda: {"ETH-USD": {"oraclePrice": "100",
                                             "atomicResolution": -9,
                                             "stepBaseQuantums": 1000000,
                                             "tickSize": "0.1",
                                             "subticksPerTick": 100000}})
    monkeypatch.setattr(srv.api, "candles", lambda t, r, l: _cnd(120, 100))
    s = srv.suggest_stops("ETH-USD", "LONG", entry=100.0,
                          atr_mult_sl=1.5, atr_mult_tp=2.5)
    # constant TR=2 -> ATR=2; SL = 100-3, TP = 100+5, RR = 5/3
    assert s["stop_loss"] == 97.0 and s["take_profit"] == 105.0
    assert s["risk_reward"] == 1.67
    assert s["breakeven_after"] == 102.0


# ---------------------------------------------------------- trader_profile

def test_trader_profile_newest_first_handling(monkeypatch):
    addr = "dydx1" + "a" * 38
    # indexer convention: newest FIRST
    pnl = [
        {"createdAt": "2026-01-03T00:00:00Z", "equity": "150", "totalPnl": "40",
         "netTransfers": "10"},
        {"createdAt": "2026-01-02T00:00:00Z", "equity": "120", "totalPnl": "20",
         "netTransfers": "5"},
        {"createdAt": "2026-01-01T00:00:00Z", "equity": "100", "totalPnl": "0",
         "netTransfers": "0"},
    ]
    monkeypatch.setattr(srv.api, "account",
                        lambda a: {"subaccounts": [{"equity": "150",
                                                    "subaccountNumber": 0}]})
    monkeypatch.setattr(srv.api, "historical_pnl", lambda a, s=0, l=1000: pnl)
    monkeypatch.setattr(srv.api, "perpetual_positions",
                        lambda a, s=0: [{"status": "OPEN", "market": "X-USD",
                                         "side": "LONG", "size": "1",
                                         "entryPrice": "100",
                                         "unrealizedPnl": "5"}])
    p = srv.trader_profile(addr)
    assert p["window_start"][:10] == "2026-01-01"
    assert p["window_end"][:10] == "2026-01-03"
    assert p["equity_now"] == 150 and p["totalPnl_now"] == 40
    assert p["totalPnl_delta_window"] == 40
    assert p["open_positions"][0]["market"] == "X-USD"
