"""Notifications: Telegram (preferred), ntfy.sh, email, console. Every message carries the disclaimer."""
from __future__ import annotations

import logging
import os
import re
import smtplib
from email.message import EmailMessage

import requests

log = logging.getLogger(__name__)

DISCLAIMER = "Personal research tool only. Not financial advice. Signals can be wrong. Do your own research."
ICONS = {"Strong Buy": "🟢🟢", "Buy": "🟢", "Watch ↑": "👀", "Hold": "⚪",
         "Watch ↓": "👀", "Sell": "🔴", "Strong Sell": "🔴🔴"}


def chart_link(r: dict) -> str | None:
    """Link to this ticker's chart on the GitHub Pages site (PAGES_URL is set by the workflow)."""
    base = os.environ.get("PAGES_URL", "").rstrip("/")
    if not base:
        return None
    return f"{base}/#{re.sub(r'[^A-Za-z0-9_.-]', '_', r['ticker'] + '_' + r['timeframe'])}"


def format_message(r: dict) -> str:
    link = chart_link(r)
    lines = [
        f"{ICONS.get(r['action'], '')} {r['action'].upper()} — {r['ticker']} ({r['timeframe']})",
        f"Price: {r['price']:,.4g}  ({r['change_pct']:+.2f}% last bar)",
        f"Confluence score: {r['score']}/100 · {r['bull']} bullish / {r['bear']} bearish models",
        "Why:",
        *[f"• {x}" for x in r["reasons"]],
        *[f"ℹ️ {x}" for x in r.get("notes", [])],
        f"🕒 {r['ts']}",
        *([f"📈 Chart: {link}"] if link else []),
        "Change alerts: /settings",
        "",
        f"⚠️ {DISCLAIMER}",
    ]
    return "\n".join(lines)


def send_telegram(token: str, chat_id: str, text: str) -> None:
    resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
                         timeout=15)
    resp.raise_for_status()


def send_ntfy(server: str, topic: str, text: str) -> None:
    requests.post(f"{server.rstrip('/')}/{topic}", data=text.encode("utf-8"), timeout=15).raise_for_status()


def send_email(e: dict, subject: str, text: str) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, e["username"], e["to"]
    msg.set_content(text)
    with smtplib.SMTP(e["smtp_host"], int(e["smtp_port"]), timeout=20) as s:
        s.starttls()
        s.login(e["username"], e["password"])
        s.send_message(msg)


def send_all(text: str, cfg: dict, subject: str = "Signal alert") -> list[str]:
    """Send through every enabled channel. Returns the channels that succeeded."""
    n, sent = cfg["notifications"], []
    if n["telegram"]["enabled"] and n["telegram"]["bot_token"] and n["telegram"]["chat_id"]:
        try:
            send_telegram(n["telegram"]["bot_token"], n["telegram"]["chat_id"], text)
            sent.append("telegram")
        except Exception as ex:
            log.error("Telegram failed: %s", ex)
    if n["ntfy"]["enabled"] and n["ntfy"]["topic"]:
        try:
            send_ntfy(n["ntfy"]["server"], n["ntfy"]["topic"], text)
            sent.append("ntfy")
        except Exception as ex:
            log.error("ntfy failed: %s", ex)
    if n["email"]["enabled"] and n["email"]["username"] and n["email"]["to"]:
        try:
            send_email(n["email"], subject, text)
            sent.append("email")
        except Exception as ex:
            log.error("Email failed: %s", ex)
    if n.get("console", True):
        print("\n" + text + "\n" + "-" * 60, flush=True)
        sent.append("console")
    return sent
