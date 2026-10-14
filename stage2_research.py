"""
Sell-off -> flat base -> breakout -> buy the pullback (Weinstein "Stage 2" / Wyckoff "backup"). Does it work?

Weekly chart (Friday close, nothing from the future):
  sell-off   the base's low is at least 30% (crypto 50%) below the high of the 2 years before the base
  base       the last 16 or 26 weeks stayed in a range (top/bottom <= 1.4x stocks, 1.8x crypto) while the
             30-week average went flat (moved less than 8%, crypto 15%)
  breakout   weekly close above the top of the base, above the 30-week average, and the average turning up;
             first breakout in 26 weeks
Entries after a breakout (within 13 weeks, bought at the next day's open):
  breakout   right away (Monday after the breakout week)
  retest     first day the low comes back to within 2% of the base top (staying above the base bottom)
  rsi_dip    first RSI(2) < 10 day (the app's "RSI dip")
  ma50_dip   first close at or under the 50-day average
Measured: return vs SPY (stocks) / vs BTC (coins) over the next 20/60/120/250 trading days, and a trade
version (stop: daily close under the base bottom; exit: weekly close under the 30-week average; costs in).
Compared with: (a) the same tickers on any day, (b) plain RSI(2) dips above the 200-day average anywhere.
t-stats clustered by month. Train = before 2015, test = 2015 on.
Stocks: today's S&P 500 (companies that failed and left the index are missing, which flatters recoveries).

    python stage2_research.py        (Actions tab -> "Stage 2 test")

Writes research/stage2.md and research/stage2.json.
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

log = logging.getLogger("stage2")
OUT = Path(__file__).with_name("research")
SPLIT = pd.Timestamp("2015-01-01")
H = (20, 60, 120, 250)
P = {"stock": {"decline": 0.30, "range": 1.4, "flat": 0.08, "cost": 0.0005, "week": "W-FRI"},
     "crypto": {"decline": 0.50, "range": 1.8, "flat": 0.15, "cost": 0.0025, "week": "W-SUN"}}
ENTRIES = ["breakout", "retest", "rsi_dip", "ma50_dip"]


def rsi(s: pd.Series, n: int) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def weekly(d: pd.DataFrame, rule: str) -> pd.DataFrame:
    return d.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna(subset=["close"])


def breakouts(w: pd.DataFrame, B: int, p: dict) -> list[dict]:
    c, hi, lo = w["close"].to_numpy(), w["high"].to_numpy(), w["low"].to_numpy()
    ma = w["close"].rolling(30, min_periods=30).mean().to_numpy()
    out, last = [], -10 ** 9
    for i in range(B + 104 + 30, len(w)):
        if i - last < 26 or np.isnan(ma[i]) or np.isnan(ma[i - B]):
            continue
        b_hi, b_lo = hi[i - B:i].max(), lo[i - B:i].min()
        prior = hi[i - B - 104:i - B].max()
        if not (b_lo <= prior * (1 - p["decline"]) and b_hi / b_lo <= p["range"]
                and abs(ma[i - 1] / ma[i - B] - 1) <= p["flat"]):
            continue
        if c[i] > b_hi and c[i] > ma[i] and ma[i] >= ma[i - 4]:
            out.append({"week": w.index[i], "base_hi": float(b_hi), "base_lo": float(b_lo)})
            last = i
    return out


def entries(d: pd.DataFrame, br: dict) -> dict[str, int]:
    """Index (in d) of the signal day for each entry type; the trade happens at the next day's open."""
    c, lo = d["close"], d["low"]
    i0 = int(d.index.searchsorted(br["week"], side="right"))           # first day after the breakout week
    i1 = min(len(d) - 2, i0 + 65)
    if i0 >= len(d) - 2:
        return {}
    r2, m50 = d["_rsi2"].to_numpy(), d["_ma50"].to_numpy()
    out = {"breakout": i0 - 1}
    for j in range(i0, i1):
        if c.iat[j] < br["base_lo"]:
            break                                                     # failed back into / below the base
        if "retest" not in out and lo.iat[j] <= br["base_hi"] * 1.02:
            out["retest"] = j
        if "rsi_dip" not in out and r2[j] < 10:
            out["rsi_dip"] = j
        if "ma50_dip" not in out and c.iat[j] <= m50[j]:
            out["ma50_dip"] = j
    return out


def fwd(d: pd.DataFrame, bench: pd.Series, j: int) -> dict:
    """Excess return vs benchmark from the open after day j."""
    o = d["open"].to_numpy(); n = len(d)
    if j + 1 >= n:
        return {}
    t0 = d.index[j + 1]; b = bench.reindex(d.index).ffill().to_numpy()
    rec = {}
    for h in H:
        k = j + 1 + h
        if k < n and o[j + 1] > 0 and b[j + 1] > 0 and b[k] == b[k]:
            rec[f"x{h}"] = (o[k] / o[j + 1] - 1) - (b[k] / b[j + 1] - 1)
    rec["date"] = t0
    return rec


def trade(d: pd.DataFrame, br: dict, j: int, cost: float, below_weeks: np.ndarray) -> dict | None:
    """Buy at the open after day j. Stop: a daily close under the base bottom (sell next open).
    Exit: a weekly close under the 30-week average (sell at the next week's first open)."""
    o, c = d["open"].to_numpy(), d["close"].to_numpy()
    if j + 1 >= len(d):
        return None
    t_in = d.index[j + 1]; entry = o[j + 1] * (1 + cost)
    li = int(np.searchsorted(below_weeks, t_in))
    exit_w = below_weeks[li] if li < len(below_weeks) else None
    for k in range(j + 1, len(d) - 1):
        if exit_w is not None and d.index[k] > exit_w:
            return {"ret": o[k] * (1 - cost) / entry - 1, "days": k - (j + 1), "stopped": False}
        if c[k] < br["base_lo"]:
            return {"ret": o[k + 1] * (1 - cost) / entry - 1, "days": k + 1 - (j + 1), "stopped": True}
    return {"ret": c[-1] / entry - 1, "days": len(d) - (j + 1), "stopped": False, "open": True}


def clustered(x: pd.Series, groups: pd.Series) -> tuple[float, float]:
    mu = float(x.mean()); resid = (x - mu).groupby(groups.values).sum(); G, N = len(resid), len(x)
    se = math.sqrt((resid ** 2).sum() * G / max(G - 1, 1)) / N if G > 2 else float("nan")
    return mu, (mu / se if se and se > 0 else float("nan"))


def summarize(ev: list[dict]) -> dict:
    if len(ev) < 15:
        return {"n": len(ev)}
    df = pd.DataFrame(ev); month = df["date"].dt.to_period("M").astype(str)
    out = {"n": len(df)}
    for h in H:
        x = df.get(f"x{h}")
        if x is None or x.notna().sum() < 15:
            continue
        m = x.notna(); mu, t = clustered(x[m], month[m])
        out[f"{h}d"] = round(mu * 100, 2); out[f"{h}d_t"] = round(t, 2); out[f"{h}d_beat"] = round(float((x[m] > 0).mean()) * 100, 1)
    if "ret" in df:
        r = df["ret"].dropna()
        out.update(trade_win=round(float((r > 0).mean()) * 100, 1), trade_avg=round(float(r.mean()) * 100, 1),
                   trade_med=round(float(r.median()) * 100, 1), trade_days=int(df["days"].median()),
                   stopped=round(float(df["stopped"].mean()) * 100, 1))
    return out


def fetch(tickers: list[str]) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), 80):
        b = tickers[i:i + 80]; d = None
        for attempt in range(3):
            try:
                d = yf.download(b, start="2003-01-01", interval="1d", auto_adjust=True, group_by="ticker", progress=False, threads=True)
                break
            except Exception as e:
                log.warning("batch %d: %s", i, e); time.sleep(10 * (attempt + 1))
        if d is None:
            continue
        for t in b:
            try:
                x = (d[t] if isinstance(d.columns, pd.MultiIndex) else d).rename(columns=str.lower)[["open", "high", "low", "close"]]
                x = x.dropna(subset=["close"]); x.index = pd.DatetimeIndex(x.index).tz_localize(None)
                if len(x) > 800:
                    out[t] = x
            except Exception:
                pass
        time.sleep(1)
    return out


def run_asset(asset: str, data: dict[str, pd.DataFrame], bench: pd.Series) -> dict:
    p = P[asset]
    res = {}
    for B in (16, 26):
        ev = {e: [] for e in ENTRIES}; ctrl_dip, ctrl_all = [], []
        for t, d in data.items():
            d = d.copy(); d["_rsi2"] = rsi(d["close"], 2); d["_ma50"] = d["close"].rolling(50).mean()
            w = weekly(d, p["week"])
            ma30 = w["close"].rolling(30, min_periods=30).mean()
            below_weeks = w.index[(w["close"] < ma30).to_numpy()].to_numpy()
            for br in breakouts(w, B, p):
                for e, j in entries(d, br).items():
                    rec = fwd(d, bench, j)
                    if rec:
                        rec.update(trade(d, br, j, p["cost"], below_weeks) or {}); rec["ticker"] = t
                        ev[e].append(rec)
            if B == 16:                               # controls, once per ticker
                ma200 = d["close"].rolling(200).mean().to_numpy(); r2 = d["_rsi2"].to_numpy()
                last = -100
                for j in range(250, len(d) - 2):
                    if r2[j] < 10 and d["close"].iat[j] > ma200[j] and j - last >= 20:
                        rec = fwd(d, bench, j)
                        if rec:
                            ctrl_dip.append(rec)
                        last = j
                for j in range(250, len(d) - 2, 20):  # every 20th day: the average day
                    rec = fwd(d, bench, j)
                    if rec:
                        ctrl_all.append(rec)
        part = lambda rows, a, b: [r for r in rows if a <= r["date"] < b]
        lo, hi = pd.Timestamp("1990-01-01"), pd.Timestamp("2100-01-01")
        res[f"base {B} weeks"] = {e: {k: summarize(part(ev[e], a, b)) for k, (a, b) in
                                      {"train": (lo, SPLIT), "test": (SPLIT, hi), "all": (lo, hi)}.items()} for e in ENTRIES}
        if B == 16:
            res["controls"] = {nm: {k: summarize(part(rows, a, b)) for k, (a, b) in
                                    {"train": (lo, SPLIT), "test": (SPLIT, hi), "all": (lo, hi)}.items()}
                               for nm, rows in (("any RSI(2) dip above the 200-day", ctrl_dip), ("average day", ctrl_all))}
        res[f"examples base {B}"] = sorted({(r["ticker"], str(r["date"].date())) for r in ev["breakout"]}, key=lambda x: x[1])[-15:]
    return res


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from factor_research import COINS
    from screen_signals import wiki
    try:
        sp = wiki("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol")
    except Exception as e:
        log.warning("S&P list: %s", e); sp = []
    if not sp:
        from factor_research import SP100
        sp = list(SP100)
    res = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "assets": {}}
    stocks = fetch(sp + ["SPY"]); spy = stocks.pop("SPY")["open"]
    res["assets"]["stock"] = {"tickers": len(stocks), **run_asset("stock", stocks, spy)}
    coins = fetch([c + "-USD" for c in COINS]); btc = coins.get("BTC-USD")["open"]
    res["assets"]["crypto"] = {"tickers": len(coins), **run_asset("crypto", coins, btc)}
    OUT.mkdir(exist_ok=True)
    (OUT / "stage2.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "stage2.md").write_text(report(res))
    log.info("done")


def report(r: dict) -> str:
    L = [f"# Sell-off -> base -> breakout -> pullback (Stage 2) test ({r['generated']})", "",
         "Return vs SPY (stocks) / BTC (coins) after buying at the next open. t clustered by month (|t| >= 2 is "
         "reasonably convincing). Trade = stop under the base, exit on a weekly close under the 30-week average, costs in. "
         "Train = before 2015, test = 2015 on.", ""]
    cols = [("n", "Events"), ("20d", "20d %"), ("60d", "60d %"), ("120d", "120d %"), ("120d_t", "t"), ("250d", "250d %"),
            ("250d_t", "t"), ("120d_beat", "Beat bench 120d %"), ("trade_win", "Trade win %"), ("trade_med", "Trade median %"),
            ("trade_days", "Days held"), ("stopped", "Stopped %")]
    for asset, a in r["assets"].items():
        L += [f"## {asset.title()}s ({a['tickers']} tickers)", ""]
        for part in ("train", "test"):
            L += [f"**{part}**", "", "| Setup | " + " | ".join(h for _, h in cols) + " |", "|---|" + "---|" * len(cols)]
            for key in [k for k in a if k.startswith("base ")]:
                for e in ENTRIES:
                    x = a[key][e][part]
                    L.append(f"| {key}, buy {e} | " + " | ".join(str(x.get(k, "–")) for k, _ in cols) + " |")
            for nm, x in a["controls"].items():
                x = x[part]
                L.append(f"| Control: {nm} | " + " | ".join(str(x.get(k, "–")) for k, _ in cols) + " |")
            L.append("")
        L += [f"Latest breakouts (26-week bases): " + ", ".join(f"{t} {d}" for t, d in a.get("examples base 26", [])), ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        OUT.mkdir(exist_ok=True)
        (OUT / "stage2.md").write_text("# Run failed\n\n```\n" + traceback.format_exc() + "```\n")
