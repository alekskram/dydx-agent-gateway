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
