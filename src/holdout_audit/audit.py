"""Run a full audit under a sealed fragility rubric (docs/RUBRIC-v1.0.md, docs/RUBRIC-v1.1.md).

Both versions are benchmark-relative (buy-and-hold of the traded asset by default). v1.1 fixes the
haircut's sidedness and adds a client-declared objective: (a) beat the benchmark (default) or
(b) reduce drawdown at acceptable cost, which must be declared in writing before the audit.
v1.0 is kept so that reports published under it can be reproduced exactly.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from holdout_audit import __version__
from holdout_audit.grade import (CAUTION, FAIL, NA, OBJECTIVE_BEAT, OBJECTIVE_DRAWDOWN, OBJECTIVE_SHARPE, PASS, Check,
                                 Grade, _band, grade_from_checks, rules_for)
from holdout_audit.io import infer_periods_per_year, sha256_file
from holdout_audit.rubric import CURRENT_VERSION, RUBRIC_VERSION, rubric_seal_info
from holdout_audit.stats import bootstrap, haircut, objective, objective_sharpe, pbo, sharpe, stability

BENCHMARK_NAMES = {"market": "buy-and-hold of the traded asset (total return)", "zero": "zero (cash, no interest)"}


@dataclass
class AuditConfig:
    name: str
    returns: pd.DataFrame  # columns: return [, turnover] [, market]
    variants: pd.DataFrame | None = None  # T x N daily returns of every variant tried
    chosen_variant: str | None = None  # column of ``variants`` that is the audited strategy
    n_trials: int | None = None  # variants the trader says they tried (>= variant columns)
    periods_per_year: int | None = None
    holdout_split: str | None = None  # date; default: last ``holdout_frac`` of the sample
    holdout_frac: float = 0.3
    base_cost_bps: float = 0.0  # one-way cost per unit turnover applied to ``return``
    benchmark: str = "auto"  # "auto" (market if a market column exists, else zero), "market" or "zero"
    benchmark_reason: str = ""  # required in the report when the zero benchmark is chosen explicitly
    n_boot: int = 1000
    pbo_blocks: int = 16
    seed: int = 20260925
    description: str = ""
    rules: str = ""
    data_files: dict = field(default_factory=dict)  # label -> path, hashed into the appendix
    data_notes: list = field(default_factory=list)  # provenance / licence lines
    subject: str = "strategy"
    rubric_version: str = CURRENT_VERSION  # "1.2" (current); "1.1" and "1.0" reproduce reports published under them
    declaration_file: str | None = None  # client's objective declaration (JSON), required for objective (b)
    declaration_seal_dir: str | None = None  # optional: seal-doc output sealing the declaration file
    data_received_utc: str | None = None  # when the audit data arrived; the declaration must predate it
    preregistration_file: str | None = None  # optional sealed preregistration (protocol) of this audit
    preregistration_seal_dir: str | None = None


@dataclass
class Declaration:
    objective: str
    max_return_shortfall_annual: float | None
    declared_at_utc: str | None
    declared_by: str | None
    benchmark: str | None
    sha256: str | None  # of the declaration file's bytes
    seal: dict | None  # verify_seal output when sealed
    source: str  # "file" or "default"


def load_declaration(cfg: "AuditConfig") -> Declaration:
    """Read and validate the objective declaration. Without one, objective (a) applies."""
    if not cfg.declaration_file:
        return Declaration(OBJECTIVE_BEAT, None, None, None, None, None, None, "default")
    raw = Path(cfg.declaration_file).read_bytes()
    d = json.loads(raw.decode("utf-8"))
    obj = d.get("objective", OBJECTIVE_BEAT)
    if obj not in (OBJECTIVE_BEAT, OBJECTIVE_DRAWDOWN, OBJECTIVE_SHARPE):
        raise ValueError(f"objective must be {OBJECTIVE_BEAT!r}, {OBJECTIVE_DRAWDOWN!r} or {OBJECTIVE_SHARPE!r}")
    tol = d.get("max_return_shortfall_annual")
    when = d.get("declared_at_utc")
    if obj == OBJECTIVE_SHARPE and not when:
        raise ValueError("the declaration needs declared_at_utc")
    if obj == OBJECTIVE_DRAWDOWN:
        if tol is None or float(tol) < 0:
            raise ValueError("objective 'reduce_drawdown' needs max_return_shortfall_annual >= 0 (e.g. 0.02 = 2%/yr)")
        if not when:
            raise ValueError("the declaration needs declared_at_utc")
    if when and cfg.data_received_utc:
        if pd.Timestamp(when) > pd.Timestamp(cfg.data_received_utc):
            raise ValueError("the objective was declared after the audit data were received; it cannot be used "
                             "(rubric v1.1 declaration rule)")
    seal = None
    sha = hashlib.sha256(raw).hexdigest()
    if cfg.declaration_seal_dir:
        from holdout_audit.seal import verify_seal

        seal = verify_seal(Path(cfg.declaration_seal_dir))
        if seal["subject_sha256"] != sha:
            raise ValueError("the declaration seal does not match the declaration file")
    return Declaration(obj, None if tol is None else float(tol), when, d.get("declared_by"), d.get("benchmark"),
                       sha, seal, "file")


@dataclass
class AuditResult:
    config: AuditConfig
    net: pd.Series
    bench: pd.Series  # benchmark returns aligned to net (zeros for the cash benchmark)
    benchmark: str  # resolved: "market" or "zero"
    benchmark_note: str
    excess: pd.Series
    ppy: int
    sharpe: sharpe.SharpeSummary  # absolute
    sharpe_excess: sharpe.SharpeSummary
    n_trials: int
    var_trials: float
    dsr: float
    sr0_annual: float
    dsr_curve: list
    haircut: haircut.HaircutResult
    pbo: pbo.PBOResult | None
    spa: bootstrap.RealityCheckResult
    holdout: stability.HoldoutResult
    yearly: pd.DataFrame
    regimes: pd.DataFrame | None
    costs: stability.CostResult | None
    surface: stability.SurfaceResult | None
    drawdowns: bootstrap.DrawdownResult
    beats_benchmark: bool
    grade: Grade
    hashes: dict
    rubric: dict
    generated_utc: str
    declaration: Declaration | None = None
    objective: str = OBJECTIVE_BEAT
    obj: dict | None = None  # objective (b) statistics for the report
    prereg_seal: dict | None = None  # verify_seal output for a sealed preregistration

    @property
    def objective_label(self) -> str:
        return {OBJECTIVE_DRAWDOWN: "reduce drawdown at acceptable cost",
                OBJECTIVE_SHARPE: "improve Sharpe vs benchmark"}.get(self.objective, "beat the benchmark")

    def headline(self) -> dict:
        return {
            "name": self.config.name,
            "rubric_version": self.rubric["version"],
            "objective": self.objective,
            "benchmark": self.benchmark,
            "grade": self.grade.letter,
            "score": round(self.grade.score, 3),
            "caps": self.grade.caps,
            "sr_annual": round(self.sharpe.sr_annual, 3),
            "excess_sr_annual": round(self.sharpe_excess.sr_annual, 3),
            "excess_return_annual": round(self.sharpe_excess.mean * self.ppy, 4),
            "beats_benchmark": self.beats_benchmark,
            "dsr": round(self.dsr, 4),
            "n_trials": self.n_trials,
            "pbo": None if self.pbo is None else round(self.pbo.pbo, 4),
            "haircut_p": round(self.haircut.p_adjusted, 4),
            "spa_p": round(self.spa.p_spa, 4),
            "holdout_excess_sr_is": round(self.holdout.sr_is_annual, 3),
            "holdout_excess_sr_oos": round(self.holdout.sr_oos_annual, 3),
            "max_drawdown": round(self.drawdowns.realized, 4),
        }


def _fmt(x: float, nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x))):
        return "n/a"
    if isinstance(x, float) and math.isinf(x):
        return "inf"
    return f"{x:.{nd}f}"


def resolve_benchmark(cfg: AuditConfig, df: pd.DataFrame) -> tuple[str, str]:
    has_market = "market" in df and df["market"].notna().any()
    if cfg.benchmark == "market":
        if not has_market:
            raise ValueError("benchmark='market' needs a market column")
        return "market", f"This is the rubric v{cfg.rubric_version} default."
    if cfg.benchmark == "zero":
        why = cfg.benchmark_reason or "declared by the client"
        return "zero", f"Cash (zero) benchmark: {why}."
    if cfg.benchmark != "auto":
        raise ValueError("benchmark must be 'auto', 'market' or 'zero'")
    if has_market:
        return "market", f"This is the rubric v{cfg.rubric_version} default."
    return "zero", "Cash (zero) benchmark: no benchmark series was supplied."


def run_audit(cfg: AuditConfig) -> AuditResult:
    if cfg.rubric_version not in ("1.0", "1.1", "1.2"):
        raise ValueError("rubric_version must be '1.0', '1.1' or '1.2'")
    decl = load_declaration(cfg)
    if cfg.rubric_version == "1.0" and decl.objective != OBJECTIVE_BEAT:
        raise ValueError("rubric v1.0 supports only the beat-the-benchmark objective")
    if cfg.rubric_version == "1.1" and decl.objective == OBJECTIVE_SHARPE:
        raise ValueError("objective (c) improve_sharpe exists only from rubric v1.2")
    RUBRIC_RULES = rules_for(cfg.rubric_version, OBJECTIVE_BEAT)[0]  # objective (a) checks (also shown under b)
    one_sided = cfg.rubric_version != "1.0"
    df = cfg.returns.copy()
    if cfg.variants is not None and cfg.chosen_variant is not None and "return" not in df:
        df["return"] = cfg.variants[cfg.chosen_variant]
    df = df.dropna(subset=["return"])
    ppy = cfg.periods_per_year or infer_periods_per_year(df.index)
    has_to = "turnover" in df and df["turnover"].notna().any()
    gross = df["return"]
    net = gross - (df["turnover"].fillna(0) * cfg.base_cost_bps / 1e4 if has_to else 0.0)
    net.name = "net"
    t = net.size
    years = t / ppy

    bmode, bnote = resolve_benchmark(cfg, df)
    bench = (df["market"].reindex(net.index).fillna(0.0) if bmode == "market" else pd.Series(0.0, index=net.index))
    bench.name = "benchmark"
    excess = (net - bench).rename("excess")

    ss = sharpe.summarize(net.to_numpy(), ppy)
    sx = sharpe.summarize(excess.to_numpy(), ppy)

    # ---------------------------------------------------------------- trials / DSR (excess)
    var = cfg.variants.loc[cfg.variants.index.isin(net.index)] if cfg.variants is not None else None
    var_ex = var.sub(bench.reindex(var.index).fillna(0.0), axis=0) if var is not None else None
    n_var_cols = 0 if var is None else var.shape[1]
    declared = cfg.n_trials is not None or var is not None
    n_trials = max(int(cfg.n_trials or 1), n_var_cols, 1)
    if var_ex is not None:
        v_srs = np.array([sharpe.sharpe(var_ex[c].dropna()) for c in var_ex.columns])
        var_trials = float(np.var(v_srs, ddof=1))
    else:
        v_srs = None
        var_trials = 1.0 / t  # sampling variance of SR under the null: trials treated as noise
    dsr, sr0 = sharpe.deflated_sharpe_ratio(sx.sr, t, sx.skew, sx.kurt, n_trials, var_trials)
    dsr_curve = []
    for n in sorted({1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, n_trials}):
        d, s0 = sharpe.deflated_sharpe_ratio(sx.sr, t, sx.skew, sx.kurt, n, var_trials)
        dsr_curve.append((n, d, s0 * math.sqrt(ppy)))

    # ---------------------------------------------------------------- haircut (excess)
    idx = None
    all_sr_ann = None
    if var is not None and n_trials == n_var_cols and cfg.chosen_variant in var.columns:
        idx = list(var.columns).index(cfg.chosen_variant)
        all_sr_ann = list(v_srs * math.sqrt(ppy))
        all_sr_ann[idx] = sx.sr_annual  # the audited (net) series for the chosen one
    hc = haircut.haircut_sharpe(sx.sr_annual, years, n_trials, all_sr_ann, idx, one_sided=one_sided)

    # ---------------------------------------------------------------- PBO (excess)
    pb = pbo.pbo_cscv(var_ex.to_numpy(), n_blocks=cfg.pbo_blocks, seed=cfg.seed) if var_ex is not None else None

    # ---------------------------------------------------------------- Reality Check / SPA
    if var is not None:
        mat = var.reindex(net.index).copy()
        if cfg.chosen_variant in mat:
            mat[cfg.chosen_variant] = net
        spa = bootstrap.reality_check_spa(mat.fillna(0.0).to_numpy(), bench.to_numpy(), cfg.n_boot, seed=cfg.seed)
    else:
        spa = bootstrap.reality_check_spa(net.to_numpy(), bench.to_numpy(), cfg.n_boot, seed=cfg.seed)

    # ---------------------------------------------------------------- stability
    ho = stability.holdout_degradation(excess, ppy, cfg.holdout_split, cfg.holdout_frac)
    yearly = stability.yearly_excess_table(net, bench, ppy)
    regimes = stability.vol_regime_table(excess, df["market"], ppy) if "market" in df else None
    costs = stability.cost_sensitivity(gross, df["turnover"], ppy) if has_to else None
    surface = None
    if var is not None and cfg.chosen_variant is not None:
        surface = stability.parameter_surface(var, cfg.chosen_variant, ppy)
    dd = bootstrap.bootstrap_drawdowns(net.to_numpy(), cfg.n_boot, seed=cfg.seed)

    # ---------------------------------------------------------------- checks (RUBRIC v1.0)
    bname = BENCHMARK_NAMES[bmode]
    checks: list[Check] = []
    st = _band(dsr, 0.95, 0.80)
    checks.append(Check(
        "dsr", "Selection-adjusted significance vs benchmark (Deflated Sharpe)", st,
        f"DSR {_fmt(dsr, 3)} (N = {n_trials})", RUBRIC_RULES["dsr"],
        f"Excess Sharpe over {bname}: {_fmt(sx.sr_annual)} a year over {_fmt(years, 1)} years. After allowing for "
        f"{n_trials} variant(s) tried, the best-of-N noise hurdle is an annualised excess Sharpe of "
        f"{_fmt(sr0 * math.sqrt(ppy))}; the probability that the true excess Sharpe exceeds it is {_fmt(dsr, 3)}."
        + ("" if declared else " The number of variants tried was not declared, so N = 1 was assumed."),
        "Declare every variant you tried (including abandoned ones), then re-test on data you have not "
        "looked at: a sealed forward period or a later holdout. A DSR that only passes at N = 1 is not evidence."
        if st != PASS else "",
    ))
    if pb is None:
        checks.append(Check("pbo", "Probability of backtest overfitting (CSCV)", NA, "not computed", RUBRIC_RULES["pbo"],
                            "No variant return matrix was supplied, so PBO could not be computed.",
                            "Send the daily returns of every variant you tried; PBO measures how often the in-sample winner "
                            "disappoints out of sample."))
    else:
        st = _band(pb.pbo, 0.20, 0.50, higher_better=False)
        if st == FAIL and pb.prob_oos_loss <= 0.10:
            st = CAUTION  # rubric v1.0 row 2: high PBO with rare OOS excess losses = rank noise
        checks.append(Check(
            "pbo", "Probability of backtest overfitting (CSCV)", st,
            f"PBO {_fmt(pb.pbo, 3)} ({pb.n_splits} splits)", RUBRIC_RULES["pbo"],
            f"Across {pb.n_splits} combinatorial in-sample/out-of-sample splits of {pb.n_variants} variants, ranked by "
            f"excess Sharpe, the in-sample winner ranked in the bottom half out of sample {_fmt(100 * pb.pbo, 1)}% of "
            f"the time and trailed the benchmark out of sample {_fmt(100 * pb.prob_oos_loss, 1)}% of the time."
            + (" A PBO this high with rare out-of-sample shortfalls says that which variant looks best is mostly "
               "noise, even though the family as a whole held up." if pb.pbo > 0.5 and pb.prob_oos_loss <= 0.10 else ""),
            "Shrink the search: fewer free parameters, coarser grids, rules fixed from theory before looking at "
            "results. Then re-run CSCV on the smaller family; PBO should fall." if st != PASS else "",
        ))
    st = _band(hc.p_adjusted, 0.05, 0.10, higher_better=False)
    which = "BHY" if hc.p_bhy is not None else "Bonferroni"
    checks.append(Check(
        "haircut", "Multiple-testing haircut vs benchmark (Harvey-Liu)", st,
        f"adj. p {_fmt(hc.p_adjusted, 4)} ({which})", RUBRIC_RULES["haircut"],
        f"Excess-return t-statistic {_fmt(hc.t_stat)} (single-test p {_fmt(hc.p_single, 4)}). Adjusted for {n_trials} "
        f"tests ({which}), p = {_fmt(hc.p_adjusted, 4)}; the Bonferroni-haircut excess Sharpe is "
        f"{_fmt(hc.sr_haircut_bonferroni)}.",
        "A longer sample raises the t-statistic without new selection: extend the test to earlier or later "
        "data the rule was not designed on, keeping the rule frozen." if st != PASS else "",
    ))
    st = _band(spa.p_spa, 0.05, 0.10, higher_better=False)
    checks.append(Check(
        "spa", "Beats the benchmark after data snooping (Hansen SPA)", st,
        f"SPA p {_fmt(spa.p_spa, 3)}; RC p {_fmt(spa.p_reality_check, 3)}", RUBRIC_RULES["spa"],
        f"Benchmark: {bname}. Testing whether the best of {spa.n_variants} variant(s) beats it in mean return, "
        f"with a stationary bootstrap ({spa.n_boot} draws, mean block {spa.mean_block:.0f} periods): Hansen SPA "
        f"p = {_fmt(spa.p_spa, 3)}, White Reality Check p = {_fmt(spa.p_reality_check, 3)}.",
        "If the rule's value is lower risk rather than higher return, state that claim before testing it "
        "(e.g. drawdown or volatility against the benchmark) and test it on unseen data." if st != PASS else "",
    ))
    if ho.sr_oos_annual > 0 and ho.sr_is_annual > 0 and ho.sr_oos_annual >= 0.5 * ho.sr_is_annual:
        st = PASS
    elif ho.sr_oos_annual > 0:
        st = CAUTION
    else:
        st = FAIL
    checks.append(Check(
        "holdout", "Holdout degradation (excess Sharpe)", st,
        f"excess SR {_fmt(ho.sr_is_annual)} -> {_fmt(ho.sr_oos_annual)}", RUBRIC_RULES["holdout"],
        f"In-sample (before {ho.split_date.date()}) annualised excess Sharpe {_fmt(ho.sr_is_annual)}; holdout "
        f"{_fmt(ho.sr_oos_annual)} over {ho.n_oos} periods. Consistency p-value {_fmt(ho.p_oos_consistent, 3)} "
        "(low values mean the holdout is unlikely to share the in-sample excess Sharpe).",
        "Lock a fresh holdout before any further tuning, or run a sealed forward trial with preregistered pass "
        "criteria; only data you have not seen can confirm a fix." if st != PASS else "",
    ))
    pos_share = float((yearly["excess"] > 0).mean()) if len(yearly) else float("nan")
    worst_regime = float(regimes["sr_annual"].min()) if regimes is not None else None
    if pos_share >= 0.6 and (worst_regime is None or worst_regime > 0):
        st = PASS
    elif pos_share >= 0.5:
        st = CAUTION
    else:
        st = FAIL
    reg_txt = "" if regimes is None else " Annualised excess Sharpe by volatility tercile: " + ", ".join(
        f"{row.regime} {_fmt(row.sr_annual)}" for row in regimes.itertuples()) + "."
    checks.append(Check(
        "stability", "Period and regime stability (vs benchmark)", st,
        f"{_fmt(100 * pos_share, 0)}% of years ahead", RUBRIC_RULES["stability"],
        f"The strategy's compounded return beat the benchmark's in {int((yearly['excess'] > 0).sum())} of "
        f"{len(yearly)} calendar years.{reg_txt}",
        "Check whether the edge over the benchmark is concentrated in a few years or one regime; if so, state that "
        "regime as part of the hypothesis and test it on a period the rule has not seen." if st != PASS else "",
    ))
    if costs is None:
        checks.append(Check("costs", "Transaction-cost headroom", NA, "no turnover data", RUBRIC_RULES["costs"],
                            "No turnover column was supplied, so cost sensitivity could not be measured.",
                            "Send position or turnover per period so cost drag can be stress-tested."))
    else:
        st = _band(costs.breakeven_bps, 20.0, 5.0)
        checks.append(Check(
            "costs", "Transaction-cost headroom (absolute)", st,
            f"break-even {_fmt(costs.breakeven_bps, 1)} bps", RUBRIC_RULES["costs"],
            f"Turnover is {_fmt(costs.turnover_per_year, 1)} units a year. The gross mean return falls to zero at a "
            f"one-way cost of {_fmt(costs.breakeven_bps, 1)} bps per unit traded. Base case in this report: "
            f"{cfg.base_cost_bps:g} bps.",
            "Measure your real fills (spread, slippage, fees) over a few weeks and re-run with that cost; "
            "reduce turnover with wider entry/exit bands and check the Sharpe survives." if st != PASS else "",
        ))
    if surface is None:
        checks.append(Check("surface", "Parameter plateau", NA, "no grid", RUBRIC_RULES["surface"],
                            "No parameter grid was supplied.",
                            "Name variant columns like 'fast=50|slow=200' so the parameter surface can be mapped."))
    else:
        st = FAIL if surface.chosen_sr <= 0 else _band(surface.neighbor_ratio, 0.70, 0.40)
        checks.append(Check(
            "surface", "Parameter plateau (absolute)", st,
            f"neighbours {_fmt(100 * surface.neighbor_ratio, 0)}% of chosen", RUBRIC_RULES["surface"],
            f"The chosen variant ranks {surface.rank_of_chosen} of {len(surface.table)} (annualised Sharpe "
            f"{_fmt(surface.chosen_sr)}; grid median {_fmt(surface.median_sr)}; best {_fmt(surface.best_sr)}). "
            f"Its one-step grid neighbours average {_fmt(100 * surface.neighbor_ratio, 0)}% of its Sharpe; "
            f"{_fmt(100 * surface.share_positive, 0)}% of the grid has a positive Sharpe.",
            "Prefer the centre of a broad plateau over the single best cell, and report the grid median as the "
            "honest expectation." if st != PASS else "",
        ))
    spa_fail = next(c for c in checks if c.key == "spa").status == FAIL
    beats = (not spa_fail) and sx.mean * ppy > 0
    obj_stats = None
    objective_met = None
    if decl.objective == OBJECTIVE_DRAWDOWN:
        checks, obj_stats = _drawdown_checks(cfg, decl, net, bench, var, df, ppy, n_trials, ho.split_date,
                                             costs, rules_for(cfg.rubric_version, decl.objective)[0])
        st_by = {c.key: c.status for c in checks}
        objective_met = st_by["drawdown"] != FAIL and st_by["tolerance"] != FAIL
    elif decl.objective == OBJECTIVE_SHARPE:
        checks, obj_stats = _sharpe_checks(cfg, net, bench, var, df, ppy, n_trials, ho.split_date, costs,
                                           rules_for(cfg.rubric_version, decl.objective)[0])
        objective_met = {c.key: c.status for c in checks}["sharpe"] != FAIL
    grade = grade_from_checks(checks, variants_declared=declared, beats_benchmark=beats,
                              version=cfg.rubric_version, objective=decl.objective, objective_met=objective_met)

    hashes = {"package": f"holdout-audit {__version__}"}
    for label, p in cfg.data_files.items():
        if p and Path(p).exists():
            hashes[label] = sha256_file(p)
    hashes["audited_series_sha256"] = hashlib.sha256(
        pd.DataFrame({"net": net, "benchmark": bench}).to_csv(float_format="%.12g", lineterminator="\n").encode()
    ).hexdigest()
    if decl.sha256:
        hashes["objective_declaration_sha256"] = decl.sha256
    prereg_seal = None
    if cfg.preregistration_file:
        hashes["preregistration_sha256"] = sha256_file(cfg.preregistration_file)
        if cfg.preregistration_seal_dir:
            from holdout_audit.seal import verify_seal

            prereg_seal = verify_seal(Path(cfg.preregistration_seal_dir))
            if prereg_seal["subject_sha256"] != hashes["preregistration_sha256"]:
                raise ValueError("the preregistration seal does not match the preregistration file")
    cfg_public = {k: v for k, v in vars(cfg).items() if k not in ("returns", "variants", "data_files", "data_notes")}
    hashes["config_sha256"] = hashlib.sha256(json.dumps(cfg_public, sort_keys=True, default=str).encode()).hexdigest()

    return AuditResult(
        config=cfg, net=net, bench=bench, benchmark=bmode, benchmark_note=bnote, excess=excess, ppy=ppy,
        sharpe=ss, sharpe_excess=sx, n_trials=n_trials, var_trials=var_trials, dsr=dsr,
        sr0_annual=sr0 * math.sqrt(ppy), dsr_curve=dsr_curve, haircut=hc, pbo=pb, spa=spa, holdout=ho,
        yearly=yearly, regimes=regimes, costs=costs, surface=surface, drawdowns=dd, beats_benchmark=beats,
        grade=grade, hashes=hashes, rubric=rubric_seal_info(cfg.rubric_version),
        generated_utc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        declaration=decl, objective=decl.objective, obj=obj_stats, prereg_seal=prereg_seal,
    )


def _drawdown_checks(cfg, decl, net, bench, var, df, ppy, n_trials, split_date, costs, R):
    """Rubric v1.1 objective (b): reduce drawdown at acceptable cost (docs/RUBRIC-v1.1.md section 3)."""
    ob = objective.objective_bootstrap(net.to_numpy(), bench.to_numpy(), ppy, cfg.n_boot, seed=cfg.seed)
    tol = decl.max_return_shortfall_annual
    b = bench.to_numpy()
    thetas = p_vec = None
    if var is not None:
        mat = var.reindex(net.index).fillna(0.0).copy()
        if cfg.chosen_variant in mat:
            mat[cfg.chosen_variant] = net
        thetas = objective.variant_cvar_reductions(mat.to_numpy(), b)
        var_theta = float(np.var(thetas, ddof=1))
        if n_trials == mat.shape[1] and cfg.chosen_variant in mat:
            p_vec = objective.variant_bootstrap_p(mat.to_numpy(), b, cfg.n_boot, seed=cfg.seed)
            p_vec[list(mat.columns).index(cfg.chosen_variant)] = ob.p_d_cvar
    else:
        var_theta = ob.d_cvar_se ** 2
    d_obj, theta0 = objective.deflated_objective(ob.d_cvar, ob.d_cvar_se, n_trials, var_theta)
    pb = objective.pbo_cscv_cvar(mat.to_numpy(), b, n_blocks=cfg.pbo_blocks) if var is not None else None
    if p_vec is not None:
        p_adj = float(haircut.bhy_adjusted(p_vec)[list(mat.columns).index(cfg.chosen_variant)])
        which = "BHY"
    else:
        p_adj = min(1.0, ob.p_d_cvar * n_trials)
        which = "Bonferroni"
    ho = objective.holdout_cvar(net, bench, split_date)
    yearly = objective.yearly_drawdown_table(net, bench)
    regimes = objective.regime_cvar_table(net, bench, df["market"]) if "market" in df else None
    surface = None
    if var is not None and cfg.chosen_variant is not None:
        surface = stability.parameter_surface(var, cfg.chosen_variant, ppy,
                                              values=dict(zip(mat.columns, thetas)))
    pct = lambda x: f"{100 * x:.1f}%"  # noqa: E731
    bp = lambda x: f"{1e4 * x:.1f} bps"  # noqa: E731
    checks: list[Check] = []
    st = _band(d_obj, 0.95, 0.80)
    checks.append(Check(
        "dsr", "Selection-adjusted tail-loss reduction (deflated dCVaR)", st, f"D {_fmt(d_obj, 3)} (N = {n_trials})", R["dsr"],
        f"Daily CVaR95 falls from {bp(ob.cvar_benchmark)} (benchmark) to {bp(ob.cvar_strategy)} (strategy): a reduction "
        f"of {bp(ob.d_cvar)} (bootstrap SE {bp(ob.d_cvar_se)}). The best-of-{n_trials} noise hurdle is {bp(theta0)}; "
        f"the probability that the true reduction exceeds it is {_fmt(d_obj, 3)}.",
        "Declare every variant tried and confirm the reduction on data the rule has not seen." if st != PASS else ""))
    if pb is None:
        checks.append(Check("pbo", "Probability of backtest overfitting (CSCV, dCVaR)", NA, "not computed", R["pbo"],
                            "No variant return matrix was supplied, so PBO could not be computed.", ""))
    else:
        st = _band(pb.pbo, 0.20, 0.50, higher_better=False)
        if st == FAIL and pb.prob_oos_loss <= 0.10:
            st = CAUTION
        checks.append(Check(
            "pbo", "Probability of backtest overfitting (CSCV, dCVaR)", st, f"PBO {_fmt(pb.pbo, 3)} ({pb.n_splits} splits)",
            R["pbo"],
            f"Ranking {pb.n_variants} variants by tail-loss reduction, the in-sample winner ranked in the bottom half out "
            f"of sample {_fmt(100 * pb.pbo, 1)}% of the time and had worse tails than the benchmark out of sample "
            f"{_fmt(100 * pb.prob_oos_loss, 1)}% of the time.",
            "Shrink the search and re-run CSCV on the smaller family." if st != PASS else ""))
    st = _band(p_adj, 0.05, 0.10, higher_better=False)
    checks.append(Check(
        "haircut", "Multiple-testing adjusted significance of the tail-loss reduction", st, f"adj. p {_fmt(p_adj, 4)} ({which})",
        R["haircut"],
        f"One-sided p that the tail-loss reduction is zero or worse: {_fmt(ob.p_d_cvar, 4)} for the audited strategy; "
        f"adjusted for {n_trials} tests ({which}): {_fmt(p_adj, 4)}.",
        "A longer sample, with the rule frozen, sharpens this test without new selection." if st != PASS else ""))
    if ob.d_mdd_lo > 0 and ob.d_cvar_lo > 0:
        st = PASS
    elif ob.d_mdd > 0 and ob.d_cvar > 0:
        st = CAUTION
    else:
        st = FAIL
    checks.append(Check(
        "drawdown", "Primary: drawdown and tail-loss reduction vs benchmark", st,
        f"dMDD {pct(ob.d_mdd)} (5th pct {pct(ob.d_mdd_lo)})", R["drawdown"],
        f"Maximum drawdown {pct(ob.mdd_strategy)} against {pct(ob.mdd_benchmark)} for the benchmark (reduction "
        f"{pct(ob.d_mdd)}; bootstrap 5th percentile {pct(ob.d_mdd_lo)}). Daily CVaR95 reduction {bp(ob.d_cvar)} "
        f"(5th percentile {bp(ob.d_cvar_lo)}). Paired stationary bootstrap, {ob.n_boot} draws.",
        "A reduction that only shows up in one or two crashes is fragile: test it on a period with different "
        "crashes, or in a sealed forward trial." if st != PASS else ""))
    if ob.shortfall_hi <= tol:
        st = PASS
    elif ob.shortfall <= tol:
        st = CAUTION
    else:
        st = FAIL
    checks.append(Check(
        "tolerance", "Primary: return cost within the declared tolerance", st,
        f"shortfall {pct(ob.shortfall)}/yr vs {pct(tol)}", R["tolerance"],
        f"The strategy gave up {pct(ob.shortfall)} a year of arithmetic return against the benchmark (bootstrap 95th "
        f"percentile {pct(ob.shortfall_hi)}). The client declared a tolerance of {pct(tol)} a year on "
        f"{decl.declared_at_utc}.",
        "The tolerance was fixed in advance and cannot be revised for this audit; a changed rule is a new variant "
        "and needs a new declaration." if st != PASS else ""))
    if ho["d_cvar_oos"] > 0 and ho["d_cvar_is"] > 0 and ho["d_cvar_oos"] >= 0.5 * ho["d_cvar_is"] and ho["d_mdd_oos"] > 0:
        st = PASS
    elif ho["d_cvar_oos"] > 0:
        st = CAUTION
    else:
        st = FAIL
    checks.append(Check(
        "holdout", "Holdout: tail-loss and drawdown reduction", st,
        f"dCVaR {bp(ho['d_cvar_is'])} -> {bp(ho['d_cvar_oos'])}", R["holdout"],
        f"Tail-loss reduction {bp(ho['d_cvar_is'])} before {ho['split_date'].date()} and {bp(ho['d_cvar_oos'])} after; "
        f"holdout drawdown reduction {pct(ho['d_mdd_oos'])}.",
        "Lock a fresh holdout or run a sealed forward trial." if st != PASS else ""))
    share = float(yearly["shallower"].mean()) if len(yearly) else float("nan")
    worst = float(regimes["d_cvar"].min()) if regimes is not None else None
    st = PASS if share >= 0.6 and (worst is None or worst > 0) else CAUTION if share >= 0.5 else FAIL
    reg_txt = "" if regimes is None else " dCVaR by volatility tercile: " + ", ".join(
        f"{r.regime} {bp(r.d_cvar)}" for r in regimes.itertuples()) + "."
    checks.append(Check(
        "stability", "Stability of the drawdown reduction", st, f"{_fmt(100 * share, 0)}% of years shallower",
        R["stability"],
        f"The strategy's within-year drawdown was shallower than the benchmark's in {int(yearly['shallower'].sum())} of "
        f"{len(yearly)} years.{reg_txt}",
        "State the regime in which the reduction is expected and test it where the rule was not designed."
        if st != PASS else ""))
    if costs is None:
        checks.append(Check("costs", "Transaction-cost headroom", NA, "no turnover data", R["costs"],
                            "No turnover column was supplied.", ""))
    else:
        st = _band(costs.breakeven_bps, 20.0, 5.0)
        checks.append(Check("costs", "Transaction-cost headroom (absolute)", st,
                            f"break-even {_fmt(costs.breakeven_bps, 1)} bps", R["costs"],
                            f"The gross mean return falls to zero at {_fmt(costs.breakeven_bps, 1)} bps per unit traded.",
                            "Measure real fills and re-run at that cost." if st != PASS else ""))
    if surface is None:
        checks.append(Check("surface", "Parameter plateau (dCVaR)", NA, "no grid", R["surface"],
                            "No parameter grid was supplied.", ""))
    else:
        st = FAIL if surface.chosen_sr <= 0 else _band(surface.neighbor_ratio, 0.70, 0.40)
        checks.append(Check(
            "surface", "Parameter plateau (dCVaR)", st, f"neighbours {_fmt(100 * surface.neighbor_ratio, 0)}% of chosen",
            R["surface"],
            f"The chosen variant ranks {surface.rank_of_chosen} of {len(surface.table)} by tail-loss reduction; its "
            f"one-step neighbours average {_fmt(100 * surface.neighbor_ratio, 0)}% of its reduction.",
            "Prefer the centre of a plateau." if st != PASS else ""))
    stats_out = {"boot": ob, "deflated": d_obj, "theta0": theta0, "p_adj": p_adj, "pbo": pb, "holdout": ho,
                 "yearly": yearly, "regimes": regimes, "surface": surface, "tolerance": tol}
    return checks, stats_out


__all__ = ["AuditConfig", "AuditResult", "run_audit", "RUBRIC_VERSION"]


def _sharpe_checks(cfg, net, bench, var, df, ppy, n_trials, split_date, costs, R):
    """Rubric v1.2 objective (c): improve Sharpe vs benchmark (docs/RUBRIC-v1.2.md section 3)."""
    S = objective_sharpe
    q = math.sqrt(ppy)
    b = bench.to_numpy()
    sb = S.sharpe_bootstrap(net.to_numpy(), b, ppy, cfg.n_boot, seed=cfg.seed)
    ds = dvec = p_vec = None
    mat = None
    if var is not None:
        mat = var.reindex(net.index).fillna(0.0).copy()
        if cfg.chosen_variant in mat:
            mat[cfg.chosen_variant] = net
        dvec = S.variant_delta_sharpes(mat.to_numpy(), b)
        var_d = float(np.var(dvec, ddof=1))
        if n_trials == mat.shape[1] and cfg.chosen_variant in mat:
            p_vec = S.variant_bootstrap_p(mat.to_numpy(), b, cfg.n_boot, seed=cfg.seed)
            p_vec[list(mat.columns).index(cfg.chosen_variant)] = sb.p_d_sr
    else:
        var_d = (sb.d_sr_se / q) ** 2
    d_obj, theta0 = objective.deflated_objective(sb.d_sr / q, sb.d_sr_se / q, n_trials, var_d)
    pb = S.pbo_cscv_delta_sharpe(mat.to_numpy(), b, n_blocks=cfg.pbo_blocks) if mat is not None else None
    if p_vec is not None:
        p_adj, which = float(haircut.bhy_adjusted(p_vec)[list(mat.columns).index(cfg.chosen_variant)]), "BHY"
    else:
        p_adj, which = min(1.0, sb.p_d_sr * n_trials), "Bonferroni"
    ho = S.holdout_delta_sharpe(net, bench, split_date, ppy)
    yearly = S.yearly_sharpe_table(net, bench, ppy)
    regimes = S.regime_delta_sharpe(net, bench, df["market"], ppy) if "market" in df else None
    surface = None
    if mat is not None and cfg.chosen_variant is not None:
        surface = stability.parameter_surface(var, cfg.chosen_variant, ppy, values=dict(zip(mat.columns, dvec * q)))
    f2 = lambda x: f"{x:+.2f}"  # noqa: E731
    checks: list[Check] = []
    st = _band(d_obj, 0.95, 0.80)
    checks.append(Check("dsr", "Selection-adjusted Sharpe improvement (deflated dSR)", st, f"D {_fmt(d_obj, 3)} (N = {n_trials})",
                        R["dsr"],
                        f"Annualised Sharpe {sb.sr_strategy:.2f} against {sb.sr_benchmark:.2f} for the benchmark: an improvement "
                        f"of {f2(sb.d_sr)} (bootstrap SE {sb.d_sr_se:.2f}). The best-of-{n_trials} noise hurdle is "
                        f"{f2(theta0 * q)}; the probability that the true improvement exceeds it is {_fmt(d_obj, 3)}.",
                        "Declare every variant tried and confirm the improvement on data the rule has not seen." if st != PASS else ""))
    if pb is None:
        checks.append(Check("pbo", "Probability of backtest overfitting (CSCV, dSR)", NA, "not computed", R["pbo"],
                            "No variant return matrix was supplied, so PBO could not be computed.", ""))
    else:
        st = _band(pb.pbo, 0.20, 0.50, higher_better=False)
        if st == FAIL and pb.prob_oos_loss <= 0.10:
            st = CAUTION
        checks.append(Check("pbo", "Probability of backtest overfitting (CSCV, dSR)", st, f"PBO {_fmt(pb.pbo, 3)} ({pb.n_splits} splits)",
                            R["pbo"],
                            f"Ranking {pb.n_variants} variants by Sharpe improvement, the in-sample winner ranked in the bottom half "
                            f"out of sample {_fmt(100 * pb.pbo, 1)}% of the time and had a lower Sharpe than the benchmark out of "
                            f"sample {_fmt(100 * pb.prob_oos_loss, 1)}% of the time.",
                            "Shrink the search and re-run CSCV on the smaller family." if st != PASS else ""))
    st = _band(p_adj, 0.05, 0.10, higher_better=False)
    checks.append(Check("haircut", "Multiple-testing adjusted significance of the Sharpe improvement", st,
                        f"adj. p {_fmt(p_adj, 4)} ({which})", R["haircut"],
                        f"One-sided p that the Sharpe improvement is zero or worse: {_fmt(sb.p_d_sr, 4)}; adjusted for {n_trials} tests "
                        f"({which}): {_fmt(p_adj, 4)}.",
                        "A longer sample, with the rule frozen, sharpens this test without new selection." if st != PASS else ""))
    st = PASS if sb.d_sr_lo > 0 else CAUTION if sb.d_sr > 0 else FAIL
    checks.append(Check("sharpe", "Primary: Sharpe-ratio improvement vs benchmark", st,
                        f"dSR {f2(sb.d_sr)} (5th pct {f2(sb.d_sr_lo)})", R["sharpe"],
                        f"Annualised Sharpe {sb.sr_strategy:.2f} vs {sb.sr_benchmark:.2f}; improvement {f2(sb.d_sr)}, paired "
                        f"stationary-bootstrap 5th percentile {f2(sb.d_sr_lo)} ({sb.n_boot} draws).",
                        "Test the improvement on a period with different market conditions, or in a sealed forward trial." if st != PASS else ""))
    if ho["d_sr_oos"] > 0 and ho["d_sr_is"] > 0 and ho["d_sr_oos"] >= 0.5 * ho["d_sr_is"]:
        st = PASS
    elif ho["d_sr_oos"] > 0:
        st = CAUTION
    else:
        st = FAIL
    checks.append(Check("holdout", "Holdout: Sharpe improvement", st, f"dSR {f2(ho['d_sr_is'])} -> {f2(ho['d_sr_oos'])}", R["holdout"],
                        f"Sharpe improvement {f2(ho['d_sr_is'])} before {ho['split_date'].date()} and {f2(ho['d_sr_oos'])} after.",
                        "Lock a fresh holdout or run a sealed forward trial." if st != PASS else ""))
    share = float(yearly["higher"].mean()) if len(yearly) else float("nan")
    worst = float(regimes["d_sr"].min()) if regimes is not None else None
    st = PASS if share >= 0.6 and (worst is None or worst > 0) else CAUTION if share >= 0.5 else FAIL
    reg = "" if regimes is None else " dSR by volatility tercile: " + ", ".join(f"{r.regime} {f2(r.d_sr)}" for r in regimes.itertuples()) + "."
    checks.append(Check("stability", "Stability of the Sharpe improvement", st, f"{_fmt(100 * share, 0)}% of years higher", R["stability"],
                        f"The strategy's Sharpe was higher than the benchmark's in {int(yearly['higher'].sum())} of {len(yearly)} years.{reg}",
                        "State the regime in which the improvement is expected and test it where the rule was not designed." if st != PASS else ""))
    if costs is None:
        checks.append(Check("costs", "Transaction-cost headroom", NA, "no turnover data", R["costs"], "No turnover column was supplied.", ""))
    else:
        st = _band(costs.breakeven_bps, 20.0, 5.0)
        checks.append(Check("costs", "Transaction-cost headroom (absolute)", st, f"break-even {_fmt(costs.breakeven_bps, 1)} bps",
                            R["costs"], f"The gross mean return falls to zero at {_fmt(costs.breakeven_bps, 1)} bps per unit traded.",
                            "Measure real fills and re-run at that cost." if st != PASS else ""))
    if surface is None:
        checks.append(Check("surface", "Parameter plateau (dSR)", NA, "no grid", R["surface"], "No parameter grid was supplied.", ""))
    else:
        st = FAIL if surface.chosen_sr <= 0 else _band(surface.neighbor_ratio, 0.70, 0.40)
        checks.append(Check("surface", "Parameter plateau (dSR)", st, f"neighbours {_fmt(100 * surface.neighbor_ratio, 0)}% of chosen",
                            R["surface"],
                            f"The chosen variant ranks {surface.rank_of_chosen} of {len(surface.table)} by Sharpe improvement; its "
                            f"one-step neighbours average {_fmt(100 * surface.neighbor_ratio, 0)}% of its improvement.",
                            "Prefer the centre of a plateau." if st != PASS else ""))
    return checks, {"sharpe_boot": sb, "deflated": d_obj, "theta0_annual": theta0 * q, "p_adj": p_adj, "pbo": pb,
                    "holdout": ho, "yearly": yearly, "regimes": regimes, "surface": surface}
