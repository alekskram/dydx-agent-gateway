# dYdX Agent Gateway

> **Give your AI agent eyes on dYdX v4.** One MCP server, 18 read-only tools: market data, funding analytics, verified trader PnL, leaderboards, and liquidation-cascade detectors. No keys, no trading, nothing to babysit.

[![CI](https://github.com/alekskram/dydx-agent-gateway/actions/workflows/tests.yml/badge.svg)](https://github.com/alekskram/dydx-agent-gateway/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

Your agent can already read files and call APIs. Point it at this gateway and it can answer the questions that actually matter on dYdX: *where is funding extreme, who is actually profitable, and what just broke?* Works with Claude, Codex, Cursor, Hermes, or any MCP client.

## Why

- **Raw indexer data lies in subtle ways.** Candles arrive newest-first (naive consumers invert every trend sign), and 197 of 296 market listings were dead while still leaking zero-volume rows and stale funding into analytics. The gateway normalizes, filters, and documents every gotcha we found (see [Data quality](#under-the-hood)).
- **PnL you can trust.** Every trader statistic is reconciled against the identity `equity-Δ = Δpnl + ΣnetTransfers` — if the data doesn't add up, the residual flags it. Live verification on a real market maker: residual $0.0000 across 25 accounts (as of 2026-08, see `reports/`).
- **Signals, not just charts.** Detectors watch every liquid market: funding extremes, OI spikes with no price move, equity jumps, and a signature liquidation-cascade detector — delivered to your agent or pushed to Telegram/webhooks.
- **Safe to hand to an agent.** All 18 tools are read-only and keyless. The gateway signs nothing, holds no keys, and cannot move funds.

## Quickstart

**Claude Code — one command:**
```bash
claude mcp add dydx -- uvx --from git+https://github.com/alekskram/dydx-agent-gateway dydx-agent-gateway
```

**Cursor / any `mcp.json`:**
```json
{"mcpServers": {"dydx": {
  "command": "uvx", "args": ["--from", "git+https://github.com/alekskram/dydx-agent-gateway", "dydx-agent-gateway"]}}}
```

**Plain Python (no agent needed):**
```bash
pip install git+https://github.com/alekskram/dydx-agent-gateway
# or, from a local checkout: pip install .
python -c "from dydx_mcp import server; import json; print(json.dumps(server.market_digest(), default=str)[:500])"
```

**Hosted (streamable HTTP):**
```bash
dydx-agent-gateway --http --port 8901
# client: {"mcpServers": {"dydx": {"type": "http", "url": "http://host:8901/mcp"}}}
```
The server binds to `127.0.0.1` by default; use `--host 0.0.0.0` to expose it externally. A plain `GET /health` endpoint returns `{"ok": true, ...}` for monitoring.

Requires Python ≥ 3.11. Deps: `fastmcp`, `pycryptodome`, `ecdsa` — installed automatically. Verified with a clean-venv `pip install .`; market/trader tools work out of the box, no keys required.

Ready-made configs live in `examples/` (Claude Desktop stdio + HTTP, Codex, Cursor, an autonomous Python agent, a webhook receiver). There is also a drop-in agent skill: copy `.agents/skills/dydx-gateway/` into your Claude Code/ZCode skills directory and the agent learns the tools *and* every known API gotcha.

## What your agent actually gets

Real output of `market_digest` — the one-call daily briefing (fetched from a live deployment on 2026-09-01; truncated to 2 events, 2 funding rows, 1 leaderboard entry — full payload has 5/5/3):

```json
{
  "events": [
    {
      "kind": "equity_jump",
      "subject": "dydx18ra3g2l7lez66nd2e07vjskccr96svd5gshpg6",
      "from": 925.55,
      "to": 1307.2,
      "pct": 41.2
    },
    {
      "kind": "funding_extreme",
      "subject": "XMR-USD",
      "ticker": "XMR-USD",
      "funding_pct_1h": 0.07097,
      "annualized_pct": 621.7,
      "oi_usd": 115478.0,
      "longs_pay": true,
      "price": "498.7378976"
    }
  ],
  "funding": [
    {
      "ticker": "XMR-USD",
      "funding_pct_1h": 0.02757,
      "funding_pct_annualized": 241.5,
      "oi_usd": 114298.0,
      "longs_pay": true,
      "oraclePrice": 493.64
    },
    {
      "ticker": "ALGO-USD",
      "funding_pct_1h": 0.00734,
      "funding_pct_annualized": 64.3,
      "oi_usd": 112479.0,
      "longs_pay": true,
      "oraclePrice": 0.09
    }
  ],
  "leaderboard_top": [
    {
      "address": "dydx1820ztafsyq48e90prf3kdh5749rqltwk3ptlkg",
      "pnl_window": 7422.88,
      "equity": 2867.81,
      "day_winrate": 23.3
    }
  ],
  "summary": "events: 5 | extreme funding: XMR-USD 241.5% ann | leaderboard #1: dydx1820zt… +$7,423"
}
```

Five detector events, ranked funding extremes, and the verified leaderboard top — in one call. That JSON is the raw material for every scenario below.

## Tools (18 — all read-only, all keyless)

| Group | Tool | What it answers |
|---|---|---|
| **Market data** | `list_markets(limit, sort)` | Active markets: price, 24h volume, OI, funding |
| | `market_detail(ticker)` | Deep market view + candles + honest 24h change (computed from candles) |
| | `candles(ticker, resolution, limit)` | OHLCV + open interest, 1MIN…1DAY, chronological |
| | `recent_trades(ticker, limit)` | The trade tape |
| | `height()` | Chain height (liveness check) |
| **Analytics** | `funding_heatmap(limit, min_oi_usd)` | Funding across all liquid markets, ranked, annualized |
| | `market_ta(ticker, resolution)` | RSI14, EMA20/50, ATR14, Bollinger %B — zero TA dependencies |
| | `suggest_stops(ticker, side, …)` | ATR-based SL/TP/breakeven/trailing plan + risk-reward |
| **Trader analytics** | `trader_profile(address)` | Equity, positions, PnL curve of *any* trader |
| | `trader_pnl_stats(address)` | Daily PnL, day-winrate, deposit-adjusted maxDD, sharpe-like + identity check |
| | `fills_review(address)` | Maker/taker mix, volumes, market mix |
| **Discovery** | `market_digest()` | One-call briefing: events + funding extremes + leaderboard top — **start here** |
| | `leaderboard(limit, metric)` | Verified top traders (rebuilt every 6h), farmer flags |
| | `discover_traders(limit, min_equity)` | Screener: funded active traders straight from an onchain registry |
| | `list_traders(limit, max_hits)` | Fresh addresses from the block-scanner registry |
| | `registry_stats()` | Address-registry statistics |
| | `usage_stats()` | Tool-call counters since deployment |
| **Anomaly detection** | `latest_events(limit, kind?)` | Detector bus: `funding_extreme`, `oi_spike_no_price`, `equity_jump`, `liq_cascade_signature` |

## Three agent scenarios

**1. The morning briefing.** One `market_digest` call, the agent turns it into three bullet points in your chat: what broke overnight (events), where funding is extreme (carry costs), and who is profitable right now (leaderboard). `examples/python-agent.py` runs events → funding → leaderboard in one pass; `examples/webhook-receiver.py` receives detector alerts the moment they fire.

**2. Due diligence before copy-trading.** The agent takes an address from `leaderboard`, pulls `trader_profile` (equity, positions), then `trader_pnl_stats` — day-winrate, deposit-adjusted maxDD, sharpe-like ratio, all identity-checked — and `fills_review` for the maker/taker mix. A real deep-dive of a market maker (equity $63.5k, lifetime PnL $488k, 68 positions, maker 21%) ships as `demos/demo2_trader_check.py` (as of 2026-08).

**3. A risk guard for your own positions.** `suggest_stops` for an ATR-based stop plan, `funding_heatmap` to price the carry you're paying, and `liq_cascade_signature` events as a de-risking signal — detectors run every 5 minutes under systemd and push to Telegram/webhooks before you'd have noticed yourself. Live catches include ETH +15.8%/h with OI −51.6% (mass short squeeze) and a 19%-OI build with a flat price (both as of 2026-08).

## Under the hood

- **Data-quality watchdog.** Five documented indexer-API gotchas (newest-first candles, dead listings, liquidity noise, …) are fixed centrally and documented in `reports/` — the kind of things that silently corrupt naive analytics.
- **The PnL engine.** Reconciles `equity-Δ = Δpnl + ΣnetTransfers` per bucket; a nonzero residual means phantom data. Live verification on a real market maker: residual $0.0000 across 25 accounts (2026-08).
- **A zero-heavy-dependency signer** (`dydx_mcp/signer.py`): keccak256 + EIP-712 + secp256k1 (RFC6979, low-S) + bech32 + order quantization from live market meta. 12/12 selftest vectors: `python -m dydx_mcp.signer --selftest`. It is an offline library for building your own execution layer — wired to no MCP tool.
- **54 tests** (49 offline + 5 online), 75% coverage, CI workflow included; QA/chaos history in `reports/qa-report.md`.
- **Systemd automation** (optional, for an always-on deployment):

| Unit | What it does | Cadence |
|---|---|---|
| `dydx-scanner.service` | scans blocks → address registry | continuous |
| `dydx-mcp.service` | MCP endpoint (HTTP) | continuous |
| `dydx-detectors.timer` | detectors + TG/webhook alerts | every 5 min |
| `dydx-leaderboard.timer` | leaderboard rebuild | every 6 h |
| `dydx-backup.timer` | WAL-safe backup (`backup.sh`) | daily 23:40 |

## Data notes

- Indicators (`market_ta`: RSI/EMA/ATR/%B, and `change24h`) are computed over the current candle window and change with every new bar — two calls minutes apart may legitimately differ.
- `nextFundingRate` is the exchange's live preview and gets recomputed; `volume24H` is a rolling window — both move between calls.

## Safety model

All tools are read-only and keyless: the gateway holds no keys, signs nothing, and cannot move funds. Optional alert credentials (Telegram/webhook) live in a gitignored `alerts.env` (see `examples/alerts.env.example`). The EIP-712 signer remains an offline library for anyone building their own execution layer — it is not wired to any MCP tool.

## FAQ

**How do I install it?**
One command for Claude Code (see [Quickstart](#quickstart)), or add the `uvx` block to any `mcp.json` for Cursor/Codex/Claude Desktop. Plain `pip install git+https://github.com/alekskram/dydx-agent-gateway` works too — Python ≥ 3.11, three dependencies, installed automatically.

**How is this different from a generic dYdX MCP wrapper?**
Thin wrappers expose the raw indexer REST API as tools and leave the traps in: newest-first candles that invert your trends, 197 dead listings polluting rankings, funding from markets with $4.5k of OI. This gateway is an analytics *layer*: normalized chronological candles, ACTIVE-markets filtering, a verified PnL engine with a built-in phantom-data detector, cross-trader discovery (block-scanner registry + leaderboard), TA, detectors — it returns conclusions-ready numbers, not raw endpoints.

**Does it need my private keys? Can it trade?**
No, and no. All 18 tools are read-only; the gateway never asks for keys and cannot place orders or move funds. You can hand it to any agent without custody risk.

**What are the rate limits?**
The gateway self-throttles to ~6–7 requests/second with a thread-safe politeness window and automatic retries on 429/5xx — under the dYdX indexer's 100 req/10 s cap. A single agent can hammer tools without getting blocked; for shared multi-user deployments, add a reverse proxy and your own quota.

**Can I trust the data?**
It's the public dYdX v4 indexer, but with the footguns fixed and documented: candles normalized to chronological order, settled/dead markets filtered out, micro-cap funding noise gated by an OI floor, and every PnL statistic reconciled against the equity identity (residual = phantom-data alarm). Our watchdog reports live in `reports/`.

**What's the license?**
MIT. Not affiliated with dYdX Trading Inc.

## Roadmap

- **Multi-venue core.** Venue specifics are deliberately isolated in two modules — `dydx_mcp/api.py` (indexer HTTP client) and `dydx_mcp/signer.py` (EIP-712/bech32/quantization). Everything else — PnL engine, detectors, TA, discovery — is venue-agnostic math over normalized data. Porting to another perps venue (Hyperliquid, …) means writing a new `api.py` + `signer.py`, not reworking the core.
- **PyPI release** (today: install from git).
- **Hosted HTTP behind TLS + auth token** for shared multi-user deployments (`deploy-public.md`).
- **Farmer-heuristic calibration** — the copy-trade abuse flag needs ground-truth labels (documented in `reports/qa-report.md`).
- **EIP-712 signature cross-validation** against the official dYdX client (testnet milestone).

## License

MIT. Not affiliated with dYdX Trading Inc. All data comes from the public dYdX v4 indexer.
