"""Clean World Bank Remittance Prices Worldwide (RPW) quotes.

Data: The World Bank, Remittance Prices Worldwide,
      available at http://remittanceprices.worldbank.org
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


# ---------- label standardisation (small functions, easy to test) ----------

def _tokens(value) -> set[str]:
    """'Bank branch,Internet' -> {'bank branch', 'internet'}"""
    if pd.isna(value):
        return set()
    return {t.strip().lower() for t in str(value).split(",") if t.strip()}


def provider_type(raw) -> str:
    """Bank / Money Transfer Operator / Other.
    Mixed labels go to 'Other' so a provider is never counted as something it is not."""
    s = "" if pd.isna(raw) else str(raw).strip().lower()
    if s == "bank":
        return "Bank"
    if s == "money transfer operator":
        return "Money Transfer Operator"
    return "Other"


def funding_group(raw) -> str:
    """How the sender pays. 'Cash' only when cash is the ONLY instrument:
    a quote that also allows a card cannot be called cash-funded."""
    t = _tokens(raw)
    if not t:
        return "Unknown"
    if t == {"cash"}:
        return "Cash"
    if t <= {"debit card", "credit card", "debit/credit card"}:
        return "Card"
    if t == {"bank account transfer"}:
        return "Bank account"
    if t == {"mobile money"}:
        return "Mobile money"
    return "Mixed/other"


def payout_group(raw) -> str:
    """How the recipient gets the money."""
    t = _tokens(raw)
    if t == {"cash"}:
        return "Cash"
    if t == {"mobile wallet"}:
        return "Mobile wallet"
    if t and all("bank account" in x for x in t):
        return "Bank account"
    return "Other"


def is_digital_access(raw) -> bool:
    """RPW counts a service as digital when it is reached online or by phone app."""
    return bool(_tokens(raw) & {"internet", "mobile phone"})


# ---------- loading and reshaping ----------

SHEET = "Dataset (from Q2 2016)"
# The older sheet (to Q1 2016) has a different layout and no funding-method
# column, so it is deliberately left out.

# Column names for the $200 (cc1) and $500 (cc2) price surveys
AMOUNTS = {
    200: dict(amt="cc1 lcu amount", fee="cc1 lcu fee", fx="cc1 fx margin", total="cc1 total cost %"),
    500: dict(amt="cc2 lcu amount", fee="cc2 lcu fee", fx="cc2 fx margin", total="cc2 total cost %"),
}

# Raw column name -> the tidy name we use from now on
ID_COLS = {
    "id": "id", "period": "period",
    "source_code": "source_code", "source_name": "source_name",
    "source_region": "source_region", "source_income": "source_income",
    "destination_code": "destination_code", "destination_name": "destination_name",
    "destination_region": "destination_region", "destination_income": "destination_income",
    "firm": "firm", "firm_type": "firm_type_raw",
    "payment instrument": "instrument_raw", "access point": "access_point_raw",
    "pickup method": "payout_raw", "speed actual": "speed", "transparent": "transparent",
}


def load_raw(path) -> pd.DataFrame:
    """Read the main data sheet (first 41 columns; the rest are empty)."""
    return pd.read_excel(path, sheet_name=SHEET, usecols=range(41))


def to_long(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (quote, surveyed amount): the $200 rows and the $500 rows stacked."""
    frames = []
    for usd, c in AMOUNTS.items():
        part = df[list(ID_COLS)].rename(columns=ID_COLS).copy()
        part["amount_usd"] = usd
        part["amount_local"] = pd.to_numeric(df[c["amt"]], errors="coerce")
        part["fee_local"] = pd.to_numeric(df[c["fee"]], errors="coerce")
        part["fx_margin_pct"] = pd.to_numeric(df[c["fx"]], errors="coerce")
        part["total_cost_pct"] = pd.to_numeric(df[c["total"]], errors="coerce")
        frames.append(part)
    return pd.concat(frames, ignore_index=True)


# ---------- core cleaning ----------

# RPW rounds to 2 decimals, so 0.05 percentage points absorbs rounding and nothing more.
IDENTITY_TOLERANCE_PP = 0.05
EXTREME_COST_PCT = 50.0  # flagged, never removed


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return the clean table and a quality report (counts of everything we found)."""
    report: dict = {"raw_quotes": int(len(raw))}
    report["duplicate_ids_dropped"] = int(raw["id"].duplicated().sum())
    raw = raw.drop_duplicates("id")

    d = to_long(raw)
    report["rows_before_null_drop"] = int(len(d))
    d = d.dropna(subset=["total_cost_pct", "fee_local", "amount_local"])
    d = d[d["amount_local"] > 0].copy()
    report["rows_after_null_drop"] = int(len(d))

    # Cost decomposition: fee as % of the amount sent, plus FX margin, equals total
    d["fee_pct"] = d["fee_local"] / d["amount_local"] * 100
    d["rebuilt_total_pct"] = d["fee_pct"] + d["fx_margin_pct"]
    d["cost_identity_ok"] = (d["rebuilt_total_pct"] - d["total_cost_pct"]).abs() <= IDENTITY_TOLERANCE_PP
    report["identity_pass_rate"] = round(float(d["cost_identity_ok"].mean()), 5)

    # If the provider did not disclose its exchange rate, RPW stores a 0 margin.
    # That 0 means "unknown", not "free", so we keep a flag.
    d["fx_known"] = d["transparent"].astype(str).str.strip().str.lower().eq("yes")

    # Standardised labels (the rules from part 2a)
    d["provider_type"] = d["firm_type_raw"].map(provider_type)
    d["funding_group"] = d["instrument_raw"].map(funding_group)
    d["payout_group"] = d["payout_raw"].map(payout_group)
    d["digital_access"] = d["access_point_raw"].map(is_digital_access)

    # Odd rows are FLAGGED, not deleted
    d["negative_cost_flag"] = d["total_cost_pct"] < 0
    d["extreme_cost_flag"] = d["total_cost_pct"] > EXTREME_COST_PCT

    # Dates and corridor name
    d["year"] = d["period"].str[:4].astype(int)
    d["quarter"] = d["period"].str[-2].astype(int)
    d["period_start"] = pd.to_datetime(
        d["year"].astype(str) + "-" + ((d["quarter"] - 1) * 3 + 1).astype(str) + "-01"
    )
    d["corridor"] = d["source_code"] + "-" + d["destination_code"]

    report.update(
        negative_cost_rows=int(d["negative_cost_flag"].sum()),
        extreme_cost_rows=int(d["extreme_cost_flag"].sum()),
        fx_not_disclosed_rows=int((~d["fx_known"]).sum()),
        periods=sorted(d["period"].unique().tolist()),
        funding_group_counts=d["funding_group"].value_counts().to_dict(),
        provider_type_counts=d["provider_type"].value_counts().to_dict(),
    )
    cols = [
        "id", "period", "period_start", "year", "quarter",
        "source_code", "source_name", "source_region", "source_income",
        "destination_code", "destination_name", "destination_region", "destination_income",
        "corridor", "firm", "provider_type", "funding_group", "payout_group",
        "digital_access", "speed", "amount_usd",
        "fee_pct", "fx_margin_pct", "total_cost_pct", "rebuilt_total_pct",
        "fx_known", "cost_identity_ok", "negative_cost_flag", "extreme_cost_flag",
        "instrument_raw", "access_point_raw", "payout_raw", "firm_type_raw",
    ]
    return d[cols].reset_index(drop=True), report


# ---------- run it from the command line ----------

def main(xlsx: str, outdir: str) -> None:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    cleaned, report = clean(load_raw(xlsx))
    cleaned.to_csv(out / "rpw_clean.csv.gz", index=False)
    (out / "quality_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({k: v for k, v in report.items() if k != "periods"}, indent=2, default=str))
    print("periods:", report["periods"][0], "to", report["periods"][-1], f"({len(report['periods'])} periods)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python src/clean.py <rpw.xlsx> <output dir>")
    main(sys.argv[1], sys.argv[2])
