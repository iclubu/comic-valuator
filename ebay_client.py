"""
ebay_client.py
eBay Browse API client — handles OAuth token management and sold listing search.
Uses Production credentials from .env file.

v1.1 fixes:
  - Volume number extracted from series_name and included in query
  - issue_year always appended to raw queries — critical disambiguation for
    series like Venom (5 volumes), Batman, X-Men etc.
  - variant_description included for graded books — Momoko/Dell'Otto variants
    sell at very different prices from regular covers
  - Noise filter expanded — wrong volume years now filtered from results
  - _build_query now accepts issue_year and variant as explicit params
  - search_sold_listings signature updated to match
"""

import os
import re
import time
import base64
import requests
import numpy as np
from dotenv import load_dotenv

load_dotenv()

EBAY_CLIENT_ID     = os.getenv("EBAY_CLIENT_ID")
EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET")

TOKEN_URL  = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

COMICS_CATEGORY_ID = "259104"

_token_cache = {"token": None, "expires_at": 0}


# ─────────────────────────────────────────────
# OAUTH
# ─────────────────────────────────────────────

def get_access_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    if not EBAY_CLIENT_ID or not EBAY_CLIENT_SECRET:
        raise ValueError(
            "EBAY_CLIENT_ID and EBAY_CLIENT_SECRET must be set in your .env file"
        )

    credentials = base64.b64encode(
        f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}".encode()
    ).decode()

    resp = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type":  "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "client_credentials",
            "scope":      "https://api.ebay.com/oauth/api_scope",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"]      = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 7200)
    return _token_cache["token"]


# ─────────────────────────────────────────────
# SERIES NAME PARSING
# Extracts vol number and clean title separately
# so both can be used independently in queries
# ─────────────────────────────────────────────

def parse_series(series: str) -> dict:
    """
    Parse a CLZ series_name into components.

    Examples:
      "Venom, Vol. 5"        → {clean: "Venom",   vol: 5,    vol_str: "Vol 5"}
      "Batman"               → {clean: "Batman",  vol: None, vol_str: ""}
      "X-Men (1991)"         → {clean: "X-Men",   vol: None, vol_str: ""}
      "Amazing Spider-Man, Vol. 3 (2014)" → {clean: "Amazing Spider-Man", vol: 3}
    """
    if not isinstance(series, str):
        return {"clean": str(series), "vol": None, "vol_str": ""}

    # Extract Vol. number before stripping
    vol_match = re.search(r'[Vv]ol\.?\s*(\d+)', series)
    vol_num   = int(vol_match.group(1)) if vol_match else None
    vol_str   = f"Vol {vol_num}" if vol_num else ""

    # Strip Vol. suffix and parenthetical publisher/year tags
    clean = re.sub(r',?\s*[Vv]ol\.?\s*\d+', '', series)
    clean = re.sub(r'\s*\([^)]+\)', '', clean)
    clean = clean.strip().rstrip(',').strip()

    return {"clean": clean, "vol": vol_num, "vol_str": vol_str}


# ─────────────────────────────────────────────
# QUERY BUILDER
# ─────────────────────────────────────────────

def _build_query(series: str, issue: str,
                 grade_type: str = None, grade: float = None,
                 issue_year: int = None, variant: str = None) -> str:
    """
    Build a targeted eBay search query for a comic.

    Raw comics:
      "Venom" #1 Vol 5 2021 comic
      "Batman" #92 2020 comic

    Graded comics:
      "Venom" #1 Vol 5 CGC 9.8
      "Venom" #1 Vol 5 Momoko CGC 9.8   (if variant has a recognisable artist name)

    Volume number is always included when present — this is the key fix
    that prevents Vol.1 (1993) results polluting Vol.5 (2021) searches.

    Issue year is always included for raw books — secondary disambiguation
    for series without explicit Vol. numbering.
    """
    parsed    = parse_series(series)
    clean     = parsed["clean"]
    vol_str   = parsed["vol_str"]
    issue_str = str(issue).replace('.0', '').strip()

    # Extract variant artist surname for graded variant queries
    # e.g. "Variant Peach Momoko Cover" → "Momoko"
    variant_tag = ""
    if variant and isinstance(variant, str):
        # Look for known artist surname patterns in variant description
        # Strip common filler words and keep the most distinctive word
        filler = r'\b(variant|cover|edition|printing|foil|virgin|blank|sketch|incentive|ratio)\b'
        v_clean = re.sub(filler, '', variant, flags=re.IGNORECASE).strip()
        words   = [w for w in v_clean.split() if len(w) > 3]
        if words:
            # Use the last meaningful word — usually the artist surname
            variant_tag = words[-1]

    # ── GRADED query ──────────────────────────────────────────────────────
    if grade_type and grade and grade_type in ('CGC', 'CBCS'):
        parts = [f'"{clean}"', f'#{issue_str}']
        if vol_str:
            parts.append(vol_str)
        if variant_tag:
            parts.append(variant_tag)
        parts.append(grade_type)
        parts.append(str(grade))
        return ' '.join(parts)

    # ── RAW query ─────────────────────────────────────────────────────────
    parts = [f'"{clean}"', f'#{issue_str}']
    if vol_str:
        parts.append(vol_str)
    if issue_year and int(issue_year) > 1900:
        parts.append(str(int(issue_year)))
    parts.append('comic')
    return ' '.join(parts)


# ─────────────────────────────────────────────
# NOISE FILTER — expanded
# ─────────────────────────────────────────────

def _is_noise(title: str, grade_type: str, grade: float,
              issue_year: int = None) -> bool:
    """
    Returns True if the listing should be excluded from price stats.

    Filters:
    - Lot / bundle sales
    - Digital items
    - Wrong grade (for graded searches)
    - Wrong year (catches wrong-volume results when year is known)
    """
    lower = title.lower()

    # Lot / bundle
    if any(w in lower for w in [
        "lot of", "lot (", "bundle", "wholesale",
        "collection lot", "mixed lot", "run of",
        "complete set", "issues #"
    ]):
        return True

    # Digital
    if any(w in lower for w in ["digital", "pdf", "cbz", "cbr", "reading copy"]):
        return True

    # Reprints / facsimile
    if any(w in lower for w in ["facsimile", "reprint", "trade paperback",
                                  "omnibus", "hardcover", "tpb"]):
        return True

    # Wrong grade — for graded searches only
    if grade_type and grade:
        grade_str = str(grade)
        # Build list of grades that would be clearly wrong
        all_grades = ["9.9", "9.8", "9.6", "9.4", "9.2", "9.0",
                      "8.5", "8.0", "7.5", "7.0", "6.5", "6.0",
                      "5.5", "5.0", "4.5", "4.0"]
        wrong = [g for g in all_grades if g != grade_str]
        # Only filter if a wrong grade appears explicitly in title
        for g in wrong:
            # Match grade as standalone token e.g. "9.6" not "9.6x"
            if re.search(r'(?<!\d)' + re.escape(g) + r'(?!\d)', title):
                return True

    # Wrong year — catches wrong-volume results
    # e.g. searching for 2021 Venom #1, filter out 1993 Venom #1 results
    if issue_year and int(issue_year) > 1900:
        # Look for 4-digit years in title that differ by >3 years
        year_matches = re.findall(r'\b(19\d{2}|20\d{2})\b', title)
        for y in year_matches:
            if abs(int(y) - int(issue_year)) > 3:
                return True

    return False


# ─────────────────────────────────────────────
# MAIN SEARCH FUNCTION
# ─────────────────────────────────────────────

def search_sold_listings(
    series:      str,
    issue:       str,
    grade_type:  str   = None,
    grade:       float = None,
    issue_year:  int   = None,
    variant:     str   = None,
    max_results: int   = 40,
) -> list[dict]:
    """
    Search eBay completed/sold listings for a specific comic.

    Parameters:
        series      — CLZ series_name (e.g. "Venom, Vol. 5")
        issue       — issue number (e.g. "1" or 1.0)
        grade_type  — "CGC", "CBCS", or None for raw
        grade       — numeric grade (e.g. 9.8) or None
        issue_year  — year of publication — used to disambiguate volumes
        variant     — variant description from CLZ (e.g. "Variant Peach Momoko Cover")
        max_results — max listings to fetch

    Returns list of dicts: title, price, currency, date, url, condition, query
    """
    token = get_access_token()
    query = _build_query(series, issue, grade_type, grade, issue_year, variant)

    params = {
        "q":            query,
        "category_ids": COMICS_CATEGORY_ID,
        "filter":       "buyingOptions:{FIXED_PRICE|AUCTION},soldItems:true",
        "sort":         "endTimeSoonest",
        "limit":        min(max_results, 200),
        "fieldgroups":  "EXTENDED",
    }

    resp = requests.get(
        BROWSE_URL,
        headers={
            "Authorization":           f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "Content-Type":            "application/json",
        },
        params=params,
        timeout=15,
    )

    if resp.status_code == 401:
        _token_cache["token"] = None
        return search_sold_listings(
            series, issue, grade_type, grade,
            issue_year, variant, max_results
        )

    if resp.status_code != 200:
        return []

    items   = resp.json().get("itemSummaries", [])
    results = []

    for item in items:
        price_info = item.get("price", {})
        price      = float(price_info.get("value", 0))
        currency   = price_info.get("currency", "USD")
        title      = item.get("title", "")
        url        = item.get("itemWebUrl", "")
        condition  = item.get("condition", "")
        end_date   = item.get("itemEndDate", "")

        if price <= 0:
            continue
        if _is_noise(title, grade_type, grade, issue_year):
            continue

        results.append({
            "title":     title,
            "price":     price,
            "currency":  currency,
            "date":      end_date[:10] if end_date else "",
            "url":       url,
            "condition": condition,
            "query":     query,
        })

    return results


# ─────────────────────────────────────────────
# PRICE STATS
# ─────────────────────────────────────────────

def compute_price_stats(listings: list[dict]) -> dict:
    """
    Compute price statistics from a list of sold listings.
    Removes outliers using IQR method before computing stats.
    """
    prices = [l["price"] for l in listings]
    if not prices:
        return {
            "count": 0, "low": None, "high": None,
            "median": None, "mean": None, "trend": None,
        }

    arr = np.array(prices)

    # IQR outlier removal
    if len(arr) >= 4:
        q1, q3 = np.percentile(arr, 25), np.percentile(arr, 75)
        iqr     = q3 - q1
        arr     = arr[(arr >= q1 - 1.5 * iqr) & (arr <= q3 + 1.5 * iqr)]

    if len(arr) == 0:
        arr = np.array(prices)

    # Trend — compare recent vs older sales
    trend = None
    dated = [l for l in listings if l.get("date")]
    if len(dated) >= 6:
        dated.sort(key=lambda x: x["date"], reverse=True)
        half   = len(dated) // 2
        recent = np.mean([l["price"] for l in dated[:half]])
        older  = np.mean([l["price"] for l in dated[half:]])
        if older > 0:
            pct = ((recent - older) / older) * 100
            if pct > 5:
                trend = f"↑ +{pct:.0f}%"
            elif pct < -5:
                trend = f"↓ {pct:.0f}%"
            else:
                trend = "→ Stable"

    return {
        "count":  len(listings),
        "low":    float(round(arr.min(), 2)),
        "high":   float(round(arr.max(), 2)),
        "median": float(round(np.median(arr), 2)),
        "mean":   float(round(arr.mean(), 2)),
        "trend":  trend,
    }


# ─────────────────────────────────────────────
# DEBUG HELPER — test a query without the app
# Usage: python3 ebay_client.py
# ─────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        # (series, issue, grade_type, grade, year, variant)
        ("Venom, Vol. 5",    "1",  None,   None, 2021, "Variant Peach Momoko Cover"),
        ("Venom, Vol. 5",    "1",  "CGC",  9.8,  2021, "Variant Peach Momoko Cover"),
        ("Venom, Vol. 4",    "35", None,   None, 2021, None),
        ("Batman",           "92", "CGC",  9.8,  2020, None),
        ("Amazing Spider-Man, Vol. 3", "1", "CGC", 9.8, 2014, None),
    ]

    print("=== QUERY BUILDER TEST ===\n")
    for s, i, gt, g, y, v in test_cases:
        parsed = parse_series(s)
        query  = _build_query(s, i, gt, g, y, v)
        print(f"  Series  : {s}")
        print(f"  Parsed  : clean='{parsed['clean']}' vol={parsed['vol']}")
        print(f"  Query   : {query}")
        print()
