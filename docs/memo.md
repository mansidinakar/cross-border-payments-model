# Cross-border payments cost model: memo

**Author:** Mansi | **Data:** World Bank Remittance Prices Worldwide, Q3 2025

## Bottom line
Sending $200 from the US costs 5.05% on average, which is $10.09, against a G20 / UN SDG 10.c goal of 3%. Of the 37 US-outbound corridors with enough quotes to rank, 17 are above the 5% cap and only one, Nigeria at 2.72%, is under 3%. Even if FX margins were removed entirely, the US average would still be 3.70%, so fees are the larger part of the problem.

## What the data shows
- **Price:** The US average is 5.05% (fees 3.70 pp + FX margin 1.35 pp), from 1,010 quotes. The global average is 6.36%.
- **Corridors:** Mexico is 4.54%, the Philippines 4.52% and India 3.68%. The most expensive ranked corridor is Lebanon at 11.28%.
- **How people pay matters:** Cash-funded transfers average 5.95%, against 4.67% for card and 5.22% for bank account. Digital access averages 4.66% against 6.02% for non-digital.
- **Trend:** US costs have stayed between roughly 5% and 6% since 2016, with a recent dip to 5.05%.

## Why the 2026 remittance tax matters
A 1% US excise tax (IRC section 4475) has applied to cash-funded remittances since 1 January 2026. Modelled as +1 percentage point on cash-funded quotes, which are 18.3% of US quotes, it raises the cash average from 5.95% to 6.95% and the US average from 5.05% to 5.23%. Two more corridors, Haiti and Colombia, cross the 5% cap (17 to 19). Among 117 matched provider and route pairs, switching from cash to a non-cash option saves a median 1.52 pp before the tax and 2.52 pp after it.

## What a product team could test
These are hypotheses to test, not conclusions.
1. Show the all-in cost, including any tax, before the customer commits.
2. Nudge cash customers toward bank-account or card funding where it is cheaper.
3. Make FX margin visible as a separate line, because undisclosed margins hide the true price.

## Method and limits
Total cost = fee % + FX margin %, as a simple average of quotes, which reproduces the World Bank's 6.36% global figure. Quotes are advertised prices, not completed transactions. The data predates the tax, so tax results are modelled, not observed. IRS rules were proposed in April 2026, so check for final rules. Negative-cost quotes are kept and flagged; without them the US average is 5.15%.

## What I built
A Python pipeline (cleaning, analysis, scenarios, 32 tests), an Excel model with a live calculator, and a Tableau Public dashboard. The code was built in assistance with Claude (Anthropic); I ran and checked every step.