# Positive-control protocol (sealed before the first run)

Written 2026-09-25T20:36:25Z. This document is sealed with RFC 3161 timestamps (DigiCert and FreeTSA) before any replicate in the range below is run.

**Question.** Does the audit tell a real edge from noise? We plant edges of known size in synthetic strategy/benchmark pairs, run each pair through the complete audit under the sealed rubric v1.2 (SHA-256 81bc60b5bf4520fdfb91c43b37883c30a9a2061903442d1e8a8b05f3d37a71fc), and record the grades.

**Code.** `samples/controls/positive_controls.py`, SHA-256 `92ef12594f520c2b168d5a533fa8dad0b4b5bc52b18ddd8fa7b6123aceeac659`. It may not change after sealing; the results file records the replicate seeds.

**Data.** Synthetic only.
- 20 years of business days (T = 5,040, 252 a year).
- Benchmark: 7% a year mean, 16% a year volatility.
- Costs: 2 bps per unit traded, about 10 units a year. The planted edges are net of costs.
- Default holdout: the last 30%.
- Bootstrap: 1,000 draws. The seed is fixed per replicate.

**Cells (17), 200 replicates each (replicate indices 0-199).**

| Cells | Objective | Nuisance | Variant grid (N declared) | Planted edge |
|---|---|---|---|---|
| a-clean-plateau | (a) beat the benchmark | Gaussian, IID | 10 variants on a plateau: neighbour correlation 0.9 per step, edge scaled by the correlation | true excess Sharpe 0, 0.25, 0.5, 0.75, 1.0 (tracking error 6%) |
| a-heavy-plateau | (a) | Student-t(4) GARCH(1,1) (alpha 0.08, beta 0.90) on the benchmark and on each excess stream | as above | 0, 0.25, 0.5, 0.75, 1.0 |
| a-clean-isolated | (a) | Gaussian | 10 variants, only the chosen one has the edge | 0, 0.5, 1.0 |
| a-clean-overfit | (a) | Gaussian | 50 zero-edge variants; the chosen one is the best in-sample (first 70%) by excess Sharpe | 0 (the apparent edge is pure selection) |
| c-clean-plateau | (c) improve Sharpe | Gaussian | strategy = 0.6 x benchmark + a stream with 4% volatility; plateau grid | true Sharpe improvement 0, 0.25, 0.5 |

**Outputs, fixed in advance.** For each cell:
- the distribution of grades;
- the **pass rate**, defined as the share graded **A or B**, with a Wilson 95% interval;
- the **false-pass rate**, which is the pass rate in every cell whose planted edge is 0.

**Headline, fixed in advance.** The headline uses the *a-clean-plateau* cells: the pass rate at edges 0.5 and 1.0, and the false-pass rate at edge 0. The heavy-tail, isolated-edge, overfit and objective-(c) cells are reported alongside it, whatever they show.

**What we will not do.** We will not change the rubric, the code, the cells or the number of replicates after seeing results. We will not drop a cell. If the audit fails to discriminate, we will say so.

**Smoke test (disclosed).** Before sealing, each cell was run once with replicate index 99999 (outside 0-199) to check that the software runs. Grades from that run were neither printed nor stored.
