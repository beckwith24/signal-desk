"""
Three models the app doesn't have yet, tested on a wide universe (not just the watchlist):

  1. Relative strength ranking  - own the strongest third of the universe (Jegadeesh & Titman 1993;
                                  crypto: Liu, Tsyvinski & Wu 2022). Stocks: 12-month return skipping
                                  the last month, rebalanced monthly. Crypto: 4-week return, weekly.
  2. Volatility-based sizing    - scale each position so each carries similar risk (Moreira & Muir 2017;
                                  standard in trend following). Applied to the crypto trend rule and to
                                  the stock ranking portfolio.
  3. Earnings drift (stocks)    - after a beat that the market cheers, does the stock keep beating the
                                  market for 20-60 trading days? (Bernard & Thomas 1989)

Universe: today's S&P 100 and ~30 large coins with long Yahoo histories (checked against Kraken's price).
Today's S&P 100 contains companies that grew into it, which flatters "buy recent winners" tests:
read the stock ranking results as an upper bound.

Train = before 2021, test = 2021 on. Costs: stocks 0.05% per side, crypto 0.25% per side.

    python factor_research.py      (Actions tab -> "Factor test")
Writes research/factors.md and research/factors.json.
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
import models
from backtest import download

log = logging.getLogger("factors")
OUT = Path(__file__).with_name("research")
SPLIT = pd.Timestamp("2021-01-01")
COST = {"stock": 0.0005, "crypto": 0.0025}

SP100 = ("AAPL ABBV ABT ACN ADBE AMAT AMD AMGN AMT AMZN ANET AVGO AXP BA BAC BKNG BLK BMY BK BRK-B C CAT CMCSA "
         "COF COP COST CRM CSCO CVS CVX DE DELL DHR DIS DUK EMR FDX GD GE GEV GILD GM GOOGL GS HD IBM INTC INTU "
         "ISRG JNJ JPM KO LIN LLY LMT LOW LRCX MA MCD MDLZ MDT META MMM MO MRK MS MSFT MU NEE NFLX NOW NVDA ORCL "
         "PANW PEP PFE PG PLTR PM QCOM RTX SBUX SCHW SNDK SO T TMO TMUS TSLA TXN UBER UNH UNP UPS USB V VZ WFC "
         "WMT XOM").split()
COINS = ("BTC ETH XRP BNB SOL DOGE ADA TRX AVAX LINK XLM BCH LTC DOT ETC ATOM FIL HBAR ALGO NEAR AAVE XMR "
         "VET ICP EOS XTZ THETA SAND MANA UNI SUI HYPE").split()


# ----------------------------------------------------------------------------- data
def panel(frames: dict[str, pd.DataFrame], asset: str, field: str = "close") -> pd.DataFrame:
    cols = {}
    for t, df in frames.items():
        idx = df.index.tz_convert("America/New_York") if asset == "stock" else df.index.tz_convert("UTC")
        s = pd.Series(df[field].values, index=pd.DatetimeIndex(idx.date))
        cols[t] = s[~s.index.duplicated(keep="last")]
    p = pd.DataFrame(cols).sort_index()
    return p.ffill(limit=3)


def kraken_prices() -> dict[str, float]:
    try:
        import ccxt
        ex = ccxt.kraken({"enableRateLimit": True})
        ex.load_markets()
        out = {}
        for b in COINS:
            sym = f"{b}/USD" if f"{b}/USD" in ex.markets else None
            if sym:
                try:
                    out[b] = float(ex.fetch_ticker(sym)["last"])
                except Exception:
                    pass
        return out
    except Exception as e:
        log.warning("Kraken check unavailable: %s", e)
        return {}


def load(asset: str) -> tuple[dict, list[str]]:
    frames, dropped = {}, []
    names = SP100 if asset == "stock" else [f"{c}-USD" for c in COINS]
    for t in names:
        try:
            df = download(t, "1d")
            if len(df) < 300:
                dropped.append(f"{t} (short history)")
                continue
            frames[t] = df
        except Exception as e:
            dropped.append(f"{t} ({str(e)[:40]})")
    if asset == "crypto":
        live = kraken_prices()
        for t in list(frames):
            b = t.split("-")[0]
            if b in live and abs(frames[t]["close"].iat[-1] / live[b] - 1) > 0.25:
                dropped.append(f"{t} (Yahoo symbol is a different coin)")
                frames.pop(t)
    return frames, dropped


# ----------------------------------------------------------------------------- metrics
def perf(r: pd.Series, per_year: int) -> dict:
    r = r.dropna()
    if len(r) < 6:
        return {"n": int(len(r))}
    eq = (1 + r).cumprod()
    years = len(r) / per_year
    return {"n": int(len(r)), "cagr_pct": round((eq.iat[-1] ** (1 / years) - 1) * 100, 1),
            "vol_pct": round(r.std() * math.sqrt(per_year) * 100, 1),
            "sharpe": round(r.mean() / r.std() * math.sqrt(per_year), 2) if r.std() > 0 else None,
            "max_dd_pct": round((eq / eq.cummax() - 1).min() * 100, 1)}


def excess(a: pd.Series, b: pd.Series, per_year: int) -> dict:
    d = (a - b).dropna()
    if len(d) < 6:
        return {}
    t = d.mean() / (d.std() / math.sqrt(len(d))) if d.std() > 0 else float("nan")
    return {"excess_pct_per_year": round(d.mean() * per_year * 100, 1), "t": round(t, 2),
            "share_beating_pct": round((d > 0).mean() * 100, 1)}


def split_report(series: dict[str, pd.Series], bench: str, per_year: int) -> dict:
    out = {}
    for part, sel in (("train", lambda s: s[s.index < SPLIT]), ("test", lambda s: s[s.index >= SPLIT]),
                      ("all", lambda s: s)):
        out[part] = {}
        for k, s in series.items():
            row = perf(sel(s), per_year)
            if k != bench:
                row.update(excess(sel(s), sel(series[bench]), per_year))
            out[part][k] = row
    return out


# ----------------------------------------------------------------------------- 1 + 2: ranking and sizing
def rebalance_dates(idx: pd.DatetimeIndex, freq: str) -> list:
    s = pd.Series(idx, index=idx)
    if freq == "M":
        return list(s.groupby([idx.year, idx.month]).max())
    return list(s.groupby(np.arange(len(idx)) // 7).max())


def run_portfolio(px: pd.DataFrame, weights_at, dates: list, cost: float) -> pd.Series:
    """Hold weights chosen at each rebalance date until the next one. Returns period returns."""
    rets, prev_w = {}, pd.Series(dtype=float)
    for d0, d1 in zip(dates[:-1], dates[1:]):
        w = weights_at(d0)
        if w is None:
            continue
        period = px.loc[d1] / px.loc[d0] - 1
        gross = float((w * period.reindex(w.index).fillna(0)).sum())
        turnover = float((w.reindex(w.index.union(prev_w.index), fill_value=0)
                          - prev_w.reindex(w.index.union(prev_w.index), fill_value=0)).abs().sum())
        rets[d1] = gross - cost * turnover
        prev_w = w
    return pd.Series(rets)


def stock_ranking(frames: dict) -> dict:
    px = panel(frames, "stock")
    ret = px.pct_change(fill_method=None)
    mom12 = px.shift(21) / px.shift(252) - 1
    mom6 = px.shift(21) / px.shift(126) - 1
    above200 = px > px.rolling(200).mean()
    vol60 = ret.rolling(60).std()
    dates = [d for d in rebalance_dates(px.index, "M") if d >= px.index[260]]
    cost = COST["stock"]

    def eligible(d):
        return mom12.loc[d].dropna().index

    def eq_all(d):
        e = eligible(d)
        return pd.Series(1 / len(e), index=e) if len(e) else None

    def top(score, d, filt=None, inv_vol=False):
        s = score.loc[d].dropna()
        if len(s) < 9:
            return None
        pick = s[s >= s.quantile(2 / 3)].index
        if filt is not None:
            pick = [t for t in pick if bool(filt.loc[d].get(t, False))]
            if not pick:
                return pd.Series(dtype=float)                 # all cash this month
        if inv_vol:
            iv = 1 / vol60.loc[d, pick].replace(0, np.nan)
            return (iv / iv.sum()).fillna(0)
        return pd.Series(1 / len(pick), index=pick)

    series = {
        "Equal weight, all stocks": run_portfolio(px, eq_all, dates, cost),
        "Top third by 12-month strength": run_portfolio(px, lambda d: top(mom12, d), dates, cost),
        "Top third by 6-month strength": run_portfolio(px, lambda d: top(mom6, d), dates, cost),
        "Top third (12m) + above 200-day": run_portfolio(px, lambda d: top(mom12, d, above200), dates, cost),
        "Top third (12m), sized by volatility": run_portfolio(px, lambda d: top(mom12, d, inv_vol=True), dates, cost),
    }
    return {"universe": len(frames), "rebalance": "monthly", **split_report(series, "Equal weight, all stocks", 12)}


def crypto_ranking_and_sizing(frames: dict) -> dict:
    px = panel(frames, "crypto")
    ret = px.pct_change(fill_method=None)
    mom28 = px / px.shift(28) - 1
    vol30 = ret.rolling(30).std() * math.sqrt(365)
    # the app's crypto rule (3 of 4 trend models bullish) for every coin
    ctx_daily = context.fetch_daily(lambda s: download(s, "1d"), context.needs("crypto"))
    trend = {}
    for t, df in frames.items():
        ctx = context.align(ctx_daily, df.index, "crypto", "1d")
        v = pd.DataFrame({k: models.run(k, df, ctx)["vote"] for k in
                          ["tsmom28", "sma_ensemble", "donchian_ensemble", "btc_trend_gate"]})
        s = pd.Series((v.mean(axis=1) > 0.5).values, index=pd.DatetimeIndex(df.index.tz_convert("UTC").date))
        trend[t] = s[~s.index.duplicated(keep="last")]
    trend = pd.DataFrame(trend).reindex(px.index).fillna(False)
    start = px.index[120]
    dates = [d for d in rebalance_dates(px.index, "W") if d >= start]
    cost = COST["crypto"]
    TARGET = 0.6                                                      # 60% a year, about bitcoin's usual

    def avail(d):
        return px.loc[d].dropna().index.intersection(mom28.loc[d].dropna().index)

    def eq_all(d):
        a = avail(d)
        return pd.Series(1 / len(a), index=a) if len(a) else None

    def top(d, with_trend=False, sized=False):
        a = avail(d)
        s = mom28.loc[d, a]
        if len(s) < 6:
            return None
        pick = list(s[s >= s.quantile(2 / 3)].index)
        if with_trend:
            pick = [t for t in pick if bool(trend.loc[d].get(t, False))]
        w = pd.Series(1 / max(len(pick), 1), index=pick)
        if sized and pick:
            w = w * (TARGET / vol30.loc[d, pick]).clip(upper=1).fillna(0)
        return w

    def trend_slots(d, sized=False):
        a = avail(d)
        if not len(a):
            return None
        on = [t for t in a if bool(trend.loc[d].get(t, False))]
        w = pd.Series(1 / len(a), index=on)                          # each coin gets a 1/N slot
        if sized and on:
            w = w * (TARGET / vol30.loc[d, on]).clip(upper=1).fillna(0)
        return w

    series = {
        "Equal weight, all coins": run_portfolio(px, eq_all, dates, cost),
        "Top third by 4-week strength": run_portfolio(px, lambda d: top(d), dates, cost),
        "App trend rule on every coin": run_portfolio(px, lambda d: trend_slots(d), dates, cost),
        "App trend rule, sized by volatility": run_portfolio(px, lambda d: trend_slots(d, sized=True), dates, cost),
        "Top third + trend rule": run_portfolio(px, lambda d: top(d, with_trend=True), dates, cost),
        "Top third + trend rule, sized by volatility": run_portfolio(px, lambda d: top(d, True, True), dates, cost),
    }
    return {"universe": len(frames), "rebalance": "weekly", "target_vol_pct": TARGET * 100,
            **split_report(series, "Equal weight, all coins", 52)}


# ----------------------------------------------------------------------------- 3: earnings drift
def earnings_events(tickers: list[str]) -> pd.DataFrame:
    import yfinance as yf
    rows = []
    for t in tickers:
        for attempt in range(2):
            try:
                e = yf.Ticker(t).get_earnings_dates(limit=48)
                if e is not None and not e.empty:
                    e = e.copy()
                    e["ticker"] = t
                    e["when"] = e.index
                    rows.append(e.reset_index(drop=True))
                break
            except Exception as ex:
                log.info("earnings %s: %s", t, ex)
                time.sleep(2)
        time.sleep(0.4)
    if not rows:
        return pd.DataFrame()
    ev = pd.concat(rows, ignore_index=True)
    ev = ev.rename(columns={"Surprise(%)": "surprise", "EPS Estimate": "est", "Reported EPS": "eps"})
    return ev.dropna(subset=["eps"])


def earnings_drift(frames: dict) -> dict:
    px = panel(frames, "stock")
    bench = px.pct_change(fill_method=None).mean(axis=1)              # equal-weight universe, daily
    bidx = (1 + bench.fillna(0)).cumprod()
    ev = earnings_events(list(frames))
    if ev.empty:
        return {"error": "no earnings data from Yahoo"}
    out_rows = []
    dates = px.index
    for _, r in ev.iterrows():
        t = r["ticker"]
        if t not in px:
            continue
        when = pd.Timestamp(r["when"])
        when = when.tz_convert("America/New_York") if when.tzinfo else when
        d = pd.Timestamp(when.date())
        i = dates.searchsorted(d)                                     # first trading day on/after the date
        if i < 1 or i + 61 >= len(dates):
            continue
        # reaction window covers before-open and after-close reports: close before -> close of next day
        p_before, p_react = px[t].iat[i - 1], px[t].iat[i + 1]
        if not (p_before > 0 and p_react > 0):
            continue
        react = p_react / p_before - 1 - (bidx.iat[i + 1] / bidx.iat[i - 1] - 1)
        rec = {"ticker": t, "date": str(d.date()), "surprise": r.get("surprise"), "react": react}
        for h in (20, 40, 60):                                         # enter at the reaction close, hold h days
            p_exit = px[t].iat[i + 1 + h]
            rec[f"drift{h}"] = (p_exit / p_react - 1) - (bidx.iat[i + 1 + h] / bidx.iat[i + 1] - 1)
        out_rows.append(rec)
    df = pd.DataFrame(out_rows).dropna(subset=["react", "drift20"])
    df["surprise"] = pd.to_numeric(df["surprise"], errors="coerce")
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").astype(str)

    def stats(sub: pd.DataFrame) -> dict:
        res = {"events": int(len(sub))}
        for h in (20, 40, 60):
            x = sub[f"drift{h}"].dropna()
            if len(x) < 15:
                continue
            mu = x.mean()
            resid = (x - mu).groupby(sub.loc[x.index, "week"]).sum()
            G = len(resid)
            se = math.sqrt((resid ** 2).sum() * G / max(G - 1, 1)) / len(x) if G > 2 else float("nan")
            res[f"{h}d_excess_pct"] = round(mu * 100, 2)
            res[f"{h}d_t"] = round(mu / se, 2) if se and se > 0 else None
            res[f"{h}d_win_pct"] = round((x > 0).mean() * 100, 1)
        return res

    groups = {
        "All reports": lambda x: x,
        "Beat (surprise > 0) and stock jumped > 3%": lambda x: x[(x["surprise"] > 0) & (x["react"] > 0.03)],
        "Biggest jumps (top 20%)": lambda x: x[x["react"] >= x["react"].quantile(0.8)],
        "Biggest drops (bottom 20%)": lambda x: x[x["react"] <= x["react"].quantile(0.2)],
        "Missed (surprise < 0) and stock fell > 3%": lambda x: x[(x["surprise"] < 0) & (x["react"] < -0.03)],
    }
    out = {"events_total": int(len(df)), "from": df["date"].min(), "to": df["date"].max()}
    for part, sel in (("train", df[pd.to_datetime(df["date"]) < SPLIT]), ("test", df[pd.to_datetime(df["date"]) >= SPLIT]),
                      ("all", df)):
        out[part] = {name: stats(f(sel)) for name, f in groups.items()} if len(sel) else {}
    return out


# ----------------------------------------------------------------------------- report
def table(block: dict, cols: list[tuple[str, str]]) -> list[str]:
    L = ["| Strategy | " + " | ".join(h for _, h in cols) + " |", "|---|" + "---|" * len(cols)]
    for name, row in block.items():
        L.append(f"| {name} | " + " | ".join(str(row.get(k, "–")) for k, _ in cols) + " |")
    return L


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    res = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    stocks, sd = load("stock")
    coins, cd = load("crypto")
    res["dropped"] = sd + cd
    res["stock_ranking"] = stock_ranking(stocks)
    res["crypto"] = crypto_ranking_and_sizing(coins)
    res["earnings"] = earnings_drift(stocks)
    OUT.mkdir(exist_ok=True)
    (OUT / "factors.json").write_text(json.dumps(res, indent=1, default=str))
    cols = [("cagr_pct", "Return/yr %"), ("sharpe", "Sharpe"), ("max_dd_pct", "Worst drop %"),
            ("excess_pct_per_year", "vs equal weight %/yr"), ("t", "t"), ("share_beating_pct", "Periods ahead %")]
    L = [f"# Factor test ({res['generated']})", "",
         f"Stocks: {res['stock_ranking']['universe']} of today's S&P 100. Coins: {res['crypto']['universe']}. "
         f"Dropped: {', '.join(res['dropped']) or 'none'}.", "",
         "Today's S&P 100 includes companies that grew into it, which flatters 'buy recent winners': treat the "
         "stock ranking numbers as an upper bound.", ""]
    for key, title in (("stock_ranking", "1. Stocks: relative strength (monthly)"),
                       ("crypto", "1-2. Crypto: relative strength and volatility sizing (weekly)")):
        L += [f"## {title}", ""]
        for part in ("train", "test"):
            L += [f"**{part}**", ""] + table(res[key][part], cols) + [""]
    L += ["## 3. Stocks: earnings drift", "",
          f"{res['earnings'].get('events_total')} reports, {res['earnings'].get('from')} to {res['earnings'].get('to')}. "
          "Buy at the close after the report reaction; return vs the equal-weight universe.", ""]
    ecols = [("events", "Reports"), ("20d_excess_pct", "Next 20 days %"), ("20d_t", "t"),
             ("40d_excess_pct", "Next 40 days %"), ("40d_t", "t"), ("60d_excess_pct", "Next 60 days %"), ("60d_t", "t")]
    for part in ("train", "test"):
        if res["earnings"].get(part):
            L += [f"**{part}**", ""] + table(res["earnings"][part], ecols) + [""]
    (OUT / "factors.md").write_text("\n".join(L))
    log.info("done")


if __name__ == "__main__":
    main()
