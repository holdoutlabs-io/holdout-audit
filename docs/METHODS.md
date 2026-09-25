# Methods

Every statistic in a Holdout Labs report is listed here with:
- what it measures;
- how it is computed;
- the assumptions it rests on;
- its limits;
- its source.

All tests are about **past data**: none of them predicts future returns.

**Conventions:**
- Returns are simple fractional returns per period.
- The risk-free rate is taken as zero unless the client subtracts it.
- Sharpe ratios in formulas are *per period* and are annualised by √q, where q is periods per year: 252 for business days, 365 for crypto.
- Kurtosis γ₄ is the raw fourth moment (a normal distribution has 3), and skewness is γ₃.
- The bootstrap seed is fixed, so audits are exactly reproducible.

---

## 1. Sharpe ratio and its standard error

**Computation.** SR = mean / standard deviation (ddof 1), annualised as SR·√q. Two standard errors are reported:
- **IID normal** (Lo 2002, eq. 8): SE = √((1 + SR²/2)/T).
- **IID non-normal** (Mertens 2002): SE = √((1 − γ₃·SR + (γ₄−1)/4·SR²)/(T−1)). This is the one used for the 95% interval, because negative skew and fat tails widen the uncertainty.

Lo's **autocorrelation-adjusted annualisation** η(q) = q/√(q + 2Σ(q−k)ρₖ) is shown alongside. Autocorrelations beyond lag 10 are set to 0 for stability.

**Assumptions.** The returns are stationary. The IID formulas ignore serial correlation, which Lo's η partly corrects.

**Limits.** A Sharpe ratio says nothing about tail events that did not occur in the sample. Zero-return days (flat periods) are included, which lowers the per-day volatility of strategies that are often out of the market.

**Tests.**
- The formula matches Lo's eq. 8.
- The simulated SE of 4,000 IID samples matches the formula to within 6%.
- The non-normal SE reduces to the normal SE when γ₃ = 0 and γ₄ = 3.

*Lo, A. W. (2002). The Statistics of Sharpe Ratios. FAJ 58(4). Mertens, E. (2002). Comments on Variance of the IID Estimator in Lo (2002).*

## 2. Probabilistic Sharpe ratio (PSR) and minimum track record length

**Computation.**
- PSR(SR*) = Φ((SR − SR*)·√(T−1) / √(1 − γ₃SR + (γ₄−1)/4·SR²)), with SR* = 0.
- MinTRL = 1 + (1 − γ₃SR + (γ₄−1)/4·SR²)·(z₀.₉₅/(SR − SR*))² periods, reported in years.

**Assumptions.** The same as for §1. The estimated SR is asymptotically normal.

**Limits.** PSR corrects for sample length and non-normality, but not for selection. That is what DSR does.

*Bailey, D. H. & López de Prado, M. (2012). The Sharpe Ratio Efficient Frontier. Journal of Risk 15(2).*

## 3. Deflated Sharpe ratio (DSR)

**Computation.** DSR = PSR(SR₀), where SR₀ is the expected maximum Sharpe ratio of N skill-less trials:

SR₀ = √V[SRₙ] · ((1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e))), where γ is the Euler–Mascheroni constant.

- **N** is the number of variants tried: the client's declared number, or the number of columns of the variant matrix if that is larger.
- **V[SRₙ]** is the variance of the per-period Sharpe ratios across the supplied variants. Without a variant matrix it is set to 1/T, the sampling variance of a Sharpe estimate when the true SR is 0.

**Worked-example test.** The paper's numerical example (annual SR 2.5, T = 1,250, γ₃ = −3, γ₄ = 10, N = 100, annualised V = 0.5) gives SR₀ = 0.1132 and DSR = 0.9004. `tests/test_sharpe.py` reproduces both to 4 decimal places.

**Assumptions.** Trials are treated as independent draws. Correlated variants make the *effective* N smaller than the nominal N, and they also shrink V[SRₙ].

**Limits.**
- With highly correlated variant families, such as moving-average grids, the estimated V[SRₙ] is small, so SR₀ is small and DSR can be close to 1 even for large N. The report therefore also prints DSR against N from 1 to 1,000.
- If a client under-declares N, DSR is overstated. We cannot detect this.
- DSR tests SR > SR₀ in *absolute* terms. For long-only strategies that includes market beta, which is why the SPA test (§6) is run against buy-and-hold where relevant.

*Bailey, D. H. & López de Prado, M. (2014). The Deflated Sharpe Ratio. JPM 40(5).*

## 4. Probability of backtest overfitting (PBO) via CSCV

**Computation.**
1. The T × N variant matrix is cut into S = 16 contiguous, equal blocks. The oldest remainder rows are dropped.
2. For each of the C(16, 8) = 12,870 choices of 8 in-sample blocks:
   - find the variant with the best in-sample Sharpe;
   - compute its relative rank ω among all N out-of-sample Sharpe ratios;
   - compute the logit λ = ln(ω/(1−ω)).
3. PBO = P(λ ≤ 0).

Also reported:
- **P(OOS loss):** the share of splits where the in-sample winner has a negative out-of-sample Sharpe;
- the median out-of-sample Sharpe of the winner;
- the slope of out-of-sample on in-sample Sharpe, the paper's degradation regression.

**Assumptions.**
- Blocks are long enough to preserve serial dependence.
- The variant matrix represents the search the trader actually did.

**Limits.**
- PBO measures *ranking* persistence within the family, not whether the family makes money.
- Because in-sample and out-of-sample are complementary halves of one sample, pure noise tends to give PBO ≥ 0.5. Our tests show this.
- Near-duplicate variants give PBO near or above 0.5 even when every variant is profitable. The rubric therefore reads PBO together with P(OOS loss) (see §11).

**Tests.**
- One genuinely superior variant gives PBO ≈ 0.
- Pure noise gives PBO in [0.45, 0.85].
- A regime-flipping family gives PBO > 0.5.

*Bailey, D. H., Borwein, J. M., López de Prado, M. & Zhu, Q. J. (2016). The Probability of Backtest Overfitting. Journal of Computational Finance 20(4).*

## 5. Multiple-testing haircut (Harvey & Liu)

**Computation.**
1. t = SR_annual·√years, with a two-sided p-value.
2. Adjusted p-values:
   - **Bonferroni** (p·N) and **Šidák** (1 − (1 − p)^N) use only N;
   - **Holm** (step-down) and **BHY** (Benjamini–Hochberg–Yekutieli step-up, valid under arbitrary dependence) use every variant's p-value, so they need the variant matrix.
3. The adjusted p-value is mapped back to a "haircut" Sharpe ratio.

Grading uses BHY when it is available, otherwise Bonferroni.

**Limits.**
- The t = SR·√years mapping assumes IID returns.
- Harvey & Liu impute unobserved tests by simulation. We do not invent p-values for variants the client did not supply, so without a matrix we report Bonferroni, which is conservative, and Šidák.

**Tests.** Hand-computed values:
- SR 1.0 over 10 years with N = 10 gives Bonferroni p = 0.01565.
- Holm and BHY are checked on a 5-test vector.

*Harvey, C. R. & Liu, Y. (2015). Backtesting. JPM 42(1). Harvey, C. R., Liu, Y. & Zhu, H. (2016). … and the Cross-Section of Expected Returns. RFS 29(1).*

## 6. White's Reality Check and Hansen's SPA test

**Computation.** Define dₖ,ₜ = rₖ,ₜ − benchmarkₜ for every variant k. The benchmark is 0 (cash) or buy-and-hold of the underlying. H₀: maxₖ E[dₖ] ≤ 0.

- **RC:** V = maxₖ √T·d̄ₖ, compared with its bootstrap distribution after recentring at d̄.
- **SPA:** the studentised statistic, with Hansen's consistent recentring (variants with d̄ₖ < −√(ω²ₖ/T·2 ln ln T) are not recentred). The lower and upper p-values are also shown.

Both use the **stationary bootstrap** with 1,000 draws and a mean block length of max(5, T^⅓).

**Assumptions.** The differentials are stationary and weakly dependent.

**Limits.**
- The tests concern *mean* return, not risk-adjusted return. A strategy that sits in cash half the time rarely beats buy-and-hold on mean return even if its Sharpe is higher.
- The block length is a rule of thumb, not the Politis–White optimal choice.

**Tests.**
- A real edge is detected (p < 0.05).
- Under the null, at most 4 of 20 runs reject at 5%.
- A series that tracks its benchmark is not rejected.

*White, H. (2000). A Reality Check for Data Snooping. Econometrica 68(5). Hansen, P. R. (2005). A Test for Superior Predictive Ability. JBES 23(4). Politis, D. N. & Romano, J. P. (1994). The Stationary Bootstrap. JASA 89(428).*

## 7. Holdout degradation

**Computation.** The holdout split date is supplied by the client or defaults to the start of the last 30% of the sample. The report shows the in-sample and holdout Sharpe ratios and their ratio. It also shows a consistency p-value: how surprising the holdout Sharpe is if the in-sample Sharpe were the truth, using the non-normal SE on the holdout's length.

**Limits.** A holdout counts only if it was not used to design or select the rule. We cannot verify this for client-supplied strategies. The sealed forward trial exists to close that gap.

*Bailey, Borwein, López de Prado & Zhu (2014). Pseudo-Mathematics and Financial Charlatanism. Notices of the AMS 61(5).*

## 8. Period and regime stability

**Computation.**
- **Calendar-year** compounded return and Sharpe.
- **Volatility regimes:** terciles of the underlying market's trailing 21-day realised volatility, lagged one day, with the annualised mean and Sharpe in each.

**Limits.**
- The tercile cut points use the full sample, so the split is descriptive, not a tradable signal.
- Terciles hide the tails.
- Partial first and last years are included as they are.

*López de Prado, M. (2018). Advances in Financial Machine Learning. Wiley.*

## 9. Parameter-sensitivity surface

**Computation.**
- Annualised Sharpe for every cell of the grid, parsed from column names such as `fast=50|slow=200`.
- The **neighbour ratio** is the mean Sharpe of the chosen cell's one-step neighbours (cells that differ in exactly one parameter by one level) divided by the chosen cell's Sharpe.
- Also reported: the rank of the chosen cell, the grid median and the share of cells with a positive Sharpe.
- The heatmap shows the two parameters with the most levels, averaged over the others.

**Limits.** The surface only covers the grid that was supplied. Ordering is ambiguous for categorical parameters: they are ordered alphabetically, and "neighbour" is then a convention.

*Pardo, R. (2008). The Evaluation and Optimization of Trading Strategies, 2nd ed. Wiley.*

## 10. Transaction-cost sensitivity and drawdown distribution

**Costs.**
- net = gross − turnover × c, for c from 0 to 50 bps per unit traded, one way.
- The break-even cost is mean(gross)/mean(turnover).
- **Limits:** the cost is flat. Market impact, borrow, funding and slippage that scales with size are not modelled.

**Drawdowns.**
- The maximum drawdown is recomputed on 1,000 stationary-bootstrap resamples.
- The report gives the realised drawdown against the distribution (5th–95th percentiles) and the share of resamples that were worse.
- **Limits:** resampling keeps the return distribution and short-range dependence, but it cannot create crashes larger than those in the sample.

## 10b. Positive controls: can the test pass a real edge?

We planted edges of known size in synthetic data and ran each case through the full audit 200 times under rubric v1.2. The protocol was sealed before the first run. In the preregistered headline cells:
- a real excess Sharpe of 1.0 gets an A or B 98.5% of the time;
- an excess Sharpe of 0.5 gets one 52.5% of the time;
- pure noise passes 2.0% of the time.

Heavy tails and volatility clustering barely move the curve, and selecting the best of 50 zero-edge variants passes 1.0% of the time. Full results and limits: [POSITIVE-CONTROLS.md](POSITIVE-CONTROLS.md).

## 11. The fragility grade (A–F): Rubric v1.1 (v1.0 kept for published reports)

The normative text of the current version is [`RUBRIC-v1.1.md`](RUBRIC-v1.1.md). It keeps v1.0's objective (a) with a one-sided haircut, and adds a declared objective (b), "reduce drawdown at acceptable cost". What follows summarises objective (a). The v1.0 text is [`RUBRIC-v1.0.md`](RUBRIC-v1.0.md). It is frozen and sealed with RFC 3161 timestamps from DigiCert and FreeTSA; the receipts are in [`rubric-seal/`](rubric-seal/). Every report prints three things: the rubric version, the SHA-256 of the rubric document and the SHA-256 of its seal record.

In summary:
- **Benchmark-relative.** The benchmark defaults to buy-and-hold of the traded asset. Checks 1–6 are computed on excess returns over it:
  - Deflated Sharpe;
  - PBO;
  - Harvey–Liu haircut;
  - Hansen SPA;
  - holdout degradation;
  - year and regime stability.
- **Two checks stay absolute:** cost headroom and parameter plateau.
- **Scoring.** Each check scores PASS 2, CAUTION 1 or FAIL 0, or N/A. The letter follows the share of available points: A ≥ 85%, B ≥ 70%, C ≥ 55%, D ≥ 40%, otherwise F.
- **Caps.** Where several apply, the most severe wins:
  - a strategy that does not beat its benchmark is capped at **C**;
  - a failed DSR check caps the grade at **C**;
  - a failed PBO check caps it at **D**;
  - if the number of variants tried is undeclared, the grade is capped at **B**.

The grade measures the fragility of *historical evidence*. It is not a forecast or a recommendation.

### Change log

**v0 drafts (package 0.1.0, 2026-09-25): unsealed and superseded.**
- The v0 rubric was drafted and then **tuned while looking at the three public sample audits**.
- Its first draft failed PBO whenever PBO > 0.50. After the first sample run showed the SPY golden-cross family with PBO 0.70 and 0% out-of-sample losses, a qualifier was added: PBO > 0.50 counts as CAUTION when P(OOS loss) ≤ 0.10.
- v0 was also **absolute**: it scored Sharpe against zero. As a result a golden cross that trailed buy-and-hold received a **B**. Reports produced under v0 (the sample reports committed in `bc38ccf` and `d8b0332`) should not be cited.

**v1.0 (package 0.2.0, 2026-09-25): current, sealed.**
- Rewritten to be benchmark-relative.
- Adds the benchmark cap.
- Keeps the PBO qualifier, now measured on excess returns.
- Makes a non-positive chosen Sharpe fail the plateau check.
- **Sealing order:** the full text was committed and then sealed (DigiCert + FreeTSA) **before** the three samples were re-run under it. The sample reports in `samples/reports/` were produced only after the seal and cite its hash.
- The rule changes in v1.0 were still designed by people who had seen the v0 sample results. The seal proves only that the rubric was fixed before the *v1.0* results, not that it was designed blind.

Future versions follow the same order: write, seal, then apply.

**Sample data source, 2026-09-25 (display change only; no rubric or grading change).**
- Yahoo Finance's public chart endpoint became the official SPY source for the published samples, because Stooq's download was blocked.
- The **PROVISIONAL** label was removed from the three v1.0 sample reports, and a data-provenance note was added: prices from Yahoo Finance's public chart endpoint; we publish derived statistics only, never raw prices; no redistribution.
- The reports were regenerated under v1.0 from the same data file (same SHA-256). Every statistic and every grade is unchanged. Only the timestamp, the package version (0.2.0 to 0.3.0), the config hash and the data-appendix notes differ.

**Known erratum in v1.0 (found 2026-09-25, after sealing; fixed in v1.1).**
- The Harvey–Liu check (#3) uses a *two-sided* p-value on the excess-return t-statistic. Read literally, the sealed rule text would therefore PASS a strategy that trails its benchmark by a statistically significant margin.
- None of the three samples is affected: all three FAIL check #3, with adjusted p of 1.00, 0.23 and 1.00.
- The benchmark cap already limits any such strategy to at most C.
- **Fixed in v1.1:** the haircut now uses a one-sided p-value, counting evidence for the strategy only.
- The package still implements v1.0 exactly as sealed (`rubric_version="1.0"`), so reports published under it can be reproduced.

**v1.1 (package 0.3.0, 2026-09-25): current, sealed; see [`RUBRIC-v1.1.md`](RUBRIC-v1.1.md) and [`rubric-seal-v1.1/`](rubric-seal-v1.1/).**
- **Erratum fix:** the one-sided haircut.
- **New: a declared objective, fixed by the client *before* the audit.** It is written down, dated before the data arrive, hashed into the report and optionally sealed:
  - **(a) beat the benchmark** is the default and is graded as in v1.0;
  - **(b) reduce drawdown at acceptable cost** grades the drawdown and CVaR95 reductions against the benchmark, with paired-bootstrap intervals, plus the client's declared return-cost tolerance.
- **Objective (b) keeps the same overfitting corrections, applied to the tail-loss reduction (dCVaR):**
  - the DSR construction;
  - PBO via CSCV;
  - a one-sided multiple-testing adjustment;
  - holdout;
  - year and regime stability;
  - the plateau check.
- If the drawdown reduction is not robust, or the tolerance is breached, the grade is capped at C.
- **Sealing order:** as with v1.0, the text was committed and then sealed before any audit was run under it.
- **The published samples were deliberately not re-graded under objective (b).** We had already seen that all three cut drawdowns, so choosing (b) for them afterwards would be exactly the post-hoc switch of objective that the declaration rule forbids. They stay v1.0 reports under objective (a).
