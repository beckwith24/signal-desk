// Refuse to run inside someone else's frame (stops click-tricking on the settings screen).
if (window.top !== window.self) { document.documentElement.style.display = "none"; throw new Error("framed"); }
(() => {
  "use strict";
  const TF_LABEL = { "1d": "Daily", "4h": "4H", "1h": "1H", "1wk": "Weekly" };
  const FILTERS = [["all", "All"], ["stock", "Stocks"], ["crypto", "Crypto"]];
  const LEVELS = { strong: (i) => i.rank >= 3, buy: (i) => i.rank === 2, sell: (i) => i.rank <= -2, signals: (i) => i.rank !== 0, all: () => true };
  const OVERLAYS = [
    ["ia", "IA view"], ["bands", "Bands"], ["layers", "ATR layers"], ["emas", "EMAs"], ["ma", "Long MA"], ["volume", "Volume"], ["markers", "Past signals"],
  ];
  const store = {
    get(k, d, ver) { try { const v = localStorage.getItem("sd." + k + (ver ? "." + ver : "")); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v, ver) { try { localStorage.setItem("sd." + k + (ver ? "." + ver : ""), JSON.stringify(v)); } catch {} },
  };
  const state = {
    index: null,
    tf: store.get("tf", "1d"),
    filter: ["all", "stock", "crypto"].includes(store.get("filter", "all")) ? store.get("filter", "all") : "all",
    level: "all",                       // all | strong | buy | sell | signals (tiles and the Signals tab)
    overlays: Object.assign({ ia: true, bands: false, layers: true, emas: false, ma: false, volume: true, markers: true }, store.get("overlays", {}, "v2")),
    detail: null, chart: null,
  };
  const LOC = (() => { try { const l = navigator.language || "en-US"; new Intl.NumberFormat(l); new Intl.DateTimeFormat(l); return l; } catch { return "en-US"; } })();
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  function actionClass(a) {
    return { "Strong Buy": "strong-up", "Buy": "up", "Watch ↑": "watch-up", "Hold": "hold",
             "Watch ↓": "watch-down", "Sell": "down", "Strong Sell": "strong-down" }[a] || "hold";
  }
  function pill(a) { return el("span", "pill " + actionClass(a), a); }
  function fmtPrice(p, nd) {
    if (p == null) return "–";
    const d = nd != null ? Math.min(nd, p >= 1000 ? 2 : nd) : 2;
    return p.toLocaleString(LOC, { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function fmtChg(c) {
    const span = el("span", "chg " + (c > 0 ? "up" : c < 0 ? "down" : "flat"), (c > 0 ? "+" : "") + c.toFixed(2) + "%");
    return span;
  }
  function since(text) {
    const t = Date.parse(text.replace(" UTC", "Z").replace(" ", "T"));
    if (isNaN(t)) return text;
    const mins = Math.round((Date.now() - t) / 60000);
    const local = new Date(t).toLocaleString(LOC, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
    if (mins < 1) return "just now";
    if (mins < 60) return mins + " min ago";
    if (mins < 60 * 24) return Math.round(mins / 60) + " h ago · " + local;
    return local;
  }

  // ---------------------------------------------------------------- controls
  function renderControls() {
    const seg = $("tfSeg"); seg.textContent = "";
    const tfs = state.index ? state.index.timeframes : ["1d", "4h", "1h"];
    if (!state.detail) state.tf = "1d";                 // the list is daily only
    if (!tfs.includes(state.tf)) state.tf = tfs[0];
    seg.hidden = !state.detail || tfs.length < 2;
    for (const tf of tfs) {
      const b = el("button", null, TF_LABEL[tf] || tf);
      b.type = "button"; b.setAttribute("aria-pressed", String(tf === state.tf));
      b.onclick = () => { state.tf = tf; store.set("tf", tf); if (state.detail) openDetail(state.detail.ticker, tf, true); else render(); renderControls(); };
      seg.append(b);
    }
    const f = $("filters"); f.textContent = "";
    f.hidden = !!state.detail;
    for (const [k, label] of FILTERS) {
      const b = el("button", "chip", label);
      b.type = "button"; b.setAttribute("aria-pressed", String(k === state.filter));
      b.onclick = () => { state.filter = k; store.set("filter", k); renderControls(); render(); };
      f.append(b);
    }
  }

  // ---------------------------------------------------------------- list
  const SVG = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs) => { const e = document.createElementNS(SVG, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  let sparkId = 0;
  function spark(vals, pct) {            // last month of daily closes, drawn as a small line (no inline script or style: CSP-safe)
    const svg = svgEl("svg", { class: "spark", viewBox: "0 0 76 30", preserveAspectRatio: "none", "aria-hidden": "true" });
    if (!vals || vals.length < 2) return svg;
    const up = vals[vals.length - 1] >= vals[0], dir = up ? "up" : "down";
    const n = vals.length, X = (i) => (i / (n - 1) * 76).toFixed(1), Y = (v) => (2 + (100 - v) / 100 * 26).toFixed(1);
    let d = ""; vals.forEach((v, i) => { d += (i ? "L" : "M") + X(i) + " " + Y(v); });
    const id = "sg" + (++sparkId);
    const grad = svgEl("linearGradient", { id, x1: "0", y1: "0", x2: "0", y2: "1" });
    grad.append(svgEl("stop", { offset: "0", class: dir, "stop-opacity": "0.28" }), svgEl("stop", { offset: "1", class: dir, "stop-opacity": "0" }));
    const defs = svgEl("defs", {}); defs.append(grad);
    svg.append(defs, svgEl("path", { d: d + "L76 30L0 30Z", fill: "url(#" + id + ")" }),
      svgEl("line", { class: "base", x1: "0", x2: "76", y1: Y(vals[0]), y2: Y(vals[0]) }),
      svgEl("path", { class: "ln " + dir, d }));
    if (pct != null) { const t = svgEl("title", {}); t.textContent = "Past month: " + (pct > 0 ? "+" : "") + pct + "%"; svg.append(t); }
    return svg;
  }
  function stripe(rank) {
    return rank >= 3 ? "s-strong" : rank === 2 ? "s-buy" : rank === 1 ? "s-watch" : rank === -1 ? "s-watchd" : rank === -2 ? "s-sell" : rank <= -3 ? "s-strongsell" : "";
  }
  function row(i) {
    const li = el("li");
    const b = el("button", "item " + stripe(i.rank)); b.type = "button";
    const head = el("div", "head");
    head.append(el("span", "tk", i.ticker.replace("-USD", "")));
    if (i.rank) head.append(pill(i.action));                 // Hold rows stay quiet
    const px = el("div", "px"); px.append(el("div", "p", fmtPrice(i.price, i.decimals)), fmtChg(i.change_pct));
    b.append(head, spark(i.spark, i.spark_pct), px);
    const mods = el("div", "mods");
    if (i.models && i.models.length) {          // what each model says today: filled dot = buy
      const on = i.models.filter((m) => m.v > 0).length;
      const n = el("span", "mods-n", on + "/" + i.models.length + " buy");
      n.title = on + " of " + i.models.length + " models say buy";
      mods.append(n);
      for (const m of i.models) {
        const c = el("span", "mod " + (m.v > 0 ? "up" : m.v < 0 ? "down" : "flat"));
        c.append(el("i"), m.s); c.title = m.r; mods.append(c);
      }
    }
    if (i.congress) {                           // congressional trades reported in the last 30 days
      const c = i.congress, parts = [];
      if (c.buys) parts.push(c.buys + " buy" + (c.buys > 1 ? "s" : ""));
      if (c.sells) parts.push(c.sells + " sell" + (c.sells > 1 ? "s" : ""));
      const tag = el("span", "mod gov", "🏛 Congress " + parts.join(", "));
      tag.title = "Reported by members of Congress in the last 30 days (information only)";
      mods.append(tag);
    }
    if (mods.childNodes.length) b.append(mods);
    b.onclick = () => { state.fromList = true; location.hash = (i.ticker + "_" + i.tf).replace(/[^A-Za-z0-9_.-]/g, "_"); };
    li.append(b);
    return li;
  }
  function syncTabs() {
    const cur = !$("settingsView").hidden ? "settings" : !$("infoView").hidden ? "info" : state.level === "all" ? "list" : "signals";
    for (const b of $("tabbar").querySelectorAll("button")) {
      if (b.dataset.tab === cur) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
    }
    const items = ((state.index && state.index.items) || []).filter((i) => i.tf === "1d" && i.rank >= 2);
    const badge = $("tabBadge"); badge.hidden = !items.length; badge.textContent = String(items.length);
  }
  const EMPTY = { strong: "No Strong Buys", buy: "No Buys", sell: "No Sells", signals: "No signals" };
  function render() {
    const box = $("list"); box.textContent = ""; box.className = "";
    const tiles = $("tiles"); tiles.textContent = "";
    syncTabs();
    const idx = state.index;
    if (!idx || !idx.items.length) {
      const e = el("div", "empty");
      e.append(el("h2", null, "No charts yet"), el("div", null, "Charts appear after the next scan publishes them."));
      box.append(e); return;
    }
    const all = idx.items.filter((i) => i.tf === "1d");
    const shown = state.filter === "all" ? all : all.filter((i) => i.asset === state.filter);
    const count = (k) => shown.filter(LEVELS[k]).length;
    const defs = [["strong", "Strong Buy", count("strong")], ["buy", "Buy", count("buy")]];
    if (count("sell")) defs.push(["sell", "Sell", count("sell")]);      // only shown when there are any
    defs.push(["all", "All tickers", shown.length]);
    tiles.style.setProperty("--n", defs.length);
    for (const [k, label, n] of defs) {
      const t = el("button", "tile " + k); t.type = "button";
      t.setAttribute("aria-pressed", String(state.level === k));
      t.append(el("span", "n", String(n)), el("span", "l", label));
      t.onclick = () => { state.level = state.level === k && k !== "all" ? "all" : k; render(); };
      tiles.append(t);
    }
    const keep = LEVELS[state.level] || LEVELS.all;
    const groups = state.filter === "all" ? [["stock", "Stocks"], ["crypto", "Crypto"]] : [[state.filter, state.filter === "stock" ? "Stocks" : "Crypto"]];
    const present = groups.filter(([a]) => all.some((i) => i.asset === a));
    if (present.length === 1) box.className = "single";
    for (const [asset, title] of present) {
      const pool = shown.filter((i) => i.asset === asset);
      const items = pool.filter(keep).sort((a, b) => b.rank - a.rank || Math.abs(b.score - 50) - Math.abs(a.score - 50) || a.ticker.localeCompare(b.ticker));
      const sec = el("section", "group");
      const h = el("h2", "group-h", title);
      h.append(el("span", "c", items.length === pool.length ? String(pool.length) : items.length + " of " + pool.length));
      const ul = el("ul", "list");
      if (!items.length) ul.append(el("li", "none", (EMPTY[state.level] || "Nothing") + " in " + title.toLowerCase() + " today."));
      for (const i of items) ul.append(row(i));
      if (present.length === 1 && items.length % 2) ul.append(el("li", "filler"));   // keeps the 2-column grid even on wide screens
      sec.append(h, ul); box.append(sec);
    }
  }
  $("addToggle").onclick = () => {
    const f = $("addForm"); f.hidden = !f.hidden;
    $("addToggle").textContent = f.hidden ? "＋ Add ticker" : "Close";
    if (!f.hidden) {
      $("addSubmit").textContent = GH.token ? "Add" : "Add in Telegram";
      $("addHint").textContent = GH.token ? "Crypto: add -USD (e.g. DOGE-USD)." :
        "Opens your bot; tap Start there. Tip: connect GitHub in Settings to add tickers right here.";
      $("addInput").focus();
    }
  };
  for (const b of $("tabbar").querySelectorAll("button")) {
    b.onclick = () => {
      const t = b.dataset.tab;
      if (t === "settings" || t === "info") { if (location.hash !== "#" + t) { state.fromList = true; location.hash = t; } return; }
      state.level = t === "signals" ? "signals" : "all";
      if (location.hash.length > 1) { state.fromList = false; location.hash = ""; } else { render(); }
      window.scrollTo(0, 0);
    };
  }

  // ---------------------------------------------------------------- detail
  async function openDetail(ticker, tf, replaceHash) {
    const id = (ticker + "_" + tf).replace(/[^A-Za-z0-9_.-]/g, "_");
    if (replaceHash) history.replaceState(null, "", "#" + id);
    let d;
    try {
      const r = await fetch("data/" + id + ".json?v=" + Date.now());
      if (!r.ok) throw new Error(r.status);
      d = await r.json();
    } catch (e) {
      showDetailError(ticker, tf); return;
    }
    state.detail = d; state.tf = tf; store.set("tf", tf);
    leaveSettings();
    $("listView").hidden = true; $("detailView").hidden = false;
    $("back").hidden = false; $("brand").hidden = true;
    renderControls();
    $("dTitle").textContent = d.ticker.replace("-USD", "");
    $("dAsset").textContent = (d.asset === "crypto" ? "Crypto · " + d.ticker : "Stock") + " · " + (TF_LABEL[d.tf] || d.tf) + " bars";
    $("dPrice").textContent = fmtPrice(d.price, d.decimals);
    const chg = $("dChg"); chg.className = "chg " + (d.change_pct > 0 ? "up" : d.change_pct < 0 ? "down" : "flat");
    chg.textContent = (d.change_pct > 0 ? "+" : "") + d.change_pct.toFixed(2) + "% " + (d.tf === "1d" ? "on the day" : "last bar");
    const daily = d.tf === "1d" ? d : ((state.index && state.index.items) || []).find((i) => i.ticker === d.ticker && i.tf === "1d");
    const dp = $("dPill"); dp.textContent = "";
    if (daily) { const p = pill(daily.action); if (d.tf !== "1d") p.textContent = "Daily: " + daily.action; dp.append(p); }
    const stats = $("dStats"); stats.textContent = "";
    const statBox = (k, node) => { const s = el("div", "stat"); const v = el("div", "val"); v.append(node); s.append(el("div", "k", k), v); stats.append(s); };
    const txt = (x) => document.createTextNode(x);
    if (d.tf === "1d") {
      statBox("Models", txt(d.bull + " buy · " + d.bear + " sell"));
      statBox("Score", txt(d.score + " / 100"));
    } else {
      statBox("This chart", txt((TF_LABEL[d.tf] || d.tf) + " view only"));
      statBox("IA view", txt(d.ia ? (d.ia.trend === "up" ? "Blue" : "Orange") + " · ATR " + d.ia.stop_side : "–"));
    }
    statBox("ATR layer", txt((d.layer > 0 ? "+" : "") + d.layer));
    statBox("RSI", txt(d.rsi != null ? String(Math.round(d.rsi)) : "–"));
    const rs = $("dReasons"); rs.textContent = "";
    for (const r of d.reasons) rs.append(el("li", null, r));
    for (const n of d.notes || []) rs.append(el("li", "note", n));
    renderLadder(d);
    renderIA(d);
    renderSize(d);
    renderCongress(d);
    $("dAbout").textContent = d.segment_about ? d.segment_about + "." : "";
    const mt = $("dModels"); mt.textContent = "";
    for (const m of d.models) {
      const tr = el("tr");
      const vc = m.vote > 0 ? "up" : m.vote < 0 ? "down" : "flat";
      tr.append(el("td", null, m.name), el("td", "vote " + vc, m.vote > 0 ? "▲ " + m.strength.toFixed(1) : m.vote < 0 ? "▼ " + m.strength.toFixed(1) : "·"), el("td", "why", m.reason));
      mt.append(tr);
    }
    const h = $("dHist"); h.textContent = "";
    const sigs = (d.signals || []).slice().reverse();
    if (!sigs.length) h.append(el("li", null, "No changes recorded yet."));
    for (const s of sigs.slice(0, 12)) {
      const li = el("li"); const left = el("span"); left.append(pill(s.action));
      li.append(left, el("span", "num", fmtPrice(s.price, d.decimals)), el("span", "when", since(s.ts)));
      h.append(li);
    }
    const rm = $("dRemove"), rmLink = botLink("rm", d.ticker);
    const rmName = "Remove " + d.ticker.replace("-USD", "") + " from watchlist";
    if (GH.token) {
      rm.hidden = false; rm.removeAttribute("href"); rm.textContent = rmName; rm.dataset.armed = "";
      rm.onclick = async (ev) => {
        ev.preventDefault();
        if (!rm.dataset.armed) { rm.dataset.armed = "1"; rm.textContent = "Tap again to remove " + d.ticker.replace("-USD", ""); return; }
        rm.textContent = "Removing…";
        await removeTicker(d.ticker);
        rm.textContent = $("sAddStatus").textContent || "Removed";
      };
    } else {
      rm.onclick = null; rm.hidden = !rmLink; if (rmLink) { rm.href = rmLink; rm.textContent = rmName; }
    }
    $("dFoot").textContent = "Latest bar " + d.bar_time.replace("+00:00", " UTC") + " · scanned " + since(d.updated) + ". Prices from Yahoo Finance (stocks) and Kraken (crypto).";
    drawChart();
    window.scrollTo(0, 0);
  }

  function renderLadder(d) {
    const box = $("dLadder"), now = $("dLadderNow"); box.textContent = ""; now.textContent = "";
    const L = d.ladder; if (!L) { now.textContent = "No layer plan in this data yet."; return; }
    const side = L.distance < 0 ? "below" : "above";
    now.append("Price is ", el("strong", null, Math.abs(L.distance).toFixed(1) + " ATR " + side),
      " the " + L.anchor_ma + "-bar average (" + fmtPrice(L.anchor, d.decimals) + "), layer ",
      el("strong", null, (L.layer > 0 ? "+" : "") + L.layer), ". Each layer is " + fmtPrice(L.step, d.decimals) + ".");
    const col = (cls, title, tiers, verb) => {
      const c = el("div", "rung-col " + cls); c.append(el("h4", null, title));
      for (const r of tiers) {
        const row = el("div", "rung " + cls + (r.reached ? " hit" : ""));
        const away = (r.price / d.price - 1) * 100;
        row.append(el("span", "lv", "L" + (r.layer > 0 ? "+" : "") + r.layer), el("span", "pr", fmtPrice(r.price, d.decimals)),
          el("span", "st", r.reached ? "✓ " + verb + " " + r.pct + "%" : verb + " " + r.pct + "% · " + (away > 0 ? "+" : "") + away.toFixed(1) + "%"));
        c.append(row);
      }
      return c;
    };
    box.append(col("in", "Layer in", L.buys, "add"), col("out", "Layer out", L.sells, "trim"));
  }

  function renderCongress(d) {
    const boxWrap = $("dCongressBox"), list = $("dCongress"), note = $("dCongressNote");
    list.textContent = ""; note.textContent = "";
    boxWrap.hidden = d.asset === "crypto" || d.congress == null;
    if (boxWrap.hidden) return;
    const fmtD = (x) => x ? new Date(x + "T12:00:00").toLocaleDateString(LOC, { month: "short", day: "numeric", year: "2-digit" }) : "?";
    const amt = (a) => a == null ? "" : " · $" + (a >= 1e6 ? Math.round(a / 1e6) + "M" : Math.round(a / 1000) + "k") + "+";
    if (!d.congress.length) list.append(el("li", null, "No trades in this stock reported in the last 12 months."));
    for (const c of d.congress) {
      const li = el("li");
      li.append(el("strong", null, c.side === "buy" ? "Buy" : "Sell"),
        " · " + c.member + " (" + c.chamber + ")" + amt(c.amount_low) + " · traded " + fmtD(c.traded) + ", reported " + fmtD(c.disclosed));
      list.append(li);
    }
    note.textContent = "From official House and Senate filings, updated daily. Tested on 22,800 trades since 2018: " +
      "once a buy was made public, the stock trailed the S&P 500 by about 1% over the next 6 months, so these " +
      "never trigger a signal.";
  }

  function renderSize(d) {
    const box = $("dSize"); box.textContent = "";
    const r = d.risk;
    if (!r) { box.textContent = d.tf === "1d" ? "Not in this data yet." : "Sizing uses the daily chart."; return; }
    if (r.size >= 0.95) {
      box.append("A ", el("strong", null, "normal position"), ". It swings about " + r.vol_pct + "% a year, within the " + r.target_pct + "% guide.");
    } else {
      box.append("About ", el("strong", null, r.size.toFixed(2).replace(/0$/, "") + "× a normal position"),
        ". It swings about " + r.vol_pct + "% a year vs a " + r.target_pct + "% guide, so a smaller position keeps the risk similar.");
    }
    box.append(el("br"), "In testing on 29 coins this roughly halved the worst drops, and gave up a similar share of the gains. A risk choice, not an edge.");
  }

  function renderIA(d) {
    const box = $("dIA"), note = $("dIANote"); box.textContent = ""; note.textContent = "";
    const v = d.ia; if (!v) { box.append(el("li", null, "Not in this data yet. It appears after the next scan.")); return; }
    const li = (label, strong, rest, cls) => { const x = el("li", cls); x.append(label, el("strong", null, strong), rest || ""); box.append(x); };
    li("Trend ribbon: ", v.trend === "up" ? "blue (uptrend)" : "orange (downtrend)",
       " — 15-bar EMA of (high+low+close)/3 " + (v.trend === "up" ? "above" : "below") + " the 34-bar EMA.");
    const ago = v.bars_since_flip == null ? "" : v.bars_since_flip === 0 ? " on this bar" : " " + v.bars_since_flip + " bar" + (v.bars_since_flip === 1 ? "" : "s") + " ago";
    li("ATR model: ", (v.stop_side === "buy" ? "buy" : "sell") + ago,
       v.stop != null ? " — stop " + fmtPrice(v.stop, d.decimals) + " (" + v.stop_key + " × 30-bar ATR). It flips when a close crosses it." : "");
    const lv = Math.floor(v.level), nxt = Math.min(lv + 1, 6);
    li("Levels: ", v.pct_of_ath + "% of the all-time high",
       " (" + fmtPrice(v.ath, d.decimals) + (v.ath_from_history ? "" : ", highest in the data shown") + "), between Level " +
       Math.max(lv, 0) + " and Level " + nxt + ". Levels are 23.6 / 38.2 / 50 / 61.8 / 76.4 / 100% of the high.");
    note.textContent = "Rebuilt from your TradingView screenshots: close matches, not InvestAnswers' own code. " +
      "Shown on the chart with the IA view switch.";
  }

  function showDetailError(ticker, tf) {
    state.detail = { ticker }; $("listView").hidden = true; $("detailView").hidden = false;
    $("dRemove").hidden = true;
    $("back").hidden = false; $("brand").hidden = true; renderControls();
    $("dTitle").textContent = ticker.replace("-USD", "");
    $("dAsset").innerHTML = ""; $("dAsset").append(el("span", "err", "No " + (TF_LABEL[tf] || tf) + " chart for this ticker yet."));
    for (const id of ["dPrice", "dChg", "dPill", "dStats", "dReasons", "dSize", "dCongress", "dCongressNote", "dIA", "dIANote", "dLadder", "dLadderNow", "dAbout", "dModels", "dHist", "dFoot", "legend"]) $(id).textContent = "";
    if (state.chart) { state.chart.remove(); state.chart = null; }
  }

  function closeDetail() {
    state.detail = null;
    if (state.chart) { state.chart.remove(); state.chart = null; }
    $("detailView").hidden = true; $("listView").hidden = false;
    $("back").hidden = true; $("brand").hidden = false;
    renderControls(); render();
  }

  // ---------------------------------------------------------------- chart
  function drawChart() {
    const d = state.detail; if (!d || !d.t) return;
    const box = $("chart");
    if (state.chart) { state.chart.remove(); state.chart = null; }
    if (!window.LightweightCharts) { box.textContent = "Chart library failed to load."; return; }
    const C = { ink: css("--ink"), muted: css("--muted"), line: css("--line"), surface: css("--surface"),
                up: css("--up"), down: css("--down"), accent: css("--accent"), watch: css("--watch"), faint: css("--faint") };
    const intraday = d.tf !== "1d" && d.tf !== "1wk";
    const chart = LightweightCharts.createChart(box, {
      autoSize: true,
      layout: { background: { type: "solid", color: C.surface }, textColor: C.muted, fontFamily: "IBM Plex Mono, ui-monospace, monospace", fontSize: 11 },
      grid: { vertLines: { color: css("--grid") }, horzLines: { color: css("--grid") } },
      rightPriceScale: { borderColor: C.line },
      timeScale: { borderColor: C.line, timeVisible: intraday, secondsVisible: false, rightOffset: 4 },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      localization: { locale: LOC, priceFormatter: (p) => fmtPrice(p, d.decimals) },
      handleScroll: { vertTouchDrag: false },
    });
    state.chart = chart;
    const prec = Math.min(d.decimals, 6);
    const candles = chart.addCandlestickSeries({
      upColor: C.up, downColor: C.down, borderUpColor: C.up, borderDownColor: C.down, wickUpColor: C.up, wickDownColor: C.down,
      priceFormat: { type: "price", precision: prec, minMove: Math.pow(10, -prec) },
    });
    const bars = [];
    for (let i = 0; i < d.t.length; i++) {
      if (d.o[i] == null || d.c[i] == null) continue;
      bars.push({ time: d.t[i], open: d.o[i], high: d.h[i], low: d.l[i], close: d.c[i] });
    }
    candles.setData(bars);
    const line = (key, color, width, style) => {
      const pts = []; const s = d.ov[key] || [];
      for (let i = 0; i < d.t.length; i++) if (s[i] != null) pts.push({ time: d.t[i], value: s[i] });
      const ser = chart.addLineSeries({ color, lineWidth: width, lineStyle: style || 0, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      ser.setData(pts); return ser;
    };
    const legend = $("legend"); legend.textContent = "";
    const ov = state.overlays;
    if (ov.volume) {
      const vol = chart.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
      chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.84, bottom: 0 }, visible: false });
      vol.setData(bars.map((b, i) => ({ time: b.time, value: d.v[d.t.indexOf(b.time)] || 0,
        color: (b.close >= b.open ? C.up : C.down) + "55" })));
    }
    if (ov.bands) {
      line("bb_up", C.accent, 1, 2); line("bb_mid", C.faint, 1, 1); line("bb_lo", C.accent, 1, 2);
    }
    if (ov.emas) { line("ema_fast", C.watch, 2); line("ema_slow", C.ink, 2); }
    if (ov.ma) line("ma_long", C.muted, 2, 1);
    const IA_BLUE = "#3E6BEF", IA_ORANGE = "#E0862C", IA_LEVEL = "#9C4DCC";
    if (ov.ia && d.ia && d.ov.ia_fast) {
      const f = d.ov.ia_fast, sl = d.ov.ia_slow, st = d.ov.ia_stop || [];
      const fp = [], sp = [], stp = [];
      for (let i = 0; i < d.t.length; i++) {
        if (f[i] == null || sl[i] == null) continue;
        const col = f[i] >= sl[i] ? IA_BLUE : IA_ORANGE;
        fp.push({ time: d.t[i], value: f[i], color: col }); sp.push({ time: d.t[i], value: sl[i], color: col });
      }
      for (let i = 0; i < d.t.length; i++) {
        if (st[i] == null || d.c[i] == null) continue;
        stp.push({ time: d.t[i], value: st[i], color: (d.c[i] > st[i] ? C.up : C.down) + "cc" });
      }
      const opts = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
      chart.addLineSeries(Object.assign({ lineWidth: 3 }, opts)).setData(fp);
      chart.addLineSeries(Object.assign({ lineWidth: 2 }, opts)).setData(sp);
      chart.addLineSeries(Object.assign({ lineWidth: 1, lineStyle: 1, lineType: 1 }, opts)).setData(stp);
      for (const [k, v] of Object.entries(d.ia.levels || {})) {
        if (v == null) continue;
        const near = Math.abs(v / d.price - 1) < 0.3;   // label only the levels near the price
        candles.createPriceLine({ price: v, color: IA_LEVEL + "bb", lineWidth: 1, lineStyle: 0, axisLabelVisible: near, title: near ? "Level " + k : "" });
      }
    }
    if (ov.layers) {
      line("anchor", C.faint, 1);
      for (const [k, v] of Object.entries(d.levels)) {
        const n = Number(k); if (!n || v == null) continue;
        candles.createPriceLine({ price: v, color: (n < 0 ? C.up : C.down) + "aa", lineWidth: 1, lineStyle: 3,
          axisLabelVisible: Math.abs(n) <= 2, title: "L" + (n > 0 ? "+" : "") + n });
      }
    }
    const marks = []; const times = bars.map((b) => b.time);
    if (ov.ia && d.ia && d.ia.flips) {
      for (const fl of d.ia.flips) {
        if (fl.t < times[0]) continue;
        const buy = fl.side === "buy";
        marks.push({ time: fl.t, position: buy ? "belowBar" : "aboveBar", color: buy ? C.up : C.down,
                     shape: buy ? "arrowUp" : "arrowDown", text: fl.side });
      }
    }
    if (ov.markers && d.signals && d.signals.length) {
      const seen = new Set();
      for (const s of d.signals) {
        if (!s.t || Math.abs(s.rank) < 1 || s.t < times[0]) continue;
        let j = times.length - 1; while (j > 0 && times[j] > s.t) j--;
        const t = times[j]; if (seen.has(t)) continue; seen.add(t);
        const up = s.rank > 0, strong = Math.abs(s.rank) >= 2;
        marks.push({ time: t, position: up ? "belowBar" : "aboveBar", color: up ? C.up : C.down,
                     shape: strong ? "square" : "circle", text: strong ? s.action : "" });
      }
    }
    marks.sort((a, b) => a.time - b.time);
    if (marks.length) candles.setMarkers(marks);
    // legend / overlay toggles
    const swatch = { ia: IA_BLUE, bands: C.accent, layers: C.up, emas: C.watch, ma: C.muted, volume: C.faint, markers: C.down };
    const labelFor = { ia: "IA ribbon · ATR buy/sell · levels", bands: "Bands (2σ)", layers: "ATR layers", emas: d.labels.ema_fast + " / " + d.labels.ema_slow.replace("EMA ", ""), ma: d.labels.ma_long, volume: "Volume", markers: "Past signals" };
    for (const [k] of OVERLAYS) {
      const b = el("button", "chip"); b.type = "button"; b.setAttribute("aria-pressed", String(!!ov[k]));
      const sw = el("span", "sw"); sw.style.background = swatch[k];
      b.append(sw, labelFor[k]);
      b.onclick = () => { ov[k] = !ov[k]; store.set("overlays", ov, "v2"); drawChart(); };
      legend.append(b);
    }
    // touch readout
    const hover = $("hover");
    const byTime = new Map(bars.map((b) => [b.time, b]));
    chart.subscribeCrosshairMove((p) => {
      if (!p || !p.time || !byTime.has(p.time)) { hover.textContent = "Touch the chart to read a candle."; return; }
      const b = byTime.get(p.time);
      const dt = new Date(p.time * 1000).toLocaleString(LOC, intraday ? { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" } : { year: "numeric", month: "short", day: "numeric" });
      hover.textContent = "";
      hover.append(dt + "  ");
      for (const [k, v] of [["O", b.open], ["H", b.high], ["L", b.low], ["C", b.close]]) {
        hover.append(k + " "); hover.append(el("span", "num", fmtPrice(v, d.decimals))); hover.append("  ");
      }
    });
    const visible = window.innerWidth < 600 ? (d.tf === "1d" ? 80 : 90) : 160;
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, bars.length - visible), to: bars.length + 3 });
  }

  // ---------------------------------------------------------------- add / remove tickers via the bot
  function botLink(cmd, sym) {
    const bot = state.index && state.index.bot;
    const clean = String(sym || "").trim().toUpperCase().replace(/^\$/, "").replace("/", "-");
    if (!bot || !/^[A-Z0-9-]{1,20}$/.test(clean)) return null;
    return "https://t.me/" + bot + "?start=" + cmd + "_" + clean;
  }
  $("addForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const sym = $("addInput").value;
    if (GH.token) {                          // connected: save directly, no Telegram
      const isCrypto = /-USDT?$/i.test(sym.trim());
      for (const x of $("sKind").children) x.setAttribute("aria-pressed", String((x.dataset.kind === "crypto") === isCrypto));
      if (!state.settings) { try { state.settings = (await loadSettings()).s; } catch (err) { if (!authFail(err)) { $("addHint").textContent = err.message; return; } } }
      await addTicker(sym);
      $("addHint").textContent = $("sAddStatus").textContent;
      $("addInput").value = "";
      return;
    }
    const link = botLink("add", sym);
    if (!state.index || !state.index.bot) { $("addHint").textContent = "Send /add " + sym.toUpperCase() + " to your Signal Desk bot in Telegram."; return; }
    if (!link) { $("addHint").textContent = "Use letters, numbers and - only (e.g. TSM, DOGE-USD). For other symbols send /add in Telegram."; return; }
    const a = document.createElement("a"); a.href = link; a.target = "_blank"; a.rel = "noopener"; document.body.append(a); a.click(); a.remove();
    $("addHint").textContent = "Opened Telegram. Tap Start there; the chart shows up after the next scan (a few minutes).";
    $("addInput").value = "";
  });

  // ---------------------------------------------------------------- settings saved to GitHub
  const GH = {
    token: store.get("gh", null),
    repo() {
      if (state.index && state.index.repo) return state.index.repo;
      const seg = location.pathname.split("/").filter(Boolean)[0] || "signal-desk";
      return location.hostname.split(".")[0] + "/" + seg;
    },
    async req(method, path, body) {
      const r = await fetch("https://api.github.com/repos/" + this.repo() + path, {
        method, cache: "no-store",
        headers: Object.assign({ Authorization: "Bearer " + this.token, Accept: "application/vnd.github+json",
                                 "X-GitHub-Api-Version": "2022-11-28" }, body ? { "Content-Type": "application/json" } : {}),
        body: body ? JSON.stringify(body) : undefined,
      });
      if (r.status === 401 || r.status === 403) { const e = new Error("auth"); e.status = r.status; throw e; }
      return r;
    },
  };
  const b64enc = (s) => { const b = new TextEncoder().encode(s); let x = ""; b.forEach((c) => x += String.fromCharCode(c)); return btoa(x); };
  const b64dec = (s) => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g, "")), (c) => c.charCodeAt(0)));

  function normalize(s) {
    const idx = state.index || {};
    const tfs = idx.timeframes || ["1d", "4h", "1h"];
    s.timeframes = Object.assign(Object.fromEntries(tfs.map((t) => [t, true])), s.timeframes || {});
    if (!["Watch", "Buy", "Strong Buy"].includes(s.min_action)) s.min_action = "Buy";
    if (typeof s.ladder !== "boolean") s.ladder = true;
    if (typeof s.paused !== "boolean") s.paused = false;
    if (!s.watchlist) {
      const w = idx.watchlist || { stocks: [], crypto: [] };
      s.watchlist = { stocks: [...w.stocks], crypto: [...w.crypto] };
    }
    return s;
  }
  async function loadSettings() {
    const r = await GH.req("GET", "/contents/settings.json?ref=main&t=" + Date.now());
    if (r.status === 404) return { s: normalize({}), sha: null };
    if (!r.ok) throw new Error("Couldn't read settings (" + r.status + ")");
    const j = await r.json();
    return { s: normalize(JSON.parse(b64dec(j.content))), sha: j.sha };
  }
  async function saveSettings(label, mutate) {
    for (let attempt = 0; attempt < 3; attempt++) {
      const { s, sha } = await loadSettings();          // always start from the latest saved copy
      const result = mutate(s);
      if (result === false) { state.settings = s; return false; }
      const body = { message: "Settings from website: " + label, content: b64enc(JSON.stringify(s, null, 2) + "\n"), branch: "main" };
      if (sha) body.sha = sha;
      const r = await GH.req("PUT", "/contents/settings.json", body);
      if (r.ok) { state.settings = s; return true; }
      if (r.status !== 409 && r.status !== 422) throw new Error("Save failed (" + r.status + ")");
    }
    throw new Error("Save failed: the file kept changing. Try again.");
  }
  async function startScan() {
    const r = await GH.req("POST", "/actions/workflows/scan.yml/dispatches", { ref: "main", inputs: { only: "all" } });
    if (r.status !== 204) throw new Error("Couldn't start a scan (" + r.status + ")");
  }
  function say(id, text, kind) { const e = $(id); e.textContent = text; e.className = "status" + (kind ? " " + kind : ""); }
  function authFail(e) {
    if (e && e.status) {
      GH.token = null; store.set("gh", null); renderSettings();
      say("connectStatus", "GitHub rejected the key (expired or missing a permission). Create a new one and connect again.", "bad");
      return true;
    }
    return false;
  }

  function cleanSymbol(raw, kind) {
    let t = String(raw || "").trim().toUpperCase().replace(/^\$/, "").replace("/", "-");
    if (!t) return null;
    if (kind === "crypto" && !/-USDT?$/.test(t)) t = t + "-USD";
    return /^[A-Z0-9.=^-]{1,20}$/.test(t) ? t : null;
  }
  async function addTicker(raw) {
    const kind = $("sKind").querySelector('[aria-pressed="true"]').dataset.kind;
    const t = cleanSymbol(raw, kind);
    if (!t) { say("sAddStatus", "Use letters and numbers (e.g. TSM, or DOGE for crypto).", "bad"); return; }
    const k = /-USDT?$/.test(t) ? "crypto" : "stocks";
    say("sAddStatus", "Saving " + t + "…");
    try {
      const saved = await saveSettings("add " + t, (s) => {
        const w = s.watchlist;
        if (w.stocks.includes(t) || w.crypto.includes(t)) return false;
        if (w.stocks.length + w.crypto.length >= 60) throw new Error("Your list is full (60). Remove a ticker first.");
        w[k].push(t);
      });
      if (!saved) { say("sAddStatus", t + " is already on your list."); renderSettings(); return; }
      $("sAddInput").value = "";
      renderSettings();
      await startScan();
      say("sAddStatus", "Added " + t + ". A scan has started; its chart appears in about 3 minutes. Alerts start from the scan after that.", "ok");
    } catch (e) { if (!authFail(e)) say("sAddStatus", e.message, "bad"); }
  }
  async function removeTicker(t) {
    say("sAddStatus", "Removing " + t + "…");
    try {
      await saveSettings("remove " + t, (s) => {
        const w = s.watchlist;
        const before = w.stocks.length + w.crypto.length;
        w.stocks = w.stocks.filter((x) => x !== t); w.crypto = w.crypto.filter((x) => x !== t);
        if (w.stocks.length + w.crypto.length === before) return false;
      });
      renderSettings();
      say("sAddStatus", "Removed " + t + ". It leaves the charts after the next scan.", "ok");
    } catch (e) { if (!authFail(e)) say("sAddStatus", e.message, "bad"); }
  }
  async function setOption(label, fn) {
    say("sStatus", "Saving…");
    try { await saveSettings(label, fn); renderSettings(); say("sStatus", "Saved. Applies from the next scan.", "ok"); }
    catch (e) { if (!authFail(e)) say("sStatus", e.message, "bad"); }
  }

  function chip(t, list) {
    const c = el("span", "tk-chip");
    const have = new Set(((state.index || {}).items || []).map((i) => i.ticker));
    const missing = new Set((state.index || {}).missing || []);
    c.append(t.replace(/-USD$/, ""));
    if (!have.has(t)) c.append(el("span", "tag", missing.has(t) ? "no data" : "waiting for scan"));
    const x = el("button", "x", "✕"); x.type = "button"; x.setAttribute("aria-label", "Remove " + t);
    x.onclick = () => {
      if (!c.classList.contains("confirm")) { c.classList.add("confirm"); x.textContent = "Remove"; setTimeout(() => { c.classList.remove("confirm"); x.textContent = "✕"; }, 4000); return; }
      removeTicker(t);
    };
    c.append(x); list.append(c);
  }
  function renderSettings() {
    const connected = !!GH.token;
    $("sConnect").hidden = connected; $("sMain").hidden = !connected;
    $("repoName").textContent = GH.repo().split("/")[1] || "signal-desk";
    if (!connected) return;
    $("sRepo").textContent = GH.repo();
    const s = state.settings;
    if (!s) { say("sStatus", "Loading your settings…"); return; }
    const ws = $("wlStocks"), wc = $("wlCrypto"); ws.textContent = ""; wc.textContent = "";
    s.watchlist.stocks.forEach((t) => chip(t, ws)); s.watchlist.crypto.forEach((t) => chip(t, wc));
    if (!s.watchlist.stocks.length) ws.append(el("span", "hint", "None"));
    if (!s.watchlist.crypto.length) wc.append(el("span", "hint", "None"));
    const tfBox = $("sTfs"); tfBox.textContent = "";
    for (const tf of Object.keys(s.timeframes)) {
      const b = el("button", "chip", TF_LABEL[tf] || tf); b.type = "button"; b.setAttribute("aria-pressed", String(!!s.timeframes[tf]));
      b.onclick = () => setOption((TF_LABEL[tf] || tf) + " alerts", (x) => { x.timeframes[tf] = !x.timeframes[tf]; });
      tfBox.append(b);
    }
    const lv = $("sLevel"); lv.textContent = "";
    for (const L of ["Watch", "Buy", "Strong Buy"]) {
      const b = el("button", null, L); b.type = "button"; b.setAttribute("aria-pressed", String(s.min_action === L));
      b.onclick = () => setOption("alert level " + L, (x) => { x.min_action = L; });
      lv.append(b);
    }
    $("sLadder").setAttribute("aria-checked", String(!!s.ladder));
    $("sPause").setAttribute("aria-checked", String(!!s.paused));
  }
  $("sLadder").onclick = () => setOption("layer alerts", (x) => { x.ladder = !x.ladder; });
  $("sPause").onclick = () => setOption("pause", (x) => { x.paused = !x.paused; });
  $("sKind").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    for (const x of $("sKind").children) x.setAttribute("aria-pressed", String(x === b));
    $("sAddInput").placeholder = b.dataset.kind === "crypto" ? "e.g. DOGE" : "e.g. TSM";
  });
  $("sAddForm").addEventListener("submit", (e) => { e.preventDefault(); addTicker($("sAddInput").value); });
  $("scanNow").onclick = async () => {
    say("sStatus", "Starting a scan…");
    try { await startScan(); say("sStatus", "Scan started. Charts update in about 2–3 minutes.", "ok"); }
    catch (e) { if (!authFail(e)) say("sStatus", e.message, "bad"); }
  };
  $("disconnect").onclick = () => { GH.token = null; store.set("gh", null); state.settings = null; renderSettings(); };
  $("connectForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const tok = $("tokenInput").value.trim();
    if (!tok) return;
    GH.token = tok; say("connectStatus", "Checking the key…");
    try {
      const r = await GH.req("GET", "");
      if (!r.ok) throw new Error(r.status === 404 ? "This key can't see " + GH.repo() + ". Check step 3." : "GitHub said " + r.status);
      const j = await r.json();
      if (j.permissions && j.permissions.push === false) throw new Error("The key can read but not write. Check step 4 (Contents: Read and write).");
      const { s } = await loadSettings();
      store.set("gh", tok); state.settings = s; $("tokenInput").value = "";
      say("connectStatus", ""); renderSettings(); say("sStatus", "Connected.", "ok");
    } catch (err) {
      GH.token = null;
      say("connectStatus", err.status ? "GitHub rejected this key. Copy it again, or create a new one." : err.message, "bad");
    }
  });
  function openPage(name) {            // full-screen pages: settings | info
    state.detail = null; if (state.chart) { state.chart.remove(); state.chart = null; }
    $("listView").hidden = true; $("detailView").hidden = true;
    $("settingsView").hidden = name !== "settings"; $("infoView").hidden = name !== "info";
    $("controls").hidden = true; $("back").hidden = false; $("brand").hidden = true;
    $("gear").hidden = name === "settings"; $("infoBtn").hidden = name === "info";
    syncTabs(); window.scrollTo(0, 0);
  }
  const onPage = () => !$("settingsView").hidden || !$("infoView").hidden;
  async function openSettings() {
    openPage("settings");
    renderSettings();
    if (GH.token) {
      try { state.settings = (await loadSettings()).s; renderSettings(); say("sStatus", ""); }
      catch (e) { if (!authFail(e)) say("sStatus", e.message, "bad"); }
    }
  }
  function leaveSettings() {           // leaves settings or info
    $("settingsView").hidden = true; $("infoView").hidden = true;
    $("controls").hidden = false; $("gear").hidden = false; $("infoBtn").hidden = false; syncTabs();
  }
  $("gear").onclick = () => { state.fromList = true; location.hash = "settings"; };
  $("infoBtn").onclick = () => { state.fromList = true; location.hash = "info"; };

  // ---------------------------------------------------------------- routing & data
  function route() {
    const h = decodeURIComponent(location.hash.slice(1));
    if (h === "settings") { openSettings(); return; }
    if (h === "info") { openPage("info"); return; }
    if (onPage()) { leaveSettings(); if (!h) { $("listView").hidden = false; $("back").hidden = true; $("brand").hidden = false; renderControls(); render(); return; } }
    const m = h.match(/^(.+)_(1d|4h|1h|1wk)$/);
    if (m) openDetail(m[1], m[2], false); else if (state.detail) closeDetail(); else { renderControls(); render(); }
  }
  // A page left open (a phone tab, a home-screen app) only refreshes its data. When a newer version of the
  // page has been published, reload once to pick it up — but never while something is being typed.
  const MY_UI = (document.querySelector('meta[name="sd-ui"]') || {}).content || "";
  function newerPage(idx) {
    if (!idx || !idx.ui || !MY_UI || MY_UI === "__UI__" || idx.ui === MY_UI) return false;
    if (!$("settingsView").hidden || !$("addForm").hidden) return false;
    let tried = null;
    try { tried = JSON.parse(sessionStorage.getItem("sd.reloadFor")); } catch {}
    if (tried && tried.v === idx.ui && Date.now() - tried.t < 15 * 60 * 1000) return false;   // tried already
    try { sessionStorage.setItem("sd.reloadFor", JSON.stringify({ v: idx.ui, t: Date.now() })); } catch { return false; }
    location.reload();
    return true;
  }
  async function loadIndex() {
    try {
      const r = await fetch("data/index.json?v=" + Date.now());
      if (!r.ok) throw new Error(r.status);
      state.index = await r.json();
      if (newerPage(state.index)) return;
      $("updated").textContent = "Updated " + since(state.index.generated);
      if (state.index.disclaimer) $("disclaimer").textContent = state.index.disclaimer;
    } catch (e) {
      $("updated").textContent = state.index ? "Offline" : "No data yet";
    }
  }
  $("back").onclick = () => {
    if (state.fromList) { state.fromList = false; history.back(); }
    else { history.replaceState(null, "", location.pathname + location.search);
           if (onPage()) { leaveSettings(); $("listView").hidden = false; $("back").hidden = true; $("brand").hidden = false; renderControls(); render(); }
           else closeDetail(); }
  };
  window.addEventListener("hashchange", route);
  // ---------------------------------------------------------------- theme (theme.js applies it before the page paints)
  function syncTheme() {
    const T = window.SDTheme; if (!T) return;
    for (const b of $("sTheme").children) b.setAttribute("aria-pressed", String(b.dataset.theme === T.pref()));
    $("themeBtn").setAttribute("aria-label", T.current() === "dark" ? "Switch to light theme" : "Switch to dark theme");
  }
  $("themeBtn").onclick = () => { const T = window.SDTheme; if (T) T.set(T.current() === "dark" ? "light" : "dark"); };
  $("sTheme").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b && window.SDTheme) window.SDTheme.set(b.dataset.theme); });
  document.addEventListener("sd-theme", () => { syncTheme(); if (state.detail && state.detail.t) drawChart(); });
  syncTheme();
  document.addEventListener("visibilitychange", async () => {
    if (document.visibilityState !== "visible") return;
    await loadIndex();
    if (state.detail && state.detail.t) openDetail(state.detail.ticker, state.detail.tf, true); else render();
  });
  setInterval(async () => { if (document.visibilityState === "visible" && !state.detail) { await loadIndex(); render(); } }, 5 * 60 * 1000);
  loadIndex().then(route);
})();
