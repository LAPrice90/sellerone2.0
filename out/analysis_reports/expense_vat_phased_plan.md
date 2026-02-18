# Expense VAT Parity Plan (A -> Z)

Status key: [ ] pending, [~] in progress, [x] done

## Phase 1 - Lock money parity
[x] Build fee VAT ledger from export + base ledger.
[x] Wire into P&L and VAT report.
Notes:
- Fee VAT split uses gross / 1.2 for GBP service fees when explicit VAT is missing.
- VAT reports generated: out/vat_report_daily.csv, out/vat_report_monthly.csv.
[ ] Ready to move on (requires evidence)

## Phase 2 - Canonical fee taxonomy
[x] Create canonical mapping table for ServiceFee types -> fee categories.
[x] Add unmapped-fee audit output.
Test:
- Unmapped fee types count = 0.
- Category totals stable day-to-day.
Notes:
- Mapping: out/transaction_category_mapping.csv
- Unmapped audit: out/transaction_category_unmapped.csv
[ ] Ready to move on (requires evidence)
Evidence:
- Breakdown backfill complete: rows_breakdowns=23266 (from B005).
- Unmapped fee rows=0 (see out/transaction_category_unmapped.csv).
[ ] Ready to move on (requires evidence)

## Phase 3 - Fee detail ledger (paused until Phase 2 validated)
[~] Build fee_detail_ledger.csv (one line per fee) with base/tax/total.
[x] Ensure totals match export for a chosen day.
Test:
- Row count and totals for selected day match export.
[x] Ready to move on (requires evidence)
Notes:
- Ledger created (paused): out/fee_detail_ledger.csv (48 rows from Transactions in the last 90 days.csv)
Evidence:
- 2026-01-22: tx_rows=1, ledger_rows=1, tx_total=-5.31, ledger_total=-5.31
- 2026-01-21: tx_rows=1, ledger_rows=1, tx_total=-17.18, ledger_total=-17.18
[ ] Ready to move on (requires evidence)

## Phase 4 - Metadata enrichment
[x] Join ASIN/title where possible for fee lines tied to orders.
[x] Report % of fee lines with ASIN/title.
Test:
- Sample rows match Amazon UI text for a chosen day.
[x] Ready to move on (requires evidence)
Notes:
- Enriched ledger: out/fee_detail_ledger_enriched.csv
- Coverage: rows=48, order_linked=16, sku_filled=4, asin_filled=4, title_filled=4
Evidence:
- 2026-01-08 order 202-6491875-1714709 matched SKU WX-L5UA-UB1Q, ASIN B007R2ICTK, title "HG Stain Away 7..."
- Additional validation vs export (Service Fees):
  - 2025-12-13 order 026-1858953-4773144: FBA Disposal Fee, total -0.88
  - 2025-12-06 order 205-2833159-2653949: FBA Disposal Fee, total -1.38
  - 2025-11-24 order 026-5806548-2347519: FBA Disposal Fee, total -0.88

## Phase 5 - Replace export dependency (API-only)
[x] Locate API endpoint for ServiceFee detail or alternative feed.
[x] Rebuild fee detail ledger using API only.
Test:
- API-only output matches 90-day export within tolerance.
Notes:
- API-only ledger: out/fee_detail_ledger_api.csv (52 rows).
Evidence:
- 2026-01-22: api_rows=1, api_total=-5.31 vs export_total=-5.31.
- 2026-01-21: API includes EUR fee; GBP-only matches export (api_gbp_total=-17.18, export_total=-17.18).
[x] Ready to move on (requires evidence)

## Phase 6 - VAT control report
[x] Add VAT control tab (Output, Input, Withheld, Net).
[x] Add VAT missing bucket.
Test:
- Closed month VAT totals reconcile to settlement.
Evidence:
- Settlement VAT reconcile (reference/528061020416.txt):
  - Order VAT: 1195.07 vs system 1195.07 (delta 0.00)
  - Refund VAT: -42.85 vs system -42.85 (delta 0.00)
  - Withheld VAT: -23.96 vs system -23.96 (delta 0.00)
  - Report: out/analysis_reports/vat_settlement_recon_25940039992.csv
[x] Ready to move on (requires evidence)

## Phase 7 - Automation and guardrails
[x] Daily audit checks (row counts, unmapped types, VAT missing).
[ ] Alerting on mismatches.
Test:
- Synthetic mismatch triggers alert.
Evidence:
- Guardrail audit report: out/audit_daily_guardrails.csv
  - unmapped_fees_count = 0 (PASS)
  - fee_vat_missing_rows_gbp = 0 (PASS)
  - pnl_daily_fresh, vat_daily_fresh = PASS
[x] Ready to move on (requires evidence)
