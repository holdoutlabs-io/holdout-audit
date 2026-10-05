"""COINTIME-1: the True Market Mean, tested as published. Runs the sealed PREREG.md once.

    uv run python samples/cointime1/run.py crosscheck   # §2: build TMM/AVIV, compare with public quotes (gate)
    uv run python samples/cointime1/run.py run          # §3: M1, M2 (Holm), R1 strategy audit, descriptives

Construction (PREREG §2, unchanged): coin-days for coinblocks; minted coins valued at the daily close used by the
ONCHAIN-1 realized cap (Bitstamp 2011-08-18..2015-07-19, Coinbase from 2015-07-20, 0 before: days with no price
contribute zero). Tests reuse samples/onchain1/run.py (episodes, fwd, zone_test, holm) unchanged and the
strategy_audit pattern of run_family_b.py. Statistical analysis of past data only; not investment advice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SAMPLES = HERE.parent
sys.path.insert(0, str(SAMPLES / "onchain1"))
sys.path.insert(0, str(SAMPLES))
import run as A  # noqa: E402  (samples/onchain1/run.py, unchanged)
import before_after as BA  # noqa: E402  (ONCHAIN-1 cycle_tops / cycle_lows, unchanged)
import strategies as S  # noqa: E402

from holdout_audit import AuditConfig, run_audit  # noqa: E402
from holdout_audit.report import write_report  # noqa: E402

PREREG = HERE / "PREREG.md"
PREREG_SHA = "270357082c5f85211245e9d050e71125d26d201738b8a89d03c80794ff526bea"
CROSS = HERE / "CROSSCHECK-QUOTES.md"
CROSS_SHA = "3492c4652199925544c49dfdbbad9aea49611fd37d4cab0025fed4eefb4a2d24"
METRICS = SAMPLES / "onchain1" / "bq" / "metrics_daily.csv"
OOS = pd.Timestamp("2023-08-24")
REPORTS = HERE / "reports"

PRIMARY = [("P1", "2023-01-01", 28659), ("P2", "2023-10-10", 29720), ("P3", "2023-12-20", 31896),
           ("P4", "2024-10-08", 47000), ("P5", "2025-12-10", 81300), ("P6", "2026-02-18", 79000),
           ("P7", "2026-04-29", 78500), ("P8", "2026-09-16", 76700)]
CONTEXT = [("C1", "2024-10-08", 52500), ("C2", "2025-10-30", 88000)]


def build() -> tuple[pd.DataFrame, pd.Series, list[str], str]:
    assert A.sha(PREREG) == PREREG_SHA, "PREREG.md differs from the sealed version"
    assert A.sha(CROSS) == CROSS_SHA, "CROSSCHECK-QUOTES.md differs from the sealed version"
    m = pd.read_csv(METRICS, parse_dates=["date"]).set_index("date").sort_index()
    m_sha = A.sha(METRICS)
    # Daily close used by the ONCHAIN-1 realized cap: market cap / supply where a price exists, else 0.
    px_m = (m["market_cap_usd"] / m["supply_btc"]).fillna(0.0)
    minted = m["supply_btc"].diff().fillna(m["supply_btc"].iloc[0])
    thermocap = (minted * px_m).cumsum()
    liveliness = m["cdd"].cumsum() / m["supply_btc"].cumsum()
    investor_cap = m["realized_cap_usd"] - thermocap
    active_supply = liveliness * m["supply_btc"]
    tmm = investor_cap / active_supply
    close, price_notes = A.load_price()  # sealed Coinbase series, forward-filled, to 2026-09-24
    out = pd.DataFrame({"px_metrics": px_m, "thermocap": thermocap, "liveliness": liveliness,
                        "investor_cap": investor_cap, "active_supply": active_supply, "tmm": tmm,
                        "mvrv": m["mvrv"], "sth_cost_basis": m["sth_cost_basis"]})
    out["aviv_metrics_close"] = np.where(px_m > 0, px_m / tmm, np.nan)
    return out, close, price_notes, m_sha


def crosscheck() -> dict:
    T, close, _, m_sha = build()
    rows = []
    for tag, d, q in PRIMARY + CONTEXT:
        ours = float(T.loc[pd.Timestamp(d), "tmm"])
        rows.append({"id": tag, "date": d, "quoted": q, "ours": round(ours, 0), "diff_pct": round(100 * (ours / q - 1), 2),
                     "set": "primary" if tag.startswith("P") else "context"})
    prim = [abs(r["diff_pct"]) for r in rows if r["set"] == "primary"]
    med = float(np.median(prim))
    res = {"metrics_sha256": m_sha, "rows": rows, "median_abs_diff_pct_primary": round(med, 2), "gate_5pct": med <= 5.0}
    (HERE / "crosscheck.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    for r in rows:
        print(r)
    print("median abs diff (primary):", round(med, 2), "% -> gate", "PASS" if med <= 5.0 else "FAIL: investigate, log deviation")
    return res


def crossings(series: pd.Series) -> pd.DatetimeIndex:
    s = np.sign(series.dropna())
    return s.index[(s != s.shift(1)) & s.shift(1).notna()]


def run() -> int:
    cc = json.loads((HERE / "crosscheck.json").read_text(encoding="utf-8"))
    assert cc["gate_5pct"], "cross-check gate failed: investigate and log a deviation before §3"
    T, close, price_notes, m_sha = build()
    tmm = T["tmm"].reindex(close.index)
    aviv = close / tmm
    res = {"prereg_sha256": PREREG_SHA, "metrics_csv_sha256": m_sha, "crosscheck": cc, "price_notes": price_notes,
           "oos_window": [str(OOS.date()), str(A.END.date())], "tests": {}}
    # §3 M1, M2 (Holm family {M1, M2})
    specs = [("M1", "AVIV < 1.0 (price below the True Market Mean)", aviv < 1.0, +1),
             ("M2", "AVIV >= 1.5", aviv >= 1.5, -1)]
    ps = []
    for tid, label, zone, direction in specs:
        t = A.zone_test(zone, close, 90, direction, OOS)
        t["label"] = label
        t["zone_share_of_oos_days"] = float(zone.loc[OOS:A.END].fillna(False).astype(bool).mean())
        ps.append(t["p_one_sided"] if (t["inferential"] and t["p_one_sided"] is not None) else 1.0)
        res["tests"][tid] = t
    for (tid, *_), p, a in zip(specs, ps, A.holm(ps)):
        t = res["tests"][tid]
        t["holm"] = {"p_entered": p, "p_holm": a, "status": (
            "NOT TESTABLE (descriptive only)" if not t["inferential"]
            else ("SUPPORTED" if a <= 0.05 else "NOT SUPPORTED"))}
    # §3 R1 strategy audit (rubric v1.1, objective (a), N = 1, 10 bps, default holdout)
    pos = (close > tmm).astype(float).where(tmm.notna(), 0.0)
    ret = close.pct_change()
    df = S.apply_positions(pos, ret).loc[OOS:A.END].assign(market=ret.loc[OOS:A.END])
    REPORTS.mkdir(exist_ok=True)
    cfg = AuditConfig(
        name="COINTIME-1 R1: True Market Mean regime line, post-publication",
        description="Implied rule of the True Market Mean (Check & Puell 2023, Cointime Economics), frozen in the "
                    "sealed COINTIME-1 preregistration before any value was computed and run once. Benchmark: "
                    "buy-and-hold BTC. Objective (a).",
        rules="Hold BTC when the close is above the True Market Mean (Investor Cap / Active Supply, self-computed from "
              "the public blockchain with coin-days and daily closes), cash otherwise; decided at the close, held "
              "close to close.",
        returns=df, n_trials=1, base_cost_bps=A.COST, seed=A.SEED, rubric_version="1.1", periods_per_year=365,
        preregistration_file=str(PREREG), preregistration_seal_dir=str(HERE / "prereg-seal"),
        data_files={"btc_daily.csv": A.PRICE_FILE, "metrics_daily.csv": METRICS},
        data_notes=[
            "Prices from the Coinbase Exchange public market-data API; derived statistics only, never raw prices; "
            "no redistribution. BTC-USD daily closes (UTC).",
            "True Market Mean self-computed from the ONCHAIN-1 public-blockchain metrics (Google BigQuery public "
            "dataset crypto_bitcoin); coin-days for coinblocks and daily closes for minted coins, as preregistered.",
            f"Audit period {OOS.date()} (day after publication) to {A.END.date()}, fixed in the sealed preregistration. N = 1.",
        ] + price_notes)
    r = run_audit(cfg)
    write_report(r, REPORTS / "r1-true-market-mean.html")
    hd = r.headline()
    hd["checks"] = {c.key: c.status for c in r.grade.checks}
    held = df["return"] - df["turnover"] * A.COST / 1e4
    years = len(held) / 365
    hd["compound_growth_rule"] = float((1 + held).prod() ** (1 / years) - 1)
    hd["compound_growth_hold"] = float((1 + df["market"]).prod() ** (1 / years) - 1)
    hd["time_in_market"] = float(pos.loc[OOS:A.END].mean())
    res["tests"]["R1"] = hd
    # Descriptives: share of days AVIV > 1; responsiveness at cycle turns
    pre = aviv.loc[:OOS - pd.Timedelta(days=1)].dropna()
    post = aviv.loc[OOS:A.END].dropna()
    full_pre = T["aviv_metrics_close"].loc[:"2023-05-08"].dropna()
    res["descriptive"] = {
        "share_aviv_gt1_to_2023_05_08_metrics_close": float((full_pre > 1).mean()),
        "share_aviv_gt1_before_publication_coinbase": float((pre > 1).mean()),
        "share_aviv_gt1_after_publication": float((post > 1).mean()),
        "aviv_range_after_publication": [float(post.min()), float(post.max())],
        "aviv_last": float(aviv.loc[A.END]), "tmm_last": float(tmm.loc[A.END]),
    }
    pxm = T["px_metrics"].replace(0.0, np.nan).dropna()
    tops = BA.cycle_tops(pxm, BA.DD_PRIMARY, BA.ATH_SEED)
    lows = BA.cycle_lows(pxm, tops)
    turns = ([{"kind": "top", "date": str(t["date"].date()), "confirmed": t["confirmed"]} for t in tops if t["date"] >= OOS]
             + [{"kind": "bottom", "date": str(l["date"].date()), "provisional": l["provisional"]} for l in lows if l["date"] >= OOS])
    lines = {"AVIV=1": crossings(aviv - 1), "MVRV=1": crossings(T["mvrv"].reindex(close.index) - 1),
             "close=STH cost basis": crossings(close - T["sth_cost_basis"].reindex(close.index))}
    for t in turns:
        d = pd.Timestamp(t["date"])
        for name, xs in lines.items():
            t[f"nearest_{name}_days"] = int(min(abs((x - d).days) for x in xs)) if len(xs) else None
    res["descriptive"]["cycle_turns_in_window"] = turns
    (HERE / "results.json").write_text(json.dumps(res, indent=2, default=str) + "\n", encoding="utf-8")
    for tid in ("M1", "M2"):
        t = res["tests"][tid]
        print(tid, t["label"], "| zone days", t["zone_days"], "| episodes", t["episodes"], "| D", t["D"],
              "| p", t["p_one_sided"], "|", t["holm"]["status"])
    print("R1 grade", hd.get("grade"), "| excess SR", hd.get("excess_sr_annual"), "| CAGR rule/hold",
          round(hd["compound_growth_rule"], 4), round(hd["compound_growth_hold"], 4), "| checks", hd["checks"])
    print("descriptive", json.dumps(res["descriptive"], default=str)[:900])
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "crosscheck":
        crosscheck()
    elif cmd == "run":
        raise SystemExit(run())
    else:
        raise SystemExit("usage: run.py crosscheck | run")
