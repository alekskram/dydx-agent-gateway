---
name: dydx-gateway
description: dYdX v4 перпетуалы через локальный MCP-шлюз dydx-agent-gateway — рыночные данные, фандинг-хитмап, теханализ, верифицированный лидерборд трейдеров, PnL-профили любых адресов, аномалии и сигнатуры каскадов ликвидаций. Использовать, когда пользователь спрашивает про dYdX, перпы на dYdX, трейдеров dYdX по адресу, аномалии OI/фандинга/ликвидаций.
metadata:
  author: ventures
  version: "0.1.0"
  requires:
    services: ["dydx-mcp.service"]
---

# dYdX Agent Gateway (локальный MCP-сервер)

Шлюз развёрнут на этом хосте: `repo`,
endpoint **http://127.0.0.1:8901/mcp** (streamable HTTP, systemd-юнит
`dydx-mcp.service`; проверить: `systemctl is-active dydx-mcp`).
Фоновые данные: сканер блоков (`dydx-scanner.service`, реестр адресов
растёт), детекторы каждые 5 мин (`dydx-detectors.timer`), лидерборд каждые
6ч (`dydx-leaderboard.timer`).

## Когда использовать

- Вопросы по dYdX: рынки, цены, фандинг, OI, объёмы, свечи
- Анализ трейдера по адресу (equity, PnL-кривая, day-винрейт, maxDD,
  флаг фармера) — например перед копитрейдингом
- Лидерборд/скрининг активных трейдеров (обнаружение с цепи)
- Аномалии: тишина vs всплески OI, экстремальный фандинг, ПРЫЖКИ equity,
  сигнатуры каскадов ликвидаций (цена+OI)
- ATR-планы стопов/тейков, базовый TA (RSI/EMA/BB/ATR)

## Инструменты MCP (19)

Данные: `list_markets(limit, sort)`, `market_detail(ticker)`,
`candles(ticker, resolution, limit)`, `recent_trades(ticker, limit)`,
`height` · Аналитика: `funding_heatmap(limit, min_oi_usd)`,
`market_ta(ticker, resolution)`, `suggest_stops(ticker, side, …)`,
`trader_profile(address)`, `trader_pnl_stats(address)`,
`fills_review(address)` · Обнаружение: `leaderboard(limit, metric)`,
`discover_traders(limit, min_equity)`, `recent_traders(limit, max_hits)`,
`registry_stats`, `latest_events(limit, kind?)` · Торговля: `place_order`,
`cancel_all`, `my_positions` (требуют DYDX_ETH_KEY пользователя; НЕ
вызывать без явного подтверждения человека).

## Как вызывать (быстрый путь — без MCP-клиента)

Каждый инструмент — обычная python-функция:
```bash
cd repo && .venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from dydx_mcp import server as s
import json; print(json.dumps(s.funding_heatmap(5), indent=1))"
```
Полноценно по MCP (stdio-сервер): `.venv/bin/python -m dydx_mcp.server`;
конфиги для Claude Desktop/Codex/Cursor: `examples/`.

## Важные особенности данных (найдены нами, не в доках)

1. Свечи и historical-pnl приходят newest-first — наш api-слой уже
   нормализует; при прямых запросах к indexer.dydx.trade учитывай сам.
2. `priceChange24H` из API некорректен — считай по свечам.
3. `netTransfers` в historical-pnl — по-бакетный поток, не кумулятив.
4. Экстремальный фандинг на рынках с OI<$100k — шум (пример: CRO
   «+2967% годовых» при OI $4.5k). Всегда фильтруй по OI.
5. Публичного фида ликвидаций нет — каскады ловим сигнатурой
   (|Δцены|↑ + OI↓ одновременно), события `liq_cascade_signature`.

## Куда смотреть ещё

- Отчёты: `reports/` (data-quality watchdog, дайджесты странного)
- Дорожная карта: `/root/ventures/ROADMAP.md`
- Не путать с xtrading-ботом (BingX) — это отдельный проект пользователя.
