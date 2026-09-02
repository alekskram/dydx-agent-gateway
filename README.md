# dYdX Agent Gateway

**One MCP server that gives any AI agent full access to dYdX v4** — market data, funding analytics, verified trader PnL, leaderboards, anomaly & liquidation-cascade detectors, and (optional) trading with user-held keys.

No dashboards to babysit: your agent *calls* the tools — Claude, Codex, Cursor, Hermes, ZCode or any MCP client.

## Quickstart

**Claude Code — one command** (replace `REPO_URL` after publish):
```bash
claude mcp add dydx -- uvx --from git+REPO_URL dydx-agent-gateway
```

**Cursor / any `mcp.json`:**
```json
{"mcpServers": {"dydx": {
  "command": "uvx", "args": ["--from", "git+REPO_URL", "dydx-agent-gateway"]}}}
```

**Plain Python (no agent needed):**
```bash
pip install git+REPO_URL
python -c "from dydx_mcp import server; print(server.market_digest()[:500])"
```

**Hosted (streamable HTTP):**
```bash
dydx-agent-gateway --http --port 8901
# client: {"mcpServers": {"dydx": {"type": "http", "url": "http://host:8901/mcp"}}}
```

Deps: `fastmcp`, `pycryptodome`, `ecdsa` — installed automatically. Verified with a clean-venv `pip install .`; market/trader tools work out of the box, no keys required.

## Tools (21, annotations-compliant)

**Market data** — `list_markets`, `market_detail` (honest 24h change computed from candles), `candles` (OHLCV+OI, 1MIN…1DAY), `recent_trades`, `height` (chain liveness).

**Analytics** — `funding_heatmap` (all markets, annualized, ranked), `market_ta` (RSI/EMA/ATR/Bollinger, zero TA deps), `suggest_stops` (ATR-based SL/TP/breakeven/trailing + RR).

**Trader analytics (the killer feature)** — `trader_profile`, `trader_pnl_stats` (daily PnL, day-winrate, **deposit-adjusted maxDD**, sharpe-like), `fills_review` (maker/taker mix). The PnL engine reconciles the identity `equity-Δ = Δpnl + ΣnetTransfers` per bucket — residual = phantom-data detector. Live-verified on a real market maker: residual $0.0000 across 25 accounts (see `reports/`).

**Discovery** — `leaderboard` (verified top traders, farmer flags), `discover_traders` (funded active addresses from an onchain registry), `list_traders`, `registry_stats`.

**Anomaly detection** — `latest_events`: `funding_extreme`, `oi_spike_no_price`, `equity_jump`, plus a signature **liquidation-cascade detector** (|Δprice|↑ + OI↓, fresh/confirmed stages). Live catches include ETH +15.8%/h with OI −51.6% (mass short squeeze) and 19%-OI builds with flat price.

**Trading (opt-in)** — `place_order`, `cancel_all`, `my_positions`. Off by default: requires the user's `DYDX_ETH_KEY`, explicit human consent per order, dry-run planning first. Keys never leave the host; nothing is logged.

## Highlights

- **Zero-heavy-dep signer** (`dydx_mcp/signer.py`): keccak256 + EIP-712 + secp256k1 (RFC6979, low-S) + bech32 + order quantization from live market meta. 12/12 selftest vectors: `python -m dydx_mcp.signer --selftest`.
- **Data quality watchdog**: 5 documented indexer-API gotchas (see `.agents/skills/dydx-gateway/references/data-gotchas.md`) — the kind of things that silently corrupt naive analytics.
- **54 tests** (49 offline + 5 online), 75% coverage, CI workflow included.
- Systemd units for continuous operation: block scanner (onchain address registry), detectors every 5 min, leaderboard every 6h, WAL-safe backups — see README table in the repo docs.

## Repo extras

- `examples/` — ready configs for Claude Desktop (stdio + HTTP), Codex, Cursor, an autonomous Python agent (events → funding → leaderboard in one run), webhook receiver.
- `demos/` — funding watch, real trader deep-dive, consent-gated order plan.
- `reports/` — monthly data-quality watchdog reports.
- `.agents/skills/dydx-gateway/` — drop-in agent skill (tool guide + data gotchas) for Claude/ZCode-compatible skill directories.

## Safety model

Read tools are keyless and safe. Trading tools are disabled unless `DYDX_ETH_KEY` is set; orders require explicit confirmation; a dry-run plan (ATR risk, RR) is always produced first. Alerts credentials live in a gitignored `alerts.env` (see `examples/alerts.env.example`).

## License

MIT. Not affiliated with dYdX Trading Inc.
