"""
Signal engine v2: each segment (stocks / crypto × daily / 4h / 1h) has its own model set, chosen
from published research and checked in our own walk-forward test (research/summary.md).

  crypto-1d  trend: 28-day momentum, price above 20/50/100-day MAs, breakout ensemble, Bitcoin trend
             Buy = at least 3 of 4 bullish (all 4 = Strong Buy). When that ends you get an EXIT alert.
             Sell = at least 3 of 4 bearish.
  stock-1d   dip-buy entries in an uptrend: RSI(2) pullback, close near the day's low (IBS), VIX panic.
             Buy = any one fires, Strong Buy = two or more. No sell signals (none tested well on stocks).
  4h / 1h    no model showed an edge after costs, so these timeframes give no Buy/Sell of their own.
             They show charts, layers and the daily signal, for timing entries.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import models
from signals import ACTION_RANK, ModelResult

DEFAULT_SEGMENTS = {
    "crypto-1d": {"models": ["tsmom28", "sma_ensemble", "donchian_ensemble", "btc_trend_gate"],
                  "buy": 0.5, "strong": 1.0, "sell": -0.5, "exit_alerts": True,
                  "about": "Trend following (3 of 4 trend models must agree)"},
    "stock-1d": {"models": ["rsi2_pullback", "ibs_reversal", "vix_backwardation"],
                 "buy_count": 1, "strong_count": 2, "sell": None, "exit_alerts": False,
                 "about": "Dip-buy entries in an uptrend (RSI(2), close near low, VIX panic)"},
    "crypto-4h": {"models": [], "about": "No tested edge on 4h crypto bars: charts and timing only"},
    "crypto-1h": {"models": [], "about": "No tested edge on 1h crypto bars: charts and timing only"},
    "stock-4h": {"models": [], "about": "No tested edge on 4h stock bars: charts and timing only"},
    "stock-1h": {"models": [], "about": "No tested edge on 1h stock bars: charts and timing only"},
}


def segment_config(cfg: dict, seg: str) -> dict:
    return {**DEFAULT_SEGMENTS.get(seg, {"models": []}), **cfg.get("segments", {}).get(seg, {})}


def evaluate(df: pd.DataFrame, cfg: dict, asset: str, tf: str, ctx: dict) -> dict:
    seg = f"{asset}-{tf}"
    sc = segment_config(cfg, seg)
    overrides = cfg.get("model_params", {})
    results: dict[str, ModelResult] = {}
    for key in sc["models"]:
        m = models.MODELS[key]
        out = models.run(key, df, ctx, overrides)
        row = out.iloc[-1]
        results[key] = ModelResult(m.name, int(row["vote"]), round(float(row["strength"]), 2),
                                   m.describe(row, models.params(key, overrides)))
    votes = np.array([r.vote for r in results.values()]) if results else np.array([0])
    bull, bear = int((votes > 0).sum()), int((votes < 0).sum())
    mean = float(votes.mean()) if results else 0.0
    score = int(round(50 + 50 * mean))

    if not results:
        action = "Hold"
    elif "buy_count" in sc:                              # entry-signal segments (stocks)
        action = "Strong Buy" if bull >= sc["strong_count"] else "Buy" if bull >= sc["buy_count"] else "Hold"
    else:                                                # trend segments (crypto)
        if mean >= sc["strong"]:
            action = "Strong Buy"
        elif mean > sc["buy"]:
            action = "Buy"
        elif sc.get("sell") is not None and mean <= -sc["strong"]:
            action = "Strong Sell"
        elif sc.get("sell") is not None and mean < sc["sell"]:
            action = "Sell"
        else:
            action = "Hold"

    direction = int(np.sign(ACTION_RANK[action]))
    aligned = [r for r in results.values() if direction and r.vote == direction]
    reasons = [f"{r.name}: {r.reason}" for r in sorted(aligned, key=lambda r: -r.strength)[:3]]
    if not results:
        reasons = [sc.get("about", "No models for this timeframe")]
    elif not reasons:
        reasons = [f"{r.name}: {r.reason}" for r in results.values()][:3]
    return {"score": score, "action": action, "rank": ACTION_RANK[action], "bull": bull, "bear": bear,
            "reasons": reasons, "models": results, "segment": seg, "engine": "v2",
            "segment_about": sc.get("about", ""), "exit_alerts": bool(sc.get("exit_alerts"))}
