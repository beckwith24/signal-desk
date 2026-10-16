"""
Check the Confluence rebuild against the AVGO 2h screenshot (research/ia_targets/avgo_conf.json).

The screenshot's chart uses a 24x5 session (overnight trading included); Yahoo has no overnight bars, so
we try the closest bar sets Yahoo offers and measure the band length in trading days:
  2h_ext   2-hour bars from 04:00-20:00 ET (8 a day)
  1h_ext   1-hour bars, same hours (16 a day)
  2h_reg   2-hour bars in regular hours (9:30, 11:30, 13:30, 15:30)
For each: line alignment (our close vs the screenshot's price line, best time shift), then the band
(Bollinger on close, length 1-15 days, width 1.5-3.0) vs the digitised grey lines, then whether
"close back inside the band" lands on the screenshot's triangles.

    python conf_avgo.py      (Actions -> "Confluence AVGO check"); writes research/conf_avgo.md
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
ET = "America/New_York"


def load() -> dict[str, pd.DataFrame]:
    import yfinance as yf
    h = yf.Ticker("AVGO").history(period="200d", interval="1h", prepost=True, auto_adjust=True)
    h = h.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
    h.index = pd.DatetimeIndex(h.index).tz_convert(ET)
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ext2 = h.resample("2h", origin="start_day", offset="4h").agg(agg).dropna(subset=["close"])
    reg = h.between_time("09:30", "15:59")
    t = reg.index
    mins = (t.hour * 60 + t.minute - 570) // 120
    start = t.normalize() + pd.to_timedelta(570 + mins * 120, unit="m")
    reg2 = reg.groupby(start).agg(agg).dropna(subset=["close"])
    reg2.index = pd.DatetimeIndex(reg2.index).tz_localize(ET) if reg2.index.tz is None else reg2.index
    return {"2h_ext": ext2, "1h_ext": h, "2h_reg": reg2}


def per_day(df: pd.DataFrame) -> float:
    return float(df.groupby(df.index.date).size().median())


def at(series: pd.Series, times: pd.DatetimeIndex) -> np.ndarray:
    s = series.copy(); s.index = s.index.tz_convert("UTC")
    return s.asof(times).to_numpy(float)


def main() -> None:
    tgt = json.loads((ROOT / "research/ia_targets/avgo_conf.json").read_text())
    up = pd.DataFrame(tgt["upper"]); lo = pd.DataFrame(tgt["lower"]); ln = pd.DataFrame(tgt["line"])
    for d in (up, lo, ln):
        d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601")
    L = ["# Confluence rebuild vs the AVGO 2h screenshot", "",
         "Screenshot: 24x5 session (overnight included); Yahoo has no overnight bars, so these are the closest sets.", ""]
    best_all = []
    for name, df in load().items():
        bpd = per_day(df)
        c = df["close"]
        # 1. line alignment
        shifts = []
        for sh in range(-24, 25, 1):
            x = at(c, pd.DatetimeIndex(ln["time"] + pd.Timedelta(hours=sh)))
            ok = ~np.isnan(x)
            if ok.sum() > 50:
                shifts.append((float(np.corrcoef(x[ok], ln["price"].to_numpy()[ok])[0, 1]), sh,
                               float(np.median(np.abs(x[ok] / ln["price"].to_numpy()[ok] - 1))) * 100))
        corr, sh, err = max(shifts)
        L += [f"## {name} ({bpd:.0f} bars a day, {len(df)} bars)", "",
              f"Price line vs real closes: correlation {corr:.3f}, median error {err:.2f}% at a {sh:+d} h shift.", "",
              "| Days | Bars | Width | Upper err % | Lower err % | Mean % |", "|---|---|---|---|---|---|"]
        tu = pd.DatetimeIndex(up["time"] + pd.Timedelta(hours=sh)); tl = pd.DatetimeIndex(lo["time"] + pd.Timedelta(hours=sh))
        rows = []
        for days in np.arange(1, 15.01, 0.5):
            n = max(3, int(round(days * bpd)))
            m, sd = c.rolling(n).mean(), c.rolling(n).std(ddof=0)
            for k in np.arange(1.5, 3.01, 0.25):
                u, l_ = at(m + k * sd, tu), at(m - k * sd, tl)
                eu = np.nanmedian(np.abs(u / up["price"].to_numpy() - 1)) * 100
                el = np.nanmedian(np.abs(l_ / lo["price"].to_numpy() - 1)) * 100
                rows.append((round((eu + el) / 2, 2), float(days), n, float(k), round(eu, 2), round(el, 2)))
        rows.sort()
        for r in rows[:8]:
            L.append(f"| {r[1]:g} | {r[2]} | {r[3]:g} | {r[4]} | {r[5]} | {r[0]} |")
        mean, days, n, k = rows[0][0], rows[0][1], rows[0][2], rows[0][3]
        best_all.append((mean, name, days, n, k, sh))
        # 3. triangles: close back inside the best band
        m, sd = c.rolling(n).mean(), c.rolling(n).std(ddof=0)
        upb, lob = m + k * sd, m - k * sd
        buy = (c > lob) & (c.shift(1) < lob.shift(1))
        sell = (c < upb) & (c.shift(1) > upb.shift(1))
        ev = [(t.tz_convert("UTC"), "buy") for t in c.index[buy]] + [(t.tz_convert("UTC"), "sell") for t in c.index[sell]]
        t0, t1 = up["time"].min(), up["time"].max() + pd.Timedelta(hours=12)
        ev = [(t - pd.Timedelta(hours=sh), s) for t, s in ev if t0 <= t - pd.Timedelta(hours=sh) <= t1]
        hits = []
        for tr in tgt["triangles"]:
            tt = pd.Timestamp(tr["time"])
            near = [abs((t - tt).total_seconds()) / 3600 for t, s in ev if s == tr["side"]]
            hits.append(f"{tr['side']} {tr['kind']} {tt.tz_convert(ET):%b %d %H:%M}: "
                        f"{'nearest ' + format(min(near), '.0f') + ' h' if near else 'none'}")
        L += ["", f"Triangles with the best band ({days:g} days, width {k:g}); predicted in the window: "
              f"{sum(s == 'buy' for _, s in ev)} buys, {sum(s == 'sell' for _, s in ev)} sells.", ""] + [f"- {h}" for h in hits] + [""]
    best_all.sort()
    b = best_all[0]
    L += ["## Best overall", "", f"{b[1]}: {b[2]:g} trading days ({b[3]} bars), width {b[4]:g}, error {b[0]}%, shift {b[5]:+d} h.", ""]
    (ROOT / "research/conf_avgo.md").write_text("\n".join(L) + "\n")
    (ROOT / "research/conf_avgo.json").write_text(json.dumps(
        {"best": {"bars": b[1], "days": b[2], "n": b[3], "k": b[4], "err_pct": b[0], "shift_h": b[5]}}, indent=1))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        (ROOT / "research/conf_avgo.md").write_text("# Run failed\n\n```\n" + traceback.format_exc() + "```\n")
