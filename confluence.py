"""
"Confluence (rebuilt)": our best approximation of InvestAnswers' IA-Confluence-Model, for intraday charts.

What it draws (fitted to two screenshots, research/confluence.md and research/conf_avgo.md):
  * Grey envelope: a Bollinger band about 8 trading days long, 2 standard deviations wide. On the AVGO 2h
    screenshot this sits within ~0.2-0.3% of his lines (likely a 100-bar band on his 24-hour chart).
  * Triangles: close comes back inside the band (buy from below, sell from above). This matches ~3 of 8 of
    his AVGO triangles and ~40% of UMAC's; his exact trigger has inputs we can't see.
  * Results table, his way: $100k, each buy spends half the cash, each sell sells half the shares and ONLY
    if the price is above the average cost (so every closed trade is a win), trading at the next bar's open.
    Shown next to simply holding over the same bars, and with the open position's gain/loss, because the
    100% win rate hides positions held under water.

Information only: in our tests it trailed buying and holding (research/confluence.md), so it doesn't feed
Buy/Sell signals, alerts or the auto-trader.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DAYS = 8.0
WIDTH = 2.0
CAPITAL = 100_000.0
BUY_FRAC = 0.5
SELL_FRAC = 0.5
COST = 0.0005


def bars_per_day(df: pd.DataFrame) -> float:
    idx = df.index.tz_convert("America/New_York") if df.index.tz is not None else df.index
    return float(pd.Series(1, index=idx).groupby(idx.date).sum().iloc[-30:].median())


def compute(df: pd.DataFrame) -> dict | None:
    if len(df) < 60:
        return None
    n = max(10, int(round(DAYS * bars_per_day(df))))
    if len(df) < n + 20:
        return None
    c = df["close"]
    mid = c.rolling(n, min_periods=n).mean()
    sd = c.rolling(n, min_periods=n).std(ddof=0)
    up, lo = mid + WIDTH * sd, mid - WIDTH * sd
    buy = ((c > lo) & (c.shift(1) < lo.shift(1))).fillna(False).to_numpy()
    sell = ((c < up) & (c.shift(1) > up.shift(1))).fillna(False).to_numpy()

    o, cl = df["open"].to_numpy(float), c.to_numpy(float)
    start = n
    cash, sh, basis = CAPITAL, 0.0, 0.0
    realized, buys, sells, wins = 0.0, 0, 0, 0
    marks = []
    for i in range(start, len(df)):
        if buy[i]:
            marks.append({"i": i, "side": "buy"})
        if sell[i]:
            marks.append({"i": i, "side": "sell"})
        j = i + 1                                   # act at the next bar's open
        if j >= len(df):
            continue
        px = o[j]
        if buy[i] and cash > 1:
            spend = cash * BUY_FRAC if cash * BUY_FRAC > 100 else cash
            sh += spend * (1 - COST) / px; basis += spend; cash -= spend; buys += 1
        elif sell[i] and sh > 0:
            avg = basis / sh
            if px * (1 - COST) > avg:               # his table only sells above the average cost
                q = sh * SELL_FRAC
                cash += q * px * (1 - COST); realized += q * (px * (1 - COST) - avg)
                basis -= avg * q; sh -= q; sells += 1; wins += 1
    open_val = sh * cl[-1]
    total = cash + open_val
    first = df.index[start]
    return {
        "n": n, "days": DAYS, "width": WIDTH,
        "up": up, "lo": lo,
        "marks": marks,
        "bt": {"since": first.strftime("%Y-%m-%d"), "profit": round(realized), "roi_pct": round(realized / CAPITAL * 100, 2),
               "win_pct": round(100.0 * wins / sells, 1) if sells else None, "buys": buys, "sells": sells,
               "open": round(open_val), "capital": round(cash), "total": round(total),
               "total_pct": round((total / CAPITAL - 1) * 100, 1),
               "open_vs_cost_pct": round((open_val / basis - 1) * 100, 1) if basis > 1 else None,
               "hold_pct": round((cl[-1] / o[start] - 1) * 100, 1)},
    }
