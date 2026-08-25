"""Stdlib-only client for the public dYdX v4 indexer API (no keys needed)."""
import json
import threading
import time
import urllib.error
import urllib.request

BASE = "https://indexer.dydx.trade/v4"
UA = {"User-Agent": "dydx-agent-gateway/0.1"}
_last_req = 0.0
_MIN_INTERVAL = 0.15  # ~6-7 req/s, under the 100 req/10s cap
_LOCK = threading.Lock()
_MARKETS_CACHE: tuple[float, dict] = (0.0, {})
_MARKETS_TTL = 60.0


def get(path: str, params: dict | None = None, retries: int = 3) -> dict:
    global _last_req
    qs = ""
    if params:
        qs = "?" + "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    url = f"{BASE}/{path}{qs}"
    for attempt in range(retries):
        with _LOCK:  # thread-safe politeness window
            wait = _MIN_INTERVAL - (time.monotonic() - _last_req)
            if wait > 0:
                time.sleep(wait)
            _last_req = time.monotonic()
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            # network blips/timeouts are retryable too
            if attempt < retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"unreachable: {url}")


def height() -> dict:
    return get("height")


def markets() -> dict:
    global _MARKETS_CACHE
    now = time.monotonic()
    if now - _MARKETS_CACHE[0] > _MARKETS_TTL:
        _MARKETS_CACHE = (now, get("perpetualMarkets").get("markets", {}))
    return _MARKETS_CACHE[1]


def candles(ticker: str, resolution: str = "1HOUR", limit: int = 100) -> list:
    c = get(f"candles/perpetualMarkets/{ticker}",
            {"resolution": resolution, "limit": limit}).get("candles", [])
    # indexer returns newest-first; normalize to chronological (oldest->newest)
    return sorted(c, key=lambda x: x["startedAt"])


def market_trades(ticker: str, limit: int = 50) -> list:
    return get(f"trades/perpetualMarket/{ticker}", {"limit": limit}).get("trades", [])


def historical_funding(ticker: str, limit: int = 100) -> list:
    return get("historicalFunding", {"ticker": ticker, "limit": limit}).get("historicalFunding", [])


def account(address: str) -> dict:
    return get(f"addresses/{address}")


def historical_pnl(address: str, subaccount: int = 0, limit: int = 1000) -> list:
    """Newest-first PnL series, paginated up to `limit` (cap 5000, ~7 months).
    The createdBeforeOrAt filter is INCLUSIVE, so each next page repeats the
    boundary row — those repeats are dropped (strict < cursor)."""
    want = min(limit, 5000)
    out: list = []
    cursor = None
    pages = 0
    while len(out) < want and pages < 30:  # hard loop guard
        fetch = min(1000, want - len(out))
        p = {"address": address, "subaccountNumber": subaccount, "limit": fetch}
        if cursor:
            p["createdBeforeOrAt"] = cursor
        raw = get("historical-pnl", p).get("historicalPnl", [])
        pages += 1
        if not raw:
            break
        page = [r for r in raw if cursor is None
                or r.get("createdAt", "") < cursor]
        if page:
            out.extend(page)
            cursor = page[-1].get("createdAt")  # strictly decreases
        else:
            # full raw page entirely at the boundary: jump to its OLDEST ts
            jump = min(r.get("createdAt", "") for r in raw)
            if cursor is not None and jump >= cursor:
                break  # mis-ordered data: refuse to loop
            cursor = jump
        if len(raw) < fetch:  # server ran out of history
            break
    return out[:want]


def perpetual_positions(address: str, subaccount: int = 0) -> list:
    return get("perpetualPositions",
               {"address": address, "subaccountNumber": subaccount}
               ).get("positions", [])


def transfers(address: str, subaccount: int = 0, limit: int = 100) -> list:
    return get("transfers",
               {"address": address, "subaccountNumber": subaccount, "limit": limit}
               ).get("transfers", [])


def fills(address: str, subaccount: int = 0, limit: int = 100) -> list:
    return get("fills",
               {"address": address, "subaccountNumber": subaccount, "limit": limit}
               ).get("fills", [])
