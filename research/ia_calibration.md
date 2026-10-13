# IA indicator calibration (2026-10-13 12:44 UTC)

Data: CBRS 208 bars from 2026-05-14, BTC-USD 4410 bars from 2014-09-17, 000660.KS 727 bars from 2023-10-13, 005930.KS 727 bars from 2023-10-13

## Alignment
- CBRS 4h: screenshot line vs real closes corr **0.915**, median error 1.3% (bar step 9.100px, shift 0)
- 000660.KS: line vs closes corr **0.999** (shift 0, month-label residuals [1.0, 0.6, 0.3, -0.3, -0.7, -1.1, -1.1, -0.9, -1.1, 3.3] px)
- 005930.KS: line vs closes corr **0.996** (shift 0, month-label residuals [8.0, -3.3, -2.9, -2.1, -1.4, -1.1, -0.8, -0.1, 1.7, 2.0] px)

## 1. Levels (IA-ATR-Model)
- CBRS: running ATH 385.0; screenshot levels [256.38, 210.02, 172.42] = [0.6659, 0.5455, 0.4478] of ATH. Error vs Fibonacci fractions [7.2, 8.34, 11.65]%, vs ATH/1.236^k [1.7, 2.92, 4.32]%
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

Pairing the screenshot's own triangles at closing prices: CBRS {'trades': 16, 'win_pct': 62.5, 'roi_pct': 31.3, 'sum_pct': 32.2, 'open': False}, BTC (visible part) {'trades': 16, 'win_pct': 37.5, 'roi_pct': 12.5, 'sum_pct': 14.2, 'open': False}

Best rule per family (F1 = timing match, 1.0 = every triangle reproduced, nothing extra):

| family | rule | mean F1 | placebo F1 | CBRS F1 (hits/targets, signals) | BTC F1 | CBRS trades | BTC full-history trades |
|---|---|---|---|---|---|---|---|
| supertrend | Supertrend 14,1 flips | 0.663 | 0.187 | 0.6 (15/32, 18) | 0.727 (24/34, 32) | {'trades': 9, 'win_pct': 33.3, 'roi_pct': -15.4, 'sum_pct': -13.4, 'open': False} | {'trades': 227, 'win_pct': 41.4, 'roi_pct': 14489.5, 'sum_pct': 756.5, 'open': False} |
| rsi | RSI4 45/55 back out | 0.495 | 0.225 | 0.533 (16/32, 28) | 0.457 (21/34, 58) | {'trades': 14, 'win_pct': 35.7, 'roi_pct': -38.2, 'sum_pct': -42.5, 'open': False} | {'trades': 327, 'win_pct': 41.6, 'roi_pct': 650.9, 'sum_pct': 426.1, 'open': True} |
| atr_band | sma8 ± 0.5×ATR14 reenter | 0.482 | 0.189 | 0.577 (15/32, 20) | 0.388 (13/34, 33) | {'trades': 10, 'win_pct': 60.0, 'roi_pct': 16.7, 'sum_pct': 19.1, 'open': False} | {'trades': 198, 'win_pct': 63.1, 'roi_pct': 2751.0, 'sum_pct': 451.7, 'open': True} |
| stoch | Stoch9,1 30/70 back out | 0.476 | 0.201 | 0.582 (16/32, 23) | 0.371 (13/34, 36) | {'trades': 11, 'win_pct': 45.5, 'roi_pct': -7.2, 'sum_pct': -1.3, 'open': True} | {'trades': 194, 'win_pct': 57.7, 'roi_pct': 4693.2, 'sum_pct': 527.6, 'open': True} |
| pivot (confirmed) | pivots L1 R4 drawn when confirmed | 0.443 | 0.217 | 0.379 (11/32, 26) | 0.506 (21/34, 49) | {'trades': 13, 'win_pct': 30.8, 'roi_pct': -27.6, 'sum_pct': -29.7, 'open': False} | {'trades': 372, 'win_pct': 45.7, 'roi_pct': 6429.4, 'sum_pct': 619.3, 'open': True} |
| bollinger | sma14 ± 1σ reenter | 0.389 | 0.177 | 0.468 (11/32, 15) | 0.31 (9/34, 24) | {'trades': 7, 'win_pct': 71.4, 'roi_pct': 15.4, 'sum_pct': 17.6, 'open': True} | {'trades': 119, 'win_pct': 63.0, 'roi_pct': 192.0, 'sum_pct': 197.4, 'open': True} |
| pivot (look-ahead) | pivots L6 R3 drawn on the pivot bar | 0.314 | 0.226 | 0.415 (11/32, 21) | 0.212 (7/34, 32) | {'trades': 10, 'win_pct': 80.0, 'roi_pct': 184.0, 'sum_pct': 116.0, 'open': True} | {'trades': 197, 'win_pct': 84.3, 'roi_pct': 102849620.3, 'sum_pct': 1574.3, 'open': True} |
| ma_cross | sma20/21 cross | 0.291 | 0.265 | 0.333 (8/32, 16) | 0.25 (10/34, 46) | {'trades': 8, 'win_pct': 50.0, 'roi_pct': -0.9, 'sum_pct': 4.7, 'open': False} | {'trades': 272, 'win_pct': 51.8, 'roi_pct': 13330.1, 'sum_pct': 789.3, 'open': False} |
| donchian | new 5-bar low / high | 0.178 | 0.263 | 0.145 (4/32, 23) | 0.212 (7/34, 32) | {'trades': 11, 'win_pct': 63.6, 'roi_pct': -24.5, 'sum_pct': -24.5, 'open': True} | {'trades': 232, 'win_pct': 65.9, 'roi_pct': -29.6, 'sum_pct': 54.8, 'open': True} |

Top 15 overall:

| family | rule | mean F1 | placebo F1 | CBRS F1 | BTC F1 | BTC trades | BTC win% |
|---|---|---|---|---|---|---|---|
| supertrend | Supertrend 14,1 flips | 0.663 | 0.187 | 0.6 | 0.727 | 227 | 41.4 |
| supertrend | Supertrend 20,1 flips | 0.64 | 0.209 | 0.48 | 0.8 | 225 | 41.8 |
| supertrend | Supertrend 7,1 flips | 0.612 | 0.194 | 0.556 | 0.667 | 231 | 42.4 |
| supertrend | Supertrend 10,1 flips | 0.606 | 0.197 | 0.556 | 0.656 | 228 | 41.7 |
| rsi | RSI4 45/55 back out | 0.495 | 0.225 | 0.533 | 0.457 | 327 | 41.6 |
| rsi | RSI5 45/55 back out | 0.486 | 0.2 | 0.473 | 0.5 | 250 | 45.6 |
| atr_band | sma8 ± 0.5×ATR14 reenter | 0.482 | 0.189 | 0.577 | 0.388 | 198 | 63.1 |
| rsi | RSI3 45/55 back out | 0.476 | 0.254 | 0.521 | 0.43 | 423 | 39.5 |
| stoch | Stoch9,1 30/70 back out | 0.476 | 0.201 | 0.582 | 0.371 | 194 | 57.7 |
| rsi | RSI2 45/55 back out | 0.475 | 0.288 | 0.565 | 0.385 | 591 | 39.4 |
| atr_band | sma8 ± 0.5×ATR10 reenter | 0.472 | 0.201 | 0.556 | 0.388 | 200 | 64.5 |
| supertrend | Supertrend 10,1.5 flips | 0.471 | 0.151 | 0.36 | 0.582 | 138 | 48.6 |
| atr_band | sma14 ± 0.75×ATR10 reenter | 0.47 | 0.172 | 0.51 | 0.429 | 109 | 62.4 |
| atr_band | sma8 ± 0.5×ATR20 reenter | 0.469 | 0.194 | 0.6 | 0.338 | 196 | 64.3 |
| supertrend | Supertrend 7,1.5 flips | 0.464 | 0.163 | 0.296 | 0.632 | 141 | 46.8 |

## 4. Fine search: ATR trailing-stop rules (Supertrend / UT Bot)

| rule | mean F1 | placebo | CBRS F1 (hits/targets, signals) | BTC F1 |
|---|---|---|---|---|
| supertrend 10, 0.8, hl2, rma | 0.712 | 0.224 | 0.655 (19/32, 26) | 0.769 (30/34, 44) |
| supertrend 17, 0.9, hl2, rma | 0.694 | 0.207 | 0.615 (16/32, 20) | 0.773 (29/34, 41) |
| supertrend 25, 1.0, hl2, sma | 0.694 | 0.216 | 0.571 (16/32, 24) | 0.817 (29/34, 37) |
| supertrend 30, 0.8, hl2, sma | 0.694 | 0.221 | 0.643 (18/32, 24) | 0.744 (29/34, 44) |
| supertrend 20, 0.8, hl2, sma | 0.689 | 0.216 | 0.633 (19/32, 28) | 0.744 (29/34, 44) |
| ut_bot 0.75, 2, ha | 0.689 | 0.227 | 0.667 (22/32, 34) | 0.711 (27/34, 42) |
| supertrend 17, 0.8, hl2, rma | 0.683 | 0.22 | 0.63 (17/32, 22) | 0.737 (28/34, 42) |
| supertrend 12, 0.8, hl2, rma | 0.682 | 0.224 | 0.621 (18/32, 26) | 0.744 (29/34, 44) |
| supertrend 14, 0.8, hl2, rma | 0.682 | 0.224 | 0.621 (18/32, 26) | 0.744 (29/34, 44) |
| supertrend 25, 0.8, hl2, sma | 0.68 | 0.212 | 0.643 (18/32, 24) | 0.718 (28/34, 44) |
| supertrend 30, 0.7, hl2, sma | 0.679 | 0.239 | 0.7 (21/32, 28) | 0.659 (29/34, 54) |
| supertrend 14, 0.9, hl2, rma | 0.677 | 0.215 | 0.571 (16/32, 24) | 0.784 (29/34, 40) |

- best_for_CBRS_4h: {'family': 'supertrend', 'params': ['20', '0.6', 'close', 'sma'], 'f1': 0.742, 'precision': 0.767, 'recall': 0.719, 'hits': 23, 'signals': 30, 'targets': 32, 'mean_lag': 0.09}
- best_for_BTC_1d: {'family': 'ut_bot', 'params': ['1.25', '30', 'close'], 'f1': 0.912, 'precision': 0.912, 'recall': 0.912, 'hits': 31, 'signals': 34, 'targets': 34, 'mean_lag': 0.1}

### How the ATR-BT table could have been computed (best rule)

- CBRS_4h close_to_close: {'trades': 13, 'win_pct': 30.8, 'sum_pct': -35.0, 'compound_pct': -33.8, 'open': False}
- CBRS_4h next_open: {'trades': 13, 'win_pct': 30.8, 'sum_pct': -42.4, 'compound_pct': -38.8, 'open': False}
- CBRS_4h hindsight_low_to_high: {'trades': 13, 'win_pct': 92.3, 'sum_pct': 177.1, 'compound_pct': 392.5, 'open': False}
- CBRS_4h sell_only_in_profit: {'trades': 0}
- BTC_1d close_to_close: {'trades': 284, 'win_pct': 44.4, 'sum_pct': 741.0, 'compound_pct': 25979.3, 'open': False}
- BTC_1d next_open: {'trades': 284, 'win_pct': 44.4, 'sum_pct': 738.6, 'compound_pct': 25611.3, 'open': False}
- BTC_1d hindsight_low_to_high: {'trades': 284, 'win_pct': 97.9, 'sum_pct': 3792.7, 'compound_pct': 2.747024712928987e+16, 'open': False}
- BTC_1d sell_only_in_profit: {'trades': 40, 'win_pct': 100.0, 'sum_pct': 646.5, 'compound_pct': 28310.5, 'open': True}

Screenshot's own CBRS triangles priced the same ways:
- close_to_close: {'trades': 16, 'win_pct': 62.5, 'sum_pct': 32.2, 'compound_pct': 31.3, 'open': False}
- next_open: {'trades': 16, 'win_pct': 43.8, 'sum_pct': 9.3, 'compound_pct': 3.8, 'open': False}
- hindsight_low_to_high: {'trades': 16, 'win_pct': 100.0, 'sum_pct': 251.9, 'compound_pct': 879.6, 'open': False}
- sell_only_in_profit: {'trades': 1, 'win_pct': 100.0, 'sum_pct': 10.1, 'compound_pct': 10.1, 'open': True}

CBRS all-time high check: {'screenshot_levels': [258.49, 209.18, 169.18], 'implied_ath_if_fib_0.764_0.618_0.5': [338.34, 338.48, 338.36], 'max_high_4h': 385.0, 'max_close_4h': 327.18, 'first_bars': [{'index': '2026-05-14 09:30:00-04:00', 'open': '185.0', 'high': '385.0', 'low': '185.0', 'close': '327.18', 'volume': '16297881.0'}, {'index': '2026-05-14 13:30:00-04:00', 'open': '326.94', 'high': '343.0', 'low': '300.0', 'close': '310.3', 'volume': '15765328.0'}, {'index': '2026-05-15 09:30:00-04:00', 'open': '297.21', 'high': '306.78', 'low': '275.0', 'close': '299.12', 'volume': '13861932.0'}, {'index': '2026-05-15 13:30:00-04:00', 'open': '299.15', 'high': '302.0', 'low': '277.0', 'close': '280.19', 'volume': '2770736.0'}], 'max_high_1d': 386.34, 'max_close_1d': 311.07, 'first_days': [{'Date': '2026-05-14 00:00:00-04:00', 'open': '350.0', 'high': '386.34', 'low': '300.0', 'close': '311.07', 'volume': '33497900.0'}, {'Date': '2026-05-15 00:00:00-04:00', 'open': '298.49', 'high': '306.78', 'low': '275.0', 'close': '279.72', 'volume': '17119200.0'}, {'Date': '2026-05-18 00:00:00-04:00', 'open': '291.55', 'high': '303.66', 'low': '272.24', 'close': '296.65', 'volume': '10158400.0'}]}

CBRS without the IPO day — best rules:

- supertrend 20, 0.6, close, sma: F1 0.742 (23/32, 30 signals)
- supertrend 25, 0.6, close, sma: F1 0.742 (23/32, 30 signals)
- supertrend 25, 0.5, close, sma: F1 0.727 (24/32, 34 signals)
- ut_bot 0.5, 20, ha: F1 0.727 (24/32, 34 signals)
- ut_bot 0.5, 30, ha: F1 0.724 (21/32, 26 signals)
- supertrend 17, 0.6, close, sma: F1 0.719 (23/32, 32 signals)
- supertrend 30, 0.5, close, rma: F1 0.719 (23/32, 32 signals)
- supertrend 30, 0.6, close, sma: F1 0.719 (23/32, 32 signals)

CBRS without the IPO day — the overall top rules:

- supertrend 10, 0.8, hl2, rma: F1 0.613 (19/32, 30 signals)
- supertrend 17, 0.9, hl2, rma: F1 0.607 (17/32, 24 signals)
- supertrend 25, 1.0, hl2, sma: F1 0.571 (16/32, 24 signals)
- supertrend 30, 0.8, hl2, sma: F1 0.643 (18/32, 24 signals)
- supertrend 20, 0.8, hl2, sma: F1 0.633 (19/32, 28 signals)
- ut_bot 0.75, 2, ha: F1 0.667 (22/32, 34 signals)
- supertrend 17, 0.8, hl2, rma: F1 0.586 (17/32, 26 signals)
- supertrend 12, 0.8, hl2, rma: F1 0.581 (18/32, 30 signals)
