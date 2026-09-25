"""Batch 2 specification: the 14 preregistered audits (ten classic rules on the markets their sources used).

Imported by make_prereg.py (to write the sealed preregistration) and by run_batch2.py (to run it),
so the two cannot drift apart.
"""

END = "2026-09-24"
HOLDOUT = "2018-01-02"

RULES = {
    "faber": {
        "name": "Faber 10-month SMA timing",
        "source": "Faber, M. T. (2007). A Quantitative Approach to Tactical Asset Allocation. Journal of Wealth Management 9(4), 69-79 (SSRN 962461).",
        "rule": "At each month end, long the asset if its monthly close is above its 10-month simple moving average of month-end closes; otherwise cash.",
        "published_default": "10 months",
        "markets_used_by_source": "US equities (S&P 500), foreign equities (MSCI EAFE), US 10-year Treasuries (plus REITs and commodities, which are outside our scope or not in this batch)",
    },
    "sma_filter": {
        "name": "200-day moving-average filter",
        "source": "Siegel, J. J. (2002). Stocks for the Long Run, 3rd ed., McGraw-Hill, ch. 17 (the 200-day moving average with a 1% band on the Dow and S&P 500).",
        "rule": "Buy at the close when the index closes at least 1% above its 200-day SMA; sell to cash when it closes at least 1% below; otherwise keep the position.",
        "published_default": "200 days, 1% band",
        "markets_used_by_source": "US large-cap equities (DJIA; S&P 500)",
    },
    "halloween": {
        "name": "Halloween indicator / Sell in May",
        "source": "Bouman, S. & Jacobsen, B. (2002). The Halloween Indicator, 'Sell in May and Go Away': Another Puzzle. American Economic Review 92(5), 1618-1635.",
        "rule": "Invested from the start of November through the end of April; cash from May through October.",
        "published_default": "November-April",
        "markets_used_by_source": "37 national stock markets including the US and the major developed markets",
    },
    "turn_of_month": {
        "name": "Turn-of-the-month effect",
        "source": "Lakonishok, J. & Smidt, S. (1988). Are Seasonal Anomalies Real? Review of Financial Studies 1(4), 403-425; McConnell, J. J. & Xu, W. (2008). Equity Returns at the Turn of the Month. Financial Analysts Journal 64(2), 49-64.",
        "rule": "Invested over the last trading day of each month and the first three trading days of the next; cash otherwise.",
        "published_default": "last 1 + first 3 trading days",
        "markets_used_by_source": "US equities (DJIA / CRSP; McConnell & Xu also 35 other countries)",
    },
    "dual_momentum": {
        "name": "Antonacci dual momentum (Global Equities Momentum)",
        "source": "Antonacci, G. (2014). Dual Momentum Investing. McGraw-Hill; Antonacci, G. (2012). Risk Premia Harvesting Through Dual Momentum (SSRN 2042750).",
        "rule": "At each month end: if US equities' 12-month total return beats the absolute-momentum hurdle, hold whichever of US (SPY) and non-US (EFA) equities had the higher 12-month return; otherwise hold aggregate bonds (AGG).",
        "published_default": "12-month lookback; aggregate bonds as the safe asset",
        "markets_used_by_source": "S&P 500, MSCI ACWI ex-US, Barclays US Aggregate Bond; T-bills for the absolute-momentum hurdle",
    },
    "sector_momentum": {
        "name": "Sector momentum rotation (12-1 month)",
        "source": "Moskowitz, T. J. & Grinblatt, M. (1999). Do Industries Explain Momentum? Journal of Finance 54(4), 1249-1290; Faber, M. T. (2010). Relative Strength Strategies for Investing (SSRN 1585517).",
        "rule": "At each month end rank the nine original sector SPDRs by total return from 12 months ago to 1 month ago, and hold the top three equally weighted until the next month end.",
        "published_default": "12-month lookback skipping the latest month; top 3",
        "markets_used_by_source": "US industries/sectors",
    },
    "vix_stretch": {
        "name": "VIX stretches (Connors & Alvarez)",
        "source": "Connors, L. & Alvarez, C. (2009). Short Term Trading Strategies That Work. TradingMarkets, chapter 'VIX Stretches'.",
        "rule": "Buy SPY at the close when SPY is above its 200-day SMA and the VIX has closed at least 5% above its 10-day SMA for three or more consecutive days; exit at the close when SPY's RSI(2) exceeds 65. The VIX index level is used only as a signal and never traded.",
        "published_default": "5% stretch, 3 days, exit RSI(2) > 65",
        "markets_used_by_source": "S&P 500 (SPY), with the VIX as the signal",
    },
    "golden_cross": {
        "name": "Golden cross (50/200-day)",
        "source": "Traditional trend-following rule; see, e.g., Brock, W., Lakonishok, J. & LeBaron, B. (1992). Simple Technical Trading Rules and the Stochastic Properties of Stock Returns. Journal of Finance 47(5), 1731-1764 (moving-average rules including 50 and 200 days).",
        "rule": "Long while the 50-day SMA is above the 200-day SMA; cash otherwise.",
        "published_default": "50/200 days",
        "markets_used_by_source": "US equity indices (DJIA in Brock et al.); this audit applies it to the Nasdaq-100 (QQQ)",
    },
    "sixty_forty": {
        "name": "60/40 rebalancing bands",
        "source": "Jaconetti, C. M., Kinniry, F. M. & Zilbering, Y. (2010). Best Practices for Portfolio Rebalancing. Vanguard Research.",
        "rule": "Hold 60% US equities (SPY) / 40% Treasuries (IEF), let the weights drift, and rebalance to 60/40 on a month end whenever the equity weight is more than 5 percentage points away from 60%.",
        "published_default": "5 percentage-point band, checked monthly",
        "markets_used_by_source": "US stocks and US bonds",
    },
    "rsi2": {
        "name": "Connors RSI(2) with exit variants",
        "source": "Connors, L. & Alvarez, C. (2009). Short Term Trading Strategies That Work. TradingMarkets, chapter 'The 2-period RSI'.",
        "rule": "Buy at the close when the close is above its 200-day SMA and RSI(2) is below 5; exit at the close when the close is above its 5-day SMA. Exit variants: 10-day SMA, RSI(2) > 70, first up close.",
        "published_default": "entry RSI(2) < 5, exit close > 5-day SMA",
        "markets_used_by_source": "US equity index ETFs (SPY, QQQ and others)",
    },
}

# id: (rule, market label, data symbols, benchmark description, audit start, cost bps per unit traded)
AUDITS = [
    ("faber-spy", "faber", "SPY", ["SPY"], "buy-and-hold SPY", "1994-01-03", 2.0),
    ("faber-efa", "faber", "EFA", ["EFA"], "buy-and-hold EFA", "2002-09-03", 5.0),
    ("faber-ief", "faber", "IEF", ["IEF"], "buy-and-hold IEF", "2003-08-01", 2.0),
    ("sma200-spy", "sma_filter", "SPY", ["SPY"], "buy-and-hold SPY", "1994-02-01", 2.0),
    ("halloween-spy", "halloween", "SPY", ["SPY"], "buy-and-hold SPY", "1994-01-03", 2.0),
    ("halloween-efa", "halloween", "EFA", ["EFA"], "buy-and-hold EFA", "2001-09-04", 5.0),
    ("tom-spy", "turn_of_month", "SPY", ["SPY"], "buy-and-hold SPY", "1994-01-03", 2.0),
    ("dualmom-spy-efa-agg", "dual_momentum", "SPY/EFA/AGG", ["SPY", "EFA", "AGG", "IEF"], "buy-and-hold SPY", "2004-10-01", 2.0),
    ("sectors-12-1", "sector_momentum", "9 sector SPDRs", ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "SPY"],
     "buy-and-hold SPY", "2000-02-01", 5.0),
    ("vix-stretch-spy", "vix_stretch", "SPY (VIX signal)", ["SPY", "^VIX"], "buy-and-hold SPY", "1994-01-03", 2.0),
    ("golden-cross-qqq", "golden_cross", "QQQ", ["QQQ"], "buy-and-hold QQQ", "2000-06-01", 2.0),
    ("sixty-forty-bands", "sixty_forty", "SPY/IEF 60/40", ["SPY", "IEF"], "60/40 SPY/IEF bought at the start and never rebalanced", "2002-08-01", 2.0),
    ("rsi2-qqq", "rsi2", "QQQ", ["QQQ"], "buy-and-hold QQQ", "2000-01-03", 2.0),
    ("rsi2-iwm", "rsi2", "IWM", ["IWM"], "buy-and-hold IWM", "2001-03-15", 5.0),
]
