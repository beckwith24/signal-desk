# Active trading test: day trading, layering, pair trading

All rules fixed in advance (textbook parameters). Signals filled one bar late. Costs per side as shown. Stocks/ETFs: NVDA AMD AVGO PLTR TSLA MRVL MU GOOGL AAPL MSFT META QQQ SPY. Coins: BTC ETH SOL LINK AVAX. Per-year and Sharpe are for an equal-weight portfolio of the rule run on every ticker.

## 1a. Day trading stocks (hourly bars, Jan 2024 – Oct 2026)

| Rule | Cost bp/side | Per year % | Sharpe | Worst drop % | Time in % | Trades/ticker/yr | Avg net per trade (bp) | Sharpe 1st half | Sharpe 2nd half |
|---|---|---|---|---|---|---|---|---|---|
| Intraday momentum: last 30 min in the first hour's direction (long & short) | 0 | -1.0 | -0.21 | -9.1 | 14.0 | 247.7 | -0.4 | -0.23 | -0.18 |
| Intraday momentum: last 30 min in the first hour's direction (long & short) | 3 | -14.7 | -3.53 | -35.6 | 14.0 | 247.7 | -6.4 | -3.11 | -4.24 |
| Intraday momentum: last 30 min in the first hour's direction (long & short) | 6 | -26.5 | -6.86 | -57.2 | 14.0 | 247.7 | -12.4 | -5.99 | -8.31 |
| Intraday momentum, long only | 0 | 1.8 | 0.59 | -3.9 | 7.0 | 130.7 | 1.4 | 0.84 | 0.27 |
| Intraday momentum, long only | 3 | -5.9 | -1.94 | -15.8 | 7.0 | 130.7 | -4.6 | -1.33 | -2.85 |
| Intraday momentum, long only | 6 | -13.0 | -4.46 | -32.0 | 7.0 | 130.7 | -10.6 | -3.49 | -5.94 |
| First-hour direction, ride to the close (long & short) | 0 | 4.2 | 0.41 | -13.8 | 71.0 | 249.9 | 1.9 | 1.05 | -0.66 |
| First-hour direction, ride to the close (long & short) | 3 | -10.3 | -0.86 | -27.9 | 71.0 | 249.9 | -4.1 | 0.01 | -2.44 |
| First-hour direction, ride to the close (long & short) | 6 | -22.9 | -2.13 | -51.3 | 71.0 | 249.9 | -10.1 | -1.02 | -4.23 |
| Hourly RSI(2) dip-buy, flat overnight | 0 | 1.8 | 0.59 | -4.3 | 8.0 | 43.0 | 4.3 | 0.54 | 0.64 |
| Hourly RSI(2) dip-buy, flat overnight | 3 | -0.8 | -0.25 | -5.4 | 8.0 | 43.0 | -1.7 | -0.21 | -0.3 |
| Hourly RSI(2) dip-buy, flat overnight | 6 | -3.3 | -1.08 | -9.4 | 8.0 | 43.0 | -7.7 | -0.96 | -1.24 |
| Hourly trend (EMA 7/35), long only, flat overnight | 0 | 4.6 | 0.52 | -12.3 | 49.0 | 165.1 | 3.0 | 0.68 | 0.32 |
| Hourly trend (EMA 7/35), long only, flat overnight | 3 | -5.3 | -0.51 | -22.5 | 49.0 | 165.1 | -3.0 | -0.23 | -0.87 |
| Hourly trend (EMA 7/35), long only, flat overnight | 6 | -14.2 | -1.53 | -37.0 | 49.0 | 165.1 | -9.0 | -1.13 | -2.05 |
| Baseline: hold all day and night | 0 | 61.8 | 1.74 | -30.4 | 100.0 | 0.4 | 14399.9 | 1.22 | 2.46 |
| Baseline: hold 10:30 -> 16:00 every day (intraday only) | 0 | 9.6 | 0.58 | -15.9 | 86.0 | 250.7 | 4.3 | 0.63 | 0.53 |
| Baseline: hold 16:00 -> 10:30 only (overnight + first hour) | 0 | 47.5 | 1.79 | -30.1 | 14.0 | 250.4 | 16.5 | 1.09 | 2.64 |

## 1b. Short-term crypto trading (hourly bars, Oct 2024 – Oct 2026)

| Rule | Cost bp/side | Per year % | Sharpe | Worst drop % | Time in % | Trades/ticker/yr | Avg net per trade (bp) | Sharpe 1st half | Sharpe 2nd half |
|---|---|---|---|---|---|---|---|---|---|
| Hourly trend (EMA 24/96 = 1 day / 4 days), long only | 0 | -18.6 | -0.29 | -66.4 | 48.0 | 61.6 | -22.1 | 0.45 | -1.36 |
| Hourly trend (EMA 24/96 = 1 day / 4 days), long only | 10 | -28.0 | -0.58 | -72.6 | 48.0 | 61.6 | -42.1 | 0.2 | -1.72 |
| Hourly trend (EMA 24/96 = 1 day / 4 days), long only | 30 | -43.6 | -1.16 | -81.9 | 48.0 | 61.6 | -82.1 | -0.29 | -2.42 |
| Hourly RSI(2) dip-buy above 200-hour average (max 24 h) | 0 | 1.8 | 0.2 | -19.5 | 9.0 | 174.4 | 1.6 | 0.64 | -0.36 |
| Hourly RSI(2) dip-buy above 200-hour average (max 24 h) | 10 | -28.2 | -2.45 | -52.3 | 9.0 | 174.4 | -18.4 | -1.76 | -3.37 |
| Hourly RSI(2) dip-buy above 200-hour average (max 24 h) | 30 | -64.2 | -7.24 | -87.2 | 9.0 | 174.4 | -58.4 | -6.23 | -8.58 |
| Hourly Bollinger: buy 2σ below 20-hour average, sell at the average | 0 | -12.0 | -0.22 | -48.2 | 27.0 | 159.5 | -3.9 | -0.12 | -0.34 |
| Hourly Bollinger: buy 2σ below 20-hour average, sell at the average | 10 | -36.0 | -1.21 | -67.9 | 27.0 | 159.5 | -23.9 | -1.03 | -1.43 |
| Hourly Bollinger: buy 2σ below 20-hour average, sell at the average | 30 | -66.2 | -3.2 | -89.3 | 27.0 | 159.5 | -63.8 | -2.87 | -3.63 |
| Hold only in US hours (13:00-20:00 UTC) | 0 | -24.9 | -0.41 | -60.3 | 29.0 | 365.8 | -5.4 | -0.09 | -0.8 |
| Hold only in US hours (13:00-20:00 UTC) | 10 | -63.8 | -2.02 | -86.5 | 29.0 | 365.8 | -25.4 | -1.57 | -2.59 |
| Hold only in US hours (13:00-20:00 UTC) | 30 | -91.6 | -5.27 | -99.2 | 29.0 | 365.8 | -65.4 | -4.55 | -6.2 |
| Hold only outside US hours | 0 | 25.1 | 0.71 | -51.0 | 71.0 | 366.3 | 9.5 | 1.13 | 0.17 |
| Hold only outside US hours | 10 | -39.7 | -0.82 | -80.1 | 71.0 | 366.3 | -10.5 | -0.24 | -1.6 |
| Hold only outside US hours | 30 | -86.0 | -3.9 | -98.4 | 71.0 | 366.3 | -50.4 | -2.99 | -5.15 |
| Baseline: hold | 0 | -5.9 | 0.24 | -69.2 | 100.0 | 0.5 | 3000.9 | 0.77 | -0.44 |

## 2a. Layering the crypto trend trade (daily, 5 coins; train < 2021, test 2021+)

| Layering | Period | Per year % | Sharpe | Worst drop % | Return ÷ drop | Invested % |
|---|---|---|---|---|---|---|
| All in / all out (current rule) | train | 147.6 | 1.91 | -48.8 | 3.03 | 41.0 |
| All in / all out (current rule) | test | 51.8 | 1.23 | -52.8 | 0.98 | 39.0 |
| Layer by agreement: size = share of trend votes up | train | 141.3 | 1.96 | -45.3 | 3.12 | 41.0 |
| Layer by agreement: size = share of trend votes up | test | 53.0 | 1.28 | -46.6 | 1.14 | 39.0 |
| Pyramid: 1/3 at signal, +1/3 each 1 ATR higher | train | 140.3 | 1.96 | -34.0 | 4.12 | 35.0 |
| Pyramid: 1/3 at signal, +1/3 each 1 ATR higher | test | 52.7 | 1.34 | -41.1 | 1.28 | 32.0 |
| Average down: 1/3 at signal, +1/3 each 1 ATR lower | train | 49.8 | 1.93 | -19.9 | 2.5 | 15.0 |
| Average down: 1/3 at signal, +1/3 each 1 ATR lower | test | 21.1 | 1.24 | -23.6 | 0.89 | 15.0 |
| Scale out: full at signal, sell 1/3 at +3 ATR and +6 ATR | train | 50.4 | 1.52 | -42.6 | 1.18 | 22.0 |
| Scale out: full at signal, sell 1/3 at +3 ATR and +6 ATR | test | 18.6 | 0.85 | -39.5 | 0.47 | 23.0 |
| Risk-sized: full slot x (60% / coin's volatility), max 1 | train | 96.1 | 2.02 | -31.5 | 3.05 | 30.0 |
| Risk-sized: full slot x (60% / coin's volatility), max 1 | test | 27.3 | 0.98 | -44.9 | 0.61 | 30.0 |

## 2b. Layering stock dip-buys (daily, 13 stocks)

| Layering | Period | Per year % | Sharpe | Worst drop % | Return ÷ drop | Invested % |
|---|---|---|---|---|---|---|
| Single entry, full slot (what the bot does) | train | -0.5 | -0.02 | -12.9 | -0.04 | 8.0 |
| Single entry, full slot (what the bot does) | test | 8.5 | 1.05 | -8.9 | 0.95 | 12.0 |
| Scale in: 1/3 at signal, +1/3 on each lower close | train | 1.7 | 0.29 | -8.9 | 0.2 | 5.0 |
| Scale in: 1/3 at signal, +1/3 on each lower close | test | 5.6 | 0.96 | -8.0 | 0.71 | 7.0 |
| Size by how oversold (deeper dip = bigger) | train | -0.4 | -0.08 | -6.6 | -0.06 | 3.0 |
| Size by how oversold (deeper dip = bigger) | test | 3.6 | 1.06 | -3.3 | 1.09 | 5.0 |

## 3. Pair trading — crypto pairs (BTC-USD/ETH-USD, BTC-USD/SOL-USD, ETH-USD/SOL-USD, ETH-USD/LINK-USD, SOL-USD/AVAX-USD), medians across pairs

| Strategy | Period | Per year % | Sharpe | Worst drop % | Better Sharpe than 50/50 |
|---|---|---|---|---|---|
| 50/50, rebalanced monthly | train | 152.1 | 1.46 | -62.0 | 0/2 |
| 50/50, rebalanced monthly | test | 21.0 | 0.65 | -89.3 | 0/5 |
| Hold A only | train | 92.6 | 1.25 | -64.5 | 1/2 |
| Hold A only | test | 5.0 | 0.41 | -79.4 | 2/5 |
| Hold B only | train | 191.3 | 1.42 | -65.1 | 1/2 |
| Hold B only | test | 23.3 | 0.66 | -95.6 | 2/5 |
| Rotation: hold the stronger (28-day), checked every 7 bars | train | 120.0 | 1.25 | -67.0 | 0/2 |
| Rotation: hold the stronger (28-day), checked every 7 bars | test | 17.5 | 0.62 | -84.6 | 2/5 |
| Dual momentum: stronger one, cash if it is falling | train | 125.7 | 1.42 | -69.8 | 1/2 |
| Dual momentum: stronger one, cash if it is falling | test | 22.7 | 0.64 | -72.9 | 3/5 |
| Ratio tilt: overweight the laggard (25-75%), long only | train | 136.1 | 1.4 | -63.2 | 0/2 |
| Ratio tilt: overweight the laggard (25-75%), long only | test | 11.1 | 0.52 | -91.5 | 0/5 |

Test-period Sharpe by pair (crypto):

| pair | 50/50, rebalanced monthly | Dual momentum: stronger one, cash if it is falling | Hold A only | Hold B only | Ratio tilt: overweight the laggard (25-75%), long only | Rotation: hold the stronger (28-day), checked every 7 bars |
|---|---|---|---|---|---|---|
| BTC/ETH | 0.66 | 0.67 | 0.6 | 0.66 | 0.56 | 0.62 |
| BTC/SOL | 0.68 | 0.64 | 0.36 | 0.76 | 0.51 | 0.75 |
| ETH/LINK | 0.61 | 0.46 | 0.66 | 0.51 | 0.56 | 0.37 |
| ETH/SOL | 0.65 | 0.71 | 0.37 | 0.76 | 0.52 | 0.62 |
| SOL/AVAX | 0.25 | 0.38 | 0.41 | 0.06 | 0.21 | 0.42 |

## 3. Pair trading — stock pairs (NVDA/AMD, MSFT/GOOGL, QQQ/SPY, AVGO/MRVL, AAPL/MSFT, META/GOOGL), medians across pairs

| Strategy | Period | Per year % | Sharpe | Worst drop % | Better Sharpe than 50/50 |
|---|---|---|---|---|---|
| 50/50, rebalanced monthly | train | 33.1 | 1.02 | -32.0 | 0/6 |
| 50/50, rebalanced monthly | test | 24.6 | 0.91 | -45.8 | 0/6 |
| Hold A only | train | 33.2 | 0.98 | -40.8 | 2/6 |
| Hold A only | test | 18.8 | 0.78 | -39.1 | 2/6 |
| Hold B only | train | 29.0 | 0.86 | -32.3 | 1/6 |
| Hold B only | test | 27.6 | 0.9 | -44.3 | 2/6 |
| Rotation: hold the stronger (63-day), checked every 5 bars | train | 29.2 | 1.03 | -33.6 | 2/6 |
| Rotation: hold the stronger (63-day), checked every 5 bars | test | 30.5 | 0.94 | -46.2 | 2/6 |
| Dual momentum: stronger one, cash if it is falling | train | 17.6 | 0.73 | -31.5 | 1/6 |
| Dual momentum: stronger one, cash if it is falling | test | 24.9 | 0.82 | -34.4 | 1/6 |
| Ratio tilt: overweight the laggard (25-75%), long only | train | 35.0 | 1.04 | -32.4 | 2/6 |
| Ratio tilt: overweight the laggard (25-75%), long only | test | 22.2 | 0.9 | -45.1 | 1/6 |
| Market-neutral stat-arb (long one, short other, z ±2) | train | 0.9 | 0.15 | -10.4 | 0/6 |
| Market-neutral stat-arb (long one, short other, z ±2) | test | 4.4 | 0.4 | -20.6 | 0/6 |

Test-period Sharpe by pair (stock):

| pair | 50/50, rebalanced monthly | Dual momentum: stronger one, cash if it is falling | Hold A only | Hold B only | Market-neutral stat-arb (long one, short other, z ±2) | Ratio tilt: overweight the laggard (25-75%), long only | Rotation: hold the stronger (63-day), checked every 5 bars |
|---|---|---|---|---|---|---|---|
| AAPL/MSFT | 0.84 | 0.39 | 0.75 | 0.73 | 0.61 | 0.88 | 0.64 |
| AVGO/MRVL | 1.02 | 0.79 | 1.11 | 0.79 | 0.28 | 0.98 | 1.0 |
| META/GOOGL | 0.86 | 1.06 | 0.62 | 0.94 | 0.56 | 0.74 | 0.87 |
| MSFT/GOOGL | 0.95 | 0.86 | 0.73 | 0.94 | 0.53 | 0.93 | 1.07 |
| NVDA/AMD | 1.14 | 0.94 | 1.23 | 0.86 | -0.29 | 1.08 | 1.08 |
| QQQ/SPY | 0.87 | 0.73 | 0.81 | 0.93 | -0.34 | 0.82 | 0.71 |
