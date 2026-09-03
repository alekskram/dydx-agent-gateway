# QA v0.3.0 "analyst pack" — live pass (2026-09-03)

Scope: 4 new tools (`historical_funding`, `raw_fills`, `cvd`, `correlation`)
+ 3 enrichments (`market_ta` MACD/VWAP/realized-vol, `market_detail`
basis_pct, `trader_pnl_stats` sortino_like_daily). Budget discipline: exactly
2 live calls per new tool (1 for the tool-output snapshot + 1 raw re-fetch for
the independent recompute) — same method as `qa-v0.2.4-live.md`.
Offline suite first: **108 passed, 5 deselected** (baseline v03-base: 63).

## New tools — live checks

| # | Tool | Call | Observed | Independent recompute |
|---|---|---|---|---|
| 1 | historical_funding | BTC-USD, limit=168 | 168 points, 2026-08-27T11Z → 2026-09-03T10Z, latest rate −3.8e-07 (−0.33% ann) | annualization `rate*100*24*365` re-derived on all 168 points: 0 mismatches (tol 0.01pp); points chronological (oldest→newest) ✓ |
| 2 | raw_fills | trader dydx1vg8g…ap0zm, limit=200 | 200 fills, all ETH-USD; per-fill fields incl. fee, positionSide/Size/entryPriceBefore | passthrough vs raw indexer JSON: price/size/side/liquidity/fee unchanged; usd_notional = price×size recomputed ✓ |
| 3 | cvd | BTC-USD, trades_limit=500 | 500 trades, window 05:00:31Z → 09:57:15Z, buy 9.8147 / sell 3.4743 → final +6.3404 BTC | full manual recompute from the raw trades tape (reverse + cumsum ±size): final/buy/sell/series_last all match to 1e-9 ✓ |
| 4 | correlation | BTC-USD × ETH-USD, 1HOUR, 168 | r=0.853, beta(a|b)=0.623, 168 candles | numpy `corrcoef` + `cov/var` on join-by-startedAt closes: r 0.8532, beta 0.6227 — matches at 3dp ✓; candles_used = 168 common timestamps ✓ |

## Enrichments — live checks

| Enrichment | Observed (BTC-USD 1HOUR) | Independent recompute (same window) |
|---|---|---|
| market_ta MACD(12,26,9) | macd_line 94.9564, signal 58.1021, hist +36.8543 | manual seed-EMA over the same 120 closes: 94.956404 — exact ✓ |
| market_ta VWAP(20) | 77415.5511 | Σ(typical×usdVolume)/Σ(usdVolume) last 20 candles: 77415.5511 — exact ✓ |
| market_ta realized_vol | 29.22% ann | pstdev(log-returns)×√8760×100 on same closes: 29.223 ✓ |
| market_detail basis_pct | −0.045% | (close_1m − oracle)/oracle×100 recomputed at snapshot time ✓ |
| trader_pnl_stats sortino | 0.46 (sharpe 0.18, same account) | mean/downside-dev over daily PnL — recomputed offline in test_compute_sortino_manual ✓ |

Note on method: an initial numpy cross-check of MACD/rVol against a separately
fetched 168-candle window showed a ~1.2pp / 0.05 discrepancy — traced to the
QA harness comparing different windows (120-candle tool window vs 168-candle
re-fetch, plus candle roll between calls), not to the tool math. Re-running
the recompute in-process on the identical window gives exact matches (above).

## API findings (fixed in this release)

- `historicalFunding?ticker=X` (query-param form) → **404** on mainnet; the
  ticker must ride in the path: `/v4/historicalFunding/{ticker}`. The old
  api.py silently returned `[]` (404 body has no `historicalFunding` key).
- `fills` requires an explicit `subaccountNumber` — omitting it returns an
  empty list rather than defaulting to 0 (api.fills already sent it).
- `perpetualMarkets` rows carry no `price` field (oracle only) — basis_pct is
  computed from the latest 1MIN candle close instead.

## Tool-output snapshot

Real outputs of all new tools + enrichments are appended to
`examples/tool-output.md` (v0.3.0 section), captured from this pass.
Raw evidence: `/tmp/mec50/` (tool_outputs.json, raw_trades.json,
raw_candles.json) — kept for audit, not committed.
