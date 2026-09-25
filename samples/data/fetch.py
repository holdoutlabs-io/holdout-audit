"""Download the public price data used by the sample audits and record their hashes.

Raw vendor data is NOT committed (see samples/data/SOURCES.md for licences). This script
writes normalised CSVs to ``samples/data/raw/`` and compares their SHA-256 with
``samples/data/MANIFEST.json`` so anyone can check they audited the same bytes.

Instruments are restricted by policy to SPY, QQQ, the S&P 500 index and BTC. No commodity,
metal or other data is ever fetched here.

Sources
- SPY:  (official source for published samples) the Yahoo Finance public chart endpoint,
        unadjusted close + dividend events, stored as raw/spy_daily_yahoo.csv; or (option) a CSV
        downloaded by hand from stooq.com and passed with ``--spy-file`` (columns
        Date,Open,High,Low,Close,Volume), stored as raw/spy_daily_stooq.csv.
- BTC:  Coinbase Exchange public market-data endpoint (``/products/BTC-USD/candles``), daily
        candles, no API key.

Usage:  python samples/data/fetch.py [--end 2026-09-24] [--spy-file path/to/spy_us_d.csv] [--force]
        python samples/data/fetch.py --yahoo --force   # re-download SPY from Yahoo
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
MANIFEST = HERE / "MANIFEST.json"
DEFAULT_END = "2026-09-24"
# Instrument policy for this toolkit's samples: every symbol fetched must be listed here under a permitted category. Commodities, metals (gold, silver), commodity ETFs and astronomical features are forbidden.
POLICY_CATEGORIES = {
    "equity_index": {"^GSPC", "^NDX", "^RUT", "^DJI"},
    "equity_index_signal_only": {"^VIX"},  # volatility index level used as a signal, never traded
    "equity_etf_broad": {"SPY", "QQQ", "IWM", "DIA", "USMV", "SPLV"},  # USMV/SPLV: broad US equity, low-volatility tilt
    "equity_etf_international": {"EFA", "EEM", "VEU"},
    "equity_etf_sector": {"XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "VNQ"},  # VNQ: US REIT equities
    "bond_etf": {"TLT", "IEF", "AGG", "SHY", "BIL"},
    "crypto": {"BTC-USD"},
}
ALLOWED = set().union(*POLICY_CATEGORIES.values())
UA = {"User-Agent": "holdout-labs-sample-fetch/0.1 (research; contact via repository)"}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - fixed public endpoints
        return r.read()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _epoch(d: str) -> int:
    return int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp())


def fetch_spy_yahoo(end: str) -> str:
    symbol = "SPY"
    assert symbol in ALLOWED
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={_epoch('1993-01-01')}"
           f"&period2={_epoch(end) + 86400}&interval=1d&events=div%2Csplit")
    d = json.loads(_get(url))["chart"]["result"][0]
    ts = d["timestamp"]
    close = d["indicators"]["quote"][0]["close"]
    divs = {}
    for ev in (d.get("events", {}).get("dividends", {}) or {}).values():
        day = dt.datetime.fromtimestamp(ev["date"], dt.timezone.utc).date().isoformat()
        divs[day] = ev["amount"]
    lines = ["date,close,dividend"]
    for t, c in zip(ts, close):
        if c is None:
            continue
        day = dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()
        if day > end:
            continue
        lines.append(f"{day},{c:.6f},{divs.get(day, 0.0):.6f}")
    return "\n".join(lines) + "\n"


def fetch_spy_ohlc_yahoo(end: str) -> str:
    """SPY daily open/high/low/close (unadjusted) and dividends from the Yahoo chart endpoint (batch 1)."""
    symbol = "SPY"
    assert symbol in ALLOWED
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={_epoch('1993-01-01')}"
           f"&period2={_epoch(end) + 86400}&interval=1d&events=div%2Csplit")
    d = json.loads(_get(url))["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    divs = {}
    for ev in (d.get("events", {}).get("dividends", {}) or {}).values():
        divs[dt.datetime.fromtimestamp(ev["date"], dt.timezone.utc).date().isoformat()] = ev["amount"]
    lines = ["date,open,high,low,close,dividend"]
    for t, o, h, lo, c in zip(d["timestamp"], q["open"], q["high"], q["low"], q["close"]):
        if None in (o, h, lo, c):
            continue
        day = dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()
        if day <= end:
            lines.append(f"{day},{o:.6f},{h:.6f},{lo:.6f},{c:.6f},{divs.get(day, 0.0):.6f}")
    return "\n".join(lines) + "\n"


def import_spy_stooq_file(path: Path, end: str) -> str:
    """Normalise a manually downloaded stooq.com SPY daily CSV. Stooq's Close is taken as given
    (dividend column 0); the report notes the source."""
    rows = path.read_text(encoding="utf-8").strip().splitlines()
    head = [h.strip().lower() for h in rows[0].split(",")]
    di, ci = head.index("date"), head.index("close")
    out = ["date,close,dividend"]
    for ln in rows[1:]:
        f = ln.split(",")
        if f[di] <= end:
            out.append(f"{f[di]},{float(f[ci]):.6f},0.000000")
    return "\n".join(out) + "\n"


def fetch_btc_coinbase(end: str, start: str = "2015-07-20") -> str:
    product = "BTC-USD"
    assert product in ALLOWED
    day = dt.date.fromisoformat(start)
    stop = dt.date.fromisoformat(end)
    rows: dict[str, float] = {}
    while day <= stop:
        chunk_end = min(day + dt.timedelta(days=299), stop)
        url = (f"https://api.exchange.coinbase.com/products/{product}/candles?granularity=86400"
               f"&start={day.isoformat()}T00:00:00Z&end={chunk_end.isoformat()}T00:00:00Z")
        for t, low, high, op, cl, vol in json.loads(_get(url)):
            d = dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()
            if start <= d <= end:
                rows[d] = cl
        day = chunk_end + dt.timedelta(days=1)
        time.sleep(0.4)  # stay far below the public rate limit
    lines = ["date,close,dividend"] + [f"{d},{rows[d]:.2f},0.000000" for d in sorted(rows)]
    return "\n".join(lines) + "\n"


def fetch_btc_ohlc_coinbase(end: str, start: str = "2015-07-20") -> str:
    """Daily BTC-USD open/high/low/close (UTC) from Coinbase; needed for ATR-based rules (sample 4)."""
    product = "BTC-USD"
    assert product in ALLOWED
    day, stop = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    rows: dict[str, tuple] = {}
    while day <= stop:
        chunk_end = min(day + dt.timedelta(days=299), stop)
        url = (f"https://api.exchange.coinbase.com/products/{product}/candles?granularity=86400"
               f"&start={day.isoformat()}T00:00:00Z&end={chunk_end.isoformat()}T00:00:00Z")
        for t, low, high, op, cl, vol in json.loads(_get(url)):
            d = dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()
            if start <= d <= end:
                rows[d] = (op, high, low, cl)
        day = chunk_end + dt.timedelta(days=1)
        time.sleep(0.4)
    lines = ["date,open,high,low,close,dividend"] + [
        f"{d},{rows[d][0]:.2f},{rows[d][1]:.2f},{rows[d][2]:.2f},{rows[d][3]:.2f},0.000000" for d in sorted(rows)]
    return "\n".join(lines) + "\n"


def fetch_yahoo_close(symbol: str, end: str, start: str = "1990-01-01") -> str:
    """Daily close (unadjusted) and cash dividends for any permitted symbol, from the Yahoo chart endpoint."""
    assert symbol in ALLOWED, f"{symbol} is not a permitted instrument (samples instrument policy)"
    import urllib.parse

    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?period1={_epoch(start)}"
           f"&period2={_epoch(end) + 86400}&interval=1d&events=div%2Csplit")
    d = json.loads(_get(url))["chart"]["result"][0]
    divs = {}
    for ev in (d.get("events", {}).get("dividends", {}) or {}).values():
        divs[dt.datetime.fromtimestamp(ev["date"], dt.timezone.utc).date().isoformat()] = ev["amount"]
    # Yahoo's `close` is split-adjusted (used for signals); `adjclose` is split- and dividend-adjusted (used for
    # total return). Indices such as ^VIX have no adjclose; their close is used for both.
    closes = d["indicators"]["quote"][0]["close"]
    adj = (d["indicators"].get("adjclose") or [{}])[0].get("adjclose") or closes
    lines = ["date,close,adjclose,dividend"]
    for t, c, a in zip(d["timestamp"], closes, adj):
        if c is None or a is None:
            continue
        day = dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()
        if day <= end:
            lines.append(f"{day},{c:.6f},{a:.6f},{divs.get(day, 0.0):.6f}")
    return "\n".join(lines) + "\n"


BATCH2_SYMBOLS = ("SPY", "QQQ", "IWM", "EFA", "IEF", "AGG", "^VIX",
                  "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")


def batch2_file(symbol: str) -> str:
    return "yahoo_" + symbol.replace("^", "idx_").lower() + ".csv"


BATCH3_SYMBOLS = ("SPY", "EFA", "IEF", "EEM", "TLT", "VNQ", "USMV", "SPLV",
                  "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")


def fetch_batch3(end: str = DEFAULT_END) -> dict:
    """Fetch (once) every Batch 3 series not already on disk and record hashes; returns the manifest."""
    return fetch_batch2(end, BATCH3_SYMBOLS)


def fetch_batch2(end: str = DEFAULT_END, symbols=BATCH2_SYMBOLS) -> dict:
    """Fetch (once) every listed series and record its SHA-256 in MANIFEST.json. Returns the manifest."""
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    for sym in symbols:
        name = batch2_file(sym)
        p = RAW / name
        if not p.exists():
            print(f"fetching {sym} ...", flush=True)
            p.write_bytes(fetch_yahoo_close(sym, end).encode("utf-8"))
            time.sleep(0.5)
        h = sha256_file(p)
        n = len(p.read_text().strip().splitlines()) - 1
        rec = manifest.get(name)
        if rec and rec["sha256"] != h:
            print(f"WARNING {name}: sha256 differs from MANIFEST", file=sys.stderr)
        elif not rec:
            manifest[name] = {"sha256": h, "rows": n, "end": end, "source": f"Yahoo Finance chart endpoint ({sym})",
                              "recorded_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    MANIFEST.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--spy-file", help="stooq.com SPY daily CSV you downloaded yourself")
    ap.add_argument("--yahoo", action="store_true", help="(re)fetch SPY from Yahoo, the official source")
    ap.add_argument("--force", action="store_true", help="re-download even if files exist")
    a = ap.parse_args(argv)
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    jobs = {"btc_daily.csv": lambda: fetch_btc_coinbase(a.end),
            "btc_ohlc_daily.csv": lambda: fetch_btc_ohlc_coinbase(a.end)}
    if a.spy_file:
        jobs["spy_daily_stooq.csv"] = lambda: import_spy_stooq_file(Path(a.spy_file), a.end)
    jobs["spy_daily_yahoo.csv"] = lambda: fetch_spy_yahoo(a.end)  # official source; fetched only if missing or --force
    jobs["spy_ohlc_daily_yahoo.csv"] = lambda: fetch_spy_ohlc_yahoo(a.end)  # batch 1 (OHLC needed for range indicators)
    source = {"spy_daily_stooq.csv": "stooq.com (manual download)",
              "spy_daily_yahoo.csv": "Yahoo Finance chart endpoint",
              "spy_ohlc_daily_yahoo.csv": "Yahoo Finance chart endpoint (OHLC)",
              "btc_daily.csv": "Coinbase Exchange public candles API",
              "btc_ohlc_daily.csv": "Coinbase Exchange public candles API (OHLC)"}
    if a.spy_file:
        a.force = True  # an explicitly supplied file always replaces the stored copy
    status = 0
    for name, job in jobs.items():
        p = RAW / name
        if a.force or not p.exists():
            print(f"fetching {name} ...", flush=True)
            p.write_bytes(job().encode("utf-8"))
        h = sha256_file(p)
        n = len(p.read_text().strip().splitlines()) - 1
        rec = manifest.get(name)
        if rec and rec.get("sha256") != h:
            print(f"WARNING {name}: sha256 {h} differs from MANIFEST {rec['sha256']} "
                  "(vendor revision or different source); results may differ slightly.", file=sys.stderr)
            status = 2
        elif rec:
            print(f"ok {name}: sha256 matches MANIFEST ({n} rows)")
        else:
            manifest[name] = {"sha256": h, "rows": n, "end": a.end, "source": source[name],
                              "recorded_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            print(f"recorded {name}: {h} ({n} rows)")
    MANIFEST.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return status


if __name__ == "__main__":
    sys.exit(main())
