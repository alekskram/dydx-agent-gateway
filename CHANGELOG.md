# Changelog

## v0.2.4 (2026-09-02) — pre-publication hardening (MEC-26)
- Crash fixes (found in the MEC-21 guild review, each with a regression test):
  pnl_engine.compute no longer raises on None equity/totalPnl/netTransfers
  fields (API nulls) or on a single history point (ZeroDivisionError in the
  summary line); market_digest/leaderboard summaries no longer raise
  TypeError on NULL pnl_window (rows from accounts with 'no pnl history').
- api.markets() now filters FINAL_SETTLEMENT (settled) markets: 197 of 296
  listings were dead but still leaked zero-volume rows into list_markets and
  stale nonzero funding rates into funding_heatmap/detectors. Live markets
  only (status == ACTIVE) by default.
- server.json rebuilt against the official MCP Registry server schema
  (2025-12-11): 0 validation errors — description <= 100 chars, name
  `io.github.ventures/dydx-agent-gateway` placeholder (GitHub org pending),
  registryType + transport{stdio} in the package, repository block added,
  $schema URL fixed (old raw.githubusercontent URL was 404).
- Demo numbers in README/README.ru dated "as of 2026-08" (kept, not scrubbed,
  per owner decision).
- Version bump 0.2.3 -> 0.2.4 (pyproject, FastMCP server, SKILL.md).

## v0.2.1 (2026-08-25) — QA-проход: полное ревью и тестирование
- Тесты: pytest-структура (49 офлайн + 5 online, маркер online), покрытие
  dydx_mcp 75% (было ~8% функций); dev-extras [dev]; CI-workflow готов
- 7 багов найдено и исправлено с регресс-тестами: key_from_hex короткие
  ключи; дедуп событий не истекал (формат ts); prune переудаление;
  market_ta краш на плоских свечах; утечка соединения equity_jumps;
  ГРАНИЧНЫЕ ДУБЛИ пагинации PnL (живой тест); isError-семантика невалидного
  тикера (ValueError)
- Chaos 4/4: restore-drill, SIGKILL-идемпотентность сканера (+23=+23),
  нагрузка 20 клиентов/0 ошибок, state выживает force-reinstall
- QA-отчёт: reports/qa-report.md

## v0.1.1 (2026-08-25)
- `trader_pnl_stats(limit)` — агентам доступна глубина истории до 5000
  точек (~7 месяцев); по умолчанию 1000 (~42 дня, быстро)
- `market_digest` — одно-вызовной брифинг: события детекторов + фандинг
  + топ лидерборда
- `usage_stats` + учёт вызовов инструментов (middleware → sqlite) —
  метрики тракции для грантовых KPI (вызовы/24ч/7д, топ инструментов)
- `watchdog.py` + таймер dydx-watchdog (1-е число, 09:00) — data-quality
  отчёт генерируется автоматически
- README: юнит dydx-backup в таблице автоматки, ссылка на deploy-public.md
- fastmcp-баннер отключён (stdio/HTTP)

## v0.1.0 (2026-08-24)
- 19 MCP-инструментов: данные, аналитика, лидерборд, события, скринер
- PnL-движок: депозит-скорр. кривая, day-винрейт, maxDD, сверка тождества
  (остаток $0.00 на живых данных), пагинация истории до 5000 точек
- Блочный сканер → реестр адресов (bech32 BIP-173, идемпотентность)
- Детекторы: funding_extreme, oi_spike_no_price, liq_cascade_signature
  (валидирован историей: 47 сигнатурных часов/7д), equity_jump
- Подписыватель EIP-712 (Order, ApiCredentials; 12/12 самотестов)
- pip-пакет (pyproject, консольная точка входа), examples для Claude
  Desktop/Codex/Cursor, скилл, HTTP+stdio транспорты
- systemd: 5 юнитов + hardening; WAL-безопасный бэкап (restore проверен)
- Тесты: suite 15/15; найдены и исправлены API-грабли индексера (5 шт.)

## v0.2.0 (2026-08-25) — стандарты скиллов и MCP
- Скилл переписан по стандартам skill-creator: description EN с триггерами
  в видимой зоне (~250 симв), when_to_use (RU, детальные триггеры),
  metadata.agent.requires.bins; источник — .agents/skills/ в репо
  (обнаруживаемый корень), самодостаточен (references/data-gotchas.md),
  синхронизация с ~/.zcode/skills задокументирована
- MCP-комплианс: tool annotations (readOnlyHint/destructiveHint/
  idempotentHint — 21 инструмент), instructions сервера (стратегия для
  агента), /health эндпоинт (custom_route)
- recent_traders → list_traders (различимость SEP-986 от recent_trades)
- server.json для официального MCP-реестра (reverse-DNS, черновик)
- deploy-public.md: origin/host-валидация, OAuth 2.1 заметка

## v0.2.3 — analytics-only release
- Trading tools (place_order / cancel_all / my_positions) removed from the
  MCP server by design decision: the public gateway is read-only analytics,
  holds no keys, signs nothing. Signer stays as a library module (offline
  selftest 12/12), unwired to any tool.
- demo3_order_consent.py removed; docs (EN/RU README, examples, skill)
  updated; tool count 21 -> 18.
