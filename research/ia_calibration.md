# IA indicator calibration (2026-10-13 12:37 UTC)

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
