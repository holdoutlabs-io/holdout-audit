# LB-1: The London Breakout from je-suis-tm/quant-trading, tested as written

> **Approved by the owner 2026-09-28** (design, HistData as source, public home in github.com/holdoutlabs-io/holdout-audit under samples/london-breakout/). Sealed with RFC 3161 timestamps (`holdout-audit seal-doc`, DigiCert and FreeTSA); the seal record sits next to this file. **No GBP/USD price had been loaded by this study at sealing**; the loaders refuse until the seal verifies (`lb_data.require_prereg_seal`).

**Status (at sealing):** sealed before any GBP/USD price series was loaded by this study. Only metadata were fetched before the seal: the strategy's source code and README at a pinned commit, the data vendor's pages (formats, time zone, listed years, terms) and one broker's published spread range (sources in §12).

**Scope:** statistical analysis of past data only (`docs/SCOPE-POLICY.md`). Nothing here or in the results is investment advice, a recommendation to trade any currency, or a statement about the author's skill. Asset guard: FX is in scope (Celestial DEV-031/032, `tests/test_policy.py`); no astronomical features.

**Public commitment:** on 2026-09-28 Holdout Labs replied on X to @RHerman (https://x.com/RHerman/status/2104453599917199646; our reply https://x.com/rv_holdoutlabs/status/2104540769486791143): *"We'll take the London Breakout from the repo as written, seal the rules and settings before touching any data, and publish the full result here whatever it shows. Will post the sealed plan first."* This document is that plan.

**Publish all:** the full report (every statistic below, every sensitivity, every deviation) will be published at `samples/london-breakout/` and on holdoutlabs.io, and the result posted as a reply in that X thread, **whatever it shows**, including if the strategy works.

## 0. What we have already seen (read this first)

- **Code and README.** We read the strategy script, the README section and the author's `Heikin-Ashi backtest.py` (for its P&L convention) at the pinned commit (§2). We did not open the README's preview images (`preview/london breakout positions.png`, `... thresholds.png`), which plot one day of the author's data.
- **The repo's own data file** `data/gbpusd.csv` (806,145 bytes, added 2022-12-05) has **not** been opened. It is used once, after sealing, for the reproduction check in §5.4.
- **No GBP/USD intraday or daily price** has been loaded by any Holdout Labs study (repository search, 2026-09-28). No result of this or any similar strategy has been looked up for this study.
- **Synthetic data only.** The port and pipeline were run on seeded random walks (§3.4, `tests/test_london_breakout.py`). Those numbers say nothing about GBP/USD.
- **General knowledge.** The author knows in general terms what any FX reader knows: GBP/USD has ranged roughly between 1.05 and 2.10 since 2000, and "opening-range breakout" rules are widely discussed. No statistic of this rule on real data has been computed or seen.

## 1. Question

The London Breakout script in je-suis-tm/quant-trading (about 10,800 GitHub stars) is presented in its README as "a fascinating information arbitrage across different markets in different time zones": the last hour before the London open "incorporates the information of all the overnight activities", and a breakout of that hour's range at the open is traded. The script itself computes no P&L.

**Claim tested:** *as coded, with its default settings, the London Breakout earns a positive risk-adjusted return on GBP/USD net of realistic trading costs.*

We test the code, not the idea. A null result says nothing about other implementations of a London breakout.

## 2. Source (pinned)

| Item | Value |
|---|---|
| Repository | https://github.com/je-suis-tm/quant-trading (Apache-2.0) |
| Commit (HEAD on 2026-09-28) | `611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5` |
| File | `London Breakout backtest.py` (286 lines) |
| File SHA-256 | `8b5a0f672c2c5a44fb5a72564fcb0b20a5bd2b0d3d9da3e2f4a52b2d047f8e3a` |
| File history | first under this name 2018-04-17 (`b6c046e`); last change 2019-03-13 (`82e748f`, "change link") |
| Vendored copy | `upstream/London Breakout backtest.py` (byte-identical, with the repo's `LICENSE`) |
| Data the repo used | HistData.com 1-minute GBP/USD: the script links `histdata.com/download-free-forex-data/?/excel/1-minute-bar-quotes` and says the author averaged bid and ask into a `price` column, in New York time "utc -5". The repo's README lists Histdata among its data sources. The repo ships `data/gbpusd.csv` (not opened, §0). No sample period is stated anywhere. |

## 3. The strategy as coded

### 3.1 Quoted logic (lines 106–209, abridged; variable names as in the source)

```python
risky_stop=0.01          # "i am using 100 basis points"; stop/target = risky_stop/2
open_minutes=30
if   hour==2:                       tokyo_price.append(price)           # range hour
elif hour==3 and minute==0:         upper=max(tokyo_price); lower=min(tokyo_price); tokyo_price=[]
elif hour==3 and minute<open_minutes:
    if price-upper>0:  signal=1;  if price-upper>risky_stop: signal=0   # "false alarm"
                                  elif cumsum>1: signal=0 else: executed_price=price
    if price-lower<0:  signal=-1; if lower-price>risky_stop: signal=0
                                  elif cumsum<-1: signal=0 else: executed_price=price
elif hour==12:                      signal=-cumsum                      # flatten
else:
    if cumsum!=0:
        if price>executed_price+risky_stop/2: signal=-cumsum
        if price<executed_price-risky_stop/2: signal=-cumsum
```

### 3.2 In five lines

1. **Instrument and clock:** GBP/USD 1-minute prices, timestamps in fixed UTC-5 (HistData's "EST without DST").
2. **Range:** high and low of every price in hour 02 (02:00–02:59 UTC-5 = 07:00–07:59 UTC), fixed at the 03:00 bar.
3. **Entry:** during 03:01–03:29, long on the first price above the high, short on the first price below the low, unless the price is more than `risky_stop` = 0.0100 (100 pips) beyond the level ("false alarm").
4. **Exit:** from 03:30 on, exit when the price moves `risky_stop/2` = 0.0050 (50 pips) from the entry price either way (target or stop, same size).
5. **Time exit:** everything is flattened at the first bar of hour 12 (12:00 UTC-5 = 17:00 UTC).

Defaults: `risky_stop = 0.01`, `open_minutes = 30`. Range hour 2, open hour 3 and close hour 12 are hard-coded.

### 3.3 Ambiguities and bugs, with the interpretation we declare

We do **not** fix the strategy. Where the code is clear we follow it, even where it looks unintended. Where it is silent or would crash, we declare a reading.

| # | Issue | Declared interpretation |
|---|---|---|
| A1 | **Clock and DST.** Hours 2/3/12 are tested on the data's own timestamps. The comments assume HistData's fixed UTC-5 ("daylight saving time is another story"). In British Summer Time the "03:00" open is 09:00 London time, an hour after the real open. | As coded: fixed UTC-5, year-round. **Sensitivity (descriptive):** the same rule on a DST-aware London clock (range 07:00–07:59, open 08:00, flatten 17:00 London time). |
| A2 | **What "price" is.** The comment says the author averaged bid and ask; HistData's 1-minute bars are bid-only OHLC. | `price` = the 1-minute bar **close bid**. A constant spread shifts every price equally and changes no breakout; the full spread is charged in costs (§4.3). |
| A3 | **Range definition.** A comment suggests an optional "10 basis points" buffer around the thresholds; the code has none. | No buffer. The range is the max/min of the hour-2 bar prices. |
| A4 | **Units.** Comments say "basis points"; `0.01` is in price units (100 pips; about 75 bp at 1.30). | Price units, as coded: 100-pip false-alarm limit, 50-pip stop and target. |
| A5 | **Entry window.** `minute==0` is caught first, so the 03:00 bar sets thresholds but is never tested for a breakout. | Entry bars are 03:01 to 03:(open_minutes−1). |
| A6 | **No stop or target inside the entry window.** The entry branch has no exit logic, so a position opened at 03:01 cannot be stopped before 03:30. | Reproduced. |
| A7 | **Opposite breakout inside the window flattens, it does not reverse.** A long followed by a price below the low gives signal −1 → flat (and resets `executed_price`); a second such bar opens the short. | Reproduced. Counted as exit reason "window_reversal". |
| A8 | **One entry per direction**, enforced with the running `cumsum` of all signals since the file's first row. | Reproduced (the port keeps the same running position). |
| A9 | **Stops and targets on bar prices.** Checked on each bar's `price` and filled at that price, so exits can overshoot 50 pips. | Reproduced, filled at the bar's price (§4.1). |
| A10 | **Missing hour-12 bar.** If a day has no bar in hour 12, the position carries into later bars and days until a stop, target or the next hour-12 bar. | Reproduced; such days are counted and listed. |
| A11 | **Empty range.** A 03:00 bar with no hour-2 bar before it makes `max([])` raise `ValueError`: the original crashes. | **The one departure:** no trade until the next valid 03:00 bar. Counted. (A missing 03:00 bar is reproduced literally: the previous thresholds stay and the range list keeps accumulating. Counted.) |
| A12 | **No P&L code.** The script only plots the first day; it points to `Heikin-Ashi backtest.py` for statistics, which books a fixed unit size filled at the signal bar's close, without compounding. | We use that convention (§4). |
| A13 | **No costs** anywhere in the repo. | Our declared cost model (§4.3). |
| A14 | **Instrument.** Comments mention "certain currency pairs"; the code reads `gbpusd.csv` only. | GBP/USD only. |
| A15 | **Non-signal bugs.** `plot()` uses an undefined global `signals` (NameError); `new['%s'%date]` fails in pandas ≥ 2; `os.chdir('d:/')` at import; O(n²) run time. | Irrelevant to signals; not executed. We run lines 51–211 (the two signal functions) unchanged; they work under pandas 3.0.6. |

### 3.4 Faithfulness of the port

- `lb_original.py` executes lines 51–211 of the vendored, hash-checked upstream file: the author's own functions, unmodified.
- `lb_port.py` is our O(n) state machine used for the audit.
- `tests/test_london_breakout.py` checks that:
  - on a hand-made 3-day example, **both** the author's code and the port give the hand-worked signals (long, window reversal to flat, short, target, false alarm, 12:00 flatten, minute-29 entry and minute-30 stop);
  - on four seeded random walks (one with 5% of bars deleted, so thresholds go stale as in A11), `signals`, `upper` and `lower` are identical bar for bar;
  - for three grid variants, the author's code with only the two constants swapped (exact text substitution) matches the port;
  - the original crashes on an empty range and the port skips it (A11).

## 4. Execution conventions and accounting

### 4.1 Fills
At the price of the bar that generates the signal (as written: `executed_price = price[i]`; the author's Heikin-Ashi `portfolio()` also fills at the signal bar's close). **Sensitivity:** fill at the next bar's price.

### 4.2 Size and returns
- One unit of GBP notional per unit of signal; no leverage, no compounding.
- The daily return is the day's mark-to-market P&L plus costs, divided by the fill price of the latest entry (the notional at risk), summed over the day's bars.
- Rows: every weekday (on the data's clock) with at least one bar. Days without a trade have return 0. 260 periods a year.
- No financing: positions are flat by 17:00 UTC, before the 17:00 New York rollover (except A10 carries, which are counted).

### 4.3 Costs
- **Base: 1.0 pip per unit traded, one way** (entry, exit, and each unit of a flip). That is a 2.0-pip round trip: a 1.0-pip spread, paid once per round trip because prices are bid, plus 0.5 pip of slippage on each fill.
- **Source.** CMC Markets gives GBP/USD's typical spread as 0.5–3.0 pips and says spreads widen in the early European morning, when these entries happen (§12).
- **Sensitivities:** 0.5 pip one way (1.0 round trip: raw-spread ECN plus commission) and 2.0 pips one way (4.0 round trip: retail standard account, or the wider spreads of the 2000s).
- **Break-even:** the gross pips per round trip ÷ 2 is reported as the one-way cost at which the gross edge is zero.

### 4.4 Benchmark: zero (cash)
- A spot FX position is self-financing: margin cash earns the same interest whether or not the rule trades.
- This rule holds nothing overnight, so it earns no carry.
- It is long and short in equal measure by construction, so buy-and-hold GBP/USD is not a meaningful comparison.
- The null hypothesis is therefore zero excess return.
- The rubric runs with `--benchmark zero`, and this reason is printed in the report.
- GBP/USD's own daily return is supplied only for the volatility-regime split.

## 5. Data (loaded only after this document is sealed)

### 5.1 Source: HistData.com, GBPUSD, Generic ASCII, 1-minute bars
- **Format:** `DateTime Stamp;Bar OPEN Bid Quote;Bar HIGH Bid Quote;Bar LOW Bid Quote;Bar CLOSE Bid Quote;Volume`.
- **Time zone:** "Eastern Standard Time (EST) time-zone WITHOUT Day Light Savings adjustments" (HistData specification page).
- **Why this source:**
  - it is the source the script names;
  - its fixed-UTC-5 clock is exactly what the hard-coded hours assume;
  - it is free;
  - it lists GBPUSD 1-minute data from 2000 to the current month.
- **Terms:** HistData publishes no licence for the free files. Its FAQ says only *"Since it's free data, you'll not get from us any kind of warranty or certification. Use the data at your own will and risk."* We found no restriction on commercial use or on publishing derived statistics, and no permission for them either (see the owner decision in §13).
- **We never redistribute:** raw and parsed files are never committed or published (`.gitignore`). Only derived statistics and hashes are published, and no price chart.
- **Not used:** Dukascopy, whose website terms restrict use to "your own non-commercial use and benefit", forbid using the information "to construct a database of any kind", and forbid automated access. Norgate and ThetaData are never used for Holdout Labs work.

### 5.2 Periods
- **Full sample:** from the first bar in the GBPUSD M1 files (HistData lists 2000) to 2026-09-25 23:59 UTC-5.
- **In-sample (Stage A):** the first bar to 2023-12-31: the annual files 2000–2023, about 24 years.
- **Locked holdout (Stage B):** 2024-01-01 to 2026-09-25: the annual files 2024 and 2025 plus the monthly files 2026-01 to 2026-09, about 2.7 years. The boundary sits on a file boundary, so holdout files need not be downloaded at all during Stage A.
- **If the September 2026 file is not yet published** at download, the holdout ends at the last complete month available. This is recorded as a deviation.

### 5.3 Hashing and locks
1. **Download and hash.** Download the in-sample files only. For each: file name, source page, download time (UTC), bytes, SHA-256 of the zip and SHA-256 of the extracted CSV. Record these in `MANIFEST.json` and **commit before Stage A runs**. HistData's per-file status/gap reports are hashed too.
2. **Canonical panel hash.** `lb_data.panel_sha256` is the SHA-256 of the parsed series written as `YYYY-MM-DD HH:MM:SS,price` (6 dp, LF). It is stored in each stage's results, so anyone with the same files can confirm they hold the same data.
3. **Loader locks.**
   - `load_real("A")` refuses to run unless `PREREG.md`'s seal verifies.
   - It refuses any file whose name holds 2024, 2025 or 2026.
   - It refuses any timestamp ≥ 2024-01-01.
4. **Unlocking the holdout.**
   - Commit `stageA/results.json`, then write `HOLDOUT-UNLOCK.json` with that file's SHA-256 and the commit hash, and commit and push it.
   - Only then download the holdout files, adding them to `MANIFEST.json` in a commit first.
   - `load_real("B")` refuses to run if the Stage A results changed after the unlock.

### 5.4 Checks (reported, never used to drop data)
- **Reproduction check on the author's own file.** After sealing and before Stage A, we run the author's code (`lb_original`) and the port on the repo's `data/gbpusd.csv`, and they must give identical signals. If the file's layout differs from `date,price`, we record the mapping used. Its date range is reported. If the file's days fall inside our sample, we disclose that the author saw them.
- **Independent level check.** We compare against FRED `DEXUSUK` (Federal Reserve H.10 noon buying rates in New York; public domain).
  - For each day, we take the HistData bar at 12:00 New York local time.
  - We report the median and 99th-percentile absolute differences in pips, and list the days with differences over 50 pips.
- **Coverage.** We report the share of weekdays with a full hour 2, a 03:00 bar and an hour-12 bar. We count A10 carries, A11 empty ranges and stale thresholds. We flag bar-to-bar moves over 100 pips.

## 6. Analysis plan

### 6.1 Stage A (in-sample; the holdout is not on disk)
1. Compute the net daily returns of all **15 grid variants** (§6.3) at base cost.
2. Run rubric v1.2 (`holdout-audit` 0.4.x, `docs/RUBRIC-v1.2.md`, SHA-256 `81bc60b5…71fc`) on the **default** as the chosen variant, with these settings:
   - objective (a) and `declaration.json`;
   - benchmark zero;
   - variant matrix supplied; `n_trials = 15`;
   - 1,000 stationary-bootstrap draws; seed 20260925; CSCV with 16 blocks;
   - 260 periods a year;
   - `base_cost_bps = 0`, because the returns are already net of the pip cost model. The rubric's cost-headroom figure is therefore extra headroom beyond our costs; the gross break-even in pips is reported separately.

   The rubric's internal split (the last 30% of the in-sample) is reported, but it is not the locked holdout.
3. **P1** = 1 − DSR of the default at N = 15.
4. Record the **in-sample-best variant** (highest net Sharpe), all 15 Sharpe ratios, PBO (CSCV), SPA, the parameter plateau, and the §6.4 sensitivities.
5. Write `stageA/results.json`, commit, and unlock the holdout (§5.3).

### 6.2 Stage B (holdout)
1. **P2:** one-sided p = P(Z ≥ annualised Sharpe × √years) of the default's net daily returns over 2024-01-01 → 2026-09-25 (N = 1: the default was fixed by the author in 2018).
2. **Holm** across {P1, P2}; the verdict of §7.2.
3. Also reported:
   - the holdout Sharpe of all 15 variants;
   - the in-sample-best variant in the holdout (did tuning help?);
   - the rank correlation of the variants' Sharpe ratios in-sample vs holdout.
4. The **full-sample rubric run** (the variant matrix, split at 2024-01-01) gives the headline letter grade.

### 6.3 Grid (declared; N = 15)
| Parameter | Values | Default |
|---|---|---|
| `risky_stop` (false-alarm limit; stop and target = half) | 0.0050, 0.0075, **0.0100**, 0.0125, 0.0150 | 0.0100 |
| `open_minutes` (entry window end) | 15, **30**, 45 | 30 |

- These are the script's only two named parameters, each within ±50% of its default. `open_minutes` stops at 45 because the code's `hour==3` test caps it below 60.
- The range hour, open hour and close hour are hard-coded, not parameters. The DST-aware clock, fills, costs and subperiods are sensitivities of the default, not selection candidates, so they do not enter N.
- The author's own search is unknown. **N = 15 is a floor.** The rubric's "DSR against N" table shows how the result moves for larger N.

### 6.4 Sensitivities of the default (DESCRIPTIVE; no inference claimed)

Each is reported for the in-sample and the holdout separately:

- costs of 0.5 and 2.0 pips one way;
- gross returns and the break-even cost;
- next-bar fills;
- the DST-aware London clock (A1);
- April–October vs November–March (roughly BST vs GMT, where A1 bites);
- before vs after 2018-04-17, the first commit of the script under its current name;
- by calendar year;
- by GBP/USD volatility tercile;
- trade count, hit rate, average pips per trade, and exits by reason (target, stop, close, window reversal);
- false alarms, A10 carries and A11 days.

## 7. Inference

### 7.1 Tests
| Test | Data | Statistic | N |
|---|---|---|---|
| **P1** | In-sample, 2000–2023 | 1 − DSR (rubric v1.2 'dsr', Bailey & López de Prado 2014) | 15 |
| **P2** | Locked holdout, 2024-01-01 → 2026-09-25 | one-sided P(Z ≥ SR_ann·√years) | 1 |

Holm step-down across the two, family-wise α = 0.05.

### 7.2 Wording (fixed now; the first line that applies is used)
1. **"Supported"**: both Holm-adjusted p ≤ 0.05. *As coded, the London Breakout earned a positive risk-adjusted return on GBP/USD net of costs, in-sample and in the locked holdout.*
2. **"Went the other way"**: the full-sample mean net return ≤ 0. *As coded, it lost money net of costs.*
3. **"In-sample only"**: P1 adjusted ≤ 0.05, P2 not. *Significant over 2000–2023, not confirmed in the locked holdout.*
4. **"Holdout only"**: P2 adjusted ≤ 0.05, P1 not. *Positive in the holdout, not shown over 2000–2023 at N = 15.*
5. **"Not shown"**: otherwise. *A positive net return was not shown; the point estimate is positive.*

- The rubric v1.2 letter grade and every check are reported whatever the verdict.
- We never write "the strategy doesn't work" or "works". We report what was and was not shown, as coded, on this data, at these costs.

### 7.3 Power (stated now)
- **In-sample (~24 years).** 80% power at N = 1 needs an annualised Sharpe of about 2.80/√24 ≈ 0.57 at the first Holm step (α = 0.025). DSR at N = 15 raises that bar by roughly 1.7 × the cross-variant standard deviation of the Sharpe estimates.
- **Holdout (~2.7 years).** 80% power needs a Sharpe of about 1.7 (α = 0.025) or 1.5 (α = 0.05).
- **A "not confirmed in the holdout" result is therefore weak evidence against a modest edge.** The holdout's confidence interval is always shown.

## 8. What could we be wrong about
1. **Fills at the signal bar's price are optimistic.** The rule sees the close and trades at that same close. The next-bar sensitivity shows how much this matters.
2. **Stops and targets fill at bar closes**, which can be better or worse than a resting stop order. There is no intrabar high/low logic, because the code has none.
3. **Costs are flat over 26 years.** Retail spreads were wider in the 2000s, so the base cost likely flatters the early years. The 2-pip-per-side sensitivity covers this.
4. **Clock.** If the author's own file was DST-adjusted, "as coded" would mean a different hour in summer. The DST-aware sensitivity and the §5.4 reproduction check address this.
5. **Bid close vs bid/ask average.** They differ only by half the spread's variation, which is negligible next to 50-pip exits.
6. **HistData quality.** It comes with no warranty: gaps, bad ticks and thin early years are possible. The FRED level check and the coverage counts expose problems but do not fix them.
7. **Fixed pip parameters** meet a pair whose price and volatility changed a great deal (from about 2.1 to 1.05). This is the rule as written; the calendar-year and regime tables show where it behaves differently.
8. **The author's N is unknown**, so our N = 15 may understate the selection the defaults went through.
9. **Low holdout power** (§7.3).

## 9. Limitations
- One pair and one implementation, as coded; this is not a verdict on breakout trading in general.
- One retail-realistic cost model. Institutional execution could be cheaper.
- Free vendor data, not an audited feed.
- Results on 2000–2026 need not hold later.

## 10. Exclusions, missing data and deviations
- **No exclusions.** Every weekday with at least one bar is a row. Missing minutes are not filled.
- **Edge cases** are handled as in §3.3 (A10, A11) and counted.
- **Any deviation** from this document (source failure, file-format change, holdout end date) is written up, dated, committed and listed in the report **before results are published**. If HistData becomes unavailable, the fallback source must be named in a sealed deviation **before any of its data is loaded**.
- **No re-runs** with other settings are reported as results.

## 11. Companion files (hashed at sealing)

| File | SHA-256 (at sealing, 2026-09-28) |
|---|---|
| `preregistration.json` | `1b031af912fbbdbbe6425b4b0313b2fdc41dc673f6aca901206efc42861af65f` |
| `declaration.json` | `84be0e4a6266d4d487cfe33083f5b31dc3bea02366ed4529b5bab4ce9efb308b` |
| `upstream/London Breakout backtest.py` | `8b5a0f672c2c5a44fb5a72564fcb0b20a5bd2b0d3d9da3e2f4a52b2d047f8e3a` |
| `lb_port.py` | `1691afc70f2fc214327cded763712c5b1d98fd21e8eb30fb9f63afbc2289f295` |
| `lb_original.py` | `323a650462dacefcaa80a5ee4225fdad145101cae78a99aefa53896f34bf452e` |
| `lb_data.py` | `cac57d87c9a1a908de3d604dcd85632566a90bd1b81f6be821be2afc279472ff` |
| `run.py` | `b12c34dc91e0605674556b8c4a645d07e00c29fb803997254f009621a3fb0348` |
| `docs/RUBRIC-v1.2.md` (already sealed) | `81bc60b5bf4520fdfb91c43b37883c30a9a2061903442d1e8a8b05f3d37a71fc` |

If this document and a companion file disagree, **this document governs**.

## 12. Sources (fetched 2026-09-28, before the seal)
- **Strategy:** `London Breakout backtest.py`, `README.md` (§ "4. London Breakout", § "Data Source") and `Heikin-Ashi backtest.py` (for `portfolio()`), all at commit `611b73f2`, fetched from raw.githubusercontent.com; commit history from the GitHub API.
- **HistData:**
  - FAQ: https://www.histdata.com/f-a-q/ (time zone; bid-based bars; "Use the data at your own will and risk");
  - format specification: https://www.histdata.com/f-a-q/data-files-detailed-specification/;
  - GBPUSD M1 listing: https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/gbpusd (2000 through September 2026 listed);
  - home page: paid FTP access $27 one-time, as an alternative to the per-file download form.
- **Dukascopy terms of use:** https://www.dukascopy.com/swiss/english/legal-pages/terms-of-use/ §3.
- **Costs:** CMC Markets, "What is a good forex spread?", https://www.cmcmarkets.com/en-gb/forex/what-is-a-good-forex-spread.
- **FRED:** series `DEXUSUK` (for the §5.4 level check only).

## 13. Owner decisions before sealing (this section is deleted at sealing)
1. **Approve the design:** the grid and N = 15, a 2.0-pip round trip base cost, the 2024-01-01 holdout (about 2.7 years, on a file boundary), zero benchmark, and the verdict wording in §7.2.
2. **HistData terms.** There is no written licence, only "use the data at your own will and risk". Options:
   - (a) proceed: statistics only, no redistribution;
   - (b) first email HistData for a one-line written OK (recommended; may delay);
   - (c) also buy the $27 one-time FTP access, which avoids about 35 manual form downloads.

   Add this to the lawyer-hour list either way.
3. **Where the sealed plan is public.** `holdout-labs` is a private repo, so the X link must point elsewhere: a holdoutlabs.io page, the public `holdoutlabs-io/holdout-audit` repo, or OSF (as with SMARTBETA-1).
4. **Optional:** a courtesy note to the repo author (a GitHub issue) after sealing.
