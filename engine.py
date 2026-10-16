"""
Signal engine v2: each segment (stocks / crypto × daily / 4h / 1h) has its own model set, chosen
from published research and checked in our own walk-forward test (research/summary.md).

  crypto-1d  trend: 28-day momentum, price above 20/50/100-day MAs, breakout ensemble, Bitcoin trend
             Buy = 3 of 4 bullish with none bearish (average vote above 0.5); all 4 = Strong Buy.
             When that ends you get an EXIT alert.
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
    "crypto-1d": {"models": ["tsmom28", "sma_ensemble", "donchian_ensemble", "btc_trend_gate"], "gate": "btc_weekly_gate",
                  "buy": 0.5, "strong": 1.0, "sell": -0.5, "exit_alerts": True,
                  "about": "Trend following: Buy when 3 of 4 trend models are bullish and none bearish; Strong Buy needs all 4 "
                           "plus Bitcoin's weekly trend up"},
    "stock-1d": {"models": ["rsi2_pullback", "ibs_reversal", "vix_backwardation"], "panic": "panic_dip",
                 "buy_count": 1, "strong_count": 2, "sell": None, "exit_alerts": False,
                 "take_profit": {"ma": 5, "max_days": 20}, "overbought_sell": True,
                 "about": "Dip-buy entries in an uptrend (RSI(2), close near low, VIX panic); Panic Buy = a deep dip during a VIX spike; Sell = the tested exit (close above the 5-day average) or a short-term overbought top"},
    "crypto-4h": {"models": [], "about": "No tested edge on 4h crypto bars: charts and timing only"},
    "crypto-1h": {"models": [], "about": "No tested edge on 1h crypto bars: charts and timing only"},
    "stock-4h": {"models": [], "about": "No tested edge on 4h stock bars: charts and timing only"},
    "stock-1h": {"models": [], "about": "No tested edge on 1h stock bars: charts and timing only"},
    "stock-2h": {"models": [], "about": "2-hour chart for the Confluence (rebuilt) view: charts and timing only"},
    "crypto-2h": {"models": [], "about": "2-hour chart for the Confluence (rebuilt) view: charts and timing only"},
    "stock-1wk": {"models": [], "about": "Weekly: the long-term trend. Shown as information, no buy/sell signals"},
    "crypto-1wk": {"models": [], "about": "Weekly: the long-term trend. Shown as information, no buy/sell signals"},
}


def segment_config(cfg: dict, seg: str) -> dict:
    return {**DEFAULT_SEGMENTS.get(seg, {"models": []}), **cfg.get("segments", {}).get(seg, {})}


def evaluate(df: pd.DataFrame, cfg: dict, asset: str, tf: str, ctx: dict) -> dict:
    seg = f"{asset}-{tf}"
    sc = segment_config(cfg, seg)
    overrides = cfg.get("model_params", {})
    results: dict[str, ModelResult] = {}
    series: dict[str, pd.DataFrame] = {}
    extra = [k for k in (sc.get("gate"), sc.get("panic")) if k]       # shown with the models, not part of the vote count
    for key in sc["models"] + extra:
        m = models.MODELS[key]
        out = models.run(key, df, ctx, overrides)
        series[key] = out
        row = out.iloc[-1]
        results[key] = ModelResult(m.name, int(row["vote"]), round(float(row["strength"]), 2),
                                   m.describe(row, models.params(key, overrides)))
    core = {k: r for k, r in results.items() if k in sc["models"]}
    votes = np.array([r.vote for r in core.values()]) if core else np.array([0])
    bull, bear = int((votes > 0).sum()), int((votes < 0).sum())
    mean = float(votes.mean()) if results else 0.0
    score = int(round(50 + 50 * mean))

    if not results:
        action = "Hold"
    elif "buy_count" in sc:                              # entry-signal segments (stocks)
        action = "Strong Buy" if bull >= sc["strong_count"] else "Buy" if bull >= sc["buy_count"] else "Hold"
        if sc.get("panic") and results[sc["panic"]].vote > 0:
            action = "Panic Buy"
    else:                                                # trend segments (crypto)
        gate_ok = not sc.get("gate") or results[sc["gate"]].vote > 0
        if mean >= sc["strong"] and gate_ok:
            action = "Strong Buy"
        elif mean >= sc["strong"]:
            action = "Buy"
        elif mean > sc["buy"]:
            action = "Buy"
        elif sc.get("sell") is not None and mean <= -sc["strong"]:
            action = "Strong Sell"
        elif sc.get("sell") is not None and mean < sc["sell"]:
            action = "Sell"
        else:
            action = "Hold"

    trade = None
    if results and sc.get("take_profit") and "buy_count" in sc:
        trade = replay_trade(df, series, sc)
        if trade and trade.get("exit_now") and ACTION_RANK[action] < 3:
            action = "Sell"
    hot = None
    if results and sc.get("overbought_sell") and action == "Hold":
        hot = overbought(df)
        if hot:
            action = "Sell"

    direction = int(np.sign(ACTION_RANK[action]))
    aligned = [r for r in results.values() if direction and r.vote == direction]
    reasons = [f"{r.name}: {r.reason}" for r in sorted(aligned, key=lambda r: -r.strength)[:3]]
    if not results:
        reasons = [sc.get("about", "No models for this timeframe")]
    elif not reasons:
        reasons = [f"{r.name}: {r.reason}" for r in results.values()][:3]
    if hot:
        reasons = [hot]
    if trade:
        if trade.get("exit_now") and action == "Sell":
            reasons = [trade["text"]]
        else:
            reasons = reasons + [trade["text"]]
    return {"trade": trade, "exit_trade": bool(trade and trade.get("exit_now") and action == "Sell"),
            "score": score, "action": action, "rank": ACTION_RANK[action], "bull": bull, "bear": bear,
            "reasons": reasons, "models": results, "segment": seg, "engine": "v2",
            "segment_about": sc.get("about", ""), "exit_alerts": bool(sc.get("exit_alerts"))}


def replay_trade(df: pd.DataFrame, series: dict, sc: dict, lookback: int = 80) -> dict | None:
    """The tested stock trade: in at the close of a Strong Buy / Panic Buy day, out at the first close above the
    5-day average (or after max_days). Replayed over recent bars, so the app needs no memory of past alerts.
    Returns the open trade (exit_now=True if today's close is the exit), or None."""
    tp = sc["take_profit"]
    votes = pd.DataFrame({k: series[k]["vote"] for k in sc["models"]})
    strong = (votes > 0).sum(axis=1) >= sc["strong_count"]
    panic = series[sc["panic"]]["vote"] > 0 if sc.get("panic") else pd.Series(False, index=df.index)
    c = df["close"]; ma = c.rolling(tp["ma"]).mean()
    n = len(df); start = max(0, n - lookback)
    entry = None
    for i in range(start, n):
        if entry is not None:
            held = i - entry
            if c.iat[i] > ma.iat[i] or held >= tp["max_days"]:
                if i == n - 1:
                    break                       # exit is today: report it below
                entry = None
        if entry is None and (strong.iat[i] or panic.iat[i]):
            entry = i
    if entry is None or entry == n - 1:
        return None
    px, last, held = float(c.iat[entry]), float(c.iat[-1]), n - 1 - entry
    kind = "Panic Buy" if panic.iat[entry] else "Strong Buy"
    when = df.index[entry].strftime("%b %-d")
    ret = (last / px - 1) * 100
    exit_now = bool(c.iat[-1] > ma.iat[-1] or held >= tp["max_days"])
    if exit_now:
        why = (f"closed above its {tp['ma']}-day average ({ma.iat[-1]:,.2f})" if c.iat[-1] > ma.iat[-1]
               else f"{held} trading days since the entry (time limit)")
        text = f"Take profit / exit: {why} after the {kind} on {when} at {px:,.2f} ({ret:+.1f}%)"
    else:
        text = (f"In the {kind} trade from {when} at {px:,.2f} ({ret:+.1f}%): sell on a close above the "
                f"{tp['ma']}-day average (now {ma.iat[-1]:,.2f}) or after {tp['max_days']} days ({held} so far)")
    return {"kind": kind, "since": df.index[entry].strftime("%Y-%m-%d"), "entry": px, "ret_pct": round(ret, 2),
            "days": held, "exit_now": exit_now, "text": text}


def overbought(df: pd.DataFrame) -> str | None:
    """Stock short-term top: RSI(2) above 90 and a close in the top 10% of the day's range.
    The only no-position sell rule that held up after 2021 (research/sell.md): the next 5 days ran about 0.2% below
    the stock's normal. A 'trim / don't chase' signal, not a crash warning."""
    c, h, l = df["close"], df["high"], df["low"]
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    r2 = float((100 - 100 / (1 + up / dn.replace(0, np.nan))).iat[-1]) if dn.iat[-1] > 0 else 100.0
    rng = float(h.iat[-1] - l.iat[-1])
    ibs = float((c.iat[-1] - l.iat[-1]) / rng) if rng > 0 else 0.5
    if r2 > 90 and ibs > 0.9:
        return (f"Short-term overbought: RSI(2) {r2:.0f} and closed at the top of the day's range ({ibs * 100:.0f}%). "
                "Tested since 2021: the next 5 days ran about 0.2% below normal, so it's a 'trim or don't chase' "
                "signal, not a crash warning")
    return None
