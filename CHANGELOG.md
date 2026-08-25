# Changelog

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
