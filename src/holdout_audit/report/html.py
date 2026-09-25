"""Branded, print-ready HTML audit report (self-contained: inline CSS and SVG, no external requests)."""

from __future__ import annotations

import math
from html import escape
from pathlib import Path

import numpy as np

from holdout_audit import __version__
from holdout_audit.grade import GRADE_BANDS, GRADE_MEANING, NA, OBJECTIVE_DRAWDOWN, OBJECTIVE_SHARPE, rules_for
from holdout_audit.report import charts
from holdout_audit.stats.bootstrap import max_drawdown
from holdout_audit.report.methods import CITATIONS, DISCLAIMER, METHODS

CSS = """
:root{--ink:#16202a;--muted:#5b6770;--line:#d9dee2;--paper:#ffffff;--wash:#f4f6f7;--accent:#0f6e6e;
--pass:#1d7a46;--caution:#a26400;--fail:#b3261e;--na:#7a848c;--bench:#9aa5ad;--pos:#2f7f8f;--neg:#c0533f}
*{box-sizing:border-box}
body{margin:0;background:var(--wash);color:var(--ink);font:15px/1.55 "Inter","Segoe UI",system-ui,-apple-system,sans-serif}
main{max-width:960px;margin:0 auto;background:var(--paper);padding:40px 48px 56px}
header.brand{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:3px solid var(--ink);padding-bottom:14px;margin-bottom:28px;gap:16px;flex-wrap:wrap}
.wordmark{font-weight:800;letter-spacing:.02em;font-size:22px}.wordmark span{color:var(--accent)}
.tagline{color:var(--muted);font-size:13px}
.meta{font-size:12px;color:var(--muted);text-align:right}
h1{font-size:28px;margin:0 0 4px}h2{font-size:20px;margin:40px 0 12px;padding-top:8px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:24px 0 8px}
.sub{color:var(--muted);margin:0 0 20px}
.summary{display:grid;grid-template-columns:170px 1fr;gap:24px;align-items:start}
.gradebox{border:2px solid var(--ink);border-radius:10px;text-align:center;padding:14px 8px}
.gradebox .letter{font-size:84px;font-weight:800;line-height:1}
.gradebox .cap{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.g-A{color:var(--pass)}.g-B{color:#4c7a2b}.g-C{color:var(--caution)}.g-D{color:#c0531f}.g-F{color:var(--fail)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.tile{background:var(--wash);border-radius:8px;padding:10px 12px}.tile .k{font-size:12px;color:var(--muted)}
.tile .v{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:8px 0 12px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.pill{display:inline-block;border-radius:999px;padding:1px 9px;font-size:11.5px;font-weight:700;color:#fff}
.PASS{background:var(--pass)}.CAUTION{background:var(--caution)}.FAIL{background:var(--fail)}.NA{background:var(--na)}
.note{font-size:13px;color:var(--muted)}
.callout{border-left:4px solid var(--accent);background:var(--wash);padding:10px 14px;margin:12px 0;border-radius:0 6px 6px 0}
.fix{border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:10px 0;break-inside:avoid}
.fix h4{margin:0 0 4px;font-size:14.5px}
figure{margin:12px 0 18px;break-inside:avoid}figcaption{font-size:12.5px;color:var(--muted)}
svg.chart{width:100%;height:auto;display:block}
svg .grid{stroke:var(--line);stroke-width:1}svg .axis{stroke:var(--ink);stroke-width:1}
svg .tick{fill:var(--muted);font-size:11px}svg .lbl{fill:var(--ink);font-size:11.5px}
svg .ln-main{fill:none;stroke:var(--accent);stroke-width:2}svg .ln-bench{fill:none;stroke:var(--bench);stroke-width:1.5}
svg .holdout{fill:var(--accent);fill-opacity:.08}svg .ref{stroke:var(--fail);stroke-width:1.5;stroke-dasharray:5 4}
svg .bar-pos{fill:var(--pos)}svg .bar-neg{fill:var(--neg)}svg .bar-hi{fill:var(--ink)}
svg .dot{fill:var(--accent)}svg .dot-hi{fill:var(--ink)}
svg .hm-pos{fill:var(--pos)}svg .hm-neg{fill:var(--neg)}svg .hm-txt{fill:var(--ink);font-size:11px}svg .hm-chosen{stroke:var(--ink)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
code,.mono{font-family:"JetBrains Mono",Consolas,monospace;font-size:12px;word-break:break-all}
.disclaimer{margin-top:36px;border:1.5px solid var(--ink);border-radius:8px;padding:12px 16px;font-size:12.5px}
ol.refs li{margin-bottom:4px;font-size:13px}
footer{margin-top:28px;font-size:11.5px;color:var(--muted);text-align:center}
@media (max-width:720px){main{padding:20px 16px}.summary,.two{grid-template-columns:1fr}.gradebox{max-width:200px}}
@media print{body{background:#fff}main{padding:0;max-width:none}h2{break-after:avoid}
 .pill{-webkit-print-color-adjust:exact;print-color-adjust:exact}
 svg,.tile,.gradebox{-webkit-print-color-adjust:exact;print-color-adjust:exact}
 @page{size:A4;margin:16mm 14mm}}
"""


def _f(x, nd=2, pct=False, sign=False) -> str:
    if x is None:
        return "n/a"
    try:
        x = float(x)
    except (TypeError, ValueError):
        return escape(str(x))
    if math.isnan(x):
        return "n/a"
    if math.isinf(x):
        return "&infin;"
    if pct:
        return f"{x * 100:{'+' if sign else ''}.{nd}f}%"
    if nd >= 3 and 0 < abs(x) < 10 ** -nd:
        return f"&lt;{10 ** -nd:.{nd}f}"
    return f"{x:{'+' if sign else ''}.{nd}f}"


def _pill(status: str) -> str:
    cls = "NA" if status == NA else status
    return f'<span class="pill {cls}">{escape(status)}</span>'


def _tile(k: str, v: str) -> str:
    return f'<div class="tile"><div class="k">{escape(k)}</div><div class="v">{v}</div></div>'


def _bh_sharpe(bench, res) -> float:
    b = bench.reindex(res.net.index).dropna()
    return float(b.mean() / b.std(ddof=1) * math.sqrt(res.ppy)) if len(b) > 2 and b.std(ddof=1) > 0 else float("nan")


def _cagr(r, ppy) -> float:
    r = r.dropna()
    return float(np.prod(1 + r.to_numpy()) ** (ppy / len(r)) - 1) if len(r) else float("nan")


def render_report(res) -> str:
    cfg = res.config
    ss = res.sharpe
    g = res.grade
    report_id = res.hashes.get("config_sha256", "")[:12]
    bench = cfg.returns["market"] if "market" in cfg.returns else None  # buy-and-hold line on the chart
    sx = res.sharpe_excess
    rb = res.rubric
    bname = "buy-and-hold of the traded asset" if res.benchmark == "market" else "zero (cash)"
    out: list[str] = []
    a = out.append

    a(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
      f'<title>Fragility Audit: {escape(cfg.name)}</title><style>{CSS}</style></head><body><main>')
    a('<header class="brand"><div><div class="wordmark">Holdout<span>Labs</span></div>'
      '<div class="tagline">Scientific audits for trading strategies</div></div>'
      f'<div class="meta">Strategy Fragility Audit<br>Report {escape(report_id)} &middot; {escape(res.generated_utc)}'
      f'<br>holdout-audit {escape(__version__)} &middot; rubric v{escape(rb["version"])}</div></header>')
    a(f'<h1>{escape(cfg.name)}</h1><p class="sub">{escape(cfg.description)}</p>')

    # ------------------------------------------------------------ executive summary
    a('<h2 id="summary">Executive summary</h2><div class="summary">')
    a(f'<div class="gradebox"><div class="cap">Fragility grade</div><div class="letter g-{g.letter}">{g.letter}</div>'
      f'<div class="cap">{g.points}/{g.max_points} points ({_f(g.score * 100, 0)}%)</div></div><div>')
    a(f'<p><strong>{escape(GRADE_MEANING[g.letter])}</strong> The grade measures how fragile the historical evidence is. '
      'It is not a forecast and not a recommendation.</p>')
    dd_obj = res.objective == OBJECTIVE_DRAWDOWN
    sh_obj = res.objective == OBJECTIVE_SHARPE
    _, cap_rules = rules_for(rb["version"], res.objective)
    if rb["version"] != "1.0":
        dec = res.declaration
        how = (f'declared by the client on {escape(str(dec.declared_at_utc))} (declaration SHA-256 '
               f'<span class="mono">{escape(dec.sha256[:16])}…</span>)' if dec and dec.source == "file"
               else 'the default; no objective declaration was supplied')
        a(f'<p><strong>Declared objective:</strong> {escape(res.objective_label)}, {how}.'
          + (f' Declared return-cost tolerance: {_f(dec.max_return_shortfall_annual, 1, pct=True)} a year.' if dd_obj else '')
          + '</p>')
    if dd_obj:
        met = not any("Objective cap" in c for c in g.caps) and all(
            c.status != "FAIL" for c in g.checks if c.key in ("drawdown", "tolerance"))
        a(f'<p><strong>Benchmark:</strong> {escape(bname)}. {escape(res.benchmark_note)} '
          + ('The drawdown reduction was robust and within the declared cost.' if met else
             'The drawdown reduction was not robust or exceeded the declared cost, so the grade is at most C.')
          + '</p>')
    elif sh_obj:
        met = all(c.status != "FAIL" for c in g.checks if c.key == "sharpe")
        a(f'<p><strong>Benchmark:</strong> {escape(bname)}. {escape(res.benchmark_note)} '
          + ('The Sharpe-ratio improvement was robust under the rubric definition.' if met else
             'The Sharpe-ratio improvement was not robust, so the grade is at most C.')
          + '</p>')
    else:
        a(f'<p><strong>Benchmark:</strong> {escape(bname)}. {escape(res.benchmark_note)} '
          + ('The strategy <strong>beat</strong> its benchmark under the rubric definition.' if res.beats_benchmark else
             'The strategy <strong>did not beat</strong> its benchmark under the rubric definition, so the grade is at most C.')
          + '</p>')
    lo95, hi95 = sx.ci95_annual
    if dd_obj:
        ob = res.obj["boot"]
        a('<div class="tiles">'
          + _tile("Max drawdown: strategy vs benchmark", f"{_f(ob.mdd_strategy, 1, pct=True)} vs {_f(ob.mdd_benchmark, 1, pct=True)}")
          + _tile("Drawdown reduction (5th pct)", f"{_f(ob.d_mdd, 1, pct=True)} <span class='note'>[{_f(ob.d_mdd_lo, 1, pct=True)}]</span>")
          + _tile("Daily CVaR95 reduction", f"{_f(ob.d_cvar * 1e4, 1)} bps")
          + _tile("Return shortfall vs tolerance", f"{_f(ob.shortfall, 1, pct=True)} vs {_f(res.obj['tolerance'], 1, pct=True)}")
          + _tile(f"Deflated dCVaR (N={res.n_trials})", _f(res.obj["deflated"], 3))
          + _tile("PBO (CSCV, dCVaR)", "n/a" if res.obj["pbo"] is None else _f(res.obj["pbo"].pbo, 3))
          + '</div>')
    if sh_obj:
        sb = res.obj["sharpe_boot"]
        a('<div class="tiles">'
          + _tile("Sharpe: strategy vs benchmark", f"{_f(sb.sr_strategy)} vs {_f(sb.sr_benchmark)}")
          + _tile("Sharpe improvement (5th pct)", f"{_f(sb.d_sr, sign=True)} <span class='note'>[{_f(sb.d_sr_lo, sign=True)}]</span>")
          + _tile(f"Deflated dSR (N={res.n_trials})", _f(res.obj["deflated"], 3))
          + _tile("PBO (CSCV, dSR)", "n/a" if res.obj["pbo"] is None else _f(res.obj["pbo"].pbo, 3))
          + _tile("Holdout dSR (in → out)", f"{_f(res.obj['holdout']['d_sr_is'], sign=True)} &rarr; {_f(res.obj['holdout']['d_sr_oos'], sign=True)}")
          + '</div>')
    a('<div class="tiles">'
      + _tile("Excess Sharpe vs benchmark (95% CI)", f"{_f(sx.sr_annual)} <span class='note'>[{_f(lo95)}, {_f(hi95)}]</span>")
      + _tile("Excess return a year", _f(sx.mean * res.ppy, 1, pct=True))
      + _tile("Absolute Sharpe", _f(ss.sr_annual))
      + _tile(f"Deflated Sharpe (N={res.n_trials})", _f(res.dsr, 3))
      + _tile("PBO (CSCV)", "n/a" if res.pbo is None else _f(res.pbo.pbo, 3))
      + _tile("Holdout excess Sharpe (in → out)", f"{_f(res.holdout.sr_is_annual)} &rarr; {_f(res.holdout.sr_oos_annual)}")
      + _tile("Max drawdown", _f(res.drawdowns.realized, 1, pct=True))
      + (_tile("Buy-and-hold Sharpe, same period", _f(_bh_sharpe(bench, res))) if bench is not None
         else _tile("Sample", f"{_f(ss.n_obs / res.ppy, 1)} yrs"))
      + '</div>')
    if dd_obj or sh_obj:
        a('<p class="note">The second row is context on the beat-the-benchmark view; it is not graded under the declared '
          'objective.</p>')
    fails = [c for c in g.checks if c.status == "FAIL"]
    if fails:
        a('<p>Checks that failed: ' + "; ".join(escape(c.name) for c in fails) + '.</p>')
    a('</div></div>')
    a('<h3>Scorecard</h3><table><thead><tr><th>Check</th><th>Result</th><th>Value</th><th>Rule</th></tr></thead><tbody>')
    for c in g.checks:
        a(f'<tr><td>{escape(c.name)}</td><td>{_pill(c.status)}</td><td class="num">{escape(c.value)}</td>'
          f'<td class="note">{escape(c.rule)}</td></tr>')
    a('</tbody></table>')
    bands = ", ".join(f"{k} &ge; {int(v * 100)}%" for k, v in GRADE_BANDS if v >= 0) + ", otherwise F"
    a(f'<p class="note"><strong>How the grade is set</strong> (Holdout Labs Fragility Rubric v{escape(rb["version"])}, '
      'sealed before this report was produced). PASS = 2 points, CAUTION = 1, FAIL = 0; N/A checks are '
      f'excluded. Share of available points: {bands}. Hard caps: ' + " ".join(escape(r) for r in cap_rules) + '</p>')
    if g.caps:
        a('<div class="callout"><strong>Cap applied:</strong> ' + " ".join(escape(x) for x in g.caps) + '</div>')

    # ------------------------------------------------------------ strategy as audited
    a('<h2 id="subject">What was audited</h2>')
    if cfg.rules:
        a(f'<div class="callout">{escape(cfg.rules)}</div>')
    a('<table><tbody>')
    a(f'<tr><td>Sample</td><td>{res.net.index[0].date()} to {res.net.index[-1].date()} ({ss.n_obs} periods, {res.ppy} per year)</td></tr>')
    a(f'<tr><td>Variants tried (N)</td><td>{res.n_trials}'
      + (f' &middot; variant matrix of {cfg.variants.shape[1]} columns supplied' if cfg.variants is not None else '')
      + '</td></tr>')
    a(f'<tr><td>Base-case cost</td><td>{cfg.base_cost_bps:g} bps per unit traded (one way)</td></tr>')
    a(f'<tr><td>Holdout split</td><td>{res.holdout.split_date.date()}</td></tr>')
    a(f'<tr><td>Compound annual return, strategy (net)</td><td>{_f(_cagr(res.net, res.ppy), 1, pct=True)}</td></tr>')
    if bench is not None:
        a(f'<tr><td>Buy-and-hold of the underlying, same period</td><td>compound annual return '
          f'{_f(_cagr(bench.reindex(res.net.index), res.ppy), 1, pct=True)}; annualised Sharpe {_f(_bh_sharpe(bench, res))}; '
          f'max drawdown {_f(max_drawdown(bench.reindex(res.net.index).fillna(0)), 1, pct=True)}</td></tr>')
    a('</tbody></table>')

    # ------------------------------------------------------------ detail
    a('<h2 id="detail">Results in detail</h2>')
    a('<figure>' + charts.equity_chart(res.net, bench, res.holdout.split_date, "Growth of 1 (log scale)")
      + '<figcaption>Growth of 1 on a log scale, net of base-case costs'
      + (', with buy-and-hold of the underlying in grey' if bench is not None else '')
      + '. The shaded area is the holdout period.</figcaption></figure>')

    a('<h3>1. Sharpe ratio and its uncertainty</h3>')
    a(f'<p class="note">Rubric checks use the excess series (strategy minus {escape(bname)}); '
      'the absolute series is shown for reference.</p>')
    a('<table><thead><tr><th></th><th class="num">Excess over benchmark</th><th class="num">Absolute</th></tr></thead><tbody>')
    pairs = [
        ("Annualised Sharpe (sqrt-time scaling)", lambda z: _f(z.sr_annual, 3)),
        ("Annualised Sharpe (Lo 2002 autocorrelation-adjusted)", lambda z: _f(z.sr_annual_lo, 3)),
        ("Standard error, annualised (non-normal)", lambda z: _f(z.se_annual, 3)),
        ("Standard error per period: IID-normal / non-normal", lambda z: f"{_f(z.se_iid, 4)} / {_f(z.se_nonnormal, 4)}"),
        ("Skewness / kurtosis", lambda z: f"{_f(z.skew)} / {_f(z.kurt)}"),
        ("Probabilistic Sharpe ratio vs 0", lambda z: _f(z.psr_zero, 4)),
        ("Minimum track record for 95% confidence", lambda z: f"{_f(z.min_trl_years, 1)} years"),
        ("Annualised mean / volatility",
         lambda z: f"{_f(z.mean * res.ppy, 1, pct=True)} / {_f(z.std * math.sqrt(res.ppy), 1, pct=True)}"),
    ]
    for k, fn in pairs:
        a(f'<tr><td>{escape(k)}</td><td class="num">{fn(sx)}</td><td class="num">{fn(ss)}</td></tr>')
    a('</tbody></table>')

    a('<h3>2. The variant-count effect (Deflated Sharpe)</h3>')
    xs = [n for n, _, _ in res.dsr_curve]
    ys = [d for _, d, _ in res.dsr_curve]
    a('<figure>' + charts.line_chart(xs, ys, "Deflated Sharpe ratio against number of variants tried", logx=True,
                                     ref_line=0.95, mark_x=res.n_trials, y_range=(0.0, 1.0), x_label="variants tried (log scale)")
      + f'<figcaption>The same backtest, judged as the best of N tries. The dark dot is the declared N = {res.n_trials}; '
        'the dashed line is the 0.95 pass mark. Computed on the excess Sharpe over the benchmark. The more variants tried, the higher the bar.'
        '</figcaption></figure>')
    a('<table><thead><tr><th>N tried</th><th class="num">Noise hurdle (annual excess SR)</th><th class="num">DSR</th></tr></thead><tbody>')
    for n, d, s0 in res.dsr_curve:
        style = ' style="font-weight:700"' if n == res.n_trials else ''
        a(f'<tr{style}><td>{n}</td><td class="num">{_f(s0, 3)}</td><td class="num">{_f(d, 4)}</td></tr>')
    a('</tbody></table>')
    a(f'<p class="note">Dispersion of trial Sharpe ratios used: {_f(math.sqrt(res.var_trials) * math.sqrt(res.ppy), 3)} '
      f'(annualised standard deviation), {"estimated from the variant matrix" if cfg.variants is not None else "set to the null sampling error 1/sqrt(T)"}.</p>')

    a('<h3>3. Probability of backtest overfitting (CSCV)</h3>')
    if res.pbo is None:
        a('<p class="note">Not computed: no variant matrix supplied.</p>')
    else:
        p = res.pbo
        a('<figure>' + charts.histogram(p.logits, 0.0, "Logit of the in-sample winner's out-of-sample rank",
                                        "median", bins=25, pct=False)
          + '</figure><table><tbody>'
          f'<tr><td>PBO</td><td class="num">{_f(p.pbo, 3)}</td></tr>'
          f'<tr><td>Splits (blocks)</td><td class="num">{p.n_splits} ({p.n_blocks})</td></tr>'
          f'<tr><td>Variants</td><td class="num">{p.n_variants}</td></tr>'
          f'<tr><td>P(IS winner trails benchmark out of sample)</td><td class="num">{_f(p.prob_oos_loss, 3)}</td></tr>'
          f'<tr><td>Median OOS excess Sharpe of IS winner (annual)</td><td class="num">{_f(float(np.median(p.oos_sr_best)) * math.sqrt(res.ppy))}</td></tr>'
          f'<tr><td>Degradation slope (OOS on IS)</td><td class="num">{_f(p.degradation_slope)}</td></tr>'
          '</tbody></table>')
        a('<p class="note">Histogram of logit ranks: values left of the dashed line are splits where the in-sample winner '
          'finished at or below the out-of-sample median (logit 0).</p>')

    hc = res.haircut
    a('<h3>4. Multiple-testing haircut</h3><table><tbody>')
    for k, v in [
        ("t-statistic (excess SR x sqrt(years))", _f(hc.t_stat)),
        ("p-value, single test", _f(hc.p_single, 5)),
        (f"Bonferroni p ({hc.n_tests} tests)", _f(hc.p_bonferroni, 5)),
        ("Sidak p", _f(hc.p_sidak, 5)),
        ("Holm p", _f(hc.p_holm, 5)),
        ("BHY p", _f(hc.p_bhy, 5)),
        ("Haircut excess Sharpe (Bonferroni)", f"{_f(hc.sr_haircut_bonferroni, 3)} ({_f(hc.haircut_pct_bonferroni, 0, pct=True)} haircut)"),
        ("Haircut excess Sharpe (BHY)", _f(hc.sr_haircut_bhy, 3)),
    ]:
        a(f'<tr><td>{escape(k)}</td><td class="num">{v}</td></tr>')
    a('</tbody></table>')

    sp = res.spa
    a('<h3>5. Reality Check and SPA</h3><table><tbody>')
    for k, v in [
        ("Benchmark", bname),
        ("Variants in the test", str(sp.n_variants)),
        ("Best mean excess return (annualised)", _f(sp.best_mean_excess * res.ppy, 2, pct=True)),
        ("White Reality Check p", _f(sp.p_reality_check, 3)),
        ("Hansen SPA p (consistent / lower / upper)", f"{_f(sp.p_spa, 3)} / {_f(sp.p_spa_lower, 3)} / {_f(sp.p_spa_upper, 3)}"),
        ("Bootstrap", f"stationary, {sp.n_boot} draws, mean block {sp.mean_block:.0f}"),
    ]:
        a(f'<tr><td>{escape(k)}</td><td class="num">{escape(v) if k in ("Benchmark", "Bootstrap") else v}</td></tr>')
    a('</tbody></table>')

    ho = res.holdout
    a('<h3>6. Holdout degradation</h3><table><thead><tr><th></th><th class="num">Periods</th><th class="num">Annualised excess Sharpe</th></tr></thead><tbody>'
      f'<tr><td>In-sample (before {ho.split_date.date()})</td><td class="num">{ho.n_is}</td><td class="num">{_f(ho.sr_is_annual, 3)}</td></tr>'
      f'<tr><td>Holdout</td><td class="num">{ho.n_oos}</td><td class="num">{_f(ho.sr_oos_annual, 3)}</td></tr>'
      f'<tr><td>Holdout / in-sample</td><td></td><td class="num">{_f(ho.ratio, 2)}</td></tr>'
      f'<tr><td>Consistency p-value</td><td></td><td class="num">{_f(ho.p_oos_consistent, 3)}</td></tr></tbody></table>')

    a('<h3>7. Period and regime stability</h3>')
    yt = res.yearly
    a('<figure>' + charts.bar_chart(yt["year"].tolist(), yt["excess"].tolist(),
                                    "Return minus benchmark return, by calendar year", pct=True)
      + f'<figcaption>Strategy compounded return minus benchmark compounded return, by year: ahead in '
        f'{int((yt["excess"] > 0).sum())} of {len(yt)} years (absolute return positive in '
        f'{int((yt["return"] > 0).sum())}).</figcaption></figure>')
    if res.regimes is not None:
        a('<table><thead><tr><th>Volatility regime (trailing 21-day, lagged)</th><th class="num">Periods</th>'
          '<th class="num">Annualised mean excess</th><th class="num">Annualised excess Sharpe</th></tr></thead><tbody>')
        for r in res.regimes.itertuples():
            a(f'<tr><td>{escape(r.regime)}</td><td class="num">{r.n}</td><td class="num">{_f(r.ann_return, 1, pct=True)}</td>'
              f'<td class="num">{_f(r.sr_annual)}</td></tr>')
        a('</tbody></table>')

    a('<h3>8. Transaction-cost sensitivity</h3>')
    if res.costs is None:
        a('<p class="note">Not computed: no turnover supplied.</p>')
    else:
        c = res.costs
        a('<table><thead><tr><th>One-way cost (bps per unit traded)</th>' + "".join(f'<th class="num">{b}</th>' for b in c.grid_bps)
          + '</tr></thead><tbody><tr><td>Annualised Sharpe</td>' + "".join(f'<td class="num">{_f(s)}</td>' for s in c.sr_annual)
          + '</tr><tr><td>Annualised mean return</td>' + "".join(f'<td class="num">{_f(r, 1, pct=True)}</td>' for r in c.ann_return)
          + f'</tr></tbody></table><p class="note">Turnover {_f(c.turnover_per_year, 1)} units per year; break-even cost '
            f'{_f(c.breakeven_bps, 1)} bps.</p>')

    a('<h3>9. Parameter sensitivity</h3>')
    su = res.surface
    if su is None:
        a('<p class="note">Not computed: no parameter grid supplied.</p>')
    else:
        chosen = next(iter(su.table.loc[su.table["variant"] == su.chosen].to_dict("records")))
        if len(su.params) >= 2:
            nlev = {p_: su.table[p_].nunique() for p_ in su.params}
            rp, cp = sorted(su.params, key=lambda p_: -nlev[p_])[:2]
            others = [p for p in su.params if p not in (rp, cp)]
            a('<figure>' + charts.heatmap(su.table, rp, cp, "sr_annual", chosen, "Annualised Sharpe across the parameter grid")
              + '<figcaption>Annualised Sharpe by parameter pair'
              + (f' (averaged over {", ".join(others)})' if others else '')
              + '. The outlined cell holds the chosen variant.</figcaption></figure>')
        else:
            p0 = su.params[0]
            t = su.table.sort_values(p0)
            a('<figure>' + charts.bar_chart(t[p0].tolist(), t["sr_annual"].tolist(), "Sharpe by parameter",
                                            highlight=list(t["variant"]).index(su.chosen)) + '</figure>')
        a(f'<p>Chosen variant <code>{escape(su.chosen)}</code> ranks {su.rank_of_chosen} of {len(su.table)}. '
          f'Grid median Sharpe {_f(su.median_sr)}, best {_f(su.best_sr)}; {_f(su.share_positive * 100, 0)}% of cells positive; '
          f'neighbour ratio {_f(su.neighbor_ratio)}.</p>')

    dd = res.drawdowns
    a('<h3>10. Drawdown distribution</h3>')
    a('<figure>' + charts.histogram(dd.boot, dd.realized, "Bootstrap distribution of maximum drawdown", "realised")
      + f'<figcaption>Maximum drawdown in {len(dd.boot)} stationary-bootstrap resamples. Realised: {_f(dd.realized, 1, pct=True)}; '
        f'median {_f(dd.percentiles[50], 1, pct=True)}; 95th percentile {_f(dd.percentiles[95], 1, pct=True)}. '
        f'{_f(dd.prob_worse_than_realized * 100, 0)}% of resamples were worse than the realised drawdown.</figcaption></figure>')

    if dd_obj:
        ob, o = res.obj["boot"], res.obj
        a('<h3>11. Declared objective: drawdown reduction at acceptable cost</h3><table><thead><tr><th></th>'
          '<th class="num">Strategy</th><th class="num">Benchmark</th><th class="num">Reduction</th>'
          '<th class="num">Bootstrap bound</th></tr></thead><tbody>')
        a(f'<tr><td>Maximum drawdown</td><td class="num">{_f(ob.mdd_strategy, 1, pct=True)}</td><td class="num">'
          f'{_f(ob.mdd_benchmark, 1, pct=True)}</td><td class="num">{_f(ob.d_mdd, 1, pct=True)}</td><td class="num">'
          f'5th pct {_f(ob.d_mdd_lo, 1, pct=True)}</td></tr>')
        a(f'<tr><td>Daily CVaR95 (bps)</td><td class="num">{_f(ob.cvar_strategy * 1e4, 1)}</td><td class="num">'
          f'{_f(ob.cvar_benchmark * 1e4, 1)}</td><td class="num">{_f(ob.d_cvar * 1e4, 1)}</td><td class="num">'
          f'5th pct {_f(ob.d_cvar_lo * 1e4, 1)}</td></tr>')
        a(f'<tr><td>Return shortfall a year (tolerance {_f(o["tolerance"], 1, pct=True)})</td><td></td><td></td>'
          f'<td class="num">{_f(ob.shortfall, 1, pct=True)}</td><td class="num">95th pct {_f(ob.shortfall_hi, 1, pct=True)}</td></tr>')
        a('</tbody></table>')
        ho2 = o["holdout"]
        a(f'<p class="note">Deflated dCVaR {_f(o["deflated"], 3)} against a best-of-{res.n_trials} hurdle of '
          f'{_f(o["theta0"] * 1e4, 1)} bps; adjusted one-sided p {_f(o["p_adj"], 4)}. Holdout: dCVaR '
          f'{_f(ho2["d_cvar_is"] * 1e4, 1)} bps before {ho2["split_date"].date()}, {_f(ho2["d_cvar_oos"] * 1e4, 1)} bps after; '
          f'holdout drawdown reduction {_f(ho2["d_mdd_oos"], 1, pct=True)}. Years with a shallower drawdown than the '
          f'benchmark: {int(o["yearly"]["shallower"].sum())} of {len(o["yearly"])}.</p>')

    # ------------------------------------------------------------ fragile + fixes
    a('<h2 id="fragile">What is fragile, and how to test the fix</h2>')
    fixes = [c for c in g.checks if c.status != "PASS"]
    if not fixes:
        a('<p>No check fell below PASS. The next step is still confirmation on unseen data: a sealed forward trial.</p>')
    for c in fixes:
        a(f'<div class="fix"><h4>{_pill(c.status)} {escape(c.name)}</h4><p>{escape(c.finding)}</p>'
          + (f'<p><strong>How to test a fix:</strong> {escape(c.fix)}</p>' if c.fix else '') + '</div>')
    a('<p class="note">These are suggestions for further statistical testing, not suggestions to trade. Any change to the '
      'rules creates a new variant: count it in N and confirm it on data it was not designed on.</p>')
    passes = [c for c in g.checks if c.status == "PASS"]
    if passes:
        a('<h3>What held up</h3><ul>' + "".join(f'<li><strong>{escape(c.name)}</strong>: {escape(c.finding)}</li>' for c in passes) + '</ul>')

    # ------------------------------------------------------------ methods
    a('<h2 id="methods">Methods appendix</h2>')
    order = []
    for m in METHODS:
        for k in m["cite"]:
            if k not in order:
                order.append(k)
    num = {k: i + 1 for i, k in enumerate(order)}
    for m in METHODS:
        refs = ", ".join(f"[{num[k]}]" for k in m["cite"])
        a(f'<h3>{escape(m["name"])}</h3><p>{escape(m["text"])} {refs}</p>')
    a('<h3>References</h3><ol class="refs">' + "".join(f'<li>{escape(CITATIONS[k])}</li>' for k in order) + '</ol>')

    # ------------------------------------------------------------ data + hashes
    a('<h2 id="data">Data and hash appendix</h2>')
    if cfg.data_notes:
        a('<ul>' + "".join(f'<li>{escape(n)}</li>' for n in cfg.data_notes) + '</ul>')
    a('<table><thead><tr><th>Item</th><th>SHA-256 / value</th></tr></thead><tbody>')
    for k, v in res.hashes.items():
        a(f'<tr><td>{escape(k)}</td><td class="mono">{escape(str(v))}</td></tr>')
    a(f'<tr><td>bootstrap seed</td><td class="mono">{cfg.seed}</td></tr>')
    a(f'<tr><td>rubric version</td><td class="mono">{escape(rb["version"])} ({escape(rb["document"])})</td></tr>')
    if rb["version"] != "1.0":
        a(f'<tr><td>declared objective</td><td class="mono">{escape(res.objective)}</td></tr>')
        dec = res.declaration
        if res.prereg_seal:
            ps = res.prereg_seal
            a(f'<tr><td>preregistration seal</td><td class="mono">{escape(ps["seal_sha256"])} '
              f'({escape(", ".join(ps["verified_tsas"]))}; earliest {escape(str(ps["earliest_gen_time_utc"]))})</td></tr>')
        if dec and dec.seal:
            a(f'<tr><td>objective declaration seal</td><td class="mono">{escape(dec.seal["seal_sha256"])} '
              f'({escape(", ".join(dec.seal["verified_tsas"]))}; earliest {escape(str(dec.seal["earliest_gen_time_utc"]))})</td></tr>')
    a(f'<tr><td>rubric document SHA-256</td><td class="mono">{escape(rb["document_sha256"])}</td></tr>')
    a(f'<tr><td>rubric seal record SHA-256</td><td class="mono">{escape(str(rb["seal_sha256"] or "not sealed"))}</td></tr>')
    for tsa, when in rb["tsa_times"].items():
        a(f'<tr><td>rubric sealed by {escape(tsa)} (RFC 3161)</td><td class="mono">{escape(when)}</td></tr>')
    a('</tbody></table>')
    a('<p class="note">Anyone with the same inputs and package version can re-run the audit and must obtain the same '
      'audited-series hash and the same statistics.</p>')

    a(f'<div class="disclaimer"><strong>Important.</strong> {escape(DISCLAIMER)}</div>')
    a('<footer>Holdout Labs &middot; statistical findings about past data only &middot; not investment advice</footer>')
    a('</main></body></html>')
    return "".join(out)


def write_report(res, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:  # LF on every OS: byte-stable reports
        f.write(render_report(res))
    return path
