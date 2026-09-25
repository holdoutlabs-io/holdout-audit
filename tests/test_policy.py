"""Instrument policy guards for this toolkit's samples: no commodity instruments.

Permitted: equity indices, equity ETFs (broad, sector, international), individual equities, bond ETFs, FX and BTC.
Forbidden: commodities, metals, gold, silver, commodity ETFs, and any astronomical, lunar or astrological feature.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = [p for d in ("src", "samples") for p in (ROOT / d).rglob("*.py")]

PERMITTED_CATEGORIES = {"equity_index", "equity_index_signal_only", "equity_etf_broad", "equity_etf_international",
                        "equity_etf_sector", "equity_single_stock", "bond_etf", "fx", "crypto"}
FORBIDDEN_SYMBOLS = {
    # commodity futures and spot metals
    "GC=F", "SI=F", "CL=F", "BZ=F", "NG=F", "HG=F", "PL=F", "PA=F", "ZW=F", "ZC=F", "ZS=F", "KC=F", "SB=F", "CC=F",
    "CT=F", "XAUUSD=X", "XAGUSD=X",
    # commodity / metal ETFs and ETNs
    "GLD", "IAU", "SGOL", "GLDM", "SLV", "SIVR", "PPLT", "PALL", "USO", "BNO", "UNG", "DBC", "PDBC", "GSG", "DBA",
    "DBB", "CPER", "COMT", "BCI", "GCC", "DJP", "RJI", "WEAT", "CORN", "SOYB", "CANE",
}


def _fetch():
    sys.path.insert(0, str(ROOT / "samples" / "data"))
    import fetch

    return fetch


def test_allowed_symbols_all_in_permitted_categories():
    f = _fetch()
    assert set(f.POLICY_CATEGORIES) <= PERMITTED_CATEGORIES
    assert f.ALLOWED == set().union(*f.POLICY_CATEGORIES.values())


def test_no_forbidden_symbol_is_allowed():
    assert not (_fetch().ALLOWED & FORBIDDEN_SYMBOLS)


def test_no_forbidden_symbols_in_sample_code():
    pat = re.compile(r"[\"'](" + "|".join(re.escape(s) for s in sorted(FORBIDDEN_SYMBOLS)) + r")[\"']", re.I)
    for p in (ROOT / "samples").rglob("*.py"):
        assert not pat.search(p.read_text(encoding="utf-8")), p


def test_no_commodity_or_metal_words_as_instruments():
    pat = re.compile(r"\b(gold|silver|crude|wheat|corn|soybean|copper)_?(price|futures|spot|etf)\b", re.I)
    for p in (ROOT / "samples").rglob("*.py"):
        assert not pat.search(p.read_text(encoding="utf-8")), p


def test_no_astronomy_libraries_or_features():
    banned = re.compile(r"\b(import|from)\s+(ephem|skyfield|astropy|swisseph|pyswisseph|flatlib|jplephem)\b"
                        r"|\b(moon_?phase|lunar_?phase|planet\w*|ephemeris|zodiac|nakshatra|retrograde)\s*[\(=]", re.I)
    for p in CODE:
        assert not banned.search(p.read_text(encoding="utf-8")), p
