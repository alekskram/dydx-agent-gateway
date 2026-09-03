# Gateway tool outputs — live snapshots (2026-09-02)

**Snapshot date: 2026-09-02.** This file shows the real output of every gateway tool (all 18),
captured during a live QA pass of gateway v0.2.4 — exactly one live call per tool against the
deployed MCP endpoint. Every number below is copied from the live QA report
(`reports/qa-v0.2.4-live.md`); nothing was invented or re-fetched. Outputs are point-in-time
snapshots: prices, funding, leaderboards and event feeds change continuously, so expect
different values when you run the same calls yourself. One caveat from that day: the live
deployment still ran pre-v0.2.4 code (e.g. `list_markets` returned 296 markets including dead
FINAL_SETTLEMENT rows, while repo v0.2.4 serves 99 ACTIVE) — noted below where it matters.

## height

Returns the latest indexed block height — the quickest liveness check for the gateway and its
indexer feed.

Call: `height()`

Observed output (2026-09-02T17:48Z):

```text
block height : 103868469
liveness     : ok
```

## list_markets

Returns the market list ranked by trading volume (descending), with per-market metadata
including the next funding rate.

Call: `list_markets(limit=200, sort="volume")`

Observed output:

```text
markets returned : 296 (live deploy, pre-v0.2.4; repo v0.2.4 ACTIVE filter serves 99)
top by volume    : ETH, BTC, SOL, ZEC, UNI
sort             : volume, descending — ok
zero-volume rows : 130 of 200 (dead markets; removed by the v0.2.4 ACTIVE filter)
cosmetic         : "-0.0" in nextFundingRate_pct_1h (float formatting artifact)
```

## market_detail

Detailed view of a single market: oracle price, honest 24h change computed from candles
(bypassing the indexer's known priceChange24H quirk), and trade counts.

Call: `market_detail(ticker="BTC-USD")`

Observed output:

```text
oracle price : 77320.81
24h change   : +0.167% (computed from candles)
trades 24h   : 4023
```

## candles

OHLCV candles (with open interest) for a market, resolutions from 1MIN to 1DAY, values as
strings. The api layer normalizes candle order to chronological (oldest → newest).

Call: `candles(ticker="BTC-USD", resolution="1HOUR", limit=24)`

Observed output:

```text
candles returned : 24
order            : chronological, oldest → newest — ok
fields           : OHLCV as strings (open interest included)
```

## recent_trades

Recent fills for a market: price, size, side.

Call: `recent_trades(ticker="BTC-USD", limit=30)`

Observed output:

```text
trades returned : 30
price range     : 77142 – 77321
consistency     : matches oracle 77320 / 77360
order types     : LIMIT only in this sample
```

## market_digest

One-call briefing: latest anomaly events + funding extremes + leaderboard top. Start here.

Call: `market_digest()`

Observed summary: 5 events, top funding XMR-USD 173.5% annualized, leaderboard #1 +$15,588.
Raw output (verbatim from the QA report):

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

> Note: `oi_now` in oi-event payloads is in **contract units, not USD** — e.g. BTC `202.2401`
> means 202.24 BTC (USD equivalent nearby: BTC OI ≈ $15.6M at that moment).

## leaderboard

Top traders for the window, ranked by `pnl_window`, with day winrate and farmer flags; only
funded/verified addresses are listed.

Call: `leaderboard()` (defaults: `limit=20`, `metric="pnl_window"`)

Observed output (run 2026-09-02T12:12Z):

```text
rows              : 18 (40 addresses checked, 18 funded)
sort              : pnl_window descending — ok
day winrate range : 27.9 – 58.1 (within [0, 100]) — ok
farmer_flag count : 0
```

Top row as embedded in the same day's `market_digest` output:

```text
address     : dydx1vg8g0rkrtv35pag20u082gj8n4k7tths7ap0zm
pnl_window  : 15587.71
equity      : 26129.12
day_winrate : 58.1
```

## latest_events

Recorded anomaly events from the detectors: `funding_extreme`, `oi_spike_no_price`,
`equity_jump`, and the liquidation-cascade detector (fresh/confirmed stages).

Call: `latest_events(limit=20)`

Observed output:

```text
events returned : 20
breakdown       : oi_spike × 12, equity_jump × 6, liq × 2
```

Example event payloads recorded the same day (from the `market_digest` call above):

```json
{"kind": "oi_spike_no_price", "subject": "BTC-USD", "oi_change_pct": -8.21, "price_change_pct": 0.471, "window_h": 6, "oi_now": 202.2401}
{"kind": "equity_jump", "subject": "dydx1ey7ghrfulgtnqeqm4mkd9w6nht9ru360ynul3g", "from": 621.99, "to": 445.19, "pct": -28.4}
```

Also recorded in the same window: a ZEC-USD liquidation cascade at stage `confirmed_6h` —
price −4.87%, OI −28.12% (LONGS), preceded by an earlier `fresh_2h` stage. The `oi_now`
contract-units note above applies to these oi-event payloads too.

## trader_profile

Account overview: equity, open positions and the analysis window.

Call: `trader_profile(address="dydx1m9hg73…")` *(the gateway's market-maker test account;
address truncated exactly as recorded in the QA report)*

Observed output:

```text
equity          : 59,943.66
open positions  : 69
analysis window : 42 days
```

## trader_pnl_stats

Daily PnL series and statistics: day-winrate, deposit-adjusted max drawdown, sharpe-like
ratio, plus the phantom-PnL detector residual from the identity
`equityΔ = Δpnl + ΣnetTransfers`.

Call: `trader_pnl_stats(address="dydx1m9hg73…")` *(same market-maker account)*

Observed output:

```text
points / window   : 1000 pts / 42 days
day winrate       : 61.9%
sharpe-like       : 0.23
max drawdown      : 13.18% (deposit-adjusted)
identity residual : $0.0
```

Deep-window reconciliation for the same account (up to 4,999 points,
2026-02-05 → 2026-09-02), from the QA report's PnL-identity check:

```text
equityΔ       : +42,962.27
Δpnl          : +134,232.11
ΣnetTransfers : −91,269.84
residual      : $0.0000
```

Without the ΣnetTransfers term the identity would be off ~3× ("profit" of 134k vs the real
+43k equity move) — the phantom-PnL detector reporting $0.0 is exactly the point.

## fills_review

Fill-level review of an account: maker/taker mix, traded volume and per-instrument counts.

Call: `fills_review(address="dydx1m9hg73…", limit=100)` *(same market-maker account)*

Observed output:

```text
fills reviewed : 100
maker share    : 6%
volume         : $8,660
avg fill       : $87
top instrument : ETHFI (94 of 100 fills)
```

## list_traders

Known trader addresses from the local registry, filtered by validator-hit count.

Call: `list_traders(limit=10, max_hits=100)`

Observed output:

```text
addresses returned : 10
validator hits     : max 86 (≤ max_hits = 100) — filter ok
```

## discover_traders

Finds funded, currently-active addresses from the onchain registry (fresh `last_seen`,
minimum equity).

Call: `discover_traders(limit=5, min_equity=100)`

Observed output:

```text
addresses returned : 5 (all funded)
equity range       : 259.79 – 2,379.72
min equity         : all ≥ 100 — ok
freshness          : last_seen < 15 min
```

## registry_stats

Health and stats of the registry scanner: address count, indexer cursor lag, 24h activity.

Call: `registry_stats()`

Observed output:

```text
addresses in registry : 2,960
indexer cursor        : 103868639 (lag < 30 blocks)
seen in 24h           : 1,268
scanner               : alive
```

## funding_heatmap

Funding rates across all markets, annualized and ranked, with a minimum-OI filter;
annualization is `1h × 24 × 365`.

Call: `funding_heatmap(limit=10, min_oi_usd=100_000)`

Observed output:

```text
rows returned : 10
OI filter     : every row ≥ $100k — ok
annualization : 1h × 24 × 365 — 0 mismatches
top row       : XMR-USD +175.6% annualized
```

Funding rows captured in the same day's `market_digest` call (same ≥ $100k OI class), for
shape:

| ticker   | funding %/1h | ann. % | OI (USD) | longs pay |
|----------|--------------|--------|----------|-----------|
| XMR-USD  | 0.0198       | 173.5  | 120,153  | yes       |
| ONDO-USD | 0.01064      | 93.2   | 107,492  | yes       |
| ALGO-USD | 0.00718      | 62.9   | 120,501  | yes       |
| BNB-USD  | 0.00394      | 34.5   | 144,240  | yes       |
| LTC-USD  | 0.00374      | 32.7   | 509,945  | yes       |

## market_ta

Technical-analysis snapshot computed from candles with zero TA dependencies: RSI, EMA trend,
ATR, Bollinger %B.

Call: `market_ta(ticker="BTC-USD")`

Observed output:

```text
RSI     : 50.6 (neutral)
trend   : down (EMA20 < EMA50)
ATR     : 0.65%
BB %B   : 0.64
```

## suggest_stops

ATR-based stop suggestion for a given side: stop-loss, take-profit, breakeven and trailing
levels plus risk/reward.

Call: `suggest_stops(ticker="BTC-USD", side="LONG")`

Observed output:

```text
entry       : 77360.5
stop loss   : 76611 (below entry — ok)
take profit : 78609 (above entry — ok)
RR          : 1.67 (= 2.5 / 1.5)
breakeven   : entry + 1 ATR — ok
```

## usage_stats

Tool-call counters since deployment — including the QA calls themselves.

Call: `usage_stats()`

Observed output:

```text
total calls  : 119
calls in 24h : 37
most called  : height (62), market_digest (15)
```

---

# v0.3.0 analyst pack (2026-09-03)

New tools funded by the same live QA pass (`reports/qa-v0.3.0-live.md`,
budget: 2 live calls per tool). Values are point-in-time snapshots.

## historical_funding

Raw 1h funding-rate history — the rates actually paid, not the next-rate
preview. Points are oldest → newest.

Call: `historical_funding(ticker="BTC-USD", limit=168)`

Observed output (2026-09-03T10Z):

```text
points   : 168 (7 days, hourly)
window   : 2026-08-27T11:00Z → 2026-09-03T10:00Z
latest   : −3.8e-07 per 1h (−0.33% annualized)
mean/max : mean +4e-08, max |rate| +4.5e-06
check    : annualized = rate × 24 × 365 — verified on all 168 points
```

## raw_fills

Raw execution tape: every indexer fill field (fee, position context), for
agents doing their own execution-quality math. Addresses from
discover_traders / leaderboard.

Call: `raw_fills(address="dydx1vg8g0rkrtv35pag20u082gj8n4k7tths7ap0zm")`

Observed output:

```text
fills     : 200 (newest first), all ETH-USD
fill[0]   : SELL 0.176 @ 2402.7, MAKER/LIMIT, fee 0.042288
            positionSide LONG, sizeBefore 34.176, entryBefore 1834.60
usd_notional per fill = price × size — recomputed, matches
```

## cvd

Cumulative volume delta from the public trades tape (+size on BUY, −size on
SELL, base units). Returns the trade window, buy/sell volumes and the last 50
running values.

Call: `cvd(ticker="BTC-USD", trades_limit=500)`

Observed output (2026-09-03T10Z):

```text
trades    : 500, window 05:00:31Z → 09:57:15Z (~5h)
buy/sell  : 9.8147 / 3.4743 BTC → CVD +6.3404 (buy-dominated tape)
check     : manual reverse+cumsum over the raw tape — exact match (1e-9)
```

## correlation

Pearson r and beta(a|b) over log returns; candle series joined by startedAt.

Call: `correlation(ticker_a="BTC-USD", ticker_b="ETH-USD")`

Observed output:

```text
candles   : 168 (1HOUR, common timestamps)
r         : 0.853   (numpy corrcoef on the same join: 0.8532)
beta(a|b) : 0.623   (numpy cov/var: 0.6227)
reading   : BTC moves ~0.62× ETH's log moves; tight majors pair
```

## market_ta — new fields (v0.3.0)

Call: `market_ta(ticker="BTC-USD", resolution="1HOUR")`

Observed output:

```text
MACD(12,26,9) : line 94.96, signal 58.10, hist +36.85 (bullish momentum)
VWAP(20)      : 77415.55 — price traded above VWAP on the snapshot
realized vol  : 29.22% annualized (pstdev of 1h log returns × √8760)
checks        : MACD/VWAP/rVol recomputed by hand on the same 120 candles — exact
```

## market_detail — basis_pct (v0.3.0)

Call: `market_detail(ticker="BTC-USD")`

Observed output:

```text
basis_pct : −0.045 (last 1MIN close 77600.4 vs oracle 77635.18)
reading   : mark traded 4.5 bps below oracle — negligible dislocation
```

## trader_pnl_stats — sortino_like_daily (v0.3.0)

Call: `trader_pnl_stats(address="dydx1vg8g…ap0zm")`

Observed output:

```text
sortino_like_daily : 0.46   (sharpe_like_daily 0.18 on the same account)
reading            : downside deviation halves the risk denominator —
                     this account's losses are concentrated in few days
```
