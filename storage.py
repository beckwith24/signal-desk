"""SQLite persistence: signal history and the latest state per ticker/timeframe (for de-duplicating alerts)."""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

DB_PATH = Path(os.environ.get("SIGNAL_DESK_DB", Path(__file__).with_name("signals.db")))

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, ticker TEXT, timeframe TEXT, price REAL,
    action TEXT, rank INTEGER, score INTEGER, bull INTEGER, bear INTEGER,
    reasons TEXT, notified INTEGER
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS ladder_state (
    ticker TEXT, timeframe TEXT, buy_tier INTEGER, sell_tier INTEGER, PRIMARY KEY (ticker, timeframe)
);
CREATE TABLE IF NOT EXISTS state (
    ticker TEXT, timeframe TEXT, action TEXT, rank INTEGER, score INTEGER,
    price REAL, ts TEXT, PRIMARY KEY (ticker, timeframe)
);
"""


def _conn():
    return closing(sqlite3.connect(DB_PATH, timeout=30))


def init() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)
        c.commit()


def get_state(ticker: str, tf: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT action, rank, score, price, ts FROM state WHERE ticker=? AND timeframe=?",
                        (ticker, tf)).fetchone()
    return dict(zip(["action", "rank", "score", "price", "ts"], row)) if row else None


def set_state(r: dict) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO state VALUES (?,?,?,?,?,?,?)",
                  (r["ticker"], r["timeframe"], r["action"], r["rank"], r["score"], r["price"], r["ts"]))
        c.commit()


def log_signal(r: dict, notified: bool) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO signals (ts,ticker,timeframe,price,action,rank,score,bull,bear,reasons,notified) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (r["ts"], r["ticker"], r["timeframe"], r["price"], r["action"], r["rank"], r["score"],
             r["bull"], r["bear"], " | ".join(r["reasons"]), int(notified)))
        c.commit()


def history(limit: int = 1000) -> pd.DataFrame:
    """Signal log joined with the latest scanned price, so you can see how each call played out."""
    q = """
    SELECT s.ts, s.ticker, s.timeframe, s.action, s.rank, s.score, s.price AS signal_price,
           st.price AS latest_price, s.reasons, s.notified
    FROM signals s LEFT JOIN state st ON st.ticker = s.ticker AND st.timeframe = s.timeframe
    ORDER BY s.id DESC LIMIT ?
    """
    with _conn() as c:
        df = pd.read_sql_query(q, c, params=(limit,))
    if not df.empty:
        move = df["latest_price"] / df["signal_price"] - 1
        df["move_since_%"] = (move * 100).round(2)
        # Positive = the signal's direction was right so far (buy & price up, or sell & price down).
        sign = df["rank"].apply(lambda x: (x > 0) - (x < 0))
        df["signal_result_%"] = (move * sign * 100).round(2)
    return df


def ensure_engine(engine: str) -> bool:
    """When the signal engine changes, forget the last action per ticker so the first scan on the
    new engine is a quiet baseline (no alerts from comparing new signals with old ones).
    Signal history and ladder state are kept. Returns True if a reset happened."""
    with _conn() as c:
        row = c.execute("SELECT value FROM meta WHERE key='engine'").fetchone()
        if row and row[0] == engine:
            return False
        c.execute("DELETE FROM state")
        c.execute("INSERT OR REPLACE INTO meta VALUES ('engine', ?)", (engine,))
        c.commit()
    return True


def last_entry(ticker: str, tf: str) -> dict | None:
    """Most recent logged Buy/Strong Buy for this ticker/timeframe (for exit messages)."""
    with _conn() as c:
        row = c.execute("SELECT ts, action, price FROM signals WHERE ticker=? AND timeframe=? AND rank>=2 "
                        "ORDER BY id DESC LIMIT 1", (ticker, tf)).fetchone()
    return dict(zip(["ts", "action", "price"], row)) if row else None


def episode_alerted(ticker: str, tf: str, min_rank: int) -> bool:
    """Was an alert sent during the current Buy run (the latest rows with rank >= 2) at your alert level?"""
    with _conn() as c:
        rows = c.execute("SELECT rank, notified FROM signals WHERE ticker=? AND timeframe=? ORDER BY id DESC LIMIT 50",
                         (ticker, tf)).fetchall()
    for rank, notified in rows:
        if rank < 2:
            return False
        if notified and rank >= min_rank:
            return True
    return False


def recently_notified(ticker: str, tf: str, action: str, hours: float) -> bool:
    """Was this same alert sent for this ticker/timeframe within the last `hours`?"""
    with _conn() as c:
        row = c.execute("SELECT ts FROM signals WHERE ticker=? AND timeframe=? AND action=? AND notified=1 "
                        "ORDER BY id DESC LIMIT 1", (ticker, tf, action)).fetchone()
    if not row:
        return False
    try:
        when = pd.Timestamp(row[0].replace(" UTC", ""), tz="UTC")
    except ValueError:
        return False
    return pd.Timestamp.now(tz="UTC") - when < pd.Timedelta(hours=hours)


def get_ladder(ticker: str, tf: str) -> tuple[int, int] | None:
    with _conn() as c:
        row = c.execute("SELECT buy_tier, sell_tier FROM ladder_state WHERE ticker=? AND timeframe=?",
                        (ticker, tf)).fetchone()
    return (int(row[0]), int(row[1])) if row else None


def set_ladder(ticker: str, tf: str, buy_tier: int, sell_tier: int) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO ladder_state VALUES (?,?,?,?)", (ticker, tf, buy_tier, sell_tier))
        c.commit()


def signals_for(ticker: str, tf: str, limit: int = 60) -> list[dict]:
    """Past action changes for one ticker/timeframe, oldest first (for chart markers)."""
    with _conn() as c:
        rows = c.execute("SELECT ts, action, rank, score, price FROM signals WHERE ticker=? AND timeframe=? "
                         "ORDER BY id DESC LIMIT ?", (ticker, tf, limit)).fetchall()
    return [dict(zip(["ts", "action", "rank", "score", "price"], r)) for r in reversed(rows)]


def latest_states() -> pd.DataFrame:
    with _conn() as c:
        return pd.read_sql_query("SELECT * FROM state ORDER BY abs(rank) DESC, score DESC", c)
