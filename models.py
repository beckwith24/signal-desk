"""
Model library (v2).

Every model is computed for the WHOLE price history at once and only ever looks backwards
(rolling windows, shifts, and forward-only state machines), so the same code serves the live scan
(take the last row) and the backtest (use every row) with no look-ahead.

Each model function:  fn(df, ctx, p) -> DataFrame indexed like df with at least
    vote      +1 bullish / -1 bearish / 0 neutral
    strength  0..1
and a describe(row, p) -> str giving the plain-English reason for the latest bar.

ctx holds outside data already aligned to df's index without look-ahead (see context.py):
    spy_close, spy_sma200, vix, vix3m, btc_close, btc_sma50

Families and where they come from (see README / research notes):
  stock pullback   rsi2_pullback (Connors), ibs_reversal (Pagonidis), turn_of_month (McConnell & Xu)
  regime / risk    market_regime (Faber 10-month/200-day), vix_backwardation (Fassas & Hourvouliades)
  trend (crypto)   tsmom28 (Han, Kang & Ryu), sma_ensemble (Detzel et al.),
                   donchian_ensemble (Zarattini, Pagani & Barbon), btc_trend_gate
  holding / exit   high_breakout_trail (Zarattini, Pagani & Wilcox: new highs + ATR trailing stop)
  original five    trend_classic, meanrev_z, confluence, atr_layers, momentum_classic
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from signals import atr, ema, macd, rsi, sma, stochastic, supertrend


@dataclass
class Model:
    key: str
    name: str
    family: str
    fn: Callable
    describe: Callable
    defaults: dict


def _frame(df, vote, strength, **extra) -> pd.DataFrame:
    out = pd.DataFrame({"vote": pd.Series(vote, index=df.index).fillna(0).astype(int),
                        "strength": pd.Series(strength, index=df.index).fillna(0).clip(0, 1)}, index=df.index)
    for k, v in extra.items():
        out[k] = v
    return out


def _hold(entry: np.ndarray, exit_: np.ndarray) -> np.ndarray:
    """Forward-only state machine: in position from an entry bar until (and including) an exit bar."""
    pos = np.zeros(len(entry), dtype=int)
    on = False
    for i in range(len(entry)):
        if not on and entry[i]:
            on = True
        elif on and exit_[i]:
            on = False
            pos[i] = 0
            continue
        pos[i] = 1 if on else 0
    return pos


# ============================================================================ stock pullbacks
def rsi2_pullback(df, ctx, p):
    c = df["close"]
    r = rsi(c, p["rsi_len"])
    trend_ma = sma(c, p["trend_ma"])
    exit_ma = sma(c, p["exit_ma"])
    entry = ((r < p["entry"]) & (c > trend_ma)).values
    exit_ = (c > exit_ma).values
    pos = _hold(entry, exit_)
    strength = np.where(entry, np.clip((p["entry"] - r) / p["entry"], 0.4, 1), 0.5)
    return _frame(df, pos, np.where(pos > 0, strength, 0), rsi2=r, trend_ma=trend_ma, exit_ma=exit_ma)


def rsi2_describe(row, p):
    if row.vote > 0:
        return (f"Pullback in an uptrend: RSI(2) {row.rsi2:.0f} (buy below {p['entry']}), price above the "
                f"{p['trend_ma']}-day average; hold until a close above the {p['exit_ma']}-day average")
    return f"No pullback setup (RSI(2) {row.rsi2:.0f})"


def ibs_reversal(df, ctx, p):
    c = df["close"]
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    ibs = (c - df["low"]) / rng
    up = c > sma(c, p["trend_ma"])
    vote = np.where((ibs < p["low"]) & up, 1, 0)
    return _frame(df, vote, np.where(vote > 0, np.clip((p["low"] - ibs) / p["low"] + 0.5, 0.5, 1), 0), ibs=ibs)


def ibs_describe(row, p):
    if row.vote > 0:
        return f"Closed near the bar's low (IBS {row.ibs:.2f}) in an uptrend: short-term bounce setup"
    return f"Close position in bar's range (IBS) {row.ibs:.2f}"


def turn_of_month(df, ctx, p):
    idx = df.index.tz_convert("America/New_York") if df.index.tz is not None else df.index
    dates = pd.Series(idx.normalize(), index=df.index)
    # trading-day number within the month, counting only dates seen so far (causal)
    uniq = pd.Series(dates.unique())
    month = uniq.dt.to_period("M")
    day_no = uniq.groupby(month).cumcount() + 1
    # last trading day of the month: the next business day falls in a new month
    nxt = uniq + pd.offsets.BDay(1)
    last = (nxt.dt.month != uniq.dt.month).values
    m_day = dict(zip(uniq, day_no))
    m_last = dict(zip(uniq, last))
    dn = dates.map(m_day)
    ls = dates.map(m_last)
    vote = np.where(ls | (dn <= p["first_days"]), 1, 0)
    return _frame(df, vote, np.where(vote > 0, 0.5, 0), day_no=dn)


def tom_describe(row, p):
    if row.vote > 0:
        return f"Turn-of-month window (last trading day to trading day {p['first_days']}): historically strong days"
    return "Outside the turn-of-month window"


# ============================================================================ regime / risk
def market_regime(df, ctx, p):
    if "spy_close" not in ctx:
        return _frame(df, 0, 0)
    on = ctx["spy_close"] > ctx["spy_sma200"]
    vote = np.where(ctx["spy_sma200"].isna(), 0, np.where(on, 1, -1))
    dist = (ctx["spy_close"] / ctx["spy_sma200"] - 1)
    return _frame(df, vote, np.clip(dist.abs() * 10, 0.3, 1), spy_dist=dist)


def regime_describe(row, p):
    if row.vote > 0:
        return f"Market regime risk-on: SPY {row.spy_dist:+.1%} vs its 200-day average"
    if row.vote < 0:
        return f"Market regime risk-off: SPY {row.spy_dist:+.1%} below its 200-day average"
    return "Market regime unknown"


def vix_backwardation(df, ctx, p):
    if "vix" not in ctx or "vix3m" not in ctx:
        return _frame(df, 0, 0)
    ratio = ctx["vix"] / ctx["vix3m"]
    vote = np.where(ratio > p["threshold"], 1, 0)
    return _frame(df, vote, np.where(vote > 0, np.clip((ratio - 1) * 5 + 0.5, 0.5, 1), 0), vix_ratio=ratio)


def vix_describe(row, p):
    if row.vote > 0:
        return f"Panic reading: VIX above 3-month VIX (ratio {row.vix_ratio:.2f}); historically followed by rebounds"
    return f"VIX term structure normal (ratio {row.vix_ratio:.2f})" if row.vix_ratio == row.vix_ratio else "No VIX data"


# ============================================================================ trend (crypto evidence)
def tsmom28(df, ctx, p):
    c = df["close"]
    r = c / c.shift(p["lookback"]) - 1
    vote = np.where(r.isna(), 0, np.where(r > 0, 1, -1))
    return _frame(df, vote, np.clip(r.abs() / p["full"], 0.2, 1), roc=r)


def tsmom_describe(row, p):
    return f"{p['lookback']}-bar momentum {row.roc:+.1%} ({'positive' if row.vote > 0 else 'negative'})"


def sma_ensemble(df, ctx, p):
    c = df["close"]
    parts = [(c > sma(c, n)).astype(float).where(sma(c, n).notna()) for n in p["lengths"]]
    frac = pd.concat(parts, axis=1).mean(axis=1)
    vote = np.where(frac.isna(), 0, np.where(frac >= p["bull"], 1, np.where(frac <= p["bear"], -1, 0)))
    return _frame(df, vote, frac.fillna(0).where(vote >= 0, 1 - frac.fillna(0)), frac=frac)


def sma_ens_describe(row, p):
    k = int(round(row.frac * len(p["lengths"]))) if row.frac == row.frac else 0
    return f"Price above {k} of {len(p['lengths'])} moving averages ({'/'.join(map(str, p['lengths']))})"


def donchian_ensemble(df, ctx, p):
    c = df["close"].values
    n = len(c)
    pos_all = []
    cs = df["close"]
    for N in p["lookbacks"]:
        prior_high = cs.shift(1).rolling(N, min_periods=N).max().values
        hi = cs.rolling(N, min_periods=N).max().values
        lo = cs.rolling(N, min_periods=N).min().values
        pos = np.zeros(n, dtype=int)
        on, stop = False, -np.inf
        for i in range(n):
            if np.isnan(prior_high[i]):
                continue
            mid = (hi[i] + lo[i]) / 2
            if not on and c[i] > prior_high[i]:
                on, stop = True, mid
            elif on:
                stop = max(stop, mid)
                if c[i] < stop:
                    on = False
            pos[i] = 1 if on else 0
        pos_all.append(pos)
    frac = pd.Series(np.mean(pos_all, axis=0), index=df.index)
    vote = np.where(frac >= p["bull"], 1, np.where(frac <= p["bear"], -1, 0))
    return _frame(df, vote, frac.where(vote >= 0, 1 - frac), frac=frac)


def donchian_describe(row, p):
    k = int(round(row.frac * len(p["lookbacks"])))
    return f"Breakout systems long: {k} of {len(p['lookbacks'])} lookbacks (5–360 bars) are in an uptrend"


def btc_trend_gate(df, ctx, p):
    if "btc_close" not in ctx:
        return _frame(df, 0, 0)
    up = ctx["btc_close"] > ctx["btc_sma"]
    vote = np.where(ctx["btc_sma"].isna(), 0, np.where(up, 1, -1))
    dist = ctx["btc_close"] / ctx["btc_sma"] - 1
    return _frame(df, vote, np.clip(dist.abs() * 5, 0.3, 1), btc_dist=dist)


def btc_gate_describe(row, p):
    return f"Bitcoin {'above' if row.vote > 0 else 'below'} its {p['sma']}-day average ({row.btc_dist:+.1%}); alts usually follow"


# ============================================================================ holding / exit
def high_breakout_trail(df, ctx, p):
    c = df["close"].values
    hh = df["close"].shift(1).rolling(p["lookback"], min_periods=p["lookback"]).max().values
    a = atr(df, p["atr_len"]).values
    n = len(c)
    vote = np.zeros(n, dtype=int)
    stop_arr = np.full(n, np.nan)
    on, peak = False, 0.0
    for i in range(n):
        if np.isnan(hh[i]):
            continue
        if not on and c[i] >= hh[i]:
            on, peak = True, c[i]
        if on:
            peak = max(peak, c[i])
            stop = peak - p["mult"] * a[i]
            stop_arr[i] = stop
            if c[i] < stop:
                on = False
                vote[i] = -1          # exit signal on the bar the trailing stop breaks
                continue
            vote[i] = 1
    return _frame(df, vote, np.where(vote != 0, 0.6, 0), trail_stop=stop_arr)


def hbt_describe(row, p):
    if row.vote > 0:
        return f"Riding a {p['lookback']}-bar-high breakout; trailing stop at {row.trail_stop:,.2f}"
    if row.vote < 0:
        return "Trailing stop broken after a breakout: exit signal"
    return f"No new {p['lookback']}-bar high breakout in force"


# ============================================================================ original five (vectorized)
def trend_classic(df, ctx, p):
    c = df["close"]
    fast, slow, long_ = ema(c, p["fast_ema"]), ema(c, p["slow_ema"]), sma(c, p["long_ma"])
    st = supertrend(df, p["supertrend_period"], p["supertrend_mult"])
    a = np.sign(fast - slow)
    b = np.sign(c - long_).where(long_.notna(), 0)
    total = a + b + st
    npts = 2 + long_.notna().astype(int)
    vote = np.sign(total).astype(int)
    unanimous = total.abs() == npts
    sep = ((fast - slow).abs() / atr(df, 14)).fillna(0)
    strength = np.where(unanimous, np.minimum(1, 0.5 + 0.25 * sep), np.where(vote != 0, 0.4, 0))
    return _frame(df, vote, strength, ema_fast=fast, ema_slow=slow, ma_long=long_)


def trend_describe(row, p):
    return {1: "Uptrend", -1: "Downtrend", 0: "Mixed trend"}[int(row.vote)] + \
        f" (EMA{p['fast_ema']}/{p['slow_ema']}, {p['long_ma']}-MA, Supertrend)"


def meanrev_z(df, ctx, p):
    c = df["close"]
    m, sd = sma(c, p["lookback"]), c.rolling(p["lookback"]).std()
    z = (c - m) / sd
    vote = np.where(z <= -p["sd_threshold"], 1, np.where(z >= p["sd_threshold"], -1, 0))
    return _frame(df, vote, np.clip(z.abs() / (p["sd_threshold"] * 1.5), 0, 1), z=z)


def meanrev_describe(row, p):
    if row.vote > 0:
        return f"Oversold: {abs(row.z):.1f}σ below the {p['lookback']}-bar mean"
    if row.vote < 0:
        return f"Overbought: {row.z:.1f}σ above the {p['lookback']}-bar mean"
    return f"Within bands (z {row.z:+.1f})"


def confluence(df, ctx, p):
    c = df["close"]
    r = rsi(c, p["rsi_period"])
    _, _, h = macd(c)
    k, d = stochastic(df, p["stoch_k"], p["stoch_d"])
    a = atr(df, 14)
    mid = ema(c, 20)
    vavg = df["volume"].rolling(p["volume_lookback"]).mean()
    s_rsi = np.where(r < p["rsi_low"], 1, np.where(r > p["rsi_high"], -1, 0))
    was_neg = (h.shift(1) < 0) | (h.shift(2) < 0) | (h.shift(3) < 0)
    was_pos = (h.shift(1) > 0) | (h.shift(2) > 0) | (h.shift(3) > 0)
    s_macd = np.where(((h > 0) & was_neg) | ((h > 0) & (h > h.shift(1))), 1,
                      np.where(((h < 0) & was_pos) | ((h < 0) & (h < h.shift(1))), -1, 0))
    s_sto = np.where((k < 20) & (k > d), 1, np.where((k > 80) & (k < d), -1, 0))
    spike = df["volume"] > p["volume_spike"] * vavg
    s_vol = np.where(spike, np.sign(c - df["open"]), 0)
    s_band = np.where(c < mid - 2 * a, 1, np.where(c > mid + 2 * a, -1, 0))
    score = 50 + 50 * (s_rsi + s_macd + s_sto + s_vol + s_band) / 5
    vote = np.where(score >= 65, 1, np.where(score <= 35, -1, 0))
    return _frame(df, vote, np.abs(score - 50) / 50, score=score, rsi=r)


def confluence_describe(row, p):
    return f"Indicator score {row.score:.0f}/100 (RSI {row.rsi:.0f})"


def atr_layers(df, ctx, p):
    c = df["close"]
    anchor = sma(c, p["anchor_ma"])
    step = p["layer_step"] * atr(df, p["atr_period"])
    dist = (c - anchor) / step
    vote = np.where(dist <= -p["zone_layer"], 1, np.where(dist >= p["zone_layer"], -1, 0))
    return _frame(df, vote, np.clip(dist.abs() / p["max_layers"], 0, 1), distance=dist)


def layers_describe(row, p):
    if row.vote > 0:
        return f"Buy zone: {abs(row.distance):.1f} ATR below the {p['anchor_ma']}-bar average"
    if row.vote < 0:
        return f"Take-profit zone: {row.distance:.1f} ATR above the {p['anchor_ma']}-bar average"
    return f"Mid-range: {row.distance:+.1f} ATR from the {p['anchor_ma']}-bar average"


def momentum_classic(df, ctx, p):
    c, h, l, n = df["close"], df["high"], df["low"], p["swing_lookback"]
    rec_hh, prev_hh = h.rolling(n).max(), h.shift(n).rolling(n).max()
    rec_ll, prev_ll = l.rolling(n).min(), l.shift(n).rolling(n).min()
    up = (rec_hh > prev_hh) & (rec_ll > prev_ll)
    down = (rec_hh < prev_hh) & (rec_ll < prev_ll)
    roc = c / c.shift(p["roc_period"]) - 1
    brk = c > h.shift(1).rolling(2 * n).max()
    bdn = c < l.shift(1).rolling(2 * n).min()
    vote = np.where((up | brk) & (roc > 0), 1, np.where((down | bdn) & (roc < 0), -1, 0))
    return _frame(df, vote, np.where(vote != 0, np.maximum(0.3, np.clip(roc.abs() / p["roc_full_strength"], 0, 1)), 0), roc=roc)


def momentum_describe(row, p):
    tag = {1: "Bullish structure", -1: "Bearish structure", 0: "No clear structure"}[int(row.vote)]
    return f"{tag}, {p['roc_period']}-bar change {row.roc:+.1%}"


# ============================================================================ registry
MODELS: dict[str, Model] = {m.key: m for m in [
    Model("rsi2_pullback", "RSI(2) pullback", "pullback", rsi2_pullback, rsi2_describe,
          {"rsi_len": 2, "entry": 10, "trend_ma": 200, "exit_ma": 5}),
    Model("ibs_reversal", "Close near low (IBS)", "pullback", ibs_reversal, ibs_describe,
          {"low": 0.2, "trend_ma": 200}),
    Model("turn_of_month", "Turn of month", "calendar", turn_of_month, tom_describe, {"first_days": 3}),
    Model("market_regime", "Market regime (SPY)", "regime", market_regime, regime_describe, {}),
    Model("vix_backwardation", "VIX panic", "regime", vix_backwardation, vix_describe, {"threshold": 1.0}),
    Model("tsmom28", "28-bar momentum", "trend", tsmom28, tsmom_describe, {"lookback": 28, "full": 0.3}),
    Model("sma_ensemble", "Above 20/50/100 MAs", "trend", sma_ensemble, sma_ens_describe,
          {"lengths": [20, 50, 100], "bull": 0.66, "bear": 0.0}),
    Model("donchian_ensemble", "Breakout ensemble", "trend", donchian_ensemble, donchian_describe,
          {"lookbacks": [5, 10, 20, 30, 60, 90, 150, 250, 360], "bull": 0.5, "bear": 0.0}),
    Model("btc_trend_gate", "Bitcoin trend", "trend", btc_trend_gate, btc_gate_describe, {"sma": 50}),
    Model("high_breakout_trail", "New-high breakout + trailing stop", "trend", high_breakout_trail, hbt_describe,
          {"lookback": 252, "atr_len": 42, "mult": 3.0}),
    Model("trend_classic", "Trend (EMA/MA/Supertrend)", "original", trend_classic, trend_describe,
          {"fast_ema": 21, "slow_ema": 55, "long_ma": 200, "supertrend_period": 10, "supertrend_mult": 3.0}),
    Model("meanrev_z", "Mean reversion (2σ)", "original", meanrev_z, meanrev_describe,
          {"lookback": 20, "sd_threshold": 2.0}),
    Model("confluence", "Indicator confluence", "original", confluence, confluence_describe,
          {"rsi_period": 14, "rsi_low": 35, "rsi_high": 65, "stoch_k": 14, "stoch_d": 3,
           "volume_lookback": 20, "volume_spike": 1.5}),
    Model("atr_layers", "ATR layers", "original", atr_layers, layers_describe,
          {"atr_period": 14, "anchor_ma": 50, "layer_step": 1.0, "max_layers": 4, "zone_layer": 2}),
    Model("momentum_classic", "Momentum (structure)", "original", momentum_classic, momentum_describe,
          {"roc_period": 20, "swing_lookback": 10, "roc_full_strength": 0.20}),
]}


def params(key: str, overrides: dict | None = None) -> dict:
    return {**MODELS[key].defaults, **((overrides or {}).get(key, {}))}


def run(key: str, df: pd.DataFrame, ctx: dict, overrides: dict | None = None) -> pd.DataFrame:
    return MODELS[key].fn(df, ctx, params(key, overrides))
