"""
Screen candidate tickers before adding them to the watchlist.

For each candidate it checks that the app can actually get its prices (crypto must be on Kraken,
the app's crypto source), then pulls today's numbers: growth and valuation (stocks, from Yahoo),
returns, distance from the high, trading volume, the app's current daily signal and the
InvestAnswers-style view. For crypto it also replays the app's tested daily trend rule
(3 of 4 trend models bullish) against simply holding, over the history Kraken provides (~2 years).

    python screen_candidates.py            (Actions tab -> "Candidate screen")

Writes research/candidates.md and research/candidates.json. Data, not advice.
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
import data
import models
import scanner
from config import load_config

log = logging.getLogger("screen")
OUT = Path(__file__).with_name("research")

STOCKS = {
    "AI chips & chip equipment": ["TSM", "ASML", "AMAT", "LRCX", "KLAC", "ARM", "ALAB", "CRDO", "INTC", "QCOM"],
    "Memory & storage": ["SNDK", "WDC", "STX"],
    "AI servers, networking & optics": ["DELL", "ANET", "VRT", "CLS", "LITE", "COHR", "CIEN", "HPE"],
    "AI cloud": ["NBIS", "CRWV", "ORCL", "AMZN"],
    "Software": ["CRWD", "PANW", "NET", "SNOW", "DDOG", "APP", "NOW", "SHOP", "FTNT", "UBER", "NFLX"],
    "Fintech & crypto stocks": ["HOOD", "COIN", "SOFI", "MSTR", "CRCL"],
    "Power for AI": ["BE", "VST", "CEG", "GEV", "OKLO"],
    "Health & other": ["LLY", "RKLB", "ISRG"],
    "Solana treasury stocks": ["DFDV", "UPXI", "FORD", "HSDT"],
}
CRYPTO = {
    "Solana: DeFi & infrastructure": ["JUP", "JTO", "PYTH", "RAY", "ORCA", "KMNO", "DRIFT", "MET", "W", "2Z", "TNSR", "CLOUD"],
    "Solana: launchpads & memes": ["PUMP", "BONK", "WIF", "TRUMP", "PENGU", "POPCAT", "FARTCOIN", "MEW", "GIGA", "SPX"],
    "Solana: AI & DePIN": ["RENDER", "HNT", "GRASS", "IO", "NOS", "GEOD"],
    "Other large coins": ["HYPE", "SUI", "XRP", "BNB", "DOGE", "TAO", "ENA", "AAVE", "NEAR", "ADA", "ONDO"],
}
TREND4 = ["tsmom28", "sma_ensemble", "donchian_ensemble", "btc_trend_gate"]


def _f(x, nd=1, pct=False):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x * 100, nd) if pct else round(x, nd)


def perf(df: pd.DataFrame) -> dict:
    c = df["close"]
    out = {}
    for name, n in (("ret_1m", 21), ("ret_3m", 63), ("ret_6m", 126), ("ret_1y", 252)):
        out[name] = _f(c.iat[-1] / c.iat[-n - 1] - 1, pct=True) if len(c) > n else None
    hi = df["high"].iloc[-252:].max()
    out["from_52w_high"] = _f(c.iat[-1] / hi - 1, pct=True)
    out["above_200d"] = bool(c.iat[-1] > c.rolling(200).mean().iat[-1]) if len(c) >= 200 else None
    out["vol_ann"] = _f(np.log(c).diff().iloc[-252:].std() * np.sqrt(252), pct=True)
    return out


def view(res: dict) -> dict:
    iv = res["overlays"]["ia"]
    return {"signal": res["action"], "ia_ribbon": "blue" if iv["trend"] == "up" else "orange",
            "ia_atr": iv["stop_side"], "pct_of_ath": _f(iv["pct_of_ath"], pct=True),
            "reasons": res["reasons"][:2]}


def stock_row(t: str, cfg: dict) -> dict:
    import yfinance as yf
    res = scanner.scan_one(t, "1d", cfg)
    df = res["_df"]
    info = {}
    for attempt in range(2):
        try:
            info = yf.Ticker(t).info or {}
            break
        except Exception as e:
            log.info("%s info failed: %s", t, e); time.sleep(2)
    price = float(df["close"].iat[-1])
    tgt = info.get("targetMeanPrice")
    return {"ticker": t, "name": info.get("shortName") or t, "price": _f(price, 2),
            "mcap_b": _f((info.get("marketCap") or 0) / 1e9, 0),
            "rev_growth": _f(info.get("revenueGrowth"), pct=True),
            "eps_growth": _f(info.get("earningsGrowth"), pct=True),
            "fwd_pe": _f(info.get("forwardPE"), 1), "gross_margin": _f(info.get("grossMargins"), pct=True, nd=0),
            "analyst_upside": _f(tgt / price - 1, pct=True) if tgt else None,
            "analysts": info.get("numberOfAnalystOpinions"), "rec_mean": _f(info.get("recommendationMean"), 2),
            "dollar_vol_m": _f((df["close"] * df["volume"]).iloc[-30:].mean() / 1e6, 0),
            **perf(df), **view(res)}


def trend_replay(df: pd.DataFrame, ctx: dict, cost: float = 0.0025) -> dict:
    """The app's crypto-daily rule (3 of 4 trend models bullish) vs holding, on this coin's history."""
    v = pd.DataFrame({k: models.run(k, df, ctx)["vote"] for k in TREND4})
    pos = (v.mean(axis=1) > 0.5).astype(float)
    r = df["close"].pct_change().shift(-1).fillna(0)
    strat = pos * r - cost * pos.diff().abs().fillna(pos.iloc[0])
    start = 100 if len(df) > 250 else 50                       # let the slower models warm up
    s, h = strat.iloc[start:], r.iloc[start:]
    eq, heq = (1 + s).cumprod(), (1 + h).cumprod()
    return {"days": int(len(s)), "rule_ret": _f(eq.iat[-1] - 1, pct=True, nd=0), "hold_ret": _f(heq.iat[-1] - 1, pct=True, nd=0),
            "rule_mdd": _f((eq / eq.cummax() - 1).min(), pct=True, nd=0), "hold_mdd": _f((heq / heq.cummax() - 1).min(), pct=True, nd=0),
            "invested": _f(pos.iloc[start:].mean(), pct=True, nd=0)}


def crypto_row(base: str, cfg: dict) -> dict:
    t = f"{base}-USD"
    try:
        df = data.fetch_ccxt(t, "1d", cfg)
    except Exception as e:
        return {"ticker": t, "on_kraken": False, "note": str(e)[:80]}
    res = scanner.scan_one(t, "1d", cfg)
    df = res["_df"]
    ctx = context.align(scanner.daily_context("crypto", cfg), df.index, "crypto", "1d")
    vol = (df["close"] * df["volume"]).iloc[-30:].mean()
    row = {"ticker": t, "on_kraken": True, "price": _f(df["close"].iat[-1], 6), "days": len(df),
           "kraken_dollar_vol_k": _f(vol / 1e3, 0), **perf(df), **view(res)}
    row["ret_1y"] = row["ret_1y"] if len(df) > 252 else None
    try:
        row.update({"replay_" + k: v for k, v in trend_replay(df, ctx).items()})
    except Exception as e:
        row["replay_error"] = str(e)[:80]
    return row


def table(rows: list[dict], cols: list[tuple[str, str]]) -> str:
    L = ["| " + " | ".join(h for _, h in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        cells = []
        for k, _ in cols:
            v = r.get(k)
            cells.append("–" if v is None else ("✓" if v is True else "✗" if v is False else str(v)))
        L.append("| " + " | ".join(cells) + " |")
    return "\n".join(L)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "stocks": {}, "crypto": {}}
    for group, ts in STOCKS.items():
        for t in ts:
            try:
                out["stocks"].setdefault(group, []).append(stock_row(t, cfg))
            except Exception as e:
                out["stocks"].setdefault(group, []).append({"ticker": t, "error": str(e)[:100]})
                log.warning("%s failed: %s", t, e)
    for group, bs in CRYPTO.items():
        for b in bs:
            try:
                out["crypto"].setdefault(group, []).append(crypto_row(b, cfg))
            except Exception as e:
                out["crypto"].setdefault(group, []).append({"ticker": b + "-USD", "error": str(e)[:100]})
                log.warning("%s failed: %s", b, e)
    OUT.mkdir(exist_ok=True)
    (OUT / "candidates.json").write_text(json.dumps(out, indent=1, default=str))
    L = [f"# Candidate screen ({out['generated']})", "",
         "Data, not advice. Growth = latest quarter vs a year ago (Yahoo). Signal = the app's daily signal today. "
         "IA = ribbon colour / ATR model side.", ""]
    sc = [("ticker", "Ticker"), ("mcap_b", "Mkt cap $B"), ("rev_growth", "Rev growth %"), ("eps_growth", "EPS growth %"),
          ("fwd_pe", "Fwd P/E"), ("ret_6m", "6m %"), ("ret_1y", "1y %"), ("from_52w_high", "From high %"),
          ("above_200d", ">200d"), ("analyst_upside", "Analyst upside %"), ("signal", "Signal"), ("ia_ribbon", "IA ribbon"),
          ("ia_atr", "IA ATR")]
    for g, rows in out["stocks"].items():
        L += [f"## {g}", "", table(rows, sc), ""]
    cc = [("ticker", "Ticker"), ("on_kraken", "Kraken"), ("kraken_dollar_vol_k", "Kraken $vol/day (k)"), ("ret_3m", "3m %"),
          ("ret_6m", "6m %"), ("from_52w_high", "From 1y high %"), ("pct_of_ath", "% of high"), ("signal", "Signal"),
          ("ia_ribbon", "IA ribbon"), ("ia_atr", "IA ATR"), ("replay_days", "Replay days"), ("replay_rule_ret", "Trend rule %"),
          ("replay_hold_ret", "Hold %"), ("replay_rule_mdd", "Rule worst %"), ("replay_hold_mdd", "Hold worst %")]
    for g, rows in out["crypto"].items():
        L += [f"## {g}", "", table(rows, cc), ""]
    (OUT / "candidates.md").write_text("\n".join(L))
    log.info("done")


if __name__ == "__main__":
    main()
