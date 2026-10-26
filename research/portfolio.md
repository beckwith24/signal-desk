# Portfolio test: diversified, trend-following, risk-sized vs what the bot does now

Daily closes from backtest/bars.csv.gz. Signal at the close, filled at the next day's close. Costs: stocks 5 bp, crypto 30 bp per side. Train = before 2021, test = 2021 on. Nothing fitted. The stock list is today's favourites, so absolute stock returns are flattered; compare rows with each other, not with the market.

## Whole portfolio — train

| Strategy | Per year % | Sharpe | Worst drop % | Return ÷ drop | Volatility % | Invested % |
|---|---|---|---|---|---|---|
| Hold SPY only | 14.8 | 0.74 | -33.7 | 0.44 | 22.1 | 100.0 |
| SPY-based: 80% SPY / 20% crypto held | 41.0 | 1.36 | -36.3 | 1.13 | 28.1 | 100.0 |
| SPY-based: 80% SPY / 20% crypto trend | 34.1 | 1.46 | -29.9 | 1.14 | 21.8 | 86.0 |
| SPY-based: same, 12% vol target | 24.6 | 1.83 | -15.5 | 1.59 | 12.5 | – |
| Hold: 80% stock basket / 20% crypto | 67.2 | 1.69 | -38.3 | 1.75 | 33.9 | 99.0 |
| Bot today (dips only, no crypto) | -0.9 | -0.02 | -15.1 | -0.06 | 11.5 | 13.0 |
| NEW: 80% stocks (basket) / 20% crypto trend | 60.4 | 1.81 | -30.2 | 2.0 | 28.4 | 86.0 |
| NEW: 80% stocks (top-third strength) / 20% crypto trend | 77.0 | 1.95 | -34.1 | 2.26 | 31.9 | 74.0 |
| NEW: 80% stocks (basket + SPY filter) / 20% crypto trend | 45.5 | 1.75 | -20.8 | 2.19 | 23.0 | 72.0 |
| NEW + 15% vol target | 47.4 | 2.45 | -19.5 | 2.43 | 16.4 | – |

## Whole portfolio — test

| Strategy | Per year % | Sharpe | Worst drop % | Return ÷ drop | Volatility % | Invested % |
|---|---|---|---|---|---|---|
| Hold SPY only | 15.0 | 0.93 | -24.5 | 0.61 | 16.6 | 100.0 |
| SPY-based: 80% SPY / 20% crypto held | 26.8 | 1.12 | -38.3 | 0.7 | 23.8 | 100.0 |
| SPY-based: 80% SPY / 20% crypto trend | 23.0 | 1.33 | -21.6 | 1.07 | 16.6 | 86.0 |
| SPY-based: same, 12% vol target | 16.4 | 1.3 | -16.2 | 1.02 | 12.3 | – |
| Hold: 80% stock basket / 20% crypto | 46.2 | 1.29 | -55.3 | 0.84 | 33.8 | 100.0 |
| Bot today (dips only, no crypto) | 11.1 | 1.07 | -11.6 | 0.96 | 10.3 | 15.0 |
| NEW: 80% stocks (basket) / 20% crypto trend | 42.7 | 1.44 | -41.8 | 1.02 | 27.3 | 86.0 |
| NEW: 80% stocks (top-third strength) / 20% crypto trend | 54.8 | 1.44 | -47.7 | 1.15 | 34.6 | 86.0 |
| NEW: 80% stocks (basket + SPY filter) / 20% crypto trend | 31.3 | 1.32 | -38.2 | 0.82 | 22.6 | 71.0 |
| NEW + 15% vol target | 27.6 | 1.59 | -25.1 | 1.1 | 16.2 | – |

## Stock sleeve — train

| Strategy | Per year % | Sharpe | Worst drop % | Return ÷ drop | Volatility % | Invested % |
|---|---|---|---|---|---|---|
| Stocks: hold basket (equal weight) | 42.9 | 1.3 | -35.1 | 1.22 | 31.4 | 100.0 |
| Stocks: basket, cash when SPY < 200-day | 26.2 | 1.12 | -26.1 | 1.0 | 23.1 | 82.0 |
| Stocks: top third by 6-month strength | 75.5 | 1.62 | -39.6 | 1.91 | 39.5 | 100.0 |
| Stocks: basket, inverse-volatility weights | 37.3 | 1.23 | -32.2 | 1.16 | 29.5 | 100.0 |
| Bot today: buy dips (RSI2 proxy), 10% slots | -0.9 | -0.02 | -15.1 | -0.06 | 11.5 | 13.0 |
| Stocks: hold SPY | 14.8 | 0.74 | -33.7 | 0.44 | 22.1 | 100.0 |

## Stock sleeve — test

| Strategy | Per year % | Sharpe | Worst drop % | Return ÷ drop | Volatility % | Invested % |
|---|---|---|---|---|---|---|
| Stocks: hold basket (equal weight) | 38.1 | 1.19 | -46.6 | 0.82 | 31.2 | 100.0 |
| Stocks: basket, cash when SPY < 200-day | 24.6 | 1.01 | -41.6 | 0.59 | 25.0 | 81.0 |
| Stocks: top third by 6-month strength | 52.2 | 1.23 | -53.3 | 0.98 | 41.1 | 100.0 |
| Stocks: basket, inverse-volatility weights | 30.8 | 1.15 | -42.3 | 0.73 | 26.5 | 100.0 |
| Bot today: buy dips (RSI2 proxy), 10% slots | 11.1 | 1.08 | -11.6 | 0.96 | 10.3 | 15.0 |
| Stocks: hold SPY | 15.1 | 0.93 | -24.5 | 0.62 | 16.6 | 100.0 |

## Crypto sleeve — train

| Strategy | Per year % | Sharpe | Worst drop % | Return ÷ drop | Volatility % | Invested % |
|---|---|---|---|---|---|---|
| Crypto: hold all 5 (equal weight) | 146.5 | 1.46 | -83.9 | 1.75 | 89.5 | 100.0 |
| Crypto: hold Bitcoin only | 95.9 | 1.24 | -83.4 | 1.15 | 80.7 | 100.0 |
| Crypto: trend rule (3 of 4) | 157.0 | 1.94 | -48.8 | 3.22 | 56.7 | 43.0 |
| Crypto: trend rule + BTC weekly up | 118.0 | 1.73 | -37.2 | 3.17 | 52.8 | 31.0 |

## Crypto sleeve — test

| Strategy | Per year % | Sharpe | Worst drop % | Return ÷ drop | Volatility % | Invested % |
|---|---|---|---|---|---|---|
| Crypto: hold all 5 (equal weight) | 45.4 | 0.88 | -84.8 | 0.54 | 76.4 | 100.0 |
| Crypto: hold Bitcoin only | 19.8 | 0.6 | -76.6 | 0.26 | 56.9 | 100.0 |
| Crypto: trend rule (3 of 4) | 51.8 | 1.23 | -52.8 | 0.98 | 40.9 | 39.0 |
| Crypto: trend rule + BTC weekly up | 49.4 | 1.25 | -38.7 | 1.28 | 38.1 | 32.0 |

## Crypto rule robustness (test period: neighbouring settings, harsher costs, slower fills)

| 28-day momentum → | BTC average | Cost bp | Fill lag (days) | Per year % | Sharpe | Worst drop % |
|---|---|---|---|---|---|---|
| 14 | 30 | 30 | 1 | 27.2 | 0.87 | -41.1 |
| 14 | 50 | 30 | 1 | 35.0 | 1.02 | -37.4 |
| 14 | 100 | 30 | 1 | 42.3 | 1.16 | -33.5 |
| 21 | 30 | 30 | 1 | 34.9 | 1.02 | -38.7 |
| 21 | 50 | 30 | 1 | 45.1 | 1.19 | -37.3 |
| 21 | 100 | 30 | 1 | 55.6 | 1.36 | -36.0 |
| 28 | 30 | 30 | 1 | 34.3 | 1.0 | -40.8 |
| 28 | 50 | 30 | 1 | 49.4 | 1.25 | -38.7 |
| 28 | 100 | 30 | 1 | 61.1 | 1.43 | -32.7 |
| 42 | 30 | 30 | 1 | 21.8 | 0.72 | -54.2 |
| 42 | 50 | 30 | 1 | 36.8 | 1.0 | -44.0 |
| 42 | 100 | 30 | 1 | 48.3 | 1.19 | -40.7 |
| 56 | 30 | 30 | 1 | 30.2 | 0.92 | -52.7 |
| 56 | 50 | 30 | 1 | 42.9 | 1.13 | -43.6 |
| 56 | 100 | 30 | 1 | 50.2 | 1.23 | -39.5 |
| 28 | 50 | 60 | 1 | 41.9 | 1.11 | -43.1 |
| 28 | 50 | 120 | 1 | 27.9 | 0.84 | -52.6 |
| 28 | 50 | 30 | 0 | 54.8 | 1.36 | -32.2 |
| 28 | 50 | 30 | 2 | 56.4 | 1.37 | -32.1 |
