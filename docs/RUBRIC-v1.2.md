# Holdout Labs Fragility Rubric, version 1.2

Status: **frozen**. This document is sealed with RFC 3161 timestamps (DigiCert and FreeTSA); the receipts are in `docs/rubric-seal-v1.2/`. Any change requires a new version number, a new seal and an entry in the change log of `docs/METHODS.md`, all *before* the new version is applied to any audit.

The grade describes how fragile the historical evidence for a strategy's **declared objective** is. It is not a forecast and not a recommendation.

## 0. What changed from v1.1

1. **New objective (c), "improve Sharpe vs benchmark".** It is for sources whose claim is a better risk-adjusted return rather than a higher return. It has the same overfitting corrections and caps as the other objectives (§3, §5).
2. **Objectives (a) and (b) are unchanged.** Their checks, thresholds, rule text and caps are copied verbatim from v1.1.
3. Reports published under v1.0 and v1.1 keep their versions. They are not re-graded.

## 1. The declared objective (pre-commitment)

Choosing the objective after seeing results is the forking path these audits exist to catch. Objectives (b) and (c) are therefore graded only when a **written declaration** exists. It must contain:

- `objective`: `reduce_drawdown` or `improve_sharpe`. The value `beat_benchmark` is also allowed and is the default when nothing is declared;
- `max_return_shortfall_annual`: the most annual return, relative to the benchmark, the client accepts giving up. It is a decimal fraction: 0.02 means "I accept up to 2% a year less return than the benchmark". It is required for (b);
- `benchmark`: the benchmark named in writing. By default this is buy-and-hold of the traded asset;
- `declared_at_utc`: when the declaration was made;
- `declared_by`: an opaque client reference.

The declaration must be dated **before the audit data were delivered**. Its canonical-JSON SHA-256 is printed in the report. The client may also seal it (`holdout-audit seal-doc`); if they do, the report prints the authorities' signed times as well. Without a declaration, objective (a) applies.

Rule text: Declaration rule: objectives (b) and (c) are graded only with a written declaration of the objective (and, for (b), the return-cost tolerance), dated before the audit data were delivered and hashed into the report; without one the audit uses objective (a).

## 2. Common definitions

- **r_t**: the audited strategy's return in period t, net of the base-case cost.
- **b_t**: the benchmark's return. By default this is the buy-and-hold total return of the traded asset; a cash (zero) benchmark is used only as in v1.0 §1.
- **e_t = r_t − b_t**: the excess return.
- **N**: the larger of the declared number of variants tried and the number of variant-matrix columns. It is 1 if neither is given.
- Stationary bootstrap: 1,000 draws, mean block length max(5, T^⅓), fixed seed. Under objectives (b) and (c) the resampling is *paired*: strategy and benchmark are resampled on the same days.
- **CVaR95(x)**: the average loss on the worst ⌈0.05·T⌉ periods, as a positive number.
- **dCVaR = CVaR95(b) − CVaR95(r)**: the tail-loss reduction. Positive values favour the strategy.
- **MDD(x)**: the maximum peak-to-trough decline of the compounded series.
- **dMDD = MDD(b) − MDD(r)**: the drawdown reduction. Positive values favour the strategy.
- **Return shortfall = (mean(b) − mean(r)) × periods per year**: arithmetic and annualised.
- **dSR = SR(r) − SR(b)**: the Sharpe-ratio improvement, per period (reported annualised by √q). Positive values favour the strategy.
- **Selection dispersion V**: the sample variance (ddof 1), across variant-matrix columns, of the objective statistic. That is the per-period excess Sharpe under (a), dCVaR under (b) and per-period dSR under (c). Without a matrix it is the statistic's sampling variance: 1/T under (a), and the squared bootstrap standard error of dCVaR under (b) or of dSR under (c).

## 3. The checks

Each check scores PASS = 2, CAUTION = 1 or FAIL = 0 points, or N/A, in which case it is excluded.

### Objective (a): beat the benchmark (eight checks)

These are identical to v1.0 §2 (DSR, PBO, Harvey–Liu, SPA, holdout, stability, costs, plateau), except for the haircut. **Haircut:**
- t = annualised excess Sharpe × √years;
- the **one-sided** p-value is P(Z ≥ t);
- adjustment is BHY when every variant is supplied, otherwise Bonferroni;
- PASS adjusted p ≤ 0.05; CAUTION ≤ 0.10; else FAIL.

### Objective (b): reduce drawdown at acceptable cost (nine checks)

| # | Key | Check | PASS | CAUTION | FAIL |
|---|---|---|---|---|---|
| 1 | dsr | Deflated dCVaR: the DSR construction of Bailey & López de Prado (2014) applied to dCVaR. D = Φ((dCVaR − θ₀)/SE), where θ₀ = √V·((1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(Ne))) and SE is the paired-bootstrap standard error of dCVaR | D ≥ 0.95 | 0.80 ≤ D < 0.95 | D < 0.80 |
| 2 | pbo | PBO via CSCV (16 blocks, all 12,870 splits), with variants ranked by dCVaR in each half | PBO ≤ 0.20 | ≤ 0.50, or > 0.50 with P(OOS dCVaR of the IS winner < 0) ≤ 0.10 | otherwise. N/A without a matrix |
| 3 | haircut | Multiple testing: one-sided p = P(Z ≥ dCVaR/SE) per variant (paired bootstrap on the same resampled days); BHY if every variant is supplied, else Bonferroni over N | adj. p ≤ 0.05 | ≤ 0.10 | > 0.10 |
| 4 | drawdown | **Primary: drawdown reduction.** Paired bootstrap of dMDD and dCVaR | 5th percentile of dMDD > 0 **and** 5th percentile of dCVaR > 0 | both point estimates > 0 | otherwise |
| 5 | tolerance | **Primary: return cost within the declared tolerance** | 95th-percentile bootstrap shortfall ≤ tolerance | point shortfall ≤ tolerance | point shortfall > tolerance |
| 6 | holdout | dCVaR before and after the holdout split (client-supplied date, else the start of the last 30%), plus dMDD in the holdout | holdout and in-sample dCVaR > 0, holdout ≥ 50% of in-sample, **and** holdout dMDD > 0 | holdout dCVaR > 0 | holdout dCVaR ≤ 0 |
| 7 | stability | Calendar years in which the strategy's within-year MDD is below the benchmark's; dCVaR within terciles of the benchmark's trailing 21-day volatility, lagged 1 period | ≥ 60% of years shallower **and** dCVaR > 0 in every tercile | ≥ 50% of years shallower | < 50% |
| 8 | costs | Transaction-cost headroom (absolute, as in v1.0) | ≥ 20 bps | ≥ 5 bps | < 5 bps. N/A without turnover |
| 9 | surface | Parameter plateau on dCVaR: the mean dCVaR of one-step neighbours ÷ the chosen variant's dCVaR | ≥ 0.70 | ≥ 0.40 | < 0.40, or chosen dCVaR ≤ 0. N/A without a grid |

### Objective (c): improve Sharpe vs benchmark (eight checks)

For sources whose claim is a better risk-adjusted return rather than a higher return (for example volatility-managed portfolios or low-volatility portfolios).

| # | Key | Check | PASS | CAUTION | FAIL |
|---|---|---|---|---|---|
| 1 | dsr | Deflated dSR: the DSR construction of Bailey & López de Prado (2014) applied to dSR. D = Φ((dSR − θ₀)/SE), where θ₀ = √V·((1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(Ne))) and SE is the paired-bootstrap standard error of dSR | D ≥ 0.95 | 0.80 ≤ D < 0.95 | D < 0.80 |
| 2 | pbo | PBO via CSCV (16 blocks, all 12,870 splits), with variants ranked by dSR (each variant's Sharpe minus the benchmark's Sharpe on the same half) | PBO ≤ 0.20 | ≤ 0.50, or > 0.50 with P(OOS dSR of the IS winner < 0) ≤ 0.10 | otherwise. N/A without a matrix |
| 3 | haircut | Multiple testing: one-sided p = P(Z ≥ dSR/SE) per variant (paired bootstrap on the same resampled days); BHY if every variant is supplied, else Bonferroni over N | adj. p ≤ 0.05 | ≤ 0.10 | > 0.10 |
| 4 | sharpe | **Primary: Sharpe-ratio improvement.** Paired stationary bootstrap of dSR (Ledoit & Wolf 2008) | 5th percentile of dSR > 0 | point dSR > 0 | otherwise |
| 5 | holdout | dSR before and after the holdout split | holdout and in-sample dSR > 0, **and** holdout ≥ 50% of in-sample | holdout dSR > 0 | holdout dSR ≤ 0 |
| 6 | stability | Calendar years in which the strategy's Sharpe exceeds the benchmark's; dSR within terciles of the benchmark's trailing 21-day volatility, lagged 1 period | ≥ 60% of years higher **and** dSR > 0 in every tercile | ≥ 50% of years higher | < 50% |
| 7 | costs | Transaction-cost headroom (absolute, as in v1.0) | ≥ 20 bps | ≥ 5 bps | < 5 bps. N/A without turnover |
| 8 | surface | Parameter plateau on dSR: the mean dSR of one-step neighbours ÷ the chosen variant's dSR | ≥ 0.70 | ≥ 0.40 | < 0.40, or chosen dSR ≤ 0. N/A without a grid |

## 4. From points to a letter

These are unchanged from v1.0: A ≥ 0.85, B ≥ 0.70, C ≥ 0.55, D ≥ 0.40, otherwise F. The score is the share of available points.

## 5. Hard caps (applied after the bands; the most severe cap wins)

1. **Objective cap.** Under (a), if the strategy does not beat its benchmark, the grade is at most **C**. Under (b), if the drawdown reduction is not robust (check 4 FAIL) or the declared tolerance is breached (check 5 FAIL), the grade is at most **C**. Under (c), if the Sharpe-ratio improvement is not robust (check 4 FAIL), the grade is at most **C**.
2. **Selection cap.** If check 1 FAILs, the grade is at most **C**.
3. **Overfitting cap.** If the PBO check FAILs, the grade is at most **D**.
4. **Disclosure cap.** If N is undeclared and no variant matrix is supplied, the grade is at most **B**.

## 6. Rule text as printed in every report

These strings are part of the rubric, and reports print them verbatim.

Objective (a), beat the benchmark (unchanged from v1.1):

- `dsr`: PASS DSR >= 0.95; CAUTION >= 0.80; else FAIL (on excess returns)
- `pbo`: PASS PBO <= 0.20; CAUTION <= 0.50, or PBO > 0.50 with P(OOS excess SR < 0) <= 0.10; else FAIL
- `haircut`: PASS one-sided adjusted p <= 0.05; CAUTION <= 0.10; else FAIL (excess-return t-statistic; evidence for the strategy only)
- `spa`: PASS p <= 0.05; CAUTION <= 0.10; else FAIL
- `holdout`: PASS holdout and in-sample excess SR > 0 and holdout >= 50% of in-sample; CAUTION holdout excess SR > 0; else FAIL
- `stability`: PASS >= 60% of years ahead of benchmark and excess SR > 0 in every volatility tercile; CAUTION >= 50%; else FAIL
- `costs`: PASS break-even cost >= 20 bps per unit traded; CAUTION >= 5 bps; else FAIL (absolute)
- `surface`: PASS neighbour SR >= 70% of chosen SR; CAUTION >= 40%; else FAIL, or FAIL if chosen SR <= 0 (absolute)

Objective (b), reduce drawdown at acceptable cost (unchanged from v1.1):

- `dsr`: PASS deflated dCVaR >= 0.95; CAUTION >= 0.80; else FAIL (DSR construction on the CVaR reduction)
- `pbo`: PASS PBO <= 0.20; CAUTION <= 0.50, or PBO > 0.50 with P(OOS dCVaR < 0) <= 0.10; else FAIL (variants ranked by dCVaR)
- `haircut`: PASS one-sided adjusted p <= 0.05; CAUTION <= 0.10; else FAIL (bootstrap z of dCVaR)
- `drawdown`: PASS 5th-percentile bootstrap dMDD > 0 and dCVaR > 0; CAUTION both point estimates > 0; else FAIL
- `tolerance`: PASS 95th-percentile bootstrap return shortfall <= declared tolerance; CAUTION point shortfall <= tolerance; else FAIL
- `holdout`: PASS holdout and in-sample dCVaR > 0, holdout >= 50% of in-sample, and holdout dMDD > 0; CAUTION holdout dCVaR > 0; else FAIL
- `stability`: PASS >= 60% of years with a shallower drawdown than the benchmark and dCVaR > 0 in every volatility tercile; CAUTION >= 50%; else FAIL
- `costs`: PASS break-even cost >= 20 bps per unit traded; CAUTION >= 5 bps; else FAIL (absolute)
- `surface`: PASS neighbour dCVaR >= 70% of chosen dCVaR; CAUTION >= 40%; else FAIL, or FAIL if chosen dCVaR <= 0

Objective (c), improve Sharpe vs benchmark (new in v1.2):

- `dsr`: PASS deflated dSR >= 0.95; CAUTION >= 0.80; else FAIL (DSR construction on the Sharpe-ratio improvement)
- `pbo`: PASS PBO <= 0.20; CAUTION <= 0.50, or PBO > 0.50 with P(OOS dSR < 0) <= 0.10; else FAIL (variants ranked by dSR)
- `haircut`: PASS one-sided adjusted p <= 0.05; CAUTION <= 0.10; else FAIL (bootstrap z of dSR)
- `sharpe`: PASS 5th-percentile bootstrap dSR > 0; CAUTION point dSR > 0; else FAIL
- `holdout`: PASS holdout and in-sample dSR > 0 and holdout >= 50% of in-sample; CAUTION holdout dSR > 0; else FAIL
- `stability`: PASS >= 60% of years with a higher Sharpe than the benchmark and dSR > 0 in every volatility tercile; CAUTION >= 50%; else FAIL
- `costs`: PASS break-even cost >= 20 bps per unit traded; CAUTION >= 5 bps; else FAIL (absolute)
- `surface`: PASS neighbour dSR >= 70% of chosen dSR; CAUTION >= 40%; else FAIL, or FAIL if chosen dSR <= 0

The caps, in the order they are applied:

- Objective cap (beat the benchmark): if the strategy does not beat its benchmark (SPA check FAIL, or annualised mean excess return <= 0), the grade is at most C.
- Objective cap (reduce drawdown): if the drawdown reduction is not robust (drawdown check FAIL) or the declared return-cost tolerance is breached (tolerance check FAIL), the grade is at most C.
- Objective cap (improve Sharpe): if the Sharpe-ratio improvement is not robust (Sharpe check FAIL), the grade is at most C.
- Selection cap: if the deflated check FAILS, the grade is at most C.
- Overfitting cap: if the PBO check FAILS, the grade is at most D.
- Disclosure cap: if the number of variants tried was not declared and no variant matrix was supplied, the grade is at most B.

The declaration rule:

- Declaration rule: objectives (b) and (c) are graded only with a written declaration of the objective (and, for (b), the return-cost tolerance), dated before the audit data were delivered and hashed into the report; without one the audit uses objective (a).

## 7. Version

- Rubric version: **1.2**
- Supersedes v1.1 for new audits. Reports published under v1.0 and v1.1 keep their versions.
- Package implementing it: holdout-audit 0.4.0 (`src/holdout_audit/grade.py`, `src/holdout_audit/audit.py`, `src/holdout_audit/stats/objective_sharpe.py`).
- Additional reference for (c): Ledoit, O. & Wolf, M. (2008). Robust performance hypothesis testing with the Sharpe ratio. *Journal of Empirical Finance* 15(5), 850–859.
