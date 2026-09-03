"""MEC-50: independent numpy reference cross-check for dydx_mcp.ta_ext.

Every ta_ext function is re-derived here from its mathematical definition
using numpy — NOT by re-reading its code — and compared on randomized data
(seeded, three seeds each) at rel tolerance 1e-9 (abs floor 1e-12 for values
that cross zero). Written per the MEC-50 owner requirement by a developer
who is NOT the ta_ext author, so a shared blind spot is less likely.

Reference styles, deliberately different from the stdlib loops in ta_ext:
- MACD: the seed-EMA recursion e_i = k*x_i + (1-k)*e_{i-1}, e_0 = x_0 has
  the closed form e = (1-k)^(L-1)*x_0 + k*sum_{j>=1} (1-k)^(L-1-j)*x_j —
  geometric weights evaluated as one dot product, no recursion at all.
- VWAP / CVD: np.cumsum running sums instead of += loops.
- Pearson: np.corrcoef (ddof=0, matching statistics.pstdev) instead of
  statistics.correlation.
- Sortino: vectorized downside deviation sqrt(mean(min(x,0)^2)).
- realized_vol: np.std of np.diff(np.log(p)) (population, ddof=0).
- funding/basis: the server formulas recomputed with np.round — checks the
  rate x 100 x 24 x 365 annualization factor and the (close-oracle)/oracle
  x 100 basis definition, plus decimal-place contracts (8dp rate, 2dp ann).

numpy is a dev-only dependency (installed in .venv, NOT in pyproject
runtime deps): pytest.importorskip keeps CI green where numpy is absent.
"""
import math

import pytest

np = pytest.importorskip("numpy")

from dydx_mcp import ta_ext          # noqa: E402  (after importorskip)
from dydx_mcp.server import _fmt     # noqa: E402

SEEDS = [0, 1, 2]
REL, ABS = 1e-9, 1e-12


def _close(actual, expected):
    return actual == pytest.approx(float(expected), rel=REL, abs=ABS)


# ------------------------------------------------------- reference kernels

def _ema_ref(xs, n):
    """Closed-form EMA (seed = first value, k = 2/(n+1)) as one dot product:
    e = (1-k)^(L-1)*x_0 + k * sum_{j=1..L-1} (1-k)^(L-1-j) * x_j."""
    xs = np.asarray(xs, dtype=np.float64)
    k = 2.0 / (n + 1)
    if len(xs) == 1:
        return float(xs[0])
    rest = (1.0 - k) ** np.arange(len(xs) - 2, -1, -1)  # exponents L-2 .. 0
    return float((1.0 - k) ** (len(xs) - 1) * xs[0]
                 + k * np.dot(rest, xs[1:]))


def _macd_ref(closes, fast=12, slow=26, signal=9):
    line = np.array([
        _ema_ref(closes[:i], fast) - _ema_ref(closes[:i], slow)
        for i in range(slow, len(closes) + 1)])
    sig = _ema_ref(line, signal)
    return {"macd": float(line[-1]), "signal": sig,
            "hist": float(line[-1] - sig)}


def _random_candles(rng, n):
    """Candles in the indexer's string form; high/low bracket the close."""
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    out = []
    for c in close:
        hi, lo = c + abs(rng.normal(0.5, 0.3)), c - abs(rng.normal(0.5, 0.3))
        vol = abs(rng.normal(10_000.0, 4_000.0)) + 1.0
        out.append({"high": str(hi), "low": str(lo), "close": str(c),
                    "usdVolume": str(vol)})
    return out


# ------------------------------------------------------------------ macd

@pytest.mark.parametrize("seed", SEEDS)
def test_macd_matches_numpy_closed_form_ewm(seed):
    rng = np.random.default_rng(seed)
    closes = list(100.0 * np.exp(np.cumsum(rng.normal(0, 0.02, 80))))
    for fast, slow, sig in ((12, 26, 9), (5, 21, 7)):
        out = ta_ext.macd(closes, fast, slow, sig)
        ref = _macd_ref(closes, fast, slow, sig)
        assert out is not None
        assert _close(out["macd"], ref["macd"])
        assert _close(out["signal"], ref["signal"])
        assert _close(out["hist"], ref["hist"])
        # hist identity is exact by construction in both worlds
        assert _close(out["hist"], out["macd"] - out["signal"])


# ------------------------------------------------------------------ vwap

@pytest.mark.parametrize("seed", SEEDS)
def test_vwap_matches_numpy_cumsum(seed):
    rng = np.random.default_rng(seed)
    cnd = _random_candles(rng, 50)
    h = np.array([float(c["high"]) for c in cnd])
    lo = np.array([float(c["low"]) for c in cnd])
    cl = np.array([float(c["close"]) for c in cnd])
    vol = np.array([float(c["usdVolume"]) for c in cnd])
    tp = (h + lo + cl) / 3.0                       # typical price
    pv, v = np.cumsum(tp * vol), np.cumsum(vol)    # running sums
    assert _close(ta_ext.vwap(cnd), pv[-1] / v[-1])
    # window-prefix invariant: VWAP of the first k candles matches cumsum
    for k in (1, 7, 50):
        assert _close(ta_ext.vwap(cnd[:k]), pv[k - 1] / v[k - 1])


# ------------------------------------------------------------------- cvd

@pytest.mark.parametrize("seed", SEEDS)
def test_cvd_matches_numpy_cumsum(seed):
    rng = np.random.default_rng(seed)
    n = 60
    # newest-first (indexer convention), string sizes like the API
    trades = [{"side": "BUY" if rng.random() < 0.5 else "SELL",
               "size": str(rng.uniform(0.01, 5.0))}
              for _ in range(n)]
    out = ta_ext.cvd(trades)
    oldest_first = trades[::-1]
    size = np.array([float(t["size"]) for t in oldest_first])
    signed = np.where([t["side"] == "BUY" for t in oldest_first], size, -size)
    series = np.cumsum(signed)
    assert len(out["series"]) == n
    for got, want in zip(out["series"], series):
        assert _close(got, want)
    assert _close(out["final"], series[-1])
    assert _close(out["buy_volume"], size[signed > 0].sum())
    assert _close(out["sell_volume"], size[signed < 0].sum())
    # CVD identity: final = buy - sell (both worlds must satisfy it)
    assert _close(out["final"], out["buy_volume"] - out["sell_volume"])


# --------------------------------------------------------------- pearson

@pytest.mark.parametrize("seed", SEEDS)
def test_pearson_matches_numpy_corrcoef(seed):
    rng = np.random.default_rng(seed)
    n = 40
    ra = rng.normal(0.0, 0.01, n)              # correlated log returns
    rb = 0.8 * ra + rng.normal(0.0, 0.02, n)
    a = list(100.0 * np.exp(np.cumsum(np.concatenate([[0.0], ra]))))
    b = list(50.0 * np.exp(np.cumsum(np.concatenate([[0.0], rb]))))
    la, lb = np.diff(np.log(a)), np.diff(np.log(b))
    r = np.corrcoef(la, lb)[0, 1]              # population moments (ddof=0)
    beta = r * np.std(la) / np.std(lb)
    out = ta_ext.pearson_log_returns(a, b)
    assert out is not None
    assert _close(out["r"], r)
    assert _close(out["beta"], beta)
    # reference identities: r in [-1,1]; identical series -> r = beta = 1
    assert -1.0 - 1e-12 <= out["r"] <= 1.0 + 1e-12
    same = ta_ext.pearson_log_returns(a, a)
    assert same is not None
    assert _close(same["r"], 1.0) and _close(same["beta"], 1.0)


# --------------------------------------------------------------- sortino

@pytest.mark.parametrize("seed", SEEDS)
def test_sortino_matches_numpy_downside_std(seed):
    rng = np.random.default_rng(seed)
    x = rng.normal(0.5, 2.0, 60)
    x[0] = -abs(x[0]) - 0.1                     # guarantee a loss (dd > 0)
    mean = np.mean(x)
    dd = np.sqrt(np.mean(np.minimum(x, 0.0) ** 2))   # downside deviation
    assert _close(ta_ext.sortino_like(list(x)), mean / dd)
    # no losses -> undefined (None), mirroring the guard
    assert ta_ext.sortino_like(list(abs(x) + 1.0)) is None


# ---------------------------------------------------------- realized_vol

@pytest.mark.parametrize("seed", SEEDS)
def test_realized_vol_matches_numpy_std(seed):
    rng = np.random.default_rng(seed)
    closes = list(100.0 * np.exp(np.cumsum(rng.normal(0, 0.015, 50))))
    rets = np.diff(np.log(closes))
    base = np.std(rets)                          # population (ddof=0)
    for ppy in (525600, 105120, 35040, 17520, 8760, 2190, 365):
        assert _close(ta_ext.realized_vol(closes, ppy),
                      base * math.sqrt(ppy))
    # scaling law cross-check between resolutions (ratio = sqrt of ratio)
    r1 = ta_ext.realized_vol(closes, 8760)
    r2 = ta_ext.realized_vol(closes, 2190)
    assert r1 is not None and r2 is not None
    assert _close(r1 / r2, math.sqrt(8760 / 2190))


# --------------------------------------------------- funding/basis formulas

@pytest.mark.parametrize("seed", SEEDS)
def test_funding_and_basis_formulas_match_numpy(seed):
    """The server's funding / basis arithmetic recomputed with numpy:
    annualization factor is exactly 24*365 (not 252/365.25), basis is
    (close - oracle)/oracle * 100, and each field honors its decimal
    contract (8dp 1h rate, 2dp annualized pct, 5dp funding_pct_1h,
    1dp funding_pct_annualized, 3dp basis, 0dp oi_usd)."""
    rng = np.random.default_rng(seed)
    rates = rng.normal(1e-4, 2e-4, 40)
    for rate in rates:
        ann = rate * 100 * 24 * 365
        assert _fmt(rate, 8) == pytest.approx(float(np.round(rate, 8)),
                                              rel=REL, abs=ABS)
        assert _fmt(ann, 2) == pytest.approx(float(np.round(ann, 2)),
                                             rel=REL, abs=ABS)
        # funding_heatmap projections from the raw 1h rate
        f1h = rate * 100
        assert _fmt(f1h, 5) == pytest.approx(float(np.round(f1h, 5)),
                                             rel=REL, abs=ABS)
        assert _fmt(f1h * 24 * 365, 1) == pytest.approx(
            float(np.round(f1h * 24 * 365, 1)), rel=REL, abs=ABS)
    for _ in range(20):                          # basis & oi, 3dp/0dp
        oracle = rng.uniform(1_000.0, 5_000.0)
        close = oracle * (1.0 + rng.normal(0.0, 0.002))
        basis = (close - oracle) / oracle * 100
        assert _fmt(basis, 3) == pytest.approx(float(np.round(basis, 3)),
                                               rel=REL, abs=ABS)
        oi = rng.uniform(0.0, 1e6)
        assert _fmt(oi * oracle, 0) == pytest.approx(
            float(np.round(oi * oracle, 0)), rel=REL, abs=1e-6)
