"""Credible-source allowlist + corroboration helpers.

docs/STRATEGY.md House Rule #2 lets >=2 distinct credible SECONDARY sources corroborate a
trade (no primary needed for a small position). Until now nothing marked reputable
news as credible, so that rule was structurally unreachable. This module gives a
code-controlled allowlist of reputable domains and a helper to extract the registrable
domain from a URL, so corroboration can be counted in code rather than guessed by the
LLM from text it is told to distrust.
"""

from __future__ import annotations

from urllib.parse import urlparse

# Reputable financial / official domains. First-party (filings/exchanges/regulators)
# are PRIMARY; the rest are credible SECONDARY sources that can corroborate.
PRIMARY_DOMAINS: frozenset[str] = frozenset({
    "sec.gov", "federalreserve.gov", "ecb.europa.eu", "bls.gov", "bea.gov",
    "treasury.gov", "imf.org", "worldbank.org", "europa.eu",
})

SECONDARY_DOMAINS: frozenset[str] = frozenset({
    # reputable financial press
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com",
    "marketwatch.com", "barrons.com", "economist.com", "nytimes.com",
    "apnews.com", "forbes.com", "businessinsider.com", "seekingalpha.com",
    "morningstar.com", "yahoo.com", "finance.yahoo.com", "investing.com",
    "nasdaq.com", "spglobal.com", "fitchratings.com", "moodys.com",
    "axios.com", "theguardian.com", "bbc.com", "cnn.com", "fortune.com",
    "kitco.com", "tradingeconomics.com",
    # banks / asset managers — their published research, outlooks and notes are credible
    "morganstanley.com", "goldmansachs.com", "gs.com", "jpmorgan.com",
    "jpmorganchase.com", "blackrock.com", "vanguard.com", "fidelity.com",
    "schwab.com", "pimco.com", "ubs.com", "credit-suisse.com", "barclays.com",
    "citigroup.com", "citi.com", "bankofamerica.com", "ml.com", "wellsfargo.com",
    "hsbc.com", "db.com", "nomura.com", "rbc.com", "tdsecurities.com",
    "statestreet.com", "invesco.com", "franklintempleton.com", "apollo.com",
    "kkr.com", "blackstone.com", "lazard.com", "jefferies.com",
})

CREDIBLE_DOMAINS: frozenset[str] = PRIMARY_DOMAINS | SECONDARY_DOMAINS


def registrable_domain(url: str) -> str:
    """Best-effort registrable domain (last two labels) from a URL or bare host."""
    if not url:
        return ""
    host = urlparse(url if "//" in url else f"//{url}").netloc or url
    host = host.split("@")[-1].split(":")[0].strip().lower()
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _is_real_url(url: str) -> bool:
    """Require an actual http(s) URL, not a bare/self-reported string. This blocks
    spoofing the credibility check with a plain 'reuters.com' source label; only a real
    fetched link counts toward verified corroboration."""
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def is_credible(url: str | None) -> bool:
    """True only if `url` is a real http(s) URL whose host is an allowlisted reputable domain."""
    if not url or not _is_real_url(url):
        return False
    return registrable_domain(url) in CREDIBLE_DOMAINS


def is_primary(url: str | None) -> bool:
    if not url or not _is_real_url(url):
        return False
    return registrable_domain(url) in PRIMARY_DOMAINS
