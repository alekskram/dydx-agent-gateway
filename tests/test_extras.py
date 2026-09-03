"""Coverage top-up: registry queries, remaining server tools, signer utils."""
import sqlite3

from dydx_mcp import analytics, registry, server as srv, signer


# ---------------------------------------------------------------- registry

def _seed_registry():
    with sqlite3.connect(registry.DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS addresses(
            address TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT,
            hits INTEGER, last_height INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS meta(
            k TEXT PRIMARY KEY, v TEXT)""")
        c.execute("DELETE FROM addresses")
        rows = [("dydx1" + "a" * 38, "2026-01-01", "2026-01-02", 5, 100),
                ("dydx1" + "b" * 38, "2026-01-01", "2026-01-03", 500, 200),
                ("dydx1" + "c" * 38, "2026-01-01", "2026-01-04", 9, 300)]
        c.executemany("INSERT INTO addresses VALUES(?,?,?,?,?)", rows)
        c.execute("INSERT OR REPLACE INTO meta VALUES('cursor','300')")


def test_registry_recent_filters_committers():
    _seed_registry()
    res = registry.recent(10, max_hits=100)
    assert res["count"] == res["total"] and not res["has_more"]
    addrs = [r["address"] for r in res["traders"]]
    assert "dydx1" + "b" * 38 not in addrs       # 500 hits = committer
    assert addrs[0] == "dydx1" + "c" * 38        # newest last_height first
    st = registry.stats()
    assert st["addresses_total"] == 3 and st["scanned_up_to_height"] == 300


def test_registry_discover_probes_equity(monkeypatch):
    _seed_registry()

    def fake_account(addr):
        eq = "150" if addr.endswith("a" * 38) else "5"
        return {"subaccounts": [{"equity": eq, "subaccountNumber": 0}]}

    monkeypatch.setattr("dydx_mcp.api.account", fake_account)
    out = registry.discover(limit=5, min_equity=100, probe_max=3, max_hits=100)
    assert len(out) == 1 and out[0]["equity"] == 150.0


# ----------------------------------------------------------------- server

def test_list_markets_sort_and_summary(monkeypatch):
    monkeypatch.setattr(srv.api, "markets", lambda: {
        "A-USD": {"oraclePrice": "1", "volume24H": "50", "openInterest": "10",
                  "nextFundingRate": "0"},
        "B-USD": {"oraclePrice": "1", "volume24H": "900", "openInterest": "5",
                  "nextFundingRate": "0"}})
    r = srv.list_markets(limit=2)
    assert r["count_total"] == 2
    assert [m["ticker"] for m in r["markets"]] == ["B-USD", "A-USD"]


def test_market_detail_unknown_ticker_raises():
    import dydx_mcp.api as api
    import pytest
    orig = api.markets
    api.markets = lambda: {}
    try:
        with pytest.raises(ValueError):  # isError per MCP spec
            srv.market_detail("NOPE-USD")
    finally:
        api.markets = orig


def test_market_detail_change24h(monkeypatch):
    cnd = [{"startedAt": f"2026-01-01T{i:02d}:00:00Z", "open": str(100 + i),
            "close": str(100 + i), "high": "0", "low": "0"} for i in range(25)]
    monkeypatch.setattr(srv.api, "markets",
                        lambda: {"X-USD": {"oraclePrice": "124", "openInterest": "1",
                                           "nextFundingRate": "0", "volume24H": "1",
                                           "trades24H": "1"}})
    monkeypatch.setattr(srv.api, "candles", lambda t, r, l: cnd)
    d = srv.market_detail("X-USD")
    assert d["change24h_pct_from_candles"] == 24.0  # 100 -> 124


def test_fills_review(monkeypatch):
    fills = [{"liquidity": "MAKER", "market": "A", "size": "1", "price": "10"},
             {"liquidity": "TAKER", "market": "A", "size": "2", "price": "10"},
             {"liquidity": "MAKER", "market": "B", "size": "1", "price": "100"}]
    monkeypatch.setattr(srv.api, "fills", lambda a, s=0, l=100: fills)
    r = srv.fills_review("dydx1" + "a" * 38)
    assert r["fills_sampled"] == 3
    assert r["maker_share_pct"] == 66.7
    assert r["sampled_volume_USD"] == 130.0
    assert r["top_markets"][0] == ("A", 2)


# ----------------------------------------------------------------- signer

def test_sign_api_credentials_deterministic():
    sk = signer.key_from_hex("01")
    a = signer.sign_api_credentials(sk, timestamp_ms=123)
    b = signer.sign_api_credentials(sk, timestamp_ms=123)
    assert a == b and a["timestamp"] == 123


def test_convertbits_roundtrip():
    data = bytes(range(20))
    five = signer._convertbits(data, 8, 5)
    back = bytes(signer._convertbits(five, 5, 8, pad=False))
    assert back == data
