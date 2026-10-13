# Model research — 2026-10-13 12:46 UTC

Bullish/bearish = next-bar return vs the ticker's own average, in basis points (1 bp = 0.01%), with a t-stat clustered by day (|t| ≥ 2 is reasonably convincing). Long-only = hold only while bullish, after costs; Sharpe compared with simply holding.

Models are **selected on TRAIN only**; the ensemble's TEST row is the honest out-of-sample result.

## stock-1d

Train 2017-10-11 → 2020-12-31 · Test 2021-01-04 → 2026-10-09 · 13 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** rsi2_pullback, ibs_reversal, vix_backwardation, ia_ath_discount

- Preset **pullback_any** (rsi2_pullback, ibs_reversal, vix_backwardation; bullish when average vote > 0.0):
  - train: bullish 4.22 bp (t 0.26), bearish None bp (t None); long-only Sharpe 0.46 vs hold 0.91, return 9.4%/yr vs 30.5%, worst dip -31.4% vs -41.5%, invested 34%
  - test: bullish 12.78 bp (t 1.23), bearish None bp (t None); long-only Sharpe 0.71 vs hold 0.86, return 10.2%/yr vs 28.0%, worst dip -32.5% vs -57.6%, invested 25%
- Preset **ia_ribbon_and_stop** (ia_ribbon, ia_atr_stop; bullish when average vote > 0.5):
  - train: bullish -3.28 bp (t -0.56), bearish 18.05 bp (t 0.86); long-only Sharpe 0.59 vs hold 0.91, return 9.0%/yr vs 30.5%, worst dip -25.4% vs -41.5%, invested 47%
  - test: bullish -0.72 bp (t -0.13), bearish 8.16 bp (t 0.66); long-only Sharpe 0.54 vs hold 0.86, return 8.1%/yr vs 28.0%, worst dip -30.6% vs -57.6%, invested 39%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| rsi2_pullback | 6.42 (0.37) | – | -0.62 | 21.8 (1.98) | – | -0.23 | 11% |
| ibs_reversal | 11.54 (1.01) | – | -0.55 | 12.82 (1.34) | – | -0.36 | 14% |
| turn_of_month | 23.24 (1.36) | – | -0.06 | -0.83 (-0.07) | – | -0.76 | 19% |
| market_regime | -3.29 (-0.56) | 17.74 (0.57) | -0.1 | 1.21 (0.25) | -5.14 (-0.3) | 0.07 | 81% |
| vix_backwardation | 13.24 (0.39) | – | -0.55 | 35.24 (0.79) | – | -0.48 | 4% |
| tsmom28 | -2.24 (-0.38) | 4.29 (0.31) | -0.16 | -0.28 (-0.06) | 0.41 (0.05) | -0.23 | 60% |
| sma_ensemble | -2.5 (-0.46) | 18.72 (0.88) | -0.07 | -0.04 (-0.01) | 1.5 (0.13) | -0.15 | 61% |
| donchian_ensemble | -3.49 (-0.57) | 5.92 (0.22) | -0.41 | 0.96 (0.18) | 2.55 (0.15) | -0.2 | 49% |
| high_breakout_trail | 0.8 (0.12) | -37.4 (-0.78) | -0.29 | 3.38 (0.59) | 20.7 (0.71) | -0.25 | 29% |
| trend_classic | -3.23 (-0.54) | 9.23 (0.58) | -0.18 | -0.72 (-0.15) | 1.45 (0.14) | -0.15 | 63% |
| meanrev_z | 76.42 (1.96) | -1.94 (-0.15) | -0.02 | 21.71 (1.12) | 4.64 (0.4) | -0.55 | 4% |
| confluence | -41.49 (-0.95) | -3.07 (-0.35) | -1.07 | 27.66 (1.21) | 3.87 (0.49) | -0.57 | 3% |
| atr_layers | 17.97 (0.68) | -0.98 (-0.16) | -0.5 | 15.38 (1.02) | 4.27 (0.75) | -0.29 | 15% |
| momentum_classic | -1.03 (-0.16) | 4.7 (0.24) | -0.28 | 1.63 (0.29) | 1.75 (0.18) | -0.16 | 44% |
| ia_ribbon | -0.5 (-0.09) | 1.19 (0.07) | -0.07 | -0.99 (-0.2) | 1.63 (0.18) | -0.18 | 61% |
| ia_atr_stop | -6.14 (-0.92) | 10.45 (0.91) | -0.49 | -2.47 (-0.47) | 3.23 (0.41) | -0.35 | 57% |
| ia_ath_discount | 34.11 (1.28) | – | -0.61 | 10.5 (0.83) | – | -0.34 | 14% |
| old_ensemble | 45.95 (0.89) | -1.07 (-0.03) | -0.43 | 49.1 (1.68) | -20.73 (-0.75) | -0.58 | 1% |

## crypto-1d

Train 2017-06-20 → 2020-12-31 · Test 2021-01-01 → 2026-10-12 · 5 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate, ibs_reversal, trend_classic, momentum_classic, ia_ribbon, ia_atr_stop

- Preset **trend4_majority** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.0):
  - train: bullish 15.12 bp (t 0.96), bearish -20.04 bp (t -0.95); long-only Sharpe 1.36 vs hold 1.27, return 90.4%/yr vs 102.3%, worst dip -54.5% vs -73.8%, invested 53%
  - test: bullish 20.04 bp (t 1.88), bearish -19.28 bp (t -1.46); long-only Sharpe 0.88 vs hold 0.6, return 40.4%/yr vs 19.7%, worst dip -70.0% vs -90.2%, invested 52%
- Preset **trend4_3of4** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.5):
  - train: bullish 28.07 bp (t 1.55), bearish -28.28 bp (t -0.97); long-only Sharpe 1.41 vs hold 1.27, return 101.5%/yr vs 102.3%, worst dip -39.3% vs -73.8%, invested 41%
  - test: bullish 30.51 bp (t 2.63), bearish -16.72 bp (t -1.04); long-only Sharpe 0.92 vs hold 0.6, return 36.1%/yr vs 19.7%, worst dip -52.7% vs -90.2%, invested 38%
- Preset **ia_ribbon_and_stop** (ia_ribbon, ia_atr_stop; bullish when average vote > 0.5):
  - train: bullish 17.55 bp (t 0.93), bearish -19.61 bp (t -0.71); long-only Sharpe 1.03 vs hold 1.27, return 53.4%/yr vs 102.3%, worst dip -48.6% vs -73.8%, invested 32%
  - test: bullish 17.54 bp (t 1.41), bearish -12.8 bp (t -0.9); long-only Sharpe 0.65 vs hold 0.6, return 17.0%/yr vs 19.7%, worst dip -73.4% vs -90.2%, invested 28%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| tsmom28 | 14.11 (0.92) | -20.55 (-0.97) | 0.03 | 17.59 (1.69) | -17.9 (-1.5) | 0.23 | 51% |
| sma_ensemble | 16.06 (1.03) | -25.88 (-1.01) | 0.01 | 16.0 (1.51) | -16.23 (-1.1) | 0.16 | 52% |
| donchian_ensemble | 39.2 (1.7) | -24.18 (-0.86) | -0.2 | 31.9 (2.38) | -9.55 (-0.6) | 0.06 | 31% |
| btc_trend_gate | 17.32 (1.03) | -20.13 (-0.97) | 0.17 | 22.13 (2.08) | -24.85 (-1.83) | 0.39 | 53% |
| high_breakout_trail | 52.98 (1.77) | -89.18 (-0.34) | -0.35 | 36.35 (1.98) | 313.65 (3.21) | -0.19 | 12% |
| rsi2_pullback | -7.05 (-0.15) | – | -1.16 | 4.09 (0.16) | – | -0.51 | 8% |
| ibs_reversal | 20.35 (0.52) | – | -1.34 | 1.64 (0.07) | – | -1.13 | 8% |
| turn_of_month | -15.31 (-0.5) | – | -1.14 | -9.0 (-0.41) | – | -0.85 | 15% |
| trend_classic | 7.57 (0.46) | -10.54 (-0.58) | -0.17 | 15.43 (1.38) | -13.52 (-1.21) | 0.16 | 48% |
| meanrev_z | 1.04 (0.01) | 18.76 (0.52) | -1.27 | 35.11 (0.68) | 30.28 (1.29) | -0.44 | 4% |
| confluence | 12.71 (0.19) | 71.89 (1.99) | -1.29 | 25.21 (0.66) | 35.75 (1.47) | -0.66 | 4% |
| atr_layers | -10.71 (-0.37) | 31.45 (1.61) | -0.98 | -17.08 (-0.97) | 33.35 (2.38) | -0.82 | 23% |
| momentum_classic | 31.2 (1.72) | -26.78 (-0.95) | -0.04 | 15.19 (1.25) | -12.33 (-0.82) | -0.04 | 37% |
| ia_ribbon | 10.89 (0.68) | -14.44 (-0.78) | -0.18 | 14.73 (1.3) | -13.79 (-1.22) | 0.14 | 50% |
| ia_atr_stop | 7.8 (0.53) | -10.17 (-0.48) | -0.22 | 4.23 (0.42) | -3.87 (-0.33) | -0.33 | 48% |
| ia_ath_discount | -6.59 (-0.49) | – | -0.14 | -1.28 (-0.13) | – | -0.08 | 73% |
| old_ensemble | 99.04 (0.65) | -28.75 (-0.38) | -1.07 | 153.05 (1.44) | 4.89 (0.11) | -0.41 | 1% |

## stock-4h

Train 2024-03-20 → 2025-06-30 · Test 2025-07-01 → 2026-10-12 · 13 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** turn_of_month, vix_backwardation, atr_layers, ia_ath_discount

- Preset **pullback_any** (rsi2_pullback, ibs_reversal, vix_backwardation; bullish when average vote > 0.0):
  - train: bullish -0.53 bp (t -0.06), bearish None bp (t None); long-only Sharpe 0.21 vs hold 0.8, return 0.6%/yr vs 16.6%, worst dip -29.7% vs -38.2%, invested 31%
  - test: bullish 7.96 bp (t 1.01), bearish None bp (t None); long-only Sharpe 0.49 vs hold 1.39, return 6.4%/yr vs 31.1%, worst dip -17.1% vs -30.0%, invested 28%
- Preset **ia_ribbon_and_stop** (ia_ribbon, ia_atr_stop; bullish when average vote > 0.5):
  - train: bullish -0.23 bp (t -0.05), bearish 4.54 bp (t 0.36); long-only Sharpe 0.25 vs hold 0.8, return 1.9%/yr vs 16.6%, worst dip -18.9% vs -38.2%, invested 34%
  - test: bullish -3.41 bp (t -0.68), bearish 0.74 bp (t 0.11); long-only Sharpe -0.27 vs hold 1.39, return -4.0%/yr vs 31.1%, worst dip -26.6% vs -30.0%, invested 33%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| rsi2_pullback | -8.41 (-0.94) | – | -1.06 | 4.19 (0.49) | – | -0.7 | 13% |
| ibs_reversal | -2.18 (-0.28) | – | -0.9 | 6.38 (0.63) | – | -1.35 | 14% |
| turn_of_month | 0.31 (0.02) | – | -0.72 | 6.21 (0.63) | – | -0.57 | 19% |
| market_regime | -2.46 (-0.56) | 18.69 (0.76) | -0.26 | -0.33 (-0.09) | 9.7 (0.26) | -0.1 | 97% |
| vix_backwardation | 15.57 (0.68) | – | -0.43 | 39.37 (1.36) | – | -0.28 | 4% |
| tsmom28 | -0.78 (-0.16) | 1.07 (0.14) | -0.22 | -2.26 (-0.51) | 3.1 (0.58) | -0.65 | 59% |
| sma_ensemble | -0.53 (-0.11) | 2.59 (0.23) | -0.27 | -3.39 (-0.79) | 5.15 (0.76) | -0.76 | 62% |
| donchian_ensemble | 1.19 (0.24) | 10.32 (0.68) | -0.2 | -0.14 (-0.03) | 1.64 (0.21) | -0.5 | 41% |
| high_breakout_trail | -2.15 (-0.37) | 7.28 (0.28) | -0.72 | -0.93 (-0.16) | -1.95 (-0.09) | -0.66 | 25% |
| trend_classic | -2.22 (-0.49) | 3.56 (0.42) | -0.24 | -1.74 (-0.39) | 3.07 (0.55) | -0.46 | 67% |
| meanrev_z | -9.76 (-0.62) | 5.35 (0.62) | -1.12 | -3.01 (-0.27) | -3.59 (-0.43) | -0.81 | 5% |
| confluence | 7.86 (0.54) | -6.91 (-1.04) | -0.33 | 22.24 (1.37) | 7.77 (0.98) | -0.65 | 3% |
| atr_layers | 5.41 (0.45) | -2.94 (-0.54) | -0.32 | 14.9 (1.7) | -1.29 (-0.24) | -0.07 | 15% |
| momentum_classic | -3.52 (-0.66) | 0.28 (0.03) | -0.5 | -1.1 (-0.23) | 11.33 (1.7) | -0.56 | 42% |
| ia_ribbon | -0.82 (-0.17) | 1.15 (0.14) | -0.18 | -1.89 (-0.43) | 2.93 (0.52) | -0.58 | 61% |
| ia_atr_stop | -0.93 (-0.17) | 1.15 (0.16) | -0.61 | -0.28 (-0.06) | 0.33 (0.07) | -0.55 | 54% |
| ia_ath_discount | 13.59 (0.96) | – | -0.54 | 49.78 (2.01) | – | -0.98 | 0% |
| old_ensemble | 6.44 (0.34) | -38.19 (-1.26) | -0.52 | 49.4 (1.9) | 8.53 (0.27) | -0.39 | 1% |

## crypto-4h

Train 2024-11-25 → 2025-11-03 · Test 2025-11-04 → 2026-10-13 · 5 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** btc_trend_gate, ibs_reversal, ia_atr_stop, ia_ath_discount

- Preset **trend4_majority** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.0):
  - train: bullish -0.86 bp (t -0.21), bearish -0.24 bp (t -0.04); long-only Sharpe -0.86 vs hold 0.34, return -44.1%/yr vs -14.7%, worst dip -61.3% vs -65.9%, invested 49%
  - test: bullish -1.96 bp (t -0.56), bearish 1.12 bp (t 0.28); long-only Sharpe -1.66 vs hold -0.39, return -46.1%/yr vs -33.2%, worst dip -60.2% vs -57.5%, invested 45%
- Preset **trend4_3of4** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.5):
  - train: bullish 5.63 bp (t 1.09), bearish 4.75 bp (t 0.55); long-only Sharpe 0.49 vs hold 0.34, return 12.4%/yr vs -14.7%, worst dip -28.8% vs -65.9%, invested 31%
  - test: bullish 2.74 bp (t 0.54), bearish -1.72 bp (t -0.26); long-only Sharpe -0.6 vs hold -0.39, return -21.6%/yr vs -33.2%, worst dip -30.7% vs -57.5%, invested 24%
- Preset **ia_ribbon_and_stop** (ia_ribbon, ia_atr_stop; bullish when average vote > 0.5):
  - train: bullish 2.02 bp (t 0.42), bearish -2.54 bp (t -0.35); long-only Sharpe -1.55 vs hold 0.34, return -52.3%/yr vs -14.7%, worst dip -52.6% vs -65.9%, invested 25%
  - test: bullish 0.14 bp (t 0.03), bearish -0.63 bp (t -0.12); long-only Sharpe -2.13 vs hold -0.39, return -42.2%/yr vs -33.2%, worst dip -46.3% vs -57.5%, invested 22%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| tsmom28 | 0.03 (0.01) | -0.03 (-0.01) | -0.73 | -1.64 (-0.47) | 1.43 (0.39) | -1.51 | 47% |
| sma_ensemble | 0.97 (0.23) | -0.28 (-0.04) | -0.67 | -1.02 (-0.28) | -0.15 (-0.03) | -1.09 | 46% |
| donchian_ensemble | 2.06 (0.41) | 2.85 (0.36) | -0.4 | 0.97 (0.21) | -0.19 (-0.03) | -0.43 | 25% |
| btc_trend_gate | 0.1 (0.02) | -0.15 (-0.02) | -0.28 | 3.39 (1.04) | -2.98 (-0.73) | 0.83 | 47% |
| high_breakout_trail | 4.87 (0.63) | -4.82 (-0.17) | 0.25 | 5.75 (0.71) | 5.45 (0.32) | 0.75 | 10% |
| rsi2_pullback | -2.83 (-0.35) | – | -1.13 | -1.04 (-0.21) | – | -1.23 | 8% |
| ibs_reversal | 0.6 (0.08) | – | -3.24 | 5.45 (0.85) | – | -4.04 | 8% |
| turn_of_month | -1.34 (-0.12) | – | -0.31 | 1.11 (0.14) | – | 0.08 | 14% |
| trend_classic | 1.68 (0.41) | -1.46 (-0.29) | 0.02 | -0.41 (-0.12) | 0.34 (0.09) | 0.05 | 46% |
| meanrev_z | -19.09 (-1.02) | 4.89 (0.53) | -2.06 | 3.74 (0.3) | -4.12 (-0.49) | -0.9 | 6% |
| confluence | -0.52 (-0.04) | 5.92 (0.7) | -2.5 | -3.11 (-0.38) | 7.82 (1.13) | -3.33 | 9% |
| atr_layers | 3.85 (0.47) | 5.93 (1.1) | -0.61 | 0.02 (0.0) | 0.77 (0.14) | -0.74 | 23% |
| momentum_classic | -1.82 (-0.36) | -1.93 (-0.31) | -1.32 | -3.92 (-0.87) | 1.05 (0.21) | -2.02 | 33% |
| ia_ribbon | -1.34 (-0.31) | 1.25 (0.25) | -0.61 | -2.66 (-0.76) | 2.21 (0.6) | -0.66 | 45% |
| ia_atr_stop | 3.49 (0.88) | -3.66 (-0.72) | -1.79 | 2.76 (0.79) | -2.84 (-0.81) | -1.61 | 50% |
| ia_ath_discount | 4.23 (0.82) | – | 0.48 | 0.72 (0.26) | – | -0.0 | 100% |
| old_ensemble | -1.28 (-0.07) | -37.42 (-1.67) | -1.23 | 17.33 (0.96) | -0.27 (-0.02) | -0.74 | 1% |

## stock-1h

Train 2024-01-08 → 2025-05-23 · Test 2025-05-27 → 2026-10-12 · 13 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** turn_of_month, vix_backwardation, ia_ath_discount

- Preset **pullback_any** (rsi2_pullback, ibs_reversal, vix_backwardation; bullish when average vote > 0.0):
  - train: bullish 1.74 bp (t 0.51), bearish None bp (t None); long-only Sharpe 0.06 vs hold 0.77, return -0.5%/yr vs 17.8%, worst dip -28.2% vs -38.5%, invested 29%
  - test: bullish 1.89 bp (t 0.88), bearish None bp (t None); long-only Sharpe -0.29 vs hold 1.58, return -5.6%/yr vs 44.6%, worst dip -17.9% vs -31.1%, invested 25%
- Preset **ia_ribbon_and_stop** (ia_ribbon, ia_atr_stop; bullish when average vote > 0.5):
  - train: bullish 1.23 bp (t 0.71), bearish -0.42 bp (t -0.14); long-only Sharpe -0.01 vs hold 0.77, return -1.8%/yr vs 17.8%, worst dip -23.1% vs -38.5%, invested 32%
  - test: bullish -1.6 bp (t -1.08), bearish 3.35 bp (t 1.19); long-only Sharpe -0.44 vs hold 1.58, return -4.1%/yr vs 44.6%, worst dip -28.6% vs -31.1%, invested 34%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| rsi2_pullback | -0.59 (-0.2) | – | -1.02 | 0.9 (0.43) | – | -1.32 | 13% |
| ibs_reversal | -0.02 (-0.01) | – | -2.3 | -0.48 (-0.17) | – | -1.99 | 12% |
| turn_of_month | 0.23 (0.05) | – | -0.95 | 1.11 (0.35) | – | -0.66 | 19% |
| market_regime | -0.66 (-0.46) | 4.75 (0.6) | -0.25 | 0.05 (0.04) | -1.32 (-0.12) | -0.03 | 97% |
| vix_backwardation | 6.44 (0.75) | – | -0.34 | 14.19 (1.62) | – | -0.32 | 4% |
| tsmom28 | -0.43 (-0.28) | 0.54 (0.21) | -0.49 | -0.46 (-0.35) | 0.62 (0.33) | -0.64 | 58% |
| sma_ensemble | 0.01 (0.01) | 0.36 (0.12) | -0.53 | -0.71 (-0.55) | 1.87 (0.78) | -0.77 | 60% |
| donchian_ensemble | 0.1 (0.06) | -0.01 (-0.0) | -0.55 | -1.2 (-0.88) | 3.54 (1.18) | -1.0 | 43% |
| high_breakout_trail | 0.35 (0.19) | 4.91 (0.65) | -0.5 | -0.73 (-0.43) | -11.52 (-1.73) | -0.77 | 24% |
| trend_classic | 0.31 (0.21) | -0.44 (-0.16) | -0.13 | -0.32 (-0.26) | 0.51 (0.26) | -0.44 | 63% |
| meanrev_z | -2.4 (-0.56) | -3.36 (-1.14) | -1.36 | 7.35 (2.03) | -2.27 (-1.0) | -1.12 | 5% |
| confluence | -0.77 (-0.18) | -0.79 (-0.34) | -1.24 | 1.12 (0.31) | -2.44 (-1.02) | -1.27 | 7% |
| atr_layers | 2.04 (0.62) | 1.02 (0.63) | -0.26 | 3.43 (1.25) | -1.2 (-0.78) | -0.26 | 20% |
| momentum_classic | 0.18 (0.1) | -0.23 (-0.08) | -0.46 | -1.23 (-0.88) | 1.29 (0.6) | -1.1 | 42% |
| ia_ribbon | 0.54 (0.35) | -0.71 (-0.27) | -0.2 | -0.71 (-0.56) | 1.04 (0.54) | -0.56 | 61% |
| ia_atr_stop | 0.34 (0.19) | -0.39 (-0.19) | -1.14 | -1.49 (-1.05) | 1.73 (0.95) | -1.67 | 53% |
| ia_ath_discount | 3.96 (0.7) | – | -0.67 | 13.1 (2.35) | – | -0.89 | 0% |
| old_ensemble | 7.2 (1.39) | -6.17 (-0.48) | -0.94 | -9.24 (-2.16) | -4.38 (-0.69) | -2.38 | 1% |

## crypto-1h

Train 2024-10-25 → 2025-10-19 · Test 2025-10-19 → 2026-10-13 · 5 tickers

**Kept (from train, strict rule):** none

**Right direction in both halves:** btc_trend_gate, momentum_classic, ia_ath_discount

- Preset **trend4_majority** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.0):
  - train: bullish 0.17 bp (t 0.17), bearish -0.12 bp (t -0.08); long-only Sharpe -2.51 vs hold 0.88, return -76.0%/yr vs 46.3%, worst dip -82.2% vs -66.3%, invested 51%
  - test: bullish -0.07 bp (t -0.09), bearish 0.03 bp (t 0.02); long-only Sharpe -4.81 vs hold -0.48, return -85.0%/yr vs -37.1%, worst dip -84.9% vs -64.1%, invested 48%
- Preset **trend4_3of4** (tsmom28, sma_ensemble, donchian_ensemble, btc_trend_gate; bullish when average vote > 0.5):
  - train: bullish 1.33 bp (t 1.06), bearish 0.11 bp (t 0.04); long-only Sharpe -1.2 vs hold 0.88, return -47.7%/yr vs 46.3%, worst dip -65.8% vs -66.3%, invested 32%
  - test: bullish 0.89 bp (t 0.69), bearish -0.63 bp (t -0.37); long-only Sharpe -2.91 vs hold -0.48, return -55.1%/yr vs -37.1%, worst dip -55.6% vs -64.1%, invested 21%
- Preset **ia_ribbon_and_stop** (ia_ribbon, ia_atr_stop; bullish when average vote > 0.5):
  - train: bullish 0.74 bp (t 0.6), bearish -0.25 bp (t -0.15); long-only Sharpe -6.52 vs hold 0.88, return -95.3%/yr vs 46.3%, worst dip -95.4% vs -66.3%, invested 26%
  - test: bullish 0.12 bp (t 0.1), bearish 0.11 bp (t 0.09); long-only Sharpe -8.81 vs hold -0.48, return -94.6%/yr vs -37.1%, worst dip -94.6% vs -64.1%, invested 24%

| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |
|---|---|---|---|---|---|---|---|
| tsmom28 | 0.12 (0.12) | -0.13 (-0.11) | -2.98 | -0.07 (-0.09) | 0.07 (0.08) | -4.7 | 49% |
| sma_ensemble | 0.59 (0.57) | -0.69 (-0.46) | -2.13 | -0.19 (-0.23) | 0.25 (0.22) | -4.39 | 49% |
| donchian_ensemble | 1.3 (1.07) | -1.34 (-0.74) | -1.44 | 0.16 (0.14) | 0.3 (0.22) | -2.68 | 25% |
| btc_trend_gate | 0.23 (0.23) | -0.43 (-0.26) | -0.1 | 0.83 (0.98) | -0.68 (-0.7) | 0.9 | 45% |
| high_breakout_trail | 1.8 (1.1) | 6.37 (0.9) | -0.75 | 0.54 (0.3) | 11.03 (1.8) | -0.21 | 10% |
| rsi2_pullback | 0.33 (0.17) | – | -4.3 | -0.34 (-0.22) | – | -5.0 | 8% |
| ibs_reversal | 2.59 (1.57) | – | -13.74 | -1.81 (-1.21) | – | -17.44 | 10% |
| turn_of_month | -1.04 (-0.39) | – | -1.11 | -0.51 (-0.27) | – | -0.18 | 15% |
| trend_classic | 0.34 (0.33) | -0.34 (-0.28) | -0.93 | -0.6 (-0.7) | 0.52 (0.58) | -1.98 | 47% |
| meanrev_z | 0.49 (0.11) | 3.63 (1.25) | -5.05 | -3.64 (-1.3) | 4.18 (1.55) | -6.66 | 6% |
| confluence | -0.38 (-0.14) | -0.46 (-0.21) | -8.44 | 2.32 (1.13) | 1.72 (0.97) | -9.26 | 8% |
| atr_layers | -1.18 (-0.67) | 1.63 (1.26) | -3.61 | -0.44 (-0.31) | 0.18 (0.14) | -3.08 | 25% |
| momentum_classic | 1.17 (1.02) | -1.02 (-0.73) | -3.46 | 0.43 (0.4) | -0.43 (-0.39) | -4.65 | 32% |
| ia_ribbon | 0.51 (0.48) | -0.53 (-0.44) | -0.85 | -0.56 (-0.67) | 0.52 (0.56) | -1.95 | 48% |
| ia_atr_stop | -0.01 (-0.01) | 0.01 (0.01) | -9.66 | 0.54 (0.6) | -0.55 (-0.65) | -11.05 | 50% |
| ia_ath_discount | 0.52 (0.39) | – | -0.24 | 0.19 (0.28) | – | 0.06 | 96% |
| old_ensemble | 1.36 (0.3) | 3.7 (0.72) | -4.52 | -4.45 (-1.01) | -0.52 (-0.1) | -5.43 | 1% |

_Personal research only. Past results don't guarantee future results._