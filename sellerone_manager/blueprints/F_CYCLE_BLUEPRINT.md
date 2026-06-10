# F Cycle Manager Blueprint

Last updated: 2026-06-04

## Plain-English Purpose

F is the supplier price-list and new-product screening lane.

In simple terms, suppliers send or expose price lists. F turns those lists into clean rows, decides which rows are worth checking, hands safe rows to the scanner path, collects web/Amazon proof, and then prepares review-ready candidates. It is like a receiving dock: supplier files come in at one side, rows are sorted into clean boxes, and only safe boxes move to scanner/review stations.

The manager's job is not to run the scanner. The manager's job is to know whether the dock is open, blocked, stale, waiting for login, missing proof, or waiting for a real human decision.

## Current Manager-Read State

Current F manager evidence says:

- The live F owner is running.
- No active F scanner blocker is detected by the read-only manager.
- CLF is recommended in the queue and has unprocessed web rows.
- TD Synnex is the live active supplier in the current owner status.
- Storage drift evidence is currently aligned for the checked F live files.
- The independent F MOT is now the front-door evidence source for F, so stale source/queue warnings are visible instead of hidden behind the older manager snapshot.
- ABGee email source and source-intake chain proof currently rely on older imported-batch fallback proof, not a clean fresh Gmail fetch.
- Shure and Stax URL-source proof is readable but old.
- One Entertainment Trading row is parked and must not be published or accepted until Luke makes a real decision or a targeted approved recovery proves it.
- The F manager lane exists in the independent MOT rollup.
- F has many scripts. The high-risk control, recovery, review, and rollout labels are now registered or covered by the manager lane; remaining work is stale/fallback proof refresh, not first setup.

## What F Should Produce

F should produce:

- Supplier intake proof: which supplier files exist, when they arrived, and whether they were imported.
- Universal supplier rows: clean supplier rows with SKU, title, barcode, availability, and cost where possible.
- Scan eligibility proof: which rows are scan-now, skipped, held, or blocked.
- Queue recommendation proof: which supplier should be handled next and why.
- Live scanner owner proof: whether the F owner is running, idle, stale, blocked, or waiting for login.
- Scanner result proof: first-check rows, scrape evidence, screening row state, and speed ledger rows.
- Storage alignment proof: CSV and SQL-compatible row counts agree where F expects mirrored proof.
- Review handoff proof: only AI-gated and review-ready rows move toward operator review or listing preparation.
- Human-decision proof: any row that needs Luke stays parked and traceable.

## Healthy Proof Files

The first F MOT should read these existing proof families without running F061:

- Manager snapshot: `out/systems/M/f_price_list_manager_snapshot.csv`
- Queue dashboard: `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`
- Next-action report: `out/systems/F/price_list_manager/test_mode/next_action_report.md`
- Live owner status: `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- Supervisor state: `out/systems/F/price_list_manager/live/fpm_live_supervisor_state.txt`
- Scanner child status: `out/systems/F/price_list_manager/live/f061_child_status.txt`
- Browser/login state: `out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt`
- Login-mode request state: `out/systems/F/price_list_manager/live/f061_login_mode.requested`
- Storage drift report: `out/systems/F/price_list_manager/live/storage_drift_report.csv`
- Live health/events: `out/systems/F/price_list_manager/live/live_cycle_health.csv` and `out/systems/F/price_list_manager/live/live_cycle_events.csv`
- Scanner live outputs: `out/systems/F/live/f_screening_row_state_live.csv`, `out/systems/F/live/feeder_legacy_first_checks_live.csv`, `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`, and `out/systems/F/live/f_scanner_speed_ledger_live.csv`
- Review handoff proof: `out/systems/F/price_list_manager/live/review_handoff_manifest.csv`
- AI gate proof: `out/systems/F/price_list_manager/live/ai_gate_quality_report.csv`
- Production-line proof: `out/systems/F/price_list_manager/live/production_line_health.csv`
- Parked human-decision proof: `out/systems/F/live/f_login_backtrack_evidence_live.csv`
- Manager script ranking: `out/systems/M/self_organisation/latest_f_manifest_priority_ranking.csv`

## What Failure Looks Like

The F manager should treat these as real failures or decision states:

- Missing dashboard: the manager cannot explain the queue.
- Missing live status: the manager cannot tell whether the live owner is running.
- Stale live owner heartbeat: F may be stuck even if an old file says running.
- Duplicate or unclear owner state: two owners or an unknown owner means unsafe control.
- Storage drift not clear: CSV and SQL-compatible proof disagree, so scanner continuation is unsafe.
- Login required but no script-owned recovery path: the scanner needs the normal F061 child browser path, not a separate workaround.
- Scanner child heartbeat stale while live owner says running: the owner and child evidence disagree.
- Queue recommendation missing or not explainable: the manager cannot say why a supplier is next.
- Manual file needed: this is a real user task only when a supplier file is missing.
- Parked decision row present: the row must stay blocked until Luke decides or approved recovery proves it.
- Review handoff missing or not AI-gated: rows must not move toward operator review or listing.
- Manager manifest coverage missing for important F scripts: the manager cannot safely describe what the script owns.

## F MOT Checks

F is checked by the independent MOT in read-only phases:

1. `f_manager_snapshot_current`
   - Read `out/systems/M/f_price_list_manager_snapshot.csv`.
   - PASS when it exists, has one F row, and status is understandable.
   - WARN when it is stale.
   - FAIL when missing or unreadable.

2. `f_live_owner_status`
   - Read `live_cycle_status.csv` and `fpm_live_supervisor_state.txt`.
   - PASS when the owner state is `running`, `idle`, `completed`, or an expected boundary state, with fresh heartbeat proof.
   - FAIL when live status is missing, stale, or contradicts supervisor state.

3. `f_child_scanner_heartbeat`
   - Read `f061_child_status.txt` only as evidence.
   - PASS when child heartbeat is fresh while owner says running.
   - WARN when child status is absent but owner is idle.
   - FAIL when owner says running but child proof is stale or contradictory.

4. `f_storage_drift_clear`
   - Read `storage_drift_report.csv`.
   - PASS when all required contracts show aligned row counts and `status_after=ok`.
   - FAIL when any required contract shows unsafe drift.

4A. `f_source_intake_chain_proof`
   - Read source acquisition status, import batches, and batch rows.
   - PASS when active supplier sources are classified and ready sources have import proof.
   - WARN when a source failed but usable older import proof is still visible.
   - FAIL when active source proof is missing, unclassified, or failed without usable import proof.

4B. `f_email_price_list_source_proof`
   - Read FPM016 local Gmail proof and FPM011 import row counts.
   - PASS when the active Gmail label, attachment visibility, source file, and imported row counts are current enough.
   - WARN when prior imported ABGee proof exists but the current Gmail fetch failed or is getting old.
   - FAIL when no usable Gmail/import proof exists.
   - This must not fetch Gmail, download attachments, delete Gmail, or delete local files.

4C. `f_url_source_download_proof`
   - Read URL/API source status and prior import proof.
   - PASS when active URL sources are current enough and imported.
   - WARN when readable URL-source proof is getting old.
   - FAIL when active URL source proof is missing or failed without import proof.
   - This must not call supplier URLs or download files from MOT.

5. `f_queue_recommendation_explainable`
   - Read `status_dashboard.csv` and `next_action_report.md`.
   - PASS when the top recommendation has supplier, state, and unprocessed count.
   - WARN when the queue dashboard is stale but still readable.
   - FAIL when missing or empty.

6. `f_login_mode_state`
   - Read `f061_browser_visibility_state.txt` and `f061_login_mode.requested`.
   - PASS when login mode is drained or the browser state is authenticated.
   - DECISION when a visible script-owned login action is required.
   - FAIL when login evidence is stuck or contradicts the owner state.

7. `f_bbp_account_login_state`
   - Read `bbp_login_recovery_proof.csv`.
   - PASS when BBP account login proof is current or the scanner-owned browser reports authenticated BBP evidence.
   - WARN when BBP account proof is missing or not successful.
   - This proof does not prove Seller Central eligibility login.

8. `f_seller_central_eligibility_auth_state`
   - Read `seller_central_login_recovery_proof.csv`.
   - PASS when Seller Central eligibility authorization is proved by current redacted proof.
   - DECISION when credentials, SMS forwarding, code entry, or live proof approval is needed.
   - WARN when proof is missing or stale.
   - FAIL when the proof is failed, expired, or contradictory.

9. `f_parked_decision_rows`
   - Read `f_login_backtrack_evidence_live.csv`.
   - DECISION when the Entertainment Trading unresolved row is still unmerged.
   - PASS only after the row is either proved recovered or explicitly approved as an exception.

10. `f_review_handoff_ai_gate`
   - Read review handoff and AI quality outputs.
   - PASS when review-ready rows are AI-gated.
   - WARN when proof is stale.
   - FAIL when non-gated rows are presented as review-ready.

11. `f_production_line_stage_health`
   - Read `production_line_health.csv`.
   - PASS when stage handoffs balance input rows to passed, blocked, and retry rows.
   - FAIL when a stage claims completion but its manifest or row balance is missing.

12. `f_manager_registration_coverage`
   - Read manager manifests and the F script priority ranking.
   - PASS when top-ranked F manager scripts are registered.
   - WARN when important scripts are only ranked but not registered.
   - FAIL only when missing registration blocks the manager from explaining a live risk.

13. `f_visible_login_control_proof`
   - Read visible-login request and launch-status evidence.
   - PASS when no separate visible-login maintenance request is active.
   - DECISION when a visible-login maintenance request exists.
   - This must not open a separate Chrome login window.

14. `f_queue_handoff_control_proof`
   - Read queue controls, manager decisions, and F061 handoff approvals.
   - PASS when control and approval evidence is readable.
   - DECISION when a safe handoff decision exists but approval proof is missing.
   - This must not edit queue state or approve handoff.

15. `f_recovery_progress_proof`
   - Read recovery progress reconciliation.
   - PASS when pending recovery rows are matched or held.
   - FAIL when recovery rows are unmatched.
   - This must not import or merge recovery rows.

16. `f_review_ai_production_readiness`
   - Read completed review pack, AI gate, incremental AI precheck, production-line, and split-rollout proof.
   - PASS when the proof is visible and no failure is reported.
   - FAIL when readiness proof reports a hard failure.
   - This must not apply AI gates, publish rows, run scanner stages, or enable rollout.

## Manager Script Registration

Already registered in the manager lane:

- `F_price_list_manager`
- `FPM050_build_next_action_report`
- `FPM129_storage_drift_guard`
- `FPM170_supervise_live_cycle`

Already added in the manager lane:

- `FPM010_check_acquisition_sources.py`
- `FPM011_import_ready_sources.py`
- `FPM012_enrich_batch_rows_for_f061.py`
- `FPM013_download_ready_url_sources.py`
- `FPM014_fetch_api_sources.py`
- `FPM015_fetch_google_sheet_sources.py`
- `FPM016_fetch_gmail_email_sources.py`
- `FPM020_run_placeholder_scanner.py`
- `FPM030_update_memory_from_results.py`
- `FPM040_build_next_action.py`
- `FPM050_build_next_action_report.py`
- `FPM060_build_status_dashboard.py`
- `FPM070_stage_f061_handoff.py`
- `FPM080_set_queue_control.py`
- `FPM090_set_f061_handoff_approval.py`
- `FPM100_apply_f061_handoff.py`
- `FPM110_run_test_mode_cycle.py`
- `FPM120_build_f061_live_trial_samples.py`
- `FPM121_apply_f061_live_trial_supplier.py`
- `FPM125_import_f061_recovery_progress.py`
- `FPM126_update_memory_from_f061_results.py`
- `FPM129_storage_drift_guard.py`
- `FPM140_check_review_handoff_ready.py`
- `FPM160_f061_visible_login_maintenance.py`
- `FPM150_build_completed_review_pack.py`
- `FPM155_apply_review_intelligence_gate.py`
- `FPM156_build_ai_gate_quality_report.py`
- `FPM157_build_incremental_ai_precheck.py`
- `FPM158_ai_precheck_common.py`
- `FPM170_supervise_live_cycle.py`
- `FPM180_build_production_line_run.py`
- `FPM190_build_split_rollout_readiness.py`
- `FPM191_backfill_ai_quality_stamps.py`
- `F005_build_supplier_price_list_universal.py`
- `F010_build_feeder_candidate_intake.py`
- `F020_build_feeder_candidate_classification.py`
- `F030_build_shared_feeder_pass_logic.py`
- `F040_build_feeder_candidate_approval_queue.py`
- `F050_build_feeder_po_handoff.py`
- `F060_build_legacy_sheet_review_pack.py`
- `F070_build_backtest_policy_snapshot.py`
- `F062_reset_supplier_test_mode.py`
- `F071_build_backtest_input_view.py`
- `F072_run_backtest_replay.py`
- `F073_build_backtest_summary.py`
- `F074_build_backtest_health.py`
- `F075_apply_backtest_policy_updates.py`
- `F080_build_feedback_calibration_shadow.py`
- `F090_build_amazon_listing_intake.py`
- `F091_reserve_amazon_listing_skus.py`
- `F092_build_amazon_listing_drafts.py`
- `F093_run_amazon_listing_preview.py`
- `F094_submit_amazon_listing_drafts.py`
- `F095_check_amazon_listing_submission_status.py`
- `F096_reconcile_amazon_listing_submissions.py`
- `F097_check_amazon_listing_restrictions.py`
- `F098_build_brand_approval_queue.py`
- `run_F_price_list_manager_cycle.bat`
- `run_F_shure_test_mode_scan_once.bat`
- `run_F_supplier_test_mode_scan_once.bat`
- `run_F_shure_full_legacy_scan.bat`
- `run_F_supplier_full_legacy_scan.bat`

Important: registering a script means adding a manager-readable label. It does not mean running the script, editing the scanner queue, restarting workers, or approving handoff.

## What Creates A Codex Worker Task

Create a manager-approved task packet when:

- a proof file is missing or stale and the root repair is inside manager/reporting scope
- a manager manifest is missing for a top F script
- an F state is real but unclassified
- storage drift proof needs classification or a safe proof plan
- login/handoff proof needs a safe plan but not a live run yet

## What Needs Luke

Luke is needed only for:

- accepting or rejecting the parked Entertainment Trading row
- changing prices
- editing the F061 queue
- writing Google Sheets
- aligning local DB facts
- deleting outputs
- restarting workers
- running a live scanner proof window
- widening this setup beyond F manager control

## Next Safe Setup Step

Use the F MOT and self-organisation reports as the outside control desk. Any remaining F script that appears high in the ranking should be registered or explicitly exempted before F is called fully complete.
