"""Reproduce the three public sample audits with one command:

    uv run python samples/run_all.py

Fetches the data if missing (samples/data/fetch.py), checks the hashes against
samples/data/MANIFEST.json, runs each audit and writes samples/reports/*.html plus
samples/reports/summary.json. Statistical illustrations only; not investment advice.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "data"))

import fetch  # noqa: E402
import strategies as S  # noqa: E402

from holdout_audit import AuditConfig, run_audit  # noqa: E402
from holdout_audit.report import write_report  # noqa: E402

REPORTS = HERE / "reports"
SEED = 20260925
# Published samples are v1.0 reports (objective a, "beat the benchmark"). They are reproduced under v1.0,
# never re-graded: see samples/README.md.
SAMPLE_RUBRIC = "1.0"


def _net(frames: dict[str, pd.DataFrame], cost_bps: float, start) -> pd.DataFrame:
    return pd.DataFrame({k: (v["return"] - v["turnover"] * cost_bps / 1e4).loc[start:] for k, v in frames.items()})


def _sharpe(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / x.std(ddof=1)) if x.std(ddof=1) > 0 else 0.0


USE_STOOQ = False  # set by --spy-file; Yahoo is the official source for the published samples


def spy_source() -> str:
    """Yahoo Finance is the official SPY source for published samples; a Stooq file is an option (--spy-file)."""
    return "spy_daily_stooq.csv" if USE_STOOQ else "spy_daily_yahoo.csv"


def _notes(name: str, extra: list[str]) -> list[str]:
    man = json.loads(fetch.MANIFEST.read_text())
    rec = man[name]
    src = {
        "Yahoo Finance chart endpoint": "Prices from Yahoo Finance's public chart endpoint; we publish derived statistics only, never raw prices; no redistribution. SPY daily closes and dividends; total return computed "
                                        "locally as (close + dividend) / previous close - 1.",
        "stooq.com (manual download)": "SPY daily closes from a stooq.com CSV downloaded by hand by the operator "
                                       "(https://stooq.com/q/d/l/?s=spy.us&i=d); closes used as given, dividend "
                                       "column 0; not redistributed.",
        "Coinbase Exchange public candles API (OHLC)": "Prices from the Coinbase Exchange public market-data API; we "
                                                       "publish derived statistics only, never raw prices; no "
                                                       "redistribution. BTC-USD daily open/high/low/close (UTC).",
        "Coinbase Exchange public candles API": "Prices from the Coinbase Exchange public market-data API; we publish "
                                                "derived statistics only, never raw prices; no redistribution. BTC-USD "
                                                "daily closes (UTC).",
    }[rec["source"]]
    out = [src, f"Normalised file {name}: {rec['rows']} rows ending {rec['end']}, SHA-256 {rec['sha256']}."]
    return out + extra


def golden_cross(px: pd.DataFrame) -> AuditConfig:
    grid = S.golden_cross_grid(px)
    start = px.index[max(S.GC_SLOW)]  # every variant has a full slow SMA from here
    cost = 2.0
    variants = _net(grid, cost, start)
    chosen = "fast=50|slow=200"
    df = grid[chosen].loc[start:].assign(market=px["tr"].loc[start:])
    return AuditConfig(
        name="Sample audit 1: SPY 50/200-day golden cross",
        description="Long SPY while the 50-day simple moving average is above the 200-day, otherwise flat (cash at 0%). "
                    "Benchmark: buy-and-hold SPY (total return), the rubric v1.0 default.",
        rules="Signal at the close of day t: long if SMA50 > SMA200 else flat; position held over day t+1. "
              f"Family audited: fast {S.GC_FAST} x slow {S.GC_SLOW} (fast < slow), 24 variants; the chosen 50/200 "
              "is the textbook rule, not the best cell.",
        returns=df, variants=variants, chosen_variant=chosen, n_trials=variants.shape[1], base_cost_bps=cost,
        seed=SEED, rubric_version=SAMPLE_RUBRIC, periods_per_year=252,
        data_files={spy_source(): fetch.RAW / spy_source()},
        data_notes=_notes(spy_source(), [f"Audit starts {start.date()} so every variant's 300-day warm-up is complete "
                                         "(price data from 1993-01-29)."]),
    )


def rsi2(px: pd.DataFrame) -> tuple[AuditConfig, dict]:
    grid = S.rsi_grid(px)
    start = px.index[220]
    cost = 2.0
    variants = _net(grid, cost, start)
    split = variants.index[int(len(variants) * 0.7)]
    is_sr = {c: _sharpe(variants.loc[:split, c].iloc[:-1]) for c in variants}
    chosen = max(is_sr, key=is_sr.get)
    df = grid[chosen].loc[start:].assign(market=px["tr"].loc[start:])
    cfg = AuditConfig(
        name="Sample audit 2: RSI(2) mean reversion on SPY",
        description="Connors-style short-term mean reversion on SPY. The audited variant is the one with the best "
                    f"in-sample Sharpe out of {variants.shape[1]} grid variants, exactly as a trader optimising a grid "
                    "would pick it; the last 30% of the sample was held out from that choice. "
                    "Benchmark: buy-and-hold SPY (total return), the rubric v1.0 default.",
        rules=f"Chosen: {chosen}. Enter long at the close when RSI(n) < entry (with trend=on, also close > SMA200); "
              "exit at the close when close > SMA(exit). Grid: RSI length (2, 3, 4) x entry (5, 10, 15, 20, 25) x exit "
              "SMA (5, 10) x trend filter (on, off) = 60 variants.",
        returns=df, variants=variants, chosen_variant=chosen, n_trials=variants.shape[1], base_cost_bps=cost,
        seed=SEED, rubric_version=SAMPLE_RUBRIC, periods_per_year=252, holdout_split=str(split.date()),
        data_files={spy_source(): fetch.RAW / spy_source()},
        data_notes=_notes(spy_source(), [f"Audit starts {start.date()} after the 200-day SMA warm-up.",
                                         f"Variant chosen on data before {split.date()} only."]),
    )
    return cfg, {"chosen_by_in_sample_sharpe": chosen, "in_sample_sharpe_annual": is_sr[chosen] * math.sqrt(252)}


def btc(px: pd.DataFrame) -> AuditConfig:
    grid = S.btc_grid(px)
    start = px.index[max(S.BTC_LOOKBACK) + 1]
    cost = 10.0
    variants = _net(grid, cost, start)
    chosen = "signal=sma|lookback=50"
    df = grid[chosen].loc[start:].assign(market=px["tr"].loc[start:])
    return AuditConfig(
        name="Sample audit 3: BTC 50-day moving-average trend",
        description="Long BTC-USD while the daily close is above its 50-day simple moving average, otherwise flat. "
                    "Seven-day calendar, 365 periods a year. Benchmark: buy-and-hold BTC, the rubric v1.0 default.",
        rules="Signal at the UTC daily close: long if close > SMA50 else flat; held over the next day. Family audited: "
              f"signal (price above SMA, or rate of change > 0) x lookback {S.BTC_LOOKBACK} = 14 variants. The "
              "SMA-50 was fixed as a common default before any results were seen; it turned out to be the best "
              "cell over the full sample, which the parameter-surface section reports.",
        returns=df, variants=variants, chosen_variant=chosen, n_trials=variants.shape[1], base_cost_bps=cost,
        seed=SEED, rubric_version=SAMPLE_RUBRIC, periods_per_year=365,
        data_files={"btc_daily.csv": fetch.RAW / "btc_daily.csv"},
        data_notes=_notes("btc_daily.csv", [f"Audit starts {start.date()} after the 200-day warm-up "
                                            "(Coinbase daily history begins 2015-07-20)."]),
    )


PREREG4 = HERE / "prereg" / "04-btc-supertrend"


def btc_supertrend(px: pd.DataFrame) -> AuditConfig:
    """Sample 4, exactly as preregistered and sealed in samples/prereg/04-btc-supertrend/ (rubric v1.1)."""
    grid = S.supertrend_grid(px)
    start, end = "2015-09-01", "2026-09-24"
    cost = 10.0
    variants = _net(grid, cost, start).loc[:end]
    chosen = "atr=10|mult=3|mode=long_short"
    df = grid[chosen].loc[start:end].assign(market=px["tr"].loc[start:end])
    man = json.loads(fetch.MANIFEST.read_text())
    return AuditConfig(
        name="Sample audit 4: TradingView Supertrend Strategy (ATR 10, factor 3) on BTC",
        description="TradingView's built-in 'Supertrend Strategy' with its default settings on BTC-USD daily bars: long in "
                    "an uptrend, short in a downtrend. Benchmark: buy-and-hold BTC. Objective (a), declared and sealed "
                    "before the data were fetched; protocol preregistered and sealed before any run.",
        rules="Pine ta.supertrend(3, 10) on daily OHLC (hl2 bands, Wilder ATR). Position set at the UTC close and held to "
              "the next close: +1 in an uptrend, -1 in a downtrend (TradingView fills at the next open; we use close to "
              "close). Grid: ATR 7/10/14 x factor 2/2.5/3/3.5/4 x long-short/long-flat = 30 variants. Short-side funding "
              "costs are not modelled.",
        returns=df, variants=variants, chosen_variant=chosen, n_trials=30, base_cost_bps=cost, seed=SEED,
        rubric_version="1.1", periods_per_year=365, holdout_split="2023-06-01",
        declaration_file=str(PREREG4 / "declaration.json"), declaration_seal_dir=str(PREREG4 / "declaration-seal"),
        preregistration_file=str(PREREG4 / "preregistration.json"),
        preregistration_seal_dir=str(PREREG4 / "preregistration-seal"),
        data_received_utc=man["btc_ohlc_daily.csv"]["recorded_utc"],
        data_files={"btc_ohlc_daily.csv": fetch.RAW / "btc_ohlc_daily.csv"},
        data_notes=_notes("btc_ohlc_daily.csv", ["Audit period 2015-09-01 to 2026-09-24; holdout from 2023-06-01 "
                                                 "(both fixed in the sealed preregistration)."]),
    )


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spy-file", help="optional: a stooq.com SPY daily CSV downloaded by hand, used instead of Yahoo")
    a = ap.parse_args(argv)
    global USE_STOOQ
    USE_STOOQ = bool(a.spy_file)
    fetch.main(["--spy-file", a.spy_file] if a.spy_file else [])
    spy = S.load_prices(fetch.RAW / spy_source())
    btcpx = S.load_prices(fetch.RAW / "btc_daily.csv")
    REPORTS.mkdir(exist_ok=True)
    summary = {}
    rsi_cfg, rsi_extra = rsi2(spy)
    jobs = [("01-spy-golden-cross", golden_cross(spy), {}), ("02-spy-rsi2", rsi_cfg, rsi_extra),
            ("03-btc-sma50", btc(btcpx), {}),
            ("04-btc-supertrend", btc_supertrend(S.load_prices(fetch.RAW / "btc_ohlc_daily.csv")), {})]
    for slug, cfg, extra in jobs:
        print(f"auditing {slug} ...", flush=True)
        res = run_audit(cfg)
        write_report(res, REPORTS / f"{slug}.html")
        head = res.headline() | extra | {"checks": {c.key: c.status for c in res.grade.checks},
                                          "spy_source": spy_source() if "spy" in slug else None,
                                          "rubric_seal_sha256": res.rubric["seal_sha256"]}
        # DSR if the trader had (falsely) declared a single trial: the variant-count effect.
        head["dsr_if_n_1"] = round(next(d for n, d, _ in res.dsr_curve if n == 1), 4)
        summary[slug] = head
        print(json.dumps(head, indent=2))
    (REPORTS / "summary.json").write_bytes((json.dumps(summary, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
