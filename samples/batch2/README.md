# Indicator Audit, Batch 2: Classic market rules (traditional markets)

**Result: none of the 14 audits survives.** We tested ten published or traditional market rules on the equity and bond markets their sources used. None of them beat its benchmark with statistical support: every Hansen SPA p-value is at least 0.68, and 0 of 14 survive Holm's correction. All 14 grade **F** under rubric v1.1, objective (a) "beat the benchmark".

Two audited defaults came out slightly *ahead* of their benchmark, but far from significant, and both failed the selection-adjusted significance and holdout checks: Sector momentum rotation (12-1 month) on 9 sector SPDRs (excess Sharpe +0.07, SPA p 0.70); Golden cross (50/200-day) on QQQ (excess Sharpe +0.03, SPA p 0.68). The golden cross on QQQ compounded faster than holding QQQ (12.0% vs 9.4% a year), but its whole advantage came from sitting out the 2000–02 crash (+4.4% a year against −37.9%). From 2003 onward it trailed holding QQQ (12.9% vs 16.3% a year).

Statistical findings about past data only. Not investment advice, and not a recommendation to use or avoid any rule. A grade describes how fragile the historical evidence is; it does not predict the future.

## How it was done

1. **Preregistered and sealed first.** Before any Batch 2 data were fetched, one preregistration fixed the following for all 14 audits. It was sealed with RFC 3161 timestamps from DigiCert (20:11:44Z) and FreeTSA (20:11:45Z) on 2026-09-25: [`prereg/batch2-preregistration.json`](prereg/batch2-preregistration.json).
   - each rule as published, with its source and default;
   - a variant grid (132 variants in all);
   - markets, costs, periods and the holdout (from 2018-01-02);
   - the benchmark and objective;
   - Holm across 14 and the commitment to publish all results.
   - Document SHA-256 `ff8cace63cad05977286a8a9a33dbbc88071c2f12a1d4a0d78f87f8d33f98250`; seal record `35f52f363e7cb128df873803d8e10268977adb2cf06204cb6dfd1b2e57f18b11`.
2. **Run once each** under rubric v1.1 (`run_batch2.py`). The data were fetched after the seal.
3. **Batch test.** Each audit's Hansen SPA p-value (the best variant of its family against the benchmark) is corrected with Holm's method across the 14. "Survives" means an adjusted p of 0.05 or less.

## Summary table

| Rule (source) | Market | Variants | Grade | Compound return a year vs benchmark | Excess Sharpe | DSR | PBO | Holdout excess Sharpe (in → out) | SPA p | Holm p | Survives |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [Faber 10-month SMA timing](reports/faber-spy.html) | SPY | 4 | **F** | 9.5% vs 10.9% | -0.16 | 0.127 | 0.64 | -0.02 → -0.54 | 1.000 | 1.000 | no |
| [Faber 10-month SMA timing](reports/faber-efa.html) | EFA | 4 | **F** | 7.7% vs 7.6% | -0.07 | 0.299 | 0.65 | -0.04 → -0.17 | 1.000 | 1.000 | no |
| [Faber 10-month SMA timing](reports/faber-ief.html) | IEF | 4 | **F** | 1.0% vs 3.3% | -0.49 | 0.003 | 0.20 | -0.89 → +0.02 | 1.000 | 1.000 | no |
| [200-day moving-average filter](reports/sma200-spy.html) | SPY | 8 | **F** | 8.7% vs 10.8% | -0.20 | 0.035 | 0.14 | -0.15 → -0.36 | 1.000 | 1.000 | no |
| [Halloween indicator / Sell in May](reports/halloween-spy.html) | SPY | 6 | **F** | 6.9% vs 10.9% | -0.35 | 0.002 | 0.13 | -0.23 → -0.76 | 1.000 | 1.000 | no |
| [Halloween indicator / Sell in May](reports/halloween-efa.html) | EFA | 6 | **F** | 6.5% vs 6.6% | -0.08 | 0.147 | 0.56 | -0.07 → -0.14 | 1.000 | 1.000 | no |
| [Turn-of-the-month effect](reports/tom-spy.html) | SPY | 6 | **F** | 3.2% vs 10.9% | -0.51 | 0.001 | 0.33 | -0.44 → -0.70 | 1.000 | 1.000 | no |
| [Antonacci dual momentum (Global Equities Momentum)](reports/dualmom-spy-efa-agg.html) | SPY/EFA/AGG | 6 | **F** | 9.7% vs 11.2% | -0.15 | 0.159 | 0.53 | +0.02 → -0.59 | 1.000 | 1.000 | no |
| [Sector momentum rotation (12-1 month)](reports/sectors-12-1.html) | 9 sector SPDRs | 12 | **F** | 9.3% vs 8.5% | +0.07 | 0.491 | 0.99 | +0.16 → -0.12 | 0.696 | 1.000 | no |
| [VIX stretches (Connors & Alvarez)](reports/vix-stretch-spy.html) | SPY (VIX signal) | 18 | **F** | 2.5% vs 10.9% | -0.54 | 0.000 | 0.00 | -0.40 → -0.98 | 1.000 | 1.000 | no |
| [Golden cross (50/200-day)](reports/golden-cross-qqq.html) | QQQ | 24 | **F** | 12.0% vs 9.4% | +0.03 | 0.287 | 0.50 | +0.08 → -0.18 | 0.680 | 1.000 | no |
| [60/40 rebalancing bands](reports/sixty-forty-bands.html) | SPY/IEF 60/40 | 10 | **F** | 8.6% vs 9.5% | -0.38 | 0.015 | 0.64 | +0.12 → -0.72 | 1.000 | 1.000 | no |
| [Connors RSI(2) with exit variants](reports/rsi2-qqq.html) | QQQ | 12 | **F** | 2.8% vs 8.9% | -0.35 | 0.011 | 0.01 | -0.17 → -0.79 | 1.000 | 1.000 | no |
| [Connors RSI(2) with exit variants](reports/rsi2-iwm.html) | IWM | 12 | **F** | 2.2% vs 8.9% | -0.39 | 0.012 | 0.87 | -0.40 → -0.37 | 1.000 | 1.000 | no |

Survive Holm: **0 of 14**.

## Sources

- **Faber 10-month SMA timing**: Faber, M. T. (2007). A Quantitative Approach to Tactical Asset Allocation. Journal of Wealth Management 9(4), 69-79 (SSRN 962461).
- **200-day moving-average filter**: Siegel, J. J. (2002). Stocks for the Long Run, 3rd ed., McGraw-Hill, ch. 17 (the 200-day moving average with a 1% band on the Dow and S&P 500).
- **Halloween indicator / Sell in May**: Bouman, S. & Jacobsen, B. (2002). The Halloween Indicator, 'Sell in May and Go Away': Another Puzzle. American Economic Review 92(5), 1618-1635.
- **Turn-of-the-month effect**: Lakonishok, J. & Smidt, S. (1988). Are Seasonal Anomalies Real? Review of Financial Studies 1(4), 403-425; McConnell, J. J. & Xu, W. (2008). Equity Returns at the Turn of the Month. Financial Analysts Journal 64(2), 49-64.
- **Antonacci dual momentum (Global Equities Momentum)**: Antonacci, G. (2014). Dual Momentum Investing. McGraw-Hill; Antonacci, G. (2012). Risk Premia Harvesting Through Dual Momentum (SSRN 2042750).
- **Sector momentum rotation (12-1 month)**: Moskowitz, T. J. & Grinblatt, M. (1999). Do Industries Explain Momentum? Journal of Finance 54(4), 1249-1290; Faber, M. T. (2010). Relative Strength Strategies for Investing (SSRN 1585517).
- **VIX stretches (Connors & Alvarez)**: Connors, L. & Alvarez, C. (2009). Short Term Trading Strategies That Work. TradingMarkets, chapter 'VIX Stretches'.
- **Golden cross (50/200-day)**: Traditional trend-following rule; see, e.g., Brock, W., Lakonishok, J. & LeBaron, B. (1992). Simple Technical Trading Rules and the Stochastic Properties of Stock Returns. Journal of Finance 47(5), 1731-1764 (moving-average rules including 50 and 200 days).
- **60/40 rebalancing bands**: Jaconetti, C. M., Kinniry, F. M. & Zilbering, Y. (2010). Best Practices for Portfolio Rebalancing. Vanguard Research.
- **Connors RSI(2) with exit variants**: Connors, L. & Alvarez, C. (2009). Short Term Trading Strategies That Work. TradingMarkets, chapter 'The 2-period RSI'.

## Deviations and disclosures

- **No deviations** from the preregistered rules, grids, markets, costs, periods, holdout or objective.
- *Cash earns 0%.* No T-bill series was used, because a Treasury-bill rate index is not a permitted instrument. This works against every timing rule by roughly the T-bill rate times the time spent in cash. Antonacci's absolute-momentum hurdle is therefore 0% instead of the T-bill return. Both points were preregistered.
- *Benchmarks.* Single-asset rules are compared with buy-and-hold of the same ETF. Dual momentum, sector rotation and the VIX rule are compared with buy-and-hold SPY. The 60/40 banding rule is compared with the same 60/40 bought at the start and never rebalanced.
- *Data* come from Yahoo Finance's public chart endpoint, fetched after the seal. Signals use the split-adjusted close and total returns use the adjusted close. As a check, SPY total return matched our earlier close-plus-dividend series (10.89% a year either way).
- *Prior exposure:* SPY and BTC results from sample audits 1–4, Batch 1 and the on-chain batch had been seen before this batch; see the preregistration.

Data: prices from Yahoo Finance's public chart endpoint; we publish derived statistics only, never raw prices; no redistribution.
