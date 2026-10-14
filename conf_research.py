"""
Rebuild the InvestAnswers IA-Confluence-Model from a screenshot, then test it honestly.

The screenshot (UMAC 1h, digitised into research/ia_targets/umac_conf.json) shows:
  - a grey envelope above and below price, with a circle on each line every ~5 trading days
  - solid buy/sell triangles with a label, and fainter triangles ~8-12 hours earlier
  - its own backtest table: 24 buys, 20 sells, 100% wins, ROI 143.85%

Steps:
  1. Line the screenshot up with real UMAC hourly prices (Yahoo, with pre/after-market hours; TradingView's chart
     also had the overnight session, which Yahoo lacks, so lengths below are in our bars: ~16 a day vs 24).
  2. Envelope: which band formula draws the grey lines?
  3. Triangles: which rule puts buy/sell signals where the screenshot has them (solid and faint)?
  4. Its backtest table: how 100% wins can happen (sell only above cost) and what it hides.
  5. The best match on the watchlist (hourly, ~2 years): normal sells vs sell-only-in-profit vs holding.

    python conf_research.py         (Actions tab -> "Confluence model test")

Writes research/confluence.md and research/confluence.json. Close approximations, not InvestAnswers' code.
"""
from __future__ import annotations

import itertools
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("confluence")
ROOT = Path(__file__).parent
OUT = ROOT / "research"
TARGET = OUT / "ia_targets" / "umac_conf.json"
TOL_H = 4                       # hours: how close a predicted signal must be to a screenshot triangle


# ----------------------------------------------------------------------------- data
FETCH_NOTES: dict = {}


def hourly(ticker: str, prepost: bool = True) -> pd.DataFrame:
    """Hourly bars from Yahoo. Tries ~2 years with pre/after-market hours, then regular hours, then shorter spans."""
    import yfinance as yf
    end = pd.Timestamp.now(tz="UTC").normalize() + pd.Timedelta(days=1)
    tries = [(728, prepost), (728, False), (360, prepost), (59, prepost)] if prepost else [(728, False), (360, False)]
    errs = []
    for days, pp in tries:
        for attempt in range(2):
            try:
                df = yf.Ticker(ticker).history(start=(end - pd.Timedelta(days=days)).date().isoformat(),
                                               end=end.date().isoformat(), interval="1h", prepost=pp, auto_adjust=True)
                if df is not None and len(df) > 200:
                    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].astype(float)
                    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
                    FETCH_NOTES[ticker] = f"{days} days, {'with' if pp else 'without'} pre/after-market hours"
                    return df[~df.index.duplicated(keep="last")].dropna(subset=["close"]).sort_index()
                errs.append(f"{days}d prepost={pp}: {0 if df is None else len(df)} rows")
            except Exception as e:
                errs.append(f"{days}d prepost={pp}: {type(e).__name__}: {str(e)[:120]}")
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"no hourly data for {ticker}: " + " | ".join(errs[-4:]))


def bar_at(df: pd.DataFrame, ts: pd.Timestamp, tol_min: int = 60) -> int | None:
    i = int(df.index.searchsorted(ts))
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(df):
            d = abs((df.index[j] - ts).total_seconds()) / 60
            if d <= tol_min and (best is None or d < best[0]):
                best = (d, j)
    return None if best is None else best[1]


# ----------------------------------------------------------------------------- indicators
def sma(s, n): return s.rolling(n, min_periods=n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False, min_periods=n).mean()
def rma(s, n): return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def atr(df, n):
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return rma(tr, n)


def rsi(s, n):
    d = s.diff()
    up, dn = rma(d.clip(lower=0), n), rma(-d.clip(upper=0), n)
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def stoch(df, n=14, k=3):
    lo, hi = df["low"].rolling(n).min(), df["high"].rolling(n).max()
    return sma(100 * (df["close"] - lo) / (hi - lo).replace(0, np.nan), k)


def mfi(df, n=14):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    pos = mf.where(tp > tp.shift(1), 0.0).rolling(n).sum()
    neg = mf.where(tp < tp.shift(1), 0.0).rolling(n).sum()
    return 100 - 100 / (1 + pos / neg.replace(0, np.nan))


def cci(df, n=20):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    md = tp.rolling(n).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - sma(tp, n)) / (0.015 * md)


def band(df, fam, n, k):
    c = df["close"]
    if fam == "bb":
        m, d = sma(c, n), c.rolling(n).std(ddof=0)
    elif fam == "bb_ema":
        m, d = ema(c, n), c.rolling(n).std(ddof=0)
    elif fam == "bb_hlc3":
        s = (df["high"] + df["low"] + c) / 3
        m, d = sma(s, n), s.rolling(n).std(ddof=0)
    else:                                   # keltner
        m, d = ema(c, n), atr(df, n)
    return m + k * d, m - k * d


# ----------------------------------------------------------------------------- 1. alignment
def align(df: pd.DataFrame, tgt: dict) -> dict:
    line = pd.DataFrame(tgt["line"]); line["time"] = pd.to_datetime(line["time"], utc=True)
    best = None
    for shift in range(-6, 7):
        rows = []
        for t, p in zip(line["time"], line["price"]):
            j = bar_at(df, t + pd.Timedelta(hours=shift))
            if j is not None:
                rows.append((j, p))
        if len(rows) < 100:
            continue
        g = pd.DataFrame(rows, columns=["bar", "p"]).groupby("bar")["p"].median()
        real = df["close"].to_numpy()[g.index]
        c = float(np.corrcoef(g.to_numpy(), real)[0, 1])
        if best is None or c > best["corr"]:
            best = {"shift_h": shift, "corr": round(c, 4), "points": len(g),
                    "median_err_pct": round(float(np.median(np.abs(g.to_numpy() / real - 1))) * 100, 2)}
    return best


# ----------------------------------------------------------------------------- 2. envelope
def envelope_fit(df: pd.DataFrame, tgt: dict, shift: int) -> list[dict]:
    env = pd.DataFrame(tgt["envelope"]); env["time"] = pd.to_datetime(env["time"], utc=True)
    bars = [bar_at(df, t + pd.Timedelta(hours=shift)) for t in env["time"]]
    ok = [i for i, b in enumerate(bars) if b is not None]
    idx = np.array([bars[i] for i in ok]); up_t = env["upper"].to_numpy()[ok]; lo_t = env["lower"].to_numpy()[ok]
    out = []
    for fam in ("bb", "bb_ema", "bb_hlc3", "keltner"):
        for n in range(10, 401, 10):
            for k in np.arange(1.0, 4.01, 0.25):
                up, lo = band(df, fam, n, k)
                u, l = up.to_numpy()[idx], lo.to_numpy()[idx]
                good = ~(np.isnan(u) | np.isnan(l))
                if good.sum() < 0.8 * len(idx):
                    continue
                eu = np.median(np.abs(u[good] / up_t[good] - 1)); el = np.median(np.abs(l[good] / lo_t[good] - 1))
                out.append({"family": fam, "n": n, "k": round(float(k), 2), "err_upper_pct": round(eu * 100, 2),
                            "err_lower_pct": round(el * 100, 2), "err_pct": round((eu + el) / 2 * 100, 2)})
    return sorted(out, key=lambda r: r["err_pct"])


# ----------------------------------------------------------------------------- 3. triangles
def edges(cond: pd.Series, cooldown: int = 6) -> np.ndarray:
    c = cond.fillna(False).to_numpy(bool)
    on = c & ~np.r_[False, c[:-1]]
    out, last = [], -10 ** 9
    for i in np.nonzero(on)[0]:
        if i - last >= cooldown:
            out.append(i); last = i
    return np.array(out, int)


def rules(df: pd.DataFrame, bands: list[dict]):
    """(name, buy condition, sell condition) candidates."""
    c = df["close"]
    osc = {}
    for n in (2, 3, 5, 7, 14):
        osc[f"RSI{n}"] = rsi(c, n)
    osc["Stoch14"], osc["MFI14"], osc["CCI20"] = stoch(df), mfi(df), cci(df)
    lims = {"RSI2": (10, 90), "RSI3": (15, 85), "RSI5": (20, 80), "RSI7": (25, 75), "RSI14": (30, 70),
            "Stoch14": (20, 80), "MFI14": (20, 80), "CCI20": (-100, 100)}
    for b in bands:
        up, lo = band(df, b["family"], b["n"], b["k"])
        nm = f"{b['family']}({b['n']},{b['k']})"
        below, above = c < lo, c > up
        yield f"close outside {nm}", below, above
        yield f"low/high touches {nm}", df["low"] < lo, df["high"] > up
        yield f"back inside {nm}", (c > lo) & below.shift(1, fill_value=False), (c < up) & above.shift(1, fill_value=False)
        for o, (L, H) in lims.items():
            x = osc[o]
            yield f"close outside {nm} and {o} {L}/{H}", below & (x < L), above & (x > H)
        for need in (2, 3):                         # confluence: several of band + oscillators agree
            buys = sum([below.astype(int)] + [(osc[o] < lims[o][0]).astype(int) for o in ("RSI14", "Stoch14", "MFI14", "CCI20")])
            sells = sum([above.astype(int)] + [(osc[o] > lims[o][1]).astype(int) for o in ("RSI14", "Stoch14", "MFI14", "CCI20")])
            yield f"{need}+ of [outside {nm}, RSI14, Stoch, MFI, CCI]", buys >= need, sells >= need
    for o, (L, H) in lims.items():
        x = osc[o]
        yield f"{o} below {L} / above {H}", x < L, x > H
        yield f"{o} back above {L} / below {H}", (x > L) & (x.shift(1) <= L), (x < H) & (x.shift(1) >= H)


def match(pred_t: list[pd.Timestamp], targets: list[pd.Timestamp]) -> int:
    used, hit = set(), 0
    for t in targets:
        for j, p in enumerate(pred_t):
            if j not in used and abs((p - t).total_seconds()) <= TOL_H * 3600:
                used.add(j); hit += 1; break
    return hit


def triangle_fit(df: pd.DataFrame, tgt: dict, shift: int, bands: list[dict]) -> list[dict]:
    tri = pd.DataFrame(tgt["triangles"]); tri["time"] = pd.to_datetime(tri["time"], utc=True) + pd.Timedelta(hours=shift)
    t0, t1 = tri["time"].min() - pd.Timedelta(days=2), tri["time"].max() + pd.Timedelta(hours=TOL_H)
    out = []
    for name, bc, sc in rules(df, bands):
        row = {"rule": name}
        tot_hit = tot_pred = 0
        for side, cond in (("buy", bc), ("sell", sc)):
            ev = [df.index[i] for i in edges(cond)]
            ev = [t for t in ev if t0 <= t <= t1]
            solid = list(tri[(tri.side == side) & (tri.kind == "solid")]["time"])
            allt = list(tri[tri.side == side]["time"])
            row[f"{side}_solid"] = f"{match(ev, solid)}/{len(solid)}"
            hit = match(ev, allt)
            row[f"{side}_all"] = f"{hit}/{len(allt)}"
            tot_hit += hit; tot_pred += len(ev)
        n_t = len(tri)
        rec, prec = tot_hit / n_t, (tot_hit / tot_pred if tot_pred else 0)
        row.update(predicted=tot_pred, recall=round(rec, 3), precision=round(prec, 3),
                   f1=round(2 * rec * prec / (rec + prec), 3) if rec + prec else 0.0)
        out.append(row)
    return sorted(out, key=lambda r: -r["f1"])


# ----------------------------------------------------------------------------- 4./5. accounting
def layered(df: pd.DataFrame, buy_i, sell_i, buy_frac: float, sell_frac: float, profit_only: bool,
            cost: float = 0.0005, start: int = 0) -> dict:
    """Conf-BT style: each buy spends a share of the cash, each sell sells a share of the holding."""
    o, c = df["open"].to_numpy(float), df["close"].to_numpy(float)
    sig = np.zeros(len(df), int); sig[[i for i in buy_i if i + 1 < len(df)]] = 1; sig[[i for i in sell_i if i + 1 < len(df)]] = -1
    cash, sh, cost_basis, eq = 1.0, 0.0, 0.0, []
    buys = sells = wins = 0
    for i in range(start, len(df)):
        s = sig[i - 1] if i > start else 0
        px = o[i]
        if s == 1 and cash > 1e-6:
            spend = cash * buy_frac
            q = spend * (1 - cost) / px
            cost_basis += spend; sh += q; cash -= spend; buys += 1
        elif s == -1 and sh > 0:
            avg = cost_basis / sh
            if not (profit_only and px * (1 - cost) <= avg):
                q = sh * sell_frac
                cash += q * px * (1 - cost); cost_basis -= avg * q; sh -= q; sells += 1
                wins += px * (1 - cost) > avg
        eq.append(cash + sh * c[i])
    eq = pd.Series(eq, index=df.index[start:])
    hold = pd.Series(c[start:] / c[start], index=eq.index)
    return {"buys": buys, "sells": sells, "win_pct": round(100 * wins / sells, 1) if sells else None,
            "roi_pct": round((eq.iat[-1] - 1) * 100, 1), "max_dd_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 1),
            "open_pct_of_equity": round(100 * sh * c[-1] / eq.iat[-1], 1) if eq.iat[-1] > 0 else None,
            "open_vs_cost_pct": round((sh * c[-1] / cost_basis - 1) * 100, 1) if sh > 0 and cost_basis > 0 else None,
            "hold_roi_pct": round((hold.iat[-1] - 1) * 100, 1), "hold_dd_pct": round(float((hold / hold.cummax() - 1).min()) * 100, 1)}


def rule_by_name(df, bands, name):
    for nm, bc, sc in rules(df, bands):
        if nm == name:
            return edges(bc), edges(sc)
    raise KeyError(name)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    tgt = json.loads(TARGET.read_text())
    res = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "conf_bt": tgt["conf_bt"]}
    um = hourly("UMAC")
    res["data"] = {"bars": len(um), "from": str(um.index[0]), "to": str(um.index[-1]), "source": FETCH_NOTES.get("UMAC"),
                   "bars_per_weekday": round(float(um.groupby(um.index.date).size().median()), 1)}
    res["alignment"] = al = align(um, tgt)
    log.info("alignment %s", al)
    env = envelope_fit(um, tgt, al["shift_h"])
    res["envelope_top"] = env[:15]
    top_bands = []
    for r in env:                                   # three distinct families/lengths for the rule search
        if all(abs(r["n"] - b["n"]) > 20 or r["family"] != b["family"] for b in top_bands):
            top_bands.append(r)
        if len(top_bands) == 3:
            break
    tri = triangle_fit(um, tgt, al["shift_h"], top_bands)
    res["triangles_top"] = tri[:20]
    # chance level: the best rule's signals shifted by a random number of days
    best = tri[0]
    b_i, s_i = rule_by_name(um, top_bands, best["rule"])
    rng = np.random.default_rng(7)
    pl = []
    tt = pd.DataFrame(tgt["triangles"]); tt["time"] = pd.to_datetime(tt["time"], utc=True) + pd.Timedelta(hours=al["shift_h"])
    for _ in range(200):
        off = int(rng.integers(30, 300))
        hits = sum(match([um.index[min(i + off, len(um) - 1)] for i in idx], list(tt[tt.side == side]["time"]))
                   for idx, side in ((b_i, "buy"), (s_i, "sell")))
        pl.append(hits / len(tt))
    res["placebo_recall_mean"] = round(float(np.mean(pl)), 3)
    # 4. its backtest table, several ways
    acc = {}
    for bf, sf, po in itertools.product((0.25, 0.5, 1.0), (0.5, 1.0), (False, True)):
        acc[f"buy {int(bf * 100)}% of cash, sell {int(sf * 100)}%{', only above cost' if po else ''}"] = \
            layered(um, b_i, s_i, bf, sf, po, cost=0.0005)
    res["umac_accounting"] = acc
    # 5. the best match on the watchlist, hourly, ~2 years
    import settings
    from config import load_config
    w = settings.watchlist(load_config(), settings.load(load_config()))
    wl = {}
    for asset, ts in (("stock", w["stocks"]), ("crypto", w["crypto"])):
        cost = 0.0025 if asset == "crypto" else 0.0005
        for t in ts:
            try:
                df = hourly(t, prepost=asset == "stock")
            except Exception as e:
                log.warning("%s: %s", t, e); continue
            b2, s2 = rule_by_name(df, top_bands, best["rule"])
            wl[t] = {"asset": asset,
                     "normal": layered(df, b2, s2, 0.5, 1.0, False, cost, start=400),
                     "only_above_cost": layered(df, b2, s2, 0.5, 0.5, True, cost, start=400)}
    res["watchlist"] = wl
    OUT.mkdir(exist_ok=True)
    (OUT / "confluence.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "confluence.md").write_text(report(res))
    log.info("done")


def _m(xs):
    xs = [x for x in xs if x is not None]
    return round(float(np.mean(xs)), 1) if xs else None


def report(r: dict) -> str:
    al = r["alignment"]
    L = [f"# IA-Confluence-Model rebuild and test ({r['generated']})", "",
         f"UMAC hourly from Yahoo ({r['data'].get('source')}): {r['data']['bars']} bars, {r['data']['bars_per_weekday']} a day "
         f"(the screenshot's chart had 24). "
         f"Screenshot line vs real prices: correlation {al['corr']}, median error {al['median_err_pct']}% (time shift {al['shift_h']} h).", "",
         "## Envelope (grey lines)", "", "| Formula | Length (our bars) | Width | Upper err % | Lower err % |", "|---|---|---|---|---|"]
    for e in r["envelope_top"][:8]:
        L.append(f"| {e['family']} | {e['n']} | {e['k']} | {e['err_upper_pct']} | {e['err_lower_pct']} |")
    L += ["", f"## Triangles (matched within ±{TOL_H} h; chance level for the best rule: {r['placebo_recall_mean']} recall)", "",
          "| Rule | Buys solid | Buys all | Sells solid | Sells all | Predicted | Recall | Precision | F1 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for t in r["triangles_top"][:12]:
        L.append(f"| {t['rule']} | {t['buy_solid']} | {t['buy_all']} | {t['sell_solid']} | {t['sell_all']} | "
                 f"{t['predicted']} | {t['recall']} | {t['precision']} | {t['f1']} |")
    L += ["", "## Its backtest table on UMAC (best rule, ~2 years of hourly bars)", "",
          f"Screenshot's table: {r['conf_bt']}", "",
          "| Sizing | Buys | Sells | Win % | ROI % | Worst drop % | Still held, % of equity | Held vs cost % | Hold ROI % |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, a in r["umac_accounting"].items():
        L.append(f"| {k} | {a['buys']} | {a['sells']} | {a['win_pct']} | {a['roi_pct']} | {a['max_dd_pct']} | "
                 f"{a['open_pct_of_equity']} | {a['open_vs_cost_pct']} | {a['hold_roi_pct']} |")
    for asset in ("stock", "crypto"):
        wl = {t: v for t, v in r["watchlist"].items() if v["asset"] == asset}
        if not wl:
            continue
        L += ["", f"## Best match on the watchlist {asset}s ({len(wl)} tickers, hourly, ~2 years)", "",
              "| Version | Win % | ROI % | Worst drop % | Beat holding |", "|---|---|---|---|---|"]
        for k, nm in (("normal", "Normal sells (sell all on a sell signal)"), ("only_above_cost", "Sell half, only above cost")):
            L.append(f"| {nm} | {_m([v[k]['win_pct'] for v in wl.values()])} | {_m([v[k]['roi_pct'] for v in wl.values()])} | "
                     f"{_m([v[k]['max_dd_pct'] for v in wl.values()])} | "
                     f"{sum(v[k]['roi_pct'] > v[k]['hold_roi_pct'] for v in wl.values())} of {len(wl)} |")
        L.append(f"| Just holding | – | {_m([v['normal']['hold_roi_pct'] for v in wl.values()])} | "
                 f"{_m([v['normal']['hold_dd_pct'] for v in wl.values()])} | – |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    try:
        main()
    except Exception:                       # keep the error readable in the results file (Actions logs aren't always reachable)
        import traceback
        OUT.mkdir(exist_ok=True)
        (OUT / "confluence.md").write_text("# Run failed\n\n```\n" + traceback.format_exc() + "```\n")
        raise SystemExit(0)
