# Tropicana Email Price Files - 2026-05-19

## Goal
Add Tropicana Wholesale to the same on-demand Gmail price-file intake pattern as TD Synnex.

## Current Facts
- Supplier id: `tropicana_wholesale`.
- Supplier name: `Tropicana Wholesale`.
- Gmail label: `Tropicana`.
- Today attachment seen in Gmail: `StockExport_190526_090831.xlsx`.
- Registry state: `active_flag=0`, `priority_band=parked`.

## Safety Rules
- Do not change Google Sheets.
- Do not activate Tropicana for live F061 scanning in this phase.
- Do not start another F scanner while the TD Synnex live scanner is running.
- Use test-mode acquisition/import only until row counts and field mapping are proven.
- Back up changed files before edits.

## Phases
- Phase 1: extend Gmail fetcher so Tropicana can fetch `.xlsx` from label `Tropicana`.
- Phase 2: download today's newest Tropicana attachment into its inbox.
- Phase 3: inspect workbook columns and build a dedicated Tropicana converter.
- Phase 4: import into test mode and prove row mapping, held rows, and scanner eligibility.
- Phase 5: leave Tropicana parked unless the user explicitly approves live activation.

## Verification
- Gmail fetch should report `fetched_sources=1`.
- Import should create a Tropicana batch with real SKU/title/barcode/cost columns.
- Held rows must have explicit hold reasons such as missing barcode or missing cost.
- No live handoff should be applied.

## Rollback
- Backup folder: `project_control/backups/tropicana_email_intake_20260519T101200Z`.

## Result
- Gmail fetch result: `fetched_sources=1`, `bytes=397964`.
- Downloaded attachment: `StockExport_190526_090831.xlsx`.
- Attachment type: stock export, not price list.
- Workbook columns: `Brand name`, `Sku code`, `Name`, `Actual quantity`, `Product group description`, `Barcode`.
- Missing required scanner field: `unit_cost`.
- Import result: `6462` source rows, `0` valid scan-ready rows, `6462` held rows.
- Hold reasons:
- `missing_cost`: `5806`
- `missing_barcode|missing_cost`: `449`
- `invalid_barcode_format|missing_cost`: `207`
- Live handoff: not applied.

## Conclusion
Tropicana email download and import plumbing is ready, but the current Gmail attachment cannot drive the price-list scanner because it contains no cost/price data.
