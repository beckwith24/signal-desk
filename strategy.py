"""
The live portfolio rules, shared by trader.py and checked against the research backtest (test_trader.py).

Portfolio (research/portfolio.md, research/active.md):
  * 80% SPY, held. Rebalanced when it drifts more than 5% of the account from target.
  * 20% crypto trend sleeve: 5 coins, each with a fixed slot of 4% of the account.
      - A coin is "on" while the average of four trend votes is above 0.5
        (28-day momentum, price vs 20/50/100-day averages, breakout ensemble, Bitcoin vs its 50-day average).
      - Pyramid: buy 1/3 of the slot when it turns on, add 1/3 each time it closes 1 ATR above the last add
        (max 3/3). Sell everything when it turns off. No averaging down, no selling into strength:
        both tested worse.
  * Whatever the crypto sleeve isn't using stays in cash.

Everything here is a pure function of completed daily closes, so the target for today can be rebuilt
from history on every run. No state file is needed and re-running is harmless.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

COINS = ["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD", "AVAX-USD"]
STOCK_SYMBOL = "SPY"
STOCK_WEIGHT = 0.80
CRYPTO_WEIGHT = 0.20
LAYERS = 3
MIN_BARS = 400                      # breakout ensemble looks back up to 360 days


def sma(s, n):
    return s.rolling(n, min_periods=n).mean()


def donchian_frac(c: pd.Series, lookbacks=(5, 10, 20, 30, 60, 90, 150, 250, 360)) -> pd.Series:
    """Share of breakout systems (one per lookback) that are long. Same logic as models.donchian_ensemble."""
    v = c.values
    out = []
    for N in lookbacks:
        prior_high = c.shift(1).rolling(N, min_periods=N).max().values
        hi = c.rolling(N, min_periods=N).max().values
        lo = c.rolling(N, min_periods=N).min().values
        pos = np.zeros(len(v))
        on, stop = False, -np.inf
        for i in range(len(v)):
            if np.isnan(prior_high[i]) or np.isnan(v[i]):
                continue
            mid = (hi[i] + lo[i]) / 2
            if not on and v[i] > prior_high[i]:
                on, stop = True, mid
            elif on:
                stop = max(stop, mid)
                if v[i] < stop:
                    on = False
            pos[i] = 1 if on else 0
        out.append(pos)
    return pd.Series(np.mean(out, axis=0), index=c.index)


def trend_votes(closes: pd.DataFrame, tsmom_n: int = 28, btc_sma: int = 50) -> tuple[pd.DataFrame, dict]:
    """Average of the four trend votes per coin (-1..1) and the individual votes for the latest bar."""
    btc = closes["BTC-USD"]
    btc_vote = np.sign(btc - sma(btc, btc_sma)).where(sma(btc, btc_sma).notna(), 0)
    avg, latest = {}, {}
    for t in [c for c in COINS if c in closes]:
        c = closes[t].dropna()
        v1 = np.sign(c / c.shift(tsmom_n) - 1).fillna(0)
        frac = pd.concat([(c > sma(c, n)).astype(float).where(sma(c, n).notna()) for n in (20, 50, 100)], axis=1).mean(axis=1)
        v2 = pd.Series(np.where(frac.isna(), 0, np.where(frac >= 0.66, 1, np.where(frac <= 0, -1, 0))), index=c.index)
        dfr = donchian_frac(c)
        v3 = pd.Series(np.where(dfr >= 0.5, 1, np.where(dfr <= 0, -1, 0)), index=c.index)
        v4 = btc_vote.reindex(c.index).fillna(0)
        avg[t] = (v1 + v2 + v3 + v4) / 4
        if len(c):
            latest[t] = {"momentum": int(v1.iat[-1]), "averages": int(v2.iat[-1]),
                         "breakouts": int(v3.iat[-1]), "bitcoin": int(v4.iat[-1])}
    return pd.DataFrame(avg).reindex(closes.index), latest


def atr_close(closes: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """ATR from closes only (mean absolute daily change); what the backtest used."""
    return closes.diff().abs().rolling(n, min_periods=n).mean()


def pyramid(c: np.ndarray, on: np.ndarray, N: np.ndarray) -> np.ndarray:
    """Layers held (0..3) per bar: 1 at the first 'on' bar, +1 each close >= last add + 1 ATR, 0 when off."""
    units_out = np.zeros(len(c), dtype=int)
    units, last, in_trade = 0, np.nan, False
    for i in range(len(c)):
        if not on[i] or np.isnan(c[i]):
            units, in_trade = 0, False
        elif not in_trade:
            in_trade, units, last = True, 1, c[i]
        elif units < LAYERS and c[i] >= last + N[i]:
            units, last = units + 1, c[i]
        units_out[i] = units
    return units_out


def crypto_targets(closes: pd.DataFrame) -> dict[str, dict]:
    """For each coin: layers to hold now (0..3), vote details and the numbers behind them."""
    avg, latest = trend_votes(closes)
    N = atr_close(closes)
    out = {}
    for t in avg.columns:
        c = closes[t]
        on = (avg[t] > 0.5).fillna(False).values
        units = pyramid(c.values, on, N[t].values)
        ok = c.notna().sum() >= MIN_BARS
        out[t] = {"layers": int(units[-1]) if ok else 0, "on": bool(on[-1]) if ok else False,
                  "score": round(float(avg[t].iat[-1]), 2) if ok and pd.notna(avg[t].iat[-1]) else None,
                  "votes": latest.get(t, {}), "close": float(c.iat[-1]) if pd.notna(c.iat[-1]) else None,
                  "atr": float(N[t].iat[-1]) if pd.notna(N[t].iat[-1]) else None,
                  "enough_data": bool(ok), "bars": int(c.notna().sum())}
    return out


def slot_value(equity: float) -> float:
    """Dollar size of one coin's full slot (all 3 layers)."""
    return equity * CRYPTO_WEIGHT / len(COINS)
