"""Sealed forward trial: preregister a strategy, hash it and RFC 3161-timestamp the hash.

A preregistration fixes, *before* any forward data exist, the strategy's rules, parameters,
instruments, the forward-test window and the pass/fail criteria. Its canonical JSON is hashed
with SHA-256 and the hash is timestamped by independent RFC 3161 timestamp authorities
(DigiCert and FreeTSA by default). Anyone can later check that the rules were fixed no later
than the authorities' signed time and have not changed since.

Design notes
- The timestamp client is injectable (``TimestampClient`` protocol). Tests use a fake;
  production uses ``Rfc3161Client``, which shells out to the ``openssl ts`` CLI and posts over
  HTTP with the standard library.
- Seals are appended to a hash-chained ``registry.jsonl``: each entry carries the SHA-256 of
  the previous entry, so deleting or editing an earlier seal breaks the chain.
- A TSA outage never raises: the receipt is recorded as unverified and the seal's status is
  ``failed`` unless at least ``min_verified`` authorities verified.

The RFC 3161 flow (query with nonce, double verification against imprint and query file,
pinned CA files) is adapted from the maintainers' earlier private research code; see NOTICE.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol, Sequence

CERT_DIR = Path(__file__).parent / "certs"
SEAL_FORMAT = "holdout-labs-seal/1"
PREREG_FORMAT = "holdout-labs-preregistration/1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


# ------------------------------------------------------------------ canonical hashing


def canonical_bytes(obj) -> bytes:
    """Deterministic JSON: sorted keys, no insignificant whitespace, UTF-8, trailing newline."""
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def fmt_utc(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


REQUIRED_PREREG_FIELDS = ("strategy_name", "rules", "parameters", "instruments", "forward_start", "forward_end",
                          "primary_metric", "pass_criteria", "data_source")


def validate_preregistration(prereg: dict) -> dict:
    """Check required fields and return a normalised copy with the format tag."""
    missing = [k for k in REQUIRED_PREREG_FIELDS if k not in prereg or prereg[k] in (None, "", [], {})]
    if missing:
        raise ValueError(f"preregistration is missing: {', '.join(missing)}")
    start = dt.date.fromisoformat(str(prereg["forward_start"]))
    end = dt.date.fromisoformat(str(prereg["forward_end"]))
    if end <= start:
        raise ValueError("forward_end must be after forward_start")
    out = dict(prereg)
    out["format"] = PREREG_FORMAT
    return out


# ------------------------------------------------------------------ timestamp clients


@dataclass(frozen=True)
class Receipt:
    tsa: str
    verified: bool
    gen_time_utc: str | None
    token_file: str | None
    token_sha256: str | None
    detail: str

    def to_dict(self) -> dict:
        return {"tsa": self.tsa, "verified": self.verified, "gen_time_utc": self.gen_time_utc,
                "token_file": self.token_file, "token_sha256": self.token_sha256, "detail": self.detail}


class TimestampClient(Protocol):
    name: str

    def stamp(self, digest_hex: str, workdir: Path) -> Receipt:
        """Timestamp ``digest_hex`` (SHA-256), storing any token bytes in ``workdir``."""

    def verify(self, digest_hex: str, token_path: Path) -> bool:
        """Re-verify a stored token against the digest."""


_GIT_OPENSSL = (r"C:\Program Files\Git\mingw64\bin\openssl.exe", r"C:\Program Files\Git\usr\bin\openssl.exe")


def find_openssl() -> str | None:
    env = os.environ.get("HOLDOUT_OPENSSL")
    if env and Path(env).exists():
        return env
    found = shutil.which("openssl")
    if found:
        return found
    return next((c for c in _GIT_OPENSSL if Path(c).exists()), None)


def urllib_post(url: str, data: bytes, timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/timestamp-query"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed TSA URLs
        return resp.status, resp.read()


_TIME_RE = re.compile(r"Time stamp: (\w{3})\s+(\d{1,2}) (\d{2}):(\d{2}):(\d{2})(?:\.\d+)? (\d{4}) GMT")
_MONTHS = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def parse_gen_time(reply_text: str) -> str | None:
    m = _TIME_RE.search(reply_text)
    if not m:
        return None
    mon, day, hh, mi, ss, year = m.groups()
    t = dt.datetime(int(year), _MONTHS[mon], int(day), int(hh), int(mi), int(ss), tzinfo=dt.timezone.utc)
    return fmt_utc(t)


class Rfc3161Client:
    """RFC 3161 client using the ``openssl ts`` CLI. ``http_post`` and ``runner`` are injectable."""

    def __init__(self, name: str, url: str, cafile: Path, untrusted: Path | None = None,
                 http_post: Callable[[str, bytes, float], tuple[int, bytes]] = urllib_post,
                 runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                 openssl: str | None = None, timeout: float = 30.0):
        self.name, self.url, self.cafile, self.untrusted = name, url, Path(cafile), untrusted
        self.http_post, self.runner, self.timeout = http_post, runner, timeout
        self.openssl = openssl or find_openssl()

    def _run(self, args: Sequence[str]) -> tuple[int, str]:
        if not self.openssl:
            raise RuntimeError("openssl not found (set HOLDOUT_OPENSSL or put openssl on PATH)")
        cp = self.runner([self.openssl, *args], capture_output=True, timeout=60)
        out = cp.stdout if isinstance(cp.stdout, str) else (cp.stdout or b"").decode("utf-8", "replace")
        err = cp.stderr if isinstance(cp.stderr, str) else (cp.stderr or b"").decode("utf-8", "replace")
        return cp.returncode, out + err

    def _verify_args(self, token: Path) -> list[str]:
        args = ["ts", "-verify", "-in", str(token), "-CAfile", str(self.cafile)]
        if self.untrusted is not None:
            args += ["-untrusted", str(self.untrusted)]
        return args

    def stamp(self, digest_hex: str, workdir: Path) -> Receipt:
        if not _HEX64.match(digest_hex):
            raise ValueError("digest must be lowercase hex SHA-256")
        workdir.mkdir(parents=True, exist_ok=True)
        tsq = workdir / f"{digest_hex[:16]}.{self.name}.tsq"
        tsr = workdir / f"{digest_hex[:16]}.{self.name}.tsr"
        try:
            rc, out = self._run(["ts", "-query", "-digest", digest_hex, "-sha256", "-cert", "-out", str(tsq)])
            if rc != 0:
                return Receipt(self.name, False, None, None, None, f"query failed: {out.strip()[-200:]}")
            status, body = self.http_post(self.url, tsq.read_bytes(), self.timeout)
            if status != 200 or not body:
                return Receipt(self.name, False, None, None, None, f"http status {status}")
            tsr.write_bytes(body)
            rc, text = self._run(["ts", "-reply", "-in", str(tsr), "-text"])
            gen = parse_gen_time(text) if rc == 0 else None
            ok1 = self._run(self._verify_args(tsr) + ["-digest", digest_hex])
            ok2 = self._run(self._verify_args(tsr) + ["-queryfile", str(tsq)])
            ok = all(r == 0 and "Verification: OK" in o for r, o in (ok1, ok2)) and gen is not None
            return Receipt(self.name, ok, gen, tsr.name, sha256_hex(body),
                           "granted and verified" if ok else f"verification failed: {ok1[1].strip()[-200:]}")
        except Exception as exc:  # network or tool trouble is a failed receipt, never a crash
            return Receipt(self.name, False, None, None, None, f"{type(exc).__name__}: {exc}")

    def verify(self, digest_hex: str, token_path: Path) -> bool:
        rc, out = self._run(self._verify_args(token_path) + ["-digest", digest_hex])
        return rc == 0 and "Verification: OK" in out


def default_clients() -> list[Rfc3161Client]:
    return [
        Rfc3161Client("digicert", "http://timestamp.digicert.com", CERT_DIR / "digicert-trusted-root-g4.pem"),
        Rfc3161Client("freetsa", "https://freetsa.org/tsr", CERT_DIR / "freetsa-cacert.pem", CERT_DIR / "freetsa-tsa.crt"),
    ]


# ------------------------------------------------------------------ sealing


@dataclass
class SealResult:
    prereg_sha256: str
    status: str  # "verified" | "failed"
    receipts: list = field(default_factory=list)
    seal_path: Path | None = None
    registry_entry_sha256: str | None = None


def _last_entry_hash(registry: Path) -> str | None:
    if not registry.exists():
        return None
    lines = [ln for ln in registry.read_bytes().splitlines() if ln.strip()]
    return sha256_hex(lines[-1] + b"\n") if lines else None


def seal_preregistration(prereg: dict, out_dir: Path, clients: Sequence[TimestampClient] | None = None,
                         min_verified: int = 1, now: Callable[[], dt.datetime] = utc_now) -> SealResult:
    """Write ``prereg.json``, timestamp its SHA-256 with every client, write ``seal.json`` and
    append the seal to the hash-chained ``registry.jsonl`` in ``out_dir``'s parent registry."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = validate_preregistration(prereg)
    data = canonical_bytes(doc)
    digest = sha256_hex(data)
    (out_dir / "prereg.json").write_bytes(data)
    clients = list(default_clients() if clients is None else clients)
    requested = now()
    receipts = [c.stamp(digest, out_dir) for c in clients]
    n_ok = len({r.tsa for r in receipts if r.verified})
    status = "verified" if n_ok >= min_verified else "failed"
    seal = {
        "format": SEAL_FORMAT,
        "prereg_file": "prereg.json",
        "prereg_sha256": digest,
        "requested_at_utc": fmt_utc(requested),
        "receipts": [r.to_dict() for r in receipts],
        "status": status,
        "min_verified": min_verified,
    }
    seal_bytes = canonical_bytes(seal)
    (out_dir / "seal.json").write_bytes(seal_bytes)
    registry = out_dir.parent / "registry.jsonl"
    entry = {
        "seal_dir": out_dir.name,
        "prereg_sha256": digest,
        "seal_sha256": sha256_hex(seal_bytes),
        "status": status,
        "recorded_at_utc": fmt_utc(now()),
        "prev_entry_sha256": _last_entry_hash(registry),
    }
    line = canonical_bytes(entry)
    with open(registry, "ab") as f:
        f.write(line)
    return SealResult(digest, status, receipts, out_dir / "seal.json", sha256_hex(line))


class SealError(RuntimeError):
    pass


def seal_document(doc_path: Path, out_dir: Path, clients: Sequence[TimestampClient] | None = None,
                  min_verified: int = 1, now: Callable[[], dt.datetime] = utc_now) -> SealResult:
    """Timestamp the SHA-256 of an existing file (e.g. a frozen rubric) without copying it.

    ``seal.json`` records the file's path relative to ``out_dir`` and its hash, so that
    ``verify_seal`` can re-hash it in place; the token is also verifiable directly with
    ``openssl ts -verify -data <file> -in <token> -CAfile <ca>``.
    """
    doc_path, out_dir = Path(doc_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_hex(doc_path.read_bytes())
    rel = Path(os.path.relpath(doc_path.resolve(), out_dir.resolve())).as_posix()
    clients = list(default_clients() if clients is None else clients)
    requested = now()
    receipts = [c.stamp(digest, out_dir) for c in clients]
    n_ok = len({r.tsa for r in receipts if r.verified})
    status = "verified" if n_ok >= min_verified else "failed"
    seal = {
        "format": SEAL_FORMAT,
        "subject_file": rel,
        "subject_sha256": digest,
        "requested_at_utc": fmt_utc(requested),
        "receipts": [r.to_dict() for r in receipts],
        "status": status,
        "min_verified": min_verified,
    }
    seal_bytes = canonical_bytes(seal)
    (out_dir / "seal.json").write_bytes(seal_bytes)
    registry = out_dir.parent / "registry.jsonl"
    entry = {"seal_dir": out_dir.name, "subject_sha256": digest, "seal_sha256": sha256_hex(seal_bytes),
             "status": status, "recorded_at_utc": fmt_utc(now()), "prev_entry_sha256": _last_entry_hash(registry)}
    line = canonical_bytes(entry)
    with open(registry, "ab") as f:
        f.write(line)
    return SealResult(digest, status, receipts, out_dir / "seal.json", sha256_hex(line))


def verify_seal(out_dir: Path, clients: Sequence[TimestampClient] | None = None) -> dict:
    """Re-derive a seal's claims from stored bytes; raise SealError on any mismatch.

    Checks: prereg.json hashes to the sealed digest; each claimed-verified token exists, matches
    its recorded hash and (when a matching client is supplied) verifies cryptographically.
    """
    out_dir = Path(out_dir)
    seal = json.loads((out_dir / "seal.json").read_text(encoding="utf-8"))
    if seal.get("format") != SEAL_FORMAT:
        raise SealError("unknown seal format")
    subject = seal.get("prereg_file") or seal.get("subject_file")
    claimed = seal.get("prereg_sha256") or seal.get("subject_sha256")
    if not subject or not (out_dir / subject).exists():
        raise SealError("sealed file is missing")
    digest = sha256_hex((out_dir / subject).read_bytes())
    if digest != claimed:
        raise SealError("sealed file was altered after sealing")
    by_name = {c.name: c for c in (clients or [])}
    good = []
    for r in seal["receipts"]:
        if not r["verified"]:
            continue
        tok = out_dir / r["token_file"]
        if not tok.exists() or sha256_hex(tok.read_bytes()) != r["token_sha256"]:
            raise SealError(f"token for {r['tsa']} missing or altered")
        c = by_name.get(r["tsa"])
        if c is not None and not c.verify(digest, tok):
            raise SealError(f"token for {r['tsa']} does not verify")
        good.append(r)
    if seal["status"] == "verified" and len(good) < seal["min_verified"]:
        raise SealError("seal claims verified but has too few verified receipts")
    times = sorted(r["gen_time_utc"] for r in good if r["gen_time_utc"])
    return {"prereg_sha256": digest, "subject_sha256": digest, "seal_sha256": sha256_hex((out_dir / "seal.json").read_bytes()),
            "status": seal["status"], "verified_tsas": [r["tsa"] for r in good],
            "earliest_gen_time_utc": times[0] if times else None}


def verify_registry_chain(registry: Path) -> int:
    """Check the hash chain of a registry file; returns the number of entries."""
    prev = None
    n = 0
    for raw in Path(registry).read_bytes().splitlines():
        if not raw.strip():
            continue
        entry = json.loads(raw)
        if entry.get("prev_entry_sha256") != prev:
            raise SealError(f"registry chain broken at entry {n}")
        prev = sha256_hex(raw + b"\n")
        n += 1
    return n
