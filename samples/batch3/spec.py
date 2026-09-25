"""Batch 3 specification: six audits of the strongest published evidence, each on its source's own objective."""

END = "2026-09-24"
SEEN_PRICES = ["SPY", "QQQ", "IWM", "EFA", "IEF", "AGG", "^VIX", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU",
               "XLV", "XLY", "BTC-USD"]
UNSEEN_PRICES = ["EEM", "TLT", "VNQ", "USMV", "SPLV"]

RULES = {
    "vol_managed": {
        "name": "Volatility-managed equity (Moreira & Muir)",
        "source": "Moreira, A. & Muir, T. (2017). Volatility-Managed Portfolios. Journal of Finance 72(4), 1611-1644.",
        "claim": "Scaling equity exposure by the inverse of last month's realised variance raises the Sharpe ratio (and produces alpha) relative to the unmanaged market.",
        "objective": "improve_sharpe",
        "rule": "At each month end, equity weight = 0.16^2 / (last calendar month's realised variance, annualised), capped at 1.5 (the paper's leverage-constrained version; the constant is fixed ex ante, not fitted); the rest in cash at 0%, or borrowed at 0% above 1.",
    },
    "lowvol_sectors": {
        "name": "Low-volatility sectors (low-volatility anomaly)",
        "source": "Blitz, D. & van Vliet, P. (2007). The Volatility Effect. Journal of Portfolio Management 34(1), 102-113; Baker, M., Bradley, B. & Wurgler, J. (2011). Benchmarks as Limits to Arbitrage. Financial Analysts Journal 67(1), 40-54.",
        "claim": "Low-volatility portfolios earn market-like returns with lower risk: a higher Sharpe ratio than the market.",
        "objective": "improve_sharpe",
        "rule": "At each month end, hold equally the 3 of the 9 original sector SPDRs with the lowest trailing 252-day volatility (a sector-level adaptation of the stock-level anomaly).",
    },
    "lowvol_etf": {
        "name": "Minimum-volatility ETFs (USMV, SPLV)",
        "source": "The low-volatility anomaly as packaged in index products: MSCI USA Minimum Volatility (USMV) and S&P 500 Low Volatility (SPLV); academic basis as for lowvol_sectors.",
        "claim": "A higher Sharpe ratio than the market (SPY).",
        "objective": "improve_sharpe",
        "rule": "Buy and hold USMV (audited variant) or SPLV.",
    },
    "tsmom": {
        "name": "Time-series momentum (Moskowitz, Ooi & Pedersen)",
        "source": "Moskowitz, T. J., Ooi, Y. H. & Pedersen, L. H. (2012). Time Series Momentum. Journal of Financial Economics 104(2), 228-250.",
        "claim": "A diversified time-series momentum portfolio earns a high Sharpe ratio and performs well in extreme markets; here judged on Sharpe improvement over holding the same assets.",
        "objective": "improve_sharpe",
        "rule": "At each month end, long each of SPY, EFA, EEM, IEF, TLT with a positive trailing 12-month return and short each with a negative one; each position sized to 40% ex-ante volatility (EWMA, centre of mass 60 days) and averaged across the five (commodities and currencies from the paper are excluded).",
    },
    "gtaa": {
        "name": "Faber GTAA timing on unseen markets (EEM, VNQ, TLT)",
        "source": "Faber, M. T. (2007). A Quantitative Approach to Tactical Asset Allocation. Journal of Wealth Management 9(4), 69-79.",
        "claim": "Timing each asset class with a 10-month SMA gives equity-like returns with bond-like volatility and much smaller drawdowns than buy-and-hold.",
        "objective": "reduce_drawdown",
        "max_return_shortfall_annual": 0.01,
        "rule": "Equal thirds in EEM, VNQ and TLT; each held only while its month-end close is above its 10-month SMA, cash otherwise.",
    },
    "risk_parity": {
        "name": "Risk parity stocks/bonds (Asness, Frazzini & Pedersen)",
        "source": "Asness, C. S., Frazzini, A. & Pedersen, L. H. (2012). Leverage Aversion and Risk Parity. Financial Analysts Journal 68(1), 47-59.",
        "claim": "Weighting stocks and bonds by inverse volatility gives a higher Sharpe ratio than a 60/40 portfolio.",
        "objective": "improve_sharpe",
        "rule": "At each month end, weight SPY and TLT inversely to their trailing 756-day (3-year) volatility, unlevered; benchmark 60/40 SPY/TLT rebalanced monthly.",
    },
}

# id, rule, market label, symbols, benchmark description, start, holdout, cost bps
AUDITS = [
    ("volman-spy", "vol_managed", "SPY", ["SPY"], "buy-and-hold SPY", "1994-01-03", "2018-01-02", 2.0),
    ("lowvol-sectors", "lowvol_sectors", "9 sector SPDRs", ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "SPY"],
     "buy-and-hold SPY", "2000-01-03", "2018-01-02", 5.0),
    ("lowvol-etf", "lowvol_etf", "USMV / SPLV", ["USMV", "SPLV", "SPY"], "buy-and-hold SPY", "2011-11-01", "2022-01-03", 5.0),
    ("tsmom-5", "tsmom", "SPY, EFA, EEM, IEF, TLT", ["SPY", "EFA", "EEM", "IEF", "TLT"],
     "equal-weight buy-and-hold of the same five ETFs, rebalanced monthly", "2004-05-03", "2018-01-02", 5.0),
    ("gtaa-eem-vnq-tlt", "gtaa", "EEM, VNQ, TLT", ["EEM", "VNQ", "TLT"],
     "equal-weight buy-and-hold of the same three ETFs, rebalanced monthly", "2005-10-03", "2018-01-02", 5.0),
    ("risk-parity-spy-tlt", "risk_parity", "SPY / TLT", ["SPY", "TLT", "IEF"], "60/40 SPY/TLT rebalanced monthly",
     "2005-08-01", "2018-01-02", 2.0),
]
