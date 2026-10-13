"""
Chart overlays and ATR layers, computed straight from prices.

Kept separate from the signal models so the charts and the layer-in / layer-out ladder look the
same whichever models a segment uses.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from signals import atr, ema, rsi, sma

EMA_FAST, EMA_SLOW, MA_LONG, BB_LEN, BB_SD = 21, 55, 200, 20, 2.0


def compute(df: pd.DataFrame, cfg: dict) -> dict:
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
    }
