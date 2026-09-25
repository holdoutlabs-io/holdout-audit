"""Methods appendix text and citations, shared by the HTML report and docs/METHODS.md."""

METHODS = [
    {
        "name": "Sharpe ratio and its standard error",
        "text": "Per-period mean over standard deviation of the audited return series (risk-free rate taken as zero), "
                "annualised by the square root of periods per year. The standard error uses the IID-normal formula of "
                "Lo (2002) and the non-normal correction of Mertens (2002), which widens the error for negative skew "
                "and fat tails. Lo's autocorrelation-adjusted annualisation is reported alongside.",
        "cite": ["lo2002", "mertens2002"],
    },
    {
        "name": "Probabilistic Sharpe ratio (PSR) and minimum track record",
        "text": "The probability that the true Sharpe ratio exceeds a benchmark (here zero), given the sample length, "
                "skewness and kurtosis; and the minimum sample length for 95% confidence.",
        "cite": ["bailey2012"],
    },
    {
        "name": "Deflated Sharpe ratio (DSR)",
        "text": "The PSR measured against the Sharpe ratio one would expect from the best of N skill-less trials, "
                "where N is the number of variants tried and the dispersion of trial Sharpe ratios is estimated from the "
                "variant matrix (or, without one, set to the null sampling variance 1/T). It corrects for selection and "
                "non-normality at once.",
        "cite": ["bailey2014"],
    },
    {
        "name": "Probability of backtest overfitting (PBO) via CSCV",
        "text": "The variant matrix is cut into 16 time blocks; for each of the 12,870 ways of picking half of them as "
                "in-sample, the in-sample best variant is ranked out of sample. PBO is the share of splits where it "
                "falls to or below the median. It assumes blocks long enough to preserve serial dependence and a "
                "variant set that represents the real search.",
        "cite": ["bailey2016"],
    },
    {
        "name": "Multiple-testing haircut",
        "text": "The Sharpe ratio is turned into a t-statistic and p-value, the p-value is adjusted for the number of "
                "tests (Bonferroni always; Holm and BHY when every variant's returns are supplied), and the adjusted "
                "p-value is mapped back to a haircut Sharpe ratio.",
        "cite": ["harvey2015", "harvey2016"],
    },
    {
        "name": "White's Reality Check and Hansen's SPA test",
        "text": "Tests whether the best of all variants beats the benchmark in mean return once the search over "
                "variants is accounted for. Uses the stationary bootstrap with mean block length T^(1/3) (at least 5) to "
                "keep short-range dependence. SPA studentises and recentres, so poor variants do not dilute the power.",
        "cite": ["white2000", "hansen2005", "politis1994"],
    },
    {
        "name": "Holdout degradation",
        "text": "In-sample versus holdout Sharpe ratio at a fixed split date (by default the last 30% of the sample). "
                "The consistency p-value asks how surprising the holdout Sharpe would be if the in-sample Sharpe were "
                "the truth. A holdout only counts if it was not used to design the rule.",
        "cite": ["bailey2014b"],
    },
    {
        "name": "Period and regime stability",
        "text": "Returns and Sharpe ratio by calendar year and by tercile of the underlying market's trailing 21-day "
                "volatility (lagged one day). Descriptive: the tercile cut points use the full sample.",
        "cite": ["lopezdeprado2018"],
    },
    {
        "name": "Parameter-sensitivity surface",
        "text": "Sharpe ratio across the supplied parameter grid. The neighbour ratio compares the chosen cell with its "
                "one-step neighbours: a plateau (ratio near 1) is less fragile than an isolated peak.",
        "cite": ["pardo2008"],
    },
    {
        "name": "Transaction-cost sensitivity",
        "text": "Net return = gross return minus turnover times a one-way cost per unit traded, over a grid of costs; "
                "the break-even cost is where the mean net return reaches zero. Market impact beyond a flat cost is not "
                "modelled.",
        "cite": ["lopezdeprado2018"],
    },
    {
        "name": "Drawdown distribution by bootstrap",
        "text": "The maximum drawdown is recomputed on 1,000 stationary-bootstrap resamples of the return series, "
                "showing how much deeper (or shallower) the worst loss could plausibly have been with the same return "
                "distribution in a different order.",
        "cite": ["politis1994"],
    },
]

CITATIONS = {
    "lo2002": "Lo, A. W. (2002). The Statistics of Sharpe Ratios. Financial Analysts Journal 58(4), 36-52.",
    "mertens2002": "Mertens, E. (2002). Comments on Variance of the IID Estimator in Lo (2002). Working paper, University of Basel.",
    "bailey2012": "Bailey, D. H. & Lopez de Prado, M. (2012). The Sharpe Ratio Efficient Frontier. Journal of Risk 15(2), 3-44.",
    "bailey2014": "Bailey, D. H. & Lopez de Prado, M. (2014). The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality. Journal of Portfolio Management 40(5), 94-107.",
    "bailey2014b": "Bailey, D. H., Borwein, J. M., Lopez de Prado, M. & Zhu, Q. J. (2014). Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance. Notices of the AMS 61(5), 458-471.",
    "bailey2016": "Bailey, D. H., Borwein, J. M., Lopez de Prado, M. & Zhu, Q. J. (2016). The Probability of Backtest Overfitting. Journal of Computational Finance 20(4), 39-69.",
    "harvey2015": "Harvey, C. R. & Liu, Y. (2015). Backtesting. Journal of Portfolio Management 42(1), 13-28.",
    "harvey2016": "Harvey, C. R., Liu, Y. & Zhu, H. (2016). ... and the Cross-Section of Expected Returns. Review of Financial Studies 29(1), 5-68.",
    "white2000": "White, H. (2000). A Reality Check for Data Snooping. Econometrica 68(5), 1097-1126.",
    "hansen2005": "Hansen, P. R. (2005). A Test for Superior Predictive Ability. Journal of Business & Economic Statistics 23(4), 365-380.",
    "politis1994": "Politis, D. N. & Romano, J. P. (1994). The Stationary Bootstrap. Journal of the American Statistical Association 89(428), 1303-1313.",
    "lopezdeprado2018": "Lopez de Prado, M. (2018). Advances in Financial Machine Learning. Wiley.",
    "pardo2008": "Pardo, R. (2008). The Evaluation and Optimization of Trading Strategies, 2nd ed. Wiley.",
}

DISCLAIMER = (
    "This report is a statistical analysis of historical data supplied by or selected for the client. It describes how "
    "fragile past results are under standard tests; it says nothing reliable about future results. It is not investment "
    "advice, not a recommendation to buy, sell or hold any security or other instrument, and not an offer of any "
    "service regulated as investment or trading advice. Past performance, simulated or real, does not guarantee future "
    "results. No warranty is given that the data, code or conclusions are free of error. Backtested and simulated results "
    "are hypothetical and have inherent limitations."
)
