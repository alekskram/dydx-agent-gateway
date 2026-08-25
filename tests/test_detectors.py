"""B2: detectors — thresholds, signs, stages, guards (offline, mocked api)."""
from dydx_mcp import analytics, detectors


def _mkts(**over):
    base = {
        "BIG-USD": {"oraclePrice": "2", "volume24H": "1000000",
                    "openInterest": "100000", "nextFundingRate": "0.004"},
        "TINY-USD": {"oraclePrice": "2", "volume24H": "500000",
                     "openInterest": "100", "nextFundingRate": "0.005"},
        "ZERO-USD": {"oraclePrice": "2", "volume24H": "900000",
                     "openInterest": "100000", "nextFundingRate": "0"},
    }
    base.update(over)
    return base


def _candles(n, oi0, oi1, p0, p1, step_oi=True):
    """n chronological candles linearly interpolating OI and price."""
    out = []
    for i in range(n):
        f = i / (n - 1)
        oi = oi0 + (oi1 - oi0) * f
        px = p0 + (p1 - p0) * f
        out.append({"startedAt": f"2026-01-01T00:{i:02d}:00Z",
                    "startingOpenInterest": str(oi),
                    "open": str(px), "close": str(px),
                    "high": str(px), "low": str(px)})
    return out


# ------------------------------------------------------- funding_extremes

def test_funding_extreme_respects_oi_floor(monkeypatch):
    monkeypatch.setattr(detectors.api, "markets", lambda: _mkts())
    evs = detectors.funding_extremes()
    # BIG: 0.4%/h ≈ 3504%/ann, OI $200k -> event; TINY same rate but OI $200 -> skip
    assert [e["ticker"] for e in evs] == ["BIG-USD"]
    assert evs[0]["longs_pay"] is True


def test_funding_extreme_negative_side(monkeypatch):
    m = _mkts()
    m["BIG-USD"]["nextFundingRate"] = "-0.004"
    monkeypatch.setattr(detectors.api, "markets", lambda: m)
    evs = detectors.funding_extremes()
    assert evs[0]["longs_pay"] is False


# ------------------------------------------------------ oi_spike_no_price

def test_oi_spike_positive_flat_price(monkeypatch):
    m = _mkts()
    monkeypatch.setattr(detectors.api, "markets", lambda: m)
    monkeypatch.setattr(detectors.api, "candles",
                        lambda t, r, l: _candles(7, 100, 106.5, 10, 10.02))
    evs = detectors.oi_spike_without_price()
    assert evs and evs[0]["ticker"] == "BIG-USD"
    assert evs[0]["oi_change_pct"] > 5


def test_oi_spike_requires_flat_price(monkeypatch):
    monkeypatch.setattr(detectors.api, "markets", lambda: _mkts())
    monkeypatch.setattr(detectors.api, "candles",
                        lambda t, r, l: _candles(7, 100, 112, 10, 10.5))
    assert detectors.oi_spike_without_price() == []


# --------------------------------------------------- liquidation_signature

def test_liq_cascade_fresh_2h_longs(monkeypatch):
    monkeypatch.setattr(detectors.api, "markets", lambda: _mkts())
    monkeypatch.setattr(detectors.api, "candles",
                        lambda t, r, l: (_candles(25, 100000, 94000, 10, 9.75)
                                         if r == "5MINS" else
                                         _candles(7, 100000, 90000, 10, 10.2)))
    evs = detectors.liquidation_signature()
    assert evs and evs[0]["stage"] == "fresh_2h"
    assert evs[0]["side_liquidated"] == "LONGS"


def test_liq_cascade_confirmed_6h_shorts(monkeypatch):
    monkeypatch.setattr(detectors.api, "markets", lambda: _mkts())
    # fresh window calm (OI flat), 6h window: pump +4% with OI -8% -> shorts
    monkeypatch.setattr(detectors.api, "candles",
                        lambda t, r, l: (_candles(25, 100000, 100500, 10, 10.1)
                                         if r == "5MINS" else
                                         _candles(7, 100000, 92000, 10, 10.42)))
    evs = detectors.liquidation_signature()
    assert evs and evs[0]["stage"] == "confirmed_6h"
    assert evs[0]["side_liquidated"] == "SHORTS"


def test_liq_cascade_zero_oi_guard(monkeypatch):
    monkeypatch.setattr(detectors.api, "markets", lambda: _mkts())
    monkeypatch.setattr(detectors.api, "candles",
                        lambda t, r, l: _candles(25, 0, 0, 10, 5))
    assert detectors.liquidation_signature() == []


# ------------------------------------------------------------ equity_jumps

def test_equity_jump_threshold_and_recovery(monkeypatch):
    from dydx_mcp import registry
    A, B = "dydx1" + "a" * 38, "dydx1" + "b" * 38
    monkeypatch.setattr(registry, "recent",
                        lambda n, max_hits=100: [{"address": A}, {"address": B}])
    acct = {"subaccounts": [{"equity": "2000", "subaccountNumber": 0}]}

    def fake_account(addr):
        if addr == B:
            raise RuntimeError("probe failed")  # mid-batch failure
        return acct

    monkeypatch.setattr(detectors.api, "account", fake_account)
    with analytics.con() as c:  # seed previous snapshot: A had $1000
        c.execute("INSERT INTO equity_snapshots VALUES(?,?,?)",
                  (A, "2026-01-01 00:00:00", 1000.0))
    n = detectors.equity_jumps(min_equity=500, threshold_pct=25)
    assert n == 1  # A jumped +100%; B failure didn't kill the batch
    evs = analytics.latest_events(5, "equity_jump")
    assert evs and evs[0]["subject"] == A and evs[0]["payload"]["pct"] == 100.0
