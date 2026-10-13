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
    return {
        "ema_fast": ema(c, EMA_FAST), "ema_slow": ema(c, EMA_SLOW), "ma_long": sma(c, MA_LONG),
        "bb_up": m + BB_SD * sd, "bb_mid": m, "bb_lo": m - BB_SD * sd, "anchor": anchor,
        "labels": {"ema_fast": f"EMA {EMA_FAST}", "ema_slow": f"EMA {EMA_SLOW}", "ma_long": f"{MA_LONG} MA",
                   "anchor": f"{lp['anchor_ma']} MA (layer anchor)"},
        "anchor_last": float(a_last), "step_last": s_last, "distance": dist,
        "layer": int(np.clip(np.trunc(dist), -mx, mx)),
        "levels": {k: float(a_last + k * s_last) for k in range(-mx, mx + 1)},
        "rsi": float(rsi(c, 14).iat[-1]),
        "z": float(((c - m) / sd).iat[-1]) if sd.iat[-1] else 0.0,
        "anchor_ma": lp["anchor_ma"],
        "ia": ia_view(df, ath_known),
    }
