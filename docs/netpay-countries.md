# Adding a country to the net-pay estimates

Net pay turns a gross offer into an estimated monthly take-home for each kind of contract, so local payroll, a local company contract and a foreign contract can be compared. Two levels:

## 1. No code: flat rates (any country, today)
In the workspace's `search/filters.md` → `person`:
```json
"netRates": {"employee": 0.72, "contractor": 0.80},
"contractorBillableMonths": 11
```
`employee` is the share of gross you keep on local payroll; `contractor` is the share kept invoicing as a contractor or through your own company. Ask a local accountant or use a trusted salary calculator once, then reuse the rates. Results are labelled as flat-rate estimates.

## 2. A country module (rules + sources)
1. **Data:** `skill/job-hunt/scripts/netpay/<CC>.json` (ISO country code), with at least:
   ```json
   {"country": "PT", "currency": "EUR", "validFrom": "2026-01-01", "validUntil": "2026-12-31",
    "note": "Estimates for comparing offers, not tax advice.", "sources": {"income_tax": "https://…official…"}}
   ```
   plus the tables your rules need (brackets, social security rates and ceilings, extra salaries…). Use **official sources** (tax authority, social security, the law) and cite each one in `sources`.
2. **Rules:** in `netpay.py`, write `xx_employee(m, gross)` and/or `xx_company(m, gross, export, person)`. Each returns `{"net": int, "basis": contract, "detail": {...}, "assumptions": [...]}`. Register them in `COUNTRIES`:
   ```python
   "PT": {"employee": pt_employee, "company": pt_company, "salaries_per_year": lambda m: 14},
   ```
   `salaries_per_year` turns an annual amount into a monthly salary (e.g. 14 in Portugal, 13.33 in Brazil).
3. **Tests:** add hand-computed cases from the official tables to `tests/test_netpay_eligibility.py`: at least three salary levels per contract type, one near each threshold. `tests/test_examples.py` already checks that every module has the required keys and a registered function.
4. **Every January:** update the tables and `validUntil`. An expired module still works, but the skill tells the user the tables need updating.

Keep the assumptions honest and visible (13th salary, vacation bonus, deferred funds, what's excluded). The goal is a fair comparison between offers, not a payslip.
