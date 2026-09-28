# Upstream source (vendored, unmodified)

`London Breakout backtest.py` is copied byte-for-byte from
https://github.com/je-suis-tm/quant-trading at commit
`611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5` (repository HEAD on 2026-09-28; the file's
last change is commit `82e748f530e2233e4bb21a7943698df79f1086f0`, 2019-03-13, "change link").

| File | SHA-256 |
|---|---|
| `London Breakout backtest.py` | `8b5a0f672c2c5a44fb5a72564fcb0b20a5bd2b0d3d9da3e2f4a52b2d047f8e3a` |
| `LICENSE` (Apache License 2.0, from the same commit) | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |

Copyright the quant-trading author (GitHub user je-suis-tm), licensed under the Apache License,
Version 2.0 (see `LICENSE`). Holdout Labs has not modified this file. `../lb_original.py` executes
lines 51–211 of it (the functions `london_breakout` and `signal_generation`) so that the tests
compare our port against the author's own code, not against our reading of it. The lines it skips
are the `os.chdir('d:/')` at import time, the plotting and `main()`; none of them affects the signals.

The repository also contains `data/gbpusd.csv` (806,145 bytes, git blob
`4ad13ffc1051da65e6d6e7aa34e006acf2c048c2`, added 2022-12-05). **It has not been opened** by this
study. It is used once, after sealing, for the reproduction check in PREREG §5.4.
