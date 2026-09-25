"""Indicator Audit, Batch 3 ("Strongest published evidence"): run the 6 preregistered audits once each.

    uv run python samples/batch3/run_batch3.py

Follows samples/batch3/prereg/ (sealed 2026-09-25T20:39Z). Each audit is graded under rubric v1.2 on the
objective its source claims, declared in its sealed declaration file. Statistical findings about past data
only; not investment advice.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SAMPLES = HERE.parent
sys.path[:0] = [str(HERE), str(SAMPLES), str(SAMPLES / "data")]

import batch3_rules as R  # noqa: E402
import fetch  # noqa: E402
import spec  # noqa: E402

from holdout_audit import AuditConfig, run_audit  # noqa: E402
from holdout_audit.report import write_report  # noqa: E402
from holdout_audit.stats.haircut import holm_adjusted  # noqa: E402

PRE = HERE / "prereg"
PREREG = PRE / "batch3-preregistration.json"
SEAL = PRE / "seal-batch3-preregistration"
SEALED_AT = "2026-09-25T20:39:55Z"  # the last of the seven seals
REPORTS = HERE / "reports"
SEED = 20260925
PROVENANCE = ("Prices from Yahoo Finance's public chart endpoint; we publish derived statistics only, never raw prices; no "
              "redistribution. Signals use the split-adjusted close; total returns use the split- and dividend-adjusted close.")


def load(sym):
    df = pd.read_csv(fetch.RAW / fetch.batch2_file(sym), parse_dates=["date"]).set_index("date").sort_index()
    df["tr"] = df["adjclose"].pct_change()
    return df


def _cagr(x):
    x = x.dropna()
    return float(np.prod(1 + x.to_numpy()) ** (252 / len(x)) - 1)


def benchmark(rule, data, start):
    if rule in ("vol_managed", "lowvol_sectors", "lowvol_etf"):
        return data["SPY"]["tr"]
    if rule == "tsmom":
        return R.equal_weight_hold(data, R.TSMOM_ASSETS, start)
    if rule == "gtaa":
        return R.equal_weight_hold(data, R.GTAA_ASSETS, start)
    return R.sixty_forty_monthly(data, "TLT", start)


def config(aid, rule, market, syms, bench_desc, start, holdout, cost, data, manifest):
    grid = R.run_grid(rule, data)
    net = pd.DataFrame({k: v["return"] - v["turnover"] * cost / 1e4 for k, v in grid.items()}).loc[start:spec.END].dropna()
    chosen = R.label(R.DEFAULTS[rule])
    bench = benchmark(rule, data, start)
    df = grid[chosen].reindex(net.index).assign(market=bench.reindex(net.index).fillna(0.0))
    files = [fetch.batch2_file(s) for s in syms]
    new = [f for f in files if manifest[f]["recorded_utc"] > SEALED_AT]
    received = max(manifest[f]["recorded_utc"] for f in files) if new else None
    notes = [PROVENANCE] + [f"{f}: {manifest[f]['rows']} rows ending {manifest[f]['end']}, SHA-256 {manifest[f]['sha256']}"
                            + (" (fetched after the seal)" if f in new else " (held before this batch; prices previously seen)")
                            for f in files]
    notes += [f"Audit period {start} to {spec.END}; holdout from {holdout}; benchmark: {bench_desc} (all fixed in the sealed "
              "batch preregistration).",
              "Cash earns 0% and borrowing above 100% exposure costs 0%; shorting has no borrow cost (stated in the preregistration)."]
    if received is None:
        notes.append("All of this audit's data files were held before the declaration was sealed (disclosed in the "
                     "preregistration); the declaration-date check is therefore not applied.")
    meta = spec.RULES[rule]
    return AuditConfig(
        name=f"Batch 3: {meta['name']}",
        description=f"{meta['name']} on {market}. Claim tested (declared before the run): {meta['claim']} Benchmark: {bench_desc}. "
                    "Part of Indicator Audit Batch 3, 'Strongest published evidence' (6 audits, sealed, Holm across the batch).",
        rules=f"Source: {meta['source']} Rule: {meta['rule']} Audited variant: {chosen}. Grid: {R.n_variants(rule)} variants.",
        returns=df, variants=net, chosen_variant=chosen, n_trials=R.n_variants(rule), base_cost_bps=cost, seed=SEED,
        rubric_version="1.2", periods_per_year=252, holdout_split=holdout,
        declaration_file=str(PRE / f"declaration-{aid}.json"), declaration_seal_dir=str(PRE / f"seal-declaration-{aid}"),
        preregistration_file=str(PREREG), preregistration_seal_dir=str(SEAL), data_received_utc=received,
        data_files={f: fetch.RAW / f for f in files}, data_notes=notes,
    )


def main() -> int:
    manifest = fetch.fetch_batch3()
    data = {s: load(s) for s in fetch.BATCH3_SYMBOLS}
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for aid, rule, market, syms, bench_desc, start, holdout, cost in spec.AUDITS:
        res = run_audit(config(aid, rule, market, syms, bench_desc, start, holdout, cost, data, manifest))
        write_report(res, REPORTS / f"{aid}.html")
        st = {c.key: c.status for c in res.grade.checks}
        o = res.obj
        if res.objective == "improve_sharpe":
            sb = o["sharpe_boot"]
            prim = {"sr": round(sb.sr_strategy, 3), "sr_benchmark": round(sb.sr_benchmark, 3), "d_sr": round(sb.d_sr, 3),
                    "d_sr_lo": round(sb.d_sr_lo, 3), "holdout_d_sr_is": round(o["holdout"]["d_sr_is"], 3),
                    "holdout_d_sr_oos": round(o["holdout"]["d_sr_oos"], 3)}
            primary_ok = st["sharpe"] != "FAIL"
        else:
            ob = o["boot"]
            prim = {"mdd": round(ob.mdd_strategy, 4), "mdd_benchmark": round(ob.mdd_benchmark, 4), "d_mdd": round(ob.d_mdd, 4),
                    "d_mdd_lo": round(ob.d_mdd_lo, 4), "d_cvar_bps": round(ob.d_cvar * 1e4, 2),
                    "shortfall": round(ob.shortfall, 4), "shortfall_hi": round(ob.shortfall_hi, 4),
                    "tolerance": o["tolerance"]}
            primary_ok = st["drawdown"] != "FAIL" and st["tolerance"] != "FAIL"
        rows.append({"id": aid, "rule": rule, "name": spec.RULES[rule]["name"], "market": market, "benchmark": bench_desc,
                     "objective": res.objective, "variant": res.config.chosen_variant, "n_variants": res.n_trials,
                     "grade": res.grade.letter, "score": round(res.grade.score, 3), "caps": res.grade.caps,
                     "checks": st, "primary": prim, "primary_ok": primary_ok, "deflated": round(o["deflated"], 4),
                     "pbo": None if o["pbo"] is None else round(o["pbo"].pbo, 4), "p_primary": round(o["p_adj"], 4),
                     "cagr": round(_cagr(res.net), 4), "bh_cagr": round(_cagr(res.bench), 4),
                     "max_drawdown": round(res.drawdowns.realized, 4), "report": f"reports/{aid}.html"})
        print(f"{aid}: {res.grade.letter}  {res.objective}  primary {prim}  p {o['p_adj']:.4f}", flush=True)
    for r, h in zip(rows, holm_adjusted([r["p_primary"] for r in rows])):
        r["p_holm"] = round(float(h), 4)
        r["survives_holm"] = bool(h <= 0.05 and r["primary_ok"])
    out = {"batch": "Indicator Audit Batch 3: Strongest published evidence", "rubric": "1.2",
           "preregistration_sha256": hashlib.sha256(PREREG.read_bytes()).hexdigest(),
           "preregistration_seal_sha256": hashlib.sha256((SEAL / "seal.json").read_bytes()).hexdigest(),
           "n_audits": len(rows), "n_survive_holm": sum(r["survives_holm"] for r in rows), "audits": rows}
    (HERE / "summary.json").write_bytes((json.dumps(out, indent=2) + "\n").encode("utf-8"))
    print(f"survive Holm: {out['n_survive_holm']} of {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
