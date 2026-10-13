"""
Backtest: replay the five models bar by bar over past prices and measure what happened next.

For every bar we run exactly the same evaluate() the live scanner uses, on only the data that
existed at that moment (a rolling window ending at that bar, so there is no look-ahead). Then for
each NEW signal (the moment an alert would have fired) we record the price move over the next
few days/weeks, and compare it with the average move over all bars (the "baseline"). A signal is
only useful if it beats the baseline.

    python backtest.py                 # all tickers, daily (10y) + 4h/1h (last ~2 years)
    python backtest.py --tf 1d         # just daily
    python backtest.py --tickers NVDA BTC-USD

Writes backtest/results.json, backtest/events.csv and backtest/summary.md.
No trading costs or slippage are included. Past results don't guarantee anything.
"""
from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from config import load_config
from data import _normalize, _resample, is_crypto
from signals import MIN_BARS, evaluate

log = logging.getLogger("backtest")
OUT = Path(__file__).with_name("backtest")
WINDOW = 400          # bars of history given to the models at each step (live scans use a similar amount)
WARMUP = 250          # first bar we score (so the 200-bar moving average exists)
HORIZONS = {          # forward windows in calendar time
    "1d": [("1 week", "7D"), ("2 weeks", "14D"), ("1 month", "30D")],
    "4h": [("1 day", "1D"), ("3 days", "3D"), ("1 week", "7D")],
    "1h": [("1 day", "1D"), ("2 days", "2D"), ("5 days", "5D")],
}
GROUPS = {"Strong Buy": "buy", "Buy": "buy", "Watch ↑": "watch_up",
          "Strong Sell": "sell", "Sell": "sell", "Watch ↓": "watch_down", "Hold": "hold"}


# --------------------------------------------------------------------------- data
def download(ticker: str, tf: str) -> pd.DataFrame:
    import yfinance as yf

    period, interval = ("10y", "1d") if tf == "1d" else ("729d", "1h")  # Yahoo keeps ~2 years of hourly bars
    for attempt in range(3):
        try:
            df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
            if df is not None and not df.empty:
                df = _normalize(df)
                return _resample(df, "4h") if tf == "4h" else df
        except Exception as e:
            log.warning("%s %s download failed: %s", ticker, tf, e)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"no data for {ticker} {tf}")


# --------------------------------------------------------------------------- replay
def replay(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Action/score at every bar using only data up to that bar."""
    rows = []
    start = max(WARMUP, MIN_BARS)
    for i in range(start, len(df)):
        w = df.iloc[max(0, i + 1 - WINDOW): i + 1]
        r = evaluate(w, cfg)
        rows.append((df.index[i], float(df["close"].iat[i]), r["action"], r["rank"], r["score"],
                     *[m.vote for m in r["models"].values()]))
    cols = ["time", "close", "action", "rank", "score", "v_trend", "v_meanrev", "v_confl", "v_layers", "v_mom"]
    return pd.DataFrame(rows, columns=cols).set_index("time")


def forward(df: pd.DataFrame, times: pd.DatetimeIndex, delta: str) -> np.ndarray:
    """Return from each time's close to the last close at or before time + delta (NaN if not reached)."""
    close = df["close"]
    end = df.index[-1]
    targets = times + pd.Timedelta(delta)
    fut = close.asof(targets).values
    now = close.reindex(times).values
    out = fut / now - 1
    out[targets > end] = np.nan
    return out


def worst_drawdown(df: pd.DataFrame, times: pd.DatetimeIndex, delta: str) -> np.ndarray:
    """Deepest drop below the entry price within the window (how much pain before the outcome)."""
    low, close = df["low"], df["close"]
    out = []
    for t in times:
        seg = low[(low.index > t) & (low.index <= t + pd.Timedelta(delta))]
        out.append(seg.min() / close.loc[t] - 1 if len(seg) else np.nan)
    return np.array(out)


def analyse_one(ticker: str, tf: str, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = download(ticker, tf)
    acts = replay(df, cfg)
    hz = HORIZONS[tf]
    for label, delta in hz:
        acts[f"fwd_{label}"] = forward(df, acts.index, delta)
    acts["ticker"], acts["tf"] = ticker, tf
    acts["asset"] = "crypto" if is_crypto(ticker, cfg) else "stock"
    # A new signal = the bar where the action group changes (what an alert would fire on).
    grp = acts["action"].map(GROUPS)
    new = grp != grp.shift(1)
    events = acts[new & (grp != "hold")].copy()
    events["group"] = grp[new & (grp != "hold")]
    events["mdd"] = worst_drawdown(df, events.index, hz[-1][1])
    return acts, events


# --------------------------------------------------------------------------- summarise
def summarise(all_bars: pd.DataFrame, events: pd.DataFrame) -> dict:
    out = {}
    for tf in sorted(events["tf"].unique(), key=["1d", "4h", "1h"].index):
        hz = [h for h, _ in HORIZONS[tf]]
        out[tf] = {}
        for asset in ("stock", "crypto", "all"):
            bars = all_bars[all_bars["tf"] == tf]
            ev = events[events["tf"] == tf]
            if asset != "all":
                bars, ev = bars[bars["asset"] == asset], ev[ev["asset"] == asset]
            if bars.empty:
                continue
            base = {h: _stats(bars[f"fwd_{h}"], +1) for h in hz}
            rows = {"baseline": base}
            for action in ["Strong Buy", "Buy", "Watch ↑", "Watch ↓", "Sell", "Strong Sell"]:
                e = ev[ev["action"] == action]
                if e.empty:
                    continue
                d = +1 if "↑" in action or "Buy" in action else -1
                rows[action] = {h: _stats(e[f"fwd_{h}"], d) for h in hz}
                rows[action]["_n"] = int(len(e))
                rows[action]["_mdd"] = _pct(e["mdd"].mean())
            out[tf][asset] = rows
    return out


def _pct(x) -> float | None:
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x) * 100, 2)


def _stats(s: pd.Series, direction: int) -> dict:
    s = s.dropna()
    if s.empty:
        return {"n": 0}
    return {"n": int(len(s)), "avg": _pct(s.mean()), "median": _pct(s.median()),
            "hit": round(float((np.sign(s) == direction).mean()) * 100, 1)}


def per_ticker(events: pd.DataFrame, tf: str = "1d", horizon: str = "1 month") -> list[dict]:
    rows = []
    for t, e in events[events["tf"] == tf].groupby("ticker"):
        b = e[e["group"] == "buy"][f"fwd_{horizon}"].dropna()
        s = e[e["group"] == "sell"][f"fwd_{horizon}"].dropna()
        rows.append({"ticker": t, "buys": int(len(b)), "buy_avg": _pct(b.mean()) if len(b) else None,
                     "buy_hit": round(float((b > 0).mean()) * 100) if len(b) else None,
                     "sells": int(len(s)), "sell_avg": _pct(s.mean()) if len(s) else None,
                     "sell_hit": round(float((s < 0).mean()) * 100) if len(s) else None})
    return rows


def write_markdown(summary: dict, tickers: list[dict], meta: dict) -> str:
    L = [f"# Signal Desk backtest — {meta['generated']}", "",
         f"Tickers: {', '.join(meta['tickers'])}. Daily: ~10 years. 4H/1H: last ~2 years. "
         "Entry at the close of the bar where a new signal appears. No costs or slippage.", "",
         "**Hit** = % of signals where price moved the signalled way (up for buys, down for sells). "
         "**Baseline** = the average over every bar, i.e. what you'd get by picking a random moment.", ""]
    for tf, assets in summary.items():
        hz = [h for h, _ in HORIZONS[tf]]
        for asset, rows in assets.items():
            L += [f"## {tf} — {asset}", "",
                  "| Signal | Count | " + " | ".join(f"{h} avg / hit" for h in hz) + " | Worst dip |",
                  "|---|---|" + "---|" * len(hz) + "---|"]
            for name, r in rows.items():
                n = r.get("_n", r[hz[0]].get("n", 0))
                cells = [f"{r[h].get('avg', '–')}% / {r[h].get('hit', '–')}%" if r[h].get("n") else "–" for h in hz]
                mdd = f"{r['_mdd']}%" if r.get("_mdd") is not None else ""
                L.append(f"| {name} | {n} | " + " | ".join(cells) + f" | {mdd} |")
            L.append("")
    L += ["## Daily, by ticker (1-month results)", "", "| Ticker | Buys | Avg | Hit | Sells | Avg | Hit |", "|---|---|---|---|---|---|---|"]
    for t in tickers:
        L.append(f"| {t['ticker']} | {t['buys']} | {t['buy_avg']}% | {t['buy_hit']}% | {t['sells']} | {t['sell_avg']}% | {t['sell_hit']}% |")
    L += ["", "_Personal research only. Past results don't guarantee future results._"]
    return "\n".join(L)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", nargs="*", default=["1d", "4h", "1h"])
    ap.add_argument("--tickers", nargs="*")
    args = ap.parse_args()
    cfg = load_config()
    tickers = args.tickers or cfg["watchlist"]["stocks"] + cfg["watchlist"]["crypto"]
    bars, events, failed = [], [], []
    t0 = time.time()
    jobs = [(t, tf) for tf in args.tf for t in tickers]
    workers = int(os.environ.get("BACKTEST_WORKERS", os.cpu_count() or 2))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(analyse_one, t, tf, cfg): (t, tf) for t, tf in jobs}
        for f in as_completed(futs):
            t, tf = futs[f]
            try:
                a, e = f.result()
                bars.append(a)
                events.append(e)
                log.info("%s %s: %d bars, %d signals (%.0fs elapsed)", t, tf, len(a), len(e), time.time() - t0)
            except Exception as ex:
                log.error("%s %s failed: %s", t, tf, ex)
                failed.append(f"{t} {tf}: {ex}")
    all_bars, all_events = pd.concat(bars), pd.concat(events)
    OUT.mkdir(exist_ok=True)
    meta = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "tickers": tickers,
            "timeframes": args.tf, "failed": failed, "window": WINDOW,
            "ensemble": cfg["ensemble"], "models": cfg["models"]}
    summary = summarise(all_bars, all_events)
    tick = per_ticker(all_events) if "1d" in args.tf else []
    # How often each action shows up at all (helps judge whether thresholds are too tight/loose).
    freq = {tf: all_bars[all_bars["tf"] == tf]["action"].value_counts(normalize=True).round(4).mul(100).to_dict()
            for tf in args.tf if (all_bars["tf"] == tf).any()}
    (OUT / "results.json").write_text(json.dumps({"meta": meta, "summary": summary, "per_ticker": tick,
                                                  "action_frequency_pct": freq}, indent=1))
    all_events.reset_index().to_csv(OUT / "events.csv", index=False, float_format="%.5f")
    # bar-level data, compact, for deeper analysis (votes + forward returns)
    all_bars.reset_index().to_csv(OUT / "bars.csv.gz", index=False, float_format="%.5f", compression="gzip")
    (OUT / "summary.md").write_text(write_markdown(summary, tick, meta))
    log.info("Done in %.0fs. %d failed.", time.time() - t0, len(failed))


if __name__ == "__main__":
    main()
