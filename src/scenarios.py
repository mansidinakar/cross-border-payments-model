"""Regulation scenarios on US-outbound costs (World Bank RPW, Q3 2025, $200 send).

IMPORTANT: the RPW data predates the 1% tax. Scenario results are modelled,
not observed. The tax is assumed to be added on top of the provider's price
and paid fully by the sender.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

import analyze
from regulation import REMITTANCE_TAX, TARGETS

TAX_PP = REMITTANCE_TAX["rate"] * 100          # 1% of the amount sent = +1.00 percentage point
CAP = TARGETS["max_corridor_cost_pct"]         # 5.0
GOAL = TARGETS["global_avg_cost_pct"]          # 3.0


def apply_cash_tax(us: pd.DataFrame, tax_pp: float = TAX_PP) -> pd.DataFrame:
    """Add the tax to cash-funded quotes only (cash must be the only instrument)."""
    x = us.copy()
    x["tax_pp"] = (x["funding_group"] == "Cash") * tax_pp
    x["cost_with_tax_pct"] = x["total_cost_pct"] + x["tax_pp"]
    return x


def corridor_flip(us_tax: pd.DataFrame, min_quotes: int = analyze.MIN_QUOTES) -> pd.DataFrame:
    """For each destination: cost before and after the tax, and does it cross the 5% cap?"""
    g = us_tax.groupby(["destination_code", "destination_name"]).agg(
        quotes=("id", "size"),
        cash_share=("tax_pp", lambda s: (s > 0).mean()),
        before=("total_cost_pct", "mean"),
        after=("cost_with_tax_pct", "mean"),
    ).reset_index()
    g = g[g.quotes >= min_quotes].copy()
    g["increase_pp"] = g["after"] - g["before"]
    g["above_cap_before"] = g["before"] > CAP
    g["above_cap_after"] = g["after"] > CAP
    g["newly_above_cap"] = g["above_cap_after"] & ~g["above_cap_before"]
    return g.sort_values("increase_pp", ascending=False).reset_index(drop=True)


def switch_pairs(us_tax: pd.DataFrame) -> pd.DataFrame:
    """Same provider, same destination, same payout: cash-funded vs non-cash-funded."""
    k = ["firm", "destination_code", "payout_group"]
    cash = (us_tax[us_tax.funding_group == "Cash"].groupby(k)
            .agg(cash_before=("total_cost_pct", "mean"), cash_after=("cost_with_tax_pct", "mean")))
    non = (us_tax[us_tax.funding_group.isin(["Card", "Bank account"])].groupby(k)
           .agg(non_cash=("total_cost_pct", "mean")))
    p = cash.join(non, how="inner").reset_index()          # keep only matched pairs
    p["saving_before_tax_pp"] = p["cash_before"] - p["non_cash"]
    p["saving_after_tax_pp"] = p["cash_after"] - p["non_cash"]
    return p 



def converge_to_median(us: pd.DataFrame) -> pd.Series:
    """Illustrative: every quote above its corridor median is repriced to that median."""
    med = us.groupby("destination_code")["total_cost_pct"].transform("median")
    return us["total_cost_pct"].clip(upper=med)


def target_summary(us_tax: pd.DataFrame) -> pd.DataFrame:
    """Average cost and distance from the 3% goal under each scenario."""
    base = us_tax["total_cost_pct"]
    rows = {
        "Baseline (Q3 2025 data)": base,
        "With 1% cash tax": us_tax["cost_with_tax_pct"],
        "No FX margin (fee only)": us_tax["fee_pct"],
        "Every quote capped at 5%": base.clip(upper=CAP),
        "Quotes above corridor median repriced to median": converge_to_median(us_tax),
    }
    out = pd.DataFrame({
        "scenario": list(rows),
        "avg_cost_pct": [s.mean() for s in rows.values()],
        "share_quotes_above_5pct": [(s > CAP).mean() for s in rows.values()],
        "share_quotes_above_3pct": [(s > GOAL).mean() for s in rows.values()],
    })
    out["cost_per_200_usd"] = out["avg_cost_pct"] * 2
    out["gap_to_3pct_goal_pp"] = out["avg_cost_pct"] - GOAL
    return out


# ---------- run it from the command line ----------

def main(outdir: str) -> None:
    out = Path(outdir)
    d = pd.read_csv(out / "rpw_clean.csv.gz", parse_dates=["period_start"])
    us = apply_cash_tax(analyze.us_slice(d))

    flip = corridor_flip(us)
    pairs = switch_pairs(us)
    summary = target_summary(us)
    flip.round(4).to_csv(out / "scenario_corridor_tax_flip.csv", index=False)
    pairs.round(4).to_csv(out / "scenario_switch_pairs.csv", index=False)
    summary.round(4).to_csv(out / "scenario_target_summary.csv", index=False)

    cash = us[us.funding_group == "Cash"]
    print(f"Cash is {len(cash) / len(us):.1%} of US quotes; cash average {cash.total_cost_pct.mean():.2f}% -> {cash.cost_with_tax_pct.mean():.2f}% with tax")
    print(f"US average {us.total_cost_pct.mean():.2f}% -> {us.cost_with_tax_pct.mean():.2f}%")
    print(f"Corridors above 5% cap: {int(flip.above_cap_before.sum())} -> {int(flip.above_cap_after.sum())} (of {len(flip)})")
    print(f"Matched cash vs non-cash pairs: {len(pairs)} | median saving from switching {pairs.saving_before_tax_pp.median():.2f} pp before tax, {pairs.saving_after_tax_pp.median():.2f} pp after")
    print()
    print(summary.round(2).to_string(index=False))
    print("\nSaved 3 scenario tables to", out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python src/scenarios.py <processed dir>")
    main(sys.argv[1])
    