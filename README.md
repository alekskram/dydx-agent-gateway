# dYdX Agent Gateway

**One MCP server that gives any AI agent analytics access to dYdX v4** — market data, funding analytics, verified trader PnL, leaderboards, and anomaly & liquidation-cascade detectors. Analytics-only by design — no trading, no keys.

No dashboards to babysit: your agent *calls* the tools — Claude, Codex, Cursor, Hermes, ZCode or any MCP client.

## Quickstart

**Claude Code — one command** (replace `https://github.com/alekskram/dydx-agent-gateway` after publish):
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

Requires Python >= 3.11. Deps: `fastmcp`, `pycryptodome`, `ecdsa` — installed automatically. Verified with a clean-venv `pip install .`; market/trader tools work out of the box, no keys required.

## Tools (18, annotations-compliant — all read-only, keyless)

**Market data** — `list_markets`, `market_detail` (honest 24h change computed from candles), `candles` (OHLCV+OI, 1MIN…1DAY), `recent_trades`, `height` (chain liveness).

**Analytics** — `funding_heatmap` (all markets, annualized, ranked), `market_ta` (RSI/EMA/ATR/Bollinger, zero TA deps), `suggest_stops` (ATR-based SL/TP/breakeven/trailing + RR).

**Trader analytics (the killer feature)** — `trader_profile`, `trader_pnl_stats` (daily PnL, day-winrate, **deposit-adjusted maxDD**, sharpe-like), `fills_review` (maker/taker mix). The PnL engine reconciles the identity `equity-Δ = Δpnl + ΣnetTransfers` per bucket — residual = phantom-data detector. Live-verified on a real market maker (data as of 2026-08): residual $0.0000 across 25 accounts (see `reports/`).

**Discovery** — `market_digest` (one-call briefing: events + funding extremes + leaderboard top — start here), `leaderboard` (verified top traders, farmer flags), `discover_traders` (funded active addresses from an onchain registry), `list_traders`, `registry_stats`, `usage_stats` (tool-call counters since deployment).

**Anomaly detection** — `latest_events`: `funding_extreme`, `oi_spike_no_price`, `equity_jump`, plus a signature **liquidation-cascade detector** (|Δprice|↑ + OI↓, fresh/confirmed stages). Live catches include ETH +15.8%/h with OI −51.6% (mass short squeeze) and 19%-OI builds with flat price (both as of 2026-08).


## Highlights

- **Zero-heavy-dep signer** (`dydx_mcp/signer.py`): keccak256 + EIP-712 + secp256k1 (RFC6979, low-S) + bech32 + order quantization from live market meta. 12/12 selftest vectors: `python -m dydx_mcp.signer --selftest`.
- **Data quality watchdog**: 5 documented indexer-API gotchas (see `.agents/skills/dydx-gateway/references/data-gotchas.md`) — the kind of things that silently corrupt naive analytics.
- **54 tests** (49 offline + 5 online), 75% coverage, CI workflow included.
- Systemd units for continuous operation: block scanner (onchain address registry), detectors every 5 min, leaderboard every 6h, WAL-safe backups (table in README.ru.md).

## Repo extras

- `examples/` — ready configs for Claude Desktop (stdio + HTTP), Codex, Cursor, an autonomous Python agent (events → funding → leaderboard in one run), webhook receiver.
- `demos/` — funding watch, real trader deep-dive.
- `reports/` — monthly data-quality watchdog reports.
- `.agents/skills/dydx-gateway/` — drop-in agent skill (tool guide + data gotchas) for Claude/ZCode-compatible skill directories.

## Safety model

All tools are read-only and keyless: the gateway holds no keys, signs nothing, and cannot move funds. (An offline-tested EIP-712 signer remains in `dydx_mcp/signer.py` as a library for anyone building their own execution layer — it is not wired to any MCP tool.) Alerts credentials live in a gitignored `alerts.env` (see `examples/alerts.env.example`).

## License

MIT. Not affiliated with dYdX Trading Inc.

## Roadmap: multi-venue core

Venue specifics are deliberately isolated in two modules — `dydx_mcp/api.py`
(indexer HTTP client, single `BASE` constant) and `dydx_mcp/signer.py`
(EIP-712/bech32/quantization). Everything else — PnL engine, detectors
(funding/OI/cascades/equity), TA, discovery pipeline — is venue-agnostic
math over normalized OHLCV/OI/equity structures. Porting to another
perps venue (Hyperliquid, TON DEX, …) means writing a new `api.py` +
`signer.py`, not reworking the core.
