# Connecting agents to the dYdX Agent Gateway

Three ways, from "30 seconds" to "full control".

## 1. Ready-made configs (the gateway is already running somewhere)

| Client | File | What to do |
|---|---|---|
| Claude Desktop | `claude-desktop/config-http.json` | paste the block into claude_desktop_config.json |
| Codex CLI | `codex/config.toml` | add to ~/.codex/config.toml |
| Cursor | `cursor/mcp.json` | put into .cursor/mcp.json |

Once connected, the agent gets these tools: `list_markets`,
`market_detail`, `candles`, `recent_trades`, `funding_heatmap`,
`market_ta`, `suggest_stops`, `trader_profile`, `trader_pnl_stats`,
`fills_review`, `leaderboard`, `discover_traders`, `list_traders`,
`registry_stats`, `latest_events`, `market_digest`, `usage_stats`,
`height`.

Example prompts for the agent:
- "Show the most extreme funding rates on dYdX with OI above $100k"
- "Vet the trader dydx1… before I copy them: profile, PnL stats,
  farmer check"
- "What unusual things happened in the last few hours?" (latest_events)
- "Find the top traders by window and give me each one's winrate and
  drawdown"
- "Give me an ATR-based stop plan for a long ETH position on the 1h
  timeframe"

## 2. Running the gateway locally (stdio — no endpoint)

Claude Desktop: `claude-desktop/config.json` (replace the paths with your
own). Requires python + `pip install fastmcp` (+ the repo on PYTHONPATH).

## 3. An autonomous Python agent

`python-agent.py` — connects over HTTP and assembles the digest
(events → funding → leaderboard) without a single manual command. A
skeleton for your own bot.

## Events and alerts

`webhook-receiver.py` — a webhook receiver (pure stdlib);
`alerts.env.example` — a Telegram token and webhook addresses for the
systemd units.

## Trading

As of v0.2.3, trading tools have been removed from the MCP gateway
(analytics-only by design). The offline-tested EIP-712 signer remains as
a library in `dydx_mcp/signer.py` for anyone building their own execution
layer.
