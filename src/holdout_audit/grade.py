"""Transparent fragility-grade rubric (A = least fragile ... F = most fragile).

Every check scores PASS = 2, CAUTION = 1, FAIL = 0 points, or N/A (excluded). The grade is set
by the share of available points, then capped by four hard rules (docs/RUBRIC-v1.0.md). The rubric is printed in
full in every report so a client can recompute the grade by hand.

The grade describes how *fragile the historical evidence* is. It is not a forecast and not a
recommendation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

PASS, CAUTION, FAIL, NA = "PASS", "CAUTION", "FAIL", "N/A"
POINTS = {PASS: 2, CAUTION: 1, FAIL: 0}
GRADE_BANDS = [("A", 0.85), ("B", 0.70), ("C", 0.55), ("D", 0.40), ("F", -1.0)]
GRADE_ORDER = "ABCDF"


@dataclass(frozen=True)
class Check:
    key: str
    name: str
    status: str
    value: str
    rule: str
    finding: str
    fix: str = ""


@dataclass(frozen=True)
class Grade:
    letter: str
    score: float  # share of available points, 0..1
    points: int
    max_points: int
    checks: list
    caps: list = field(default_factory=list)


# Exact rule text of docs/RUBRIC-v1.0.md, section 2 (tests check every string appears there verbatim).
RUBRIC_RULES = {
    "dsr": "PASS DSR >= 0.95; CAUTION >= 0.80; else FAIL (on excess returns)",
    "pbo": "PASS PBO <= 0.20; CAUTION <= 0.50, or PBO > 0.50 with P(OOS excess SR < 0) <= 0.10; else FAIL",
    "haircut": "PASS adjusted p <= 0.05; CAUTION <= 0.10; else FAIL (excess-return t-statistic)",
    "spa": "PASS p <= 0.05; CAUTION <= 0.10; else FAIL",
    "holdout": "PASS holdout and in-sample excess SR > 0 and holdout >= 50% of in-sample; CAUTION holdout excess SR > 0; else FAIL",
    "stability": "PASS >= 60% of years ahead of benchmark and excess SR > 0 in every volatility tercile; CAUTION >= 50%; else FAIL",
    "costs": "PASS break-even cost >= 20 bps per unit traded; CAUTION >= 5 bps; else FAIL (absolute)",
    "surface": "PASS neighbour SR >= 70% of chosen SR; CAUTION >= 40%; else FAIL, or FAIL if chosen SR <= 0 (absolute)",
}

CAP_RULES = [
    "Benchmark cap: if the strategy does not beat its benchmark (SPA check FAIL, or annualised mean excess return <= 0), the grade is at most C.",
    "Selection cap: if the Deflated Sharpe check FAILS, the grade is at most C.",
    "Overfitting cap: if the PBO check FAILS, the grade is at most D.",
    "Disclosure cap: if the number of variants tried was not declared and no variant matrix was supplied, the grade is at most B.",
]


# ---------------------------------------------------------------- rubric v1.1 (docs/RUBRIC-v1.1.md)
RUBRIC_RULES_V10 = RUBRIC_RULES
CAP_RULES_V10 = CAP_RULES

OBJECTIVE_BEAT = "beat_benchmark"
OBJECTIVE_DRAWDOWN = "reduce_drawdown"

RUBRIC_RULES_V11_BEAT = dict(RUBRIC_RULES_V10)
RUBRIC_RULES_V11_BEAT["haircut"] = ("PASS one-sided adjusted p <= 0.05; CAUTION <= 0.10; else FAIL "
                                    "(excess-return t-statistic; evidence for the strategy only)")

RUBRIC_RULES_V11_DRAWDOWN = {
    "dsr": "PASS deflated dCVaR >= 0.95; CAUTION >= 0.80; else FAIL (DSR construction on the CVaR reduction)",
    "pbo": "PASS PBO <= 0.20; CAUTION <= 0.50, or PBO > 0.50 with P(OOS dCVaR < 0) <= 0.10; else FAIL (variants ranked by dCVaR)",
    "haircut": "PASS one-sided adjusted p <= 0.05; CAUTION <= 0.10; else FAIL (bootstrap z of dCVaR)",
    "drawdown": "PASS 5th-percentile bootstrap dMDD > 0 and dCVaR > 0; CAUTION both point estimates > 0; else FAIL",
    "tolerance": "PASS 95th-percentile bootstrap return shortfall <= declared tolerance; CAUTION point shortfall <= tolerance; else FAIL",
    "holdout": "PASS holdout and in-sample dCVaR > 0, holdout >= 50% of in-sample, and holdout dMDD > 0; CAUTION holdout dCVaR > 0; else FAIL",
    "stability": "PASS >= 60% of years with a shallower drawdown than the benchmark and dCVaR > 0 in every volatility tercile; CAUTION >= 50%; else FAIL",
    "costs": RUBRIC_RULES_V10["costs"],
    "surface": "PASS neighbour dCVaR >= 70% of chosen dCVaR; CAUTION >= 40%; else FAIL, or FAIL if chosen dCVaR <= 0",
}

CAP_RULES_V11 = [
    "Objective cap (beat the benchmark): if the strategy does not beat its benchmark (SPA check FAIL, or annualised mean excess return <= 0), the grade is at most C.",
    "Objective cap (reduce drawdown): if the drawdown reduction is not robust (drawdown check FAIL) or the declared return-cost tolerance is breached (tolerance check FAIL), the grade is at most C.",
    "Selection cap: if the deflated check FAILS, the grade is at most C.",
    CAP_RULES_V10[2],
    CAP_RULES_V10[3],
]

DECLARATION_RULE = ("Declaration rule: objective (b) is graded only with a written declaration of the objective and the "
                    "return-cost tolerance, dated before the audit data were delivered and hashed into the report; "
                    "without one the audit uses objective (a).")


# ---------------------------------------------------------------- rubric v1.2 (docs/RUBRIC-v1.2.md)
OBJECTIVE_SHARPE = "improve_sharpe"

RUBRIC_RULES_V12_SHARPE = {
    "dsr": "PASS deflated dSR >= 0.95; CAUTION >= 0.80; else FAIL (DSR construction on the Sharpe-ratio improvement)",
    "pbo": "PASS PBO <= 0.20; CAUTION <= 0.50, or PBO > 0.50 with P(OOS dSR < 0) <= 0.10; else FAIL (variants ranked by dSR)",
    "haircut": "PASS one-sided adjusted p <= 0.05; CAUTION <= 0.10; else FAIL (bootstrap z of dSR)",
    "sharpe": "PASS 5th-percentile bootstrap dSR > 0; CAUTION point dSR > 0; else FAIL",
    "holdout": "PASS holdout and in-sample dSR > 0 and holdout >= 50% of in-sample; CAUTION holdout dSR > 0; else FAIL",
    "stability": "PASS >= 60% of years with a higher Sharpe than the benchmark and dSR > 0 in every volatility tercile; CAUTION >= 50%; else FAIL",
    "costs": RUBRIC_RULES_V10["costs"],
    "surface": "PASS neighbour dSR >= 70% of chosen dSR; CAUTION >= 40%; else FAIL, or FAIL if chosen dSR <= 0",
}

CAP_RULES_V12 = CAP_RULES_V11[:2] + [
    "Objective cap (improve Sharpe): if the Sharpe-ratio improvement is not robust (Sharpe check FAIL), the grade is at most C.",
] + CAP_RULES_V11[2:]

DECLARATION_RULE_V12 = ("Declaration rule: objectives (b) and (c) are graded only with a written declaration of the objective "
                        "(and, for (b), the return-cost tolerance), dated before the audit data were delivered and hashed into "
                        "the report; without one the audit uses objective (a).")


def rules_for(version: str, objective: str = OBJECTIVE_BEAT) -> tuple[dict, list]:
    if version == "1.0":
        if objective != OBJECTIVE_BEAT:
            raise ValueError("rubric v1.0 has only the beat-the-benchmark objective")
        return RUBRIC_RULES_V10, CAP_RULES_V10
    if version == "1.1":
        if objective == OBJECTIVE_SHARPE:
            raise ValueError("objective (c) exists only from rubric v1.2")
        return (RUBRIC_RULES_V11_BEAT if objective == OBJECTIVE_BEAT else RUBRIC_RULES_V11_DRAWDOWN), CAP_RULES_V11
    if version == "1.2":
        table = {OBJECTIVE_BEAT: RUBRIC_RULES_V11_BEAT, OBJECTIVE_DRAWDOWN: RUBRIC_RULES_V11_DRAWDOWN,
                 OBJECTIVE_SHARPE: RUBRIC_RULES_V12_SHARPE}
        return table[objective], CAP_RULES_V12
    raise ValueError(f"unknown rubric version {version!r}")


def _band(v: float, pass_at: float, caution_at: float, higher_better: bool = True) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return NA
    if higher_better:
        return PASS if v >= pass_at else CAUTION if v >= caution_at else FAIL
    return PASS if v <= pass_at else CAUTION if v <= caution_at else FAIL


def _cap(letter: str, worst_allowed: str) -> str:
    return letter if GRADE_ORDER.index(letter) >= GRADE_ORDER.index(worst_allowed) else worst_allowed


def grade_from_checks(checks: list[Check], variants_declared: bool, beats_benchmark: bool = True,
                      version: str = "1.0", objective: str = OBJECTIVE_BEAT, objective_met: bool | None = None) -> Grade:
    """Letter grade from checks. ``beats_benchmark`` (v1.0, and v1.1 objective a) or ``objective_met``
    (v1.1 objective b) drives the objective cap."""
    scored = [c for c in checks if c.status != NA]
    pts = sum(POINTS[c.status] for c in scored)
    mx = 2 * len(scored)
    share = pts / mx if mx else 0.0
    letter = next(g for g, lo in GRADE_BANDS if share >= lo)
    by = {c.key: c for c in checks}
    dsr_fail = bool(by.get("dsr")) and by["dsr"].status == FAIL
    pbo_fail = bool(by.get("pbo")) and by["pbo"].status == FAIL
    if version == "1.0":
        rules = [(not beats_benchmark, "C", CAP_RULES_V10[0]), (dsr_fail, "C", CAP_RULES_V10[1]),
                 (pbo_fail, "D", CAP_RULES_V10[2]), (not variants_declared, "B", CAP_RULES_V10[3])]
    else:
        caps_list = CAP_RULES_V12 if version == "1.2" else CAP_RULES_V11
        met = objective_met if objective_met is not None else True
        if objective == OBJECTIVE_BEAT:
            obj = (not beats_benchmark, "C", caps_list[0])
        elif objective == OBJECTIVE_DRAWDOWN:
            obj = (not met, "C", caps_list[1])
        else:
            obj = (not met, "C", CAP_RULES_V12[2])
        rules = [obj, (dsr_fail, "C", caps_list[-3]), (pbo_fail, "D", caps_list[-2]),
                 (not variants_declared, "B", caps_list[-1])]
    caps = []
    for applies, worst, text in rules:
        if applies:
            new = _cap(letter, worst)
            if new != letter:
                caps.append(text)
            letter = new
    return Grade(letter, share, pts, mx, checks, caps)


GRADE_MEANING = {
    "A": "Robust on every test we ran. The evidence survives selection, holdout and cost stress.",
    "B": "Mostly robust. One or two weaker spots worth testing further.",
    "C": "Mixed. Part of the historical edge looks explainable by selection, period or cost effects.",
    "D": "Fragile. Most of the historical edge does not survive the stress tests.",
    "F": "Very fragile. The backtest shows no robust edge over its benchmark once selection, holdout and "
         "stability are accounted for.",
}
