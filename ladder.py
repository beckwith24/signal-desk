"""
Layer-in / layer-out ladder.

Price is measured against an anchor (the 50-bar moving average) in steps of one ATR (a typical
bar's range). Each step is a "layer". The plan, by default:

    Layer in:   L-2  add 33%    L-3  add 33%    L-4  add 34%   (of the position you plan to build)
    Layer out:  L+2  trim 33%   L+3  trim 33%   L+4  trim 34%  (of the position you hold)

Once price climbs back above the anchor, the buy ladder resets for the next dip (and the sell
ladder resets once price drops below it), so each new dip or rally starts at layer 1 again.

plan() describes the ladder for one scan result; check_alerts() decides which layers were newly
reached since the last scan and builds Telegram messages for them.
"""
from __future__ import annotations

import os
import re

import storage
from notify import DISCLAIMER

DEFAULT = {
    "enabled": True,
    "timeframes": ["1d"],              # layer alerts are a positioning plan; daily is the natural pace
    "buy_layers": [-2, -3, -4],
    "buy_pct": [33, 33, 34],
    "sell_layers": [2, 3, 4],
    "sell_pct": [33, 33, 34],
}


def _fmt(p: float) -> str:
    return f"{p:,.2f}" if p >= 1 else f"{p:.4g}"


def plan(res: dict, cfg: dict) -> dict:
    lc = cfg["ladder"]
    ov = res["overlays"]
    anchor, step, dist = ov["anchor_last"], ov["step_last"], ov["distance"]
    level = lambda k: anchor + k * step
    buys = [{"layer": k, "price": level(k), "pct": p, "reached": dist <= k}
            for k, p in zip(lc["buy_layers"], lc["buy_pct"])]
    sells = [{"layer": k, "price": level(k), "pct": p, "reached": dist >= k}
             for k, p in zip(lc["sell_layers"], lc["sell_pct"])]
    return {"anchor": anchor, "step": step, "distance": dist, "layer": ov["layer"],
            "anchor_ma": ov["anchor_ma"], "buys": buys, "sells": sells}


def _link(res: dict) -> str | None:
    base = os.environ.get("PAGES_URL", "").rstrip("/")
    if not base:
        return None
    return f"{base}/#{re.sub(r'[^A-Za-z0-9_.-]', '_', res['ticker'] + '_' + res['timeframe'])}"


def _message(res: dict, p: dict, side: str, idx: int, first: int | None = None) -> str:
    """Message for reaching tier idx; if first < idx, the earlier tiers were passed in the same move."""
    tiers = p["buys"] if side == "buy" else p["sells"]
    t = tiers[idx]
    first = idx if first is None else first
    nxt = tiers[idx + 1] if idx + 1 < len(tiers) else None
    above_below = "below" if side == "buy" else "above"
    span = f"{idx + 1}" if first == idx else f"{first + 1}–{idx + 1}"
    head = (f"🪜 LAYER IN {span} of {len(tiers)} — {res['ticker']} ({res['timeframe']})" if side == "buy"
            else f"🪜 LAYER OUT {span} of {len(tiers)} — {res['ticker']} ({res['timeframe']})")
    pct = sum(x["pct"] for x in tiers[first: idx + 1])
    passed = ", ".join(f"L{x['layer']:+d} ({_fmt(x['price'])})" for x in tiers[first: idx + 1])
    plan_line = (f"Plan: add {pct}% of your planned position here." if side == "buy"
                 else f"Plan: trim {pct}% of your position here.")
    if first != idx:
        plan_line = f"Price moved through {passed} since the last scan. " + plan_line
    lines = [
        head,
        f"Price {_fmt(res['price'])} reached L{t['layer']:+d} ({_fmt(t['price'])}), "
        f"{abs(p['distance']):.1f} ATR {above_below} the {p['anchor_ma']}-bar average ({_fmt(p['anchor'])}).",
        plan_line,
        (f"Next: L{nxt['layer']:+d} at {_fmt(nxt['price'])}." if nxt else
         ("That's the last layer in the plan." if side == "buy" else "That's the last layer out in the plan.")),
        f"Overall signal: {res['action']} (score {res['score']}/100).",
    ]
    ov = res["overlays"]
    falling = ov["ema_fast"].iat[-1] < ov["ema_slow"].iat[-1] and res["price"] < (ov["ma_long"].iat[-1] or 0)
    if side == "buy" and falling:
        lines.append("Note: the trend is still down (below the 200-bar average, short EMA under long EMA), "
                     "so the price may keep falling to lower layers.")
    if side == "buy" and res.get("asset") == "crypto":
        if res.get("rank", 0) <= -2:
            lines.append(f"⚠️ Conflict: the crypto trend signal is {res['action']}. In our backtests, buying crypto "
                         "dips against the trend did worse than waiting for the trend to turn.")
        else:
            lines.append("Backtest note: on crypto, buying dips has done worse than following the trend.")
    if side == "sell" and res.get("asset") == "crypto" and res.get("rank", 0) >= 2:
        lines.append(f"⚠️ Conflict: the crypto trend signal is still {res['action']}. In our backtests, trimming "
                     "crypto while the trend was up gave up most of the gains.")
    if (link := _link(res)):
        lines.append(f"📈 Chart: {link}")
    lines += ["Change alerts: /settings", "", f"⚠️ {DISCLAIMER}"]
    return "\n".join(lines)


def check_alerts(res: dict, cfg: dict) -> list[str]:
    """Messages for ladder layers newly reached since the last scan (and update the saved state).

    The first scan of a ticker only records where it is, so you don't get alerts for layers that
    were reached before you started.
    """
    lc = cfg["ladder"]
    if res["timeframe"] not in lc["timeframes"]:
        return []
    p = plan(res, cfg)
    d = p["distance"]
    b_now = sum(t["reached"] for t in p["buys"])
    s_now = sum(t["reached"] for t in p["sells"])
    prev = storage.get_ladder(res["ticker"], res["timeframe"])
    # A tier stays "used" until price crosses back over the anchor, then the ladder resets.
    b_keep = max(prev[0] if prev else 0, b_now) if d < 0 else 0
    s_keep = max(prev[1] if prev else 0, s_now) if d > 0 else 0
    storage.set_ladder(res["ticker"], res["timeframe"], b_keep, s_keep)
    if prev is None or not lc.get("enabled", True):
        return []
    b_prev = prev[0] if d < 0 else 0
    s_prev = prev[1] if d > 0 else 0
    msgs = []
    if b_now > b_prev:
        msgs.append(_message(res, p, "buy", b_now - 1, b_prev))
    if s_now > s_prev:
        msgs.append(_message(res, p, "sell", s_now - 1, s_prev))
    return msgs
