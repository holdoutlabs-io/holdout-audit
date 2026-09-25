"""Indicator Audit, Batch 2 ("Classic market rules"): run the 14 preregistered audits once each.

    uv run python samples/batch2/run_batch2.py

Follows samples/batch2/prereg/batch2-preregistration.json (sealed 2026-09-25T20:11:44Z) via spec.py.
Writes samples/batch2/reports/<id>.html and summary.json, with Holm's correction across the 14 Hansen
SPA p-values. Statistical findings about past data only; not investment advice.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SAMPLES = HERE.parent
sys.path[:0] = [str(HERE), str(SAMPLES), str(SAMPLES / "data")]

import batch2_rules as R  # noqa: E402
import fetch  # noqa: E402
import spec  # noqa: E402

from holdout_audit import AuditConfig, run_audit  # noqa: E402
from holdout_audit.report import write_report  # noqa: E402
from holdout_audit.stats.haircut import holm_adjusted  # noqa: E402

PREREG = HERE / "prereg" / "batch2-preregistration.json"
SEAL = HERE / "prereg" / "seal"
REPORTS = HERE / "reports"
SEED = 20260925
PROVENANCE = ("Prices from Yahoo Finance's public chart endpoint; we publish derived statistics only, never raw prices; "
              "no redistribution. Signals use the split-adjusted close; total returns use the split- and dividend-adjusted "
              "close.")


def load(sym: str) -> pd.DataFrame:
    df = pd.read_csv(fetch.RAW / fetch.batch2_file(sym), parse_dates=["date"]).set_index("date").sort_index()
    df["tr"] = df["adjclose"].pct_change()
    return df


def _cagr(x: pd.Series) -> float:
    x = x.dropna()
    return float(np.prod(1 + x.to_numpy()) ** (252 / len(x)) - 1)


def config(aid, rule, market, syms, bench_desc, start, cost, data, manifest) -> AuditConfig:
    single = rule not in ("dual_momentum", "sector_momentum", "sixty_forty")
    d = {"asset": data[syms[0]], **data} if single else dict(data)
    if rule == "vix_stretch":
        d = {"asset": data["SPY"], "VIX": data["^VIX"]}
    grid = R.run_grid(rule, d, start)
    net = pd.DataFrame({k: v["return"] - v["turnover"] * cost / 1e4 for k, v in grid.items()}).loc[start:spec.END]
    chosen = R.label(R.DEFAULTS[rule])
    if rule == "sixty_forty":
        bench = R.buy_and_hold_60_40(data["SPY"], data["IEF"], start)
    elif rule in ("dual_momentum", "sector_momentum", "vix_stretch"):
        bench = data["SPY"]["tr"]
    else:
        bench = data[syms[0]]["tr"]
    df = grid[chosen].loc[start:spec.END].assign(market=bench.reindex(grid[chosen].loc[start:spec.END].index))
    files = [fetch.batch2_file(s) for s in syms]
    notes = [PROVENANCE] + [f"{f}: {manifest[f]['rows']} rows ending {manifest[f]['end']}, SHA-256 {manifest[f]['sha256']}."
                            for f in files]
    notes += [f"Audit period {start} to {spec.END}; holdout from {spec.HOLDOUT}; benchmark: {bench_desc} (all fixed in the "
              "sealed batch preregistration).",
              "Out of the market the rule holds cash at 0% (no T-bill series; a bias against timing rules, stated in the "
              "preregistration). Signals at the close, held close to close; no leverage, no shorting."]
    meta = spec.RULES[rule]
    return AuditConfig(
        name=f"Batch 2: {meta['name']} on {market}",
        description=f"{meta['name']}, as published, on {market}. Benchmark: {bench_desc}. Part of Indicator Audit Batch 2, "
                    "'Classic market rules' (14 audits, one sealed preregistration, Holm across the batch).",
        rules=f"Source: {meta['source']} Rule: {meta['rule']} Audited variant: {chosen}. Grid: {R.n_variants(rule)} variants "
              "(see the preregistration).",
        returns=df, variants=net, chosen_variant=chosen, n_trials=R.n_variants(rule), base_cost_bps=cost, seed=SEED,
        rubric_version="1.1", periods_per_year=252, holdout_split=spec.HOLDOUT,
        declaration_file=str(PREREG), declaration_seal_dir=str(SEAL), preregistration_file=str(PREREG),
        preregistration_seal_dir=str(SEAL), data_received_utc=max(manifest[f]["recorded_utc"] for f in files),
        data_files={f: fetch.RAW / f for f in files}, data_notes=notes,
    )


def main() -> int:
    manifest = fetch.fetch_batch2()  # first call fetches (after the seal) and records hashes
    data = {s: load(s) for s in fetch.BATCH2_SYMBOLS}
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for aid, rule, market, syms, bench_desc, start, cost in spec.AUDITS:
        res = run_audit(config(aid, rule, market, syms, bench_desc, start, cost, data, manifest))
        write_report(res, REPORTS / f"{aid}.html")
        ho = res.holdout
        rows.append({
            "id": aid, "rule": rule, "name": spec.RULES[rule]["name"], "market": market, "benchmark": bench_desc,
            "variant": res.config.chosen_variant, "n_variants": res.n_trials, "grade": res.grade.letter,
            "score": round(res.grade.score, 3), "sharpe": round(res.sharpe.sr_annual, 3),
            "excess_sharpe": round(res.sharpe_excess.sr_annual, 3), "cagr": round(_cagr(res.net), 4),
            "bh_cagr": round(_cagr(res.bench), 4), "dsr": round(res.dsr, 4), "pbo": round(res.pbo.pbo, 4),
            "spa_p": round(res.spa.p_spa, 4), "holdout_excess_sharpe_is": round(ho.sr_is_annual, 3),
            "holdout_excess_sharpe_oos": round(ho.sr_oos_annual, 3), "max_drawdown": round(res.drawdowns.realized, 4),
            "beats_benchmark_rubric": res.beats_benchmark, "report": f"reports/{aid}.html",
        })
        print(f"{aid}: {res.grade.letter}  excess SR {res.sharpe_excess.sr_annual:+.2f}  SPA p {res.spa.p_spa:.3f}", flush=True)
    for r, h in zip(rows, holm_adjusted([r["spa_p"] for r in rows])):
        r["spa_p_holm"] = round(float(h), 4)
        r["survives_holm"] = bool(h <= 0.05)
    pre = json.loads((SEAL / "seal.json").read_text())
    out = {"batch": "Indicator Audit Batch 2: Classic market rules", "rubric": "1.1", "objective": "beat_benchmark",
           "preregistration_sha256": pre["subject_sha256"],
           "preregistration_seal_sha256": __import__("hashlib").sha256((SEAL / "seal.json").read_bytes()).hexdigest(),
           "n_audits": len(rows), "n_survive_holm": sum(r["survives_holm"] for r in rows), "audits": rows}
    (HERE / "summary.json").write_bytes((json.dumps(out, indent=2) + "\n").encode("utf-8"))
    print(f"survive Holm: {out['n_survive_holm']} of {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
