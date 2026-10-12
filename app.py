"""
Signal Desk — personal buy/sell signal dashboard.
Run:  streamlit run app.py
"""
from __future__ import annotations

import copy
import os

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Signal Desk", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")

# Streamlit Community Cloud: secrets entered in the app settings become environment variables.
for _k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SMTP_PASSWORD"):
    try:
        if _k in st.secrets:
            os.environ.setdefault(_k, str(st.secrets[_k]))
    except Exception:  # no secrets file locally — fine
        pass

import storage
from config import load_config, save_config
from data import is_crypto
from notify import DISCLAIMER, ICONS, send_all
from scanner import run_scan
from signals import ACTION_RANK

storage.init()

if "cfg" not in st.session_state:
    st.session_state.cfg = load_config()
cfg = copy.deepcopy(st.session_state.cfg)

# Tighter spacing so it reads well on a phone.
st.markdown("""
<style>
.block-container {padding-top: 2.2rem; padding-left: 0.8rem; padding-right: 0.8rem;}
div[data-testid="stMetricValue"] {font-size: 1.25rem;}
.sig-reason {font-size: 0.88rem; line-height: 1.35; margin: 0.1rem 0;}
</style>
""", unsafe_allow_html=True)

st.title("📈 Signal Desk")
st.caption(f"⚠️ {DISCLAIMER}")


# --------------------------------------------------------------------------- background scheduler
@st.cache_resource
def get_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler

    s = BackgroundScheduler(daemon=True)
    s.start()
    return s


def parse_list(text: str) -> list[str]:
    return [t.strip().upper() for t in text.replace("\n", ",").split(",") if t.strip()]


# --------------------------------------------------------------------------- sidebar: settings
with st.sidebar:
    st.header("Watchlist")
    cfg["watchlist"]["stocks"] = parse_list(st.text_area("Stocks / ETFs", ", ".join(cfg["watchlist"]["stocks"])))
    cfg["watchlist"]["crypto"] = parse_list(st.text_area("Crypto (yfinance-style, e.g. BTC-USD)",
                                                         ", ".join(cfg["watchlist"]["crypto"])))
    cfg["timeframes"] = st.multiselect("Timeframes", ["1d", "4h", "1h", "1wk"], cfg["timeframes"]) or ["1d"]

    with st.expander("Model settings"):
        m = cfg["models"]
        st.caption("Trend")
        m["trend"]["fast_ema"] = st.number_input("Fast EMA", 5, 100, m["trend"]["fast_ema"])
        m["trend"]["slow_ema"] = st.number_input("Slow EMA", 10, 200, m["trend"]["slow_ema"])
        m["trend"]["long_ma"] = st.number_input("Long MA", 50, 300, m["trend"]["long_ma"])
        st.caption("Mean reversion")
        m["mean_reversion"]["lookback"] = st.number_input("Lookback", 10, 100, m["mean_reversion"]["lookback"])
        m["mean_reversion"]["sd_threshold"] = st.slider("SD threshold", 1.0, 3.5,
                                                        float(m["mean_reversion"]["sd_threshold"]), 0.1)
        st.caption("Confluence")
        m["confluence"]["rsi_low"] = st.slider("RSI oversold", 10, 45, m["confluence"]["rsi_low"])
        m["confluence"]["rsi_high"] = st.slider("RSI overbought", 55, 90, m["confluence"]["rsi_high"])
        st.caption("ATR layers")
        m["atr_layers"]["anchor_ma"] = st.number_input("Anchor MA", 10, 200, m["atr_layers"]["anchor_ma"])
        m["atr_layers"]["layer_step"] = st.slider("ATRs per layer", 0.5, 3.0,
                                                  float(m["atr_layers"]["layer_step"]), 0.25)
        m["atr_layers"]["zone_layer"] = st.slider("Buy/reduce zone starts at layer", 1, 4,
                                                  m["atr_layers"]["zone_layer"])
        st.caption("Momentum")
        m["momentum"]["roc_period"] = st.number_input("ROC period", 5, 100, m["momentum"]["roc_period"])

    with st.expander("Ensemble rule"):
        e = cfg["ensemble"]
        e["min_agree"] = st.slider("Models that must agree (of 5)", 2, 5, e["min_agree"])
        e["strong_score"] = st.slider("'Strong' score threshold", 60, 95, e["strong_score"])
        e["watch_score"] = st.slider("'Watch' score threshold", 51, 75, e["watch_score"])
        e["knife_guard"] = st.checkbox("Falling-knife / strong-uptrend guard", e["knife_guard"])

    with st.expander("Notifications"):
        n = cfg["notifications"]
        n["min_action"] = st.selectbox("Alert at or above", ["Watch", "Buy", "Strong Buy"],
                                       ["Watch", "Buy", "Strong Buy"].index(n["min_action"]))
        n["telegram"]["enabled"] = st.checkbox("Telegram", n["telegram"]["enabled"])
        n["telegram"]["bot_token"] = st.text_input("Bot token", n["telegram"]["bot_token"], type="password")
        n["telegram"]["chat_id"] = st.text_input("Chat ID", n["telegram"]["chat_id"])
        n["ntfy"]["enabled"] = st.checkbox("ntfy.sh", n["ntfy"]["enabled"])
        n["ntfy"]["topic"] = st.text_input("ntfy topic", n["ntfy"]["topic"])
        if st.button("Send test notification"):
            ok = send_all(f"✅ Signal Desk test message.\n\n⚠️ {DISCLAIMER}", cfg, "Signal Desk test")
            st.success(f"Sent via: {', '.join(ok)}") if ok else st.error("Nothing sent — check settings/logs")

    with st.expander("Scheduler"):
        s = cfg["scheduler"]
        s["stock_interval_min"] = st.number_input("Stock scan every (min)", 15, 240, s["stock_interval_min"])
        s["crypto_interval_min"] = st.number_input("Crypto scan every (min)", 15, 240, s["crypto_interval_min"])
        s["market_hours_only"] = st.checkbox("Stocks only during US market hours", s["market_hours_only"])
        sched = get_scheduler()
        running = bool(sched.get_jobs())
        st.write("Status:", "🟢 running" if running else "⚪ stopped")
        c1, c2 = st.columns(2)
        if c1.button("Start", disabled=running):
            from runner import add_jobs

            save_config(cfg)  # jobs read config.yaml
            add_jobs(sched, cfg)
            st.rerun()
        if c2.button("Stop", disabled=not running):
            sched.remove_all_jobs()
            st.rerun()
        st.caption("Runs only while this Streamlit server is up. In the cloud, the GitHub Actions "
                   "workflow does the scheduled scans instead.")

    st.session_state.cfg = cfg
    if st.button("💾 Save settings", type="primary", use_container_width=True):
        save_config(cfg)
        st.success("Saved to config.yaml")
    st.caption("Sidebar changes apply to scans right away. On Streamlit Cloud, saved settings reset when the "
               "app restarts — for permanent changes, edit config.yaml in your GitHub repo.")


# --------------------------------------------------------------------------- helpers
def vote_cell(r) -> str:
    return {1: "▲", -1: "▼", 0: "·"}[r.vote] + (f" {r.strength:.1f}" if r.vote else "")


def results_table(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        mo = r["models"]
        rows.append({
            "Ticker": r["ticker"], "TF": r["timeframe"], "Price": r["price"],
            "Δ bar %": round(r["change_pct"], 2),
            "Action": f"{ICONS.get(r['action'], '')} {r['action']}", "Score": r["score"],
            "Trend": vote_cell(mo["trend"]), "MeanRev": vote_cell(mo["mean_reversion"]),
            "Confl.": vote_cell(mo["confluence"]), "Layer": f"{mo['atr_layers'].extra['layer']:+d}",
            "Mom.": vote_cell(mo["momentum"]), "_rank": abs(r["rank"]),
        })
    df = pd.DataFrame(rows)
    return df.sort_values(["_rank", "Score"], ascending=False).drop(columns="_rank") if not df.empty else df


def signal_card(r: dict) -> None:
    """One signal as a compact card — readable on a phone without sideways scrolling."""
    mo = r["models"]
    with st.container(border=True):
        st.markdown(f"**{ICONS.get(r['action'], '')} {r['action']} · {r['ticker']}** "
                    f"<span style='opacity:.6'>{r['timeframe']}</span>", unsafe_allow_html=True)
        a, b = st.columns(2)
        a.metric("Price", f"{r['price']:,.4g}", f"{r['change_pct']:+.2f}%")
        b.metric("Score", f"{r['score']}/100", f"{r['bull']}▲ {r['bear']}▼", delta_color="off")
        votes = " ".join(f"{m.name.split()[0]} {vote_cell(m).split()[0]}" for m in mo.values())
        st.caption(votes + f" · layer {mo['atr_layers'].extra['layer']:+d}")
        for reason in r["reasons"] + r["notes"]:
            st.markdown(f"<p class='sig-reason'>• {reason}</p>", unsafe_allow_html=True)


def price_chart(r: dict, cfg: dict):
    import plotly.graph_objects as go

    df, mo = r["_df"], r["models"]
    n = 180
    d = df.tail(n)
    fig = go.Figure(go.Candlestick(x=d.index, open=d.open, high=d.high, low=d.low, close=d.close, name="Price"))
    mr = mo["mean_reversion"].extra
    for key, name, dash in [("bb_upper", "Upper band", "dot"), ("bb_mid", "Mean", "dash"), ("bb_lower", "Lower band", "dot")]:
        fig.add_scatter(x=d.index, y=mr[key].tail(n), name=name, line=dict(width=1, dash=dash))
    al = mo["atr_layers"].extra
    fig.add_scatter(x=d.index, y=al["anchor"].tail(n), name="Layer anchor", line=dict(width=1.5))
    for k, lvl in al["levels"].items():
        if k:
            fig.add_hline(y=lvl, line=dict(width=0.6, color="green" if k < 0 else "red"),
                          annotation_text=f"L{k:+d}", annotation_position="right")
    fig.update_layout(height=440, xaxis_rangeslider_visible=False, margin=dict(l=4, r=34, t=30, b=4),
                      legend=dict(orientation="h", y=1.1, font=dict(size=10)), dragmode="pan")
    if not is_crypto(r["ticker"], cfg):
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------- tabs
tab_dash, tab_detail, tab_hist, tab_about = st.tabs(["Signals", "Chart", "History", "About"])

with tab_dash:
    scope = st.segmented_control("Scan", ["Everything", "Stocks only", "Crypto only"],
                                 default="Everything", label_visibility="collapsed") or "Everything"
    send = st.toggle("Send alerts from this scan", False,
                     help="Scheduled scans already alert you. Off = just look.")
    if st.button("🔍 Run scan now", type="primary", use_container_width=True):
        tickers = {"Everything": None, "Stocks only": cfg["watchlist"]["stocks"],
                   "Crypto only": cfg["watchlist"]["crypto"]}[scope]
        bar = st.progress(0.0, "Starting…")
        results, errors = run_scan(cfg, tickers=tickers, notify=send,
                                   progress=lambda f, label: bar.progress(f, f"Scanning {label}"))
        bar.empty()
        st.session_state.results, st.session_state.errors = results, errors

    results = st.session_state.get("results", [])
    if results:
        m1, m2, m3 = st.columns(3)
        m1.metric("Scanned", len(results))
        m2.metric("Buy-side", sum(r["rank"] >= 2 for r in results))
        m3.metric("Sell-side", sum(r["rank"] <= -2 for r in results))

        ranked = sorted(results, key=lambda r: (-abs(r["rank"]), -abs(r["score"] - 50)))
        active = [r for r in ranked if abs(r["rank"]) >= 1]
        st.subheader("Signals" if active else "No active signals")
        for r in active:
            signal_card(r)
        if not active:
            st.caption("Everything is on Hold right now.")

        with st.expander(f"All {len(results)} results (table)"):
            st.dataframe(
                results_table(results), hide_index=True, use_container_width=True,
                column_config={
                    "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
                    "Price": st.column_config.NumberColumn(format="%.4g"),
                },
            )
            st.caption("▲/▼ = model vote with strength 0–1 · Layer = ATR layer vs anchor MA · "
                       "Score 50 is neutral, 100 max bullish, 0 max bearish")
        if st.session_state.get("errors"):
            with st.expander(f"⚠️ {len(st.session_state.errors)} tickers had data problems"):
                st.write("\n".join(st.session_state.errors))
    else:
        states = storage.latest_states()
        if states.empty:
            st.info("No scans yet. Tap **Run scan now**.")
        else:
            st.caption("Latest state from scheduled scans (tap Run scan now for fresh reasons and charts):")
            for _, s in states[states["rank"].abs() >= 1].iterrows():
                st.markdown(f"{ICONS.get(s['action'], '')} **{s['action']} · {s['ticker']}** {s['timeframe']} — "
                            f"{s['price']:,.4g} · score {s['score']} · <span style='opacity:.6'>{s['ts']}</span>",
                            unsafe_allow_html=True)
            with st.expander("All tickers"):
                st.dataframe(states[["ticker", "timeframe", "action", "score", "price", "ts"]],
                             hide_index=True, use_container_width=True)

with tab_detail:
    results = st.session_state.get("results", [])
    if not results:
        st.info("Run a scan first.")
    else:
        labels = [f"{r['ticker']} · {r['timeframe']}" for r in results]
        r = results[labels.index(st.selectbox("Ticker", labels))]
        a, b = st.columns(2)
        a.metric("Price", f"{r['price']:,.4g}", f"{r['change_pct']:+.2f}%")
        b.metric(r["action"], f"{r['score']}/100", f"{r['bull']}▲ {r['bear']}▼", delta_color="off")
        price_chart(r, cfg)
        st.subheader("Model breakdown")
        st.dataframe(pd.DataFrame([{"Model": mo.name, "Vote": vote_cell(mo), "Reading": mo.reason}
                                   for mo in r["models"].values()]),
                     hide_index=True, use_container_width=True)
        if r["notes"]:
            st.info(" · ".join(r["notes"]))
        st.caption(f"Latest bar: {r['bar_time']} · scanned {r['ts']}")

with tab_hist:
    hist = storage.history()
    if hist.empty:
        st.info("No signals logged yet. Every change of action per ticker/timeframe is recorded here.")
    else:
        only = st.toggle("Only Buy/Sell (hide Watch/Hold)", True)
        if only:
            hist = hist[hist["rank"].abs() >= 2]
        st.dataframe(hist[["ts", "ticker", "timeframe", "action", "score", "signal_price", "latest_price",
                           "signal_result_%", "reasons"]],
                     hide_index=True, use_container_width=True,
                     column_config={"signal_result_%": st.column_config.NumberColumn("Result %", format="%+.2f"),
                                    "signal_price": st.column_config.NumberColumn("At signal", format="%.4g"),
                                    "latest_price": st.column_config.NumberColumn("Latest", format="%.4g")})
        scored = hist.dropna(subset=["signal_result_%"])
        scored = scored[scored["rank"] != 0]
        if len(scored):
            st.caption(f"Rough performance note: {len(scored)} directional signals, "
                       f"{(scored['signal_result_%'] > 0).mean():.0%} currently moving the signalled way, "
                       f"average {scored['signal_result_%'].mean():+.2f}% (vs latest scanned price — not a backtest).")

with tab_about:
    st.markdown(f"""
### The five models
Each model votes **▲ bullish / ▼ bearish / · neutral** with a strength from 0 to 1.

1. **Trend** — EMA fast/slow, price vs the long MA (200), and Supertrend. Votes only when all agree.
2. **Mean reversion** — z-score of price vs its rolling mean (same thing as Bollinger Band position). ≤ −2σ oversold, ≥ +2σ overbought.
3. **Confluence** — five sub-votes: RSI, MACD histogram, Stochastic, volume spike, and price outside ATR (Keltner) bands. Averaged into a 0–100 score.
4. **ATR layers** — distance from an anchor MA measured in ATR steps. Layer −2 or lower is the *buy zone* (layer in); +2 or higher is the *take-profit / reduce zone* (layer out).
5. **Momentum** — higher highs/lows or lower highs/lows plus rate of change, and swing breakouts. Stops mean reversion from fighting a strong trend.

### Ensemble decision
- **Score** = 50 + 50 × average of (vote × strength) across the 5 models.
- **Buy / Sell** when at least **{cfg['ensemble']['min_agree']}** models agree. **Strong** when the score also passes **{cfg['ensemble']['strong_score']}** (or below {100 - cfg['ensemble']['strong_score']} for sells).
- **Watch** when one model short of agreement, or the score passes {cfg['ensemble']['watch_score']}.
- **Falling-knife guard**: an oversold Buy is downgraded to Watch while trend *and* momentum are both still down (and the mirror for Sells in strong uptrends).

### Alerts
You're alerted on a **new** signal at or above your threshold, a **direction flip**, or a **strengthening** (Buy → Strong Buy). Repeating the same signal scan after scan doesn't re-alert.

*These are open, transparent approximations of confluence / mean-reversion / trend / ATR-layer ideas — not a copy of any proprietary indicator.*

**{DISCLAIMER}**
""")
