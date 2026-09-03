"""B1: api layer — retries, pagination, cache, candle ordering (offline)."""
import io
import json
import urllib.error

import pytest

from dydx_mcp import api


class _Resp:
    def __init__(self, payload, code=200):
        self._payload = payload
        self.status = code

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ok(payload):
    return _Resp(payload)


# ---------------------------------------------------------------- retries

def test_retry_on_429_then_success(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=25):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many",
                                         {}, io.BytesIO(b"{}"))
        return _ok({"x": 1})

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(api.time, "sleep", lambda s: None)  # no real waits
    assert api.get("test") == {"x": 1}
    assert calls["n"] == 2


def test_retry_on_urlerror_then_success(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=25):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.URLError("conn reset")
        return _ok({"ok": True})

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(api.time, "sleep", lambda s: None)
    assert api.get("test") == {"ok": True}


def test_retry_exhaustion_raises(monkeypatch):
    def fake_urlopen(req, timeout=25):
        raise urllib.error.HTTPError(req.full_url, 503, "unavail",
                                     {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(api.time, "sleep", lambda s: None)
    with pytest.raises(ValueError, match="indexer 503.*after 3 attempts"):
        api.get("test")


def test_no_retry_on_404(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=25):
        calls["n"] += 1
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found",
                                     {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ValueError, match="indexer 404"):
        api.get("test")
    assert calls["n"] == 1  # immediate raise, no retries


# ---------------------------------------------------------------- pagination

def _pnl_page(items):
    return {"historicalPnl": items}


def test_pnl_pagination_two_pages(monkeypatch):
    def item(i):
        return {"createdAt": f"2026-01-01T{i // 60:02d}:{i % 60:02d}:00Z",
                "equity": "1", "totalPnl": "1", "netTransfers": "0"}

    page1 = [item(i) for i in range(1499, 499, -1)]  # newest (1000 items)
    page2 = [item(i) for i in range(499, -1, -1)]    # strictly older (500)
    pages = [{"historicalPnl": page1}, {"historicalPnl": page2}]
    seen = []

    def fake_get(path, params=None, retries=3):
        seen.append(params)
        return pages.pop(0)

    monkeypatch.setattr(api, "get", fake_get)
    rows = api.historical_pnl("addr", limit=1500)
    assert len(rows) == 1500
    assert len(seen) == 2
    assert seen[1]["createdBeforeOrAt"] == "2026-01-01T08:20:00Z"
    assert seen[1]["limit"] == 500
    ts = [r["createdAt"] for r in rows]
    assert len(set(ts)) == len(ts)          # no boundary dupes
    assert ts == sorted(ts, reverse=True)   # monotonic newest-first


def test_pnl_pagination_stops_on_short_page(monkeypatch):
    def fake_get(path, params=None, retries=3):
        # full-width page (limit=1000 forced by want) then nothing
        if "createdBeforeOrAt" in (params or {}):
            return {"historicalPnl": []}
        return _pnl_page([{"createdAt": "2026-01-01T00:00:00Z",
                           "equity": "1", "totalPnl": "1",
                           "netTransfers": "0"}])

    monkeypatch.setattr(api, "get", fake_get)
    rows = api.historical_pnl("addr", limit=1000)
    assert len(rows) == 1  # short page -> stop, no infinite loop


def test_pnl_pagination_cap_5000(monkeypatch):
    state = {"hi": 999_999}  # descending global counter (newest-first pages)

    def fake_get(path, params=None, retries=3):
        lo = state["hi"] - params["limit"]
        items = []
        for n in range(state["hi"], lo, -1):
            items.append({"createdAt": f"2026-{1 + n // 44640:02d}-"
                                       f"{1 + n // 1440 % 31:02d}T"
                                       f"{n // 60 % 24:02d}:{n % 60:02d}:00Z",
                          "equity": "1", "totalPnl": "1", "netTransfers": "0"})
        state["hi"] = lo
        return _pnl_page(items)

    monkeypatch.setattr(api, "get", fake_get)
    assert len(api.historical_pnl("addr", limit=99999)) == 5000


# ---------------------------------------------------------------- cache/order

def test_markets_ttl_cache(monkeypatch):
    calls = {"n": 0}

    def fake_get(path, params=None, retries=3):
        calls["n"] += 1
        return {"markets": {"ETH-USD": {"oraclePrice": "1"}}}

    monkeypatch.setattr(api, "get", fake_get)
    api._MARKETS_CACHE = (-1e9, {})  # always stale (monotonic may be < TTL on fresh VMs)
    api.markets()
    api.markets()
    assert calls["n"] == 1  # second call served from cache
    api._MARKETS_CACHE = (-1e9, {})  # always stale (monotonic may be < TTL on fresh VMs)  # cleanup for other tests


def test_candles_normalized_chronological(monkeypatch):
    newest = {"startedAt": "2026-01-03T00:00:00Z", "open": "3", "close": "3"}
    oldest = {"startedAt": "2026-01-01T00:00:00Z", "open": "1", "close": "1"}
    mid = {"startedAt": "2026-01-02T00:00:00Z", "open": "2", "close": "2"}

    def fake_get(path, params=None, retries=3):
        return {"candles": [newest, oldest, mid]}  # shuffled, newest first

    monkeypatch.setattr(api, "get", fake_get)
    c = api.candles("X-USD")
    assert [x["startedAt"] for x in c] == sorted(x["startedAt"] for x in c)
