# Multi-timeframe confirmation test (2026-10-13 15:11 UTC)

Same daily-signal trades, same exits; only the entry differs. Returns are per trade after costs.

## stock

1820 daily-signal trades. Buy at the next open: average 0.82% per trade (median 0.59%), 60.8% winners, total 1488.5%.

| Timing check | Trades taken | Avg per trade taken | Winners | Total | Total vs buying every signal (t) | Entry vs next open (median) | Median wait (h) | Skipped trades would have made (avg) |
|---|---|---|---|---|---|---|---|---|
| 4H + 1H ATR stop on buy side | 62.8% | 0.79% | 56.3% | 906.0% | -582.6% (-2.18) | 0.72% | 3.0 | -0.39% |
| 4H + 1H ribbon blue | 53.8% | 0.69% | 56.8% | 673.6% | -814.9% (-3.11) | 0.1% | 0.0 | 0.31% |
| ATR and ribbon | 34.8% | 0.59% | 55.0% | 371.2% | -1117.3% (-4.01) | 0.91% | 1.0 | 0.06% |
| 1H RSI(2) below 10 (intraday dip) | 56.5% | 1.28% | 62.0% | 1319.1% | -169.5% (-0.78) | -1.02% | 0.0 | 2.03% |

## crypto

129 daily-signal trades. Buy at the next open: average 0.04% per trade (median -1.73%), 27.9% winners, total 4.8%.

| Timing check | Trades taken | Avg per trade taken | Winners | Total | Total vs buying every signal (t) | Entry vs next open (median) | Median wait (h) | Skipped trades would have made (avg) |
|---|---|---|---|---|---|---|---|---|
| 4H + 1H ATR stop on buy side | 93.8% | 0.04% | 28.9% | 4.9% | +0.1% (0.0) | 0.3% | 1.0 | -5.06% |
| 4H + 1H ribbon blue | 88.4% | 0.05% | 28.1% | 6.0% | +1.2% (0.05) | 0.03% | 0.0 | -2.39% |
| ATR and ribbon | 80.6% | 0.04% | 28.8% | 4.3% | -0.5% (-0.02) | 0.42% | 3.0 | -2.99% |
| 1H RSI(2) below 10 (intraday dip) | 98.4% | -0.09% | 29.1% | -11.1% | -15.9% (-0.48) | -0.38% | 9.0 | -0.19% |
