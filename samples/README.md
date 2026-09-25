# Public sample audits

Three well-known public strategies, audited with `holdout_audit`, and reported as they came out. These are statistical illustrations of the audit method, **not recommendations**. See `../docs/DISCLAIMER.md`.

```bash
uv sync
uv run python samples/run_all.py                                         # published samples (Yahoo, official source)
uv run python samples/run_all.py --spy-file ~/Downloads/spy_us_d.csv   # option: SPY from a manual Stooq download
```

**Data provenance.** Prices from Yahoo Finance's public chart endpoint; we publish derived statistics only, never raw prices; no redistribution.

- **SPY:** the official source for the published samples is **Yahoo Finance's public chart endpoint** (unadjusted close plus dividend events; total return is computed locally). The raw file stays in `samples/data/raw/` (git-ignored). Only the fetch script and the file's SHA-256 (`MANIFEST.json`) are committed.
- **SPY via Stooq (option):**
  - Download the file by hand from https://stooq.com/q/d/l/?s=spy.us&i=d. The expected header is `Date,Open,High,Low,Close,Volume`, with ISO dates, oldest first.
  - Pass it with `--spy-file`.
  - Stooq closes are used as given, with no dividend column.
  - The published samples do not use this path: Stooq's browser check blocked our download too.

BTC comes from the Coinbase Exchange public candles API, with the same policy: derived statistics only, never raw prices, no redistribution.

This writes `samples/reports/*.html`, which print cleanly to PDF, and `samples/reports/summary.json`.

| # | Strategy | Variant family (N) | How the audited variant was chosen | Report |
|---|---|---|---|---|
| 1 | SPY 50/200-day golden cross | fast (20–100) × slow (100–300), 24 | Fixed in advance: the textbook 50/200 | `reports/01-spy-golden-cross.html` |
| 2 | RSI(2) mean reversion on SPY (Connors-style) | RSI length × entry × exit SMA × trend filter, 60 | **Best in-sample Sharpe** on the first 70%, as an optimiser would pick it. The last 30% is a true holdout | `reports/02-spy-rsi2.html` |
| 3 | BTC close above its 50-day SMA | SMA or rate of change × 7 lookbacks, 14 | Fixed in advance: SMA-50, a common default | `reports/03-btc-sma50.html` |
| 4 | **TradingView built-in "Supertrend Strategy"** on BTC daily (rubric **v1.1**) | ATR 7/10/14 × factor 2–4 × long-short/long-flat, 30 | **Preregistered and sealed before any run:** the TradingView default (ATR 10, factor 3, long and short) | `reports/04-btc-supertrend.html` |

Samples 1–3 are graded under the sealed **rubric v1.0**, against buy-and-hold of the same asset.

**Sample 4 is done the way we sell it.** Before the BTC OHLC data were fetched and before any Supertrend result existed, we wrote two documents and sealed each with RFC 3161 timestamps from DigiCert and FreeTSA. The documents are in `samples/prereg/04-btc-supertrend/`:

| Document | SHA-256 | Seal record SHA-256 | Signed (UTC) |
|---|---|---|---|
| Objective declaration: (a) beat buy-and-hold BTC | `2ae0b40e7f8dc8a6453eef02c9239286f36e6b42c7fc115da7001bc34ab64ca2` | `f5a13f10501ae6925f7292e68ee203e49a2f204c5c36dc384b96cf570fe3842c` | 2026-09-25 15:33:18 |
| Preregistration: rule, 30-variant grid, costs, data, dates, holdout, prior exposure | `14326ac57f065915a0997f376cb313b68170b1b213d9f95404ce0ace9a3dc48b` | `87c73803cae076ec7d19ac2bdd2f423c39588e9780dd61b0c092731bb94c209c` | 2026-09-25 15:33:22 |

- The data were fetched at 15:34:16Z, after both seals, and the report cites both.
- **Result: F.** The TradingView default had a Sharpe of 0.37, compounding at 2.4% a year against 70.4% for buy-and-hold BTC. Its excess Sharpe was −0.52, its DSR 0.006 and its PBO 0.32. Its maximum drawdown was 88% against 84% for buy-and-hold.
- None of the 30 variants beat buy-and-hold; the best had an excess Sharpe of −0.12. The default ranked 29th of 30. The long-flat variants did much better than long-short, but still trailed.
- There are no deviations from the preregistration.

Common conventions:
- The signal is taken at the close and held over the next day.
- Money out of the market earns 0%.
- Base costs are 2 bps per unit traded for SPY and 10 bps for BTC; the cost curve runs to 50 bps.
- The bootstrap seed is fixed, so reruns give identical statistics.

`summary.json` holds the headline numbers:
- grade and caps;
- absolute and excess Sharpe;
- DSR, PBO and SPA p;
- holdout excess Sharpe;
- the rubric version and seal hash;
- the SPY data source (`spy_daily_yahoo.csv`).

**Indicator Audit, Batch 3: Strongest published evidence** ([`batch3/`](batch3/README.md)): six audits judged on each source's own claim, under rubric v1.2. 0 of 6 survive; Faber timing on EEM/VNQ/TLT cut drawdowns robustly but exceeded its declared return cost. Positive controls, showing that the audit can pass real edges, are in [`controls/`](controls/) and `docs/POSITIVE-CONTROLS.md`.

**Indicator Audit, Batch 2: Classic market rules** ([`batch2/`](batch2/README.md)): ten published rules on SPY, QQQ, IWM, EFA, sector ETFs and Treasury ETFs, 14 audits under one sealed preregistration. 0 of 14 survive Holm, and all grade F. Reproduce with `uv run python samples/batch2/run_batch2.py`.

**Indicator Audit, Batch 1** ([`batch1/`](batch1/README.md)) adds 20 more audits: ten TradingView built-in strategies × {SPY, BTC}, under one sealed preregistration with Holm's correction across the batch. Result: 0 of 20 survive, and all 20 grade F. Reproduce with `uv run python samples/batch1/run_batch1.py`.

**Why not the drawdown objective?** Rubric v1.1 adds a "reduce drawdown at acceptable cost" objective for clients who **declare it before** their audit. We deliberately did not apply it to these samples after the fact. We had already seen that they cut drawdowns, and switching objective after seeing results is the forking path we audit against. The samples remain v1.0 reports under "beat the benchmark". `run_all.py` pins `rubric_version="1.0"` so that they reproduce exactly.

Current results: all four are **F**. Each has a positive absolute Sharpe, but none beats buy-and-hold of the same asset. See the top-level README.

## On-chain Indicator Audit, Batch 1 (`onchain1/`)

Six famous Bitcoin cycle indicators (Pi Cycle Top, 200-week MA, Mayer Multiple, 2-Year MA Multiplier, Puell Multiple, stock-to-flow), each frozen as first published and tested only on data after its publication. The protocol was preregistered and sealed (DigiCert + FreeTSA, 2026-09-25 18:22:38Z; preregistration SHA-256 `aafe3c37…de40`, seal record `f8d7d587…0275`) before any on-chain data were fetched. Puell and stock-to-flow are computed from block headers we fetched from the Bitcoin P2P network. **Result:** none of the six claims is supported; five had too few post-publication episodes for inference and are reported descriptively; all four implied rules graded F against buy-and-hold BTC. Six UTXO-based metrics (MVRV-Z, NUPL, SOPR, Reserve Risk, STH cost basis, realized price) are sealed but **not run**, pending a data licence that permits commercial publication. See [`onchain1/SUMMARY.md`](onchain1/SUMMARY.md) and [`onchain1/LICENCE-DECISION.md`](onchain1/LICENCE-DECISION.md).

```bash
uv run python samples/onchain1/fetch_headers.py   # ~968k headers over P2P, PoW-checked (git-ignored)
uv run python samples/onchain1/run.py             # needs samples/data/raw/btc_daily.csv (samples/data/fetch.py)
uv run python samples/onchain1/summarize.py
```
