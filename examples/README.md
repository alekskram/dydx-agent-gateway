# Подключение агентов к dYdX Agent Gateway

Три способа, от «30 секунд» до «полный контроль».

## 1. Готовые конфиги (шлюз уже где-то запущен)

| Клиент | Файл | Что сделать |
|---|---|---|
| Claude Desktop | `claude-desktop/config-http.json` | вставить блок в claude_desktop_config.json |
| Codex CLI | `codex/config.toml` | добавить в ~/.codex/config.toml |
| Cursor | `cursor/mcp.json` | положить в .cursor/mcp.json |

После подключения у агента появляются инструменты: `list_markets`,
`market_detail`, `candles`, `recent_trades`, `funding_heatmap`, `market_ta`,
`suggest_stops`, `trader_profile`, `trader_pnl_stats`, `fills_review`,
`leaderboard`, `discover_traders`, `list_traders`, `registry_stats`,
`latest_events`, `market_digest`, `usage_stats`, `height`.

Примеры промптов для агента:
- «Покажи самые экстремальные фандинги на dYdX с OI от $100k»
- «Проверь трейдера dydx1… перед тем, как я буду его копировать:
  профиль, PnL-статистику, не фармер ли»
- «Что странного происходило за последние часы?» (latest_events)
- «Найди топ трейдеров по окну и дай по каждому винрейт и просадку»
- «Дай ATR-план стопов для лонга ETH на 1ч таймфрейме»

## 2. Локальный запуск шлюза (stdio — без endpoint)

Claude Desktop: `claude-desktop/config.json` (заменить пути на свои).
Нужен python + `pip install fastmcp` (+ repo в PYTHONPATH).

## 3. Автономный агент на Python

`python-agent.py` — подключается по HTTP и собирает дайджест (события →
фандинг → лидерборд) без единой ручной команды. Каркас для своего бота.

## События и алерты

`webhook-receiver.py` — приёмник вебхуков (чистый stdlib);
`alerts.env.example` — токен Telegram и адреса вебхуков для systemd-юнитов.

## Торговля

Начиная с v0.2.3 торговые инструменты из MCP-шлюза убраны (analytics-only
by design). Офлайн-протестированный EIP-712 подписыватель остаётся
библиотекой в `dydx_mcp/signer.py` для тех, кто строит свой слой исполнения.
