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

### Testing the demo's tuning (research/ia_tuning.md)
Picking each ticker's settings on 2017-2022 the demo's way chose "only sell in profit" every time, so the win
rate stayed 100% after 2022 too. But from 2023 on the picked settings made a median +144% on 29 stocks vs +293%
for just holding (beat holding on 1 of 29), with about the same worst drop (-38% vs -37%), because a falling
position is held rather than sold. On 8 coins: +63% vs +120% holding; 7 of 8 still hold lots 28-80% under cost.
Without that option, the best tuned settings won ~80% (stocks) / ~40% (crypto) and still trailed holding.

## Confluence Model (research/confluence.md)
No public description. Rebuilt from a UMAC 1h screenshot (research/ia_targets/umac_conf.json):
- The screenshot lines up with real UMAC prices (correlation 0.99, median error 0.6%) on a 24-hour session chart.
- Grey envelope: Bollinger Bands, about 4 trading days long, 2-2.25 standard deviations (upper line within
  0.3-1%; the lower line fits worse, partly because the shaded box hides it).
- Triangles: "close comes back inside the band" reproduces 9 of 24 (chance: ~1); the solid triangles come
  ~8-12 hours after the faint ones, often right after the daily close. Other inputs set the exact timing.
- Its table (24 buys, 20 sells, 100% wins) is what you get when it only sells above the average cost: our
  rebuild on UMAC gave 100% wins and +171% over two years while UMAC itself rose ~1,100%.
- On the watchlist (hourly, 2 years, medians): stocks +44% with normal sells / +72% selling only above cost vs
  +100% holding. Crypto in a falling stretch: normal sells +5% vs -19% holding, but "only above cost" -35% and
  coins still held 52% under cost - the 100% win rate hides those open losses.
