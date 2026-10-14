"""
Weekly trend rules: do they help, and which one should the app show?

Rules (weekly bars, decided at the Friday close, acted on at the next week's open; costs included):
  sma40      close above its 40-week average (the classic "10-month" rule)
  mom52      up over the past 52 weeks (time-series momentum)
  cross10_40 10-week average above the 40-week average
  ribbon_w   IA ribbon on weekly bars: EMA15 of (H+L+C)/3 above EMA34 of close
  atr_w      IA ATR stop on weekly bars (1.25 x ATR30)
  two_of_3   at least 2 of sma40, mom52, ribbon_w
Each is "hold while up, cash while down" vs simply holding. Stocks: today's S&P 100 + SPY/QQQ, 2005 on
(today's members flatter holding and trend rules alike). Crypto: 29 large coins. Train = before 2021,
test = 2021 on; the rules have no fitted settings, so both halves are out of sample in practice.

    python weekly_research.py        (Actions tab -> "Weekly trend test")

Writes research/weekly.md and research/weekly.json.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("weekly")
OUT = Path(__file__).with_name("research")
SPLIT = pd.Timestamp("2021-01-01")
RULES = ["sma40", "mom52", "cross10_40", "ribbon_w", "atr_w", "two_of_3"]


def weekly(df: pd.DataFrame) -> pd.DataFrame:
    w = df.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return w.dropna(subset=["close"])


def ema(s, n): return s.ewm(span=n, adjust=False, min_periods=n).mean()


def atr_up(w: pd.DataFrame, k: float = 1.25, n: int = 30) -> pd.Series:
    pc = w["close"].shift(1)
    tr = pd.concat([w["high"] - w["low"], (w["high"] - pc).abs(), (w["low"] - pc).abs()], axis=1).max(axis=1)
    a = (k * tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()).to_numpy()
    c = w["close"].to_numpy(); stop = np.zeros(len(c)); up = np.zeros(len(c), bool)
    for i in range(1, len(c)):
        if a[i] != a[i]:
            continue
        p, x, xp = stop[i - 1], c[i], c[i - 1]
        stop[i] = max(p, x - a[i]) if x > p and xp > p else min(p, x + a[i]) if x < p and xp < p else x - a[i] if x > p else x + a[i]
        up[i] = x > stop[i]
    return pd.Series(up, index=w.index)


def states(w: pd.DataFrame) -> pd.DataFrame:
    c = w["close"]
    s40 = c.rolling(40, min_periods=40).mean()
    hlc3 = (w["high"] + w["low"] + c) / 3
    st = pd.DataFrame(index=w.index)
    st["sma40"] = (c > s40) & s40.notna()
    st["mom52"] = (c > c.shift(52)) & c.shift(52).notna()
    st["cross10_40"] = (c.rolling(10).mean() > s40) & s40.notna()
    st["ribbon_w"] = ema(hlc3, 15) > ema(c, 34)
    st["atr_w"] = atr_up(w)
    st["two_of_3"] = (st[["sma40", "mom52", "ribbon_w"]].sum(axis=1) >= 2)
    return st


def run(w: pd.DataFrame, up: pd.Series, cost: float, start, end) -> dict | None:
    r = (w["open"].shift(-2) / w["open"].shift(-1) - 1)
    pos = up.astype(float)
    m = (w.index >= start) & (w.index < end) & r.notna() & up.notna()
    if m.sum() < 52:
        return None
    p, rr = pos[m], r[m]
    strat = p * rr - cost * p.diff().abs().fillna(p.iloc[0])
    eq, hold = (1 + strat).cumprod(), (1 + rr).cumprod()
    yrs = len(rr) / 52.18
    f = lambda e: {"cagr": (e.iat[-1] ** (1 / yrs) - 1) * 100, "mdd": float((e / e.cummax() - 1).min()) * 100}
    sr = lambda x: float(x.mean() / x.std() * np.sqrt(52)) if x.std() > 0 else 0.0
    return {"weeks": int(m.sum()), "rule": {**f(eq), "sharpe": sr(strat)}, "hold": {**f(hold), "sharpe": sr(rr)},
            "invested": float(p.mean()) * 100, "switches": int(p.diff().abs().sum()),
            "down_capture": float(strat[rr < 0].sum() / rr[rr < 0].sum()) if (rr < 0).any() else None,
            "up_capture": float(strat[rr > 0].sum() / rr[rr > 0].sum()) if (rr > 0).any() else None}


def fetch(tickers: list[str]) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), 50):
        b = tickers[i:i + 50]
        for attempt in range(3):
            try:
                d = yf.download(b, start="2004-01-01", interval="1d", auto_adjust=True, group_by="ticker", progress=False, threads=True)
                break
            except Exception as e:
                log.warning("batch %d: %s", i, e); time.sleep(10 * (attempt + 1)); d = None
        if d is None:
            continue
        for t in b:
            try:
                x = (d[t] if isinstance(d.columns, pd.MultiIndex) else d).rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
                x = x.dropna(subset=["close"]); x.index = pd.DatetimeIndex(x.index).tz_localize(None)
                if len(x) > 400:
                    out[t] = x
            except Exception:
                pass
    return out


def summarize(results: list[dict]) -> dict:
    keys = ["cagr", "mdd", "sharpe"]
    med = lambda f: round(float(np.median([f(x) for x in results])), 2) if results else None
    out = {k: med(lambda x, k=k: x["rule"][k]) for k in keys}
    out.update({"hold_" + k: med(lambda x, k=k: x["hold"][k]) for k in keys})
    out.update(invested=med(lambda x: x["invested"]), switches_per_year=med(lambda x: x["switches"] / (x["weeks"] / 52.18)),
               down_capture=med(lambda x: x["down_capture"] or 0), up_capture=med(lambda x: x["up_capture"] or 0),
               better_sharpe=f"{sum(x['rule']['sharpe'] > x['hold']['sharpe'] for x in results)}/{len(results)}",
               smaller_drop=f"{sum(x['rule']['mdd'] > x['hold']['mdd'] for x in results)}/{len(results)}", n=len(results))
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from factor_research import COINS, SP100
    groups = {"stock": (list(SP100) + ["SPY", "QQQ"], 0.0005), "crypto": ([c + "-USD" for c in COINS], 0.0025)}
    res = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "segments": {}}
    for asset, (tickers, cost) in groups.items():
        data = fetch(tickers)
        seg = {}
        for part, (a, b) in {"train": (pd.Timestamp("2005-01-01"), SPLIT), "test": (SPLIT, pd.Timestamp("2100-01-01")),
                             "all": (pd.Timestamp("2005-01-01"), pd.Timestamp("2100-01-01"))}.items():
            seg[part] = {}
            for rule in RULES:
                rows = []
                for t, df in data.items():
                    w = weekly(df); st = states(w)
                    x = run(w, st[rule], cost, a, b)
                    if x:
                        rows.append(x)
                seg[part][rule] = summarize(rows)
        if asset == "stock":                        # the market itself, for context
            for t in ("SPY", "QQQ"):
                if t in data:
                    w = weekly(data[t]); st = states(w)
                    seg[t] = {rule: run(w, st[rule], cost, pd.Timestamp("2005-01-01"), pd.Timestamp("2100-01-01")) for rule in RULES}
        res["segments"][asset] = {"tickers": len(data), **seg}
    OUT.mkdir(exist_ok=True)
    (OUT / "weekly.json").write_text(json.dumps(res, indent=1, default=float))
    L = [f"# Weekly trend rules ({res['generated']})", "",
         "Hold while the rule says up, cash while down; weekly decisions at the Friday close, trades at Monday's open, "
         "costs included. Medians across tickers. Train = before 2021, test = 2021 on.", ""]
    for asset, seg in res["segments"].items():
        L += [f"## {asset.title()}s ({seg['tickers']} tickers)", ""]
        for part in ("train", "test"):
            L += [f"**{part}**", "", "| Rule | Per year % | Worst drop % | Sharpe | Hold: per year % | Hold: worst drop % | Hold: Sharpe | "
                  "Invested % | Switches/yr | Better Sharpe | Smaller drop |", "|---|---|---|---|---|---|---|---|---|---|---|"]
            for rule in RULES:
                x = seg[part][rule]
                L.append(f"| {rule} | {x['cagr']} | {x['mdd']} | {x['sharpe']} | {x['hold_cagr']} | {x['hold_mdd']} | {x['hold_sharpe']} | "
                         f"{x['invested']} | {x['switches_per_year']} | {x['better_sharpe']} | {x['smaller_drop']} |")
            L.append("")
        for t in ("SPY", "QQQ"):
            if t in seg:
                L += [f"**{t} since 2005**", "", "| Rule | Per year % | Worst drop % | Sharpe | Hold per year % | Hold worst drop % |", "|---|---|---|---|---|---|"]
                for rule, x in seg[t].items():
                    if x:
                        L.append(f"| {rule} | {x['rule']['cagr']:.1f} | {x['rule']['mdd']:.1f} | {x['rule']['sharpe']:.2f} | "
                                 f"{x['hold']['cagr']:.1f} | {x['hold']['mdd']:.1f} |")
                L.append("")
    (OUT / "weekly.md").write_text("\n".join(L) + "\n")
    log.info("done")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        OUT.mkdir(exist_ok=True)
        (OUT / "weekly.md").write_text("# Run failed\n\n```\n" + traceback.format_exc() + "```\n")
