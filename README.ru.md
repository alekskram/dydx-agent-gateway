# dYdX Agent Gateway (RU)

> English version: [README.md](README.md). Этот файл — русская версия документации.

MCP-сервер: любой ИИ-агент подключается к dYdX v4 — рыночные данные,
аналитика трейдеров. Только аналитика by design — без торговли и ключей.

## Установка (для чужих машин)

Пакет `dydx-agent-gateway` ставится из git (после публикации репо) или
PyPI (позже). Ниже `REPO_URL` = адрес репозитория.

**Claude Code (одной командой):**
```bash
claude mcp add dydx -- uvx --from git+REPO_URL dydx-agent-gateway
```

**Cursor / любой mcp.json:**
```json
{"mcpServers": {"dydx": {
  "command": "uvx", "args": ["--from", "git+REPO_URL", "dydx-agent-gateway"]}}}
```

**Claude Desktop** (stdio, локально): см. `examples/claude-desktop/config.json`
— команда `uvx --from git+REPO_URL dydx-agent-gateway`.

**Hosted вариант:** `dydx-agent-gateway --http --port 8901`, затем в любом
клиенте `{"mcpServers": {"dydx": {"type": "http", "url": "http://host:8901/mcp"}}}`.

**ZCode/Claude Code скилл:** скопировать `.agents/skills/dydx-gateway/` в
`~/.zcode/skills/` (или `.claude/skills/`) — агент получает инструкцию
по инструментам и всем известным API-граблям.

**Только Python (без агента):**
```bash
uvx --from git+REPO_URL python -c "..."   # или: pip install git+REPO_URL
```

Зависимости: fastmcp, pycryptodome, ecdsa (ставятся сами). Ровно
`pip install .` в чистом venv проверен: market/trader-инструменты работают
сразу.

## Запуск (stdio, для Claude Desktop / Codex / любого MCP-клиента)

```bash
python -m dydx_mcp.server
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dydx": {
      "command": "python",
      "args": ["-m", "dydx_mcp.server"],
      "cwd": "/path/to/agent-gateway"
    }
  }
}
```

## Инструменты (18, все read-only и без ключей)

Публичные (без ключей):
- `list_markets(limit, sort)` — рынки: цена, объём 24ч, OI, фандинг
- `market_detail(ticker)` — рынок глубоко + свечи + честный 24ч-изм. (по свечам!)
- `candles(ticker, resolution, limit)` — OHLCV+OI (1MIN…1DAY)
- `recent_trades(ticker, limit)` — лента сделок
- `funding_heatmap(limit)` — фандинг всех рынков, ranked, годовая нормализация
- `market_ta(ticker, resolution)` — RSI14, EMA20/50, ATR14, Bollinger %B
- `suggest_stops(ticker, side, …)` — ATR-план: SL/TP/breakeven/trailing + RR
- `trader_profile(address)` — equity, позиции, кривая PnL любого трейдера
- `trader_pnl_stats(address)` — дневной PnL, day-винрейт, maxDD (деп.-скорр.),
  sharpe-like, сверка тождества (фантом-детектор; живая проверка: $0.00)
- `fills_review(address)` — maker/taker, объёмы, рынок-микс
- `registry_stats` — статистика реестра адресов из сканера блоков
- `list_traders(limit, max_hits)` — свежие адреса из реестра (без коммиттеров)
- `discover_traders(limit, min_equity)` — скринер: фондированные активные
  трейдеры с цепи (реестр + проба equity) — стартовая точка для анализа
- `leaderboard(limit, metric)` — верифицированный топ трейдеров (батч
  каждые 6ч: реестр + PnL-движок + флаги фармеров, эвристика v0)
- `market_digest()` — брифинг одной командой: события + экстрим-фандинг +
  топ лидерборда (начинать с него)
- `usage_stats()` — счётчики вызовов инструментов с момента развёртывания
- `latest_events(limit, kind?)` — события детекторов: funding_extreme /
  oi_spike_no_price / equity_jump / liq_cascade_signature (шина событий
  в sqlite)
- `height` — высота цепи (liveness)

## Автоматика (systemd)

| Юнит | Что делает | Период |
|---|---|---|
| dydx-scanner.service | блоки → реестр адресов | непрерывно |
| dydx-mcp.service | MCP endpoint (HTTP) | непрерывно |
| dydx-detectors.timer | детекторы + алерты (TG/вебхуки) | каждые 5 мин |
| dydx-leaderboard.timer | пересборка лидерборда | каждые 6 ч |
| dydx-backup.timer | WAL-безопасный бэкап (backup.sh, 30 дней) | ежедневно 23:40 |

Публичный URL: инструкция именованного туннеля — `deploy-public.md`.

Алерты: `alerts.env` (DYDX_TG_BOT_TOKEN, DYDX_TG_CHAT_ID, DYDX_WEBHOOKS).

## Подключение агентов (`examples/`)

- `claude-desktop/config.json` (stdio) и `config-http.json` (hosted)
- `codex/config.toml`, `cursor/mcp.json`
- `python-agent.py` — автономный мини-агент: события → фандинг →
  лидерборд одним запуском (проверен живьём)
- `webhook-receiver.py` — приёмник вебхуков (проверен сквозной доставкой)
- `alerts.env.example` — Telegram/вебхуки для systemd-юнитов
- Промпты для агентов и инструкция — `examples/README.md`

## Отчёты

`reports/data-quality-2026-08.md` — watchdog №1: сверка тождества 25/25
аккаунтов (остаток $0.0000), реестр найденных API-граблей.

## Транспорты

- stdio: `python -m dydx_mcp.server` (локальные агенты, Claude Desktop)
- HTTP (streamable): systemd `dydx-mcp.service` → 127.0.0.1:8901/mcp —
  для публичного URL нужен reverse-proxy с TLS + auth-токен (в планах)

## Signer (`dydx_mcp/signer.py`)

Собственный zero-heavy-dep подписыватель: keccak256 (pycryptodome) + EIP-712
(Order / ApiCredentials; domain `dydx`/1/1337) + secp256k1 RFC6979 с
recovery-id + bech32 (dydx1…) + квантизация ордеров из живой меты рынка
(size → base-quantums кратно stepBaseQuantums; price → subticks через
tickSize/subticksPerTick). Самотест: 12/12 PASS (вектора keccak, рекавери
раунд-трип, low-S, packing, bech32 раунд-трип реального адреса, кванты):
`python -m dydx_mcp.signer --selftest`. Подписыватель офлайн-протестирован
и не подключён ни к одному MCP-инструменту — библиотека для тех, кто строит
свой слой исполнения.

## PnL-движок (`dydx_mcp/pnl_engine.py`)

Считает по кривой historical-pnl: дневной PnL, day-винрейт, maxDD на
депозит-скорректированном капитале, sharpe-like, лучшие/худшие дни.
Ключ: тождество equity-Δ = Δpnl + ΣnetTransfers (netTransfers — ПО-БАКЕТНЫЙ
поток, не кумулятив!) — остаток тождества = детектор фантомных данных.
Живая проверка: маркет-мейкер, 42 дня, остаток = $0.00, day-winrate 64.3%,
avg $433/день, maxDD 11.9%.

## Демо (`demos/`, всё через MCP-клиент in-process)

1. `demo1_funding_watch.py` — ватч фандинга: нашёл SHIB +0.147%/1h
   (≈+1284% годовых, лонги платят) — готовый алерт.
2. `demo2_trader_check.py` — DD-карта реального маркет-мейкера: equity
   $63.5k, PnL $488k, 68 позиций, 100 филлов, maker 21%.

## Сканер (`scanner.py` + systemd `dydx-scanner.service`)

Блоки dYdX-чейна → sqlite-реестр активных адресов (`data/registry.sqlite`),
с валидацией bech32-формы (43 символа). Работает как системный сервис:
`systemctl status dydx-scanner`; реестр растёт непрерывно. Разовый проход:
`python scanner.py --blocks 200`.

## Демо-сценарии (для X-треда и заявки в dYdX EDP)

1. «Агент следит за фандингом»: list_markets по |funding| каждые N минут,
   алерт при аномалии.
2. «Проверь трейдера перед копированием»: trader_profile по адресу из
   лидерборда — equity, позиции, динамика PnL.
