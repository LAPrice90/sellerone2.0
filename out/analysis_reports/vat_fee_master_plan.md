# VAT & Fee Integration Plan (SP-API)

Goal: Reliable VAT + fee tracking (monthly VAT accuracy + daily cash/fee reality).
Constraint: **Pull raw data with correct endpoints/options before writing to DB**.

---

## Phase 0 — Preconditions (Access & Auth)
**Objective:** Ensure permissions and auth won’t block reports/finances calls.

Checklist:
- [ ] Seller Central app roles include **Finance** and **Tax** (if applicable).
- [ ] Refresh token re‑authorized **after** role change (24h propagation may apply).
- [ ] SP‑API host/region confirmed for UK/EU (sellingpartnerapi-eu.amazon.com).
- [ ] SigV4 signing validated for Reports + Finances endpoints.
- [ ] Marketplace ID verified for UK: **A1F83G8C2ARO7P**.

Evidence to move on:
- Successful `GET /finances/v0/financialEvents` call returns non‑empty payload.
- Successful `POST /reports/2021-06-30/reports` returns a reportId.

[ ] Ready to move on (requires evidence)

Evidence (current):
- Finance API working: `out/financial_transactions_v2024_breakdowns.csv` exists (non‑empty).
- Reports API working (create): `out/report_create_latest.csv` shows `GET_MERCHANT_LISTINGS_ALL_DATA` for UK marketplace.
- VAT report create attempt (2025‑12): **403 Unauthorized** (missing VAT/Tax permission or token scope).

---

## Phase 1 — Reports API: VAT Transaction Report (Monthly VAT truth)
**Objective:** Pull `GET_VAT_TRANSACTION_DATA` with required reportOptions.

Calls:
1) Request report:
   - POST `/reports/2021-06-30/reports`
   - reportType: `GET_VAT_TRANSACTION_DATA`
   - marketplaceIds: `[A1F83G8C2ARO7P]`
   - reportOptions: `{ "reportPeriod": "MONTH" }`
   - dataStartTime / dataEndTime (monthly window)
2) Poll status:
   - GET `/reports/2021-06-30/reports/{reportId}`
3) Download:
   - GET `/reports/2021-06-30/documents/{reportDocumentId}`
   - **RDT required** for download (PII present in VAT report)
     - Call `createRestrictedDataToken` with the reportDocumentId in restrictedResources
     - Use RDT for the document download call
   - Decrypt if needed (compression/encryption handled)

Raw outputs to store (no transforms):
- `out/reports/vat_transaction/{yyyy-mm}.csv` (raw)

Validation:
- [ ] VAT report contains expected columns (VAT amounts on sales, promos, shipping, etc.).
- [ ] Non‑empty rows for period.

[ ] Ready to move on (requires evidence)

---

## Phase 2 — Finances API: Real‑time Fees + Tax per order
**Objective:** Pull financialEvents and map fees/tax at order level.

Calls:
- GET `/finances/v0/financialEvents?PostedAfter=...&PostedBefore=...`

Raw outputs to store:
- `out/financial_events/raw/{date_range}.json`
- `out/financial_events/normalized/{date_range}.csv`

Mapping targets (must retain TaxAmount per Fee):
- `ShipmentEventList → ItemFeeList → FeeAmount + TaxAmount`
- `ShipmentEventList → ItemPrice → Principal/Tax`
- `ServiceFeeEventList` (subscription fee)

Validation:
- [ ] Fee component rows have TaxAmount when provided by Amazon.
- [ ] Subscription fee appears in ServiceFeeEventList.

[ ] Ready to move on (requires evidence)

---

## Phase 3 — Normalize + Category Ledger (Canonical fee lines)
**Objective:** Convert finance events into a canonical ledger with categories.

Outputs:
- `out/transaction_category_ledger.csv`
- `out/transaction_category_summary.csv`
- `out/transaction_category_unmapped.csv`

Rules:
- No writes into P&L until ledger is built.
- Any new/unknown category must land in `unmapped` and be reviewed.
- **Source priority:** VAT Report is source‑of‑truth for tax amounts, Finances API is source‑of‑truth for cash date.

Validation:
- [ ] `unmapped` is empty (or explicitly accepted).
- [ ] Totals for ledger match raw financialEvents totals.

[ ] Ready to move on (requires evidence)

---

## Phase 4 — VAT on Service Fees (Estimates vs truth)
**Objective:** Ensure VAT treatment for non‑order fees is not missing.

If VAT report does NOT include service fee VAT:
- Apply UK VAT estimate (20%) to eligible fee categories.
- Mark as Estimated_VAT in output.

If VAT report includes fee VAT:
- Use VAT report amounts as source of truth for service fees.

Important policy note:
- Since **2024‑08‑01**, UK‑established sellers have **direct VAT (20%) on fees**.
- Older periods may show **reverse charge (0% VAT)**. Logic must allow both.

Validation:
- [ ] Storage/Disposal/Inbound fees show ExVAT + VAT in outputs.
- [ ] VAT estimate is labeled when no source provided.

[ ] Ready to move on (requires evidence)

---

## Phase 5 — P&L Integration (Daily + Monthly)
**Objective:** Wire ledger outputs into P&L lines.

Outputs:
- `out/pnl_daily.csv`
- `ProfitAndLoss_YYYY_MM` tabs
- `P&L_Summary` tab

Validation:
- [ ] Fees present for days where transactions exist.
- [ ] Subscription fee shown as £25 ExVAT / £5 VAT on 2026‑01‑01.
- [ ] Side‑by‑side comparison vs Amazon shows only rounding deltas.

[ ] Ready to move on (requires evidence)

---

## Phase 6 — Monitoring + Alerts
**Objective:** Prevent silent drift.

Add daily checks:
- [ ] Unmapped categories > 0 (alert)
- [ ] Missing VAT report for month (alert)
- [ ] Level‑2 orders missing Level‑3 after N days (alert)

[ ] Ready to move on (requires evidence)

---

## Phase 7 — Automation (Scheduled runs)
**Objective:** Ensure full pipeline runs reliably.

Schedule:
- Daily: Finances API → ledger → P&L
- Monthly: VAT report request → download → ledger merge

[ ] Ready to move on (requires evidence)

---

Notes / Evidence Log:
- 
-
-
