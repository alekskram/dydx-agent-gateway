---
name: dydx-gateway
description: dYdX v4 perps via local MCP gateway — market data, funding heatmap, verified trader PnL analytics, leaderboards, OI and liquidation-cascade anomaly detection. Use when the user asks about dYdX, a perp trader by address, funding/OI anomalies, or before copy-trading.
when_to_use: Использовать при любых вопросах про dYdX — рынки, цены, фандинг, OI, объёмы; аномалии (всплески OI без цены, каскады ликвидаций, экстрим-фандинг, прыжки equity трейдеров); анализ трейдера по адресу (equity, PnL-кривая, day-винрейт, maxDD, флаг фармера) перед копированием; лидерборд и скрининг трейдеров с цепи; TA и ATR-планы стопов. Триггер-слова: dYdX, перпы, funding, OI anomaly, trader PnL, проверь трейдера, liquidation cascade.
metadata:
  author: ventures
  version: "0.2.0"
  agent:
    requires:
      bins: ["python3"]
---

# dYdX Agent Gateway (локальный MCP-сервер)

Шлюз развёрнут на этом хосте, endpoint **http://127.0.0.1:8901/mcp**
(streamable HTTP, systemd-юнит `dydx-mcp.service`; проверить:
`systemctl is-active dydx-mcp`). Код и репо-копия этого скилла:
`/root/ventures/dydx-grant/agent-gateway` (источник скилла —
`.agents/skills/dydx-gateway/`; после правок там скопировать в
`~/.zcode/skills/dydx-gateway/`).

Фоновые данные: сканер блоков (`dydx-scanner`, реестр адресов растёт),
детекторы каждые 5 мин (`dydx-detectors.timer`), лидерборд каждые 6 ч
(`dydx-leaderboard.timer`), watchdog-отчёт 1-го числа.

## Инструменты MCP (18)

Данные: `list_markets`, `market_detail`, `candles`, `recent_trades`, `height`
· Аналитика: `funding_heatmap(min_oi_usd)`, `market_ta`, `suggest_stops`,
`trader_profile`, `trader_pnl_stats(limit≤5000)`, `fills_review`
· Обнаружение: `market_digest` (брифинг одной командой — начинать с него),
`leaderboard`, `discover_traders`, `list_traders`, `registry_stats`,
`latest_events`, `usage_stats`
DYDX_ETH_KEY пользователя и явного подтверждения человека (ключи не
покидают хост; причины — см. signer в репо).

## Быстрый путь без MCP-клиента

```bash
cd /root/ventures/dydx-grant/agent-gateway && .venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from dydx_mcp import server as s
import json; print(json.dumps(s.market_digest(), indent=1)[:800])"
```

Полноценные подключения (stdio / конфиги Claude Desktop, Codex, Cursor):
`examples/` в репо.

## Важные особенности данных

Читать `references/data-gotchas.md` (5 задокументированных граблей
indexer API: порядок свечей, netTransfers, priceChange24H, subticksPerTick,
отсутствие фида ликвидаций). Короткое правило: фандинг без фильтра
OI ≥ $100k — шум.

## Куда смотреть ещё

- Отчёты: `reports/` (data-quality watchdog помесячно, дайджесты)
- Дорожная карта: `/root/ventures/ROADMAP.md`
- Не путать с xtrading-ботом (BingX) — отдельный проект пользователя.
