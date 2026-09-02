# QA report: full review and testing (v0.2.0 → v0.2.1)

Date: 2026-08-25 · executed by: agent · protocol: user-approved plan
(Tracks A–F).

## Bottom line in numbers

| Metric | Before | After |
|---|---|---|
| Tests (offline) | 15 asserts | **49 passed** (pytest) |
| Tests (online) | 0 | **5 passed** (online marker) |
| dydx_mcp coverage | ~8% of functions | **75% of lines** (target ≥70% ✅) |
| Bugs found and fixed | — | **7** (+1 hang protection) |
| Chaos checks | 0 | 4/4 PASS |

## Bugs found and fixed (each with a regression test)

1. `signer.key_from_hex` — crashed on short hex keys (did not pad to
   32 bytes). Vector: key 0x01 → address 0x7e5f...5bdf.
2. `analytics.add_event` — dedup did not expire within a day: ISO-'T'+tz
   strings are not comparable with sqlite datetime('now'). Fix: write in
   sqlite format + compare via julianday() (also digests legacy rows in
   the prod database).
3. `analytics.prune_events` — the `id <= MAX-keep` arithmetic
   over-deleted when there were gaps in id. Fix: NOT IN (latest N by id).
4. `server.market_ta` — crash on perfectly flat candles (zero
   bollinger → pct_b=None → format error). Real case: stable pairs.
5. `detectors.equity_jumps` — sqlite connection leak on an exception
   mid-batch. Fix: try/finally.
6. `api.historical_pnl` — **boundary duplicates in pagination**: the
   createdBeforeOrAt filter is inclusive, so every next page repeats the
   boundary row → duplicated PnL history. Caught LIVE (monotonicity/
   uniqueness test on a real account). Fix: strict `< cursor` + loop
   protection (cursor only decreases + 30-page limit). Found in passing:
   on unsorted data the loop could hang — added a guard.
7. `server.market_detail`/`suggest_stops` — an invalid ticker came back
   as a successful result dict instead of isError (a violation of the
   MCP spec semantics: the model cannot self-correct). Fix: ValueError →
   isError result. Verified by an online test (ToolError, not a protocol
   error).

## Online integration (Track C, 5/5)

21 tools over HTTP and stdio; invariants on a live MM (equity ≥ 0,
winrate ∈ [0,100], residual < $1); registry freshness (cursor lag < 120
blocks); pagination of 2500 points with no duplicates, strict
monotonicity; invalid ticker → tool error.

## Chaos / DR (Track D, 4/4)

- **Restore drill**: backup deployed into a clean directory; registry
  (1183 addresses) and leaderboard readable, smoke via env-override.
- **Scanner kill test**: SIGKILL mid-run → restart → hits delta strictly
  equals addr_blocks delta (+23 = +23) — crash idempotency confirmed.
- **Load**: 20 concurrent MCP clients × 3 calls + 30 × /health —
  60 calls in 12.2 s, 0 errors; the indexer politeness cap not hit.
- **Update test**: force-reinstall of the package does not touch state
  (~/.local/state) — the marker survived, tools work.

## Static review and dependencies (Track E)

- pip-audit: runtime dependencies (fastmcp, pycryptodome, ecdsa) — clean;
  advisories only for pip inside the venv (not shipped to users).
- Documentation consistent: 21 tools across README/skill/inline;
  versions aligned (0.2.1).
- Test isolation: prod data unreachable from the suite (DYDX_GATEWAY_DATA
  → tmp, conftest before imports).

## Residual risks (accepted, documented)

1. EIP-712 signature not cross-checked against the official client (a
   golden vector guards against regressions; cross-validation is a
   testnet milestone — no real money at risk until orders are placed).
2. Farmer heuristic not calibrated (0 flags; needs a ground-truth label).
3. OI/funding detectors use practice-derived thresholds; no historical
   backtest of false positives (cascades only: 47 signature hours/7d).
4. `discover`/leaderboard: the max-equity subaccount may differ from
   subaccount 0 in edge cases (handled correctly today).
5. Flat series → RSI=100 by our convention (documented in a test).

## Tooling

pytest 9.1.1 + pytest-cov (dev extras), online marker (default run is
offline-only), CI workflow prepared (.github/workflows/tests.yml,
activates on GitHub).
