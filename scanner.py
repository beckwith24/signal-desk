"""Scan tickers, evaluate models, persist state, and fire de-duplicated alerts."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import confluence
import context
import engine
import ia
import ladder
import overlays
import storage
from data import fetch_funding_rate, fetch_ohlcv, is_crypto
from notify import format_exit, format_message, send_all
from signals import evaluate, volume_note

log = logging.getLogger(__name__)
MIN_RANK = {"Watch": 1, "Buy": 2, "Strong Buy": 3, "Panic Buy": 4}
_CTX: dict = {}      # asset -> (fetched_at, daily context series); refreshed every 30 minutes
TF_NAMES = {"1d": "daily", "4h": "4-hour", "2h": "2-hour", "1h": "hourly", "1wk": "weekly"}


def daily_context(asset: str, cfg: dict) -> dict:
    hit = _CTX.get(asset)
    if hit and time.time() - hit[0] < 1800:
        return hit[1]
    ctx = context.fetch_daily(lambda s: fetch_ohlcv(s, "1d", cfg), context.needs(asset))
    _CTX[asset] = (time.time(), ctx)
    return ctx


def scan_one(ticker: str, tf: str, cfg: dict) -> dict:
    df = fetch_ohlcv(ticker, tf, cfg)
    asset = "crypto" if is_crypto(ticker, cfg) else "stock"
    ath_known = ia.known_ath(ticker, float(df["close"].iat[-1]))   # full-history high (cached in ath.json)
    if cfg.get("engine", "v2") == "v2":
        ctx = context.align(daily_context(asset, cfg), df.index, asset, tf)
        ctx["ath_known"] = ath_known
        res = engine.evaluate(df, cfg, asset, tf, ctx)
    else:
        res = evaluate(df, cfg)
    res["overlays"] = overlays.compute(df, cfg, ath_known)
    if tf in ("1h", "2h", "4h"):
        try:
            res["conf"] = confluence.compute(df)
        except Exception as e:
            log.warning("%s %s confluence: %s", ticker, tf, e)
    res["asset"] = asset
    price, prev = float(df["close"].iat[-1]), float(df["close"].iat[-2])
    notes = []
    if tf != "1d" and res.get("engine") == "v2":
        daily = storage.get_state(ticker, "1d")
        if daily:
            notes.append(f"Daily signal: {daily['action']} (score {daily['score']}). Use this timeframe to time entries.")
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


REPEAT_HOURS = 20    # the same alert for the same ticker isn't repeated within this many hours


def should_alert(res: dict, prev: dict | None, cfg: dict) -> bool:
    """Alert on a NEW qualifying signal, a direction flip, or a strengthening (e.g. Buy -> Strong Buy).

    A signal that flickers (Strong Buy -> Buy -> Strong Buy during the day, as the day's bar forms)
    doesn't alert again within REPEAT_HOURS.
    """
    n = cfg["notifications"]
    if res.get("exit_trade"):                  # the tested exit of a stock dip-buy trade always alerts once
        if prev is not None and prev["action"] == res["action"]:
            return False
        return not storage.recently_notified(res["ticker"], res["timeframe"], res["action"], REPEAT_HOURS)
    min_rank = MIN_RANK.get(n["min_action"], 2)
    rank = res["rank"]
    if abs(rank) < min_rank:
        return False
    if prev is None:
        return bool(n.get("alert_on_first_scan", False))
    p = prev["rank"]
    if not (abs(p) < min_rank or (rank > 0) != (p > 0) or abs(rank) > abs(p)):
        return False
    return not storage.recently_notified(res["ticker"], res["timeframe"], res["action"], REPEAT_HOURS)


def is_exit(res: dict, prev: dict | None, cfg: dict) -> bool:
    """Trend segments: a Buy you were alerted to has ended (dropped below Buy, even via a weaker Buy first)."""
    if not res.get("exit_alerts") or prev is None:
        return False
    if not (prev["rank"] >= 2 and res["rank"] < 2):
        return False
    min_rank = MIN_RANK.get(cfg["notifications"]["min_action"], 2)
    return storage.episode_alerted(res["ticker"], res["timeframe"], max(min_rank, 2))


def handle_result(res: dict, cfg: dict, notify: bool = True) -> bool:
    prev = storage.get_state(res["ticker"], res["timeframe"])
    sent = False
    tf_alerts = res["timeframe"] in cfg.get("alert_timeframes", cfg["timeframes"])
    if notify and tf_alerts and should_alert(res, prev, cfg):
        sent = bool(send_all(format_message(res), cfg, subject=f"{res['action']}: {res['ticker']}"))
    elif notify and tf_alerts and is_exit(res, prev, cfg):
        entry = storage.last_entry(res["ticker"], res["timeframe"]) or prev
        sent = bool(send_all(format_exit(res, entry), cfg, subject=f"Exit: {res['ticker']}"))
    # Layer-in / layer-out alerts are separate from the Buy/Sell signal (always checked, so the
    # saved ladder position stays current even when alerts are off).
    for msg in ladder.check_alerts(res, cfg):
        if notify:
            sent = bool(send_all(msg, cfg, subject=f"Layer alert: {res['ticker']}")) or sent
    if prev is None or prev["action"] != res["action"]:
        storage.log_signal(res, sent)
    storage.set_state(res)
    res["notified"] = sent
    return sent


def run_scan(cfg: dict, tickers: list[str] | None = None, timeframes: list[str] | None = None,
             notify: bool = True, progress=None) -> tuple[list[dict], list[str]]:
    storage.init()
    if storage.ensure_engine(cfg.get("engine", "v2")):
        log.info("Signal engine changed to %s: this scan records a quiet baseline", cfg.get("engine", "v2"))
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
