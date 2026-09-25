"""Builds docs/RUBRIC-v1.2.md from the sealed v1.1 text (kept verbatim for objectives a and b) plus objective (c).
Run once before sealing v1.2; kept for transparency."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from holdout_audit.grade import (CAP_RULES_V12, DECLARATION_RULE_V12, RUBRIC_RULES_V11_BEAT,  # noqa: E402
                                 RUBRIC_RULES_V11_DRAWDOWN, RUBRIC_RULES_V12_SHARPE)

v11 = (ROOT / "docs" / "RUBRIC-v1.1.md").read_text(encoding="utf-8")


def section(text, start, end):
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


common = section(v11, "## 2. Common definitions", "## 3. The checks")
checks_ab = section(v11, "## 3. The checks", "## 4. From points to a letter")
bands = section(v11, "## 4. From points to a letter", "## 5. Hard caps")
decl_v11 = section(v11, "## 1. The declared objective (pre-commitment)", "## 2. Common definitions")

decl = decl_v11.replace("Objective (b) is therefore graded only when a **written declaration** exists.",
                        "Objectives (b) and (c) are therefore graded only when a **written declaration** exists.")
decl = decl.replace("- `objective`: `reduce_drawdown`. The value `beat_benchmark` is also allowed and is the default when nothing is declared;",
                    "- `objective`: `reduce_drawdown` or `improve_sharpe`. The value `beat_benchmark` is also allowed and is the default when nothing is declared;")
decl = re.sub(r"Rule text: .*\n", f"Rule text: {DECLARATION_RULE_V12}\n", decl)

common = common.replace("- **Selection dispersion V**: the sample variance (ddof 1), across variant-matrix columns, of the objective statistic. That is the per-period excess Sharpe under (a) and dCVaR under (b). Without a matrix it is the statistic's sampling variance: 1/T under (a), and the squared bootstrap standard error of dCVaR under (b).",
                        "- **dSR = SR(r) − SR(b)**: the Sharpe-ratio improvement, per period (reported annualised by √q). Positive values favour the strategy.\n"
                        "- **Selection dispersion V**: the sample variance (ddof 1), across variant-matrix columns, of the objective statistic. That is the per-period excess Sharpe under (a), dCVaR under (b) and per-period dSR under (c). Without a matrix it is the statistic's sampling variance: 1/T under (a), and the squared bootstrap standard error of dCVaR under (b) or of dSR under (c).")
common = common.replace("Under objective (b) the resampling is *paired*", "Under objectives (b) and (c) the resampling is *paired*")

c_table = """
### Objective (c): improve Sharpe vs benchmark (eight checks)

For sources whose claim is a better risk-adjusted return rather than a higher return (for example volatility-managed portfolios or low-volatility portfolios).

| # | Key | Check | PASS | CAUTION | FAIL |
|---|---|---|---|---|---|
| 1 | dsr | Deflated dSR: the DSR construction of Bailey & López de Prado (2014) applied to dSR. D = Φ((dSR − θ₀)/SE), where θ₀ = √V·((1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(Ne))) and SE is the paired-bootstrap standard error of dSR | D ≥ 0.95 | 0.80 ≤ D < 0.95 | D < 0.80 |
| 2 | pbo | PBO via CSCV (16 blocks, all 12,870 splits), with variants ranked by dSR (each variant's Sharpe minus the benchmark's Sharpe on the same half) | PBO ≤ 0.20 | ≤ 0.50, or > 0.50 with P(OOS dSR of the IS winner < 0) ≤ 0.10 | otherwise. N/A without a matrix |
| 3 | haircut | Multiple testing: one-sided p = P(Z ≥ dSR/SE) per variant (paired bootstrap on the same resampled days); BHY if every variant is supplied, else Bonferroni over N | adj. p ≤ 0.05 | ≤ 0.10 | > 0.10 |
| 4 | sharpe | **Primary: Sharpe-ratio improvement.** Paired stationary bootstrap of dSR (Ledoit & Wolf 2008) | 5th percentile of dSR > 0 | point dSR > 0 | otherwise |
| 5 | holdout | dSR before and after the holdout split | holdout and in-sample dSR > 0, **and** holdout ≥ 50% of in-sample | holdout dSR > 0 | holdout dSR ≤ 0 |
| 6 | stability | Calendar years in which the strategy's Sharpe exceeds the benchmark's; dSR within terciles of the benchmark's trailing 21-day volatility, lagged 1 period | ≥ 60% of years higher **and** dSR > 0 in every tercile | ≥ 50% of years higher | < 50% |
| 7 | costs | Transaction-cost headroom (absolute, as in v1.0) | ≥ 20 bps | ≥ 5 bps | < 5 bps. N/A without turnover |
| 8 | surface | Parameter plateau on dSR: the mean dSR of one-step neighbours ÷ the chosen variant's dSR | ≥ 0.70 | ≥ 0.40 | < 0.40, or chosen dSR ≤ 0. N/A without a grid |

"""

caps = """## 5. Hard caps (applied after the bands; the most severe cap wins)

1. **Objective cap.** Under (a), if the strategy does not beat its benchmark, the grade is at most **C**. Under (b), if the drawdown reduction is not robust (check 4 FAIL) or the declared tolerance is breached (check 5 FAIL), the grade is at most **C**. Under (c), if the Sharpe-ratio improvement is not robust (check 4 FAIL), the grade is at most **C**.
2. **Selection cap.** If check 1 FAILs, the grade is at most **C**.
3. **Overfitting cap.** If the PBO check FAILs, the grade is at most **D**.
4. **Disclosure cap.** If N is undeclared and no variant matrix is supplied, the grade is at most **B**.

"""

rules_txt = "## 6. Rule text as printed in every report\n\nThese strings are part of the rubric, and reports print them verbatim.\n\n"
rules_txt += "Objective (a), beat the benchmark (unchanged from v1.1):\n\n" + "".join(f"- `{k}`: {v}\n" for k, v in RUBRIC_RULES_V11_BEAT.items())
rules_txt += "\nObjective (b), reduce drawdown at acceptable cost (unchanged from v1.1):\n\n" + "".join(f"- `{k}`: {v}\n" for k, v in RUBRIC_RULES_V11_DRAWDOWN.items())
rules_txt += "\nObjective (c), improve Sharpe vs benchmark (new in v1.2):\n\n" + "".join(f"- `{k}`: {v}\n" for k, v in RUBRIC_RULES_V12_SHARPE.items())
rules_txt += "\nThe caps, in the order they are applied:\n\n" + "".join(f"- {c}\n" for c in CAP_RULES_V12)
rules_txt += f"\nThe declaration rule:\n\n- {DECLARATION_RULE_V12}\n\n"

head = """# Holdout Labs Fragility Rubric, version 1.2

Status: **frozen**. This document is sealed with RFC 3161 timestamps (DigiCert and FreeTSA); the receipts are in `docs/rubric-seal-v1.2/`. Any change requires a new version number, a new seal and an entry in the change log of `docs/METHODS.md`, all *before* the new version is applied to any audit.

The grade describes how fragile the historical evidence for a strategy's **declared objective** is. It is not a forecast and not a recommendation.

## 0. What changed from v1.1

1. **New objective (c), "improve Sharpe vs benchmark".** It is for sources whose claim is a better risk-adjusted return rather than a higher return. It has the same overfitting corrections and caps as the other objectives (§3, §5).
2. **Objectives (a) and (b) are unchanged.** Their checks, thresholds, rule text and caps are copied verbatim from v1.1.
3. Reports published under v1.0 and v1.1 keep their versions. They are not re-graded.

"""

version = """## 7. Version

- Rubric version: **1.2**
- Supersedes v1.1 for new audits. Reports published under v1.0 and v1.1 keep their versions.
- Package implementing it: holdout-audit 0.4.0 (`src/holdout_audit/grade.py`, `src/holdout_audit/audit.py`, `src/holdout_audit/stats/objective_sharpe.py`).
- Additional reference for (c): Ledoit, O. & Wolf, M. (2008). Robust performance hypothesis testing with the Sharpe ratio. *Journal of Empirical Finance* 15(5), 850–859.
"""

doc = head + decl + common + checks_ab.rstrip() + "\n" + c_table + bands + caps + rules_txt + version
doc = doc.replace("## 3. The checks", "## 3. The checks", 1)
(ROOT / "docs" / "RUBRIC-v1.2.md").write_bytes(doc.encode("utf-8"))
print(len(doc))
