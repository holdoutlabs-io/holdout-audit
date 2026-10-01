# COINTIME-1: the True Market Mean, tested as published (preregistration)

**Status:** written 2026-10-01 and sealed with RFC 3161 timestamps (`holdout-audit seal-doc`, DigiCert + FreeTSA)
**before the True Market Mean, the AVIV ratio, liveliness, the Thermocap or the Investor Cap has been computed by
Holdout Labs.** Run once after the seal. Public study; results published whatever they show.

## 1. The claims (primary source)

Check, J. & Puell, D. (23 August 2023), *Cointime Economics: A New Framework for Bitcoin On-chain Analysis*,
Glassnode and ARK Invest, chapter 6:

- **Definition.** True Market Mean (Active-Investor Price) = Investor Cap / Active Supply, where Investor Cap =
  Realized Cap − Thermocap, Active Supply = Liveliness × Circulating Supply, and Liveliness = cumulative coinblocks
  destroyed / cumulative coinblocks created. AVIV ratio = price / True Market Mean (equivalently Active Cap /
  Investor Cap).
- **Claim M (mean reversion).** The True Market Mean is "a likely reference point for mean reversion models".
- **Claim R (regime).** AVIV "oscillate[s] around a value of 1.0", with "transitions between cyclical bull and bear
  markets being more responsive than other MVRV variants".

Out-of-sample window for every test: **2023-08-24** (the day after publication) **to 2026-09-24** (the last day of the
ONCHAIN-1 data). Before-publication values are reported for context only.

## 2. Data and construction (no vendor metric is loaded)

Inputs are the ONCHAIN-1 daily series (`samples/onchain1/bq/metrics_daily.csv`, built from the public Bitcoin
blockchain in Google BigQuery and the sealed BTC price series; method in `bq/METHOD.md`): `supply_btc`,
`realized_cap_usd`, `cdd` (coin-days destroyed, value × exact lifespan in days) and the daily close.

- **Coin-days, not coinblocks (stated simplification).** Coin-days created on day d = supply_btc(d) × 1 day;
  coin-days destroyed = `cdd`. Liveliness(d) = Σ cdd / Σ supply_btc over all days up to d, from the first day of the
  series. Blocks average about 10 minutes, so the ratio of the two cumulative sums is close to the coinblock version.
- **Thermocap (stated simplification).** Thermocap(d) = Σ over days up to d of (supply_btc(t) − supply_btc(t−1)) ×
  close(t): newly minted coins valued at that day's close (the paper values them at the block's price; fees are not
  included, matching "coins … mined … valued at the pricestamp of the block … when they were minted"). Days with no
  price contribute zero, as coins without a market price carry zero cost in our realized cap.
- **Investor Cap** = realized_cap_usd − Thermocap. **Active Supply** = Liveliness × supply_btc.
  **TMM** = Investor Cap / Active Supply. **AVIV** = close / TMM.
- **Cross-check before any test** (fixed now): compare TMM with publicly quoted True Market Mean values (prose in
  research notes and news articles; no vendor files downloaded) at dates spread over 2023-2026. If the median absolute
  difference exceeds 5%, we investigate and log a dated deviation **before** running §3. Vendor figures may use
  coinblocks and block-level prices, so differences of a few percent are expected.

## 3. Tests (all frozen here; nothing is tuned)

Code: `samples/onchain1/run.py` functions `episodes`, `fwd`, `zone_test`, `holm` and the `strategy_audit` pattern of
`run_family_b.py`, reused unchanged, with the same price series, 30-day episode merge gap and 10 bps costs.

| ID | Claim | Rule (frozen) | Statistic | Horizon |
|---|---|---|---|---|
| **M1** | Mean reversion, below the mean | zone = AVIV < 1.0 (price below the True Market Mean) | `zone_test`: forward log return after zone days vs all days, direction +1 (higher) | 90 days |
| **M2** | Mean reversion, far above the mean | zone = AVIV ≥ 1.5 | `zone_test`, direction −1 (lower) | 90 days |
| **R1** | Regime line | hold BTC when close(t) > TMM(t), cash otherwise; decided at close t, held to close t+1 | strategy audit, rubric v1.1, objective (a) beat buy-and-hold BTC, 10 bps per unit turnover, N = 1, default holdout | daily |

- **Inference.** At least 5 independent episodes in the out-of-sample window are needed for a p-value (ONCHAIN-1
  rule); fewer → **NOT TESTABLE (descriptive only)**, entered into Holm with p = 1. Holm family = {M1, M2}. R1 is
  graded by the rubric. The 1.5 band for M2 is our choice (the paper gives no upper band); it is fixed here before any
  AVIV value is seen, and it is reported as our threshold, not the authors'.
- **Responsiveness (descriptive, no p-value).** For each cycle top and bottom in the window (ONCHAIN-1 definition:
  all-time-high close followed by a fall of at least 50%; bottom = lowest close between tops), the nearest crossing of
  AVIV = 1, MVRV = 1 and close = STH cost basis, in days. "More responsive" = AVIV crosses closer to the turning point.
- **Descriptive check of the paper's own statistic.** Share of days with AVIV > 1 (paper: 53.3% to 8 May 2023),
  before and after publication.

## 4. Honesty notes (stated before the run)

- **Not blind.** BTC prices, realized cap, CDD, supply, MVRV and STH cost basis were computed and seen in ONCHAIN-1,
  and the True Market Mean is published on public charts we may have glanced at. The protection here is that every
  rule is the authors' own published construction, frozen before we compute it, and run once.
- **Low power expected.** About three years after publication; few episodes are likely, so "NOT TESTABLE" is a
  possible, honest outcome.
- **Right of reply.** We will show the frozen rules to James Check publicly before the run and invite corrections to
  how we read the paper. A correction that arrives before the run is logged as a dated deviation (with the reason)
  before any value is computed; nothing changes after.
- **Not advice.** Statistics on past data. Holdout Labs has no position in this test's outcome; the founder's
  personal-trading policy applies (30-day blackout around publication).
