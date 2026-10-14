"""
Does tuning the IA ATR Model per asset hold up on data it never saw?

The InvestAnswers ATR demo tunes the settings on each asset's own backtest (signal logic, noise suppression,
Heikin-Ashi or candles, 50% entries and exits) and keeps the combination with a high win rate (80-90%) and
the best ROI, skipping assets where nothing looks good. This replays that process honestly:

  1. For each ticker, try every combination on 2017-2022 and pick the way the demo does.
  2. Run the picked combination on 2023 to now, which it never saw.
  3. Compare with the same settings' in-sample numbers, with the default settings, and with just holding.

The ATR Model itself is our close rebuild (ia.py), not InvestAnswers' code:
  Trend logic      ATR trailing stop flips (k x ATR30); noise none/low/medium/high = k 0.75/1.0/1.25/1.75
  Deviation logic  buy below SMA30 - m x ATR30, sell above SMA30 + m x ATR30; m 1.0/1.5/2.0/2.5
  Basis            real candles or Heikin-Ashi candles
  Sizing           "double tap": each buy adds one lot (half of equity, while cash lasts); each sell sells one
                   lot (first in, first out). Option: only sell when the lot is in profit (never book a loss).
Trades fill at the next bar's open, with costs (0.05% a side for stocks, 0.25% for crypto).

    python ia_tuning_research.py        (Actions tab -> "IA tuning test")

Writes research/ia_tuning.md and research/ia_tuning.json.
"""
from __future__ import annotations

import itertools
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("ia_tuning")
OUT = Path(__file__).with_name("research")
SPLIT = pd.Timestamp("2023-01-01")
START = pd.Timestamp("2017-01-01")
NOISE = {"none": (0.75, 1.0), "low": (1.0, 1.5), "medium": (1.25, 2.0), "high": (1.75, 2.5)}   # (trend k, deviation m)
GRID = list(itertools.product(["trend", "deviation"], list(NOISE), ["candles", "heikin-ashi"], [False, True]))
DEFAULT = ("trend", "medium", "candles", False)
N_ATR = 30


def heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    hc = (o + h + l + c) / 4
    ho = np.empty_like(hc); ho[0] = (o[0] + c[0]) / 2
    for i in range(1, len(hc)):
        ho[i] = (ho[i - 1] + hc[i - 1]) / 2
    return pd.DataFrame({"open": ho, "high": np.maximum.reduce([h, ho, hc]), "low": np.minimum.reduce([l, ho, hc]),
                         "close": hc}, index=df.index)


def atr(df: pd.DataFrame, n: int = N_ATR) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def events(df: pd.DataFrame, logic: str, noise: str, basis: str) -> tuple[np.ndarray, np.ndarray]:
    """Buy and sell signal flags at each bar's close (only past and current bars used)."""
    b = heikin_ashi(df) if basis == "heikin-ashi" else df
    a = atr(b).to_numpy()
    c = b["close"].to_numpy(float)
    k, m = NOISE[noise]
    n = len(c)
    if logic == "trend":                    # ATR trailing stop, flips when the close crosses it
        stop, up = np.zeros(n), np.zeros(n, bool)
        for i in range(1, n):
            nl = k * a[i]
            if nl != nl:
                continue
            p, x, xp = stop[i - 1], c[i], c[i - 1]
            if x > p and xp > p: stop[i] = max(p, x - nl)
            elif x < p and xp < p: stop[i] = min(p, x + nl)
            elif x > p: stop[i] = x - nl
            else: stop[i] = x + nl
            up[i] = x > stop[i]
        prev = np.r_[False, up[:-1]]
        valid = ~np.isnan(a)
        return up & ~prev & valid, ~up & prev & valid
    mid = pd.Series(c).rolling(N_ATR).mean().to_numpy()
    lo, hi = mid - m * a, mid + m * a
    below, above = c < lo, c > hi
    return below & ~np.r_[False, below[:-1]], above & ~np.r_[False, above[:-1]]


def simulate(df: pd.DataFrame, buy: np.ndarray, sell: np.ndarray, cost: float, profit_only: bool,
             start: pd.Timestamp, end: pd.Timestamp | None = None) -> dict:
    """Double-tap lots from `start`; fills at the next bar's open; equity marked to market daily."""
    o, c = df["open"].to_numpy(float), df["close"].to_numpy(float)
    idx = df.index
    i0 = int(np.searchsorted(idx, start)); i1 = len(df) if end is None else int(np.searchsorted(idx, end))
    if i1 - i0 < 60:
        return {}
    cash, lots, eq, wins, sells, buys, inv = 1.0, [], [], 0, 0, 0, 0
    for i in range(i0, i1):
        if i > i0 and i - 1 >= i0:
            px = o[i]
            if buy[i - 1] and len(lots) < 2 and cash > 1e-9:
                spend = min(cash, 0.5 * (cash + sum(q * px for q, _ in lots)))
                q = spend * (1 - cost) / px
                lots.append((q, px * (1 + cost))); cash -= spend; buys += 1
            elif sell[i - 1] and lots:
                q, cb = lots[0]
                if not (profit_only and px * (1 - cost) <= cb):
                    lots.pop(0); cash += q * px * (1 - cost); sells += 1; wins += px * (1 - cost) > cb
        eq.append(cash + sum(q * c[i] for q, _ in lots)); inv += bool(lots)
    eq = pd.Series(eq, index=idx[i0:i1])
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 0.1)
    hold = c[i1 - 1] / c[i0] - 1
    hold_eq = pd.Series(c[i0:i1] / c[i0], index=eq.index)
    open_loss = min([c[i1 - 1] / cb - 1 for _, cb in lots], default=0.0)
    return {"roi_pct": round((eq.iat[-1] - 1) * 100, 1), "cagr_pct": round((eq.iat[-1] ** (1 / years) - 1) * 100, 1),
            "win_pct": round(100 * wins / sells, 1) if sells else None, "sells": sells, "buys": buys,
            "max_dd_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 1),
            "hold_roi_pct": round(hold * 100, 1), "hold_dd_pct": round(float((hold_eq / hold_eq.cummax() - 1).min()) * 100, 1),
            "invested_pct": round(100 * inv / max(len(eq), 1), 1), "open_lots": len(lots), "worst_open_lot_pct": round(open_loss * 100, 1)}


def label(combo) -> str:
    logic, noise, basis, prof = combo
    return f"{logic}, {noise} noise, {basis}" + (", sells only in profit" if prof else "")


def pick(rows: list[dict]) -> dict | None:
    """The demo's way: among settings with 80%+ wins (and enough trades), the highest ROI; else skip."""
    ok = [r for r in rows if r["is"] and (r["is"].get("win_pct") or 0) >= 80 and r["is"]["sells"] >= 5]
    return max(ok, key=lambda r: r["is"]["roi_pct"]) if ok else None


def tickers() -> dict[str, list[str]]:
    import settings
    from config import load_config
    w = settings.watchlist(load_config(), settings.load(load_config()))
    return {"stock": list(w["stocks"]), "crypto": list(w["crypto"])}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from backtest import download
    res = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "split": str(SPLIT.date()),
           "assets": {}, "skipped_data": []}
    for asset, ts in tickers().items():
        cost = 0.0025 if asset == "crypto" else 0.0005
        for t in ts:
            try:
                df = download(t, "1d")
            except Exception as e:
                res["skipped_data"].append(f"{t}: {str(e)[:60]}"); continue
            df.index = pd.DatetimeIndex(df.index).tz_localize(None)
            if df.index[0] > pd.Timestamp("2020-01-01") or len(df) < 800:
                res["skipped_data"].append(f"{t}: history starts {df.index[0].date()}"); continue
            start = max(START, df.index[0] + pd.Timedelta(days=60))
            rows = []
            for combo in GRID:
                logic, noise, basis, prof = combo
                b, s = events(df, logic, noise, basis)
                rows.append({"combo": combo, "is": simulate(df, b, s, cost, prof, start, SPLIT),
                             "oos": simulate(df, b, s, cost, prof, SPLIT)})
            chosen = pick(rows)
            best_roi = max([r for r in rows if not r["combo"][3]], key=lambda r: r["is"].get("roi_pct", -1e9))
            default = next(r for r in rows if r["combo"] == DEFAULT)
            oos_all = [r["oos"]["roi_pct"] for r in rows if r["oos"]]
            is_rank = pd.Series([r["is"].get("roi_pct", np.nan) for r in rows]).rank()
            oos_rank = pd.Series([r["oos"].get("roi_pct", np.nan) for r in rows]).rank()
            res["assets"][t] = {
                "asset": asset, "from": str(df.index[0].date()),
                "chosen": None if chosen is None else {"settings": list(chosen["combo"]), "is": chosen["is"], "oos": chosen["oos"]},
                "best_roi": {"settings": list(best_roi["combo"]), "is": best_roi["is"], "oos": best_roi["oos"]},
                "default": {"is": default["is"], "oos": default["oos"]},
                "oos_median_all_settings_roi": float(np.median(oos_all)) if oos_all else None,
                "rank_corr_is_oos": round(float(is_rank.corr(oos_rank)), 2),
            }
            log.info("%s done (%s)", t, "picked " + "/".join(map(str, chosen["combo"])) if chosen else "skipped")
    OUT.mkdir(exist_ok=True)
    (OUT / "ia_tuning.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "ia_tuning.md").write_text(report(res))
    log.info("done")


def _mean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return round(float(np.mean(xs)), 1) if xs else None


def report(res: dict) -> str:
    A = res["assets"]
    L = [f"# Tuning the IA ATR Model per asset: does it hold up? ({res['generated']})", "",
         f"Settings picked on 2017–2022 (the demo's way: 80%+ wins, then highest ROI), then run on "
         f"{res['split']} to now. Fills at next open, with costs. Our rebuild of the model, not IA's code.", ""]
    for asset in ("stock", "crypto"):
        names = [t for t, a in A.items() if a["asset"] == asset]
        picked = [t for t in names if A[t]["chosen"]]
        L += [f"## {asset.title()}s ({len(names)} tickers; {len(picked)} passed the 80%-win screen, "
              f"{len(names) - len(picked)} would be skipped)", ""]
        if picked:
            ch = [A[t]["chosen"] for t in picked]
            L += ["| | Win % | ROI % | Worst drop % | Trades (sells) |", "|---|---|---|---|---|",
                  f"| Picked settings, 2017–2022 (in-sample) | {_mean([c['is']['win_pct'] for c in ch])} | "
                  f"{_mean([c['is']['roi_pct'] for c in ch])} | {_mean([c['is']['max_dd_pct'] for c in ch])} | "
                  f"{_mean([c['is']['sells'] for c in ch])} |",
                  f"| Same settings, 2023–now (unseen) | {_mean([c['oos']['win_pct'] for c in ch])} | "
                  f"{_mean([c['oos']['roi_pct'] for c in ch])} | {_mean([c['oos']['max_dd_pct'] for c in ch])} | "
                  f"{_mean([c['oos']['sells'] for c in ch])} |",
                  f"| Best in-sample ROI with normal sells, 2017–2022 | {_mean([A[t]['best_roi']['is'].get('win_pct') for t in picked])} | "
                  f"{_mean([A[t]['best_roi']['is'].get('roi_pct') for t in picked])} | "
                  f"{_mean([A[t]['best_roi']['is'].get('max_dd_pct') for t in picked])} | "
                  f"{_mean([A[t]['best_roi']['is'].get('sells') for t in picked])} |",
                  f"| Same, 2023–now (unseen) | {_mean([A[t]['best_roi']['oos'].get('win_pct') for t in picked])} | "
                  f"{_mean([A[t]['best_roi']['oos'].get('roi_pct') for t in picked])} | "
                  f"{_mean([A[t]['best_roi']['oos'].get('max_dd_pct') for t in picked])} | "
                  f"{_mean([A[t]['best_roi']['oos'].get('sells') for t in picked])} |",
                  f"| Default settings, 2023–now | {_mean([A[t]['default']['oos'].get('win_pct') for t in picked])} | "
                  f"{_mean([A[t]['default']['oos'].get('roi_pct') for t in picked])} | "
                  f"{_mean([A[t]['default']['oos'].get('max_dd_pct') for t in picked])} | "
                  f"{_mean([A[t]['default']['oos'].get('sells') for t in picked])} |",
                  f"| Just holding, 2023–now | – | {_mean([c['oos']['hold_roi_pct'] for c in ch])} | "
                  f"{_mean([c['oos']['hold_dd_pct'] for c in ch])} | – |", ""]
            beat = sum(c["oos"]["roi_pct"] > c["oos"]["hold_roi_pct"] for c in ch)
            L += [f"Picked settings beat holding on {beat} of {len(ch)} tickers after 2022. "
                  f"Average rank correlation between in-sample and later ROI across all {len(GRID)} settings: "
                  f"{_mean([A[t]['rank_corr_is_oos'] for t in names])} (1 = the best in-sample stay best; 0 = no link).", ""]
        L += ["| Ticker | Picked settings | Win % then → after | ROI % then → after | Hold % after | Open lots / worst open lot % |",
              "|---|---|---|---|---|---|"]
        for t in names:
            a = A[t]; c = a["chosen"]
            if not c:
                L.append(f"| {t} | skipped (no setting reached 80% wins) | | | {a['default']['oos'].get('hold_roi_pct')} | |"); continue
            L.append(f"| {t} | {label(c['settings'])} | {c['is']['win_pct']} → {c['oos']['win_pct']} | "
                     f"{c['is']['roi_pct']} → {c['oos']['roi_pct']} | {c['oos']['hold_roi_pct']} | "
                     f"{c['oos']['open_lots']} / {c['oos']['worst_open_lot_pct']} |")
        L.append("")
    if res["skipped_data"]:
        L += ["Not enough history: " + ", ".join(res["skipped_data"]), ""]
    return "\n".join(L)


if __name__ == "__main__":
    try:
        main()
    except Exception:                       # keep the error readable in the results file (Actions logs aren't always reachable)
        import traceback
        OUT.mkdir(exist_ok=True)
        (OUT / "ia_tuning.md").write_text("# Run failed\n\n```\n" + traceback.format_exc() + "```\n")
        raise SystemExit(0)
