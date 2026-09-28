"""The author's own London Breakout signal code, executed verbatim (reference for tests).

Loads lines 51-211 of the vendored upstream file (``upstream/London Breakout backtest.py``,
je-suis-tm/quant-trading @ 611b73f2, SHA-256 checked) and executes them. Those lines hold the two
functions ``london_breakout`` and ``signal_generation`` exactly as published. Skipped: the
module-level ``os.chdir('d:/')``, plotting and ``main()``, none of which affects signals.

``load_original(risky_stop=..., open_minutes=...)`` can swap the two hard-coded constants by exact
text substitution (each must occur exactly once), so grid variants can also be checked against the
author's code with nothing else changed.

This module is slow (the original recomputes a full cumulative sum on almost every bar, O(n^2)).
It is only for tests on small synthetic or hand-made series. The audit uses ``lb_port``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE / "upstream" / "London Breakout backtest.py"
UPSTREAM_SHA256 = "8b5a0f672c2c5a44fb5a72564fcb0b20a5bd2b0d3d9da3e2f4a52b2d047f8e3a"
UPSTREAM_COMMIT = "611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5"
FIRST_LINE, LAST_LINE = 51, 211  # 1-based, inclusive: def london_breakout ... return signals


def upstream_source() -> str:
    raw = UPSTREAM.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != UPSTREAM_SHA256:
        raise RuntimeError(f"upstream file changed: SHA-256 {got} != {UPSTREAM_SHA256}")
    lines = raw.decode("utf-8").splitlines()
    body = "\n".join(lines[FIRST_LINE - 1:LAST_LINE]) + "\n"
    assert body.startswith("def london_breakout(df):"), "unexpected upstream layout"
    assert body.rstrip().endswith("return signals"), "unexpected upstream layout"
    return body


def load_original(risky_stop: float | None = None, open_minutes: int | None = None):
    """Return the author's ``(signal_generation, london_breakout)`` functions."""
    body = upstream_source()
    for name, value, default in (("risky_stop", risky_stop, "0.01"), ("open_minutes", open_minutes, "30")):
        if value is None:
            continue
        old = f"{name}={default}\n"
        if body.count(old) != 1:
            raise RuntimeError(f"expected exactly one '{old.strip()}' in upstream code")
        body = body.replace(old, f"{name}={value!r}\n")
    ns: dict = {"pd": pd}
    exec(compile(body, str(UPSTREAM), "exec"), ns)  # noqa: S102 - pinned, hash-checked upstream code
    return ns["signal_generation"], ns["london_breakout"]


def run_original(df: pd.DataFrame, risky_stop: float | None = None, open_minutes: int | None = None) -> pd.DataFrame:
    """Run the author's code on a frame with columns ``date`` (str or datetime) and ``price``.

    The frame must have a default RangeIndex (the original indexes rows by position with ``[i]``).
    A copy is passed, because the original mutates its input.
    """
    signal_generation, london_breakout = load_original(risky_stop, open_minutes)
    out = signal_generation(df.reset_index(drop=True).copy(), london_breakout)
    return out
