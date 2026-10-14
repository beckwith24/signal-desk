"""
Auto-trading through Alpaca (paper account by default).

Once a day, shortly after the US market opens:
  1. Sells: any stock held that closed above its 5-day average yesterday (the tested exit),
     or has been held 20 trading days (a safety limit).
  2. Buys: watchlist stocks whose daily signal at yesterday's close was Strong Buy or Panic Buy,
     PER_TRADE dollars each, at most MAX_POSITIONS open, none if the account is down more than
     DAILY_LOSS_PCT today.
Signals are re-computed here from completed daily bars only (today's half-finished bar is dropped),
so an intraday wobble never triggers a trade. Crypto is not traded.

Safety:
  * Paper money unless the workflow sets ALPACA_LIVE=1 (it doesn't).
  * Telegram /settings has an "Auto-trading" on/off button (settings.json "trading").
  * Runs twice a morning for reliability; anything already ordered today is skipped.
  * Nothing about the account is written to the (public) repo: details go to Telegram only.

    python trader.py            trade (only acts in the first two hours after the open)
    python trader.py --check    check the connection and send a status message
    python trader.py --dry-run  show what it would do, place nothing
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone

import pandas as pd
import requests

import context
import engine
import settings as S
from config import load_config
from data import fetch_ohlcv, is_crypto

log = logging.getLogger("trader")
PER_TRADE = 1000.0          # dollars per buy
MAX_POSITIONS = 10
DAILY_LOSS_PCT = 3.0        # no new buys if the account is down more than this today
MAX_HOLD_DAYS = 20          # trading days
BUY_ON = ("Panic Buy", "Strong Buy")
WINDOW_MIN = (5, 150)       # act between 5 and 150 minutes after the open
ET = "America/New_York"


class Alpaca:
    def __init__(self) -> None:
        self.live = os.environ.get("ALPACA_LIVE") == "1"
        self.base = "https://api.alpaca.markets" if self.live else "https://paper-api.alpaca.markets"
        self.h = {"APCA-API-KEY-ID": os.environ["ALPACA_KEY_ID"].strip(),
                  "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"].strip()}

    def req(self, method: str, path: str, **kw):
        r = requests.request(method, self.base + path, headers=self.h, timeout=20, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path}: {r.status_code} {r.text[:200]}")
        return r.json() if r.text else None

    get = lambda self, p, **kw: self.req("GET", p, **kw)


def telegram(text: str) -> None:
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    print(text)
    if tok and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": chat, "text": text, "disable_web_page_preview": True}, timeout=15)
        except Exception as e:
            log.warning("telegram: %s", e)


def completed_daily(ticker: str, cfg: dict, today) -> pd.DataFrame:
    df = fetch_ohlcv(ticker, "1d", cfg)
    dates = df.index.tz_convert(ET).date
    return df[dates < today]


def signal(ticker: str, cfg: dict, ctx_daily: dict, today) -> dict | None:
    df = completed_daily(ticker, cfg, today)
    if len(df) < 210:
        return None
    ctx = context.align({k: v[v.index.tz_convert(ET).date < today] for k, v in ctx_daily.items()},
                        df.index, "stock", "1d")
    ctx["ath_known"] = None
    res = engine.evaluate(df, cfg, "stock", "1d", ctx)
    res["close"], res["bar"] = float(df["close"].iat[-1]), df.index[-1].tz_convert(ET).date()
    return res


def entry_date(api: Alpaca, sym: str):
    for o in api.get("/v2/orders", params={"status": "closed", "symbols": sym, "limit": 50, "direction": "desc"}):
        if o.get("side") == "buy" and o.get("filled_at"):
            return pd.Timestamp(o["filled_at"]).tz_convert(ET).date()
    return None


def money(x) -> str:
    return f"${float(x):,.2f}"


def check(api: Alpaca) -> None:
    a, pos = api.get("/v2/account"), api.get("/v2/positions")
    clock = api.get("/v2/clock")
    telegram("🤖 Auto-trading connected to Alpaca " + ("LIVE (real money)" if api.live else "paper (pretend money)") +
             f"\nAccount value {money(a['equity'])}, cash {money(a['cash'])}, {len(pos)} positions open."
             f"\nMarket {'open' if clock['is_open'] else 'closed'}; next open {clock['next_open'][:16].replace('T', ' ')} ET."
             f"\nRules: {money(PER_TRADE)} per Strong Buy / Panic Buy, max {MAX_POSITIONS} positions, "
             f"sell on a close above the 5-day average (or after {MAX_HOLD_DAYS} days).")


def run(api: Alpaca, dry: bool) -> None:
    cfg = S.apply(load_config(), S.load(load_config()))
    s = S.load(load_config())
    if not s.get("trading", True):
        log.info("Auto-trading is switched off in settings"); return
    clock = api.get("/v2/clock")
    now = pd.Timestamp(clock["timestamp"]).tz_convert(ET)
    if not clock["is_open"] and not dry:
        log.info("Market closed"); return
    opened = now.normalize() + pd.Timedelta(hours=9, minutes=30)
    mins = (now - opened).total_seconds() / 60
    if not dry and not (WINDOW_MIN[0] <= mins <= WINDOW_MIN[1]):
        log.info("Outside the trading window (%.0f min after open)", mins); return
    today = now.date()

    acct = api.get("/v2/account")
    if acct.get("trading_blocked") or acct.get("account_blocked"):
        telegram("⚠️ Alpaca says the account is blocked from trading; nothing done."); return
    since_open = opened.tz_convert("UTC").isoformat()
    done_today = {o["symbol"] for o in api.get("/v2/orders", params={"status": "all", "after": since_open, "limit": 500})}
    positions = {p["symbol"]: p for p in api.get("/v2/positions") if p.get("asset_class") == "us_equity"}
    lines = []

    # 1. sells
    for sym, p in positions.items():
        if sym in done_today:
            continue
        try:
            df = completed_daily(sym.replace(".", "-"), cfg, today)
        except Exception as e:
            log.warning("%s data: %s", sym, e); continue
        close, sma5 = float(df["close"].iat[-1]), float(df["close"].iloc[-5:].mean())
        start = entry_date(api, sym)
        held = int((df.index.tz_convert(ET).date > start).sum()) if start else 0
        why = (f"closed {close:.2f} above its 5-day average {sma5:.2f}" if close > sma5 else
               f"held {held} trading days" if held >= MAX_HOLD_DAYS else None)
        if why:
            pl = float(p.get("unrealized_pl") or 0)
            lines.append(f"🔴 Sell {sym} ({why}); about {'+' if pl >= 0 else '-'}{money(abs(pl))} "
                         f"({float(p.get('unrealized_plpc') or 0) * 100:+.1f}%)")
            if not dry:
                try:
                    api.req("DELETE", f"/v2/positions/{sym}")
                except Exception as e:
                    lines[-1] = f"⚠️ Couldn't sell {sym}: {e}"
            positions.pop(sym)

    # 2. buys
    down = (float(acct["equity"]) / float(acct["last_equity"]) - 1) * 100 if float(acct["last_equity"]) else 0
    stocks = [t for t in S.watchlist(load_config(), s)["stocks"] if not is_crypto(t, cfg)]
    from scanner import daily_context
    ctx_daily = daily_context("stock", cfg)
    picks = []
    for t in stocks:
        try:
            r = signal(t, cfg, ctx_daily, today)
        except Exception as e:
            log.warning("%s: %s", t, e); continue
        if r and r["action"] in BUY_ON:
            picks.append((BUY_ON.index(r["action"]), -r["score"], t, r))
    picks.sort()
    if picks and down < -DAILY_LOSS_PCT:
        lines.append(f"⏸ No buys today: account down {down:.1f}% (limit {DAILY_LOSS_PCT:.0f}%).")
        picks = []
    cash = float(acct["buying_power"])
    for _, _, t, r in picks:
        sym = t.replace("-", ".")
        if sym in positions or sym in done_today:
            continue
        if len(positions) >= MAX_POSITIONS:
            lines.append(f"• Skipped {t} ({r['action']}): already {MAX_POSITIONS} positions open"); continue
        if cash < PER_TRADE:
            lines.append(f"• Skipped {t}: not enough cash"); continue
        lines.append(f"🟢 Buy {t} {money(PER_TRADE)} ({r['action']}, closed {r['close']:.2f} on {r['bar']:%b %-d})")
        if not dry:
            try:
                api.req("POST", "/v2/orders", json={"symbol": sym, "notional": f"{PER_TRADE:.2f}", "side": "buy",
                                                      "type": "market", "time_in_force": "day"})
            except Exception as e:
                lines[-1] = f"⚠️ Couldn't buy {t}: {e}"; continue
        positions[sym] = {}
        cash -= PER_TRADE

    if lines or dry:
        head = ("🧪 Dry run (nothing placed)" if dry else "🤖 Auto-trades") + (" — PAPER" if not api.live else " — LIVE")
        body = "\n".join(lines) or "Nothing to do today."
        telegram(f"{head}\n{body}\nOpen positions: {len(positions)}/{MAX_POSITIONS}")
    else:
        log.info("Nothing to do today")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not os.environ.get("ALPACA_KEY_ID") or not os.environ.get("ALPACA_SECRET_KEY"):
        telegram("⚠️ Auto-trading: the ALPACA_KEY_ID / ALPACA_SECRET_KEY secrets aren't set in GitHub."); return
    api = Alpaca()
    try:
        check(api) if a.check else run(api, a.dry_run)
    except Exception as e:
        telegram(f"⚠️ Auto-trading error: {e}")
        raise


if __name__ == "__main__":
    main()
