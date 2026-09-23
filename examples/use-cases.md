# Real Trading Problems Solved

Five scenarios a trader hits daily. Each one closes with a single MCP call, and the outputs below are real captures.

## 1. "Is this trader on Twitter actually profitable?"

Screenshots lie and aggregators lag. Before copying anyone, pull the numbers yourself.

```
→ leaderboard(limit=5, metric="pnl_window")

  dydx1qqeac9sjya8…  PnL $2,782 | Equity $5,726 | WinRate 56% | ROI 48.6%
  dydx1hqamt3pmez8…  PnL $217   | Equity $300   | WinRate 58% | ROI 72.2%
  
  Every entry carries identity_residual ($0.0000 = data verified)
  farmer_flag marks reward-farming bots
```

Plenty of tools show PnL. This one checks it against the deposit-adjusted equity curve, and a non-zero residual means the numbers are lying. That check is the whole reason it exists.

## 2. "Is the market calm or about to storm?"

You want to enter. A cascade could wipe you in the next ten minutes.

```
→ latest_events(limit=15)

  🔴 CASCADE SOL-USD: OI -21.3% px +3.9% SHORTS (confirmed_6h)
  🔴 CASCADE BTC-USD: OI -5.5%  px +2.1% SHORTS (fresh_2h)
  🔴 CASCADE XMR-USD: OI -6.5%  px -1.7% LONGS  (fresh_2h)
  📊 OI-SPIKE  ETH-USD: OI +10.9% at px +0.2%  ← silent accumulation

  VERDICT: 5 cascades — STORM. SHORTS being liquidated → squeeze up.
```

The signature detector reads |Δprice|↑ + OI↓, the shape cascades take before they become visible on charts.

## 3. "Where is smart money accumulating?"

Big players build quietly. Seeing it before the move is the entire game.

```
→ latest_events(kind="oi_spike_no_price")

  🎯 ETH-USD: OI +10.9% while price flat (+0.2%)
     Funding: +0.0046%/1h — longs paying (bullish bias)
     Volume: $19.6M in 24h
     RSI 73, trend up
     
  Signal: someone added $2M+ in OI without moving the price.
```

OI up 11% on a flat price is someone absorbing supply. Add the funding direction and you know which side they are on while the chart still shows nothing.

## 4. "What's my portfolio risk if BTC drops 5%?"

You hold alts and BTC sneezes. What does it cost you?

```
→ correlation("ETH-USD", "BTC-USD", "1HOUR", 168)
→ correlation("SOL-USD", "BTC-USD", "1HOUR", 168)
→ correlation("AVAX-USD", "BTC-USD", "1HOUR", 168)

  ETH:  beta +1.19, r=0.88 → BTC -5% → ETH -6.0%
  SOL:  beta +1.28, r=0.77 → BTC -5% → SOL -6.4%
  AVAX: beta +0.82, r=0.38 → BTC -5% → AVAX -4.1%
  
  Portfolio impact: ~-5.5% average. SOL is the riskiest holding.
```

Beta and r come from actual dYdX candles, not a generic estimate. One call per pair, and the answer is immediate.

## 5. "Where should I place my stop?"

Tight stops get hunted. Wide ones bleed you slowly. Levels should come from volatility, not vibes.

```
→ suggest_stops("SOL-USD", side="long")

  Entry:      $104.4550
  Stop loss:  $103.0129  (1.5 ATR below)
  Take profit:$106.8596  (2.5 ATR above)
  Risk/RR:    1.67
  Breakeven:  $105.4171  (after +1 ATR move)
```

The levels ride ATR(14), so they tighten in calm tape and widen in storms. Fixed percentages stop being your problem.

---

## Bonus: The identity check nobody else does

```
→ trader_pnl_stats(address)

  identity_residual: $0.0000  ← equity-Δ = Δpnl + Σtransfers
  
  If this ≠ 0, the platform data is wrong.
  We verify it on every account, every time.
```

One number, and you know whether the rest can be trusted.

---

# Analyst Workflows

Six scenarios for researchers, report writers, and on-chain investigators.

## A1. "I need a morning briefing in 5 minutes"

A daily report used to mean ten tabs and copy-paste archaeology.

```
→ market_digest()

  EVENTS (5):
    liq_cascade_signature  SOL-USD   ← confirmed_6h, SHORTS liquidated
    liq_cascade_signature  BTC-USD   ← fresh_2h
    oi_spike_no_price      ETH-USD   ← OI +10.9% while price flat

  FUNDING EXTREMES: XMR, ONDO, ALGO
  TOP TRADERS: dydx1qqeac9… PnL $2,782 | dydx1hqamt3… PnL $217
```

One call → skeleton of your daily report. Every number is timestamped and sourced from the indexer.

## A2. "Someone said 'funding on XMR is crazy'. Verify before publishing."

Fact-checking a claim like this normally means digging through archives.

```
→ historical_funding("XMR-USD", limit=48)

  XMR — funding over 48 hours:
  Average: +0.0046%/1h → +40% annualized
  Direction: LONGS paying (bullish bias)
  
  vs ETH benchmark: +0.0002%/1h → +1.8% annualized
  
  VERDICT: XMR funding is 23x more expensive than ETH. "Crazy" confirmed.
```

Every number traceable to the indexer API. No screenshots needed.

## A3. "Reconstruct what happened with SOL"

An event report needs a timeline: what price did, what OI did, and what it means.

```
→ candles("SOL-USD", "1HOUR", 12)

  13:00  OI 56,854  ← OI starts dropping
  14:00  price +3.3%  ← sharp move up
  15:00  OI 48,297   ← OI down -15% from peak

  TOTAL 12h: price +3.9% | OI -18.8%
  
  INTERPRETATION: Price ↑ + OI ↓ = SHORT SQUEEZE
  Positions were force-closed, not new longs entering.
```

Because candles carry OI, you can tell genuine buying from forced liquidation. That difference decides whether your report is right.

## A4. "Compare two traders' execution styles"

Real trader or bot? The answer lives in the fills, not the PnL.

```
→ fills_review(address) for two top traders

  Trader #1: maker_share 0% → aggressive (market orders, momentum)
  Trader #2: maker_share 0% → aggressive
  
  Both: identity_residual $0.0000 → data verified
  Both: day_winrate 56% → similar hit rate
```

The maker/taker split exposes execution style; the identity check rules out phantom numbers. Together they separate alpha from wash trading.

## A5. "What's the market structure right now?"

Regime detection is cross-asset work, and doing it by hand takes an afternoon.

```
→ correlation + market_ta across assets

  CORRELATIONS (1H, 7 days):
    ETH↔BTC: r=0.88 (strong)   | β=+1.19
    SOL↔BTC: r=0.77 (moderate) | β=+1.28
    SOL↔ETH: r=0.76 (moderate) | β=+0.94

  VOLATILITY (annualized):
    BTC: 36% | ETH: 49% | SOL: 59%

  BTC REGIME: short-term up (RSI 82) | long-term up (RSI 72)
  → TRENDING MARKET (up) — high correlations, cascades likely on reversal
```

Twenty seconds for a full structure read. High correlations with an overbought RSI is exactly the combo that precedes cascades on reversal.

## A6. "Verify data quality before publishing"

One wrong number in a published report costs more than a week of being late.

```
→ trader_pnl_stats(address) for top 3 traders

  dydx1qqeac9…  residual $0.0000  ✓
  dydx15y4tcc…  residual $0.0000  ✓
  dydx1kajhdcm… residual $0.0000  ✓

  ALL VERIFIED — safe to publish.
  
  Check: equity-Δ = Δpnl + ΣnetTransfers (on every account)
```

No other analytics tool we know verifies its own data against the accounting identity. A non-zero residual means the upstream numbers are wrong, and now you know it before your readers do.

---

## Summary: 12 problems solved

| # | Problem | Tool | Time |
|---|---|---|---|
| T1 | Verify trader claims | `leaderboard` | 3s |
| T2 | Storm detection | `latest_events` | 3s |
| T3 | Smart money tracking | OI spikes | 5s |
| T4 | Portfolio risk (BTC -5%) | `correlation` × N | 20s |
| T5 | Where to place stops | `suggest_stops` | 3s |
| A1 | Morning briefing | `market_digest` | 3s |
| A2 | Fact-check funding claims | `historical_funding` | 5s |
| A3 | Reconstruct market event | `candles` + OI | 10s |
| A4 | Compare trader styles | `fills_review` | 15s |
| A5 | Market structure/regime | `correlation` + `market_ta` | 20s |
| A6 | Verify data before publishing | `trader_pnl_stats` | 5s |
| A7 | Find research subjects | `discover_traders` | 10s |
