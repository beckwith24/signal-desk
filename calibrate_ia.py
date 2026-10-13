"""
Reverse-engineer the InvestAnswers TradingView indicators from screenshots.

The screenshots were digitised into research/ia_targets/ (marker positions, level lines, the
Optimized-Trend ribbon edges). This script lines them up with real prices and searches families of
candidate formulas for the closest match:

  1. Levels (IA-ATR-Model "Level 3..6")  -> Fibonacci fractions of the running all-time high?
  2. Ribbon (IA-Optimized-Trend)         -> which moving averages, which lengths?
  3. Buy/sell triangles (IA-ATR-Model)   -> which rule reproduces their timing?

Runs on GitHub Actions (Actions tab -> "IA calibration"). Writes research/ia_calibration.md + .json.
`python calibrate_ia.py --synthetic` runs offline on random prices (only checks the plumbing).
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import logging
import time as _time
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("calibrate_ia")
ROOT = Path(__file__).parent
TARGETS = ROOT / "research" / "ia_targets"
OUT = ROOT / "research"
FIB = [0.236, 0.382, 0.5, 0.618, 0.764, 1.0]


# ----------------------------------------------------------------------------- data
def _norm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].astype(float)
    return df[~df.index.duplicated(keep="last")].sort_index().dropna(subset=["close"])


def yf_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    import yfinance as yf
    for attempt in range(3):
        try:
            df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
            if df is not None and not df.empty:
                return _norm(df)
        except Exception as e:  # network hiccup
            log.warning("%s %s attempt %d: %s", ticker, interval, attempt + 1, e)
        _time.sleep(3)
    raise RuntimeError(f"no data for {ticker} {interval}")


def session_4h(h: pd.DataFrame) -> pd.DataFrame:
    """TradingView-style 4h bars for US stocks: 09:30-13:30 and 13:30-16:00 New York time."""
    h = h.tz_convert("America/New_York")
    t = h.index.time
    h = h[(t >= time(9, 30)) & (t < time(16, 0))]
    first = h.index.time < time(13, 30)
    start = h.index.normalize() + pd.to_timedelta(np.where(first, 9.5, 13.5), unit="h")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return h.groupby(start).agg(agg).dropna(subset=["close"])


def synthetic(start: str, end: str, freq: str, p0: float, seed: int, vol: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, end, freq=freq, tz="UTC")
    if freq == "B":
        idx = idx[idx.dayofweek < 5]
    c = p0 * np.exp(np.cumsum(rng.normal(0, vol, len(idx))))
    o = np.r_[c[0], c[:-1]]
    hi = np.maximum(o, c) * (1 + np.abs(rng.normal(0, vol / 2, len(idx))))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, vol / 2, len(idx))))
    return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c, "volume": 1e6}, index=idx)


def load_data(offline: bool) -> dict:
    if offline:
        h = synthetic("2026-05-14 13:30", "2026-10-13 20:00", "1h", 250, 1, 0.012)
        h = h[(h.index.dayofweek < 5)]
        return {"CBRS": session_4h(h),
                "BTC-USD": synthetic("2014-09-17", "2026-10-13", "D", 400, 2, 0.035),
                "000660.KS": synthetic("2024-10-01", "2026-10-13", "B", 200000, 3, 0.025),
                "005930.KS": synthetic("2024-10-01", "2026-10-13", "B", 60000, 4, 0.02)}
    return {"CBRS": session_4h(yf_history("CBRS", "729d", "1h")),
            "BTC-USD": yf_history("BTC-USD", "max", "1d"),
            "000660.KS": yf_history("000660.KS", "3y", "1d"),
            "005930.KS": yf_history("005930.KS", "3y", "1d")}


# ----------------------------------------------------------------------------- indicators
def sma(s, n): return s.rolling(n, min_periods=n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False, min_periods=n).mean()
def rma(s, n): return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def wma(s, n):
    w = np.arange(1, n + 1, dtype=float)
    return s.rolling(n, min_periods=n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def hma(s, n): return wma(2 * wma(s, max(n // 2, 1)) - wma(s, n), max(int(np.sqrt(n)), 1))
def dema(s, n): e = ema(s, n); return 2 * e - ema(e, n)
def tema(s, n): e1 = ema(s, n); e2 = ema(e1, n); return 3 * e1 - 3 * e2 + ema(e2, n)
def zlema(s, n): return ema(s + (s - s.shift((n - 1) // 2)), n)


def lsma(s, n):
    x = np.arange(n, dtype=float)
    def f(y):
        b, a = np.polyfit(x, y, 1)
        return a + b * (n - 1)
    return s.rolling(n, min_periods=n).apply(f, raw=True)


def alma(s, n, offset=0.85, sigma=6.0):
    m = offset * (n - 1); sd = n / sigma
    w = np.exp(-((np.arange(n) - m) ** 2) / (2 * sd * sd)); w /= w.sum()
    return s.rolling(n, min_periods=n).apply(lambda x: np.dot(x, w), raw=True)


MA = {"sma": sma, "ema": ema, "rma": rma, "wma": wma, "hma": hma, "dema": dema, "tema": tema,
      "zlema": zlema, "lsma": lsma, "alma": alma}


def source(df, name):
    return {"close": df["close"], "hl2": (df["high"] + df["low"]) / 2,
            "hlc3": (df["high"] + df["low"] + df["close"]) / 3,
            "ohlc4": (df["open"] + df["high"] + df["low"] + df["close"]) / 4}[name]


def atr(df, n):
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return rma(tr, n)


def rsi(s, n):
    d = s.diff()
    up, dn = rma(d.clip(lower=0), n), rma(-d.clip(upper=0), n)
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def supertrend_dir(df, n, f):
    a = atr(df, n).to_numpy(); hl2 = ((df["high"] + df["low"]) / 2).to_numpy(); c = df["close"].to_numpy()
    up, dn = hl2 - f * a, hl2 + f * a
    d = np.zeros(len(c)); fu, fd = up.copy(), dn.copy()
    for i in range(1, len(c)):
        if np.isnan(a[i]):
            continue
        fu[i] = max(up[i], fu[i - 1]) if c[i - 1] > fu[i - 1] else up[i]
        fd[i] = min(dn[i], fd[i - 1]) if c[i - 1] < fd[i - 1] else dn[i]
        d[i] = 1 if c[i] > fd[i - 1] else (-1 if c[i] < fu[i - 1] else d[i - 1])
    return d


# ----------------------------------------------------------------------------- alignment helpers
def fit_line(x, y):
    b, a = np.polyfit(x, y, 1)
    return a, b


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = ~(np.isnan(a) | np.isnan(b))
    return float(np.corrcoef(a[ok], b[ok])[0, 1]) if ok.sum() > 5 else float("nan")


def align_cbrs(t: dict, df: pd.DataFrame) -> dict:
    """Bar index for every digitised x. Checks the screenshot mapping against real closes."""
    line = {int(k): v for k, v in t["line"].items()}
    days = df.index.tz_convert("America/New_York").normalize()
    i0 = int(np.argmax(days >= pd.Timestamp("2026-06-01", tz="America/New_York")))
    xs = np.array(sorted(line)); ys = np.array([line[x] for x in xs])
    price = 290 - (ys - 181) / 7.3
    best = None
    for shift in range(-6, 7):
        for step in np.arange(8.95, 9.17, 0.01):
            bars = i0 + np.round((xs - 373) / step).astype(int) + shift
            ok = (bars >= 0) & (bars < len(df))
            if ok.sum() < 200:
                continue
            g = pd.DataFrame({"bar": bars[ok], "p": price[ok]}).groupby("bar")["p"].median()
            c = corr(g.to_numpy(), df["close"].to_numpy()[g.index])
            if best is None or c > best["corr"]:
                best = {"corr": c, "shift": shift, "step": float(step)}
    bars = i0 + np.round((xs - 373) / best["step"]).astype(int) + best["shift"]
    ok = (bars >= 0) & (bars < len(df))
    g = pd.DataFrame({"bar": bars[ok], "p": price[ok]}).groupby("bar")["p"].median()
    a, b = fit_line(g.to_numpy(), df["close"].to_numpy()[g.index])    # screenshot price -> real price
    best.update(i0=i0, price_fix=[a, b],
                median_err_pct=float(np.median(np.abs((a + b * g.to_numpy()) / df["close"].to_numpy()[g.index] - 1)) * 100),
                first_bar=str(df.index[0]), x_first_bar=373 + (0 - i0 - best["shift"]) * best["step"])
    best["bar_of_x"] = lambda x: int(i0 + round((x - 373) / best["step"]) + best["shift"])
    return best


def align_krx(t: dict, df: pd.DataFrame) -> dict:
    """Trading-day index for each column (month labels sit on the first trading day of each month)."""
    year = 2026
    months = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
    dates = df.index.tz_convert("Asia/Seoul").normalize() if df.index.tz is not None else df.index
    pts = []
    for name, x in zip(t["months"], t["months_x"]):
        first = pd.Timestamp(year, months[name], 1, tz=dates.tz)
        idx = int(np.argmax(dates >= first))
        if dates[idx] >= first and idx > 0:
            pts.append((idx, x))
        elif dates[-1] < first:          # month not traded yet (e.g. Nov): extrapolate by calendar
            pts.append((len(dates) - 1 + int(np.busday_count(dates[-1].date(), first.date())), x))
    a, b = fit_line([p[0] for p in pts], [p[1] for p in pts])   # x = a + b * idx
    resid = [x - (a + b * i) for i, x in pts]
    cols = {int(k): v for k, v in t["cols"].items()}
    ay, by = fit_line([p for _, p in t["axis"]], [y for y, _ in t["axis"]])   # y = ay + by * price
    yp = lambda y: (y - ay) / by
    best = None
    for shift in range(-4, 5):
        rows = []
        for x, r in cols.items():
            if "line" in r:
                i = int(round((x - a) / b)) + shift
                if 0 <= i < len(df):
                    rows.append((i, yp(r["line"])))
        g = pd.DataFrame(rows, columns=["bar", "p"]).groupby("bar")["p"].median()
        c = corr(g.to_numpy(), df["close"].to_numpy()[g.index])
        if best is None or c > best["corr"]:
            best = {"corr": c, "shift": shift}
    rows = []
    for x, r in cols.items():
        i = int(round((x - a) / b)) + best["shift"]
        if 0 <= i < len(df):
            rows.append({"bar": i, **{k: r.get(k) for k in ("top", "bot", "color", "line")}})
    tab = pd.DataFrame(rows)
    gl = tab.dropna(subset=["line"]).groupby("bar")["line"].median()
    fa, fb = fit_line(yp(gl.to_numpy()), df["close"].to_numpy()[gl.index])   # axis price -> real price
    price = lambda y: fa + fb * yp(np.asarray(y, float))
    rib = tab.dropna(subset=["top"]).groupby("bar").agg(top=("top", "median"), bot=("bot", "median"),
                                                          color=("color", lambda s: s.mode().iloc[0]))
    rib["upper"], rib["lower"] = price(rib["top"]), price(rib["bot"])
    rib["fast"] = np.where(rib["color"] == "blue", rib["upper"], rib["lower"])
    rib["slow"] = np.where(rib["color"] == "blue", rib["lower"], rib["upper"])
    return {"corr": best["corr"], "shift": best["shift"], "px_per_day": b, "month_resid_px": [round(float(r), 1) for r in resid],
            "price_fix": [fa, fb], "ribbon": rib,
            "line_err_pct": float(np.median(np.abs(price(gl.to_numpy()) / df["close"].to_numpy()[gl.index] - 1)) * 100)}


def btc_bar(df: pd.DataFrame, date: str) -> int:
    d = pd.Timestamp(date, tz=df.index.tz) if df.index.tz is not None else pd.Timestamp(date)
    return int(np.argmin(np.abs((df.index - d).total_seconds())))


# ----------------------------------------------------------------------------- 1. levels
def levels_check(df: pd.DataFrame, end_bar: int, seen: list[float]) -> dict:
    ath = float(df["high"].iloc[: end_bar + 1].max())
    fib = [ath * f for f in FIB]
    geo = [ath / 1.236 ** k for k in range(6)]
    def err(cands):
        return [round(float(min(abs(c / s - 1) for c in cands)) * 100, 2) for s in seen]
    implied = [round(float(s / ath), 4) for s in seen]
    return {"ath": round(ath, 2), "seen": [round(float(x), 2) for x in seen], "fraction_of_ath": implied,
            "fib_err_pct": err(fib), "geometric_err_pct": err(geo)}


# ----------------------------------------------------------------------------- 2. ribbon
LENGTHS = list(range(3, 61)) + list(range(65, 205, 5))


def ribbon_fit(df: pd.DataFrame, rib: pd.DataFrame) -> dict:
    bars = rib.index.to_numpy()
    res = []
    for (mname, fn), src in itertools.product(MA.items(), ["close", "hl2", "hlc3", "ohlc4"]):
        s = source(df, src)
        for n in LENGTHS:
            if mname in ("lsma", "alma", "wma", "hma") and src != "close" and n > 60:
                continue  # slow rolling-apply; close-only beyond 60
            v = fn(s, n).to_numpy()[bars]
            if np.isnan(v).mean() > 0.05:
                continue
            ef = float(np.nanmedian(np.abs(np.log(v / rib["fast"].to_numpy()))))
            es = float(np.nanmedian(np.abs(np.log(v / rib["slow"].to_numpy()))))
            res.append({"ma": mname, "src": src, "n": n, "err_fast": ef, "err_slow": es})
    r = pd.DataFrame(res)
    fast = r.nsmallest(8, "err_fast"); slow = r.nsmallest(8, "err_slow")
    pairs = []
    for _, f in fast.head(5).iterrows():
        for _, s in slow.head(5).iterrows():
            fv = MA[f.ma](source(df, f.src), int(f.n)).to_numpy()[bars]
            sv = MA[s.ma](source(df, s.src), int(s.n)).to_numpy()[bars]
            agree = float(np.mean((fv > sv) == (rib["color"].to_numpy() == "blue")))
            pairs.append({"fast": f"{f.ma}({f.src},{int(f.n)})", "slow": f"{s.ma}({s.src},{int(s.n)})",
                          "err_fast_pct": round(f.err_fast * 100, 2), "err_slow_pct": round(s.err_slow * 100, 2),
                          "colour_agree": round(agree, 3)})
    pairs.sort(key=lambda p: (-p["colour_agree"], p["err_fast_pct"] + p["err_slow_pct"]))
    keep = lambda d: d.assign(err_fast=(d.err_fast * 100).round(2), err_slow=(d.err_slow * 100).round(2)).to_dict("records")
    return {"bars": int(len(bars)), "blue_share": round(float((rib["color"] == "blue").mean()), 3),
            "best_fast": keep(fast), "best_slow": keep(slow), "pairs": pairs[:10]}


# ----------------------------------------------------------------------------- 3. buy/sell rules
def alternate(buy: np.ndarray, sell: np.ndarray) -> tuple[list[int], list[int]]:
    """Long/flat state machine: a buy opens, a sell closes, repeats are ignored."""
    b, s, pos = [], [], False
    for i in range(len(buy)):
        if not pos and buy[i]:
            b.append(i); pos = True
        elif pos and sell[i]:
            s.append(i); pos = False
    return b, s


def _prev(a):
    return np.r_[np.nan, np.asarray(a, float)[:-1]]


def cross_up(a, lvl):
    a = np.asarray(a, float); lvl = np.broadcast_to(np.asarray(lvl, float), a.shape)
    return (a > lvl) & (_prev(a) <= _prev(lvl))


def cross_dn(a, lvl):
    a = np.asarray(a, float); lvl = np.broadcast_to(np.asarray(lvl, float), a.shape)
    return (a < lvl) & (_prev(a) >= _prev(lvl))


def band_modes(df, lo, up):
    c, h, l = (df[k].to_numpy() for k in ("close", "high", "low"))
    return {"touch": (l <= lo, h >= up), "close": (c < lo, c > up),
            "reenter": (cross_up(c, lo), cross_dn(c, up))}


def candidates(df: pd.DataFrame):
    """Yield (family, params, buy_bool, sell_bool, display_offset)."""
    c = df["close"]
    atrs = {n: atr(df, n).to_numpy() for n in (10, 14, 20)}
    for mt, n in itertools.product(["sma", "ema"], [5, 8, 10, 13, 14, 20, 21, 26, 30, 34, 50]):
        mid = MA[mt](c, n).to_numpy()
        for an, k in itertools.product((10, 14, 20), (0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3)):
            lo, up = mid - k * atrs[an], mid + k * atrs[an]
            for mode, (b, s) in band_modes(df, lo, up).items():
                yield "atr_band", f"{mt}{n} ± {k}×ATR{an} {mode}", b, s, 0
    for n in (10, 14, 20, 30, 50):
        m, sd = sma(c, n).to_numpy(), c.rolling(n).std().to_numpy()
        for k in (1, 1.5, 2, 2.5):
            for mode, (b, s) in band_modes(df, m - k * sd, m + k * sd).items():
                yield "bollinger", f"sma{n} ± {k}σ {mode}", b, s, 0
    for n, L in itertools.product((2, 3, 4, 5, 7, 9, 14, 21), (10, 15, 20, 25, 30, 35, 40, 45)):
        r = rsi(c, n).to_numpy()
        yield "rsi", f"RSI{n} {L}/{100 - L} into", r < L, r > 100 - L, 0
        yield "rsi", f"RSI{n} {L}/{100 - L} back out", cross_up(r, L), cross_dn(r, 100 - L), 0
    for n, sm, L in itertools.product((5, 9, 14, 21), (1, 3), (10, 20, 30)):
        lo_n, hi_n = df["low"].rolling(n).min(), df["high"].rolling(n).max()
        k = (100 * (c - lo_n) / (hi_n - lo_n)).rolling(sm).mean().to_numpy()
        yield "stoch", f"Stoch{n},{sm} {L}/{100 - L} into", k < L, k > 100 - L, 0
        yield "stoch", f"Stoch{n},{sm} {L}/{100 - L} back out", cross_up(k, L), cross_dn(k, 100 - L), 0
    for n in (3, 5, 10, 20):
        l, h = df["low"].to_numpy(), df["high"].to_numpy()
        pl, ph = df["low"].shift(1).rolling(n).min().to_numpy(), df["high"].shift(1).rolling(n).max().to_numpy()
        yield "donchian", f"new {n}-bar low / high", l < pl, h > ph, 0
    for L, R in itertools.product(range(1, 7), range(1, 7)):
        lo, hi = df["low"], df["high"]
        win = L + R + 1
        piv_l = (lo == lo.rolling(win, center=False).min().shift(-R)).to_numpy()
        piv_h = (hi == hi.rolling(win, center=False).max().shift(-R)).to_numpy()
        yield "pivot (look-ahead)", f"pivots L{L} R{R} drawn on the pivot bar", piv_l, piv_h, 0
        yield "pivot (confirmed)", f"pivots L{L} R{R} drawn when confirmed", np.r_[[False] * R, piv_l[:-R]], np.r_[[False] * R, piv_h[:-R]], 0
    for mt, f, s in itertools.product(["ema", "sma"], (5, 8, 10, 13, 20), (20, 21, 30, 50)):
        if f >= s:
            continue
        fv, sv = MA[mt](c, f).to_numpy(), MA[mt](c, s).to_numpy()
        yield "ma_cross", f"{mt}{f}/{s} cross", cross_up(fv, sv), cross_dn(fv, sv), 0
    for n, f in itertools.product((7, 10, 14, 20), (1, 1.5, 2, 2.5, 3)):
        d = supertrend_dir(df, n, f)
        flip_up = (d == 1) & (np.r_[0, d[:-1]] == -1); flip_dn = (d == -1) & (np.r_[0, d[:-1]] == 1)
        yield "supertrend", f"Supertrend {n},{f} flips", flip_up, flip_dn, 0


def score(pred: list[tuple[str, int]], target: list[tuple[str, int]], tol: int) -> dict:
    used, tp, lag = set(), 0, []
    for side, t in target:
        best = None
        for j, (ps, p) in enumerate(pred):
            if ps == side and j not in used and abs(p - t) <= tol and (best is None or abs(p - t) < abs(pred[best][1] - t)):
                best = j
        if best is not None:
            used.add(best); tp += 1; lag.append(pred[best][1] - t)
    prec = tp / len(pred) if pred else 0.0
    rec = tp / len(target) if target else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"f1": round(f1, 3), "precision": round(prec, 3), "recall": round(rec, 3), "hits": tp,
            "signals": len(pred), "targets": len(target), "mean_lag": round(float(np.mean(lag)), 2) if lag else None}


def trade_stats(df: pd.DataFrame, b: list[int], s: list[int], start: int = 0) -> dict:
    c = df["close"].to_numpy()
    rets = [c[j] / c[i] - 1 for i, j in zip(b, s) if i >= start]
    if not rets:
        return {"trades": 0}
    eq = float(np.prod([1 + r for r in rets]))
    return {"trades": len(rets), "win_pct": round(100 * float(np.mean([r > 0 for r in rets])), 1),
            "roi_pct": round((eq - 1) * 100, 1), "sum_pct": round(100 * float(np.sum(rets)), 1),
            "open": len(b) > len(s)}


def rule_search(charts: list[dict]) -> list[dict]:
    """charts: [{name, df, targets [(side, bar)], window (lo, hi), exclude [(lo, hi)], tol}]"""
    rows = {}
    for ch in charts:
        for fam, prm, buy, sell, _ in candidates(ch["df"]):
            buy = np.nan_to_num(np.asarray(buy, float)).astype(bool)
            sell = np.nan_to_num(np.asarray(sell, float)).astype(bool)
            b, s = alternate(buy, sell)
            lo, hi = ch["window"]
            inside = lambda i: lo <= i <= hi and not any(a <= i <= z for a, z in ch["exclude"])
            pred = sorted([("buy", i) for i in b if inside(i)] + [("sell", i) for i in s if inside(i)], key=lambda p: p[1])
            sc = score(pred, ch["targets"], ch["tol"])
            key = (fam, prm)
            row = rows.setdefault(key, {"family": fam, "rule": prm})
            row[ch["name"]] = sc
            row[ch["name"] + "_stats"] = trade_stats(ch["df"], b, s)
            row["_pred_" + ch["name"]] = pred
    out = list(rows.values())
    for r in out:
        r["mean_f1"] = round(float(np.mean([r[ch["name"]]["f1"] for ch in charts if ch["name"] in r])), 3)
    out.sort(key=lambda r: -r["mean_f1"])
    # placebo: the same signals slid 7-15 bars away. A real match should score far above this.
    keep = {id(r) for r in out[:40]}
    seen = set()
    for r in out:
        if r["family"] not in seen:
            keep.add(id(r)); seen.add(r["family"])
    for r in out:
        if id(r) in keep:
            f = []
            for ch in charts:
                for sh in (-15, -11, -7, 7, 11, 15):
                    f.append(score([(sd, i + sh) for sd, i in r["_pred_" + ch["name"]]], ch["targets"], ch["tol"])["f1"])
            r["placebo_f1"] = round(float(np.mean(f)), 3)
        for ch in charts:
            r.pop("_pred_" + ch["name"], None)
    return out


# ----------------------------------------------------------------------------- report
def md_table(rows: list[dict], cols: list[str]) -> str:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true", help="offline plumbing test on random prices")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    data = load_data(args.synthetic)
    for k, v in data.items():
        log.info("%s: %d bars %s .. %s", k, len(v), v.index[0], v.index[-1])
    res: dict = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "synthetic": args.synthetic,
                 "data": {k: [str(v.index[0]), str(v.index[-1]), len(v)] for k, v in data.items()}}

    # --- CBRS 4h
    cb_t = json.loads((TARGETS / "cbrs.json").read_text())
    cb = data["CBRS"]
    al = align_cbrs(cb_t, cb)
    bar_of = al.pop("bar_of_x")
    cb_targets = [(m["side"], bar_of(m["x"])) for m in cb_t["markers"]]
    res["cbrs_alignment"] = al
    fix = lambda p: al["price_fix"][0] + al["price_fix"][1] * p
    res["cbrs_levels"] = levels_check(cb, bar_of(2046), [round(fix(p), 2) for p in cb_t["levels"]])
    res["cbrs_marker_trades"] = trade_stats(cb, [b for s, b in cb_targets if s == "buy"], [b for s, b in cb_targets if s == "sell"])

    # --- BTC daily
    bt_t = json.loads((TARGETS / "btc.json").read_text())
    bt = data["BTC-USD"]
    bt_targets = [(m["side"], btc_bar(bt, m["date"])) for m in bt_t["markers"]]
    excl = [(btc_bar(bt, bt_t["exclude"][0]), btc_bar(bt, bt_t["exclude"][1]))]
    win = (btc_bar(bt, bt_t["window"][0]), btc_bar(bt, bt_t["window"][1]))
    # how well do triangles sit just under lows / over highs, for small date shifts?
    shifts = {}
    for sh in range(-3, 4):
        e = []
        for m, (side, i) in zip(bt_t["markers"], bt_targets):
            j = min(max(i + sh, 0), len(bt) - 1)
            e.append(abs(np.log(bt["low"].iloc[j] if side == "buy" else bt["high"].iloc[j])))
        shifts[sh] = float(np.mean(e))
    res["btc_levels"] = levels_check(bt, win[1], bt_t["levels"])
    vis_b = [i for s, i in bt_targets if s == "buy"]; vis_s = [i for s, i in bt_targets if s == "sell"]
    res["btc_marker_trades"] = trade_stats(bt, *alternate(np.isin(np.arange(len(bt)), vis_b), np.isin(np.arange(len(bt)), vis_s)))

    # --- ribbons
    res["ribbon"] = {}
    k_t = json.loads((TARGETS / "krx.json").read_text())
    for key in ("sk", "ss"):
        t = k_t[key]; df = data[t["ticker"]]
        a = align_krx(t, df)
        rib = a.pop("ribbon")
        fit = ribbon_fit(df, rib) if len(rib) > 30 else {"error": "too few ribbon bars"}
        res["ribbon"][t["ticker"]] = {"alignment": a, **fit}
        log.info("ribbon %s: corr %.3f, best pair %s", t["ticker"], a["corr"], fit.get("pairs", [{}])[0])

    # --- rule search
    charts = [
        {"name": "CBRS_4h", "df": cb, "targets": cb_targets, "window": (0, len(cb) - 1), "exclude": [], "tol": 1},
        {"name": "BTC_1d", "df": bt, "targets": [(s, i) for s, i in bt_targets if not (excl[0][0] <= i <= excl[0][1])],
         "window": win, "exclude": excl, "tol": 2},
    ]
    rows = rule_search(charts)
    res["rules_top"] = rows[:40]
    best_by_family = {}
    for r in rows:
        best_by_family.setdefault(r["family"], r)
    res["rules_best_by_family"] = list(best_by_family.values())

    (OUT / "ia_calibration.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "ia_calibration.md").write_text(report(res))
    log.info("done")


def report(r: dict) -> str:
    L = [f"# IA indicator calibration ({r['generated']})", ""]
    if r["synthetic"]:
        L += ["**SYNTHETIC DATA — plumbing test only.**", ""]
    L += ["Data: " + ", ".join(f"{k} {v[2]} bars from {v[0][:10]}" for k, v in r["data"].items()), ""]
    a = r["cbrs_alignment"]
    L += ["## Alignment", f"- CBRS 4h: screenshot line vs real closes corr **{a['corr']:.3f}**, median error "
          f"{a['median_err_pct']:.1f}% (bar step {a['step']:.3f}px, shift {a['shift']})"]
    for t, v in r["ribbon"].items():
        al = v["alignment"]
        L.append(f"- {t}: line vs closes corr **{al['corr']:.3f}** (shift {al['shift']}, month-label residuals {al['month_resid_px']} px)")
    L += ["", "## 1. Levels (IA-ATR-Model)"]
    for k in ("cbrs_levels", "btc_levels"):
        v = r[k]
        L.append(f"- {k.split('_')[0].upper()}: running ATH {v['ath']:,}; screenshot levels {v['seen']} = "
                 f"{v['fraction_of_ath']} of ATH. Error vs Fibonacci fractions {v['fib_err_pct']}%, vs ATH/1.236^k {v['geometric_err_pct']}%")
    L += ["", "## 2. Ribbon (IA-Optimized-Trend)"]
    for t, v in r["ribbon"].items():
        if "pairs" not in v:
            L.append(f"- {t}: {v.get('error')}"); continue
        L += [f"### {t} ({v['bars']} bars, {v['blue_share']:.0%} blue)", "",
              md_table(v["pairs"][:6], ["fast", "slow", "err_fast_pct", "err_slow_pct", "colour_agree"]), ""]
    L += ["## 3. Buy/sell triangles (IA-ATR-Model)", "",
          f"Pairing the screenshot's own triangles at closing prices: CBRS {r['cbrs_marker_trades']}, "
          f"BTC (visible part) {r['btc_marker_trades']}", "",
          "Best rule per family (F1 = timing match, 1.0 = every triangle reproduced, nothing extra):", ""]
    rows = []
    for x in r["rules_best_by_family"]:
        rows.append({"family": x["family"], "rule": x["rule"], "mean F1": x["mean_f1"], "placebo F1": x.get("placebo_f1"),
                     "CBRS F1 (hits/targets, signals)": f"{x['CBRS_4h']['f1']} ({x['CBRS_4h']['hits']}/{x['CBRS_4h']['targets']}, {x['CBRS_4h']['signals']})",
                     "BTC F1": f"{x['BTC_1d']['f1']} ({x['BTC_1d']['hits']}/{x['BTC_1d']['targets']}, {x['BTC_1d']['signals']})",
                     "CBRS trades": x["CBRS_4h_stats"], "BTC full-history trades": x["BTC_1d_stats"]})
    L += [md_table(rows, list(rows[0].keys())), "", "Top 15 overall:", ""]
    rows = [{"family": x["family"], "rule": x["rule"], "mean F1": x["mean_f1"], "placebo F1": x.get("placebo_f1"), "CBRS F1": x["CBRS_4h"]["f1"],
             "BTC F1": x["BTC_1d"]["f1"], "BTC trades": x["BTC_1d_stats"].get("trades"),
             "BTC win%": x["BTC_1d_stats"].get("win_pct")} for x in r["rules_top"][:15]]
    L += [md_table(rows, list(rows[0].keys())), ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
