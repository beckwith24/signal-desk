"""
"What's driving it": a short, data-built note per ticker comparing the business with the share price.

Stocks: latest-quarter sales and earnings growth (vs a year ago), margins, next earnings date and analyst
targets from Yahoo, against the price move (1 month, 1 year, distance from the high, vs the S&P 500), plus a
plain read of whether they agree, and the latest headlines. Crypto: price vs Bitcoin plus headlines.
No AI: every sentence is filled in from numbers, so it never invents a reason.

Runs once a day (Actions -> "Ticker notes"); writes narratives.json, which the site build publishes.

    python narrative.py
"""
from __future__ import annotations

import json
import logging
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import settings
from config import load_config

log = logging.getLogger("narrative")
OUT = Path(__file__).with_name("narratives.json")


def _f(x):
    try:
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else x
    except (TypeError, ValueError):
        return None


def pct(x, nd=0, sign=True):
    return "–" if x is None else (f"{x:+.{nd}f}%" if sign else f"{x:.{nd}f}%")


NEWS_DEBUG: list[str] = []


def company_word(t: str, info: dict) -> str | None:
    """The word a headline about this company would use: 'Nvidia', 'Astera', 'Exxon', 'Bitcoin', 'Solana'..."""
    name = (info.get("shortName") or info.get("longName") or "").replace(",", " ")
    for w in name.split():
        w = re.sub(r"[^A-Za-z0-9&.-]", "", w)
        if len(w) >= 3 and w.lower() not in {"the", "inc", "corp", "usd", "class", "holdings", "group", "technologies", "co"}:
            return w
    return None


def headlines(tk, info: dict, days: int = 21, n: int = 3) -> list[dict]:
    """Recent headlines that actually name the company or ticker (Yahoo's search is loose)."""
    t = tk.ticker
    word = company_word(t, info)
    base = t.split("-")[0]
    pats = [re.compile(rf"\b{re.escape(base)}\b")] if len(base) >= 2 else []
    if word:
        pats.append(re.compile(re.escape(word), re.I))
    items = []
    try:
        items = list(tk.news or [])
    except Exception:
        pass
    import yfinance as yf
    for q in dict.fromkeys([q for q in (word if t.endswith("-USD") else None, t, word) if q]):
        if len(items) >= 20:
            break
        try:
            items += list(yf.Search(q, news_count=20).news or [])
        except Exception as e:
            NEWS_DEBUG.append(f"{t} search {q}: {type(e).__name__}")
    cut = time.time() - days * 86400
    out, seen = [], set()
    for it in items:
        c = it.get("content", it)                          # newer yfinance nests the story under "content"
        title = c.get("title")
        url = (c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url") or c.get("link")
        src = (c.get("provider") or {}).get("displayName") or c.get("publisher")
        when = c.get("pubDate") or c.get("providerPublishTime")
        try:
            ts = pd.Timestamp(when, unit="s", tz="UTC") if isinstance(when, (int, float)) else pd.Timestamp(when)
            ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
        except Exception:
            ts = None
        if not title or not url or not str(url).startswith("http") or title in seen:
            continue
        if ts is not None and ts.timestamp() < cut:
            continue
        if not any(p.search(title) for p in pats):
            continue
        seen.add(title)
        out.append({"title": str(title)[:160], "url": str(url), "source": src, "date": ts.date().isoformat() if ts is not None else None,
                    "_ts": ts.timestamp() if ts is not None else 0})
    out.sort(key=lambda h: -h["_ts"])
    for h in out:
        h.pop("_ts")
    NEWS_DEBUG.append(f"{t}: {len(items)} raw, {len(out)} kept (word {word})")
    return out[:n]


def price_facts(h: pd.DataFrame, bench: pd.Series | None) -> dict:
    c = h["Close"].dropna()
    ret = lambda n: (c.iat[-1] / c.iat[-n - 1] - 1) * 100 if len(c) > n else None
    out = {"m1": ret(21), "m3": ret(63), "y1": ret(252), "from_high": (c.iat[-1] / h["High"].iloc[-252:].max() - 1) * 100}
    if bench is not None and len(bench) > 63:
        b = bench.reindex(c.index).ffill()
        out["vs_bench_3m"] = out["m3"] - (b.iat[-1] / b.iat[-64] - 1) * 100 if out["m3"] is not None else None
    return out


def read(g_rev, g_eps, p) -> str:
    """One plain sentence on whether the latest results and the price agree. Deliberately cautious."""
    strong = (g_rev is not None and g_rev >= 15) or (g_eps is not None and g_eps >= 20)
    weak = (g_rev is not None and g_rev < 0) or (g_eps is not None and g_eps <= -10)
    fell = p["from_high"] is not None and p["from_high"] <= -15
    near_high = p["from_high"] is not None and p["from_high"] >= -5
    if strong and fell:
        return ("The latest results were strong, so the drop from the high isn't explained by the last report: "
                "it's coming from outlook, valuation or the wider market.")
    if weak and fell:
        return "Results and price are both weakening: the drop lines up with slowing business."
    if weak and near_high:
        return "The price is near its high even though the latest results slowed: the market is looking past them."
    if strong and near_high:
        return "Strong results and a price near its high: business and stock are moving together."
    return "No clear gap between the latest results and the price move."


def stock_note(t: str, spy: pd.Series | None) -> dict:
    import yfinance as yf
    tk = yf.Ticker(t)
    info = {}
    for attempt in range(2):
        try:
            info = tk.info or {}; break
        except Exception as e:
            log.info("%s info: %s", t, e); time.sleep(2)
    h = tk.history(period="14mo", auto_adjust=True)
    p = price_facts(h, spy)
    g_rev, g_eps = _f(info.get("revenueGrowth")), _f(info.get("earningsGrowth"))
    g_rev = g_rev * 100 if g_rev is not None else None
    g_eps = g_eps * 100 if g_eps is not None else None
    gm, om = _f(info.get("grossMargins")), _f(info.get("operatingMargins"))
    parts = []
    if g_rev is not None or g_eps is not None:
        s = "Business: latest quarter " + ", ".join(x for x in (
            f"sales {pct(g_rev)}" if g_rev is not None else "", f"earnings {pct(g_eps)}" if g_eps is not None else "") if x)
        s += " vs a year ago"
        if om is not None:
            s += f"; operating margin {om * 100:.0f}%"
        parts.append(s + ".")
    s = f"Stock: {pct(p['m1'])} this month, {pct(p['y1'])} over a year, {abs(p['from_high']):.0f}% below its 52-week high"
    if p.get("vs_bench_3m") is not None:
        s += f"; {'ahead of' if p['vs_bench_3m'] >= 0 else 'behind'} the S&P 500 by {abs(p['vs_bench_3m']):.0f} points over 3 months"
    parts.append(s + ".")
    if g_rev is not None or g_eps is not None:
        parts.append(read(g_rev, g_eps, p))
    extra = []
    ts = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
    if ts and ts > time.time() - 86400:
        extra.append("Next earnings: " + datetime.fromtimestamp(ts, timezone.utc).strftime("%b %-d"))
    tgt, px, n = _f(info.get("targetMeanPrice")), _f(info.get("currentPrice") or info.get("regularMarketPrice")), info.get("numberOfAnalystOpinions")
    if tgt and px and n:
        extra.append(f"analysts' average target {pct((tgt / px - 1) * 100)} away ({n} analysts, '{info.get('recommendationKey', '?')}')")
    return {"text": parts, "extra": "; ".join(extra), "news": headlines(tk, info),
            "data": {"rev_growth": g_rev, "eps_growth": g_eps, "gross_margin": gm, "op_margin": om, **p}}


def crypto_note(t: str, btc: pd.Series | None) -> dict:
    import yfinance as yf
    tk = yf.Ticker(t)
    try:
        h = tk.history(period="14mo", auto_adjust=True)
    except Exception:
        h = pd.DataFrame()
    parts = []
    if len(h) > 30:
        p = price_facts(h, btc if t != "BTC-USD" else None)
        s = f"Price: {pct(p['m1'])} this month, {pct(p['y1'])} over a year, {abs(p['from_high']):.0f}% below its 52-week high"
        if p.get("vs_bench_3m") is not None:
            s += f"; {'ahead of' if p['vs_bench_3m'] >= 0 else 'behind'} Bitcoin by {abs(p['vs_bench_3m']):.0f} points over 3 months"
        parts.append(s + ".")
        parts.append("Coins have no sales or earnings to compare; the headlines below are the best guide to what's moving it.")
    try:
        info = tk.info or {}
    except Exception:
        info = {}
    return {"text": parts, "extra": "", "news": headlines(tk, info)}


def clean(x):
    """JSON the browser can read: NaN/inf become null, numpy numbers become plain ones, rounded."""
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if math.isnan(x) or math.isinf(x) else round(float(x), 2)
    if isinstance(x, np.integer):
        return int(x)
    return x


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    import yfinance as yf
    cfg = settings.apply(load_config(), settings.load(load_config()))
    bench = {}
    for s in ("SPY", "BTC-USD"):
        try:
            bench[s] = yf.Ticker(s).history(period="14mo", auto_adjust=True)["Close"]
        except Exception:
            bench[s] = None
    notes = {}
    for t in cfg["watchlist"]["stocks"]:
        try:
            notes[t] = stock_note(t, bench["SPY"])
        except Exception as e:
            log.warning("%s: %s", t, e)
        time.sleep(0.5)
    for t in cfg["watchlist"]["crypto"]:
        try:
            notes[t] = crypto_note(t, bench["BTC-USD"])
        except Exception as e:
            log.warning("%s: %s", t, e)
        time.sleep(0.3)
    OUT.write_text(json.dumps(clean({"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "notes": notes, "news_debug": NEWS_DEBUG[-70:]}),
                              indent=1, default=str, allow_nan=False))
    log.info("notes for %d tickers", len(notes))


if __name__ == "__main__":
    main()
