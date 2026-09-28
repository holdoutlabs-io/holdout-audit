# holdout-audit

[![CI](https://github.com/holdoutlabs-io/holdout-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/holdoutlabs-io/holdout-audit/actions/workflows/ci.yml)

**Scientific audits for trading strategies.** `holdout-audit` measures how much of a backtest survives the tests that catch overfitting:
- how many variants were tried;
- whether the edge holds on data the search never touched;
- whether it survives costs, regimes and parameter changes.

It produces a written report with a transparent **A–F fragility grade**. The rules that set the grade are published and **sealed with RFC 3161 timestamps before use**.

It is the open-source engine behind [Holdout Labs](https://holdoutlabs.io). Every audit Holdout Labs publishes can be reproduced from this repository.

> **Statistics on past data only.** This software and its reports measure how fragile historical evidence is. They are not investment advice and not a recommendation to buy, sell or hold anything, and they give no guarantee about future results. See [docs/DISCLAIMER.md](docs/DISCLAIMER.md).

## What it does

```
your returns / trades ─┐   checks on the excess return over a benchmark (default: buy-and-hold)
variant matrix (opt.) ─┼─► Sharpe ± SE (Lo) ─► PSR ─► Deflated Sharpe (N variants tried)
                       ├─► PBO via CSCV (12,870 splits)       ─┐
                       ├─► Harvey–Liu haircut (Bonf/Holm/BHY)  ├─► 8–9 checks ─► A–F grade (sealed rubric)
                       ├─► White Reality Check + Hansen SPA    │
                       ├─► holdout degradation                 │
                       ├─► year and volatility-regime stability│
                       ├─► transaction-cost break-even         │
                       └─► parameter plateau vs isolated peak ─┘ ─► self-contained HTML report (prints to PDF)
```

- **Declared objectives** (rubric v1.2), chosen *before* looking at results:
  - (a) beat the benchmark;
  - (b) reduce drawdown at an acceptable, pre-declared return cost;
  - (c) improve the Sharpe ratio over the benchmark.
- **Sealing.** `holdout-audit seal-doc` timestamps any document, such as a preregistration, an objective declaration or a rubric, with two independent RFC 3161 authorities (DigiCert and FreeTSA). `verify-seal` re-checks it later.
- **Reproducibility.** Every report prints the SHA-256 of its inputs, of the audited series, of the rubric document and of its seal record, together with the bootstrap seed.

## Quick start

Requires Python 3.11 or later and [uv](https://docs.astral.sh/uv/). Sealing also needs `openssl` on your PATH.

```bash
git clone https://github.com/holdoutlabs-io/holdout-audit && cd holdout-audit
uv sync
uv run pytest

# Audit a daily return series (see docs/INPUT-FORMATS.md)
uv run holdout-audit audit --returns my_returns.csv --n-trials 40 --cost-bps 2 --out my-audit.html

# With every variant you tried (enables PBO, SPA across the family, and the parameter surface)
uv run holdout-audit audit --returns my_returns.csv --variants my_variants.csv \
    --chosen "fast=50|slow=200" --out my-audit.html

# Declare the objective first, seal it, then audit against it
uv run holdout-audit seal-doc declaration.json --out-dir declaration-seal
uv run holdout-audit audit --returns my_returns.csv --declaration declaration.json \
    --declaration-seal declaration-seal --out my-audit.html

# Verify any seal in this repository, e.g. the current rubric
uv run holdout-audit verify-seal docs/rubric-seal-v1.2
```

From Python:

```python
from holdout_audit import AuditConfig, run_audit
from holdout_audit.io import load_returns
from holdout_audit.report import write_report

res = run_audit(AuditConfig(name="My strategy", returns=load_returns("r.csv"), n_trials=40, base_cost_bps=2))
print(res.headline())
write_report(res, "audit.html")
```

## Use it in CI

Add a few lines to any workflow. Every pull request then gets a comment (and every run a job summary) with the deflated Sharpe ratio, PBO (when you give the variant grid), the holdout comparison and the A–F grade. The action can also write a badge.

```yaml
permissions:
  contents: read
  pull-requests: write          # for the PR comment

steps:
  - uses: actions/checkout@v6
  - id: holdout
    uses: holdoutlabs-io/holdout-audit@v0
    with:
      returns: results/returns.csv       # date,return[,turnover][,market]
      variants: results/variants.csv     # optional: every variant you tried (PBO, N for the DSR)
      # n-trials: 40                     # ...or just how many variants you tried
      holdout-start: "2023-01-02"        # first date the search never touched
      frequency: daily                   # auto | daily | crypto | weekly | monthly | 252
      badge-path: badges/holdout-grade.svg
      # benchmark: bench.csv             # auto | zero | market | CSV of benchmark returns
      # fail-below: C                    # fail the job on a D or F
  - run: echo "grade ${{ steps.holdout.outputs.grade }}, DSR ${{ steps.holdout.outputs.dsr }}, PBO ${{ steps.holdout.outputs.pbo }}"
```

The badge is a self-contained SVG. Commit it, or publish it as an artifact, and link it from your README:

![holdout grade: B](examples/github-action/holdout-grade.svg) *(example: seeded synthetic data)*

```markdown
[![holdout grade](badges/holdout-grade.svg)](https://holdoutlabs.io/tools/luck/)
```

Inputs:
- `returns` (required);
- `benchmark`, `variants`, `chosen`, `n-trials`, `holdout-start`, `frequency`, `cost-bps`, `name`;
- `badge-path`, `fail-below`, `comment` (default `true`), `github-token`, `python-version`.

Outputs: `grade`, `dsr`, `pbo`, `score` and `summary-path`. Without a workflow, run `holdout-audit ci --returns r.csv ...` locally; it takes the same options and prints the markdown summary.

A full example, with seeded synthetic data and a workflow file, is in [`examples/github-action/`](examples/github-action/). This repository runs it on every push ([`ci.yml`](.github/workflows/ci.yml)).

The grade rates how fragile the historical evidence is. It is not a forecast, and a good grade does not mean a strategy will make money. Statistics on past data, not investment advice. Want to try it without CI? Use [holdoutlabs.io/tools/luck](https://holdoutlabs.io/tools/luck/).

## Methods and citations

Each statistic is described, with its assumptions and limits, in [docs/METHODS.md](docs/METHODS.md).

| Statistic | Source |
|---|---|
| Sharpe-ratio standard error; autocorrelation-adjusted annualisation | Lo (2002), *Financial Analysts Journal*; Mertens (2002) |
| Probabilistic Sharpe ratio, minimum track record | Bailey & López de Prado (2012), *Journal of Risk* |
| Deflated Sharpe ratio | Bailey & López de Prado (2014), *Journal of Portfolio Management* |
| Probability of backtest overfitting (CSCV) | Bailey, Borwein, López de Prado & Zhu (2016), *Journal of Computational Finance* |
| Multiple-testing haircut | Harvey & Liu (2015), *Journal of Portfolio Management*; Harvey, Liu & Zhu (2016), *Review of Financial Studies* |
| Reality Check; Superior Predictive Ability | White (2000), *Econometrica*; Hansen (2005), *Journal of Business & Economic Statistics* |
| Stationary bootstrap | Politis & Romano (1994), *Journal of the American Statistical Association* |
| Sharpe-ratio difference test (objective c) | Ledoit & Wolf (2008), *Journal of Empirical Finance* |
| CVaR (objective b) | Rockafellar & Uryasev (2000), *Journal of Risk* |

## The grade, and evidence that it discriminates

The grading rules are versioned documents. Each was sealed before it was used:
- [v1.0](docs/RUBRIC-v1.0.md);
- [v1.1](docs/RUBRIC-v1.1.md);
- [v1.2](docs/RUBRIC-v1.2.md), the current version.

The receipts are in `docs/rubric-seal*/`, and the change log is at the end of [docs/METHODS.md](docs/METHODS.md).

**Positive controls** ([docs/POSITIVE-CONTROLS.md](docs/POSITIVE-CONTROLS.md)). We planted edges of known size in synthetic data and ran each case through the full audit 200 times, under a protocol sealed before the first run:
- a real excess Sharpe of 1.0 gets an A or B **98.5%** of the time;
- a real excess Sharpe of 0.5 gets one **52.5%** of the time;
- pure noise passes **2.0%** of the time;
- the best of 50 noise variants passes **1.0%** of the time.

## Published audits (reproducible from `samples/`)

Every batch was preregistered and sealed before its data were fetched, run once, and published in full.

| Folder | What | Result |
|---|---|---|
| `samples/reports/` | Sample audits 1–4: SPY golden cross, SPY RSI(2), BTC 50-day SMA, TradingView Supertrend on BTC | 4 of 4 graded F against buy-and-hold |
| `samples/batch1/` | Ten TradingView built-in strategies on SPY and BTC (20 audits) | 0 of 20 survive Holm |
| `samples/batch2/` | Ten classic published rules on stocks and bonds (14 audits) | 0 of 14 survive Holm |
| `samples/batch3/` | Six strategies with the strongest published evidence, each judged on its own claim | 0 of 6 survive; Faber timing cut drawdowns robustly but exceeded its declared return cost |
| `samples/onchain1/` | Six Bitcoin on-chain cycle indicators, tested after publication | No claim supported |
| `samples/controls/` | Positive controls | see above |

Raw price data are **not** included. Each folder has fetch scripts and a `MANIFEST.json` of SHA-256 hashes, so you can fetch the same data yourself and check it byte for byte. See [samples/data/SOURCES.md](samples/data/SOURCES.md) for sources and terms.

Some sealed documents in `samples/` are published byte for byte, because any edit would break their timestamps. They refer to the maintainers' internal research programme and policy-ledger entries (for example "DEV-031", the instrument policy). The instrument policy is also encoded in `samples/data/fetch.py` and enforced by `tests/test_policy.py`: equity indices, equity ETFs, bond ETFs and BTC; no commodity instruments.

## Repository layout

```
src/holdout_audit/   the package: stats/ (sharpe, pbo, haircut, bootstrap, stability, objective, objective_sharpe),
                     grade.py (rubrics), audit.py, report/ (HTML), seal.py (RFC 3161), rubric.py, cli.py, ci.py
tests/               pytest suite, including published worked examples where they exist
docs/                METHODS, RUBRIC v1.0 / v1.1 / v1.2 with seal receipts, POSITIVE-CONTROLS, INPUT-FORMATS,
                     DISCLAIMER, SCOPE-POLICY, templates for preregistrations and objective declarations
samples/             every published audit: preregistrations, seals, runners, fetch scripts, reports, summaries
examples/            GitHub Action example (seeded synthetic data)
action.yml           the GitHub Action (uses: holdoutlabs-io/holdout-audit@v0)
```

## Licence

[Apache-2.0](LICENSE); see [NOTICE](NOTICE). Contributions are welcome under the same licence.

Questions: hello@holdoutlabs.io · [holdoutlabs.io](https://holdoutlabs.io)
