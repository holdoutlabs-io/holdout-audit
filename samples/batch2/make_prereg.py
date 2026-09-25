"""Writes samples/batch2/prereg/batch2-preregistration.json (run once, before sealing and before any fetch)."""

import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import batch2_rules as R  # noqa: E402
import spec  # noqa: E402

now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    rules = []
    for key, meta in spec.RULES.items():
        rules.append({"key": key, **meta, "audited_variant": R.label(R.DEFAULTS[key]),
                      "variant_grid": R.GRIDS[key], "n_variants": R.n_variants(key),
                      "implementation": f"samples/batch2_rules.py ({key})"})
    audits = [{"id": a, "rule": r, "market": m, "data_symbols": syms, "benchmark": bench, "audit_period": f"{start} to {spec.END}",
               "holdout_split": spec.HOLDOUT, "cost_bps_per_unit_turnover": cost, "n_variants": R.n_variants(r)}
              for a, r, m, syms, bench, start, cost in spec.AUDITS]
    doc = {
        "objective": "beat_benchmark",
        "max_return_shortfall_annual": None,
        "benchmark": "buy-and-hold of the same asset (total return); for multi-asset rules see each audit",
        "declared_at_utc": now,
        "declared_by": "holdout-labs-batch-2",
        "title": "Holdout Labs Indicator Audit, Batch 2: Classic market rules (traditional markets only), 14 audits",
        "written_at_utc": now,
        "scope_policy": "Instrument policy: equity indices, equity ETFs (broad, sector, international), individual equities, bond ETFs, FX and BTC are permitted; commodities, metals, commodity ETFs and astronomical features are forbidden. This batch uses no crypto. The VIX index level is used only as a signal (vix_stretch).",
        "rubric": "Holdout Labs Fragility Rubric v1.1 (docs/RUBRIC-v1.1.md, SHA-256 2311b126336bab9f426a84f9c9cd9cb937e346b403a62f60e3c96ed8b5868e46), objective (a) beat the benchmark, for every audit.",
        "rules": rules,
        "audits": audits,
        "data": {
            "source": "Yahoo Finance public chart endpoint (daily), fetched by samples/data/fetch.py (fetch_batch2) into samples/data/raw/yahoo_*.csv AFTER this document is sealed; each file's SHA-256 is recorded in samples/data/MANIFEST.json and printed in the reports. Symbols: SPY, QQQ, IWM, EFA, IEF, AGG, ^VIX and the nine sector SPDRs (XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY).",
            "fields": "Signals use Yahoo's split-adjusted close; total returns use Yahoo's split- and dividend-adjusted close (adjclose). For ^VIX (an index) the close is used.",
            "terms_and_publication": "Yahoo Finance's terms cover personal use and grant no redistribution. Holdout Labs publishes derived statistics only, never raw prices, and does not redistribute the data (Yahoo adopted on 2026-09-25 as the official source for published samples). The raw files are git-ignored; only fetch code and hashes are committed.",
        },
        "execution_convention": "Signals at the daily close (monthly rules at the last trading day of each month), position held from that close to the next; out of the market the strategy holds cash earning 0% (no T-bill series is used, because a Treasury-bill rate index is not a permitted instrument). This biases the results against the timing rules by roughly the T-bill rate times the time spent in cash; it is stated in every report. Dual momentum's absolute-momentum hurdle is therefore 0% rather than the T-bill return. No leverage, no shorting.",
        "settings": {"bootstrap_draws": 1000, "cscv_blocks": 16, "seed": 20260925, "periods_per_year": 252,
                     "declared_n_trials": "equal to n_variants of each rule"},
        "batch_level_inference": {
            "primary_statistic": "each audit's Hansen SPA consistent p-value (best variant of the preregistered family against the audit's benchmark, stationary bootstrap).",
            "multiplicity": "Holm step-down correction across all 14 audits at family-wise alpha 0.05.",
            "survives": "An audit survives only if its Holm-adjusted SPA p <= 0.05. No rule will be described as beating its benchmark unless it survives. The rubric v1.1 grade is reported for every audit regardless."},
        "publication_commitment": "All 14 results are published in samples/batch2/ and on holdoutlabs.io/audits/batch-2/, pass or fail, with every report, the summary table and this preregistration. No audit will be dropped, re-run with different settings, or re-graded under another objective.",
        "prior_exposure": "The auditors have already seen SPY and BTC results: sample audits 1-4 (SPY golden cross, SPY RSI(2), BTC), Indicator Audit Batch 1 (ten TradingView built-ins on SPY and BTC, none beat buy-and-hold) and the on-chain batch. We know that timing rules on SPY broadly failed to beat buy-and-hold in 1994-2026. None of the ten rules here has been run by us on QQQ, IWM, EFA, IEF, AGG, the sector SPDRs or the VIX; the SPY golden-cross and RSI(2) rules were run in samples 1 and 2 (the golden cross here is on QQQ and the RSI(2) on QQQ and IWM). The implementations were tested on synthetic data only.",
        "deviations": "Any deviation from this document will be listed on the summary page and in the affected reports.",
    }
    out = HERE / "prereg" / "batch2-preregistration.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(out, len(audits), sum(a["n_variants"] for a in audits), now)


if __name__ == "__main__":
    main()
