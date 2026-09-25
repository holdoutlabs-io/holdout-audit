"""Dependency-free inline SVG charts for the audit report.

Charts use CSS classes (``.ln-main``, ``.bar-pos`` ...) so colours follow the report's theme
and print cleanly. Every chart carries a <title> for accessibility.
"""

from __future__ import annotations

import math
from html import escape

import numpy as np
import pandas as pd

W, H = 640, 240
PAD_L, PAD_R, PAD_T, PAD_B = 56, 16, 14, 30


def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        return [lo]
    span = hi - lo
    step = 10 ** math.floor(math.log10(span / n))
    for m in (1, 2, 2.5, 5, 10):
        if span / (step * m) <= n:
            step *= m
            break
    start = math.ceil(lo / step) * step
    ticks = []
    v = start
    while v <= hi + 1e-12:
        ticks.append(round(v, 10))
        v += step
    return ticks


def _frame(title: str, body: str, w: int = W, h: int = H) -> str:
    cap = f' style="max-width:{int(w * 1.35)}px"' if w < W else ""
    return (f'<svg class="chart"{cap} viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}" '
            f'preserveAspectRatio="xMidYMid meet"><title>{escape(title)}</title>{body}</svg>')


def _fmt_tick(v: float, pct: bool) -> str:
    if pct:
        return f"{v * 100:.0f}%"
    if abs(v) >= 100:
        return f"{v:.0f}"
    if abs(v) >= 10:
        return f"{v:.0f}"
    return f"{v:.2g}" if v != 0 else "0"


def equity_chart(net: pd.Series, bench: pd.Series | None, split_date, title: str) -> str:
    """Growth of 1 on a log scale, with the holdout period shaded."""
    eq = (1 + net.fillna(0)).cumprod()
    series = [("ln-main", eq, "Strategy")]
    if bench is not None:
        series.append(("ln-bench", (1 + bench.reindex(net.index).fillna(0)).cumprod(), "Buy and hold"))
    allv = np.concatenate([np.log10(s.to_numpy()) for _, s, _ in series])
    lo, hi = float(allv.min()), float(allv.max())
    if hi - lo < 1e-9:
        hi = lo + 1
    x0, x1 = net.index[0].value, net.index[-1].value
    iw, ih = W - PAD_L - PAD_R, H - PAD_T - PAD_B

    def X(ts):
        return PAD_L + (pd.Timestamp(ts).value - x0) / (x1 - x0) * iw

    def Y(v):
        return PAD_T + (1 - (v - lo) / (hi - lo)) * ih

    parts = []
    if split_date is not None:
        xs = X(split_date)
        parts.append(f'<rect class="holdout" x="{xs:.1f}" y="{PAD_T}" width="{PAD_L + iw - xs:.1f}" height="{ih}"/>')
        parts.append(f'<text class="lbl" x="{xs + 4:.1f}" y="{PAD_T + 12}">holdout</text>')
    # y ticks at powers of 1, 2, 5
    for e in range(math.floor(lo), math.ceil(hi) + 1):
        for m in (1, 2, 5):
            v = math.log10(m) + e
            if lo <= v <= hi:
                y = Y(v)
                parts.append(f'<line class="grid" x1="{PAD_L}" x2="{PAD_L + iw}" y1="{y:.1f}" y2="{y:.1f}"/>')
                parts.append(f'<text class="tick" x="{PAD_L - 6}" y="{y + 4:.1f}" text-anchor="end">{m * 10 ** e:g}</text>')
    years = sorted(set(net.index.year))
    step = max(1, len(years) // 8)
    for yr in years[::step]:
        x = X(pd.Timestamp(year=yr, month=1, day=1)) if pd.Timestamp(year=yr, month=1, day=1) >= net.index[0] else X(net.index[0])
        parts.append(f'<text class="tick" x="{x:.1f}" y="{H - 10}" text-anchor="middle">{yr}</text>')
    for cls, s, _ in series[::-1]:
        step_pts = max(1, len(s) // 900)
        sv = s.iloc[::step_pts]
        pts = " ".join(f"{X(i):.1f},{Y(math.log10(v)):.1f}" for i, v in zip(sv.index, sv.to_numpy()))
        parts.append(f'<polyline class="{cls}" points="{pts}"/>')
    lx = PAD_L + 8
    for k, (cls, _, lab) in enumerate(series):
        parts.append(f'<line class="{cls}" x1="{lx}" x2="{lx + 18}" y1="{PAD_T + 10 + 14 * k}" y2="{PAD_T + 10 + 14 * k}"/>'
                     f'<text class="lbl" x="{lx + 24}" y="{PAD_T + 14 + 14 * k}">{lab}</text>')
    return _frame(title, "".join(parts))


def bar_chart(labels: list, values: list, title: str, pct: bool = False, highlight: int | None = None,
              ref_line: float | None = None) -> str:
    vals = np.array([0 if (v is None or not math.isfinite(v)) else v for v in values], dtype=float)
    lo, hi = min(0.0, float(vals.min())), max(0.0, float(vals.max()))
    if ref_line is not None:
        lo, hi = min(lo, ref_line), max(hi, ref_line)
    if hi - lo < 1e-12:
        hi = lo + 1
    iw, ih = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    n = len(vals)
    bw = iw / max(n, 1)

    def Y(v):
        return PAD_T + (1 - (v - lo) / (hi - lo)) * ih

    parts = []
    for tv in _nice_ticks(lo, hi):
        y = Y(tv)
        parts.append(f'<line class="grid" x1="{PAD_L}" x2="{PAD_L + iw}" y1="{y:.1f}" y2="{y:.1f}"/>'
                     f'<text class="tick" x="{PAD_L - 6}" y="{y + 4:.1f}" text-anchor="end">{_fmt_tick(tv, pct)}</text>')
    y0 = Y(0)
    for i, v in enumerate(vals):
        x = PAD_L + i * bw + bw * 0.12
        y = min(Y(v), y0)
        h = abs(Y(v) - y0)
        cls = "bar-hi" if highlight == i else ("bar-pos" if v >= 0 else "bar-neg")
        lab = escape(str(labels[i]))
        disp = f"{v * 100:.1f}%" if pct else f"{v:.2f}"
        parts.append(f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{bw * 0.76:.1f}" height="{max(h, 0.5):.1f}">'
                     f'<title>{lab}: {disp}</title></rect>')
    parts.append(f'<line class="axis" x1="{PAD_L}" x2="{PAD_L + iw}" y1="{y0:.1f}" y2="{y0:.1f}"/>')
    if ref_line is not None:
        yr = Y(ref_line)
        parts.append(f'<line class="ref" x1="{PAD_L}" x2="{PAD_L + iw}" y1="{yr:.1f}" y2="{yr:.1f}"/>')
    step = max(1, math.ceil(n / 12))
    for i in range(0, n, step):
        x = PAD_L + (i + 0.5) * bw
        parts.append(f'<text class="tick" x="{x:.1f}" y="{H - 10}" text-anchor="middle">{escape(str(labels[i]))}</text>')
    return _frame(title, "".join(parts))


def histogram(values: np.ndarray, marker: float, title: str, marker_label: str, bins: int = 30, pct: bool = True) -> str:
    counts, edges = np.histogram(values, bins=bins)
    lo, hi = float(min(edges[0], marker)), float(max(edges[-1], marker))
    iw, ih = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    cmax = counts.max() or 1

    def X(v):
        return PAD_L + (v - lo) / (hi - lo) * iw

    parts = []
    for c, a, b in zip(counts, edges[:-1], edges[1:]):
        h = c / cmax * ih
        parts.append(f'<rect class="bar-pos" x="{X(a) + 0.5:.1f}" y="{PAD_T + ih - h:.1f}" width="{max(X(b) - X(a) - 1, 0.5):.1f}" height="{h:.1f}"/>')
    for tv in _nice_ticks(lo, hi, 6):
        parts.append(f'<text class="tick" x="{X(tv):.1f}" y="{H - 10}" text-anchor="middle">{_fmt_tick(tv, pct)}</text>')
    xm = X(marker)
    parts.append(f'<line class="ref" x1="{xm:.1f}" x2="{xm:.1f}" y1="{PAD_T}" y2="{PAD_T + ih}"/>'
                 f'<text class="lbl" x="{xm + 4:.1f}" y="{PAD_T + 12}">{escape(marker_label)}</text>')
    parts.append(f'<line class="axis" x1="{PAD_L}" x2="{PAD_L + iw}" y1="{PAD_T + ih}" y2="{PAD_T + ih}"/>')
    return _frame(title, "".join(parts))


def line_chart(xs: list, ys: list, title: str, logx: bool = False, ref_line: float | None = None,
               mark_x: float | None = None, y_range: tuple | None = None, x_label: str = "", pct: bool = False) -> str:
    fx = (lambda v: math.log10(v)) if logx else (lambda v: v)
    xv = [fx(x) for x in xs]
    lo, hi = y_range if y_range else (min(ys + ([ref_line] if ref_line is not None else [])),
                                      max(ys + ([ref_line] if ref_line is not None else [])))
    if hi - lo < 1e-12:
        hi = lo + 1
    iw, ih = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    x0, x1 = min(xv), max(xv)

    def X(v):
        return PAD_L + (fx(v) - x0) / ((x1 - x0) or 1) * iw

    def Y(v):
        return PAD_T + (1 - (v - lo) / (hi - lo)) * ih

    parts = []
    for tv in _nice_ticks(lo, hi):
        y = Y(tv)
        parts.append(f'<line class="grid" x1="{PAD_L}" x2="{PAD_L + iw}" y1="{y:.1f}" y2="{y:.1f}"/>'
                     f'<text class="tick" x="{PAD_L - 6}" y="{y + 4:.1f}" text-anchor="end">{_fmt_tick(tv, pct)}</text>')
    if ref_line is not None:
        parts.append(f'<line class="ref" x1="{PAD_L}" x2="{PAD_L + iw}" y1="{Y(ref_line):.1f}" y2="{Y(ref_line):.1f}"/>')
    pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in zip(xs, ys))
    parts.append(f'<polyline class="ln-main" points="{pts}"/>')
    for x, y in zip(xs, ys):
        cls = "dot-hi" if mark_x is not None and x == mark_x else "dot"
        parts.append(f'<circle class="{cls}" cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{5 if cls == "dot-hi" else 3}">'
                     f'<title>{x:g}: {y:.3f}</title></circle>')
        parts.append(f'<text class="tick" x="{X(x):.1f}" y="{H - 10}" text-anchor="middle">{x:g}</text>')
    if x_label:
        parts.append(f'<text class="lbl" x="{PAD_L + iw}" y="{H - 22}" text-anchor="end">{escape(x_label)}</text>')
    return _frame(title, "".join(parts))


def heatmap(table: pd.DataFrame, row_param: str, col_param: str, value: str, chosen: dict, title: str) -> str:
    """Mean ``value`` over any other parameters, arranged row_param x col_param."""
    pv = table.groupby([row_param, col_param])[value].mean().unstack(col_param)
    rows, cols = list(pv.index), list(pv.columns)
    cw = min(64, (W - 110) / max(len(cols), 1))
    ch = 26
    h = 40 + ch * len(rows) + 20
    w = 110 + cw * len(cols) + 10
    vals = pv.to_numpy(dtype=float)
    vmax = np.nanmax(np.abs(vals)) or 1.0
    parts = [f'<text class="lbl" x="4" y="14">{escape(row_param)} ↓ / {escape(col_param)} →</text>']
    for j, c in enumerate(cols):
        parts.append(f'<text class="tick" x="{110 + (j + 0.5) * cw:.1f}" y="32" text-anchor="middle">{escape(str(c))}</text>')
    for i, r in enumerate(rows):
        y = 40 + i * ch
        parts.append(f'<text class="tick" x="100" y="{y + ch / 2 + 4:.1f}" text-anchor="end">{escape(str(r))}</text>')
        for j, c in enumerate(cols):
            v = vals[i, j]
            x = 110 + j * cw
            if not math.isfinite(v):
                continue
            a = min(abs(v) / vmax, 1.0)
            cls = "hm-pos" if v >= 0 else "hm-neg"
            is_ch = chosen.get(row_param) == r and chosen.get(col_param) == c
            stroke = ' stroke-width="2.5" class="hm-chosen"' if is_ch else ""
            parts.append(f'<g><rect class="{cls}" x="{x + 1:.1f}" y="{y + 1}" width="{cw - 2:.1f}" height="{ch - 2}" '
                         f'fill-opacity="{0.15 + 0.85 * a:.2f}"/>'
                         + (f'<rect x="{x + 1:.1f}" y="{y + 1}" width="{cw - 2:.1f}" height="{ch - 2}" fill="none"{stroke}/>' if is_ch else "")
                         + f'<text class="hm-txt" x="{x + cw / 2:.1f}" y="{y + ch / 2 + 4:.1f}" text-anchor="middle">{v:.2f}</text>'
                         f'<title>{row_param}={r}, {col_param}={c}: {v:.3f}</title></g>')
    return _frame(title, "".join(parts), int(w), int(h))
