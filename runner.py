"""
Headless scheduler — run this to get alerts without keeping the dashboard open.

    python runner.py          # stocks every N min during US market hours, crypto 24/7
    python runner.py --once                 # single scan (stocks skipped outside market hours), then exit
    python runner.py --once --only crypto   # just crypto (what the GitHub Actions hourly job runs)
    python runner.py --once --force         # everything, ignoring market hours
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

import settings
from config import load_config
from scanner import run_scan

log = logging.getLogger("runner")


def us_market_open(now: datetime | None = None) -> bool:
    """Regular session Mon–Fri 9:30–16:05 ET. (Exchange holidays are not handled.)"""
    now = now or datetime.now(ZoneInfo("America/New_York"))
    return now.weekday() < 5 and time(9, 30) <= now.time() <= time(16, 5)


def _config_with_switches() -> tuple[dict, bool]:
    """Load config.yaml (re-read every run) and apply the on/off switches set from Telegram."""
    s = settings.load(load_config())
    cfg = settings.apply(load_config(), s)
    if s["paused"]:
        log.info("Alerts paused from Telegram: scanning without sending")
    return cfg, not s["paused"]


def job_stocks(force: bool = False) -> None:
    cfg, notify = _config_with_switches()
    if not force and cfg["scheduler"]["market_hours_only"] and not us_market_open():
        log.info("Market closed, skipping stock scan")
        return
    if not cfg["timeframes"]:
        log.info("All timeframes switched off")
        return
    res, errs = run_scan(cfg, tickers=cfg["watchlist"]["stocks"], notify=notify)
    log.info("Stock scan: %d results, %d errors", len(res), len(errs))


def job_crypto() -> None:
    cfg, notify = _config_with_switches()
    if not cfg["timeframes"]:
        log.info("All timeframes switched off")
        return
    res, errs = run_scan(cfg, tickers=cfg["watchlist"]["crypto"], notify=notify)
    log.info("Crypto scan: %d results, %d errors", len(res), len(errs))


def add_jobs(scheduler, cfg: dict) -> None:
    now = datetime.now()
    s = cfg["scheduler"]
    scheduler.add_job(job_stocks, "interval", minutes=s["stock_interval_min"], id="stocks",
                      next_run_time=now, replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(job_crypto, "interval", minutes=s["crypto_interval_min"], id="crypto",
                      next_run_time=now, replace_existing=True, max_instances=1, coalesce=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="scan once and exit (used by cron / GitHub Actions)")
    ap.add_argument("--only", choices=["all", "stocks", "crypto"], default="all")
    ap.add_argument("--force", action="store_true", help="scan stocks even outside market hours")
    args = ap.parse_args()
    cfg = load_config()
    if args.once:
        if args.only in ("all", "stocks"):
            job_stocks(force=args.force)
        if args.only in ("all", "crypto"):
            job_crypto()
        return
    from apscheduler.schedulers.blocking import BlockingScheduler

    sched = BlockingScheduler()
    add_jobs(sched, cfg)
    log.info("Scheduler started (Ctrl+C to stop)")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
