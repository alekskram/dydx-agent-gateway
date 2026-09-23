# dYdX Agent Gateway

<!-- mcp-name: io.github.alekskram/dydx-agent-gateway -->

[![tests](https://github.com/alekskram/dydx-agent-gateway/actions/workflows/tests.yml/badge.svg)](https://github.com/alekskram/dydx-agent-gateway/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/dydx-agent-gateway.svg)](https://pypi.org/project/dydx-agent-gateway/)
[![PyPI downloads](https://img.shields.io/pypi/dm/dydx-agent-gateway?label=downloads)](https://pypi.org/project/dydx-agent-gateway/)
[![MCP Catalog](https://img.shields.io/badge/MCP_Catalog-glama.ai-4f46e5)](https://glama.ai/mcp/servers/alekskram/dydx-agent-gateway)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://pypi.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

One MCP server, 22 read-only tools, and your agent suddenly reads dYdX v4 the way a desk analyst does: live funding, trader PnL it can actually trust, anomaly detectors, leaderboards. No API keys anywhere. The gateway signs nothing, stores nothing, and cannot move funds even if it wanted to.

## Use cases

Copy-trading is where this pays off first. Before you follow anyone, `trader_pnl_stats` reconciles their equity curve against deposits and transfers; the residual tells you if the numbers are real. We built it after watching a "top trader of the week" who turned out to be down $1,271 all-time with a 77% drawdown.

Funding analytics: a heatmap ranked by |rate| with OI context on every row, realized 1h funding history, and detectors for the patterns that precede pain, like OI spiking while price goes flat, or the |Δprice|↑ + OI↓ cascade signature.

Discovery is on-chain, not scraped: block-scanned trader registry, funded-accounts probe, farmer-bot flags so you copy a trader and not a rewards farmer. One `market_digest` call gives you the day's events, funding extremes and the leaderboard top in a single response. When you're ready to enter, `suggest_stops` returns an ATR-based stop, take-profit, breakeven trigger and trailing level for your side.

Full walkthroughs with real outputs: [examples/use-cases.md](examples/use-cases.md).

## Install

**Claude Code:**
```bash
claude mcp add dydx -- uvx dydx-agent-gateway
```

**Claude Desktop / Cursor / any mcp.json:**
```json
{"mcpServers": {"dydx": {
  "command": "uvx",
  "args": ["dydx-agent-gateway"]}}}
```

<details>
<summary><b>Codex</b> (~/.codex/config.toml)</summary>

```toml
[mcp_servers.dydx]
command = "uvx"
args = ["dydx-agent-gateway"]
```
</details>

<details>
<summary><b>ZCode</b>: register the server and copy the agent skill</summary>

```bash
# 1) start the gateway (keep it running)
uvx dydx-agent-gateway --http --port 8901 &

# 2) register it (merges into ~/.zcode/cli/config.json; workspace .zcode/config.json works too)
python3 - <<'PY'
import json, os
p = os.path.expanduser("~/.zcode/cli/config.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
cfg = json.load(open(p)) if os.path.exists(p) else {}
cfg.setdefault("mcp", {}).setdefault("servers", {})["dydx"] = {
    "type": "http", "url": "http://127.0.0.1:8901/mcp"}
json.dump(cfg, open(p, "w"), indent=2)
print("dydx MCP server registered:", p)
PY

# 3) copy the agent skill (tool guide + data gotchas)
git clone -q --depth 1 https://github.com/alekskram/dydx-agent-gateway /tmp/dag
cp -r /tmp/dag/.agents/skills/dydx-gateway ~/.zcode/skills/ && rm -rf /tmp/dag
echo "ZCode setup done, restart your session and call any dydx tool"
```
</details>

**Plain Python:**
```bash
pip install dydx-agent-gateway
python -c "from dydx_mcp import server; import json; print(json.dumps(server.market_digest(), default=str)[:400])"
```

**Hosted (streamable HTTP):** `dydx-agent-gateway --http --port 8901`, then any client:
```json
{"mcpServers": {"dydx": {"type": "http", "url": "http://host:8901/mcp"}}}
```

Requires Python ≥ 3.11. Deps (`fastmcp`, `pycryptodome`, `ecdsa`) install automatically. See `examples/` for ready-made configs and a working autonomous agent script.

## Tools (22 — read-only, keyless)

| Group | Tools |
|---|---|
| Market data | `list_markets`, `market_detail`, `candles`, `recent_trades`, `height`, `historical_funding` |
| Analytics | `funding_heatmap`, `market_ta`, `suggest_stops`, `cvd`, `correlation` |
| Traders | `trader_profile`, `trader_pnl_stats`, `fills_review`, `raw_fills` |
| Discovery | `discover_traders`, `leaderboard`, `list_traders`, `registry_stats` |
| Signals | `latest_events` (funding extremes, OI spikes, liquidation cascades, equity jumps) |
| Briefing | `market_digest`: one call with events + funding + leaderboard top. **Start here.** |
| Meta | `usage_stats`: tool-call counters (traction/uptime of your instance) |

Real outputs of every tool: [`examples/tool-output.md`](examples/tool-output.md).

**Solving real trader problems**, five scenarios with live data: [`examples/use-cases.md`](examples/use-cases.md).

## What makes it different

PnL you can audit. `trader_pnl_stats` reconciles the identity `equity-Δ = Δpnl + ΣnetTransfers` on every account; when the residual is not zero, the numbers lie, and the tool says so instead of averaging the lie away. We ran it against real accounts and the residual lands at $0.0000. Deposit-adjusted maxDD, day-winrate and a sharpe-like ratio come out of the same pass.

Detectors instead of dashboards. Funding extremes, OI spikes without price, equity jumps, and the liquidation-cascade signature (|Δprice|↑ + OI↓). Live catches sit in `reports/`.

The rest is analyst gear: realized funding history, CVD from the trades tape, cross-market correlation with beta, raw fills for execution review, MACD/VWAP/realized-vol enrichments, sortino-like downside risk.

And a habit of writing down what bites. Five indexer gotchas that silently corrupt naive analytics are documented in `.agents/skills/dydx-gateway/references/data-gotchas.md`; 129 tests (now 133) run in CI on 3.11 and 3.13.

## Why a gateway and not the raw indexer API?

Point an agent at `indexer.dydx.trade` directly and see how far it gets before the fun starts:

| Raw indexer gives you | You would have to build |
|---|---|
| paginated endpoints (≤1000/req) | per-endpoint pagination logic |
| a funding endpoint that intermittently returns EMPTY or rpc-times out | retry + cached-series fallback |
| per-bucket (non-cumulative) netTransfers, newest-first PnL, an unreliable `priceChange24H` field | reconciliation math; this gateway verifies `equity-Δ = Δpnl + ΣnetTransfers` per account (phantom-PnL detection) |
| raw candles and trades | detectors (funding extremes, OI spikes, cascade signature), a TA pack (RSI/MACD/ATR/Bollinger/VWAP), CVD, correlation, ATR stop plans |
| address strings in blocks | a validated bech32 trader registry with farmer-bot flags and a verified leaderboard |

The five documented indexer gotchas: `.agents/skills/dydx-gateway/references/data-gotchas.md`.

## Data notes

Indicators are computed over the current candle window and move with every new bar. `nextFundingRate` is the exchange's live preview, recomputed continuously; `volume24H` rolls. Two calls a minute apart will legitimately differ, and that is not a bug.

## Safety model

Every tool is read-only and keyless. The gateway signs nothing and holds no credentials. An offline-tested EIP-712 signer stays in `dydx_mcp/signer.py` as a library for anyone building their own execution layer; it is wired to no MCP tool.

## FAQ

- **Does it trade?** No, analytics only. That was the design brief.
- **API keys?** None. Public indexer endpoints.
- **Rate limits?** No auth; a 60s markets cache keeps the traffic polite.
- **How do I vet a trader before copying?** `trader_profile`, then `trader_pnl_stats`, then `fills_review`. Check the identity residual and the maker/taker mix before anything else.


## Part of the suite

Four sibling read-only MCP gateways, one style: keyless, cached, honest degradation.

| Gateway | Focus |
|---|---|
| **dydx-agent-gateway** (you are here) | dYdX v4: verified trader PnL, funding/OI anomaly detectors, leaderboard |
| [arcus-agent-gateway](https://github.com/alekskram/arcus-agent-gateway) | 194 tokenized US equities on Robinhood Chain: quotes, holders, whale transfers |
| [hyperliquid-agent-gateway](https://github.com/alekskram/hyperliquid-agent-gateway) | Hyperliquid: 233 perps + spot, funding carry, account risk, HyperEVM |
| [aster-agent-gateway](https://github.com/alekskram/aster-agent-gateway) | Aster DEX: ~580 futures incl. 24/7 TradFi perps, funding caps/floors |

All four are on [glama.ai](https://glama.ai/mcp/servers/alekskram/dydx-agent-gateway) and PyPI; any of them installs with `uvx <name>`.

## License

MIT. Not affiliated with dYdX Trading Inc.
