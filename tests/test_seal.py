"""Sealed forward trial: the RFC 3161 client is injected; tests never touch the network."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from holdout_audit import seal as S

PREREG = {
    "strategy_name": "Example trend rule",
    "rules": "Hold SPY when close > 200-day SMA, else cash. Signal at close, applied next day.",
    "parameters": {"sma": 200},
    "instruments": ["SPY"],
    "forward_start": "2026-10-01",
    "forward_end": "2026-12-31",
    "primary_metric": "annualised Sharpe of daily returns",
    "pass_criteria": "Sharpe > 0 and max drawdown < 15% over the window",
    "data_source": "client broker statements",
}


class FakeTSA:
    """Deterministic stand-in for an RFC 3161 authority."""

    def __init__(self, name, ok=True, gen="2026-09-25T12:00:00Z"):
        self.name, self.ok, self.gen = name, ok, gen
        self.calls = []

    def stamp(self, digest_hex, workdir: Path):
        self.calls.append(digest_hex)
        if not self.ok:
            return S.Receipt(self.name, False, None, None, None, "simulated outage")
        tok = workdir / f"{digest_hex[:16]}.{self.name}.tsr"
        body = f"FAKE-TOKEN|{self.name}|{digest_hex}|{self.gen}".encode()
        tok.write_bytes(body)
        return S.Receipt(self.name, True, self.gen, tok.name, hashlib.sha256(body).hexdigest(), "fake")

    def verify(self, digest_hex, token_path: Path):
        return token_path.read_bytes().split(b"|")[2].decode() == digest_hex


def test_seal_and_verify(tmp_path):
    a, b = FakeTSA("digicert"), FakeTSA("freetsa")
    res = S.seal_preregistration(PREREG, tmp_path / "trial-001", [a, b])
    assert res.status == "verified"
    data = (tmp_path / "trial-001" / "prereg.json").read_bytes()
    assert hashlib.sha256(data).hexdigest() == res.prereg_sha256 == a.calls[0] == b.calls[0]
    out = S.verify_seal(tmp_path / "trial-001", [a, b])
    assert out["verified_tsas"] == ["digicert", "freetsa"]
    assert out["earliest_gen_time_utc"] == "2026-09-25T12:00:00Z"


def test_canonical_hash_is_key_order_independent(tmp_path):
    r1 = S.seal_preregistration(PREREG, tmp_path / "a", [FakeTSA("x")])
    r2 = S.seal_preregistration(dict(reversed(list(PREREG.items()))), tmp_path / "b", [FakeTSA("x")])
    assert r1.prereg_sha256 == r2.prereg_sha256


def test_tamper_detected(tmp_path):
    d = tmp_path / "t"
    S.seal_preregistration(PREREG, d, [FakeTSA("digicert")])
    doc = json.loads((d / "prereg.json").read_text())
    doc["parameters"]["sma"] = 150
    (d / "prereg.json").write_bytes(S.canonical_bytes(doc))
    with pytest.raises(S.SealError, match="altered"):
        S.verify_seal(d)


def test_token_tamper_detected(tmp_path):
    d = tmp_path / "t"
    r = S.seal_preregistration(PREREG, d, [FakeTSA("digicert")])
    (d / r.receipts[0].token_file).write_bytes(b"forged")
    with pytest.raises(S.SealError, match="token"):
        S.verify_seal(d)


def test_outage_gives_failed_status(tmp_path):
    r = S.seal_preregistration(PREREG, tmp_path / "t", [FakeTSA("digicert", ok=False), FakeTSA("freetsa", ok=False)])
    assert r.status == "failed"
    assert S.verify_seal(tmp_path / "t")["status"] == "failed"


def test_one_of_two_is_enough_by_default(tmp_path):
    r = S.seal_preregistration(PREREG, tmp_path / "t", [FakeTSA("digicert", ok=False), FakeTSA("freetsa")])
    assert r.status == "verified"
    r2 = S.seal_preregistration(PREREG, tmp_path / "u", [FakeTSA("digicert", ok=False), FakeTSA("freetsa")],
                                min_verified=2)
    assert r2.status == "failed"


def test_registry_chain(tmp_path):
    for i in range(3):
        S.seal_preregistration(PREREG, tmp_path / f"trial-{i}", [FakeTSA("x")])
    reg = tmp_path / "registry.jsonl"
    assert S.verify_registry_chain(reg) == 3
    lines = reg.read_bytes().splitlines()
    e = json.loads(lines[1])
    e["status"] = "edited"
    lines[1] = S.canonical_bytes(e).rstrip(b"\n")
    reg.write_bytes(b"\n".join(lines) + b"\n")
    with pytest.raises(S.SealError, match="chain"):
        S.verify_registry_chain(reg)


def test_prereg_validation():
    bad = dict(PREREG)
    del bad["pass_criteria"]
    with pytest.raises(ValueError, match="pass_criteria"):
        S.validate_preregistration(bad)
    worse = dict(PREREG, forward_end="2026-01-01")
    with pytest.raises(ValueError, match="after"):
        S.validate_preregistration(worse)


def test_rfc3161_client_with_injected_openssl_and_http(tmp_path):
    """Exercise Rfc3161Client's control flow with a fake openssl runner and fake HTTP."""
    calls = []

    def runner(args, capture_output, timeout):
        calls.append(args)
        if "-query" in args:
            Path(args[args.index("-out") + 1]).write_bytes(b"TSQ")
            return subprocess.CompletedProcess(args, 0, b"", b"")
        if "-reply" in args:
            return subprocess.CompletedProcess(args, 0, b"Status: Granted.\nTime stamp: Sep 25 12:39:01 2026 GMT\n", b"")
        return subprocess.CompletedProcess(args, 0, b"Verification: OK\n", b"")

    def http_post(url, data, timeout):
        assert data == b"TSQ"
        return 200, b"TSR-BYTES"

    c = S.Rfc3161Client("digicert", "http://tsa.example", tmp_path / "ca.pem", http_post=http_post,
                        runner=runner, openssl="openssl")
    digest = hashlib.sha256(b"x").hexdigest()
    r = c.stamp(digest, tmp_path)
    assert r.verified and r.gen_time_utc == "2026-09-25T12:39:01Z"
    assert r.token_sha256 == hashlib.sha256(b"TSR-BYTES").hexdigest()
    assert any("-queryfile" in a for a in calls) and any("-digest" in a and "-verify" in a for a in calls)


def test_rfc3161_client_network_failure_is_not_a_crash(tmp_path):
    def runner(args, capture_output, timeout):
        Path(args[args.index("-out") + 1]).write_bytes(b"TSQ")
        return subprocess.CompletedProcess(args, 0, b"", b"")

    def http_post(url, data, timeout):
        raise OSError("network down")

    c = S.Rfc3161Client("freetsa", "https://tsa.example", tmp_path / "ca.pem", http_post=http_post,
                        runner=runner, openssl="openssl")
    r = c.stamp(hashlib.sha256(b"y").hexdigest(), tmp_path)
    assert not r.verified and "network down" in r.detail


def test_parse_gen_time():
    assert S.parse_gen_time("Time stamp: Jan  5 03:04:05.123 2027 GMT") == "2027-01-05T03:04:05Z"
    assert S.parse_gen_time("nothing") is None


def test_default_clients_have_pinned_certs():
    for c in S.default_clients():
        assert c.cafile.exists()
        assert c.cafile.read_text().startswith("-----BEGIN CERTIFICATE-----")


def test_seal_document_and_verify(tmp_path):
    doc = tmp_path / "docs" / "RUBRIC.md"
    doc.parent.mkdir()
    doc.write_bytes(b"# rubric v1\nPASS DSR >= 0.95\n")
    out = tmp_path / "docs" / "rubric-seal"
    a, b = FakeTSA("digicert"), FakeTSA("freetsa")
    res = S.seal_document(doc, out, [a, b])
    assert res.status == "verified"
    assert res.prereg_sha256 == hashlib.sha256(doc.read_bytes()).hexdigest() == a.calls[0]
    seal = json.loads((out / "seal.json").read_text())
    assert seal["subject_file"] == "../RUBRIC.md"
    info = S.verify_seal(out, [a, b])
    assert info["subject_sha256"] == res.prereg_sha256 and info["verified_tsas"] == ["digicert", "freetsa"]
    assert not (out / "prereg.json").exists()  # the document is sealed in place, not copied
    doc.write_bytes(b"# rubric v1\nPASS DSR >= 0.90\n")
    with pytest.raises(S.SealError, match="altered"):
        S.verify_seal(out, [a, b])
