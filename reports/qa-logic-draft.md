# dydx-agent-gateway — Logical QA draft (phase 1, live)

Ticket MEC-34 · 2026-09-02 · Analyst (MECorp) · draft for TechLead/owner review — findings NOT fixed.

Scope: 59 live tools/call against the production MCP gateway `http://127.0.0.1:8901/mcp`
(3-4 varied inputs per each of the 18 tools), raw responses checkpointed to `/tmp/mec34/*.json`.
Every invariant below was recomputed **in code** (not by eye) against: (a) the gateway's own
saved snapshot, (b) fresh raw dYdX v4 indexer REST data, (c) repo math replicated from
`dydx_mcp/server.py` / `pnl_engine.py` (v0.2.4).

Verdict: **47 PASS / 0 FAIL / 5 anomalies** (47 checked invariants). No fabrication, no
chronology breaks, no rank/kind/side mix-ups found; all numeric identities reconcile to
rounding precision. The 5 anomalies are display/precision/interpretation issues, listed
individually with reproducible numbers.

## Coverage summary

| # | Tool | Live calls (inputs) | Invariant checked | Verdict |
|---|------|--------------------|-------------------|---------|
| 1 | height | ×3 (same inputs, liveness) | monotonic chain, ISO ts parse, no future ts | PASS (103872725→726→726; ts ≤ now) |
| 2 | list_markets | ×3 (limit=5 vol; limit=5 oi; limit=1) | sort key per param; limit honored; OI vs volume not swapped; cross-call OI consistency | PASS |
| 3 | market_detail | ×4 (BTC, ETH, BTC-INVALID, "") | change24h recomputed on the tool's own candle window; funding/volume vs indexer snapshot | PASS (+ ETH note below) |
| 4 | candles | ×4 (BTC 1H×30, ETH 1H×5, DOGE 1H×10, BTC 1MIN×10) | chronology (uniform spacing, no gaps/inversions), high≥max(o,c), low≤min(o,c), volume≥0 | PASS ×4 (0 violations) |
| 5 | recent_trades | ×4 (BTC×10, ETH×5, DOGE×3, BTC-INVALID) | each trade price/time inside a saved candle (±2% band) or newer than newest candle; invalid ticker → isError | PASS ×4 |
| 6 | trader_profile | ×3 (fresh discover_traders addresses) | consistency with trader_pnl_stats (equity_now / totalPnl_now / Δpnl_window) | PASS ×3 (identical to ±0.01) |
| 7 | trader_pnl_stats | ×4 (3 traders limit=1000 + t1 limit=500) | identity equityΔ=Δpnl+ΣnetTransfers (max residual), day-winrate vs daily PnL signs, maxDD recompute, points vs indexer pages | PASS ×4 (residual 0.0000) |
| 8 | registry_stats | ×2 | counters sanity (total ≥ seen_24h; scan_height ≥ max list_traders last_height); stable across calls | PASS |
| 9 | list_traders | ×3 (limit 5 / 3+max_hits=10 / 1) | limit & max_hits respected; last_height ≤ scan cursor | PASS |
| 10 | discover_traders | ×3 (min_equity 100 / 10k / 1M) | equity ≥ min_equity; registry_hits match list_traders; empty result for 1M is honest | PASS |
| 11 | leaderboard | ×4 (pnl_window / equity / day_winrate / pnl_total ×10) | descending order per declared metric; per-address values identical across metric views; farmer_flag bool; run metadata | PASS |
| 12 | latest_events | ×4 (limit=10; kind=funding_extreme / equity_jump / oi_spike_no_price) | no future timestamps; id desc; kind filter exact | PASS |
| 13 | market_digest | ×2 (+ vs standalone calls) | funding block == offline recompute of digest's own filter (min_oi=1e5, order equal); leaderboard rows == leaderboard call; 5 events == latest_events; stable across two calls | PASS |
| 14 | funding_heatmap | ×3 (limit=5; min_oi 1e6; min_oi=10) | ann == own 1h rate×24×365 on ALL rows (≤0.06pp); side flag == sign; \|1h\| desc; min_oi filter honored | PASS |
| 15 | market_ta | ×4 (BTC/ETH/DOGE 1H, BTC 1DAY) | RSI∈[0,100]; zone classification from printed RSI; %B defined & in [-0.5,1.5]; EMA/ATR recompute (EXACT on DOGE, window-drift ANOM on others) | PASS ×4 + 3 ANOM |
| 16 | suggest_stops | ×4 (BTC long; ETH short; BTC mult 1.0/3.0; DOGE long) | SL/TP distances == declared ATR mults; RR == level math; side geometry (long: SL<entry<TP, short inverse); BE=±1ATR; ATR == market_ta same window | PASS ×4 + 1 ANOM (DOGE display) |
| 17 | fills_review | ×3 (3 traders, limit=100) | maker+taker == sampled; volume & top-markets == raw indexer fills recompute | PASS ×3 (exact) |
| 18 | usage_stats | ×2 | total ≥ 7d ≥ 24h; Σtop_tools ≤ total; monotone across calls (our own 59 calls counted) | PASS |

## Anomaly blocks (for Researcher / owner verdict — not fixed)

### A1. market_ta: values drift vs a fresh recompute (BTC-USD 1H, ETH-USD 1H, BTC-USD 1DAY)

Gateway: BTC 1H `rsi=52.2 atr=474.3177 pctB=0.69 price=77408.0`; offline recompute on fresh
REST candles (fetched ~6 min after the gateway snapshot): `rsi=51.7 atr=477.8177 pctB=0.67 price=77385.0`.
ETH 1H: gateway `rsi=45.1 atr=18.3563 pctB=0.46` vs recompute `rsi=43.6 atr=18.4563 pctB=0.42`.
BTC 1DAY: gateway `rsi=65.6` vs recompute `65.5` (atr/pctB equal).

Recomputation replicates `server.py::_ema/_rsi/_atr` exactly (DOGE 1H reproduced **EXACTLY**:
`rsi 44.1==44.1, atr 0.0005==0.0005, pctB 0.38==0.38` — proof the formulas are implemented
correctly). The drift on the other three views equals the candle-window shift between the two
fetch moments (the gateway's snapshot was ~6 min older; each new 1H/1DAY candle changes
RSI/EMA/ATR inputs). Hard gates all PASS: RSI∈[0,100], zone classification matches printed RSI,
%B bounded. **Not a math bug**; flagged so consumers know two calls minutes apart may
legitimately disagree. Repro: `/tmp/mec34/phaseB1_invariants.py` (market_ta section).

### A2. suggest_stops DOGE-USD: printed fields self-inconsistent for sub-cent assets

Response: `entry=0.08 atr14=0.0005 stop_loss=0.0807 take_profit=0.0827 breakeven_after=0.082
risk_reward=1.67` and `summary="LONG DOGE-USD @ 0.08148: SL 0.08073 / TP 0.08273 (RR 1.7)"`.

Engine math on TRUE values is exact: 0.08148−1.5×0.0005=0.08073; 0.08148+2.5×0.0005=0.08273;
RR=2.5/1.5=1.67; BE=0.08148+0.0005=0.082. But the JSON fields are rounded (`_fmt` 2dp for
entry): printed entry 0.08 < printed SL 0.0807 → implied multipliers from printed fields are
nonsense (−1.4×/5.4×, RR-from-printed 3.86 vs claimed 1.67). An agent reading only the JSON
fields gets a wrong risk picture. Also ATR 4dp rounding (0.0005 vs ~0.00046) ≈ 9% quantization
of true risk. BTC/ETH unaffected (values ≫ rounding step). Owner call: higher precision for
sub-cent assets (or token-decimal-aware `_fmt`). Repro: saved record
`/tmp/mec34/29-suggest_stops_doge_long.json`.

### A3. trader_pnl_stats maxDD can exceed 100% (t3: 2711.54%)

Fresh trader `dydx1q8pg5…` (equity ~$142k): `max_drawdown_pct=2711.54`. Offline recompute on raw
indexer historical-pnl reproduces **exactly** 2711.54% — the formula is faithful to
`pnl_engine.compute` (peak-relative drawdown on the deposit-adjusted curve `equity−ΣnetTransfers`
with a near-zero peak: eq0=$9.80 → min(perf)=−$19423.28). The identity residual stays 0.0000 and
day-winrate matches (W1/L4 → 2.3%) — only the % interpretation breaks: >100% DD is not
human-meaningful. Owner call: express maxDD in USD or cap/annotate when peak ≈ 0. Repro:
`/tmp/mec34/phaseB23_invariants.py` (trader.t3 section).

### A4. Post-hoc verification limits (not gateway defects; recorded for reproducibility)

- `nextFundingRate` is a moving preview: gateway XMR row printed ann 215.2% at 18:34Z; the
  preview had drifted to 206-208% when re-checked. Formula-internal check
  (ann == own printed rate×24×365 on all 5 heatmap rows, ≤0.06pp) PASSes; exact cross-time
  equality is impossible by construction.
- `volume24H` is a rolling window: BTC 8948025 (snapshot) → 8254299 (~1 h later) = −7.7%
  window decay; volumes are positive and self-consistent across gateway calls.
- ETH 1H candle closes revise after hour close: gateway's change24h (−0.663% = 2395.8/2411.8)
  verified EXACT on its own snapshot window; the same computation on finalized candles gives
  −0.713%.
- market_ta/annualization computed from the gateway's own fetch moment — see A1.

### A5. Observed behaviors worth an owner look (no math impact)

- `list_markets` serves 296 markets (pre-v0.2.4 deploy; repo v0.2.4 filters FINAL_SETTLEMENT →
  99). Known deploy-lag from MEC-30, still present on 2026-09-02.
- `latest_events` ts has no timezone marker (`2026-09-02 18:20:51`, sqlite UTC); `trader_profile`
  window uses ISO-Z. Mixed formats inside one API surface.
- BTC/ETH `nextFundingRate_pct_1h` printed as `-0.00018`/`0.0` — the −0.0 float artifact from
  MEC-30 findings still visible in live output.

## Reproducibility

- Raw gateway responses (all 59): `/tmp/mec34/NN-<tag>.json` (+ `manifest.json`).
- Phase A collector: `/tmp/mec34/phaseA_collect.py` (one session init, checkpoint-before-next-call).
- Invariant recomputation: `/tmp/mec34/phaseB1_invariants.py`, `/tmp/mec34/phaseB23_invariants.py`
  (fresh REST calls to `indexer.dydx.trade/v4` are made by these scripts; REST is not budgeted).
- Machine-readable verdicts: `grep '^INVAR\|^ANOM'` over `/tmp/mec34/block1.log` and
  `/tmp/mec34/block23.log` → 47×`INVAR|…|PASS|`, 0×FAIL, 5×`ANOM`.

Method note: all identity/level/winrate/maxDD checks re-derive the number from raw data and
compare to the gateway value at rounding precision; "PASS" means exact or within the documented
rounding/drift tolerance, never "looks plausible".

## Researcher verdicts (MEC-35, 2026-09-02 ~19:10 UTC)

Method: 13 live calls (a portfolio across all 5 anomalies: market_ta ×3, suggest_stops DOGE,
candles DOGE/BTC 120, market_detail BTC, trader_pnl_stats t3 ×2, discover, heatmap, latest_events),
my own recomputation of the server.py formulas on the gateway's own candles, local records /tmp/mec34/*.
Format: a) reproducibility; b) a gateway bug or dYdX data; c) severity.

**A1 (market_ta drift between calls)** — (a) NOT reproducible as a bug: my recomputation
of _rsi/_atr/_ema/_pctB on 120 candles from MY OWN candles call (seconds after market_ta)
matched the gateway to the last digit: BTC 1H rsi 50.9==50.9, atr 446.8244==446.8244, pctB 0.65==0.65,
trend down==down; DOGE 1H rsi 44.1==44.1, atr 0.0004==0.0004, pctB 0.40==0.40. The Analyst's "drift"
(rsi 52.2→51.7 etc.) is a candle-window shift between two sampling moments (~6 min); every new
1H candle changes the RSI/EMA/ATR inputs. (b) a data property (rolling candles), the gateway is right.
(c) low: two calls minutes apart legitimately diverge; document it for consumers.
NOTE: the Analyst's "EXACT on DOGE" control confirms the same — the formulas are implemented correctly.

**A2 (suggest_stops DOGE, JSON fields vs summary)** — (a) reproduces: entry 0.08 (2dp)
< stop_loss 0.0808 (4dp) on a LONG; the summary "@ 0.08138: SL 0.08078 / TP 0.08238" is truthful
and the engine is right (SL=0.08138−1.5×0.0004=0.08078 ✓, TP=0.08138+2.5×0.0004=0.08238 ✓,
BE=0.08138+0.0004=0.08178≈0.0818 ✓, RR=2.5/1.5=1.67 ✓). From the PRINTED JSON fields the invariant
entry>SL for LONG breaks and the implied multipliers are meaningless: SL −2.0×, TP +6.0×
(stated 1.5×/2.5×), RR-from-printed 2.00 vs 1.67. (b) a gateway bug (_fmt rounding: entry
at 2dp for sub-cent assets), NOT dYdX data. (c) medium: an agent reading only the JSON fields
gets a wrong risk picture; BTC/ETH are unaffected (prices ≫ the rounding step).

**A3 (trader_pnl_stats maxDD 2711.54% for t3)** — (a) reproduces deterministically: same
address dydx1q8pg5…, same value 2711.54% on two windows (1000 and 500 points) ~5 min apart.
(b) formally NOT a computation bug: the identity reconciles exactly (equityΔ −8175.60 + netTransfers
+150402.19 → eq0 = $9.79 ≈ $9.80 per the draft — a near-zero curve peak); >100% DD is an artifact
of the peak-relative formula on a deposit-adjusted curve with a near-zero peak. This is
interpretational semantics of the output, not a math error. (c) medium: the 2711% figure misleads
the consumer (canonical maxDD ≤ 100%); recommendation — also report in USD
and/or annotate when the peak ≈ 0.

**A4 (moving windows: funding preview / volume24H / last-candle revision)** — (a)
reproduces as a CLASS, confirmed by three independent snapshots today: XMR ann
173.5% (MEC-30 ~17:50Z) → 215.2% (Analyst 18:34Z) → 274.2% (my call 19:04Z); the within-formula
relation held in each (274.19≈274.2 etc.). (b) a dYdX data property (preview rates
and rolling windows); the gateway correctly reflects the source. (c) low: exact cross-time
verification is impossible by construction; a documentation warning suffices.

**A5 (cosmetics: 296 markets pre-v0.2.4, mixed ts formats, −0.0)** — (a) reproduces:
ts in latest_events "2026-09-02 19:00:06" (sqlite UTC, no TZ) vs ISO-Z in trader_profile —
confirmed by a live call; −0.00018/-0.0 visible in the Analyst's records (list_markets/market_detail);
296 markets — the known deploy-lag from MEC-30 (repo v0.2.4 = 99). (b) deploy-lag and gateway
cosmetics. (c) low: does not affect calculations; fixed by deploying v0.2.4 and targeted _fmt/ts cleanup.

BOTTOM LINE: 0 of 5 anomalies are gateway math bugs; 1 display bug (A2, _fmt 2dp for sub-cents —
the only finding with an ACTIONABLE fix); 1 interpretational semantic (A3, maxDD>100%);
3 — data properties/deploy lag (A1/A4/A5). I confirm the Analyst's 47 PASS (their 47×INVAR|PASS
recomputed locally from /tmp/mec34/block*.log: 22+25, 0 FAIL — consistent with the draft).

CONFIDENCE: high — for every anomaly there is a live call + an independent recomputation; the key
A1 test (same-basis 120-candle recomputation) matched to the last digit.

Spend re-check: 13 MCP calls (within the ticket's 2-4 per contested tool:
market_ta ×3, suggest_stops ×1(+1 by Analyst), trader_pnl_stats ×3, candles ×2, +5 service
market_detail/discover/heatmap/latest_events/height-test). The gateway's REST was not used.
NOT checked: behavior on other sub-cent assets besides DOGE (the signal is already clear),
A2/A3 milestone fixes (outside the mandate — "do not fix the tools").
