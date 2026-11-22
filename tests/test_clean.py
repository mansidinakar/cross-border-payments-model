"""Tests for src/clean.py.

Unit tests use tiny hand-built rows (test fixtures only; never used in any
result). Real-data tests run on the World Bank file and are skipped if it
is not present.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import clean  # noqa: E402

RAW = next((ROOT / "data" / "raw").glob("*.xlsx"), None)


# ---------- label rules ----------
@pytest.mark.parametrize("raw,expected", [
    ("Cash", "Cash"),
    ("cash", "Cash"),
    ("Credit Card", "Card"),
    ("Debit card", "Card"),
    ("Debit/credit card", "Card"),
    ("Credit Card,Debit card", "Card"),
    ("Bank account transfer", "Bank account"),
    ("Bank account transfer,Cash", "Mixed/other"),   # cannot call it cash-funded
    ("Cash,Debit/credit card", "Mixed/other"),
    ("Mobile money", "Mobile money"),
    (None, "Unknown"),
])
def test_funding_group(raw, expected):
    assert clean.funding_group(raw) == expected


def test_provider_type_mixed_goes_to_other():
    assert clean.provider_type("Bank") == "Bank"
    assert clean.provider_type("Money Transfer Operator") == "Money Transfer Operator"
    assert clean.provider_type("Bank / Money Transfer Operator") == "Other"
    assert clean.provider_type(None) == "Other"


def test_payout_and_digital():
    assert clean.payout_group("Bank account (same/partner bank)") == "Bank account"
    assert clean.payout_group("Mobile wallet") == "Mobile wallet"
    assert clean.is_digital_access("Agent,Internet")
    assert not clean.is_digital_access("Agent")
    assert not clean.is_digital_access(None)


# ---------- cost decomposition on hand-built rows ----------
def _row(**kw):
    base = {
        "id": 1, "period": "2025_3Q",
        "source_code": "USA", "source_name": "United States", "source_region": "North America",
        "source_income": "High income", "destination_code": "MEX", "destination_name": "Mexico",
        "destination_region": "LAC", "destination_income": "Upper middle income",
        "firm": "TestCo", "firm_type": "Money Transfer Operator",
        "payment instrument": "Debit card", "access point": "Internet",
        "pickup method": "Bank account", "speed actual": "Same day", "transparent": "Yes",
        "cc1 lcu amount": 200, "cc1 lcu fee": 2.0, "cc1 fx margin": 1.0, "cc1 total cost %": 2.0,
        "cc2 lcu amount": 500, "cc2 lcu fee": 5.0, "cc2 fx margin": 1.0, "cc2 total cost %": 2.0,
    }
    base.update(kw)
    return base


def test_fee_plus_margin_equals_total():
    out, rep = clean.clean(pd.DataFrame([_row()]))
    r200 = out[out.amount_usd == 200].iloc[0]
    assert r200.fee_pct == pytest.approx(1.0)        # $2 on $200
    assert r200.fx_margin_pct == pytest.approx(1.0)
    assert r200.cost_identity_ok
    assert rep["identity_pass_rate"] == 1.0


def test_identity_failure_is_flagged_not_dropped():
    out, _ = clean.clean(pd.DataFrame([_row(**{"cc1 total cost %": 9.0})]))
    r200 = out[out.amount_usd == 200].iloc[0]
    assert not r200.cost_identity_ok      # kept, but marked
    assert len(out) == 2


def test_negative_and_extreme_flags():
    rows = [_row(id=1, **{"cc1 fx margin": -3.0, "cc1 total cost %": -2.0}),
            _row(id=2, **{"cc1 fx margin": 60.0, "cc1 total cost %": 61.0})]
    out, _ = clean.clean(pd.DataFrame(rows))
    a = out[(out.id == 1) & (out.amount_usd == 200)].iloc[0]
    b = out[(out.id == 2) & (out.amount_usd == 200)].iloc[0]
    assert a.negative_cost_flag and not a.extreme_cost_flag
    assert b.extreme_cost_flag and not b.negative_cost_flag


def test_undisclosed_rate_is_not_treated_as_free():
    out, _ = clean.clean(pd.DataFrame([_row(transparent="no", **{"cc1 fx margin": 0.0})]))
    assert not out[out.amount_usd == 200].iloc[0].fx_known


def test_missing_total_rows_dropped_and_counted():
    out, rep = clean.clean(pd.DataFrame([_row(**{"cc2 total cost %": None})]))
    assert set(out.amount_usd) == {200}
    assert rep["rows_before_null_drop"] - rep["rows_after_null_drop"] == 1


def test_duplicate_ids_dropped():
    out, rep = clean.clean(pd.DataFrame([_row(), _row()]))
    assert rep["duplicate_ids_dropped"] == 1 and len(out) == 2


def test_non_usd_source_fee_is_relative_to_local_amount():
    # 2,900 AOA fee on 33,000 AOA sent = 8.79%
    row = _row(**{"cc1 lcu amount": 33000, "cc1 lcu fee": 2900, "cc1 fx margin": 7.49, "cc1 total cost %": 16.28})
    out, _ = clean.clean(pd.DataFrame([row]))
    r = out[out.amount_usd == 200].iloc[0]
    assert r.fee_pct == pytest.approx(8.79, abs=0.01) and r.cost_identity_ok


# ---------- real data (skipped without the World Bank file) ----------
@pytest.fixture(scope="session")
def real():
    if RAW is None:
        pytest.skip("World Bank RPW file not in data/raw")
    return clean.clean(clean.load_raw(RAW))


def test_real_headline_matches_world_bank_report(real):
    out, _ = real
    q = out[(out.period == "2025_3Q") & (out.amount_usd == 200)]
    assert round(q.total_cost_pct.mean(), 2) == 6.36      # World Bank RPW Issue 54


def test_real_identity_rate_and_unique_ids(real):
    out, rep = real
    assert rep["identity_pass_rate"] > 0.999
    assert not out.duplicated(["id", "amount_usd"]).any()


def test_real_us_q3_2025_shape(real):
    out, _ = real
    us = out[(out.source_code == "USA") & (out.period == "2025_3Q") & (out.amount_usd == 200)]
    assert len(us) == 1010
    assert set(us.funding_group) == {"Cash", "Card", "Bank account"}