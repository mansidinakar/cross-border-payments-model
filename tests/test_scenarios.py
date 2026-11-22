import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import scenarios  # noqa: E402


def _us(rows):
    """Hand-built US quotes for testing only."""
    df = pd.DataFrame(rows, columns=["id", "firm", "destination_code", "destination_name",
                                     "payout_group", "funding_group", "fee_pct", "total_cost_pct"])
    df["fx_margin_pct"] = df.total_cost_pct - df.fee_pct
    return df


def test_tax_applies_to_cash_only():
    x = scenarios.apply_cash_tax(_us([
        (1, "A", "MEX", "Mexico", "Cash", "Cash", 3, 4),
        (2, "A", "MEX", "Mexico", "Cash", "Card", 3, 4),
    ]))
    assert x.loc[x.id == 1, "cost_with_tax_pct"].iloc[0] == pytest.approx(5.0)   # +1.00 pp
    assert x.loc[x.id == 2, "cost_with_tax_pct"].iloc[0] == pytest.approx(4.0)   # exempt


def test_mixed_funding_is_not_taxed():
    x = scenarios.apply_cash_tax(_us([(1, "A", "MEX", "Mexico", "Cash", "Mixed/other", 3, 4)]))
    assert x.cost_with_tax_pct.iloc[0] == pytest.approx(4.0)


def test_corridor_flip_detects_newly_above_cap():
    rows = [(i, f"p{i}", "AAA", "A", "Cash", "Cash", 3, 4.5) for i in range(10)]   # 4.5 -> 5.5 with tax
    flip = scenarios.corridor_flip(scenarios.apply_cash_tax(_us(rows)))
    assert bool(flip.newly_above_cap.iloc[0]) and flip.increase_pp.iloc[0] == pytest.approx(1.0)


def test_switch_pairs_savings():
    rows = [
        (1, "A", "MEX", "Mexico", "Bank account", "Cash", 4, 6),
        (2, "A", "MEX", "Mexico", "Bank account", "Card", 3, 4),
    ]
    p = scenarios.switch_pairs(scenarios.apply_cash_tax(_us(rows)))
    assert p.saving_before_tax_pp.iloc[0] == pytest.approx(2.0)
    assert p.saving_after_tax_pp.iloc[0] == pytest.approx(3.0)


def test_converge_to_median_never_raises_cost():
    us = _us([(i, f"p{i}", "AAA", "A", "Cash", "Card", 1, c) for i, c in enumerate([2, 3, 10])])
    new = scenarios.converge_to_median(us)
    assert (new <= us.total_cost_pct).all() and new.max() == 3