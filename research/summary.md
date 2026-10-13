# Model research — 2026-10-13 03:29 UTC

Bullish/bearish = next-bar return vs the ticker's own average, in basis points (1 bp = 0.01%), with a t-stat clustered by day (|t| ≥ 2 is reasonably convincing). Long-only = hold only while bullish, after costs; Sharpe compared with simply holding.

Models are **selected on TRAIN only**; the ensemble's TEST row is the honest out-of-sample result.

## stock-1d

Train 2017-10-11 → 2020-12-31 · Test 2021-01-04 → 2026-10-09 · 13 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** rsi2_pullback, ibs_reversal, vix_backwardation

- Preset **pullback_any** (rsi2_pullback, ibs_reversal, vix_backwardation; bullish when average vote > 0.0):
  - train: bullish 4.22 bp (t 0.26), bearish None bp (t None); long-only Sharpe 0.46 vs hold 0.91, return 9.4%/yr vs 30.5%, worst dip -31.4% vs -41.5%, invested 34%
  - test: bullish 12.78 bp (t 1.23), bearish None bp (t None); long-only Sharpe 0.71 vs hold 0.86, return 10.2%/yr vs 28.0%, worst dip -32.5% vs -57.6%, invested 25%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| rsi2_pullback | 6.42 (0.37) | – | -0.62 | 21.8 (1.98) | – | -0.23 | 11% |
| ibs_reversal | 11.54 (1.01) | – | -0.55 | 12.82 (1.34) | – | -0.36 | 14% |
| turn_of_month | 23.24 (1.36) | – | -0.06 | -0.83 (-0.07) | – | -0.76 | 19% |
| market_regime | -3.29 (-0.56) | 17.74 (0.57) | -0.1 | 1.21 (0.25) | -5.14 (-0.3) | 0.07 | 81% |
| vix_backwardation | 13.24 (0.39) | – | -0.55 | 35.24 (0.79) | – | -0.48 | 4% |
| tsmom28 | -2.24 (-0.38) | 4.29 (0.31) | -0.16 | -0.28 (-0.06) | 0.41 (0.05) | -0.23 | 60% |
| sma_ensemble | -2.5 (-0.46) | 18.72 (0.88) | -0.07 | -0.04 (-0.01) | 1.5 (0.13) | -0.15 | 61% |
| donchian_ensemble | -3.33 (-0.55) | 5.92 (0.22) | -0.41 | 0.96 (0.18) | 2.55 (0.15) | -0.2 | 49% |
| high_breakout_trail | 0.8 (0.12) | -37.4 (-0.78) | -0.29 | 3.38 (0.59) | 20.7 (0.71) | -0.25 | 29% |
| trend_classic | -3.23 (-0.54) | 9.23 (0.58) | -0.18 | -0.72 (-0.15) | 1.45 (0.14) | -0.15 | 63% |
| meanrev_z | 76.42 (1.96) | -1.94 (-0.15) | -0.02 | 21.71 (1.12) | 4.64 (0.4) | -0.55 | 4% |
| confluence | -41.49 (-0.95) | -3.07 (-0.35) | -1.07 | 27.66 (1.21) | 3.87 (0.49) | -0.57 | 3% |
| atr_layers | 17.97 (0.68) | -0.98 (-0.16) | -0.5 | 15.38 (1.02) | 4.27 (0.75) | -0.29 | 15% |
| momentum_classic | -1.16 (-0.19) | 4.56 (0.24) | -0.28 | 1.63 (0.29) | 1.75 (0.18) | -0.16 | 44% |
| old_ensemble | 45.95 (0.89) | -1.38 (-0.04) | -0.43 | 49.1 (1.68) | -20.73 (-0.75) | -0.58 | 1% |

## crypto-1d

Train 2017-06-20 → 2020-12-31 · Test 2021-01-01 → 2026-10-11 · 5 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate, ibs_reversal, trend_classic, momentum_classic

- Preset **trend4_majority** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.0):
  - train: bullish 15.12 bp (t 0.96), bearish -20.04 bp (t -0.95); long-only Sharpe 1.36 vs hold 1.27, return 90.4%/yr vs 102.3%, worst dip -54.5% vs -73.8%, invested 53%
  - test: bullish 20.11 bp (t 1.89), bearish -19.3 bp (t -1.46); long-only Sharpe 0.88 vs hold 0.6, return 40.9%/yr vs 19.6%, worst dip -70.0% vs -90.2%, invested 52%
- Preset **trend4_3of4** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.5):
  - train: bullish 28.07 bp (t 1.55), bearish -28.28 bp (t -0.97); long-only Sharpe 1.41 vs hold 1.27, return 101.5%/yr vs 102.3%, worst dip -39.3% vs -73.8%, invested 41%
  - test: bullish 30.57 bp (t 2.63), bearish -16.74 bp (t -1.04); long-only Sharpe 0.92 vs hold 0.6, return 36.0%/yr vs 19.6%, worst dip -52.7% vs -90.2%, invested 38%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| tsmom28 | 14.11 (0.92) | -20.55 (-0.97) | 0.03 | 17.66 (1.7) | -17.96 (-1.51) | 0.23 | 51% |
| sma_ensemble | 16.06 (1.03) | -25.88 (-1.01) | 0.01 | 16.04 (1.52) | -16.26 (-1.11) | 0.16 | 52% |
| donchian_ensemble | 39.2 (1.7) | -24.18 (-0.86) | -0.2 | 31.95 (2.38) | -9.57 (-0.6) | 0.06 | 31% |
| btc_trend_gate | 17.32 (1.03) | -20.13 (-0.97) | 0.17 | 22.17 (2.08) | -24.87 (-1.83) | 0.39 | 53% |
| high_breakout_trail | 52.98 (1.77) | -89.18 (-0.34) | -0.35 | 36.34 (1.98) | 313.64 (3.21) | -0.19 | 12% |
| rsi2_pullback | -7.05 (-0.15) | – | -1.16 | 4.07 (0.16) | – | -0.51 | 8% |
| ibs_reversal | 20.35 (0.52) | – | -1.34 | 0.87 (0.04) | – | -1.14 | 8% |
| turn_of_month | -15.31 (-0.5) | – | -1.14 | -9.02 (-0.41) | – | -0.84 | 15% |
| trend_classic | 7.57 (0.46) | -10.54 (-0.58) | -0.17 | 15.48 (1.39) | -13.54 (-1.21) | 0.16 | 48% |
| meanrev_z | 1.04 (0.01) | 18.76 (0.52) | -1.27 | 34.77 (0.67) | 30.26 (1.29) | -0.45 | 4% |
| confluence | 12.71 (0.19) | 71.89 (1.99) | -1.29 | 25.17 (0.66) | 35.74 (1.47) | -0.66 | 4% |
| atr_layers | -10.71 (-0.37) | 31.45 (1.61) | -0.98 | -17.11 (-0.97) | 33.42 (2.39) | -0.83 | 23% |
| momentum_classic | 31.2 (1.72) | -26.78 (-0.95) | -0.04 | 15.17 (1.25) | -12.3 (-0.82) | -0.04 | 37% |
| old_ensemble | 99.04 (0.65) | -28.75 (-0.38) | -1.07 | 153.02 (1.44) | 4.87 (0.11) | -0.41 | 1% |

## stock-4h

Train 2024-03-20 → 2025-06-30 · Test 2025-07-01 → 2026-10-12 · 13 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** turn_of_month, vix_backwardation, atr_layers

- Preset **pullback_any** (rsi2_pullback, ibs_reversal, vix_backwardation; bullish when average vote > 0.0):
  - train: bullish -0.53 bp (t -0.06), bearish None bp (t None); long-only Sharpe 0.21 vs hold 0.8, return 0.6%/yr vs 16.6%, worst dip -29.7% vs -38.2%, invested 31%
  - test: bullish 8.83 bp (t 1.13), bearish None bp (t None); long-only Sharpe 0.53 vs hold 1.4, return 8.6%/yr vs 31.4%, worst dip -17.4% vs -30.0%, invested 28%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| rsi2_pullback | -8.41 (-0.94) | – | -1.06 | 4.66 (0.55) | – | -0.7 | 13% |
| ibs_reversal | -2.18 (-0.28) | – | -0.9 | 7.25 (0.71) | – | -1.17 | 14% |
| turn_of_month | 0.31 (0.02) | – | -0.72 | 6.14 (0.62) | – | -0.57 | 19% |
| market_regime | -2.46 (-0.56) | 18.69 (0.76) | -0.26 | -0.33 (-0.09) | 9.63 (0.26) | -0.1 | 97% |
| vix_backwardation | 15.57 (0.68) | – | -0.43 | 39.3 (1.36) | – | -0.3 | 4% |
| tsmom28 | -0.78 (-0.16) | 1.07 (0.14) | -0.22 | -2.39 (-0.54) | 3.29 (0.61) | -0.81 | 59% |
| sma_ensemble | -0.53 (-0.11) | 2.59 (0.23) | -0.27 | -3.22 (-0.75) | 5.26 (0.77) | -0.67 | 62% |
| donchian_ensemble | 1.19 (0.24) | 10.32 (0.68) | -0.2 | -0.18 (-0.04) | 1.32 (0.17) | -0.46 | 41% |
| high_breakout_trail | -2.15 (-0.37) | 7.28 (0.28) | -0.72 | -0.99 (-0.17) | -2.02 (-0.09) | -0.66 | 25% |
| trend_classic | -2.22 (-0.49) | 3.56 (0.42) | -0.24 | -1.49 (-0.33) | 2.64 (0.47) | -0.36 | 67% |
| meanrev_z | -9.76 (-0.62) | 5.35 (0.62) | -1.12 | -4.68 (-0.41) | -3.76 (-0.44) | -0.78 | 5% |
| confluence | 7.86 (0.54) | -6.91 (-1.04) | -0.33 | 24.12 (1.51) | 7.6 (0.95) | -0.5 | 3% |
| atr_layers | 5.41 (0.45) | -2.94 (-0.54) | -0.32 | 15.71 (1.75) | -1.09 (-0.2) | -0.2 | 15% |
| momentum_classic | -3.52 (-0.66) | 0.28 (0.03) | -0.5 | -1.44 (-0.3) | 11.17 (1.66) | -0.56 | 43% |
| old_ensemble | 6.44 (0.34) | -38.19 (-1.26) | -0.52 | 42.99 (1.7) | 7.4 (0.23) | -0.44 | 1% |

## crypto-4h

Train 2024-11-25 → 2025-11-03 · Test 2025-11-03 → 2026-10-12 · 5 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** btc_trend_gate, ibs_reversal

- Preset **trend4_majority** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.0):
  - train: bullish -0.81 bp (t -0.19), bearish -0.32 bp (t -0.06); long-only Sharpe -0.86 vs hold 0.33, return -44.1%/yr vs -15.8%, worst dip -61.3% vs -65.9%, invested 49%
  - test: bullish -1.93 bp (t -0.55), bearish 1.09 bp (t 0.27); long-only Sharpe -1.63 vs hold -0.37, return -45.9%/yr vs -32.5%, worst dip -60.2% vs -57.7%, invested 45%
- Preset **trend4_3of4** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.5):
  - train: bullish 5.68 bp (t 1.1), bearish 4.54 bp (t 0.52); long-only Sharpe 0.49 vs hold 0.33, return 12.4%/yr vs -15.8%, worst dip -28.8% vs -65.9%, invested 31%
  - test: bullish 2.7 bp (t 0.53), bearish -1.56 bp (t -0.23); long-only Sharpe -0.6 vs hold -0.37, return -21.6%/yr vs -32.5%, worst dip -30.7% vs -57.7%, invested 24%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| tsmom28 | 0.08 (0.02) | -0.08 (-0.02) | -0.71 | -1.61 (-0.46) | 1.4 (0.39) | -1.51 | 47% |
| sma_ensemble | 1.02 (0.24) | -0.38 (-0.06) | -0.65 | -1.08 (-0.3) | -0.07 (-0.02) | -1.1 | 46% |
| donchian_ensemble | 2.12 (0.42) | 2.7 (0.34) | -0.38 | 0.92 (0.19) | -0.08 (-0.01) | -0.45 | 25% |
| btc_trend_gate | 0.15 (0.04) | -0.23 (-0.04) | -0.27 | 3.36 (1.02) | -2.94 (-0.72) | 0.81 | 47% |
| high_breakout_trail | 4.92 (0.63) | -4.77 (-0.17) | 0.26 | 5.7 (0.71) | 5.4 (0.32) | 0.7 | 10% |
| rsi2_pullback | -2.77 (-0.34) | – | -1.11 | -1.02 (-0.21) | – | -1.27 | 8% |
| ibs_reversal | 0.66 (0.08) | – | -3.23 | 5.67 (0.88) | – | -4.06 | 8% |
| turn_of_month | -1.65 (-0.14) | – | -0.33 | 1.41 (0.18) | – | 0.11 | 15% |
| trend_classic | 1.74 (0.43) | -1.51 (-0.3) | 0.03 | -0.42 (-0.13) | 0.34 (0.09) | 0.03 | 46% |
| meanrev_z | -19.71 (-1.04) | 4.94 (0.54) | -2.09 | 3.97 (0.31) | -4.12 (-0.49) | -0.91 | 6% |
| confluence | -0.47 (-0.04) | 5.92 (0.7) | -2.48 | -3.33 (-0.41) | 7.57 (1.1) | -3.34 | 9% |
| atr_layers | 3.69 (0.45) | 5.98 (1.11) | -0.62 | 0.12 (0.02) | 0.71 (0.12) | -0.73 | 23% |
| momentum_classic | -1.77 (-0.35) | -1.96 (-0.31) | -1.31 | -3.97 (-0.88) | 0.99 (0.2) | -2.07 | 33% |
| old_ensemble | -1.23 (-0.06) | -37.36 (-1.67) | -1.2 | 18.07 (1.0) | -1.02 (-0.07) | -0.78 | 1% |

## stock-1h

Train 2024-01-08 → 2025-05-23 · Test 2025-05-27 → 2026-10-12 · 13 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** turn_of_month, vix_backwardation

- Preset **pullback_any** (rsi2_pullback, ibs_reversal, vix_backwardation; bullish when average vote > 0.0):
  - train: bullish 1.74 bp (t 0.51), bearish None bp (t None); long-only Sharpe 0.06 vs hold 0.77, return -0.5%/yr vs 17.8%, worst dip -28.2% vs -38.5%, invested 29%
  - test: bullish 1.87 bp (t 0.87), bearish None bp (t None); long-only Sharpe -0.34 vs hold 1.59, return -6.4%/yr vs 44.9%, worst dip -18.8% vs -31.1%, invested 25%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| rsi2_pullback | -0.59 (-0.2) | – | -1.02 | 0.87 (0.41) | – | -1.32 | 13% |
| ibs_reversal | -0.02 (-0.01) | – | -2.3 | -0.37 (-0.13) | – | -1.97 | 12% |
| turn_of_month | 0.23 (0.05) | – | -0.95 | 1.08 (0.34) | – | -0.67 | 19% |
| market_regime | -0.66 (-0.46) | 4.75 (0.6) | -0.25 | 0.05 (0.04) | -1.34 (-0.12) | -0.03 | 96% |
| vix_backwardation | 6.44 (0.75) | – | -0.34 | 14.16 (1.62) | – | -0.33 | 4% |
| tsmom28 | -0.43 (-0.28) | 0.54 (0.21) | -0.49 | -0.53 (-0.4) | 0.72 (0.38) | -0.67 | 58% |
| sma_ensemble | 0.01 (0.01) | 0.36 (0.12) | -0.53 | -0.76 (-0.59) | 2.16 (0.9) | -0.77 | 60% |
| donchian_ensemble | 0.1 (0.06) | -0.01 (-0.0) | -0.55 | -1.08 (-0.79) | 3.58 (1.19) | -0.96 | 43% |
| high_breakout_trail | 0.35 (0.19) | 4.91 (0.65) | -0.5 | -0.75 (-0.44) | -11.54 (-1.73) | -0.77 | 24% |
| trend_classic | 0.31 (0.21) | -0.44 (-0.16) | -0.13 | -0.37 (-0.3) | 0.6 (0.3) | -0.5 | 64% |
| meanrev_z | -2.4 (-0.56) | -3.36 (-1.14) | -1.36 | 7.28 (2.0) | -2.45 (-1.07) | -1.12 | 5% |
| confluence | -0.77 (-0.18) | -0.79 (-0.34) | -1.24 | 0.75 (0.21) | -2.3 (-0.97) | -1.25 | 7% |
| atr_layers | 2.04 (0.62) | 1.02 (0.63) | -0.26 | 3.44 (1.25) | -1.22 (-0.79) | -0.22 | 20% |
| momentum_classic | 0.18 (0.1) | -0.23 (-0.08) | -0.46 | -1.17 (-0.84) | 1.36 (0.63) | -1.09 | 42% |
| old_ensemble | 7.2 (1.39) | -6.17 (-0.48) | -0.94 | -9.96 (-2.35) | -3.97 (-0.62) | -2.39 | 1% |

## crypto-1h

Train 2024-10-25 → 2025-10-19 · Test 2025-10-19 → 2026-10-13 · 5 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** btc_trend_gate, momentum_classic

- Preset **trend4_majority** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.0):
  - train: bullish 0.18 bp (t 0.18), bearish -0.13 bp (t -0.09); long-only Sharpe -2.51 vs hold 0.86, return -75.6%/yr vs 42.6%, worst dip -82.2% vs -66.3%, invested 51%
  - test: bullish -0.07 bp (t -0.09), bearish 0.02 bp (t 0.02); long-only Sharpe -4.81 vs hold -0.46, return -85.0%/yr vs -36.4%, worst dip -84.9% vs -64.1%, invested 48%
- Preset **trend4_3of4** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.5):
  - train: bullish 1.35 bp (t 1.07), bearish 0.13 bp (t 0.05); long-only Sharpe -1.2 vs hold 0.86, return -47.7%/yr vs 42.6%, worst dip -65.8% vs -66.3%, invested 32%
  - test: bullish 0.86 bp (t 0.67), bearish -0.66 bp (t -0.39); long-only Sharpe -2.91 vs hold -0.46, return -55.1%/yr vs -36.4%, worst dip -55.7% vs -64.1%, invested 21%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| tsmom28 | 0.1 (0.1) | -0.11 (-0.09) | -2.99 | -0.05 (-0.07) | 0.05 (0.06) | -4.68 | 49% |
| sma_ensemble | 0.59 (0.58) | -0.68 (-0.45) | -2.12 | -0.19 (-0.23) | 0.23 (0.21) | -4.39 | 49% |
| donchian_ensemble | 1.32 (1.08) | -1.39 (-0.77) | -1.43 | 0.15 (0.13) | 0.33 (0.24) | -2.69 | 25% |
| btc_trend_gate | 0.25 (0.25) | -0.46 (-0.29) | -0.08 | 0.81 (0.96) | -0.67 (-0.69) | 0.89 | 45% |
| high_breakout_trail | 1.81 (1.11) | 6.39 (0.9) | -0.73 | 0.52 (0.29) | 11.01 (1.8) | -0.26 | 10% |
| rsi2_pullback | 0.35 (0.18) | – | -4.28 | -0.38 (-0.24) | – | -5.03 | 8% |
| ibs_reversal | 2.61 (1.58) | – | -13.72 | -1.72 (-1.15) | – | -17.4 | 10% |
| turn_of_month | -1.02 (-0.38) | – | -1.09 | -0.53 (-0.28) | – | -0.2 | 15% |
| trend_classic | 0.36 (0.34) | -0.36 (-0.3) | -0.91 | -0.63 (-0.72) | 0.54 (0.6) | -2.01 | 47% |
| meanrev_z | 0.48 (0.11) | 3.61 (1.24) | -5.04 | -3.55 (-1.28) | 4.28 (1.59) | -6.68 | 6% |
| confluence | -0.43 (-0.16) | -0.61 (-0.28) | -8.42 | 2.45 (1.2) | 1.87 (1.05) | -9.34 | 8% |
| atr_layers | -1.16 (-0.66) | 1.64 (1.26) | -3.59 | -0.45 (-0.32) | 0.17 (0.13) | -3.1 | 25% |
| momentum_classic | 1.19 (1.03) | -1.02 (-0.73) | -3.42 | 0.42 (0.38) | -0.45 (-0.41) | -4.67 | 33% |
| old_ensemble | 1.38 (0.31) | 3.29 (0.63) | -4.5 | -3.72 (-0.83) | 0.3 (0.06) | -5.19 | 1% |

_Personal research only. Past results don't guarantee future results._