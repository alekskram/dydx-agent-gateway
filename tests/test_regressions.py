"""review: regression tests for v0.2.4 crashes found in review/review —
None fields from the indexer (TypeError in pnl_engine / digest / leaderboard
summary formatting), ZeroDivisionError on single-point PnL windows, and
FINAL_SETTLEMENT (dead) markets leaking into market listings and the
funding heatmap. Expected RED until the fix branch merges; must be GREEN
after. Mocks follow tests/test_server.py (srv.api monkeypatch) and
tests/test_analytics.py (direct sqlite INSERT)."""
from dydx_mcp import analytics, api
from dydx_mcp import server as srv
from dydx_mcp.pnl_engine import compute


# ------------------------------------------------------------ pnl_engine

def test_pnl_engine_none_fields():
    """REGRESSION review: compute() raised TypeError (float(None)) when the
    indexer returns rows with equity/totalPnl/netTransfers = None."""
    rows = [
        {"createdAt": "2026-01-02T00:00:00Z", "equity": "120",
         "totalPnl": "20", "netTransfers": "5"},
        {"createdAt": "2026-01-03T00:00:00Z", "equity": None,
         "totalPnl": None, "netTransfers": None},
    ]
    d = compute(rows)  # must not raise
    assert isinstance(d, dict) and "summary" in d


def test_pnl_engine_single_point_no_zero_division():
    """REGRESSION review: compute() raised ZeroDivisionError in summary
    (wins/len(days)) when the PnL window has a single daily point."""
    rows = [{"createdAt": "2026-01-01T00:00:00Z", "equity": "100",
             "totalPnl": "0", "netTransfers": "0"}]
    d = compute(rows)  # must not raise
    assert isinstance(d, dict) and d["days"] == 0


# --------------------------------------------------------- market_digest

def test_market_digest_null_pnl_window(monkeypatch):
    """REGRESSION review: market_digest() raised TypeError formatting a
    leaderboard row with pnl_window=None (f"+${None:,.0f}") — review."""
    monkeypatch.setattr(srv, "funding_heatmap",
                        lambda *a, **k: {"top": []})
    monkeypatch.setattr(srv, "leaderboard",
                        lambda *a, **k: {"top": [{
                            "address": "A" * 40, "pnl_window": None,
                            "equity": 100.0, "day_winrate": None}]})
    monkeypatch.setattr(analytics, "latest_events", lambda *a, **k: [])
    d = srv.market_digest()  # must not raise
    assert isinstance(d, dict)
    assert d["leaderboard_top"][0]["pnl_window"] is None


# ------------------------------------------------------- analytics store

def test_analytics_leaderboard_null_metric_summary():
    """REGRESSION review: analytics.leaderboard() raised TypeError in
    summary (f"${None:,.0f}") when the top row's metric column is NULL."""
    with analytics.con() as c:
        c.execute("DELETE FROM leaderboard_runs")
        c.execute("DELETE FROM leaderboard_rows")
        c.execute("INSERT INTO leaderboard_runs VALUES(1,'t',1,1)")
        c.execute(
            "INSERT INTO leaderboard_rows VALUES(1,?,?,?,?,?,?,?,?,?,?)",
            ("D" * 40, 100.0, 5.0, None, 40.0, 10.0, 50.0, 100.0, 0, 0.1))
    lb = analytics.leaderboard(limit=1, metric="pnl_window")  # must not raise
    assert len(lb["top"]) == 1
    assert lb["top"][0]["pnl_window"] is None


# ------------------------------------------------- dead-market filtering

def test_api_markets_filters_final_settlement(monkeypatch):
    """REGRESSION review: api.markets() leaked FINAL_SETTLEMENT (delisted)
    markets into listings and the funding heatmap, where their garbage
    extreme funding polluted rankings."""
    def fake_get(path, params=None, retries=3):
        return {"markets": {
            "BTC-USD": {"status": "ACTIVE", "oraclePrice": "100",
                        "volume24H": "1", "openInterest": "1",
                        "nextFundingRate": "0.001"},
            "DEAD-USD": {"status": "FINAL_SETTLEMENT", "oraclePrice": "50",
                         "volume24H": "0", "openInterest": "1",
                         "nextFundingRate": "0.05"},
        }}

    monkeypatch.setattr(api, "get", fake_get)
    monkeypatch.setattr(api, "_MARKETS_CACHE", (0.0, {}))  # bust TTL cache
    assert set(api.markets()) == {"BTC-USD"}

    # same data through the server tools
    assert srv.list_markets()["count_total"] == 1
    heat = srv.funding_heatmap(min_oi_usd=0)  # let both past the OI filter
    tickers = [r["ticker"] for r in heat["top"]]
    assert "DEAD-USD" not in tickers
    assert tickers == ["BTC-USD"]  # DEAD's 5%/1h must not rank first
