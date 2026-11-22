"""Build Tableau-ready CSVs from the analysis tables."""
import sys
from pathlib import Path

import pandas as pd

GOAL = 3.0
CAP = 5.0


def main(indir, outdir):
    indir, outdir = Path(indir), Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    corr = pd.read_csv(indir / "analysis_corridors.csv")
    flip = pd.read_csv(indir / "scenario_corridor_tax_flip.csv")
    flip = flip[["destination_code", "cash_share", "after", "increase_pp", "newly_above_cap"]]
    flip = flip.rename(columns={"after": "cost_with_tax_pct"})
    corr = corr.merge(flip, on="destination_code", how="left")
    corr = corr[corr["ranked"]].copy()
    corr["goal_pct"] = GOAL
    corr["cap_pct"] = CAP
    corr["status"] = corr["total_cost_pct"].apply(
        lambda v: "Above 5% cap" if v > CAP else ("Above 3% goal" if v > GOAL else "Meets goal")
    )
    corr.round(4).to_csv(outdir / "tableau_corridors.csv", index=False)

    trend = pd.read_csv(indir / "analysis_trend.csv")
    trend["goal_pct"] = GOAL
    trend.round(4).to_csv(outdir / "tableau_trend.csv", index=False)

    scen = pd.read_csv(indir / "scenario_target_summary.csv")
    scen["goal_pct"] = GOAL
    scen.round(4).to_csv(outdir / "tableau_scenarios.csv", index=False)

    fund = pd.read_csv(indir / "analysis_by_funding.csv")
    fund.round(4).to_csv(outdir / "tableau_funding.csv", index=False)

    print("corridors:", len(corr), "| trend:", len(trend),
          "| scenarios:", len(scen), "| funding:", len(fund))
    print(corr["status"].value_counts().to_string())


if __name__ == "__main__":
    indir = sys.argv[1] if len(sys.argv) > 1 else "data/processed"
    outdir = sys.argv[2] if len(sys.argv) > 2 else "data/tableau"
    main(indir, outdir)