"""Data plumbing for the London Breakout audit: synthetic series, HistData parsing, locks, hashing.

NOTHING IN THIS MODULE DOWNLOADS DATA. Real HistData files are placed by hand in ``raw/`` (never
committed) after the preregistration is sealed, and every loader checks the locks first:

* ``require_prereg_seal()``: refuses to read any real price file unless ``prereg-seal/seal.json``
  exists and verifies against the current ``PREREG.md`` (holdout-audit ``verify_seal``).
* Stage A (in-sample, 2000-2023) accepts timestamps < 2024-01-01 only, and refuses any file whose name carries
  a holdout year (2024, 2025, 2026).
* Stage B (holdout) additionally requires ``HOLDOUT-UNLOCK.json``, which records the SHA-256 of the
  committed Stage A results file; the hash must still match.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
PREREG = HERE / "PREREG.md"
PREREG_SEAL = HERE / "prereg-seal"
STAGE_A_RESULTS = HERE / "stageA" / "results.json"
UNLOCK = HERE / "HOLDOUT-UNLOCK.json"

SAMPLE_START = pd.Timestamp("2000-01-01")  # all HistData GBPUSD M1 history (PREREG §5.2)
HOLDOUT_START = pd.Timestamp("2024-01-01")
SAMPLE_END = pd.Timestamp("2026-09-25 23:59:59")
HOLDOUT_YEARS = ("2024", "2025", "2026")


class LockError(RuntimeError):
    pass


# ------------------------------------------------------------------------------------ synthetic

def random_walk_minutes(start: str = "2020-01-06", days: int = 10, seed: int = 20260928, sd: float = 2e-4,
                        p0: float = 1.30, hours: tuple[int, int] = (0, 24), drop_frac: float = 0.0) -> pd.DataFrame:
    """Seeded Gaussian random walk of 1-minute prices on weekdays, in the original's input format.

    Columns ``date`` (string "YYYY-MM-DD HH:MM:SS", fixed UTC-5 clock like HistData) and ``price``.
    ``hours`` limits each day to [start_hour, end_hour); ``drop_frac`` deletes that share of bars at
    random (mimics minutes without ticks) but never the first bar of the series.
    SYNTHETIC: it has no relation to any market and no result computed on it is evidence of anything.
    """
    rng = np.random.default_rng(seed)
    day_idx = pd.bdate_range(start, periods=days)
    stamps = [d + pd.Timedelta(minutes=k) for d in day_idx for k in range(hours[0] * 60, hours[1] * 60)]
    t = pd.DatetimeIndex(stamps)
    price = p0 + np.cumsum(rng.normal(0.0, sd, len(t)))
    keep = np.ones(len(t), dtype=bool)
    if drop_frac > 0:
        keep = rng.random(len(t)) >= drop_frac
        keep[0] = True
    return pd.DataFrame({"date": t[keep].strftime("%Y-%m-%d %H:%M:%S"), "price": np.round(price[keep], 6)})


# ------------------------------------------------------------------------------------ HistData

HISTDATA_LINE = re.compile(r"^\d{8} \d{6};")


def parse_histdata_m1(text: str) -> pd.DataFrame:
    """Parse HistData "Generic ASCII" M1 bars: ``YYYYMMDD HHMMSS;open;high;low;close;volume`` (bid).

    Returns the original's input format: ``date`` (fixed UTC-5, as in the file) and ``price`` = bar
    CLOSE bid (declared interpretation, PREREG §3.3 A2).
    """
    df = pd.read_csv(io.StringIO(text), sep=";", header=None,
                     names=["stamp", "open", "high", "low", "close", "volume"], dtype={"stamp": str})
    if len(df) and not HISTDATA_LINE.match(f"{df['stamp'].iloc[0]};"):
        raise ValueError("not a HistData generic ASCII M1 file")
    t = pd.to_datetime(df["stamp"], format="%Y%m%d %H%M%S")
    out = pd.DataFrame({"date": t, "price": df["close"].astype(float)})
    return out.sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)


# ------------------------------------------------------------------------------------ locks

def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def require_prereg_seal(seal_dir: Path = PREREG_SEAL, prereg: Path = PREREG) -> dict:
    seal_json = Path(seal_dir) / "seal.json"
    if not seal_json.exists():
        raise LockError("PREREG.md is not sealed: no real price data may be loaded (PREREG §0).")
    from holdout_audit.seal import verify_seal

    info = verify_seal(Path(seal_dir))
    if info.get("status") != "verified":
        raise LockError("the PREREG.md seal is not verified")
    if info.get("subject_sha256") != sha256_file(prereg):
        raise LockError("the seal does not match the current PREREG.md")
    return info


def require_holdout_unlock(unlock: Path = UNLOCK, stage_a: Path = STAGE_A_RESULTS) -> dict:
    if not Path(unlock).exists():
        raise LockError("holdout is locked: HOLDOUT-UNLOCK.json not found (PREREG §6.1).")
    rec = json.loads(Path(unlock).read_text(encoding="utf-8"))
    if not Path(stage_a).exists() or sha256_file(stage_a) != rec.get("stage_a_results_sha256"):
        raise LockError("Stage A results missing or changed since the holdout was unlocked")
    return rec


def load_real(stage: str, raw_dir: Path = RAW) -> pd.DataFrame:
    """Load the real GBP/USD M1 series for a stage ('A' in-sample, 'B' full sample incl. holdout)."""
    require_prereg_seal()
    if stage == "B":
        require_holdout_unlock()
    elif stage != "A":
        raise ValueError("stage must be 'A' or 'B'")
    files = sorted(Path(raw_dir).glob("DAT_ASCII_GBPUSD_M1_*.csv"))
    if stage == "A":
        bad = [f.name for f in files if any(y in f.name for y in HOLDOUT_YEARS)]
        if bad:
            raise LockError(f"holdout files present during Stage A: {bad}. Move them out of raw/ first.")
    if not files:
        raise FileNotFoundError(f"no HistData M1 files in {raw_dir}")
    df = pd.concat([parse_histdata_m1(f.read_text(encoding="utf-8")) for f in files], ignore_index=True)
    df = df.sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)
    df = df[(df["date"] >= SAMPLE_START) & (df["date"] <= SAMPLE_END)]
    if stage == "A":
        if (df["date"] >= HOLDOUT_START).any():
            raise LockError("holdout timestamps found in Stage A input")
    return df.reset_index(drop=True)


def panel_sha256(df: pd.DataFrame) -> str:
    """Canonical hash of the parsed series (PREREG §5.3): 'YYYY-MM-DD HH:MM:SS,price' with 6 dp, LF."""
    t = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    body = "\n".join(t + "," + df["price"].map(lambda x: f"{x:.6f}")) + "\n"
    return hashlib.sha256(body.encode("ascii")).hexdigest()
