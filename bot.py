"""
Telegram controls. In your bot chat send:

    /settings   buttons to turn Daily / 4-hour / Hourly on or off, change the alert level, or pause alerts
    /signals    the current Buy and Sell signals
    /help       this list

GitHub Actions runs `python bot.py` every few minutes, so taps take effect within about 5-15 minutes.
Only messages from your own chat (TELEGRAM_CHAT_ID) are obeyed.
"""
from __future__ import annotations

import logging

import requests

import settings as S
import storage
from config import load_config
from notify import ICONS

log = logging.getLogger("bot")
LABEL = {"1d": "Daily", "4h": "4-hour", "1h": "Hourly", "1wk": "Weekly"}
HELP = ("Signal Desk commands:\n"
        "/settings — turn timeframes on or off, change the alert level, pause alerts\n"
        "/signals — current Buy and Sell signals\n\n"
        "Button taps are picked up within about 5–15 minutes.")


def call(token: str, method: str, **params) -> dict:
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=20)
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
        f"Timeframes on: {', '.join(on) or 'none'}",
        f"Alert level: {s['min_action']} and stronger (sells too)",
        "Status: ⏸ alerts paused" if s["paused"] else "Status: ▶️ alerts on",
        "",
        "Tap to change. Taps are picked up within about 5–15 minutes.",
    ])


def keyboard(cfg: dict, s: dict) -> dict:
    tf_row = [{"text": f"{'✅' if s['timeframes'].get(tf, True) else '⬜️'} {LABEL.get(tf, tf)}",
               "callback_data": f"tf:{tf}"} for tf in cfg["timeframes"]]
    return {"inline_keyboard": [
        tf_row,
        [{"text": f"🔔 Alert level: {s['min_action']}", "callback_data": "level"}],
        [{"text": "▶️ Resume alerts" if s["paused"] else "⏸ Pause all alerts", "callback_data": "pause"}],
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


def handle_callback(data: str, cfg: dict, s: dict) -> str:
    if data.startswith("tf:"):
        tf = data[3:]
        if tf in s["timeframes"]:
            s["timeframes"][tf] = not s["timeframes"][tf]
            return f"{LABEL.get(tf, tf)} turned {'on' if s['timeframes'][tf] else 'off'}"
    elif data == "level":
        i = S.LEVELS.index(s["min_action"]) if s["min_action"] in S.LEVELS else 1
        s["min_action"] = S.LEVELS[(i + 1) % len(S.LEVELS)]
        return f"Alert level: {s['min_action']}"
    elif data == "pause":
        s["paused"] = not s["paused"]
        return "Alerts paused" if s["paused"] else "Alerts resumed"
    return "Unknown button"


def process(cfg: dict | None = None) -> bool:
    """Handle new messages and button taps. Returns True if settings.json changed."""
    cfg = cfg or load_config()
    tg = cfg["notifications"]["telegram"]
    token, chat = tg["bot_token"], str(tg["chat_id"])
    if not (token and chat):
        log.info("Telegram not configured; nothing to do")
        return False
    s = S.load(cfg)
    params = {"timeout": 0, "allowed_updates": ["message", "callback_query"]}
    if s["tg_offset"]:
        params["offset"] = s["tg_offset"] + 1
    updates = call(token, "getUpdates", **params).get("result", [])
    changed = False
    for u in updates:
        s["tg_offset"] = u["update_id"]
        changed = True
        if (msg := u.get("message")) and str(msg["chat"]["id"]) == chat:
            text = (msg.get("text") or "").strip().lower()
            if text.startswith(("/settings", "/start", "settings")):
                call(token, "sendMessage", chat_id=chat, text=settings_text(cfg, s), reply_markup=keyboard(cfg, s))
            elif text.startswith(("/signals", "signals")):
                call(token, "sendMessage", chat_id=chat, text=signals_text())
            else:
                call(token, "sendMessage", chat_id=chat, text=HELP)
        elif (cq := u.get("callback_query")) and str(cq["message"]["chat"]["id"]) == chat:
            note = handle_callback(cq.get("data", ""), cfg, s)
            call(token, "answerCallbackQuery", callback_query_id=cq["id"], text=note)  # may be too old; harmless
            call(token, "editMessageText", chat_id=chat, message_id=cq["message"]["message_id"],
                 text=settings_text(cfg, s), reply_markup=keyboard(cfg, s))
            call(token, "sendMessage", chat_id=chat, text=f"✅ {note}")
    if changed:
        S.save(s)
    log.info("Processed %d Telegram updates", len(updates))
    return changed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    process()
