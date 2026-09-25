# Positive controls: does the audit tell real edges from noise?

A test that fails everything proves nothing, so we checked that ours can pass a real edge. We built synthetic strategies with an edge of **known** size, ran each through the complete audit under the sealed rubric v1.2 **200 times**, and recorded the grades.

The protocol was written and sealed before the first run. It is [`docs/positive-controls/PROTOCOL.md`](positive-controls/PROTOCOL.md), sealed with DigiCert and FreeTSA at 2026-09-25 20:36:27Z, and its receipts are in `docs/positive-controls/seal/`. It pins:
- the generator's SHA-256 (`samples/controls/positive_controls.py`, `92ef1259…c659`);
- the cells and the pass definition;
- the headline cells.

The raw results, with every replicate's grade and checks, are in `samples/controls/results.json`.

## Headline

> **Our test isn't just a failure machine.** A strategy with a real excess Sharpe of **1.0** over its benchmark gets an **A or B 98.5%** of the time, and one with **0.5** does so **52.5%** of the time. A **pure-noise** strategy passes **2.0%** of the time.

These figures come from the preregistered headline cells (`a-clean-plateau`): 20 years of daily data, 10 declared variants on a parameter plateau, and costs included. The 95% intervals are:
- edge 1.0: 98.5% [95.7, 99.5];
- edge 0.5: 52.5% [45.6, 59.3];
- noise: 2.0% [0.8, 5.0].

## All cells (pass = grade A or B; Wilson 95% interval; grade shares in %)

| Cell | Objective | Nuisance | Variant grid | Planted edge | Pass (A/B) | A / B / C / D / F |
|---|---|---|---|---|---|---|
| `a-clean-plateau-0.0` | (a) | clean | plateau | 0.0 | **2.0%** [0.8, 5.0] | 0 / 2 / 2 / 24 / 71 |
| `a-clean-plateau-0.25` | (a) | clean | plateau | 0.25 | **17.0%** [12.4, 22.8] | 8 / 9 / 20 / 34 / 30 |
| `a-clean-plateau-0.5` | (a) | clean | plateau | 0.5 | **52.5%** [45.6, 59.3] | 38 / 14 / 15 / 24 / 9 |
| `a-clean-plateau-0.75` | (a) | clean | plateau | 0.75 | **85.0%** [79.4, 89.3] | 76 / 9 / 6 / 8 / 1 |
| `a-clean-plateau-1.0` | (a) | clean | plateau | 1.0 | **98.5%** [95.7, 99.5] | 97 / 2 / 2 / 0 / 0 |
| `a-heavy-plateau-0.0` | (a) | heavy | plateau | 0.0 | **1.5%** [0.5, 4.3] | 0 / 1 / 4 / 22 / 73 |
| `a-heavy-plateau-0.25` | (a) | heavy | plateau | 0.25 | **15.5%** [11.1, 21.2] | 5 / 10 / 18 / 36 / 30 |
| `a-heavy-plateau-0.5` | (a) | heavy | plateau | 0.5 | **52.0%** [45.1, 58.8] | 39 / 13 / 15 / 24 / 10 |
| `a-heavy-plateau-0.75` | (a) | heavy | plateau | 0.75 | **88.0%** [82.8, 91.8] | 79 / 9 / 6 / 6 / 0 |
| `a-heavy-plateau-1.0` | (a) | heavy | plateau | 1.0 | **95.5%** [91.7, 97.6] | 94 / 2 / 2 / 1 / 1 |
| `a-clean-isolated-0.0` | (a) | clean | isolated | 0.0 | **0.5%** [0.1, 2.8] | 0 / 0 / 5 / 28 / 67 |
| `a-clean-isolated-0.5` | (a) | clean | isolated | 0.5 | **18.5%** [13.7, 24.5] | 8 / 10 / 36 / 30 / 16 |
| `a-clean-isolated-1.0` | (a) | clean | isolated | 1.0 | **91.0%** [86.2, 94.2] | 79 / 12 / 8 / 0 / 0 |
| `a-clean-overfit-0.0` | (a) | clean | overfit | 0.0 | **1.0%** [0.3, 3.6] | 0 / 0 / 15 / 32 / 52 |
| `c-clean-plateau-0.0` | (c) | clean | plateau | 0.0 | **1.5%** [0.5, 4.3] | 1 / 0 / 5 / 20 / 73 |
| `c-clean-plateau-0.25` | (c) | clean | plateau | 0.25 | **73.5%** [67.0, 79.1] | 62 / 12 / 12 / 14 / 0 |
| `c-clean-plateau-0.5` | (c) | clean | plateau | 0.5 | **100.0%** [98.1, 100.0] | 100 / 0 / 0 / 0 / 0 |

## What this shows

- **It discriminates.** The pass rate climbs from about 2% with no edge to about 98% at an excess Sharpe of 1.0. The curve is essentially the same with heavy tails and volatility clustering: 1.5% [0.5, 4.3] with no edge and 95.5% [91.7, 97.6] at 1.0.
- **It resists selection.** Choosing the best of 50 zero-edge variants in sample produces an A or B 1.0% [0.3, 3.6] of the time.
- **It is demanding.** An edge of 0.25 on 20 years passes only about one time in six, and an edge of 0.5 about half the time. A real edge that exists in only one of ten variants (the isolated grid) passes 18.5% [13.7, 24.5] at 0.5, because the rubric reads an isolated peak as fragile. That is the price of the low false-pass rate, and it is deliberate.
- **Objective (c), new in v1.2, also discriminates.** It passes 1.5% [0.5, 4.3] with no Sharpe improvement, 73.5% [67.0, 79.1] at +0.25 and 100.0% [98.1, 100.0] at +0.5.

## What this does not show

- Synthetic data are cleaner than markets. Real strategies face regime changes, structural breaks and costs that vary over time, none of which is in these cells.
- The pass rate depends on sample length. With 10 years instead of 20, the same edge would pass less often.
- These controls say nothing about any particular strategy's future. They are evidence about the *test*, not about markets.

## Reproduce

```bash
uv run python samples/controls/positive_controls.py      # about 15 minutes on 30 cores; writes samples/controls/results.json
```
