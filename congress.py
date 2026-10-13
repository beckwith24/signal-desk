"""
Congressional stock trades (STOCK Act disclosures), from free public sources.

  House Stock Watcher / Senate Stock Watcher   community JSON copies of the official filings
  House Clerk (official)                       yearly index of Periodic Transaction Reports (PTRs)

Members must report a trade within 45 days, so what you can act on is the DISCLOSURE date, not the
trade date. Everything here keys off the disclosure date.

    python congress.py --probe      # which sources respond, how many trades, how recent
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import re
import zipfile
from datetime import datetime, timezone

import pandas as pd
import requests

log = logging.getLogger("congress")
UA = {"User-Agent": "signal-desk research (personal, non-commercial)"}
HOUSE_SW = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
SENATE_SW = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"
CLERK_INDEX = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
AMOUNT_LOW = re.compile(r"\$?([\d,]+)")


def _date(x) -> pd.Timestamp | None:
    if not x or not isinstance(x, str):
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return pd.Timestamp(datetime.strptime(x.strip()[:10], fmt))
        except ValueError:
            continue
    return None


def _side(t: str) -> str | None:
    t = (t or "").lower()
    if "purchase" in t or t in ("p", "buy"):
        return "buy"
    if "sale" in t or t in ("s", "s (partial)", "sell"):
        return "sell"
    return None


def _amount_low(a: str) -> float | None:
    m = AMOUNT_LOW.search(a or "")
    return float(m.group(1).replace(",", "")) if m else None


def _clean_ticker(t) -> str | None:
    t = (t or "").strip().upper().replace(".", "-")
    return t if re.fullmatch(r"[A-Z]{1,5}(-[A-Z])?", t or "") else None


def house_watcher() -> pd.DataFrame:
    r = requests.get(HOUSE_SW, headers=UA, timeout=60)
    r.raise_for_status()
    rows = []
    for x in r.json():
        rows.append({"chamber": "House", "member": x.get("representative"), "ticker": _clean_ticker(x.get("ticker")),
                     "side": _side(x.get("type")), "traded": _date(x.get("transaction_date")),
                     "disclosed": _date(x.get("disclosure_date")), "amount_low": _amount_low(x.get("amount")),
                     "owner": x.get("owner")})
    return pd.DataFrame(rows)


def senate_watcher() -> pd.DataFrame:
    r = requests.get(SENATE_SW, headers=UA, timeout=60)
    r.raise_for_status()
    rows = []
    for x in r.json():
        rows.append({"chamber": "Senate", "member": x.get("senator"), "ticker": _clean_ticker(x.get("ticker")),
                     "side": _side(x.get("type")), "traded": _date(x.get("transaction_date")),
                     "disclosed": _date(x.get("disclosure_date") or x.get("date_recieved") or x.get("date_received")),
                     "amount_low": _amount_low(x.get("amount")), "owner": x.get("owner")})
    return pd.DataFrame(rows)


def clerk_index(year: int) -> pd.DataFrame:
    """Official House index: one row per filing (PTRs are FilingType 'P')."""
    r = requests.get(CLERK_INDEX.format(year=year), headers=UA, timeout=60)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    name = next(n for n in z.namelist() if n.lower().endswith(".txt"))
    df = pd.read_csv(io.BytesIO(z.read(name)), sep="\t", dtype=str)
    return df


# ----------------------------------------------------------------------------- official House PTRs
PTR_PDF = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc}.pdf"
ROW = re.compile(
    r"\(([A-Z][A-Z0-9.\-]{0,6})\)\s*\[([A-Z]{2})\]\s*(?:[A-Z]{1,2}\s+)?(P|S \(partial\)|S|E)\s+"
    r"(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(\$[\d,]+(?:\s*-\s*\$[\d,]+)?|Over \$[\d,]+)")


TYPE_DATES = re.compile(r"(?:^|\s)(P|S \(partial\)|S|E)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(\$[\d,]+|Over \$[\d,]+)")
TICKER = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,6})\)\s*\[([A-Z]{2})\]")
BLOCK_END = re.compile(r"F\s+S\s*:\s*[A-Za-z]+")


def parse_house_ptr(text: str) -> list[dict]:
    """Transactions from an electronic House PTR's text. Stocks ([ST]) only.

    Each transaction ends with a "Filing Status: New" line. Inside a block the ticker can come before
    the type/dates (older layout) or after them on the next line (layout used since 2024).
    """
    t = text.replace("\x00", " ")
    out = []
    blocks = BLOCK_END.split(t) if BLOCK_END.search(t) else [t]
    for b in blocks:
        b1 = re.sub(r"\s+", " ", b)
        m, k = TYPE_DATES.search(b1), TICKER.search(b1)
        if not (m and k) or k.group(2) != "ST":
            continue
        typ, tdate, _notified, amt = m.groups()
        out.append({"ticker": _clean_ticker(k.group(1)),
                    "side": "buy" if typ == "P" else ("sell" if typ.startswith("S") else None),
                    "traded": _date(tdate), "amount_low": _amount_low(amt)})
    return out


def house_ptrs(years: list[int], skip_docs: set[str] | None = None, workers: int = 4) -> tuple[pd.DataFrame, dict]:
    import pdfplumber
    from concurrent.futures import ThreadPoolExecutor
    skip_docs = skip_docs or set()
    jobs = []
    for y in years:
        idx = clerk_index(y)
        idx = idx[idx["FilingType"] == "P"]
        for _, r in idx.iterrows():
            doc = str(r["DocID"]).strip()
            if doc in skip_docs:
                continue
            jobs.append((y, doc, f"{str(r.get('First') or '').strip()} {str(r.get('Last') or '').strip()}".strip(),
                         _date(str(r["FilingDate"]))))
    stats = {"filings": len(jobs), "parsed": 0, "no_text": 0, "errors": 0}

    def one(job):
        y, doc, member, filed = job
        try:
            r = requests.get(PTR_PDF.format(year=y, doc=doc), headers=UA, timeout=40)
            if not r.ok:
                return "err", []
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
            if len(text.strip()) < 50:
                return "no_text", []                       # scanned paper filing
            rows = parse_house_ptr(text)
            for x in rows:
                x.update(chamber="House", member=member, disclosed=filed, doc=doc)
            return "ok", rows
        except Exception:
            return "err", []

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for status, rs in pool.map(one, jobs):
            stats["parsed" if status == "ok" else ("no_text" if status == "no_text" else "errors")] += 1
            rows += rs
    return pd.DataFrame(rows), stats


# ----------------------------------------------------------------------------- official Senate PTRs (eFD)
EFD = "https://efdsearch.senate.gov"


def senate_ptrs(since: str = "01/01/2018", skip_docs: set[str] | None = None, workers: int = 4) -> tuple[pd.DataFrame, dict]:
    from concurrent.futures import ThreadPoolExecutor
    skip_docs = skip_docs or set()
    s = requests.Session()
    s.headers.update(UA)
    home = s.get(f"{EFD}/search/home/", timeout=30)
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', home.text).group(1)
    s.post(f"{EFD}/search/home/", data={"csrfmiddlewaretoken": token, "prohibition_agreement": "1"},
           headers={"Referer": f"{EFD}/search/home/"}, timeout=30)
    csrf = s.cookies.get("csrftoken")
    reports, start = [], 0
    while True:
        r = s.post(f"{EFD}/search/report/data/", timeout=60, headers={"Referer": f"{EFD}/search/", "X-CSRFToken": csrf},
                   data={"start": start, "length": 100, "report_types": "[11]", "filer_types": "[]",
                         "submitted_start_date": f"{since} 00:00:00", "submitted_end_date": "", "candidate_state": "",
                         "senator_state": "", "office_id": "", "first_name": "", "last_name": "",
                         "csrfmiddlewaretoken": csrf})
        d = r.json()
        batch = d.get("data", [])
        reports += batch
        start += len(batch)
        if not batch or start >= int(d.get("recordsTotal", 0)):
            break
    jobs = []
    for first, last, _office, link, filed in reports:
        m = re.search(r'href="(/search/view/(ptr|paper)/([^/]+)/)"', link)
        if not m:
            continue
        jobs.append((m.group(1), m.group(2), m.group(3), f"{first} {last}".strip(), _date(filed)))
    stats = {"filings": len(jobs), "paper": sum(1 for j in jobs if j[1] == "paper"), "parsed": 0, "errors": 0}

    def one(job):
        path, kind, doc, member, filed = job
        if kind != "ptr" or doc in skip_docs:
            return "skip", []
        try:
            page = s.get(EFD + path, timeout=40, headers={"Referer": f"{EFD}/search/"})
            tables = pd.read_html(io.StringIO(page.text))
            if not tables:
                return "err", []
            t = tables[0]
            t.columns = [str(c).strip().lower() for c in t.columns]
            rows = []
            for _, r in t.iterrows():
                if "stock" not in str(r.get("asset type", "")).lower():
                    continue
                rows.append({"ticker": _clean_ticker(str(r.get("ticker", ""))), "side": _side(str(r.get("type", ""))),
                             "traded": _date(str(r.get("transaction date", ""))), "amount_low": _amount_low(str(r.get("amount", ""))),
                             "chamber": "Senate", "member": member, "disclosed": filed, "doc": doc})
            return "ok", rows
        except Exception:
            return "err", []

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for status, rs in pool.map(one, jobs):
            if status == "ok":
                stats["parsed"] += 1
            elif status == "err":
                stats["errors"] += 1
            rows += rs
    return pd.DataFrame(rows), stats


def load_trades() -> tuple[pd.DataFrame, dict]:
    """All usable trades (stock tickers, buy/sell, with a disclosure date). Also reports source status."""
    frames, status = [], {}
    for name, fn in (("House Stock Watcher", house_watcher), ("Senate Stock Watcher", senate_watcher)):
        try:
            df = fn()
            ok = df.dropna(subset=["ticker", "side", "disclosed"])
            status[name] = {"ok": True, "rows": int(len(df)), "usable": int(len(ok)),
                            "latest_disclosure": str(ok["disclosed"].max().date()) if len(ok) else None,
                            "earliest": str(ok["disclosed"].min().date()) if len(ok) else None}
            frames.append(ok)
        except Exception as e:
            status[name] = {"ok": False, "error": str(e)[:120]}
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return df, status


# ----------------------------------------------------------------------------- cache used by the app
from functools import lru_cache
from pathlib import Path

CACHE = Path(__file__).with_name("research") / "congress_trades.csv.gz"


def update() -> dict:
    """Add newly filed reports to the cache (daily job). Only new filings are downloaded."""
    old = pd.read_csv(CACHE, parse_dates=["traded", "disclosed"]) if CACHE.exists() else pd.DataFrame()
    seen = set(old["doc"].astype(str)) if len(old) else set()
    now = datetime.now()
    years = [now.year - 1, now.year] if now.month <= 2 else [now.year]
    stats = {}
    house, stats["house"] = house_ptrs(years, skip_docs=seen)
    since = (old["disclosed"].max() - pd.Timedelta(days=20)).strftime("%m/%d/%Y") if len(old) else "01/01/2018"
    try:
        senate, stats["senate"] = senate_ptrs(since, skip_docs=seen)
    except Exception as e:
        senate, stats["senate"] = pd.DataFrame(), {"error": str(e)[:150]}
    df = pd.concat([x for x in (old, house, senate) if len(x)], ignore_index=True)
    df = df.dropna(subset=["ticker", "side", "disclosed"])
    df["disclosed"] = pd.to_datetime(df["disclosed"])
    df["traded"] = pd.to_datetime(df["traded"], errors="coerce")
    df = df.drop_duplicates(subset=["chamber", "member", "ticker", "side", "traded", "disclosed", "amount_low"])
    CACHE.parent.mkdir(exist_ok=True)
    df.sort_values("disclosed").to_csv(CACHE, index=False, compression="gzip")
    stats.update(total=int(len(df)), added=int(len(df) - len(old)), latest=str(df["disclosed"].max().date()))
    return stats


@lru_cache(maxsize=1)
def _cached() -> pd.DataFrame:
    try:
        return pd.read_csv(CACHE, parse_dates=["traded", "disclosed"])
    except Exception:
        return pd.DataFrame(columns=["ticker", "side", "traded", "disclosed", "amount_low", "member", "chamber"])


def recent_for(ticker: str, days: int = 365, limit: int = 12) -> list[dict]:
    """Disclosed congressional trades in this stock over the last `days`, newest first."""
    df = _cached()
    if df.empty:
        return []
    t = ticker.upper()
    cut = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
    sub = df[(df["ticker"] == t) & (df["disclosed"] >= cut)].sort_values("disclosed", ascending=False).head(limit)
    return [{"member": str(r.member), "chamber": str(r.chamber), "side": str(r.side),
             "traded": None if pd.isna(r.traded) else str(r.traded.date()), "disclosed": str(r.disclosed.date()),
             "amount_low": None if pd.isna(r.amount_low) else float(r.amount_low)} for r in sub.itertuples()]


def probe() -> dict:
    trades, status = load_trades()
    for year in (2025, 2026):
        try:
            idx = clerk_index(year)
            ptr = idx[idx.get("FilingType", pd.Series(dtype=str)) == "P"] if "FilingType" in idx else idx
            status[f"House Clerk index {year}"] = {"ok": True, "filings": int(len(idx)), "ptrs": int(len(ptr)),
                                                   "columns": list(idx.columns)[:12],
                                                   "latest_filing": str(pd.to_datetime(ptr.get("FilingDate"), errors="coerce").max())}
        except Exception as e:
            status[f"House Clerk index {year}"] = {"ok": False, "error": str(e)[:120]}
    try:
        r = requests.get("https://efdsearch.senate.gov/search/home/", headers=UA, timeout=30)
        status["Senate eFD site"] = {"ok": r.ok, "status": r.status_code}
    except Exception as e:
        status["Senate eFD site"] = {"ok": False, "error": str(e)[:120]}
    return {"checked": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "sources": status,
            "usable_trades": int(len(trades))}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()
    if a.update:
        print(json.dumps(update(), indent=1))
    if a.debug:                     # save raw text of a few recent House PTRs to tune the parser
        import pdfplumber
        out = []
        for y in (2024, 2026):
            idx = clerk_index(y)
            for _, r in idx[idx["FilingType"] == "P"].tail(4).iterrows():
                doc = str(r["DocID"]).strip()
                b = requests.get(PTR_PDF.format(year=y, doc=doc), headers=UA, timeout=40).content
                with pdfplumber.open(io.BytesIO(b)) as pdf:
                    text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
                out.append(f"===== {y} {doc} ({len(text)} chars, parsed {len(parse_house_ptr(text))} rows)\n{text[:2500]}")
        from pathlib import Path as _P
        _P("research").mkdir(exist_ok=True)
        _P("research/congress_debug.txt").write_text("\n\n".join(out))
    if a.probe:
        res = probe()
        print(json.dumps(res, indent=1))
        from pathlib import Path
        Path("research").mkdir(exist_ok=True)
        Path("research/congress_probe.json").write_text(json.dumps(res, indent=1))
