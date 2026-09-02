# dYdX Data-Quality Watchdog — 2026-08

Period: 2026-08-25T06:12:00+00:00 · generator: watchdog.py (automatic,
timer on the 1st of the month)

## PnL identity check (equity−Δ = Δpnl + ΣnetTransfers)

- Accounts checked: 29
- Residual < $0.01: **29/29** · maximum: $0.0000

## Registry and load

- Addresses in the registry (block scanner): 1306
- Tool calls since deployment: 0

## Persistent indexer API quirks

1. `netTransfers` in historical-pnl is a per-period flow, NOT cumulative
   (the naive interpretation would show a phantom 79.5% drawdown vs the
   real 11.9%).
2. `priceChange24H` in perpetualMarkets does not match the candle-derived
   price change — compute from candles.
3. Per-fill PnL in /v4/fills is absent on mainnet — winrate only via the
   historical-pnl curve.
4. The price subticks field is `subticksPerTick` (not subticksPerBase):
   price_subticks = price / tickSize * subticksPerTick.
5. /v4/candles and historical-pnl return newest-first (normalized in the
   gateway API layer). /v4/historicalFunding on mainnet — 404.
