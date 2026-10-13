# Factor test (2026-10-13 20:51 UTC)

Stocks: 99 of today's S&P 100. Coins: 29. Dropped: BK (no data for BK 1d), UNI-USD (no data for UNI-USD 1d), SUI-USD (no data for SUI-USD 1d), HYPE-USD (no data for HYPE-USD 1d).

Today's S&P 100 includes companies that grew into it, which flatters 'buy recent winners': treat the stock ranking numbers as an upper bound.

## 1. Stocks: relative strength (monthly)

**train**

| Strategy | Return/yr % | Sharpe | Worst drop % | vs equal weight %/yr | t | Periods ahead % |
|---|---|---|---|---|---|---|
| Equal weight, all stocks | 18.9 | 1.02 | -18.5 | – | – | – |
| Top third by 12-month strength | 20.5 | 1.09 | -16.5 | 1.3 | 0.33 | 52.6 |
| Top third by 6-month strength | 21.8 | 1.07 | -19.0 | 2.7 | 0.86 | 60.5 |
| Top third (12m) + above 200-day | 19.9 | 1.04 | -16.1 | 0.9 | 0.19 | 50.0 |
| Top third (12m), sized by volatility | 18.9 | 1.09 | -16.9 | -0.3 | -0.07 | 52.6 |

**test**

| Strategy | Return/yr % | Sharpe | Worst drop % | vs equal weight %/yr | t | Periods ahead % |
|---|---|---|---|---|---|---|
| Equal weight, all stocks | 18.9 | 1.26 | -22.1 | – | – | – |
| Top third by 12-month strength | 22.4 | 1.28 | -18.7 | 3.3 | 0.84 | 48.6 |
| Top third by 6-month strength | 22.9 | 1.29 | -22.7 | 3.8 | 1.02 | 52.9 |
| Top third (12m) + above 200-day | 22.2 | 1.2 | -21.4 | 3.3 | 0.74 | 51.4 |
| Top third (12m), sized by volatility | 18.2 | 1.24 | -17.4 | -0.6 | -0.22 | 50.0 |

## 1-2. Crypto: relative strength and volatility sizing (weekly)

**train**

| Strategy | Return/yr % | Sharpe | Worst drop % | vs equal weight %/yr | t | Periods ahead % |
|---|---|---|---|---|---|---|
| Equal weight, all coins | 282.8 | 1.62 | -83.5 | – | – | – |
| Top third by 4-week strength | 118.6 | 1.17 | -78.9 | 50.4 | 2.16 | 57.2 |
| App trend rule on every coin | 219.6 | 1.65 | -34.8 | -50.1 | -1.27 | 39.1 |
| App trend rule, sized by volatility | 102.1 | 1.74 | -17.1 | -118.3 | -2.46 | 42.1 |
| Top third + trend rule | 97.3 | 1.07 | -68.6 | 18.6 | 0.44 | 51.6 |
| Top third + trend rule, sized by volatility | 54.3 | 1.3 | -39.3 | -38.5 | -0.81 | 50.3 |

**test**

| Strategy | Return/yr % | Sharpe | Worst drop % | vs equal weight %/yr | t | Periods ahead % |
|---|---|---|---|---|---|---|
| Equal weight, all coins | 29.7 | 0.71 | -80.8 | – | – | – |
| Top third by 4-week strength | 48.4 | 0.87 | -80.0 | 16.1 | 1.53 | 49.3 |
| App trend rule on every coin | 68.5 | 1.4 | -44.1 | 6.5 | 0.3 | 46.0 |
| App trend rule, sized by volatility | 36.3 | 1.35 | -28.2 | -20.4 | -0.81 | 50.0 |
| Top third + trend rule | 116.6 | 1.43 | -58.3 | 44.4 | 2.12 | 52.0 |
| Top third + trend rule, sized by volatility | 56.7 | 1.35 | -44.3 | -2.3 | -0.1 | 49.3 |

## 3. Stocks: earnings drift

3750 reports, 2016-10-17 to 2026-07-16. Buy at the close after the report reaction; return vs the equal-weight universe.

**train**

| Strategy | Reports | Next 20 days % | t | Next 40 days % | t | Next 60 days % | t |
|---|---|---|---|---|---|---|---|
| All reports | 1592 | -0.26 | -1.48 | -0.36 | -1.5 | -0.5 | -1.56 |
| Beat (surprise > 0) and stock jumped > 3% | 365 | 0.16 | 0.53 | -0.11 | -0.25 | 0.15 | 0.25 |
| Biggest jumps (top 20%) | 319 | 0.33 | 1.01 | 0.26 | 0.51 | 0.69 | 1.03 |
| Biggest drops (bottom 20%) | 319 | -0.95 | -2.6 | -0.55 | -0.98 | -0.54 | -0.75 |
| Missed (surprise < 0) and stock fell > 3% | 104 | -0.97 | -1.6 | -1.23 | -1.39 | -1.86 | -1.78 |

**test**

| Strategy | Reports | Next 20 days % | t | Next 40 days % | t | Next 60 days % | t |
|---|---|---|---|---|---|---|---|
| All reports | 2158 | -0.14 | -0.82 | -0.22 | -0.9 | -0.26 | -0.67 |
| Beat (surprise > 0) and stock jumped > 3% | 576 | 0.5 | 1.57 | 0.28 | 0.65 | -0.06 | -0.1 |
| Biggest jumps (top 20%) | 432 | 0.67 | 1.62 | 0.74 | 1.3 | 0.45 | 0.56 |
| Biggest drops (bottom 20%) | 432 | -0.26 | -0.55 | -0.06 | -0.07 | 1.01 | 0.7 |
| Missed (surprise < 0) and stock fell > 3% | 133 | -1.25 | -1.57 | -1.14 | -0.88 | -0.26 | -0.15 |
