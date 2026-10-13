"""
Does copying members of Congress work, if you can only act once a trade is DISCLOSED?

1. Pulls every electronic Periodic Transaction Report (stock trades) from the official House Clerk
   (PDFs) and Senate eFD (web pages) since 2018. Saves them to research/congress_trades.csv.gz.
2. For each disclosed buy or sell: buy at the close of the first trading day after the disclosure,
   and measure the return over the next 20 / 60 / 120 trading days minus SPY's.
   For comparison, the same from the TRADE date (not copyable: you can't know it yet).
3. NANC / KRUZ (the ETFs that copy Democratic / Republican trades) vs SPY since they started.

t-stats are clustered by disclosure week (members often report the same stocks at the same time).
Train = before 2021, test = 2021 on.  Writes research/congress.md and research/congress.json.
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

import congress

log = logging.getLogger("congress_research")
OUT = Path(__file__).with_name("research")
CACHE = OUT / "congress_trades.csv.gz"
SPLIT = pd.Timestamp("2021-01-01")
H = (20, 60, 120)


def fetch_all() -> tuple[pd.DataFrame, dict]:
    old = pd.read_csv(CACHE, parse_dates=["traded", "disclosed"]) if CACHE.exists() else pd.DataFrame()
    if len(old):                      # re-read every House report with the current parser
        old = old[old["chamber"] != "House"]
    seen = set(old["doc"].astype(str)) if len(old) else set()
    stats = {}
    house, stats["house"] = congress.house_ptrs(list(range(2018, datetime.now().year + 1)), skip_docs=seen)
    try:
        senate, stats["senate"] = congress.senate_ptrs("01/01/2018", skip_docs=seen)
    except Exception as e:
        senate, stats["senate"] = pd.DataFrame(), {"error": str(e)[:150]}
    df = pd.concat([x for x in (old, house, senate) if len(x)], ignore_index=True)
    df = df.dropna(subset=["ticker", "side", "disclosed"])
    df["disclosed"] = pd.to_datetime(df["disclosed"])
    df["traded"] = pd.to_datetime(df["traded"], errors="coerce")
    df = df.drop_duplicates(subset=["chamber", "member", "ticker", "side", "traded", "disclosed", "amount_low"])
    OUT.mkdir(exist_ok=True)
    df.sort_values("disclosed").to_csv(CACHE, index=False, compression="gzip")
    return df, stats


PRICE_STATS: dict = {}


def _download(batch: list[str], start: str) -> pd.DataFrame:
    import yfinance as yf
    d = yf.download(batch, start=start, auto_adjust=True, progress=False, threads=True)["Close"]
    d = d if isinstance(d, pd.DataFrame) else d.to_frame(batch[0])
    d.index = pd.DatetimeIndex(d.index).tz_localize(None).normalize()
    d = d[~d.index.duplicated(keep="last")]
    return d.loc[:, [c for c in d.columns if d[c].notna().any()]]


def prices(tickers: list[str], start: str = "2017-12-01") -> pd.DataFrame:
    """Daily closes on SPY's trading calendar. SPY comes first and must load: every return is measured against it
    (a rate-limited SPY batch once left every result blank). Batches that come back empty are retried after a pause."""
    spy = None
    for attempt in range(5):
        try:
            d = _download(["SPY"], start)
            if "SPY" in d and d["SPY"].notna().sum() > 500:
                spy = d["SPY"].dropna(); break
        except Exception as e:
            log.warning("SPY download failed (%s), retrying", e)
        time.sleep(15 * (attempt + 1))
    if spy is None:
        raise RuntimeError("SPY prices unavailable from Yahoo; try again later")
    frames, want = [spy.to_frame("SPY")], sorted(set(tickers) - {"SPY"})
    got: set[str] = set()
    for i in range(0, len(want), 100):
        todo = want[i:i + 100]
        for attempt in range(3):
            try:
                d = _download(todo, start)
                frames.append(d); got |= set(d.columns)
            except Exception as e:
                log.warning("price batch %d failed: %s", i, e)
            missing = [t for t in todo if t not in got]
            if len(missing) <= max(10, len(todo) // 3):   # the rest are mostly delisted or renamed symbols
                break
            todo = missing
            time.sleep(10 * (attempt + 1))
        time.sleep(1)
    px = pd.concat(frames, axis=1)
    px = px.loc[:, ~px.columns.duplicated()].reindex(spy.index)
    PRICE_STATS.update({"tickers": len(want), "with_prices": len(got), "days": int(len(spy)),
                        "from": str(spy.index[0].date()), "to": str(spy.index[-1].date())})
    log.info("prices: %s", PRICE_STATS)
    return px


def events(df: pd.DataFrame, px: pd.DataFrame, when: str) -> pd.DataFrame:
    dates = px.index
    spy = px["SPY"]
    rows = []
    g = df.groupby(["member", "ticker", "side", when], as_index=False).agg(amount_low=("amount_low", "sum"),
                                                                           chamber=("chamber", "first"),
                                                                           d_first=("disclosed", "min"),
                                                                           t_first=("traded", "min"))
    for _, e in g.iterrows():
        t = e["ticker"]
        if t not in px or pd.isna(e[when]):
            continue
        i = dates.searchsorted(pd.Timestamp(e[when]), side="right")    # first trading day AFTER the date
        if i >= len(dates):
            continue
        p0, s0 = px[t].iat[i], spy.iat[i]
        if not (p0 > 0 and s0 > 0):
            continue
        rec = {"ticker": t, "side": e["side"], "member": e["member"], "chamber": e["chamber"],
               "date": dates[i], "amount_low": e["amount_low"],
               "lag_days": (e["d_first"] - e["t_first"]).days if pd.notna(e["t_first"]) else None}
        for h in H:
            if i + h < len(dates) and px[t].iat[i + h] > 0 and spy.iat[i + h] > 0:
                rec[f"x{h}"] = (px[t].iat[i + h] / p0 - 1) - (spy.iat[i + h] / s0 - 1)
        rows.append(rec)
    return pd.DataFrame(rows)


def stats(ev: pd.DataFrame) -> dict:
    out = {"events": int(len(ev))}
    if len(ev) < 20:
        return out
    week = ev["date"].dt.to_period("W").astype(str)
    for h in H:
        x = ev.get(f"x{h}")
        if x is None:
            continue
        x = x.dropna()
        if len(x) < 20:
            continue
        mu = x.mean()
        resid = (x - mu).groupby(week[x.index]).sum()
        G = len(resid)
        se = math.sqrt((resid ** 2).sum() * G / max(G - 1, 1)) / len(x) if G > 2 else float("nan")
        out[f"{h}d_pct"] = round(mu * 100, 2)
        out[f"{h}d_t"] = round(mu / se, 2) if se and se > 0 else None
        out[f"{h}d_win"] = round((x > 0).mean() * 100, 1)
    return out


def groups(ev: pd.DataFrame) -> dict:
    if ev.empty:
        return {}
    buys, sells = ev[ev["side"] == "buy"], ev[ev["side"] == "sell"]
    cl = buys.sort_values("date").copy()
    cl["n_members_30d"] = 0
    for t, g in cl.groupby("ticker"):
        d = g["date"].values
        for j, idx in enumerate(g.index):
            lo = d[j] - np.timedelta64(30, "D")
            cl.loc[idx, "n_members_30d"] = g.loc[(g["date"] >= lo) & (g["date"] <= d[j]), "member"].nunique()
    return {
        "All buys": buys, "All sells": sells,
        "Buys of $50k or more": buys[buys["amount_low"] >= 50001],
        "Buys reported within 7 days": buys[buys["lag_days"].fillna(99) <= 7],
        "Buys by 2+ members within 30 days": cl[cl["n_members_30d"] >= 2],
        "House buys": buys[buys["chamber"] == "House"], "Senate buys": buys[buys["chamber"] == "Senate"],
    }


def etfs() -> dict:
    px = prices(["NANC", "GOP", "SPY"], start="2023-02-01")       # KRUZ became GOP in March 2025
    out = {}
    for t in ("NANC", "GOP", "SPY"):
        s = px[t].dropna()
        if len(s) < 50:
            continue
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        out[t] = {"from": str(s.index[0].date()), "total_pct": round((s.iat[-1] / s.iat[0] - 1) * 100, 1),
                  "per_year_pct": round(((s.iat[-1] / s.iat[0]) ** (1 / yrs) - 1) * 100, 1),
                  "worst_drop_pct": round((s / s.cummax() - 1).min() * 100, 1)}
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    trades, fetch_stats = fetch_all()
    log.info("trades: %d", len(trades))
    px = prices(trades["ticker"].dropna().unique().tolist())
    res = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "fetch": fetch_stats,
           "trades": int(len(trades)), "members": int(trades["member"].nunique()),
           "disclosed_from": str(trades["disclosed"].min().date()), "disclosed_to": str(trades["disclosed"].max().date()),
           "median_days_to_disclose": float((trades["disclosed"] - trades["traded"]).dt.days.median())}
    res["prices"] = dict(PRICE_STATS)
    res["results"] = {}
    for when, label in (("disclosed", "copyable (after disclosure)"), ("traded", "trade date (NOT copyable)")):
        ev = events(trades, px, when)
        res["results"][label] = {}
        for part, sel in (("train", ev[ev["date"] < SPLIT]), ("test", ev[ev["date"] >= SPLIT]), ("all", ev)):
            res["results"][label][part] = {k: stats(v) for k, v in groups(sel).items()}
    res["etfs"] = etfs()
    (OUT / "congress.json").write_text(json.dumps(res, indent=1, default=str))
    L = [f"# Congressional trades test ({res['generated']})", "",
         f"{res['trades']:,} stock trades by {res['members']} members, disclosed {res['disclosed_from']} to "
         f"{res['disclosed_to']}. Median {res['median_days_to_disclose']:.0f} days from trade to disclosure.",
         f"Sources: {json.dumps(fetch_stats)}", f"Prices: {json.dumps(res['prices'])}", "",
         "Return = stock minus SPY over the next 20/60/120 trading days. t clustered by week.", ""]
    cols = [("events", "Trades"), ("20d_pct", "20d %"), ("20d_t", "t"), ("60d_pct", "60d %"), ("60d_t", "t"),
            ("120d_pct", "120d %"), ("120d_t", "t"), ("60d_win", "60d beat SPY %")]
    for label, parts in res["results"].items():
        L += [f"## Buying {label}", ""]
        for part in ("train", "test", "all"):
            L += [f"**{part}**", "", "| Group | " + " | ".join(h for _, h in cols) + " |", "|---|" + "---|" * len(cols)]
            for g, row in parts[part].items():
                L.append(f"| {g} | " + " | ".join(str(row.get(k, "–")) for k, _ in cols) + " |")
            L.append("")
    L += ["## Congress-copying ETFs vs SPY", "", "| ETF | Since | Total % | Per year % | Worst drop % |", "|---|---|---|---|---|"]
    for t, x in res["etfs"].items():
        L.append(f"| {t} | {x['from']} | {x['total_pct']} | {x['per_year_pct']} | {x['worst_drop_pct']} |")
    (OUT / "congress.md").write_text("\n".join(L))
    log.info("done")


if __name__ == "__main__":
    main()
