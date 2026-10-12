"""Scan tickers, evaluate models, persist state, and fire de-duplicated alerts."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import storage
from data import fetch_funding_rate, fetch_ohlcv, is_crypto
from notify import format_message, send_all
from signals import evaluate, volume_note

log = logging.getLogger(__name__)
MIN_RANK = {"Watch": 1, "Buy": 2, "Strong Buy": 3}


def scan_one(ticker: str, tf: str, cfg: dict) -> dict:
    df = fetch_ohlcv(ticker, tf, cfg)
    res = evaluate(df, cfg)
    price, prev = float(df["close"].iat[-1]), float(df["close"].iat[-2])
    notes = []
    if is_crypto(ticker, cfg):
        if (vn := volume_note(df)):
            notes.append(vn)
        fr = fetch_funding_rate(ticker, cfg)
        if fr is not None:
            crowd = " (crowded longs)" if fr > 0.0005 else " (crowded shorts)" if fr < -0.0002 else ""
            notes.append(f"Perp funding {fr * 100:+.4f}% per period{crowd}")
    res.update(ticker=ticker, timeframe=tf, price=price, change_pct=(price / prev - 1) * 100,
               notes=notes, ts=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               bar_time=str(df.index[-1]), _df=df)
    return res


def should_alert(res: dict, prev: dict | None, cfg: dict) -> bool:
    """Alert on a NEW qualifying signal, a direction flip, or a strengthening (e.g. Buy -> Strong Buy)."""
    n = cfg["notifications"]
    min_rank = MIN_RANK.get(n["min_action"], 2)
    rank = res["rank"]
    if abs(rank) < min_rank:
        return False
    if prev is None:
        return bool(n.get("alert_on_first_scan", False))
    p = prev["rank"]
    return abs(p) < min_rank or (rank > 0) != (p > 0) or abs(rank) > abs(p)


def handle_result(res: dict, cfg: dict, notify: bool = True) -> bool:
    prev = storage.get_state(res["ticker"], res["timeframe"])
    sent = False
    if notify and should_alert(res, prev, cfg):
        sent = bool(send_all(format_message(res), cfg, subject=f"{res['action']}: {res['ticker']}"))
    if prev is None or prev["action"] != res["action"]:
        storage.log_signal(res, sent)
    storage.set_state(res)
    res["notified"] = sent
    return sent


def run_scan(cfg: dict, tickers: list[str] | None = None, timeframes: list[str] | None = None,
             notify: bool = True, progress=None) -> tuple[list[dict], list[str]]:
    storage.init()
    tickers = tickers or cfg["watchlist"]["stocks"] + cfg["watchlist"]["crypto"]
    timeframes = timeframes or cfg["timeframes"]
    jobs = [(t, tf) for t in tickers for tf in timeframes]
    results, errors = [], []
    for i, (t, tf) in enumerate(jobs, 1):
        try:
            res = scan_one(t, tf, cfg)
            handle_result(res, cfg, notify)
            results.append(res)
        except Exception as e:
            log.error("%s %s: %s", t, tf, e)
            errors.append(f"{t} {tf}: {e}")
        if progress:
            progress(i / len(jobs), f"{t} {tf}")
        time.sleep(0.3)  # be polite to free APIs
    return results, errors
