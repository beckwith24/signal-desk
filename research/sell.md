# Stock sell signals without a prior buy (2026-10-16 14:17 UTC, 98 stocks)

Alert = the day the rule turns on. Excess = return vs the stock's own average over the next 5 / 20 trading days (negative = a useful warning). Sit-out = hold, but cash while the rule is on (equal weight, costs in).

## train (2005-2020)

| Rule | Alerts | 5d excess % | t | 20d excess % | t | 20d down % | On % of days | Sit-out per yr % | Sit-out worst % | Hold per yr % | Hold worst % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RSI(2) above 95 | 14869 | -0.28 | -4.85 | -0.35 | -2.93 | 41.7 | 8.4 | 16.3 | -41.3 | 16.9 | -46.7 |
| Above upper Bollinger band and RSI(14) > 70 | 4404 | -0.37 | -4.96 | -0.62 | -4.07 | 43.4 | 2.3 | 16.8 | -46.3 | 16.9 | -46.7 |
| RSI(2) > 90 and close near the day's high | 13147 | -0.25 | -3.73 | -0.35 | -2.55 | 41.9 | 4.1 | 16.6 | -42.5 | 16.9 | -46.7 |
| Close below 200-day average | 5835 | 0.01 | 0.05 | 0.07 | 0.36 | 40.2 | 30.3 | 9.3 | -22.8 | 16.9 | -46.7 |
| 50-day average below 200-day | 1029 | 0.17 | 0.82 | 0.56 | 1.64 | 37.5 | 30.1 | 10.3 | -28.1 | 16.9 | -46.7 |
| Weekly trend down | 2271 | 0.18 | 0.5 | 0.15 | 0.28 | 39.7 | 35.7 | 8.9 | -15.3 | 16.9 | -46.7 |
| Below 50-day and 20%+ under 52-week high | 4132 | 0.14 | 0.72 | 0.62 | 1.74 | 40.1 | 11.9 | 12.0 | -33.6 | 16.9 | -46.7 |

## test (2021 on)

| Rule | Alerts | 5d excess % | t | 20d excess % | t | 20d down % | On % of days | Sit-out per yr % | Sit-out worst % | Hold per yr % | Hold worst % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RSI(2) above 95 | 5909 | -0.07 | -0.84 | -0.08 | -0.38 | 44.0 | 8.9 | 17.2 | -20.9 | 19.4 | -23.0 |
| Above upper Bollinger band and RSI(14) > 70 | 1793 | -0.1 | -0.77 | -0.14 | -0.46 | 44.6 | 2.5 | 18.7 | -23.3 | 19.4 | -23.0 |
| RSI(2) > 90 and close near the day's high | 5057 | -0.23 | -2.2 | -0.16 | -0.64 | 43.8 | 4.1 | 17.7 | -22.5 | 19.4 | -23.0 |
| Close below 200-day average | 2324 | -0.09 | -0.67 | -0.01 | -0.02 | 46.1 | 33.7 | 11.8 | -11.7 | 19.4 | -23.0 |
| 50-day average below 200-day | 409 | 0.31 | 1.39 | 0.73 | 1.43 | 41.8 | 33.1 | 13.0 | -11.5 | 19.4 | -23.0 |
| Weekly trend down | 897 | 0.18 | 0.67 | 0.11 | 0.23 | 45.3 | 39.5 | 10.9 | -11.1 | 19.4 | -23.0 |
| Below 50-day and 20%+ under 52-week high | 2084 | -0.07 | -0.37 | -0.12 | -0.29 | 46.7 | 16.1 | 12.9 | -19.1 | 19.4 | -23.0 |

