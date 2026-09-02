"""MEC-43 (v0.2.5) regressions for the logical-QA findings:

- A2: suggest_stops / market_ta printed prices broke level geometry and ATR
  multipliers for sub-cent assets (DOGE entry rounded to 0.08 while SL printed
  0.0807 — impossible for a LONG; qa-logic.md A2).
- A3: trader_pnl_stats maxDD — peak-relative pct misleads when the
  deposit-adjusted curve's running peak at the worst drawdown is near zero
  (t3: 2711.54%); needs max_drawdown_usd + dd_pct_unreliable (MEC-44 spec).

Mocks follow tests/test_server.py (srv.api monkeypatch). PnL rows are
newest-first (the indexer convention), as in test_regressions.py."""
from dydx_mcp import server as srv
from dydx_mcp.pnl_engine import compute


# --------------------------------------------------------------- A2 helpers

def _candles(n, base, atr):
    """Constant-TR candles (TR = atr exactly: high = close + atr, low =
    close): Wilder ATR(14) converges to `atr` and stays there."""
    return [{"startedAt": f"2026-01-01T{i // 60:02d}:{i % 60:02d}:00Z",
             "open": str(base), "close": str(base),
             "high": str(base + atr), "low": str(base)}
            for i in range(n)]


def _doge_api(monkeypatch, price="0.08148", atr=0.0005):
    monkeypatch.setattr(srv.api, "markets",
                        lambda: {"DOGE-USD": {"oraclePrice": price}})
    monkeypatch.setattr(srv.api, "candles",
                        lambda t, r, l: _candles(120, float(price), atr))


# --------------------------------------------------------- A2: suggest_stops

def test_a2_suggest_stops_sub_cent_geometry(monkeypatch):
    """DOGE-like LONG (entry 0.08148, ATR 0.0005): printed fields must keep
    SL < entry < TP and the implied multipliers must equal the declared
    1.5 / 2.5 (qa-logic.md A2: v0.2.4 printed entry 0.08 < SL 0.0807)."""
    _doge_api(monkeypatch)
    s = srv.suggest_stops("DOGE-USD", "LONG", atr_mult_sl=1.5,
                          atr_mult_tp=2.5)
    e, a, sl, tp = s["entry"], s["atr14"], s["stop_loss"], s["take_profit"]
    assert sl < e < tp, (sl, e, tp)
    assert abs((e - sl) / a - 1.5) < 0.05, (e, sl, a)
    assert abs((tp - e) / a - 2.5) < 0.05, (tp, e, a)
    # RR recomputed from printed fields matches the claimed risk_reward
    assert abs((tp - e) / (e - sl) - s["risk_reward"]) < 0.02


def test_a2_suggest_stops_sub_cent_class(monkeypatch):
    """The whole sub-cent class (qa-logic A2 repro set + a PEPE-like
    extreme): multiplier geometry must hold from printed fields alone."""
    for price, atr in [(0.08148, 0.0005),   # qa-logic.md saved record
                       (0.08138, 0.0004),   # Researcher fresh repro
                       (0.0123, 0.00008),
                       (0.00001234, 0.00000008)]:
        _doge_api(monkeypatch, price=str(price), atr=atr)
        s = srv.suggest_stops("DOGE-USD", "LONG", atr_mult_sl=1.5,
                              atr_mult_tp=2.5)
        e, a, sl, tp = s["entry"], s["atr14"], s["stop_loss"], s["take_profit"]
        assert sl < e < tp, (price, sl, e, tp)
        assert abs((e - sl) / a - 1.5) < 0.05, (price, e, sl, a)
        assert abs((tp - e) / a - 2.5) < 0.05, (price, tp, e, a)


def test_a2_suggest_stops_short_inverse_geometry(monkeypatch):
    """Sub-cent SHORT: TP < entry < SL and multipliers still readable."""
    _doge_api(monkeypatch)
    s = srv.suggest_stops("DOGE-USD", "SHORT", atr_mult_sl=1.5,
                          atr_mult_tp=2.5)
    e, a, sl, tp = s["entry"], s["atr14"], s["stop_loss"], s["take_profit"]
    assert tp < e < sl, (tp, e, sl)
    assert abs((sl - e) / a - 1.5) < 0.05 and abs((e - tp) / a - 2.5) < 0.05


def test_a2_suggest_stops_btc_unchanged(monkeypatch):
    """BTC-scale prices keep the legacy prints (entry 2dp, ATR/SL/TP 4dp)."""
    monkeypatch.setattr(srv.api, "markets",
                        lambda: {"BTC-USD": {"oraclePrice": "77408"}})
    monkeypatch.setattr(srv.api, "candles",
                        lambda t, r, l: _candles(120, 77408.0, 446.8244))
    s = srv.suggest_stops("BTC-USD", "LONG", atr_mult_sl=1.5,
                          atr_mult_tp=2.5)
    assert s["entry"] == 77408.0 and s["atr14"] == 446.8244
    assert s["stop_loss"] == 76737.7634 and s["take_profit"] == 78525.061


def test_a2_fmt_price_vectors():
    """_fmt_price: 6-significant-digit floor for sub-cent values, legacy
    `step` as the minimum, non-numeric passthrough like _fmt."""
    f = srv._fmt_price
    assert f(2445.5) == 2445.5            # 2dp legacy floor (6sig needs 2)
    assert f(0.08148) == 0.08148          # full sub-cent precision kept
    assert f(0.08148, 4) == 0.08148       # explicit step honored (>= 4dp)
    assert f(0.00001234) == 0.00001234    # PEPE-like: 6 sig digits visible
    assert f("n/a") == "n/a"              # passthrough, as _fmt
    assert f(None) is None


# ------------------------------------------------------------- A3: maxDD

def _row(day, eq, pnl, ntr="0"):
    return {"createdAt": f"2026-{day}T00:00:00Z", "equity": eq,
            "totalPnl": pnl, "netTransfers": ntr}


def test_a3_maxdd_usd_and_flag_t3(monkeypatch=None):
    """t3 shape (qa-logic.md A3 / MEC-44): deposit-adjusted running peak
    ~$744, deep negative trough, current equity ~$142k -> pct in the
    2711%-class (live t3 figure: 2711.54), max_drawdown_usd present,
    dd_pct_unreliable True via the <1%-of-equity branch ($744 < $1,422).
    Synthetic pins clean 2dp inputs (pct 2711.60 on peak $743.75)."""
    rows = [  # newest first, as the indexer returns
        _row("09-01", "142236.38", "764586.17"),
        _row("08-20", "-18723.78", "-19423.78"),
        _row("07-10", "1443.75", "44", "700"),
        _row("07-01", "9.80", "0"),
    ]
    d = compute(rows)
    assert d["max_drawdown_pct"] == 2711.6
    assert d["max_drawdown_usd"] == 20167.53
    assert d["dd_pct_unreliable"] is True


def test_a3_flag_first_branch_tiny_peak():
    """MEC-44 case: running peak $0.50 (< $1 branch) with current equity
    $40; the 1%-of-equity branch alone would need peak < $0.40, so this
    isolates the near-zero-peak branch."""
    rows = [
        _row("07-03", "40", "-0.10", "39.5"),
        _row("07-02", "0.20", "-0.30"),
        _row("07-01", "0.50", "0"),
    ]
    d = compute(rows)
    assert d["dd_pct_unreliable"] is True
    assert d["max_drawdown_usd"] == 0.3


def test_a3_no_flag_healthy_curve():
    """Healthy deposit-adjusted curve: no flag, USD depth equals the known
    30% drawdown of the 140 -> 110 perf curve."""
    rows = [
        _row("01-03", "110", "10"),
        _row("01-02", "140", "40"),
        _row("01-01", "100", "0"),
    ]
    d = compute(rows)
    assert d["max_drawdown_pct"] == 21.43
    assert d["max_drawdown_usd"] == 30.0
    assert d["dd_pct_unreliable"] is False
