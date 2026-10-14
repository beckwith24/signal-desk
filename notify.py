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
ICONS = {"Panic Buy": "🟢🟢🟢", "Strong Buy": "🟢🟢", "Buy": "🟢", "Watch ↑": "👀", "Hold": "⚪",
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
        f"Score: {r['score']}/100 · {r['bull']} bullish / {r['bear']} bearish of {len(r['models'])} models",
        *([f"Models: {r['segment_about']}"] if r.get("segment_about") else []),
        "Why:",
        *[f"• {x}" for x in r["reasons"]],
        *[f"ℹ️ {x}" for x in r.get("notes", [])],
        *([size_line(r)] if r.get("rank", 0) > 0 and size_line(r) else []),
        f"🕒 {r['ts']}",
        *([f"📈 Chart: {link}"] if link else []),
        "Change alerts: /settings",
        "",
        f"⚠️ {DISCLAIMER}",
    ]
    return "\n".join(lines)


def size_line(r: dict) -> str | None:
    rk = (r.get("overlays") or {}).get("risk")
    if not rk:
        return None
    if rk["size"] >= 0.95:
        return f"⚖️ Size: a normal position (swings {rk['vol_pct']}% a year, within the {rk['target_pct']}% guide)."
    return (f"⚖️ Size: about {rk['size']:.2g}× a normal position. It swings {rk['vol_pct']}% a year vs a "
            f"{rk['target_pct']}% guide, so a smaller position keeps the risk similar.")


def format_exit(r: dict, entry: dict) -> str:
    """entry = the Buy that is ending (its time, action and price when it started)."""
    link = chart_link(r)
    move = (r["price"] / entry["price"] - 1) * 100 if entry.get("price") else None
    lines = [
        f"⚪ EXIT — {r['ticker']} ({r['timeframe']})",
        f"The {entry['action']} signal from {entry['ts']} has ended: now {r['action']} "
        f"({r['bull']} of {len(r['models'])} models bullish).",
        "The tested strategy steps aside here and waits for the next Buy.",
        f"Price: {r['price']:,.4g}" + (f" ({move:+.1f}% since that signal at {entry['price']:,.4g})" if move is not None else ""),
        *[f"• {x}" for x in r["reasons"]],
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
