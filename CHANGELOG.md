# Changelog

## v0.3.0 (2026-09-03) — analyst pack
- 4 new tools: `historical_funding` (raw 1h funding-rate series with
  annualized rate = rate*24*365, ticker-guard), `cvd` (cumulative volume
  delta from the trades tape: buy/sell by side, current CVD + series over
  the window), `correlation` (Pearson r over log-returns of two tickers'
  candles + beta(a|b)), `raw_fills` (raw fills of a trader for own
  execution analysis; addresses from discover_traders/leaderboard).
- Enrichments: `market_ta` + MACD(12,26,9) + VWAP(20, typical price x
  volume) + realized_vol (annualized at candle resolution); `market_detail`
  + basis_pct (mark deviation from oracle); `trader_pnl_stats` +
  sortino_like_daily (downside deviation) next to the sharpe-like metric.
- Fix: api historical_funding used a non-working query path (404) —
  switched to the path form /historicalFunding/{ticker}.
- Fix (live QA): correlation aligned the two candle series by index
  tail; candle feeds are trade-driven and can differ by a bar, which
  shifted one series and collapsed r (BTC/ETH 1h: 0.853 -> 0.033).
  Now joined on startedAt (inner join). raw_fills prints
  self-consistent price/size/usd_notional (6 significant digits).
- Tests: +29 invariant (ta_ext) and regression tests per tool (mocked,
  incl. ticker-guard cases) + shift-bug regression; plus an independent
  numpy reference cross-check on randomized data
  (tests/test_ta_ext_reference.py, tol 1e-9; author ≠ ta_ext author —
  owner requirement).
- Version bump 0.2.5 -> 0.3.0 (pyproject, FastMCP server, server.json);
  numpy added to dev extras (reference cross-check; runtime stays stdlib).

## v0.2.5 (2026-09-02) — logical-QA fixes (review/43, findings A1-A4)
- A2 (bug, Medium): adaptive price precision in `suggest_stops` /
  `market_ta` via `_fmt_price` — at least 6 significant digits (never fewer
  decimals than before), so level geometry (SL < entry < TP) and ATR
  multipliers hold in the printed JSON fields for sub-cent assets
  (DOGE entry now prints 0.08148 with SL 0.08073, not 0.08 vs 0.0807).
- A3 (semantics, Medium): `trader_pnl_stats` adds `max_drawdown_usd` (depth
  of the same worst drawdown in USD) and `dd_pct_unreliable: true` when the
  deposit-adjusted curve's running peak at the worst drawdown is near zero
  (< $1 or < 1% of current equity) — the peak-relative
  `max_drawdown_pct` exceeds 100% there and misleads (t3 case: 2711.54%);
  thresholds per Researcher (review).
- A1/A4 (docs): README "Data notes" — indicators recompute per candle
  window; `nextFundingRate` is an exchange preview, `volume24H` a rolling
  window.
- Version bump 0.2.4 -> 0.2.5 (pyproject, FastMCP server, server.json).

## v0.2.4 (2026-09-02) — pre-publication hardening (review)
- Crash fixes (found in the review internal review, each with a regression test):
  pnl_engine.compute no longer raises on None equity/totalPnl/netTransfers
  fields (API nulls) or on a single history point (ZeroDivisionError in the
  summary line); market_digest/leaderboard summaries no longer raise
  TypeError on NULL pnl_window (rows from accounts with 'no pnl history').
- api.markets() now filters FINAL_SETTLEMENT (settled) markets: 197 of 296
  listings were dead but still leaked zero-volume rows into list_markets and
  stale nonzero funding rates into funding_heatmap/detectors. Live markets
  only (status == ACTIVE) by default.
- server.json rebuilt against the official MCP Registry server schema
  (2025-12-11): 0 validation errors — description <= 100 chars, name
  `io.github.ventures/dydx-agent-gateway` placeholder (GitHub org pending),
  registryType + transport{stdio} in the package, repository block added,
  $schema URL fixed (old raw.githubusercontent URL was 404).
- Demo numbers in README dated "as of 2026-08" (kept, not scrubbed,
  by design decision).
- Version bump 0.2.3 -> 0.2.4 (pyproject, FastMCP server, SKILL.md).

## v0.2.1 (2026-08-25) — QA pass: full review and testing
- Tests: pytest structure (49 offline + 5 online, online marker), dydx_mcp
  coverage 75% (up from ~8% of functions); dev extras [dev]; CI workflow
  ready.
- 7 bugs found and fixed with regression tests: short keys in key_from_hex;
  event dedup never expired (ts format); prune over-deletion; market_ta
  crash on flat candles; equity_jumps connection leak; BOUNDARY DUPLICATES
  in PnL pagination (live test); isError semantics for invalid tickers
  (ValueError).
- Chaos 4/4: restore drill, scanner SIGKILL idempotency (+23 = +23), load
  test 20 clients / 0 errors, state survives force-reinstall.
- QA report: reports/qa-report.md

## v0.1.1 (2026-08-25)
- `trader_pnl_stats(limit)` — agents get up to 5000 history points
  (~7 months); default 1000 (~42 days, fast).
- `market_digest` — one-call briefing: detector events + funding extremes
  + leaderboard top.
- `usage_stats` + tool-call accounting (middleware → sqlite) — traction
  metrics for grant KPIs (calls/24h/7d, top tools).
- `watchdog.py` + dydx-watchdog timer (1st of the month, 09:00) — the
  data-quality report is generated automatically.
- README: dydx-backup unit in the automation table, deploy-public.md link.
- fastmcp banner disabled (stdio/HTTP).

## v0.1.0 (2026-08-24)
- 19 MCP tools: market data, analytics, leaderboard, events, screener.
- PnL engine: deposit-adjusted curve, day-winrate, maxDD, identity check
  (residual $0.00 on live data), history pagination up to 5000 points.
- Block scanner → address registry (bech32 BIP-173, idempotent).
- Detectors: funding_extreme, oi_spike_no_price, liq_cascade_signature
  (validated on history: 47 signature hours/7d), equity_jump.
- EIP-712 signer (Order, ApiCredentials; 12/12 selftests).
- pip package (pyproject, console entry point), examples for Claude
  Desktop/Codex/Cursor, skill, HTTP+stdio transports.
- systemd: 5 units + hardening; WAL-safe backup (restore verified).
- Tests: suite 15/15; 5 indexer API gotchas found and fixed.

## v0.2.0 (2026-08-25) — skill and MCP standards
- Skill rewritten to skill-creator standards: EN description with triggers
  in the visible zone (~250 chars), when_to_use (detailed triggers),
  metadata.agent.requires.bins; source of truth — .agents/skills/ in the
  repo (discoverable root), self-contained (references/data-gotchas.md),
  sync with ~/.zcode/skills documented.
- MCP compliance: tool annotations (readOnlyHint/destructiveHint/
  idempotentHint — 21 tools), server instructions (strategy for the
  agent), /health endpoint (custom_route).
- recent_traders → list_traders (SEP-986 distinctness from recent_trades).
- server.json for the official MCP registry (reverse-DNS, draft).
- deploy-public.md: origin/host validation, OAuth 2.1 note.

## v0.2.3 — analytics-only release
- Trading tools (place_order / cancel_all / my_positions) removed from the
  MCP server by design decision: the public gateway is read-only analytics,
  holds no keys, signs nothing. Signer stays as a library module (offline
  selftest 12/12), unwired to any tool.
- demo3_order_consent.py removed; docs (EN/RU README, examples, skill)
  updated; tool count 21 -> 18.
