# One-off / Temporary Scripts (Renumbered)

Moved to scripts/one_off and renumbered with T###_ prefix.

## Mapping (old -> new)

- scripts/one_off/T001_B011_build_token_tests_daily.py -> scripts/one_off/T001_B011_build_token_tests_daily.py
- scripts/one_off/T002_B015_fix_duplicate_token_ids.py -> scripts/one_off/T002_B015_fix_duplicate_token_ids.py
- scripts/one_off/T003_B017_backfill_missing_tokens_from_orders_sheet.py -> scripts/one_off/T003_B017_backfill_missing_tokens_from_orders_sheet.py
- scripts/one_off/T004_B018_add_placeholder_purchase_rows.py -> scripts/one_off/T004_B018_add_placeholder_purchase_rows.py
- scripts/one_off/T005_B019_rebuild_tokens_for_top_mismatches.py -> scripts/one_off/T005_B019_rebuild_tokens_for_top_mismatches.py
- scripts/one_off/T006_B022_rebuild_tokens_for_all_mismatches.py -> scripts/one_off/T006_B022_rebuild_tokens_for_all_mismatches.py
- scripts/one_off/T007_B027_backfill_commission_bands.py -> scripts/one_off/T007_B027_backfill_commission_bands.py
- scripts/one_off/T008_B029_backfill_fba_fee_bands.py -> scripts/one_off/T008_B029_backfill_fba_fee_bands.py
- scripts/one_off/T009_B031_backfill_tokens_from_orders_sheet.py -> scripts/one_off/T009_B031_backfill_tokens_from_orders_sheet.py
- scripts/one_off/T010_B034_full_rebuild_tokens_from_orders_sheet.py -> scripts/one_off/T010_B034_full_rebuild_tokens_from_orders_sheet.py
- scripts/one_off/T011_B036_test_vat_transaction_report_sigv4.py -> scripts/one_off/T011_B036_test_vat_transaction_report_sigv4.py
- scripts/one_off/T012_C001_seed_product_db.py -> scripts/one_off/T012_C001_seed_product_db.py
- scripts/one_off/T013_D002_backfill_all_markets.py -> scripts/one_off/T013_D002_backfill_all_markets.py
- scripts/one_off/T014_D005_seed_tokens_from_orders_sheet.py -> scripts/one_off/T014_D005_seed_tokens_from_orders_sheet.py
- scripts/one_off/T015_D006_backfill_token_allocations.py -> scripts/one_off/T015_D006_backfill_token_allocations.py
- scripts/one_off/T016_D008_rebuild_tokens_for_sku.py -> scripts/one_off/T016_D008_rebuild_tokens_for_sku.py
- scripts/one_off/T017_D010_add_legacy_tokens.py -> scripts/one_off/T017_D010_add_legacy_tokens.py
- scripts/one_off/T018_D014_fix_order_master_cogs_cancelled.py -> scripts/one_off/T018_D014_fix_order_master_cogs_cancelled.py
- scripts/one_off/T019_D020_backfill_missing_orders_from_sellerboard.py -> scripts/one_off/T019_D020_backfill_missing_orders_from_sellerboard.py
- scripts/one_off/T020_B002_run_financial_events_to_sheet.py -> scripts/one_off/T020_B002_run_financial_events_to_sheet.py
- scripts/one_off/T021_B003_estimate_financials_csv.py -> scripts/one_off/T021_B003_estimate_financials_csv.py
- scripts/one_off/T022_B004_build_order_audit.py -> scripts/one_off/T022_B004_build_order_audit.py
- scripts/one_off/T023_rebuild_level1_from_archive.py -> scripts/one_off/T023_rebuild_level1_from_archive.py
- scripts/one_off/T024_rebuild_level1_level2_from_archive.py -> scripts/one_off/T024_rebuild_level1_level2_from_archive.py
- scripts/one_off/T025_test_fee_api.py -> scripts/one_off/T025_test_fee_api.py
- scripts/one_off/T026_test_financial_events_24h.py -> scripts/one_off/T026_test_financial_events_24h.py
- scripts/one_off/T027_test_financial_events_level3_window.py -> scripts/one_off/T027_test_financial_events_level3_window.py
- scripts/one_off/T028_backdate_tokens_from_live_stock.py

## Current operational one-off helpers

- `scripts/one_off/F036_build_passed_product_page_evidence_backfill_queue.py`
  - Purpose: build a passed-product Amazon page evidence backfill queue from local Pass review files
  - Use for: finding clean Pass rows that still need `product_detail_text`, `product_description`, or `product_feature_bullets`
  - Includes: scanner-ready F061 active-run staging output, schema health checks, and summary outputs
  - Safe boundary: builds local queue files only; does not scrape, change Google Sheets, or change the product database

- `scripts/one_off/F037_run_passed_product_page_evidence_backfill_batch.py`
  - Purpose: stage and optionally execute controlled F061 batches for passed-product page evidence backfill
  - Use for: working through the full historical backfill queue while recording per-ASIN status
  - Includes: durable state file, batch manifest, batch health output, isolated proof roots, and consolidated backfill results
  - Safe boundary: one-off only; default prepare mode does not scrape; execute mode refuses live F overlap unless explicit maintenance forcing is requested

- `scripts/one_off/F038_apply_page_evidence_backfill_to_review_packs.py`
  - Purpose: fill blank New Product Review page-evidence fields from successful F037 backfill results
  - Use for: refreshing already-built review packs that were created before Amazon description/detail/bullet capture existed
  - Includes: dry-run previews, execute-mode backups, manifest output, and health output
  - Safe boundary: one-off only; does not change scanner evidence, Google Sheets, product database, or user review decisions

- `scripts/one_off/F039_build_legacy_pass_ai_candidate_queues.py`
  - Purpose: convert old pre-AI clean Pass handoff rows into current AI candidate manifests
  - Use for: moving legacy clean Pass rows into the normal FPM155/Codex AI gate without treating legacy manual/near rows as clean Pass work
  - Includes: dry-run mode, execute-mode manifest backup, clean-pass-only empty near-miss placeholder, conversion report, and optional FPM155 queue build
  - Safe boundary: one-off only; does not change Google Sheets, product database, scanner evidence, or user review decisions

- `scripts/one_off/P001_create_plan_workspace.py`
  - Purpose: create a standard plan folder under `plans/active/`
  - Use for: starting a new planning and execution workspace for a ticket
  - Includes: build-lane and debug-lane starter files
  - Safe boundary: one-off only, not for daily loops

- `scripts/one_off/P002_plan_forced_proof_window.py`
  - Purpose: produce a read-only forced-proof plan for A, B, E, or H runtime validation
  - Use for: deciding how to prove a single-run or scoped fix now without unsafe overlap
  - Includes: lock and marker readout, safe boundary, preflight checks, and command sequence
  - Safe boundary: read-only planner only; execution still happens through the flow-owned cycle or isolation path
