"""Fetch the full Bitcoin block-header chain over P2P (after the ONCHAIN-1 seal) and record its hash."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p2p import fetch_all_headers  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw" / "headers.csv"
MANIFEST = HERE / "MANIFEST.json"
CUTOFF = int(dt.datetime(2026, 9, 25, tzinfo=dt.timezone.utc).timestamp())  # discard after 2026-09-24 23:59:59


def main() -> int:
    started = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = fetch_all_headers()
    print(f"downloaded {len(rows)} verified headers (tip height {rows[-1][0]})")
    # keep the chain prefix up to the last block whose timestamp is before the cutoff (a later block
    # with an earlier miner timestamp is still excluded: the cut is on height order)
    last = max(i for i, r in enumerate(rows) if r[1] < CUTOFF)
    kept = [r for r in rows[: last + 1] if r[1] < CUTOFF]
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text("height,timestamp,hash\n" + "".join(f"{h},{t},{x}\n" for h, t, x in kept))
    digest = hashlib.sha256(RAW.read_bytes()).hexdigest()
    MANIFEST.write_text(json.dumps({"headers.csv": {
        "source": "Bitcoin P2P network (getheaders from DNS-seed peers); every header prev-hash-linked and PoW-checked",
        "fetch_started_utc": started, "rows": len(kept), "max_height": kept[-1][0],
        "cutoff": "timestamp < 2026-09-25T00:00:00Z", "sha256": digest,
        "tip_height_seen": rows[-1][0]}}, indent=2) + "\n")
    print("sha256", digest, "rows", len(kept))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
