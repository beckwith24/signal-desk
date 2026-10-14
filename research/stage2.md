# Sell-off -> base -> breakout -> pullback (Stage 2) test (2026-10-14 01:41 UTC)

Return vs SPY (stocks) / BTC (coins) after buying at the next open. t clustered by month (|t| >= 2 is reasonably convincing). Trade = stop under the base, exit on a weekly close under the 30-week average, costs in. Train = before 2015, test = 2015 on.

## Stocks (494 tickers)

**train**

| Setup | Events | 20d % | 60d % | 120d % | t | 250d % | t | Beat bench 120d % | Trade win % | Trade median % | Days held | Stopped % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base 16 weeks, buy breakout | 637 | -0.29 | -0.9 | -0.5 | -0.63 | 2.84 | 2.1 | 47.7 | 48.0 | -1.1 | 106 | 1.1 |
| base 16 weeks, buy retest | 587 | 0.03 | -0.87 | -0.5 | -0.62 | 3.23 | 2.39 | 46.5 | 45.5 | -1.9 | 99 | 0.9 |
| base 16 weeks, buy rsi_dip | 625 | 0.08 | -1.04 | 0.38 | 0.46 | 3.41 | 2.61 | 49.8 | 46.2 | -1.6 | 86 | 1.1 |
| base 16 weeks, buy ma50_dip | 525 | -0.18 | -0.55 | 0.39 | 0.32 | 4.26 | 2.94 | 48.8 | 41.7 | -2.2 | 57 | 1.0 |
| base 26 weeks, buy breakout | 338 | -0.36 | -1.24 | -0.79 | -0.81 | 3.69 | 1.7 | 47.3 | 49.4 | -0.4 | 110 | 1.2 |
| base 26 weeks, buy retest | 312 | -0.09 | -1.21 | -0.92 | -1.02 | 3.79 | 1.83 | 46.2 | 46.8 | -1.2 | 103 | 1.0 |
| base 26 weeks, buy rsi_dip | 332 | -0.24 | -1.06 | 0.25 | 0.28 | 3.7 | 2.04 | 46.4 | 46.7 | -1.3 | 87 | 1.2 |
| base 26 weeks, buy ma50_dip | 279 | 0.24 | -0.06 | 0.38 | 0.39 | 4.27 | 2.45 | 50.5 | 44.8 | -1.5 | 64 | 1.1 |
| Control: any RSI(2) dip above the 200-day | 21931 | 0.66 | 1.59 | 3.38 | 11.61 | 7.26 | 16.95 | 55.9 | – | – | – | – |
| Control: average day | 56828 | 0.63 | 1.89 | 3.79 | 12.08 | 7.86 | 15.88 | 56.1 | – | – | – | – |

**test**

| Setup | Events | 20d % | 60d % | 120d % | t | 250d % | t | Beat bench 120d % | Trade win % | Trade median % | Days held | Stopped % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base 16 weeks, buy breakout | 905 | -0.48 | -0.77 | 0.05 | 0.04 | -0.71 | -0.4 | 44.7 | 43.1 | -3.0 | 90 | 0.9 |
| base 16 weeks, buy retest | 826 | -0.34 | -0.74 | -0.37 | -0.29 | -0.56 | -0.33 | 43.4 | 41.0 | -3.0 | 81 | 1.0 |
| base 16 weeks, buy rsi_dip | 903 | -0.08 | -0.04 | 0.38 | 0.27 | -0.64 | -0.44 | 46.8 | 42.5 | -2.7 | 73 | 0.9 |
| base 16 weeks, buy ma50_dip | 768 | 0.02 | -0.94 | -0.08 | -0.06 | -0.46 | -0.25 | 47.6 | 38.3 | -3.0 | 42 | 1.3 |
| base 26 weeks, buy breakout | 526 | -0.15 | -0.34 | -0.83 | -0.75 | -3.06 | -2.07 | 45.7 | 43.9 | -2.4 | 101 | 0.2 |
| base 26 weeks, buy retest | 491 | 0.46 | -0.18 | -0.63 | -0.53 | -2.59 | -1.55 | 44.8 | 44.4 | -2.0 | 91 | 0.2 |
| base 26 weeks, buy rsi_dip | 525 | 0.31 | -0.83 | -0.25 | -0.21 | -2.46 | -1.69 | 47.6 | 42.3 | -2.4 | 78 | 0.2 |
| base 26 weeks, buy ma50_dip | 444 | 0.5 | -0.99 | -0.24 | -0.24 | -2.85 | -1.68 | 49.8 | 40.3 | -2.9 | 48 | 0.7 |
| Control: any RSI(2) dip above the 200-day | 25766 | 0.22 | 0.54 | 1.26 | 3.84 | 2.19 | 5.11 | 49.3 | – | – | – | – |
| Control: average day | 70926 | 0.19 | 0.61 | 1.17 | 4.26 | 3.3 | 7.59 | 49.1 | – | – | – | – |

Latest breakouts (26-week bases): OMC 2026-02-23, OXY 2026-02-23, SJM 2026-03-02, APD 2026-04-13, ABNB 2026-04-20, ELV 2026-05-18, CDNS 2026-05-26, MGM 2026-06-01, KDP 2026-06-15, INVH 2026-06-29, KVUE 2026-06-29, KHC 2026-07-06, DXCM 2026-08-03, A 2026-08-17, REGN 2026-08-24

## Cryptos (29 tickers)

**train**

| Setup | Events | 20d % | 60d % | 120d % | t | 250d % | t | Beat bench 120d % | Trade win % | Trade median % | Days held | Stopped % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base 16 weeks, buy breakout | 0 | – | – | – | – | – | – | – | – | – | – | – |
| base 16 weeks, buy retest | 0 | – | – | – | – | – | – | – | – | – | – | – |
| base 16 weeks, buy rsi_dip | 0 | – | – | – | – | – | – | – | – | – | – | – |
| base 16 weeks, buy ma50_dip | 0 | – | – | – | – | – | – | – | – | – | – | – |
| base 26 weeks, buy breakout | 0 | – | – | – | – | – | – | – | – | – | – | – |
| base 26 weeks, buy retest | 0 | – | – | – | – | – | – | – | – | – | – | – |
| base 26 weeks, buy rsi_dip | 0 | – | – | – | – | – | – | – | – | – | – | – |
| base 26 weeks, buy ma50_dip | 0 | – | – | – | – | – | – | – | – | – | – | – |
| Control: any RSI(2) dip above the 200-day | 0 | – | – | – | – | – | – | – | – | – | – | – |
| Control: average day | 0 | – | – | – | – | – | – | – | – | – | – | – |

**test**

| Setup | Events | 20d % | 60d % | 120d % | t | 250d % | t | Beat bench 120d % | Trade win % | Trade median % | Days held | Stopped % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base 16 weeks, buy breakout | 35 | 11.11 | 39.9 | 322.49 | 1.06 | 192.18 | 0.88 | 40.0 | 51.4 | 1.7 | 154 | 5.7 |
| base 16 weeks, buy retest | 26 | 0.9 | 48.44 | 387.96 | 1.14 | 342.91 | 0.97 | 33.3 | 50.0 | -0.2 | 54 | 7.7 |
| base 16 weeks, buy rsi_dip | 33 | 4.79 | 4.46 | 211.03 | 0.93 | 69.64 | 0.6 | 28.6 | 51.5 | 0.5 | 121 | 6.1 |
| base 16 weeks, buy ma50_dip | 27 | -6.15 | -6.46 | -14.35 | -2.5 | -25.27 | -1.6 | 28.0 | 51.9 | 0.0 | 110 | 7.4 |
| base 26 weeks, buy breakout | 16 | 12.02 | 6.63 | 64.62 | 0.86 | -3.42 | -0.08 | 53.3 | 68.8 | 26.3 | 175 | 0.0 |
| base 26 weeks, buy retest | 10 | – | – | – | – | – | – | – | – | – | – | – |
| base 26 weeks, buy rsi_dip | 15 | -2.79 | – | – | – | – | – | – | 60.0 | 10.1 | 148 | 0.0 |
| base 26 weeks, buy ma50_dip | 13 | – | – | – | – | – | – | – | – | – | – | – |
| Control: any RSI(2) dip above the 200-day | 934 | 0.31 | 2.82 | 13.44 | 0.87 | 77.8 | 2.31 | 28.8 | – | – | – | – |
| Control: average day | 4016 | 0.75 | 3.35 | 9.35 | 1.3 | 35.17 | 2.1 | 32.1 | – | – | – | – |

Latest breakouts (26-week bases): ETC-USD 2021-01-11, TRX-USD 2023-05-22, BCH-USD 2023-06-26, XLM-USD 2023-07-17, XRP-USD 2023-07-17, LINK-USD 2023-10-23, XMR-USD 2023-10-30, ETH-USD 2023-12-04, DOGE-USD 2023-12-11, ADA-USD 2023-12-11, VET-USD 2023-12-11, ETC-USD 2024-01-15, BNB-USD 2024-02-19, XRP-USD 2024-11-18, XMR-USD 2026-09-07

