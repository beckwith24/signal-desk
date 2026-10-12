"""
Signal models and the ensemble decision.

Everything is written in plain pandas/numpy (no TA library) so the logic is transparent,
easy to tweak, and won't break when a third-party indicator package changes.

Every model returns a ModelResult:
    vote      +1 bullish, -1 bearish, 0 neutral
    strength  0..1, how convincing the reading is
    reason    one plain-English line
    extra     numbers the dashboard can display or chart

To add a model: write a function (df, params) -> ModelResult, add it to MODELS,
and give it a params block in config.yaml under `models:`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MIN_BARS = 60

# Higher |rank| = stronger. Sign = direction.
ACTION_RANK = {
    "Strong Sell": -3,
    "Sell": -2,
    "Watch ↓": -1,
    "Hold": 0,
    "Watch ↑": 1,
    "Buy": 2,
    "Strong Buy": 3,
}


# --------------------------------------------------------------------------- indicators
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].shift(1)
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1
    ).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder's Average True Range."""
    return true_range(df).ewm(alpha=1 / n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    out = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    return out.where(dn != 0, 100.0)


def macd(s: pd.Series, fast=12, slow=26, signal=9):
    line = ema(s, fast) - ema(s, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def stochastic(df: pd.DataFrame, k: int = 14, d: int = 3):
    ll = df["low"].rolling(k).min()
    hh = df["high"].rolling(k).max()
    pct_k = 100 * (df["close"] - ll) / (hh - ll).replace(0, np.nan)
    return pct_k, pct_k.rolling(d).mean()


def supertrend(df: pd.DataFrame, period: int = 10, mult: float = 3.0) -> pd.Series:
    """Returns direction series: +1 uptrend, -1 downtrend."""
    hl2 = ((df["high"] + df["low"]) / 2).values
    a = atr(df, period).values
    close = df["close"].values
    upper, lower = hl2 + mult * a, hl2 - mult * a
    fu, fl = upper.copy(), lower.copy()
    d = np.ones(len(df))
    for i in range(1, len(df)):
        fu[i] = upper[i] if (upper[i] < fu[i - 1] or close[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lower[i] if (lower[i] > fl[i - 1] or close[i - 1] < fl[i - 1]) else fl[i - 1]
        if d[i - 1] == 1:
            d[i] = -1 if close[i] < fl[i] else 1
        else:
            d[i] = 1 if close[i] > fu[i] else -1
    return pd.Series(d, index=df.index)


# --------------------------------------------------------------------------- models
@dataclass
class ModelResult:
    name: str
    vote: int
    strength: float
    reason: str
    extra: dict = field(default_factory=dict)

    @property
    def signed(self) -> float:
        return self.vote * self.strength


def trend_model(df: pd.DataFrame, p: dict) -> ModelResult:
    """Fast/slow EMA, price vs long MA, and Supertrend must all agree to vote."""
    c = df["close"]
    fast, slow = ema(c, p["fast_ema"]), ema(c, p["slow_ema"])
    long_ma = sma(c, p["long_ma"])
    st_dir = supertrend(df, p["supertrend_period"], p["supertrend_mult"])
    a = atr(df, 14).iat[-1]

    points, parts = [], []
    up = fast.iat[-1] > slow.iat[-1]
    points.append(1 if up else -1)
    cross = np.sign(fast - slow)
    fresh = (cross.iloc[-4:-1] != cross.iat[-1]).any()
    parts.append(f"EMA{p['fast_ema']} {'above' if up else 'below'} EMA{p['slow_ema']}"
                 + (" (fresh cross)" if fresh else ""))

    if not np.isnan(long_ma.iat[-1]):
        above = c.iat[-1] > long_ma.iat[-1]
        points.append(1 if above else -1)
        parts.append(f"price {'above' if above else 'below'} {p['long_ma']}-MA")

    points.append(int(st_dir.iat[-1]))
    parts.append(f"Supertrend {'up' if st_dir.iat[-1] > 0 else 'down'}")

    # Unanimous = full-strength vote; 2-of-3 majority = weaker vote (Supertrend often flips on
    # a sharp dip inside a healthy uptrend, and we don't want that to silence the trend model).
    total = sum(points)
    vote = int(np.sign(total))
    unanimous = abs(total) == len(points)
    sep = abs(fast.iat[-1] - slow.iat[-1]) / a if a else 0
    strength = min(1.0, 0.5 + 0.25 * sep) if unanimous else (0.4 if vote else 0.0)
    label = {1: "Uptrend", -1: "Downtrend", 0: "Mixed trend"}[vote]
    if vote and not unanimous:
        label = "Leaning " + label.lower()
    return ModelResult("Trend", vote, round(strength, 2), f"{label}: " + ", ".join(parts),
                       {"fast": fast, "slow": slow, "long_ma": long_ma})


def mean_reversion_model(df: pd.DataFrame, p: dict) -> ModelResult:
    """Z-score of price vs rolling mean (equivalent to Bollinger Band position)."""
    c, lb, thr = df["close"], p["lookback"], p["sd_threshold"]
    m, sd = sma(c, lb), c.rolling(lb).std()
    z = ((c - m) / sd).iat[-1]
    extra = {"z": round(float(z), 2), "bb_mid": m, "bb_upper": m + thr * sd, "bb_lower": m - thr * sd}
    if z <= -thr:
        return ModelResult("Mean reversion", 1, round(min(1.0, abs(z) / (thr * 1.5)), 2),
                           f"Oversold: price {abs(z):.1f}σ below its {lb}-bar mean", extra)
    if z >= thr:
        return ModelResult("Mean reversion", -1, round(min(1.0, abs(z) / (thr * 1.5)), 2),
                           f"Overbought: price {z:.1f}σ above its {lb}-bar mean", extra)
    return ModelResult("Mean reversion", 0, 0.0, f"Within bands (z = {z:+.1f})", extra)


def confluence_model(df: pd.DataFrame, p: dict) -> ModelResult:
    """Five sub-indicators each vote; their average becomes a 0-100 score."""
    c = df["close"]
    r = rsi(c, p["rsi_period"]).iat[-1]
    _, _, hist = macd(c)
    k, d = stochastic(df, p["stoch_k"], p["stoch_d"])
    a = atr(df, 14)
    mid = ema(c, 20)
    vol_avg = df["volume"].rolling(p["volume_lookback"]).mean().iat[-1]

    sub = {}
    sub["RSI"] = 1 if r < p["rsi_low"] else -1 if r > p["rsi_high"] else 0
    h0, h1 = hist.iat[-1], hist.iat[-2]
    crossed_up = (np.sign(hist.iloc[-4:-1]) < 0).any() and h0 > 0
    crossed_dn = (np.sign(hist.iloc[-4:-1]) > 0).any() and h0 < 0
    sub["MACD"] = 1 if (crossed_up or (h0 > 0 and h0 > h1)) else -1 if (crossed_dn or (h0 < 0 and h0 < h1)) else 0
    sub["Stoch"] = 1 if (k.iat[-1] < 20 and k.iat[-1] > d.iat[-1]) else -1 if (k.iat[-1] > 80 and k.iat[-1] < d.iat[-1]) else 0
    if vol_avg and df["volume"].iat[-1] > p["volume_spike"] * vol_avg:
        sub["Volume"] = 1 if c.iat[-1] > df["open"].iat[-1] else -1
    else:
        sub["Volume"] = 0
    upper_k, lower_k = mid.iat[-1] + 2 * a.iat[-1], mid.iat[-1] - 2 * a.iat[-1]
    sub["ATR band"] = 1 if c.iat[-1] < lower_k else -1 if c.iat[-1] > upper_k else 0

    score = 50 + 50 * sum(sub.values()) / len(sub)
    vote = 1 if score >= 65 else -1 if score <= 35 else 0
    ups = [n for n, v in sub.items() if v > 0]
    dns = [n for n, v in sub.items() if v < 0]
    desc = f"Score {score:.0f}/100 (RSI {r:.0f})"
    if ups:
        desc += f"; bullish: {', '.join(ups)}"
    if dns:
        desc += f"; bearish: {', '.join(dns)}"
    return ModelResult("Confluence", vote, round(abs(score - 50) / 50, 2), desc,
                       {"score": round(score), "rsi": round(float(r), 1), "votes": sub})


def atr_layer_model(df: pd.DataFrame, p: dict) -> ModelResult:
    """LILO-style layers: price distance from an anchor MA measured in ATR steps."""
    c = df["close"]
    anchor = sma(c, p["anchor_ma"])
    anchor_v = anchor.iat[-1] if not np.isnan(anchor.iat[-1]) else ema(c, p["anchor_ma"]).iat[-1]
    step = p["layer_step"] * atr(df, p["atr_period"]).iat[-1]
    dist = (c.iat[-1] - anchor_v) / step
    mx = p["max_layers"]
    layer = int(np.clip(np.trunc(dist), -mx, mx))
    levels = {k: anchor_v + k * step for k in range(-mx, mx + 1)}
    extra = {"layer": layer, "distance": round(float(dist), 2), "levels": levels, "anchor": anchor}
    zone = p["zone_layer"]
    if dist <= -zone:
        return ModelResult("ATR layers", 1, round(min(1.0, abs(dist) / mx), 2),
                           f"Buy zone: layer {layer} ({abs(dist):.1f} ATR below the {p['anchor_ma']}-MA)", extra)
    if dist >= zone:
        return ModelResult("ATR layers", -1, round(min(1.0, abs(dist) / mx), 2),
                           f"Take-profit / reduce zone: layer +{layer} ({dist:.1f} ATR above the {p['anchor_ma']}-MA)", extra)
    return ModelResult("ATR layers", 0, 0.0, f"Mid-range: layer {layer:+d} ({dist:+.1f} ATR from anchor)", extra)


def momentum_model(df: pd.DataFrame, p: dict) -> ModelResult:
    """Market structure (higher highs/lows) plus rate of change; flags breakouts."""
    c, n = df["close"], p["swing_lookback"]
    h, l = df["high"], df["low"]
    rec_hh, prev_hh = h.iloc[-n:].max(), h.iloc[-2 * n:-n].max()
    rec_ll, prev_ll = l.iloc[-n:].min(), l.iloc[-2 * n:-n].min()
    up = rec_hh > prev_hh and rec_ll > prev_ll
    down = rec_hh < prev_hh and rec_ll < prev_ll
    roc = c.iat[-1] / c.iat[-1 - p["roc_period"]] - 1
    breakout = c.iat[-1] > h.iloc[-2 * n - 1:-1].max()
    breakdown = c.iat[-1] < l.iloc[-2 * n - 1:-1].min()
    strength = round(min(1.0, abs(roc) / p["roc_full_strength"]), 2)
    extra = {"roc": round(float(roc) * 100, 1)}
    if (up and roc > 0) or (breakout and roc > 0):
        tag = "breakout to new swing high" if breakout else "higher highs & higher lows"
        return ModelResult("Momentum", 1, max(strength, 0.3), f"Bullish momentum: {tag}, ROC {roc:+.1%}", extra)
    if (down and roc < 0) or (breakdown and roc < 0):
        tag = "breakdown to new swing low" if breakdown else "lower highs & lower lows"
        return ModelResult("Momentum", -1, max(strength, 0.3), f"Bearish momentum: {tag}, ROC {roc:+.1%}", extra)
    return ModelResult("Momentum", 0, 0.0, f"No clear structure, ROC {roc:+.1%}", extra)


MODELS = {
    "trend": trend_model,
    "mean_reversion": mean_reversion_model,
    "confluence": confluence_model,
    "atr_layers": atr_layer_model,
    "momentum": momentum_model,
}


# --------------------------------------------------------------------------- ensemble
def ensemble(results: dict[str, ModelResult], e: dict) -> dict:
    rs = list(results.values())
    signed = sum(r.signed for r in rs) / len(rs)
    score = int(round(50 + 50 * signed))  # 50 = neutral, 100 = max bullish, 0 = max bearish
    bull = sum(r.vote > 0 for r in rs)
    bear = sum(r.vote < 0 for r in rs)
    k = e["min_agree"]
    caveats = []

    if bull > bear:
        if bull >= k and score >= e["strong_score"]:
            action = "Strong Buy"
        elif bull >= k:
            action = "Buy"
        elif bull >= k - 1 or score >= e["watch_score"]:
            action = "Watch ↑"
        else:
            action = "Hold"
    elif bear > bull:
        if bear >= k and (100 - score) >= e["strong_score"]:
            action = "Strong Sell"
        elif bear >= k:
            action = "Sell"
        elif bear >= k - 1 or (100 - score) >= e["watch_score"]:
            action = "Watch ↓"
        else:
            action = "Hold"
    else:
        action = "Hold"

    # Don't buy an oversold dip while the trend and momentum are both still falling (and vice versa).
    if e.get("knife_guard", True):
        t, m = results["trend"].vote, results["momentum"].vote
        if action in ("Buy", "Strong Buy") and t < 0 and m < 0:
            action = "Watch ↑"
            caveats.append("Falling-knife guard: trend and momentum still down, downgraded to Watch")
        elif action in ("Sell", "Strong Sell") and t > 0 and m > 0:
            action = "Watch ↓"
            caveats.append("Strong-uptrend guard: trend and momentum still up, downgraded to Watch")

    direction = int(np.sign(ACTION_RANK[action])) or int(np.sign(bull - bear))
    aligned = sorted([r for r in rs if r.vote != 0 and r.vote == direction], key=lambda r: -r.strength)
    reasons = [f"{r.name}: {r.reason}" for r in aligned[:3]] + caveats
    if not reasons:
        reasons = ["No model has a strong reading right now"]
    return {"score": score, "action": action, "rank": ACTION_RANK[action],
            "bull": bull, "bear": bear, "reasons": reasons}


def evaluate(df: pd.DataFrame, cfg: dict) -> dict:
    if len(df) < MIN_BARS:
        raise ValueError(f"only {len(df)} bars of data (need {MIN_BARS})")
    results = {name: fn(df, cfg["models"][name]) for name, fn in MODELS.items()}
    return {**ensemble(results, cfg["ensemble"]), "models": results}


def volume_note(df: pd.DataFrame, lookback: int = 50) -> str | None:
    """Crypto extra: flag extreme volume (z-score of log volume)."""
    v = np.log(df["volume"].replace(0, np.nan)).dropna()
    if len(v) < lookback:
        return None
    z = (v.iat[-1] - v.iloc[-lookback:].mean()) / v.iloc[-lookback:].std()
    if z >= 2.5:
        return f"Extreme volume on the latest bar ({z:.1f}σ above normal)"
    return None
