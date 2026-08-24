"""Market detectors -> event bus (funding extremes, OI spikes without price)."""
from . import api, analytics

FUNDING_ANN_THRESHOLD = 300.0   # |annualized| % that triggers an event
MIN_OI_USD = 100_000.0          # liquidity floor: smaller markets are noise
OI_TOP_MARKETS = 20             # check top-N markets by volume
OI_MOVE_PCT = 5.0               # OI change over window, %
PRICE_MOVE_PCT = 0.5            # ...while price stays within, %


def funding_extremes() -> list[dict]:
    out = []
    for t, m in api.markets().items():
        f1h = float(m.get("nextFundingRate", 0) or 0)
        ann = f1h * 100 * 24 * 365
        oi_usd = float(m.get("openInterest", 0) or 0) * float(m.get("oraclePrice") or 0)
        if abs(ann) >= FUNDING_ANN_THRESHOLD and oi_usd >= MIN_OI_USD:
            ev = {"ticker": t, "funding_pct_1h": round(f1h * 100, 5),
                  "annualized_pct": round(ann, 1), "oi_usd": round(oi_usd, 0),
                  "longs_pay": f1h > 0, "price": m.get("oraclePrice")}
            analytics.add_event("funding_extreme", t, ev)
            out.append(ev)
    return out


def oi_spike_without_price(window: int = 6) -> list[dict]:
    """OI moved >OI_MOVE_PCT over `window` hours while price moved <PRICE_MOVE_PCT:
    someone quietly built a position."""
    ms = api.markets()
    top = sorted(ms.items(), key=lambda kv: -float(kv[1].get("volume24H", 0) or 0))[:OI_TOP_MARKETS]
    out = []
    for t, _ in top:
        try:
            cnd = api.candles(t, "1HOUR", window + 1)
        except Exception:  # noqa: BLE001
            continue
        if len(cnd) < window + 1:
            continue
        oi0, oi1 = float(cnd[0]["startingOpenInterest"]), float(cnd[-1]["startingOpenInterest"])
        p0, p1 = float(cnd[0]["open"]), float(cnd[-1]["close"])
        if not (oi0 and p0):
            continue
        doi = (oi1 / oi0 - 1) * 100
        dp = (p1 / p0 - 1) * 100
        if abs(doi) >= OI_MOVE_PCT and abs(dp) < PRICE_MOVE_PCT:
            ev = {"ticker": t, "oi_change_pct": round(doi, 2),
                  "price_change_pct": round(dp, 3), "window_h": window,
                  "oi_now": oi1}
            analytics.add_event("oi_spike_no_price", t, ev)
            out.append(ev)
    return out


def liquidation_signature() -> list[dict]:
    """Cascade signature from candles (no public liquidations feed on the
    mainnet indexer): a sharp price move together with an OI collapse means
    forced closures. Fresh (2h/5MINS): |dp|>=1.5% & dOI<=-4%.
    Confirmed (6h/1HOUR): |dp|>=3% & dOI<=-6%."""
    ms = api.markets()
    top = sorted(ms.items(), key=lambda kv: -float(kv[1].get("volume24H", 0) or 0))[:OI_TOP_MARKETS]
    out = []
    for t, _ in top:
        try:
            c5 = api.candles(t, "5MINS", 25)   # ~2h
            c1 = api.candles(t, "1HOUR", 7)    # 6h
        except Exception:  # noqa: BLE001
            continue
        stage = None
        dp = doi = oi_usd = None
        if len(c5) >= 25:
            p0, p1 = float(c5[0]["open"]), float(c5[-1]["close"])
            o0, o1 = float(c5[0]["startingOpenInterest"]), float(c5[-1]["startingOpenInterest"])
            oi_usd = o1 * p1
            if p0 and o0 and oi_usd >= MIN_OI_USD:
                dp = (p1 / p0 - 1) * 100
                doi = (o1 / o0 - 1) * 100
                if abs(dp) >= 1.5 and doi <= -4:
                    stage = "fresh_2h"
        if stage is None and len(c1) >= 7:
            p0, p1 = float(c1[0]["open"]), float(c1[-1]["close"])
            o0, o1 = float(c1[0]["startingOpenInterest"]), float(c1[-1]["startingOpenInterest"])
            oi_usd = o1 * p1
            if p0 and o0 and oi_usd >= MIN_OI_USD:
                dp = (p1 / p0 - 1) * 100
                doi = (o1 / o0 - 1) * 100
                if abs(dp) >= 3 and doi <= -6:
                    stage = "confirmed_6h"
        if stage:
            ev = {"ticker": t, "stage": stage,
                  "price_change_pct": round(dp, 2), "oi_change_pct": round(doi, 2),
                  "oi_usd": round(oi_usd, 0),
                  "side_liquidated": "LONGS" if dp < 0 else "SHORTS"}
            analytics.add_event("liq_cascade_signature", t, ev)
            out.append(ev)
    return out


def equity_jumps(n_candidates: int = 25, min_equity: float = 500.0,
                 threshold_pct: float = 25.0) -> int:
    """Compare live equity of recent registry traders vs previous snapshot
    (5-minute cadence). |change| >= threshold_pct on a funded account is an
    event: a whale moved capital in or out."""
    from datetime import datetime, timezone
    from . import registry
    cands = registry.recent(n_candidates, max_hits=100)
    con = analytics.con()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n = 0
    for c in cands:
        addr = c["address"]
        try:
            acct = api.account(addr)
        except Exception:  # noqa: BLE001
            continue
        eq = max((float(s.get("equity", 0) or 0)
                  for s in acct.get("subaccounts", [])), default=0.0)
        prev = con.execute("SELECT equity FROM equity_snapshots "
                           "WHERE address=? ORDER BY ts DESC LIMIT 1",
                           (addr,)).fetchone()
        con.execute("INSERT INTO equity_snapshots VALUES(?,?,?)", (addr, ts, eq))
        if prev and prev["equity"] >= min_equity:
            pct = (eq / prev["equity"] - 1) * 100
            if abs(pct) >= threshold_pct:
                analytics.add_event("equity_jump", addr,
                                    {"from": round(prev["equity"], 2),
                                     "to": round(eq, 2),
                                     "pct": round(pct, 1)}, con)
                n += 1
    con.commit()
    con.close()
    return n


def run_all() -> dict:
    f = funding_extremes()
    o = oi_spike_without_price()
    l = liquidation_signature()
    e = equity_jumps()
    return {"funding_extremes": len(f), "oi_spikes": len(o),
            "liq_cascades": len(l), "equity_jumps": e}
