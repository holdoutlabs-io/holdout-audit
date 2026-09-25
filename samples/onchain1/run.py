"""ONCHAIN-1: run the sealed preregistration once.

    uv run python samples/onchain1/fetch_headers.py   # block headers over P2P (after the seal)
    uv run python samples/onchain1/run.py             # indicators, tests, Holm, strategy audits, reports

Implements samples/onchain1/prereg/preregistration.json (sealed 2026-09-25T18:22:38Z, SHA-256
aafe3c37...de40) exactly. Statistical analysis of past data only; not investment advice.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SAMPLES = HERE.parent
sys.path.insert(0, str(SAMPLES))
import strategies as S  # noqa: E402

from holdout_audit import AuditConfig, run_audit  # noqa: E402
from holdout_audit.report import write_report  # noqa: E402

PREREG = HERE / "prereg"
REPORTS = HERE / "reports"
PRICE_FILE = SAMPLES / "data" / "raw" / "btc_daily.csv"
PRICE_SHA = "064d2d183581eebe94c24ab3e69e318c369068c03adfe61bac39528f6a2d5c17"
HEADERS = HERE / "raw" / "headers.csv"
END = pd.Timestamp("2026-09-24")
SEED = 20260925
DRAWS = 2000
MIN_EP = 5
GAP = 30
HORIZONS = (90, 180, 365)
COST = 10.0


# ---------------------------------------------------------------- data
def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_price() -> tuple[pd.Series, list[str]]:
    assert sha(PRICE_FILE) == PRICE_SHA, "price file hash differs from the sealed preregistration"
    px = S.load_prices(PRICE_FILE)["close"]
    full = pd.date_range(px.index[0], END, freq="D")
    missing = full.difference(px.index)
    notes = []
    if len(missing):
        notes.append(f"{len(missing)} calendar day(s) missing from the Coinbase file were forward-filled: "
                     + ", ".join(str(d.date()) for d in missing[:10]) + (" ..." if len(missing) > 10 else ""))
    return px.reindex(full).ffill().loc[:END], notes


def load_issuance() -> tuple[pd.Series, dict]:
    h = pd.read_csv(HEADERS)
    subsidy = pd.Series(np.right_shift(np.int64(5_000_000_000), (h["height"] // 210_000).to_numpy(np.int64)), index=h.index) / 1e8
    day = pd.to_datetime(h["timestamp"], unit="s", utc=True).dt.tz_localize(None).dt.normalize()
    iss = subsidy.groupby(day).sum()
    iss = iss.reindex(pd.date_range(iss.index[0], END, freq="D"), fill_value=0.0)
    halvings = {k: pd.to_datetime(int(h.loc[h.height == k, "timestamp"].iloc[0]), unit="s").normalize()
                for k in (210_000, 420_000, 630_000, 840_000) if (h.height == k).any()}
    return iss, halvings


# ---------------------------------------------------------------- indicators
def indicators(close: pd.Series, iss: pd.Series) -> dict[str, pd.Series]:
    out = {}
    out["dma111"], out["dma350x2"] = S.sma(close, 111), 2 * S.sma(close, 350)
    above = out["dma111"] > out["dma350x2"]
    out["pi_cross"] = above & ~above.shift(1, fill_value=False) & out["dma350x2"].shift(1).notna()
    sundays = close[close.index.dayofweek == 6]
    wma = sundays.rolling(200, min_periods=200).mean()
    out["wma200"] = wma.reindex(close.index).ffill()
    out["mayer"] = close / S.sma(close, 200)
    out["ma2y"] = S.sma(close, 730)
    iss = iss.reindex(close.index)
    usd = iss * close
    out["puell"] = usd / usd.rolling(365, min_periods=365).mean()
    usd7 = iss.rolling(7, min_periods=7).mean() * close
    out["puell7"] = usd7 / usd7.rolling(365, min_periods=365).mean()
    return out


def s2f(close: pd.Series, iss_full: pd.Series) -> pd.DataFrame:
    supply = iss_full.cumsum()
    flow = iss_full.rolling(365, min_periods=365).sum()
    sf = supply / flow
    model = np.exp(14.6) * sf ** 3.3 / supply
    return pd.DataFrame({"supply": supply, "sf": sf, "model": model}).reindex(close.index)


def state_machine(enter: pd.Series, exit_: pd.Series, valid: pd.Series) -> pd.Series:
    pos, st = [], 0.0
    for e, x, v in zip(enter.values, exit_.values, valid.values):
        if v:
            if st == 0.0 and e:
                st = 1.0
            elif st == 1.0 and x:
                st = 0.0
        pos.append(st if v else 0.0)
    return pd.Series(pos, index=enter.index)


# ---------------------------------------------------------------- tests
def episodes(zone: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    days = zone.index[zone.fillna(False).astype(bool).values]
    eps: list[list[pd.Timestamp]] = []
    for d in days:
        if eps and (d - eps[-1][1]).days < GAP:
            eps[-1][1] = d
        else:
            eps.append([d, d])
    return [(a, b) for a, b in eps]


def fwd(close: pd.Series, h: int) -> pd.Series:
    return np.log(close.shift(-h) / close)


def zone_test(zone: pd.Series, close: pd.Series, h: int, direction: int, start: pd.Timestamp) -> dict:
    F = fwd(close, h)
    idx = F.loc[start:].dropna().index
    z = zone.reindex(idx).fillna(False).astype(bool).values
    f = F.loc[idx].values
    T = len(f)
    eps = episodes(pd.Series(z, index=idx))
    res = {"h": h, "T": T, "zone_days": int(z.sum()), "episodes": len(eps),
           "episode_starts": [str(a.date()) for a, _ in eps], "unconditional_mean": float(f.mean()) if T else None}
    if not z.any():
        return res | {"conditional_mean": None, "D": None, "p_one_sided": None, "inferential": False}
    obs = f[z].mean() - f.mean()
    rng = np.random.default_rng(SEED)
    ks = rng.integers(h, T - h + 1, size=DRAWS)
    null = np.array([f[np.roll(z, k)].mean() for k in ks]) - f.mean()
    p = (1 + int(np.sum(direction * null >= direction * obs))) / (DRAWS + 1)
    return res | {"conditional_mean": float(f[z].mean()), "D": float(obs), "p_one_sided": float(p),
                  "inferential": len(eps) >= MIN_EP,
                  "conditional_simple_return": float(np.exp(f[z].mean()) - 1),
                  "unconditional_simple_return": float(np.exp(f.mean()) - 1)}


def hits(zone: pd.Series, close: pd.Series, start: pd.Timestamp, kind: str, windows) -> list[dict]:
    out = []
    for s, e in episodes(zone.loc[start:]):
        lo = max(close.index[0], s - pd.Timedelta(days=365))
        hi_end = (s if kind == "top" else e) + pd.Timedelta(days=365)
        seg = close.loc[lo:min(END, hi_end)]
        ext = seg.idxmax() if kind == "top" else seg.idxmin()
        rec = {"start": str(s.date()), "end": str(e.date()), "days": (e - s).days + 1,
               "extreme_date": str(ext.date()), "window_complete": bool(hi_end <= END),
               "days_from_start_to_extreme": (ext - s).days}
        for W in windows:
            rec[f"hit_W{W}"] = bool(s - pd.Timedelta(days=W) <= ext <= e + pd.Timedelta(days=W))
        f365 = close.loc[s:s + pd.Timedelta(days=365)]
        rec["max_gain_after_start_365d"] = float(f365.max() / close.loc[s] - 1)
        rec["fwd365_from_start"] = (float(close.loc[s + pd.Timedelta(days=365)] / close.loc[s] - 1)
                                    if s + pd.Timedelta(days=365) <= END else None)
        rec["min_after_start_365d"] = float(f365.min() / close.loc[s] - 1)
        out.append(rec)
    return out


def holm(ps: list[float], alpha=0.05) -> list[float]:
    m = len(ps)
    order = np.argsort(ps)
    adj = np.empty(m)
    run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m - r) * ps[i]))
        adj[i] = run
    return adj.tolist()


# ---------------------------------------------------------------- strategy audits
def strategy_audit(slug, name, pos, close, start, rule_text, notes, uses_headers):
    ret = close.pct_change()
    df = S.apply_positions(pos, ret).loc[start:END].assign(market=ret.loc[start:END])
    man = json.loads((HERE / "MANIFEST.json").read_text())
    cfg = AuditConfig(
        name=name, description=f"Implied trading rule of a published Bitcoin indicator, frozen as first published "
                               f"and tested only after its publication (ONCHAIN-1, preregistered and sealed). "
                               f"Benchmark: buy-and-hold BTC. Objective (a).",
        rules=rule_text, returns=df, n_trials=1, base_cost_bps=COST, seed=SEED, rubric_version="1.1",
        periods_per_year=365, preregistration_file=str(PREREG / "preregistration.json"),
        preregistration_seal_dir=str(PREREG / "preregistration-seal"),
        data_files={"btc_daily.csv": PRICE_FILE, **({"headers.csv": HEADERS} if uses_headers else {})},
        data_notes=notes)
    res = run_audit(cfg)
    write_report(res, REPORTS / f"{slug}.html")
    hd = res.headline()
    hd["checks"] = {c.key: c.status for c in res.grade.checks}
    return hd


# ---------------------------------------------------------------- main
def main() -> int:
    prereg_sha = sha(PREREG / "preregistration.json")
    assert prereg_sha == "aafe3c37f5bbf83bc6e4b9a986ef1c936c3b74a927c253b833a5a7626482de40"
    close, price_notes = load_price()
    iss_full, halvings = load_issuance()
    ind = indicators(close, iss_full)
    sf = s2f(close, iss_full)
    first_ok = lambda s: s.first_valid_index()  # noqa: E731
    D = pd.Timestamp
    R: dict = {"prereg_sha256": prereg_sha, "price_notes": price_notes,
               "halvings": {k: str(v.date()) for k, v in halvings.items()},
               "headers": json.loads((HERE / "MANIFEST.json").read_text())["headers.csv"], "indicators": {}}

    def start_of(pub_start, *series):
        return max([D(pub_start)] + [first_ok(s) for s in series])

    specs = []
    # A1 Pi Cycle
    st = start_of("2019-05-01", ind["dma350x2"])
    specs.append(("A1", "Pi Cycle Top", st, ind["pi_cross"], -1, "top",
                  {}, None))
    # A2 200WMA
    st = start_of("2019-02-01", ind["wma200"])
    specs.append(("A2", "200-week MA heatmap (bottom claim)", st, close <= 1.10 * ind["wma200"], +1, "bottom",
                  {"below_200wma": (close < ind["wma200"], +1, "bottom")}, None))
    # A3 Mayer
    st = start_of("2018-01-01", ind["mayer"])
    mayer_pos = (ind["mayer"] <= 2.4).astype(float).where(ind["mayer"].notna(), 0.0)
    specs.append(("A3", "Mayer Multiple", st, ind["mayer"] > 2.4, -1, "top", {},
                  (mayer_pos, "Hold BTC when Mayer Multiple (close / 200-day SMA) <= 2.4 at the close, cash otherwise; "
                              "held close to close; audit period = OOS window from 2018-01-01.")))
    # A4 2yMA
    st = start_of("2017-08-01", ind["ma2y"])
    ma = ind["ma2y"]
    ma_pos = state_machine(close < ma, close >= 5 * ma, ma.notna())
    specs.append(("A4", "2-Year MA Multiplier", st, close < ma, +1, "bottom",
                  {"top_5x": (close >= 5 * ma, -1, "top")},
                  (ma_pos, "State machine from the first day the 730-day SMA exists: long after a close below the "
                           "2yMA, flat after a close at or above 5 x 2yMA, otherwise unchanged.")))
    # A5 Puell
    st = start_of("2019-04-01", ind["puell"])
    pu = ind["puell"]
    pu_pos = state_machine(pu < 0.5, pu > 4, pu.notna())
    specs.append(("A5", "Puell Multiple", st, pu < 0.5, +1, "bottom",
                  {"top_gt4": (pu > 4, -1, "top"), "sensitivity_7d_bottom": (ind["puell7"] < 0.5, +1, "bottom")},
                  (pu_pos, "State machine from the first day Puell exists: long after a close with Puell < 0.5, flat "
                           "after Puell > 4, otherwise unchanged. Daily issuance from P2P block headers x Coinbase "
                           "close.")))
    # A6 S2F
    st = start_of("2019-03-23", sf["model"])
    s2f_pos = (close < sf["model"]).astype(float).where(sf["model"].notna(), 0.0)
    specs.append(("A6", "Stock-to-flow (PlanB 2019)", st, close < sf["model"], +1, "bottom",
                  {"above_model": (close > sf["model"], -1, "top")},
                  (s2f_pos, "Hold BTC when the close is below the PlanB (2019) stock-to-flow model price "
                            "exp(14.6) x SF^3.3 / supply, cash otherwise; SF from P2P block headers.")))

    REPORTS.mkdir(exist_ok=True)
    primary_p = []
    for sid, name, st, zone, direction, kind, extra, strat in specs:
        rec = {"name": name, "oos_start_effective": str(st.date()), "kind": kind,
               "tests": {f"primary_D{h}" if h == 365 else f"D{h}": zone_test(zone, close, h, direction, st)
                         for h in HORIZONS}}
        rec["hits"] = hits(zone, close, st, kind, (3, 30, 90) if kind == "top" else (30, 90))
        for key, (z2, d2, k2) in extra.items():
            rec["tests"][f"{key}_D365"] = zone_test(z2, close, 365, d2, st)
            rec["tests"][f"{key}_D90"] = zone_test(z2, close, 90, d2, st)
            rec[f"hits_{key}"] = hits(z2, close, st, k2, (3, 30, 90) if k2 == "top" else (30, 90))
        pt = rec["tests"]["primary_D365"]
        primary_p.append(pt["p_one_sided"] if (pt["inferential"] and pt["p_one_sided"] is not None) else 1.0)
        if strat is not None:
            pos, rule = strat
            notes = [
                "Prices from the Coinbase Exchange public market-data API; we publish derived statistics only, never "
                "raw prices; no redistribution. BTC-USD daily closes (UTC).",
                f"Audit period {st.date()} to {END.date()}: the indicator's post-publication window, fixed in the "
                "sealed ONCHAIN-1 preregistration. N = 1 declared: the rule is the creator's, frozen as published.",
            ] + price_notes + (["Block headers fetched by us from the Bitcoin P2P network (every header prev-hash-"
                                "linked and proof-of-work checked); issuance = consensus subsidy by height."]
                               if sid in ("A5", "A6") else [])
            rec["strategy"] = strategy_audit(f"{sid.lower()}-{name.split(' (')[0].lower().replace(' ', '-')}",
                                             f"ONCHAIN-1 {sid}: {name}, implied rule, post-publication", pos, close,
                                             st, rule, notes, sid in ("A5", "A6"))
        R["indicators"][sid] = rec
    adj = holm(primary_p)
    for (sid, *_), p, a in zip(specs, primary_p, adj):
        pt = R["indicators"][sid]["tests"]["primary_D365"]
        R["indicators"][sid]["holm"] = {"p_entered": p, "p_holm": a, "status": (
            "NOT TESTABLE (descriptive only)" if not pt["inferential"]
            else ("SUPPORTED" if a <= 0.05 else "NOT SUPPORTED"))}
    # descriptive extras
    a1 = R["indicators"]["A1"]
    epochs = [(D("2019-05-01"), halvings.get(630_000)), (halvings.get(630_000), halvings.get(840_000)),
              (halvings.get(840_000), END)]
    crosses = ind["pi_cross"][ind["pi_cross"]].index
    missed = []
    for a, b in epochs:
        seg = close.loc[max(a, D(a1["oos_start_effective"])):b]
        top = seg.idxmax()
        pre = [c for c in crosses if top - pd.Timedelta(days=90) <= c <= top]
        missed.append({"epoch": f"{a.date()}..{b.date()}", "highest_close_date": str(top.date()),
                       "crossing_within_90d_before": [str(c.date()) for c in pre], "missed": not pre})
    a1["epoch_tops"] = missed
    a2 = R["indicators"]["A2"]
    oos = close.loc[D(a2["oos_start_effective"]):]
    a2["share_days_below_200wma"] = float((oos < ind["wma200"].loc[oos.index]).mean())
    a6 = R["indicators"]["A6"]
    oos = close.loc[D(a6["oos_start_effective"]):]
    le = np.log(oos / sf["model"].loc[oos.index])
    a6["fit_by_year"] = {str(y): {"mean_log_error": float(g.mean()), "rms_log_error": float(np.sqrt((g ** 2).mean())),
                                  "mean_ratio_close_to_model": float(np.exp(g.mean()))} for y, g in le.groupby(le.index.year)}
    a6["share_within_factor_2"] = float((le.abs() <= math.log(2)).mean())
    a6["model_price_on"] = {d: float(sf["model"].loc[D(d)]) for d in ("2019-03-22", "2021-12-31", "2024-12-31", "2026-09-24")}
    a6["sf_on"] = {d: float(sf["sf"].loc[D(d)]) for d in ("2019-03-22", "2021-12-31", "2024-12-31", "2026-09-24")}
    (HERE / "results.json").write_text(json.dumps(R, indent=2, default=str) + "\n", encoding="utf-8")
    for sid in R["indicators"]:
        r = R["indicators"][sid]
        pt = r["tests"]["primary_D365"]
        print(sid, r["name"], "| episodes", pt["episodes"], "| D", pt["D"], "| p", pt["p_one_sided"],
              "|", r["holm"]["status"], "| grade", r.get("strategy", {}).get("grade"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
