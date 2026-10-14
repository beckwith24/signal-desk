"""
Chart overlays and ATR layers, computed straight from prices.

Kept separate from the signal models so the charts and the layer-in / layer-out ladder look the
same whichever models a segment uses.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import ia
from signals import atr, ema, rsi, sma

EMA_FAST, EMA_SLOW, MA_LONG, BB_LEN, BB_SD = 21, 55, 200, 20, 2.0


def ia_view(df: pd.DataFrame, ath_known: tuple[float, str] | None = None, recent: int = 300) -> dict:
    """InvestAnswers-style view: trend ribbon, ATR buy/sell stop with its flips, all-time-high levels."""
    fast, slow = ia.ribbon(df)
    stop, up = ia.atr_stop(df)
    ready = stop.notna()
    flips = up.ne(up.shift(1)) & ready & ready.shift(1, fill_value=False)
    ath_s = ia.running_ath(df, ath_known)
    ath = float(ath_s.iat[-1])
    price = float(df["close"].iat[-1])
    since = int(len(df) - 1 - np.flatnonzero(flips.to_numpy())[-1]) if flips.any() else None
    tail = flips.iloc[-recent:]
    return {
        "fast": fast, "slow": slow, "stop": stop,
        "trend": "up" if fast.iat[-1] > slow.iat[-1] else "down",
        "stop_side": "buy" if bool(up.iat[-1]) else "sell",
        "stop_last": float(stop.iat[-1]) if ready.iat[-1] else None,
        "bars_since_flip": since,
        "flips": [(ts, "buy" if bool(up.loc[ts]) else "sell") for ts in tail.index[tail.to_numpy()]],
        "ath": ath, "ath_from_history": bool(ath_known),
        "levels": ia.levels(ath),
        "level": ia.level_of(price, ath),
        "pct_of_ath": price / ath,
        "intraday": ia.is_intraday(df),
        "stop_key": ia.STOP_KEY_INTRADAY if ia.is_intraday(df) else ia.STOP_KEY,
    }


RISK_TARGET = {"crypto": 0.60, "stock": 0.30}   # yearly swings of bitcoin / of a typical large stock


def risk_size(df: pd.DataFrame) -> dict | None:
    """Risk-matched position size: smaller in wilder tickers so each position carries similar risk.

    size = target volatility / this ticker's 30-day volatility, capped at 1 (never more than normal).
    Tested on 29 coins with the trend rule (research/factors.md): roughly halved the worst drops and
    gave up a similar share of the gains, so it's a risk choice, not an edge.
    """
    if ia.is_intraday(df) or len(df) < 40 or pd.Series(df.index).diff().median() > pd.Timedelta(days=3):
        return None                                               # daily bars only
    crypto = bool((df.index[-30:].dayofweek >= 5).any())       # trades on weekends
    per_year = 365 if crypto else 252
    vol = float(np.log(df["close"]).diff().iloc[-30:].std() * np.sqrt(per_year))
    if not vol or vol != vol:
        return None
    target = RISK_TARGET["crypto" if crypto else "stock"]
    size = min(1.0, target / vol)
    return {"vol_pct": round(vol * 100), "target_pct": round(target * 100), "size": round(size * 20) / 20}


def long_term(df: pd.DataFrame) -> dict | None:
    """Weekly bars only: the long-term trend. Uptrend = weekly IA ribbon blue AND price above its 40-week
    average; downtrend = both down; otherwise mixed. Tested (research/weekly.md): on the S&P 500 and Nasdaq,
    being out while it was down roughly halved the worst crashes since 2005; on single stocks it mostly cost
    return, so it's shown as information, not a signal."""
    if len(df) < 45 or pd.Series(df.index).diff().median() < pd.Timedelta(days=5):
        return None
    c = df["close"]
    fast, slow = ia.ribbon(df)
    up = (fast > slow).fillna(False)
    s40 = sma(c, 40)
    flips = up.ne(up.shift()).cumsum()
    weeks = None if flips.iat[-1] == 1 else int((flips == flips.iat[-1]).sum()) - 1   # None: no flip in the data
    above = bool(c.iat[-1] > s40.iat[-1]) if s40.iat[-1] == s40.iat[-1] else None
    ribbon_up = bool(up.iat[-1])
    state = "up" if ribbon_up and above else "down" if (not ribbon_up and above is False) else "mixed"
    return {"state": state, "ribbon_up": ribbon_up, "above_40w": above, "weeks": weeks,
            "sma40": float(s40.iat[-1]) if above is not None else None,
            "mom52_pct": round(float(c.iat[-1] / c.iat[-53] - 1) * 100, 1) if len(c) > 53 else None}


def compute(df: pd.DataFrame, cfg: dict, ath_known: tuple[float, str] | None = None) -> dict:
    c = df["close"]
    lp = cfg["models"]["atr_layers"]
    anchor = sma(c, lp["anchor_ma"])
    step = lp["layer_step"] * atr(df, lp["atr_period"])
    m, sd = sma(c, BB_LEN), c.rolling(BB_LEN).std()
    a_last = anchor.iat[-1] if not np.isnan(anchor.iat[-1]) else ema(c, lp["anchor_ma"]).iat[-1]
    s_last = float(step.iat[-1])
    dist = float((c.iat[-1] - a_last) / s_last) if s_last else 0.0
    mx = lp["max_layers"]
    lt = long_term(df)
    ma_long, ma_label = (sma(c, 40), "40-week average") if lt else (sma(c, MA_LONG), f"{MA_LONG} MA")
    return {
        "long_term": lt,
        "ema_fast": ema(c, EMA_FAST), "ema_slow": ema(c, EMA_SLOW), "ma_long": ma_long,
        "bb_up": m + BB_SD * sd, "bb_mid": m, "bb_lo": m - BB_SD * sd, "anchor": anchor,
        "labels": {"ema_fast": f"EMA {EMA_FAST}", "ema_slow": f"EMA {EMA_SLOW}", "ma_long": ma_label,
                   "anchor": f"{lp['anchor_ma']} MA (layer anchor)"},
        "anchor_last": float(a_last), "step_last": s_last, "distance": dist,
        "layer": int(np.clip(np.trunc(dist), -mx, mx)),
        "levels": {k: float(a_last + k * s_last) for k in range(-mx, mx + 1)},
        "rsi": float(rsi(c, 14).iat[-1]),
        "z": float(((c - m) / sd).iat[-1]) if sd.iat[-1] else 0.0,
        "anchor_ma": lp["anchor_ma"],
        "ia": ia_view(df, ath_known),
        "risk": risk_size(df),
    }
