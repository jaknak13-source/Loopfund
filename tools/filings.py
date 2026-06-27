"""SEC EDGAR (free). Company facts + recent filings. EDGAR requires a descriptive
User-Agent with contact info (SEC_USER_AGENT). Degrades gracefully when offline.
"""

from __future__ import annotations

import math
import re

import httpx

from core.config import env
from core.logging import get_logger
from tools.cache import DiskCache

log = get_logger("filings")
_cache = DiskCache("filings", ttl_s=12 * 3600)

# Form-4 non-derivative transaction parsing (regex; namespace-agnostic, robust to
# the raw EDGAR XML). transactionCode: P=open-market purchase, S=open-market sale,
# M=option exercise, F=tax withholding, A/G=grant — only P/S carry conviction signal.
_TXN_BLOCK = re.compile(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", re.DOTALL)
_TXN_CODE = re.compile(r"<transactionCode>\s*([A-Z])\s*</transactionCode>")
_TXN_SHARES = re.compile(r"<transactionShares>\s*<value>\s*([0-9.]+)", re.DOTALL)
_RPT_OWNER = re.compile(r"<rptOwnerName>\s*([^<]+?)\s*</rptOwnerName>")


def _parse_form4_events(xml: str) -> list[dict]:
    events = []
    for blk in _TXN_BLOCK.findall(xml):
        c = _TXN_CODE.search(blk)
        if not c:
            continue
        s = _TXN_SHARES.search(blk)
        events.append({"code": c.group(1), "shares": float(s.group(1)) if s else 0.0})
    return events


def score_insider_events(events: list[dict]) -> dict:
    """Signed conviction score in [-1,1] from Form-4 transaction codes.

    Calibrated to the documented asymmetry: open-market BUYS (P) are a strong bullish
    signal ('insiders sell for many reasons, buy for one'); open-market SALES (S) are
    mostly routine (vesting/diversification/taxes), so on their OWN they only produce a
    mild, capped bearish lean — they must not turn the fund strongly against a name.
    Routine comp codes (M=option exercise, F=tax withholding, A/G=grant) are ignored."""
    buy = sell = 0.0
    n_buys = n_sells = 0
    for e in events:
        sh = max(float(e.get("shares", 0.0)), 0.0)
        w = math.log10(sh + 10.0)  # damp huge share counts
        if e.get("code") == "P":
            buy += w
            n_buys += 1
        elif e.get("code") == "S":
            sell += w
            n_sells += 1
    if n_buys > 0:
        # buying present -> the real signal; a few sells only lightly offset it
        score = math.tanh((buy - 0.3 * sell) / 4.0)
    else:
        # sells only -> routine; mild bearish lean, capped so it can't dominate
        score = -min(0.3, math.tanh(sell / 12.0))
    return {"score": max(-1.0, min(1.0, score)), "n_buys": n_buys, "n_sells": n_sells}


def _ua() -> str:
    return env("SEC_USER_AGENT", "loopfund/0.1 contact@example.com") or "loopfund/0.1"


async def _sec_get_json(url: str, timeout: float = 30.0) -> dict:
    """GET SEC JSON with light retry on TRANSIENT errors (rate-limit 429 / 5xx / timeout).
    Hard client errors (403/404 — non-filers/ETFs) raise immediately so callers can
    negative-cache. SEC throttles hard; a couple of backed-off retries cut most of the
    `sec_financials_failed` noise without hammering."""
    import asyncio
    last: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": _ua()}) as c:
                resp = await c.get(url)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response is None or e.response.status_code not in (429, 500, 502, 503, 504):
                raise  # 403/404 etc — don't retry; caller negative-caches
            last = e
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last = e
        await asyncio.sleep(1.5 * (attempt + 1))
    assert last is not None
    raise last


async def _ticker_to_cik(ticker: str) -> str | None:
    cached = _cache.get("ticker_map")
    if cached is not None:
        mapping = cached[0]
    else:
        try:
            async with httpx.AsyncClient(timeout=20, headers={"User-Agent": _ua()}) as c:
                resp = await c.get("https://www.sec.gov/files/company_tickers.json")
                resp.raise_for_status()
                raw = resp.json()
            mapping = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in raw.values()}
            _cache.set("ticker_map", mapping)
        except Exception as exc:
            log.warning("edgar_ticker_map_failed", error=str(exc))
            stale = _cache.get("ticker_map", allow_stale=True)
            if stale is None:
                return None
            mapping = stale[0]
    return mapping.get(ticker.upper())


_GAAP_TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss"],
    "operating_income": ["OperatingIncomeLoss"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "eps_diluted": ["EarningsPerShareDiluted"],
}


def _latest_annual(facts: dict, tags: list[str]) -> tuple[float | None, list[float]]:
    """Return (latest annual value, [recent annual values newest-first]) for the first
    tag that exists. Annual = form 10-K (fp FY)."""
    for tag in tags:
        node = facts.get(tag)
        if not node:
            continue
        for unit_vals in (node.get("units") or {}).values():
            annual = [u for u in unit_vals if u.get("form") == "10-K" and u.get("fp") == "FY" and u.get("val") is not None]
            if not annual:
                annual = [u for u in unit_vals if u.get("val") is not None]
            if annual:
                annual.sort(key=lambda u: u.get("end", ""), reverse=True)
                vals = [float(u["val"]) for u in annual[:4]]
                return vals[0], vals
    return None, []


async def sec_financials(ticker: str) -> dict:
    """Real fundamentals from SEC XBRL companyfacts (US filers): revenue, margins,
    leverage, EPS, plus YoY revenue growth. Degrades gracefully (non-US -> unavailable)."""
    cik = await _ticker_to_cik(ticker)
    if cik is None:
        return {"ticker": ticker, "available": False, "reason": "no CIK (non-US or unknown)"}
    key = f"facts:{cik}"
    cached = _cache.get(key)
    if cached is not None:
        return {"ticker": ticker, "cik": cik, "financials": cached[0], "stale": cached[1], "source": "sec-xbrl"}
    try:
        data = await _sec_get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        facts = data.get("facts", {}).get("us-gaap", {})
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code in (403, 404):
            # known non-filer (ETF/fund has no XBRL companyfacts) — negative-cache the empty
            # result so we stop re-hitting SEC every cycle (was 33 benign error lines/run).
            _cache.set(key, {})
            return {"ticker": ticker, "cik": cik, "financials": {}, "available": False,
                    "reason": "no XBRL companyfacts (likely ETF/fund)", "stale": False, "source": "sec-xbrl"}
        log.warning("sec_financials_failed", ticker=ticker, error=str(exc))
        stale = _cache.get(key, allow_stale=True)
        if stale is not None:
            return {"ticker": ticker, "cik": cik, "financials": stale[0], "stale": True, "source": "sec-xbrl"}
        return {"ticker": ticker, "available": False, "error": str(exc)}
    except Exception as exc:
        log.warning("sec_financials_failed", ticker=ticker, error=str(exc))
        stale = _cache.get(key, allow_stale=True)
        if stale is not None:
            return {"ticker": ticker, "cik": cik, "financials": stale[0], "stale": True, "source": "sec-xbrl"}
        return {"ticker": ticker, "available": False, "error": str(exc)}

    fin: dict = {}
    series: dict = {}
    for name, tags in _GAAP_TAGS.items():
        latest, vals = _latest_annual(facts, tags)
        fin[name] = latest
        series[name] = vals
    rev, ni, oi = fin.get("revenue"), fin.get("net_income"), fin.get("operating_income")
    fin["net_margin"] = (ni / rev) if (rev and ni is not None and rev != 0) else None
    fin["operating_margin"] = (oi / rev) if (rev and oi is not None and rev != 0) else None
    eq, liab = fin.get("equity"), fin.get("liabilities")
    fin["debt_to_equity"] = (liab / eq) if (eq and liab is not None and eq != 0) else None
    rev_series = series.get("revenue", [])
    fin["revenue_yoy"] = ((rev_series[0] / rev_series[1] - 1.0)
                          if len(rev_series) >= 2 and rev_series[1] else None)
    _cache.set(key, fin)
    return {"ticker": ticker, "cik": cik, "financials": fin, "stale": False, "source": "sec-xbrl"}


async def recent_filings(ticker: str, limit: int = 10) -> dict:
    cik = await _ticker_to_cik(ticker)
    if cik is None:
        return {"ticker": ticker, "filings": [], "available": False, "reason": "cik not found"}
    key = f"submissions:{cik}"
    cached = _cache.get(key)
    if cached is not None:
        val, stale = cached
        return {"ticker": ticker, "cik": cik, "filings": val[:limit], "stale": stale, "source": "edgar"}
    try:
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": _ua()}) as c:
            resp = await c.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
            resp.raise_for_status()
            data = resp.json()
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accession = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        filings = [
            {"form": forms[i], "date": dates[i], "accession": accession[i], "doc": docs[i]}
            for i in range(min(len(forms), 40))
        ]
        _cache.set(key, filings)
        return {"ticker": ticker, "cik": cik, "filings": filings[:limit], "stale": False, "source": "edgar"}
    except Exception as exc:
        log.warning("edgar_failed", ticker=ticker, error=str(exc))
        stale_hit = _cache.get(key, allow_stale=True)
        if stale_hit is not None:
            return {"ticker": ticker, "cik": cik, "filings": stale_hit[0][:limit], "stale": True, "source": "edgar"}
        return {"ticker": ticker, "filings": [], "available": False, "stale": True}


async def insider_transactions(ticker: str, max_filings: int = 10) -> dict:
    """Signed insider-trading signal from recent SEC Form-4 filings (free, reliable).

    Parses open-market purchases (P, strongly bullish) vs sales (S, mildly bearish),
    ignoring routine option/comp codes. Returns a per-ticker score in [-1,1] plus the
    buyers/sellers. This is the SmartMoneyAgent's reliable spine (SEC, no key)."""
    rf = await recent_filings(ticker, limit=40)
    cik = rf.get("cik")
    if not cik or not rf.get("filings"):
        return {"ticker": ticker, "available": False, "score": 0.0,
                "n_buys": 0, "n_sells": 0, "buyers": [], "reason": rf.get("reason", "no filings")}
    form4s = [f for f in rf["filings"] if str(f.get("form", "")) == "4"][:max_filings]
    cik_int = int(cik)
    # cache the RAW parsed events (not the score) so scoring stays fresh if recalibrated
    key = f"insider_raw:{cik}:{max_filings}"
    cached = _cache.get(key)
    if cached is not None:
        events, buyers = cached[0]["events"], cached[0]["buyers"]
        stale = cached[1]
    else:
        events, buyers, stale = [], [], False
        try:
            async with httpx.AsyncClient(timeout=20, headers={"User-Agent": _ua()}) as c:
                for f in form4s:
                    acc = str(f.get("accession", "")).replace("-", "")
                    doc = str(f.get("doc", "")).split("/")[-1]  # raw XML, strip xsl wrapper dir
                    if not acc or not doc:
                        continue
                    url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{doc}"
                    try:
                        resp = await c.get(url)
                        if resp.status_code != 200:
                            continue
                        evs = _parse_form4_events(resp.text)
                        if any(e["code"] == "P" for e in evs):
                            owner = _RPT_OWNER.search(resp.text)
                            if owner:
                                buyers.append(owner.group(1))
                        events.extend(evs)
                    except Exception:
                        continue
            _cache.set(key, {"events": events, "buyers": buyers})
        except Exception as exc:
            log.warning("insider_failed", ticker=ticker, error=str(exc))
            return {"ticker": ticker, "available": False, "score": 0.0,
                    "n_buys": 0, "n_sells": 0, "buyers": []}

    scored = score_insider_events(events)
    return {"ticker": ticker, "available": True, "score": scored["score"],
            "n_buys": scored["n_buys"], "n_sells": scored["n_sells"],
            "buyers": buyers[:5], "n_filings": len(form4s), "source": "sec-form4", "stale": stale}
