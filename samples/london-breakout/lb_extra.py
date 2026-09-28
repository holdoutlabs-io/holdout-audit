"""LB-1 companion: declared checks and descriptive tables that the sealed ``run.py`` does not compute.

Added under DEVIATION-001 (sealed before this file touched any real price). It imports the sealed
modules (``lb_data``, ``lb_port``, ``lb_original``, ``run``) UNCHANGED and changes no number that
``run.py`` produces, no inference and no verdict. It only adds what PREREG declares but the sealed
pipeline leaves out:

    uv run python samples/london-breakout/lb_extra.py repro              # §5.4 reproduction check (before Stage A)
    uv run python samples/london-breakout/lb_extra.py checks --stage A   # §5.4 coverage + FRED level check, §6.4 tables
    uv run python samples/london-breakout/lb_extra.py checks --stage B   # same, in-sample and holdout; §6.2 rank corr; §7.3 CI
    uv run python samples/london-breakout/lb_extra.py report --stage A|B # HTML report(s) via holdout-audit's write_report

Real prices are only read through ``lb_data.load_real`` (seal- and unlock-checked), except the
author's own ``data/gbpusd.csv`` for the reproduction check (PREREG §5.4).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))

import lb_data  # noqa: E402
import lb_original  # noqa: E402
import lb_port  # noqa: E402
import run as R  # noqa: E402  (the sealed pipeline; used unchanged)
from holdout_audit.audit import AuditConfig, run_audit  # noqa: E402
from holdout_audit.report import write_report  # noqa: E402
from holdout_audit.stats import sharpe as S  # noqa: E402
from holdout_audit.stats.stability import vol_regime_table, yearly_table  # noqa: E402

RAW = lb_data.RAW
AUTHOR_FILE = RAW / "author_gbpusd.csv"
AUTHOR_URL = ("https://raw.githubusercontent.com/je-suis-tm/quant-trading/"
              "611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5/data/gbpusd.csv")
FRED_FILE = RAW / "fred_DEXUSUK.csv"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSUK"
PIP = lb_port.PIP
NOW = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731


def _dump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=_jsonable) + "\n", encoding="utf-8", newline="\n")


def _jsonable(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return None if not np.isfinite(x) else float(x)
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(x))
    return str(x)


def _fetch(url: str, dest: Path) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 holdout-labs LB-1 research"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    dest.parent.mkdir(exist_ok=True)
    dest.write_bytes(data)
    return {"url": url, "downloaded_at_utc": NOW(), "bytes": len(data), "sha256": lb_data.sha256_file(dest)}


# ------------------------------------------------------------------------------ §5.4 reproduction

def repro() -> dict:
    lb_data.require_prereg_seal()
    prov = {"url": AUTHOR_URL, "bytes": AUTHOR_FILE.stat().st_size, "sha256": lb_data.sha256_file(AUTHOR_FILE)} \
        if AUTHOR_FILE.exists() else _fetch(AUTHOR_URL, AUTHOR_FILE)
    df = pd.read_csv(AUTHOR_FILE, encoding="utf-8-sig")
    mapping = {"columns": list(df.columns), "encoding": "UTF-8 with BOM (read as utf-8-sig)",
               "note": "layout is already date,price; no mapping needed; timestamps HH:MM, no seconds"}
    df = df[["date", "price"]].reset_index(drop=True)
    t = pd.to_datetime(df["date"])
    out = {"file": prov, "layout": mapping, "rows": int(len(df)), "first": str(t.min()), "last": str(t.max()),
           "days": int(t.dt.normalize().nunique()), "variants": {}}
    for p in (lb_port.DEFAULT,):  # the original's own constants
        rec = {}
        try:
            orig = lb_original.run_original(df)
            rec["original_ran"] = True
        except ValueError as e:  # A11 crash on an empty range
            orig, rec["original_ran"], rec["original_error"] = None, False, repr(e)
        port = lb_port.signals_frame(df, p, on_empty_range="skip")
        rec["port_stats"] = port.attrs["stats"]
        if orig is not None:
            rec["signals_identical"] = bool((orig["signals"].to_numpy() == port["signals"].to_numpy()).all())
            rec["upper_identical"] = bool(np.allclose(orig["upper"].to_numpy(dtype=float), port["upper"].to_numpy()))
            rec["lower_identical"] = bool(np.allclose(orig["lower"].to_numpy(dtype=float), port["lower"].to_numpy()))
            rec["n_signal_bars"] = int((port["signals"] != 0).sum())
            rec["n_mismatch_bars"] = int((orig["signals"].to_numpy() != port["signals"].to_numpy()).sum())
        out["variants"][p.label] = rec
    in_sample = (t.min() >= lb_data.SAMPLE_START) and (t.max() < lb_data.HOLDOUT_START)
    out["disclosure"] = ("The author's file covers dates inside the LB-1 in-sample period (2000-2023): the author saw "
                         "these days." if in_sample else "The author's file dates are reported above.")
    _dump(out, HERE / "repro" / "repro.json")
    return out


# ------------------------------------------------------------------------------ §5.4 coverage etc.

def coverage(df: pd.DataFrame, p: lb_port.Params = lb_port.DEFAULT) -> dict:
    t = pd.to_datetime(df["date"])
    px = df["price"].to_numpy()
    h, m = t.dt.hour.to_numpy(), t.dt.minute.to_numpy()
    day = t.dt.normalize()
    g = pd.DataFrame({"day": day, "h": h, "m": m})
    wd = g[day.dt.dayofweek < 5]
    per = pd.DataFrame(index=pd.DatetimeIndex(sorted(wd["day"].unique())))
    per["h2_minutes"] = wd[wd["h"] == p.range_hour].groupby("day")["m"].nunique().reindex(per.index).fillna(0)
    per["has_0300"] = wd[(wd["h"] == p.open_hour) & (wd["m"] == 0)].groupby("day").size().reindex(per.index).fillna(0) > 0
    per["has_h12"] = wd[wd["h"] == p.close_hour].groupby("day").size().reindex(per.index).fillna(0) > 0
    per["has_window"] = wd[(wd["h"] == p.open_hour) & (wd["m"] >= 1) & (wd["m"] < p.open_minutes)] \
        .groupby("day").size().reindex(per.index).fillna(0) > 0
    full_h2 = per["h2_minutes"] >= 60
    n = len(per)
    out = {"weekdays_with_bars": int(n), "bars": int(len(df)),
           "share_full_hour2": float(full_h2.mean()), "share_has_0300": float(per["has_0300"].mean()),
           "share_has_hour12": float(per["has_h12"].mean()),
           "share_all_three": float((full_h2 & per["has_0300"] & per["has_h12"]).mean()),
           "share_any_hour2_bar": float((per["h2_minutes"] > 0).mean())}
    sig = lb_port.generate_signals(h, m, px, p)
    pos = np.cumsum(sig["signals"])
    last_pos = pd.Series(pos).groupby(day.to_numpy()).last()
    carry_days = last_pos[last_pos != 0]
    out["a10_carry_days"] = int(len(carry_days))
    out["a10_carry_dates"] = [str(d.date()) for d in carry_days.index[:200]]
    out["a11_empty_range_days"] = int(sig["stats"]["empty_range_days"])
    out["a11_entry_bars_without_thresholds"] = int(sig["stats"]["entry_bars_without_thresholds"])
    out["stale_threshold_days"] = int((per["has_window"] & ~per["has_0300"]).sum())
    win = (h == p.open_hour) & (m >= 1) & (m < p.open_minutes) & (sig["upper"] > 0)
    fa = win & ((px - sig["upper"] > p.risky_stop) | (sig["lower"] - px > p.risky_stop))
    out["false_alarm_days"] = int(pd.Series(fa).groupby(day.to_numpy()).any().sum())
    d = np.abs(np.diff(px))
    big = np.where(d > 0.01)[0]
    out["jumps_over_100_pips"] = int(big.size)
    order = big[np.argsort(-d[big])][:25]
    out["largest_jumps"] = [{"from": str(t.iloc[i]), "to": str(t.iloc[i + 1]), "pips": round(float(d[i] / PIP), 1)}
                            for i in order]
    return out


def fred_level_check(df: pd.DataFrame) -> dict:
    prov = _fetch(FRED_URL, FRED_FILE) if not FRED_FILE.exists() else \
        {"url": FRED_URL, "bytes": FRED_FILE.stat().st_size, "sha256": lb_data.sha256_file(FRED_FILE)}
    f = pd.read_csv(FRED_FILE)
    f.columns = ["date", "rate"]
    f["rate"] = pd.to_numeric(f["rate"], errors="coerce")
    f = f.dropna()
    f["date"] = pd.to_datetime(f["date"])
    t = pd.to_datetime(df["date"])
    f = f[(f["date"] >= t.min().normalize()) & (f["date"] <= t.max())]
    # 12:00 New York local time -> HistData's fixed UTC-5 clock (11:00 during US daylight time)
    noon = (f["date"] + pd.Timedelta(hours=12)).dt.tz_localize("America/New_York").dt.tz_convert("UTC") \
        .dt.tz_localize(None) - pd.Timedelta(hours=5)
    s = pd.Series(df["price"].to_numpy(), index=t)
    idx = s.index.searchsorted(noon.to_numpy(), side="right") - 1
    ok = idx >= 0
    bar_t = pd.Series(pd.NaT, index=f.index, dtype="datetime64[ns]")
    bar_t[ok] = s.index[idx[ok]]
    lag = (noon.to_numpy() - bar_t.to_numpy()) / np.timedelta64(1, "m")
    use = ok & (lag >= 0) & (lag <= 15)  # the bar at noon, or the last bar in the 15 minutes before it
    hd = np.where(use, s.to_numpy()[np.clip(idx, 0, None)], np.nan)
    diff = np.abs(hd - f["rate"].to_numpy()) / PIP
    dd = pd.DataFrame({"date": f["date"].dt.date.astype(str).to_numpy(), "diff_pips": diff,
                       "histdata": hd, "fred": f["rate"].to_numpy()}).dropna()
    over = dd[dd["diff_pips"] > 50].sort_values("diff_pips", ascending=False)
    return {"fred_file": prov, "fred_days_in_range": int(len(f)), "matched_days": int(len(dd)),
            "rule": "HistData bar at 12:00 New York local time (fixed-UTC-5 11:00 in US daylight time), or the last bar "
                    "up to 15 minutes before it; days without such a bar are not compared",
            "median_abs_diff_pips": float(dd["diff_pips"].median()) if len(dd) else None,
            "p99_abs_diff_pips": float(dd["diff_pips"].quantile(0.99)) if len(dd) else None,
            "days_over_50_pips": int(len(over)),
            "days_over_50_pips_list": over.round(5).to_dict("records")}


def trades_table(df: pd.DataFrame, p: lb_port.Params = lb_port.DEFAULT) -> dict:
    t = pd.to_datetime(df["date"])
    sig = lb_port.generate_signals(t.dt.hour.to_numpy(), t.dt.minute.to_numpy(), df["price"].to_numpy(), p)["signals"]
    tr = lb_port.trade_list(t, df["price"].to_numpy(), sig, p)
    if not len(tr):
        return {"round_trips": 0}
    by = tr.groupby("exit_reason")["pips"].agg(["count", "mean"]).round(2)
    return {"round_trips": int(len(tr)), "hit_rate": float((tr["pips"] > 0).mean()),
            "mean_gross_pips": float(tr["pips"].mean()), "median_gross_pips": float(tr["pips"].median()),
            "long_share": float((tr["side"] > 0).mean()),
            "by_exit_reason": {k: {"count": int(v["count"]), "mean_pips": float(v["mean"])} for k, v in by.iterrows()}}


def period_tables(df: pd.DataFrame) -> dict:
    base = R.variant_returns(df, lb_port.DEFAULT)
    mkt = R.market_returns(df)
    yt = yearly_table(base["net"], R.PPY)
    yt["mean_annual"] = [float(base["net"][base.index.year == y].mean() * R.PPY) for y in yt["year"]]
    yt["trades"] = [int(base["trades"][base.index.year == y].sum()) for y in yt["year"]]
    yt["gross_mean_annual"] = [float(base["gross"][base.index.year == y].mean() * R.PPY) for y in yt["year"]]
    vr = vol_regime_table(base["net"], mkt, R.PPY)
    return {"by_calendar_year": yt.to_dict("records"), "by_vol_tercile": vr.to_dict("records"),
            "vol_tercile_note": "21-day trailing std of GBP/USD daily returns, lagged a day; tercile cut points "
                                "within this period (holdout-audit stability.vol_regime_table)",
            "trades": trades_table(df)}


def sharpe_ci(r: pd.Series, level: float = 0.95) -> dict:
    x = pd.Series(r).dropna().to_numpy()
    sr = S.sharpe(x)
    sk, ku = S.moments(x)
    se = S.se_sharpe_nonnormal(sr, x.size, sk, ku)
    z = norm.ppf(0.5 + level / 2)
    a = math.sqrt(R.PPY)
    return {"sr_annual": sr * a, "ci_low": (sr - z * se) * a, "ci_high": (sr + z * se) * a, "level": level,
            "method": "Mertens (2002) non-normal IID SE of the daily Sharpe, annualised by sqrt(260)"}


def checks(stage: str) -> dict:
    df = lb_data.load_real(stage)
    out = {"stage": stage, "computed_at_utc": NOW(), "panel_sha256": lb_data.panel_sha256(df),
           "first_bar": str(pd.to_datetime(df["date"]).min()), "last_bar": str(pd.to_datetime(df["date"]).max())}
    if stage == "A":
        out["coverage"] = coverage(df)
        out["fred_level_check"] = fred_level_check(df)
        out["tables"] = period_tables(df)
    else:
        t = pd.to_datetime(df["date"])
        ho = df[t >= lb_data.HOLDOUT_START].reset_index(drop=True)
        out["holdout_first_bar"] = str(pd.to_datetime(ho["date"]).min())
        out["holdout_last_bar"] = str(pd.to_datetime(ho["date"]).max())
        out["coverage_holdout"] = coverage(ho)
        out["coverage_full"] = coverage(df)
        out["fred_level_check_holdout"] = fred_level_check(ho)
        out["tables_holdout"] = period_tables(ho)
        out["tables_full"] = period_tables(df)
        a = json.loads(lb_data.STAGE_A_RESULTS.read_text(encoding="utf-8"))
        b = json.loads((HERE / "stageB" / "results.json").read_text(encoding="utf-8"))
        keys = list(a["variant_sr_annual"])
        rho, pv = spearmanr([a["variant_sr_annual"][k] for k in keys], [b["holdout_by_variant"][k] for k in keys])
        out["rank_corr_is_vs_holdout"] = {"spearman_rho": float(rho), "p_two_sided": float(pv), "n_variants": len(keys)}
        mat_ho = R.variant_returns(ho, lb_port.DEFAULT)
        base_full = R.variant_returns(df, lb_port.DEFAULT)
        out["holdout_sharpe_ci_default"] = sharpe_ci(base_full["net"][base_full.index >= lb_data.HOLDOUT_START])
        out["holdout_sharpe_ci_default_note"] = "net daily returns of the default, computed on the full series (as run.py)"
        out["holdout_only_series_check"] = {"sr_annual_holdout_computed_alone": R.one_sided_p(mat_ho["net"])["sr_annual"]}
        out["in_sample_sharpe_ci_default"] = sharpe_ci(base_full["net"][base_full.index < lb_data.HOLDOUT_START])
    _dump(out, HERE / f"stage{stage}" / "extra.json")
    return out


# ------------------------------------------------------------------------------ HTML report

def report(stage: str) -> Path:
    df = lb_data.load_real(stage)
    man = json.loads((HERE / "MANIFEST.json").read_text(encoding="utf-8"))
    files = [f for f in man["files"] if stage == "B" or f["stage"] == "A"]
    received = max(f["downloaded_at_utc"] for f in files)
    mat = R.variant_matrix(df)
    base = R.variant_returns(df, lb_port.DEFAULT)
    mkt = R.market_returns(df)
    ret = pd.DataFrame({"return": mat[lb_port.DEFAULT.label], "turnover": base["turnover"].reindex(mat.index).fillna(0.0),
                        "market": mkt.reindex(mat.index)})
    split = str(lb_data.HOLDOUT_START.date()) if stage == "B" else None
    name = ("London Breakout (as coded), GBP/USD, full sample" if stage == "B"
            else "London Breakout (as coded), GBP/USD, Stage A")
    notes = [
        "Data: HistData.com GBPUSD Generic ASCII 1-minute bid bars, fixed UTC-5 clock; price = bar close bid "
        "(PREREG A2). Raw files are not redistributed; every file's SHA-256 is in MANIFEST.json.",
        f"{len(files)} HistData files, downloaded {min(f['downloaded_at_utc'] for f in files)} to {received} "
        "(after the preregistration seal, 2026-09-28T13:23:36Z). Canonical panel SHA-256 "
        f"{lb_data.panel_sha256(df)}.",
        "Returns are already net of the declared cost model: 1.0 pip per unit traded one way (2.0-pip round trip); "
        "the rubric's base cost is therefore 0 and its cost headroom is extra headroom beyond that model.",
        "Grid: risky_stop in {0.0050, 0.0075, 0.0100, 0.0125, 0.0150} x open_minutes in {15, 30, 45}; N = 15 (a floor).",
        ("Holdout: 2024-01-01 onwards (locked; downloaded only after Stage A results were committed and hashed)."
         if stage == "B" else "Stage A: in-sample only; the rubric's internal split is its default last 30%, not the "
                              "locked holdout."),
        "LB-1 preregistration (PREREG.md) sealed 2026-09-28T13:23:36Z (DigiCert, FreeTSA). Deviations: see DEVIATION-*.md.",
        "Statistics about past data only. Not investment advice.",
    ]
    cfg = AuditConfig(
        name=name, returns=ret, variants=mat, chosen_variant=lb_port.DEFAULT.label, n_trials=lb_port.N_VARIANTS,
        periods_per_year=R.PPY, holdout_split=split, base_cost_bps=0.0, benchmark="zero",
        benchmark_reason=R.BENCHMARK_REASON, seed=R.SEED, rubric_version="1.2",
        declaration_file=str(HERE / "declaration.json"), data_received_utc=received,
        preregistration_file=str(lb_data.PREREG), preregistration_seal_dir=str(lb_data.PREREG_SEAL),
        data_files={"MANIFEST.json": HERE / "MANIFEST.json"}, data_notes=notes,
        description=("The London Breakout script from je-suis-tm/quant-trading @ 611b73f2, run as coded with its "
                     "default settings on GBP/USD 1-minute data. Claim tested (sealed before any price was loaded): "
                     "as coded, it earns a positive risk-adjusted return on GBP/USD net of realistic trading costs."),
        rules=("Range = high/low of hour 02 (fixed UTC-5); at 03:01-03:29 go long on a close above the high or short "
               "below the low (not if more than 100 pips beyond); exit at +/-50 pips from entry (from 03:30) or at the "
               "first bar of hour 12; one unit, no compounding; costs 1.0 pip per side."),
    )
    res = run_audit(cfg)
    # the headline must equal the sealed pipeline's own rubric run (same inputs, same seed)
    src = HERE / ("stageB/results.json" if stage == "B" else "stageA/results.json")
    sealed = json.loads(src.read_text(encoding="utf-8"))
    sealed_head = sealed["rubric_full_sample" if stage == "B" else "rubric"]["headline"]
    mine = res.headline()
    diffs = {k: (sealed_head[k], mine[k]) for k in sealed_head if k != "name" and sealed_head[k] != mine[k]}
    if diffs:
        raise RuntimeError(f"HTML rubric run differs from run.py's: {diffs}")
    out = HERE / "reports" / ("lb1-full-sample.html" if stage == "B" else "lb1-stage-a.html")
    write_report(res, out)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["repro", "checks", "report"])
    ap.add_argument("--stage", choices=["A", "B"])
    a = ap.parse_args(argv)
    if a.cmd == "repro":
        r = repro()
        print(json.dumps({k: r[k] for k in ("rows", "first", "last", "variants")}, indent=1, default=_jsonable))
    elif a.cmd == "checks":
        checks(a.stage)
        print("wrote", HERE / f"stage{a.stage}" / "extra.json")
    else:
        print("wrote", report(a.stage))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
