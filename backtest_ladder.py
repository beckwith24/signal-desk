"""
Backtest the layer-in / layer-out ladder against simpler ways to invest the same money.

Three strategies on each ticker, each starting with $1 of cash and paying a fee on every trade:

  ladder   add 1/3 of available cash at L-2, L-3, L-4; trim 1/3 of the position at L+2, L+3, L+4
           (buy ladder resets once price is back above the anchor, sell ladder once it's below)
  core     same ladder, but layer-out only trims half the position (1/6 at each sell layer), keeping a core
  in_only  layer in at L-2/-3/-4, never sell (a way to time entries for money you want invested anyway)
  lump     put all cash in at the first L-2; sell everything at the first L+2
  hold     buy at the start and never sell

Layers use exactly the live definition: distance of the close from the 50-bar average, in units of
the 14-bar ATR, computed only from data up to each bar. Trades happen at that bar's close.

    python backtest_ladder.py                       # daily (10y) and 4h (~2y), all tickers
    python backtest_ladder.py --tf 1d --tickers NVDA BTC-USD

Writes backtest/ladder_results.json and backtest/ladder_summary.md. Past results guarantee nothing.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import download
from config import load_config
from data import is_crypto
from signals import atr, sma

log = logging.getLogger("ladder_bt")
OUT = Path(__file__).with_name("backtest")
FEE = 0.001     # 0.1% per trade
MODES = ("ladder", "core", "in_only", "lump", "hold")
NAMES = {"ladder": "Ladder", "core": "Ladder, keep half", "in_only": "Layer-in only", "lump": "Lump sum", "hold": "Buy & hold"}
WARMUP = 250


def distance(df: pd.DataFrame, cfg: dict) -> np.ndarray:
    p = cfg["models"]["atr_layers"]
    anchor = sma(df["close"], p["anchor_ma"])
    step = p["layer_step"] * atr(df, p["atr_period"])
    return ((df["close"] - anchor) / step).values


def simulate(close: np.ndarray, dist: np.ndarray, lc: dict, mode: str) -> dict:
    buy_l, sell_l = lc["buy_layers"], lc["sell_layers"]
    nb_total, ns_total = len(buy_l), len(sell_l)
    cash, sh = 1.0, 0.0
    b_tier = s_tier = 0
    tranche = sell_tranche = 0.0
    trades = 0
    eq, exposure = [], []
    for i in range(WARMUP, len(close)):
        px, d = close[i], dist[i]
        if mode == "hold":
            if i == WARMUP:
                sh, cash, trades = (1 - FEE) / px, 0.0, 1
        elif not np.isnan(d):
            if d >= 0:
                b_tier = 0
            if d <= 0:
                s_tier = 0
            nb = sum(d <= L for L in buy_l)
            ns = sum(d >= L for L in sell_l)
            if mode in ("ladder", "core", "in_only"):
                while b_tier < nb:
                    if b_tier == 0:
                        tranche = cash / nb_total
                    amt = cash if b_tier == nb_total - 1 else min(tranche, cash)
                    if amt > 1e-9:
                        sh += amt * (1 - FEE) / px
                        cash -= amt
                        trades += 1
                    b_tier += 1
                while s_tier < ns and mode != "in_only":
                    if s_tier == 0:
                        sell_tranche = sh / ns_total * (0.5 if mode == "core" else 1.0)
                    q = sh if (s_tier == ns_total - 1 and mode == "ladder") else min(sell_tranche, sh)
                    if q > 1e-12:
                        cash += q * px * (1 - FEE)
                        sh -= q
                        trades += 1
                    s_tier += 1
            else:  # lump
                if b_tier == 0 and nb >= 1 and cash > 1e-9:
                    sh += cash * (1 - FEE) / px
                    cash = 0.0
                    trades += 1
                b_tier = max(b_tier, nb)
                if s_tier == 0 and ns >= 1 and sh > 1e-12:
                    cash += sh * px * (1 - FEE)
                    sh = 0.0
                    trades += 1
                s_tier = max(s_tier, ns)
        value = cash + sh * px
        eq.append(value)
        exposure.append(sh * px / value if value > 0 else 0)
    eq = np.array(eq)
    peak = np.maximum.accumulate(eq)
    return {"return": round((eq[-1] - 1) * 100, 1),
            "max_drawdown": round(float(((eq / peak) - 1).min()) * 100, 1),
            "avg_invested": round(float(np.mean(exposure)) * 100, 1),
            "trades": trades,
            "equity": eq}


def run_one(ticker: str, tf: str, cfg: dict) -> dict:
    df = download(ticker, tf)
    close, dist = df["close"].values, distance(df, cfg)
    out = {"ticker": ticker, "tf": tf, "asset": "crypto" if is_crypto(ticker, cfg) else "stock",
           "start": str(df.index[WARMUP].date()), "end": str(df.index[-1].date()),
           "years": round((df.index[-1] - df.index[WARMUP]).days / 365.25, 1)}
    curves = {}
    for mode in MODES:
        r = simulate(close, dist, cfg["ladder"], mode)
        curves[mode] = r.pop("equity")
        out[mode] = r
    # Per year of time invested, to compare strategies that sit in cash a lot with ones that don't.
    for mode in ("ladder", "core", "in_only", "lump"):
        inv = out[mode]["avg_invested"] / 100
        out[mode]["return_per_invested"] = round(out[mode]["return"] / inv, 1) if inv > 0.01 else None
    # How many full buy cycles reached each layer (how often the deeper layers actually get used).
    d = dist[WARMUP:]
    cycles, depth, deepest = 0, [0, 0, 0], 0
    in_cycle = False
    for x in d:
        if np.isnan(x):
            continue
        if x >= 0 and in_cycle:
            for k in range(deepest):
                depth[k] += 1
            in_cycle, deepest = False, 0
        n = sum(x <= L for L in cfg["ladder"]["buy_layers"])
        if n:
            in_cycle = True
            deepest = max(deepest, n)
    if in_cycle:
        for k in range(deepest):
            depth[k] += 1
    out["dip_cycles"] = {"reached_L-2": depth[0], "reached_L-3": depth[1], "reached_L-4": depth[2]}
    return out


def summarise(rows: list[dict]) -> dict:
    df = pd.DataFrame([{**{k: r[k] for k in ("ticker", "tf", "asset")},
                        **{f"{m}_{k}": r[m][k] for m in MODES
                           for k in ("return", "max_drawdown", "avg_invested", "trades")}} for r in rows])
    out = {}
    for (tf, asset), g in list(df.groupby(["tf", "asset"])) + [((tf, "all"), g) for tf, g in df.groupby("tf")]:
        out.setdefault(tf, {})[asset] = {
            "tickers": int(len(g)),
            "median_return": {m: float(g[f"{m}_return"].median()) for m in MODES},
            "median_max_drawdown": {m: float(g[f"{m}_max_drawdown"].median()) for m in MODES},
            "median_avg_invested": {m: float(g[f"{m}_avg_invested"].median()) for m in MODES},
            "ladder_beats_lump": int((g["ladder_return"] > g["lump_return"]).sum()),
            "ladder_beats_hold": int((g["ladder_return"] > g["hold_return"]).sum()),
            "ladder_smaller_drawdown_than_lump": int((g["ladder_max_drawdown"] > g["lump_max_drawdown"]).sum()),
            "ladder_smaller_drawdown_than_hold": int((g["ladder_max_drawdown"] > g["hold_max_drawdown"]).sum()),
            "core_beats_hold": int((g["core_return"] > g["hold_return"]).sum()),
            "in_only_beats_hold": int((g["in_only_return"] > g["hold_return"]).sum()),
            "core_beats_ladder": int((g["core_return"] > g["ladder_return"]).sum()),
        }
    return out


def markdown(rows: list[dict], summary: dict, meta: dict) -> str:
    L = [f"# Layer-in / layer-out backtest — {meta['generated']}", "",
         "Each strategy starts with $1 and pays 0.1% per trade. **Return** = total gain over the period. "
         "**Max dip** = worst fall from a high. **Invested** = average share of money in the market.", ""]
    for tf, assets in summary.items():
        for asset, s in assets.items():
            L += [f"## {tf} — {asset} ({s['tickers']} tickers, medians)", "",
                  "| | " + " | ".join(NAMES[m] for m in MODES) + " |", "|---|" + "---|" * len(MODES),
                  "| Return | " + " | ".join(f"{s['median_return'][m]:.1f}%" for m in MODES) + " |",
                  "| Max dip | " + " | ".join(f"{s['median_max_drawdown'][m]:.1f}%" for m in MODES) + " |",
                  "| Invested | " + " | ".join(f"{s['median_avg_invested'][m]:.0f}%" for m in MODES) + " |",
                  "",
                  f"Ladder beat lump sum on {s['ladder_beats_lump']}/{s['tickers']}, beat buy & hold on "
                  f"{s['ladder_beats_hold']}/{s['tickers']}; smaller worst dip than lump sum on "
                  f"{s['ladder_smaller_drawdown_than_lump']}/{s['tickers']} and than buy & hold on "
                  f"{s['ladder_smaller_drawdown_than_hold']}/{s['tickers']}. Keep-half beat buy & hold on "
                  f"{s['core_beats_hold']}/{s['tickers']}; layer-in only beat buy & hold on {s['in_only_beats_hold']}/{s['tickers']}.", ""]
    L += ["## By ticker", "", "| Ticker | TF | Years | Ladder | Keep half | In only | Lump | Hold | Ladder dip | Keep-half dip | Hold dip | Dips to L-2 / L-3 / L-4 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["tf"], r["ticker"])):
        c = r["dip_cycles"]
        L.append(f"| {r['ticker']} | {r['tf']} | {r['years']} | {r['ladder']['return']}% | {r['core']['return']}% | "
                 f"{r['in_only']['return']}% | {r['lump']['return']}% | {r['hold']['return']}% | "
                 f"{r['ladder']['max_drawdown']}% | {r['core']['max_drawdown']}% | {r['hold']['max_drawdown']}% | "
                 f"{c['reached_L-2']} / {c['reached_L-3']} / {c['reached_L-4']} |")
    L += ["", "_Personal research only. Past results don't guarantee future results._"]
    return "\n".join(L)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", nargs="*", default=["1d", "4h"])
    ap.add_argument("--tickers", nargs="*")
    args = ap.parse_args()
    cfg = load_config()
    tickers = args.tickers or cfg["watchlist"]["stocks"] + cfg["watchlist"]["crypto"]
    rows, failed = [], []
    for tf in args.tf:
        for t in tickers:
            try:
                rows.append(run_one(t, tf, cfg))
                log.info("%s %s done", t, tf)
            except Exception as e:
                log.error("%s %s failed: %s", t, tf, e)
                failed.append(f"{t} {tf}: {e}")
            time.sleep(0.5)
    summary = summarise(rows)
    meta = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "fee": FEE,
            "ladder": cfg["ladder"], "anchor_ma": cfg["models"]["atr_layers"]["anchor_ma"], "failed": failed}
    OUT.mkdir(exist_ok=True)
    (OUT / "ladder_results.json").write_text(json.dumps({"meta": meta, "summary": summary, "rows": rows}, indent=1))
    (OUT / "ladder_summary.md").write_text(markdown(rows, summary, meta))
    log.info("Done: %d results, %d failed", len(rows), len(failed))


if __name__ == "__main__":
    main()
