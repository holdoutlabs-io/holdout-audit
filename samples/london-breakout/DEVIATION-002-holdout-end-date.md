# LB-1 DEVIATION-002: the holdout ends at 2026-09-24 19:58 (UTC-5), not 2026-09-25 23:59

**Date:** 2026-09-28. Written after Stage B ran and before any result was published (PREREG §10).
Sealed with `holdout-audit seal-doc`.

**What PREREG says.** §5.2: the locked holdout runs 2024-01-01 to 2026-09-25 (monthly files 2026-01 to 2026-09);
"if the September 2026 file is not yet published at download, the holdout ends at the last complete month available.
This is recorded as a deviation."

**What happened.** The September 2026 file *was* published, but it is a partial month. Downloaded 2026-09-28
(`MANIFEST.json`, period `2026/9`), its last bar is **2026-09-24 19:58** on the fixed UTC-5 clock. Friday 2026-09-25
is absent from the vendor file. HistData labelled the file ".Zip with Full Month Data" on its listing page.

**Handling (no choice made on results).**
- We used the September file as published, with every bar up to its last one. `lb_data.load_real("B")` keeps bars
  up to 2026-09-25 23:59, which is all of them. We did not truncate to the "last complete month" (August 2026).
  PREREG gives that rule only for a file that is not published, and the file here is published.
  So the holdout has **714 weekday rows** (2024-01-01 to 2026-09-24). With no bars, 2026-09-25 is not a row
  (PREREG §4.2, §10).
- We fetched no other source for 2026-09-25 and filled no bars.
- **Impact.** One trading day out of about 715 in the holdout. The file was observed at download, before Stage B ran.
  No alternative end date was computed or compared.
- **Disclosure.** Truncating to August 2026 was not run, and will not be reported.

Nothing else changes: P2, Holm and the verdict are computed by the sealed `run.py` on the data as loaded.
