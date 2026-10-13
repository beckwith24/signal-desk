"""
Assemble the chart website in site/ (published to GitHub Pages by the scan workflow).

Each scan only refreshes the tickers it scanned (stocks or crypto), so any chart file not written
this run is copied from the live site. Then an index of every ticker/timeframe is written.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from chart_export import SITE_DIR, file_id
from config import load_config
from notify import DISCLAIMER

log = logging.getLogger("build_site")
ROOT = Path(__file__).parent
SUMMARY_KEYS = ["ticker", "tf", "asset", "updated", "price", "change_pct", "action", "rank", "score",
                "bull", "bear", "layer", "decimals"]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    data = SITE_DIR / "data"
    data.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "web").iterdir():
        if f.is_file():
            shutil.copy(f, SITE_DIR / f.name)
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
                items.append({k: d.get(k) for k in SUMMARY_KEYS})
    index = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "timeframes": cfg["timeframes"],
        "disclaimer": DISCLAIMER,
        "items": items,
    }
    (data / "index.json").write_text(json.dumps(index, separators=(",", ":")))
    log.info("Site built: %d charts (%d carried over from the live site)", len(items), kept)


if __name__ == "__main__":
    main()
