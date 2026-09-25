# Holdout Labs Fragility Rubric, version 1.0

Status: **frozen**. This document is sealed with RFC 3161 timestamps (DigiCert and FreeTSA); the receipts are in `docs/rubric-seal/`. Any change requires a new version number, a new seal, and an entry in the change log of `docs/METHODS.md`, all *before* the new version is applied to any audit.

The grade describes how fragile the historical evidence for a strategy is. It is not a forecast and not a recommendation.

## 1. Definitions

- **r_t**: the audited strategy's return in period t, net of the base-case cost (one-way cost per unit of turnover, stated in the report).
- **Benchmark b_t**: by default, the buy-and-hold total return of the asset the strategy trades (the `market` column). A client may name a different benchmark in writing before the audit starts. The zero (cash) benchmark is used only when (a) the client declares the strategy market-neutral or long/short and names cash as its benchmark, or (b) no benchmark series exists. The report states which benchmark was used, and why, on its first page.
- **Excess return e_t = r_t − b_t**. For each variant k in the variant matrix, e_k,t = r_k,t − b_t.
- **Excess Sharpe ratio**: mean(e)/sd(e), per period (ddof 1), annualised by √q (q = 252 for business-day data, 365 for 7-day calendars).
- **N (variants tried)**: the larger of the client's declared number and the number of variant-matrix columns. It is 1 if neither is given ("undeclared").
- **Variant dispersion V**: the sample variance (ddof 1) of the per-period *excess* Sharpe ratios of the variant-matrix columns. It is 1/T if no matrix is supplied.

## 2. The eight checks

Each check scores **PASS = 2**, **CAUTION = 1** or **FAIL = 0** points, or **N/A**, in which case it is excluded from both the points and the maximum.

| # | Key | Check | Computed on | PASS | CAUTION | FAIL |
|---|---|---|---|---|---|---|
| 1 | dsr | Deflated Sharpe ratio (Bailey & López de Prado 2014) | excess returns e; N; V | DSR ≥ 0.95 | 0.80 ≤ DSR < 0.95 | DSR < 0.80 |
| 2 | pbo | PBO via CSCV, 16 blocks, all 12,870 splits (Bailey, Borwein, López de Prado & Zhu 2016) | variant excess returns, ranked by excess Sharpe | PBO ≤ 0.20 | 0.20 < PBO ≤ 0.50, **or** PBO > 0.50 with P(OOS excess Sharpe of IS winner < 0) ≤ 0.10 | otherwise. N/A without a variant matrix |
| 3 | haircut | Harvey–Liu multiple-testing haircut | t = annualised excess Sharpe × √years; BHY-adjusted p if every variant is supplied, else Bonferroni | adjusted p ≤ 0.05 | 0.05 < p ≤ 0.10 | p > 0.10 |
| 4 | spa | Hansen SPA test, consistent p-value; stationary bootstrap, 1,000 draws, mean block max(5, T^⅓) | mean of e_k over all variants (or the strategy alone) | p ≤ 0.05 | 0.05 < p ≤ 0.10 | p > 0.10 |
| 5 | holdout | Holdout degradation | excess Sharpe before and after the holdout split (client-supplied date, else the start of the last 30%) | holdout excess SR > 0 **and** in-sample excess SR > 0 **and** holdout ≥ 50% of in-sample | holdout excess SR > 0, PASS not met | holdout excess SR ≤ 0 |
| 6 | stability | Period and regime stability | calendar years: strategy's compounded return minus benchmark's compounded return; regimes: terciles of the benchmark's trailing 21-day volatility, lagged 1 period | ≥ 60% of years with positive excess **and** annualised excess SR > 0 in every tercile | ≥ 50% of years with positive excess, PASS not met | < 50% of years with positive excess |
| 7 | costs | Transaction-cost headroom | **absolute** gross returns: break-even one-way cost = mean(gross)/mean(turnover) | ≥ 20 bps | 5 ≤ bps < 20 | < 5 bps. N/A without turnover |
| 8 | surface | Parameter plateau | **absolute** annualised Sharpe over the supplied grid; neighbour ratio = mean SR of one-step neighbours ÷ SR of chosen cell | ratio ≥ 0.70 | 0.40 ≤ ratio < 0.70 | < 0.40, or chosen SR ≤ 0. N/A without a parameter grid |

Checks 7 and 8 stay absolute on purpose. They measure how fragile the strategy's own return is to costs and parameter choice; its performance relative to the benchmark is already scored by checks 1–6.

With the zero benchmark, e_t = r_t and every check reduces to its absolute form.

## 3. From points to a letter

Score = points ÷ maximum available points (N/A checks excluded).

| Letter | Score |
|---|---|
| A | ≥ 0.85 |
| B | ≥ 0.70 |
| C | ≥ 0.55 |
| D | ≥ 0.40 |
| F | < 0.40 |

## 4. Hard caps (applied after the bands; the most severe cap wins)

1. **Benchmark cap.** If the strategy does not beat its benchmark, the grade is at most **C**. "Does not beat" means that the SPA check (#4) is FAIL, **or** that the audited strategy's annualised mean excess return, net of base-case costs, is ≤ 0.
2. **Selection cap.** If the DSR check (#1) is FAIL, the grade is at most **C**.
3. **Overfitting cap.** If the PBO check (#2) is FAIL, the grade is at most **D**.
4. **Disclosure cap.** If N is undeclared and no variant matrix is supplied, the grade is at most **B**.

## 5. Fixed settings

- Bootstrap seed: fixed per report and printed in it. Reruns give identical numbers.
- CSCV: S = 16 blocks. The oldest remainder rows are dropped so the blocks are equal.
- Base-case costs are stated by the client, or set by the auditor before the run and printed in the report.
- Every report prints this rubric's version, its document SHA-256 and the SHA-256 of its seal record.

## 6. Rule text as printed in every report

These strings are part of the rubric, and reports print them verbatim.

- `dsr`: PASS DSR >= 0.95; CAUTION >= 0.80; else FAIL (on excess returns)
- `pbo`: PASS PBO <= 0.20; CAUTION <= 0.50, or PBO > 0.50 with P(OOS excess SR < 0) <= 0.10; else FAIL
- `haircut`: PASS adjusted p <= 0.05; CAUTION <= 0.10; else FAIL (excess-return t-statistic)
- `spa`: PASS p <= 0.05; CAUTION <= 0.10; else FAIL
- `holdout`: PASS holdout and in-sample excess SR > 0 and holdout >= 50% of in-sample; CAUTION holdout excess SR > 0; else FAIL
- `stability`: PASS >= 60% of years ahead of benchmark and excess SR > 0 in every volatility tercile; CAUTION >= 50%; else FAIL
- `costs`: PASS break-even cost >= 20 bps per unit traded; CAUTION >= 5 bps; else FAIL (absolute)
- `surface`: PASS neighbour SR >= 70% of chosen SR; CAUTION >= 40%; else FAIL, or FAIL if chosen SR <= 0 (absolute)

The caps, in the order they are applied:

- Benchmark cap: if the strategy does not beat its benchmark (SPA check FAIL, or annualised mean excess return <= 0), the grade is at most C.
- Selection cap: if the Deflated Sharpe check FAILS, the grade is at most C.
- Overfitting cap: if the PBO check FAILS, the grade is at most D.
- Disclosure cap: if the number of variants tried was not declared and no variant matrix was supplied, the grade is at most B.

## 7. Version

- Rubric version: **1.0**
- Supersedes: v0 drafts (unsealed; tuned while looking at the sample audits; see the METHODS change log).
- Package implementing it: holdout-audit 0.2.0 (`src/holdout_audit/grade.py`, `src/holdout_audit/audit.py`).
