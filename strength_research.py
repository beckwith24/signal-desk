"""
Is a Strong Buy actually stronger than a Buy?

Uses the same data, models, costs and train/test split as research_backtest.py, and compares the
days in each signal level:

  stocks (3 dip models)   Buy = exactly 1 fires        Strong Buy = 2 or 3 fire
  crypto (4 trend models) Buy = 3 of 4 bullish, none bearish     Strong Buy = all 4 bullish

For each level: next-day return above the ticker's own average (bp, t clustered by day), and the
average return over the next 5 days. Writes research/strength.md and research/strength.json.

    python strength_research.py     (Actions tab -> "Signal strength test")
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
import settings
from backtest import download
from config import load_config
from research_backtest import DAILY_SPLIT, one_ticker

log = logging.getLogger("strength")
OUT = Path(__file__).with_name("research")
CRYPTO_OK = ["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD", "AVAX-USD"]   # long, reliable Yahoo histories


def clustered(x: pd.Series, day: pd.Series) -> tuple[float, float, int]:
    mu = float(x.mean())
    resid = (x - mu).groupby(day.values).sum()
    G, N = len(resid), len(x)
    se = math.sqrt((resid ** 2).sum() * G / max(G - 1, 1)) / N if G > 2 else float("nan")
    return mu, (mu / se if se and se > 0 else float("nan")), G


def levels(bars: pd.DataFrame, asset: str, cfg: dict) -> pd.Series:
    """The live engine's levels, replayed over history (same rules as engine.evaluate)."""
    sc = engine.segment_config(cfg, f"{asset}-1d")
    v = bars[sc["models"]]
    if asset == "stock":
        n = (v > 0).sum(axis=1)
        panic = bars[sc["panic"]] > 0 if sc.get("panic") in bars else pd.Series(False, index=bars.index)
        return pd.Series(np.select([panic, n >= 2, n == 1], ["Panic Buy", "Strong Buy", "Buy"], "Hold"), index=bars.index)
    m = v.mean(axis=1)
    gate = bars[sc["gate"]] > 0 if sc.get("gate") in bars else pd.Series(True, index=bars.index)
    return pd.Series(np.select([(m >= 1.0) & gate, m > 0.5], ["Strong Buy", "Buy"], "Hold"), index=bars.index)


def summarize(bars: pd.DataFrame) -> dict:
    b = bars.copy()
    b["x1"] = b["r_next"] - b.groupby("ticker")["r_next"].transform("mean")
    b["x5"] = b["r5"] - b.groupby("ticker")["r5"].transform("mean")
    day = pd.Series(b.index.floor("D"), index=b.index)
    out = {}
    for lv in ("Hold", "Buy", "Strong Buy", "Panic Buy"):
        m = b["level"] == lv
        if m.sum() < 20:
            out[lv] = {"days": int(m.sum())}
            continue
        mu1, t1, g = clustered(b.loc[m, "x1"], day[m])
        mu5, t5, _ = clustered(b.loc[m, "x5"].dropna(), day[m & b["x5"].notna()])
        out[lv] = {"ticker_days": int(m.sum()), "dates": g, "share_pct": round(m.mean() * 100, 1),
                   "next_day_excess_bp": round(mu1 * 1e4, 1), "t": round(t1, 2),
                   "next_5d_excess_pct": round(mu5 * 100, 2), "t5": round(t5, 2),
                   "next_5d_win_pct": round((b.loc[m, "r5"] > 0).mean() * 100, 1)}
    # Strong Buy vs Buy directly (difference of means, clustered by day)
    sb, bu = b[b["level"] == "Strong Buy"], b[b["level"] == "Buy"]
    if len(sb) >= 20 and len(bu) >= 20:
        out["strong_minus_buy_next_day_bp"] = round((sb["x1"].mean() - bu["x1"].mean()) * 1e4, 1)
        out["strong_minus_buy_5d_pct"] = round((sb["x5"].mean() - bu["x5"].mean()) * 100, 2)
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = settings.apply(load_config(), settings.load(load_config()))
    groups = {"stock": cfg["watchlist"]["stocks"], "crypto": [t for t in cfg["watchlist"]["crypto"] if t in CRYPTO_OK]}
    res = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "tickers": groups, "segments": {}}
    for asset, tickers in groups.items():
        ctx_daily = context.fetch_daily(lambda s: download(s, "1d"), context.needs(asset))
        frames = []
        for t in tickers:
            try:
                v = one_ticker(t, asset, "1d", ctx_daily)
                g = (1 + v["r_next"])[::-1].rolling(5).apply(np.prod, raw=True)[::-1] - 1
                v["r5"] = g                      # return from this close to 5 bars later
                frames.append(v)
            except Exception as e:
                log.error("%s failed: %s", t, e)
        bars = pd.concat(frames).sort_index()
        bars["level"] = levels(bars, asset, cfg)
        res["segments"][asset] = {"all": summarize(bars),
                                  "train": summarize(bars[bars.index < DAILY_SPLIT]),
                                  "test": summarize(bars[bars.index >= DAILY_SPLIT])}
    OUT.mkdir(exist_ok=True)
    (OUT / "strength.json").write_text(json.dumps(res, indent=1, default=str))
    L = [f"# Is a Strong Buy stronger than a Buy? ({res['generated']})", "",
         "Excess = return above that ticker's own average over the same years. t clustered by date. "
         "Train = before 2021, test = 2021 on.", ""]
    for asset, seg in res["segments"].items():
        L += [f"## {asset}", "", "| Period | Level | Ticker-days | Next day (bp) | t | Next 5 days | t | 5-day winners |",
              "|---|---|---|---|---|---|---|---|"]
        for part in ("train", "test", "all"):
            for lv in ("Hold", "Buy", "Strong Buy", "Panic Buy"):
                x = seg[part].get(lv, {})
                if "t" not in x:
                    L.append(f"| {part} | {lv} | {x.get('days', 0)} | – | – | – | – | – |"); continue
                L.append(f"| {part} | {lv} | {x['ticker_days']} | {x['next_day_excess_bp']} | {x['t']} | "
                         f"{x['next_5d_excess_pct']}% | {x['t5']} | {x['next_5d_win_pct']}% |")
        L += ["", f"Strong Buy minus Buy (all years): next day {seg['all'].get('strong_minus_buy_next_day_bp')} bp, "
              f"next 5 days {seg['all'].get('strong_minus_buy_5d_pct')}%", ""]
    (OUT / "strength.md").write_text("\n".join(L))
    log.info("done")


if __name__ == "__main__":
    main()
