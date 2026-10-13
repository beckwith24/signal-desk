"""
On/off switches changed from Telegram (see bot.py). Kept in settings.json in the repo, so the
scheduled scans in GitHub Actions pick them up on their next run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

SETTINGS_PATH = Path(os.environ.get("SIGNAL_DESK_SETTINGS", Path(__file__).with_name("settings.json")))
LEVELS = ["Watch", "Buy", "Strong Buy"]


def load(cfg: dict) -> dict:
    s = {"timeframes": {tf: True for tf in cfg["timeframes"]}, "paused": False,
         "ladder": bool(cfg["ladder"].get("enabled", True)),
         "min_action": cfg["notifications"]["min_action"], "tg_offset": 0}
    try:
        saved = json.loads(SETTINGS_PATH.read_text())
    except (FileNotFoundError, ValueError):
        saved = {}
    s["timeframes"].update({k: bool(v) for k, v in saved.get("timeframes", {}).items() if k in s["timeframes"]})
    for key in ("paused", "tg_offset", "ladder"):
        if key in saved:
            s[key] = saved[key]
    if saved.get("min_action") in LEVELS:
        s["min_action"] = saved["min_action"]
    return s


def save(s: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(s, indent=2) + "\n")


def apply(cfg: dict, s: dict) -> dict:
    """Return cfg with the Telegram switches applied (timeframes switched off are not scanned)."""
    cfg["timeframes"] = [tf for tf in cfg["timeframes"] if s["timeframes"].get(tf, True)]
    cfg["notifications"]["min_action"] = s["min_action"]
    cfg["ladder"]["enabled"] = bool(s.get("ladder", True))
    return cfg
