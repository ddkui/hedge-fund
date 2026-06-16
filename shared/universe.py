# shared/universe.py
"""
Full market universe — every symbol the system can chart, analyze, and trade.

Symbols follow Yahoo Finance conventions (used by the prices endpoint and ingest):
  - US stocks/ETFs:    AAPL, SPY, QQQ
  - International:     0700.HK, SAP.DE, 7203.T  (Yahoo exchange suffixes)
  - Crypto spot:       BTCUSDT, ETHUSDT          (Binance/Yahoo format)
  - Hyperliquid perps: HL:BTC, HL:ETH            (our own HL: prefix)
  - Forex:             EURUSD=X, USDJPY=X
  - Commodities:       GC=F, CL=F

Agents read from the `prices` DB table (populated by ingest agents using Yahoo Finance).
HL: symbols are fetched live from Hyperliquid and not stored in the DB.
"""

# ── US ──────────────────────────────────────────────────────────────────────
US_LARGE_CAP: list[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META",
    "NFLX", "AMD", "INTC", "QCOM", "ORCL", "CRM", "ADBE",
    "JPM", "GS", "BAC", "MS", "C", "WFC",
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    "XOM", "CVX", "COP",
    "BRK-B", "V", "MA", "PYPL",
    "HD", "WMT", "COST", "TGT",
]

US_ETFS: list[str] = [
    "SPY", "QQQ", "IWM", "DIA",
    "XLK", "XLF", "XLE", "XLV", "XLU", "XLI", "XLB",
    "GLD", "SLV", "USO",
    "TLT", "IEF", "SHY",
]

# ── International ────────────────────────────────────────────────────────────
INTL_ASIA: list[str] = [
    "0700.HK",     # Tencent
    "9988.HK",     # Alibaba
    "9618.HK",     # JD.com
    "2318.HK",     # Ping An Insurance
    "1299.HK",     # AIA Group
    "7203.T",      # Toyota
    "9984.T",      # SoftBank
    "6758.T",      # Sony
    "8306.T",      # Mitsubishi UFJ
    "6861.T",      # Keyence
    "005930.KS",   # Samsung Electronics
    "035420.KS",   # Naver
    "RELIANCE.NS", # Reliance Industries
    "TCS.NS",      # Tata Consultancy
    "INFY.NS",     # Infosys
    "HDFCBANK.NS", # HDFC Bank
    "2330.TW",     # TSMC
    "2317.TW",     # Foxconn
]

INTL_EUROPE: list[str] = [
    "SAP.DE",      # SAP
    "BMW.DE",      # BMW
    "SIE.DE",      # Siemens
    "VOW3.DE",     # Volkswagen
    "ALV.DE",      # Allianz
    "ASML.AS",     # ASML
    "PHIA.AS",     # Philips
    "MC.PA",       # LVMH
    "AIR.PA",      # Airbus
    "BNP.PA",      # BNP Paribas
    "SAN.PA",      # Sanofi
    "HSBA.L",      # HSBC
    "SHEL.L",      # Shell
    "AZN.L",       # AstraZeneca
    "BP.L",        # BP
    "ULVR.L",      # Unilever
    "RIO.L",       # Rio Tinto
    "NESN.SW",     # Nestlé
    "ROG.SW",      # Roche
    "NOVN.SW",     # Novartis
    "ABB.ST",      # ABB
    "ERIC-B.ST",   # Ericsson
]

INTL_AMERICAS: list[str] = [
    "SHOP.TO",     # Shopify (Toronto)
    "RY.TO",       # Royal Bank of Canada
    "TD.TO",       # TD Bank
    "VALE3.SA",    # Vale (Brazil)
    "PETR4.SA",    # Petrobras (Brazil)
]

INTL_ETFS: list[str] = [
    "EWJ",   # Japan
    "EWG",   # Germany
    "EWY",   # South Korea
    "EWH",   # Hong Kong
    "EWT",   # Taiwan
    "EWZ",   # Brazil
    "EWA",   # Australia
    "EWC",   # Canada
    "EWU",   # United Kingdom
    "EEM",   # Emerging Markets
    "VEA",   # Developed Markets ex-US
    "IEFA",  # International Developed Markets
    "MCHI",  # China
    "INDA",  # India
    "VWO",   # Vanguard Emerging Markets
]

# ── Crypto spot ──────────────────────────────────────────────────────────────
CRYPTO_SPOT: list[str] = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT",
    "MATICUSDT", "LINKUSDT", "UNIUSDT", "AAVEUSDT",
    "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT",
]

# ── Hyperliquid perpetuals (live via HL: prefix, not in DB) ──────────────────
HYPERLIQUID_PERPS: list[str] = [
    "HL:BTC", "HL:ETH", "HL:SOL", "HL:HYPE",
    "HL:AVAX", "HL:ARB", "HL:OP",
    "HL:DOGE", "HL:LINK", "HL:UNI", "HL:WIF",
    "HL:INJ", "HL:SUI", "HL:TIA", "HL:SEI",
    "HL:BNB", "HL:MATIC", "HL:ATOM", "HL:APT",
]

# ── Forex ────────────────────────────────────────────────────────────────────
FOREX: list[str] = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCAD=X",
    "AUDUSD=X", "NZDUSD=X", "USDCHF=X",
    "USDCNY=X", "USDMXN=X", "USDBRL=X",
    "USDINR=X", "USDKRW=X", "USDZAR=X",
    "EURGBP=X", "EURJPY=X", "GBPJPY=X",
]

# ── Commodities (Yahoo Finance futures) ──────────────────────────────────────
COMMODITIES: list[str] = [
    "GC=F",  # Gold
    "SI=F",  # Silver
    "PL=F",  # Platinum
    "CL=F",  # Crude Oil WTI
    "BZ=F",  # Brent Crude
    "NG=F",  # Natural Gas
    "HG=F",  # Copper
    "ZC=F",  # Corn
    "ZW=F",  # Wheat
    "ZS=F",  # Soybeans
    "KC=F",  # Coffee
    "CT=F",  # Cotton
]


def ingest_symbols() -> list[str]:
    """
    All symbols fetchable via Yahoo Finance.
    Used by ingest agents and analysis agents. Excludes HL: perps.
    """
    return (
        US_LARGE_CAP
        + US_ETFS
        + INTL_ASIA
        + INTL_EUROPE
        + INTL_AMERICAS
        + INTL_ETFS
        + CRYPTO_SPOT
        + FOREX
        + COMMODITIES
    )


def chart_universe() -> dict[str, list[str]]:
    """Organized by category for the price chart UI tabs."""
    return {
        "US Stocks":     US_LARGE_CAP + US_ETFS,
        "International": INTL_ASIA + INTL_EUROPE + INTL_AMERICAS + INTL_ETFS,
        "Crypto":        CRYPTO_SPOT,
        "Hyperliquid":   HYPERLIQUID_PERPS,
        "Forex":         FOREX,
        "Commodities":   COMMODITIES,
    }
