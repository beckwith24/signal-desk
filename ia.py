"""
InvestAnswers-style indicators, reverse-engineered from the TradingView screenshots.

How each formula was found is in research/ia_calibration.md (calibrate_ia.py lines the screenshots
up with real prices and searches thousands of candidate formulas):

  Optimized-Trend ribbon   EMA(15) of (high+low+close)/3  vs  EMA(34) of close.
                           Blue when the fast line is above, orange when below.
                           Matched SK hynix and Samsung to ~0.3-0.7% with 97-98% colour agreement.
  ATR-Model buy/sell       ATR trailing stop ("UT Bot" style): the stop trails k x ATR(30) behind the
                           close and flips when the close crosses it. Daily k = 1.25 reproduced 31 of
                           34 BTC triangles (3 extra signals); on the 4h CBRS chart a tighter k of
                           about 0.5 fitted best (about 23 of 32 triangles).
  ATR-Model levels         Fibonacci fractions of the all-time high: Level 1..6 =
                           0.236, 0.382, 0.5, 0.618, 0.764, 1.0 x ATH. BTC levels matched within 0.25%.

These are close approximations, not InvestAnswers' code.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

RIBBON_FAST, RIBBON_SLOW = 15, 34
STOP_KEY, STOP_KEY_INTRADAY, STOP_ATR = 1.25, 0.5, 30
FIB = {1: 0.236, 2: 0.382, 3: 0.5, 4: 0.618, 5: 0.764, 6: 1.0}
ATH_CACHE = Path(__file__).with_name("ath.json")


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def ribbon(df: pd.DataFrame, fast: int = RIBBON_FAST, slow: int = RIBBON_SLOW) -> tuple[pd.Series, pd.Series]:
    hlc3 = (df["high"] + df["low"] + df["close"]) / 3
    return _ema(hlc3, fast), _ema(df["close"], slow)


def is_intraday(df: pd.DataFrame) -> bool:
    if len(df) < 3:
        return False
    return pd.Series(df.index).diff().median() < pd.Timedelta(hours=20)


def atr_stop(df: pd.DataFrame, key: float | None = None, n: int = STOP_ATR) -> tuple[pd.Series, pd.Series]:
    """ATR trailing stop. Returns (stop level, uptrend flag). Only uses past and current bars."""
    if key is None:
        key = STOP_KEY_INTRADAY if is_intraday(df) else STOP_KEY
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    loss = (key * tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()).tolist()
    c = df["close"].tolist()
    N = len(c)
    stop = [np.nan] * N
    up = [False] * N
    prev = 0.0
    for i in range(1, N):
        nl = loss[i]
        if nl != nl:          # not enough bars for the ATR yet
            continue
        x, xp = c[i], c[i - 1]
        if x > prev and xp > prev:
            s = max(prev, x - nl)
        elif x < prev and xp < prev:
            s = min(prev, x + nl)
        elif x > prev:
            s = x - nl
        else:
            s = x + nl
        stop[i], up[i], prev = s, x > s, s
    return pd.Series(stop, index=df.index), pd.Series(up, index=df.index)


def levels(ath: float) -> dict[int, float]:
    return {k: ath * f for k, f in FIB.items()}


def level_of(price: float, ath: float) -> float:
    """Where price sits on the 1..6 ladder, e.g. 3.4 = 40% of the way from Level 3 to Level 4."""
    fr = price / ath
    ks = sorted(FIB)
    if fr <= FIB[ks[0]]:
        return fr / FIB[ks[0]]
    for a, b in zip(ks, ks[1:]):
        if fr <= FIB[b]:
            return a + (fr - FIB[a]) / (FIB[b] - FIB[a])
    return 6.0 + (fr - 1.0)


def running_ath(df: pd.DataFrame, known: tuple[float, str] | None = None) -> pd.Series:
    """All-time high so far at each bar. `known` = (ATH, date) from the full history, used from that date on."""
    run = df["high"].cummax()
    if known and known[0]:
        when = pd.Timestamp(known[1])
        when = when.tz_localize(df.index.tz) if df.index.tz is not None and when.tzinfo is None else when
        run = run.where(df.index < when, np.maximum(run, known[0]))
    return run


# ----------------------------------------------------------------------------- all-time-high cache
def _load_cache() -> dict:
    try:
        return json.loads(ATH_CACHE.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def known_ath(ticker: str, refresh_days: int = 1) -> tuple[float, str] | None:
    """(ATH, month it happened) from Yahoo's full monthly history; cached in ath.json, refreshed daily."""
    cache = _load_cache()
    hit = cache.get(ticker)
    today = date.today().isoformat()
    if hit and (date.fromisoformat(hit["checked"]) - date.today()).days > -refresh_days:
        return hit["ath"], hit["date"]
    try:
        import yfinance as yf
        m = yf.Ticker(ticker).history(period="max", interval="1mo", auto_adjust=True)
        if m is None or m.empty:
            raise ValueError("no monthly history")
        i = m["High"].idxmax()
        rec = {"ath": float(m["High"].max()), "date": str(pd.Timestamp(i).date()), "checked": today}
        if hit and hit["ath"] > rec["ath"] and hit["date"] >= rec["date"]:
            rec.update(ath=hit["ath"], date=hit["date"])   # keep a higher high seen by the scans
        cache[ticker] = rec
        ATH_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
        return rec["ath"], rec["date"]
    except Exception as e:
        log.info("ATH lookup failed for %s: %s", ticker, e)
        return (hit["ath"], hit["date"]) if hit else None
