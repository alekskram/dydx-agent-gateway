# Live-QA v0.2.4 — 18 tools, PnL identity, detectors

Date: 2026-09-02 · Author: Analyst (review) · Gateway: http://127.0.0.1:8901/mcp
(Streamable HTTP, session init) · Rule: exactly one live call per tool.

Deploy note: the live service on 8901 still runs pre-v0.2.4 code
(`list_markets` returns 296 markets = 197 FINAL_SETTLEMENT still present;
repo v0.2.4 code serves 99). v0.2.4 logic (ACTIVE filter, NULL policy) was
verified offline on repo code over live indexer data — no second online pass.
Live deploy may lag the repo until the next systemd restart.

## 1. Tools: 18/18 ok, 0 errors

| # | Tool | Result | Notes |
|---|---|---|---|
| 1 | height | 103868469 @ 2026-09-02T17:48Z | liveness ok |
| 2 | list_markets | 296 markets, top by volume ETH/BTC/SOL/ZEC/UNI, desc sort ✓ | Live deploy is pre-v0.2.4: 130 of 200 rows zero-volume (dead markets). Repo v0.2.4: 99 markets. Cosmetic: `-0.0` in nextFundingRate_pct_1h |
| 3 | market_detail BTC-USD | oracle 77320.81; change24h **+0.167% from candles**; trades24h 4023 | units ok; priceChange computed from candles (known priceChange24H gotcha handled) |
| 4 | candles BTC-USD 24×1H | 24 candles, chronological oldest→newest ✓, OHLCV strings | newest-first normalization done in the api layer |
| 5 | recent_trades BTC-USD | 30 trades, px 77142–77321 vs oracle 77320/77360 — consistent | LIMIT-only in this sample |
| 6 | market_digest | 5 events, funding top XMR 173.5% ann, lb#1 +$15,588 | raw output archived below (section 4) |
| 7 | leaderboard | 18 rows, pnl_window desc ✓, winrate 27.9–58.1 ∈ [0,100] ✓, farmer_flag: 0 | run 2026-09-02T12:12Z, checked 40, funded 18; no NULL-pnl rows (v0.2.4 guard not exercised — not needed) |
| 8 | latest_events | 20: oi_spike×12, equity_jump×6, liq×2 | dedup/retention work; ts in sqlite format |
| 9 | trader_profile MM | equity 59,943.66; 69 open positions; 42-day window | |
| 10 | trader_pnl_stats MM | 1000 pts/42 days; winrate 61.9%; sharpe 0.23; maxDD 13.18%; **residual $0.0** | v0.2.4 crash-guards not exercised (data complete) |
| 11 | fills_review MM | 100 fills; maker 6%; vol $8,660; avg $87; top ETHFI 94/100 | bot-like activity profile; consistent with leaderboard |
| 12 | list_traders | 10 addresses, hits ≤ 86 ≤ max_hits=100 ✓ | validator filter works |
| 13 | discover_traders | 5 funded, equity 259.79–2,379.72, all ≥ min_equity=100 ✓ | live, last_seen < 15 min |
| 14 | registry_stats | 2,960 addresses; cursor 103868639 (lag < 30 blocks); 1,268 seen/24h | scanner alive |
| 15 | funding_heatmap | 10 rows (≥$100k OI); oi_usd ≥ min ✓; ann = 1h×24×365 ✓ (0 mismatches) | top XMR +175.6% ann |
| 16 | market_ta BTC-USD | RSI 50.6 neutral; trend down (EMA20<EMA50); ATR 0.65%; BB%B 0.64 | sane for a range-bound tape |
| 17 | suggest_stops BTC LONG | entry 77360.5; SL 76611 < entry < TP 78609 ✓; RR 1.67=2.5/1.5 ✓; BE=entry+1ATR ✓ | ATR math checks out |
| 18 | usage_stats | 119 total; 37/24h; top: height 62, market_digest 15 | counter works (incl. my calls) |

NULL policy (v0.2.4): no NULL-pnl/None-crash cases appeared in live data
(offline regression suite green — v0.2.4 guards in repo).

## 2. PnL identity: 9 accounts, residual $0.0000 everywhere

Identity: equityΔ = Δpnl + ΣnetTransfers (netTransfers is per-bucket flow,
NOT cumulative). Discrepancy reported as % of |equityΔ| (move scale).

Fresh traders (window 2026-08-19 → 2026-09-02, 350 pts; addresses from live
discover_traders):

| Address | equityΔ | Δpnl | ΣnetTransfers | Residual | Discrepancy |
|---|---|---|---|---|---|
| dydx1plnflaf… | −16.15 | −43.21 | +27.06 | $0.0000 | 0.0000% |
| dydx1ld35hvl… | −431.66 | −431.66 | 0 | $0.0000 | 0.0000% |
| dydx1k5m7val… | +1,146.31 | +752.85 | +393.46 | $0.0000 | 0.0000% |
| dydx1rxpnld4… | −27.78 | −27.78 | 0 | $0.0000 | 0.0000% |
| dydx1qtumyhx… | +21.85 | +21.85 | 0 | $0.0000 | 0.0000% |
| dydx1vg8g0rk… (lb #1) | +17,099.62 | +17,099.62 | 0 | $0.0000 | 0.0000% |

Deep window (up to 4,999 pts, 2026-02-05 → 2026-09-02):

| Address | equityΔ | Δpnl | ΣnetTransfers | Residual |
|---|---|---|---|---|
| dydx1m9hg73… (MM, gateway test) | +42,962.27 | +134,232.11 | **−91,269.84** | $0.0000 |
| dydx1plnflaf… (deposits) | +244.94 | −98.00 | +342.94 | $0.0000 |
| dydx1vg8g0rk… (lb #1) | +23,271.01 | +21,665.83 | +1,605.18 | $0.0000 |

Key case MM: without the ΣnetTransfers term the identity would be off ~3×
(134k "profit" vs the real +43k equity move) — the gateway's phantom-PnL
detector (identity_max_residual_usd) reports $0.0 on the live account.
Total: 9/9 reconciliations agree, max discrepancy < 10⁻⁶% (float precision
limit). Matches the monthly watchdog report (29/29 < $0.01 for 2026-08).

## 3. Detectors: the v0.2.4 dead-market filter did not kill sensitivity

Compared on a single live indexer snapshot (2026-09-02 ~17:50 UTC):
"before" = raw 296 markets, "after" = 99 ACTIVE (v0.2.4 code).

- funding_extreme (300% ann threshold, OI ≥ $100k): events 0 → 0. Removed 0, lost 0.
  Max among ACTIVE: XMR-USD +178.9% ann — below threshold; proximity confirmed
  by heatmap/digest (173.5–175.6% across two live calls).
- Why the filter belongs in code, not just the OI threshold: 197 FINAL_SETTLEMENT
  markets, 176 of them with nonzero (frozen ~10.9% ann) funding, but 0 with
  OI ≥ $100k today. The threshold removes them only in the current window;
  the ACTIVE filter removes the class entirely (plus 226 zero-vol rows from
  list_markets and detector inputs).
- oi_spike_no_price / liq_cascade: the top-20 by volume is 100% ACTIVE;
  detector sample identical before/after. Recorded events reproduced from raw
  candles: BTC −8.21%/+0.47%, ETH −8.59%/+0.36% (payload match exact);
  ZEC-USD liq cascade confirmed_6h: px −4.87%, OI −28.12% (LONGS) plus an
  earlier fresh_2h stage — a real deleveraging case, detector caught it.
- equity_jump: live example dydx1ey7…: 621.99 → 445.19 (−28.4%). Cause
  (withdrawal/loss) is not distinguishable from the digest — known caveat,
  confidence: fact high, cause unknown.
- No active signatures at snapshot time (top-20 recheck: 0 signatures) — quiet
  tape; sensitivity judged from the window's recorded events.

Conclusion: after v0.2.4 the detectors are not blinded — in the current window
the OI threshold and the status filter cut exactly the same dead class; live
signals (ZEC liq, BTC/ETH OI, equity jumps) pass through.

## 4. Raw market_digest (source of truth for README / examples)

```json
{"events": [
  {"kind": "oi_spike_no_price", "subject": "BTC-USD", "ticker": "BTC-USD", "oi_change_pct": -8.21, "price_change_pct": 0.471, "window_h": 6, "oi_now": 202.2401},
  {"kind": "oi_spike_no_price", "subject": "ETH-USD", "ticker": "ETH-USD", "oi_change_pct": -8.59, "price_change_pct": 0.362, "window_h": 6, "oi_now": 5362.864},
  {"kind": "oi_spike_no_price", "subject": "NEAR-USD", "ticker": "NEAR-USD", "oi_change_pct": -10.6, "price_change_pct": -0.377, "window_h": 6, "oi_now": 33910.0},
  {"kind": "oi_spike_no_price", "subject": "TRX-USD", "ticker": "TRX-USD", "oi_change_pct": -7.25, "price_change_pct": 0.028, "window_h": 6, "oi_now": 539600.0},
  {"kind": "equity_jump", "subject": "dydx1ey7ghrfulgtnqeqm4mkd9w6nht9ru360ynul3g", "from": 621.99, "to": 445.19, "pct": -28.4}],
 "funding": [
  {"ticker": "XMR-USD", "funding_pct_1h": 0.0198, "funding_pct_annualized": 173.5, "oi_usd": 120153.0, "longs_pay": true, "oraclePrice": 519.2},
  {"ticker": "ONDO-USD", "funding_pct_1h": 0.01064, "funding_pct_annualized": 93.2, "oi_usd": 107492.0, "longs_pay": true, "oraclePrice": 0.34},
  {"ticker": "ALGO-USD", "funding_pct_1h": 0.00718, "funding_pct_annualized": 62.9, "oi_usd": 120501.0, "longs_pay": true, "oraclePrice": 0.09},
  {"ticker": "BNB-USD", "funding_pct_1h": 0.00394, "funding_pct_annualized": 34.5, "oi_usd": 144240.0, "longs_pay": true, "oraclePrice": 687.35},
  {"ticker": "LTC-USD", "funding_pct_1h": 0.00374, "funding_pct_annualized": 32.7, "oi_usd": 509945.0, "longs_pay": true, "oraclePrice": 49.52}],
 "leaderboard_top": [
  {"address": "dydx1vg8g0rkrtv35pag20u082gj8n4k7tths7ap0zm", "pnl_window": 15587.71, "equity": 26129.12, "day_winrate": 58.1},
  {"address": "dydx1cysrhj32q4hrh7j9ec92chxlcqk6e9gwtk2ts7", "pnl_window": 4698.97, "equity": 6482.76, "day_winrate": 55.8},
  {"address": "dydx12ar5c446txrnel3y2mlhr4w4vdqf7cm9fd2ycm", "pnl_window": 2359.26, "equity": 15314.37, "day_winrate": 27.9}],
 "summary": "events: 5 | extreme funding: XMR-USD 173.5% ann | leaderboard #1: dydx1vg8g0… +$15,588"}
```

README example note: `oi_now` in oi-event payloads is in contract units
(BTC 202.24 = 202 BTC), not USD (USD equivalent nearby: BTC OI ≈ $15.6M).
