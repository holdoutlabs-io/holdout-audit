# COINTIME-1: the True Market Mean, tested as published. Result

**Result, in the plan's own terms:**
- **M1 and M2 (mean reversion): NOT TESTABLE (descriptive only).** In the three years since the paper there were 2 and 4 independent episodes. The sealed plan needs at least 5 for a p-value.
- **R1 (regime line): grade F.** Holding Bitcoin only while it was above the True Market Mean compounded at 29.9% a year, against 45.6% for simply holding. Its average excess return was −13.9 points a year.

Run once on 2026-10-05 against the sealed [PREREG.md](PREREG.md) (sealed 2026-10-01 13:43:01Z, DigiCert and FreeTSA; SHA-256 `27035708…6bea`). Statistical findings about past data only. This is not investment advice and makes no claim about the authors' skill.

## What we tested

Check & Puell (2023), *Cointime Economics*, chapter 6:
- **The line.** The True Market Mean (TMM), or active-investor price, is Investor Cap divided by Active Supply.
- **Claim M.** TMM is "a likely reference point for mean reversion models".
- **Claim R.** The ratio of price to TMM, called AVIV, "oscillate[s] around a value of 1.0" and responds to bull and bear transitions.

The out-of-sample window runs from 2023-08-24, the day after publication, to 2026-09-24.

## Before the tests: no correction, and a cross-check that passed

- **Right of reply.** On 2026-10-01 we showed the frozen rules publicly to one of the paper's authors and asked for corrections before run day. None arrived: X was checked on 2026-10-05, before anything was computed. So there is no deviation.
- **Construction.** We built TMM ourselves from the public blockchain, exactly as preregistered:
  - coin-days instead of coinblocks;
  - newly minted coins valued at the daily close used by our realized cap (Bitstamp from 2011-08-18, Coinbase from 2015-07-20, and zero before any price existed).
- **Cross-check (PREREG §2, gate 5%).** First we wrote down and sealed the inclusion rule and eight public "True Market Mean" quotes ([CROSSCHECK-QUOTES.md](CROSSCHECK-QUOTES.md), sealed 2026-10-05 14:24:28Z, before any value was computed). Then we compared:

| Date | Quoted TMM | Ours | Difference |
|---|---|---|---|
| 2023-01-01 | $28,659 | $28,912 | +0.9% |
| 2023-10-10 | $29,720 | $29,964 | +0.8% |
| 2023-12-20 | $31,896 | $32,185 | +0.9% |
| 2024-10-08 | $47,000 | $47,831 | +1.8% |
| 2025-12-10 | $81,300 | $81,791 | +0.6% |
| 2026-02-18 | ~$79,000 | $79,233 | +0.3% |
| 2026-04-29 | $78,000–79,000 | $78,411 | −0.1% |
| 2026-09-16 | $76,700 | $77,070 | +0.5% |

**The median absolute difference is 0.7%, so the gate passes.** Two "Active Investor Price" quotes were reported for context only, under the sealed rule: one source quoted them as a different number from the True Market Mean on the same day. They differ from our TMM by −8.9% and −6.5%. Sources are in [CROSSCHECK-QUOTES.md](CROSSCHECK-QUOTES.md), and values in `crosscheck.json`.

## The tests (each run once)

| ID | Claim | Rule | Zone days (share) | Independent episodes | 90-day return after zone days vs all days | Status |
|---|---|---|---|---|---|---|
| **M1** | Mean reversion below the mean | AVIV < 1.0 | 192 (22%) | **2** (from 2023-08-24 and 2026-01-31) | +16.1% vs +7.7% (higher, as claimed) | **NOT TESTABLE (descriptive only)** |
| **M2** | Mean reversion far above the mean | AVIV ≥ 1.5 (our threshold, fixed before the run) | 278 (25%) | **4** (from 2024-02-14, 2024-11-06, 2025-05-08, 2025-10-02) | −5.2% vs +7.7% (lower, as claimed) | **NOT TESTABLE (descriptive only)** |

Both zones pointed the way the paper suggests, but there were too few independent episodes to tell a pattern from luck: 2 and 4, where the sealed rule needs 5. Following the plan, both enter the Holm family {M1, M2} with p = 1. Their circular-shift p-values (0.32 and 0.09) are shown for information only.

**R1, the regime line:**
- **Rule.** Hold BTC when the close is above TMM, otherwise cash. Decided at the close, 10 bps costs, N = 1, rubric v1.1, objective (a): beat buy-and-hold BTC. Full report: `reports/r1-true-market-mean.html`.
- **Grade F.** It was in the market 78% of days.
- **Returns.** Compound growth was 29.9% a year against 45.6% for holding. The average excess return was −13.9 points a year, with an excess Sharpe ratio of −0.62.
- **Holdout.** The excess Sharpe was −0.97 in-sample and −0.55 in the holdout.
- **Drawdown.** The rule's maximum drawdown was 42.8%.
- **Checks.** It fails DSR, haircut, SPA, holdout and stability, and passes costs.

## Descriptive (no p-values, as preregistered)

- **Share of days with AVIV > 1.**
  - Before publication: 64.3% (2011-08-18 to 2023-05-08, our data). The paper reports 53.3% to 2023-05-08 over its longer history, which starts before our first priced day.
  - After publication: 77.7%.
  - AVIV ranged from 0.76 to 1.86 after publication. On 2026-09-24 it stood at 1.09, with TMM at about $77,500.
- **Responsiveness at cycle turns.** The ONCHAIN-1 definition is an all-time-high close followed by a fall of at least 50%. The window contains one confirmed top (2025-10-06) and one provisional low (2026-06-30). The nearest crossing to each turn, in days:

  | Turn | AVIV = 1 | MVRV = 1 | Close = STH cost basis |
  |---|---|---|---|
  | Top 2025-10-06 | 117 | 997 | 4 |
  | Low 2026-06-30 (provisional) | 45 | 1,264 | 45 |

  AVIV responded far faster than MVRV, which did not cross 1 at all in the window. At the top it was slower than the short-term-holder cost basis, and at the low the two tied. With one cycle, this is an observation, not evidence.

## Honesty notes

- **Not blind.** As the plan says, the inputs had been computed in ONCHAIN-1, and the TMM is on public charts. The protection is that the rules are the authors' own construction, frozen and timestamped before we computed them, and run once.
- **Low power, as forecast.** The plan predicted "NOT TESTABLE" might be the honest outcome for the mean-reversion claims after only three years. It was. The forward record keeps growing, and any re-test needs a new sealed plan.
- **Data file.** We used `samples/onchain1/bq/metrics_daily.csv` (SHA-256 `28c1e423…a7df`), as preregistered. Its byte hash differs from the CSV entry in the ONCHAIN-1 manifest, but its values match the manifest-verified Parquet copy (`f556f7fe…eb57`) to within 5 × 10⁻¹⁰ relative error, a difference from CSV text rounding. No result depends on it.
- **Policy.** Holdout Labs has no position in this test's outcome. The founder's personal-trading policy applies (30-day blackout around publication).

## Reproduce

```
uv run python samples/cointime1/run.py crosscheck
uv run python samples/cointime1/run.py run
```
