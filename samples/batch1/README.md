# Indicator Audit, Batch 1: ten TradingView built-in strategies on SPY and BTC

**Result: none of the 20 audits survives.** Not one of the ten TradingView built-in strategies, run with its default settings as it ships (long and short), beat simply holding the same asset. That holds on SPY (1994–2026) and on BTC (2015–2026). Across all ten preregistered variant families (250 variants), no variant had a positive mean return over buy-and-hold after costs. Every Hansen SPA p-value is 1.000, so nothing survives Holm's correction across the 20 audits (0 of 20). All 20 grade **F** under rubric v1.1, objective (a) "beat buy-and-hold of the same asset".

Statistical findings about past data only. Not investment advice, and not a recommendation to use or avoid any indicator. A grade describes how fragile the historical evidence is; it does not predict the future.

## How it was done

1. **Preregistered and sealed first.** Before any SPY OHLC data were fetched and before any of these strategies was run on market data, one batch preregistration fixed the following for every audit. It was sealed with RFC 3161 timestamps from DigiCert (18:21:44Z) and FreeTSA (18:21:45Z) on 2026-09-25: [`prereg/batch1-preregistration.json`](prereg/batch1-preregistration.json).
   - the rule and its defaults;
   - the variant grid;
   - costs, data, dates and the holdout split;
   - the objective;
   - the Holm rule and the commitment to publish all 20.
   - Document SHA-256 `35b4d77e284614c15fafdacaf91e122b600e520c1ea61e33627a64c3497c765d`; seal record `9f25abc24d54753071fc54da00bda52705ea2e7c0b6d2ba3011d7c009fa22d5c`. Every report cites the seal.
2. **Run once each** under rubric v1.1 (`run_batch1.py`). BTC Supertrend is carried over unchanged from sample audit 4 (same sealed grid, data, dates and costs), as the preregistration says.
3. **Batch-level test.** Each audit contributes its Hansen SPA p-value: the best variant of its preregistered family against buy-and-hold, by stationary bootstrap. Holm's step-down correction across the 20 decides "survives" at family-wise α = 0.05.

## Summary table

| Asset | TradingView strategy (default, long/short) | Variants | Grade | Compound return a year vs buy-and-hold | Excess Sharpe | DSR | PBO | Holdout excess Sharpe (in → out) | SPA p | Holm p | Survives |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SPY | [Supertrend](reports/spy-supertrend.html) | 30 | **F** | -3.7% vs 10.9% | -0.46 | 0.000 | 0.77 | -0.38 → -0.66 | 1.000 | 1.000 | no |
| SPY | [MACD](reports/spy-macd.html) | 48 | **F** | -4.1% vs 10.9% | -0.48 | 0.000 | 0.32 | -0.45 → -0.55 | 1.000 | 1.000 | no |
| SPY | [RSI](reports/spy-rsi.html) | 24 | **F** | -2.8% vs 10.9% | -0.59 | 0.000 | 0.37 | -0.50 → -0.82 | 1.000 | 1.000 | no |
| SPY | [Bollinger Bands](reports/spy-bollinger.html) | 32 | **F** | 2.5% vs 10.9% | -0.40 | 0.000 | 0.43 | -0.32 → -0.60 | 1.000 | 1.000 | no |
| SPY | [MovingAvg2Line Cross](reports/spy-ma-cross.html) | 40 | **F** | -0.6% vs 10.9% | -0.37 | 0.000 | 0.20 | -0.37 → -0.38 | 1.000 | 1.000 | no |
| SPY | [Parabolic SAR](reports/spy-psar.html) | 18 | **F** | -6.9% vs 10.9% | -0.61 | 0.000 | 0.29 | -0.69 → -0.41 | 1.000 | 1.000 | no |
| SPY | [Stochastic Slow](reports/spy-stochastic.html) | 16 | **F** | -5.1% vs 10.9% | -0.59 | 0.000 | 0.67 | -0.48 → -0.92 | 1.000 | 1.000 | no |
| SPY | [Channel BreakOut](reports/spy-channel-breakout.html) | 8 | **F** | -8.5% vs 10.9% | -0.65 | 0.000 | 0.14 | -0.67 → -0.59 | 1.000 | 1.000 | no |
| SPY | [Keltner Channels](reports/spy-keltner.html) | 24 | **F** | -2.6% vs 10.9% | -0.41 | 0.000 | 0.54 | -0.38 → -0.49 | 1.000 | 1.000 | no |
| SPY | [Momentum](reports/spy-momentum.html) | 10 | **F** | -1.1% vs 10.9% | -0.38 | 0.000 | 0.66 | -0.42 → -0.27 | 1.000 | 1.000 | no |
| BTC | [Supertrend](reports/btc-supertrend.html) | 30 | **F** | 2.4% vs 70.4% | -0.52 | 0.006 | 0.32 | -0.47 → -0.76 | 1.000 | 1.000 | no |
| BTC | [MACD](reports/btc-macd.html) | 48 | **F** | 28.7% vs 70.4% | -0.29 | 0.072 | 0.50 | -0.19 → -0.68 | 1.000 | 1.000 | no |
| BTC | [RSI](reports/btc-rsi.html) | 24 | **F** | -37.9% vs 70.4% | -0.95 | 0.000 | 0.77 | -0.98 → -0.95 | 1.000 | 1.000 | no |
| BTC | [Bollinger Bands](reports/btc-bollinger.html) | 32 | **F** | -47.6% vs 70.4% | -1.17 | 0.000 | 0.28 | -1.26 → -0.91 | 1.000 | 1.000 | no |
| BTC | [MovingAvg2Line Cross](reports/btc-ma-cross.html) | 40 | **F** | 9.6% vs 70.4% | -0.47 | 0.000 | 0.19 | -0.42 → -0.71 | 1.000 | 1.000 | no |
| BTC | [Parabolic SAR](reports/btc-psar.html) | 18 | **F** | -11.6% vs 70.4% | -0.67 | 0.000 | 0.08 | -0.67 → -0.75 | 1.000 | 1.000 | no |
| BTC | [Stochastic Slow](reports/btc-stochastic.html) | 16 | **F** | -57.2% vs 70.4% | -1.28 | 0.000 | 0.75 | -1.33 → -1.22 | 1.000 | 1.000 | no |
| BTC | [Channel BreakOut](reports/btc-channel-breakout.html) | 8 | **F** | -0.8% vs 70.4% | -0.56 | 0.010 | 0.71 | -0.54 → -0.67 | 1.000 | 1.000 | no |
| BTC | [Keltner Channels](reports/btc-keltner.html) | 24 | **F** | 15.4% vs 70.4% | -0.45 | 0.003 | 0.35 | -0.48 → -0.38 | 1.000 | 1.000 | no |
| BTC | [Momentum](reports/btc-momentum.html) | 10 | **F** | 19.5% vs 70.4% | -0.38 | 0.027 | 0.53 | -0.23 → -0.96 | 1.000 | 1.000 | no |

Survive Holm: **0 of 20**.

## Deviations and disclosures

- **No deviations** from the preregistered rules, grids, costs, dates, holdout splits or objective.
- *Code fix before the first run:* the runner first crashed while building a report description (it read a missing docstring), before any audit statistic was computed. It now takes each rule's text verbatim from the sealed preregistration.
- *BTC data:* the BTC OHLC file was fetched for sample audit 4 (15:34:16Z), before this batch was declared (18:21:27Z). The preregistration disclosed this and pinned the file's SHA-256, and the file is unchanged. The engine's declaration-date check, which exists to police objective (b), was therefore not applied to the 10 BTC audits. All 20 audits use objective (a).
- *SPY data* were fetched after the seal (see `samples/data/MANIFEST.json`).
- *Execution convention,* stated in every report: signals are taken at the daily close and held close to close. Stop entries are treated as filled at the signal close, and short-side funding is not modelled. This differs from TradingView's broker emulator, which fills at the next open and fills stops intrabar.
- *Selection of the ten:* all ten indicators are TradingView built-ins (Help Center). We had no quantitative popularity data. Ichimoku was excluded because it has no built-in strategy. See the preregistration.
- *Prior exposure:* SPY and BTC prices and results from sample audits 1–4 had been seen before this batch.

Data: prices from Yahoo Finance's public chart endpoint (SPY) and the Coinbase Exchange public API (BTC). We publish derived statistics only, never raw prices; no redistribution.
