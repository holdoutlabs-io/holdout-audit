# Indicator Audit, Batch 3: Strongest published evidence (traditional markets)

**Result: none of the 6 audits meets its source's own claim under the preregistered test (0 of 6 survive).** One claim came closest, and we report it prominently:

- **Faber timing on EEM, VNQ and TLT did cut drawdowns, robustly.** The maximum drawdown fell from 43.9% to 14.5%. The bootstrap 5th percentile of the reduction was 3.5%, the daily tail loss fell by 110 bps, and the Holm-adjusted p is 0.0006. Every check passed except one: it gave up 3.2% a year of return against the 1.0% tolerance we declared in advance, following Faber's 'equity-like returns' claim. The objective cap therefore limits it to **C**, and it does not count as surviving. Half of the claim (drawdowns) held; the other half (returns) did not.
- **Volatility-managed SPY** raised the Sharpe ratio from 0.65 to 0.79. But the improvement was not robust: its 5th percentile is -0.01, the family-adjusted p is 0.71 and the PBO is 0.72. Grade **D**.

Everything else failed its own claim: low-volatility sectors, the minimum-volatility ETF, time-series momentum and risk parity. Two rules compounded faster than their benchmark only through leverage financed at the preregistered 0%. Neither improved the Sharpe ratio: time-series momentum 11.0% vs 7.5%, volatility-managed SPY 12.5% vs 10.9%.

Statistical findings about past data only. Not investment advice, and not a recommendation to use or avoid any rule.

## How it was done

1. **Rubric v1.2** added objective (c), "improve Sharpe vs benchmark", for sources whose claim is risk-adjusted. It was sealed at 20:33:45Z, before any Batch 3 data were fetched. Objectives (a) and (b) are unchanged.
2. **Preregistration and six objective declarations** were sealed with DigiCert and FreeTSA at 20:39:31–55Z on 2026-09-25. Each audit is judged on the objective its own source claims. The documents also fix the exact list of instruments whose prices we had already seen, and the list of those we had not. See [`prereg/`](prereg/).
   - Preregistration SHA-256 `2142d17c29db1f2b0080e225cfbcd15ba67582b4122adcc6c78b0aad1325d690`; seal record `90ff232e75d552219386a15d1bc0990a86b40a925d2a7dc1405e7be67995e009`.
3. **New data fetched after the seal:** EEM, TLT, VNQ, USMV and SPLV. SPY, EFA, IEF and the sector SPDRs are reused files whose prices we had already seen, which is disclosed in each report.
4. **Run once each** under rubric v1.2.
5. **Batch test.** Each audit contributes its primary-objective p-value (dSR for (c), dCVaR for (b); adjusted within its variant family). Holm's correction is applied across the six. "Survives" requires a Holm p of 0.05 or less *and* a primary objective check that is not FAIL.

## Summary table

| Rule (source) | Market | Objective | Variants | Grade | Primary result | Deflated | PBO | Holm p | Survives |
|---|---|---|---|---|---|---|---|---|---|
| [Volatility-managed equity (Moreira & Muir)](reports/volman-spy.html) | SPY | (c) improve Sharpe | 12 | **D** | Sharpe 0.79 vs 0.65 (dSR +0.14, 5th pct -0.01); holdout dSR +0.17 → +0.07 | 0.815 | 0.72 | 1.0000 | no |
| [Low-volatility sectors (low-volatility anomaly)](reports/lowvol-sectors.html) | 9 sector SPDRs | (c) improve Sharpe | 9 | **F** | Sharpe 0.62 vs 0.51 (dSR +0.12, 5th pct -0.06); holdout dSR +0.20 → -0.08 | 0.544 | 0.33 | 1.0000 | no |
| [Minimum-volatility ETFs (USMV, SPLV)](reports/lowvol-etf.html) | USMV / SPLV | (c) improve Sharpe | 2 | **F** | Sharpe 0.88 vs 0.92 (dSR -0.04, 5th pct -0.25); holdout dSR +0.02 → -0.23 | 0.215 | 0.04 | 1.0000 | no |
| [Time-series momentum (Moskowitz, Ooi & Pedersen)](reports/tsmom-5.html) | SPY, EFA, EEM, IEF, TLT | (c) improve Sharpe | 8 | **F** | Sharpe 0.53 vs 0.65 (dSR -0.13, 5th pct -0.52); holdout dSR -0.02 → -0.28 | 0.045 | 0.30 | 1.0000 | no |
| [Faber GTAA timing on unseen markets (EEM, VNQ, TLT)](reports/gtaa-eem-vnq-tlt.html) | EEM, VNQ, TLT | (b) reduce drawdown | 8 | **C** | max drawdown 14.5% vs 43.9% (5th pct of the cut 3.5%); return cost 3.2%/yr vs declared tolerance 1.0% | 1.000 | 0.53 | 0.0006 | no |
| [Risk parity stocks/bonds (Asness, Frazzini & Pedersen)](reports/risk-parity-spy-tlt.html) | SPY / TLT | (c) improve Sharpe | 8 | **D** | Sharpe 0.79 vs 0.79 (dSR +0.00, 5th pct -0.17); holdout dSR +0.17 → -0.16 | 0.166 | 0.13 | 1.0000 | no |

Survive: **0 of 6**.

## Sources

- **Volatility-managed equity (Moreira & Muir)**: Moreira, A. & Muir, T. (2017). Volatility-Managed Portfolios. Journal of Finance 72(4), 1611-1644.
- **Low-volatility sectors (low-volatility anomaly)**: Blitz, D. & van Vliet, P. (2007). The Volatility Effect. Journal of Portfolio Management 34(1), 102-113; Baker, M., Bradley, B. & Wurgler, J. (2011). Benchmarks as Limits to Arbitrage. Financial Analysts Journal 67(1), 40-54.
- **Minimum-volatility ETFs (USMV, SPLV)**: The low-volatility anomaly as packaged in index products: MSCI USA Minimum Volatility (USMV) and S&P 500 Low Volatility (SPLV); academic basis as for lowvol_sectors.
- **Time-series momentum (Moskowitz, Ooi & Pedersen)**: Moskowitz, T. J., Ooi, Y. H. & Pedersen, L. H. (2012). Time Series Momentum. Journal of Financial Economics 104(2), 228-250.
- **Faber GTAA timing on unseen markets (EEM, VNQ, TLT)**: Faber, M. T. (2007). A Quantitative Approach to Tactical Asset Allocation. Journal of Wealth Management 9(4), 69-79.
- **Risk parity stocks/bonds (Asness, Frazzini & Pedersen)**: Asness, C. S., Frazzini, A. & Pedersen, L. H. (2012). Leverage Aversion and Risk Parity. Financial Analysts Journal 68(1), 47-59.

## Deviations and disclosures

- **No deviations** from the preregistered rules, grids, markets, costs, periods, holdouts, objectives or tolerance.
- *Prior exposure.* We had already seen SPY, QQQ, IWM, EFA, IEF, AGG, ^VIX, the sector SPDRs and BTC. We had not seen EEM, TLT, VNQ, USMV or SPLV. The volatility-managed and low-volatility-sector audits therefore run on prices we had seen, with no new data, and the engine's declaration-date check is not applied to them (stated in their reports). No earlier audit is re-graded.
- *Financing.* Cash earns 0% and borrowing costs 0%. That flatters the levered variants (volatility-managed caps above 1.0; time-series momentum's volatility-scaled bond positions) and penalises the de-risked ones.
- *Scope.* The paper's commodities and currencies are excluded from time-series momentum (the samples' instrument policy), and the low-volatility rule is a sector-level adaptation of a stock-level anomaly. Both points are stated in the preregistration.

Data: prices from Yahoo Finance's public chart endpoint; we publish derived statistics only, never raw prices; no redistribution.
