# Combo test: four ideas vs the current signals (2026-10-14 02:23 UTC)

Excess = next-5-day return above the ticker's own average, t clustered by date. Strategy = equal weight across tickers, in while the rule is on, cash otherwise, costs in. Train = before 2021, test = 2021 on.

## Stocks (98 tickers)

**train**

| Rule | Signal days | Next 5d excess % | t | 5d winners % | Time in % | Rule: per yr % | worst drop % | Sharpe | Hold: per yr % | worst drop % | Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Current Strong Buy (2+ dip models) | 19406 | 0.45 | 4.16 | 60.6 | 5.4 | 2.0 | -6.6 | 0.57 | 16.9 | -46.7 | 0.87 |
| A: Strong Buy + own weekly trend up | 18137 | 0.47 | 4.51 | 60.8 | 5.1 | 1.7 | -6.6 | 0.53 | 16.9 | -46.7 | 0.87 |
| B: market-panic dip (RSI2<5, VIX panic, above 200d) | 4569 | 0.56 | 2.53 | 60.4 | 1.3 | 0.7 | -4.8 | 0.37 | 16.9 | -46.7 | 0.87 |
| D1: Strong Buy + S&P weekly trend up | 15687 | 0.47 | 3.98 | 60.9 | 4.4 | 1.1 | -6.8 | 0.36 | 16.9 | -46.7 | 0.87 |

**test**

| Rule | Signal days | Next 5d excess % | t | 5d winners % | Time in % | Rule: per yr % | worst drop % | Sharpe | Hold: per yr % | worst drop % | Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Current Strong Buy (2+ dip models) | 5792 | 0.39 | 2.42 | 56.8 | 4.1 | 1.7 | -3.2 | 0.83 | 19.2 | -23.0 | 1.2 |
| A: Strong Buy + own weekly trend up | 5496 | 0.37 | 2.33 | 56.6 | 3.9 | 1.5 | -3.0 | 0.82 | 19.2 | -23.0 | 1.2 |
| B: market-panic dip (RSI2<5, VIX panic, above 200d) | 807 | 2.01 | 5.48 | 69.8 | 0.6 | 0.8 | -0.6 | 1.0 | 19.2 | -23.0 | 1.2 |
| D1: Strong Buy + S&P weekly trend up | 4785 | 0.33 | 1.91 | 56.2 | 3.4 | 1.5 | -2.0 | 0.87 | 19.2 | -23.0 | 1.2 |

## Cryptos (29 tickers)

**train**

| Rule | Signal days | Next 5d excess % | t | 5d winners % | Time in % | Rule: per yr % | worst drop % | Sharpe | Hold: per yr % | worst drop % | Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Current trend rule (3 of 4) | 6705 | 1.15 | 3.0 | 51.4 | 35.7 | 105.6 | -50.2 | 1.58 | 163.3 | -89.2 | 1.54 |
| C: trend rule, volatility-sized | 6705 | 1.15 | 3.0 | 51.4 | 35.7 | 69.1 | -29.9 | 1.8 | 163.3 | -89.2 | 1.54 |
| D2: trend rule + Bitcoin weekly trend up | 4329 | 0.71 | 1.47 | 49.8 | 23.0 | 80.1 | -45.2 | 1.39 | 163.3 | -89.2 | 1.54 |
| E: trend rule on weekly bars | 4751 | 0.73 | 1.69 | 51.2 | 25.3 | 127.6 | -43.7 | 1.79 | 163.3 | -89.2 | 1.54 |

**test**

| Rule | Signal days | Next 5d excess % | t | 5d winners % | Time in % | Rule: per yr % | worst drop % | Sharpe | Hold: per yr % | worst drop % | Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Current trend rule (3 of 4) | 18944 | 1.7 | 5.25 | 50.8 | 31.7 | 65.7 | -46.8 | 1.49 | 29.0 | -81.7 | 0.72 |
| C: trend rule, volatility-sized | 18944 | 1.7 | 5.25 | 50.8 | 31.7 | 35.2 | -30.5 | 1.32 | 29.0 | -81.7 | 0.72 |
| D2: trend rule + Bitcoin weekly trend up | 13302 | 2.63 | 6.37 | 52.1 | 22.1 | 67.3 | -37.9 | 1.63 | 29.0 | -81.7 | 0.72 |
| E: trend rule on weekly bars | 12584 | 1.49 | 3.53 | 50.3 | 21.1 | 38.8 | -51.2 | 1.11 | 29.0 | -81.7 | 0.72 |

