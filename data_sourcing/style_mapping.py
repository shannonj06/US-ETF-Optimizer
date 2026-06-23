"""
etf_classifier.py
-----------------
classify_etf_name(etf_name) -> str

Maps an ETF's *name* to one of the style keys used in styleranks.py
(e.g. "High Yield Bond", "Short Term Government Bond", "Ultra Short-Low Risk", ...).

The classifier is rule-based and works purely off the descriptive name. It is
robust to a ticker being present in the string (a leading/trailing all-caps
token is ignored), because all the real signal lives in the words of the name.
"""

import re

# ---- The valid output labels (must match keys in STYLE_RANKS) -------------
VALID_STYLES = {
    "Ultra Short-Low Risk", "Ultra Short Term Bond", "Money Market",
    "Low Risk Bank Deposit", "High Interest Savings Account",
    "Short Term Government Bond", "Short Term High Quality", "Treasury Bond",
    "Short Term Bond", "Short Term Mid Quality", "Multi Alternative",
    "Short Term Low Quality", "Short Term High Yield Bond",
    "Intermediate Term Government Bond", "Intermediate Term Bond",
    "Intermediate Term High Quality", "Long Term Government Bond",
    "Long Term Bond", "Investment Grade Bond", "Intermediate Term Mid Quality",
    "Long Term Mid Quality", "Long Term High Quality",
    "Intermediate Term Low Quality", "High Yield Bond", "Preferred Stock",
    "Real Estate", "Equity", "Commodity", "Cryptocurrency", "Unknown",
}

# Spelled-out numbers used in "Target Duration" treasury funds
_WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15,
    "twenty": 20, "thirty": 30,
}


# ---------------------------------------------------------------------------
# Duration parsing
# ---------------------------------------------------------------------------
def _max_years(s):
    """Return the largest maturity-in-years implied by the name, or None.

    Handles '20+', '1-3 Year', '0-5 Yr', '7-10 Year', 'Two Year',
    'Six Month' (-> 0.5), 'Dec 2028 Term'/'BulletShares 2030' (years-to-target).
    """
    # months -> fraction of a year (e.g. "1-3 Month", "6 Month")
    m = re.findall(r'(\d+)\s*-\s*(\d+)\s*month', s)
    if m:
        return int(m[-1][1]) / 12.0
    m = re.findall(r'(\d+)\s*month', s)
    if m:
        return int(m[-1]) / 12.0
    if "six month" in s or "6 month" in s:
        return 0.5
    if "three month" in s or "3 month" in s:
        return 0.25

    # explicit "N+ Year" (e.g. 20+, 25+, 10+, 15+) -> at least N, treat as a
    # touch longer so "10+" lands in the long bucket
    m = re.findall(r'(\d+)\s*\+\s*year', s)
    if m:
        return float(max(int(x) for x in m)) + 0.5

    # ranges "A-B Year"  (e.g. 1-3, 5-10, 7-10, 0-5)
    m = re.findall(r'(\d+)\s*-\s*(\d+)\s*year', s)
    if m:
        return float(max(int(b) for _, b in m))

    # single "N Year"
    m = re.findall(r'(\d+)\s*year', s)
    if m:
        return float(max(int(x) for x in m))

    # spelled-out "<word> Year" (target-duration treasuries)
    for w, n in _WORD_NUM.items():
        if re.search(r'\b' + w + r'\b\s+year', s):
            return float(n)

    # defined-maturity funds: "Dec 2028 Term", "BulletShares 2030", "iBonds 2026"
    m = re.findall(r'\b(20[2-9]\d)\b', s)
    if m and ("term" in s or "bulletshares" in s or "ibonds" in s
              or "ibond" in s or "target maturity" in s):
        target = max(int(x) for x in m)
        return max(0.0, target - 2026)  # current year baseline

    return None


def _duration_bucket(s):
    """Return one of: 'ultra', 'short', 'intermediate', 'long', or None."""
    yrs = _max_years(s)
    if yrs is not None:
        if yrs <= 1.0:
            return "ultra"
        if yrs <= 3.0:
            return "short"
        if yrs <= 10.0:
            return "intermediate"
        return "long"

    # word cues
    if re.search(r'ultra[\s-]?short|ultrashort', s):
        return "ultra"
    if re.search(r'low duration|enhanced short|short maturity|reserve|'
                 r'ultra[\s-]?short|0-1 year', s):
        return "ultra"
    if re.search(r'short[\s-]?term|short duration|short-duration|limited '
                 r'duration|limited term|short ', s):
        return "short"
    if re.search(r'intermediate|medium[\s-]?term|mid[\s-]?term|5-10', s):
        return "intermediate"
    if re.search(r'long[\s-]?term|long duration|extended duration|long ', s):
        return "long"
    return None


# ---------------------------------------------------------------------------
# Helper predicates
# ---------------------------------------------------------------------------
def _has(s, *words):
    return any(w in s for w in words)


def _strip_ticker(name):
    """Remove a leading or trailing standalone all-caps ticker token."""
    toks = name.strip().split()
    if not toks:
        return name
    # leading ticker
    if len(toks) > 1 and re.fullmatch(r'[A-Z]{2,6}', toks[0]):
        toks = toks[1:]
    if toks and re.fullmatch(r'[A-Z]{2,6}', toks[-1]):
        toks = toks[:-1]
    return " ".join(toks)


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------
def classify_etf_name(etf_name):
    if not etf_name or not str(etf_name).strip():
        return "Unknown"

    raw = _strip_ticker(str(etf_name))
    s = " " + raw.lower().strip() + " "
    s = re.sub(r'\s+', ' ', s)

    dur = _duration_bucket(s)
    # Floating / variable rate -> near-zero duration (unless an explicit
    # maturity band was already given)
    if dur is None and re.search(r'floating[\s-]?rate|variable rate', s):
        dur = "ultra" if "treasury" in s else "short"
    is_short_like = dur in ("ultra", "short")
    yrs = _max_years(s)

    # 1) Crypto -------------------------------------------------------------
    if _has(s, "bitcoin", "btc", "ethereum", " ether ", "crypto"):
        return "Cryptocurrency"

    # 2) Commodity (word-boundaries so "Goldman" != gold) -------------------
    if (re.search(r'\b(gold|silver|commodit\w*|crude|bullion)\b', s)
            or _has(s, "precious metal", "natural gas", "broad metals")):
        return "Commodity"

    # 3) Preferred ----------------------------------------------------------
    if "preferred" in s:
        return "Preferred Stock"

    # 4) Real estate --------------------------------------------------------
    if "real estate" in s:
        return "Real Estate"

    # 5) Money market / T-bills --------------------------------------------
    if _has(s, "money market", "t-bill", "t bill", "treasury bill",
            " bill etf", "month bill", "month t-bill", "box etf", "1-3 month",
            "3-12 month", "3-month"):
        return "Money Market"

    # 6) TIPS / inflation-protected -> Treasury Bond (ultra-short -> cash) ---
    if _has(s, "tips", "inflation protected", "inflation-protected",
            "inflation protection"):
        return "Ultra Short-Low Risk" if dur == "ultra" else "Treasury Bond"

    # 7) Pure rate / vol / inflation-hedge alternative strategies -----------
    bond_underlying = _has(s, "corporate", "aggregate", "high yield",
                           "treasury", "municipal", " muni", "government",
                           "investment grade", "core")
    if (not bond_underlying and
            _has(s, "interest rate hedge", "rate volatility",
                 "volatility", "inflation hedge", "inflation expectations",
                 "deflation")):
        return "Multi Alternative"

    # 8) Multi-asset / unconstrained / go-anywhere strategies ---------------
    if _has(s, "multi-asset", "multi asset", "real return", "multi-strategy"):
        return "Multi Alternative"

    # 9) Senior / bank / leveraged loans -> Short Term Low Quality ---------
    if _has(s, "senior loan", "bank loan", "leveraged loan",
            "floating rate income", "floating rate high income",
            "floating rate municipal income"):
        return "Short Term Low Quality"

    # 10) CLOs --------------------------------------------------------------
    if "clo" in s:
        return "Ultra Short-Low Risk" if "aaa" in s else "Short Term Low Quality"

    # 11) Convertibles -> Equity (hybrid) -----------------------------------
    if "convertible" in s:
        return "Equity"

    # 12) Municipal bonds ---------------------------------------------------
    is_muni = _has(s, "muni", "municipal", "tax-exempt", "tax exempt",
                   "tax-aware", "amt-free", "amt free")
    if is_muni:
        if _has(s, "high yield", "high-yield", "high income"):
            return "Short Term High Yield Bond" if is_short_like else "High Yield Bond"
        if dur == "ultra":
            return "Ultra Short-Low Risk"
        if dur == "short":
            return "Short Term Bond"
        if dur == "intermediate":
            return "Intermediate Term Bond"
        if dur == "long":
            return "Long Term Bond"
        return "Investment Grade Bond"

    # 13) High yield (corp / EM / fallen-angel / rating-based) --------------
    rating_hy = bool(re.search(r'\bccc\b|\bbb[\s-]?rated|\bb[\s-]?rated|'
                               r'\bb-bbb\b', s)) and "bbb" not in re.sub(
                                   r'b-bbb', '', s)
    if _has(s, "high yield", "high-yield", "hi yield", "fallen angel",
            "speculative") or rating_hy:
        short_hy = is_short_like or (yrs is not None and yrs <= 5)
        return "Short Term High Yield Bond" if short_hy else "High Yield Bond"

    # 14) Emerging markets (non-HY) -> Intermediate Term Low Quality --------
    if _has(s, "emerging market", "emerging markets", " em ", "em local",
            "em corporate", "em sovereign", "china bond"):
        return "Intermediate Term Low Quality"

    # 15) Treasury / government (non-TIPS) ----------------------------------
    if _has(s, "treasury", "t-bond", "government", "govt", "sovereign",
            "strips", "gnma", "agency bond"):
        if dur == "ultra":
            return "Ultra Short-Low Risk"
        if dur == "short":
            return "Short Term Government Bond"
        if dur == "long":
            return "Long Term Government Bond"
        return "Intermediate Term Government Bond"

    # 16) MBS / securitized (agency, high quality) --------------------------
    if _has(s, "mbs", "mortgage-backed", "mortgage backed", "cmbs",
            "securitized", "mortgage plus", "abs"):
        if dur == "ultra":
            return "Ultra Short-Low Risk"
        if dur == "short":
            return "Short Term High Quality"
        if dur == "long":
            return "Long Term High Quality"
        return "Investment Grade Bond"

    # 17) Aggregate / core / total bond (broad IG) --------------------------
    if _has(s, "aggregate", "core bond", "core plus", "core-plus",
            "total bond", "total return bond", "core fixed income",
            "core select", "core intermediate", "us bond", "u.s. bond",
            "broad usd", "universal", "core tax"):
        if dur == "ultra":
            return "Ultra Short-Low Risk"
        if dur == "short":
            return "Short Term High Quality"
        if dur == "long":
            return "Long Term High Quality"
        return "Investment Grade Bond"

    # 18) Quality tier from explicit markers --------------------------------
    high_q = _has(s, "investment grade", "investment-grade", "high quality",
                  "aaa", " aa ", "a rated", "a-rated", " ig ", "ig corporate",
                  "ig floating")
    mid_q = "bbb" in s

    if high_q:
        if dur == "ultra":
            return "Ultra Short-Low Risk"
        if dur == "short":
            return "Short Term High Quality"
        if dur == "long":
            return "Long Term High Quality"
        if dur == "intermediate":
            return "Intermediate Term High Quality"
        return "Investment Grade Bond"

    if mid_q:
        if dur == "short":
            return "Short Term Mid Quality"
        if dur == "long":
            return "Long Term Mid Quality"
        return "Intermediate Term Mid Quality"

    # 19) Generic corporate / credit ---------------------------------------
    if _has(s, "corporate", "corp ", "credit", "fixed income", "fixed-income"):
        if dur == "ultra":
            return "Ultra Short-Low Risk"
        if dur == "short":
            return "Short Term High Quality"
        if dur == "long":
            return "Long Term High Quality"
        if dur == "intermediate":
            return "Intermediate Term Mid Quality"
        return "Investment Grade Bond"

    # 20) Flexible / income / multi-sector go-anywhere strategies -----------
    if _has(s, "unconstrained", "flexible", "opportunistic", "tactical",
            "multi-sector", "multisector", "multi sector", "sector rotation",
            "credit rotation", "strategic income", "strategic focus",
            "dynamic", "optimized", "smart sector", "allocation",
            "income opportunities", "universal", "economic cycle",
            "total return"):
        return "Multi Alternative"

    # Sukuk (Islamic fixed income) -> IG ; crossover equity-style ----------
    if "sukuk" in s:
        return "Investment Grade Bond"
    if _has(s, "crossover", "private-public", "equity"):
        return "Equity"

    # 21) Generic "bond" or "income" with a duration ------------------------
    if _has(s, "bond", "income", "fixed"):
        if dur == "ultra":
            return "Ultra Short-Low Risk"
        if dur == "short":
            return "Short Term Bond"
        if dur == "long":
            return "Long Term Bond"
        if dur == "intermediate":
            return "Intermediate Term Bond"
        return "Investment Grade Bond"

    # 22) Final fallback: classify by duration alone (cash-mgmt / generic) ---
    if dur == "ultra":
        return "Ultra Short-Low Risk"      # enhanced short maturity, reserve...
    if dur == "short":
        return "Short Term Bond"
    if dur == "intermediate":
        return "Intermediate Term Bond"
    if dur == "long":
        return "Long Term Bond"

    return "Unknown"


