# On-chain Indicator Audit, Batch 1: data-licence decision

**Recorded:** 2026-09-25 (UTC), before the preregistration was sealed and before any on-chain value series was accessed by this study.
**Question:** which data sources' terms permit publishing derived statistics on a commercial website (holdoutlabs)?
**Rule applied:** if no permissive source exists for a metric, the metric is not run for publication. Nothing is published under non-commercial terms.

## Evidence (terms pages fetched 2026-09-25)

| Source | Relevant terms (quoted) | Commercial publication of derived statistics? |
|---|---|---|
| **BGeometrics / bitcoin-data.com free API** (terms at https://charts.bgeometrics.com/terms.html, last updated 2026-02-24) | "All charts published on BGeometrics are provided free of charge for personal, educational, and non-commercial use." "Any platform, application, or service that delivers BGeometrics API data to end users — directly or as part of a larger product — is classified as commercial redistribution and requires the Professional plan." Prohibited: "Resell, sublicense, or redistribute API access or data to third parties — directly or as part of a product or service — without a Professional plan or an explicit commercial agreement with BGeometrics." | **No** on the free tier. Needs the Professional plan or a written commercial agreement. |
| **Coin Metrics Community** (https://github.com/coinmetrics/data, README and LICENSE) | "Data is made available under the CC BY-NC 4.0 license." LICENSE: "licensed under the Creative Commons Attribution-NonCommercial 4.0 International License." | **No.** NonCommercial. A commercial audit business's use, even internally for marketing research, is "directed towards commercial advantage". Not used at all. |
| **Bitcoin Magazine Pro / LookIntoBitcoin API** (https://www.lookintobitcoin.com/api/) | Professional plan is "For personal use"; "Enterprise License — For commercial products and services, the platform offers annual licensing. Pricing depends on your stage and use case." The full terms-of-use page did not render its text to our fetcher. | **No** without an Enterprise licence. Chart pages were used only for the *definitions and creation dates* of indicators (facts, not data). |
| **Glassnode** | Advanced tier ($49/mo): personal-use licence; Professional: custom licence options (from an internal research scan). The public terms URLs tried (`/terms`, `/terms-and-conditions`) returned 404 on 2026-09-25. | **No** without a written Professional/custom licence. |
| **Bitcoin P2P network** (public full nodes, protocol messages `version`/`getheaders`) | No terms of service: the block-header chain is the public consensus record, fetched peer-to-peer from nodes found via the standard DNS seeds. Every header is checked for its prev-hash link and its proof-of-work target. | **Yes.** Block heights and timestamps are facts computed by us from the public blockchain. |
| **Coinbase Exchange public candles API** (BTC-USD daily) | Already used for published samples 3 and 4 under the policy "derived statistics only, never raw prices, no redistribution" (`samples/README.md`). | **Yes, on the same basis as samples 3–4** (derived statistics only). |
| mempool.space public API (considered, not used) | Docs suggest "an enterprise sponsorship if you need higher API limits"; its terms page did not render text to our fetcher. | Not needed: the P2P path covers block headers. |

## Decision per metric

| Metric | Needs | Source decision | Status in Batch 1 |
|---|---|---|---|
| Pi Cycle Top | BTC price only | Coinbase (derived only) | **Run, publishable** |
| 200-week MA heatmap (bottom claim) | BTC price only | Coinbase (derived only) | **Run, publishable** |
| Mayer Multiple | BTC price only | Coinbase (derived only) | **Run, publishable** |
| 2-Year MA Multiplier | BTC price only | Coinbase (derived only) | **Run, publishable** |
| Puell Multiple | daily issuance (block headers + consensus subsidy) × price | **Self-computed** from P2P block headers + Coinbase | **Run, publishable** |
| Stock-to-flow (PlanB 2019) | supply and annual issuance (block headers) | **Self-computed** from P2P block headers | **Run, publishable** |
| MVRV-Z | realized cap (full UTXO history) | No permissive source; self-computing needs a full-chain UTXO replay (~650 GB of blocks), not feasible in this batch | **Rule sealed; NOT RUN — pending licence or own UTXO pipeline** |
| NUPL | realized cap | as above | **Sealed; NOT RUN** |
| SOPR | spent-output cost basis | as above | **Sealed; NOT RUN** |
| Reserve Risk | coin-days destroyed (UTXO ages) | as above | **Sealed; NOT RUN** |
| STH cost basis / realized price (155-day cohort) | UTXO ages and cost basis | as above | **Sealed; NOT RUN** |
| Realized price | realized cap | as above | **Sealed; NOT RUN** |

**Consequence.** Batch 1 publishes six indicators: four are price-derived dashboard staples and two (Puell, stock-to-flow) are genuinely on-chain, computed by us from block headers. The six UTXO-based metrics are preregistered and sealed now, so their rules cannot drift, but they are **not run** until either a commercial licence is signed in writing (BGeometrics Professional, Bitcoin Magazine Pro Enterprise, Glassnode Professional or Coin Metrics) or we build our own UTXO replay. We did not load any of their values.

**Not loaded at all (LRI lock, `research/leverage-risk/lock/`):** funding rates, open interest, basis, liquidations, estimated leverage.
