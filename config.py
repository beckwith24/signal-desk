"""Config loading/saving. Defaults live here so a partial config.yaml still works."""
from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

CONFIG_PATH = Path(os.environ.get("SIGNAL_DESK_CONFIG", Path(__file__).with_name("config.yaml")))

DEFAULTS = {
    "watchlist": {
        "stocks": ["NVDA", "AMD", "AVGO", "PLTR", "TSLA", "MRVL", "MU", "GOOGL",
                   "AAPL", "MSFT", "META", "QQQ", "SPY"],
        "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD", "AVAX-USD"],
    },
    "timeframes": ["1d", "1wk", "4h", "2h", "1h"],
    # v2 = per-segment models from engine.py (crypto/stock x daily/4h/1h). v1 = the original five-model vote.
    "engine": "v2",
    # Optional per-segment overrides of engine.DEFAULT_SEGMENTS, e.g. {"stock-1d": {"strong_count": 3}}
    "segments": {},
    "crypto": {
        "source": "ccxt",          # ccxt or yfinance
        "exchange": "kraken",      # kraken / coinbase work from the US; binance does not
        "quote": "USD",
        "funding_exchange": "",    # e.g. "okx" or "bybit" to show perp funding rate (optional)
    },
    "models": {
        "trend": {"fast_ema": 21, "slow_ema": 55, "long_ma": 200,
                  "supertrend_period": 10, "supertrend_mult": 3.0},
        "mean_reversion": {"lookback": 20, "sd_threshold": 2.0},
        "confluence": {"rsi_period": 14, "rsi_low": 35, "rsi_high": 65, "stoch_k": 14,
                       "stoch_d": 3, "volume_lookback": 20, "volume_spike": 1.5},
        "atr_layers": {"atr_period": 14, "anchor_ma": 50, "layer_step": 1.0,
                       "max_layers": 4, "zone_layer": 2},
        "momentum": {"roc_period": 20, "swing_lookback": 10, "roc_full_strength": 0.20},
    },
    # Layer-in / layer-out plan (see ladder.py). Percentages are of the position you plan to build / hold.
    "ladder": {"enabled": True, "timeframes": ["1d"], "buy_layers": [-2, -3, -4], "buy_pct": [33, 33, 34],
               "sell_layers": [2, 3, 4], "sell_pct": [33, 33, 34]},
    "ensemble": {"min_agree": 3, "strong_score": 75, "watch_score": 58, "knife_guard": True},
    "notifications": {
        "min_action": "Buy",            # Watch, Buy or Strong Buy (applies to sells too)
        "alert_on_first_scan": False,   # don't blast every existing signal on the very first run
        "console": True,
        "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
        "ntfy": {"enabled": False, "topic": "", "server": "https://ntfy.sh"},
        "email": {"enabled": False, "smtp_host": "smtp.gmail.com", "smtp_port": 587,
                  "username": "", "password": "", "to": ""},
    },
    "scheduler": {"stock_interval_min": 30, "crypto_interval_min": 60, "market_hours_only": True},
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config(path: Path = CONFIG_PATH) -> dict:
    user = yaml.safe_load(path.read_text()) if path.exists() else {}
    cfg = _merge(DEFAULTS, user or {})
    # Secrets from environment win over the file.
    n = cfg["notifications"]
    n["telegram"]["bot_token"] = os.environ.get("TELEGRAM_BOT_TOKEN", n["telegram"]["bot_token"])
    n["telegram"]["chat_id"] = os.environ.get("TELEGRAM_CHAT_ID", n["telegram"]["chat_id"])
    n["email"]["password"] = os.environ.get("SMTP_PASSWORD", n["email"]["password"])
    # In the cloud (GitHub Actions / Streamlit Cloud) the token arrives as a secret: switch Telegram on.
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        n["telegram"]["enabled"] = True
    if os.environ.get("NTFY_TOPIC"):
        n["ntfy"]["topic"], n["ntfy"]["enabled"] = os.environ["NTFY_TOPIC"], True
    return cfg


def save_config(cfg: dict, path: Path = CONFIG_PATH) -> None:
    path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
