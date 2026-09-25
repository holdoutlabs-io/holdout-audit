"""Indicator Audit, Batch 1: run the 20 preregistered audits once each (rubric v1.1, objective a).

    uv run python samples/batch1/run_batch1.py

Follows samples/batch1/prereg/batch1-preregistration.json (sealed 2026-09-25T18:21:44Z). Writes
samples/batch1/reports/<asset>-<strategy>.html, summary.json and README.md (the summary table),
with Holm's correction across the 20 Hansen SPA p-values. Statistical findings about past data only;
not investment advice.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SAMPLES = HERE.parent
sys.path[:0] = [str(SAMPLES), str(SAMPLES / "data")]

import batch1_strategies as B  # noqa: E402
import fetch  # noqa: E402
import strategies as S  # noqa: E402

from holdout_audit import AuditConfig, run_audit  # noqa: E402
from holdout_audit.report import write_report  # noqa: E402
from holdout_audit.stats.haircut import holm_adjusted  # noqa: E402

PREREG = HERE / "prereg" / "batch1-preregistration.json"
SEAL = HERE / "prereg" / "seal"
REPORTS = HERE / "reports"
SEED = 20260925
ASSETS = {
    "SPY": dict(file="spy_ohlc_daily_yahoo.csv", start="1994-01-03", end="2026-09-24", holdout="2017-01-03", ppy=252,
                cost=2.0, note="Prices from Yahoo Finance's public chart endpoint; we publish derived statistics only, "
                               "never raw prices; no redistribution. SPY daily OHLC (unadjusted) and dividends; total "
                               "return computed locally."),
    "BTC": dict(file="btc_ohlc_daily.csv", start="2015-09-01", end="2026-09-24", holdout="2023-06-01", ppy=365,
                cost=10.0, note="Prices from the Coinbase Exchange public market-data API; we publish derived statistics "
                                "only, never raw prices; no redistribution. BTC-USD daily OHLC (UTC)."),
}
NAMES = {"supertrend": "Supertrend", "macd": "MACD", "rsi": "RSI", "bollinger": "Bollinger Bands",
         "ma_cross": "MovingAvg2Line Cross", "psar": "Parabolic SAR", "stochastic": "Stochastic Slow",
         "channel_breakout": "Channel BreakOut", "keltner": "Keltner Channels", "momentum": "Momentum"}


def _cagr(x: pd.Series, ppy: int) -> float:
    x = x.dropna()
    return float(np.prod(1 + x.to_numpy()) ** (ppy / len(x)) - 1)


PRE = {s["key"]: s for s in json.loads(PREREG.read_text(encoding="utf-8"))["strategies"]}


def config(key: str, asset: str, px: pd.DataFrame, manifest: dict) -> AuditConfig:
    a = ASSETS[asset]
    tv, rule = PRE[key]["tradingview_builtin_name"], PRE[key]["rule"]
    grid = B.run_grid(key, px)
    net = pd.DataFrame({k: (v["return"] - v["turnover"] * a["cost"] / 1e4) for k, v in grid.items()}).loc[a["start"]:a["end"]]
    chosen = B.default_label(key)
    df = grid[chosen].loc[a["start"]:a["end"]].assign(market=px["tr"].loc[a["start"]:a["end"]])
    rec = manifest[a["file"]]
    notes = [a["note"], f"Normalised file {a['file']}: {rec['rows']} rows ending {rec['end']}, SHA-256 {rec['sha256']}.",
             f"Audit period {a['start']} to {a['end']}; holdout from {a['holdout']} (fixed in the sealed batch "
             "preregistration).",
             "Execution convention: signal at the close, held close to close; stop entries treated as filled at the "
             "signal close; short-side funding not modelled (differs from TradingView's broker emulator)."]
    received = rec["recorded_utc"] if asset == "SPY" else None
    if asset == "BTC":
        notes.append("The BTC OHLC file was fetched for sample audit 4 before this batch was declared (disclosed in the "
                     "preregistration); the declaration date check is therefore not applied to BTC audits.")
    return AuditConfig(
        name=f"Batch 1: {NAMES[key]} (TradingView built-in strategy) on {asset}",
        description=f"TradingView's built-in '{tv}' with its default "
                    f"settings, long and short as it ships, on {asset} daily bars. Benchmark: buy-and-hold {asset}. "
                    "Part of Indicator Audit Batch 1 (20 audits, one sealed preregistration, Holm across the batch).",
        rules=f"Audited variant: {chosen}. Rule (as preregistered): {rule} Grid: "
              f"{B.n_variants(key)} variants (see the preregistration).",
        returns=df, variants=net, chosen_variant=chosen, n_trials=B.n_variants(key), base_cost_bps=a["cost"],
        seed=SEED, rubric_version="1.1", periods_per_year=a["ppy"], holdout_split=a["holdout"],
        declaration_file=str(PREREG), declaration_seal_dir=str(SEAL), preregistration_file=str(PREREG),
        preregistration_seal_dir=str(SEAL), data_received_utc=received,
        data_files={a["file"]: fetch.RAW / a["file"]}, data_notes=notes,
    )


def row(key, asset, res) -> dict:
    ho = res.holdout
    return {
        "asset": asset, "strategy": key, "name": NAMES[key], "variant": res.config.chosen_variant,
        "n_variants": res.n_trials, "grade": res.grade.letter, "score": round(res.grade.score, 3),
        "sharpe": round(res.sharpe.sr_annual, 3), "excess_sharpe": round(res.sharpe_excess.sr_annual, 3),
        "cagr": round(_cagr(res.net, res.ppy), 4), "bh_cagr": round(_cagr(res.bench, res.ppy), 4),
        "dsr": round(res.dsr, 4), "pbo": round(res.pbo.pbo, 4), "spa_p": round(res.spa.p_spa, 4),
        "holdout_excess_sharpe_is": round(ho.sr_is_annual, 3), "holdout_excess_sharpe_oos": round(ho.sr_oos_annual, 3),
        "beats_benchmark_rubric": res.beats_benchmark,
        "report": f"reports/{asset.lower()}-{key.replace('_', '-')}.html",
    }


def main() -> int:
    fetch.main([])  # fetches the SPY OHLC file (first time: after the seal) and checks all hashes
    manifest = json.loads(fetch.MANIFEST.read_text())
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for asset in ("SPY", "BTC"):
        px = S.load_prices(fetch.RAW / ASSETS[asset]["file"])
        for key in B.STRATEGIES:
            slug = f"{asset.lower()}-{key.replace('_', '-')}"
            if asset == "BTC" and key == "supertrend":
                # Carried over from sample 4 (same sealed grid, data, period, holdout and costs); not re-run.
                s4 = json.loads((SAMPLES / "reports" / "summary.json").read_text())["04-btc-supertrend"]
                shutil.copyfile(SAMPLES / "reports" / "04-btc-supertrend.html", REPORTS / f"{slug}.html")
                a = ASSETS["BTC"]
                g = B.supertrend_strategy(px, 10, 3.0, "long_short").loc[a["start"]:a["end"]]
                s4_net = g["return"] - g["turnover"] * a["cost"] / 1e4
                s4_cagr, s4_bh = _cagr(s4_net, 365), _cagr(px["tr"].loc[a["start"]:a["end"]], 365)
                rows.append({"asset": "BTC", "strategy": key, "name": NAMES[key], "variant": "atr=10|mult=3|mode=long_short",
                             "n_variants": 30, "grade": s4["grade"], "score": s4["score"], "sharpe": s4["sr_annual"],
                             "excess_sharpe": s4["excess_sr_annual"], "cagr": round(s4_cagr, 4), "bh_cagr": round(s4_bh, 4),
                             "dsr": s4["dsr"], "pbo": s4["pbo"], "spa_p": s4["spa_p"],
                             "holdout_excess_sharpe_is": s4["holdout_excess_sr_is"],
                             "holdout_excess_sharpe_oos": s4["holdout_excess_sr_oos"],
                             "beats_benchmark_rubric": s4["beats_benchmark"], "report": f"reports/{slug}.html",
                             "carried_over": "sample audit 4"})
                print(f"{slug}: carried over from sample 4 ({s4['grade']})", flush=True)
                continue
            res = run_audit(config(key, asset, px, manifest))
            write_report(res, REPORTS / f"{slug}.html")
            rows.append(row(key, asset, res))
            print(f"{slug}: {res.grade.letter}  excess SR {res.sharpe_excess.sr_annual:+.2f}  SPA p {res.spa.p_spa:.3f}",
                  flush=True)
    holm = holm_adjusted([r["spa_p"] for r in rows])
    for r, h in zip(rows, holm):
        r["spa_p_holm"] = round(float(h), 4)
        r["survives_holm"] = bool(h <= 0.05)
    out = {"batch": "Indicator Audit Batch 1", "rubric": "1.1", "objective": "beat_benchmark",
           "preregistration_sha256": "35b4d77e284614c15fafdacaf91e122b600e520c1ea61e33627a64c3497c765d",
           "preregistration_seal_sha256": "9f25abc24d54753071fc54da00bda52705ea2e7c0b6d2ba3011d7c009fa22d5c",
           "n_audits": len(rows), "n_survive_holm": sum(r["survives_holm"] for r in rows), "audits": rows}
    (HERE / "summary.json").write_bytes((json.dumps(out, indent=2) + "\n").encode("utf-8"))
    print(f"survive Holm: {out['n_survive_holm']} of {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
