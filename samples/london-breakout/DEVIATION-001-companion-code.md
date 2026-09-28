# LB-1 DEVIATION-001: companion code for declared items the sealed pipeline does not compute

**Date:** 2026-09-28 (written after the PREREG seal of 2026-09-28T13:23:36Z; sealed with `holdout-audit seal-doc`
before `lb_extra.py` read any real price and before Stage A ran).

**Nature:** a disclosure of added code and of method details that PREREG left unspecified.
The sealed files (`PREREG.md`, `preregistration.json`, `declaration.json`, `lb_port.py`, `lb_original.py`,
`lb_data.py`, `run.py`, the vendored upstream file) are **not modified**. No inference, grid, cost, period, test,
α, or verdict wording changes. Nothing here can change P1, P2, Holm, the verdict or the rubric grade.

## 1. Why

The sealed `run.py` computes P1, P2, Holm, the verdict, the rubric runs, the 15 Sharpe ratios, the
in-sample-best variant, and the cost / gross / break-even / next-bar / DST-clock / season / before-after-2018 sensitivities.
It does **not** compute some items that PREREG declares:

| PREREG | Item | Not in `run.py` |
|---|---|---|
| §5.4 | Reproduction check on the author's `data/gbpusd.csv` (author's code vs port) | yes |
| §5.4 | FRED `DEXUSUK` level check | yes |
| §5.4 | Coverage shares; A10 carries; A11 empty ranges; stale thresholds; >100-pip bar moves | yes |
| §6.4 | By calendar year; by volatility tercile; false alarms; exits by reason in the holdout | partly |
| §6.2 | Rank correlation of the 15 variants' Sharpe, in-sample vs holdout | yes |
| §7.3 | The holdout confidence interval | yes |
| §0/§12 | An HTML report ("the full report") | yes (run.py writes JSON only) |

## 2. What is added (not sealed in PREREG §11, sealed here)

| File | SHA-256 | Role |
|---|---|---|
| `lb_extra.py` | `222530f2da5c6c361289f6bf729f233c432a5204911240a9b250353cd04cbdc3` | computes the items above; imports the sealed modules unchanged; reads real prices only via `lb_data.load_real` (seal- and unlock-checked), except the author's file |
| `fetch_histdata.py` | `dac612dbf8178556d5216d4a6018672dafbba51331886af1f6cb38eaeeb0cd6a` | downloads HistData files via its free per-file form (owner instruction), 4 s between requests; records hashes in `MANIFEST.json`; refuses holdout files until `HOLDOUT-UNLOCK.json` verifies |

`lb_data.py`'s docstring says files are "placed by hand"; `fetch_histdata.py` replicates the same manual form
POST (with Referer), so the files are identical. **Disclosure:** the fetcher was written and started (Stage A years
only, 2000–2023) at 2026-09-28T13:28Z, before this note was sealed; it reads no prices. During its test the first
3 lines of the 2000 file were printed (2000-05-30, about 1.497), and the first 5 lines of the author's file
(2018-06-01, about 1.326) were printed to confirm its layout.

## 3. Method details declared now (PREREG was silent)

- **Reproduction check.** The author's file is read as UTF-8 with BOM (`utf-8-sig`); its columns are already `date,price`
  (minute stamps without seconds; CRLF). `lb_original.run_original` and `lb_port.signals_frame` are run with the
  defaults; we report whether `signals`, `upper`, `lower` are identical, the mismatch count, and the date range.
  If the original crashes (A11), that is reported. SHA-256 of the file: `4282af5378d01e0878f339296720e27954b97c090e4c06af104a3d37426c4ac6`.
- **FRED level check.** For each FRED date, the HistData bar at 12:00 New York local time (converted to the fixed
  UTC-5 clock, so 11:00 during US daylight time), or the last bar up to 15 minutes before it; days without such a
  bar are not compared (count reported). Median and 99th-percentile absolute differences in pips; days over 50 pips listed.
- **Coverage (default parameters).** Per weekday with bars: "full hour 2" = 60 distinct minutes in hour 02;
  shares with a 03:00 bar and with an hour-12 bar. **A10 carry day** = a data-clock day whose last bar leaves a
  non-zero position. **A11** = the port's `empty_range_days` counter. **Stale-threshold day** = a day with
  entry-window bars but no 03:00 bar. **False-alarm day** = a day with at least one entry-window bar beyond a
  threshold by more than `risky_stop`. **Jumps** = consecutive bars more than 100 pips apart (count, 25 largest).
- **Volatility tercile.** `holdout_audit.stats.stability.vol_regime_table` (21-day trailing std of GBP/USD daily
  returns from `run.market_returns`, lagged one day), cut points computed within each period reported
  (in-sample, holdout, full) separately.
- **By calendar year.** Net Sharpe, compounded net return, mean annual net and gross return, trades.
- **Holdout confidence interval.** 95% CI of the default's annualised net Sharpe in the holdout (and in-sample),
  Mertens (2002) non-normal IID standard error (`holdout_audit.stats.sharpe.se_sharpe_nonnormal`), ×√260.
- **Rank correlation.** Spearman ρ of the 15 variants' annualised Sharpe, in-sample (Stage A) vs holdout (Stage B).
- **HTML report.** `holdout_audit.report.write_report` on a rubric run with exactly `run.py`'s inputs and settings,
  plus report metadata only (description, rules, provenance notes, the sealed PREREG and its seal, the declaration,
  data-received time). `lb_extra.py` refuses to write the report unless its headline equals the headline stored by
  `run.py` in `stageA/results.json` / `stageB/results.json`.

## 4. Other notes (no change needed)

- HistData's GBPUSD M1 history starts on **2000-05-30** (first bar of the 2000 file), not 2000-01-01.
  PREREG §5.2 defines the sample from "the first bar", so this is not a deviation; it is reported.
- PREREG §13 ("Owner decisions before sealing (this section is deleted at sealing)") was left in the sealed text.
  The owner's decisions are recorded in its header note (approve design; HistData; public home in holdout-audit).
  The sealed text is not edited.
