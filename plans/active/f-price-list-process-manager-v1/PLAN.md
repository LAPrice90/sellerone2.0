# F Price List Process Manager v1 - System Plan

Date: 2026-04-30

## A. Purpose
The price-list process manager decides what supplier list should be handled next.

It is not the scanner. It is the traffic controller before the scanner.

Target flow:
1. Check the next supplier or source that may have a new price list.
2. Acquire the file by the supplier's method.
3. Store the raw file as its own batch.
4. Convert the file to the universal F supplier format.
5. Decide which rows in that batch are worth scanning now.
6. In test mode, send rows to a placeholder scanner.
7. Later, when safe, hand one prepared batch to F061 only if F061 is idle or explicitly switched over.
8. Record results, update cooldown memory, then repeat.

## B. Current Live Boundary
The live scanner is currently working through `supplier_price_list_active_run.csv` and `supplier_price_list_run_state.csv`.

Current plan rule:
- v1 manager is read-only against live F061 artifacts.
- v1 manager may write only to its own test/output area.
- no automatic F061 start
- no active-run overwrite
- no supplier switch while F061 is running

## C. Proposed Data Model
### 1. Supplier Registry
One row per supplier.

Required fields:
- `supplier_id`
- `supplier_name`
- `source_type`: `manual_request`, `email_attachment`, `api_pull`, `url_download`, `local_file`
- `converter_id`
- `normal_refresh_days`
- `minimum_rescan_days`
- `large_file_flag`
- `manual_request_required_flag`
- `priority_band`
- `active_flag`
- `notes`

Purpose:
- tells the manager how the file is acquired
- tells the manager how often it is worth checking
- prevents a one-size-fits-all supplier loop

Examples:
- Shure Cosmetics: `api_pull` with `csv_link` subtype, daily cadence, use the existing CSV URL and existing Shure converter as the first pilot example.
- DHB or Bliss: `manual_request`, monthly cadence, do not scan again before a new file arrives.
- TD Synnex: `email_attachment`, daily file cadence, huge file, scan only new rows and cooldown-expired rows.
- API supplier: `api_pull`, scheduled check, dedupe by file hash and row hash.

### 2. Price List Batches
One row per acquired file.

Required fields:
- `batch_id`
- `supplier_id`
- `source_type`
- `source_received_at_utc`
- `source_file_path`
- `source_file_hash`
- `converted_file_path`
- `source_row_count`
- `valid_row_count`
- `held_row_count`
- `new_row_count`
- `changed_row_count`
- `eligible_row_count`
- `skipped_cooldown_row_count`
- `batch_status`
- `status_reason`
- `updated_at_utc`

Recommended `batch_status` values:
- `received`
- `converted`
- `recommendation_ready`
- `test_scan_running`
- `test_scan_complete`
- `ready_for_f061_handoff`
- `active_in_f061`
- `completed`
- `blocked`
- `superseded`

### 3. Batch Rows
One row per supplier price-list row inside a batch.

Required fields:
- `batch_id`
- `supplier_id`
- `row_key`
- `supplier_sku`
- `barcode`
- `unit_cost`
- `currency`
- `source_row_hash`
- `row_change_status`: `new`, `changed`, `unchanged`
- `scan_eligibility`: `scan_now`, `skip_cooldown`, `skip_unchanged`, `blocked_missing_data`
- `eligibility_reason`
- `last_memory_key`
- `cooldown_until_utc`

### 4. Barcode Scan Memory
This is the key cost-saving table.

Use two levels:
- global barcode memory for product facts that do not depend on supplier cost
- supplier offer memory for supplier-specific facts like cost and ROI

Global memory key:
- `barcode` plus `asin` when known

Supplier offer memory key:
- `supplier_id` plus `barcode` plus `supplier_sku` plus `unit_cost`

Required fields:
- `memory_key`
- `memory_scope`: `global_barcode` or `supplier_offer`
- `supplier_id`
- `barcode`
- `asin`
- `last_result_status`
- `last_fail_code`
- `last_stage`
- `last_scanned_at_utc`
- `cooldown_until_utc`
- `cooldown_basis`
- `attempt_count`
- `last_batch_id`
- `last_row_hash`
- `updated_at_utc`

Reason:
- a barcode that failed history checks may not need another expensive history scan for months
- a barcode that failed ROI might pass if a supplier sends a better price
- a barcode with missing ASIN might be worth trying again sooner than a history fail

### 5. Manager Decisions
One row per manager cycle.

Required fields:
- `decision_id`
- `decided_at_utc`
- `recommended_action`
- `supplier_id`
- `batch_id`
- `reason_code`
- `estimated_scan_rows`
- `estimated_skip_rows`
- `f061_owner_status`
- `safe_to_handoff_flag`
- `notes`

Recommended actions:
- `request_manual_price_file`
- `wait_for_email_file`
- `pull_api_file`
- `convert_batch`
- `run_test_scan`
- `recommend_f061_handoff`
- `do_nothing_wait`
- `blocked_needs_user_decision`

## D. Source Acquisition Model
Every supplier has its own acquisition method, but the manager sees one standard result: a raw source artifact plus metadata.

### Manual Request
Used for suppliers who send lists only after asking.

Manager behavior:
- if request is due, emit `request_manual_price_file`
- do not create a batch until a file is actually received
- do not rescan the previous monthly list just because scanner capacity is available

### Email Attachment
Used for suppliers who send regular files by email.

v1 implementation:
- use a local import folder first, for example `imports/price_lists/<supplier_id>/inbox`
- dedupe by file hash
- later, an email connector can drop attachments into the same folder

Manager behavior:
- store every new file as a batch
- scan only if the batch has new rows, changed rows, or cooldown-expired rows

### API Pull
Used for suppliers with API access.

Manager behavior:
- call supplier adapter only when supplier is acquisition-due
- store response payload or exported file as the raw artifact
- create a new batch only if file hash or row hash evidence changed

### URL Download Or Local File
Used where existing `F005` style source config already works.

Manager behavior:
- pull or copy the source
- store a batch-specific raw file
- convert through the supplier converter

## E. Queue Decision Model
The manager should not simply scan suppliers in a fixed order.

It should score useful work:
- new rows are valuable
- changed cost rows are valuable
- cooldown-expired rows are valuable
- unchanged rows inside active cooldown are not valuable
- manual monthly suppliers are not valuable until a fresh list exists
- huge lists need stricter row filtering before scanning

Simple v1 decision order:
1. Complete any interrupted test-manager batch first.
2. If a manual supplier request is due, recommend the request.
3. If a new source file exists, convert it.
4. If a converted batch has eligible rows, recommend test scan.
5. If multiple batches are eligible, pick the highest score:
   - high score for new barcodes
   - high score for changed costs
   - medium score for cooldown-expired rows
   - low score for stale but unchanged rows
   - penalty for huge estimated scan time
6. If nothing is useful, recommend waiting and name the next expected supplier event.

## F. Row Cooldown Policy
Start simple. Make it smarter later only after the manager proves clean movement and count reconciliation.

### v3 Balanced Default Cooldowns
Short cooldowns do not protect scan capacity when a complete supplier-file pass may take months. The balanced rule uses 90 days as the standard wait, 180 days as the high end for slow-moving evidence, and keeps cost-sensitive rows eligible as soon as the supplier cost changes.

| Result or fail code | v3 cooldown | Reason |
|---|---:|---|
| `PASS` | no repeat for same batch | row moves to review or approval; do not rescan same evidence |
| `NOASIN` | 90 days | catalog match may improve but not usually inside days |
| `OVER50K` | 90 days | demand/rank can change over a market cycle |
| `NOCOST` | until source row cost changes, max 90 days | supplier file issue, not scanner issue |
| `ROIFAIL` | until source row cost changes, max 90 days | cost change is the cleanest reason to retest economics |
| `LOWROI` | until source row cost changes, max 60 days | closer economics deserve a shorter review window |
| `SCRAPEFAIL` | 30 days | technical scrape failures can recover sooner but should not churn daily |
| `RESCAN` | 30 days | reserved for technical retry rows after price-history failures are split out |
| `PRICEHISTORYFAIL` | 180 days | no usable 365-day price history is slow-moving evidence |
| `HAZMATFAIL` | 365 days | expensive and unlikely to change quickly |
| `BRANDFAIL` or direct-seller block | 180 days | policy or market structure issue |
| `NODATE` or `REVIEWFAIL` | 90 days | evidence may improve over a normal cycle |
| `SELLERHISTORYFAIL` or `HISTORY_RISK_BLOCK` | 180 days | expensive history evidence should not be repeated monthly |
| `FAIL` or unknown fallback | 90 days | generic failures are a process problem and should not churn |

### Later Dynamic History Cooldown
The smarter version can calculate exactly when the blocking history evidence ages out of the 12-month window.

Example:
- Amazon price evidence from 8 months ago is blocking a row.
- The row works on a 12-month window.
- That evidence stops blocking after roughly 4 more months.
- The later rule can set `cooldown_until_utc` to the newest blocking evidence date plus 365 days plus a small buffer.

v3 should not start here. Use the simple 180-day history cooldown first and only add dynamic expiry after result memory is reliable.

## G. Test-Mode Placeholder Scanner
Before real integration, build a fake scanner that returns controlled outcomes.

Test source:
- one or more fake suppliers
- one fake price-list batch
- 10 fake barcodes

Round 1 expected movement:
- 10 source rows received
- 10 rows converted
- 10 rows scan eligible
- 10 placeholder results returned
- 10 memory rows written
- batch summary reconciles to 10

Round 2 expected movement with same rows:
- unchanged rows do not get rescanned
- cooldown rows remain skipped
- pass rows do not repeat for the same batch
- manager recommends no useful scan unless a row changed or cooldown expired

Round 3 expected movement with a changed file:
- new rows are scanned
- changed cost rows are rescanned where supplier offer memory requires it
- unchanged rows still in cooldown are skipped

### 10 Placeholder Outcomes
| Row | Fake outcome | Expected manager behavior |
|---:|---|---|
| 1 | `PASS` | record pass, route to next review layer, no same-batch rescan |
| 2 | `NOASIN` | set 90-day cooldown |
| 3 | `OVER50K` | set 90-day cooldown |
| 4 | `NOCOST` | block until source cost changes |
| 5 | `ROIFAIL_NEAR` | set 60-day supplier-offer cooldown |
| 6 | `ROIFAIL_FAR` | set 90-day supplier-offer cooldown |
| 7 | `SCRAPEFAIL` | set 30-day retry cooldown |
| 8 | `SELLERHISTORYFAIL` | set 180-day global barcode cooldown |
| 9 | `BRANDFAIL` | set 180-day global barcode cooldown |
| 10 | `MANUAL_REVIEW` | hold until decision or fallback cooldown |

## H. F061 Handoff Rule - Later Phase Only
The manager can recommend handoff before it can execute handoff.

Before execution is allowed, the system needs:
- a reliable F061 owner check
- a clear F061 idle definition
- a lock that prevents two owners
- a staged handoff file
- a rollback/snapshot of current F live files
- proof that F061 consumes exactly one batch and finalizes it

Initial handoff state:
- `safe_to_handoff_flag=false`
- `recommended_action=recommend_f061_handoff`
- human approval required before any live handoff implementation

## I. Health Checks Required
Any implementation of this manager must add health output.

Minimum checks:
- supplier registry has unique active supplier IDs
- every active supplier has an acquisition method
- every acquired batch has a source file path and file hash
- converted row counts reconcile to raw rows plus holds
- batch rows reconcile to manager decision counts
- placeholder scanner results reconcile to scan-ready rows
- cooldown memory has no duplicate active keys
- no live F061 handoff is attempted while owner status is busy or unknown

## J. Proposed File Layout
Planning files:
- `plans/active/f-price-list-process-manager-v1/PROJECT_BRIEF.md`
- `plans/active/f-price-list-process-manager-v1/PLAN.md`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`

Future runtime files:
- `config/feeder/price_list_manager/suppliers.csv`
- `out/systems/F/price_list_manager/price_list_batches.csv`
- `out/systems/F/price_list_manager/batch_rows.csv`
- `out/systems/F/price_list_manager/barcode_scan_memory.csv`
- `out/systems/F/price_list_manager/manager_decisions.csv`
- `out/systems/F/price_list_manager/health.csv`
- `out/systems/F/price_list_manager/test_mode/placeholder_scanner_results.csv`

Future scripts:
- `scripts/flows/F/price_list_manager/FPM001_build_test_fixtures.py`
- `scripts/flows/F/price_list_manager/FPM010_run_manager_once.py`
- `scripts/flows/F/price_list_manager/FPM020_run_placeholder_scanner.py`
- `scripts/flows/F/price_list_manager/FPM030_update_memory_from_results.py`
- `scripts/flows/F/price_list_manager/FPM040_build_next_action.py`

Current first supplier example:
- `shure_cosmetics`
- registered in `config/feeder/price_list_manager/suppliers.csv`
- reviewed in `plans/active/f-price-list-process-manager-v1/SHURE_COSMETICS_EXAMPLE.md`

Current manual-file examples:
- `dhb`
- `bliss_distribution`
- both are registered as `manual_request` / `desktop_csv_folder`
- missing files should display in Manual File Alerts and move down the queue while API-ready suppliers continue

## K. Decisions Deferred
Keep these out of v1 until the simple manager is proven:
- exact dynamic 12-month history cooldown calculation
- full email inbox integration
- real API credentials and supplier-specific API logic
- automatic F061 start
- multi-supplier mixed scanner batches
- value-based learning from later sales outcomes

## L. First Practical Build
The first coding target is a dry test-mode loop:
1. create fake supplier registry
2. create fake converted batch with 10 rows
3. run placeholder scanner
4. update cooldown memory
5. build next recommended action
6. prove counts:
   - source rows = 10
   - converted rows = 10
   - placeholder result rows = 10
   - memory update rows = 10
   - unresolved rows = 0
