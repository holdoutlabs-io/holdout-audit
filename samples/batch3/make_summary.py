"""Builds samples/batch3/README.md from summary.json."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spec  # noqa: E402

OBJ = {"improve_sharpe": "(c) improve Sharpe", "reduce_drawdown": "(b) reduce drawdown"}


def pct(x):
    return f"{100 * x:.1f}%"


def primary(r):
    p = r["primary"]
    if r["objective"] == "improve_sharpe":
        return (f"Sharpe {p['sr']:.2f} vs {p['sr_benchmark']:.2f} (dSR {p['d_sr']:+.2f}, 5th pct {p['d_sr_lo']:+.2f}); "
                f"holdout dSR {p['holdout_d_sr_is']:+.2f} → {p['holdout_d_sr_oos']:+.2f}")
    return (f"max drawdown {pct(p['mdd'])} vs {pct(p['mdd_benchmark'])} (5th pct of the cut {pct(p['d_mdd_lo'])}); "
            f"return cost {pct(p['shortfall'])}/yr vs declared tolerance {pct(p['tolerance'])}")


def main():
    s = json.loads((HERE / "summary.json").read_text())
    rows = s["audits"]
    g = {r["id"]: r for r in rows}
    gt, vm = g["gtaa-eem-vnq-tlt"], g["volman-spy"]
    lines = [
        "# Indicator Audit, Batch 3: Strongest published evidence (traditional markets)",
        "",
        f"**Result: none of the {s['n_audits']} audits meets its source's own claim under the preregistered test (0 of "
        f"{s['n_audits']} survive).** One claim came closest, and we report it prominently:",
        "",
        f"- **Faber timing on EEM, VNQ and TLT did cut drawdowns, robustly.** The maximum drawdown fell from "
        f"{pct(gt['primary']['mdd_benchmark'])} to {pct(gt['primary']['mdd'])}. The bootstrap 5th percentile of the reduction "
        f"was {pct(gt['primary']['d_mdd_lo'])}, the daily tail loss fell by {gt['primary']['d_cvar_bps']:.0f} bps, and the "
        f"Holm-adjusted p is {gt['p_holm']:.4f}. Every check passed except one: it gave up "
        f"{pct(gt['primary']['shortfall'])} a year of return against the {pct(gt['primary']['tolerance'])} tolerance we declared "
        f"in advance, following Faber's 'equity-like returns' claim. The objective cap therefore limits it to **C**, and it does "
        f"not count as surviving. Half of the claim (drawdowns) held; the other half (returns) did not.",
        f"- **Volatility-managed SPY** raised the Sharpe ratio from {vm['primary']['sr_benchmark']:.2f} to {vm['primary']['sr']:.2f}. "
        f"But the improvement was not robust: its 5th percentile is {vm['primary']['d_sr_lo']:+.2f}, the family-adjusted p is "
        f"{vm['p_primary']:.2f} and the PBO is {vm['pbo']:.2f}. Grade **D**.",
        "",
        "Everything else failed its own claim: low-volatility sectors, the minimum-volatility ETF, time-series momentum and risk "
        "parity. Two rules compounded faster than their benchmark only through leverage financed at the preregistered 0%. "
        "Neither improved the Sharpe ratio: time-series momentum "
        f"{pct(g['tsmom-5']['cagr'])} vs {pct(g['tsmom-5']['bh_cagr'])}, volatility-managed SPY {pct(vm['cagr'])} vs "
        f"{pct(vm['bh_cagr'])}.",
        "",
        "Statistical findings about past data only. Not investment advice, and not a recommendation to use or avoid any rule.",
        "",
        "## How it was done",
        "",
        "1. **Rubric v1.2** added objective (c), \"improve Sharpe vs benchmark\", for sources whose claim is risk-adjusted. It "
        "was sealed at 20:33:45Z, before any Batch 3 data were fetched. Objectives (a) and (b) are unchanged.",
        "2. **Preregistration and six objective declarations** were sealed with DigiCert and FreeTSA at 20:39:31–55Z on "
        "2026-09-25. Each audit is judged on the objective its own source claims. The documents also fix the exact list of "
        "instruments whose prices we had already seen, and the list of those we had not. See [`prereg/`](prereg/).",
        f"   - Preregistration SHA-256 `{s['preregistration_sha256']}`; seal record `{s['preregistration_seal_sha256']}`.",
        "3. **New data fetched after the seal:** EEM, TLT, VNQ, USMV and SPLV. SPY, EFA, IEF and the sector SPDRs are reused "
        "files whose prices we had already seen, which is disclosed in each report.",
        "4. **Run once each** under rubric v1.2.",
        "5. **Batch test.** Each audit contributes its primary-objective p-value (dSR for (c), dCVaR for (b); adjusted "
        "within its variant family). Holm's correction is applied across the six. \"Survives\" requires a Holm p of 0.05 or less "
        "*and* a primary objective check that is not FAIL.",
        "",
        "## Summary table",
        "",
        "| Rule (source) | Market | Objective | Variants | Grade | Primary result | Deflated | PBO | Holm p | Survives |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| [{r['name']}]({r['report']}) | {r['market']} | {OBJ[r['objective']]} | {r['n_variants']} | **{r['grade']}** | "
                     f"{primary(r)} | {r['deflated']:.3f} | {'n/a' if r['pbo'] is None else format(r['pbo'], '.2f')} | "
                     f"{r['p_holm']:.4f} | {'yes' if r['survives_holm'] else 'no'} |")
    lines += ["", f"Survive: **{s['n_survive_holm']} of {s['n_audits']}**.", "", "## Sources", ""]
    lines += [f"- **{m['name']}**: {m['source']}" for m in spec.RULES.values()]
    lines += [
        "",
        "## Deviations and disclosures",
        "",
        "- **No deviations** from the preregistered rules, grids, markets, costs, periods, holdouts, objectives or tolerance.",
        "- *Prior exposure.* We had already seen SPY, QQQ, IWM, EFA, IEF, AGG, ^VIX, the sector SPDRs and BTC. We had not "
        "seen EEM, TLT, VNQ, USMV or SPLV. The volatility-managed and low-volatility-sector audits therefore run on prices we "
        "had seen, with no new data, and the engine's declaration-date check is not applied to them (stated in their reports). "
        "No earlier audit is re-graded.",
        "- *Financing.* Cash earns 0% and borrowing costs 0%. That flatters the levered variants (volatility-managed caps above "
        "1.0; time-series momentum's volatility-scaled bond positions) and penalises the de-risked ones.",
        "- *Scope.* The paper's commodities and currencies are excluded from time-series momentum (the samples' instrument policy), and the low-volatility "
        "rule is a sector-level adaptation of a stock-level anomaly. Both points are stated in the preregistration.",
        "",
        "Data: prices from Yahoo Finance's public chart endpoint; we publish derived statistics only, never raw prices; no "
        "redistribution.",
    ]
    (HERE / "README.md").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
