# Task Queue

Audit source: project control full audit on 2026-05-01.

## Scanner / F Price-List Manager

- [ ] F due checks now live in `project_control/DUE_CHECK_REGISTER.csv`; morning MOT should read `out/cycle_alerts/due_check_register_status.csv` for due/overdue follow-ups.
- [x] Investigate duplicate scanner ASIN `B0DPMGDZLZ` in `out/scanner_latest.csv`. User decision: different supplier SKUs are separate products and must not be sold together. Applied classification reason `different_sku_separate_product_not_sold_together`.
- [x] Add or confirm a scanner-level uniqueness check for ASIN plus supplier SKU. Implemented as `P012_scanner_identity_check.py`; current proof reads 51 scanner rows, 51 unique `asin + supplier_sku` keys, 0 exact duplicate keys, and 1 same-ASIN/different-supplier-SKU context row.
- [x] Insert approved scanner new-product candidates into SQL Product DB and local Product DB mirror. `P011_apply_scanner_product_db_inserts.py` inserted 51 rows, including the 2 duplicate-ASIN scanner rows as separate products with `different_sku_separate_product_not_sold_together`.
- [ ] Continue FPM live-owner monitoring from `out/systems/F/price_list_manager/live/live_cycle_status.csv` until pending rows materially reduce from 18168.
- [ ] Add a stable scanner proof summary that is not dependent on reading a live file mid-owner-run.
- [ ] Clean up F061 manual Seller Central login fallback UX and post-login proof. Trigger: after the current Seller Central login recovery proof window, or before relying on manual login again. Inspect artifacts: `out/systems/F/price_list_manager/live/f061_manager_mode_state.txt`, `out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt`, `out/systems/F/price_list_manager/live/seller_central_login_recovery_proof.csv`, and F061 child logs. Current evidence on 2026-06-02: Luke completed manual login, F later read BBP data and `Dashboard yes/no => YES`, but the proof file still recorded `manual_seller_central_login_wait_timeout` before recognising the success evidence. Success condition: the scanner-owned browser appears promptly, stays visible for the whole manual login hold, does not let other scanner pages jump in front while Luke types, records `Login Window Missing` if the window cannot be proved visible, reconciles later dashboard/eligibility success after manual login, and gives a clear succeeded/blocked proof row. If it fails: repair only the F061/FPM130 window-surfacing, focus-control, and post-login proof reconciliation path; do not run F061, restart workers, edit queues, change prices, write Sheets, align local DB facts, delete outputs, or open a separate Chrome login window without a separate approved proof packet.
- [ ] Wire O New Product Review `Re scan` decisions into a real F061 rescan queue. Read-only proof on 2026-06-02 showed `ai_rescan_promotion_status.csv` had `queue_rows=0` and `promoted_rows=0`, all `ai_rescan_queue.csv` files were empty, and `supplier_price_list_active_run.csv` contained 10,659 normal TD Synnex pending rows with blank `scan_reason`. Success condition: a Luke/operator `Re scan` decision creates a scanner-safe rescan row, FPM130 promotes it ahead of ordinary pending rows with a clear `scan_reason`, and tests prove it without editing the live queue or running F061. If it fails: fix the O event-to-F rescan bridge first; do not hand-edit F061 queue rows.
- [ ] Reconcile AI `rescan_needed` decisions with built F rescan queues before using them for scanner priority. Read-only proof on 2026-06-02 showed 13 rows across 9 handoffs where `codex_ai_review_decisions.csv` contains `rescan_needed`, while the matching `ai_rescan_queue.csv` files are empty; at least one handoff also has a built pass output that contradicts the later decision file. Success condition: FPM155 or an approved read-only checker proves whether each row is stale, already cleared, needs manual review, or belongs in `ai_rescan_queue.csv`; only rebuilt, current queue rows may be promoted by FPM130. If it fails: rebuild/reconcile the AI gate source first; do not inject rows directly into the live F061 queue from `codex_ai_review_decisions.csv`.
- [x] Deduplicate O New Product Review handoff dropdown by supplier and ASIN, and hide or group old superseded F handoff folders. Completed 2026-06-02: `O400_operator_ui.py` now groups current F review handoffs by supplier, reduces grouped rows to unique supplier/ASIN products, and applies latest supplier/ASIN review decisions across old duplicate handoff runs. Live DHB proof after the fix showed no current DHB pass option, DHB history folders at `0 passes to review`, and grouped DHB sent rows for `B001AI8AKI` and `B0853KGR7X` both already failed. Proof: `python -m py_compile scripts/flows/O/O400_operator_ui.py`; `python -m pytest tests/test_o_ui_operator_view.py -q` passed 90 tests. No review history, Product DB status, queues, prices, Sheets, or F handoff outputs were rewritten.
- [x] Provide or locate the latest ABGee price-list attachment, then rerun the single-supplier Gmail/import/O cost proof. Completed 2026-05-22: Gmail label `ABGee` contained `ABGee_Stock_Feed.xlsx` from `2026-05-21T14:47:06Z`; ABGee import batch `abgee_source_20260522T134758Z_fa74c131f665` produced 5770 valid rows, 2975 held rows, and 17 current ABGee O cost matches. Proof: `out/systems/O/history/abgee_pack_price_proof_20260522T134747Z/proof.md`.
- [ ] We Stock Lots authenticated export check. Trigger: when a logged-in CSV/XLSX export from `https://westocklots.com/api/export/stocklist/?format=csv` or `?format=xlsx` is available. Inspect artifact: exported file saved under `out/systems/F/price_list_manager/test_mode/downloaded_sources/we_stock_lots/Inbox/` or a manually supplied equivalent. Success condition: export contains usable barcode/EAN plus cost/price columns and converter produces scan-ready rows. If it fails: keep `we_stock_lots` parked and record whether the blocker is `unauthorized_export`, `missing_barcode`, or `missing_cost`.

## Database / Product DB

- [x] Define Product DB single source of truth: SQL, edited through the UI.
- [x] Define the SQL Product DB table contract before moving writes. Implemented in `scripts/core/storage/product_db_contract.py` with `seller_sku` primary key and non-unique ASIN index.
- [x] Decide whether the first implementation target is PostgreSQL production only, or SQLite local proof first with later PostgreSQL promotion. Current decision: PostgreSQL production target, SQLite local proof only.
- [ ] Mark Google Sheet `Product_DB` as legacy/export-only after SQL cutover.
- [ ] Mark CSV Product DB files as read-only mirrors/export artifacts after SQL cutover.
- [x] Control Product DB CSV mirror drift. P018 reports SQL/O rows 659, SQL unique `seller_sku` 659, legacy CSV mirror rows 608, and classifies the CSV as `mirror_stale_not_authority`.
- [x] Build exact Product DB reader migration map for A/B/E/H/F/O before changing any runtime consumers. P019 mapped 298 Product DB references across 87 files, with 0 unknown owners and 58 changes blocked without explicit approval.
- [x] Prepare PostgreSQL Product DB DDL, seed, export, and rollback rehearsal without live production promotion. P020 passed offline and reports production promotion `not_run_requires_explicit_approval`.
- [x] Make O Product DB operator view prefer SQL authority when the local `product_db_products` table exists. O030 rebuilt 659 operator rows from SQL while the legacy CSV mirror was stale at 608 rows.
- [x] Add a local-only Product DB edit-event applier. Implemented as `P014_apply_product_db_edit_events.py`; dry-run by default, confirmed local apply only, blocks unsafe ASIN identity changes, writes local SQL plus mirror export only.
- [x] Add SQL authority rehearsal proof for Product DB. Implemented as `P015_product_db_sql_authority_rehearsal.py`; latest proof reports SQL 659 rows, O view 659 rows, CSV mirror 608 rows, 0 FAIL, 3 WARN.
- [x] Build a staged legacy import check from current Sheet/CSV shape into SQL without changing live Product DB records. Implemented as `scripts/one_off/P008_product_db_sql_contract_check.py`; current live source fails closed before staged import.
- [x] Fix Product DB duplicate header `last_updated_A003` at the source/export generation path. Shared repair helper now coalesces duplicate Product_DB headers before A/B Product DB sheet updates or preview exports; current local preview has 71 unique columns and staged SQL import passes.
- [x] Add Product DB schema validation before SQL import, export, or mirror use. O030 now writes `out/systems/O/live/product_db_source_health.csv`; P008 writes `out/sql_migration/product_db_contract/product_db_sql_contract_check.csv`.
- [x] Review duplicate Product DB ASINs: `0786964502`, `B07RRQX71T`, `B09NQ9ZHDQ`. User decision: different SKUs stay on different rows and are classed as separate products not sold together. Recorded as `different_sku_separate_product_not_sold_together`.
- [x] Enforce Product DB identity rule in SQL: `seller_sku` is primary key.
- [x] Enforce ASIN rule: ASIN is controlled non-unique unless later approved otherwise.
- [x] Add a non-destructive Product DB unique-key validation for `seller_sku` and optional ASIN duplicates.
- [x] Build a safe local-only database linking test that simulates `WOULD INSERT`, `WOULD UPDATE`, `REVIEW`, and `BLOCKED` without writing SQL, CSV, or Google Sheets. Implemented as `scripts/one_off/P009_product_db_link_simulation.py`; current live run reads 51 scanner rows and returns 49 `WOULD INSERT`, 2 `REVIEW`, and 0 `BLOCKED`.

## Pricing / H Repricing

- [x] Investigate the 20 rows in `out/pricing_output.csv` with blank `execution_write_status`. Read-only proof `P013_repricing_write_status_proof.py` now distinguishes current H runtime evidence from stale audit pricing output.
- [x] Migrate the repricer tracker from Google Sheets to a UI view backed by SQL/read-only pricing outputs. O UI replacement candidate is locally complete; P017 reports `ready_with_stale_audit_warning`, missing critical fields `0`, tracker rows 89, terminal run `20260501T215343Z`, publish `ok`. The Sheet is not retired.
- [x] Keep the current repricer tracker Sheet as a temporary operator output until the UI replacement is proven. P017/P021 record Sheet status as temporary fallback until explicit operator cutover.
- [ ] Complete one normal operating day of repricer tracker UI observation before retiring or disabling the repricer tracker Sheet. User accepted this path on 2026-05-02; keep the Sheet fallback during observation.
- [x] Define the UI repricer tracker fields from existing H outputs before changing `scripts/flows/H/H130_build_phase1_observation_sheet.py`.
- [ ] Let the next owner health pass clear or confirm stale H freshness FAIL rows from `out/cycle_alerts/checklist_H.csv`.
- [x] Keep separate evidence for eligible-to-write, decision-to-change-price, write-attempted, and write-applied stages. P017 requires those tracker fields before UI parity can pass.
- [x] Add a compact H pricing proof summary that records latest run id, finalized status, publish status, and write status counts. Implemented as read-only `P013_repricing_write_status_proof.py`; current proof writes `repricing_write_status_proof_summary.json` and `repricing_write_status_root_cause.csv`.
- [x] Decide whether H should normalize `WRITE_NOT_APPLIED` to an approved contract value such as `ERROR`/`BLOCKED`, or whether `WRITE_NOT_APPLIED` should be added to the approved write-status contract. User approved the suggested path; `WRITE_NOT_APPLIED` is now an approved contract status because it is already produced by the write-verification path when a write was attempted but not applied.
- [x] Apply the H source blank-status normalization patch. `run_H_pricing_cycle.py` now sets and re-asserts `execution_write_status=READ_ONLY_NO_WRITE` for current-cycle no-market-data rows after truth reconciliation and sets `execution_write_status=NO_WRITE_REQUIRED` for parked rows; `H130_build_phase1_observation_sheet.py` keeps parked rows as `NO_WRITE_REQUIRED`.
- [x] Mark stale audit `out/pricing_output.csv` separately in P013/O050 instead of treating it as current H source proof. Current stale reason: `pricing_output_older_than_runtime_and_missing_latest_runtime_run`.
- [x] Run H-owned proof for blank-status normalization. Owner run `20260501T183549Z` finalized with publish `ok`; P013 at `2026-05-01T18:56:55Z` reports runtime blanks `0`, invalid statuses `0`, proof-run rows `49`, and proof-run status counts `APPLIED=3`, `NO_WRITE_REQUIRED=34`, `READ_ONLY_NO_WRITE=12`. O050 health has 9 ok checks and 2 stale-audit warnings only.
- [x] Re-check repricer tracker UI cutover after latest H terminal recovery. P016 at `2026-05-01T21:01:46Z` reports `ready_with_stale_audit_warning`, `fail_count=0`, terminal run `20260501T203514Z`, publish `ok`; remaining warning is stale audit `out/pricing_output.csv`.
- [x] Root-cause H `item_offers` timeout from run `20260501T174941Z` before using H as repricer tracker sign-off evidence. Evidence showed one-cycle retry expanded the candidate ASIN budget to 65 and the snapshot budget to 645 seconds, but the `H_item_offers_lookup.py` subprocess still had a fixed 240-second watchdog. Code now passes the remaining retry-aware snapshot budget into the helper watchdog, with focused tests covering base, expanded, and nearly-consumed budget cases.
- [x] Confirm whether 4 `APPLIED` pricing rows in the latest proof are expected under current writer mode. O050 shows 3 current proof-run `APPLIED` rows from `20260501T183549Z` with eligible/write-attempted/write-applied flags all `1`; the fourth `APPLIED` row is historical from `20260430T134435Z` and not part of the latest terminal proof run.
- [x] Keep stale compact `out/pricing_output.csv` as audit-only until a later approved cleanup/export refresh removes its historical blank-status rows without hiding source truth. P013/O050/P016/P017 classify it as stale audit evidence and do not use it as current H runtime proof.

## B Cycle

- [x] MAIN MONDAY MOT TASK: Resolve `token_shortages_by_sku` FAIL with value 6 in `out/cycle_alerts/checklist_B.csv`. Completed on 2026-05-06 after approved correction tokens were applied under B maintenance; B proof cycle `B_20260506T083023Z` finalized with `token_shortages_by_sku=ok 0`.
- [x] Review `order_master_placeholder_cogs_rows` WARN with value 6. Cleared in the same B proof cycle with `order_master_placeholder_cogs_rows=ok 0`.
- [x] Record B management-ready status from the 2026-05-27 manager proof: missing Amazon.ae order `171-1388771-2409132` is in the live B order chain, survived a normal B cycle, Sellerboard shows 0 shipped orders missing from SellerOne, promotion proof is live, and the final B proof cycle had 0 B gate fails.
- [x] Refresh B per-marketplace cursor proof. Completed 2026-05-30 with read-only cursor proof scan; `b_future_marketplace_order_cursors` cleared from 12 stale cursors to proved. No B run, restart, Sheet write, queue/price edit, local DB alignment, output deletion, live merge, or missing-order fetch was performed.
- [x] Resolve the current B token-shortage path for SKU `AK-OB6V-HIYD`, missing quantity `3`, shortage class `true_live_shortage`. Luke approved correction on 2026-05-30. Applied 3 approved stock-correction tokens with `T030_apply_approved_token_corrections.py` under B maintenance. Proof cycle `B_20260530T191754Z` published P and L and finalized with split B health `fail=0`, `warn=0`; B MOT now has `fail_count=0` and no Luke decision.
- [ ] Continue B refund, fee, shipping, and ROI proof work. Keep Sellerboard values labelled as bridge evidence only; do not feed them into live ROI/restocking until API-backed proof or explicit Luke approval exists.
- [ ] Keep B proof owner-safe. If a manual B proof is required, use maintenance handoff and `B_RUN_ONCE=1` only at a safe boundary.

## A Cycle

- [ ] Do not run A015 ad hoc as proof. Use next A-owned run or an explicitly approved A-owned proof window.
- [ ] Confirm whether `out/system_health_checklist.csv` should be refreshed by the next scheduled A015 after the H runtime evidence at 2026-05-01T14:20:11Z.
- [ ] Record A current-state evidence from owner artifacts after the next completed A run.

## E Analytics

- [ ] Keep E scoped proof separate from global health. E checklist currently has 23 ok and 0 fail/warn.
- [ ] Add a small E proof summary from `out/systems/E/live/e_run_log.jsonl` with latest success run id and row counts.
- [x] Prove E confidence and coverage labels after Luke approves an E-owned proof run. Completed 2026-05-27 after approved one-off E proof run `20260527T101108436384Z`. `out/systems/M/hourly_mot_E.csv` no longer warns for missing confidence fields, missing coverage summary, or restock readiness not live. Remaining E warnings are business coverage gaps: ROI proof covers 43 of 161 SKUs and daily-truth explanation is blank for 117 of 161 study rows.
- [ ] Create bounded E follow-up tasks for the remaining coverage gaps only when they block a business decision: ROI-backed profit proof coverage and blank daily-truth explanation coverage. Do not write Sheets, change prices, edit queues, delete outputs, align local DB data, or rerun E again without approval.

## O Operations

- [ ] Standardize module execution for O scripts that import `scripts.flows.*`; direct path execution can fail without `PYTHONPATH`.
- [ ] Improve O New Product Review visibility for supplier handoffs. Bliss proof on 2026-06-02 showed 19 raw first-check PASS rows split into 4 clean AI/operator passes and 15 held near-miss/manual rows across two handoffs. Success condition: O can show a combined supplier view that clearly separates raw first-check passes, clean AI/operator passes, and held/manual rows without relying on the old legacy second-check file.
- [x] Add a Product DB operator view schema check that reports source duplicate headers before the O view masks them.
- [ ] Confirm O outputs that remain planned or empty are marked NOT VERIFIED, not treated as complete.
- [ ] Verify the O single workflow view as a user walkthrough only. Success condition: the operator can inspect Product DB, restock review, proof labels, holds, and blocked action states without creating PO, receiving, send-to-Amazon, Sheet, price, queue, DB-alignment, output-deletion, H-pause, market-scan, or business-approval actions.
- [ ] Add O pack and supplier readiness proof as read-only manager evidence. Success condition: pack/supplier readiness is visible as not_verified, ready, or blocked with source proof and no purchase commitment or receiving action.
- [ ] Refresh stale O active proof files only through an approved O proof path when they block the next O build step. Success condition: `o_active_restock_proof_files` has no stale warning after the approved proof refresh; if it fails, inspect the earliest O builder source instead of editing outputs.
- [ ] Keep O/H market proof parked until clean H maintenance controller install proof exists and a separate approved proof packet proves H ownership restoration. Success condition: controller install proof is clean and the later packet proves pause, candidate-only market proof, resume, and restored H ownership; if not, keep market proof parked.
- [ ] Build the future native live O loop in separate approved phases: native Restock Advisor, human approval gate, PO creation, ordered stock, receiving, send-to-Amazon, and closed-loop feedback. Success condition: each phase has a health check, schema check, idempotent output, and protected-action boundary before any runtime use.

## External Integrations

- [ ] Produce a read-only external integration inventory: Amazon SP-API, Google Sheets, BBP/web scrape, and scheduler task names.
- [ ] Add a no-write external integration smoke test plan. Do not execute write-capable Sheet or listing calls without explicit approval.
- [ ] Export or document scheduler XML for `AMZ Orders`, `AMZ H Cycle`, and `AMZ Controlled Restart` if those tasks are still active owners.
- [ ] Fix controlled restart gate/ownership handling after missed 2026-05-06 overnight reboot. Evidence: `AMZ Controlled Restart` ran at 2026-05-06 02:10:02 local with task result 0, but `out/locks/restart_control/restart_controller.latest.json` ended `skipped_post_heal_blocked` with final blockers `H_LAUNCHER_ACTIVE`, `H_CYCLE_ACTIVE_LOCK`, `B_ACTIVE_LOCK`, `F_MANAGER_ACTIVE_LOCK`, and `AMBIGUOUS_OWNERSHIP_HOLD`; OS `LastBootUpTime` remained 2026-05-05 02:24:12. Success condition: next controlled restart either reboots inside the 02:00-03:00 window after a clean drain boundary, or records one explicit safe skip reason without relaunching owners into a self-blocking final gate.

## Governance

- [x] Build a proper due-check register for deferred operational checks, with fields for due date, owner flow, artifact to inspect, success condition, and alert status. Implemented as `project_control/DUE_CHECK_REGISTER.csv` plus `scripts/tools/due_check_register.py`.
- [ ] Keep `project_control/SCRIPT_INVENTORY.csv` current when new flow scripts or entrypoints are added.
- [ ] Convert `project_control/OUTPUT_SCHEMA_CHECKS.md` into a repeatable check if these visibility exports become daily artifacts.
- [ ] Update roadmap/expectation progress only when a flow-owned proof confirms a real reliability or completion change.
