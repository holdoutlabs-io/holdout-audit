# COINTIME-1 §2 cross-check: public quotes, and the comparison rule

Written on 2026-10-05, **before** any True Market Mean (TMM) or AVIV value was computed by Holdout Labs. No vendor file was downloaded: these are figures quoted in the prose of research notes and news articles, as PREREG §2 requires.

## Rule (fixed before computing)

1. **Primary set:** quotes labelled "True Market Mean" or "True Market Mean Price".
   - The comparison date is the date the source gives for the value; if none is given, the publication date.
   - When one source gives two values for the same date, use their midpoint.
   - Gate (PREREG §2): if the median absolute percentage difference between our TMM and the primary set exceeds 5%, we investigate and log a dated deviation before §3 runs.
2. **Context set:** quotes labelled "Active Investor Price" or "active investors' realized price".
   - These are reported but do not enter the gate.
   - The paper says the two names mean the same metric. But one source (Glassnode, 2024-10-08) quotes them side by side as different numbers ($47k vs $52.5k), so the labels are ambiguous in public use.
3. Vendor figures may use coinblocks and block-level prices, while ours uses coin-days and daily closes (PREREG §2). Differences of a few percent are expected and are not tuned away.

## Primary set (True Market Mean)

| # | Value date | Quoted value | Source |
|---|---|---|---|
| P1 | 2023-01-01 | $28,659 | CryptoSlate, "Realized price and true market mean…", 2023-12-21 ("increased from $28,659 on Jan. 1, 2023, to $31,896 on Dec. 20, 2023") |
| P2 | 2023-10-10 | $29,720 | CryptoSlate, "Active investor price: a fresh perspective…", 2023-10-10 ("notably below the True Market Mean Price of $29,720"; AVIV 0.928 at about $27,590) |
| P3 | 2023-12-20 | $31,896 | CryptoSlate, 2023-12-21 (as P1) |
| P4 | 2024-10-08 | $47,000 | Glassnode, The Week On-chain week 41-2024 ("the True-Market Mean ($47k) and the Active Investor Price ($52.5k)") |
| P5 | 2025-12-10 | $81,300 | Glassnode, week 49-2025 ("the True Market Mean at $81.3k") |
| P6 | 2026-02-18 | $79,000 | Glassnode, week 07-2026 ("the True Market Mean (~$79k)") |
| P7 | 2026-04-29 | $78,500 | Glassnode, week 17-2026: "(~$79k)" and "at $78k" in the same report; midpoint per rule 1 |
| P8 | 2026-09-16 | $76,700 | Glassnode, week 37-2026 ("the True Market Mean at $76.7K") |

## Context set (Active Investor Price)

| # | Value date | Quoted value | Source |
|---|---|---|---|
| C1 | 2024-10-08 | $52,500 | Glassnode, week 41-2024 (as P4) |
| C2 | 2025-10-30 | $88,000 | CoinDesk, 2025-10-30 ("the current active investors' realized price") |
