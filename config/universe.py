"""Tradable universe — a broad candidate list across asset classes. Agents do NOT
price all of these every cycle; instead the orchestrator samples a rotating subset
each cycle (plus held positions and any tickers agents propose), so over time the
fund researches the whole universe — large, mid, AND small caps — without pricing
thousands of symbols at once. Any ticker can be priced on demand via the `price`
tool, and agents can grow this list with `propose_ticker`.

yfinance symbology: crypto = BTC-USD, FX = EURUSD=X, futures = CL=F (WTI), etc.
"""

from __future__ import annotations

import json

from core.config import data_dir

# --- Equities: mega/large cap across sectors ---
MEGA_LARGE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ORCL", "AMD",
    "CRM", "ADBE", "NFLX", "INTC", "QCOM", "TXN", "IBM", "NOW", "INTU", "PANW",
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "V", "MA", "AXP", "PYPL",
    "BRK-B", "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "ABT", "DHR", "BMY",
    "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "MPC", "OXY", "WMB", "KMI",
    "WMT", "COST", "PG", "KO", "PEP", "MCD", "NKE", "SBUX", "HD", "LOW", "TGT",
    "BA", "CAT", "GE", "HON", "UPS", "RTX", "LMT", "DE", "UNP", "MMM",
    "DIS", "CMCSA", "T", "VZ", "TMUS", "LIN", "CVS", "PM", "AMT", "NEE",
]

# --- Semiconductors & memory (the NVDA->memory supply-chain theme) ---
SEMI_MEMORY = [
    "MU", "WDC", "STX", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "MRVL", "ON",
    "MCHP", "NXPI", "ADI", "SWKS", "TER", "ENTG", "ARM", "SMCI", "DELL", "ANET",
]

# --- High-growth / newer / more volatile / "startup-y" public names ---
GROWTH_SPEC = [
    "PLTR", "SNOW", "CRWD", "DDOG", "NET", "ZS", "MDB", "SHOP", "UBER", "ABNB",
    "COIN", "HOOD", "SOFI", "RBLX", "U", "DASH", "RIVN", "LCID", "ROKU", "AFRM",
    "PATH", "AI", "IONQ", "RGTI", "QBTS", "OKLO", "SMR", "TEM", "RKLB", "ASTS",
    "CELH", "DKNG", "TTD", "CVNA", "ELF", "ONON", "DUOL", "APP", "GTLB", "S",
]

# --- Sector / thematic ETFs ---
SECTOR_ETFS = [
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "XLC",
    "SMH", "SOXX", "IGV", "ARKK", "ARKG", "ICLN", "TAN", "LIT", "URA", "URNM",
    "XBI", "IBB", "ITA", "JETS", "XHB", "KRE", "XME", "XOP", "OIH", "GDX",
]

# --- Broad / index / international ETFs ---
BROAD_ETFS = [
    "SPY", "VOO", "IVV", "QQQ", "DIA", "IWM", "VTI", "RSP", "MDY", "VXUS",
    "EFA", "VEA", "VWO", "EEM", "FXI", "MCHI", "EWJ", "EWZ", "INDA", "EWG",
]

# --- Commodities (ETFs + futures) ---
COMMODITIES = [
    "GLD", "IAU", "SLV", "GLDM", "PPLT", "PALL",          # metals
    "USO", "BNO", "UNG", "UCO", "DBO",                      # energy
    "DBA", "CORN", "WEAT", "SOYB", "DBC", "DBB", "COPX",    # ags + base metals
    "CL=F", "NG=F", "GC=F", "SI=F", "HG=F", "ZC=F", "ZS=F", "ZW=F",  # futures
]

# --- Bonds / rates / credit ---
BONDS = ["TLT", "IEF", "SHY", "BIL", "AGG", "BND", "LQD", "HYG", "JNK", "TIP", "MUB"]

# --- FX pairs (yfinance =X) ---
FX = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X",
      "DX-Y.NYB", "EURJPY=X", "USDCNY=X", "USDMXN=X"]

# --- Crypto (standard only; no memecoins per house rules) ---
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
          "LINK-USD", "DOT-USD", "LTC-USD", "BCH-USD"]

# Volatility / hedges
HEDGES = ["VIXY", "UVXY", "SH", "SQQQ", "SPXU", "PSQ"]

# --- GLOBAL equities (yfinance exchange suffixes). Tradable in dry mode only if the
# local currency is FX-convertible to EUR (major ccys: EUR/GBP/JPY/CHF/CNY/HKD/KRW/
# INR/AUD/CAD/ZAR ok; e.g. Saudi SAR is researchable but not yet FX-convertible). ---
EUROPE = [
    "ASML.AS", "PRX.AS", "ADYEN.AS", "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "MBG.DE",
    "VOW3.DE", "BAS.DE", "BAYN.DE", "MC.PA", "OR.PA", "AIR.PA", "SU.PA", "TTE.PA",
    "SAN.PA", "NESN.SW", "NOVN.SW", "ROG.SW", "UBSG.SW", "AZN.L", "SHEL.L", "HSBA.L",
    "ULVR.L", "BP.L", "GSK.L", "RIO.L", "BATS.L", "DGE.L", "ENEL.MI", "ISP.MI",
    "ENI.MI", "SAN.MC", "IBE.MC", "ITX.MC", "NOVO-B.CO", "EQNR.OL", "NDA-FI.HE",
]
ASIA = [
    "7203.T", "6758.T", "9984.T", "8306.T", "6861.T", "9433.T", "7974.T", "6098.T",  # Japan
    "0700.HK", "9988.HK", "9618.HK", "3690.HK", "1299.HK", "0941.HK", "1810.HK",     # HK/China
    "005930.KS", "000660.KS", "005380.KS",                                            # Korea (Samsung, SK Hynix, Hyundai)
    "2330.TW", "2317.TW", "2454.TW",                                                  # Taiwan (TSMC, Foxconn, MediaTek)
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",                # India
    "D05.SI", "Z74.SI",                                                               # Singapore
]
MIDEAST_AFRICA_OCEANIA = [
    "2222.SR", "1120.SR", "2010.SR",                       # Saudi (Aramco etc.) — FX-limited
    "EMAAR.DU", "FAB.AD",                                  # UAE — FX-limited
    "NPN.JO", "FSR.JO", "SOL.JO", "MTN.JO", "AGL.JO",      # South Africa (ZAR ok)
    "BHP.AX", "CBA.AX", "CSL.AX", "NAB.AX", "WBC.AX", "FMG.AX", "WES.AX", "MQG.AX",  # Australia
]
# Country / region ETFs (US-listed, USD — fully tradable; cover global beta)
REGION_ETFS = [
    "EWJ", "EWG", "EWU", "EWQ", "EWA", "EWY", "EWT", "INDA", "EWZ", "EWW", "EWC",
    "EWS", "EWH", "EWP", "EWI", "EWN", "EWD", "EWL", "EIDO", "EPHE", "THD", "TUR",
    "KSA", "UAE", "EZA", "NGE", "FXI", "MCHI", "KWEB", "EEM", "EMXC", "FM", "AFK",
]

BASE_UNIVERSE: list[str] = list(dict.fromkeys(
    MEGA_LARGE + SEMI_MEMORY + GROWTH_SPEC + SECTOR_ETFS + BROAD_ETFS
    + COMMODITIES + BONDS + FX + CRYPTO + HEDGES
    + EUROPE + ASIA + MIDEAST_AFRICA_OCEANIA + REGION_ETFS
))

_DYN_PATH = lambda: data_dir() / "dynamic_universe.json"  # noqa: E731


def dynamic_additions() -> list[str]:
    p = _DYN_PATH()
    if p.exists():
        try:
            return list(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def add_ticker(ticker: str, reason: str = "") -> bool:
    """Agents grow the universe here. Returns True if newly added."""
    t = ticker.strip().upper()
    if not t or t in BASE_UNIVERSE:
        return False
    cur = dynamic_additions()
    if t in cur:
        return False
    cur.append(t)
    _DYN_PATH().write_text(json.dumps(cur[-500:], indent=0), encoding="utf-8")
    return True


def full_universe() -> list[str]:
    return list(dict.fromkeys(BASE_UNIVERSE + dynamic_additions()))
