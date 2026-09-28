"""``holdout-audit ci``: run the standard audit in a CI job and report it as markdown, outputs and a badge.

This module only formats results. Every statistic comes from :func:`holdout_audit.audit.run_audit`.
The grade rates how fragile the *historical* evidence is; it is not a forecast and not investment advice.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd

from holdout_audit import __version__
from holdout_audit.audit import BENCHMARK_NAMES, AuditConfig, AuditResult, run_audit
from holdout_audit.grade import GRADE_MEANING, GRADE_ORDER
from holdout_audit.io import load_returns, load_variants

TOOL_URL = "https://holdoutlabs.io/tools/luck/"
REPO_URL = "https://github.com/holdoutlabs-io/holdout-audit"
COMMENT_MARKER = "<!-- holdout-audit-ci -->"
FOOTER = "Statistics on past data, not investment advice."

FREQUENCIES = {"daily": 252, "business": 252, "daily-365": 365, "crypto": 365, "weekly": 52, "monthly": 12}
BADGE_COLORS = {"A": "#4c1", "B": "#97ca00", "C": "#dfb317", "D": "#fe7d37", "F": "#e05d44"}


def parse_frequency(value: str | None) -> int | None:
    """``auto``/empty -> None (inferred from the dates); a name from FREQUENCIES; or a positive integer."""
    if value is None or str(value).strip().lower() in ("", "auto"):
        return None
    v = str(value).strip().lower()
    if v in FREQUENCIES:
        return FREQUENCIES[v]
    try:
        n = int(v)
    except ValueError:
        raise ValueError(f"frequency must be auto, {', '.join(FREQUENCIES)} or a number of periods per year; got {value!r}")
    if n <= 0:
        raise ValueError("frequency must be a positive number of periods per year")
    return n


def attach_benchmark(returns: pd.DataFrame, benchmark: str | None, percent: bool = False) -> tuple[pd.DataFrame, str]:
    """Resolve ``benchmark``: ``auto``/``zero``/``market`` pass through; anything else is a CSV path whose
    return column becomes the ``market`` column (joined on date) and the benchmark is ``market``."""
    b = (benchmark or "auto").strip()
    if b.lower() in ("auto", "zero", "market", ""):
        return returns, (b.lower() or "auto")
    bench = load_returns(b, percent=percent)["return"]
    out = returns.copy()
    out["market"] = bench.reindex(out.index)
    if out["market"].notna().sum() < 60:
        raise ValueError(f"benchmark file {b!r} overlaps the returns on fewer than 60 dates")
    return out, "market"


def _f(x, nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:.{nd}f}"


def summary_markdown(res: AuditResult) -> str:
    """Markdown for the job summary and the pull-request comment."""
    g = res.grade
    by = {c.key: c for c in g.checks}
    ho = res.holdout
    v = res.rubric["version"]

    def status(key: str) -> str:
        c = by.get(key)
        return "" if c is None else c.status

    rows = [
        (f"Deflated Sharpe ratio (N = {res.n_trials} trial{'s' if res.n_trials != 1 else ''})", _f(res.dsr, 3), status("dsr")),
        ("Probability of backtest overfitting (CSCV)",
         "not computed (no variants file)" if res.pbo is None else f"{_f(res.pbo.pbo, 3)} ({res.pbo.n_splits} splits)",
         status("pbo")),
        (f"Holdout: excess Sharpe in-sample -> holdout (from {ho.split_date.date()}, {ho.n_oos} periods)",
         f"{_f(ho.sr_is_annual)} -> {_f(ho.sr_oos_annual)}", status("holdout")),
        ("Multiple-testing haircut, adjusted p", _f(res.haircut.p_adjusted, 4), status("haircut")),
        ("Hansen SPA p (vs benchmark)", _f(res.spa.p_spa, 3), status("spa")),
    ]
    lines = [
        COMMENT_MARKER,
        f"### Holdout audit: fragility grade **{g.letter}**",
        "",
        f"**{res.config.name}**; rubric v{v}; score {g.points}/{g.max_points} ({_f(100 * g.score, 0)}%); "
        f"benchmark: {res.benchmark}; {res.net.size} periods, {res.ppy}/year",
        "",
        f"> {GRADE_MEANING[g.letter]} The grade (A = least fragile, F = most fragile) rates how well the historical "
        "evidence survives selection, holdout and stability tests. It is not a forecast of future returns.",
        "",
        "| Statistic | Value | Check |",
        "|---|---|---|",
        *[f"| {a} | {b} | {c} |" for a, b, c in rows],
        "",
    ]
    if g.caps:
        lines += ["**Grade caps applied:**", *[f"- {c}" for c in g.caps], ""]
    lines += [
        "<details><summary>All rubric checks</summary>",
        "",
        "| Check | Status | Value |",
        "|---|---|---|",
        *[f"| {c.name} | {c.status} | {c.value} |" for c in g.checks],
        "",
        f"Benchmark: {BENCHMARK_NAMES[res.benchmark]}. {res.benchmark_note}" + ("" if res.n_trials > 1 or res.pbo is not None else
                                   " The number of variants tried was not declared, so N = 1 was assumed."),
        "",
        "</details>",
        "",
        f"Try it without CI: [holdoutlabs.io/tools/luck]({TOOL_URL}); Source and methods: "
        f"[holdout-audit]({REPO_URL}) ([rubric v{v}]({REPO_URL}/blob/main/docs/RUBRIC-v{v}.md)); "
        f"holdout-audit {__version__}",
        "",
        f"_{FOOTER}_",
        "",
    ]
    return "\n".join(lines)


# Approximate Verdana 11px advance widths (px), enough to size a shields-style badge.
_NARROW = set("fijlrtI|.,:;!' ()[]")
_WIDE = set("mwMW@%")


def _text_width(s: str) -> float:
    w = 0.0
    for ch in s:
        if ch in _NARROW:
            w += 4.0
        elif ch in _WIDE:
            w += 10.5
        elif ch.isupper() or ch.isdigit():
            w += 7.5
        else:
            w += 6.8
    return w


def badge_svg(letter: str, label: str = "holdout grade") -> str:
    """Self-contained shields-style (flat) SVG badge: ``label | letter``."""
    color = BADGE_COLORS.get(letter, "#9f9f9f")
    lw = round(_text_width(label) + 12)
    rw = round(_text_width(letter) + 12)
    total = lw + rw
    title = f"{label}: {letter} (fragility of past data; not a forecast, not investment advice). {TOOL_URL} {REPO_URL}"
    lx, rx = lw * 5, (lw + rw / 2) * 10
    lt, rt = (lw - 12) * 10, (rw - 12) * 10
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{total}" '
        f'height="20" role="img" aria-label="{escape(label)}: {escape(letter)}">'
        f"<title>{escape(title)}</title>"
        f'<a xlink:href="{TOOL_URL}" href="{TOOL_URL}" target="_blank">'
        '<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
        '<stop offset="1" stop-opacity=".1"/></linearGradient>'
        f'<clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>'
        f'<g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#555"/>'
        f'<rect x="{lw}" width="{rw}" height="20" fill="{color}"/>'
        f'<rect width="{total}" height="20" fill="url(#s)"/></g>'
        '<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        'text-rendering="geometricPrecision" font-size="110">'
        f'<text aria-hidden="true" x="{lx}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" '
        f'textLength="{lt}">{escape(label)}</text>'
        f'<text x="{lx}" y="140" transform="scale(.1)" fill="#fff" textLength="{lt}">{escape(label)}</text>'
        f'<text aria-hidden="true" x="{rx:g}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" '
        f'textLength="{rt}">{escape(letter)}</text>'
        f'<text x="{rx:g}" y="140" transform="scale(.1)" fill="#fff" textLength="{rt}">{escape(letter)}</text>'
        "</g></a></svg>\n"
    )


def outputs(res: AuditResult) -> dict:
    return {
        "grade": res.grade.letter,
        "score": f"{res.grade.score:.3f}",
        "dsr": f"{res.dsr:.4f}",
        "pbo": "" if res.pbo is None else f"{res.pbo.pbo:.4f}",
        "n-trials": str(res.n_trials),
        "holdout-sr-is": f"{res.holdout.sr_is_annual:.3f}",
        "holdout-sr-oos": f"{res.holdout.sr_oos_annual:.3f}",
        "rubric-version": res.rubric["version"],
    }


def below(letter: str, threshold: str) -> bool:
    """True if ``letter`` is a worse grade than ``threshold`` (e.g. D is below C)."""
    return GRADE_ORDER.index(letter) > GRADE_ORDER.index(threshold)


def run_ci(a) -> int:
    returns = load_returns(a.returns, percent=a.percent)
    returns, bmode = attach_benchmark(returns, a.benchmark, percent=a.percent)
    variants = load_variants(a.variants, percent=a.percent) if a.variants else None
    if a.chosen and (variants is None or a.chosen not in variants.columns):
        raise ValueError(f"--chosen {a.chosen!r} is not a column of the variants file")
    files = {"returns_file_sha256": a.returns}
    if a.variants:
        files["variants_file_sha256"] = a.variants
    cfg = AuditConfig(
        name=a.name or "Strategy", returns=returns, variants=variants, chosen_variant=a.chosen,
        n_trials=a.n_trials, periods_per_year=parse_frequency(a.frequency), holdout_split=a.holdout_start or None,
        base_cost_bps=a.cost_bps, benchmark=bmode, n_boot=a.n_boot, seed=a.seed, data_files=files,
    )
    res = run_audit(cfg)
    md = summary_markdown(res)
    print(md)

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            for k, v in outputs(res).items():
                f.write(f"{k}={v}\n")
    if a.summary_out:
        Path(a.summary_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.summary_out).write_text(md, encoding="utf-8", newline="\n")
    if a.badge:
        Path(a.badge).parent.mkdir(parents=True, exist_ok=True)
        Path(a.badge).write_text(badge_svg(res.grade.letter), encoding="utf-8", newline="\n")
        print(f"badge: {a.badge}")
    if a.report:
        from holdout_audit.report import write_report

        print(f"report: {write_report(res, a.report)}")

    if a.fail_below and below(res.grade.letter, a.fail_below):
        print(f"holdout-audit: grade {res.grade.letter} is below the --fail-below threshold {a.fail_below}")
        return 1
    return 0


def add_parser(sub) -> None:
    ci = sub.add_parser("ci", help="audit in CI: markdown job summary, GitHub outputs and an SVG badge")
    ci.add_argument("--returns", required=True, help="CSV of dates and strategy returns (docs/INPUT-FORMATS.md)")
    ci.add_argument("--benchmark", default="auto",
                    help="auto | zero | market, or a CSV of benchmark returns (date,return) joined on date")
    ci.add_argument("--variants", help="CSV matrix of the returns of every variant tried (enables PBO; sets N)")
    ci.add_argument("--chosen", help="variant column that is the audited strategy")
    ci.add_argument("--n-trials", type=int, help="number of variants tried, if there is no variants file")
    ci.add_argument("--holdout-start", help="YYYY-MM-DD first date of the holdout; default: last 30%% of the sample")
    ci.add_argument("--frequency", default="auto",
                    help=f"auto, {', '.join(FREQUENCIES)} or periods per year (e.g. 252)")
    ci.add_argument("--cost-bps", type=float, default=0.0, help="one-way cost per unit turnover (bps)")
    ci.add_argument("--name", help="strategy name shown in the summary (default: Strategy)")
    ci.add_argument("--percent", action="store_true", help="returns are in percent, not fractions")
    ci.add_argument("--n-boot", type=int, default=1000)
    ci.add_argument("--seed", type=int, default=20260925)
    ci.add_argument("--badge", help="write a shields-style SVG badge to this path")
    ci.add_argument("--summary-out", help="also write the markdown summary to this path")
    ci.add_argument("--report", help="also write the full HTML report to this path")
    ci.add_argument("--fail-below", type=str.upper, choices=list(GRADE_ORDER),
                    help="exit 1 if the grade is worse than this letter (e.g. C fails on D and F)")
    ci.set_defaults(func=run_ci)


__all__ = ["run_ci", "add_parser", "summary_markdown", "badge_svg", "parse_frequency", "below"]
