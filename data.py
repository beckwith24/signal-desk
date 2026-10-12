"""Free market data: yfinance for stocks/ETFs, ccxt (public endpoints) for crypto, with fallbacks."""
from __future__ import annotations

import logging
import time

import pandas as pd

log = logging.getLogger(__name__)
_EXCHANGES: dict = {}


def is_crypto(ticker: str, cfg: dict) -> bool:
    return ticker in cfg["watchlist"]["crypto"] or ticker.upper().endswith(("-USD", "-USDT"))


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df = df.dropna(subset=["close"]).astype(float)
    df.index = pd.to_datetime(df.index, utc=True)
    return df[~df.index.duplicated(keep="last")].sort_index()


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(rule).agg(agg).dropna(subset=["close"])


_YF_CACHE: dict = {}
_YF_TTL = 300  # seconds; 1h and 4h share one hourly download per ticker


def fetch_yfinance(ticker: str, tf: str) -> pd.DataFrame:
    import yfinance as yf

    # yfinance has no 4h interval: pull 1h and resample.
    period, interval = {"1d": ("2y", "1d"), "1wk": ("5y", "1wk"),
                        "1h": ("360d", "1h"), "4h": ("360d", "1h")}[tf]
    key = (ticker, period, interval)
    hit = _YF_CACHE.get(key)
    if hit and time.time() - hit[0] < _YF_TTL:
        df = hit[1]
    else:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
        if df is None or df.empty:
            raise ValueError(f"yfinance returned no data for {ticker} {tf}")
        df = _normalize(df)
        _YF_CACHE[key] = (time.time(), df)
    return _resample(df, "4h") if tf == "4h" else df.copy()


def _exchange(name: str):
    import ccxt

    if name not in _EXCHANGES:
        ex = getattr(ccxt, name)({"enableRateLimit": True})
        ex.load_markets()
        _EXCHANGES[name] = ex
    return _EXCHANGES[name]


def _ccxt_symbol(ex, ticker: str, quote: str) -> str:
    base = ticker.split("-")[0].upper()
    for q in (quote, "USD", "USDT", "USDC"):
        if f"{base}/{q}" in ex.markets:
            return f"{base}/{q}"
    raise ValueError(f"{base} not listed on {ex.id}")


def fetch_ccxt(ticker: str, tf: str, cfg: dict) -> pd.DataFrame:
    ex = _exchange(cfg["crypto"]["exchange"])
    sym = _ccxt_symbol(ex, ticker, cfg["crypto"]["quote"])
    raw = ex.fetch_ohlcv(sym, timeframe=tf, limit=500)
    if not raw:
        raise ValueError(f"{ex.id} returned no candles for {sym}")
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df.index = pd.to_datetime(df.pop("ts"), unit="ms", utc=True)
    return _normalize(df)


def fetch_ohlcv(ticker: str, tf: str, cfg: dict, retries: int = 2) -> pd.DataFrame:
    """Try each source in order, retrying with backoff; raise only if every source fails."""
    sources = []
    if is_crypto(ticker, cfg) and cfg["crypto"]["source"] == "ccxt":
        sources.append(("ccxt", lambda: fetch_ccxt(ticker, tf, cfg)))
    sources.append(("yfinance", lambda: fetch_yfinance(ticker, tf)))

    last_err = None
    for name, fn in sources:
        for attempt in range(retries):
            try:
                return fn()
            except Exception as e:  # network errors, rate limits, unknown symbols
                last_err = e
                log.warning("%s %s via %s failed (attempt %d): %s", ticker, tf, name, attempt + 1, e)
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"No data for {ticker} {tf}: {last_err}")


def fetch_funding_rate(ticker: str, cfg: dict) -> float | None:
    """Optional crypto extra: perpetual funding rate from a public endpoint. None if unavailable."""
    name = cfg["crypto"].get("funding_exchange")
    if not name:
        return None
    try:
        ex = _exchange(name)
        base = ticker.split("-")[0].upper()
        return float(ex.fetch_funding_rate(f"{base}/USDT:USDT")["fundingRate"])
    except Exception as e:
        log.info("Funding rate unavailable for %s: %s", ticker, e)
        return None
