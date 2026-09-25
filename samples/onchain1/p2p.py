"""Minimal Bitcoin P2P client: fetch the block-header chain directly from public full nodes.

Why: block headers are the public Bitcoin blockchain itself (no vendor, no terms of service).
From headers we get each block's height and miner timestamp; subsidy per block is fixed by the
consensus rule 50 BTC >> (height // 210000). That is all Puell Multiple and stock-to-flow need.

Every header is checked: it must link to its predecessor (prev-hash) and meet its own
proof-of-work target (nBits). Only standard library.
"""
from __future__ import annotations

import hashlib
import random
import socket
import struct
import time

MAGIC = bytes.fromhex("f9beb4d9")
GENESIS = bytes.fromhex("000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f")[::-1]
SEEDS = ["seed.bitcoin.sipa.be", "dnsseed.bluematt.me", "seed.bitcoinstats.com",
         "seed.bitcoin.jonasschnelli.ch", "seed.btc.petertodd.net", "seed.bitcoin.sprovoost.nl",
         "dnsseed.emzy.de", "seed.bitcoin.wiz.biz"]


def dsha(b: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def varint(n: int) -> bytes:
    if n < 0xfd:
        return bytes([n])
    if n <= 0xffff:
        return b"\xfd" + struct.pack("<H", n)
    if n <= 0xffffffff:
        return b"\xfe" + struct.pack("<I", n)
    return b"\xff" + struct.pack("<Q", n)


def read_varint(b: bytes, i: int) -> tuple[int, int]:
    f = b[i]
    if f < 0xfd:
        return f, i + 1
    if f == 0xfd:
        return struct.unpack_from("<H", b, i + 1)[0], i + 3
    if f == 0xfe:
        return struct.unpack_from("<I", b, i + 1)[0], i + 5
    return struct.unpack_from("<Q", b, i + 1)[0], i + 9


def msg(cmd: str, payload: bytes) -> bytes:
    return MAGIC + cmd.encode().ljust(12, b"\0") + struct.pack("<I", len(payload)) + dsha(payload)[:4] + payload


class Peer:
    def __init__(self, host: str, port: int = 8333, timeout: float = 20):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.host = host

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            c = self.s.recv(n - len(buf))
            if not c:
                raise ConnectionError("peer closed")
            buf += c
        return buf

    def recv(self) -> tuple[str, bytes]:
        h = self._recv_exact(24)
        if h[:4] != MAGIC:
            raise ConnectionError("bad magic")
        cmd = h[4:16].rstrip(b"\0").decode()
        n = struct.unpack("<I", h[16:20])[0]
        p = self._recv_exact(n)
        if dsha(p)[:4] != h[20:24]:
            raise ConnectionError("bad checksum")
        return cmd, p

    def send(self, cmd: str, payload: bytes = b"") -> None:
        self.s.sendall(msg(cmd, payload))

    def handshake(self) -> int:
        addr = struct.pack(">Q", 0) + b"\0" * 10 + b"\xff\xff" + b"\0" * 4 + struct.pack(">H", 8333)
        ua = b"/holdout-labs-headers:0.1/"
        v = (struct.pack("<iQq", 70016, 0, int(time.time())) + addr + addr
             + struct.pack("<Q", random.getrandbits(64)) + varint(len(ua)) + ua + struct.pack("<i", 0) + b"\0")
        self.send("version", v)
        got_version = got_verack = False
        height = -1
        while not (got_version and got_verack):
            cmd, p = self.recv()
            if cmd == "version":
                got_version = True
                height = struct.unpack_from("<i", p, len(p) - 5)[0] if len(p) >= 85 else -1
                self.send("verack")
            elif cmd == "verack":
                got_verack = True
            elif cmd == "ping":
                self.send("pong", p)
        return height

    def getheaders(self, locator: list[bytes]) -> list[bytes]:
        payload = struct.pack("<I", 70016) + varint(len(locator)) + b"".join(locator) + b"\0" * 32
        self.send("getheaders", payload)
        while True:
            cmd, p = self.recv()
            if cmd == "headers":
                n, i = read_varint(p, 0)
                out = []
                for _ in range(n):
                    out.append(p[i:i + 80])
                    i += 81  # 80-byte header + tx count (always 0)
                return out
            if cmd == "ping":
                self.send("pong", p)


def target(bits: int) -> int:
    exp, mant = bits >> 24, bits & 0xffffff
    return mant << (8 * (exp - 3))


def verify_link(prev_hash: bytes, h: bytes) -> bytes:
    if h[4:36] != prev_hash:
        raise ValueError("header does not link to predecessor")
    hh = dsha(h)
    bits = struct.unpack_from("<I", h, 72)[0]
    if int.from_bytes(hh, "little") > target(bits):
        raise ValueError("header fails its proof-of-work target")
    return hh


def peers() -> list[str]:
    ips = []
    for s in SEEDS:
        try:
            ips += [a[4][0] for a in socket.getaddrinfo(s, 8333, socket.AF_INET, socket.SOCK_STREAM)]
        except OSError:
            pass
    random.shuffle(ips)
    return list(dict.fromkeys(ips))


def fetch_all_headers(stop_time: int | None = None, log=print) -> list[tuple[int, int, str]]:
    """Return [(height, timestamp, block_hash_hex)] for the whole chain from genesis (height 0)."""
    gen_ts = 1231006505
    rows = [(0, gen_ts, GENESIS[::-1].hex())]
    tip = GENESIS
    candidates = peers()
    for host in candidates:
        try:
            p = Peer(host)
            ph = p.handshake()
            log(f"peer {host} reports height {ph}")
            while True:
                hs = p.getheaders([tip])
                if not hs:
                    return rows
                for h in hs:
                    tip = verify_link(tip, h)
                    ts = struct.unpack_from("<I", h, 68)[0]
                    rows.append((len(rows), ts, tip[::-1].hex()))
                if len(rows) % 20000 < 2000:
                    log(f"  {len(rows)} headers")
                if len(hs) < 2000:
                    return rows
        except (OSError, ConnectionError, ValueError) as e:  # try the next peer, keep progress
            log(f"peer {host} failed: {e!r}; continuing from height {len(rows) - 1}")
    raise RuntimeError("no peer completed the header download")


if __name__ == "__main__":
    import sys
    if "--handshake-only" in sys.argv:
        for host in peers()[:5]:
            try:
                print(host, "height", Peer(host).handshake())
                break
            except Exception as e:  # noqa: BLE001
                print(host, "failed", e)
