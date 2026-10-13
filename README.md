# Signal Desk

A private, local dashboard that scans a watchlist of stocks and crypto, runs five independent signal
models, combines them with a confluence vote, and pings you on Telegram (or ntfy / email) only when
enough evidence lines up.

> **Personal research tool only. Not financial advice. Signals can be wrong. Do your own research.**

---

## Architecture

```
                 ┌──────────────┐
 yfinance ──────▶│              │      ┌─────────────┐     ┌────────────┐
 ccxt (Kraken) ─▶│   data.py    │─df──▶│ signals.py  │────▶│ scanner.py │──▶ notify.py ──▶ Telegram / ntfy / email
                 │ fetch+retry  │      │ 5 models +  │     │ dedupe +   │
                 └──────────────┘      │ ensemble    │     │ persist    │──▶ storage.py (SQLite: signals.db)
                                       └─────────────┘     └────────────┘
                                                                 ▲
                            app.py (Streamlit dashboard) ────────┤
                            runner.py (headless scheduler) ──────┘
```

| File | Job |
|---|---|
| `app.py` | Streamlit dashboard: settings, scan button, results table, chart, history |
| `signals.py` | Indicators (pure pandas), the five models, the ensemble rule |
| `data.py` | Free data with retries and fallback (crypto: ccxt → yfinance) |
| `scanner.py` | Runs a scan, decides whether to alert, saves history |
| `notify.py` | Telegram, ntfy.sh, email, console |
| `storage.py` | SQLite signal log and latest state per ticker/timeframe |
| `runner.py` | Always-on scheduler without the UI (`python runner.py`) |
| `config.py` | Defaults + loading/saving `config.yaml` |
| `.github/workflows/scan.yml` | Scheduled cloud scans + Telegram alerts via GitHub Actions |
| `bot.py`, `settings.py`, `.github/workflows/bot.yml` | Telegram `/settings` buttons: timeframes on/off, alert level, pause |

Indicators are written directly in pandas rather than pandas-ta: pandas-ta has had repeated
install problems with newer NumPy, and plain code is easier to read and tweak.

---

## Run it from your phone (free, no laptop needed)

Two free services do the work, so nothing has to be running at home:

- **GitHub Actions** runs the scanner on a schedule (stocks every 30 min in market hours, crypto hourly)
  and sends **Telegram alerts** to your phone. Signal history is saved back into the repo.
- **Streamlit Community Cloud** hosts the dashboard as a web page you open on your phone
  (add it to your home screen and it works like an app).

Each step works in a phone browser, though steps 2–3 are quicker on a computer.

**1. Telegram bot (5 min, on the phone)**
In Telegram, message **@BotFather** → `/newbot` → copy the token. Open your new bot and send it "hi". Then in
your browser go to `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the number after `"chat":{"id":`.

**2. Put the code on GitHub (10 min)**
1. Create a free account at github.com → **New repository** → name it `signal-desk`.
   - **Public** gives unlimited free Actions minutes. Your code, watchlist and signal history are visible,
     but your Telegram token stays secret. You can still make the dashboard private in step 4.
   - **Private** works too. Free private repos get 2,000 Actions minutes a month, and this uses roughly
     1,400. If GitHub emails you about the limit, change the crypto line in `scan.yml` to `"15 */2 * * *"`
     to scan every 2 hours.
2. **Add file → Upload files**, and upload everything in this folder *except* the `.github` folder.
3. Hidden folders often don't upload, so create the workflow by hand: **Add file → Create new file**, type
   the name `.github/workflows/scan.yml`, paste in the contents of that file, and **Commit**.
4. **Settings → Secrets and variables → Actions → New repository secret**: add `TELEGRAM_BOT_TOKEN` and
   `TELEGRAM_CHAT_ID`. (Optionally add `NTFY_TOPIC` for ntfy alerts.)
5. **Actions** tab → enable workflows if asked → **Signal scan → Run workflow**. In about 2 minutes it
   goes green. The first run only records a baseline, so you'll get alerts once signals *change* after that.

**3. Dashboard on your phone (5 min)**
1. Go to **share.streamlit.io** → sign in with GitHub → **Create app** → pick the `signal-desk` repo,
   branch `main`, file `app.py`.
2. **Advanced settings**: Python 3.12, and paste into Secrets:
   ```toml
   TELEGRAM_BOT_TOKEN = "123456:ABC..."
   TELEGRAM_CHAT_ID = "123456789"
   ```
3. **Deploy**. You get a URL like `https://signal-desk-yourname.streamlit.app`.
4. App **Settings → Sharing**: make it **private** (only you), so strangers can't run scans from it.
   Streamlit allows one private app on the free plan.
5. Open the URL on your phone → Share → **Add to Home Screen**.

**Turning things on and off from your phone:** in your Telegram bot chat, send `/settings`. You get buttons
to switch **Daily / 4-hour / Hourly** on or off, change the **alert level** (Watch → Buy → Strong Buy), and
**pause** all alerts. Send `/signals` to see the current Buy and Sell signals. A small GitHub job checks
the chat every 5 minutes, so a tap takes effect within about 5–15 minutes, and the bot confirms it. Only your
own chat ID is obeyed. The switches are saved in `settings.json` in the repo.

**Charts on your phone:** every scan publishes a small website at
`https://<your-github-username>.github.io/signal-desk`. It lists every ticker with its current signal and score.
Tap a ticker for a candlestick chart with the Bollinger bands, ATR layers, EMAs, volume and past signal arrows,
plus each model's reading. Switch Daily / 4H / 1H at the top. In Safari, use Share → **Add to Home Screen**
to make it open like an app. Telegram alerts include a direct link to that ticker's chart, and `/chart` in the
bot chat sends the link. One-time setup: repo **Settings → Pages → Source: GitHub Actions**. The site is
public, as the repo is, but only shows prices and signals.

**Changing things later:** to change the watchlist or thresholds for good, edit `config.yaml` in the repo
(the GitHub app on your phone can do it). The dashboard sidebar lets you experiment, but changes made there
reset when the cloud app restarts. The dashboard sleeps after a few days unused, so tap "wake up" if you see
that screen. Alerts keep coming either way.

**Caveat:** Yahoo sometimes rate-limits requests from cloud servers. When that happens, those tickers show
as failed for that run and get picked up on the next one. Crypto data comes from Kraken and isn't affected.

---

## Setup on your own computer (about 10 minutes)

**1. Install Python 3.11+**, then in a terminal:

```bash
cd signal-desk
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp config.example.yaml config.yaml # optional; you can do everything from the dashboard
```

**2. Create a Telegram bot**

1. In Telegram, message **@BotFather** → send `/newbot` → pick a name and username.
2. Copy the token it gives you (looks like `123456:ABC-...`).
3. Open your new bot and send it any message (e.g. "hi"). This is required before it can message you.
4. In a browser open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and find
   `"chat":{"id":123456789` — that number is your **chat ID**.
5. Put both in the dashboard sidebar (Notifications), tick Telegram, press **Send test notification**,
   then **Save settings**. Or keep them out of files with environment variables:

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-..."
export TELEGRAM_CHAT_ID="123456789"
```

*No Telegram?* Install the ntfy app on your phone, subscribe to an unguessable topic name, and enable ntfy
in settings with the same topic.

**3. Run the dashboard**

```bash
streamlit run app.py
```

It opens at http://localhost:8501. Press **Run scan now**. A full scan of 18 tickers × 2 timeframes takes
roughly 1–2 minutes on free APIs.

**4. Keep it running in the background (optional)**

The dashboard's Scheduler panel works only while the Streamlit window is running. For always-on alerts use
the headless runner, which re-reads `config.yaml` every cycle:

```bash
python runner.py            # stocks every 30 min in US market hours, crypto every 60 min, 24/7
python runner.py --once     # one scan, then exit
```

- **macOS / Linux, simplest:** `nohup python runner.py > runner.log 2>&1 &`
- **cron instead:** `*/30 * * * * cd /path/to/signal-desk && .venv/bin/python runner.py --once >> runner.log 2>&1`
- **Windows:** Task Scheduler → run `.venv\Scripts\python.exe runner.py --once` every 30 minutes.
- **Mobile access:** run Streamlit on a home machine and reach it via Tailscale; don't expose it to the open internet.

---

## The five models

Every model votes **bullish (+1), bearish (−1) or neutral (0)** with a strength from 0 to 1, plus a one-line reason.

1. **Trend** — EMA 21 vs 55, price vs 200-MA, and Supertrend (10, 3). All three agreeing gives a strong vote
   (bigger EMA gap = stronger); a 2-of-3 majority gives a weaker "leaning" vote.
2. **Mean reversion** — z-score of price against its 20-bar mean (identical to Bollinger %B). At or below −2σ
   = oversold (bullish), at or above +2σ = overbought (bearish). Lookback and σ are configurable.
3. **Confluence** — five sub-votes averaged into 0–100: RSI (<35 / >65), MACD histogram direction/cross,
   Stochastic turning in an extreme, volume spike (direction of the bar), and price outside 2-ATR Keltner bands.
4. **ATR layers (layer-in / layer-out)** — distance from the 50-MA measured in 1-ATR steps, shown as a layer
   number (−4 … +4). Layer −2 or lower = buy zone (scale in); +2 or higher = take-profit / reduce zone.
   The layers are drawn on the chart.
5. **Momentum / breakout** — higher highs + higher lows (or lower/lower) over the last 10 bars vs the 10 before,
   rate of change, and swing breakouts/breakdowns. Its job is to stop mean reversion from fighting a strong move.

**Crypto extras:** an "extreme volume" note when the latest bar's volume is 2.5σ above normal, and optionally the
perpetual funding rate (set `funding_exchange`; some exchanges block US IPs).

### The ensemble decision

- **Confluence score** = 50 + 50 × average(vote × strength) across the five models. 50 is neutral, 100 is
  everything maximally bullish, 0 maximally bearish.
- **Buy / Sell**: at least `min_agree` (default 3) of 5 models point the same way and outnumber the other side.
- **Strong Buy / Strong Sell**: the above *and* score ≥ 75 (≤ 25 for sells).
- **Watch ↑ / Watch ↓**: one model short, or score past 58 / below 42.
- **Falling-knife guard**: if trend *and* momentum are both down, an oversold Buy is capped at Watch.
  The mirror applies to Sells during strong uptrends (don't short a squeeze).

Tested on synthetic scenarios: a sharp dip inside an uptrend → **Buy**; a crash that's still accelerating → **Hold**
(oversold, but trend and momentum disagree); a vertical squeeze → **Hold** (overbought, but trend and momentum up).

### When you get pinged

Only when something changes: a *new* signal at or above your `min_action` level, a direction flip, or a
strengthening (Buy → Strong Buy). The same Buy showing up every 30 minutes does not re-alert. A signal that fades
and comes back alerts again. On the very first scan nothing is sent (it just records the baseline), unless you
set `alert_on_first_scan: true`.

### How this relates to InvestAnswers-style thinking

The idea is the same family: don't act on one indicator, wait for **confluence** of trend, mean reversion
and multi-indicator agreement, and think in **ATR layers** for scaling in and out, with daily/4H as the main
timeframes. Everything here is an open, documented approximation written from scratch. It isn't a copy
of IADSS or any proprietary Pine script, and it won't produce identical signals.

---

## Notes and limits

- **Data:** yfinance is unofficial and occasionally rate-limits or breaks; the app retries and shows any failed
  tickers instead of crashing. Stock 4H bars are built from 1H data. Intraday scans of the `1d` timeframe use
  the still-forming daily bar.
- **Hourly stock data** comes from Yahoo (free); 4-hour bars are built from it. Crypto hourly comes from Kraken.
- **Market hours** are 9:30–16:05 ET weekdays; exchange holidays aren't handled (the scan just sees no new bar).
- **History tab** shows each signal's price and the latest scanned price. The "% moving the signalled way"
  note is a rough sanity check, **not a backtest**.
- Tune thresholds in the sidebar; changes apply to the next scan immediately, and **Save** writes them to
  `config.yaml` (which the runner uses).

## Adding a model

Write `def my_model(df, p) -> ModelResult` in `signals.py`, add it to `MODELS`, and add a `my_model:` params
block under `models:` in the config. The ensemble picks it up automatically (consider raising `min_agree`).

## Worthwhile next improvements

1. **Multi-timeframe confirmation** — only alert a daily Buy when the 4H is at least neutral (or require
   weekly trend up). Cuts a lot of noise for little code.
2. **Backtest tab** — replay `evaluate()` bar by bar over 2–5 years per ticker and report hit rate, average
   forward 5/20-day return and max drawdown after each action. This is the single most important step
   before trusting any threshold.
3. **More free context** — the Fear & Greed index (alternative.me) and BTC dominance (CoinGecko) as crypto
   regime filters, and a QQQ/SPY regime gate so individual stock Buys are discounted when the market trend is down.
