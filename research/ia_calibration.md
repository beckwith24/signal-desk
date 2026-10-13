# IA indicator calibration (2026-10-13 12:41 UTC)

Data: CBRS 203 bars from 2026-05-14, BTC-USD 4410 bars from 2014-09-17, 000660.KS 727 bars from 2023-10-13, 005930.KS 727 bars from 2023-10-13

## Alignment
- CBRS 4h: screenshot line vs real closes corr **0.837**, median error 2.4% (bar step 9.040px, shift -6)
- 000660.KS: line vs closes corr **0.999** (shift 0, month-label residuals [1.0, 0.6, 0.3, -0.3, -0.7, -1.1, -1.1, -0.9, -1.1, 3.3] px)
- 005930.KS: line vs closes corr **0.996** (shift 0, month-label residuals [8.0, -3.3, -2.9, -2.1, -1.4, -1.1, -0.8, -0.1, 1.7, 2.0] px)

## 1. Levels (IA-ATR-Model)
- CBRS: running ATH 385.0; screenshot levels [259.58, 211.61, 172.69] = [0.6742, 0.5496, 0.4485] of ATH. Error vs Fibonacci fractions [8.34, 9.03, 11.47]%, vs ATH/1.236^k [2.91, 3.65, 4.47]%
- BTC: running ATH 126,198.07; screenshot levels [126406.0, 96266.0, 77815.0, 63055.0, 48295.0] = [1.0016, 0.7628, 0.6166, 0.4997, 0.3827] of ATH. Error vs Fibonacci fractions [0.16, 0.16, 0.23, 0.07, 0.18]%, vs ATH/1.236^k [0.16, 6.06, 6.16, 5.99, 9.41]%

## 2. Ribbon (IA-Optimized-Trend)
### 000660.KS (181 bars, 79% blue)

| fast | slow | err_fast_pct | err_slow_pct | colour_agree |
|---|---|---|---|---|
| ema(hlc3,16) | ema(close,34) | 0.67 | 0.3 | 0.972 |
| ema(hlc3,15) | ema(close,35) | 0.7 | 0.3 | 0.972 |
| ema(hlc3,15) | rma(close,18) | 0.7 | 0.3 | 0.972 |
| rma(hlc3,8) | ema(close,35) | 0.7 | 0.3 | 0.972 |
| rma(hlc3,8) | rma(close,18) | 0.7 | 0.3 | 0.972 |
| ema(ohlc4,15) | ema(close,34) | 0.72 | 0.3 | 0.972 |

### 005930.KS (185 bars, 77% blue)

| fast | slow | err_fast_pct | err_slow_pct | colour_agree |
|---|---|---|---|---|
| ema(hlc3,15) | ema(close,34) | 0.33 | 0.16 | 0.978 |
| rma(hlc3,8) | ema(close,34) | 0.33 | 0.16 | 0.978 |
| ema(ohlc4,14) | ema(close,34) | 0.37 | 0.16 | 0.978 |
| ema(hlc3,15) | ema(close,33) | 0.33 | 0.24 | 0.978 |
| ema(hlc3,15) | rma(close,17) | 0.33 | 0.24 | 0.978 |
| rma(hlc3,8) | ema(close,33) | 0.33 | 0.24 | 0.978 |

## 3. Buy/sell triangles (IA-ATR-Model)

Pairing the screenshot's own triangles at closing prices: CBRS {'trades': 16, 'win_pct': 56.2, 'roi_pct': 60.3, 'sum_pct': 56.0, 'open': False}, BTC (visible part) {'trades': 16, 'win_pct': 37.5, 'roi_pct': 12.5, 'sum_pct': 14.2, 'open': False}

Best rule per family (F1 = timing match, 1.0 = every triangle reproduced, nothing extra):

| family | rule | mean F1 | placebo F1 | CBRS F1 (hits/targets, signals) | BTC F1 | CBRS trades | BTC full-history trades |
|---|---|---|---|---|---|---|---|
| supertrend | Supertrend 20,1 flips | 0.62 | 0.206 | 0.44 (11/32, 18) | 0.8 (28/34, 36) | {'trades': 9, 'win_pct': 33.3, 'roi_pct': -28.0, 'sum_pct': -28.9, 'open': False} | {'trades': 225, 'win_pct': 41.8, 'roi_pct': 16411.8, 'sum_pct': 736.4, 'open': False} |
| rsi | RSI5 45/55 back out | 0.45 | 0.207 | 0.4 (11/32, 23) | 0.5 (20/34, 46) | {'trades': 11, 'win_pct': 27.3, 'roi_pct': -45.2, 'sum_pct': -52.0, 'open': True} | {'trades': 250, 'win_pct': 45.6, 'roi_pct': 1519.8, 'sum_pct': 500.6, 'open': True} |
| pivot (look-ahead) | pivots L5 R1 drawn on the pivot bar | 0.394 | 0.252 | 0.545 (15/32, 23) | 0.242 (8/34, 32) | {'trades': 11, 'win_pct': 72.7, 'roi_pct': -6.6, 'sum_pct': -1.4, 'open': True} | {'trades': 231, 'win_pct': 74.5, 'roi_pct': 34552.6, 'sum_pct': 699.2, 'open': True} |
| atr_band | sma8 ± 0.5×ATR14 reenter | 0.387 | 0.201 | 0.385 (10/32, 20) | 0.388 (13/34, 33) | {'trades': 10, 'win_pct': 50.0, 'roi_pct': 7.4, 'sum_pct': 11.0, 'open': False} | {'trades': 198, 'win_pct': 63.1, 'roi_pct': 2751.0, 'sum_pct': 451.7, 'open': True} |
| stoch | Stoch9,1 30/70 back out | 0.386 | 0.207 | 0.4 (11/32, 23) | 0.371 (13/34, 36) | {'trades': 11, 'win_pct': 45.5, 'roi_pct': -11.3, 'sum_pct': -5.7, 'open': True} | {'trades': 194, 'win_pct': 57.7, 'roi_pct': 4693.2, 'sum_pct': 527.6, 'open': True} |
| pivot (confirmed) | pivots L4 R1 drawn when confirmed | 0.366 | 0.253 | 0.476 (15/32, 31) | 0.256 (10/34, 44) | {'trades': 15, 'win_pct': 53.3, 'roi_pct': -5.7, 'sum_pct': -1.0, 'open': True} | {'trades': 284, 'win_pct': 60.2, 'roi_pct': 557.5, 'sum_pct': 282.8, 'open': False} |
| donchian | new 5-bar low / high | 0.324 | 0.248 | 0.436 (12/32, 23) | 0.212 (7/34, 32) | {'trades': 11, 'win_pct': 63.6, 'roi_pct': -18.5, 'sum_pct': -16.2, 'open': True} | {'trades': 232, 'win_pct': 65.9, 'roi_pct': -29.6, 'sum_pct': 54.8, 'open': True} |
| bollinger | sma10 ± 1σ touch | 0.289 | 0.242 | 0.393 (12/32, 29) | 0.186 (8/34, 52) | {'trades': 14, 'win_pct': 78.6, 'roi_pct': 36.1, 'sum_pct': 37.3, 'open': True} | {'trades': 264, 'win_pct': 63.6, 'roi_pct': -61.6, 'sum_pct': -3.1, 'open': True} |
| ma_cross | ema5/20 cross | 0.262 | 0.139 | 0.091 (2/32, 12) | 0.433 (13/34, 26) | {'trades': 6, 'win_pct': 33.3, 'roi_pct': -39.1, 'sum_pct': -45.5, 'open': False} | {'trades': 119, 'win_pct': 31.9, 'roi_pct': 27291.2, 'sum_pct': 870.4, 'open': False} |

Top 15 overall:

| family | rule | mean F1 | placebo F1 | CBRS F1 | BTC F1 | BTC trades | BTC win% |
|---|---|---|---|---|---|---|---|
| supertrend | Supertrend 20,1 flips | 0.62 | 0.206 | 0.44 | 0.8 | 225 | 41.8 |
| supertrend | Supertrend 14,1 flips | 0.603 | 0.18 | 0.48 | 0.727 | 227 | 41.4 |
| supertrend | Supertrend 7,1 flips | 0.555 | 0.182 | 0.444 | 0.667 | 231 | 42.4 |
| supertrend | Supertrend 10,1 flips | 0.55 | 0.185 | 0.444 | 0.656 | 228 | 41.7 |
| supertrend | Supertrend 14,1.5 flips | 0.458 | 0.133 | 0.333 | 0.582 | 138 | 48.6 |
| supertrend | Supertrend 10,1.5 flips | 0.451 | 0.151 | 0.32 | 0.582 | 138 | 48.6 |
| rsi | RSI5 45/55 back out | 0.45 | 0.207 | 0.4 | 0.5 | 250 | 45.6 |
| supertrend | Supertrend 7,1.5 flips | 0.446 | 0.154 | 0.259 | 0.632 | 141 | 46.8 |
| rsi | RSI4 45/55 back out | 0.445 | 0.236 | 0.433 | 0.457 | 327 | 41.6 |
| rsi | RSI2 45/55 back out | 0.421 | 0.29 | 0.458 | 0.385 | 591 | 39.4 |
| rsi | RSI3 45/55 back out | 0.42 | 0.267 | 0.411 | 0.43 | 423 | 39.5 |
| supertrend | Supertrend 20,1.5 flips | 0.414 | 0.112 | 0.174 | 0.655 | 140 | 46.4 |
| pivot (look-ahead) | pivots L5 R1 drawn on the pivot bar | 0.394 | 0.252 | 0.545 | 0.242 | 231 | 74.5 |
| atr_band | sma8 ± 0.5×ATR14 reenter | 0.387 | 0.201 | 0.385 | 0.388 | 198 | 63.1 |
| stoch | Stoch9,1 30/70 back out | 0.386 | 0.207 | 0.4 | 0.371 | 194 | 57.7 |

## 4. Fine search: ATR trailing-stop rules (Supertrend / UT Bot)

| rule | mean F1 | placebo | CBRS F1 (hits/targets, signals) | BTC F1 |
|---|---|---|---|---|
| supertrend 10, 0.8, hl2, rma | 0.661 | 0.218 | 0.552 (16/32, 26) | 0.769 (30/34, 44) |
| supertrend 14, 0.9, hl2, rma | 0.66 | 0.2 | 0.536 (15/32, 24) | 0.784 (29/34, 40) |
| supertrend 25, 1.0, hl2, sma | 0.658 | 0.204 | 0.5 (14/32, 24) | 0.817 (29/34, 37) |
| supertrend 17, 1.2, close, rma | 0.65 | 0.198 | 0.44 (11/32, 18) | 0.861 (31/34, 38) |
| supertrend 12, 0.8, hl2, rma | 0.648 | 0.213 | 0.552 (16/32, 26) | 0.744 (29/34, 44) |
| supertrend 14, 0.8, hl2, rma | 0.648 | 0.207 | 0.552 (16/32, 26) | 0.744 (29/34, 44) |
| supertrend 17, 0.8, hl2, rma | 0.647 | 0.208 | 0.556 (15/32, 22) | 0.737 (28/34, 42) |
| ut_bot 1.25, 30, close | 0.643 | 0.178 | 0.375 (9/32, 16) | 0.912 (31/34, 34) |
| supertrend 20, 0.9, hl2, sma | 0.641 | 0.204 | 0.483 (14/32, 26) | 0.8 (30/34, 41) |
| supertrend 30, 0.8, hl2, sma | 0.64 | 0.209 | 0.536 (15/32, 24) | 0.744 (29/34, 44) |
| supertrend 20, 0.8, hl2, sma | 0.639 | 0.211 | 0.533 (16/32, 28) | 0.744 (29/34, 44) |
| supertrend 20, 0.8, hl2, rma | 0.634 | 0.216 | 0.577 (15/32, 20) | 0.692 (27/34, 44) |

- best_for_CBRS_4h: {'family': 'supertrend', 'params': ['25', '0.6', 'hl2', 'rma'], 'f1': 0.607, 'precision': 0.708, 'recall': 0.531, 'hits': 17, 'signals': 24, 'targets': 32, 'mean_lag': 0.24}
- best_for_BTC_1d: {'family': 'ut_bot', 'params': ['1.25', '30', 'close'], 'f1': 0.912, 'precision': 0.912, 'recall': 0.912, 'hits': 31, 'signals': 34, 'targets': 34, 'mean_lag': 0.1}

### How the ATR-BT table could have been computed (best rule)

- CBRS_4h close_to_close: {'trades': 13, 'win_pct': 30.8, 'sum_pct': -39.4, 'compound_pct': -36.7, 'open': False}
- CBRS_4h next_open: {'trades': 13, 'win_pct': 30.8, 'sum_pct': -46.9, 'compound_pct': -41.6, 'open': False}
- CBRS_4h hindsight_low_to_high: {'trades': 13, 'win_pct': 92.3, 'sum_pct': 175.1, 'compound_pct': 383.6, 'open': False}
- CBRS_4h sell_only_in_profit: {'trades': 0}
- BTC_1d close_to_close: {'trades': 284, 'win_pct': 44.4, 'sum_pct': 741.0, 'compound_pct': 25979.3, 'open': False}
- BTC_1d next_open: {'trades': 284, 'win_pct': 44.4, 'sum_pct': 738.6, 'compound_pct': 25611.3, 'open': False}
- BTC_1d hindsight_low_to_high: {'trades': 284, 'win_pct': 97.9, 'sum_pct': 3792.7, 'compound_pct': 2.747024712928987e+16, 'open': False}
- BTC_1d sell_only_in_profit: {'trades': 40, 'win_pct': 100.0, 'sum_pct': 646.5, 'compound_pct': 28310.5, 'open': True}

Screenshot's own CBRS triangles priced the same ways:
- close_to_close: {'trades': 16, 'win_pct': 56.2, 'sum_pct': 56.0, 'compound_pct': 60.3, 'open': False}
- next_open: {'trades': 16, 'win_pct': 43.8, 'sum_pct': 48.8, 'compound_pct': 49.8, 'open': False}
- hindsight_low_to_high: {'trades': 16, 'win_pct': 87.5, 'sum_pct': 194.9, 'compound_pct': 490.1, 'open': False}
- sell_only_in_profit: {'trades': 5, 'win_pct': 100.0, 'sum_pct': 53.1, 'compound_pct': 63.0, 'open': True}

CBRS all-time high check: {'screenshot_levels': [258.49, 209.18, 169.18], 'implied_ath_if_fib_0.764_0.618_0.5': [338.34, 338.48, 338.36], 'max_high_4h': 385.0, 'max_close_4h': 327.18, 'first_bars': [{'index': '2026-05-14 09:30:00-04:00', 'open': '185.0', 'high': '385.0', 'low': '185.0', 'close': '327.18', 'volume': '16297881.0'}, {'index': '2026-05-14 13:30:00-04:00', 'open': '326.94', 'high': '343.0', 'low': '300.0', 'close': '310.3', 'volume': '15765328.0'}, {'index': '2026-05-15 09:30:00-04:00', 'open': '297.21', 'high': '306.78', 'low': '275.0', 'close': '299.12', 'volume': '13861932.0'}, {'index': '2026-05-15 13:30:00-04:00', 'open': '299.15', 'high': '302.0', 'low': '277.0', 'close': '280.19', 'volume': '2770736.0'}], 'max_high_1d': 386.34, 'max_close_1d': 311.07, 'first_days': [{'Date': '2026-05-14 00:00:00-04:00', 'open': '350.0', 'high': '386.34', 'low': '300.0', 'close': '311.07', 'volume': '33497900.0'}, {'Date': '2026-05-15 00:00:00-04:00', 'open': '298.49', 'high': '306.78', 'low': '275.0', 'close': '279.72', 'volume': '17119200.0'}, {'Date': '2026-05-18 00:00:00-04:00', 'open': '291.55', 'high': '303.66', 'low': '272.24', 'close': '296.65', 'volume': '10158400.0'}]}
