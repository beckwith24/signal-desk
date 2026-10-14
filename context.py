"""
Outside data the models use, lined up with a ticker's bars WITHOUT look-ahead.

  stocks: SPY close and its 200-day average (market regime), VIX and 3-month VIX (panic gauge)
  crypto: BTC close and its 50-day average (alts tend to follow Bitcoin)

Alignment rules
  daily bars:    same calendar date (New York date for stocks, UTC date for crypto); daily closes of
                 SPY/VIX/BTC are known at the same moment as the ticker's own daily close.
  intraday bars: the previous day's value (a 4h/1h bar can't know today's daily close yet).
"""
from __future__ import annotations

import logging

import pandas as pd

from signals import sma

log = logging.getLogger(__name__)
SYMBOLS = {"spy": "SPY", "vix": "^VIX", "vix3m": "^VIX3M", "btc": "BTC-USD"}


def fetch_daily(fetch, need: set[str]) -> dict[str, pd.Series]:
    """fetch(symbol) -> daily OHLCV DataFrame. Missing pieces are skipped (models then stay neutral)."""
    out = {}
    for key in need:
        try:
            out[key] = fetch(SYMBOLS[key])["close"]
        except Exception as e:
            log.warning("Context %s unavailable: %s", key, e)
    return out


def _by_date(s: pd.Series, tz: str) -> pd.Series:
    idx = s.index.tz_convert(tz) if s.index.tz is not None else s.index.tz_localize("UTC").tz_convert(tz)
    out = pd.Series(s.values, index=idx.normalize().tz_localize(None))
    return out[~out.index.duplicated(keep="last")]


def align(daily: dict[str, pd.Series], index: pd.DatetimeIndex, asset: str, tf: str) -> dict[str, pd.Series]:
    feats = {}
    if "spy" in daily:
        feats["spy_close"], feats["spy_sma200"] = daily["spy"], sma(daily["spy"], 200)
    if "vix" in daily:
        feats["vix"] = daily["vix"]
    if "vix3m" in daily:
        feats["vix3m"] = daily["vix3m"]
    if "btc" in daily:
        feats["btc_close"], feats["btc_sma"] = daily["btc"], sma(daily["btc"], 50)
        feats["btc_wk_up"] = btc_weekly_up(daily["btc"])
    out = {}
    if tf in ("1d", "1wk"):
        tz = "America/New_York" if asset == "stock" else "UTC"
        keys = _by_date(pd.Series(0, index=index), tz).index
        for k, s in feats.items():
            d = _by_date(s, tz)
            # VIX and SPY dates line up with stock dates; ffill covers holidays that differ.
            out[k] = pd.Series(d.reindex(d.index.union(keys)).ffill().reindex(keys).values, index=index)
    else:
        lagged = index - pd.Timedelta(days=1)
        for k, s in feats.items():
            s = s.sort_index()
            s.index = s.index.tz_convert("UTC") if s.index.tz is not None else s.index.tz_localize("UTC")
            vals = s.asof(lagged.tz_convert("UTC"))
            out[k] = pd.Series(vals.values, index=index)
    return out


def btc_weekly_up(close: pd.Series) -> pd.Series:
    """Bitcoin's weekly trend (ribbon blue and above its 40-week average), as a daily series that only changes after
    a week closes, so nothing from the current week leaks in."""
    import ia
    w = close.resample("W-SUN").agg(["first", "max", "min", "last"]).dropna()
    w.columns = ["open", "high", "low", "close"]
    fast, slow = ia.ribbon(w)
    up = ((fast > slow) & (w["close"] > w["close"].rolling(40, min_periods=40).mean())).where(fast.notna() & slow.notna())
    return up.reindex(close.index, method="ffill").shift(1)


def needs(asset: str) -> set[str]:
    return {"spy", "vix", "vix3m"} if asset == "stock" else {"btc"}
