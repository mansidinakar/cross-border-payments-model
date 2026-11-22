import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import analyze  # noqa: E402

PROCESSED = ROOT / "data" / "processed" / "rpw_clean.csv.gz"


def _quotes(costs, dest="MEX"):
    """Hand-built US quotes for testing only. Fee is 75% of cost, FX margin 25%."""
    return pd.DataFrame({
        "source_code": "USA", "period": "2025_3Q", "amount_usd": 200,
        "destination_code": dest, "destination_name": dest, "destination_region": "X",
        "firm": [f"p{i}" for i in range(len(costs))],
        "fee_pct": [c * 0.75 for c in costs], "fx_margin_pct": [c * 0.25 for c in costs],
        "total_cost_pct": costs, "negative_cost_flag": [c < 0 for c in costs],
        "fx_known": True,
    })


def test_summarise_basic():
    s = analyze.summarise(_quotes([2.0, 4.0, 6.0]))
    assert s.total_cost_pct == pytest.approx(4.0)
    assert s.median_cost_pct == 4.0 and s.cheapest_quote_pct == 2.0
    assert s.fee_share_of_cost == pytest.approx(0.75)


def test_corridor_flags_and_min_quotes():
    big = _quotes([6.0] * 12, "AAA")          # above 5% cap, enough quotes
    small = _quotes([2.0] * 3, "BBB")         # under 3%, too few quotes to rank
    t = analyze.corridor_table(pd.concat([big, small]))
    a = t[t.destination_code == "AAA"].iloc[0]
    b = t[t.destination_code == "BBB"].iloc[0]
    assert a.above_5pct_cap and a.above_3pct_sdg and a.ranked
    assert not b.above_3pct_sdg and not b.ranked


def test_sensitivity_excludes_negatives():
    s = analyze.sensitivity(_quotes([-2.0, 4.0, 6.0])).set_index("version")
    assert s.loc["All quotes (default)", "total_cost_pct"] == pytest.approx(8 / 3)
    assert s.loc["Excluding negative-cost quotes", "total_cost_pct"] == pytest.approx(5.0)


@pytest.mark.skipif(not PROCESSED.exists(), reason="run clean.py first")
def test_real_global_and_us_headlines():
    d = pd.read_csv(PROCESSED, parse_dates=["period_start"])
    g = d[(d.period == "2025_3Q") & (d.amount_usd == 200)]
    assert round(g.total_cost_pct.mean(), 2) == 6.36
    assert len(analyze.us_slice(d)) == 1010