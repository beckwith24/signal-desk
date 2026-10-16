"""
Stock sell signals that don't need a prior buy: which ones actually warn of weaker returns?

Each rule is tested two ways on today's S&P 100 (2005 on; train = before 2021, test = 2021 on):
  * Alert days (the day the rule turns on): next 5 and 20 trading days' return vs the stock's own
    average (negative = a useful sell warning), t clustered by date.
  * Sit-out strategy: hold the stock, but go to cash while the rule is on; vs simply holding
    (equal weight across stocks, 0.05% per trade).

Rules:
  rsi2_hot      RSI(2) above 95 (short-term overbought)
  stretch       close above the upper 20-day Bollinger band and RSI(14) above 70
  ibs_top       RSI(2) above 90 and close in the top 10% of the day's range
  below200      close below its 200-day average
  death_cross   50-day average below the 200-day average
  weekly_down   weekly trend down (ribbon orange or below the 40-week average), known at the week's close
  breakdown     close below the 50-day average and 20%+ below its 52-week high

    python sell_research.py        (Actions tab -> "Sell signal test")

Writes research/sell.md and research/sell.json.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from combo_research import SPLIT, fetch, rsi, strategy, weekly_up

log = logging.getLogger("sell")
OUT = Path(__file__).with_name("research")
RULES = {
    "rsi2_hot": "RSI(2) above 95",
    "stretch": "Above upper Bollinger band and RSI(14) > 70",
    "ibs_top": "RSI(2) > 90 and close near the day's high",
    "below200": "Close below 200-day average",
    "death_cross": "50-day average below 200-day",
    "weekly_down": "Weekly trend down",
    "breakdown": "Below 50-day and 20%+ under 52-week high",
}


def frame(t: str, df: pd.DataFrame) -> pd.DataFrame:
    c, h, l = df["close"], df["high"], df["low"]
    ma20, sd20 = c.rolling(20).mean(), c.rolling(20).std()
    ma50, ma200 = c.rolling(50).mean(), c.rolling(200).mean()
    r2, r14 = rsi(c, 2), rsi(c, 14)
    ibs = ((c - l) / (h - l)).where(h > l)
    f = pd.DataFrame(index=df.index)
    f["ticker"] = t
    f["r_next"] = c.pct_change().shift(-1)
    for n in (5, 20):
        f[f"r{n}"] = c.shift(-n) / c - 1
    f["rsi2_hot"] = r2 > 95
    f["stretch"] = (c > ma20 + 2 * sd20) & (r14 > 70)
    f["ibs_top"] = (r2 > 90) & (ibs > 0.9)
    f["below200"] = (c < ma200) & ma200.notna()
    f["death_cross"] = (ma50 < ma200) & ma200.notna()
    f["weekly_down"] = ~weekly_up(df, "W-FRI")
    f["breakdown"] = (c < ma50) & (c < 0.8 * h.rolling(252).max())
    for k in RULES:
        f[k] = f[k].fillna(False).astype(bool)
        f[k + "_on"] = f[k] & ~f[k].shift(1, fill_value=False)
        f["keep_" + k] = ~f[k]
    return f.iloc[260:]


def stats(frames: list[pd.DataFrame], col: str, n: int) -> dict:
    b = pd.concat(frames)
    b["x"] = b[f"r{n}"] - b.groupby("ticker")[f"r{n}"].transform("mean")
    m = b[col] & b["x"].notna()
    if m.sum() < 30:
        return {"n": int(m.sum())}
    x = b.loc[m, "x"]; day = b.index[m].floor("D")
    mu = float(x.mean()); resid = (x - mu).groupby(day).sum(); G, N = len(resid), len(x)
    se = math.sqrt((resid ** 2).sum() * G / max(G - 1, 1)) / N
    return {"n": int(N), "x_pct": round(mu * 100, 2), "t": round(mu / se, 2) if se > 0 else None,
            "down_pct": round(float((b.loc[m, f"r{n}"] < 0).mean()) * 100, 1)}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from factor_research import SP100
    data = fetch(list(SP100))
    frames = [frame(t, df) for t, df in data.items()]
    res = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "tickers": len(frames), "parts": {}}
    for part, sel in (("train", lambda f: f[f.index < SPLIT]), ("test", lambda f: f[f.index >= SPLIT])):
        fs = [sel(f) for f in frames]
        res["parts"][part] = {k: {"alert5": stats(fs, k + "_on", 5), "alert20": stats(fs, k + "_on", 20),
                                  "state20": stats(fs, k, 20), "sitout": strategy(fs, "keep_" + k, 0.0005),
                                  "share_pct": round(float(pd.concat(fs)[k].mean()) * 100, 1)} for k in RULES}
    OUT.mkdir(exist_ok=True)
    (OUT / "sell.json").write_text(json.dumps(res, indent=1, default=float))
    L = [f"# Stock sell signals without a prior buy ({res['generated']}, {res['tickers']} stocks)", "",
         "Alert = the day the rule turns on. Excess = return vs the stock's own average over the next 5 / 20 trading days "
         "(negative = a useful warning). Sit-out = hold, but cash while the rule is on (equal weight, costs in).", ""]
    for part in ("train", "test"):
        L += [f"## {part} ({'2005-2020' if part == 'train' else '2021 on'})", "",
              "| Rule | Alerts | 5d excess % | t | 20d excess % | t | 20d down % | On % of days | Sit-out per yr % | Sit-out worst % | Hold per yr % | Hold worst % |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, name in RULES.items():
            x = res["parts"][part][k]
            a5, a20, so = x["alert5"], x["alert20"], x["sitout"] or {}
            L.append(f"| {name} | {a5.get('n')} | {a5.get('x_pct')} | {a5.get('t')} | {a20.get('x_pct')} | {a20.get('t')} | "
                     f"{a20.get('down_pct')} | {x['share_pct']} | {so.get('rule', {}).get('cagr')} | {so.get('rule', {}).get('mdd')} | "
                     f"{so.get('hold', {}).get('cagr')} | {so.get('hold', {}).get('mdd')} |")
        L.append("")
    (OUT / "sell.md").write_text("\n".join(L) + "\n")
    log.info("done")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        OUT.mkdir(exist_ok=True)
        (OUT / "sell.md").write_text("# Run failed\n\n```\n" + traceback.format_exc() + "```\n")
