"""
Assemble the chart website in site/ (published to GitHub Pages by the scan workflow).

Each scan only refreshes the tickers it scanned (stocks or crypto), so any chart file not written
this run is copied from the live site. Then an index of every ticker/timeframe is written.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import settings
from chart_export import SITE_DIR, file_id
from config import load_config
from notify import DISCLAIMER

log = logging.getLogger("build_site")
ROOT = Path(__file__).parent
SUMMARY_KEYS = ["ticker", "tf", "asset", "updated", "price", "change_pct", "action", "rank", "score",
                "bull", "bear", "layer", "decimals", "segment_about"]


def spark(d: dict, days: int = 30) -> dict:
    """The last month of daily closes for the home-page mini chart, scaled 0-100 (shape only, small file)."""
    t, c = d.get("t") or [], d.get("c") or []
    if not t or len(t) != len(c):
        return {}
    cut = t[-1] - days * 86400
    closes = [x for ts, x in zip(t, c) if ts >= cut and x is not None]
    if len(closes) < 2:
        return {}
    lo, hi = min(closes), max(closes)
    return {"spark": [round((x - lo) / (hi - lo) * 100) if hi > lo else 50 for x in closes],
            "spark_pct": round((closes[-1] / closes[0] - 1) * 100, 1)}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = settings.apply(load_config(), settings.load(load_config()))   # includes Telegram watchlist edits
    data = SITE_DIR / "data"
    data.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "web").iterdir():
        if f.is_file():
            shutil.copy(f, SITE_DIR / f.name)
    page = (SITE_DIR / "index.html").read_text()
    for js in ("theme.js", "app.js", "lightweight-charts.js"):   # new code reaches phones right away, not after a cache expires
        ver = hashlib.sha256((ROOT / "web" / js).read_bytes()).hexdigest()[:10]
        page = page.replace(f'src="{js}"', f'src="{js}?v={ver}"')
    # version of the whole page: an open page (or home-screen app) compares it with index.json and reloads itself
    ui = hashlib.sha256(b"".join((ROOT / "web" / f).read_bytes() for f in
                                 ("index.html", "app.js", "theme.js", "lightweight-charts.js"))).hexdigest()[:12]
    page = page.replace('content="__UI__"', f'content="{ui}"')
    (SITE_DIR / "index.html").write_text(page)
    (SITE_DIR / ".nojekyll").touch()

    live = os.environ.get("PAGES_URL", "").rstrip("/")
    tickers = cfg["watchlist"]["stocks"] + cfg["watchlist"]["crypto"]
    items, kept = [], 0
    for t in tickers:
        for tf in cfg["timeframes"]:
            path = data / f"{file_id(t, tf)}.json"
            if not path.exists() and live:
                try:
                    r = requests.get(f"{live}/data/{path.name}", params={"v": int(time.time())}, timeout=15)
                    if r.ok:
                        json.loads(r.text)  # only keep valid files
                        path.write_text(r.text)
                        kept += 1
                except Exception as e:
                    log.info("No previous chart for %s %s: %s", t, tf, e)
            if path.exists():
                d = json.loads(path.read_text())
                item = {k: d.get(k) for k in SUMMARY_KEYS}
                if tf == "1d":                    # one chip per model on the home page
                    item["models"] = [{"s": m.get("short") or m["name"], "v": m["vote"], "r": m["reason"]}
                                      for m in d.get("models", [])]
                    cut = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
                    recent = [c for c in (d.get("congress") or []) if c["disclosed"] >= cut]
                    if recent:                    # congressional trades reported in the last 30 days
                        item["congress"] = {"buys": sum(c["side"] == "buy" for c in recent),
                                            "sells": sum(c["side"] == "sell" for c in recent)}
                    item.update(spark(d))
                items.append(item)
    bot_name = ""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if token:   # the bot's @username, so the site can open it to add/remove tickers
        try:
            bot_name = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10).json()["result"]["username"]
        except Exception as e:
            log.info("Bot name unavailable: %s", e)
    have = {(i["ticker"]) for i in items}
    index = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "bot": bot_name,
        "repo": os.environ.get("GITHUB_REPOSITORY", ""),
        "watchlist": cfg["watchlist"],
        "missing": [t for t in tickers if t not in have],   # on the list but no chart yet (new or bad symbol)
        "timeframes": cfg["timeframes"],
        "disclaimer": DISCLAIMER,
        "ui": ui,
        "items": items,
    }
    (data / "index.json").write_text(json.dumps(index, separators=(",", ":")))
    log.info("Site built: %d charts (%d carried over from the live site)", len(items), kept)


if __name__ == "__main__":
    main()
