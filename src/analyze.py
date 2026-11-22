"""Analyse US-outbound remittance costs (World Bank RPW, $200 send).

Method (same as the World Bank's, so numbers can be compared with its report):
  * a "corridor average" is the simple average of all provider quotes in that corridor
  * negative-cost quotes are KEPT by default (the World Bank keeps them)
  * RPW has no volume data, so nothing here is volume-weighted

Benchmarks (UN SDG 10.c / G20 roadmap): global average <= 3% and
no corridor above 5% by 2030.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

LATEST = "2025_3Q"        # newest period in the data
SDG_AVG_TARGET = 3.0      # percent
CORRIDOR_CAP = 5.0        # percent
MIN_QUOTES = 10           # corridors with fewer quotes are not ranked


def summarise(g: pd.DataFrame) -> pd.Series:
    """Turn a group of quotes into one row of statistics."""
    t = g["total_cost_pct"]
    return pd.Series({
        "quotes": len(g),
        "providers": g["firm"].nunique(),
        "fee_pct": g["fee_pct"].mean(),
        "fx_margin_pct": g["fx_margin_pct"].mean(),
        "total_cost_pct": t.mean(),
        "median_cost_pct": t.median(),
        "cheapest_quote_pct": t.min(),
        "p90_cost_pct": t.quantile(0.9),
        "most_expensive_pct": t.max(),
        "fee_share_of_cost": g["fee_pct"].mean() / t.mean() if t.mean() else float("nan"),
    })


def us_slice(d: pd.DataFrame, period: str = LATEST, amount: int = 200) -> pd.DataFrame:
    """Only quotes sent FROM the US, in one period, for one send amount."""
    return d[(d.source_code == "USA") & (d.period == period) & (d.amount_usd == amount)]


def corridor_table(us: pd.DataFrame) -> pd.DataFrame:
    """One row per destination country, flagged against the targets."""
    t = (us.groupby(["destination_code", "destination_name", "destination_region"])
           .apply(summarise, include_groups=False).reset_index())
    t["spread_median_vs_cheapest_pp"] = t["median_cost_pct"] - t["cheapest_quote_pct"]
    t["above_5pct_cap"] = t["total_cost_pct"] > CORRIDOR_CAP
    t["above_3pct_sdg"] = t["total_cost_pct"] > SDG_AVG_TARGET
    t["ranked"] = t["quotes"] >= MIN_QUOTES
    return t.sort_values("total_cost_pct", ascending=False).reset_index(drop=True)


def by_dimension(us: pd.DataFrame, col: str) -> pd.DataFrame:
    """The same summary, split by any column (funding_group, provider_type, ...)."""
    return (us.groupby(col).apply(summarise, include_groups=False)
              .reset_index().sort_values("total_cost_pct"))


def sensitivity(us: pd.DataFrame) -> pd.DataFrame:
    """Does the headline change if we make a different data choice?"""
    rows = []
    for label, x in [("All quotes (default)", us),
                     ("Excluding negative-cost quotes", us[~us.negative_cost_flag]),
                     ("Only quotes with disclosed FX rate", us[us.fx_known])]:
        rows.append({"version": label, "quotes": len(x), "total_cost_pct": x.total_cost_pct.mean(),
                     "fee_pct": x.fee_pct.mean(), "fx_margin_pct": x.fx_margin_pct.mean()})
    return pd.DataFrame(rows)


def trend(d: pd.DataFrame, source: str | None = "USA", amount: int = 200) -> pd.DataFrame:
    """Average cost per period. source=None means all sending countries (global)."""
    x = d[d.amount_usd == amount]
    if source:
        x = x[x.source_code == source]
    out = x.groupby("period_start").apply(summarise, include_groups=False).reset_index()
    out["scope"] = source or "Global"
    return out


def sender_league(d: pd.DataFrame, period: str = LATEST) -> pd.DataFrame:
    """Where each sending country sits (countries with >= 20 quotes), cheapest first."""
    x = d[(d.period == period) & (d.amount_usd == 200)]
    t = x.groupby(["source_code", "source_name"]).apply(summarise, include_groups=False).reset_index()
    t = t[t.quotes >= 20].sort_values("total_cost_pct").reset_index(drop=True)
    t["rank_cheapest_first"] = t.index + 1
    return t


# ---------- run it from the command line ----------

def main(outdir: str) -> None:
    out = Path(outdir)
    d = pd.read_csv(out / "rpw_clean.csv.gz", parse_dates=["period_start"])
    us = us_slice(d)
    glob = d[(d.period == LATEST) & (d.amount_usd == 200)]

    tables = {
        "analysis_corridors.csv": corridor_table(us),
        "analysis_by_funding.csv": by_dimension(us, "funding_group"),
        "analysis_by_provider_type.csv": by_dimension(us, "provider_type"),
        "analysis_by_payout.csv": by_dimension(us, "payout_group"),
        "analysis_by_digital.csv": by_dimension(us, "digital_access"),
        "analysis_trend.csv": pd.concat([trend(d, "USA"), trend(d, None)]),
        "analysis_sensitivity.csv": sensitivity(us),
        "analysis_sender_league.csv": sender_league(d),
    }
    for name, t in tables.items():
        t.round(4).to_csv(out / name, index=False)

    c = tables["analysis_corridors.csv"]
    ranked = c[c.ranked]
    lg = tables["analysis_sender_league.csv"]
    us_rank = int(lg[lg.source_code == "USA"].rank_cheapest_first.iloc[0])
    print(f"Global avg {glob.total_cost_pct.mean():.2f}% | US avg {us.total_cost_pct.mean():.2f}% | US quotes {len(us)}")
    print(f"Ranked US corridors: {len(ranked)} | above 5% cap: {int(ranked.above_5pct_cap.sum())} | above 3%: {int(ranked.above_3pct_sdg.sum())}")
    print(f"US rank among {len(lg)} sending countries (1 = cheapest): {us_rank}")
    print("\nUS vs global average cost over time:")
    print(tables["analysis_trend.csv"].pivot(index="period_start", columns="scope", values="total_cost_pct").round(2).tail(4))
    print(f"\nSaved {len(tables)} tables to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python src/analyze.py <processed dir>")
    main(sys.argv[1])