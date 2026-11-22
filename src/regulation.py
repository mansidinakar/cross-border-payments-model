"""Regulatory inputs used by the model, each with its source.
Verified against public sources on 2026-11-12. Change a value here and
every scenario follows.
"""

REMITTANCE_TAX = {
    "rate": 0.01,                      # 1% of the amount transferred
    "effective_from": "2026-01-01",    # transfers made after 2025-12-31
    "law": "IRC section 4475 (added by Public Law 119-21, 'One Big Beautiful Bill Act')",
    "taxed_funding": "cash, money order, cashier's check or similar physical instrument",
    "exempt_funding": "withdrawal from a US financial-institution account; US-issued debit/credit card",
    "tax_base": "amount transferred to the recipient; provider fees are NOT in the base",
    "paid_by": "sender; provider collects and remits",
    "status_note": "Statute is in force. IRS proposed regulations (Federal Register, 13 Apr 2026) "
                   "clarify the base and instruments; check whether final rules have replaced them.",
    "source": "https://www.law.cornell.edu/uscode/text/26/4475 ; "
              "https://www.federalregister.gov/documents/2026/04/13/2026-07085/excise-tax-on-remittance-transfers",
}

REG_E_REMITTANCE_RULE = {
    "rule": "CFPB Remittance Rule, Regulation E Subpart B (12 CFR 1005.30-1005.36)",
    "pre_payment_disclosure": "sender must be shown fees, exchange rate, taxes and amount received before paying",
    "cancellation_window_minutes": 30,
    "safe_harbor_transfers_per_year": 500,
    "source": "https://www.ecfr.gov/current/title-12/chapter-X/part-1005/subpart-B",
}

TARGETS = {
    "global_avg_cost_pct": 3.0,        # remittances, $200 send, by 2030
    "max_corridor_cost_pct": 5.0,      # no corridor above this, by 2030
    "source": "G20 roadmap / UN SDG 10.c; https://treasurytoday.com/?p=120397",
}