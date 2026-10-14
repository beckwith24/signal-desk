# What InvestAnswers says about the models (paraphrased notes)

## ATR Model ("ATR DEMO" video, InvestAnswers, 12 Mar 2026, https://youtu.be/2BKyuH7oARw)

- Three jobs: trend and mean-reversion buy/sell flags, automatic support/resistance "levels" (purple lines,
  Level 0 to Level 6), and a built-in backtest table for tuning the settings.
- The trend ribbon is part of it: blue = uptrend, orange = downtrend.
- Levels are built from the all-time high reached after the chosen start date, and move up when a new high is
  made. Advice: set the start date before the last all-time high (for crypto, the prior cycle peak, Nov 2021).
- A grey/red background gradient marks bear markets.
- Settings:
  - Signal logic: **Trend** (stocks, crypto) or **Deviation** (mean reversion; slow movers, commodities).
  - Noise suppression: None / Low / Medium (default) / High. Less suppression = more signals.
  - Chart basis: candles / line / Heikin-Ashi (Heikin-Ashi showed the best win rate in the demo).
  - Order trigger: bar open (short timeframes) or bar close (longer ones).
  - Entry size per signal (the author uses 50% to "double tap in, double tap out"); exit size; FIFO or LIFO.
  - Initial capital for the simulated backtest.
- Timeframe: built for the daily chart (product page: also 12h / 2-day / 3-day / weekly; not for day trading).
  In the demo the 12h, 8h and 4h results on TSLA were worse than daily.
- How the demo tunes it: try combinations per asset and keep the one with a high win rate (80-90%), strong
  ROI and a manageable number of trades; if no combination looks good, skip the asset. Example on TSLA since
  2021: Heikin-Ashi + no suppression 85% wins / ~1,500% ROI; Low 90% / ~700%; Medium 80% / ~200%.

**Caution for our use:** those numbers are measured on the same history the settings were picked on, after
trying many combinations per asset and dropping assets that don't fit. That flatters results. Our tests pick
settings on older data and judge them on later data they never saw.

## Confluence Model
No public description found. Behaviour read from a UMAC 1h screenshot: see research/ia_targets/umac_conf.json.
