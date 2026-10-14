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

**Settings on the website (recommended):** tap **Settings** (bottom bar on phones, top-right icon on computers) on the chart site and connect once with a GitHub
fine-grained token limited to this repository (Contents: read & write, Actions: read & write); the page shows
the exact steps. The key is kept only in that browser. From then on you can add/remove tickers, choose alert
timeframes and level, switch layer alerts, pause alerts and start a scan, all saved straight to
`settings.json`. The Telegram bot re-reads that file before every change, so the two never overwrite each other.

**Adding and removing tickers from Telegram (also works):** in your bot chat send `/add TSM AMZN` (crypto must end in `-USD`, e.g.
`/add DOGE-USD`), `/remove TSLA`, or `/list` to see your tickers as tap-to-remove buttons. The bot checks the
symbol exists on Yahoo, saves the list to `settings.json` (it overrides the watchlist in `config.yaml`) and
starts a scan so the new chart appears within minutes. The chart site has the same controls: **＋ Add ticker**
on the main list and **Remove from watchlist** on each chart. Both open your bot; tap **Start** to confirm.
Up to 70 tickers.

**Charts on your phone:** every scan publishes a small website at
`https://<your-github-username>.github.io/signal-desk`, with four sections (bottom bar on phones, top bar on
computers). **Watchlist** lists every ticker, stocks and crypto in separate panels: one dot per model (filled =
says buy), the daily signal, a one-month mini chart and the price. **Signals** shows only tickers with a signal,
one card each: when the signal started and the move since, every model's reading in words, the suggested
size, the next add / trim prices from the layer plan, the IA view, and how that signal level did in testing
(2021 on); the Strong Buy / Buy tiles filter it. **Info** explains each model in plain English and summarises
the backtests. **Settings** is below.
Tap a ticker for a candlestick chart with the Bollinger bands, ATR layers, EMAs, volume and past signal arrows,
plus each model's reading. Switch Daily / 4H / 1H at the top. The site is dark by default; the sun/moon button
(or Settings → Theme: Dark / Light / Auto) changes it, remembered per device. In Safari, use Share → **Add to Home Screen**
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
| **4-hour and hourly** (both) | none | no Buy/Sell. The site's list is daily only; 4H/1H charts are on each ticker page | Large studies (e.g., Marshall, Cahan & Cahan 2008) find intraday rules don't survive costs; our tests agreed |

**Three more model types** (`factor_research.py`, results in `research/factors.md`; S&P 100 and 29 coins,
not just the watchlist):
- *Relative strength ranking* (own the strongest third): stocks +1 to +4%/yr vs equal weight, not
  statistically reliable even with today's S&P 100 flattering it; crypto inconsistent between the two
  halves. Not used for signals.
- *Earnings drift* (buy after a beat the market cheers): too small to trade on big US stocks (+0.2 to
  +0.7% over 20 days, not reliable). Not used.
- *Risk-matched size* (smaller positions in wilder tickers): on the crypto trend rule it roughly halved
  the worst drops (−35% → −17% before 2021, −44% → −28% after) and gave up a similar share of the gains.
  Shown as a suggested size on each ticker page and in Buy alerts; a risk choice, not an edge.
- Bonus check: the app's crypto trend rule, run on all 29 coins, beat holding them equally after 2021
  (Sharpe 1.40 vs 0.71, worst drop −44% vs −81%).

**Copying Congress** (`congress_research.py`, results in `research/congress.md`): 22,821 stock trades by 266
members from the official House Clerk and Senate eFD filings, 2018 on (median 28 days from trade to report).
Buying the day after a buy was reported trailed the S&P 500 by 1.3% over the next 6 months since 2021
(t −2.7) and beat it over 3 months only 45% of the time. Buys by 2+ members within 30 days were the one
group ahead in both halves (+0.75% over 20 trading days; t 1.5 before 2021, 2.6 after), fading after that.
The copy-Congress ETFs since Feb 2023: NANC +110%, GOP +82%, SPY +99%. Reported trades are shown on stock
pages and as a 🏛 tag on the list (last 30 days) but never trigger a signal. The daily `Congress trades` job
adds new filings.

**InvestAnswers-style backtests** (`ia_tuning_research.py`, `conf_research.py`, notes in `research/ia_notes.md`):
tuning the ATR Model per ticker the way IA's demo does always ends up choosing "only sell in profit", which
gives 100% wins in and out of sample, but after 2022 it made a median +144% on 29 stocks vs +293% for
holding, with the same drawdowns. The Confluence Model rebuilt from a screenshot (Bollinger Bands, about 4
days, 2 standard deviations; re-entries match 9 of 24 of its triangles) also trailed holding on stocks; on
crypto, its "sell only above cost" version left coins ~50% under cost. None of this is used for signals.

**Strong Buy vs Buy** (`strength_research.py`, results in `research/strength.md`, ~10 years): on stocks,
Strong Buy days (2+ dip signals) beat the stock's normal next day by 0.44% (t 2.8) and its normal 5 days by
0.76%; single-signal Buys were close to random (+0.01% next day). On crypto, all-4 Strong Buys beat normal
by 0.44% next day (t 3.6) and 1.9% over 5 days, in both halves of the data; 3-of-4 Buys were weak and
inconsistent. So "Strong Buy" is the level worth alerting on.

**Waiting for the 4H and 1H to line up before buying doesn't help** (`mtf_research.py`, results in
`research/mtf.md`). Over ~2 years of daily Buy signals, entering only once the 4H and 1H had turned up
(ATR model on the buy side, ribbon blue, or both) gave up about a third of the stock profit (1,820 trades:
you buy after the bounce has started and skip some winners) and made no difference on crypto. So the daily
Buy alert itself is the "buy now".

What we tested and dropped: the InvestAnswers-style ribbon and ATR stop (see below), the original five-model vote (no edge in any segment), market-regime filters
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

### InvestAnswers-style view (rebuilt from TradingView screenshots)

Every chart has an **IA view** switch, plus an "InvestAnswers-style view" box on each ticker page. The
formulas were worked out by digitising screenshots of the IA indicators (`research/ia_targets/`) and
searching thousands of candidate formulas against real prices (`calibrate_ia.py`, Actions → "IA calibration",
results in `research/ia_calibration.md`). They are close matches, not InvestAnswers' own code.

| Indicator | Rebuilt as | How close |
|---|---|---|
| IA-Optimized-Trend ribbon | 15-bar EMA of (high+low+close)/3 vs 34-bar EMA of close; blue when the fast line is above | SK hynix and Samsung: lines within 0.3–0.7%, colour right on 97–98% of days |
| IA-ATR-Model buy/sell | ATR trailing stop that trails k × 30-bar ATR behind the close and flips when a close crosses it; k = 1.25 daily, 0.5 intraday | BTC daily: 31 of 34 triangles, 3 extra. CBRS 4h: about 23 of 32 |
| IA-ATR-Model levels | Fibonacci fractions of the all-time high: Level 1–6 = 23.6 / 38.2 / 50 / 61.8 / 76.4 / 100% | BTC levels within 0.25% |

**Tested like every other model** (same walk-forward test, costs included). Results:
- Crypto daily: ribbon and ATR stop point the right way in both halves but weakly. Ribbon + stop together:
  Sharpe 0.65 vs 0.60 holding, 17%/yr vs 20%, worst drop −73% vs −90%. The crypto trend set already in use
  did better (Sharpe 0.92, 36%/yr, worst drop −53%), so it stays in charge of alerts.
- Stocks daily: no edge from the ribbon or the ATR stop. "Below Level 4 (61.8% of the high)" pointed the right
  way in both halves but fires rarely.
- 4h and 1h: no edge; the ATR stop flips often and costs eat it.
- The ATR-BT table's 91–94% win rates can't be reproduced by trading the signals at real prices
  (close to close: about 44–56% wins). Buying at each signal bar's low and selling at its high gives
  92–98%, which suggests the table uses prices you couldn't actually get.

So the IA view is for reading the chart the way you're used to. Alerts still come from the tested model sets.

---

## Notes and limits

- **Data:** yfinance is unofficial and occasionally rate-limits or breaks; the app retries and shows any failed
  tickers instead of crashing. Stock 4H bars are built from 1H data as two session bars per day
  (9:30–13:30 and 13:30–16:00 ET), the way TradingView draws them. Intraday scans of the `1d` timeframe use
  the still-forming daily bar.
- **Hourly stock data** comes from Yahoo (free); 4-hour bars are built from it. Crypto hourly comes from Kraken.
- **Market hours** are 9:30–16:05 ET weekdays; exchange holidays aren't handled (the scan just sees no new bar).
- **History tab** shows each signal's price and the latest scanned price. The "% moving the signalled way"
  note is a rough sanity check, **not a backtest**.
- Tune thresholds in the sidebar; changes apply to the next scan immediately, and **Save** writes them to
  `config.yaml` (which the runner uses).

## Security

Checked with a penetration test (October 2026). What protects what:

- **Telegram bot:** obeys only your own chat (TELEGRAM_CHAT_ID). Messages and button taps from anyone else
  are ignored without a reply. A "remove" link from the site asks you to confirm with a tap, so a link
  someone sends you can't quietly change your list. A malformed update is skipped instead of stopping the bot.
- **Chart site:** every ticker name and reason is shown as plain text (tested with script-injection names).
  The page carries a Content-Security-Policy: scripts only from the site itself, and network calls only
  to the site and api.github.com. That limits what a bad script could do with the GitHub key stored in
  your browser. It refuses to run inside another site's frame.
- **GitHub key on the site:** fine-grained, this repository only, Contents + Actions. It's stored only in
  that browser; "Forget key on this device" removes it. Give it an expiry date when you create it.
- **Workflows:** inputs are passed as data, never pasted into shell commands; the scan job can only write
  repository contents, and only the publish job can deploy Pages. Secrets are masked in logs.
- **Public by design:** the repository and chart site are public (free Actions minutes and free Pages), so
  your watchlist, signal history and bot username are visible to anyone who finds them. No keys or tokens
  are stored in the repository (history checked). Python packages aren't pinned, so fixes (often needed
  for Yahoo) arrive automatically, at the cost of trusting new releases.

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
