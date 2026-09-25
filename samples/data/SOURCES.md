# Sample data: sources, licences and hashes

Raw vendor data is **not committed**. `fetch.py` downloads it into `samples/data/raw/` (git-ignored) and checks the SHA-256 of the normalised files against `MANIFEST.json`. The reports' data-hash appendix repeats the hashes.

**Instrument policy:** sample audits use equity indices, equity ETFs, bond ETFs and BTC (see `fetch.py`). No commodity, grain, soft, oil, metal, gold or silver data, and no astronomical, lunar or astrological features, appear anywhere in this repository. `fetch.py` asserts its symbols against an allow-list.

| File | Instrument | Source | Terms / licence (as understood 2026-09-25) | Committed? |
|---|---|---|---|---|
| `spy_daily_stooq.csv` (option) | SPY daily | stooq.com CSV, downloaded manually in a browser from https://stooq.com/q/d/l/?s=spy.us&i=d (header `Date,Open,High,Low,Close,Volume`) and passed with `--spy-file` | Stooq offers free downloads. Its terms page does not grant redistribution, so treat it as personal use and do not commit the raw file. Automated download now sits behind a JavaScript bot check, which this project does not attempt to bypass. | No |
| `spy_daily_yahoo.csv` (**official source for published samples**, adopted 2026-09-25) | SPY (SPDR S&P 500 ETF), daily close and dividends, 1993-01-29 to 2026-09-24 | Yahoo Finance public chart endpoint (`query1.finance.yahoo.com/v8/finance/chart/SPY`), no key | The Yahoo terms of service cover personal, non-commercial use and do not grant redistribution. **We redistribute nothing.** The reports publish derived statistics and charts only. The owner chose this source on 2026-09-25 because Stooq downloads were blocked. Policy: prices from Yahoo Finance's public chart endpoint; we publish derived statistics only, never raw prices; no redistribution. | No. Script and hash only |
| `btc_daily.csv` | BTC-USD daily close (UTC), 2015-07-20 to 2026-09-24 | Coinbase Exchange public market-data API (`api.exchange.coinbase.com/products/BTC-USD/candles`, granularity 86400), no key | Public market data under Coinbase's API and user terms. These do not grant bulk redistribution, so the raw file is not committed. **Owner action:** confirm that publishing derived statistics is acceptable. | No. Script and hash only |

## Reproducing

```bash
uv run python samples/data/fetch.py            # downloads, writes raw/, checks MANIFEST.json
uv run python samples/run_all.py               # fetch-if-missing + all three audits
uv run python samples/data/fetch.py --spy-file ~/Downloads/spy_us_d.csv --force   # Stooq route
```

A hash mismatch prints a warning and exits with status 2. It does not fail silently. Vendors occasionally revise history, and Yahoo's dividend records can change. If the hashes differ, the statistics may differ in the last decimals.

## Normalised format

`date,close,dividend`: ISO date, unadjusted close, and the cash dividend paid that day (0 for BTC). Total return is computed in `samples/strategies.py` as `(close + dividend) / previous close - 1`.
