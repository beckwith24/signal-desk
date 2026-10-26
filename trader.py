"""
Auto-trading through Alpaca (paper account by default): SPY core + crypto trend sleeve with pyramid entries.

The rules live in strategy.py and match the backtest in research/portfolio.md and research/active.md:
  * 80% of the account in SPY, rebalanced when it drifts more than 5% of the account from target.
  * 20% across BTC, ETH, SOL, LINK and AVAX (4% slot each). A coin is bought in thirds while its trend
    rule is on: 1/3 when it turns on, +1/3 each time it closes 1 ATR above the last add. All of it is sold
    when the rule turns off. Unused crypto slots stay in cash.

How a run works (it is safe to run as often as you like):
  1. Rebuild today's targets from completed daily bars only (no half-finished bar).
  2. Compare them with what Alpaca actually holds and plan only the differences.
  3. Sells first, then buys paid from cash (never margin). No new buys if the account is down more than
     DAILY_LOSS_PCT today. Symbols with an order still open are skipped.
  4. Each order carries a client_order_id of date + symbol + side (crypto: the daily candle the decision
     came from; SPY: the trading day), so Alpaca refuses a duplicate even if two runs overlap.
Crypto is handled on every run (it trades 24/7). SPY and the wind-down of old dip-trade positions are only
handled in the first two hours after the US open.

Safety:
  * Paper money unless the workflow sets ALPACA_LIVE=1 (it doesn't).
  * Telegram /settings has an "Auto-trading" on/off button (settings.json "trading").
  * Nothing about the account is written to the (public) repo: details go to Telegram only.

    python trader.py            trade
    python trader.py --check    check the connection and send a status message
    python trader.py --dry-run  show what it would do, place nothing
"""
from __future__ import annotations

import argparse
import logging
import math
import os

import pandas as pd
import requests

import settings as S
import strategy as ST
from config import load_config
from data import fetch_ohlcv

log = logging.getLogger("trader")
DAILY_LOSS_PCT = 3.0        # no new buys if the account is down more than this today
STOCK_BAND = 0.05           # rebalance SPY when it is off target by more than 5% of the account
COIN_BAND = 0.25            # trade a coin when it is off target by more than a quarter of one layer
MIN_ORDER = 10.0            # dollars; smaller differences are ignored
CASH_BUFFER = 0.005         # keep 0.5% of the account in cash so market orders aren't rejected
LEGACY_HOLD_DAYS = 20       # old dip-trade positions: same exits as before (close > 5-day avg, or 20 days)
WINDOW_MIN = (5, 150)       # stock orders only between 5 and 150 minutes after the open
ET = "America/New_York"


def alpaca_symbol(ticker: str) -> str:
    """BTC-USD -> BTC/USD (orders); positions come back as BTCUSD."""
    return ticker.replace("-", "/") if ticker.endswith("-USD") else ticker


def position_key(symbol: str) -> str:
    return symbol.replace("/", "")


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

    def get(self, path: str, **kw):
        return self.req("GET", path, **kw)


def telegram(text: str) -> None:
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    print(text)
    if tok and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": chat, "text": text, "disable_web_page_preview": True}, timeout=15)
        except Exception as e:
            log.warning("telegram: %s", e)


def money(x) -> str:
    return f"${float(x):,.2f}"


# ============================================================================ data
def completed_closes(tickers: list[str], cfg: dict, now_utc: pd.Timestamp) -> tuple[pd.DataFrame, list[str]]:
    """Daily closes with today's unfinished bar dropped (crypto days end at 00:00 UTC), plus any fetch errors.
    A coin whose data fails is left out, so its position is simply left alone this run."""
    cols, errors = {}, []
    for t in tickers:
        try:
            df = fetch_ohlcv(t, "1d", cfg)
        except Exception as e:
            errors.append(f"{t}: {e}")
            continue
        cols[t] = df["close"][df.index.normalize() < now_utc.normalize()]
    if not cols:
        return pd.DataFrame(), errors
    closes = pd.DataFrame(cols).sort_index()
    closes.index = closes.index.normalize()
    return closes[~closes.index.duplicated(keep="last")], errors


def legacy_exit(sym: str, cfg: dict, today, entry) -> str | None:
    """Old dip-trade exit rule, used only to wind down positions the previous strategy opened."""
    df = fetch_ohlcv(sym.replace(".", "-"), "1d", cfg)
    df = df[df.index.tz_convert(ET).date < today]
    close, sma5 = float(df["close"].iat[-1]), float(df["close"].iloc[-5:].mean())
    held = int((df.index.tz_convert(ET).date > entry).sum()) if entry else LEGACY_HOLD_DAYS
    if close > sma5:
        return f"closed {close:.2f} above its 5-day average {sma5:.2f}"
    if held >= LEGACY_HOLD_DAYS:
        return f"held {held} trading days"
    return None


def entry_date(api: Alpaca, sym: str):
    for o in api.get("/v2/orders", params={"status": "closed", "symbols": sym, "limit": 50, "direction": "desc"}):
        if o.get("side") == "buy" and o.get("filled_at"):
            return pd.Timestamp(o["filled_at"]).tz_convert(ET).date()
    return None


# ============================================================================ planning (pure, tested)
def plan(equity: float, positions: dict[str, dict], targets: dict[str, dict], stock_window: bool,
         open_order_symbols: set[str], down_pct: float) -> list[dict]:
    """
    Orders needed to move the account to target. positions: key (e.g. "SPY", "BTCUSD") ->
    {"qty", "market_value", "price"}. Returns orders as dicts:
      {"symbol", "side", "kind": "close" | "qty" | "notional", "amount", "why", "asset": "stock" | "crypto"}
    Sells come before buys. Buys are left uncapped here; execute() caps them by available cash.
    """
    sells, buys, notes = [], [], []
    no_buys = down_pct < -DAILY_LOSS_PCT
    slot = ST.slot_value(equity)
    layer = slot / ST.LAYERS

    def add(symbol, asset, current, target, band, why, price, qty):
        diff = target - current
        if symbol in open_order_symbols:
            notes.append({"symbol": symbol, "skip": "an earlier order is still open"})
            return
        if target <= 0 and current > MIN_ORDER:
            sells.append({"symbol": symbol, "side": "sell", "kind": "close", "amount": qty, "why": why, "asset": asset})
        elif abs(diff) > max(MIN_ORDER, band):
            if diff < 0:
                q = min(qty, -diff / price) if price else qty
                kind = "close" if q >= 0.98 * qty else "qty"
                sells.append({"symbol": symbol, "side": "sell", "kind": kind, "amount": q if kind == "qty" else qty,
                              "why": why, "asset": asset})
            elif no_buys:
                notes.append({"symbol": symbol, "skip": f"account down {down_pct:.1f}% today, no new buys"})
            else:
                buys.append({"symbol": symbol, "side": "buy", "kind": "notional", "amount": round(diff, 2),
                             "why": why, "asset": asset})

    for t, tg in targets.items():
        sym = alpaca_symbol(t)
        pos = positions.get(position_key(sym), {})
        cur, qty, price = float(pos.get("market_value", 0)), float(pos.get("qty", 0)), float(pos.get("price", 0) or tg.get("close") or 0)
        target = slot * tg["layers"] / ST.LAYERS
        why = (f"trend {'on' if tg['on'] else 'off'}, {tg['layers']}/3 layers"
               + ("" if tg["enough_data"] else f" (only {tg['bars']} days of data, needs {ST.MIN_BARS})"))
        add(sym, "crypto", cur, target, COIN_BAND * layer, why, price, qty)

    if stock_window:
        pos = positions.get(ST.STOCK_SYMBOL, {})
        add(ST.STOCK_SYMBOL, "stock", float(pos.get("market_value", 0)), equity * ST.STOCK_WEIGHT,
            STOCK_BAND * equity, f"core holding, target {ST.STOCK_WEIGHT:.0%} of the account",
            float(pos.get("price", 0)), float(pos.get("qty", 0)))
    return sells + buys + [{"note": n} for n in notes]


# ============================================================================ execution
def execute(api: Alpaca, orders: list[dict], days: dict[str, str], dry: bool, equity: float) -> list[str]:
    """days: {"crypto": date of the daily candle the targets came from, "stock": today's New York date}.
    They go into client_order_id, so the same decision can never be ordered twice."""
    lines = []
    for o in [o for o in orders if "note" in o]:
        lines.append(f"• Skipped {o['note']['symbol']}: {o['note']['skip']}")
    real = [o for o in orders if "note" not in o]
    sells, buys = [o for o in real if o["side"] == "sell"], [o for o in real if o["side"] == "buy"]

    for o in sells:
        sym = o["symbol"]
        size = "all " if o["kind"] == "close" else ""
        units = "" if o["kind"] == "close" else "{:.6g} units ".format(o["amount"])
        lines.append(f"🔴 Sell {size}{sym} {units}({o['why']})")
        if dry:
            continue
        try:
            if o["kind"] == "close":
                api.req("DELETE", f"/v2/positions/{position_key(sym)}")
            else:
                api.req("POST", "/v2/orders", json={
                    "symbol": sym, "qty": f"{math.floor(o['amount'] * 1e8) / 1e8:.8f}", "side": "sell", "type": "market",
                    "time_in_force": "gtc" if o["asset"] == "crypto" else "day",
                    "client_order_id": f"sd-{days[o['asset']]}-{position_key(sym)}-sell"})
        except Exception as e:
            lines[-1] = f"⚠️ Couldn't sell {sym}: {e}"

    if buys:
        acct = api.get("/v2/account") if not dry else None
        cash = float(acct["cash"]) if acct else equity
        crypto_bp = float(acct.get("non_marginable_buying_power", cash)) if acct else equity
        cash -= CASH_BUFFER * equity
        for o in buys:
            sym = o["symbol"]
            limit = min(cash, crypto_bp) if o["asset"] == "crypto" else cash
            amt = round(min(o["amount"], limit), 2)
            if amt < MIN_ORDER:
                lines.append(f"• Skipped buying {sym}: not enough cash (wanted {money(o['amount'])})")
                continue
            lines.append(f"🟢 Buy {sym} {money(amt)} ({o['why']})")
            cash -= amt
            crypto_bp -= amt
            if dry:
                continue
            try:
                api.req("POST", "/v2/orders", json={
                    "symbol": sym, "notional": f"{amt:.2f}", "side": "buy", "type": "market",
                    "time_in_force": "gtc" if o["asset"] == "crypto" else "day",
                    "client_order_id": f"sd-{days[o['asset']]}-{position_key(sym)}-buy"})
            except Exception as e:
                lines[-1] = f"⚠️ Couldn't buy {sym}: {e}"
    return lines


def summary(targets: dict, equity: float) -> str:
    rows = []
    for t, tg in targets.items():
        v = tg["votes"]
        ups = sum(1 for x in v.values() if x > 0)
        rows.append(f"{t.replace('-USD', '')}: {'ON' if tg['on'] else 'off'} ({ups}/4 trend votes up), "
                    f"hold {tg['layers']}/3 = {money(ST.slot_value(equity) * tg['layers'] / ST.LAYERS)}")
    return "\n".join(rows)


def run(api: Alpaca, dry: bool) -> None:
    cfg = load_config()
    s = S.load(cfg)
    if not s.get("trading", True):
        log.info("Auto-trading is switched off in settings")
        return
    clock = api.get("/v2/clock")
    now = pd.Timestamp(clock["timestamp"]).tz_convert(ET)
    opened = now.normalize() + pd.Timedelta(hours=9, minutes=30)
    mins = (now - opened).total_seconds() / 60
    stock_window = bool(clock["is_open"]) and WINDOW_MIN[0] <= mins <= WINDOW_MIN[1]
    today = now.strftime("%Y%m%d")

    acct = api.get("/v2/account")
    if acct.get("trading_blocked") or acct.get("account_blocked"):
        telegram("⚠️ Alpaca says the account is blocked from trading; nothing done.")
        return
    equity = float(acct["equity"])
    down = (equity / float(acct["last_equity"]) - 1) * 100 if float(acct.get("last_equity") or 0) else 0.0
    positions = {p["symbol"]: {"qty": float(p["qty"]), "market_value": float(p["market_value"]),
                               "price": float(p.get("current_price") or 0), "asset_class": p.get("asset_class")}
                 for p in api.get("/v2/positions")}
    open_syms = {o["symbol"] for o in api.get("/v2/orders", params={"status": "open", "limit": 500})}

    closes, errors = completed_closes(ST.COINS, cfg, now.tz_convert("UTC"))
    lines = [f"⚠️ No data, left alone: {e}" for e in errors]
    if "BTC-USD" in closes:
        targets = ST.crypto_targets(closes)
    else:                                   # every coin's rule needs Bitcoin's trend: skip crypto this run
        targets = {}
        lines.append("⚠️ No Bitcoin data, so no crypto trades this run")
    orders = plan(equity, positions, targets, stock_window, open_syms, down)
    crypto_day = closes.index[-1].strftime("%Y%m%d") if len(closes) else today
    lines += execute(api, orders, {"crypto": crypto_day, "stock": today}, dry, equity)

    # Wind down positions the old dip strategy opened, with its own exit rule.
    if stock_window:
        crypto_keys = {position_key(alpaca_symbol(t)) for t in ST.COINS}
        for sym, p in positions.items():
            if sym == ST.STOCK_SYMBOL or sym in crypto_keys or p.get("asset_class") != "us_equity" or sym in open_syms:
                continue
            try:
                why = legacy_exit(sym, cfg, now.date(), entry_date(api, sym))
            except Exception as e:
                lines.append(f"⚠️ {sym}: {e}")
                continue
            if why:
                lines.append(f"🔴 Sell old dip trade {sym} ({why})")
                if not dry:
                    try:
                        api.req("DELETE", f"/v2/positions/{sym}")
                    except Exception as e:
                        lines[-1] = f"⚠️ Couldn't sell {sym}: {e}"

    acted = [x for x in lines if not x.startswith("•")]
    if acted or dry:
        head = ("🧪 Dry run (nothing placed)" if dry else "🤖 Auto-trades") + (" — LIVE" if api.live else " — PAPER")
        body = "\n".join(lines) or "Nothing to do: everything is on target."
        stock_note = "" if stock_window else "\n(SPY is only traded in the first 2 hours after the US open.)"
        telegram(f"{head}\n{body}{stock_note}\n\nCrypto trend:\n{summary(targets, equity)}\n"
                 f"Account {money(equity)} ({down:+.1f}% today)")
    else:
        log.info("Nothing to do: everything is on target")


def check(api: Alpaca) -> None:
    a, pos = api.get("/v2/account"), api.get("/v2/positions")
    clock = api.get("/v2/clock")
    telegram("🤖 Auto-trading connected to Alpaca " + ("LIVE (real money)" if api.live else "paper (pretend money)") +
             f"\nAccount value {money(a['equity'])}, cash {money(a['cash'])}, {len(pos)} positions open."
             f"\nMarket {'open' if clock['is_open'] else 'closed'}; next open {clock['next_open'][:16].replace('T', ' ')} ET."
             f"\nRules: {ST.STOCK_WEIGHT:.0%} SPY; {ST.CRYPTO_WEIGHT:.0%} across "
             f"{', '.join(c.replace('-USD', '') for c in ST.COINS)}, each bought in thirds while its trend is up "
             f"and sold when it turns down. Buys use cash only, never margin.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not os.environ.get("ALPACA_KEY_ID") or not os.environ.get("ALPACA_SECRET_KEY"):
        telegram("⚠️ Auto-trading: the ALPACA_KEY_ID / ALPACA_SECRET_KEY secrets aren't set in GitHub.")
        return
    api = Alpaca()
    try:
        check(api) if a.check else run(api, a.dry_run)
    except Exception as e:
        telegram(f"⚠️ Auto-trading error: {e}")
        raise


if __name__ == "__main__":
    main()
