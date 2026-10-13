"""
Model research: test every model separately for each segment and keep only what holds up.

Segments: stock-1d, stock-4h, stock-1h, crypto-1d, crypto-4h, crypto-1h.

Method (decided before looking at results):
  * Each model's vote is computed for every bar using only past data (see models.py).
  * "Bullish" bars are judged by the NEXT bar's return (you act at the close, you earn the next bar).
  * Excess return = next-bar return minus that ticker's own average in the same period, so a model
    doesn't look good just because NVDA went up a lot. t-stats are clustered by calendar day, which
    stops 13 correlated stocks moving on the same day from counting as 13 independent wins.
  * Long-only test: hold the asset only while the model is bullish, pay costs on every switch
    (stocks 0.05%/side, crypto 0.25%/side), and compare the Sharpe ratio with simply holding.
  * TRAIN / TEST split: daily = before 2021 / 2021 onwards; intraday = first half / second half of
    the ~2 years available.
  * Selection uses TRAIN ONLY. A model is kept for a segment if its bullish bars beat the ticker's
    average with t >= 1.5 AND holding only while it's bullish improved the Sharpe ratio for the
    median ticker AND for at least half the tickers. (On random prices a looser rule kept ~20% of
    models, so it was tightened before any real data was run.) The kept models form the segment's
    ensemble, which is then judged on TEST data it has never seen.

    python research_backtest.py [--segments stock-1d crypto-1d ...]

Writes research/results.json and research/summary.md. No guarantee about the future.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import context
import models
from backtest import download
from config import load_config

log = logging.getLogger("research")
OUT = Path(__file__).with_name("research")
COST = {"stock": 0.0005, "crypto": 0.0025}
BARS_PER_YEAR = {("stock", "1d"): 252, ("crypto", "1d"): 365, ("stock", "4h"): 504, ("crypto", "4h"): 2190,
                 ("stock", "1h"): 1764, ("crypto", "1h"): 8760}
DAILY_SPLIT = pd.Timestamp("2021-01-01", tz="UTC")
WARMUP = 250
ORIGINAL = ["trend_classic", "meanrev_z", "confluence", "atr_layers", "momentum_classic"]
SEGMENT_MODELS = {   # which models make sense to test where (gates need their outside data)
    "stock": ["rsi2_pullback", "ibs_reversal", "turn_of_month", "market_regime", "vix_backwardation",
              "tsmom28", "sma_ensemble", "donchian_ensemble", "high_breakout_trail"] + ORIGINAL,
    "crypto": ["tsmom28", "sma_ensemble", "donchian_ensemble", "btc_trend_gate", "high_breakout_trail",
               "rsi2_pullback", "ibs_reversal", "turn_of_month"] + ORIGINAL,
}


# Model sets chosen from the PUBLISHED research (before our own test), evaluated as a whole.
PRESETS = {
    "stock": {"pullback_any": (["rsi2_pullback", "ibs_reversal", "vix_backwardation"], 0.0)},
    "crypto": {"trend4_majority": (["tsmom28", "sma_ensemble", "donchian_ensemble", "btc_trend_gate"], 0.0),
               "trend4_3of4": (["tsmom28", "sma_ensemble", "donchian_ensemble", "btc_trend_gate"], 0.5)},
}


def old_ensemble(v: pd.DataFrame) -> pd.Series:
    """The original Signal Desk rule (3 of 5 agree + falling-knife guard) as a vote."""
    o = v[ORIGINAL]
    bull, bear = (o > 0).sum(axis=1), (o < 0).sum(axis=1)
    buy = (bull >= 3) & (bull > bear) & ~((o["trend_classic"] < 0) & (o["momentum_classic"] < 0))
    sell = (bear >= 3) & (bear > bull) & ~((o["trend_classic"] > 0) & (o["momentum_classic"] > 0))
    return pd.Series(np.where(buy, 1, np.where(sell, -1, 0)), index=v.index)


def one_ticker(ticker: str, asset: str, tf: str, ctx_daily: dict) -> pd.DataFrame:
    df = download(ticker, tf)
    ctx = context.align(ctx_daily, df.index, asset, tf)
    votes = {k: models.run(k, df, ctx)["vote"] for k in SEGMENT_MODELS[asset]}
    v = pd.DataFrame(votes, index=df.index)
    v["old_ensemble"] = old_ensemble(v)
    v["r_next"] = df["close"].pct_change().shift(-1)
    v["ticker"] = ticker
    return v.iloc[WARMUP:].dropna(subset=["r_next"])


def split_point(bars: pd.DataFrame, tf: str) -> pd.Timestamp:
    if tf in ("1d", "1wk"):
        return DAILY_SPLIT
    t = bars.index
    return t.min() + (t.max() - t.min()) / 2


def stats(bars: pd.DataFrame, col: str, asset: str, tf: str) -> dict:
    """Bullish/bearish excess returns (clustered by day) and long-only Sharpe vs holding."""
    b = bars.copy()
    b["x"] = b["r_next"] - b.groupby("ticker")["r_next"].transform("mean")
    day = b.index.floor("D")
    out = {}
    for side, mask in (("bull", b[col] > 0), ("bear", b[col] < 0)):
        sub = b[mask]
        if len(sub) < 20:
            out[side] = {"n": int(len(sub))}
            continue
        # t-stat of the pooled mean with standard errors clustered by calendar day (bars on the same
        # day across tickers/hours are not independent).
        mu = float(sub["x"].mean())
        resid = (sub["x"] - mu).groupby(np.asarray(day[mask.values])).sum()
        G, N = len(resid), len(sub)
        se = float(np.sqrt((resid ** 2).sum() * G / max(G - 1, 1)) / N) if G > 2 else np.nan
        out[side] = {"n": int(N), "days": int(G), "share": round(float(mask.mean()) * 100, 1),
                     "excess_bp": round(mu * 1e4, 2),
                     "t": round(mu / se, 2) if se and se > 0 else None}
    # long-only strategy per ticker
    bpy, cost = BARS_PER_YEAR[(asset, tf)], COST[asset]
    rows = []
    for t, g in b.groupby("ticker"):
        pos = (g[col] > 0).astype(float)
        strat = pos * g["r_next"] - cost * pos.diff().abs().fillna(pos.iloc[0])
        hold = g["r_next"]
        sh = lambda s: float(s.mean() / s.std() * np.sqrt(bpy)) if s.std() > 0 else 0.0
        eq = (1 + strat).cumprod()
        heq = (1 + hold).cumprod()
        years = len(g) / bpy
        rows.append({"ticker": t, "sharpe": sh(strat), "hold_sharpe": sh(hold),
                     "ann": float(eq.iloc[-1] ** (1 / years) - 1) if years > 0 else 0,
                     "hold_ann": float(heq.iloc[-1] ** (1 / years) - 1) if years > 0 else 0,
                     "mdd": float((eq / eq.cummax() - 1).min()), "hold_mdd": float((heq / heq.cummax() - 1).min()),
                     "exposure": float(pos.mean()), "switches": int(pos.diff().abs().sum())})
    r = pd.DataFrame(rows)
    out["long_only"] = {
        "median_sharpe": round(float(r["sharpe"].median()), 2),
        "median_hold_sharpe": round(float(r["hold_sharpe"].median()), 2),
        "median_sharpe_gain": round(float((r["sharpe"] - r["hold_sharpe"]).median()), 2),
        "share_better": round(float((r["sharpe"] > r["hold_sharpe"]).mean()), 2),
        "median_ann_pct": round(float(r["ann"].median()) * 100, 1),
        "median_hold_ann_pct": round(float(r["hold_ann"].median()) * 100, 1),
        "median_mdd_pct": round(float(r["mdd"].median()) * 100, 1),
        "median_hold_mdd_pct": round(float(r["hold_mdd"].median()) * 100, 1),
        "median_exposure_pct": round(float(r["exposure"].median()) * 100, 0),
        "median_switches_per_year": round(float((r["switches"] / (len(b) / max(1, r.shape[0]) / bpy)).median()), 1),
    }
    return out


def consistent(m: dict) -> bool:
    """Right direction in BOTH halves: bullish bars beat average, bearish bars (if any) lag it."""
    ok = True
    for part in ("train", "test"):
        bull, bear = m[part]["bull"], m[part]["bear"]
        if bull.get("n", 0) < 20 or (bull.get("excess_bp") or 0) <= 0:
            return False
        if bear.get("n", 0) >= 20 and (bear.get("excess_bp") or 0) >= 0:
            ok = False
    return ok


def keep(s: dict) -> bool:
    bull, lo = s["bull"], s["long_only"]
    if bull.get("n", 0) < 20 or bull.get("excess_bp") is None or bull["excess_bp"] <= 0:
        return False
    return (bull.get("t") or 0) >= 1.5 and lo["median_sharpe_gain"] > 0 and lo["share_better"] >= 0.5


def run_segment(asset: str, tf: str, tickers: list[str], ctx_daily: dict, workers: int) -> dict:
    frames, failed = [], []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(one_ticker, t, asset, tf, ctx_daily): t for t in tickers}
        for f in as_completed(futs):
            try:
                frames.append(f.result())
            except Exception as e:
                failed.append(f"{futs[f]}: {e}")
                log.error("%s-%s %s failed: %s", asset, tf, futs[f], e)
    bars = pd.concat(frames).sort_index()
    cut = split_point(bars, tf)
    train, test = bars[bars.index < cut], bars[bars.index >= cut]
    cols = SEGMENT_MODELS[asset] + ["old_ensemble"]
    res = {"split": str(cut.date()), "tickers": sorted(bars["ticker"].unique().tolist()), "failed": failed,
           "train_period": [str(train.index.min().date()), str(train.index.max().date())],
           "test_period": [str(test.index.min().date()), str(test.index.max().date())],
           "models": {}}
    for c in cols:
        res["models"][c] = {"train": stats(train, c, asset, tf), "test": stats(test, c, asset, tf)}
    kept = [c for c in SEGMENT_MODELS[asset] if keep(res["models"][c]["train"])]
    res["kept"] = kept
    res["consistent"] = [c for c in SEGMENT_MODELS[asset] if consistent(res["models"][c])]
    if kept:
        for part, data in (("train", train), ("test", test)):
            d = data.copy()
            d["new_ensemble"] = np.sign(d[kept].mean(axis=1)).astype(int)
            res.setdefault("ensemble", {})[part] = stats(d, "new_ensemble", asset, tf)
    for name, (cols_, thr) in PRESETS[asset].items():
        for part, data in (("train", train), ("test", test)):
            d = data.copy()
            m = d[cols_].mean(axis=1)
            d[name] = np.where(m > thr, 1, np.where(m < -thr if thr else m < 0, -1, 0))
            res.setdefault("presets", {}).setdefault(name, {"models": cols_, "threshold": thr})[part] = stats(d, name, asset, tf)
    log.info("%s-%s: kept %s", asset, tf, kept)
    return res


def markdown(all_res: dict, meta: dict) -> str:
    L = [f"# Model research — {meta['generated']}", "",
         "Bullish/bearish = next-bar return vs the ticker's own average, in basis points (1 bp = 0.01%), "
         "with a t-stat clustered by day (|t| ≥ 2 is reasonably convincing). Long-only = hold only while "
         "bullish, after costs; Sharpe compared with simply holding.", "",
         "Models are **selected on TRAIN only**; the ensemble's TEST row is the honest out-of-sample result.", ""]
    for seg, r in all_res.items():
        L += [f"## {seg}", "", f"Train {r['train_period'][0]} → {r['train_period'][1]} · Test {r['test_period'][0]} → "
              f"{r['test_period'][1]} · {len(r['tickers'])} tickers", "",
              f"**Kept (from train, strict rule):** {', '.join(r['kept']) or 'none'}", "",
              f"**Right direction in both halves:** {', '.join(r['consistent']) or 'none'}", ""]
        if r.get("ensemble"):
            for part in ("train", "test"):
                e = r["ensemble"][part]["long_only"]
                b = r["ensemble"][part]["bull"]
                L.append(f"- Ensemble **{part}**: Sharpe {e['median_sharpe']} vs hold {e['median_hold_sharpe']} "
                         f"(better on {int(e['share_better'] * 100)}% of tickers); return {e['median_ann_pct']}%/yr vs "
                         f"{e['median_hold_ann_pct']}%; worst dip {e['median_mdd_pct']}% vs {e['median_hold_mdd_pct']}%; "
                         f"invested {e['median_exposure_pct']:.0f}%; bullish excess {b.get('excess_bp')} bp (t {b.get('t')})")
            L.append("")
        for name, pr in r.get("presets", {}).items():
            L.append(f"- Preset **{name}** ({', '.join(pr['models'])}; bullish when average vote > {pr['threshold']}):")
            for part in ("train", "test"):
                e, b, br = pr[part]["long_only"], pr[part]["bull"], pr[part]["bear"]
                L.append(f"  - {part}: bullish {b.get('excess_bp')} bp (t {b.get('t')}), bearish {br.get('excess_bp')} bp "
                         f"(t {br.get('t')}); long-only Sharpe {e['median_sharpe']} vs hold {e['median_hold_sharpe']}, "
                         f"return {e['median_ann_pct']}%/yr vs {e['median_hold_ann_pct']}%, worst dip {e['median_mdd_pct']}% "
                         f"vs {e['median_hold_mdd_pct']}%, invested {e['median_exposure_pct']:.0f}%")
        L.append("")
        L += ["| Model | Train bull bp (t) | Train bear bp (t) | Train Sharpe gain | Test bull bp (t) | Test bear bp (t) | Test Sharpe gain | Test invested |",
              "|---|---|---|---|---|---|---|---|"]
        for m, s in r["models"].items():
            tr, te = s["train"], s["test"]
            f = lambda x: f"{x.get('excess_bp', '–')} ({x.get('t', '–')})" if x.get("n", 0) >= 20 else "–"
            mark = " ✅" if m in r["kept"] else ""
            L.append(f"| {m}{mark} | {f(tr['bull'])} | {f(tr['bear'])} | {tr['long_only']['median_sharpe_gain']} | "
                     f"{f(te['bull'])} | {f(te['bear'])} | {te['long_only']['median_sharpe_gain']} | "
                     f"{te['long_only']['median_exposure_pct']:.0f}% |")
        L.append("")
    L.append("_Personal research only. Past results don't guarantee future results._")
    return "\n".join(L)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", nargs="*",
                    default=["stock-1d", "crypto-1d", "stock-4h", "crypto-4h", "stock-1h", "crypto-1h"])
    ap.add_argument("--tickers", nargs="*")
    args = ap.parse_args()
    cfg = load_config()
    workers = int(os.environ.get("BACKTEST_WORKERS", os.cpu_count() or 2))
    t0 = time.time()
    ctx_daily = {}
    for asset in ("stock", "crypto"):
        ctx_daily[asset] = context.fetch_daily(lambda s: download(s, "1d"), context.needs(asset))
    all_res = {}
    for seg in args.segments:
        asset, tf = seg.split("-")
        tickers = [t for t in (args.tickers or cfg["watchlist"]["stocks"] + cfg["watchlist"]["crypto"])
                   if (t in cfg["watchlist"]["crypto"] or t.endswith("-USD")) == (asset == "crypto")]
        all_res[seg] = run_segment(asset, tf, tickers, ctx_daily[asset], workers)
        log.info("%s done (%.0fs)", seg, time.time() - t0)
    meta = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "costs": COST,
            "daily_split": str(DAILY_SPLIT.date()), "selection_rule": keep.__doc__ or "see module docstring",
            "params": {k: m.defaults for k, m in models.MODELS.items()}}
    OUT.mkdir(exist_ok=True)
    (OUT / "results.json").write_text(json.dumps({"meta": meta, "segments": all_res}, indent=1, default=str))
    (OUT / "summary.md").write_text(markdown(all_res, meta))
    log.info("Done in %.0fs", time.time() - t0)


if __name__ == "__main__":
    main()
