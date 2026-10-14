# IA-Confluence-Model rebuild and test (2026-10-14 00:48 UTC)

UMAC hourly from Yahoo (728 days, with pre/after-market hours): 8098 bars, 17.0 a day (the screenshot's chart had 24). Screenshot line vs real prices: correlation 0.9915, median error 0.62% (time shift 1 h).

## Envelope (grey lines)

| Formula | Length (our bars) | Width | Upper err % | Lower err % |
|---|---|---|---|---|
| bb_hlc3 | 70 | 2.25 | 0.88 | 6.26 |
| bb | 70 | 2.25 | 1.01 | 6.37 |
| bb | 70 | 2.0 | 0.34 | 7.11 |
| bb_hlc3 | 70 | 2.5 | 1.76 | 5.7 |
| bb_hlc3 | 80 | 2.25 | 1.06 | 6.47 |
| bb | 80 | 2.25 | 1.22 | 6.33 |
| bb_hlc3 | 70 | 2.0 | 0.34 | 7.22 |
| bb_hlc3 | 60 | 2.25 | 1.21 | 6.38 |

## Triangles (matched within ±4 h; chance level for the best rule: 0.048 recall)

| Rule | Buys solid | Buys all | Sells solid | Sells all | Predicted | Recall | Precision | F1 |
|---|---|---|---|---|---|---|---|---|
| back inside bb(70,2.25) | 2/4 | 5/13 | 0/2 | 4/11 | 19 | 0.375 | 0.474 | 0.419 |
| back inside bb_hlc3(70,2.25) | 2/4 | 5/13 | 0/2 | 4/11 | 21 | 0.375 | 0.429 | 0.4 |
| close outside bb(70,2.25) and RSI14 30/70 | 0/4 | 2/13 | 0/2 | 6/11 | 19 | 0.333 | 0.421 | 0.372 |
| close outside bb_hlc3(70,2.25) and RSI14 30/70 | 0/4 | 2/13 | 0/2 | 6/11 | 20 | 0.333 | 0.4 | 0.364 |
| close outside bb_ema(80,2.0) and RSI14 30/70 | 0/4 | 2/13 | 0/2 | 5/11 | 18 | 0.292 | 0.389 | 0.333 |
| close outside bb(70,2.25) and Stoch14 20/80 | 0/4 | 3/13 | 0/2 | 4/11 | 19 | 0.292 | 0.368 | 0.326 |
| close outside bb_hlc3(70,2.25) and Stoch14 20/80 | 0/4 | 3/13 | 0/2 | 4/11 | 21 | 0.292 | 0.333 | 0.311 |
| close outside bb(70,2.25) and RSI2 10/90 | 0/4 | 2/13 | 0/2 | 5/11 | 21 | 0.292 | 0.333 | 0.311 |
| close outside bb(70,2.25) and CCI20 -100/100 | 0/4 | 2/13 | 0/2 | 5/11 | 21 | 0.292 | 0.333 | 0.311 |
| close outside bb_hlc3(70,2.25) and CCI20 -100/100 | 0/4 | 2/13 | 0/2 | 5/11 | 22 | 0.292 | 0.318 | 0.304 |
| close outside bb_hlc3(70,2.25) and RSI2 10/90 | 0/4 | 2/13 | 0/2 | 5/11 | 23 | 0.292 | 0.304 | 0.298 |
| close outside bb_hlc3(70,2.25) and MFI14 20/80 | 0/4 | 3/13 | 0/2 | 3/11 | 18 | 0.25 | 0.333 | 0.286 |

## Its backtest table on UMAC (best rule, ~2 years of hourly bars)

Screenshot's table: {'profit': 143847, 'roi_pct': 143.85, 'win_pct': 100.0, 'buys': 24, 'sells': 20, 'open': 241433, 'capital': 84, 'total': 241518}

| Sizing | Buys | Sells | Win % | ROI % | Worst drop % | Still held, % of equity | Held vs cost % | Hold ROI % |
|---|---|---|---|---|---|---|---|---|
| buy 25% of cash, sell 50% | 68 | 86 | 81.4 | 32.6 | -42.3 | 78.2 | -10.1 | 1139.0 |
| buy 25% of cash, sell 50%, only above cost | 68 | 51 | 100.0 | 171.4 | -56.9 | 78.3 | -10.1 | 1139.0 |
| buy 25% of cash, sell 100% | 68 | 26 | 61.5 | 2.6 | -38.8 | 74.4 | -9.8 | 1139.0 |
| buy 25% of cash, sell 100%, only above cost | 68 | 15 | 100.0 | 92.8 | -54.3 | 84.8 | -13.9 | 1139.0 |
| buy 50% of cash, sell 50% | 68 | 86 | 75.6 | 31.6 | -56.6 | 97.5 | -11.7 | 1139.0 |
| buy 50% of cash, sell 50%, only above cost | 67 | 34 | 100.0 | 162.4 | -64.5 | 97.5 | -11.8 | 1139.0 |
| buy 50% of cash, sell 100% | 68 | 26 | 57.7 | -11.7 | -54.7 | 96.5 | -11.6 | 1139.0 |
| buy 50% of cash, sell 100%, only above cost | 68 | 15 | 100.0 | 101.8 | -62.7 | 99.1 | -17.3 | 1139.0 |
| buy 100% of cash, sell 50% | 27 | 86 | 70.9 | 41.9 | -65.8 | 100.0 | -13.2 | 1139.0 |
| buy 100% of cash, sell 50%, only above cost | 14 | 28 | 100.0 | 204.1 | -67.9 | 100.0 | -13.3 | 1139.0 |
| buy 100% of cash, sell 100% | 27 | 26 | 50.0 | -16.1 | -69.8 | 100.0 | -13.6 | 1139.0 |
| buy 100% of cash, sell 100%, only above cost | 10 | 9 | 100.0 | 84.1 | -70.9 | 100.0 | -23.4 | 1139.0 |

## Best match on the watchlist stocks (34 tickers, hourly, ~2 years)

Medians across tickers. Rule: the best triangle match above, buying half the cash on each buy.

| Version | Win % | ROI % | Worst drop % | Still held vs cost % | Beat holding |
|---|---|---|---|---|---|
| Normal sells (sell all on a sell signal) | 77.9 | 44.4 | -28.4 | -1.1 | 4 of 34 |
| Sell half, only above cost | 100.0 | 72.0 | -34.5 | 0.3 | 7 of 34 |
| Just holding | – | 99.5 | -43.2 | – | – |

## Best match on the watchlist cryptos (14 tickers, hourly, ~2 years)

Medians across tickers. Rule: the best triangle match above, buying half the cash on each buy.

| Version | Win % | ROI % | Worst drop % | Still held vs cost % | Beat holding |
|---|---|---|---|---|---|
| Normal sells (sell all on a sell signal) | 64.3 | 5.2 | -46.7 | 1.0 | 11 of 14 |
| Sell half, only above cost | 100.0 | -34.9 | -75.2 | -52.0 | 5 of 14 |
| Just holding | – | -19.1 | -82.2 | – | – |
