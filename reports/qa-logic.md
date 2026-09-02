# dydx-agent-gateway — Logical QA report (final)

Ticket review (phase 3 of review) · 2026-09-02 · Analyst  · final report for
TechLead/maintainer review — findings NOT fixed, no code was touched.

## Method and headline counters

- **Phase 1 (review, Analyst):** 59 live calls against the production MCP gateway
  `http://127.0.0.1:8901/mcp` — 3–4 varied inputs per each of the 18 tools; raw responses
  checkpointed to `/tmp/mec34/NN-<tag>.json` (+ `manifest.json`).
- Every invariant was recomputed **in code** (not by eye) against: (a) the gateway's own saved
  snapshot, (b) fresh raw dYdX v4 indexer REST data, (c) repo math replicated from
  `dydx_mcp/server.py` / `pnl_engine.py` (v0.2.4). "PASS" means exact match or within the
  documented rounding/drift tolerance — never "looks plausible".
- **Phase 2 (review, Researcher):** independent re-verification — 13 further live calls across
  all 5 anomalies, own same-basis recompute of `server.py` formulas on the gateway's own
  candles, plus the checkpointed records. Verdicts per anomaly: reproducibility /
  gateway-bug-vs-dydx-data / severity.
- **Final counters: 47 PASS / 0 FAIL / 5 anomalies** (47 checked invariants; 22 + 25 across the
  two recompute logs, cross-checked by `grep '^INVAR\|^ANOM'` over `/tmp/mec34/block1.log`,
  `block23.log`). Total live MCP calls across both phases: 72.
- None of the 5 anomalies is a math bug: 1 display/rounding bug (A2), 1 output-semantics issue
  (A3), 3 data/deploy behaviors (A1, A4, A5). No fabrication, no chronology breaks, no
  rank/kind/side mix-ups; all numeric identities reconcile to rounding precision.

## Main table: tool → calls (inputs) → invariant → verdict + recompute

| # | Tool | Live calls (inputs) | Invariant checked | Verdict + recompute |
|---|------|--------------------|-------------------|---------------------|
| 1 | height | ×3 (same inputs, liveness) | monotonic chain, ISO ts parse, no future ts | PASS (103872725→726→726; ts ≤ now) |
| 2 | list_markets | ×3 (limit=5 vol; limit=5 oi; limit=1) | sort key per param; limit honored; OI vs volume not swapped; cross-call OI consistency | PASS (recompute exact; 296 markets = deploy lag, see A5) |
| 3 | market_detail | ×4 (BTC, ETH, BTC-INVALID, "") | change24h recomputed on the tool's own candle window; funding/volume vs indexer snapshot | PASS (change24h −0.663% = 2395.8/2411.8 EXACT on own window; finalized-candle value differs — see A4) |
| 4 | candles | ×4 (BTC 1H×30, ETH 1H×5, DOGE 1H×10, BTC 1MIN×10) | chronology (uniform spacing, no gaps/inversions), high≥max(o,c), low≤min(o,c), volume≥0 | PASS ×4 (0 violations) |
| 5 | recent_trades | ×4 (BTC×10, ETH×5, DOGE×3, BTC-INVALID) | each trade price/time inside a saved candle (±2% band) or newer than newest candle; invalid ticker → isError | PASS ×4 |
| 6 | trader_profile | ×3 (fresh discover_traders addresses) | consistency with trader_pnl_stats (equity_now / totalPnl_now / Δpnl_window) | PASS ×3 (identical to ±0.01) |
| 7 | trader_pnl_stats | ×4 (3 traders limit=1000 + t1 limit=500) | identity equityΔ=Δpnl+ΣnetTransfers (max residual), day-winrate vs daily PnL signs, maxDD recompute, points vs indexer pages | PASS ×4 (residual 0.0000; maxDD semantics → A3) |
| 8 | registry_stats | ×2 | counters sanity (total ≥ seen_24h; scan_height ≥ max list_traders last_height); stable across calls | PASS |
| 9 | list_traders | ×3 (limit 5 / 3+max_hits=10 / 1) | limit & max_hits respected; last_height ≤ scan cursor | PASS |
| 10 | discover_traders | ×3 (min_equity 100 / 10k / 1M) | equity ≥ min_equity; registry_hits match list_traders; empty result for 1M is honest | PASS |
| 11 | leaderboard | ×4 (pnl_window / equity / day_winrate / pnl_total ×10) | descending order per declared metric; per-address values identical across metric views; farmer_flag bool; run metadata | PASS |
| 12 | latest_events | ×4 (limit=10; kind=funding_extreme / equity_jump / oi_spike_no_price) | no future timestamps; id desc; kind filter exact | PASS (ts format → A5) |
| 13 | market_digest | ×2 (+ vs standalone calls) | funding block == offline recompute of digest's own filter (min_oi=1e5, order equal); leaderboard rows == leaderboard call; 5 events == latest_events; stable across two calls | PASS |
| 14 | funding_heatmap | ×3 (limit=5; min_oi 1e6; min_oi=10) | ann == own 1h rate×24×365 on ALL rows (≤0.06pp); side flag == sign; \|1h\| desc; min_oi filter honored | PASS (preview drift across time → A4) |
| 15 | market_ta | ×4 (BTC/ETH/DOGE 1H, BTC 1DAY) | RSI∈[0,100]; zone classification from printed RSI; %B defined & in [−0.5,1.5]; EMA/ATR recompute | PASS ×4 + ANOM (window drift A1; same-basis recompute EXACT per Researcher) |
| 16 | suggest_stops | ×4 (BTC long; ETH short; BTC mult 1.0/3.0; DOGE long) | SL/TP distances == declared ATR mults; RR == level math; side geometry (long: SL<entry<TP, short inverse); BE=±1ATR; ATR == market_ta same window | PASS ×4 + ANOM (DOGE display rounding A2) |
| 17 | fills_review | ×3 (3 traders, limit=100) | maker+taker == sampled; volume & top-markets == raw indexer fills recompute | PASS ×3 (exact) |
| 18 | usage_stats | ×2 | total ≥ 7d ≥ 24h; Σtop_tools ≤ total; monotone across calls (our own 59 calls counted) | PASS |

## Anomaly blocks (recompute + Researcher verdict)

### A1. market_ta: values drift between calls minutes apart (BTC-USD 1H, ETH-USD 1H, BTC-USD 1DAY)

**Recompute (Analyst, phase 1).** Gateway BTC 1H `rsi=52.2 atr=474.3177 pctB=0.69 price=77408.0`;
offline recompute on fresh REST candles fetched ~6 min after the gateway snapshot (338 s window
shift): `rsi=51.2 atr=477.8177 pctB=0.66 price=77360.0` — deltas within candle-window drift
(rsi≤3, atr≤2%, pctB≤0.15). ETH 1H: gateway `rsi=45.1 atr=18.3563 pctB=0.46` vs recompute
`rsi=44.7 atr=18.4563 pctB=0.45`. BTC 1DAY: gateway `rsi=65.6` vs recompute `65.4` (atr/pctB
equal). DOGE 1H reproduced **EXACTLY** (`rsi 44.1==44.1, atr 0.0005==0.0005, pctB 0.38==0.38`) —
proof the formulas are implemented correctly. Hard gates all PASS (RSI∈[0,100], zone matches
printed RSI, %B bounded).

**Researcher verdict (review).** (a) NOT reproducible as a bug: same-basis recompute of
`_rsi/_atr/_ema/_pctB` on 120 candles of their own candles-call (seconds after market_ta) matched
the gateway to the last digit — BTC 1H `rsi 50.9==50.9, atr 446.8244==446.8244, pctB 0.65==0.65,
trend down==down`; DOGE 1H `rsi 44.1==44.1, atr 0.0004==0.0004, pctB 0.40==0.40`. The "drift" is
the candle-window shift between two sampling moments; every new 1H/1DAY candle changes RSI/EMA/ATR
inputs. (b) **Data behavior** (rolling candles), gateway is correct. (c) **Low**: two calls minutes
apart legitimately disagree; document for consumers. Repro: `/tmp/mec34/phaseB1_invariants.py`
(market_ta section).

### A2. suggest_stops DOGE-USD: printed JSON fields self-inconsistent for sub-cent assets

**Recompute (Analyst, phase 1).** Saved record `/tmp/mec34/29-suggest_stops_doge_long.json`:
`entry=0.08 atr14=0.0005 stop_loss=0.0807 take_profit=0.0827 breakeven_after=0.082
risk_reward=1.67`, `summary="LONG DOGE-USD @ 0.08148: SL 0.08073 / TP 0.08273 (RR 1.7)"`.
Engine math on TRUE values is exact: 0.08148−1.5×0.0005=0.08073; 0.08148+2.5×0.0005=0.08273;
RR=2.5/1.5=1.67; BE=0.08148+0.0005=0.082. But printed entry is rounded to 2dp (0.08 < printed SL
0.0807 — impossible for a LONG), so implied multipliers from printed fields are nonsense
(−1.4×/5.4×, RR-from-printed 3.86 vs claimed 1.67). ATR 4dp rounding (0.0005 vs ~0.00046) ≈ 9%
quantization of true risk. BTC/ETH unaffected (values ≫ rounding step).

**Researcher verdict (review).** (a) Reproduces: fresh DOGE call `@ 0.08138: SL 0.08078 /
TP 0.08238` — summary holds truth (SL=0.08138−1.5×0.0004=0.08078 ✓, TP=0.08138+2.5×0.0004=0.08238 ✓,
BE≈0.0818 ✓, RR=2.5/1.5=1.67 ✓) while printed fields break the LONG invariant (implied −2.0×/+6.0×,
RR-from-printed 2.00 vs 1.67). Two independent reproductions (0.0807 / 0.0808 printed SL), same
conclusion. (b) **Gateway bug** (`_fmt` rounds entry to 2dp for sub-cent assets), NOT dYdX data.
(c) **Medium**: an agent reading only the JSON fields gets a wrong risk picture. Repro: saved
record above.

### A3. trader_pnl_stats: maxDD can exceed 100% (t3: 2711.54%)

**Recompute (Analyst, phase 1).** Fresh trader `dydx1q8pg5…` (equity ~$142k):
`max_drawdown_pct=2711.54`. Offline recompute on raw indexer historical-pnl reproduces **exactly**
2711.54% — the formula is faithful to `pnl_engine.compute` (peak-relative drawdown on the
deposit-adjusted curve `equity−ΣnetTransfers` with a near-zero peak: eq0=$9.80 →
min(perf)=−$19423.28). Identity residual stays 0.0000 and day-winrate matches (W1/L4 → 2.3%) —
only the % interpretation breaks: >100% DD is not human-meaningful.

**Researcher verdict (review).** (a) Reproduces deterministically: same address, same 2711.54% on
two windows (1000 and 500 points) ~5 min apart; equityΔ −8175.60 + netTransfers +150402.19 →
eq0 = $9.79 ≈ $9.80. (b) Formally **not a computation bug**: the identity converges exactly; >100%
DD is an artifact of the peak-relative formula on a deposit-adjusted curve with an almost-zero
peak — an output-semantics issue, not a math error. (c) **Medium**: 2711% misleads a consumer
(canonical maxDD ≤ 100%); recommend duplicating in USD and/or annotating when peak ≈ 0. Repro:
`/tmp/mec34/phaseB23_invariants.py` (trader.t3 section).

### A4. Moving windows: funding preview / volume24H / last-candle revision (post-hoc verification limits)

**Recompute (Analyst, phase 1).** `nextFundingRate` is a moving preview: gateway XMR row printed
ann 215.2% at 18:34Z; the preview had drifted when re-checked. `volume24H` is a rolling window:
BTC 8948025 (snapshot) → 8254299 (~1 h later) = −7.7% window decay. ETH 1H candle closes revise
after hour close: gateway change24h (−0.663%) verified EXACT on its own snapshot window; the same
computation on finalized candles gives −0.713%. Formula-internal check (ann == own printed
rate×24×365 on all 5 heatmap rows, ≤0.06pp) PASSes; exact cross-time equality is impossible by
construction.

**Researcher verdict (review).** (a) Reproduces as a CLASS, confirmed by three independent
snapshots the same day: XMR ann 173.5% (review, ~17:50Z) → 215.2% (Analyst, 18:34Z) → 274.2%
(Researcher, 19:04Z); the formula-internal link held in every snapshot (274.19≈274.2 etc.).
(b) **dYdX data behavior** (preview rates, rolling windows), gateway correctly reflects the
source. (c) **Low**: a documentation warning is sufficient. Repro: `/tmp/mec34/07..09-*.json`.

### A5. Cosmetic observations (no math impact)

**Recompute (Analyst, phase 1).** `list_markets` serves 296 markets (pre-v0.2.4 deploy; repo
v0.2.4 filters FINAL_SETTLEMENT → 99). `latest_events` ts has no timezone marker
(`2026-09-02 18:20:51`, sqlite UTC) while `trader_profile` windows use ISO-Z. BTC/ETH
`nextFundingRate_pct_1h` printed as `-0.00018`/`0.0` — the −0.0 float artifact from review still
visible in live output.

**Researcher verdict (review).** (a) Reproduces: mixed ts formats confirmed by a live call; −0.0
visible in the Analyst records; 296 markets is the known deploy lag from review. (b) **Deploy lag
and gateway cosmetics**, not data. (c) **Low**: no effect on calculations; resolved by deploying
v0.2.4 plus targeted `_fmt`/ts cleanup.

## Findings fixable in code (decision for maintainers — NO code edits made)

Priority order; all are display/output-layer changes, no engine math touched:

1. **A2 — suggest_stops `_fmt` for sub-cent assets (MEDIUM, the only actionable bug):** entry
   rounded to 2dp makes printed JSON fields self-contradictory (printed entry 0.08 < printed SL),
   implied multipliers/RR from printed fields are wrong. Fix options: higher precision for
   sub-cent prices or token-decimal-aware `_fmt`.
2. **A3 — trader_pnl_stats maxDD semantics (MEDIUM):** peak-relative maxDD exceeds 100% when the
   deposit-adjusted curve peak ≈ 0. Fix options: duplicate maxDD in USD, and/or annotate when
   peak ≈ 0.
3. **A5 — latest_events ts format (LOW):** no TZ marker (sqlite UTC) vs ISO-Z elsewhere in the
   same API surface; unify (e.g. emit ISO-Z).
4. **A5 — −0.0 float artifact (LOW):** normalize −0.0 → 0.0 in `_fmt` outputs
   (`nextFundingRate_pct_1h`).
5. **A5 — 296 vs 99 markets (LOW, ops):** resolved by deploying v0.2.4 (FINAL_SETTLEMENT filter),
   no code change needed — deploy action.
6. **A1/A4 — no code fix:** document rolling-window / preview-rate semantics for consumers
   (two calls minutes apart may legitimately disagree).

## Per-tool conclusions (one line each)

1. **height** — PASS: monotonic chain, timestamps parse and are never in the future.
2. **list_markets** — PASS: sort/limit/OI-vs-volume correct; 296 markets is deploy lag (A5), not a data fault.
3. **market_detail** — PASS: change24h exact on its own candle window; funding/volume match the indexer (hour-close revision = A4 class).
4. **candles** — PASS ×4: chronology, high/low and volume invariants hold with 0 violations.
5. **recent_trades** — PASS ×4: trade prices/times inside candle bands (±2%) or newer; invalid ticker errors honestly.
6. **trader_profile** — PASS ×3: cross-tool consistency with trader_pnl_stats to ±0.01.
7. **trader_pnl_stats** — PASS ×4: equity identity residual 0.0000, winrate and maxDD recompute; maxDD>100% is a semantics caveat (A3).
8. **registry_stats** — PASS: counters sane (total ≥ seen_24h, scan cursor ≥ observed heights) and stable.
9. **list_traders** — PASS: limit/max_hits respected, last_height ≤ scan cursor.
10. **discover_traders** — PASS: equity thresholds honored, registry hits consistent, empty 1M result is honest.
11. **leaderboard** — PASS: correct descending order per declared metric, per-address values consistent across views, flags well-typed.
12. **latest_events** — PASS: no future timestamps, id desc, kind filter exact; ts lacks TZ marker (A5).
13. **market_digest** — PASS: funding/leaderboard/events blocks equal standalone tool calls and stay stable across calls.
14. **funding_heatmap** — PASS: ann == 1h rate×24×365 on every row (≤0.06pp), side and min_oi correct; preview drift is A4.
15. **market_ta** — PASS + ANOM (A1): hard gates hold, formulas exact on same-basis recompute; values legitimately drift between calls minutes apart.
16. **suggest_stops** — PASS + ANOM (A2): engine math/RR/geometry exact; DOGE printed fields self-inconsistent due to 2dp entry rounding.
17. **fills_review** — PASS ×3: maker+taker and volume/top-markets reconcile exactly with raw indexer fills.
18. **usage_stats** — PASS: totals monotone (total ≥ 7d ≥ 24h, Σtop ≤ total), own live calls counted.

## Reproducibility

- Raw gateway responses (all 59 phase-1 calls): `/tmp/mec34/NN-<tag>.json` (+ `manifest.json`).
- Phase A collector: `/tmp/mec34/phaseA_collect.py` (one session init, checkpoint-before-next-call).
- Invariant recomputation: `/tmp/mec34/phaseB1_invariants.py`, `/tmp/mec34/phaseB23_invariants.py`
  (fresh REST calls to `indexer.dydx.trade/v4` are made by these scripts; REST is not budgeted).
- Machine-readable verdicts: `grep '^INVAR\|^ANOM'` over `/tmp/mec34/block1.log` and
  `/tmp/mec34/block23.log` → 47×`INVAR|…|PASS|`, 0×FAIL, 5×`ANOM` (re-verified 2026-09-02 at
  finalization).
- Researcher phase-2 method: 13 live MCP calls (market_ta ×3, suggest_stops DOGE, candles
  DOGE/BTC 120, market_detail BTC, trader_pnl_stats t3 ×2, discover, heatmap, latest_events) +
  own recompute of `server.py` formulas on the gateway's own candles + checkpointed records.
  Not covered: other sub-cent assets beyond DOGE (signal already clear); A2/A3 fixes (out of
  mandate — tools are not to be modified during QA).

Method note: all identity/level/winrate/maxDD checks re-derive the number from raw data and
compare to the gateway value at rounding precision; "PASS" means exact or within the documented
rounding/drift tolerance, never "looks plausible".
