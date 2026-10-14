"""
Four ideas to beat the app's current signals, tested the same honest way (train < 2021, test 2021 on).

Stocks (S&P 100 + SPY/QQQ, 2005 on, daily bars; next-day fills, costs in):
  A  weekly-trend gate: current Strong Buy (2+ dip models) only when the stock's OWN weekly trend is up
     (weekly IA ribbon blue and close above its 40-week average)
  B  market-panic dip: RSI(2) < 5, close above the 200-day average, VIX above 3-month VIX; hold until a
     close above the 5-day average (vs the current Strong Buy)
  D1 index gate: Strong Buy only while SPY's weekly trend is up
Crypto (29 large coins, daily, 2017 on):
  C  the app's trend rule (3 of 4) with volatility sizing (size = 60% / 30-day vol, cap 1) as the default
  D2 Bitcoin gate: the trend rule only while BTC's weekly trend is up
  E  the trend rule on WEEKLY bars (a slower version)
Every row reports next-5-day excess return (vs the ticker's own average) with a t-stat clustered by date,
share of time invested, and the long-only strategy vs holding (CAGR, worst drop, Sharpe).

    python combo_research.py        (Actions tab -> "Combo test")
Writes research/combo.md and research/combo.json.
"""
from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import context
import ia
import models
from config import load_config

log = logging.getLogger("combo")
OUT = Path(__file__).with_name("research")
SPLIT = pd.Timestamp("2021-01-01", tz="UTC")
COST = {"stock": 0.0005, "crypto": 0.0025}
TREND4 = ["tsmom28", "sma_ensemble", "donchian_ensemble", "btc_trend_gate"]
DIP3 = ["rsi2_pullback", "ibs_reversal", "vix_backwardation"]


def fetch(tickers: list[str], start="2004-01-01") -> dict[str, pd.DataFrame]:
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), 60):
        b = tickers[i:i + 60]; d = None
        for attempt in range(3):
            try:
                d = yf.download(b, start=start, interval="1d", auto_adjust=True, group_by="ticker", progress=False, threads=True); break
            except Exception as e:
                log.warning("batch %d: %s", i, e); time.sleep(10 * (attempt + 1))
        if d is None:
            continue
        for t in b:
            try:
                x = (d[t] if isinstance(d.columns, pd.MultiIndex) else d).rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
                x = x.dropna(subset=["close"]).astype(float); x.index = pd.to_datetime(x.index, utc=True)
                if len(x) > 600:
                    out[t] = x[~x.index.duplicated(keep="last")].sort_index()
            except Exception:
                pass
        time.sleep(1)
    return out


def weekly_up(df: pd.DataFrame, rule: str) -> pd.Series:
    """Own weekly trend (ribbon blue and close > 40-week avg), known at the week's close, applied from the next day."""
    w = df.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna(subset=["close"])
    fast, slow = ia.ribbon(w)
    up = ((fast > slow) & (w["close"] > w["close"].rolling(40, min_periods=40).mean())).fillna(False)
    return up.reindex(df.index, method="ffill").shift(1).fillna(False).astype(bool)


def rsi(s, n):
    d = s.diff(); up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def excess_stats(frames: list[pd.DataFrame], col: str) -> dict:
    b = pd.concat(frames)
    b["x5"] = b["r5"] - b.groupby("ticker")["r5"].transform("mean")
    m = b[col].astype(bool) & b["x5"].notna()
    if m.sum() < 30:
        return {"n": int(m.sum())}
    x = b.loc[m, "x5"]; day = b.index[m].floor("D")
    mu = float(x.mean()); resid = (x - mu).groupby(day).sum(); G, N = len(resid), len(x)
    se = math.sqrt((resid ** 2).sum() * G / max(G - 1, 1)) / N
    return {"n": int(N), "dates": int(G), "x5_pct": round(mu * 100, 2), "t": round(mu / se, 2) if se > 0 else None,
            "win5_pct": round(float((b.loc[m, "r5"] > 0).mean()) * 100, 1), "share_pct": round(float(b[col].mean()) * 100, 1)}


def strategy(frames: list[pd.DataFrame], col: str, cost: float, size_col: str | None = None) -> dict:
    """Equal-weight across tickers each day: hold while col is true (size from size_col), else cash."""
    rows = []
    for f in frames:
        pos = f[col].astype(float) * (f[size_col].clip(upper=1) if size_col else 1.0)
        strat = pos * f["r_next"] - cost * pos.diff().abs().fillna(0)
        rows.append(pd.DataFrame({"s": strat, "h": f["r_next"]}, index=f.index))
    d = pd.concat(rows).groupby(level=0).mean().dropna()
    if len(d) < 100:
        return {}
    per = 365 if (d.index.dayofweek >= 5).any() else 252
    f = lambda r: {"cagr": round(((1 + r).prod() ** (per / len(r)) - 1) * 100, 1),
                   "mdd": round(float(((1 + r).cumprod() / (1 + r).cumprod().cummax() - 1).min()) * 100, 1),
                   "sharpe": round(float(r.mean() / r.std() * np.sqrt(per)), 2) if r.std() > 0 else None}
    return {"rule": f(d["s"]), "hold": f(d["h"])}


def stock_frames(data: dict, ctx_daily: dict) -> list[pd.DataFrame]:
    out = []
    for t, df in data.items():
        if t in ("SPY", "QQQ"):
            continue
        ctx = context.align(ctx_daily, df.index, "stock", "1d")
        v = pd.DataFrame({k: models.run(k, df, ctx)["vote"] for k in DIP3}, index=df.index)
        n = (v > 0).sum(axis=1)
        f = pd.DataFrame(index=df.index)
        f["ticker"] = t
        f["r_next"] = df["close"].pct_change().shift(-1)
        f["r5"] = df["close"].shift(-5) / df["close"] - 1
        f["strong"] = n >= 2
        f["own_wk"] = weekly_up(df, "W-FRI")
        f["A"] = f["strong"] & f["own_wk"]
        c = df["close"]; r2 = rsi(c, 2); ma200 = c.rolling(200).mean(); ma5 = c.rolling(5).mean()
        panic = (ctx["vix"] > ctx["vix3m"]).reindex(df.index).fillna(False) if "vix" in ctx and "vix3m" in ctx else pd.Series(False, index=df.index)
        entry = ((r2 < 5) & (c > ma200) & panic).to_numpy(); exit_ = (c > ma5).to_numpy()
        pos = np.zeros(len(c), bool); on = False
        for i in range(len(c)):
            if on and exit_[i]: on = False
            if entry[i]: on = True
            pos[i] = on
        f["B"] = pos
        f["B_entry"] = entry
        out.append(f.iloc[260:])
    spy_wk = weekly_up(data["SPY"], "W-FRI") if "SPY" in data else None
    for f in out:
        f["D1"] = f["strong"] & (spy_wk.reindex(f.index).fillna(False) if spy_wk is not None else False)
    return out


def crypto_frames(data: dict, ctx_daily: dict) -> list[pd.DataFrame]:
    out = []
    btc_wk = weekly_up(data["BTC-USD"], "W-SUN") if "BTC-USD" in data else None
    for t, df in data.items():
        ctx = context.align(ctx_daily, df.index, "crypto", "1d")
        v = pd.DataFrame({k: models.run(k, df, ctx)["vote"] for k in TREND4}, index=df.index)
        f = pd.DataFrame(index=df.index)
        f["ticker"] = t
        f["r_next"] = df["close"].pct_change().shift(-1)
        f["r5"] = df["close"].shift(-5) / df["close"] - 1
        f["trend"] = v.mean(axis=1) > 0.5
        vol = np.log(df["close"]).diff().rolling(30).std() * np.sqrt(365)
        f["size"] = (0.6 / vol).clip(upper=1).fillna(0)
        f["D2"] = f["trend"] & (btc_wk.reindex(f.index).fillna(False) if btc_wk is not None else False)
        # E: trend rule on weekly bars, applied from the next day
        w = df.resample("W-SUN").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["close"])
        wctx = context.align(ctx_daily, w.index, "crypto", "1wk")
        try:
            wv = pd.DataFrame({k: models.run(k, w, wctx)["vote"] for k in TREND4}, index=w.index)
            f["E"] = (wv.mean(axis=1) > 0.5).reindex(df.index, method="ffill").shift(1).fillna(False).astype(bool)
        except Exception as e:
            log.info("%s weekly: %s", t, e); f["E"] = False
        out.append(f.iloc[260:])
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from factor_research import COINS, SP100
    cfg = load_config()
    res = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "segments": {}}
    stocks = fetch(list(SP100) + ["SPY", "QQQ"])
    ctx_s = context.fetch_daily(lambda s: fetch([s])[s], context.needs("stock"))
    sf = stock_frames(stocks, ctx_s)
    coins = fetch([c + "-USD" for c in COINS], start="2016-01-01")
    ctx_c = context.fetch_daily(lambda s: fetch([s], start="2014-01-01")[s], context.needs("crypto"))
    cf = crypto_frames(coins, ctx_c)
    tests = {"stock": (sf, [("strong", "Current Strong Buy (2+ dip models)", None), ("A", "A: Strong Buy + own weekly trend up", None),
                             ("B", "B: market-panic dip (RSI2<5, VIX panic, above 200d)", None), ("D1", "D1: Strong Buy + S&P weekly trend up", None)]),
             "crypto": (cf, [("trend", "Current trend rule (3 of 4)", None), ("trend", "C: trend rule, volatility-sized", "size"),
                              ("D2", "D2: trend rule + Bitcoin weekly trend up", None), ("E", "E: trend rule on weekly bars", None)])}
    for asset, (frames, rows) in tests.items():
        seg = {"tickers": len(frames)}
        for part, sel in (("train", lambda f: f[f.index < SPLIT]), ("test", lambda f: f[f.index >= SPLIT])):
            fr = [sel(f) for f in frames]
            seg[part] = {}
            for col, name, size in rows:
                key = name
                seg[part][key] = {"excess": excess_stats(fr, col), "strategy": strategy(fr, col, COST[asset], size)}
        res["segments"][asset] = seg
    OUT.mkdir(exist_ok=True)
    (OUT / "combo.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "combo.md").write_text(report(res))
    log.info("done")


def report(r: dict) -> str:
    L = [f"# Combo test: four ideas vs the current signals ({r['generated']})", "",
         "Excess = next-5-day return above the ticker's own average, t clustered by date. Strategy = equal weight across "
         "tickers, in while the rule is on, cash otherwise, costs in. Train = before 2021, test = 2021 on.", ""]
    for asset, seg in r["segments"].items():
        L += [f"## {asset.title()}s ({seg['tickers']} tickers)", ""]
        for part in ("train", "test"):
            L += [f"**{part}**", "", "| Rule | Signal days | Next 5d excess % | t | 5d winners % | Time in % | Rule: per yr % | worst drop % | Sharpe | Hold: per yr % | worst drop % | Sharpe |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for name, x in seg[part].items():
                e, s = x["excess"], x["strategy"]
                ru, ho = s.get("rule", {}), s.get("hold", {})
                L.append(f"| {name} | {e.get('n')} | {e.get('x5_pct', '–')} | {e.get('t', '–')} | {e.get('win5_pct', '–')} | {e.get('share_pct', '–')} | "
                         f"{ru.get('cagr', '–')} | {ru.get('mdd', '–')} | {ru.get('sharpe', '–')} | {ho.get('cagr', '–')} | {ho.get('mdd', '–')} | {ho.get('sharpe', '–')} |")
            L.append("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        OUT.mkdir(exist_ok=True)
        (OUT / "combo.md").write_text("# Run failed\n\n```\n" + traceback.format_exc() + "```\n")
