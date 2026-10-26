"""
Active trading research: day trading, layering in/out with different amounts, and pair trading.

Uses the bars already stored in backtest/bars.csv.gz:
  hourly  - 13 stocks/ETFs (Jan 2024 -> Oct 2026, regular session, 7 bars a day) and 5 coins (Oct 2024 -> Oct 2026)
  daily   - same tickers, ~10 years
Nothing is fitted: every rule uses textbook / published parameters, fixed in advance.

Honesty rules
  * Signal at a bar's close is filled at the NEXT bar's close (one bar late), unless a rule says otherwise.
  * Day-trading stock rules are flat every night (no position over the overnight gap).
  * Costs on every change in position. Hourly: stocks 0 / 3 / 6 bp per side, crypto 0 / 10 / 30 bp per side.
    Daily: stocks 5 bp, crypto 30 bp per side (Alpaca crypto taker is 25 bp).

    python active_research.py      -> research/active.md + research/active.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import portfolio_research as P

ROOT = Path(__file__).parent
ET = "America/New_York"


# ============================================================================ helpers
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def hold(entry: np.ndarray, exit_: np.ndarray, max_bars: int | None = None) -> np.ndarray:
    """1 from an entry bar until (and excluding) the bar after an exit condition."""
    pos = np.zeros(len(entry))
    on, held = False, 0
    for i in range(len(entry)):
        if on:
            held += 1
            if exit_[i] or (max_bars and held >= max_bars):
                on = False
        elif entry[i]:
            on, held = True, 0
        pos[i] = 1.0 if on else 0.0
    return pos


def per_col(df: pd.DataFrame, fn) -> pd.DataFrame:
    return pd.DataFrame({c: fn(c) for c in df.columns}, index=df.index)


def daily_from_bars(net: pd.DataFrame, day: pd.Series) -> pd.Series:
    """Per-ticker bar returns -> per-ticker daily returns -> equal-weight portfolio daily return."""
    d = np.log1p(net).groupby(day.values).sum()
    return np.expm1(d).mean(axis=1)


def run_bars(px: pd.DataFrame, held: pd.DataFrame, cost: float) -> tuple[pd.DataFrame, dict]:
    ret = px.pct_change().fillna(0)
    held = held.reindex(px.index).fillna(0)
    turn = held.diff().abs()
    turn.iloc[0] = held.iloc[0].abs()
    net = held * ret - turn * cost
    entries = ((held != 0) & (held != held.shift(1).fillna(0))).sum().sum()
    yrs = (px.index[-1] - px.index[0]).days / 365.25
    info = {"trades_per_ticker_yr": round(entries / px.shape[1] / yrs, 1),
            "avg_net_bp_per_trade": round(1e4 * net.sum().sum() / entries, 1) if entries else None,
            "exposure": round(100 * held.abs().mean().mean(), 0)}
    return net, info


def row(name, daily: pd.Series, ann: int, info: dict) -> dict:
    s = P.stats(daily, ann)
    half = daily.index[len(daily) // 2]
    s1, s2 = P.stats(daily[daily.index < half], ann), P.stats(daily[daily.index >= half], ann)
    return {"name": name, **s, **info, "sharpe_1st_half": s1.get("sharpe"), "sharpe_2nd_half": s2.get("sharpe")}


# ============================================================================ 1. day trading
def load_hourly():
    b = pd.read_csv(ROOT / "backtest/bars.csv.gz")
    h = b[b.tf == "1h"].copy()
    h["t"] = pd.to_datetime(h["time"], utc=True)
    px = h.pivot_table(index="t", columns="ticker", values="close", aggfunc="last").sort_index()
    st = px[P.STOCKS]
    st = st[st["SPY"].notna()].ffill()
    cr = px[P.COINS].dropna(how="all").ffill()
    return st, cr


def stock_day_trading(st: pd.DataFrame) -> list[dict]:
    et = st.index.tz_convert(ET)
    day = pd.Series(et.date, index=st.index)
    bar = pd.Series(((et.hour * 60 + et.minute) - (9 * 60 + 30)) // 60, index=st.index)   # 0 = 9:30 bar ... 6 = 15:30 bar
    first = bar == 0
    ret = st.pct_change()
    r0 = ret.where(first)                                       # prev close -> 10:30 (overnight gap + first hour)
    r0_day = r0.groupby(day.values).transform("first")             # first non-missing value = that day's bar-0 return
    sign0 = np.sign(r0_day).fillna(0)
    M = lambda cond: pd.DataFrame(np.repeat(np.asarray(cond)[:, None], st.shape[1], 1), index=st.index, columns=st.columns)

    rules = {}
    # Gao, Han, Li & Zhou (2018) intraday momentum: first-hour return predicts the last half hour
    rules["Intraday momentum: last 30 min in the first hour's direction (long & short)"] = sign0.where(M(bar == 6), 0)
    rules["Intraday momentum, long only"] = sign0.clip(lower=0).where(M(bar == 6), 0)
    # Opening-drive: ride the first hour's direction for the rest of the day (entered at 11:30, one bar late)
    rules["First-hour direction, ride to the close (long & short)"] = sign0.where(M(bar >= 2), 0)
    # Hourly RSI(2) dip-buy above the 70-hour (~10-day) average, exit above the 5-hour average, flat overnight
    r2, m70, m5 = P.rsi(st), P.sma(st, 70), P.sma(st, 5)
    sig = per_col(st, lambda c: hold(((r2[c] < 10) & (st[c] > m70[c])).values, (st[c] > m5[c]).values))
    rules["Hourly RSI(2) dip-buy, flat overnight"] = sig.shift(1).where(M(bar > 0), 0)   # +1 bar fill lag; can't hold bar 0
    # Hourly trend: EMA 7 (1 day) above EMA 35 (5 days), long only, flat overnight
    tr = (ema(st, 7) > ema(st, 35)).astype(float)
    rules["Hourly trend (EMA 7/35), long only, flat overnight"] = tr.shift(1).where(M(bar > 0), 0)
    # Baselines
    rules["Baseline: hold all day and night"] = pd.DataFrame(1.0, index=st.index, columns=st.columns)
    rules["Baseline: hold 10:30 -> 16:00 every day (intraday only)"] = pd.DataFrame(1.0, index=st.index, columns=st.columns).where(M(bar > 0), 0)
    rules["Baseline: hold 16:00 -> 10:30 only (overnight + first hour)"] = pd.DataFrame(1.0, index=st.index, columns=st.columns).where(M(bar == 0), 0)

    out = []
    for name, h in rules.items():
        for bp in (0, 3, 6):
            if name.startswith("Baseline") and bp:
                continue
            net, info = run_bars(st, h, bp / 1e4)
            out.append(row(name, daily_from_bars(net, day), 252, {"cost_bp": bp, **info}))
    return out


def crypto_day_trading(cr: pd.DataFrame) -> list[dict]:
    day = pd.Series(cr.index.date, index=cr.index)
    hour = pd.Series(cr.index.hour, index=cr.index)
    rules = {}
    tr = (ema(cr, 24) > ema(cr, 96)).astype(float)
    rules["Hourly trend (EMA 24/96 = 1 day / 4 days), long only"] = tr.shift(1)
    r2, m200, m5 = P.rsi(cr), P.sma(cr, 200), P.sma(cr, 5)
    rules["Hourly RSI(2) dip-buy above 200-hour average (max 24 h)"] = per_col(
        cr, lambda c: hold(((r2[c] < 10) & (cr[c] > m200[c])).values, (cr[c] > m5[c]).values, 24)).shift(1)
    m20, sd20 = P.sma(cr, 20), cr.rolling(20).std()
    rules["Hourly Bollinger: buy 2σ below 20-hour average, sell at the average"] = per_col(
        cr, lambda c: hold((cr[c] < m20[c] - 2 * sd20[c]).values, (cr[c] > m20[c]).values)).shift(1)
    us = ((hour >= 13) & (hour <= 19)).astype(float)
    rules["Hold only in US hours (13:00-20:00 UTC)"] = pd.DataFrame({c: us for c in cr.columns})
    rules["Hold only outside US hours"] = 1 - rules["Hold only in US hours (13:00-20:00 UTC)"]
    rules["Baseline: hold"] = pd.DataFrame(1.0, index=cr.index, columns=cr.columns)
    out = []
    for name, h in rules.items():
        for bp in (0, 10, 30):
            if name == "Baseline: hold" and bp:
                continue
            net, info = run_bars(cr, h.fillna(0), bp / 1e4)
            out.append(row(name, daily_from_bars(net, day), 365, {"cost_bp": bp, **info}))
    return out


# ============================================================================ 2. layering in / out
def crypto_votes(coins: pd.DataFrame, tsmom_n=28, btc_sma=50) -> pd.DataFrame:
    btc = coins["BTC-USD"]
    btc_vote = np.sign(btc - P.sma(btc, btc_sma)).where(P.sma(btc, btc_sma).notna(), 0)
    out = {}
    for t in P.COINS:
        c = coins[t].dropna()
        v1 = np.sign(c / c.shift(tsmom_n) - 1).fillna(0)
        frac = pd.concat([(c > P.sma(c, n)).astype(float).where(P.sma(c, n).notna()) for n in (20, 50, 100)], axis=1).mean(axis=1)
        v2 = pd.Series(np.where(frac.isna(), 0, np.where(frac >= 0.66, 1, np.where(frac <= 0, -1, 0))), index=c.index)
        dfr = P.donchian_frac(c)
        v3 = pd.Series(np.where(dfr >= 0.5, 1, np.where(dfr <= 0, -1, 0)), index=c.index)
        out[t] = (v1 + v2 + v3 + btc_vote.reindex(c.index).fillna(0)) / 4
    return pd.DataFrame(out).reindex(coins.index)


def ladder(c: np.ndarray, on: np.ndarray, N: np.ndarray, mode: str) -> np.ndarray:
    """Fraction of the slot held (0..1) for one coin. Units of 1/3."""
    w = np.zeros(len(c))
    units, last, entry, Ne, sold, in_trade = 0, np.nan, np.nan, np.nan, 0, False
    for i in range(len(c)):
        if not on[i] or np.isnan(c[i]):
            units, in_trade, sold = 0, False, 0
        elif not in_trade:
            in_trade, entry, last, Ne = True, c[i], c[i], N[i]
            units = 3 if mode == "scale_out" else 1
        elif mode == "pyramid" and units < 3 and c[i] >= last + N[i]:
            units, last = units + 1, c[i]
        elif mode == "average_down" and units < 3 and c[i] <= last - N[i]:
            units, last = units + 1, c[i]
        elif mode == "scale_out" and sold < 2 and c[i] >= entry + 3 * (sold + 1) * Ne:
            units, sold = units - 1, sold + 1
        w[i] = units / 3
    return w


def crypto_layering(coins: pd.DataFrame) -> dict:
    avail = coins.notna().astype(float)
    slot = avail.div(avail.sum(axis=1).clip(lower=1), axis=0)
    votes = crypto_votes(coins)
    on = (votes > 0.5)
    N = coins.diff().abs().rolling(20, min_periods=20).mean()      # close-only ATR(20)
    vol = coins.pct_change().rolling(30, min_periods=20).std() * np.sqrt(365)
    variants = {
        "All in / all out (current rule)": on.astype(float),
        "Layer by agreement: size = share of trend votes up": votes.clip(lower=0).fillna(0),
        "Pyramid: 1/3 at signal, +1/3 each 1 ATR higher": per_col(coins, lambda t: ladder(coins[t].values, on[t].values, N[t].values, "pyramid")),
        "Average down: 1/3 at signal, +1/3 each 1 ATR lower": per_col(coins, lambda t: ladder(coins[t].values, on[t].values, N[t].values, "average_down")),
        "Scale out: full at signal, sell 1/3 at +3 ATR and +6 ATR": per_col(coins, lambda t: ladder(coins[t].values, on[t].values, N[t].values, "scale_out")),
        "Risk-sized: full slot x (60% / coin's volatility), max 1": on.astype(float) * (0.6 / vol).clip(upper=1).fillna(0),
    }
    return {k: (P.run_weights(coins, v * slot, P.COST["crypto"]), (v * slot).sum(axis=1)) for k, v in variants.items()}


def stock_layering(stocks: pd.DataFrame) -> dict:
    avail = stocks.notna().astype(float)
    slot = avail.div(avail.sum(axis=1).clip(lower=1), axis=0)
    r2, m200, m5 = P.rsi(stocks), P.sma(stocks, 200), P.sma(stocks, 5)

    def one(t, mode):
        c, r, up, ex = stocks[t].values, r2[t].values, (stocks[t] > m200[t]).values, (stocks[t] > m5[t]).values
        w = np.zeros(len(c))
        units, size, on = 0, 0.0, False
        for i in range(len(c)):
            if on and ex[i]:
                on, units, size = False, 0, 0.0
            elif on and mode == "scale_in" and units < 3 and c[i] < c[i - 1]:
                units += 1
            elif not on and r[i] < 10 and up[i]:
                on, units = True, 1
                size = max(1 / 3, (10 - r[i]) / 10)
            w[i] = (1.0 if mode == "single" else units / 3 if mode == "scale_in" else size) if on else 0.0
        return w

    variants = {
        "Single entry, full slot (what the bot does)": per_col(stocks, lambda t: one(t, "single")),
        "Scale in: 1/3 at signal, +1/3 on each lower close": per_col(stocks, lambda t: one(t, "scale_in")),
        "Size by how oversold (deeper dip = bigger)": per_col(stocks, lambda t: one(t, "depth")),
    }
    return {k: (P.run_weights(stocks, v * slot, P.COST["stock"]), (v * slot).sum(axis=1)) for k, v in variants.items()}


# ============================================================================ 3. pair trading
PAIRS = {"crypto": [("BTC-USD", "ETH-USD"), ("BTC-USD", "SOL-USD"), ("ETH-USD", "SOL-USD"), ("ETH-USD", "LINK-USD"), ("SOL-USD", "AVAX-USD")],
         "stock": [("NVDA", "AMD"), ("MSFT", "GOOGL"), ("QQQ", "SPY"), ("AVGO", "MRVL"), ("AAPL", "MSFT"), ("META", "GOOGL")]}


def pair_strats(px: pd.DataFrame, asset: str) -> dict:
    a, b = px.columns
    lb = 28 if asset == "crypto" else 63
    every = 7 if asset == "crypto" else 5
    cost = P.COST[asset]
    month_end = px.index.to_series().groupby(px.index.to_period("M")).transform("max") == px.index
    out = {}
    w = pd.DataFrame(0.5, index=px.index, columns=[a, b]).where(month_end).ffill().fillna(0.5)
    out["50/50, rebalanced monthly"] = w
    out[f"Hold {a} only"] = pd.DataFrame({a: 1.0, b: 0.0}, index=px.index)
    out[f"Hold {b} only"] = pd.DataFrame({a: 0.0, b: 1.0}, index=px.index)
    mom = px / px.shift(lb) - 1
    check = pd.Series(np.arange(len(px)) % every == 0, index=px.index)
    lead_a = (mom[a] > mom[b]).astype(float)
    w = pd.DataFrame({a: lead_a, b: 1 - lead_a}).where(mom.notna().all(axis=1) & check).ffill().fillna(0.5)
    out[f"Rotation: hold the stronger ({lb}-day), checked every {every} bars"] = w
    best = np.where(lead_a > 0, mom[a], mom[b])
    in_mkt = pd.Series(best > 0, index=px.index).astype(float)
    w2 = pd.DataFrame({a: lead_a * in_mkt, b: (1 - lead_a) * in_mkt}).where(mom.notna().all(axis=1) & check).ffill().fillna(0.5)
    out["Dual momentum: stronger one, cash if it is falling"] = w2
    lr = np.log(px[a] / px[b])
    z = ((lr - lr.rolling(60).mean()) / lr.rolling(60).std()).fillna(0)
    target = 0.5 - 0.125 * z.clip(-2, 2)
    cur, wa = 0.5, []
    for x in target.values:
        if abs(x - cur) > 0.05:
            cur = x
        wa.append(cur)
    wa = pd.Series(wa, index=px.index)
    out["Ratio tilt: overweight the laggard (25-75%), long only"] = pd.DataFrame({a: wa, b: 1 - wa})
    if asset == "stock":
        la, lb_ = np.log(px[a]), np.log(px[b])
        beta = la.rolling(60).cov(lb_) / lb_.rolling(60).var()
        spread = la - beta * lb_
        zs = ((spread - spread.rolling(60).mean()) / spread.rolling(60).std()).values
        pos, s = np.zeros(len(px)), 0
        for i in range(len(px)):
            if np.isnan(zs[i]):
                s = 0
            elif s == 0 and zs[i] < -2:
                s = 1
            elif s == 0 and zs[i] > 2:
                s = -1
            elif s == 1 and (zs[i] >= 0 or zs[i] < -4):
                s = 0
            elif s == -1 and (zs[i] <= 0 or zs[i] > 4):
                s = 0
            pos[i] = s
        out["Market-neutral stat-arb (long one, short other, z ±2)"] = pd.DataFrame({a: 0.5 * pos, b: -0.5 * pos}, index=px.index)
    return {k: (P.run_weights(px, v, cost), v.abs().sum(axis=1)) for k, v in out.items()}


def pair_results(stocks, coins) -> list[dict]:
    rows = []
    for asset, pairs in PAIRS.items():
        src, ann = (coins, 365) if asset == "crypto" else (stocks, 252)
        for a, b in pairs:
            px = src[[a, b]].dropna()
            for name, (r, inv) in pair_strats(px, asset).items():
                generic = name.replace(a, "A").replace(b, "B")
                r = r.iloc[120:]                       # warm-up
                for per, sl in (("train", r[r.index < P.SPLIT]), ("test", r[r.index >= P.SPLIT])):
                    s = P.stats(sl, ann, inv)
                    if s:
                        rows.append({"asset": asset, "pair": f"{a.replace('-USD', '')}/{b.replace('-USD', '')}",
                                     "strategy": generic, "period": per, **s})
    return rows


# ============================================================================ report
def md_rows(rows, cols, heads) -> str:
    s = "| " + " | ".join(heads) + " |\n|" + "---|" * len(heads) + "\n"
    for r in rows:
        s += "| " + " | ".join("–" if r.get(c) is None else str(r.get(c)) for c in cols) + " |\n"
    return s


def main() -> None:
    st_h, cr_h = load_hourly()
    stocks, coins = P.load()
    res = {"day_stock": stock_day_trading(st_h), "day_crypto": crypto_day_trading(cr_h)}
    lay = {}
    for label, d, ann in (("crypto", crypto_layering(coins), 365), ("stock", stock_layering(stocks), 252)):
        lay[label] = [{"name": k, "period": per, **P.stats(r[(r.index < P.SPLIT) if per == "train" else (r.index >= P.SPLIT)], ann, inv)}
                      for k, (r, inv) in d.items() for per in ("train", "test")]
    res["layering"] = lay
    res["pairs"] = pair_results(stocks, coins)
    (ROOT / "research/active.json").write_text(json.dumps(res, indent=1, default=str))

    md = ["# Active trading test: day trading, layering, pair trading\n",
          "All rules fixed in advance (textbook parameters). Signals filled one bar late. Costs per side as shown. "
          "Stocks/ETFs: NVDA AMD AVGO PLTR TSLA MRVL MU GOOGL AAPL MSFT META QQQ SPY. Coins: BTC ETH SOL LINK AVAX. "
          "Per-year and Sharpe are for an equal-weight portfolio of the rule run on every ticker.\n"]
    dc = ["name", "cost_bp", "cagr", "sharpe", "max_dd", "exposure", "trades_per_ticker_yr", "avg_net_bp_per_trade", "sharpe_1st_half", "sharpe_2nd_half"]
    dh = ["Rule", "Cost bp/side", "Per year %", "Sharpe", "Worst drop %", "Time in %", "Trades/ticker/yr", "Avg net per trade (bp)", "Sharpe 1st half", "Sharpe 2nd half"]
    md.append("## 1a. Day trading stocks (hourly bars, Jan 2024 – Oct 2026)\n\n" + md_rows(res["day_stock"], dc, dh))
    md.append("## 1b. Short-term crypto trading (hourly bars, Oct 2024 – Oct 2026)\n\n" + md_rows(res["day_crypto"], dc, dh))
    lc = ["name", "period", "cagr", "sharpe", "max_dd", "calmar", "invested"]
    lh = ["Layering", "Period", "Per year %", "Sharpe", "Worst drop %", "Return ÷ drop", "Invested %"]
    md.append("## 2a. Layering the crypto trend trade (daily, 5 coins; train < 2021, test 2021+)\n\n" + md_rows(lay["crypto"], lc, lh))
    md.append("## 2b. Layering stock dip-buys (daily, 13 stocks)\n\n" + md_rows(lay["stock"], lc, lh))

    pr = pd.DataFrame(res["pairs"])
    for asset in ("crypto", "stock"):
        sub = pr[pr.asset == asset]
        base = sub[sub.strategy == "50/50, rebalanced monthly"].set_index(["pair", "period"])["sharpe"]
        lines = []
        for (strat, per), g in sub.groupby(["strategy", "period"], sort=False):
            g = g.set_index("pair")
            beat = sum(g.loc[p, "sharpe"] > base.get((p, per), np.nan) for p in g.index)
            lines.append({"strategy": strat, "period": per, "cagr": round(g.cagr.median(), 1), "sharpe": round(g.sharpe.median(), 2),
                          "max_dd": round(g.max_dd.median(), 1), "beat": f"{beat}/{len(g)}"})
        md.append(f"## 3. Pair trading — {asset} pairs ({', '.join(f'{a}/{b}' for a, b in PAIRS[asset])}), medians across pairs\n\n" +
                  md_rows(lines, ["strategy", "period", "cagr", "sharpe", "max_dd", "beat"],
                          ["Strategy", "Period", "Per year %", "Sharpe", "Worst drop %", "Better Sharpe than 50/50"]))
        det = sub[sub.period == "test"].pivot_table(index="pair", columns="strategy", values="sharpe")
        det = det.round(2).reset_index()
        md.append(f"Test-period Sharpe by pair ({asset}):\n\n" + md_rows(det.to_dict("records"), list(det.columns), list(det.columns)))
    (ROOT / "research/active.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
