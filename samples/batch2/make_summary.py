"""Builds samples/batch2/README.md (the summary table) from summary.json."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spec  # noqa: E402


def pct(x):
    return f"{100 * x:.1f}%"


def main():
    s = json.loads((HERE / "summary.json").read_text())
    rows = s["audits"]
    pos = [r for r in rows if r["excess_sharpe"] > 0]
    lines = [
        "# Indicator Audit, Batch 2: Classic market rules (traditional markets)",
        "",
        f"**Result: none of the {s['n_audits']} audits survives.** We tested ten published or traditional market rules on the "
        "equity and bond markets their sources used. None of them beat its benchmark with statistical support: every Hansen SPA "
        f"p-value is at least {min(r['spa_p'] for r in rows):.2f}, and 0 of {s['n_audits']} survive Holm's correction. All "
        f"{s['n_audits']} grade **F** under rubric v1.1, objective (a) \"beat the benchmark\".",
        "",
        "Two audited defaults came out slightly *ahead* of their benchmark, but far from significant, and both failed the "
        "selection-adjusted significance and holdout checks: "
        + "; ".join(f"{r['name']} on {r['market']} (excess Sharpe {r['excess_sharpe']:+.2f}, SPA p {r['spa_p']:.2f})" for r in pos)
        + ". The golden cross on QQQ compounded faster than holding QQQ (12.0% vs 9.4% a year), but its whole advantage "
        "came from sitting out the 2000–02 crash (+4.4% a year against −37.9%). From 2003 onward it trailed holding QQQ "
        "(12.9% vs 16.3% a year).",
        "",
        "Statistical findings about past data only. Not investment advice, and not a recommendation to use or avoid any rule. "
        "A grade describes how fragile the historical evidence is; it does not predict the future.",
        "",
        "## How it was done",
        "",
        "1. **Preregistered and sealed first.** Before any Batch 2 data were fetched, one preregistration fixed the following "
        "for all 14 audits. It was sealed with RFC 3161 timestamps from DigiCert (20:11:44Z) and FreeTSA (20:11:45Z) on "
        "2026-09-25: [`prereg/batch2-preregistration.json`](prereg/batch2-preregistration.json).",
        "   - each rule as published, with its source and default;",
        "   - a variant grid (132 variants in all);",
        "   - markets, costs, periods and the holdout (from 2018-01-02);",
        "   - the benchmark and objective;",
        "   - Holm across 14 and the commitment to publish all results.",
        f"   - Document SHA-256 `{s['preregistration_sha256']}`; seal record `{s['preregistration_seal_sha256']}`.",
        "2. **Run once each** under rubric v1.1 (`run_batch2.py`). The data were fetched after the seal.",
        "3. **Batch test.** Each audit's Hansen SPA p-value (the best variant of its family against the benchmark) is "
        "corrected with Holm's method across the 14. \"Survives\" means an adjusted p of 0.05 or less.",
        "",
        "## Summary table",
        "",
        "| Rule (source) | Market | Variants | Grade | Compound return a year vs benchmark | Excess Sharpe | DSR | PBO | Holdout excess Sharpe (in → out) | SPA p | Holm p | Survives |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| [{r['name']}]({r['report']}) | {r['market']} | {r['n_variants']} | **{r['grade']}** | {pct(r['cagr'])} vs {pct(r['bh_cagr'])} "
            f"| {r['excess_sharpe']:+.2f} | {r['dsr']:.3f} | {r['pbo']:.2f} | {r['holdout_excess_sharpe_is']:+.2f} → "
            f"{r['holdout_excess_sharpe_oos']:+.2f} | {r['spa_p']:.3f} | {r['spa_p_holm']:.3f} | {'yes' if r['survives_holm'] else 'no'} |")
    lines += ["", f"Survive Holm: **{s['n_survive_holm']} of {s['n_audits']}**.", "", "## Sources", ""]
    lines += [f"- **{m['name']}**: {m['source']}" for m in spec.RULES.values()]
    lines += [
        "",
        "## Deviations and disclosures",
        "",
        "- **No deviations** from the preregistered rules, grids, markets, costs, periods, holdout or objective.",
        "- *Cash earns 0%.* No T-bill series was used, because a Treasury-bill rate index is not a permitted "
        "instrument. This works against every timing rule by roughly the T-bill rate times the time spent in cash. Antonacci's "
        "absolute-momentum hurdle is therefore 0% instead of the T-bill return. Both points were preregistered.",
        "- *Benchmarks.* Single-asset rules are compared with buy-and-hold of the same ETF. Dual momentum, sector rotation and "
        "the VIX rule are compared with buy-and-hold SPY. The 60/40 banding rule is compared with the same 60/40 bought at the "
        "start and never rebalanced.",
        "- *Data* come from Yahoo Finance's public chart endpoint, fetched after the seal. Signals use the split-adjusted close "
        "and total returns use the adjusted close. As a check, SPY total return matched our earlier close-plus-dividend series "
        "(10.89% a year either way).",
        "- *Prior exposure:* SPY and BTC results from sample audits 1–4, Batch 1 and the on-chain batch had been seen before "
        "this batch; see the preregistration.",
        "",
        "Data: prices from Yahoo Finance's public chart endpoint; we publish derived statistics only, never raw prices; no "
        "redistribution.",
    ]
    (HERE / "README.md").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
