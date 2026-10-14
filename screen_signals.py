"""
Which stocks are a Strong Buy today, by this app's own daily signal, but not on the watchlist yet?

Universe: S&P 500 + Nasdaq-100 (from Wikipedia) + popular growth names. Batch-downloads ~2 years of daily
prices, runs the app's stock-daily engine on each (same models and thresholds as the live scan), then pulls
size, growth and valuation from Yahoo for the Strong Buys and the biggest Buys.

    python screen_signals.py         (Actions tab -> "Signal screen")

Writes research/signal_screen.md and research/signal_screen.json. Data, not advice.
"""
from __future__ import annotations

import io
import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import context
import engine
import models
import scanner
import settings
from config import load_config
from data import _normalize

log = logging.getLogger("signal_screen")
OUT = Path(__file__).with_name("research")
EXTRA = ("SOFI RKLB IONQ OKLO SMR ASTS NBIS CRWV APP AFRM NET SNOW MDB U RBLX COIN MSTR HIMS ARM SMCI VRT TLN RDDT "
         "DUOL CVNA NU MELI SE SHOP SPOT CELH TOST SOUN RGTI QBTS LUNR ACHR JOBY PATH S GTLB IOT ZS TEAM WDAY DDOG "
         "CRWD CRCL FIG KTOS AVAV RBRK CIEN COHR NVT POWL STRL FN IREN CIFR WULF HUT CLS VIK ONON DECK AXON "
         "TTD PINS SNAP UBER ABNB DASH TSM ASML BABA PDD").split()


def wiki(url: str, col: str) -> list[str]:
    import requests
    html = requests.get(url, headers={"User-Agent": "signal-desk research (github.com)"}, timeout=30).text
    for t in pd.read_html(io.StringIO(html)):
        if col in t.columns and len(t) > 90:
            return [str(s).strip().replace(".", "-") for s in t[col].dropna()]
    return []


def universe(have: set[str]) -> tuple[list[str], dict]:
    src = {}
    for name, url, col in (("S&P 500", "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol"),
                           ("Nasdaq-100", "https://en.wikipedia.org/wiki/Nasdaq-100", "Ticker")):
        try:
            src[name] = wiki(url, col)
        except Exception as e:
            log.warning("%s list failed: %s", name, e); src[name] = []
    if not src["S&P 500"]:
        from factor_research import SP100
        src["S&P 100 (fallback)"] = list(SP100)
    src["growth extras"] = EXTRA
    allt = sorted({t for v in src.values() for t in v if t and t not in have})
    return allt, {k: len(v) for k, v in src.items()}


def download(tickers: list[str]) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), 100):
        batch = tickers[i:i + 100]
        for attempt in range(3):
            try:
                d = yf.download(batch, period="2y", interval="1d", auto_adjust=True, group_by="ticker",
                                progress=False, threads=True)
                break
            except Exception as e:
                log.warning("batch %d: %s", i, e); time.sleep(10 * (attempt + 1)); d = None
        if d is None:
            continue
        for t in batch:
            try:
                df = _normalize(d[t] if isinstance(d.columns, pd.MultiIndex) else d)
                if len(df) >= 250:
                    out[t] = df
            except Exception:
                pass
        time.sleep(1)
    return out


def _f(x, nd=1, pct=False):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x * 100, nd) if pct else round(x, nd)


def facts(df: pd.DataFrame) -> dict:
    c = df["close"]
    ret = lambda n: _f(c.iat[-1] / c.iat[-n - 1] - 1, pct=True) if len(c) > n else None
    return {"price": _f(c.iat[-1], 2), "chg_pct": _f(c.iat[-1] / c.iat[-2] - 1, pct=True, nd=2),
            "ret_1m": ret(21), "ret_3m": ret(63), "ret_1y": ret(252),
            "from_high": _f(c.iat[-1] / df["high"].iloc[-252:].max() - 1, pct=True),
            "vol_pct": _f(np.log(c).diff().iloc[-252:].std() * np.sqrt(252), pct=True, nd=0),
            "dollar_vol_m": _f((c * df["volume"]).iloc[-30:].mean() / 1e6, 0)}


def info(t: str) -> dict:
    import yfinance as yf
    for attempt in range(2):
        try:
            i = yf.Ticker(t).info or {}
            tgt, px = i.get("targetMeanPrice"), i.get("currentPrice") or i.get("regularMarketPrice")
            return {"name": i.get("shortName") or t, "sector": i.get("sector"),
                    "mcap_b": _f((i.get("marketCap") or 0) / 1e9, 0), "rev_growth": _f(i.get("revenueGrowth"), pct=True),
                    "eps_growth": _f(i.get("earningsGrowth"), pct=True), "fwd_pe": _f(i.get("forwardPE")),
                    "analyst_upside": _f(tgt / px - 1, pct=True) if tgt and px else None}
        except Exception as e:
            log.info("%s info: %s", t, e); time.sleep(2)
    return {"name": t}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = settings.apply(load_config(), settings.load(load_config()))
    have = set(cfg["watchlist"]["stocks"])
    tickers, sources = universe(have)
    log.info("universe %d (%s)", len(tickers), sources)
    prices = download(tickers)
    daily = scanner.daily_context("stock", cfg)
    vix, vix3m = daily.get("vix"), daily.get("vix3m")
    rows = []
    for t, df in prices.items():
        try:
            ctx = context.align(daily, df.index, "stock", "1d"); ctx["ath_known"] = None
            r = engine.evaluate(df, cfg, "stock", "1d", ctx)
        except Exception as e:
            log.info("%s: %s", t, e); continue
        fired = [models.SHORT.get(k, k) for k, m in r["models"].items() if m.vote > 0]
        rows.append({"ticker": t, "action": r["action"], "fired": fired, "reasons": r["reasons"][:3], **facts(df)})
    strong = [r for r in rows if r["action"] == "Strong Buy"]
    buys = sorted([r for r in rows if r["action"] == "Buy"], key=lambda r: -(r["dollar_vol_m"] or 0))
    for r in strong + buys[:25]:
        r.update(info(r["ticker"])); time.sleep(0.3)
    res = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "sources": sources,
           "screened": len(rows), "universe": len(tickers),
           "vix": _f(vix.iat[-1], 2) if vix is not None else None, "vix3m": _f(vix3m.iat[-1], 2) if vix3m is not None else None,
           "counts": {a: sum(r["action"] == a for r in rows) for a in ("Strong Buy", "Buy", "Hold")},
           "strong": sorted(strong, key=lambda r: -(r.get("mcap_b") or 0)), "top_buys": buys[:25]}
    OUT.mkdir(exist_ok=True)
    (OUT / "signal_screen.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "signal_screen.md").write_text(report(res))
    log.info("done: %s", res["counts"])


def report(r: dict) -> str:
    panic = r["vix"] and r["vix3m"] and r["vix"] > r["vix3m"]
    L = [f"# Stocks not on the watchlist, by today's app signal ({r['generated']})", "",
         f"Screened {r['screened']} of {r['universe']} stocks ({', '.join(f'{k} {v}' for k, v in r['sources'].items())}). "
         f"Today: {r['counts']['Strong Buy']} Strong Buy, {r['counts']['Buy']} Buy. VIX {r['vix']} vs 3-month VIX {r['vix3m']}"
         f" ({'panic reading ON: every stock gets the VIX vote, so one more dip signal makes a Strong Buy' if panic else 'no panic reading'}).",
         "", "A stock Strong Buy = 2+ of the 3 dip signals (RSI dip, low close, VIX panic) while above its 200-day average. "
         "Tested edge: about +0.9% vs normal over the next 5 days (2021-26). It's a short-term entry signal, not a long-term pick.", "",
         "## Strong Buys", "",
         "| Ticker | Name | Sector | Mkt cap $B | Signals | 1m % | 1y % | From high % | Rev growth % | Fwd P/E | $ vol/day M |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in r["strong"]:
        L.append(f"| {x['ticker']} | {x.get('name', '')} | {x.get('sector') or '–'} | {x.get('mcap_b') or '–'} | {', '.join(x['fired'])} | "
                 f"{x['ret_1m']} | {x['ret_1y']} | {x['from_high']} | {x.get('rev_growth') if x.get('rev_growth') is not None else '–'} | "
                 f"{x.get('fwd_pe') or '–'} | {x['dollar_vol_m']} |")
    L += ["", "## Biggest Buys (one dip signal)", "", "| Ticker | Name | Signals | 1y % | From high % | $ vol/day M |", "|---|---|---|---|---|---|"]
    for x in r["top_buys"]:
        L.append(f"| {x['ticker']} | {x.get('name', '')} | {', '.join(x['fired'])} | {x['ret_1y']} | {x['from_high']} | {x['dollar_vol_m']} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        OUT.mkdir(exist_ok=True)
        (OUT / "signal_screen.md").write_text("# Run failed\n\n```\n" + traceback.format_exc() + "```\n")
