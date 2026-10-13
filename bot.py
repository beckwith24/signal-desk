"""
Telegram controls. In your bot chat send:

    /settings   buttons to turn Daily / 4-hour / Hourly on or off, change the alert level, or pause alerts
    /signals    the current Buy and Sell signals
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
LABEL = {"1d": "Daily", "4h": "4-hour", "1h": "Hourly", "1wk": "Weekly"}
HELP = ("Signal Desk commands:\n"
        "/settings — turn timeframes on or off, change the alert level, pause alerts\n"
        "/signals — current Buy and Sell signals\n"
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
    elif data.startswith("level:") and data[6:] in S.LEVELS:
        s["min_action"] = data[6:]
        return f"Alert level: {s['min_action']} and stronger"
    elif data == "level":
        i = S.LEVELS.index(s["min_action"]) if s["min_action"] in S.LEVELS else 1
        s["min_action"] = S.LEVELS[(i + 1) % len(S.LEVELS)]
        return f"Alert level: {s['min_action']}"
    elif data == "ladder":
        s["ladder"] = not s.get("ladder", True)
        return f"Layer alerts turned {'on' if s['ladder'] else 'off'}"
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
    for u in updates:
        s["tg_offset"] = u["update_id"]
        if (msg := u.get("message")) and str(msg["chat"]["id"]) == chat:
            text = (msg.get("text") or "").strip().lower()
            if text.startswith(("/settings", "/start", "settings")):
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
        elif (cq := u.get("callback_query")) and str(cq["message"]["chat"]["id"]) == chat:
            note = handle_callback(cq.get("data", ""), cfg, s)
            changes.append(note)
            call(token, "answerCallbackQuery", callback_query_id=cq["id"], text=note)
            call(token, "editMessageText", chat_id=chat, message_id=cq["message"]["message_id"],
                 text=settings_text(cfg, s), reply_markup=keyboard(cfg, s))
            call(token, "sendMessage", chat_id=chat, text=f"✅ {note}")
    if updates:
        S.save(s)
    if changes:
        commit_settings("; ".join(changes))
    log.info("Processed %d Telegram updates", len(updates))
    return s, changes


def listen(minutes: float) -> None:
    """Long-poll Telegram for `minutes`, answering instantly; save the read position at the end."""
    cfg = load_config()
    s = S.load(cfg)
    end = time.time() + minutes * 60
    while time.time() < end - 5:
        poll = int(max(1, min(25, end - time.time() - 5)))
        s, _ = process(cfg, poll=poll, s=s)
    S.save(s)
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
