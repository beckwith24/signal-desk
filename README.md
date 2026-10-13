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

**Settings on the website (recommended):** tap **⚙︎** on the chart site and connect once with a GitHub
fine-grained token limited to this repository (Contents: read & write, Actions: read & write); the page shows
the exact steps. The key is kept only in that browser. From then on you can add/remove tickers, choose alert
timeframes and level, switch layer alerts, pause alerts and start a scan, all saved straight to
`settings.json`. The Telegram bot re-reads that file before every change, so the two never overwrite each other.

**Adding and removing tickers from Telegram (also works):** in your bot chat send `/add TSM AMZN` (crypto must end in `-USD`, e.g.
`/add DOGE-USD`), `/remove TSLA`, or `/list` to see your tickers as tap-to-remove buttons. The bot checks the
symbol exists on Yahoo, saves the list to `settings.json` (it overrides the watchlist in `config.yaml`) and
starts a scan so the new chart appears within minutes. The chart site has the same controls: **＋ Add ticker**
on the main list and **Remove from watchlist** on each chart. Both open your bot; tap **Start** to confirm.
Up to 40 tickers.

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

## Models by segment (engine v2)

Stocks and crypto, and daily vs 4-hour vs hourly, each get their own model set. A model is used only if
published out-of-sample research supports it **and** our own walk-forward test on these tickers agrees
(`python research_backtest.py`, results in `research/summary.md`). Models live in `models.py`, the
per-segment sets and Buy/Sell rules in `engine.py`.

| Segment | Models | Buy / Sell rule | Evidence |
|---|---|---|---|
| **Crypto · daily** | 28-day momentum · price above 20/50/100-day MAs · breakout ensemble (5–360 days, trailing stop) · Bitcoin above its 50-day MA | **Buy** when 3 of 4 are bullish and none bearish (4 = Strong Buy); **Exit** alert when that ends; **Sell** when ≥3 bearish | Han, Kang & Ryu; Detzel et al. (Financial Management 2021); Zarattini, Pagani & Barbon (2025). Our test 2021–2026 (never used for tuning): 36%/yr vs 19.6% holding, worst drop −53% vs −90%, Sharpe 0.92 vs 0.60 |
| **Stocks · daily** | RSI(2) < 10 above the 200-day MA (exit on close above 5-day MA) · close in bottom 20% of the day's range in an uptrend (IBS) · VIX above 3-month VIX | **Buy** when one fires, **Strong Buy** when two or more; no sell signals | Connors & Alvarez; Pagonidis / arXiv 2306.12434; Fassas & Hourvouliades. Our test: positive in both halves but weak (+0.04% to +0.13% per day above normal, not statistically significant). Best used to time additions, not to be in or out |
| **4-hour and hourly** (both) | none | no Buy/Sell; charts, layers and the daily signal for timing entries | Large studies (e.g., Marshall, Cahan & Cahan 2008) find intraday rules don't survive costs; our tests agreed |

What we tested and dropped: the original five-model vote (no edge in any segment), market-regime filters
for single-stock timing, the turn-of-month effect (worked before 2021, not after), trend models on stocks,
dip-buying on crypto (it hurt), and every model on 4h/1h bars.

Honest caveats: with 13 stocks and 5 coins (picked because they did well), no model passed the strict
pre-set test on the older half alone; the chosen sets are the ones the published research favors and
that pointed the right way in both halves of our data. Costs assumed: 0.05% per side for stocks, 0.25% for crypto.

The **layer-in / layer-out ladder** (`ladder.py`) runs separately on every daily chart. On crypto, its
messages say so when the ladder and the trend signal disagree.

### When you get pinged

Only when something changes: a *new* signal at or above your `min_action` level, a direction flip, a
strengthening (Buy → Strong Buy), or (crypto) an **Exit** when a Buy you were alerted to ends. The same Buy showing up every 30 minutes does not re-alert. A signal that fades
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

Write `def my_model(df, ctx, p)` in `models.py` returning a DataFrame with `vote` (+1/0/−1) and `strength`
for every bar (looking only backwards), plus a `describe(row, p)`; register it in `MODELS`. Add it to the
segment lists in `research_backtest.py`, run the research, and only then add it to a segment in `engine.py`.
The look-ahead test (each bar's vote must be identical whether computed on the full history or only up to
that bar) should pass for every model.

## Worthwhile next improvements

1. **Multi-timeframe confirmation** — only alert a daily Buy when the 4H is at least neutral (or require
   weekly trend up). Cuts a lot of noise for little code.
2. **Backtest tab** — replay `evaluate()` bar by bar over 2–5 years per ticker and report hit rate, average
   forward 5/20-day return and max drawdown after each action. This is the single most important step
   before trusting any threshold.
3. **More free context** — the Fear & Greed index (alternative.me) and BTC dominance (CoinGecko) as crypto
   regime filters, and a QQQ/SPY regime gate so individual stock Buys are discounted when the market trend is down.
