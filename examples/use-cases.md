# Real Trading Problems Solved

Five scenarios a trader faces daily — solved with single MCP calls.

## 1. "Is this trader on Twitter actually profitable?"

**Pain:** Screenshots lie. Aggregators show stale data. You need verified numbers before copying.

```
→ leaderboard(limit=5, metric="pnl_window")

  dydx1qqeac9sjya8…  PnL $2,782 | Equity $5,726 | WinRate 56% | ROI 48.6%
  dydx1hqamt3pmez8…  PnL $217   | Equity $300   | WinRate 58% | ROI 72.2%
  
  Every entry carries identity_residual ($0.0000 = data verified)
  farmer_flag marks reward-farming bots
```

**Why it matters:** No other tool verifies PnL against the deposit-adjusted equity curve. If residual ≠ 0, the numbers lie.

## 2. "Is the market calm or about to storm?"

**Pain:** You want to enter, but a liquidation cascade could wipe you in minutes.

```
→ latest_events(limit=15)

  🔴 CASCADE SOL-USD: OI -21.3% px +3.9% SHORTS (confirmed_6h)
  🔴 CASCADE BTC-USD: OI -5.5%  px +2.1% SHORTS (fresh_2h)
  🔴 CASCADE XMR-USD: OI -6.5%  px -1.7% LONGS  (fresh_2h)
  📊 OI-SPIKE  ETH-USD: OI +10.9% at px +0.2%  ← silent accumulation

  VERDICT: 5 cascades — STORM. SHORTS being liquidated → squeeze up.
```

**Why it matters:** The signature detector catches |Δprice|↑ + OI↓ patterns that precede cascades — before they hit your position.

## 3. "Where is smart money accumulating?"

**Pain:** Big players build positions quietly. You want to see it before the move.

```
→ latest_events(kind="oi_spike_no_price")

  🎯 ETH-USD: OI +10.9% while price flat (+0.2%)
     Funding: +0.0046%/1h — longs paying (bullish bias)
     Volume: $19.6M in 24h
     RSI 73, trend up
     
  Signal: someone added $2M+ in OI without moving the price.
```

**Why it matters:** OI spikes without price movement = accumulation or distribution. Combined with funding direction, this reveals positioning before charts show it.

## 4. "What's my portfolio risk if BTC drops 5%?"

**Pain:** You hold alts, BTC sneezes. How much do you lose?

```
→ correlation("ETH-USD", "BTC-USD", "1HOUR", 168)
→ correlation("SOL-USD", "BTC-USD", "1HOUR", 168)
→ correlation("AVAX-USD", "BTC-USD", "1HOUR", 168)

  ETH:  beta +1.19, r=0.88 → BTC -5% → ETH -6.0%
  SOL:  beta +1.28, r=0.77 → BTC -5% → SOL -6.4%
  AVAX: beta +0.82, r=0.38 → BTC -5% → AVAX -4.1%
  
  Portfolio impact: ~-5.5% average. SOL is the riskiest holding.
```

**Why it matters:** Beta and correlation from actual dYdX candle data — not generic estimates. One call per pair, instant result.

## 5. "Where should I place my stop?"

**Pain:** Stops too tight get hunted, too wide lose money. You need data-driven levels.

```
→ suggest_stops("SOL-USD", side="long")

  Entry:      $104.4550
  Stop loss:  $103.0129  (1.5 ATR below)
  Take profit:$106.8596  (2.5 ATR above)
  Risk/RR:    1.67
  Breakeven:  $105.4171  (after +1 ATR move)
```

**Why it matters:** ATR-based stops adapt to current volatility. In calm markets, stops tighten. In storms, they widen. No more fixed percentages.

---

## Bonus: The identity check nobody else does

```
→ trader_pnl_stats(address)

  identity_residual: $0.0000  ← equity-Δ = Δpnl + Σtransfers
  
  If this ≠ 0, the platform data is wrong.
  We verify it on every account, every time.
```

This is the `market_digest` of trust — one number that proves the data isn't lying.

---

# Analyst Workflows

Six scenarios for researchers, report writers, and on-chain investigators.

## A1. "I need a morning briefing in 5 minutes"

**Pain:** Daily reports require 10 browser tabs, manual copy-paste, and stale screenshots.

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

**Pain:** Fact-checking claims requires pulling historical data from multiple sources.

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

**Pain:** For an event report, you need the timeline: price action, OI changes, and interpretation.

```
→ candles("SOL-USD", "1HOUR", 12)

  13:00  OI 56,854  ← OI starts dropping
  14:00  price +3.3%  ← sharp move up
  15:00  OI 48,297   ← OI down -15% from peak

  TOTAL 12h: price +3.9% | OI -18.8%
  
  INTERPRETATION: Price ↑ + OI ↓ = SHORT SQUEEZE
  Positions were force-closed, not new longs entering.
```

The OI-in-candles feature lets you distinguish genuine buying from forced liquidation — critical for accurate reporting.

## A4. "Compare two traders' execution styles"

**Pain:** Understanding WHO is a real trader vs a bot requires execution data.

```
→ fills_review(address) for two top traders

  Trader #1: maker_share 0% → aggressive (market orders, momentum)
  Trader #2: maker_share 0% → aggressive
  
  Both: identity_residual $0.0000 → data verified
  Both: day_winrate 56% → similar hit rate
```

Maker/taker split reveals execution strategy. Combined with PnL identity check, you can separate genuine alpha from wash trading.

## A5. "What's the market structure right now?"

**Pain:** Regime detection requires cross-asset analysis that's manual and slow.

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

This is a market structure report in 20 seconds. High correlations + overbought RSI = elevated cascade risk.

## A6. "Verify data quality before publishing"

**Pain:** Your reputation depends on accuracy. One wrong number destroys credibility.

```
→ trader_pnl_stats(address) for top 3 traders

  dydx1qqeac9…  residual $0.0000  ✓
  dydx15y4tcc…  residual $0.0000  ✓
  dydx1kajhdcm… residual $0.0000  ✓

  ALL VERIFIED — safe to publish.
  
  Check: equity-Δ = Δpnl + ΣnetTransfers (on every account)
```

**This is unique.** No other analytics tool verifies its own data against the fundamental accounting identity. If residual ≠ 0, the platform data is wrong — and now you know before your readers do.

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
