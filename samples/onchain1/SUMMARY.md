# On-chain Indicator Audit, Batch 1: summary

Famous Bitcoin cycle indicators, each frozen **as first published** and tested only on data **after** its first publication. The protocol was preregistered and sealed with RFC 3161 timestamps before any on-chain data were fetched. All results are published, whatever they show. Statistical analysis of past data only; not investment advice.

- Preregistration: `prereg/preregistration.json`, SHA-256 `aafe3c37f5bbf83bc6e4b9a986ef1c936c3b74a927c253b833a5a7626482de40`
- Seal record: SHA-256 `f8d7d587466a4bb61b5c179aba44bb766825a6a495cc3ecb68d16e39c1810275`; signed by digicert at 2026-09-25T18:22:38Z and freetsa at 2026-09-25T18:22:38Z
- Block headers fetched from the Bitcoin P2P network at 2026-09-25T18:23:09Z, after the seal: 968,471 headers, every one checked for its prev-hash link and proof of work (SHA-256 `a69bc2d867edf4e5c46ea5b87aeb0e1fbc24ff795d7776b72407abe4f9025b15`)
- Licence decision: `LICENCE-DECISION.md`

## Result in one line

**None of the six claims is supported.** One (stock-to-flow) had enough independent episodes to test and failed; the other five had only 1 to 4 out-of-sample episodes, so they are reported descriptively and no p-value is offered as evidence. Descriptively, those five all pointed the way their creators claimed (lower average returns after top signals, higher after bottom zones), but with 1 to 4 episodes each that is what a handful of cycles looks like, not evidence. All four indicators with an implied trading rule graded **F** against buy-and-hold BTC under rubric v1.1: none beat simply holding, net of 10 bps costs.

## Summary table

| ID | Indicator (first published) | Frozen rule tested (primary zone) | Out-of-sample window | Episodes | Avg 365-day BTC return after zone days vs all days | Holm status | Implied-rule audit |
|---|---|---|---|---|---|---|---|
| A1 | Pi Cycle Top (Philip Swift, Apr 2019) | crossing day (top claim) | 2019-05-01 to 2026-09-24 | 1 | -33% vs +42% | NOT TESTABLE (descriptive only) | none (no exit/re-entry rule published) |
| A2 | 200-week MA heatmap (bottom claim) (PlanB concept, Jan 2019) | close <= 1.10 x 200WMA (bottom claim) | 2019-05-19 to 2026-09-24 | 3 | +102% vs +42% | NOT TESTABLE (descriptive only) | none (no exit/re-entry rule published) |
| A3 | Mayer Multiple (Trace Mayer, 2017) | MM > 2.4 (top claim) | 2018-01-01 to 2026-09-24 | 3 | -21% vs +36% | NOT TESTABLE (descriptive only) | **F** (excess +3%/yr) |
| A4 | 2-Year MA Multiplier (Philip Swift, Jul 2017) | close < 2yMA (bottom claim) | 2017-08-01 to 2026-09-24 | 4 | +108% vs +33% | NOT TESTABLE (descriptive only) | **F** (excess -13%/yr) |
| A5 | Puell Multiple (David Puell, Mar 2019) | Puell < 0.5 (bottom claim) | 2019-04-01 to 2026-09-24 | 4 | +105% vs +42% | NOT TESTABLE (descriptive only) | **F** (excess +0%/yr) |
| A6 | Stock-to-flow (PlanB 2019) (22 Mar 2019) | close < S2F model (bottom claim) | 2019-03-23 to 2026-09-24 | 6 | +26% vs +42% | NOT SUPPORTED (p = 0.94, Holm 1.00) | **F** (excess -19%/yr) |

Returns are geometric means of 365-day log returns, over days with a full 365-day window. "Episodes" are runs of zone days (gaps under 30 days merged): the effective sample size. The preregistered rule: at least 5 episodes for inference; fewer means descriptive only, entered into Holm with p = 1. Top-zone claims predict *lower* forward returns; bottom-zone claims *higher*.

## What we found

- **Stock-to-flow.** The only primary claim with enough episodes to test (6). Days below the model price were followed by *lower* 365-day returns than average, the opposite of the claim (one-sided p = 0.94; Holm-adjusted 1.00): **not supported**. As a level model it drifted away: BTC closed at 0.15x the model on average in 2025 and 0.09x in 2026 (model price on 2026-09-24: $862,472).
- **Pi Cycle Top.** One out-of-sample crossing, on 2021-04-12. It came one day before the April 2021 local high (context, not a preregistered test), but the highest close within a year either side came 210 days later, on 2021-11-08, and 12.9% higher, so it misses the preregistered 'within 3 days' test at every window. No crossing at all before the highest closes of 2024-03 or 2025-10.
- **Mayer Multiple > 2.4.** Three episodes (Jan 2018, Jun 2019, Jan-Mar 2021). The first came 20 days after the December 2017 high and the second on the day of the 2019 high; the 2021 one came ten months before the cycle high. None since March 2021. Its implied rule beat buy-and-hold by 3% a year, all of it from those early episodes: not significant (SPA p = 0.12), and identical to holding throughout the holdout, so it grades F.
- **2-Year MA Multiplier.** Four bottom-zone episodes with a full 365-day window (plus one open in 2026); the 5x top zone fired only in late 2017. Too few for inference.
- **Puell Multiple.** Never above 4 after publication; four episodes below 0.5. The implied rule was long for the whole window, so it was buy-and-hold.
- **200-week MA.** Three bottom-zone episodes with a full 365-day window (plus two open in 2026). Price spent 13% of out-of-sample days below the 200-week MA.

## Not run in this batch (sealed, pending licence)

MVRV Z-score, NUPL, SOPR, Reserve Risk, short-term-holder cost basis and realized price need UTXO-level data. No source we found permits publishing derived statistics commercially on its free or personal tiers (BGeometrics: non-commercial; Coin Metrics Community: CC BY-NC 4.0; Glassnode and Bitcoin Magazine Pro: personal use unless licensed). Their rules are frozen in the same sealed preregistration (Family B) and will be run only with a written commercial licence or our own UTXO replay. **No values of these metrics were loaded.**

## Honest limits

- **Not blind.** We had seen the BTC price path through 2026. Four indicators are pure functions of price. What protects the test is that every rule, threshold, window and test was taken from the creators' publications and sealed before the run, and that everything is published.
- **Tiny samples.** Cycle-top signals fired 0 to 3 times after publication. No statistic can confirm or refute a claim from one or two events; we say so rather than print a p-value.
- **Our operationalisations.** "Close to the 200-week MA" = within 10%; "approaches 5x the 2-year MA" = reaches it; stock-to-flow uses a daily trailing-365-day flow (PlanB used monthly data); Puell bands are Glassnode's (>4, <0.5); the Mayer Multiple's first-publication month is unverified, so its window starts conservatively on 2018-01-01. The 200-week heatmap's top (colour) claim was not tested: its thresholds were not retrievable, and we did not pick one.
- **Issuance** is the consensus subsidy per block, assigned to the UTC day of each block's miner timestamp.

## Deviations from the preregistration

1. Clerical: the sealed document's `written_at_utc` field reads 18:23:00Z, a rounded-up estimate typed just before sealing; the RFC 3161 tokens (18:22:38Z) are authoritative. No effect on any result.
2. The first run attempt crashed while loading headers (a pandas type error in the subsidy shift), before any statistic was computed. It was fixed and the analysis was then run once. No effect on the protocol.

No other deviations.

## Files

- `results.json`: every statistic, including secondary horizons, raw p-values of descriptive tests (not evidence) and episode lists
- `reports/summary.html`: this summary as a page; `reports/a3-...a6-*.html`: full rubric-v1.1 audits of the implied rules
- `run.py`, `p2p.py`, `fetch_headers.py`, `summarize.py`: the full pipeline; `tests/test_onchain1.py`: synthetic tests

Prices from the Coinbase Exchange public market-data API; we publish derived statistics only, never raw prices; no redistribution. Not investment advice.
