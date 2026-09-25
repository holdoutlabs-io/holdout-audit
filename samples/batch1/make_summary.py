"""Builds samples/batch1/README.md (the summary table) from summary.json."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pct(x):
    return f"{100 * x:.1f}%"


def main():
    s = json.loads((HERE / "summary.json").read_text())
    rows = s["audits"]
    lines = [
        "# Indicator Audit, Batch 1: ten TradingView built-in strategies on SPY and BTC",
        "",
        "**Result: none of the 20 audits survives.** Not one of the ten TradingView built-in strategies, run with its default "
        "settings as it ships (long and short), beat simply holding the same asset. That holds on SPY (1994–2026) and on "
        "BTC (2015–2026). Across all ten preregistered variant families (250 variants), no variant had a positive mean "
        "return over buy-and-hold after costs. Every Hansen SPA p-value is 1.000, so nothing survives Holm's correction "
        "across the 20 audits (0 of 20). All 20 grade **F** under rubric v1.1, objective (a) \"beat buy-and-hold of the same asset\".",
        "",
        "Statistical findings about past data only. Not investment advice, and not a recommendation to use or avoid any "
        "indicator. A grade describes how fragile the historical evidence is; it does not predict the future.",
        "",
        "## How it was done",
        "",
        "1. **Preregistered and sealed first.** Before any SPY OHLC data were fetched and before any of these strategies was "
        "run on market data, one batch preregistration fixed the following for every audit. It was sealed with RFC 3161 "
        "timestamps from DigiCert (18:21:44Z) and FreeTSA (18:21:45Z) on 2026-09-25: [`prereg/batch1-preregistration.json`](prereg/batch1-preregistration.json).",
        "   - the rule and its defaults;",
        "   - the variant grid;",
        "   - costs, data, dates and the holdout split;",
        "   - the objective;",
        "   - the Holm rule and the commitment to publish all 20.",
        "   - Document SHA-256 `35b4d77e284614c15fafdacaf91e122b600e520c1ea61e33627a64c3497c765d`; seal record "
        "`9f25abc24d54753071fc54da00bda52705ea2e7c0b6d2ba3011d7c009fa22d5c`. Every report cites the seal.",
        "2. **Run once each** under rubric v1.1 (`run_batch1.py`). BTC Supertrend is carried over unchanged from sample audit 4 "
        "(same sealed grid, data, dates and costs), as the preregistration says.",
        "3. **Batch-level test.** Each audit contributes its Hansen SPA p-value: the best variant of its preregistered family "
        "against buy-and-hold, by stationary bootstrap. Holm's step-down correction across the 20 decides \"survives\" at "
        "family-wise α = 0.05.",
        "",
        "## Summary table",
        "",
        "| Asset | TradingView strategy (default, long/short) | Variants | Grade | Compound return a year vs buy-and-hold | Excess Sharpe | DSR | PBO | Holdout excess Sharpe (in → out) | SPA p | Holm p | Survives |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['asset']} | [{r['name']}]({r['report']}) | {r['n_variants']} | **{r['grade']}** | {pct(r['cagr'])} vs {pct(r['bh_cagr'])} "
            f"| {r['excess_sharpe']:+.2f} | {r['dsr']:.3f} | {r['pbo']:.2f} | {r['holdout_excess_sharpe_is']:+.2f} → "
            f"{r['holdout_excess_sharpe_oos']:+.2f} | {r['spa_p']:.3f} | {r['spa_p_holm']:.3f} | {'yes' if r['survives_holm'] else 'no'} |")
    lines += [
        "",
        f"Survive Holm: **{s['n_survive_holm']} of {s['n_audits']}**.",
        "",
        "## Deviations and disclosures",
        "",
        "- **No deviations** from the preregistered rules, grids, costs, dates, holdout splits or objective.",
        "- *Code fix before the first run:* the runner first crashed while building a report description (it read a missing docstring), "
        "before any audit statistic was computed. It now takes each rule's text verbatim from the sealed preregistration.",
        "- *BTC data:* the BTC OHLC file was fetched for sample audit 4 (15:34:16Z), before this batch was declared (18:21:27Z). The preregistration "
        "disclosed this and pinned the file's SHA-256, and the file is unchanged. The engine's declaration-date check, which exists to police "
        "objective (b), was therefore not applied to the 10 BTC audits. All 20 audits use objective (a).",
        "- *SPY data* were fetched after the seal (see `samples/data/MANIFEST.json`).",
        "- *Execution convention,* stated in every report: signals are taken at the daily close and held close to close. Stop entries are treated "
        "as filled at the signal close, and short-side funding is not modelled. This differs from TradingView's broker emulator, which fills at the next "
        "open and fills stops intrabar.",
        "- *Selection of the ten:* all ten indicators are TradingView built-ins (Help Center). We had no quantitative popularity data. Ichimoku "
        "was excluded because it has no built-in strategy. See the preregistration.",
        "- *Prior exposure:* SPY and BTC prices and results from sample audits 1–4 had been seen before this batch.",
        "",
        "Data: prices from Yahoo Finance's public chart endpoint (SPY) and the Coinbase Exchange public API (BTC). We publish "
        "derived statistics only, never raw prices; no redistribution.",
    ]
    (HERE / "README.md").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
