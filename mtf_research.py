"""
Does waiting for the 4H and 1H charts to line up improve entries on the daily signals?

Replays ~2 years (all the hourly history Yahoo keeps). For every daily Buy episode (stocks: dip-buy
set; crypto: 3-of-4 trend set, exactly the app's rules) it compares two ways of getting in:

  baseline   buy at the first hourly bar after the daily signal (its open)
  confirmed  wait inside the episode for the first hourly bar where the timing check is true and
             buy at its close; if it never comes, skip the trade

Both exit at the same moment: the first hourly bar after the daily signal ends (its open).
So the only difference is the entry. Timing checks tested (decided before running):

  atr      4H and 1H ATR stop both on the buy side (the IA ATR model, k = 0.5 x ATR(30) intraday)
  ribbon   4H and 1H trend ribbon both blue
  both     atr and ribbon
  dip_1h   1H RSI(2) below 10 (buy an intraday dip instead of an intraday turn-up)

Only data available at each moment is used: the daily signal from the last completed day, the
last completed 4H bar, and the current hourly bar's close. Costs: one round trip per trade
(stocks 0.10%, crypto 0.50%).

    python mtf_research.py     (Actions tab -> "Multi-timeframe test")
Writes research/mtf.md and research/mtf.json.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import context
import engine
import ia
import models
import settings
from backtest import download
from config import load_config
from data import _resample, to_4h
from signals import rsi

log = logging.getLogger("mtf")
OUT = Path(__file__).with_name("research")
COST = {"stock": 0.0010, "crypto": 0.0050}
CRYPTO_OK = ["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD", "AVAX-USD"]   # Yahoo symbols known to be right
CHECKS = ["atr", "ribbon", "both", "dip_1h"]
NY = "America/New_York"


def daily_buy(df: pd.DataFrame, asset: str, ctx: dict, cfg: dict) -> pd.Series:
    sc = engine.segment_config(cfg, f"{asset}-1d")
    v = pd.DataFrame({k: models.run(k, df, ctx)["vote"] for k in sc["models"]})
    if "buy_count" in sc:
        return (v > 0).sum(axis=1) >= sc["buy_count"]
    return v.mean(axis=1) > sc["buy"]


def close_times(idx: pd.DatetimeIndex, hours: float, asset: str) -> pd.DatetimeIndex:
    """When each bar's close is known (UTC)."""
    idx = idx.tz_convert("UTC")
    ct = idx + pd.Timedelta(hours=hours)
    if asset == "stock":
        cap = (idx.tz_convert(NY).normalize() + pd.Timedelta(hours=16)).tz_convert("UTC")
        ct = ct.where(ct <= cap, cap)
    return ct.as_unit("ns")


def states(df: pd.DataFrame) -> pd.DataFrame:
    _, up = ia.atr_stop(df)
    fast, slow = ia.ribbon(df)
    return pd.DataFrame({"atr": up.astype(bool), "ribbon": (fast > slow).fillna(False),
                         "rsi2": rsi(df["close"], 2)}, index=df.index)


def one_ticker(t: str, asset: str, ctx_daily: dict, cfg: dict) -> list[dict]:
    d = download(t, "1d")
    h = download(t, "1h")
    h4 = to_4h(h, t) if asset == "stock" else _resample(h, "4h")
    ctx = context.align(ctx_daily, d.index, asset, "1d")
    buy = daily_buy(d, asset, ctx, cfg)
    # daily close time
    if asset == "stock":
        dct = (d.index.tz_convert(NY).normalize() + pd.Timedelta(hours=16)).tz_convert("UTC")
    else:
        dct = d.index.tz_convert("UTC").normalize() + pd.Timedelta(days=1)
    daily = pd.DataFrame({"t": dct.tz_convert("UTC").as_unit("ns"), "buy": buy.values}).sort_values("t")
    daily["ep"] = (daily["buy"] & ~daily["buy"].shift(1, fill_value=False)).cumsum().where(daily["buy"])
    s1, s4 = states(h), states(h4)
    hh = pd.DataFrame({"t": close_times(h.index, 1, asset), "open": h["open"].values,
                       "close": h["close"].values, "atr1": s1["atr"].values, "rib1": s1["ribbon"].values,
                       "rsi1": s1["rsi2"].values, "start": h.index.tz_convert("UTC").as_unit("ns")}).sort_values("t")
    q4 = pd.DataFrame({"t": close_times(h4.index, 4, asset), "atr4": s4["atr"].values,
                       "rib4": s4["ribbon"].values}).sort_values("t")
    hh = pd.merge_asof(hh, q4, on="t", direction="backward")
    # daily signal in force for an hourly bar = the last daily close at or before the bar's START
    hh = pd.merge_asof(hh.sort_values("start"), daily.rename(columns={"t": "start"}), on="start", direction="backward")
    hh = hh.sort_values("t").reset_index(drop=True)
    hh = hh[hh["start"] >= hh["start"].iloc[0] + pd.Timedelta(days=30)]   # let 4H/1H indicators warm up
    hh["chk_atr"] = hh["atr1"].astype(bool) & hh["atr4"].fillna(False).astype(bool)
    hh["chk_ribbon"] = hh["rib1"].astype(bool) & hh["rib4"].fillna(False).astype(bool)
    hh["chk_both"] = hh["chk_atr"] & hh["chk_ribbon"]
    hh["chk_dip_1h"] = hh["rsi1"] < 10
    rows = []
    active = hh["buy"].fillna(False).astype(bool).to_numpy()
    eps = hh["ep"].to_numpy()
    for ep in pd.unique(eps[active]):
        idx = np.flatnonzero(active & (eps == ep))
        first, last = idx[0], idx[-1]
        if last + 1 >= len(hh):
            continue                                   # still open at the end of the data
        g = hh.iloc[idx]
        exit_px = hh["open"].iat[last + 1]
        base_px = g["open"].iat[0]
        r = {"ticker": t, "asset": asset, "start": str(g["start"].iat[0]), "hours": int(len(idx)),
             "base": exit_px / base_px - 1 - COST[asset]}
        for c in CHECKS:
            hit = np.flatnonzero(g[f"chk_{c}"].to_numpy())
            if len(hit):
                px = g["close"].iat[hit[0]]
                r[c] = exit_px / px - 1 - COST[asset]
                r[c + "_wait_h"] = int(hit[0])
                r[c + "_entry_vs_base"] = px / base_px - 1
            else:
                r[c] = None
        rows.append(r)
    log.info("%s: %d daily-signal episodes", t, len(rows))
    return rows


def summarize(rows: list[dict]) -> dict:
    df = pd.DataFrame(rows)
    if df.empty:
        return {}
    out = {"episodes": int(len(df)), "base_mean_pct": round(df["base"].mean() * 100, 2),
           "base_median_pct": round(df["base"].median() * 100, 2), "base_win_pct": round((df["base"] > 0).mean() * 100, 1),
           "base_sum_pct": round(df["base"].sum() * 100, 1)}
    day = pd.to_datetime(df["start"]).dt.floor("D")
    for c in CHECKS:
        m = df[c].notna()
        sub = df[m]
        N = int(m.sum())
        # Strategy-level comparison: a skipped trade earns 0 (cash). Comparing only the confirmed
        # trades would be biased (waiting selects the trades that already turned up / dipped).
        strat = df[c].fillna(0.0)
        diff = strat - df["base"]
        resid = (diff - diff.mean()).groupby(day).sum()
        G, n = len(resid), len(diff)
        se = math.sqrt((resid ** 2).sum() * G / max(G - 1, 1)) / n if G > 2 else float("nan")
        missed = df.loc[~m, "base"]
        out[c] = {
            "taken_pct": round(m.mean() * 100, 1),
            "mean_taken_pct": round(sub[c].mean() * 100, 2) if N else None,
            "win_pct": round((sub[c] > 0).mean() * 100, 1) if N else None,
            "sum_pct": round(strat.sum() * 100, 1),
            "vs_base_sum_pct": round(diff.sum() * 100, 1),
            "vs_base_per_signal_pct": round(diff.mean() * 100, 2),
            "t": round(diff.mean() / se, 2) if se == se and se > 0 else None,
            "entry_vs_base_median_pct": round(sub[c + "_entry_vs_base"].median() * 100, 2) if N else None,
            "median_wait_h": float(sub[c + "_wait_h"].median()) if N else None,
            "skipped_base_mean_pct": round(missed.mean() * 100, 2) if len(missed) else None,
        }
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = settings.apply(load_config(), settings.load(load_config()))
    groups = {"stock": cfg["watchlist"]["stocks"], "crypto": [t for t in cfg["watchlist"]["crypto"] if t in CRYPTO_OK]}
    res = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "segments": {}, "tickers": groups}
    all_rows = []
    for asset, tickers in groups.items():
        ctx_daily = context.fetch_daily(lambda s: download(s, "1d"), context.needs(asset))
        rows = []
        for t in tickers:
            try:
                rows += one_ticker(t, asset, ctx_daily, cfg)
            except Exception as e:
                log.error("%s failed: %s", t, e)
        res["segments"][asset] = summarize(rows)
        all_rows += rows
    OUT.mkdir(exist_ok=True)
    (OUT / "mtf.json").write_text(json.dumps({**res, "episodes": all_rows}, indent=1, default=str))
    L = [f"# Multi-timeframe confirmation test ({res['generated']})", "",
         "Same daily-signal trades, same exits; only the entry differs. Returns are per trade after costs.", ""]
    names = {"atr": "4H + 1H ATR stop on buy side", "ribbon": "4H + 1H ribbon blue", "both": "ATR and ribbon",
             "dip_1h": "1H RSI(2) below 10 (intraday dip)"}
    for asset, s in res["segments"].items():
        if not s:
            continue
        L += [f"## {asset}", "", f"{s['episodes']} daily-signal trades. Buy at the next open: average {s['base_mean_pct']}% "
              f"per trade (median {s['base_median_pct']}%), {s['base_win_pct']}% winners, total {s['base_sum_pct']}%.", "",
              "| Timing check | Trades taken | Avg per trade taken | Winners | Total | Total vs buying every signal (t) | Entry vs next open (median) | Median wait (h) | Skipped trades would have made (avg) |",
              "|---|---|---|---|---|---|---|---|---|"]
        for c in CHECKS:
            x = s[c]
            L.append(f"| {names[c]} | {x['taken_pct']}% | {x['mean_taken_pct']}% | {x['win_pct']}% | {x['sum_pct']}% | "
                     f"{x['vs_base_sum_pct']:+}% ({x['t']}) | {x['entry_vs_base_median_pct']}% | {x['median_wait_h']} | "
                     f"{x['skipped_base_mean_pct']}% |")
        L.append("")
    (OUT / "mtf.md").write_text("\n".join(L))
    log.info("done")


if __name__ == "__main__":
    main()
