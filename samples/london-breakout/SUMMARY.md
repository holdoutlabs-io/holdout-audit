# LB-1: The London Breakout, tested as written. Result: it went the other way.

**Verdict (wording fixed in advance, PREREG §7.2): "Went the other way". As coded, the London Breakout lost money
on GBP/USD net of costs over the full sample.**

We took the London Breakout script from
[je-suis-tm/quant-trading](https://github.com/je-suis-tm/quant-trading) (commit `611b73f2`) and ran it exactly as
written, with its default settings, on 26 years of 1-minute GBP/USD prices. Every rule, setting, cost and test was
sealed with independent timestamps before we loaded any price
([PREREG.md](PREREG.md); seal 2026-09-28T13:23:36Z, DigiCert and FreeTSA). We run it once and publish it whatever it shows.

Run once on 2026-09-28. Statistical findings about past data only. This is not investment advice, not a
recommendation to trade any currency, and not a statement about the author's skill.

## The result in one table

| | In-sample (2000-05-30 to 2023-12-29) | Locked holdout (2024-01-01 to 2026-09-24) | Full sample |
|---|---|---|---|
| Years of weekdays | 23.2 | 2.7 | 26.0 |
| Average return a year, net of costs (on the notional traded) | **−3.97%** | **−4.46%** | **−4.02%** |
| Sharpe ratio (annualised, net) | **−0.88** | **−1.08** | **−0.90** |
| 95% interval for the Sharpe ratio | −1.29 to −0.48 | −2.26 to +0.10 | |
| Before any costs (gross) Sharpe / return a year | −0.27 / −1.22% | −0.29 / −1.21% | |
| Round-trip trades | 4,788 | 585 | 5,373 |
| Winning trades | 47.9% | 48.7% | 48.0% |
| Average trade before costs | −0.65 pips | −0.73 pips | −0.66 pips |
| Preregistered test (one-sided p) | P1 = 1.0000 (1 − DSR at N = 15) | P2 = 0.9631 | |
| Holm-adjusted p | 1.0000 | 1.0000 | |
| Holdout Audit rubric v1.2 grade | F | | **F** ([full report](reports/lb1-full-sample.html)) |

**In plain words.** The rule was right on slightly fewer than half of its trades. Its winners and losers were about
the same size, so it lost a little on average **before paying anything to trade**. After a realistic 2-pip
round-trip cost it lost about 4% of the traded amount a year. That held over 2000–2023, and again on the
2.7 years of data we kept locked away until the 2000–2023 results were committed.

## What each test says

- **P1, in-sample.** This asks whether the default beat zero over 2000–2023 once we allow for the 15 setting
  combinations tried (the Deflated Sharpe Ratio). It did not: DSR ≈ 0, so p = 1.0000.
- **P2, holdout.** This asks whether the default beat zero over 2024-01-01 to 2026-09-24. It did not: Sharpe −1.08 over
  2.75 years, p = 0.9631.
- **Verdict rule.** Neither test is significant. The full-sample average net return is below zero
  (−4.02% a year). So the second rule of §7.2 applies: **"Went the other way."**
- **Rubric v1.2, full sample: grade F.**
  - Fails: the multiple-testing checks (DSR, haircut, SPA), the holdout check (Sharpe −0.88 in-sample → −1.08
    in the holdout), stability (ahead in 19% of calendar years), costs (break-even below zero) and the parameter surface.
  - Passes: the overfitting check (PBO 0.10). The rule was not tuned into looking good; it lost with every setting.
  - The in-sample rubric run is also grade F ([Stage A report](reports/lb1-stage-a.html)).

## Did any setting work? No: all 15 lost, in both periods

We tried the script's two settings over a grid of 15 combinations (false-alarm limit 50–150 pips, entry window
15–45 minutes). Their net Sharpe ratios:

- **In-sample:** from −0.99 to −0.42. All 15 are negative. The best in-sample setting (150-pip limit, 15-minute window)
  scored −0.86 in the holdout.
- **Holdout:** from −1.54 to −0.69. All 15 are negative.
- **Ranking:** the in-sample ranking of the settings barely carried over (Spearman ρ = 0.14, p = 0.63).

## Sensitivities (declared in advance; descriptive, no test)

Net Sharpe ratio of the default. Average net return a year in brackets.

| Change | In-sample | Holdout |
|---|---|---|
| **Base case: 2-pip round-trip cost** (1.0 pip per side) | −0.88 (−3.97%) | −1.08 (−4.46%) |
| **Cheaper: 1-pip round trip** (0.5 pip per side; raw-spread account) | −0.58 (−2.59%) | −0.69 (−2.84%) |
| **Dearer: 4-pip round trip** (2.0 pips per side; retail standard account or 2000s spreads) | −1.49 (−6.73%) | −1.86 (−7.72%) |
| **No costs at all** (gross) | −0.27 (−1.22%) | −0.29 (−1.21%) |
| **Break-even cost** (the cost per side at which the rule would break even) | −0.33 pips: **none** | −0.37 pips: **none** |
| **Fill at the next bar** instead of the signal bar | −0.94 (−4.24%) | −1.07 (−4.42%) |
| **DST-aware London clock** (range 07:00–07:59, entry from 08:00, exit 17:00 London time, all year) | −0.85 (−3.90%) | −1.28 (−5.40%) |
| April–October (roughly British Summer Time, when the coded clock is an hour late) | −1.00 | −0.60 |
| November–March (roughly GMT, when the coded clock matches the London open) | −0.72 | −1.78 |
| Before the script was published (2000-05-30 to 2018-04-16) | −0.71 (−3.04%) | – |
| After it was published (2018-04-17 to 2023) | −1.33 (−6.81%) | – |
| Low / middle / high GBP/USD volatility (thirds) | −0.34 / −1.39 / −0.87 | −0.08 / −1.52 / −1.28 |

**Clock (DST).** The script's hours are fixed at UTC-5 all year, so for about seven months of each year its "London
open" is one hour late. Moving to the real London clock does not rescue it. On that clock it lost about as much in-sample
and more in the holdout.

**By year.** In-sample the rule made money in 5 of 24 calendar years (2004, 2005, 2006, 2009, 2015).
In the holdout it lost in all three (2024 −0.40, 2025 −1.00, 2026 to September −2.22 Sharpe). The worst years were
2010 (−3.50), 2016 (−2.55) and 2022 (−2.11). Per-year tables are in `stageA/extra.json` and `stageB/extra.json`.

**How trades ended (in-sample / holdout).**
- 50-pip target: 1,662 / 109 (average +54.2 / +52.4 pips).
- 50-pip stop: 1,621 / 117 (−54.1 / −53.2).
- Flattened at 17:00 UTC: 1,246 / 333 (−0.0 / +1.3).
- Opposite breakout in the entry window, which only flattens: 259 / 26 (−20.9 / −13.3).

## Checks on the code and the data (PREREG §5.4)

- **The port matches the author's own code on the author's own data.** On the repo's `data/gbpusd.csv`
  (1-minute GBP/USD, 2018-06-01 to 2018-06-29, 29,698 bars), the author's functions and our port gave identical
  signals and thresholds on every bar (42 signal bars, 0 mismatches). **Disclosure:** June 2018 sits inside our
  in-sample, so the author had seen those days. It is after the script was first published (2018-04-17).
- **Price level vs the Federal Reserve.** We compared the HistData price at noon New York time with FRED `DEXUSUK`:
  - in-sample: 5,804 days, median gap 6.0 pips, 99th percentile 62 pips, 129 days over 50 pips (mostly the
    2008–2009 crisis and October 2022);
  - holdout: 681 days, median 4.5 pips, 99th percentile 33 pips, 2 days over 50 pips.
- **Coverage.** Share of weekdays with a full range hour, a 03:00 bar and a 12:00 bar:
  - in-sample 68.5%; thin early years pull this down (range hour complete on 69.5% of days);
  - holdout 98.6%.
- **Edge cases (in-sample / holdout).**
  - Positions carried overnight because a day had no 12:00 bar (A10): 26 / 0.
  - Days with an empty range (A11): 0 / 0.
  - Days on stale thresholds (no 03:00 bar): 92 / 0.
  - Days with a "false alarm": 15 / 0.
- **Bad ticks.** 79 in-sample and 2 holdout bar-to-bar moves exceeded 100 pips. They include vendor spikes of about
  4,000 pips on 2000-11-24 and the 2016 Brexit vote. We kept every bar (no exclusions, §10).
  - An extra check, not preregistered and changing nothing: only two trades moved more than 150 pips. They were
    2004-08-06 (−204) and 2016-06-24 (−201, Brexit). Neither was a bad tick.

## Deviations (all listed; none changes a test or the verdict)

1. **[DEVIATION-001](DEVIATION-001-companion-code.md)**, sealed 2026-09-28T13:31:54Z (DigiCert, FreeTSA), before it
   was used.
   - The sealed `run.py` leaves out some declared items: the reproduction, FRED and coverage checks, the per-year and
     volatility tables, the rank correlation, the holdout interval and the HTML report.
   - A companion script, `lb_extra.py`, computes them. It uses the sealed code unchanged.
   - The HTML report is refused unless its grade and headline equal `run.py`'s own.
   - The download script `fetch_histdata.py` is also hashed there.
2. **[DEVIATION-002](DEVIATION-002-holdout-end-date.md)**, sealed 2026-09-28T13:59:20Z.
   - HistData's September 2026 file ends at 2026-09-24 19:58 (UTC-5), so the holdout ends one trading day
     earlier than planned (2026-09-24, not 2026-09-25).
   - No other source was used and no alternative end date was run.

Also noted:
- HistData's GBP/USD 1-minute history starts on 2000-05-30.
- PREREG §13 ("owner decisions … deleted at sealing") was left in the sealed text by mistake. It is harmless; the
  decisions are recorded in its header.

## Limitations (read these before quoting the result)

- **This tests one script as coded, not the idea of a London breakout.** Other implementations, such as a DST-aware
  clock, intrabar stops, other pairs or other exits, are not covered. The DST-aware clock was run only as a sensitivity.
- **Fills are simplified.** Trades fill at the 1-minute bar close that triggers them, stops and targets included.
  There is no intrabar high/low logic, because the code has none. Next-bar fills barely change the result.
- **One flat cost model over 26 years.** Real spreads were wider in the 2000s and narrower today. The rule loses
  even at zero cost, so no cost level changes the direction.
- **Free vendor data, bid prices only, no warranty.** HistData data are free, with gaps and some bad ticks, and early years are thin. The FRED comparison and coverage
  counts expose problems but do not fix them. We do not redistribute the data; only statistics and file hashes are
  published ([MANIFEST.json](MANIFEST.json)).
- **Low holdout power.** 2.7 years can only detect large edges: 80% power needs a Sharpe of about 1.5–1.7. The
  holdout interval (−2.26 to +0.10) does not rule out a small positive edge from that period alone. The 23-year
  in-sample does: its interval is entirely below zero (−1.29 to −0.48).
- **The author's own search is unknown.** N = 15 is a floor; this matters little when every setting lost.
- **Past data only.** Results on 2000–2026 need not hold later.

## Files

- **Plan and seals:**
  - [PREREG.md](PREREG.md) and `prereg-seal/`;
  - `DEVIATION-00*.md` and `deviation-00*-seal/`;
  - `registry.jsonl`, the hash-chained seal log.
- **Results:**
  - `stageA/results.json` (in-sample, committed and hashed into `HOLDOUT-UNLOCK.json` before any holdout file was
    downloaded);
  - `stageB/results.json` (holdout, verdict, full-sample rubric);
  - `stageA/extra.json`, `stageB/extra.json` and `repro/repro.json` (DEVIATION-001 items).
- **Reports:** [reports/lb1-full-sample.html](reports/lb1-full-sample.html) (headline) and
  [reports/lb1-stage-a.html](reports/lb1-stage-a.html).
- **Data provenance:** [MANIFEST.json](MANIFEST.json) holds the SHA-256 of all 35 HistData zips, CSVs and status
  reports. Canonical panel hashes: Stage A `fb1865a3…b904d8`, full sample `edf2cc47…701741`.
- **Code:**
  - sealed: `lb_port.py`, `lb_original.py`, `lb_data.py`, `run.py`;
  - companion: `lb_extra.py`, `fetch_histdata.py`.
