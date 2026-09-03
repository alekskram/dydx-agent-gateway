# dYdX Agent Gateway

[![tests](https://github.com/alekskram/dydx-agent-gateway/actions/workflows/tests.yml/badge.svg)](https://github.com/alekskram/dydx-agent-gateway/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://pypi.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

One MCP server that gives any AI agent analytics access to dYdX v4: market data, funding analytics, verified trader PnL, leaderboards, anomaly detection. Read-only and keyless — the gateway holds no keys and cannot move funds.

## Install

**Claude Code:**
```bash
claude mcp add dydx -- uvx --from git+https://github.com/alekskram/dydx-agent-gateway dydx-agent-gateway
```

**Cursor / any mcp.json:**
```json
{"mcpServers": {"dydx": {
  "command": "uvx",
  "args": ["--from", "git+https://github.com/alekskram/dydx-agent-gateway", "dydx-agent-gateway"]}}}
```

**Codex** (`~/.codex/config.toml`):
```toml
[mcp_servers.dydx]
command = "uvx"
args = ["--from", "git+https://github.com/alekskram/dydx-agent-gateway", "dydx-agent-gateway"]
```

**ZCode** — register the MCP server and copy the agent skill (all copy-paste):
```bash
# 1) start the gateway (keep it running)
uvx --from git+https://github.com/alekskram/dydx-agent-gateway dydx-agent-gateway --http --port 8901 &

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
echo "ZCode setup done — restart your session and call any dydx tool"
```

**Plain Python:**
```bash
pip install git+https://github.com/alekskram/dydx-agent-gateway
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
| Briefing | `market_digest` — one call: events + funding + leaderboard top. **Start here.** |

Real outputs of every tool: [`examples/tool-output.md`](examples/tool-output.md).

## What makes it different

- **Verified trader PnL.** `trader_pnl_stats` reconciles the identity `equity-Δ = Δpnl + ΣnetTransfers` on every account — residual ≠ 0 means the numbers lie. Live-checked on real accounts to $0.0000 (see `reports/qa-logic.md`). Deposit-adjusted maxDD, day-winrate, sharpe-like.
- **Anomaly detectors, not dashboards.** Funding extremes, OI spikes without price, equity jumps, and a liquidation-cascade signature (|Δprice|↑ + OI↓) — the patterns that matter before they're charts. Live catches in `reports/`.
- **Analyst pack.** Funding-rate history, CVD, cross-market correlation, raw fills for execution analysis; TA enrichments MACD/VWAP/realized vol; sortino-like downside risk.
- **Data-quality discipline.** Five documented indexer API gotchas (`.agents/skills/dydx-gateway/references/data-gotchas.md`) that silently corrupt naive analytics. 129 tests, CI on 3.11/3.13.

## Data notes

Indicators are computed over the current candle window and change with every new bar. `nextFundingRate` is the exchange's live preview and is recomputed continuously; `volume24H` is a rolling window. Two calls moments apart legitimately differ.

## Safety model

All tools are read-only and keyless. The gateway signs nothing and holds no credentials. An offline-tested EIP-712 signer remains in `dydx_mcp/signer.py` as a library for anyone building their own execution layer — it is wired to no MCP tool.

## FAQ

- **Does it trade?** No. Analytics only, by design.
- **API keys?** None. Everything runs on public indexer endpoints.
- **Rate limits?** Public endpoints, no auth; a 60s markets cache keeps you polite.
- **How do I verify a trader before copying them?** `trader_profile` → `trader_pnl_stats` → `fills_review` — check the identity residual and maker/taker mix first.


## License

MIT. Not affiliated with dYdX Trading Inc.
