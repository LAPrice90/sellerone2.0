# Feeder Cycle Expectations

## Purpose
The feeder cycle is the new-product intake and qualification system. It converts supplier lists into approved, test-buy-ready candidates that can enter the main loop at Purchase Orders with clean token compatibility.

## SECTION 1 - Completion Definition
| Feature | Description | Status | Notes |
|---|---|---|---|
| Supplier list intake | Supplier files can be ingested with source metadata | In Progress | Active playground is now Shure, DHB, Bliss, Stax, Heo, and Entertainment Trading; ET imported 42,717 rows from the original XLSX with source artifact/hash preserved, then imported old F061 progress so the resume queue is 20,083 rows instead of restarting the full source. TD Synnex OAuth/Gmail zip intake now has real-file proof: 103,543 rows converted, 81,238 base scan-ready, 22,305 missing-cost holds, and 43,636 timeout/memory eligible scan rows. TD remains parked pending controlled live-trial/full-queue decision. |
| Email price-list manager proof | Active Gmail attachment suppliers are manager-proven from local FPM016/FPM011 evidence | In Progress | FPM016 is registered as the first email-price-list proof step. MOT reads local Gmail OAuth presence, label/attachment proof, and import row counts only; it must not download attachments, delete Gmail, delete local files, run F061, or edit queues/prices. |
| Price-list test-mode cycle | Source download/import, placeholder scan, memory update, and dashboard refresh can run as one loop | In Progress | `FPM110_run_test_mode_cycle.py` processed Stax, Heo, Shure, Bliss, and DHB with fake 10-row scanner results; cycle health reconciles expected fake results |
| Price-list queue controls | Operator can pause or prioritise supplier batches before scanner handoff | In Progress | Test-mode `queue_controls.csv` is implemented; Streamlit buttons now write test-mode controls and rebuild the manager view |
| Price-list queue UI | Operator can read queue state in the same style as the rest of the workspace | In Progress | Streamlit price-list queue now uses compact rows, dark dividers, grey headers, inline badges, and row-level controls |
| F061 handoff guard | Manager can prove whether a selected batch is technically ready and explicitly approved | In Progress | Staged preview separates `technical_ready_flag`, `approval_state`, and `live_apply_allowed`; Streamlit can approve/revoke the exact staged batch; guarded apply script defaults to preview-only and requires explicit live flags plus backups before any live write |
| Live price-list manager ownership | BAT and Task Scheduler can own the F manager loop and resume after restart | In Progress | `run_F_price_list_manager_cycle.bat`, `FPM130_run_live_cycle.py`, and task `AMZ Price List Manager` are registered; isolated proof shows ET stages 20,083 rows without live write; 2026-05-07 live proof reloaded FPM at a safe drain boundary, resumed DHB under owner pid `27332`, and wrote binary browser state `browser_state=HIDDEN|auth_state=LOGGED_IN`; 2026-05-20 MOT coverage now includes executable post-restart F evidence at `out/cycle_alerts/f_price_list_post_restart_mot.csv` for orphan `F_restart_drain.ready`, stale supervisor state, and active login-mode requests not handled by a script-owned F061 child; broader controlled live scan proof is still required |
| Scanner-to-review handoff gate | Completed supplier scans can be checked before delivery to New Product Review | In Progress | `FPM140_check_review_handoff_ready.py` writes a read-only readiness status and health row; `FPM150_build_completed_review_pack.py` builds immutable manifests only after readiness passes; FPM130 now calls the builder when a supplier run drains to 0 pending; New Product Review can load completed handoff manifests; F021 now includes completed handoff packs referenced by feedback events, proven on 2026-05-19 with DHB and Entertainment Trading May manual fails matched into triage; live ET proof correctly blocks review delivery while the supplier run is still running; O400 now has an `AI Product Check Gate` page between Price List Queue and New Product Review so the operator can see pending, cleared, user-guidance, rescan, and rejected AI decisions before ordinary review; 2026-05-21 proof added AI rescan promotion ahead of normal rows and forced review-pack/AI-gate rebuild after rescan completion so stale `rescan_needed` rows cannot remain operator-ready; 2026-05-21 Kuriboh proof added page-description capture and F032 quantity confirmation so Amazon description can clear a title-only pack-size warning before New Product Review; 2026-05-21 current-scanner-fail guard proof blocks F037 `LOWROI`/`OVER50K` rows from operator visibility before New Product Review; 2026-05-21 stale-decision archive proof keeps active AI decision files aligned 1:1 with current AI queues; 2026-05-22 Phase 11 proof made FPM155 require FPM156 `fail_checks=0` before a manifest remains operator-ready, and focused regression passed with `114 passed` |
| F scanner production-line split | Scanner evidence is materialized as durable stage handoffs before browser-last routing takes control | In Progress | 2026-05-22 v1 added `FPM180_build_production_line_run.py` with per-run stage folders, completed-manifest handshakes, row reconciliation, and block/retry preservation. `FPM130` now writes production-line snapshots and `production_line_health.csv` after successful chunks while keeping the existing live scanner path unchanged. 2026-05-22 Phase 9 added disabled-default F061 `api_only` and `browser_only` modes plus FPM130 `split_enforced`. 2026-05-22 capped TD Synnex proof passed: API-only checked 10 rows, created 2 `BROWSER_READY` survivors, browser-only loaded the allowlist with 2 selected rows, reused API evidence with 0 repeated endpoint calls, and processed only those 2 routed rows. Normal live owner was restored afterward in `legacy_full`. 2026-05-22 Phase 12 added default-off rollout readiness via `FPM190`, guarded old-manifest quality-stamp backfill via `FPM191`, and final readiness returned `status=ok` with `fail_checks=0`. 2026-05-22 Phase 13 passed a guarded capped split-enforced proof: API-only checked 10 rows, browser-only processed the 2 allowlisted survivors, reused API evidence with 0 endpoint calls, and normal live ownership was restored in `legacy_full`. 2026-05-22 Phase 14 shadow monitoring stayed in normal `legacy_full` while production-line health and storage drift remained clean. 2026-05-22 Phase 15 passed a capped 25-row split proof: API-only checked 25 rows, stopped all rows before browser work, wrote completed routing with 0 browser-input rows, and restored normal `legacy_full` ownership. 2026-05-22 Phase 16 passed a capped 50-row split proof: API-only checked 50 rows, stopped 42 rows before browser work, routed 9 browser survivors through completed `browser_input.csv`, browser-only loaded exactly 9 allowlisted rows, repeated 0 API endpoint calls, and normal `legacy_full` ownership was restored with FPM190 `fail_checks=0` and storage drift at 0 rows. |
| Review pass to Amazon listing draft bridge | New Product Review pass decisions can become product listing profile review rows, stable local SKU reservations, listing drafts, local UI approval, Amazon validation preview, guarded live submit, Amazon read-back reconciliation, brand-approval blocking, and Product DB promotion candidates | In Progress | F090-F098 plus the O400 "Approved For Amazon Listing" lane and `Brand Approval Queue` page are implemented with focused tests. First-page `pass` is lightweight and routes rows to the second Product Listing Profile Review page; the user must complete COO, VAT source/rate and confirmation, purchase pack size, sold pack size, supplier case quantity, order step, MOQ, target margin, tax code, currency, and starting price before Amazon draft/Product DB eligibility. The current 3 checked pass rows were seeded, drafted, previewed, and submitted to Amazon successfully with `3/3` ACCEPTED responses after correcting fulfillment channel to `DEFAULT` and omitting preview-only `includedData` from live submit. Amazon read-back and Listings Restrictions confirmed 2 rows as Product-DB-eligible and blocked 1 Embryolisse row with Amazon brand-approval issue `ERROR 18304` / `APPROVAL_REQUIRED`. The approval queue now stores invoice requirements, fail/park decisions, Seller Central attempts, invoice-upload states, and recheck triggers while excluding approval-blocked rows from Product DB promotion. O430/O431 now build Product DB promotion candidates and dry-run Product DB create-event staging; O431 also blocks live staging when the Product DB destination schema is missing full profile fields. Live proof found Kensington and JVC held for missing Product DB profile fields and the current Product DB destination missing 9 required columns, so no Product DB edit events, Product DB writes, or Google Sheets writes were made. |
| List normalization | Mixed supplier formats are converted to one canonical structure | In Progress | Active playground converts DHB and Bliss Excel files, the Stax keyed CSV feed, the Heo authenticated API, and Entertainment Trading XLSX/EUR costs into manager batch-row format; parked converters are retained for later |
| Barcode and identity validation | Candidate identity and barcode validation state are recorded | In Progress | Supplier converters now hold missing, invalid, and discontinued barcode rows before scan recommendation |
| Viability checks | Candidate viability status and reason codes are produced | In Progress | Baseline output now built in isolated F040 proof |
| Profit and demand checks | Estimated margin/ROI and demand indicators are generated | In Progress | Baseline output now built in isolated F040 proof |
| Test-buy recommendation | Recommended test quantity is output per candidate | In Progress | Baseline output now built in isolated F040 proof |
| Approval queue | Human decision queue supports approve/reject/watch/manual-review | In Progress | Baseline output now built in isolated F040 proof |
| PO handoff package | Approved candidates can be handed off to Purchase Orders | In Progress | Baseline output now built in isolated F050 proof |
| Token-safe handoff checks | Approved candidates meet minimum token-compatibility prerequisites | Not Started | Required before downstream COGS/returns traceability |
| Dropped/discontinued handling | Dropped is recoverable, Discontinued is terminal | Not Started | Waste/output channel behavior |

## SECTION 1A - Storage Retention Guard
- F storage-drift checks must not create full SQLite backups when SQL and CSV contracts are already aligned.
- Full SQLite backup is allowed only immediately before a safe SQL reconcile write.
- `out/backups/f_storage_drift_reconcile_*` keeps the newest 1 non-empty rollback copy by default.
- Empty storage-drift backup folders are cleanup debris and should not accumulate.
- If retention cannot enforce the cap, the feeder manager must block as `blocked_storage_drift` instead of writing more backup data.
- F source intake should store one canonical raw source with source-hash proof instead of repeated raw copies.
- F flow-end cleanup should call registry-backed housekeeping in dry-run-first mode and rely on `out/housekeeping/storage_health.latest.csv` for storage drift proof.

## SECTION 2 - Reliability Measurement
Measure reliability over the last 10 completed feeder runs:
- Fails: ingestion failure, normalization breakage, invalid handoff package, or status-routing corruption.
- Warnings: partial parse, ambiguous identity match, incomplete checklist evidence, or manual-review overflow.
- Clean runs: full intake-to-handoff processing with valid status outputs and no handoff contract defects.

Before runtime exists:
- Reliability Score = `To Baseline`.

Suggested scoring baseline (post-implementation):
- Start at 100.
- Subtract 25 if any fail in window.
- Subtract 10 per warned run, up to 30.
- Subtract 20 if approved candidates fail PO/token handoff contract checks.

## SECTION 3 - Acceptance Criteria
- Replacement Complete:
- Feeder can intake supplier lists, normalize, classify candidates, output test-buy recommendation, and hand approved candidates into Purchase Orders.
- Dropped and Discontinued behavior is implemented with correct lifecycle meaning.
- Stable:
- No fail in last 10 feeder runs.
- At least 8 of last 10 runs are clean.
- No approved candidate fails handoff contract validation.
- Ready for expansion:
- Stable across 2 review windows.
- Extended intelligence checks can be added without breaking baseline outputs.

## SECTION 4 - Improvement Backlog
These do not affect Completion Score:
- Automated brand gating and restriction APIs.
- Advanced barcode-to-listing confidence scoring.
- Rank/rating/seller-count scoring models.
- Adaptive test-buy sizing with feedback learning.
- Multi-supplier dropped-product recovery intelligence.
- Scanner speed production plan: `project_control/F_SCANNER_SPEED_PRODUCTION_PLAN.md` defines the safe route for higher throughput through timing evidence, cooldown skips, official API batching, browser-last staging, and controlled chunk-size rollout.
