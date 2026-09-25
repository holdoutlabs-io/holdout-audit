"""Writes samples/batch1/prereg/batch1-preregistration.json (run once, before sealing; kept for transparency)."""

import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import batch1_strategies as B  # noqa: E402

now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
TVKB = "https://www.tradingview.com/support/folders/43000587405-technical-indicators/"
PINE = "https://www.tradingview.com/pine-script-reference/v5/"
RULES = {
    "supertrend": ("Supertrend Strategy",
                   "ta.supertrend(factor, atrPeriod) on hl2 with Wilder ATR; long when the direction turns up, short when it turns down (market orders).",
                   "atrPeriod 10, factor 3"),
    "macd": ("MACD Strategy",
             "MACD = EMA(close, fast) - EMA(close, slow); delta = MACD - EMA(MACD, signal); long on crossover(delta, 0), short on crossunder(delta, 0) (market orders).",
             "fast 12, slow 26, signal 9"),
    "rsi": ("RSI Strategy",
            "RSI(close, length) (Wilder); long on crossover(RSI, oversold), short on crossunder(RSI, overbought) (market orders).",
            "length 14, oversold 30, overbought 70"),
    "bollinger": ("Bollinger Bands Strategy",
                  "basis = SMA(close, length), dev = mult x population stdev; long stop entry at the lower band after close crosses above it; short stop entry at the upper band after close crosses below it. Port: enter at the signal close.",
                  "length 20, mult 2.0"),
    "ma_cross": ("MovingAvg2Line Cross",
                 "SMA(close, fast) crossing over / under SMA(close, slow): long / short (market orders).",
                 "fast 9, slow 18"),
    "psar": ("Parabolic SAR Strategy",
             "Wilder parabolic SAR state machine (start, increment, maximum) with stop-and-reverse stop orders at the next bar's SAR. Port: the position equals the SAR trend at the close.",
             "start 0.02, increment 0.02, maximum 0.2"),
    "stochastic": ("Stochastic Slow Strategy",
                   "k = SMA(stoch(close, high, low, length), 3), d = SMA(k, 3); long on crossover(k, d) with k < oversold, short on crossunder(k, d) with k > overbought (market orders).",
                   "length 14, smoothK 3, smoothD 3, oversold 20, overbought 80"),
    "channel_breakout": ("Channel BreakOut Strategy",
                         "stop entries at the highest high / lowest low of the last `length` bars. Port: long when the bar's high exceeds the prior bar's channel high, short when its low breaks the prior channel low (if both, the close vs the channel midpoint decides); entry at the signal close.",
                         "length 5"),
    "keltner": ("Keltner Channels Strategy",
                "EMA(close, length) +/- mult x ATR(atrLength); long stop entry after close crosses above the upper band, short stop entry after close crosses below the lower band. Port: enter at the signal close; the built-in's cancellation of a pending stop when price falls back inside the band is not modelled.",
                "length 20, mult 2.0, EMA basis, ATR bands, ATR length 10"),
    "momentum": ("Momentum Strategy",
                 "mom0 = close - close[length], mom1 = mom0 - mom0[1]; long stop entry when both > 0, short stop entry when both < 0. Port: enter at the signal close.",
                 "length 12"),
}


def main():
    strategies = []
    for k, (tv, rule, dflt) in RULES.items():
        grid = {g: [list(v) if isinstance(v, tuple) else v for v in vals] for g, vals in B.STRATEGIES[k]["grid"].items()}
        strategies.append({"key": k, "tradingview_builtin_name": tv, "rule": rule, "defaults_as_shipped": dflt,
                           "long_short_as_shipped": "stop-and-reverse: always long or short after the first signal",
                           "audited_variant": B.default_label(k), "variant_grid": {**grid, "mode": list(B.MODES)},
                           "n_variants": B.n_variants(k)})
    doc = {
        "objective": "beat_benchmark",
        "max_return_shortfall_annual": None,
        "benchmark": "buy-and-hold of the same asset (SPY total return incl. dividends; BTC-USD close to close)",
        "declared_at_utc": now,
        "declared_by": "holdout-labs-batch-1",
        "title": "Holdout Labs Indicator Audit, Batch 1: ten TradingView built-in strategies x {SPY, BTC} = 20 audits",
        "written_at_utc": now,
        "rubric": "Holdout Labs Fragility Rubric v1.1 (docs/RUBRIC-v1.1.md, SHA-256 2311b126336bab9f426a84f9c9cd9cb937e346b403a62f60e3c96ed8b5868e46), objective (a) beat buy-and-hold of the same asset, for every audit.",
        "selection_of_the_ten": {
            "rule": "TradingView built-in strategies (the Pine Editor's built-in library) for the most widely known indicators, audited with the settings they ship with.",
            "public_evidence": [
                "TradingView Help Center, 'Technical indicators' folder: lists Supertrend, MACD, RSI, Bollinger Bands, Parabolic SAR, Stochastic, Ichimoku Cloud, Donchian Channels, Keltner Channels, Momentum and Moving Averages as built-in indicators (" + TVKB + "), checked 2026-09-25.",
                "Pine Script v5 reference for the ta.* functions ported (" + PINE + ")."],
            "limits_of_the_evidence": "We could not obtain quantitative popularity data: usage counts are not published on TradingView's script pages, and our web-search budget was exhausted. The strategies' Pine source is visible in TradingView's Pine Editor but has no public URL; the ports follow that built-in logic and the Pine reference. Ichimoku Cloud was a candidate but is excluded because TradingView ships no built-in Ichimoku strategy (to our knowledge; not verified from a public page). Donchian breakout is represented by the built-in 'Channel BreakOut Strategy', and the EMA/MA cross by the built-in 'MovingAvg2Line Cross' (SMA)."},
        "strategies": strategies,
        "assets": {
            "SPY": {"data": "Yahoo Finance public chart endpoint, daily OHLC (unadjusted) + dividends, fetched by samples/data/fetch.py into samples/data/raw/spy_ohlc_daily_yahoo.csv AFTER this document is sealed; SHA-256 recorded in MANIFEST.json and printed in each report.",
                    "audit_period": "1994-01-03 to 2026-09-24", "holdout_split": "2017-01-03", "periods_per_year": 252,
                    "cost_bps_per_unit_turnover": 2.0},
            "BTC": {"data": "Coinbase Exchange public candles API, daily UTC OHLC: the file already fetched for sample audit 4 (samples/data/raw/btc_ohlc_daily.csv, SHA-256 59824cab0b610717f0ea82fdb748df98d81849aeaaac3fe62452a3d8043ac775, fetched 2026-09-25T15:34:16Z), reused unchanged.",
                    "audit_period": "2015-09-01 to 2026-09-24", "holdout_split": "2023-06-01", "periods_per_year": 365,
                    "cost_bps_per_unit_turnover": 10.0}},
        "btc_supertrend": "Already audited as sample 4 under its own sealed preregistration (seal record 87c73803cae076ec7d19ac2bdd2f423c39588e9780dd61b0c092731bb94c209c) with the identical grid, data, period, holdout and costs. It is NOT re-run; its result (grade F, Hansen SPA p 1.000) enters this batch as one of the 20.",
        "execution_convention": "Signal at the daily close t, position held close t to close t+1; stop entries treated as filled at the signal close; position 0 before the first signal; long_flat maps shorts to flat. Short-side borrow/funding costs are not modelled. These differ from TradingView's broker emulator (next-open market fills, intrabar stop fills) and are stated in every report.",
        "settings": {"bootstrap_draws": 1000, "cscv_blocks": 16, "seed": 20260925,
                     "declared_n_trials": "equal to n_variants of each strategy"},
        "batch_level_inference": {
            "primary_statistic": "each audit's Hansen SPA consistent p-value (best variant of the preregistered family vs buy-and-hold of the same asset, stationary bootstrap).",
            "multiplicity": "Holm step-down correction across all 20 audits at family-wise alpha 0.05.",
            "survives": "An audit survives only if its Holm-adjusted SPA p <= 0.05. No strategy will be described as beating buy-and-hold unless it survives. The rubric v1.1 grade is reported for every audit regardless."},
        "publication_commitment": "All 20 results are published in samples/batch1/ and on holdoutlabs.io/audits/batch-1/, pass or fail, with every report, the summary table and this preregistration. No audit will be dropped, re-run with different settings, or re-graded under another objective.",
        "prior_exposure": "The auditors have already seen SPY and BTC prices and results in sample audits 1-4 (golden cross, RSI(2) mean reversion and 50-day SMA trend on SPY/BTC; Supertrend on BTC). None of the other nine strategies in this batch has been run by us on SPY or BTC data before this seal; the ports were tested on synthetic data only.",
        "deviations": "Any deviation from this document will be listed on the summary page and in the affected reports.",
    }
    out = HERE / "prereg" / "batch1-preregistration.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(out, sum(s["n_variants"] for s in strategies), now)


if __name__ == "__main__":
    main()
