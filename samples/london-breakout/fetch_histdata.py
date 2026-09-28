"""Download HistData.com GBPUSD Generic ASCII M1 files for LB-1 (PREREG.md §5), politely, and hash them.

    uv run python samples/london-breakout/fetch_histdata.py --stage A   # annual files 2000-2023 only
    uv run python samples/london-breakout/fetch_histdata.py --stage B   # 2024, 2025, 2026-01..09 (needs the unlock)

Replicates HistData's free per-file download form (hidden ``tk`` token -> POST /get.php, and the
file status report -> POST /getStatus.php) with the Referer of the page, one file at a time, 4 s
between requests. Zips and extracted CSVs go to ``raw/`` (gitignored, never committed or
published). Every file is recorded in ``MANIFEST.json`` (name, source page, download time UTC,
bytes, SHA-256 of zip, extracted CSV and status report), as PREREG §5.3 requires.

Stage B refuses to run unless ``HOLDOUT-UNLOCK.json`` exists and still matches the committed
Stage A results (``lb_data.require_holdout_unlock``). This script loads no prices.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import http.cookiejar
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lb_data  # noqa: E402

RAW = HERE / "raw"
MANIFEST = HERE / "MANIFEST.json"
BASE = "https://www.histdata.com"
PAGE = BASE + "/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/gbpusd/{period}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) holdout-labs LB-1 research (statistics only; no redistribution)"
PAUSE_S = 4.0
STAGE_A = [str(y) for y in range(2000, 2024)]
STAGE_B = ["2024", "2025"] + [f"2026/{m}" for m in range(1, 10)]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def form_fields(html: str, form_id: str) -> dict:
    m = re.search(rf'<form id="{form_id}".*?</form>', html, re.S)
    if not m:
        raise RuntimeError(f"form {form_id} not found (page layout changed or access blocked)")
    return dict(re.findall(r'name="(\w+)" id="\w+" value="([^"]*)"', m.group(0)))


class Session:
    """Minimal cookie-keeping HTTP client (standard library only)."""

    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(self, url: str, timeout: int) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with self.opener.open(req, timeout=timeout) as r:
            return r.read()

    def post(self, url: str, data: dict, referer: str, timeout: int) -> bytes:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                     headers={"User-Agent": UA, "Referer": referer,
                                              "Content-Type": "application/x-www-form-urlencoded"})
        with self.opener.open(req, timeout=timeout) as r:
            return r.read()


def fetch(session: Session, period: str) -> dict:
    page = PAGE.format(period=period)
    html = session.get(page, timeout=60).decode("utf-8", "replace")
    fields = form_fields(html, "file_down")
    status_fields = form_fields(html, "file_status")
    time.sleep(PAUSE_S)
    zc = session.post(BASE + "/get.php", fields, page, timeout=300)
    when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not zc.startswith(b"PK"):
        raise RuntimeError(f"{period}: response is not a zip ({zc[:120]!r}); blocked or login required")
    time.sleep(PAUSE_S)
    sc = session.post(BASE + "/getStatus.php", status_fields, page, timeout=120)
    zname = f"HISTDATA_COM_ASCII_GBPUSD_M1{fields['datemonth']}.zip"
    RAW.mkdir(exist_ok=True)
    (RAW / zname).write_bytes(zc)
    rec = {"period": period, "source_page": page, "form": {k: v for k, v in fields.items() if k != "tk"},
           "downloaded_at_utc": when, "zip_file": zname, "zip_bytes": len(zc), "zip_sha256": sha(zc),
           "members": []}
    with zipfile.ZipFile(io.BytesIO(zc)) as zf:
        for info in zf.infolist():
            data = zf.read(info)
            (RAW / info.filename).write_bytes(data)
            rec["members"].append({"name": info.filename, "bytes": len(data), "sha256": sha(data)})
    sname = zname.replace(".zip", ".status.txt")
    (RAW / sname).write_bytes(sc)
    rec["status_report"] = {"name": sname, "bytes": len(sc), "sha256": sha(sc),
                            "downloaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=["A", "B"], required=True)
    ap.add_argument("--only", nargs="*", help="subset of periods (e.g. 2000 2001, or 2026/9)")
    a = ap.parse_args(argv)
    if a.stage == "B":
        lb_data.require_holdout_unlock()
        periods = STAGE_B
    else:
        periods = STAGE_A
    if a.only:
        bad = [p for p in a.only if p not in periods]
        if bad:
            raise SystemExit(f"periods not allowed in stage {a.stage}: {bad}")
        periods = a.only
    man = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {
        "study": "LB-1 London Breakout", "source": "HistData.com GBPUSD Generic ASCII M1 (bid), fixed UTC-5",
        "fetcher": "fetch_histdata.py", "note": "raw files are never committed or published (PREREG §5.1)",
        "files": []}
    done = {f["period"] for f in man["files"]}
    session = Session()
    for p in periods:
        if p in done:
            print("skip (already in manifest)", p)
            continue
        rec = fetch(session, p)
        rec["stage"] = a.stage
        man["files"].append(rec)
        man["fetcher_sha256"] = lb_data.sha256_file(Path(__file__))
        MANIFEST.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
        print(p, rec["zip_bytes"], [m["name"] for m in rec["members"]])
        time.sleep(PAUSE_S)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
