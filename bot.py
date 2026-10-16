"""
Telegram controls. In your bot chat send:

    /settings   buttons to turn Daily / 4-hour / Hourly on or off, change the alert level, or pause alerts
    /signals    the current Buy and Sell signals
    /list       your watchlist, with tap-to-remove buttons
    /add NVDA TSM DOGE-USD      add tickers (crypto: add -USD)
    /remove TSLA                remove tickers
    /help       this list

GitHub Actions keeps `python bot.py --listen 50` running (a new 50-minute session starts as soon as the
previous one ends), long-polling Telegram so taps take effect within seconds. Setting changes are
committed to settings.json right away so the next scan uses them.
Only messages from your own chat (TELEGRAM_CHAT_ID) are obeyed.
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import time

import requests

import settings as S
import storage
from config import load_config
from notify import ICONS

log = logging.getLogger("bot")
LABEL = {"1d": "Daily", "4h": "4-hour", "2h": "2-hour", "1h": "Hourly", "1wk": "Weekly"}
HELP = ("Signal Desk commands:\n"
        "/settings — turn timeframes on or off, change the alert level, pause alerts\n"
        "/signals — current Buy and Sell signals\n"
        "/list — your tickers (tap one to remove it)\n"
        "/add NVDA TSM — add stocks or ETFs\n"
        "/add DOGE-USD — add crypto (always end with -USD)\n"
        "/remove TSLA — remove tickers\n"
        "/chart — link to your charts\n\n"
        "Taps usually take effect within seconds. If the bot doesn't answer, GitHub is restarting it; "
        "try again in a few minutes.")


def call(token: str, method: str, **params) -> dict:
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params,
                          timeout=params.get("timeout", 0) + 20)
        data = r.json()
    except Exception as e:
        log.error("%s failed: %s", method, e)
        return {"ok": False}
    if not data.get("ok"):
        log.warning("%s: %s", method, data.get("description"))
    return data


def settings_text(cfg: dict, s: dict) -> str:
    on = [LABEL.get(tf, tf) for tf in cfg["timeframes"] if s["timeframes"].get(tf, True)]
    return "\n".join([
        "⚙️ Signal Desk settings",
        f"Alerts for: {', '.join(on) or 'no timeframes (charts still update)'}",
        f"Alert level: {s['min_action']} and stronger (sells too)",
        f"Layer-in / layer-out alerts: {'on' if s.get('ladder', True) else 'off'} (daily)",
        "Status: ⏸ alerts paused" if s["paused"] else "Status: ▶️ alerts on",
        f"Auto-trading (paper): {'on' if s.get('trading', True) else 'off'}",
        "",
        "Tap to change. Changes apply to the next scan.",
    ])


def keyboard(cfg: dict, s: dict) -> dict:
    tf_row = [{"text": f"{'✅' if s['timeframes'].get(tf, True) else '⬜️'} {LABEL.get(tf, tf)}",
               "callback_data": f"tf:{tf}"} for tf in cfg["timeframes"]]
    return {"inline_keyboard": [
        tf_row,
        [{"text": f"{'🔔 ' if s['min_action'] == lv else ''}{lv}", "callback_data": f"level:{lv}"} for lv in S.LEVELS],
        [{"text": f"🪜 Layer alerts: {'On' if s.get('ladder', True) else 'Off'}", "callback_data": "ladder"}],
        [{"text": "▶️ Resume alerts" if s["paused"] else "⏸ Pause all alerts", "callback_data": "pause"}],
        [{"text": "🤖 Auto-trading: On (tap to stop)" if s.get("trading", True) else "🤖 Auto-trading: Off (tap to start)",
          "callback_data": "trade"}],
    ]}


def signals_text() -> str:
    storage.init()
    st = storage.latest_states()
    active = st[st["rank"].abs() >= 2] if not st.empty else st
    if active.empty:
        return "No Buy or Sell signals right now."
    lines = ["📋 Current signals"]
    for _, r in active.iterrows():
        lines.append(f"{ICONS.get(r['action'], '')} {r['action']} — {r['ticker']} "
                     f"({LABEL.get(r['timeframe'], r['timeframe'])}) · {r['price']:,.4g} · score {r['score']}")
    return "\n".join(lines)


MAX_TICKERS = 70      # a full scan (3 timeframes each) still finishes well inside the 30-minute schedule


def _clean(raw: str) -> str:
    return raw.strip().upper().replace("/", "-").lstrip("$")


def ticker_exists(t: str) -> bool:
    """Does Yahoo have recent daily prices for this symbol? (Stocks/ETFs; crypto as XXX-USD.)"""
    try:
        import yfinance as yf
        df = yf.Ticker(t).history(period="1mo", interval="1d")
        return df is not None and len(df.dropna(subset=["Close"])) >= 5
    except Exception as e:
        log.warning("Lookup of %s failed: %s", t, e)
        return False


def add_tickers(raw: list[str], cfg: dict, s: dict) -> str:
    w = S.watchlist(cfg, s)
    added, already, unknown, full = [], [], [], []
    for r in raw:
        t = _clean(r)
        if not t or not all(c.isalnum() or c in "-._=" for c in t):
            unknown.append(r)
            continue
        kind = "crypto" if t.endswith(("-USD", "-USDT")) else "stocks"
        if t in w["stocks"] or t in w["crypto"]:
            already.append(t)
        elif len(w["stocks"]) + len(w["crypto"]) >= MAX_TICKERS:
            full.append(t)
        elif ticker_exists(t):
            w[kind].append(t)
            added.append(t)
        else:
            unknown.append(t)
    if added:
        s["watchlist"] = w
    lines = []
    if added:
        lines.append(f"✅ Added {', '.join(added)}. Charts appear after the next scan (a few minutes); "
                     "the first scan only records a starting point, so alerts begin after that.")
    if already:
        lines.append(f"Already on your list: {', '.join(already)}")
    if unknown:
        lines.append(f"❓ Couldn't find prices for {', '.join(unknown)}. Check the symbol on Yahoo Finance; "
                     "crypto must end in -USD (e.g. DOGE-USD).")
    if full:
        lines.append(f"List is full ({MAX_TICKERS} tickers). Remove some first: {', '.join(full)} not added.")
    return "\n".join(lines) or "Nothing to add."


def remove_tickers(raw: list[str], cfg: dict, s: dict) -> str:
    w = S.watchlist(cfg, s)
    removed, missing = [], []
    for r in raw:
        t = _clean(r)
        for kind in ("stocks", "crypto"):
            if t in w[kind]:
                w[kind].remove(t)
                removed.append(t)
                break
        else:
            missing.append(t)
    if removed:
        s["watchlist"] = w
    lines = []
    if removed:
        lines.append(f"🗑 Removed {', '.join(removed)}. Re-add any time with /add.")
    if missing:
        lines.append(f"Not on your list: {', '.join(missing)}")
    return "\n".join(lines) or "Nothing to remove."


def list_text(cfg: dict, s: dict) -> str:
    w = S.watchlist(cfg, s)
    return "\n".join([f"📋 Watchlist ({len(w['stocks']) + len(w['crypto'])} tickers)",
                      f"Stocks/ETFs: {', '.join(w['stocks']) or 'none'}",
                      f"Crypto: {', '.join(w['crypto']) or 'none'}",
                      "", "Tap a ticker below to remove it. Add with /add TICKER (crypto: /add DOGE-USD)."])


def list_keyboard(cfg: dict, s: dict) -> dict:
    w = S.watchlist(cfg, s)
    btns = [{"text": f"✖ {t}", "callback_data": f"rm:{t}"} for t in w["stocks"] + w["crypto"]]
    return {"inline_keyboard": [btns[i:i + 3] for i in range(0, len(btns), 3)]}


def trigger_scan() -> None:
    """Start a scan right away so a new ticker's chart appears (needs the workflow's GITHUB_TOKEN)."""
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        return
    try:
        r = requests.post(f"https://api.github.com/repos/{repo}/actions/workflows/scan.yml/dispatches",
                          headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                          json={"ref": "main", "inputs": {"only": "all"}}, timeout=15)
        log.info("Scan dispatch: %s", r.status_code)
    except Exception as e:
        log.warning("Could not start a scan: %s", e)


def handle_callback(data: str, cfg: dict, s: dict) -> str:
    if data.startswith("tf:"):
        tf = data[3:]
        if tf in s["timeframes"]:
            s["timeframes"][tf] = not s["timeframes"][tf]
            return f"{LABEL.get(tf, tf)} turned {'on' if s['timeframes'][tf] else 'off'}"
    elif data.startswith("level:") and data[6:] in S.LEVELS:
        s["min_action"] = data[6:]
        return f"Alert level: {s['min_action']} and stronger"
    elif data == "level":
        i = S.LEVELS.index(s["min_action"]) if s["min_action"] in S.LEVELS else 1
        s["min_action"] = S.LEVELS[(i + 1) % len(S.LEVELS)]
        return f"Alert level: {s['min_action']}"
    elif data.startswith("rm:"):
        return remove_tickers([data[3:]], cfg, s)
    elif data == "ladder":
        s["ladder"] = not s.get("ladder", True)
        return f"Layer alerts turned {'on' if s['ladder'] else 'off'}"
    elif data == "trade":
        s["trading"] = not s.get("trading", True)
        return "Auto-trading turned on" if s["trading"] else "Auto-trading stopped: no new buys or sells"
    elif data == "pause":
        s["paused"] = not s["paused"]
        return "Alerts paused" if s["paused"] else "Alerts resumed"
    return "Unknown button"


def commit_settings(reason: str) -> None:
    """In GitHub Actions (BOT_COMMIT=1), save settings.json to the repo right away."""
    if os.environ.get("BOT_COMMIT") != "1":
        return
    run = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True)
    run("add", "settings.json")
    if run("diff", "--cached", "--quiet").returncode == 0:
        return
    run("commit", "-m", f"Settings from Telegram: {reason}")
    for _ in range(3):
        if run("pull", "--rebase").returncode == 0 and run("push").returncode == 0:
            log.info("Settings pushed (%s)", reason)
            return
        time.sleep(3)
    log.error("Could not push settings")


def refresh_repo() -> None:
    """Pull the latest scan results before answering /signals during a long session."""
    if os.environ.get("BOT_COMMIT") == "1":
        subprocess.run(["git", "pull", "--rebase"], capture_output=True)


def process(cfg: dict | None = None, poll: int = 0, s: dict | None = None) -> tuple[dict, list[str]]:
    """Handle new messages and button taps (waiting up to `poll` seconds for them).

    Returns the (possibly updated) settings and a list of setting changes made.
    """
    cfg = cfg or load_config()
    tg = cfg["notifications"]["telegram"]
    token, chat = tg["bot_token"], str(tg["chat_id"])
    s = s if s is not None else S.load(cfg)
    if not (token and chat):
        log.info("Telegram not configured; nothing to do")
        return s, []
    params = {"timeout": poll, "allowed_updates": ["message", "callback_query"]}
    if s["tg_offset"]:
        params["offset"] = s["tg_offset"] + 1
    updates = call(token, "getUpdates", **params).get("result", [])
    changes = []
    if updates:
        # Settings may have changed on the website since we last looked: start from the saved file.
        offset = s["tg_offset"]
        refresh_repo()
        s = S.load(cfg)
        s["tg_offset"] = max(offset, s.get("tg_offset") or 0)
    for u in updates:
        s["tg_offset"] = u["update_id"]
        try:
            handle_update(u, token, chat, cfg, s, changes)
        except Exception as e:             # a malformed update is skipped, never retried forever
            log.error("Skipped Telegram update %s: %s", u.get("update_id"), e)
    if updates:
        S.save(s)
    if changes:
        commit_settings("; ".join(changes))
    if "watchlist" in changes:
        trigger_scan()
    log.info("Processed %d Telegram updates", len(updates))
    return s, changes


def _chat_id(obj: dict | None) -> str | None:
    return str(((obj or {}).get("chat") or {}).get("id")) if obj else None


def handle_update(u: dict, token: str, chat: str, cfg: dict, s: dict, changes: list[str]) -> None:
    """Obey only your own chat. Everything else is ignored without a reply."""
    if (msg := u.get("message")) and _chat_id(msg) == chat:
        raw = (msg.get("text") or "").strip()
        text = raw.lower()
        words = raw.replace(",", " ").split()
        # links from the chart site arrive as "/start add_TSM" or "/start rm_TSLA"
        if text.startswith("/start ") and len(words) > 1 and words[1].lower().startswith("rm_"):
            # Removing via a link needs a confirming tap, so a link someone else sends you can't
            # quietly change your list.
            sym = _clean(words[1][3:])
            w = S.watchlist(cfg, s)
            if sym in w["stocks"] + w["crypto"]:
                call(token, "sendMessage", chat_id=chat, text=f"Remove {sym} from your watchlist?",
                     reply_markup={"inline_keyboard": [[{"text": f"✖ Yes, remove {sym}", "callback_data": f"rm:{sym}"}]]})
            else:
                call(token, "sendMessage", chat_id=chat, text=f"{sym} isn't on your list.")
            return
        if text.startswith("/start ") and len(words) > 1 and words[1].lower().startswith("add_"):
            words, text = ["/add", words[1][4:]], "/add"
        if text.startswith(("/add", "add ")):
            if len(words) < 2:
                call(token, "sendMessage", chat_id=chat, text="Usage: /add NVDA TSM  (crypto: /add DOGE-USD)")
            else:
                reply = add_tickers(words[1:], cfg, s)
                call(token, "sendMessage", chat_id=chat, text=reply)
                if reply.startswith("✅"):
                    changes.append("watchlist")
        elif text.startswith(("/remove", "/rm", "/del", "remove ")):
            if len(words) < 2:
                call(token, "sendMessage", chat_id=chat, text=list_text(cfg, s), reply_markup=list_keyboard(cfg, s))
            else:
                reply = remove_tickers(words[1:], cfg, s)
                call(token, "sendMessage", chat_id=chat, text=reply)
                if reply.startswith("🗑"):
                    changes.append("watchlist")
        elif text.startswith(("/list", "/watchlist", "list")):
            call(token, "sendMessage", chat_id=chat, text=list_text(cfg, s), reply_markup=list_keyboard(cfg, s))
        elif text.startswith(("/settings", "/start", "settings")):
            call(token, "sendMessage", chat_id=chat, text=settings_text(cfg, s), reply_markup=keyboard(cfg, s))
        elif text.startswith(("/chart", "chart")):
            url = os.environ.get("PAGES_URL", "")
            call(token, "sendMessage", chat_id=chat,
                 text=f"📈 Your charts: {url}" if url else "Charts aren't published yet.")
        elif text.startswith(("/signals", "signals")):
            refresh_repo()
            call(token, "sendMessage", chat_id=chat, text=signals_text())
        else:
            call(token, "sendMessage", chat_id=chat, text=HELP)
    elif (cq := u.get("callback_query")) and _chat_id(cq.get("message")) == chat:
        data = cq.get("data", "")
        note = handle_callback(data, cfg, s)
        call(token, "answerCallbackQuery", callback_query_id=cq["id"], text=note[:190])
        if data.startswith("rm:"):
            call(token, "editMessageText", chat_id=chat, message_id=cq["message"]["message_id"],
                 text=list_text(cfg, s), reply_markup=list_keyboard(cfg, s))
            call(token, "sendMessage", chat_id=chat, text=note)
            if note.startswith("🗑"):
                changes.append("watchlist")
        else:
            changes.append(note)
            call(token, "editMessageText", chat_id=chat, message_id=cq["message"]["message_id"],
                 text=settings_text(cfg, s), reply_markup=keyboard(cfg, s))
            call(token, "sendMessage", chat_id=chat, text=f"✅ {note}")


def listen(minutes: float) -> None:
    """Long-poll Telegram for `minutes`, answering instantly; save the read position at the end."""
    cfg = load_config()
    s = S.load(cfg)
    end = time.time() + minutes * 60
    while time.time() < end - 5:
        poll = int(max(1, min(25, end - time.time() - 5)))
        s, _ = process(cfg, poll=poll, s=s)
    refresh_repo()
    fresh = S.load(cfg)                    # keep any website edits; only update our read position
    fresh["tg_offset"] = max(s["tg_offset"], fresh.get("tg_offset") or 0)
    S.save(fresh)
    commit_settings("read position")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", type=float, default=0, help="minutes to keep listening (0 = check once)")
    a = ap.parse_args()
    if a.listen:
        listen(a.listen)
    else:
        process()
