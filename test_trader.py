"""
Checks for the live trader. No network needed: uses the stored bars in backtest/bars.csv.gz and a fake Alpaca.

    python -m pytest test_trader.py -q      (or: python test_trader.py)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import active_research as A
import portfolio_research as P
import strategy as ST
import trader as T

STOCKS, COINS = P.load()


# ---------------------------------------------------------------------------- live rules == backtest
def test_votes_and_pyramid_match_backtest():
    bt_votes = A.crypto_votes(COINS)
    live_votes, _ = ST.trend_votes(COINS)
    pd.testing.assert_frame_equal(bt_votes[ST.COINS], live_votes[ST.COINS], check_names=False)
    on = bt_votes > 0.5
    N = COINS.diff().abs().rolling(20, min_periods=20).mean()
    for t in ST.COINS:
        bt = A.ladder(COINS[t].values, on[t].values, N[t].values, "pyramid")
        live = ST.pyramid(COINS[t].values, on[t].fillna(False).values, ST.atr_close(COINS)[t].values) / 3
        assert np.allclose(bt, live), t


def test_500_day_window_gives_the_same_answer_as_full_history():
    """The live feed returns ~500 daily bars. Today's layers must match what 10 years of history says."""
    full = {}
    on = A.crypto_votes(COINS) > 0.5
    N = ST.atr_close(COINS)
    for t in ST.COINS:
        full[t] = pd.Series(ST.pyramid(COINS[t].values, on[t].fillna(False).values, N[t].values), index=COINS.index)
    ends = COINS.index[-365:][::5]                      # every 5th day of the last year
    mismatches, checked = [], 0
    for end in ends:
        window = COINS.loc[:end].iloc[-500:]
        got = ST.crypto_targets(window)
        for t in ST.COINS:
            if not got[t]["enough_data"]:
                continue
            checked += 1
            if got[t]["layers"] != full[t].loc[end]:
                mismatches.append((end.date(), t, got[t]["layers"], int(full[t].loc[end])))
    assert checked > 300
    assert len(mismatches) / checked < 0.02, mismatches[:10]


# ---------------------------------------------------------------------------- planning
def tg(layers, on=True, close=100.0):
    return {"layers": layers, "on": on, "score": 0.75, "votes": {}, "close": close, "atr": 2.0,
            "enough_data": True, "bars": 500}


def targets(**layers):
    return {t: tg(layers.get(t.split("-")[0], 0), layers.get(t.split("-")[0], 0) > 0) for t in ST.COINS}


def test_fresh_account_builds_spy_and_first_layers():
    orders = T.plan(10_000, {}, targets(BTC=1, ETH=3), True, set(), 0.0)
    buys = {o["symbol"]: o["amount"] for o in orders if o.get("side") == "buy"}
    assert buys == {"BTC/USD": round(10_000 * 0.04 / 3, 2), "ETH/USD": 400.0, "SPY": 8000.0}
    assert not [o for o in orders if o.get("side") == "sell"]


def test_on_target_does_nothing():
    pos = {"SPY": {"qty": 10, "market_value": 8100, "price": 810},
           "BTCUSD": {"qty": 0.002, "market_value": 270, "price": 135000}}
    orders = T.plan(10_000, pos, targets(BTC=2), True, set(), 0.0)
    assert orders == []


def test_trend_off_sells_everything_and_loss_guard_blocks_buys_only():
    pos = {"SOLUSD": {"qty": 2, "market_value": 400, "price": 200}}
    orders = T.plan(10_000, pos, targets(ETH=1), True, set(), -4.0)
    assert {"symbol": "SOL/USD", "side": "sell", "kind": "close"}.items() <= orders[0].items()
    assert not [o for o in orders if o.get("side") == "buy"]
    assert any(o.get("note", {}).get("symbol") == "ETH/USD" for o in orders)


def test_layer_removed_sells_part():
    pos = {"BTCUSD": {"qty": 0.003, "market_value": 400, "price": 400 / 0.003}}
    orders = T.plan(10_000, pos, targets(BTC=1), False, set(), 0.0)
    (o,) = orders
    assert o["side"] == "sell" and o["kind"] == "qty"
    assert abs(o["amount"] * pos["BTCUSD"]["price"] - (400 - 400 / 3)) < 0.01


def test_outside_stock_window_spy_untouched_and_open_orders_skipped():
    orders = T.plan(10_000, {}, targets(BTC=3), False, {"BTC/USD"}, 0.0)
    assert [o["note"]["symbol"] for o in orders] == ["BTC/USD"]


def test_small_drift_ignored():
    pos = {"SPY": {"qty": 10, "market_value": 7700, "price": 770}}      # 3% under target: inside the 5% band
    assert T.plan(10_000, pos, targets(), True, set(), 0.0) == []


# ---------------------------------------------------------------------------- end to end with a fake broker
class FakeAlpaca:
    live = False

    def __init__(self, cash=10_000.0, prices=None, is_open=True):
        self.cash, self.prices, self.is_open = cash, prices, is_open
        self.pos: dict[str, float] = {}
        self.orders: list[dict] = []
        self.ids: set[str] = set()

    def value(self):
        return self.cash + sum(q * self.prices[s] for s, q in self.pos.items())

    def get(self, path, **kw):
        if path == "/v2/clock":
            ts = "2026-10-13T10:00:00-04:00" if self.is_open else "2026-10-13T20:35:00-04:00"
            return {"timestamp": ts, "is_open": self.is_open, "next_open": "2026-10-14T09:30:00-04:00"}
        if path == "/v2/account":
            v = self.value()
            return {"equity": str(v), "last_equity": str(v), "cash": str(self.cash),
                    "non_marginable_buying_power": str(self.cash)}
        if path == "/v2/positions":
            return [{"symbol": s, "qty": str(q), "market_value": str(q * self.prices[s]),
                     "current_price": str(self.prices[s]), "asset_class": "us_equity" if s == "SPY" else "crypto"}
                    for s, q in self.pos.items() if q > 0]
        if path == "/v2/orders":
            return []
        raise AssertionError(path)

    def req(self, method, path, json=None, **kw):
        if method == "DELETE":
            s = path.rsplit("/", 1)[1]
            self.cash += self.pos.pop(s) * self.prices[s]
            return {}
        assert json["client_order_id"] not in self.ids, "duplicate order id"
        self.ids.add(json["client_order_id"])
        s = json["symbol"].replace("/", "")
        if json["side"] == "buy":
            amt = float(json["notional"])
            assert amt <= self.cash + 1e-6, "spent money it didn't have"
            self.pos[s] = self.pos.get(s, 0) + amt / self.prices[s]
            self.cash -= amt
        else:
            q = float(json["qty"])
            self.pos[s] -= q
            self.cash += q * self.prices[s]
        self.orders.append(json)
        return {}


def fake_fetch(ticker, tf, cfg):
    c = COINS[ticker].dropna() if ticker in COINS else STOCKS[ticker].dropna()
    c = c.loc[:"2026-10-12"].iloc[-500:]
    df = pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": 1.0})
    df.index = df.index.tz_localize("UTC")
    return df


def test_two_runs_in_a_row_do_not_double_buy(monkeypatch):
    monkeypatch.setattr(T, "fetch_ohlcv", fake_fetch)
    monkeypatch.setattr(T, "telegram", lambda text: None)
    prices = {"SPY": float(STOCKS["SPY"].dropna().iat[-1]),
              **{T.position_key(T.alpaca_symbol(t)): float(COINS[t].dropna().iat[-1]) for t in ST.COINS}}
    api = FakeAlpaca(prices=prices)
    T.run(api, dry=False)
    first = list(api.orders)
    assert any(o["symbol"] == "SPY" for o in first)
    assert api.cash >= 0
    spy_share = api.pos["SPY"] * prices["SPY"] / api.value()
    assert abs(spy_share - 0.80) < 0.01
    T.run(api, dry=False)                               # same day, same data: nothing more to do
    assert api.orders == first


def test_dry_run_places_nothing(monkeypatch):
    monkeypatch.setattr(T, "fetch_ohlcv", fake_fetch)
    sent = []
    monkeypatch.setattr(T, "telegram", sent.append)
    prices = {"SPY": 600.0, **{T.position_key(T.alpaca_symbol(t)): 1.0 for t in ST.COINS}}
    api = FakeAlpaca(prices=prices, is_open=False)
    T.run(api, dry=True)
    assert api.orders == [] and api.pos == {}
    assert "Dry run" in sent[0] and "SPY is only traded" in sent[0]


def test_public_logs_hide_account_numbers():
    msg = ("🟢 Buy SPY $8,000.00 (core)\n🔴 Sell BTC/USD 0.00123 units (trend on, 1/3 layers)\n"
           "🔴 Sell ETH/USD 1.2e-05 units (x)\nAccount $10,234.56 (-1.4% today)")
    out = T.redact(msg)
    assert "8,000" not in out and "10,234" not in out and "0.00123" not in out and "1.2e-05" not in out
    assert "1.4%" not in out and "SPY" in out and "1/3 layers" in out


if __name__ == "__main__":
    import sys

    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
