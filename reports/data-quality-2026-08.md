# dYdX Data-Quality Watchdog — 2026-08

Период: 2026-08-25T06:12:00+00:00 · генератор: watchdog.py (авто, таймер 1-го числа)

## Сверка тождества PnL (equity−Δ = Δpnl + ΣnetTransfers)

- Проверено аккаунтов: 29
- Остаток < $0.01: **29/29** · максимум: $0.0000

## Реестр и нагрузка

- Адресов в реестре (блочный сканер): 1306
- Вызовов инструментов с деплоя: 0

## Постоянные особенности indexer API

1. `netTransfers` в historical-pnl — поток за период, НЕ кумулятив (наивная интерпретация дала бы фантомную просадку 79.5% vs реальные 11.9%).
2. `priceChange24H` в perpetualMarkets не соответствует изменению цены по свечам — считать по свечам.
3. Per-fill PnL в /v4/fills на мейннете отсутствует — винрейт только через кривую historical-pnl.
4. Поле субтиков цены — `subticksPerTick` (не subticksPerBase): price_subticks = price / tickSize * subticksPerTick.
5. /v4/candles и historical-pnl возвращают newest-first (нормализовано в api-слое шлюза). /v4/historicalFunding на мейннете — 404.
