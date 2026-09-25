import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def rng():
    return np.random.default_rng(12345)


def make_returns(n=2520, mu=0.0004, sd=0.01, seed=1, start="2010-01-01"):
    r = np.random.default_rng(seed).normal(mu, sd, n)
    idx = pd.bdate_range(start, periods=n)
    return pd.Series(r, index=idx)


@pytest.fixture
def returns_df():
    s = make_returns()
    m = make_returns(mu=0.0003, seed=2)
    to = pd.Series(np.where(np.arange(len(s)) % 20 == 0, 1.0, 0.0), index=s.index)
    return pd.DataFrame({"return": s, "turnover": to, "market": m})
