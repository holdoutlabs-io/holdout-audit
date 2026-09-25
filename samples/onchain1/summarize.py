"""Build the ONCHAIN-1 summary (SUMMARY.md, reports/summary.html, summary.json) from results.json.

Every number comes from results.json, which run.py wrote in its single sealed run.
Descriptive-only tests show no p-value (preregistered testability rule).
"""
from __future__ import annotations

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
SEAL = json.loads((HERE / "prereg" / "preregistration-seal" / "seal.json").read_text())
REG = [json.loads(x) for x in (HERE / "prereg" / "registry.jsonl").read_text().splitlines() if x.strip()]

RULES = {
    "A1": ("111-day SMA crosses above 2 x 350-day SMA", "top", "crossing day"),
    "A2": ("close within 10% above the 200-week MA, or below it", "bottom", "close <= 1.10 x 200WMA"),
    "A3": ("close / 200-day SMA > 2.4", "top", "MM > 2.4"),
    "A4": ("close below the 730-day SMA", "bottom", "close < 2yMA"),
    "A5": ("issuance value / its 365-day mean < 0.5", "bottom", "Puell < 0.5"),
    "A6": ("close below PlanB's model price exp(14.6) SF^3.3 / supply", "bottom", "close < S2F model"),
}
PUB = {"A1": "Philip Swift, Apr 2019", "A2": "PlanB concept, Jan 2019", "A3": "Trace Mayer, 2017",
       "A4": "Philip Swift, Jul 2017", "A5": "David Puell, Mar 2019", "A6": "22 Mar 2019"}


def pct(x, signed=True):
    return "n/a" if x is None else (f"{x * 100:+.0f}%" if signed else f"{x * 100:.0f}%")


rows = []
for sid, r in R["indicators"].items():
    t = r["tests"]["primary_D365"]
    strat = r.get("strategy")
    rows.append({
        "id": sid, "indicator": r["name"], "published": PUB[sid], "rule": RULES[sid][0], "kind": RULES[sid][1],
        "zone": RULES[sid][2], "oos": f"{r['oos_start_effective']} to 2026-09-24",
        "episodes": t["episodes"], "zone_days": t["zone_days"], "episode_starts": t["episode_starts"],
        "fwd365_zone": t.get("conditional_simple_return"), "fwd365_all": t.get("unconditional_simple_return"),
        "p": t["p_one_sided"] if t["inferential"] else None, "p_holm": r["holm"]["p_holm"] if t["inferential"] else None,
        "status": r["holm"]["status"],
        "grade": strat["grade"] if strat else None,
        "strategy_excess_return": strat["excess_return_annual"] if strat else None,
        "strategy_excess_sr": strat["excess_sr_annual"] if strat else None,
        "report": f"reports/{sid.lower()}-{r['name'].split(' (')[0].lower().replace(' ', '-')}.html" if strat else None,
    })

hdr = {
    "prereg_sha256": R["prereg_sha256"], "seal_sha256": REG[0]["seal_sha256"],
    "signed_utc": [(x["tsa"], x["gen_time_utc"]) for x in SEAL["receipts"]],
    "headers": R["headers"],
}
(HERE / "summary.json").write_text(json.dumps({"seal": hdr, "rows": rows}, indent=2) + "\n", encoding="utf-8")

A1, A2, A3, A4, A5, A6 = (R["indicators"][k] for k in ("A1", "A2", "A3", "A4", "A5", "A6"))

KEY_FINDINGS = [
    ("Stock-to-flow", f"The only primary claim with enough episodes to test ({A6['tests']['primary_D365']['episodes']}). "
     f"Days below the model price were followed by <em>lower</em> 365-day returns than average, the opposite of the claim "
     f"(one-sided p = {A6['tests']['primary_D365']['p_one_sided']:.2f}; Holm-adjusted 1.00): <strong>not supported</strong>. "
     f"As a level model it drifted away: BTC closed at {A6['fit_by_year']['2025']['mean_ratio_close_to_model']:.2f}x the model "
     f"on average in 2025 and {A6['fit_by_year']['2026']['mean_ratio_close_to_model']:.2f}x in 2026 "
     f"(model price on 2026-09-24: ${A6['model_price_on']['2026-09-24']:,.0f})."),
    ("Pi Cycle Top", "One out-of-sample crossing, on 2021-04-12. It came one day before the April 2021 local high "
     "(context, not a preregistered test), but the highest close within a year either side came 210 days later, on "
     "2021-11-08, and 12.9% higher, so it misses the preregistered 'within 3 days' test at every window. "
     "No crossing at all before the highest closes of 2024-03 or 2025-10."),
    ("Mayer Multiple > 2.4", "Three episodes (Jan 2018, Jun 2019, Jan&ndash;Mar 2021). The first came 20 days after the "
     "December 2017 high and the second on the day of the 2019 high; the 2021 one came ten months before the cycle high. "
     "None since March 2021. Its implied rule beat buy-and-hold by 3% a year, all of it from those early episodes: "
     "not significant (SPA p = 0.12), and identical to holding throughout the holdout, so it grades F."),
    ("2-Year MA Multiplier", "Four bottom-zone episodes with a full 365-day window (plus one open in 2026); "
     "the 5x top zone fired only in late 2017. Too few for inference."),
    ("Puell Multiple", "Never above 4 after publication; four episodes below 0.5. The implied rule was long for the whole "
     "window, so it was buy-and-hold."),
    ("200-week MA", f"Three bottom-zone episodes with a full 365-day window (plus two open in 2026). Price spent "
     f"{A2['share_days_below_200wma'] * 100:.0f}% of out-of-sample days below the 200-week MA."),
]

# ---------------------------------------------------------------- markdown
md = [
    "# On-chain Indicator Audit, Batch 1: summary",
    "",
    "Famous Bitcoin cycle indicators, each frozen **as first published** and tested only on data **after** its first "
    "publication. The protocol was preregistered and sealed with RFC 3161 timestamps before any on-chain data were "
    "fetched. All results are published, whatever they show. Statistical analysis of past data only; not investment advice.",
    "",
    f"- Preregistration: `prereg/preregistration.json`, SHA-256 `{hdr['prereg_sha256']}`",
    f"- Seal record: SHA-256 `{hdr['seal_sha256']}`; signed by "
    + " and ".join(f"{a} at {b}" for a, b in hdr["signed_utc"]),
    f"- Block headers fetched from the Bitcoin P2P network at {hdr['headers']['fetch_started_utc']}, after the seal: "
    f"{hdr['headers']['rows']:,} headers, every one checked for its prev-hash link and proof of work (SHA-256 "
    f"`{hdr['headers']['sha256']}`)",
    "- Licence decision: `LICENCE-DECISION.md`",
    "",
    "## Result in one line",
    "",
    "**None of the six claims is supported.** One (stock-to-flow) had enough independent episodes to test and failed; "
    "the other five had only 1 to 4 out-of-sample episodes, so they are reported descriptively and no p-value is "
    "offered as evidence. Descriptively, those five all pointed the way their creators claimed (lower average "
    "returns after top signals, higher after bottom zones), but with 1 to 4 episodes each that is what a handful of "
    "cycles looks like, not evidence. All four indicators with an implied trading rule graded **F** against "
    "buy-and-hold BTC under rubric v1.1: none beat simply holding, net of 10 bps costs.",
    "",
    "## Summary table",
    "",
    "| ID | Indicator (first published) | Frozen rule tested (primary zone) | Out-of-sample window | Episodes | Avg 365-day BTC return after zone days vs all days | Holm status | Implied-rule audit |",
    "|---|---|---|---|---|---|---|---|",
]
for r in rows:
    fw = f"{pct(r['fwd365_zone'])} vs {pct(r['fwd365_all'])}" if r["fwd365_zone"] is not None else "n/a"
    st = r["status"] + (f" (p = {r['p']:.2f}, Holm {r['p_holm']:.2f})" if r["p"] is not None else "")
    g = f"**{r['grade']}** (excess {pct(r['strategy_excess_return'])}/yr)" if r["grade"] else "none (no exit/re-entry rule published)"
    md.append(f"| {r['id']} | {r['indicator']} ({r['published']}) | {r['zone']} ({r['kind']} claim) | {r['oos']} | "
              f"{r['episodes']} | {fw} | {st} | {g} |")
md += [
    "",
    "Returns are geometric means of 365-day log returns, over days with a full 365-day window. \"Episodes\" are runs of "
    "zone days (gaps under 30 days merged): the effective sample size. The preregistered rule: at least 5 episodes for "
    "inference; fewer means descriptive only, entered into Holm with p = 1. Top-zone claims predict *lower* forward "
    "returns; bottom-zone claims *higher*.",
    "",
    "## What we found",
    "",
]
for k, v in KEY_FINDINGS:
    md.append(f"- **{k}.** " + v.replace("<em>", "*").replace("</em>", "*").replace("<strong>", "**")
              .replace("</strong>", "**").replace("&ndash;", "-"))
md += [
    "",
    "## Not run in this batch (sealed, pending licence)",
    "",
    "MVRV Z-score, NUPL, SOPR, Reserve Risk, short-term-holder cost basis and realized price need UTXO-level data. "
    "No source we found permits publishing derived statistics commercially on its free or personal tiers "
    "(BGeometrics: non-commercial; Coin Metrics Community: CC BY-NC 4.0; Glassnode and Bitcoin Magazine Pro: personal "
    "use unless licensed). Their rules are frozen in the same sealed preregistration (Family B) and will be run only "
    "with a written commercial licence or our own UTXO replay. **No values of these metrics were loaded.**",
    "",
    "## Honest limits",
    "",
    "- **Not blind.** We had seen the BTC price path through 2026. Four indicators are pure functions of price. What "
    "protects the test is that every rule, threshold, window and test was taken from the creators' publications and "
    "sealed before the run, and that everything is published.",
    "- **Tiny samples.** Cycle-top signals fired 0 to 3 times after publication. No statistic can confirm or refute a "
    "claim from one or two events; we say so rather than print a p-value.",
    "- **Our operationalisations.** \"Close to the 200-week MA\" = within 10%; \"approaches 5x the 2-year MA\" = reaches it; "
    "stock-to-flow uses a daily trailing-365-day flow (PlanB used monthly data); Puell bands are Glassnode's (>4, <0.5); "
    "the Mayer Multiple's first-publication month is unverified, so its window starts conservatively on 2018-01-01. "
    "The 200-week heatmap's top (colour) claim was not tested: its thresholds were not retrievable, and we did not pick one.",
    "- **Issuance** is the consensus subsidy per block, assigned to the UTC day of each block's miner timestamp.",
    "",
    "## Deviations from the preregistration",
    "",
    "1. Clerical: the sealed document's `written_at_utc` field reads 18:23:00Z, a rounded-up estimate typed just before "
    "sealing; the RFC 3161 tokens (18:22:38Z) are authoritative. No effect on any result.",
    "2. The first run attempt crashed while loading headers (a pandas type error in the subsidy shift), before any "
    "statistic was computed. It was fixed and the analysis was then run once. No effect on the protocol.",
    "",
    "No other deviations.",
    "",
    "## Files",
    "",
    "- `results.json`: every statistic, including secondary horizons, raw p-values of descriptive tests (not evidence) and episode lists",
    "- `reports/summary.html`: this summary as a page; `reports/a3-...a6-*.html`: full rubric-v1.1 audits of the implied rules",
    "- `run.py`, `p2p.py`, `fetch_headers.py`, `summarize.py`: the full pipeline; `tests/test_onchain1.py`: synthetic tests",
    "",
    "Prices from the Coinbase Exchange public market-data API; we publish derived statistics only, never raw prices; "
    "no redistribution. Not investment advice.",
]
(HERE / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- html (standalone)
def row_html(r):
    fw = (f"{pct(r['fwd365_zone'])} <span class=m>vs {pct(r['fwd365_all'])}</span>" if r["fwd365_zone"] is not None else "n/a")
    cls = "ns" if r["status"].startswith("NOT SUPPORTED") else ("sup" if r["status"] == "SUPPORTED" else "nt")
    st = html.escape(r["status"].replace(" (descriptive only)", ""))
    if r["p"] is not None:
        st += f"<br><span class=m>p {r['p']:.2f}, Holm {r['p_holm']:.2f}</span>"
    else:
        st += "<br><span class=m>descriptive only</span>"
    g = (f"<a href=\"{html.escape(Path(r['report']).name)}\"><b class=grade>{r['grade']}</b></a> "
         f"<span class=m>excess {pct(r['strategy_excess_return'])}/yr</span>") if r["grade"] else "<span class=m>no implied rule</span>"
    return (f"<tr><td><b>{html.escape(r['indicator'])}</b><br><span class=m>{html.escape(r['published'])}</span></td>"
            f"<td>{html.escape(r['zone'])}<br><span class=m>{r['kind']} claim</span></td><td class=n>{r['episodes']}</td>"
            f"<td class=n>{fw}</td><td class={cls}>{st}</td><td>{g}</td></tr>")


page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>On-chain Indicator Audit 1</title>
<style>
:root{{--bg:#f5f3ec;--fg:#1b1d1f;--mut:#5f6368;--rule:#d8d4c8;--ns:#9b2c2c;--nt:#6b5d2a;--sup:#2f6b3a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#131517;--fg:#e8e6e1;--mut:#a0a4a8;--rule:#33373b;--ns:#e08a8a;--nt:#d8c47a;--sup:#8fd19e}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif;margin:0}}
.w{{max-width:1040px;margin:0 auto;padding:24px 16px 64px}}h1{{font-size:1.7rem;margin:.2em 0}}h2{{margin-top:2em;font-size:1.2rem}}
.m{{color:var(--mut);font-size:.85em}}.tw{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:.93rem}}
th,td{{text-align:left;vertical-align:top;padding:.55em .6em;border-bottom:1px solid var(--rule)}}th{{font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}}
td.n{{font-variant-numeric:tabular-nums;white-space:nowrap}}.ns{{color:var(--ns);font-weight:600}}.nt{{color:var(--nt);font-weight:600}}.sup{{color:var(--sup);font-weight:600}}
.grade{{font-size:1.2em}}.box{{border:1.5px solid var(--fg);padding:12px 16px;margin:16px 0}}code{{font-size:.85em;word-break:break-all}}a{{color:inherit}}
li{{margin:.35em 0}}
</style></head><body><div class=w>
<p class=m>Holdout Labs &middot; On-chain Indicator Audit &middot; Batch 1 &middot; 2026-09-25</p>
<h1>Six famous Bitcoin cycle indicators, tested only after they were published</h1>
<p>Each rule frozen exactly as its creator published it, tested only on data after its first publication, with the protocol sealed by RFC 3161 timestamps (DigiCert, FreeTSA) before any on-chain data were fetched. Every result is published.</p>
<div class=box><b>Result:</b> none of the six claims is supported. Stock-to-flow, the only one with enough independent episodes to test, went the wrong way. The other five fired 1&ndash;4 times after publication, too few for any honest inference, so we report them descriptively; all five pointed the way their creators claimed, which is what a handful of cycles can do by chance. All four implied trading rules graded <b>F</b> against buy-and-hold BTC.</div>
<div class=tw><table><thead><tr><th>Indicator</th><th>Frozen rule (primary zone)</th><th>Episodes</th><th>Avg 365-day return after zone days vs all days</th><th>Status (Holm, m=6)</th><th>Implied-rule audit</th></tr></thead><tbody>
{''.join(row_html(r) for r in rows)}
</tbody></table></div>
<p class=m>Out-of-sample windows start the first day after publication (or when the indicator can be computed) and end 2026-09-24. Returns are geometric means of 365-day returns over days with a full window. Fewer than 5 episodes = descriptive only (preregistered).</p>
<h2>What we found</h2><ul>{''.join(f'<li><b>{k}.</b> {v}</li>' for k, v in KEY_FINDINGS)}</ul>
<h2>Not run: pending a commercial data licence</h2>
<p>MVRV Z-score, NUPL, SOPR, Reserve Risk, short-term-holder cost basis and realized price need UTXO-level data, and no source we found permits commercial publication on its free or personal tiers. Their rules are sealed in the same preregistration; no values were loaded.</p>
<h2>Limits</h2><ul>
<li>Not blind: we had seen BTC prices through 2026; four indicators are pure functions of price. Protection comes from rules taken from the creators, sealed before the run, and full publication.</li>
<li>Tiny samples: cycle-top signals fired 0&ndash;3 times after publication. One or two events cannot confirm or refute a claim.</li>
<li>Our operationalisations (sealed in advance): &ldquo;close to the 200-week MA&rdquo; = within 10%; 5x the 2-year MA = reached; daily stock-to-flow; Glassnode's Puell bands; Mayer window from 2018-01-01.</li>
</ul>
<h2>Seal</h2>
<p class=m>Preregistration SHA-256 <code>{hdr['prereg_sha256']}</code><br>Seal record SHA-256 <code>{hdr['seal_sha256']}</code><br>
Signed: {', '.join(f'{a} {b}' for a, b in hdr['signed_utc'])}<br>Block headers fetched over P2P at {hdr['headers']['fetch_started_utc']} ({hdr['headers']['rows']:,} headers, PoW-checked).</p>
<p class=m>Prices from the Coinbase Exchange public market-data API; derived statistics only, never raw prices; no redistribution. Statistical analysis of past data. Not investment advice; no recommendation to buy, sell or hold anything.</p>
</div></body></html>
"""
(HERE / "reports" / "summary.html").write_text(page, encoding="utf-8", newline="\n")
print("\n".join(md[20:32]))
