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

import ladder
import models
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
    return max(2, 4 - math.floor(math.log10(price)))


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
    ov = res["overlays"]

    def series(s: pd.Series) -> list:
        return [_num(v, nd) for v in s.reindex(idx).values]

    lp = ladder.plan(res, cfg)
    for tier in lp["buys"] + lp["sells"]:
        tier["price"] = _num(tier["price"], nd)
    lp["anchor"], lp["step"], lp["distance"] = _num(lp["anchor"], nd), _num(lp["step"], nd), round(lp["distance"], 2)
    iv = ov["ia"]
    start = idx[0]
    ia_out = {
        "trend": iv["trend"], "stop_side": iv["stop_side"], "stop": _num(iv["stop_last"], nd),
        "bars_since_flip": iv["bars_since_flip"], "stop_key": iv["stop_key"],
        "ath": _num(iv["ath"], nd), "ath_from_history": iv["ath_from_history"],
        "levels": {str(k): _num(v, nd) for k, v in iv["levels"].items()},
        "level": round(iv["level"], 2), "pct_of_ath": round(iv["pct_of_ath"] * 100, 1),
        "flips": [{"t": int(ts.timestamp()), "side": side} for ts, side in iv["flips"] if ts >= start],
    }
    return {
        "ladder": lp,
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
        "models": [{"key": k, "short": models.SHORT.get(k, m.name), "name": m.name, "vote": m.vote,
                    "strength": m.strength, "reason": m.reason} for k, m in res["models"].items()],
        "layer": ov["layer"],
        "levels": {str(k): _num(v, nd) for k, v in ov["levels"].items()},
        "z": round(ov["z"], 2),
        "rsi": round(ov["rsi"], 1),
        "labels": ov["labels"],
        "segment": res.get("segment"),
        "segment_about": res.get("segment_about", ""),
        "engine": res.get("engine", "v1"),
        "t": [int(ts.timestamp()) for ts in idx],
        "o": series(df["open"]),
        "h": series(df["high"]),
        "l": series(df["low"]),
        "c": series(df["close"]),
        "v": [int(v) if v == v else 0 for v in df["volume"].values],
        "ov": {
            "ema_fast": series(ov["ema_fast"]),
            "ema_slow": series(ov["ema_slow"]),
            "ma_long": series(ov["ma_long"]),
            "bb_up": series(ov["bb_up"]),
            "bb_mid": series(ov["bb_mid"]),
            "bb_lo": series(ov["bb_lo"]),
            "anchor": series(ov["anchor"]),
            "ia_fast": series(iv["fast"]),
            "ia_slow": series(iv["slow"]),
            "ia_stop": series(iv["stop"]),
        },
        "ia": ia_out,
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
