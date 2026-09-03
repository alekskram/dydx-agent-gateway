"""MEC-50 (v0.3.0): ta_ext invariant tests — manual recomputation on
mini-samples ("logical QA" method). Offline only: pure functions over lists.

Two corrections vs the ticket's example numbers (formulas kept as specified):
- VWAP sample: (10*1+20*2+30*3)/(1+2+3) = 140/6 = 23.333... (not 25.0).
- pearson: closes_b = 2*closes_a gives IDENTICAL log returns (scale cancels
  in ln), so beta = 1.0; beta = 0.5 needs doubled-magnitude returns
  (closes_b = closes_a**2 -> rb = 2*ra).
"""
import math
import statistics

import pytest

from dydx_mcp import ta_ext
from dydx_mcp.server import _ema


# ---------------------------------------------------------------- macd

def test_macd_flat_series_zero():
    closes = [100.0] * 40
    out = ta_ext.macd(closes)
    assert out is not None
    assert out["macd"] == 0.0 and out["signal"] == 0.0 and out["hist"] == 0.0


def test_macd_rising_series_positive():
    closes = [100.0 + i for i in range(40)]
    out = ta_ext.macd(closes)
    assert out is not None
    assert out["macd"] > 0 and out["hist"] > 0


def test_macd_matches_direct_ema_recomputation():
    closes = [100.0 * (1.01 ** i) * (1 if i % 3 else 0.99) for i in range(50)]
    out = ta_ext.macd(closes)
    assert out is not None
    assert out["macd"] == pytest.approx(_ema(closes, 12) - _ema(closes, 26))
    # signal is the seed-EMA9 over the macd line -> hist identity holds exactly
    assert out["hist"] == pytest.approx(out["macd"] - out["signal"])


def test_macd_not_enough_data():
    assert ta_ext.macd([1.0] * 34) is None  # 34 < 26 + 9


# ---------------------------------------------------------------- vwap

def test_vwap_manual_three_candles():
    cnd = [
        {"high": "12", "low": "6", "close": "12", "usdVolume": "1"},   # tp 10
        {"high": "24", "low": "12", "close": "24", "usdVolume": "2"},  # tp 20
        {"high": "36", "low": "18", "close": "36", "usdVolume": "3"},  # tp 30
    ]
    expected = (10 * 1 + 20 * 2 + 30 * 3) / (1 + 2 + 3)  # 140/6
    assert expected == pytest.approx(140 / 6)             # guard the manual math
    assert ta_ext.vwap(cnd) == pytest.approx(expected)


def test_vwap_zero_volume_none():
    cnd = [{"high": "12", "low": "6", "close": "12", "usdVolume": "0"}] * 3
    assert ta_ext.vwap(cnd) is None


# ---------------------------------------------------------------- realized_vol

def test_realized_vol_flat_zero():
    assert ta_ext.realized_vol([50.0] * 10, 525600) == 0.0


def test_realized_vol_manual_invariant():
    closes = [100.0, 110.0, 105.0, 120.75, 108.0]
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    for ppy in (525600, 35040, 8760, 365):
        assert ta_ext.realized_vol(closes, ppy) == pytest.approx(
            statistics.pstdev(rets) * math.sqrt(ppy))


def test_realized_vol_two_points_valid():
    rv = ta_ext.realized_vol([100.0, 110.0], 365)
    r = math.log(1.1)  # single return -> pstdev of one sample is 0
    assert rv == pytest.approx(0.0) and math.isfinite(r)


def test_realized_vol_nonpositive_close_none():
    assert ta_ext.realized_vol([100.0, 0.0, 110.0], 365) is None
    assert ta_ext.realized_vol([100.0], 365) is None


# ---------------------------------------------------------------- cvd

def test_cvd_manual_three_trades():
    trades = [  # newest-first (indexer convention)
        {"side": "BUY", "size": "1", "price": "10"},
        {"side": "BUY", "size": "3", "price": "11"},
        {"side": "SELL", "size": "2", "price": "9"},
    ]
    out = ta_ext.cvd(trades)  # oldest->newest: SELL2, BUY3, BUY1
    assert out["series"] == pytest.approx([-2.0, 1.0, 2.0])
    assert out["final"] == pytest.approx(2.0)
    assert out["buy_volume"] == pytest.approx(4.0)
    assert out["sell_volume"] == pytest.approx(2.0)
    assert out["final"] == pytest.approx(out["buy_volume"] - out["sell_volume"])


def test_cvd_unknown_side_raises():
    with pytest.raises(ValueError):
        ta_ext.cvd([{"side": "LONG", "size": "1"}])


def test_cvd_empty():
    out = ta_ext.cvd([])
    assert out == {"series": [], "final": 0.0,
                   "buy_volume": 0.0, "sell_volume": 0.0}


# ---------------------------------------------------------------- pearson/beta

def test_pearson_identical_series():
    closes = [100.0, 102.0, 101.0, 105.0, 107.0, 104.0]
    out = ta_ext.pearson_log_returns(closes, closes)
    assert out is not None
    assert out["r"] == pytest.approx(1.0)
    assert out["beta"] == pytest.approx(1.0)


def test_pearson_scaled_series_scale_invariant():
    # b = 2*a: log returns identical (scale cancels in ln) -> beta 1.0
    a = [100.0, 102.0, 101.0, 105.0, 107.0]
    out = ta_ext.pearson_log_returns(a, [2 * x for x in a])
    assert out is not None
    assert out["r"] == pytest.approx(1.0)
    assert out["beta"] == pytest.approx(1.0)


def test_pearson_beta_half_on_doubled_returns():
    # b = a^2 -> rb = 2*ra -> beta(a|b) = 1 * sa/sb = 0.5
    a = [2.0, 2.2, 2.1, 2.4, 2.6]
    out = ta_ext.pearson_log_returns(a, [x * x for x in a])
    assert out is not None
    assert out["r"] == pytest.approx(1.0)
    assert out["beta"] == pytest.approx(0.5)


def test_pearson_opposite_series():
    # b = 1/a: rb = ln((1/p_t)/(1/p_{t-1})) = -ra exactly -> r = -1.0
    # (plain negation does NOT work: sign cancels in the log ratio)
    a = [100.0, 102.0, 101.0, 105.0, 107.0]
    out = ta_ext.pearson_log_returns(a, [1 / x for x in a])
    assert out is not None
    assert out["r"] == pytest.approx(-1.0)


def test_pearson_mismatched_length_raises():
    with pytest.raises(ValueError):
        ta_ext.pearson_log_returns([1.0, 2.0, 3.0], [1.0, 2.0])


def test_pearson_too_short_and_flat_none():
    assert ta_ext.pearson_log_returns([1.0, 2.0], [1.0, 2.0]) is None
    flat = [5.0] * 12  # zero std on side a -> None
    assert ta_ext.pearson_log_returns(flat, [5.0, 6.0, 5.5, 6.2] * 3) is None


# ---------------------------------------------------------------- sortino

def test_sortino_manual():
    # [10, -5, 10, -5]: mean 2.5, dd = sqrt((0+25+0+25)/4) = sqrt(12.5)
    expected = 2.5 / math.sqrt(12.5)
    assert ta_ext.sortino_like([10.0, -5.0, 10.0, -5.0]) == pytest.approx(
        expected, abs=1e-9)
    assert expected == pytest.approx(0.7071067811865476, abs=1e-9)


def test_sortino_all_positive_none():
    assert ta_ext.sortino_like([1.0, 2.0, 3.0]) is None
    assert ta_ext.sortino_like([]) is None


# ---------------------------------------------------------------- periods

@pytest.mark.parametrize("res,expected", [
    ("1MIN", 525600), ("5MIN", 105120), ("15MIN", 35040), ("30MIN", 17520),
    ("1HOUR", 8760), ("4HOURS", 2190), ("1DAY", 365),
])
def test_periods_per_year_table(res, expected):
    assert ta_ext.periods_per_year(res) == expected


def test_periods_per_year_unknown_raises():
    with pytest.raises(ValueError):
        ta_ext.periods_per_year("7MIN")
