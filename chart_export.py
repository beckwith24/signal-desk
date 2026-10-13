"""
Write chart data for the phone chart site: one JSON file per ticker/timeframe with candles,
indicator overlays, ATR layers, each model's reading, and past signals (for chart markers).
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from pathlib import Path

import pandas as pd

import storage
from data import is_crypto

log = logging.getLogger(__name__)
SITE_DIR = Path(os.environ.get("SIGNAL_DESK_SITE", Path(__file__).with_name("site")))
BARS = {"1d": 250, "4h": 300, "1h": 300, "1wk": 200}


def file_id(ticker: str, tf: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", f"{ticker}_{tf}")


def _decimals(price: float) -> int:
    if not price or price <= 0 or math.isnan(price):
        return 2
    return max(2, 5 - math.floor(math.log10(price)))


def _num(x, nd: int):
    if x is None:
        return None
    x = float(x)
    return None if math.isnan(x) or math.isinf(x) else round(x, nd)


def _ts(text: str) -> int | None:
    try:
        return int(pd.Timestamp(text.replace(" UTC", ""), tz="UTC").timestamp())
    except Exception:
        return None


def build_payload(res: dict, cfg: dict) -> dict:
    df = res["_df"].tail(BARS.get(res["timeframe"], 300))
    nd = _decimals(res["price"])
    idx = df.index
    mo = res["models"]
    tr, mr, al = mo["trend"].extra, mo["mean_reversion"].extra, mo["atr_layers"].extra

    def series(s: pd.Series) -> list:
        return [_num(v, nd) for v in s.reindex(idx).values]

    p = cfg["models"]
    return {
        "ticker": res["ticker"],
        "tf": res["timeframe"],
        "asset": "crypto" if is_crypto(res["ticker"], cfg) else "stock",
        "updated": res["ts"],
        "bar_time": res["bar_time"],
        "decimals": nd,
        "price": _num(res["price"], nd),
        "change_pct": round(float(res["change_pct"]), 2),
        "action": res["action"],
        "rank": res["rank"],
        "score": res["score"],
        "bull": res["bull"],
        "bear": res["bear"],
        "reasons": res["reasons"],
        "notes": res.get("notes", []),
        "models": [{"name": m.name, "vote": m.vote, "strength": m.strength, "reason": m.reason}
                   for m in mo.values()],
        "layer": al["layer"],
        "levels": {str(k): _num(v, nd) for k, v in al["levels"].items()},
        "z": mr["z"],
        "rsi": mo["confluence"].extra.get("rsi"),
        "labels": {"ema_fast": f"EMA {p['trend']['fast_ema']}", "ema_slow": f"EMA {p['trend']['slow_ema']}",
                   "ma_long": f"{p['trend']['long_ma']} MA", "anchor": f"{p['atr_layers']['anchor_ma']} MA (layer anchor)"},
        "t": [int(ts.timestamp()) for ts in idx],
        "o": series(df["open"]),
        "h": series(df["high"]),
        "l": series(df["low"]),
        "c": series(df["close"]),
        "v": [int(v) if v == v else 0 for v in df["volume"].values],
        "ov": {
            "ema_fast": series(tr["fast"]),
            "ema_slow": series(tr["slow"]),
            "ma_long": series(tr["long_ma"]),
            "bb_up": series(mr["bb_upper"]),
            "bb_mid": series(mr["bb_mid"]),
            "bb_lo": series(mr["bb_lower"]),
            "anchor": series(al["anchor"]),
        },
        "signals": [{"t": _ts(s["ts"]), "ts": s["ts"], "action": s["action"], "rank": s["rank"],
                     "score": s["score"], "price": _num(s["price"], nd)}
                    for s in storage.signals_for(res["ticker"], res["timeframe"])],
    }


def export_results(results: list[dict], cfg: dict, site_dir: Path = SITE_DIR) -> int:
    """Write one JSON file per result. Never raises: charts must not break alerts."""
    out = site_dir / "data"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for res in results:
        try:
            payload = build_payload(res, cfg)
            (out / f"{file_id(res['ticker'], res['timeframe'])}.json").write_text(
                json.dumps(payload, separators=(",", ":"), allow_nan=False))
            n += 1
        except Exception as e:
            log.error("Chart export failed for %s %s: %s", res.get("ticker"), res.get("timeframe"), e)
    return n
