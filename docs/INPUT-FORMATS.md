# Input formats

The audit reads CSV files: UTF-8, a header row, ISO dates (`YYYY-MM-DD`), and returns as **simple fractions** (`0.012` = +1.2%). Use `--percent` if yours are in percent.

### A. Daily strategy returns (preferred)

```csv
date,return,turnover,market
2019-01-02,0.0031,1.0,0.0035
2019-01-03,-0.0120,0.0,-0.0239
```

| Column | Required | Meaning |
|---|---|---|
| `date` | yes | Trading day (UTC day for crypto) |
| `return` | yes | Strategy return that day, on the capital allocated to it, gross or net of costs. For gross returns, `--cost-bps` applies a cost per unit of turnover |
| `turnover` | recommended | Fraction of capital traded that day. Entering a full position is 1, closing it is 1, and flipping long to short is 2. This enables the cost-sensitivity check |
| `market` | optional | Return of the underlying or benchmark that day. It enables the volatility-regime split and a "beats buy-and-hold" test |

At least 60 rows are required. Two years or more is recommended; five or more is better.

### B. Trade list

```csv
entry_date,exit_date,return
2021-03-01,2021-03-09,0.042
2021-04-12,2021-04-13,-0.011
```

There is one row per closed trade, with `return` as the fractional return on the capital committed. The toolkit converts it to daily returns by spreading each trade's compounded return evenly over its holding days, with turnover 1 at entry and at exit. This approximation is stated in the report. If you can provide daily marked-to-market returns (option A), please do.

### C. How many variants you tried (`--n-trials`)

Give the number of distinct rule or parameter combinations you tested before settling on this one, **including the ones you abandoned**. If you are unsure, use an honest upper estimate. The report always includes a "DSR against N" table showing how the conclusions change with N. Without it (and without a variant matrix), the grade is capped at B.

### D. Variant return matrix (`--variants`, `--chosen`)

```csv
date,fast=20|slow=100,fast=20|slow=150,fast=50|slow=200,...
```

This holds the daily returns of every variant, one column each, on the same dates as A. It enables PBO (CSCV) and the Reality Check / SPA across the family. If the columns are named `param=value|param=value`, the parameter surface is mapped too. Pass the audited column with `--chosen`.

### E. The objective (`--declaration`), declared before looking at results

What counts as success should be fixed **before** the results are seen. Choosing the goal afterwards is the forking path these audits exist to catch. The rubric (v1.2) offers three objectives:

| Objective | What is graded | Extra field |
|---|---|---|
| **(a) Beat the benchmark** (default) | Selection-adjusted excess return over the benchmark (buy-and-hold of the traded asset unless another is named) | none |
| **(b) Reduce drawdown at acceptable cost** | The reductions in maximum drawdown and daily CVaR95 against the benchmark, with bootstrap intervals and the same overfitting corrections | `max_return_shortfall_annual`, e.g. `0.02` for up to 2% a year less return |
| **(c) Improve Sharpe vs the benchmark** | The Sharpe-ratio improvement, with a paired bootstrap and the same corrections | none |

To declare one:
1. Fill in `docs/objective-declaration-template.json` and date it (`declared_at_utc`).
2. Optionally seal it: `holdout-audit seal-doc declaration.json --out-dir declaration-seal`. This adds RFC 3161 timestamps from DigiCert and FreeTSA.
3. Run `holdout-audit audit ... --declaration declaration.json [--declaration-seal declaration-seal] [--data-received 2026-10-01T09:00:00Z]`.

The declaration's SHA-256, and its seal if one is given, are printed in the report. A declaration dated after `--data-received` is refused. Without a declaration, objective (a) applies.
