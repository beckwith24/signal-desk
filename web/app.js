// Refuse to run inside someone else's frame (stops click-tricking on the settings screen).
if (window.top !== window.self) { document.documentElement.style.display = "none"; throw new Error("framed"); }
(() => {
  "use strict";
  const TF_LABEL = { "1d": "Daily", "4h": "4H", "1h": "1H", "1wk": "Weekly" };
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
    view: "list",                       // list | signals: which list page is showing (or was, under a chart)
    level: "signals",                   // Signals page filter: signals | strong | buy | sell
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
    if (!state.detail) state.tf = "1d";                 // the lists are daily only
    if (!tfs.includes(state.tf)) state.tf = tfs[0];
    $("controls").hidden = !state.detail;
    seg.hidden = !state.detail || tfs.length < 2;
    for (const tf of tfs) {
      const b = el("button", null, TF_LABEL[tf] || tf);
      b.type = "button"; b.setAttribute("aria-pressed", String(tf === state.tf));
      b.onclick = () => { state.tf = tf; store.set("tf", tf); if (state.detail) openDetail(state.detail.ticker, tf, true); renderControls(); };
      seg.append(b);
    }
  }
  function setView(v) { document.body.dataset.view = v; }

  // ---------------------------------------------------------------- shared bits
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
  const hrefFor = (i) => "#" + (i.ticker + "_" + i.tf).replace(/[^A-Za-z0-9_.-]/g, "_");
  const short = (t) => t.replace("-USD", "");
  const pct = (x) => (x > 0 ? "+" : "") + x.toFixed(1) + "%";
  function congressText(c) {
    const parts = [];
    if (c.buys) parts.push(c.buys + " buy" + (c.buys > 1 ? "s" : ""));
    if (c.sells) parts.push(c.sells + " sell" + (c.sells > 1 ? "s" : ""));
    return parts.join(", ");
  }
  const LT = { up: ["Uptrend", "↑"], down: ["Downtrend", "↓"], mixed: ["Mixed", "↔"] };
  const ltWord = (lt) => lt && LT[lt.state] ? LT[lt.state][0] : null;
  const ltWeeks = (lt) => !lt ? "" : lt.weeks != null ? lt.weeks + " wk" + (lt.weeks === 1 ? "" : "s") : "2+ yrs";
  function ltTag(lt) {
    if (!lt || !LT[lt.state]) return null;
    const s = el("span", "ltag " + lt.state, "Weekly " + LT[lt.state][1]);
    s.title = "Long-term (weekly) trend: " + LT[lt.state][0] + (lt.state !== "mixed" ? " for " + ltWeeks(lt) : "");
    return s;
  }
  function renderMarket(all) {          // S&P 500 / Nasdaq long-term trend, from SPY and QQQ's weekly view
    const m = $("market"); m.textContent = "";
    const parts = [["SPY", "S&P 500"], ["QQQ", "Nasdaq"]].map(([t, n]) => [t, n, all.find((i) => i.ticker === t)]).filter((p) => p[2] && p[2].lt);
    m.hidden = !parts.length;
    if (!parts.length) return;
    const states = parts.map((p) => p[2].lt.state);
    m.className = "market " + (states.includes("down") ? "down" : states.every((s) => s === "up") ? "up" : "mixed");
    m.append(el("span", "mk-k", "Market, long-term (weekly)"));
    for (const [t, n, i] of parts) {
      const a = el("a", "mk-v " + i.lt.state, n + " " + LT[i.lt.state][1] + " " + LT[i.lt.state][0].toLowerCase() +
        (i.lt.state !== "mixed" ? " · " + ltWeeks(i.lt) : ""));
      a.href = "#" + t + "_1wk"; a.onclick = () => { state.fromList = true; };
      m.append(a);
    }
    if (states.includes("down")) m.append(el("span", "mk-note", "Past long-term downtrends held the worst crashes; dip-buys were riskier then."));
  }
  const byStrength = (a, b) => b.rank - a.rank || Math.abs(b.score - 50) - Math.abs(a.score - 50) || a.ticker.localeCompare(b.ticker);
  const GROUPS = [["stock", "Stocks"], ["crypto", "Crypto"]];

  // ---------------------------------------------------------------- Watchlist: everything, one line each
  function watchRow(i) {
    const li = el("li");
    const b = el("button", "item wrow " + stripe(i.rank)); b.type = "button";
    const id = el("div", "id");
    const st = el("div", "st");
    if (i.models && i.models.length) {            // one dot per model: filled = says buy
      const dots = el("span", "dots");
      for (const m of i.models) dots.append(el("i", m.v > 0 ? "up" : m.v < 0 ? "down" : ""));
      dots.title = i.models.map((m) => m.s + ": " + (m.v > 0 ? "buy" : m.v < 0 ? "sell" : "no")).join(" · ");
      st.append(dots);
    }
    const cls = i.rank > 0 ? "up" : i.rank < 0 ? "down" : "hold";
    st.append(el("span", "word " + cls, i.action));
    const lt = ltTag(i.lt); if (lt) st.append(lt);
    if (i.congress) { const g = el("span", "gov", "🏛"); g.title = "Congress: " + congressText(i.congress) + " reported in the last 30 days"; st.append(g); }
    id.append(el("span", "tk", short(i.ticker)), st);
    const px = el("div", "px"); px.append(el("div", "p", fmtPrice(i.price, i.decimals)), fmtChg(i.change_pct));
    b.append(id, spark(i.spark, i.spark_pct), px);
    b.onclick = () => { state.fromList = true; location.hash = hrefFor(i); };
    li.append(b);
    return li;
  }
  function renderWatchlist(all, box) {
    $("pageTitle").textContent = "Watchlist";
    const ns = all.filter((i) => i.asset === "stock").length, nc = all.length - ns;
    $("pageSub").textContent = ns + " stocks · " + nc + " crypto · tap one for its chart";
    const present = GROUPS.filter(([a]) => all.some((i) => i.asset === a));
    if (present.length === 1) box.className = "single";
    for (const [asset, title] of present) {
      const items = all.filter((i) => i.asset === asset).sort(byStrength);
      const sec = el("section", "group");
      const h = el("h2", "group-h", title); h.append(el("span", "c", String(items.length)));
      const ul = el("ul", "list");
      for (const i of items) ul.append(watchRow(i));
      if (present.length === 1 && items.length % 2) ul.append(el("li", "filler"));   // keeps the 2-column grid even on wide screens
      sec.append(h, ul); box.append(sec);
    }
  }

  // ---------------------------------------------------------------- Signals: only tickers with a signal, with the detail
  function fact(box, k, v, sub) {
    const d = el("div"); const val = el("span", "v", v);
    if (sub) val.append(" ", el("small", null, sub));
    d.append(el("span", "k", k), val); box.append(d);
  }
  function signalCard(i, stats) {
    const li = el("li");
    const a = el("a", "scard " + stripe(i.rank)); a.href = hrefFor(i);
    a.onclick = () => { state.fromList = true; };
    const top = el("div", "sc-top");
    const left = el("div");
    const idr = el("div", "sc-id"); idr.append(el("span", "tk", short(i.ticker)), pill(i.action));
    left.append(idr);
    const sinceEl = el("div", "sc-since");
    if (i.since && i.since.ts) {
      const t = Date.parse(i.since.ts.replace(" UTC", "Z").replace(" ", "T"));
      const day = isNaN(t) ? i.since.ts : new Date(t).toLocaleDateString(LOC, { month: "short", day: "numeric" });
      sinceEl.append("Since ", el("b", null, day));
      if (i.since.price) {
        const move = (i.price / i.since.price - 1) * 100;
        sinceEl.append(" at " + fmtPrice(i.since.price, i.decimals) + " · ", el("b", null, pct(move)), " since");
      }
    } else sinceEl.textContent = (i.asset === "crypto" ? "Crypto" : "Stock") + " · daily signal";
    left.append(sinceEl);
    const px = el("div", "sc-px"); px.append(el("div", "p", fmtPrice(i.price, i.decimals)), fmtChg(i.change_pct));
    top.append(left, px);
    a.append(top, spark(i.spark, i.spark_pct));
    if (i.models && i.models.length) {           // every model's reading, in words
      const on = i.models.filter((m) => m.v > 0).length;
      a.append(el("div", "sc-label", on + " of " + i.models.length + " models say buy"));
      const ul = el("ul", "sc-models");
      for (const m of i.models) {
        const row = el("li", m.v > 0 ? "up" : m.v < 0 ? "down" : "flat");
        const txt = el("div"); txt.append(el("b", null, m.s), el("span", null, m.r));
        row.append(el("i"), txt); ul.append(row);
      }
      a.append(ul);
    }
    const facts = el("div", "sc-facts");
    if (i.risk && i.risk.size != null) {
      fact(facts, "Suggested size", i.risk.size >= 0.95 ? "Normal" : i.risk.size.toFixed(2).replace(/0$/, "") + "× normal",
        "swings " + i.risk.vol_pct + "%/yr");
    }
    const nx = i.next || {};
    if (nx.add) fact(facts, "Next add", fmtPrice(nx.add.price, i.decimals), pct((nx.add.price / i.price - 1) * 100));
    else if (i.next) fact(facts, "Next add", "All layers hit");
    if (nx.trim) fact(facts, "Next trim", fmtPrice(nx.trim.price, i.decimals), pct((nx.trim.price / i.price - 1) * 100));
    if (i.ia) fact(facts, "IA view", (i.ia.trend === "up" ? "Blue" : "Orange") + " · ATR " + i.ia.stop_side);
    if (i.lt) fact(facts, "Long-term (weekly)", ltWord(i.lt), i.lt.state !== "mixed" ? ltWeeks(i.lt) : "");
    if (facts.childNodes.length % 2) fact(facts, "Score", i.score + " / 100");
    if (facts.childNodes.length) a.append(facts);
    const st = stats && stats[i.asset] && stats[i.asset][i.action];
    if (st && st.x5 != null) {                   // how this level did in testing (2021 on)
      const n = el("p", "sc-note");
      n.append("Past " + (i.asset === "crypto" ? "crypto" : "stock") + " " + i.action + "s (2021–26): ",
        el("b", null, pct(st.x5)), " vs normal over 5 days; higher 5 days later ", el("b", null, Math.round(st.win5) + "%"), " of the time.");
      a.append(n);
    }
    if (i.congress) a.append(el("p", "sc-note", "🏛 Congress: " + congressText(i.congress) + " reported in the last 30 days (information only)."));
    a.append(el("span", "sc-open", "Open chart ›"));
    li.append(a);
    return li;
  }
  const EMPTY = { strong: "No Strong Buys", buy: "No Buys", sell: "No Sells", signals: "No signals" };
  function renderSignals(all, box) {
    $("pageTitle").textContent = "Signals";
    const sig = all.filter(LEVELS.signals);
    $("pageSub").textContent = sig.length ? "Each signal with the reasons behind it" : "Nothing is signalling today";
    const tiles = $("tiles");
    const count = (k) => all.filter(LEVELS[k]).length;
    const defs = [["strong", "Strong Buy", count("strong")], ["buy", "Buy", count("buy")]];
    if (count("sell")) defs.push(["sell", "Sell", count("sell")]);      // only shown when there are any
    defs.push(["signals", "All signals", sig.length]);
    tiles.style.setProperty("--n", defs.length);
    for (const [k, label, n] of defs) {
      const t = el("button", "tile " + k); t.type = "button";
      t.setAttribute("aria-pressed", String(state.level === k));
      t.append(el("span", "n", String(n)), el("span", "l", label));
      t.onclick = () => { state.level = state.level === k ? "signals" : k; render(); };
      tiles.append(t);
    }
    const keep = LEVELS[state.level] || LEVELS.signals;
    const stats = (state.index && state.index.stats) || {};
    const present = GROUPS.filter(([a]) => all.some((i) => i.asset === a));
    if (present.length === 1) box.className = "single";
    for (const [asset, title] of present) {
      const items = all.filter((i) => i.asset === asset && keep(i)).sort(byStrength);
      const sec = el("section", "group");
      const h = el("h2", "group-h", title); h.append(el("span", "c", String(items.length)));
      const ul = el("ul", "cards");
      if (!items.length) ul.append(el("li", "none", (EMPTY[state.level] || "Nothing") + " in " + title.toLowerCase() + " today."));
      for (const i of items) ul.append(signalCard(i, stats));
      sec.append(h, ul); box.append(sec);
    }
  }

  function render() {
    const box = $("list"); box.textContent = ""; box.className = "";
    $("tiles").textContent = "";
    const sigView = state.view === "signals";
    $("tiles").hidden = !sigView; $("keyBar").hidden = !sigView;
    $("addToggle").hidden = sigView; if (sigView) $("addForm").hidden = true;
    syncTabs();
    const idx = state.index;
    if (!idx || !idx.items.length) {
      $("pageTitle").textContent = sigView ? "Signals" : "Watchlist"; $("pageSub").textContent = "";
      const e = el("div", "empty");
      e.append(el("h2", null, "No charts yet"), el("div", null, "Charts appear after the next scan publishes them."));
      box.append(e); return;
    }
    const all = idx.items.filter((i) => i.tf === "1d");
    renderMarket(all);
    if (sigView) renderSignals(all, box); else renderWatchlist(all, box);
  }
  function syncTabs() {
    const cur = !$("settingsView").hidden ? "settings" : !$("infoView").hidden ? "info" : state.view;
    for (const b of document.querySelectorAll("#tabbar button, #topnav button")) {
      if (b.dataset.tab === cur) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
    }
    const n = ((state.index && state.index.items) || []).filter((i) => i.tf === "1d" && i.rank >= 2).length;
    for (const id of ["tabBadge", "navBadge"]) { const badge = $(id); badge.hidden = !n; badge.textContent = String(n); }
  }
  function showList(view) {              // Watchlist or Signals page
    state.view = view;
    if (onPage()) leaveSettings();
    state.detail = null; if (state.chart) { state.chart.remove(); state.chart = null; }
    $("detailView").hidden = true; $("listView").hidden = false;
    $("back").hidden = true; $("brand").hidden = false;
    setView(view); renderControls(); render();
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
  const TAB_HASH = { list: "", signals: "signals", info: "info", settings: "settings" };
  for (const b of document.querySelectorAll("#tabbar button, #topnav button")) {
    b.onclick = () => {
      const t = b.dataset.tab, want = TAB_HASH[t];
      if (t === "signals" && state.view === "signals" && !state.detail && !onPage()) { state.level = "signals"; }
      if (location.hash.slice(1) !== want) { state.fromList = t === "info" || t === "settings"; location.hash = want; }
      else if (t === "list" || t === "signals") showList(t);
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
    $("back").hidden = false; $("brand").hidden = true; setView("detail");
    $("back").textContent = "‹ " + (state.view === "signals" ? "Signals" : "Watchlist");
    renderControls(); syncTabs();
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
    const dailyItem = ((state.index && state.index.items) || []).find((i) => i.ticker === d.ticker && i.tf === "1d");
    const lt = d.long_term || (dailyItem && dailyItem.lt);
    if (d.tf === "1d") {
      statBox("Models", txt(d.bull + " buy · " + d.bear + " sell"));
      statBox("Weekly trend", txt(lt && LT[lt.state] ? LT[lt.state][1] + " " + (lt.state === "mixed" ? "Mixed" : ltWord(lt) === "Uptrend" ? "Up · " + ltWeeks(lt) : "Down · " + ltWeeks(lt)) : "–"));
    } else if (d.tf === "1wk") {
      statBox("Long-term", txt(lt && LT[lt.state] ? LT[lt.state][1] + " " + (lt.state === "mixed" ? "Mixed" : ltWord(lt) === "Uptrend" ? "Up · " + ltWeeks(lt) : "Down · " + ltWeeks(lt)) : "–"));
      statBox("40-week avg", txt(lt && lt.above_40w != null ? (lt.above_40w ? "Price above" : "Price below") : "–"));
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
    renderNote(d);
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

  let notesP = null;
  function loadNotes() {
    if (!notesP) notesP = fetch("data/notes.json?v=" + new Date().toISOString().slice(0, 13)).then((r) => r.ok ? r.json() : null).catch(() => null);
    return notesP;
  }
  async function renderNote(d) {
    const box = $("dNote"), card = $("cNote"); box.textContent = ""; card.hidden = true;
    const all = await loadNotes();
    if (!state.detail || state.detail.ticker !== d.ticker) return;          // user moved on
    const n = all && all.notes && all.notes[d.ticker];
    if (!n || !(n.text && n.text.length)) return;
    n.text.forEach((s, k) => box.append(el("p", k === 2 ? "read" : null, s)));
    if (n.extra) box.append(el("p", "extra", n.extra.charAt(0).toUpperCase() + n.extra.slice(1) + "."));
    if (n.news && n.news.length) {
      const ul = el("ul", "news");
      for (const h of n.news) {
        if (!/^https?:\/\//.test(h.url)) continue;
        const li = el("li"), a = el("a", null, h.title); a.href = h.url; a.target = "_blank"; a.rel = "noopener noreferrer";
        li.append(a, el("small", null, [h.source, h.date].filter(Boolean).join(" · "))); ul.append(li);
      }
      if (ul.childNodes.length) box.append(ul);
    }
    box.append(el("div", "asof", "Built from Yahoo Finance data and headlines, " + since(all.generated) + ". Not advice."));
    card.hidden = false;
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
    if (onPage()) leaveSettings();
    state.detail = { ticker }; $("listView").hidden = true; $("detailView").hidden = false;
    $("dRemove").hidden = true; $("cNote").hidden = true; setView("detail");
    $("back").textContent = "‹ " + (state.view === "signals" ? "Signals" : "Watchlist");
    $("back").hidden = false; $("brand").hidden = true; renderControls();
    $("dTitle").textContent = ticker.replace("-USD", "");
    $("dAsset").innerHTML = ""; $("dAsset").append(el("span", "err", "No " + (TF_LABEL[tf] || tf) + " chart for this ticker yet."));
    for (const id of ["dPrice", "dChg", "dPill", "dStats", "dReasons", "dSize", "dCongress", "dCongressNote", "dIA", "dIANote", "dLadder", "dLadderNow", "dAbout", "dModels", "dHist", "dFoot", "legend"]) $(id).textContent = "";
    if (state.chart) { state.chart.remove(); state.chart = null; }
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
        if (w.stocks.length + w.crypto.length >= 70) throw new Error("Your list is full (70). Remove a ticker first.");
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
    $("back").textContent = "‹ Back"; $("gear").hidden = name === "settings";
    setView(name); syncTabs(); window.scrollTo(0, 0);
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
    $("gear").hidden = false; renderControls(); syncTabs();
  }
  $("gear").onclick = () => { state.fromList = true; location.hash = "settings"; };

  // ---------------------------------------------------------------- routing & data
  function route() {
    const h = decodeURIComponent(location.hash.slice(1));
    if (h === "settings") { openSettings(); return; }
    if (h === "info") { openPage("info"); return; }
    const m = h.match(/^(.+)_(1d|4h|1h|1wk)$/);
    if (m) { openDetail(m[1], m[2], false); return; }
    showList(h === "signals" ? "signals" : "list");
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
    else { history.replaceState(null, "", location.pathname + location.search + (state.view === "signals" ? "#signals" : ""));
           showList(state.view); }
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
