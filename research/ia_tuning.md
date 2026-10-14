# Tuning the IA ATR Model per asset: does it hold up? (2026-10-14 00:43 UTC)

Settings picked on 2017–2022 (the demo's way: 80%+ wins, then highest ROI), then run on 2023-01-01 to now. Fills at next open, with costs. Our rebuild of the model, not IA's code.

## Stocks (29 tickers; 29 passed the 80%-win screen, 0 would be skipped)

| | Win % | ROI % | Worst drop % | Trades (sells) |
|---|---|---|---|---|
| Picked settings, 2017–2022 (in-sample) | 100.0 | 199.2 | -47.7 | 33.5 |
| Same settings, 2023–now (unseen) | 100.0 | 214.2 | -39.2 | 22.4 |
| Best in-sample ROI with normal sells, 2017–2022 | 74.8 | 134.6 | -29.5 | 32.7 |
| Same, 2023–now (unseen) | 74.9 | 78.6 | -27.3 | 20.7 |
| Default settings, 2023–now | 43.5 | 58.2 | -19.5 | 52.7 |
| Just holding, 2023–now | – | 512.0 | -41.7 | – |

Picked settings beat holding on 1 of 29 tickers after 2022. Average rank correlation between in-sample and later ROI across all 32 settings: 0.5 (1 = the best in-sample stay best; 0 = no link).

| Ticker | Picked settings | Win % then → after | ROI % then → after | Hold % after | Open lots / worst open lot % |
|---|---|---|---|---|---|
| NVDA | trend, none noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 378.8 → 755.3 | 1486.3 | 1 / 7.2 |
| AMD | trend, high noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 352.0 → 411.7 | 828.2 | 2 / 8.6 |
| AVGO | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 193.3 → 378.8 | 574.0 | 2 / -17.8 |
| TSLA | trend, low noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 464.7 → 129.4 | 249.7 | 2 / -15.1 |
| MRVL | trend, none noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 150.4 → 364.9 | 648.8 | 2 / -10.4 |
| MU | deviation, low noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 112.3 → 175.2 | 1893.2 | 0 / 0.0 |
| GOOGL | trend, high noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 100.7 → 224.5 | 299.5 | 2 / -4.4 |
| AAPL | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 247.3 → 144.3 | 177.5 | 2 / 2.0 |
| MSFT | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 208.8 → 95.9 | 132.7 | 2 / 1.7 |
| META | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | -9.8 → 244.0 | 501.3 | 2 / -5.8 |
| QQQ | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 95.5 → 116.2 | 188.1 | 1 / 3.6 |
| SPY | trend, low noise, candles, sells only in profit | 100.0 → 100.0 | 76.5 → 83.3 | 114.2 | 2 / 1.0 |
| TSM | trend, low noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 255.8 → 262.7 | 533.9 | 2 / -4.8 |
| LITE | deviation, high noise, candles, sells only in profit | 100.0 → 100.0 | 183.3 → 73.6 | 1787.4 | 0 / 0.0 |
| DELL | trend, low noise, candles, sells only in profit | 100.0 → 100.0 | 203.3 → 779.4 | 1415.0 | 2 / -2.8 |
| BE | deviation, high noise, candles, sells only in profit | 100.0 → 100.0 | 190.6 → 142.7 | 1266.8 | 1 / 37.6 |
| LLY | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 387.5 → 209.3 | 233.4 | 2 / 0.8 |
| PANW | deviation, medium noise, candles, sells only in profit | 100.0 → 100.0 | 288.2 → 243.7 | 483.4 | 0 / 0.0 |
| INTC | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 1.9 → 238.8 | 293.2 | 2 / -25.0 |
| NOW | trend, none noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 239.4 → 55.6 | 82.0 | 2 / -36.3 |
| CSCO | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 102.3 → 140.6 | 167.5 | 2 / -5.1 |
| CRM | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 69.5 → 24.0 | 76.9 | 2 / -34.8 |
| TXN | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 140.6 → 90.0 | 92.2 | 2 / -11.1 |
| ANET | trend, low noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 432.5 → 317.9 | 597.6 | 2 / 2.4 |
| V | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 131.1 → 67.7 | 93.1 | 2 / 2.3 |
| ABBV | trend, none noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 255.9 → 95.3 | 97.8 | 2 / 4.7 |
| XOM | deviation, medium noise, candles, sells only in profit | 100.0 → 100.0 | 117.6 → 64.8 | 82.8 | 0 / 0.0 |
| AMAT | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 184.0 → 261.0 | 430.3 | 2 / -28.6 |
| TMO | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 223.3 → 22.4 | 21.1 | 1 / -3.1 |

## Cryptos (10 tickers; 10 passed the 80%-win screen, 0 would be skipped)

| | Win % | ROI % | Worst drop % | Trades (sells) |
|---|---|---|---|---|
| Picked settings, 2017–2022 (in-sample) | 100.0 | 1205.8 | -84.5 | 12.1 |
| Same settings, 2023–now (unseen) | 100.0 | 121304.1 | -72.0 | 9.1 |
| Best in-sample ROI with normal sells, 2017–2022 | 49.7 | 14053.0 | -52.4 | 42.8 |
| Same, 2023–now (unseen) | 43.9 | 482.4 | -56.9 | 32.2 |
| Default settings, 2023–now | 32.1 | 5.8 | -52.0 | 64.0 |
| Just holding, 2023–now | – | 98.0 | -78.3 | – |

Picked settings beat holding on 3 of 10 tickers after 2022. Average rank correlation between in-sample and later ROI across all 32 settings: 0.0 (1 = the best in-sample stay best; 0 = no link).

| Ticker | Picked settings | Win % then → after | ROI % then → after | Hold % after | Open lots / worst open lot % |
|---|---|---|---|---|---|
| BTC-USD | trend, none noise, candles, sells only in profit | 100.0 → 100.0 | 1621.9 → 247.9 | 402.5 | 2 / -27.6 |
| ETH-USD | deviation, high noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 102.4 → 53.6 | 109.4 | 2 / -9.3 |
| LINK-USD | trend, none noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 1310.6 → 72.2 | 131.2 | 2 / -55.7 |
| JUP-USD | deviation, medium noise, candles, sells only in profit | 100.0 → 100.0 | 5259.2 → 1212411.1 | -93.9 | 0 / 0.0 |
| MET-USD | deviation, none noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 14.6 → -24.7 | -43.1 | 2 / -59.3 |
| XRP-USD | trend, high noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 68.0 → 135.9 | 305.9 | 2 / -58.3 |
| ADA-USD | trend, high noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 117.7 → -28.4 | -4.4 | 2 / -79.0 |
| DOGE-USD | trend, medium noise, candles, sells only in profit | 100.0 → 100.0 | 1182.9 → -3.9 | 21.0 | 2 / -80.1 |
| LTC-USD | trend, low noise, candles, sells only in profit | 100.0 → 100.0 | 2330.3 → -42.8 | -12.9 | 2 / -52.7 |
| XLM-USD | deviation, medium noise, heikin-ashi, sells only in profit | 100.0 → 100.0 | 50.4 → 219.8 | 164.3 | 2 / -46.3 |

Not enough history: PLTR: history starts 2020-09-30, CRDO: history starts 2022-01-27, ALAB: history starts 2024-03-20, HOOD: history starts 2021-07-29, SPCX: history starts 2026-06-12, SOL-USD: history starts 2020-04-10, AVAX-USD: history starts 2020-07-13, PUMP-USD: no data for PUMP-USD 1d, RAY-USD: history starts 2021-02-21, RENDER-USD: history starts 2020-06-11, HYPE-USD: no data for HYPE-USD 1d, NEAR-USD: history starts 2020-10-14, SUI-USD: no data for SUI-USD 1d, TAO-USD: no data for TAO-USD 1d, UNI-USD: no data for UNI-USD 1d, ONDO-USD: history starts 2024-01-18
