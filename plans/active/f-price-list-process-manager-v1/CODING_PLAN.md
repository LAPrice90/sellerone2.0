# Coding Plan

Date: 2026-04-30
Scope: F price-list process manager, upstream of F061, test-mode first.

## Current implementation addendum - 2026-05-22 ABGee daily email queue activation

Active phase:
- Reactivate ABGee as a daily Gmail attachment supplier and keep the latest imported stock feed available to the price-list scanner queue.

Goal:
- Use the latest available ABGee Gmail price attachment as the source file.
- Preserve the ABGee pack rule at the converter stage: `PK12` means 12 individual units, so pack cost is divided into scanner `unit_cost`.
- Add ABGee to the normal manager queue without overwriting the current TD Synnex live F061 run.

Allowed files:
- `config/feeder/price_list_manager/suppliers.csv`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- Read and rebuild existing F price-list manager artifacts under `out/systems/F/price_list_manager/test_mode/`

Not allowed:
- No Google Sheets writes.
- No local DB alignment changes.
- No manual overwrite of live F061 active-run files.
- No forced stop or restart of the current FPM130 owner.
- No A/B/E/H flow runs.

Tests and isolated proof:
- Compile the ABGee converter plus Gmail/import manager modules.
- Run the ABGee converter and Gmail/import regression tests.
- Rebuild the test-mode manager queue artifacts and confirm ABGee appears with scanner-eligible rows.

Live monitoring target:
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/inbox/supplier_price_list_active_run.csv`
- `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`

Success threshold:
- ABGee registry row has `active_flag=1`.
- Latest ABGee batch remains imported with source rows, valid rows, held rows, and scanner-eligible rows reconciled.
- ABGee appears in the manager dashboard/queue.
- Current live TD Synnex run remains owned by FPM130 and is not overwritten.

Backup:
- Pre-change snapshot: `project_control/backups/abgee_queue_activation_20260522T135312Z`.
- CLF source-fix snapshot: `project_control/backups/clf_title_source_fix_20260522T140433Z`.

Proof update:
- Code fix applied: yes.
- Isolated verification passed:
  - `python -m py_compile scripts\flows\F\suppliers\abgee.py scripts\flows\F\suppliers\clf.py scripts\flows\F\price_list_manager\FPM011_import_ready_sources.py scripts\flows\F\price_list_manager\FPM040_build_next_action.py scripts\flows\F\price_list_manager\timeout_queue.py`
  - Focused pytest passed: `17 passed`.
  - Wider focused pytest passed: `39 passed` for ABGee converter, CLF converter, Gmail fetch/import, ready-source import, next-action scoring, and timeout queue coverage.
- Gmail proof:
  - ABGee Gmail fetch found latest available attachment from label `ABGee`.
  - Attachment message timestamp: `2026-05-21T14:47:06Z`.
  - Attachment bytes: `551602`.
  - Attachment SHA1: `fa74c131f665f434c93bf220df9ea93a270df0a8`.
  - Duplicate refetch was archived instead of creating a second ABGee batch.
- ABGee import proof:
  - Source rows: `8745`.
  - Converter-valid rows: `5770`.
  - Held rows: `2975`.
  - Scanner-eligible rows after memory checks: `5307`.
  - Scanner-selected ABGee rows missing title: `0`.
  - Real ABGee pack rows with pack size above 1: `1317`.
- Queue proof:
  - Dashboard rows rebuilt: `8`.
  - ABGee dashboard state: `Ready`, queue state `Queued`, control state `Normal`.
  - Current recommended supplier remains `CLF` because CLF has an existing `Prioritised #1` queue control.
  - Latest next-action report built at `2026-05-22T14:22:57Z`.
  - Latest F061 required-field check passed with `before_missing_title=0`, `after_missing_title=0`, `before_missing_vat=0`, and `after_missing_vat=0`.
  - Current live F061 run remains TD Synnex and was not overwritten.
- CLF blocker correction:
  - Root cause: CLF API fetch dropped the product description before conversion.
  - Fix: CLF API fetch now writes `Title`, converter maps it to `supplier_title`, and rows still missing a title are held instead of scanner-ready.
  - Refreshed CLF batch imported `16528` source rows, `16246` valid rows, `282` held rows, and `16230` scanner-eligible rows.
  - Old titleless CLF batch is `superseded`; superseded batch rows are explicit `superseded_batch` skips.
  - Scanner-selected rows missing title across the rebuilt manager queue: `0`.

Verification status:
- Code fix applied: yes.
- Isolated verification passed: yes.
- Live loop verification: not forced. FPM130 is already running TD Synnex, so ABGee remains queued until the normal manager boundary selects it.
- Latest live ownership check: FPM130 running TD Synnex with `43931` pending rows at `2026-05-22T14:17:14Z`.

## Current implementation addendum - 2026-05-07 DHB operator-intent correction

Active phase:
- Correct live queue after operator clarified that DHB should be scanned deliberately, not skipped by prior memory.

Problem:
- Operator intended the DHB file from `C:\Users\Luke\Desktop\SellerOne Price Files\DHB\inbox` to be scanned.
- Earlier handling moved that file into the configured DHB processed folder and treated the identical file hash as no new scan work.
- FPM130 then moved on to Stax after DHB memory filtering showed `0` manager-selected rows.

Corrective intent:
- Pause FPM130 at a safe chunk boundary.
- Preserve the current Stax active run before changing live F061 contracts.
- Start a deliberate DHB scan from the imported DHB batch rows, bypassing the manager memory skip for this operator-requested run.

Allowed files:
- `out/systems/F/price_list_manager/live/f061_visible_login.requested`
- `out/systems/F/price_list_manager/live/F_restart_drain.ready`
- `out/systems/F/inbox/supplier_price_list_active_run.csv`
- `out/systems/F/inbox/supplier_price_list_run_state.csv`
- `out/systems/F/price_list_manager/test_mode/batch_rows.csv`
- `out/systems/F/price_list_manager/test_mode/manual_backups/`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`

Not allowed:
- No Google Sheets writes.
- No local DB alignment changes.
- No mid-chunk process kill.
- No A/B/E/H flow runs.

Success threshold:
- Stax active run is backed up before replacement.
- DHB active run is written with scanner-valid rows from the imported DHB batch.
- FPM130 restarts and active supplier is `dhb`.
- Live status shows scanner running or successful chunk completion for DHB.

Result:
- Updated UTC: 2026-05-07T08:37:13Z
- Root cause: I let the manager's automatic memory-filtered result override the operator intent. DHB was filtered to zero manager-selected rows, so FPM130 resumed Stax as the next active queue.
- Corrective action:
  - Stax was drained at a safe FPM130 boundary with `23,835` pending rows preserved.
  - Stax backup written at `out/systems/F/price_list_manager/test_mode/manual_backups/dhb_operator_contract_switch_20260507T083136Z/`.
  - DHB active run was written through `write_f_contract_df` so SQL-primary and CSV-export state match.
  - DHB run id: `fpm_dhb_operator_20260507T083136Z`.
  - DHB source file: `C:\Users\Luke\Desktop\Amazon price files\DHB\Processed\Trade Price May 2026_20260506T131752Z_c4b2b32cee_duplicate.xlsx`.
  - DHB scanner-valid rows queued: `788`.
- Live proof:
  - FPM130 restarted with active supplier `dhb`.
  - F061 child started with `supplier_id=dhb`.
  - Live chunks completed for DHB.
  - Run state moved from `pending_rows=788`, `done_rows=0` to `pending_rows=768`, `done_rows=20`.
- Verification status: live loop verification confirmed for DHB scanner start.
- Next move: no further action needed now; normal FPM130 ownership continues the DHB scan.

Login maintenance update:
- Updated UTC: 2026-05-07T09:04:02Z
- Trigger: DHB live scan showed repeated BBP evidence problems:
  - `Dashboard yes/no ignored non yes/no value => LOGIN`
  - `No BBP iframe`
  - `bbp_dashboard_yes_or_no` blank on affected scrape rows
- Root cause status: visible-login maintenance exists, but the live scanner did not automatically trigger it from these BBP evidence failures.
- Action taken:
  - Requested F061 visible-login maintenance.
  - FPM130 reached safe drain boundary.
  - Live state: `drain_wait`.
  - Pending rows at pause: `708`.
  - Visible browser launched for login, pid `22064`.
- User task trigger: user logs into Amazon/BBP in the visible browser and confirms able-to-sell YES/NO is visible.
- Next verifier after user confirmation:
  - run `python scripts/flows/F/price_list_manager/FPM160_f061_visible_login_maintenance.py clear --json`
  - confirm FPM130 resumes DHB
  - confirm a later DHB scrape row has `bbp_dashboard_yes_or_no` as `YES` or `NO`
- If verifier fails:
  - keep scanner paused
  - inspect Chrome profile mismatch and BBP iframe detection before resuming

## Current implementation addendum - 2026-05-07 DHB pass-memory queue correction

Active phase:
- Fix DHB live queue selection so prior `PASS` memory is not presented as new scan work.

Goal:
- Explain why DHB showed only 13 scan rows.
- Correct the earliest queue-decision step that selected already-passed rows.
- Rebuild manager artifacts and restart FPM130 from a clean boundary.

Root-cause evidence:
- DHB source rows: `959`.
- DHB converter-valid rows: `788`.
- Current manager scan decision rows: `13`.
- The `13` selected rows all have existing exact `supplier_offer` memory with `last_result_status=PASS`.
- The remaining scanner-valid rows are mostly recent fail/rescan memory under timeout policy, with `755` rows marked `timeout_active`.
- The uploaded May DHB workbook is content-identical to the previously imported DHB workbook by hash `c4b2b32cee41ae7f5252c600ffa524e4cca952db`.

Allowed files:
- `scripts/flows/F/price_list_manager/timeout_queue.py`
- `tests/test_fpm040_build_next_action.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- Read and rebuild existing F price-list manager artifacts under `out/systems/F/price_list_manager/`

Not allowed:
- No Google Sheets writes.
- No local DB alignment changes.
- No manual overwrite of live F061 contracts except through the guarded FPM130/FPM100 path.
- No A/B/E/H flow runs.

Tests and isolated proof:
- Add focused test coverage proving exact prior `PASS` supplier-offer memory is skipped.
- Run `pytest tests/test_fpm040_build_next_action.py -q`.
- Rebuild manager artifacts with the FPM scripts, then check DHB scan/skip counts.

Live monitoring target:
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/price_list_manager/live/live_cycle.lock`
- `out/systems/F/price_list_manager/live/f061_child_status.txt`
- `out/systems/F/price_list_manager/test_mode/batch_scan_eligibility.csv`
- `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`

Poll cadence:
- First check after code/test/rebuild.
- Then every 5 minutes while restart proof is still active.
- Stop after 60 minutes if no clean owner state is reached.

Success threshold:
- DHB exact prior-pass rows are skipped with an explicit decision reason.
- DHB manager scan rows no longer equal the old `13` prior-pass rows.
- FPM130 is running or cleanly idle with truthful status after restart.
- No partial manual live queue write is used as proof.

Timeout rule:
- If FPM130 cannot reach a clean boundary or restart within the window, park the phase with exact evidence and the next artifact to inspect.

Proof update:
- Code fix applied: yes.
- Isolated verification passed:
  - `python -m py_compile scripts\flows\F\price_list_manager\timeout_queue.py scripts\flows\F\price_list_manager\FPM040_build_next_action.py tests\test_fpm040_build_next_action.py` passed.
  - `pytest tests\test_fpm040_build_next_action.py -q` passed: `9 passed`.
  - Pytest emitted the known Windows temp cleanup permission warning after the passing result.
- Rebuild proof:
  - `FPM040_build_next_action.py` completed on live manager artifacts in `15.227` seconds after lookup caching.
  - Rebuilt `FPM050_build_next_action_report.py`, `FPM070_stage_f061_handoff.py`, and `FPM060_build_status_dashboard.py`.
  - DHB eligibility after rebuild: total `959`, scan `0`, skip `959`.
  - DHB skip reasons after rebuild: `timeout_active=755`, `missing_unit_cost=65`, `missing_barcode=54`, `invalid_barcode_format=52`, `already_processed_in_placeholder_results=20`, `already_passed_in_memory=13`.
- Live restart proof:
  - F-specific reload marker created and FPM130 exited at a chunk boundary with `state=drain_exit`.
  - Old owner pid `10004` and old child pid `26840` were no longer alive before restart.
  - Reload marker and drain-ready marker were cleared by `FPM160_f061_visible_login_maintenance.py clear`.
  - `AMZ Price List Manager` was started.
  - New FPM130 owner pid `4268` started and resumed the old DHB active run.
  - Old DHB active run drained to `pending_rows=0` with `last_action_status=success`.
  - Patched manager did not reselect DHB.
  - FPM130 applied and started Stax run `fpm_stax_20260507T065226Z`.
  - Latest live status after restart: `running`, active supplier `stax`, pending rows `24200`, `last_action=resume_f061_active_run`, `last_action_status=scanner_running`.
- Live verification status: confirmed for DHB queue correction and FPM130 restart.

## Current implementation addendum - 2026-05-06 DHB duplicate-file queue override

Active phase:
- Operational DHB queue override while FPM130 is still scanning Entertainment Trading.

Goal:
- Use the operator-uploaded `Trade Price May 2026.xlsx` as the current DHB source instead of showing the older January filename.
- Put DHB next in the price-list manager queue without overwriting live F061 while Entertainment Trading is still pending.

Findings:
- The uploaded May DHB workbook was first found in `C:\Users\Luke\Desktop\SellerOne Price Files\DHB\inbox`.
- The active DHB manager registry watches `C:\Users\Luke\Desktop\Amazon price files\DHB\Inbox`.
- The May workbook hash matched the existing DHB imported workbook hash: `c4b2b32cee41ae7f5252c600ffa524e4cca952db`.
- Because the file was an exact duplicate by content, `FPM011_import_ready_sources.py` correctly archived it as a duplicate and did not create a second batch.

Changes:
- Moved the May workbook through the configured DHB inbox and into `C:\Users\Luke\Desktop\Amazon price files\DHB\Processed`.
- Updated the existing DHB batch metadata to point at the May processed file and use source date `2026-05-05T14:48:28Z`.
- Cleared the old Entertainment Trading queue control and set DHB to `prioritised` rank `1`.
- Updated `FPM040_build_next_action.py` so future `superseded` batches are ignored by next-action scoring.

Proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM040_build_next_action.py tests\test_fpm040_build_next_action.py` passed.
- `pytest tests\test_fpm040_build_next_action.py -q` passed: `8 passed`.
- Rebuilt manager artifacts:
  - `FPM010_check_acquisition_sources.py --skip-remote-check`
  - `FPM012_enrich_batch_rows_for_f061.py`
  - `FPM040_build_next_action.py`
  - `FPM050_build_next_action_report.py`
  - `FPM070_stage_f061_handoff.py`
  - `FPM060_build_status_dashboard.py`
- Latest manager decision:
  - supplier `dhb`
  - batch `dhb_source_20260430T121200Z_c4b2b32cee41`
  - reason `operator_prioritised_supplier`
  - estimated scan rows `768`
  - safe handoff flag `0`
- Dashboard:
  - DHB queue position `1`
  - queue state `Recommended`
  - control state `Prioritised #1`
  - price list date `2026-05-05T14:48:28Z`
- Handoff preview:
  - staged DHB rows `768`
  - approval state `approved`
  - approved by `FPM130_live_cycle`
  - live apply allowed `0` only because F061 is still busy
  - block reason `f061_not_idle:pending_active=1838;running_state=1;pending_state=1838`
- UI simplification after operator feedback:
  - removed the visible `F061 Handoff Guard` panel from the Streamlit price-list queue page
  - removed the handoff guard panel from the static dashboard HTML
  - normal automatic waiting is now represented by the queue row only, not by a blocked/error-looking guard
  - internal handoff preview files still exist for safety and proof, but they are no longer surfaced as routine operator UI
- Additional proof:
  - `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\F\price_list_manager\FPM070_stage_f061_handoff.py scripts\flows\F\price_list_manager\FPM090_set_f061_handoff_approval.py` passed.
  - `pytest tests\test_o_ui_operator_view.py::test_price_list_handoff_approval_helper_records_exact_batch_and_rebuilds_preview tests\test_fpm070_stage_f061_handoff.py::test_fpm070_matching_approval_allows_guard_readiness_without_live_write -q` passed: `2 passed`.
  - `pytest tests\test_fpm060_build_status_dashboard.py -q` passed: `6 passed`.

Live status:
- FPM130 is still running Entertainment Trading and must finish the active pending rows before live DHB handoff.
- No live F061 active-run files were overwritten manually.
- When the active Entertainment Trading run reaches zero pending rows, the existing live manager selection path should refresh outputs, see DHB as the prioritised next decision, auto-approve the exact selected batch, and apply DHB at that safe boundary.

Backup:
- Pre-change manager CSV backup:
  - `out/systems/F/price_list_manager/test_mode/manual_backups/dhb_override_20260506T131747Z`

Next verifier:
- Wait for Entertainment Trading pending rows to reach `0`, then confirm FPM130 applies DHB as the next active supplier and starts scanning `fpm_dhb_*`.

## Current implementation addendum - 2026-05-01 visible F061 login maintenance

Active phase:
- Phase 25 - controlled visible-login maintenance for F061 scanner profiles.

Goal:
- Let the operator log back into Amazon/BBP without killing a scanner chunk or losing F run state.
- Pause only the F price-list scanner at a chunk boundary.
- Open a visible Chrome window using the same BBP/Amazon profile that F061 uses.
- Resume FPM130 after the operator confirms the browser login is complete.

Allowed runtime actions:
- Create `out/systems/F/price_list_manager/live/f061_visible_login.requested`.
- Wait for `out/systems/F/price_list_manager/live/F_restart_drain.ready`.
- Stop only the small `f_hide_scraper_windows.ps1` helper before opening the visible login window.
- Open visible Chrome using `C:\Chrome_UC136\bin\chrome.exe` and the configured `F061_BBP_USER_DATA_DIR` / `F061_BBP_PROFILE_DIR`.
- Clear `f061_visible_login.requested` and `F_restart_drain.ready` after the user has completed login.

Not allowed in this phase:
- No Google Sheets writes.
- No active F061 CSV edits.
- No process kill against FPM130 or F061 scanner children.
- No B, H, A, or E flow runs.

Tests and isolated proof:
- `pytest tests/test_fpm160_visible_login_maintenance.py -q` passed, 5 tests.
- `pytest tests/test_fpm130_live_cycle.py -q` passed, 8 tests.
- Pytest emitted a Windows temp-folder cleanup warning after completion, but the test results were passing.

Monitoring target:
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/price_list_manager/live/f061_child_status.txt`
- `out/systems/F/price_list_manager/live/F_restart_drain.ready`
- `out/systems/F/price_list_manager/live/f061_visible_login.requested`

Success threshold:
- FPM130 reaches `drain_wait` with `last_action=restart_drain`.
- No active F061 child is running.
- Visible Chrome opens and stays accessible to the operator.
- After clear, FPM130 resumes scanning and pending rows continue decreasing.

Phase 25 live status:
- Code fix applied: yes.
- Isolated verification passed: yes.
- Live maintenance requested at `2026-05-01T13:55:25Z`.
- Current owner needed the legacy global marker because it was already running with old in-memory code.
- `drain_wait` reached with `pending_rows=18183`.
- Last child pid `27532` was no longer alive before opening Chrome.
- Visible Chrome launched with pid `24708`.
- Old window-hider helper pids `132,9268` were stopped before launch.
- Operator reported BBP missing in the first visible window.
- Root cause: visible helper opened `Profile 2`; the first replacement `BBPProfile` was also not the operator's BBP profile.
- Second visible Chrome launched with `--profile-directory=BBPProfile`, pid `28664`.
- Manifest search found `BuyBotPro - Amazon FBA Deal Analyzer` in `C:\Users\Luke\AppData\Local\Chrome_UC136v2\BBPProfile1`.
- Third visible Chrome launched with `C:\Chrome_UC136v2\bin\chrome.exe --user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136v2 --profile-directory=BBPProfile1`.
- Helper defaults changed to `Chrome_UC136v2` and `F061_VISIBLE_LOGIN_PROFILE_DIR=BBPProfile1`.
- Operator asked to abandon visible-login attempt and run the normal script.
- Maintenance cleared after operator request:
  - `f061_visible_login.requested` removed
  - legacy global `maintenance.requested` removed
  - `F_restart_drain.ready` removed
- FPM130 resumed normal scanning:
  - live state `running`
  - `last_action_status=scanner_running`
  - new F061 child pid `6332`
  - child started `2026-05-01T14:07:35Z`
  - heartbeat observed `2026-05-01T14:08:55Z`
- Normal path proof completed:
  - F061 child pid `6332` finished with `rc=0` at `2026-05-01T14:10:35Z`
  - processed rows `5`
  - pending rows moved from `18183` to `18178`
  - `scanner_speed_browser_blocked_rows=0`
  - FPM130 immediately started next normal child pid `17420` at `2026-05-01T14:10:55Z`
  - `scanner_chunk` event status `success`
  - `f061_memory_import` event status `success`
- Visible-login helper profile choice is not proven for operator use; normal scanner path is the active route.

Phase 25B - ongoing visible scanner windows:
- Operator issue: normal F061 windows are still placed offscreen, so future login expiry cannot be fixed manually.
- Root cause:
  - current FPM130 owner was already running old code
  - old child env uses `F061_BACKGROUND_BROWSER_MODE=minimized`
  - F061 adds `--window-position=-32000,-32000`
- Code change applied for future owner reloads:
  - FPM130 child env now defaults `F061_BACKGROUND_BROWSER_MODE=visible`
  - FPM130 child env now defaults `F061_SHOW_WINDOWS=1`
  - FPM130 child env now defaults `FPM_LIVE_HIDE_SCRAPER_WINDOWS=0`
  - FPM130 no longer starts the hide helper by default
- Runtime bridge applied for current already-running owner:
  - added `scripts/tools/f_show_scraper_windows.ps1`
  - started visible-window helper pid `22968`
  - helper restores/moves scanner Chrome windows onscreen every second
  - hider script now stands down when the show helper is running
- Proof:
  - `pytest tests/test_fpm130_live_cycle.py -q` passed, 8 tests
  - `pytest tests/test_f061_run_legacy_first_checks_local.py -q` passed, 29 tests
  - scanner Chromium windows observed with main window handles:
    - pid `22652`, Amazon product page
    - pid `28376`, New Tab
  - live FPM130 state remained `running`
  - live child pid `22716` heartbeat observed at `2026-05-01T14:18:29Z`

Phase 25C - adaptive auth-attention browser mode:
- Operator idea accepted: do not pause overnight scans for login expiry; instead let the scanner keep running and make the next browser visible when an auth/browser block is detected.
- Plain-English behavior:
  - normal logged-in batches run offscreen/minimized
  - if a batch records `scanner_speed_browser_blocked_rows > 0`, FPM130 writes a `f061_auth_attention` event
  - the next child sees that event and starts visible
  - the operator can log in whenever they notice the visible browser
  - after a later clean child records processed rows with `scanner_speed_browser_blocked_rows=0`, FPM130 writes `f061_auth_attention` status `cleared`
  - after clear, future children return to minimized/offscreen
- Implementation:
  - auth state is stored in existing `live_cycle_events.csv`, not a new output file
  - no product rows are edited just to manage auth state
  - no Google Sheets writes
  - no scan pause is introduced
- Files changed:
  - `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
  - `tests/test_fpm130_live_cycle.py`
- Tests:
  - `pytest tests/test_fpm130_live_cycle.py -q` passed, 10 tests
  - `pytest tests/test_f061_run_legacy_first_checks_local.py -q` passed, 29 tests
- Live status:
  - code fix applied: yes
  - isolated verification passed: yes
  - live owner reload: confirmed
  - old owner pid `25688` exited itself at drain boundary with `drain_exit`
  - reload marker cleared before restart
  - new owner pid `16888` started from scheduled task
  - first post-reload child pid `19440` finished successfully
  - pending rows moved from `18153` to `18148`
  - `scanner_speed_browser_blocked_rows=0`
  - post-reload `scanner_chunk` event status `success`
  - post-reload `f061_memory_import` event status `success`
  - next child pid `9620` started at `2026-05-01T14:35:43Z`
  - live adaptive auth trigger: armed, but no real auth block observed yet
- Next verifier for the visible-on-auth branch:
  - next real chunk with `scanner_speed_browser_blocked_rows > 0`, or an approved controlled auth-block simulation.

Phase 25D - recovery row queue bump:
- Operator question: rows that need new information, such as RESCAN rows or rows affected by missing login-derived fields, should be bumped up once they are eligible again.
- Current truth:
  - live scanner is healthy:
    - child pid `24596`
    - heartbeat `2026-05-01T14:43:54Z`
    - pending rows `18138`
    - recent chunks show `scanner_speed_browser_blocked_rows=0`
    - recent `scanner_chunk` and `f061_memory_import` events are `success`
  - retry control is timeout-policy based, not a hard attempt-count cap.
  - `RESCAN` timeout is currently 30 days in `config/feeder/f_scanner_timeout_policy.csv`.
  - technical/browser auth evidence uses `scanner_speed_browser_blocked_rows`; current live status is logged in/healthy because that value is `0`.
- Implementation:
  - `FPM040_build_next_action.py` now gives eligible recovery rows an extra score boost.
  - recovery rows are currently rows with scan decisions caused by:
    - `timeout_expired_or_missing`
    - `cost_changed_reset`
    - `source_changed_reset`
    - `policy_disabled`
  - when recovery rows win the batch choice, decision reason is `recovery_rows_prioritised_after_timeout`.
- Files changed:
  - `scripts/flows/F/price_list_manager/FPM040_build_next_action.py`
  - `tests/test_fpm040_build_next_action.py`
- Tests:
  - `pytest tests/test_fpm040_build_next_action.py -q` passed, 7 tests
  - `pytest tests/test_fpm130_live_cycle.py -q` passed, 10 tests
- Live status:
  - code fix applied: yes
  - isolated verification passed: yes
  - live queue-selection verification: not yet reached
  - reason: current Entertainment Trading active run still has many pending rows, so FPM130 will not select the next supplier batch yet.
  - new scoring will matter at the next `build_next_action` / next-batch selection boundary.

## Current implementation addendum - 2026-05-01 timeout queue integration phase 4

Active phase:
- Phase 24D - safe FPM130 owner reload and live memory-import proof.

Goal:
- Reload the F price-list manager owner so the already-tested `f061_memory_import` hook is active in the live loop.
- Use the existing maintenance boundary, not a mid-child interruption.
- Prove the next successful F061 child chunk writes manager timeout memory.

Allowed runtime actions:
- Create `out/locks/maintenance.requested`.
- Wait for `out/systems/F/price_list_manager/live/F_restart_drain.ready`.
- Stop the FPM130 owner only after the drain-ready boundary is observed.
- Restart `AMZ Price List Manager`.
- Clear maintenance request only after the old owner is stopped.
- Read live F manager artifacts for proof.

Not allowed in this phase:
- No Google Sheets writes.
- No live F061 active-run pruning.
- No manual edits to active F061 CSVs.
- No B, H, A, or E flow runs.
- No forced kill while `last_action_status=scanner_running`.

Monitoring target:
- `out/systems/F/price_list_manager/live/live_cycle.lock`
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/price_list_manager/live/live_cycle_events.csv`
- `out/systems/F/price_list_manager/live/F_restart_drain.ready`
- `out/systems/F/price_list_manager/test_mode/barcode_scan_memory.csv`

Poll cadence:
- Check for drain-ready every 30 seconds for up to 10 minutes.
- After restart, check live events every 60 seconds for up to 10 minutes.

Success threshold:
- old owner reaches `drain_wait` or `F_restart_drain.ready`
- old owner is stopped only at that boundary
- new FPM130 owner starts
- next successful `scanner_chunk` is followed by `f061_memory_import`
- `barcode_scan_memory.csv` last write is after the reload
- pending rows continue decreasing from the same Entertainment Trading run

Phase 24D result:
- Reload attempted but blocked by Windows process permissions.
- Safe boundary proof:
  - maintenance requested at `2026-05-01T11:01:46Z`
  - `F_restart_drain.ready` observed at `2026-05-01T11:02:19Z`
  - owner pid `24560` was in `drain_wait`
  - child pid from `f061_child_status.txt` was not alive
  - pending rows had moved to `18403`
- Stop attempt result:
  - `Stop-Process -Id 24560 -Force` failed with `Access is denied`
  - `schtasks /End /TN "AMZ Price List Manager"` reported success, but detached python owner pid `24560` stayed alive
  - `taskkill /PID 24560 /T /F` failed with `Access is denied`
  - temporary elevated scheduled-task helper could not be registered: `Access is denied`
- Safety restoration:
  - maintenance request was cleared
  - stale `F_restart_drain.ready` was cleared
  - existing owner resumed the same Entertainment Trading run
  - follow-up `scanner_chunk` at `2026-05-01T11:07:03Z` succeeded with `rows=5`, `pending_after=18393`
- Live memory-import proof was not achieved:
  - no `f061_memory_import` event appeared
  - `barcode_scan_memory.csv` last write remained `2026-04-30T12:45:32Z`
- No Google Sheets writes were made.
- No live F061 active-run rows were edited or pruned.

Phase 24D status:
- code fix applied: already yes from phases 24A-24C
- isolated verification passed: already yes
- live owner reload: blocked by Windows permission
- live memory-import verification: not yet proven
- live scanner continuity: restored; existing owner is running and pending rows are still decreasing

Verification status: Parked pending elevated FPM130 owner restart
Changed at: 2026-05-01T10:54:10Z
Latest live check at: 2026-05-01T11:12:36Z
Next verifier: restart `AMZ Price List Manager` from an elevated Windows session or wait for the next normal machine restart, then check the next successful chunk for `f061_memory_import` in `out/systems/F/price_list_manager/live/live_cycle_events.csv`

## Current implementation addendum - 2026-05-01 FPM130 graceful reload fix

Active phase:
- Phase 24E - remove ongoing dependency on admin process kill.

Reason:
- `AMZ Price List Manager` already runs with `RunLevel=HighestAvailable`.
- The failure was not that future starts lack admin rights.
- The failure was that the elevated detached Python owner could not be killed from this non-elevated Codex session.

Code change:
- `FPM130_run_live_cycle.py` now supports a maintenance reload request.
- If `out/locks/maintenance.requested` contains `exit_after_drain=1` or `action=reload`, FPM130:
  - waits until the current child chunk is finished
  - writes `F_restart_drain.ready`
  - writes status `drain_exit`
  - exits its own loop cleanly
  - releases `live_cycle.lock`
- After that, `Start-ScheduledTask -TaskName "AMZ Price List Manager"` can start a fresh elevated owner without killing the old process.

Proof:
- Compile passed:
  - `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py tests\test_fpm130_live_cycle.py`
- Focused pytest passed:
  - `8 passed`
- Broader touched-manager pytest passed:
  - `58 passed`
- Added test proving a reload maintenance request returns `drain_exit`, leaves active F061 rows untouched, writes `F_restart_drain.ready`, and releases `live_cycle.lock`.

Important limitation:
- The currently running owner pid `24560` was loaded before this change, so it cannot understand `exit_after_drain=1` yet.
- This graceful reload path becomes available after one admin/manual/normal restart loads the new FPM130 code.

Phase 24E status:
- code fix applied: yes
- isolated verification passed: yes
- live loop verification: pending one owner restart to load the new graceful reload code

Verification status: Isolated proof passed; live reload self-exit available after next FPM130 owner restart
Changed at: 2026-05-01T11:45:15Z
Latest health snapshot at: not used because this phase used F manager isolated proof, not A015
Next verifier: after the next FPM130 owner restart, request reload with `exit_after_drain=1`, then confirm `drain_exit`, lock release, scheduled task restart, and `f061_memory_import`

Phase 24E live result:
- Admin restart worked at `2026-05-01T11:53:23Z`:
  - old owner pid `24560` stopped
  - scheduled task restart succeeded
  - new owner pid `20456` started and resumed the same Entertainment Trading run
- First live memory-import hook fired:
  - chunk at `2026-05-01T11:53:25Z`
  - pending moved to `18333`
  - `f061_memory_import` event appeared
  - memory file grew to `1894` unique keys
- Status correction applied after live proof showed a false `blocked` event:
  - root cause: `FPM126_update_memory_from_f061_results.py` used cumulative historical `health_fail_rows` to decide the current import status
  - fix: current import status now uses only the current F061 memory-import health rows
  - historical health failures remain visible but no longer make a successful current import look blocked
- Proof after status correction:
  - compile passed
  - focused pytest passed: `8 passed`
  - broader touched-manager pytest passed: `58 passed`
- Graceful reload proof after status correction:
  - maintenance request with `exit_after_drain=1` at `2026-05-01T11:58:01Z`
  - FPM130 exited itself at `drain_exit` at `2026-05-01T12:00:56Z`
  - `live_cycle.lock` was released
  - scheduled task restarted a fresh owner pid `25688` at `2026-05-01T12:01:28Z`
- Final live proof:
  - `scanner_chunk` at `2026-05-01T12:01:28Z`: `success`, `rows=5`, `pending_after=18323`
  - `f061_memory_import` at `2026-05-01T12:01:28Z`: `success`, `rows=1833`, `processed_rows=1790`, `memory_rows=1904`
  - latest F061 memory health rows are all `ok`
  - `barcode_scan_memory.csv`: `1904` rows, `1904` unique keys, last write `2026-05-01T12:04:30Z`
  - current FPM130 owner is running pid `25688`, same Entertainment Trading run, pending `18323`
- No Google Sheets writes were made.
- No live F061 active-run rows were manually edited or pruned.

Phase 24E final status:
- code fix applied: yes
- isolated verification passed: yes
- graceful owner reload confirmed: yes
- live memory-import verification confirmed: yes
- live scanner continuity confirmed: yes

Verification status: Live FPM130 timeout-memory import confirmed
Changed at: 2026-05-01T12:05:02Z
Latest live proof at: 2026-05-01T12:04:41Z
Next verifier: next manager batch-selection boundary should use the updated `barcode_scan_memory.csv` to skip active-timeout barcodes before F061 staging

## Current implementation addendum - 2026-05-01 timeout queue integration phase 3

Active phase:
- Phase 24C - import finalized live F061 screening results into manager timeout memory.

Goal:
- After each successful F061 child chunk, convert finalized `f_screening_row_state_live.csv` pass/timeout evidence into `barcode_scan_memory.csv`.
- Keep the update at the child-chunk boundary only, not mid-scan.
- Let future manager queue builds skip newly failed timed-out barcodes.

Allowed files for this addendum:
- `scripts/flows/F/price_list_manager/FPM126_update_memory_from_f061_results.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `tests/test_fpm126_update_memory_from_f061_results.py`
- `tests/test_fpm130_live_cycle.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`

Not allowed in this phase:
- No Google Sheets writes.
- No live F061 active-run pruning.
- No scheduler or lock changes.
- No scraper behavior changes.
- No API timing or chunk-size changes.
- No reading half-written F061 outputs mid-child-run.

Tests and isolated proof:
- Unit proof that live screening pass/timeout rows become unique memory rows.
- Unit proof that product-level fails use global barcode memory.
- Unit proof that cost-sensitive fails use supplier-offer memory with unit cost.
- FPM130 proof that memory import runs only after a fake scanner child succeeds.

Live monitoring target:
- None during implementation. This phase wires the boundary hook but does not force a live F061 child run.

Success threshold:
- compile touched modules
- focused FPM126/FPM130 tests pass
- broader touched manager tests pass
- no Google Sheets writes

Phase 24C result:
- Code fix applied: yes.
- Added live-result memory importer:
  - `scripts/flows/F/price_list_manager/FPM126_update_memory_from_f061_results.py`
- `FPM130_run_live_cycle.py` now calls the importer after a successful F061 child chunk, both when resuming an existing active run and when applying/scanning the next manager batch.
- Memory import is filtered by supplier and run id at the child-chunk boundary.
- Product-level failures write `global_barcode` memory keys.
- Cost-sensitive failures write `supplier_offer` memory keys with the manager unit cost.
- PASS rows write memory that can clear old global or supplier-offer fail memory when newer evidence exists.
- Current active F061 run was not pruned or rewritten.
- No Google Sheets writes were made.

Proof:
- Compile passed:
  - `python -m py_compile scripts\flows\F\price_list_manager\FPM126_update_memory_from_f061_results.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\price_list_manager\timeout_queue.py scripts\flows\F\price_list_manager\FPM011_import_ready_sources.py scripts\flows\F\price_list_manager\FPM012_enrich_batch_rows_for_f061.py scripts\flows\F\price_list_manager\FPM040_build_next_action.py`
- Focused pytest passed:
  - `23 passed`
- Broader touched-manager pytest passed:
  - `57 passed`
- Added live-memory tests proving:
  - finalized F061 screening rows become unique memory rows
  - `PRICEHISTORYFAIL` becomes a global barcode timeout memory row
  - `ROIFAIL` becomes a supplier-offer memory row with unit cost
  - FPM130 imports memory only after a successful fake scanner chunk
- Read-only live check after the isolated proof:
  - current FPM130 owner pid `24560` is still running the already-loaded live loop
  - latest observed chunk event at `2026-05-01T10:51:45Z` was `success`, `rows=5`, `pending_after=18413`
  - no `f061_memory_import` event has appeared yet
  - `barcode_scan_memory.csv` last write remains `2026-04-30T12:45:32Z`
- Pytest printed a Windows temp cleanup `PermissionError` after the pass summaries; pytest had already emitted pass counts and returned exit code `0`.

Phase 24C status:
- code fix applied: yes
- isolated verification passed: yes
- live loop verification: not confirmed yet because the current live FPM130 owner is already loaded and has not emitted the new memory-import event

Verification status: Isolated proof passed; live chunk-boundary proof pending FPM130 owner reload
Changed at: 2026-05-01T10:54:10Z
Latest health snapshot at: not used because this phase used F manager isolated proof, not A015
Next verifier: safe FPM130 owner reload at a child-chunk boundary, then check the next successful chunk for `f061_memory_import` in `out/systems/F/price_list_manager/live/live_cycle_events.csv` and a fresh write to `out/systems/F/price_list_manager/test_mode/barcode_scan_memory.csv`

## Current implementation addendum - 2026-05-01 timeout queue integration phase 2

Active phase:
- Phase 24B - apply timeout queue immediately after import and enrichment.

Goal:
- When a supplier price file is loaded or enriched, immediately build the filtered scanner eligibility queue.
- Keep full `batch_rows.csv` intact for audit and future comparison.
- Update batch counts so the manager can see eligible vs skipped-timeout rows before FPM040 chooses the next action.

Allowed files for this addendum:
- `scripts/flows/F/price_list_manager/timeout_queue.py`
- `scripts/flows/F/price_list_manager/FPM011_import_ready_sources.py`
- `scripts/flows/F/price_list_manager/FPM012_enrich_batch_rows_for_f061.py`
- relevant focused tests
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`

Not allowed in this phase:
- No Google Sheets writes.
- No live F061 active-run pruning.
- No scheduler or lock changes.
- No scraper behavior changes.
- No API timing or chunk-size changes.

Tests and isolated proof:
- Import proof that a newly loaded supplier file writes `batch_scan_eligibility.csv`.
- Import proof that active-timeout rows are counted as skipped and not eligible.
- Enrichment proof that the timeout queue can be refreshed again without changing full batch rows.

Live monitoring target:
- None for this phase. This changes manager-owned artifacts only and does not rewrite the current active F061 run.

Success threshold:
- focused import/enrichment timeout queue tests pass
- broader touched manager tests pass
- no Google Sheets writes

Phase 24B result:
- Code fix applied: yes.
- `FPM011_import_ready_sources.py` now refreshes `batch_scan_eligibility.csv` immediately after importing a ready supplier source.
- `FPM012_enrich_batch_rows_for_f061.py` now refreshes timeout eligibility before checking F061-required fields and again after enrichment writes.
- Full `batch_rows.csv` remains intact. Timed-out barcodes are removed from scan eligibility, not deleted from the supplier batch.
- `price_list_batches.csv` now receives refreshed `eligible_row_count`, `skipped_cooldown_row_count`, `new_row_count`, and `changed_row_count` from the timeout queue helper.
- Current active F061 run was not pruned or rewritten.
- No Google Sheets writes were made.

Proof:
- Compile passed:
  - `python -m py_compile scripts\flows\F\price_list_manager\timeout_queue.py scripts\flows\F\price_list_manager\FPM011_import_ready_sources.py scripts\flows\F\price_list_manager\FPM012_enrich_batch_rows_for_f061.py scripts\flows\F\price_list_manager\FPM040_build_next_action.py`
- Focused pytest passed:
  - `16 passed`
- Broader touched-manager pytest passed:
  - `50 passed`
- Added import/enrichment tests proving:
  - a newly imported supplier file writes `batch_scan_eligibility.csv`
  - active timeout memory skips the barcode before scanner selection
  - skipped timeout rows do not block F061 required-field enrichment
  - full supplier rows remain present for audit and future comparison
- Pytest printed a Windows temp cleanup `PermissionError` after the pass summaries; pytest had already emitted pass counts and returned exit code `0`.

Phase 24B status:
- code fix applied: yes
- isolated verification passed: yes
- live loop verification: not applied to the current active F061 run because this phase does not rewrite active scanner rows

Verification status: Isolated proof passed
Changed at: 2026-05-01T10:48:28Z
Latest health snapshot at: not used because this phase used F manager isolated proof, not A015
Next verifier: next manager-owned real supplier import/enrichment cycle, then check `out/systems/F/price_list_manager/test_mode/batch_scan_eligibility.csv` and `price_list_batches.csv` counts

## Current implementation addendum - 2026-05-01 timeout queue integration phase 1

Active phase:
- Phase 24A - shared timeout queue helper and FPM040 wiring.

Goal:
- Build one reusable manager-owned timeout queue decision helper.
- Keep full supplier batch rows for audit.
- Exclude active-timeout rows from scanner eligibility before F061 staging.
- Do not prune or rewrite the currently active F061 run.

Allowed files for this addendum:
- `scripts/flows/F/price_list_manager/timeout_queue.py`
- `scripts/flows/F/price_list_manager/FPM040_build_next_action.py`
- `tests/test_timeout_queue.py`
- `tests/test_fpm040_build_next_action.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`

Not allowed in this phase:
- No Google Sheets writes.
- No live F061 active-run pruning.
- No scheduler or lock changes.
- No scraper behavior changes.
- No API timing or chunk-size changes.
- No import/enrichment automatic filtering yet.

Tests and isolated proof:
- Helper tests proving global barcode timeout blocks another supplier.
- Helper tests proving supplier-offer timeout resets on changed cost.
- Helper tests proving expired timeout re-enters the queue.
- FPM040 regression tests proving selected scan counts and skip reasons still work through the helper.

Live monitoring target:
- None for this phase. This is isolated helper wiring and does not change the active F061 run already in progress.

Success threshold:
- focused timeout queue and FPM040 tests pass
- broader touched manager tests pass
- no Google Sheets writes

Phase 24A result:
- Code fix applied: yes.
- Added shared helper:
  - `scripts/flows/F/price_list_manager/timeout_queue.py`
- FPM040 now builds `batch_scan_eligibility.csv` through the shared helper instead of carrying its own private timeout decision implementation.
- Full supplier batch rows remain unchanged; active-timeout rows are excluded only from scan eligibility.
- Current active F061 run was not pruned or rewritten.

Proof:
- Compile passed:
  - `python -m py_compile scripts\flows\F\price_list_manager\timeout_queue.py scripts\flows\F\price_list_manager\FPM040_build_next_action.py`
- Focused pytest passed:
  - `9 passed`
- Broader touched-manager pytest passed:
  - `32 passed`
- Added helper tests proving:
  - global barcode timeout blocks the same barcode for another supplier
  - supplier-offer timeout resets when cost changes
  - expired timeout re-enters the scan queue

Phase 24A status:
- code fix applied: yes
- isolated verification passed: yes
- live loop verification: not applicable for this phase because active-run pruning and live F061 result-memory import were not changed

Verification status: Isolated proof passed
Changed at: 2026-05-01T10:42:46Z
Latest health snapshot at: not used because this phase is isolated manager helper proof
Next verifier: Phase 24B post-import/post-enrichment filtering proof

## Current implementation addendum - 2026-05-01 scanner timeout policy phase 4

Active phase:
- Phase 23D - balanced timeout policy and explicit price-history fail code.

Reason for correction:
- User correctly challenged phase 23C as too harsh.
- `RESCAN` was overloaded. It included true technical retry conditions and `NO_PRICE_HISTORY_365D`, which should not share the same timeout.
- 90 days is now the standard commercial wait; 180 days is the higher end for slow-moving evidence; 365 days is reserved for hazmat or FBA eligibility.

Balanced v3 timeout policy values:
- `NOASIN`: `fixed_days`, `90`
- `OVER50K`: `fixed_days`, `90`
- `HAZMATFAIL`: `fixed_days`, `365`
- `NOCOST`: `until_cost_changes`, max `90`, cost reset enabled
- `ROIFAIL`: `until_cost_changes`, max `90`, cost reset enabled
- `LOWROI`: `until_cost_changes`, max `60`, cost reset enabled
- `BRANDFAIL`: `fixed_days`, `180`
- `NODATE`: `fixed_days`, `90`
- `REVIEWFAIL`: `fixed_days`, `90`
- `SCRAPEFAIL`: `fixed_days`, `30`
- `LOWSALESFAIL`: `fixed_days`, `90`
- `SELLERHISTORYFAIL`: `fixed_days`, `180`
- `PRICEHISTORYFAIL`: `fixed_days`, `180`
- `RESCAN`: `fixed_days`, `30`
- `FAIL`: `fixed_days`, `90`

Allowed files for this addendum:
- `config/feeder/f_scanner_timeout_policy.csv`
- `scripts/flows/F/f_scanner_timeout_policy.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/price_list_manager/FPM020_run_placeholder_scanner.py`
- `tests/test_f_scanner_timeout_policy.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_fpm020_placeholder_scanner.py`
- `tests/test_fpm030_update_memory_from_results.py`
- `tests/test_fpm040_build_next_action.py`
- `project_control/F_SCANNER_TIMEOUT_POLICY_SPEC.md`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `plans/active/f-price-list-process-manager-v1/PLAN.md`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`

Not allowed in this phase:
- No Google Sheets writes.
- No scanner scrape behavior changes.
- No API timing or chunk-size changes.
- No manual local DB or sheet alignment changes.

Tests and isolated proof:
- Compile touched modules.
- Focused timeout-policy tests proving balanced defaults and `PRICEHISTORYFAIL`.
- F061 mapping test proving `NO_PRICE_HISTORY_365D` maps to `PRICEHISTORYFAIL`.
- Placeholder and manager tests proving test-mode memory and skip decisions use the balanced values.

Live monitoring target:
- `out/systems/F/live/f_screening_row_state_live.csv`
- `out/systems/F/live/feeder_legacy_sheet_health.csv`
- `out/systems/F/price_list_manager/test_mode/batch_scan_eligibility.csv`

Success threshold:
- static policy CSV parses cleanly with `15` rows
- policy health rows remain `ok`
- focused tests pass
- next live F061 chunk after the change writes balanced timeout dates

Phase 23D result:
- Code fix applied: yes.
- `PRICEHISTORYFAIL` added as an explicit fail code for `NO_PRICE_HISTORY_365D`.
- `RESCAN` is now reserved for technical retry rows:
  - catalog `http_429`
  - request exception
  - HTTP 5xx
  - `CHROMEVERSIONFAIL`
  - `REVIEWS_TIMEOUT`
  - `INCOMPLETE_PRICE_HISTORY_CAPTURE`
  - `SCRAPE_DISABLED`
- Balanced v3 values written to `config/feeder/f_scanner_timeout_policy.csv`.
- Placeholder scanner cooldowns updated to the balanced values.
- Guidebook, spec, and active manager plan updated.

Proof:
- Static policy CSV parse proof:
  - rows: `15`
  - columns: `10`
  - `PRICEHISTORYFAIL=180`
  - `RESCAN=30`
  - `HAZMATFAIL=365`
- Compile passed:
  - `python -m py_compile scripts\flows\F\f_scanner_timeout_policy.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\price_list_manager\FPM020_run_placeholder_scanner.py scripts\flows\F\price_list_manager\FPM030_update_memory_from_results.py scripts\flows\F\price_list_manager\FPM040_build_next_action.py`
- Focused pytest passed:
  - `42 passed`
- Broad manager and UI regression pytest passed:
  - `80 passed`
- Live F061 balanced-timeout proof:
  - balanced config changed at `2026-05-01T10:20:44Z`
  - next completed F manager scanner chunk: `2026-05-01T10:21:34Z`, `success`, `5`, `pending_after=18453`
  - policy health rows at `2026-05-01T10:21:36Z`: all `ok`, known codes value `15`
  - live row-state at `2026-05-01T10:21:36Z` wrote:
    - `ROIFAIL` timeout `2026-07-30T10:21:36Z`
    - `LOWSALESFAIL` timeout `2026-07-30T10:21:36Z`
    - `FAIL` timeout `2026-07-30T10:21:36Z`

Phase 23D status:
- code fix applied: yes
- isolated verification passed: yes
- live F061 timeout verification confirmed: yes
- live price-list manager skip-decision verification: still parked pending next batch-selection boundary because the manager is continuing the active Entertainment Trading scan

Verification status: F061 live verification confirmed; manager skip proof parked pending next batch-selection boundary
Changed at: 2026-05-01T10:20:44Z
Latest F policy health snapshot at: 2026-05-01T10:21:36Z
Next verifier: wait until current Entertainment Trading F061 active run reaches a manager batch-selection boundary, then check `out/systems/F/price_list_manager/test_mode/batch_scan_eligibility.csv` for balanced policy skip reasons

## Current implementation addendum - 2026-05-01 scanner timeout policy phase 3

Active phase:
- Phase 23C - strict scan-capacity timeout correction.

Status:
- Superseded by phase 23D balanced policy after user review.

Reason for correction:
- User rejected the softer values because short cooldowns are pointless when a full supplier-file pass can take months.
- The policy now protects scan capacity by keeping unchanged failed barcodes out long enough for new barcodes to get priority.

Approved strict v2 timeout policy values:
- `NOASIN`: `fixed_days`, `180`
- `OVER50K`: `fixed_days`, `180`
- `HAZMATFAIL`: `fixed_days`, `365`
- `NOCOST`: `until_cost_changes`, max `180`, cost reset enabled
- `ROIFAIL`: `until_cost_changes`, max `180`, cost reset enabled
- `LOWROI`: `until_cost_changes`, max `120`, cost reset enabled
- `BRANDFAIL`: `fixed_days`, `365`
- `NODATE`: `fixed_days`, `180`
- `REVIEWFAIL`: `fixed_days`, `180`
- `SCRAPEFAIL`: `fixed_days`, `120`
- `LOWSALESFAIL`: `fixed_days`, `180`
- `SELLERHISTORYFAIL`: `fixed_days`, `365`
- `RESCAN`: `fixed_days`, `120`
- `FAIL`: `fixed_days`, `180`

Allowed files for this addendum:
- `config/feeder/f_scanner_timeout_policy.csv`
- `scripts/flows/F/f_scanner_timeout_policy.py`
- `scripts/flows/F/price_list_manager/FPM020_run_placeholder_scanner.py`
- `tests/test_f_scanner_timeout_policy.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_fpm020_placeholder_scanner.py`
- `tests/test_fpm030_update_memory_from_results.py`
- `tests/test_fpm040_build_next_action.py`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `plans/active/f-price-list-process-manager-v1/PLAN.md`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`

Not allowed in this phase:
- No Google Sheets writes.
- No scraper behavior changes.
- No API timing or chunk-size changes.
- No manual local DB or sheet alignment changes.

Tests and isolated proof:
- Compile touched modules.
- Focused timeout-policy tests proving stricter defaults.
- F061 test proving stricter timeout dates are written.
- Placeholder and manager tests proving test-mode memory and skip decisions use the stricter values.

Live monitoring target:
- `out/systems/F/live/f_screening_row_state_live.csv`
- `out/systems/F/price_list_manager/test_mode/batch_scan_eligibility.csv`
- `out/systems/F/live/feeder_legacy_sheet_health.csv`

Success threshold:
- static policy CSV parses cleanly
- strict default values are loaded by reset/default helpers
- F061 and manager tests pass with strict dates
- no timeout policy health WARN or FAIL appears from malformed config

Phase 23C result:
- Code fix applied: yes.
- Strict v2 values written to `config/feeder/f_scanner_timeout_policy.csv`.
- Default/reset helper values updated in `scripts/flows/F/f_scanner_timeout_policy.py`.
- Placeholder scanner cooldowns updated so test-mode memory no longer writes the old weak values.
- Guidebook and active manager plan updated to explain the scan-capacity reason for harsher cooldowns.

Proof:
- Static policy CSV parse proof:
  - rows: `14`
  - columns: `10`
  - strict values parsed as expected
- Compile passed:
  - `python -m py_compile scripts\flows\F\f_scanner_timeout_policy.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\price_list_manager\FPM020_run_placeholder_scanner.py scripts\flows\F\price_list_manager\FPM030_update_memory_from_results.py scripts\flows\F\price_list_manager\FPM040_build_next_action.py`
- Focused pytest passed:
  - `42 passed`
- Broad manager and UI regression pytest passed:
  - `80 passed`
- Live F061 strict-timeout proof:
  - strict config changed at `2026-05-01T10:04:42Z`
  - next completed F manager scanner chunk: `2026-05-01T10:07:27Z`, `success`, `5`, `pending_after=18473`
  - policy health rows at `2026-05-01T10:07:29Z`: all `ok`
  - live row-state at `2026-05-01T10:07:29Z` wrote:
    - `LOWROI` timeout `2026-08-29T10:07:29Z`
    - `ROIFAIL` timeout `2026-10-28T10:07:29Z`
    - `LOWSALESFAIL` timeout `2026-10-28T10:07:29Z`

Phase 23C status:
- code fix applied: yes
- isolated verification passed: yes
- live F061 timeout verification confirmed: yes
- live price-list manager skip-decision verification: still parked pending next batch-selection boundary because the manager is continuing the active Entertainment Trading scan

Verification status: F061 live verification confirmed; manager skip proof parked pending next batch-selection boundary
Changed at: 2026-05-01T10:04:42Z
Latest F policy health snapshot at: 2026-05-01T10:07:29Z
Next verifier: wait until current Entertainment Trading F061 active run reaches a manager batch-selection boundary, then check `out/systems/F/price_list_manager/test_mode/batch_scan_eligibility.csv` for strict policy skip reasons

## Current implementation addendum - 2026-05-01 scanner timeout policy phase 1

Active phase:
- Phase 23A - operator-editable scanner timeout policy, read-only/default mode.

Goal:
- Create the F-owned timeout policy file for F061 fail reasons.
- Add policy validation and health rows.
- Add Streamlit settings in the existing Price List Queue page.
- Keep live scanner timeout/skip behavior unchanged until timeout values are approved.

Allowed files for this addendum:
- `config/feeder/f_scanner_timeout_policy.csv`
- `scripts/flows/F/f_scanner_timeout_policy.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_f_scanner_timeout_policy.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_o_ui_operator_view.py`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`

Not allowed in this phase:
- No Google Sheets changes.
- No live F061 queue writes outside normal scanner behavior.
- No scanner scrape behavior changes.
- No API timing, rate-limit, chunk-size, or queue-priority changes.
- No manager skip-decision wiring yet.

Tests and isolated proof:
- Focused timeout-policy tests for default creation/read, code coverage, fallback WARN, fixed-day calculation, cost/source reset behavior, manual-review blocking, and health rows.
- Focused F061 test proving health reports policy state while current timeout calculation remains unchanged.
- Focused O UI test proving save writes only `config/feeder/f_scanner_timeout_policy.csv`.

Live monitoring target:
- None for phase 23A. This is a read-only/default policy surface and does not alter live scanner decisions.

Success threshold:
- policy file exists with exactly one row for each known F061 fail/retry code
- focused pytest passes
- F061 health includes scanner timeout policy rows
- Streamlit helper can load/edit/save the policy
- no Google Sheets writes
- live skip decisions remain not wired to the new values

Automatic next step:
- Prepare recommended timeout values for user approval, then wire policy into F061 timeout calculation and price-list manager skip decisions in a separate phase.

Phase 23A result:
- Code fix applied: yes.
- Policy file added:
  - `config/feeder/f_scanner_timeout_policy.csv`
  - rows: `14`
  - default basis: current legacy hardcoded timeout minutes represented as fractional days
- Policy helper added:
  - `scripts/flows/F/f_scanner_timeout_policy.py`
  - default create/read/write
  - fallback to `FAIL` for unknown fail codes
  - fixed-day timeout calculation
  - cost/source reset decision helper
  - manual-review automatic-rescan block helper
  - health row builder
- F061 integration:
  - added timeout-policy health rows to `feeder_legacy_sheet_health`
  - did not wire edited policy values into live timeout calculation
- Streamlit integration:
  - added `Scanner Timeout Settings` expander to the existing Price List Queue page
  - save writes only `config/feeder/f_scanner_timeout_policy.csv`
  - reset restores current legacy defaults
- Guidebook updated with phase status and policy path.

Proof:
- `python -m py_compile scripts\flows\F\f_scanner_timeout_policy.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\O\O400_operator_ui.py` passed.
- Focused proof passed: `10 passed`.
- F061 plus policy proof passed: `33 passed`.
- Operator UI proof passed: `51 passed`.
- Manager cooldown regression proof passed: `5 passed`.
- Policy health shape proof:
  - policy rows: `14`
  - health rows: `6`
  - health statuses: `6 ok`
  - known fail/retry codes covered: `14`
- Pytest printed a Windows temp cleanup `PermissionError` after the pass summaries; the pass counts were already emitted and exit code was `0`.

Phase 23A status:
- code fix applied: yes
- isolated verification passed: yes
- live loop verification: not applicable yet because this phase intentionally does not change live scanner decisions

Verification status: Isolated proof passed
Changed at: 2026-05-01T09:42:40Z
Latest health snapshot at: not used for phase 23A because this is F-scoped isolated proof
Next verifier: user-approved phase 23B to wire timeout policy into F061 timeout calculation and price-list manager skip decisions

## Current implementation addendum - 2026-05-01 scanner timeout policy phase 2

Active phase:
- Phase 23B - wire approved timeout policy into F061 and price-list manager skip decisions.

User approval:
- User replied `proceed` after the phase 23A recommendation list.

Superseded phase 23B timeout policy values:
- These softer values were replaced by phase 23C after user feedback that short cooldowns do not protect scan capacity across multi-month supplier-file passes.
- `NOASIN`: `fixed_days`, `60`
- `OVER50K`: `fixed_days`, `45`
- `HAZMATFAIL`: `fixed_days`, `180`
- `NOCOST`: `until_cost_changes`, max `30`, cost reset enabled
- `ROIFAIL`: `until_cost_changes`, max `60`, cost reset enabled
- `LOWROI`: `until_cost_changes`, max `45`, cost reset enabled
- `BRANDFAIL`: `fixed_days`, `180`
- `NODATE`: `fixed_days`, `60`
- `REVIEWFAIL`: `fixed_days`, `60`
- `SCRAPEFAIL`: `fixed_days`, `3`
- `LOWSALESFAIL`: `fixed_days`, `60`
- `SELLERHISTORYFAIL`: `fixed_days`, `120`
- `RESCAN`: `fixed_days`, `3`
- `FAIL`: `fixed_days`, `30`

Allowed files for this addendum:
- `config/feeder/f_scanner_timeout_policy.csv`
- `scripts/flows/F/f_scanner_timeout_policy.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/price_list_manager/FPM040_build_next_action.py`
- `tests/test_f_scanner_timeout_policy.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_fpm040_build_next_action.py`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`

Not allowed in this phase:
- No Google Sheets writes.
- No scraper behavior changes.
- No API timing or chunk-size changes.
- No manual local DB or sheet alignment changes.

Tests and isolated proof:
- Focused policy tests for approved values.
- F061 test proving `timeout_until_utc` uses approved policy values.
- Manager tests proving cost-change reset bypasses cooldown and manual-review policy blocks automatic rescan.

Live monitoring target:
- `out/systems/F/live/f_screening_row_state_live.csv`
- `out/systems/F/price_list_manager/test_mode/batch_scan_eligibility.csv`
- `out/systems/F/live/feeder_legacy_sheet_health.csv`

Success threshold:
- F061 writes policy-based `timeout_until_utc`.
- Manager skip decisions apply fixed-day expiry, cost/source reset, disabled policy, fallback, and manual-review blocking.
- Existing cooldown behavior remains covered by regression tests.

Phase 23B result:
- Code fix applied: yes.
- Approved timeout values written to `config/feeder/f_scanner_timeout_policy.csv`.
- F061 now calculates `timeout_until_utc` from the policy file.
- Price-list manager `FPM040_build_next_action.py` now re-evaluates memory rows against the policy instead of blindly trusting stored cooldown dates:
  - fixed-day timeout active rows skip
  - cost-change reset rows scan
  - source-change reset helper is available
  - disabled policies scan
  - manual-review policies block automatic rescan
  - unknown fail codes fall back to `FAIL`
- Root-cause correction during live validation:
  - the static policy CSV initially contained unquoted commas in notes
  - live F061 failed several chunks with a pandas CSV parse error
  - the policy file was fixed at source by removing comma characters from static notes
  - the file now parses cleanly with `14` rows and `10` columns

Proof:
- Compile passed:
  - `python -m py_compile scripts\flows\F\f_scanner_timeout_policy.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\price_list_manager\FPM040_build_next_action.py scripts\flows\O\O400_operator_ui.py`
- Focused phase 23B pytest passed:
  - `15 passed`
- Broad touched-surface pytest passed:
  - policy/F061/O UI: `85 passed`
  - FPM030/FPM040/FPM050/FPM060/FPM070/FPM080/FPM110: `23 passed`
- Static policy CSV parse proof:
  - rows: `14`
  - columns: `10`
  - approved values parsed as expected
- Live F061 recovery proof:
  - failed chunks occurred from `2026-05-01T09:45:14Z` through `2026-05-01T09:50:51Z` due to the malformed policy CSV
  - after the CSV fix, F manager ran a successful chunk at `2026-05-01T09:51:12Z`
  - pending rows dropped from `18,503` to `18,498`
  - F policy health rows at `2026-05-01T09:51:13Z`: `6 ok`, `0 warn`, `0 fail`
  - recent live `ROIFAIL` and `LOWSALESFAIL` rows wrote `timeout_until_utc=2026-06-30T09:51:13Z`, proving the approved 60 day policy replaced the old 12 hour timeout

Phase 23B status:
- code fix applied: yes
- isolated verification passed: yes
- live F061 timeout verification confirmed: yes
- live price-list manager skip-decision verification: not yet proven because the live manager is currently resuming the existing Entertainment Trading active scan, not selecting a new batch

Verification status: F061 live verification confirmed; manager skip proof parked pending next batch-selection boundary
Changed at: 2026-05-01T09:56:32Z
Latest health snapshot at: F policy health rows observed at 2026-05-01T09:51:13Z
Next verifier: wait until current Entertainment Trading F061 active run reaches a manager batch-selection boundary, then check `out/systems/F/price_list_manager/test_mode/batch_scan_eligibility.csv` for policy reasons such as `timeout_active`, `cost_changed_reset`, or `manual_review_required`

## Current implementation addendum - 2026-04-30 Shure example seed

Active phase:
- Phase 1 preparation: first supplier registry example.

Allowed files for this addendum:
- `config/feeder/price_list_manager/suppliers.csv`
- `plans/active/f-price-list-process-manager-v1/SHURE_COSMETICS_EXAMPLE.md`
- `plans/active/f-price-list-process-manager-v1/PLAN.md`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`

Implementation:
- Shure Cosmetics is registered as the first process-manager supplier example.
- The manager source classification is `api_pull` with `csv_link` subtype.
- The existing source is `https://aux.shure-cosmetics.co.uk/pricelist/`.
- The existing converter is `scripts/flows/F/suppliers/shure_cosmetics.py`.
- Live F061 handoff remains disabled.

Verification:
- Source HEAD check returned status `200` and content type `text/csv;charset=UTF-8`.
- Direct converter fixture check returned `valid_rows=2` and `hold_rows=0`.
- Process-manager supplier registry CSV parsed with `1` data row and `14` columns.
- ASCII check returned no matches.
- F005 was not run because it resets live F scanner workspace files.

Follow-up:
- Add manager barcode validity health so short digit-only leftovers like `123` are held before scanner handoff.

## Current implementation addendum - 2026-04-30 status dashboard preview

Active phase:
- UI preview for process-manager progress visibility.

Allowed files for this addendum:
- `scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py`
- `scripts/flows/F/price_list_manager/_schemas.py`
- `tests/test_fpm060_build_status_dashboard.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`

Implementation:
- Added a read-only test-mode dashboard builder.
- The dashboard follows the old working page shape:
  - Queue
  - Manual File Alerts
  - Bot Status
  - Web Scraper
  - Second Checks
- Shure Cosmetics sits at the top of the queue as the active CSV-link test item.
- DHB and Bliss Distribution are registered as monthly email-request examples with Desktop drop folders.
- Missing manual files move down the queue and appear in Manual File Alerts so API pulls can continue.
- It writes:
  - `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`
  - `out/systems/F/price_list_manager/test_mode/status_dashboard.html`
- It does not write F061 inbox or live scanner files.

Verification:
- Compile passed for `FPM060_build_status_dashboard.py`, `tests/test_fpm060_build_status_dashboard.py`, and updated schemas.
- Focused tests passed: `pytest tests\test_fpm001_build_test_fixtures.py tests\test_fpm060_build_status_dashboard.py -q` returned `4 passed`.
- Earlier preview build passed with dashboard rows `3`, web unprocessed total `10`, and HTML output at `out/systems/F/price_list_manager/test_mode/status_dashboard.html`.
- Dashboard row proof:
  - Shure Cosmetics: queue position `1`, method `CSV link`, file state `Ready`, queue state `Active`
  - Bliss Distribution: file state `Missing`, queue state `Needs Manual File`
  - DHB: file state `Missing`, queue state `Needs Manual File`
- ASCII check returned no matches.

## Current implementation addendum - 2026-04-30 Streamlit UI integration

Active phase:
- Read-only UI integration for the price-list queue.

Allowed files for this addendum:
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`

Implementation:
- Added `Price List Queue` to the existing Streamlit operator UI navigation.
- Added UI loader for `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`.
- Added queue summary metrics, manual-file alerts, queue rows, method, source location, file state, and read-only pause/prioritise buttons.
- Controls remain disabled until a safe command writer exists.

Verification:
- Compile passed for `scripts\flows\O\O400_operator_ui.py` and `tests\test_o_ui_operator_view.py`.
- Focused tests passed: `pytest tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_fpm001_build_test_fixtures.py tests\test_fpm060_build_status_dashboard.py -q` returned `5 passed`.
- Existing Streamlit server responded at `http://localhost:8501/?page=price_list_queue` with HTTP `200`.
- Dashboard data was refreshed with Shure active and DHB/Bliss missing manual files.

## Current implementation addendum - 2026-04-30 placeholder scanner and memory proof

Active phase:
- Phase 2 placeholder scanner and memory update.

Allowed files for this addendum:
- `scripts/flows/F/price_list_manager/_schemas.py`
- `scripts/flows/F/price_list_manager/FPM020_run_placeholder_scanner.py`
- `scripts/flows/F/price_list_manager/FPM030_update_memory_from_results.py`
- `scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py`
- `tests/test_fpm020_placeholder_scanner.py`
- `tests/test_fpm030_update_memory_from_results.py`
- `tests/test_fpm060_build_status_dashboard.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`

Implementation:
- Added a placeholder scanner that takes the 10 Shure test rows and produces 10 controlled scanner-style outcomes.
- Added a memory update step that stores cooldown memory from those outcomes.
- Updated the dashboard builder so the UI now shows processed result counts when placeholder results exist.
- The manager remains test-mode only and does not hand anything to live F061.

Verification:
- Focused tests passed: `pytest tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_fpm001_build_test_fixtures.py tests\test_fpm020_placeholder_scanner.py tests\test_fpm030_update_memory_from_results.py tests\test_fpm060_build_status_dashboard.py -q` returned `7 passed`.
- Real test-mode sequence passed:
  - fixture rows: source `10`, valid `10`, eligible `10`, health fail rows `0`
  - placeholder scanner rows: result `10`, pass `1`, fail `8`, rescan `1`
  - memory rows: result `10`, memory `10`, unresolved `0`, health fail rows `0`
  - dashboard rows: `3`, web unprocessed total `0`
- Existing Streamlit UI responded at `http://localhost:8501/?page=price_list_queue` with HTTP `200`.
- Current dashboard proof:
  - Shure Cosmetics: queue position `1`, method `CSV link`, file state `Ready`, queue state `Active`, unprocessed `0`, pass `1`, fail `8`, rescan `1`
  - Bliss Distribution: file state `Missing`, queue state `Needs Manual File`
  - DHB: file state `Missing`, queue state `Needs Manual File`

## Current implementation addendum - 2026-04-30 starter supplier queue

Active phase:
- Phase 3 preparation: starter supplier acquisition registry.

Allowed files for this addendum:
- `config/feeder/price_list_manager/suppliers.csv`
- `scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py`
- `tests/test_fpm060_build_status_dashboard.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`

Implementation:
- Added the 12 starter suppliers to the process-manager registry:
  - Bliss Distribution: email request
  - Stax: API
  - Rashmian: website link
  - TD Synnex: daily email
  - DHB: email request
  - Shure Cosmetics: CSV link
  - CLF: API
  - Heo: API
  - ABGee: daily email
  - We Stock Lots: CSV link
  - Tropicana Wholesale: daily email
  - Entertainment Trading: email request
- Updated dashboard method labels to match operator wording: `Email request`, `API`, `Website link`, `Daily email`, and `CSV link`.
- Unknown CSV-link source details now show as `Config Needed` with action `Add source details`.

Verification:
- Supplier registry parsed with `12` rows and `15` columns.
- Focused tests passed: `pytest tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_fpm001_build_test_fixtures.py tests\test_fpm020_placeholder_scanner.py tests\test_fpm030_update_memory_from_results.py tests\test_fpm060_build_status_dashboard.py -q` returned `7 passed`.
- Real test-mode sequence passed with dashboard rows `12`, web unprocessed total `0`, and UI HTTP `200`.
- Current queue proof:
  - Shure Cosmetics: active, CSV link, ready, pass `1`, fail `8`, rescan `1`
  - CLF, Heo, Stax: API, green, ready when due
  - ABGee, TD Synnex, Tropicana Wholesale: daily email, waiting for file
  - Bliss Distribution, DHB, Entertainment Trading: email request, needs manual file
  - Rashmian: website link, needs manual file
  - We Stock Lots: CSV link, config needed

## Current implementation addendum - 2026-04-30 acquisition source check

Active phase:
- Phase 3 acquisition source checker.

Allowed files for this addendum:
- `scripts/flows/F/price_list_manager/_schemas.py`
- `scripts/flows/F/price_list_manager/FPM010_check_acquisition_sources.py`
- `scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py`
- `tests/test_fpm010_check_acquisition_sources.py`
- `tests/test_fpm060_build_status_dashboard.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`

Implementation:
- Added `source_acquisition_status.csv` as the standard acquisition-state output.
- Added a read-only source checker:
  - manual email-request folders
  - website-download folders
  - daily-email folders
  - API placeholder rows
  - CSV-link remote checks
- Created the Desktop inbox folders for suppliers that need file drops.
- Updated the dashboard so acquisition state drives visible file state and operator action.
- No converter ran and no live F061 handoff occurred.

Verification:
- Created and confirmed these empty inbox folders:
  - `C:\Users\Luke\Desktop\SellerOne Price Files\Bliss Distribution\inbox`
  - `C:\Users\Luke\Desktop\SellerOne Price Files\Rashmian\inbox`
  - `C:\Users\Luke\Desktop\SellerOne Price Files\TD Synnex\inbox`
  - `C:\Users\Luke\Desktop\SellerOne Price Files\DHB\inbox`
  - `C:\Users\Luke\Desktop\SellerOne Price Files\ABGee\inbox`
  - `C:\Users\Luke\Desktop\SellerOne Price Files\Tropicana Wholesale\inbox`
  - `C:\Users\Luke\Desktop\SellerOne Price Files\Entertainment Trading\inbox`
- Focused tests passed: `pytest tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_fpm001_build_test_fixtures.py tests\test_fpm010_check_acquisition_sources.py tests\test_fpm020_placeholder_scanner.py tests\test_fpm030_update_memory_from_results.py tests\test_fpm060_build_status_dashboard.py -q` returned `9 passed`.
- Real acquisition proof:
  - supplier rows `12`
  - ready rows `4`
  - missing rows `4`
  - waiting rows `3`
  - config-needed rows `1`
  - fail rows `0`
  - health fail rows `0`
- Shure CSV link returned HTTP `200` and content type `text/csv;charset=UTF-8`.
- Existing Streamlit UI responded at `http://localhost:8501/?page=price_list_queue` with HTTP `200`.

## Current implementation addendum - 2026-04-30 ready source import and dedupe

Active phase:
- Phase 3 ready source import and duplicate-file protection.

Allowed files for this addendum:
- `scripts/flows/F/price_list_manager/FPM010_check_acquisition_sources.py`
- `scripts/flows/F/price_list_manager/FPM011_import_ready_sources.py`
- `scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py`
- `tests/test_fpm011_import_ready_sources.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`

Implementation:
- Added a test-mode ready-source importer.
- Ready local CSV/TXT files are parsed into the manager's standard `price_list_batches.csv` and `batch_rows.csv` format.
- The importer maps common column names for SKU, barcode, cost, and currency.
- Rows with missing barcode or missing/invalid cost are held before scanning.
- Source files are hashed and duplicate supplier/file hashes are skipped instead of creating another batch.
- The acquisition checker now also writes the active supplier registry snapshot used by the dashboard.
- No live F061 files are written.

Verification:
- Focused tests passed: `pytest tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_fpm001_build_test_fixtures.py tests\test_fpm010_check_acquisition_sources.py tests\test_fpm011_import_ready_sources.py tests\test_fpm020_placeholder_scanner.py tests\test_fpm030_update_memory_from_results.py tests\test_fpm060_build_status_dashboard.py -q` returned `12 passed`.
- Importer test proof:
  - first ready local CSV import created `1` batch
  - source rows `3`
  - valid rows `2`
  - held rows `1`
  - second run imported `0` batches and reported `1` duplicate source
- Real Desktop-folder run proof:
  - ready sources `0`
  - imported batches `0`
  - duplicate sources `0`
  - failed sources `0`
  - total test-mode batches `1`
  - health fail rows `0`
- Existing Streamlit UI responded at `http://localhost:8501/?page=price_list_queue` with HTTP `200`.

## Current implementation addendum - 2026-04-30 simple manual Desktop folders

Active phase:
- Phase 3 operator folder simplification.

Allowed files for this addendum:
- `config/feeder/price_list_manager/suppliers.csv`
- `scripts/flows/F/price_list_manager/FPM011_import_ready_sources.py`
- `scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py`
- `tests/test_fpm011_import_ready_sources.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`

Implementation:
- Created simple Desktop folders:
  - `C:\Users\Luke\Desktop\Amazon price files\DHB\Inbox`
  - `C:\Users\Luke\Desktop\Amazon price files\DHB\Processed`
  - `C:\Users\Luke\Desktop\Amazon price files\Bliss\Inbox`
  - `C:\Users\Luke\Desktop\Amazon price files\Bliss\Processed`
- Updated DHB and Bliss Distribution registry rows to use the simple `Amazon price files` inbox paths.
- Importer now moves successfully imported files from `Inbox` to `Processed`.
- Duplicate files are moved to `Processed` and do not create another batch.
- Missing stale inbox paths after a move are treated as harmless stale acquisition evidence, not as a failed import.
- Dashboard keeps an imported batch visible as ready after the original source file has moved out of the inbox.

Verification:
- Folder creation proof returned `OK` for all four simple folders.
- Registry proof shows DHB and Bliss using the new `Amazon price files` inbox paths.
- Focused tests passed: `pytest tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_fpm001_build_test_fixtures.py tests\test_fpm010_check_acquisition_sources.py tests\test_fpm011_import_ready_sources.py tests\test_fpm020_placeholder_scanner.py tests\test_fpm030_update_memory_from_results.py tests\test_fpm060_build_status_dashboard.py -q` returned `12 passed`.
- Real test-mode run passed with `0` imported batches because the new inboxes are empty, `0` failed sources, and UI HTTP `200`.
- Live F061 was not touched.

## Current implementation addendum - 2026-04-30 DHB Excel converter

Active phase:
- Phase 3 supplier-specific converter for DHB.

Allowed files for this addendum:
- `scripts/flows/F/suppliers/dhb.py`
- `scripts/flows/F/price_list_manager/FPM011_import_ready_sources.py`
- `tests/test_dhb_supplier_converter.py`
- `tests/test_fpm011_import_ready_sources.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`

Implementation:
- Added a DHB Excel converter for the workbook format:
  - sheet `Trade Price`: `No.`, `Description`, `Barcode`, `Trade Price`
  - sheet `End of Line - Whilst Stocks Las`: `No.`, `Description`, `Available Stock`, `Clearance Price`, `Barcode`
- Normalized barcodes to digits only.
- Normalized prices to plain GBP values with two decimal places.
- Held rows before scanning when SKU, barcode, barcode format, or cost is missing/invalid.
- Updated the ready-source importer to use supplier-specific converters when `converter_id` exists.
- The real DHB workbook was imported from the simple Desktop folder and moved to `C:\Users\Luke\Desktop\Amazon price files\DHB\Processed`.

Verification:
- Real DHB workbook analysed:
  - source rows `959`
  - scan-ready rows `788`
  - held rows `171`
  - hold reasons:
    - `missing_or_invalid_cost`: `63`
    - `invalid_barcode_format`: `52`
    - `missing_barcode`: `51`
    - `missing_barcode|missing_or_invalid_cost`: `3`
    - `invalid_barcode_format|missing_or_invalid_cost`: `2`
- Real manager import proof:
  - ready sources `1`
  - imported batches `1`
  - failed sources `0`
  - batch rows after import `969`
  - total batches `2`
  - health fail rows `0`
- Focused tests passed: `pytest tests\test_dhb_supplier_converter.py tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_fpm001_build_test_fixtures.py tests\test_fpm010_check_acquisition_sources.py tests\test_fpm011_import_ready_sources.py tests\test_fpm020_placeholder_scanner.py tests\test_fpm030_update_memory_from_results.py tests\test_fpm060_build_status_dashboard.py -q` returned `14 passed`.
- Existing Streamlit UI responded at `http://localhost:8501/?page=price_list_queue` with HTTP `200`.
- Live F061 was not touched.

## Current implementation addendum - 2026-04-30 Bliss Excel converter and monthly rollover

Active phase:
- Phase 3 supplier-specific converter for Bliss and monthly manual cadence.

Allowed files for this addendum:
- `scripts/flows/F/suppliers/bliss_distribution.py`
- `scripts/flows/F/price_list_manager/FPM011_import_ready_sources.py`
- `scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py`
- `tests/test_bliss_supplier_converter.py`
- `tests/test_fpm011_import_ready_sources.py`
- `tests/test_fpm060_build_status_dashboard.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`

Implementation:
- Added a Bliss Excel converter for the workbook format:
  - sheet `Data`: `Inventory ID`, `Inventory Barcode #`, `Description`, `Price`, `RRP`
  - sheet `Parameters`: ignored as metadata
- Normalized barcodes to digits only.
- Normalized prices to plain GBP values with two decimal places.
- Held rows before scanning when barcode, barcode format, or cost is missing/invalid.
- Added monthly manual rollover logic to the queue dashboard:
  - current-month imported file shows `Done`
  - next-month check with no fresh file shows `Needs Manual File`
- The real Bliss workbook was imported from the simple Desktop folder and moved to `C:\Users\Luke\Desktop\Amazon price files\Bliss\Processed`.

Verification:
- Real Bliss workbook analysed:
  - source rows `2212`
  - scan-ready rows `1526`
  - held rows `686`
  - hold reasons:
    - `invalid_barcode_format`: `438`
    - `missing_barcode`: `248`
- Real manager import proof:
  - ready sources `1`
  - imported batches `1`
  - failed sources `0`
  - batch rows after import `3181`
  - total batches `3`
  - health fail rows `0`
- April 30 dashboard proof:
  - Bliss Distribution: `Ready`, `Complete`, `Done`, unprocessed rows `1526`
  - DHB: `Ready`, `Complete`, `Done`, unprocessed rows `788`
- May 1 rollover proof:
  - Bliss Distribution: `Missing`, `Needs Manual File`, `Request price file`
  - DHB: `Missing`, `Needs Manual File`, `Request price file`
- Focused tests passed: `pytest tests\test_bliss_supplier_converter.py tests\test_dhb_supplier_converter.py tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_fpm001_build_test_fixtures.py tests\test_fpm010_check_acquisition_sources.py tests\test_fpm011_import_ready_sources.py tests\test_fpm020_placeholder_scanner.py tests\test_fpm030_update_memory_from_results.py tests\test_fpm060_build_status_dashboard.py -q` returned `16 passed`.
- Existing Streamlit UI responded at `http://localhost:8501/?page=price_list_queue` with HTTP `200`.
- Live F061 was not touched.

## Current implementation addendum - 2026-04-30 next-action prioritizer

Active phase:
- Phase 4 prioritizer and cooldown engine.

Allowed files for this addendum:
- `scripts/flows/F/price_list_manager/_schemas.py`
- `scripts/flows/F/price_list_manager/FPM040_build_next_action.py`
- `scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py`
- `tests/test_fpm040_build_next_action.py`
- `tests/test_fpm060_build_status_dashboard.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`

Implementation:
- Added `batch_scan_eligibility.csv` as the row-level prioritizer output.
- Added `FPM040_build_next_action.py`.
- The prioritizer filters rows in this order:
  - already processed in placeholder results
  - held by converter
  - active cooldown memory
  - scan eligible
- It writes a recommendation into `manager_decisions.csv`.
- It marks `safe_to_handoff_flag=0`, so this is recommendation-only and does not hand off to F061.
- The dashboard now shows a recommended next scan row with `Recommended` / `Next Scan`.

Verification:
- Focused tests passed: `pytest tests\test_bliss_supplier_converter.py tests\test_dhb_supplier_converter.py tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_fpm001_build_test_fixtures.py tests\test_fpm010_check_acquisition_sources.py tests\test_fpm011_import_ready_sources.py tests\test_fpm020_placeholder_scanner.py tests\test_fpm030_update_memory_from_results.py tests\test_fpm040_build_next_action.py tests\test_fpm060_build_status_dashboard.py -q` returned `19 passed`.
- Real prioritizer proof:
  - eligibility rows `3181`
  - scan rows `2314`
  - skip rows `867`
  - candidate batches `2`
  - selected supplier `bliss_distribution`
  - selected batch `bliss_distribution_source_20260430T123700Z_eaff4dc4572b`
  - estimated scan rows `1526`
  - safe handoff flag `0`
  - health fail rows `0`
- Row decision proof:
  - Bliss Distribution: scan `1526`, skip `686`
  - DHB: scan `788`, skip `171`
  - Shure Cosmetics: scan `0`, skip `10`
  - Shure rows are skipped because they are already processed in placeholder results.
- Dashboard proof:
  - Shure Cosmetics: `Active`, `Test Ready`
  - Bliss Distribution: `Recommended`, `Next Scan`, unprocessed `1526`
  - DHB: `Complete`, `Done`, unprocessed `788`
- Existing Streamlit UI responded at `http://localhost:8501/?page=price_list_queue` with HTTP `200`.
- Live F061 was not touched.

## Current implementation addendum - 2026-04-30 next-action report and UI explanation

Active phase:
- Phase 5 read-only next-action report.

Allowed files for this addendum:
- `scripts/flows/F/price_list_manager/_schemas.py`
- `scripts/flows/F/price_list_manager/FPM050_build_next_action_report.py`
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_fpm050_build_next_action_report.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `project_control/EXPECTATIONS/feeder_cycle_expectations.md`

Implementation:
- Added `next_action_skip_reasons` as a schema-backed report output.
- Added `FPM050_build_next_action_report.py`.
- The report explains:
  - recommended next test scan
  - supplier batch counts
  - skipped-row reasons
  - live F061 handoff safety state
- Added the report to the existing Streamlit `Price List Queue` page under `Next Action Explanation`.
- The report and UI are read-only and do not start F061.

Verification:
- Compile passed for `FPM050_build_next_action_report.py`, `_schemas.py`, `O400_operator_ui.py`, and the focused tests.
- Focused tests passed: `pytest tests\test_fpm060_build_status_dashboard.py tests\test_bliss_supplier_converter.py tests\test_dhb_supplier_converter.py tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_o_ui_operator_view.py::test_price_list_queue_report_loader_reads_markdown tests\test_fpm001_build_test_fixtures.py tests\test_fpm010_check_acquisition_sources.py tests\test_fpm011_import_ready_sources.py tests\test_fpm020_placeholder_scanner.py tests\test_fpm030_update_memory_from_results.py tests\test_fpm040_build_next_action.py tests\test_fpm050_build_next_action_report.py -q` returned `22 passed`.
- Real report proof:
  - eligibility rows `3181`
  - scan rows `2314`
  - skip rows `867`
  - selected supplier `Bliss Distribution`
  - selected batch `bliss_distribution_source_20260430T123700Z_eaff4dc4572b`
  - estimated scan rows `1526`
  - estimated skipped rows `686`
  - safe handoff flag `0`
  - health fail rows `0`
- Real skip-reason proof:
  - Bliss Distribution: `invalid_barcode_format=438`, `missing_barcode=248`
  - DHB: `missing_or_invalid_cost=63`, `invalid_barcode_format=52`, `missing_barcode=51`, combined holds `5`
  - Shure Cosmetics: `already_processed_in_placeholder_results=10`
- Dashboard proof after rebuild:
  - Bliss Distribution: queue position `1`, queue state `Recommended`, bot status `Next Scan`, unprocessed `1526`
  - Shure Cosmetics: queue position `12`, queue state `Complete`, bot status `Complete`, pass `1`, fail `8`, rescan `1`
- Existing Streamlit UI responded at `http://localhost:8501/?page=price_list_queue` with HTTP `200`.
- ASCII check on the new FPM report files returned no matches.
- Live F061 was not touched.

## Current implementation addendum - 2026-04-30 staged F061 handoff guard

Active phase:
- Phase 6 staged handoff design and guard proof.

Allowed files for this addendum:
- `scripts/flows/F/price_list_manager/_schemas.py`
- `scripts/flows/F/price_list_manager/FPM011_import_ready_sources.py`
- `scripts/flows/F/price_list_manager/FPM012_enrich_batch_rows_for_f061.py`
- `scripts/flows/F/price_list_manager/FPM070_stage_f061_handoff.py`
- `tests/test_fpm012_enrich_batch_rows_for_f061.py`
- `tests/test_fpm070_stage_f061_handoff.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`
- `plans/active/f-price-list-process-manager-v1/F061_HANDOFF_PROOF_PLAN.md`

Implementation:
- Added `supplier_title` and `vat_rate` to manager batch rows because F061 requires those fields.
- Updated the ready-source importer so new batches keep title and VAT data at the earliest manager stage.
- Added `FPM012_enrich_batch_rows_for_f061.py` to repair current test-mode rows from archived source files.
- Added `FPM070_stage_f061_handoff.py`.
- The handoff script writes staged F061-shaped files only:
  - `f061_handoff_staged_active_run.csv`
  - `f061_handoff_staged_run_state.csv`
  - `f061_handoff_preview.csv`
- Live apply remains disabled in this phase.
- The guard checks F061 idle state and blocks live apply while F061 has pending/running rows.

Verification:
- Compile passed for the changed FPM scripts and tests.
- Focused tests passed: `pytest tests\test_bliss_supplier_converter.py tests\test_dhb_supplier_converter.py tests\test_fpm001_build_test_fixtures.py tests\test_fpm010_check_acquisition_sources.py tests\test_fpm011_import_ready_sources.py tests\test_fpm012_enrich_batch_rows_for_f061.py tests\test_fpm020_placeholder_scanner.py tests\test_fpm030_update_memory_from_results.py tests\test_fpm040_build_next_action.py tests\test_fpm050_build_next_action_report.py tests\test_fpm060_build_status_dashboard.py tests\test_fpm070_stage_f061_handoff.py tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_o_ui_operator_view.py::test_price_list_queue_report_loader_reads_markdown -q` returned `26 passed`.
- Real enrichment proof:
  - batch rows `3181`
  - current F061-required rows `2314`
  - missing title before enrichment `2314`
  - missing title after enrichment `0`
  - missing VAT before enrichment `2314`
  - missing VAT after enrichment `0`
  - enriched titles `2314`
- Current live F061 state proof:
  - supplier `stocklist_supplier`
  - run status `running`
  - pending active rows `20316`
  - pending run-state rows `20316`
- Latest staged handoff proof:
  - supplier `Bliss Distribution`
  - batch `bliss_distribution_source_20260430T123700Z_eaff4dc4572b`
  - run id `fpm_bliss_distribution_20260430T140000Z`
  - staged rows `1526`
  - live apply allowed `0`
  - F061 idle status `busy`
  - block reason `f061_not_idle:pending_active=20316;running_state=1;pending_state=20316`
- Health note:
  - one earlier `f061_handoff_stage_guard` fail row remains in test-mode health because staging was first attempted before enrichment finished.
  - the latest `f061_handoff_stage_guard` row is `ok` and records the correct busy-state block.
- ASCII check on the new Phase 6 files returned no matches.
- Live F061 files were not changed.

## Current implementation addendum - 2026-04-30 Rashmian URL download probe

Active phase:
- Acquisition source validation for Rashmian.

Allowed files for this addendum:
- `config/feeder/price_list_manager/suppliers.csv`
- `scripts/flows/F/price_list_manager/FPM010_check_acquisition_sources.py`
- `tests/test_fpm010_check_acquisition_sources.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`

Implementation:
- Updated Rashmian from a manual website-folder source to a direct `url_download` / `csv_link` source.
- Added remote response validation so login HTML is not treated as a ready price file.
- The manager now marks Rashmian as blocked when the download returns login HTML.

Verification:
- Direct URL probe downloaded `80546` bytes of HTML.
- Page title/content showed Rashmian login content and reseller login requirement.
- Acquisition check proof:
  - Rashmian source state `error`
  - status `fail`
  - notes `http_status=200;content_type=text/html;remote_type=auth_required_html_response`
- Dashboard proof:
  - Rashmian file state `Error`
  - queue state `Blocked`
  - operator action `Investigate CSV link`
- Focused tests passed: `pytest tests\test_bliss_supplier_converter.py tests\test_dhb_supplier_converter.py tests\test_fpm001_build_test_fixtures.py tests\test_fpm010_check_acquisition_sources.py tests\test_fpm011_import_ready_sources.py tests\test_fpm012_enrich_batch_rows_for_f061.py tests\test_fpm020_placeholder_scanner.py tests\test_fpm030_update_memory_from_results.py tests\test_fpm040_build_next_action.py tests\test_fpm050_build_next_action_report.py tests\test_fpm060_build_status_dashboard.py tests\test_fpm070_stage_f061_handoff.py tests\test_o_ui_operator_view.py::test_price_list_queue_loader_and_summary_reads_dashboard_csv tests\test_o_ui_operator_view.py::test_price_list_queue_report_loader_reads_markdown -q` returned `28 passed`.
- ASCII check on the changed files returned no matches.
- No price file was created for Rashmian because the source response is not a price file.
- Live F061 was not touched.

## 1) Phase Summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 0 | Create plan and operating boundary | plan folder, guidebook only | document review | no | completed |
| Phase 1 | Define manager schemas and fake fixtures | `scripts/flows/F/price_list_manager/*`, `tests/test_fpm_*`, plan files | focused pytest | no | completed |
| Phase 2 | Build placeholder scanner and memory update | same FPM module and tests | focused pytest plus dry-run command | no | completed |
| Phase 3 | Build acquisition adapter shell | FPM acquisition modules, supplier config fixtures, tests | focused pytest | no | in progress |
| Phase 4 | Build prioritizer and cooldown engine | FPM decision modules, tests | focused pytest plus dry-run count proof | no | completed |
| Phase 5 | Build read-only next-action report and dashboard | FPM report module, output schemas, tests | focused pytest plus dry-run output | no | completed |
| Phase 6 | Design controlled F061 handoff | plan files first, then guarded handoff only after approval | forced proof plan and focused tests | yes | staged proof complete; live apply blocked while F061 busy |

## 2) Phase Details

### Phase 0 - Plan And Boundary
Goal:
- Create the durable plan for the process manager.
- Keep the live scanner untouched.

Files allowed to change:
- `plans/active/f-price-list-process-manager-v1/*`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`

Implementation tasks:
- write the project brief
- write the system plan
- write this coding plan
- write the runbook
- write the guidebook

Isolated verification:
- command:
  - `Select-String -Path plans/active/f-price-list-process-manager-v1/*.md,project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md -Pattern '[^\x00-\x7F]'`
- expected result:
  - no non-ASCII output

Monitored validation:
- live proof needed: no
- forced proof window: not required
- artifacts to poll: none
- poll cadence: none
- success threshold: plan files exist and state live F061 boundary clearly
- timeout rule: not applicable
- fallback if forced proof is blocked: not applicable
- next automatic step after success: Phase 1
- notification mode: final only
- user interruption threshold: not applicable

Phase status:
- code fix applied: no live code changed
- isolated verification passed: yes - ASCII check returned no matches and plan files exist
- monitored validation: not needed

### Phase 1 - Schemas And Fake Fixtures
Goal:
- Define the manager's own file contracts before logic is added.
- Create fake supplier and batch data that cannot affect live F061.

Files allowed to change:
- `scripts/flows/F/price_list_manager/_schemas.py`
- `scripts/flows/F/price_list_manager/_paths.py`
- `scripts/flows/F/price_list_manager/FPM001_build_test_fixtures.py`
- `tests/test_fpm001_build_test_fixtures.py`
- `plans/active/f-price-list-process-manager-v1/*`

Implementation tasks:
- create schema constants for:
  - supplier registry
  - price-list batches
  - batch rows
  - barcode scan memory
  - manager decisions
  - manager health
- create a fake supplier registry
- create a fake converted batch with 10 rows
- write only under `out/systems/F/price_list_manager/test_mode/`

Isolated verification:
- command:
  - `python -m py_compile scripts/flows/F/price_list_manager/FPM001_build_test_fixtures.py tests/test_fpm001_build_test_fixtures.py`
  - `pytest tests/test_fpm001_build_test_fixtures.py -q`
- expected result:
  - schema columns are present
  - 10 fake rows are emitted
  - no live F061 inbox or live files are written

Monitored validation:
- live proof needed: no
- forced proof window: not required
- artifacts to poll:
  - `out/systems/F/price_list_manager/test_mode/batch_rows.csv`
  - `out/systems/F/price_list_manager/test_mode/price_list_batches.csv`
- poll cadence: one check after dry run
- success threshold:
  - source rows = 10
  - batch rows = 10
  - health status has no `fail`
- timeout rule:
  - park with exact missing schema or count mismatch
- fallback if forced proof is blocked: not applicable
- next automatic step after success: Phase 2
- notification mode: milestone only
- user interruption threshold: schema conflict with existing F contracts

Phase status:
- code fix applied: yes - added `scripts/flows/F/price_list_manager/` schema/path/IO helpers and `FPM001_build_test_fixtures.py`.
- isolated verification passed: yes - `python -m py_compile scripts\flows\F\price_list_manager\FPM001_build_test_fixtures.py tests\test_fpm001_build_test_fixtures.py` passed; `pytest tests\test_fpm001_build_test_fixtures.py -q` passed `3`.
- monitored validation: passed - `python scripts\flows\F\price_list_manager\FPM001_build_test_fixtures.py --supplier-id shure_cosmetics --observed-utc 2026-04-30T09:00:00Z` wrote test-mode artifacts with source rows `10`, valid rows `10`, eligible rows `10`, decision rows `1`, and health fail rows `0`.

### Phase 2 - Placeholder Scanner And Memory Update
Goal:
- Prove the manager can process 10 fake scanner outcomes and update cooldown memory cleanly.

Files allowed to change:
- `scripts/flows/F/price_list_manager/FPM020_run_placeholder_scanner.py`
- `scripts/flows/F/price_list_manager/FPM030_update_memory_from_results.py`
- `tests/test_fpm020_placeholder_scanner.py`
- `tests/test_fpm030_update_memory_from_results.py`
- plan files

Implementation tasks:
- generate 10 controlled outcomes:
  - `PASS`
  - `NOASIN`
  - `OVER50K`
  - `NOCOST`
  - `ROIFAIL_NEAR`
  - `ROIFAIL_FAR`
  - `SCRAPEFAIL`
  - `SELLERHISTORYFAIL`
  - `BRANDFAIL`
  - `MANUAL_REVIEW`
- update barcode memory with simple v1 cooldowns
- reconcile:
  - scan-ready rows
  - result rows
  - memory update rows
  - unresolved rows

Isolated verification:
- command:
  - `python -m py_compile scripts/flows/F/price_list_manager/FPM020_run_placeholder_scanner.py scripts/flows/F/price_list_manager/FPM030_update_memory_from_results.py tests/test_fpm020_placeholder_scanner.py tests/test_fpm030_update_memory_from_results.py`
  - `pytest tests/test_fpm020_placeholder_scanner.py tests/test_fpm030_update_memory_from_results.py -q`
- expected result:
  - all 10 fake outcomes map to one memory action
  - cooldown dates are populated where required
  - pass rows do not get a same-batch rescan recommendation

Monitored validation:
- live proof needed: no
- forced proof window: not required
- artifacts to poll:
  - `out/systems/F/price_list_manager/test_mode/placeholder_scanner_results.csv`
  - `out/systems/F/price_list_manager/test_mode/barcode_scan_memory.csv`
- poll cadence: one check after dry run
- success threshold:
  - result rows = 10
  - memory rows = 10
  - unresolved result rows = 0
- timeout rule:
  - park with exact missing outcome mapping
- fallback if forced proof is blocked: not applicable
- next automatic step after success: Phase 3
- notification mode: milestone only
- user interruption threshold: cooldown rule ambiguity that changes scan economics materially

Phase status:
- code fix applied: yes - added `FPM020_run_placeholder_scanner.py`, `FPM030_update_memory_from_results.py`, placeholder result schema, focused tests, and dashboard result counting.
- isolated verification passed: yes - focused pytest returned `7 passed`.
- monitored validation: passed - the real test-mode sequence wrote result rows `10`, memory rows `10`, unresolved rows `0`, health fail rows `0`, and dashboard counts Shure as unprocessed `0`, pass `1`, fail `8`, rescan `1`.

### Phase 3 - Acquisition Adapter Shell
Goal:
- Represent manual request, email attachment, API pull, URL download, and local file sources through one manager interface.

Files allowed to change:
- `scripts/flows/F/price_list_manager/FPM010_check_acquisition_sources.py`
- `scripts/flows/F/price_list_manager/_schemas.py`
- `config/feeder/price_list_manager/*`
- `tests/test_fpm010_check_acquisition_sources.py`
- plan files

Implementation tasks:
- create adapter interface that returns:
  - source path
  - source hash
  - received/downloaded timestamp
  - acquisition status
  - notes
- implement safe placeholders:
  - manual request emits an action row only
  - email attachment reads local import folder only
  - API pull uses fixtures only
  - URL/local path uses fixture-safe behavior first
- do not connect real inbox or real supplier API credentials in this phase

Isolated verification:
- command:
  - `pytest tests/test_fpm_acquisition_* -q`
- expected result:
  - each adapter emits standard metadata
  - duplicate file hash does not create duplicate active batch

Monitored validation:
- live proof needed: no
- forced proof window: not required
  - artifacts to poll:
    - `out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv`
    - `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`
- poll cadence: one check after dry run
- success threshold:
  - manual source recommends request when due
  - duplicate email/API file is deduped
  - local fixture file creates one batch
- timeout rule:
  - park with exact adapter failure
- fallback if forced proof is blocked: not applicable
- next automatic step after success: Phase 4
- notification mode: milestone only
- user interruption threshold: real credential or email permission required

Phase status:
- code fix applied: yes - added `FPM010_check_acquisition_sources.py`, `source_acquisition_status` schema, acquisition-aware dashboard behavior, and focused tests.
- isolated verification passed: yes - focused pytest returned `9 passed`.
- monitored validation: passed for source-state reporting - real run wrote `12` supplier rows, `4` ready rows, `4` missing rows, `3` waiting rows, `1` config-needed row, `0` fail rows, and UI HTTP `200`.
  - remaining Phase 3 work: convert known supplier-specific formats with proper supplier converters instead of the generic CSV parser.

### Phase 4 - Prioritizer And Cooldown Engine
Goal:
- Decide which supplier batch and which rows are worth scanning now.

Files allowed to change:
- `scripts/flows/F/price_list_manager/FPM040_build_next_action.py`
- `scripts/flows/F/price_list_manager/cooldowns.py`
- `scripts/flows/F/price_list_manager/prioritizer.py`
- `tests/test_fpm040_build_next_action.py`
- plan files

Implementation tasks:
- calculate row eligibility:
  - new
  - changed
  - cooldown expired
  - cooldown active
  - blocked missing data
- calculate batch score
- choose exactly one recommended next action
- explain skipped rows by reason

Isolated verification:
- command:
  - `pytest tests/test_fpm040_build_next_action.py -q`
- expected result:
  - same unchanged rows are not rescanned
  - changed cost rows can become eligible again
  - history fail rows respect the 180-day v1 cooldown
  - huge supplier lists are filtered before scan recommendation

Monitored validation:
- live proof needed: no
- forced proof window: not required
- artifacts to poll:
  - `out/systems/F/price_list_manager/test_mode/manager_decisions.csv`
  - `out/systems/F/price_list_manager/test_mode/health.csv`
- poll cadence: one check after dry run
- success threshold:
  - one next action is selected
  - selected action has reason code
  - decision counts reconcile to batch rows
- timeout rule:
  - park with exact unreconciled count
- fallback if forced proof is blocked: not applicable
- next automatic step after success: Phase 5
- notification mode: milestone only
- user interruption threshold: prioritizer recommends live handoff before Phase 6 approval

Phase status:
- code fix applied: yes - added `FPM040_build_next_action.py`, `batch_scan_eligibility` schema, recommendation dashboard state, and focused tests.
- isolated verification passed: yes - focused pytest returned `19 passed`.
- monitored validation: passed - real run wrote `3181` eligibility rows, selected Bliss Distribution as next recommended scan with `1526` scan rows, skipped `867` rows, and kept `safe_to_handoff_flag=0`.

### Phase 5 - Read-Only Next-Action Report
Goal:
- Produce operator-facing recommendations without changing the scanner.

Files allowed to change:
- `scripts/flows/F/price_list_manager/FPM050_build_next_action_report.py`
- `tests/test_fpm050_build_next_action_report.py`
- plan files

Implementation tasks:
- output a plain CSV/Markdown report:
  - next recommended supplier action
  - batch counts
  - why not scanning other suppliers
  - manual request tasks
  - expected next check time
- keep all live scanner writes disabled

Isolated verification:
- command:
  - `pytest tests/test_fpm050_build_next_action_report.py -q`
- expected result:
  - report names the next action
  - report includes count proof
  - report marks F061 handoff as recommendation-only

Monitored validation:
- live proof needed: no
- forced proof window: not required
- artifacts to poll:
  - `out/systems/F/price_list_manager/test_mode/next_action_report.md`
- poll cadence: one check after dry run
- success threshold:
  - report exists
  - no unresolved manager decision
  - no live F061 files changed
- timeout rule:
  - park with exact missing report or unwanted live write
- fallback if forced proof is blocked: not applicable
- next automatic step after success: Phase 6 planning decision
- notification mode: milestone only
- user interruption threshold: user approval required before live handoff design

Phase status:
- code fix applied: yes - added `FPM050_build_next_action_report.py`, schema-backed skip-reason output, focused report test, and UI report display.
- isolated verification passed: yes - focused pytest returned `22 passed`.
- monitored validation: passed - real report selected Bliss Distribution with `1526` scan rows, reconciled `3181` eligibility rows, wrote `next_action_report.md` and `next_action_skip_reasons.csv`, and kept `safe_to_handoff_flag=0`.

### Phase 6 - Controlled F061 Handoff
Goal:
- Design and later implement a safe handoff from one manager-selected batch into F061.

Files allowed to change:
- first pass: plan files only
- later only after approval:
  - guarded FPM handoff script
  - F061 owner/lock helper if missing
  - focused tests

Implementation tasks:
- define F061 idle truth
- define owner lock
- build staged handoff file
- snapshot current F live files before any handoff
- apply handoff only when idle and approved
- prove F061 consumes one staged batch and finalizes terminal markers

Isolated verification:
- command:
  - `python scripts/one_off/P002_plan_forced_proof_window.py --flow f`
  - focused handoff tests after implementation
- expected result:
  - forced proof plan documents the safe F-owned proof boundary
  - handoff script refuses busy or unknown owner state

Monitored validation:
- live proof needed: yes
- forced proof window:
  - F-owned proof window only after live scanner is idle or explicitly paused/safely switched
- artifacts to poll:
  - F061 owner/lock evidence
  - staged handoff file
  - `out/systems/F/inbox/supplier_price_list_active_run.csv`
  - `out/systems/F/inbox/supplier_price_list_run_state.csv`
  - F061 final summary/log artifact
- poll cadence:
  - first check at +5 minutes
  - second check at +10 minutes
  - then every +15 minutes up to +60 minutes
- success threshold:
  - terminal truth for target run is present
  - F061 ownership is restored or idle as intended
  - batch counts reconcile
- timeout rule:
  - parked pending next proof window with exact missing terminal marker
- fallback if forced proof is blocked:
  - keep recommendation-only mode
- next automatic step after success:
  - enable handoff only for one approved supplier/batch at a time
- notification mode:
  - passive interval checks, milestone only
- user interruption threshold:
  - approval needed, busy owner, contradictory count evidence, or unsafe handoff state

Phase status:
- code fix applied: yes - added F061-required batch fields, enrichment repair, staged handoff files, and a live-apply guard.
- isolated verification passed: yes - focused pytest returned `26 passed`.
- monitored validation: staged proof complete; live loop verification not run because F061 is busy with `stocklist_supplier`.

### Phase 7 - Stax CSV-Link Supplier Example
Goal:
- Add Stax as the first large keyed CSV feed supplier in the manager.

Files allowed to change:
- `config/feeder/price_list_manager/suppliers.csv`
- `scripts/flows/F/suppliers/stax.py`
- `scripts/flows/F/price_list_manager/FPM011_import_ready_sources.py`
- `scripts/flows/F/price_list_manager/FPM013_download_ready_url_sources.py`
- focused tests
- plan/runbook/guidebook files

Implementation tasks:
- register Stax as `api_pull` / `csv_link`
- download the keyed Stax CSV into a local test-mode inbox
- preserve the downloaded source as a batch artifact
- convert the unusual Stax CSV layout where row 2 is the product header
- normalize barcode digits, GBP prices, and VAT rate values
- hold discontinued or missing-barcode rows before scan recommendation

Isolated verification:
- command:
  - `python -m pytest tests\test_stax_supplier_converter.py tests\test_fpm013_download_ready_url_sources.py tests\test_fpm011_import_ready_sources.py tests\test_fpm010_check_acquisition_sources.py -q`
- expected result:
  - Stax converter handles the second-row product header
  - URL download marks the source ready with a local file path
  - importer still handles existing DHB/Bliss local source paths

Monitored validation:
- live proof needed: no
- forced proof window: not required
- artifacts to poll:
  - `out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv`
  - `out/systems/F/price_list_manager/test_mode/price_list_batches.csv`
  - `out/systems/F/price_list_manager/test_mode/batch_rows.csv`
  - `out/systems/F/price_list_manager/test_mode/next_action_report.md`
  - `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`
- poll cadence: one check after real Stax dry run
- success threshold:
  - Stax download succeeds
  - one Stax batch is imported
  - valid plus held row counts reconcile to source rows
  - dashboard recommends Stax without enabling live F061 handoff
- timeout rule:
  - park with the exact failed download/import/count reconciliation evidence
- fallback if forced proof is blocked: not applicable
- next automatic step after success: continue supplier-by-supplier intake
- notification mode: milestone only
- user interruption threshold: download auth failure, malformed CSV, or live handoff becoming enabled before approval

Phase status:
- code fix applied: yes - added `FPM013_download_ready_url_sources.py`, the Stax supplier converter, registry URL, and focused tests.
- isolated verification passed: yes - focused pytest returned `11 passed`; FPM-focused test suite returned `27 passed`.
- monitored validation: passed - real Stax feed downloaded `14849765` bytes, imported `27201` source rows, produced `24231` scan-ready rows and `2970` held rows, selected Stax as the next recommendation, and kept `safe_to_handoff_flag=0`.

### Phase 8 - Heo Authenticated API Supplier Example
Goal:
- Add Heo as the first authenticated API supplier in the manager.

Files allowed to change:
- `config/feeder/price_list_manager/suppliers.csv`
- `scripts/flows/F/suppliers/heo.py`
- `scripts/flows/F/price_list_manager/FPM014_fetch_api_sources.py`
- focused tests
- plan/runbook/guidebook files
- local ignored credential file under `secrets/`

Implementation tasks:
- register the Heo retailer API endpoint
- store credentials in a local git-ignored secret file
- fetch products and prices from separate paginated API endpoints
- join prices by product number
- expand every product barcode into a scan row
- convert the generated local CSV into manager batch rows
- normalize barcode digits, GBP prices, VAT values, and English product titles

Isolated verification:
- command:
  - `python -m pytest tests\test_heo_supplier_converter.py tests\test_fpm014_fetch_api_sources.py tests\test_fpm011_import_ready_sources.py -q`
- expected result:
  - Heo converter normalizes prices and barcode holds
  - API fetch wrapper writes a local ready source from a mocked fetcher
  - missing credentials are surfaced as an operator action instead of failing silently

Monitored validation:
- live proof needed: no
- forced proof window: not required
- artifacts to poll:
  - `out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv`
  - `out/systems/F/price_list_manager/test_mode/price_list_batches.csv`
  - `out/systems/F/price_list_manager/test_mode/batch_rows.csv`
  - `out/systems/F/price_list_manager/test_mode/next_action_report.md`
  - `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`
- poll cadence: one check after real Heo dry run
- success threshold:
  - Heo API fetch succeeds
  - one Heo batch is imported
  - valid plus held row counts reconcile to expanded rows
  - dashboard includes Heo without enabling live F061 handoff
- timeout rule:
  - park with exact API failure, credential failure, or count mismatch
- fallback if forced proof is blocked: not applicable
- next automatic step after success: continue supplier-by-supplier intake
- notification mode: milestone only
- user interruption threshold: credential failure, malformed API response, or live handoff becoming enabled before approval

Phase status:
- code fix applied: yes - added `FPM014_fetch_api_sources.py`, the Heo supplier API adapter/converter, registry endpoint, local ignored credential file, and focused tests.
- isolated verification passed: yes - Heo focused tests returned `8 passed`; FPM-focused supplier suite returned `31 passed`.
- monitored validation: passed - real Heo API fetched `7610` product rows and `7610` price rows, expanded to `7919` barcode rows, imported `7754` scan-ready rows and `165` held rows, rebuilt queue/report/dashboard, and kept `safe_to_handoff_flag=0`.

### Phase 9 - CLF SOAP API Supplier Adapter
Goal:
- Add CLF SOAP API support far enough that it can pull once the missing auth-token source is supplied.

Files allowed to change:
- `config/feeder/price_list_manager/suppliers.csv`
- `scripts/flows/F/suppliers/clf.py`
- `scripts/flows/F/price_list_manager/FPM014_fetch_api_sources.py`
- `scripts/flows/F/price_list_manager/FPM010_check_acquisition_sources.py`
- focused tests
- plan/runbook/guidebook files

Implementation tasks:
- register the CLF SOAP endpoint
- build the SOAP `GetProductCodes` request
- parse SKU XML from `GetProductCodesResult`
- build batched `GetProductData` requests
- parse SKU, barcode, cost, and VAT from product XML
- convert generated local CSV into manager batch rows
- surface missing auth-token details as an operator action

Isolated verification:
- command:
  - `python -m pytest tests\test_clf_supplier_converter.py tests\test_fpm014_fetch_api_sources.py tests\test_fpm011_import_ready_sources.py -q`
- expected result:
  - CLF XML parsing works
  - CLF generated CSV conversion works
  - token-based API fetch path writes a ready local source in mocked proof

Monitored validation:
- live proof needed: no, blocked by missing auth-token source
- forced proof window: not required
- artifacts to poll:
  - `out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv`
  - `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`
- poll cadence: one check after blocked real CLF fetch attempt
- success threshold:
  - CLF appears as blocked with `Add API credentials`
  - no CLF batch is imported without credentials
  - existing queue recommendation remains safe and live handoff disabled
- timeout rule:
  - park until `getAuthenticationToken()` logic or a valid CLF token is supplied
- fallback if forced proof is blocked: keep CLF blocked and continue other suppliers
- next automatic step after success: run real CLF fetch/import after auth-token source is added
- notification mode: milestone only
- user interruption threshold: token becomes available or SOAP response contradicts expected XML shape

Phase status:
- code fix applied: yes - added the CLF SOAP adapter/converter, registry endpoint, token-aware API fetch support, adapter-aware acquisition notes, and focused tests.
- isolated verification passed: yes - CLF/API focused tests returned `10 passed`; FPM-focused supplier suite returned `34 passed`.
- monitored validation: blocked as expected - real CLF fetch attempt produced `api_credentials_missing`, dashboard shows CLF `Error` / `Blocked` / `Add API credentials`, and `safe_to_handoff_flag=0` remains in the queue decision.

### Phase 10 - We Stock Lots EUR CSV-Link Converter
Goal:
- Add We Stock Lots conversion logic and fix the old hard-coded EUR to GBP rate.

Files allowed to change:
- `config/feeder/price_list_manager/suppliers.csv`
- `scripts/flows/F/suppliers/we_stock_lots.py`
- focused tests
- plan/runbook/guidebook files

Implementation tasks:
- preserve the old Google Sheet column mapping:
  - description from column B
  - barcode from column D
  - pieces MOQ from column F
  - source EUR price from column H
- support friendly headers when present
- convert EUR source prices to GBP during supplier conversion
- use current online EUR to GBP rate before local cache fallback
- expose the source-rate evidence in row notes
- hold missing barcode and invalid cost rows before scan recommendation

Isolated verification:
- command:
  - `python -m pytest tests\test_we_stock_lots_supplier_converter.py tests\test_fpm011_import_ready_sources.py tests\test_fpm010_check_acquisition_sources.py -q`
- expected result:
  - EUR prices convert to GBP with two decimals
  - fixed test rate can be pinned via `WE_STOCK_LOTS_EUR_GBP_RATE`
  - missing barcode and invalid price rows are held
  - positional fallback works when source headers are not friendly

Monitored validation:
- live proof needed: no, blocked by missing CSV link
- forced proof window: not required
- artifacts to poll:
  - `out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv`
  - `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`
- poll cadence: one check after acquisition refresh
- success threshold:
  - We Stock Lots appears as `config_needed`
  - operator action is `Add CSV link`
  - existing queue recommendation remains safe and live handoff disabled
- timeout rule:
  - park until the We Stock Lots CSV link or a local source file is supplied
- fallback if forced proof is blocked: keep We Stock Lots blocked and continue other suppliers
- next automatic step after success: run real We Stock Lots download/import after CSV link is added
- notification mode: milestone only
- user interruption threshold: CSV link becomes available or source columns differ from expected mapping

Phase status:
- code fix applied: yes - added the We Stock Lots converter, current-rate EUR to GBP conversion with cache fallback, registry note, and focused tests.
- isolated verification passed: yes - We Stock Lots focused tests returned `10 passed`; FPM-focused supplier suite returned `36 passed`.
- monitored validation: blocked as expected - acquisition shows We Stock Lots `config_needed` with `Add CSV link`, dashboard shows it as blocked, current rate check returned `0.86643000` from `frankfurter_latest:2026-04-29`, and `safe_to_handoff_flag=0` remains in the queue decision.

### Phase 10 Addendum - We Stock Lots Website Export Endpoint
User supplied the logged-in We Stock Lots Products page HTML. The page exposed export options:
- CSV: `/api/export/stocklist/?format=csv`
- Excel: `/api/export/stocklist/?format=xlsx`
- XML: `/api/export/stocklist/?format=xml`
- PDF: `/api/export/stocklist/?format=pdf`

Implementation update:
- Registry source changed from the earlier Google Sheet false lead to the website CSV export endpoint.
- Source URL is now `https://westocklots.com/api/export/stocklist/?format=csv`.
- Acquisition/download code supports cookie or authorization headers from environment variables without storing those secrets in the repo.
- Preferred auth env for this supplier: `WE_STOCK_LOTS_COOKIE`.
- Generic auth envs also available: `FPM_DOWNLOAD_COOKIE` and `FPM_DOWNLOAD_AUTHORIZATION`.

Current blocker:
- Unauthenticated endpoint check returns `401 Unauthorized`.
- The embedded page product JSON is not enough for scanning because it does not include EAN/barcode fields.
- The CSV export is the correct target because the previous converter mapping expects the EAN/barcode column from the export/raw stock list.

Validation target:
- We Stock Lots should show `Error` / `Blocked` until the authenticated export can be pulled.
- No batch should import from the old Google Sheet source.

Runtime check - 2026-04-30 authenticated export attempt:
- Direct endpoint check confirmed `401 Unauthorized`.
- F061 currently owns `C:\Users\Luke\AppData\Local\Chrome_UC136`, `Profile 2` through remote debugging port `51263`, so opening or navigating that profile for We Stock Lots would risk interrupting the active scan.
- Read-only DevTools cookie check on that running profile found `0` We Stock Lots cookies.
- Normal Chrome `Profile 1` and `Profile 5` cookie databases are locked by open browser processes and do not expose a remote debugging port.
- Edge default profile only has We Stock Lots analytics cookies, not an authenticated export session.
- Decision: keep We Stock Lots blocked in the queue until an authenticated website session can be made available to the downloader. Do not disturb live F061.

User decision - 2026-04-30:
- We Stock Lots is not worth the authentication effort right now.
- Supplier registry changed to `active_flag=0` and `priority_band=parked`.
- Converter remains in place for future reuse, but We Stock Lots must not appear in the active queue.

### Phase 11 - Active Queue Cleanup And Handoff Preview
Goal:
- Move on from parked low-value suppliers and prove the manager can prepare the next useful batch without changing live F061.

Files allowed to change:
- `config/feeder/price_list_manager/suppliers.csv`
- FPM outputs under `out/systems/F/price_list_manager/test_mode/`
- plan/runbook/guidebook files

Implementation tasks:
- park We Stock Lots from active supplier registry
- refresh acquisition source state
- rebuild next-action decision
- rebuild dashboard and next-action report
- stage the selected batch for F061 handoff preview only
- keep live apply disabled while F061 is busy

Verification:
- acquisition refresh returned `supplier_rows=11`, `fail_rows=1`; We Stock Lots no longer appears in active source state
- dashboard refresh returned `dashboard_rows=11`
- next selected supplier is Stax
- Stax selected batch: `stax_source_20260430T144700Z_eaf2df92f4e3`
- staged handoff rows: `24231`
- live apply allowed: `0`
- F061 status: `busy`
- block reason: `f061_not_idle:pending_active=20216;running_state=1;pending_state=20216`

Phase status:
- code fix applied: yes - We Stock Lots is parked and the active queue was rebuilt without it.
- isolated verification passed: yes - FPM and supplier focused test suite returned `37 passed`.
- live loop verification: not attempted; F061 remains busy and live apply remains disabled.

### Phase 12 - Reduce Active Playground Scope
Goal:
- Pin the unresolved suppliers that need extra API, Google/email, or login work, because the current working set is enough for queue and handoff testing.

User decision:
- Park the other suppliers for now.
- Continue with suppliers that already give enough useful queue volume.

Active suppliers after cleanup:
- `stax`
- `heo`
- `shure_cosmetics`
- `bliss_distribution`
- `dhb`

Parked suppliers:
- `rashmian`
- `td_synnex`
- `clf`
- `abgee`
- `we_stock_lots`
- `tropicana_wholesale`
- `entertainment_trading`

Verification:
- supplier registry active counts: `5` active, `7` inactive
- acquisition refresh returned `supplier_rows=5`, `fail_rows=0`
- dashboard refresh returned `dashboard_rows=5`
- dashboard active rows:
  - Stax: `Recommended`, `24231` unprocessed
  - Bliss Distribution: `Complete`, `1526` unprocessed from registered batch
  - DHB: `Complete`, `788` unprocessed from registered batch
  - Heo: `Complete`, `7754` unprocessed from registered batch
  - Shure Cosmetics: `Complete`, `0` unprocessed
- handoff preview still selects Stax
- staged rows: `24231`
- live apply allowed: `0`
- live block reason: `f061_not_idle:pending_active=20216;running_state=1;pending_state=20216`

Phase status:
- code fix applied: yes - unresolved suppliers parked and queue outputs rebuilt.
- isolated verification passed: yes - FPM and supplier focused test suite returned `37 passed`.
- live loop verification: not attempted; live F061 handoff remains disabled while current scanner is busy.

### Phase 13 - Queue Wording And Handoff Readiness Panel
Goal:
- Make the operator UI reflect real queue state: unprocessed ready batches sit in the queue, not under `Complete`.
- Surface the handoff guard result on the dashboard page.

Implementation:
- Dashboard now marks ready batches with unprocessed scan rows as `Queued` when they are not the current recommendation.
- Dashboard HTML now includes a handoff-readiness panel.
- The panel shows the latest staged handoff state, supplier, staged rows, and block reason.

Verification:
- Dashboard focused tests returned `5 passed`.
- Rebuilt dashboard rows:
  - Stax: `Recommended`, `Next Scan`, `24231` unprocessed
  - Bliss Distribution: `Queued`, `Queued`, `1526` unprocessed
  - DHB: `Queued`, `Queued`, `788` unprocessed
  - Heo: `Queued`, `Queued`, `7754` unprocessed
  - Shure Cosmetics: `Complete`, `Complete`, `0` unprocessed
- Dashboard HTML handoff panel shows:
  - `Blocked - F061 busy`
  - `24231 staged`
  - `f061_not_idle:pending_active=20216;running_state=1;pending_state=20216`

Phase status:
- code fix applied: yes - dashboard queue wording and handoff readiness panel added.
- isolated verification passed: yes - dashboard focused tests returned `5 passed`; full FPM/supplier focused suite returned `38 passed`.
- live loop verification: not attempted; live F061 handoff remains disabled while current scanner is busy.

### Phase 14 - Test-Mode Queue Controls
Goal:
- Let the manager pause or prioritise suppliers in the test-mode queue without touching live F061.

Implementation:
- Added `queue_controls.csv` as a test-mode control file.
- Added `FPM080_set_queue_control.py` for setting `normal`, `paused`, or `prioritised` supplier control states.
- `FPM040_build_next_action.py` now skips paused suppliers and lets a prioritised supplier outrank larger normal batches.
- `FPM060_build_status_dashboard.py` now shows `Normal`, `Paused`, or `Prioritised #n` in the queue and HTML dashboard.

Verification:
- Focused queue-control tests returned `11 passed`.
- Full FPM and supplier focused suite returned `42 passed`.
- Real test-mode rebuild left the active queue normal because no control file was present:
  - Stax: `Recommended`, `Normal`, `24231` unprocessed
  - Bliss Distribution: `Queued`, `Normal`, `1526` unprocessed
  - DHB: `Queued`, `Normal`, `788` unprocessed
  - Heo: `Queued`, `Normal`, `7754` unprocessed
  - Shure Cosmetics: `Complete`, `Normal`, `0` unprocessed
- Latest next action selected Stax with `safe_to_handoff_flag=0`.
- Latest staged preview still blocks live apply because F061 is busy: `f061_not_idle:pending_active=20116;running_state=1;pending_state=20116`.

Phase status:
- code fix applied: yes - test-mode queue controls are implemented.
- isolated verification passed: yes - focused and wider FPM tests passed.
- live loop verification: not attempted; live F061 handoff remains disabled while current scanner is busy.

### Phase 15 - Streamlit Queue Control Buttons
Goal:
- Wire the visible Streamlit pause/prioritise buttons to the test-mode queue-control system.

Implementation:
- Streamlit `Price List Queue` buttons now write test-mode controls through `FPM080_set_queue_control.py`.
- After a button click, the UI backend rebuilds:
  - next-action decision
  - next-action report
  - staged F061 preview in `stage_only` mode
  - status dashboard
- Pause becomes Resume when a supplier is paused.
- Prioritise becomes Clear Priority when a supplier is prioritised.
- Buttons remain blocked from live F061 writes.

Verification:
- Streamlit queue-control backend test returned `3 passed`.
- Combined FPM/UI queue test returned `14 passed`.
- Wider FPM/supplier/UI focused suite returned `43 passed`.
- `scripts\flows\O\O400_operator_ui.py` and `FPM080_set_queue_control.py` compile successfully.
- Existing Streamlit UI responded at `http://localhost:8501/?page=price_list_queue` with HTTP `200`.

Phase status:
- code fix applied: yes - UI buttons now update test-mode queue controls and rebuild the manager view.
- isolated verification passed: yes - focused and wider FPM/UI tests passed.
- live loop verification: not attempted; live F061 handoff remains disabled while current scanner is busy.

### Phase 16 - Operator UI Style Alignment
Goal:
- Make the price-list queue page feel like part of the existing operator workspace.

Design study:
- The current operator UI uses compact data rows, dark divider lines, grey column headers, inline badges, and a dark blue/black operator summary strip.
- Reorder and New Product Review avoid large floating dashboard cards and put controls directly into each row.
- The price-list queue should use the same row rhythm because it is an operational work queue, not a standalone report.

Implementation:
- Reworked the Streamlit price-list queue from stacked dashboard cards into a compact row layout.
- Added a dark summary strip matching the New Product Review style.
- Added fixed column headers for supplier, state, method, file, control, scan counts, and actions.
- Kept Pause/Prioritise buttons inline with each supplier row.
- Changed manual-file alerts to the same dark operator style.

Verification:
- Streamlit queue tests returned `3 passed`.
- Combined FPM/UI queue tests returned `14 passed`.
- Wider FPM/supplier/UI focused suite returned `43 passed`.
- `O400_operator_ui.py` compiles successfully.
- Existing Streamlit UI responded at `http://localhost:8501/?page=price_list_queue` with HTTP `200`.

Phase status:
- code fix applied: yes - price-list queue UI now follows the existing operator style.
- isolated verification passed: yes - focused and wider UI/FPM tests passed.
- live loop verification: not required; UI-only change with no live F061 write path.

### Phase 17 - Safe F061 Handoff Approval Gate
Goal:
- Separate "F061 is technically idle" from "the operator approved this exact supplier batch for handoff".

Implementation:
- Added `f061_handoff_approvals.csv` as a test-mode approval ledger.
- Added `FPM090_set_f061_handoff_approval.py` to record `approved` or `revoked` handoff approvals.
- Updated `FPM070_stage_f061_handoff.py` so staged preview now records:
  - `technical_ready_flag`
  - `approval_state`
  - `approval_id`
  - `live_apply_allowed`
- A staged batch can be technically ready but still blocked by `handoff_approval_required`.
- Live F061 writing remains disabled.

Safe rule:
- F061 active run has zero pending rows.
- F061 run state has no `running` row and zero pending rows.
- Selected batch has at least one staged row.
- All required F061 fields are present.
- A latest matching approval exists for the same supplier and batch.
- Only then may the preview show `live_apply_allowed=1`.
- Even then, the current phase still refuses live apply.

Verification:
- Focused handoff tests returned `13 passed`.
- Wider FPM/supplier/UI focused suite returned `46 passed`.
- Compile passed for `FPM070`, `FPM090`, dashboard, and Streamlit UI.
- Real current preview remains blocked because F061 is busy:
  - supplier `stax`
  - staged rows `24231`
  - `technical_ready_flag=0`
  - `approval_state=required`
  - `live_apply_allowed=0`
  - block reason `f061_not_idle:pending_active=20116;running_state=1;pending_state=20116`

Phase status:
- code fix applied: yes - technical readiness and approval are now separate gates.
- isolated verification passed: yes - focused and wider FPM/UI tests passed.
- live loop verification: not attempted; live F061 handoff remains disabled while current scanner is busy.

### Phase 18 - Streamlit Handoff Approval Controls
Goal:
- Let the operator record or revoke approval for the exact staged supplier/batch from the Price List Queue page.

Implementation:
- Added a Streamlit `F061 Handoff Guard` panel to the price-list queue.
- The panel shows:
  - staged supplier and batch
  - staged row count
  - technical readiness
  - approval state
  - live-allowed state
  - block reason
- Added `Approve` and `Revoke` buttons.
- Button clicks write `f061_handoff_approvals.csv`, rebuild the staged preview, and rebuild the dashboard.
- Buttons do not write live F061 files.

Verification:
- Focused approval UI backend tests returned `8 passed`.
- Wider FPM/supplier/UI focused suite returned `47 passed`.
- Compile passed for Streamlit UI, `FPM090`, and `FPM070`.
- Existing Streamlit UI responded at `http://localhost:8501/?page=price_list_queue` with HTTP `200`.
- Current real preview remains unapproved and blocked because F061 is busy:
  - supplier `stax`
  - staged rows `24231`
  - `technical_ready_flag=0`
  - `approval_state=required`
  - `live_apply_allowed=0`
  - block reason `f061_not_idle:pending_active=20116;running_state=1;pending_state=20116`

Phase status:
- code fix applied: yes - Streamlit can now record and revoke exact staged-batch approval.
- isolated verification passed: yes - focused and wider FPM/UI tests passed.
- live loop verification: not attempted; live F061 handoff remains disabled while current scanner is busy.

### Phase 19 - Guarded F061 Live Apply Script
Goal:
- Add the final guarded copy step from staged manager files into the real F061 inbox, but keep preview-only as the default.

Implementation:
- Added `FPM100_apply_f061_handoff.py`.
- Default mode writes only `f061_handoff_apply_preview.csv`.
- Live write requires both:
  - `--apply-live`
  - `--confirm-approved-handoff`
- Before any live write, the script checks:
  - latest staged preview exists
  - `technical_ready_flag=1`
  - `approval_state=approved`
  - `live_apply_allowed=1`
  - staged active row count matches preview
  - staged run-state row count matches preview
  - staged run is all pending rows
  - F061 is still idle at apply time
- If all guards pass, the script snapshots current live F061 input files before writing.

New outputs:
- `f061_handoff_apply_preview.csv`
- `f061_handoff_apply_backups.csv`
- `f061_handoff_backups/<backup_id>/manifest.csv`

Verification:
- Focused FPM100/FPM070/FPM090 tests returned `10 passed`.
- Wider FPM/supplier/UI focused suite returned `51 passed`.
- Compile passed for `FPM100`, `FPM070`, and `FPM090`.
- Real preview-only run at `2026-04-30T17:15:00Z` wrote no live F061 files and remained blocked:
  - supplier `stax`
  - staged rows `24231`
  - `apply_ready_flag=0`
  - `live_write_attempted=0`
  - `live_write_succeeded=0`
  - block reason `technical_ready_flag_not_1;approval_state_not_approved;live_apply_allowed_not_1;f061_not_idle:pending_active=20116;running_state=1;pending_state=20116`

Phase status:
- code fix applied: yes - guarded apply path exists with preview-only default and backup-before-write behavior.
- isolated verification passed: yes - focused and wider FPM/UI tests passed.
- live loop verification: not attempted; real F061 remains busy and no approval exists for the current Stax batch.

### Phase 20 - Test-Mode Acquisition and Fake-Scan Loop
Goal:
- Prove the upstream manager can download/fetch/import supplier files, convert them to the manager format, fake-scan 10 rows, update memory/counts, and move to another supplier without touching F061.

Implementation:
- Added `FPM110_run_test_mode_cycle.py`.
- The runner can:
  - check active source locations
  - download URL/CSV-link sources
  - fetch API sources
  - import ready files into batches
  - enrich rows for F061-required fields
  - build next action/report/dashboard
  - fake-scan 10 rows per selected supplier
  - update barcode memory from fake results
  - record cycle run and step logs
- Placeholder scanner now appends results instead of replacing the file.
- Placeholder scanner now selects rows from `batch_scan_eligibility.csv`, so already-processed rows are skipped.
- Added cycle health check `test_mode_cycle_reconciliation`.
- Fixed Shure Cosmetics CSV title mapping:
  - `Product Name` is now treated as `supplier_title`.
  - Existing Shure CSV batches can be repaired from their archived source file during enrichment.

New outputs:
- `test_mode_cycle_runs.csv`
- `test_mode_cycle_steps.csv`

Verification:
- Focused cycle tests returned `7 passed`.
- Wider FPM/supplier/UI focused suite returned `52 passed`.
- Real cycle at `2026-04-30T17:45:00Z`:
  - downloaded sources: `2`
  - API fetched sources: `1`
  - imported batches: `3`
  - scanner iterations: `5`
  - fake result rows: `50`
  - processed suppliers: `bliss_distribution,dhb,heo,shure_cosmetics,stax`
- Follow-up real cycle at `2026-04-30T18:00:00Z`:
  - scanner iterations: `2`
  - fake result rows: `20`
  - skipped pre-existing result suppliers and processed remaining manual batches.
- Short real cycle at `2026-04-30T18:15:00Z`:
  - scanner iterations: `1`
  - fake result rows: `10`
  - `test_mode_cycle_reconciliation=ok`
- Shure enrichment proof at `2026-04-30T18:30:00Z`:
  - before missing title: `5047`
  - after missing title: `0`
  - enriched titles: `9646`

Phase status:
- code fix applied: yes - test-mode queue loop exists and source-format issue in Shure was fixed at conversion/enrichment.
- isolated verification passed: yes - focused and wider FPM/UI tests passed.
- live loop verification: not applicable; this phase intentionally uses placeholder results and does not write live F061 files.

### Phase 21 - 50-Row Live Scanner Trial
Goal:
- Pause the current long Stocklist F061 run and run a small real scanner trial across current supplier price-list formats.

Boundary:
- F061 handles one supplier active queue at a time.
- Do not combine suppliers into one active run.
- Preserve the current Stocklist active queue before replacing the live F061 inbox.
- Use 50 rows per supplier from the current manager batches.

Planned sequence:
- Stop the current F061 loop owner process and its parent `cmd.exe` wrapper.
- Snapshot current live F061 files:
  - `supplier_price_list_active_run.csv`
  - `supplier_price_list_run_state.csv`
- Build 50-row sample queues for:
  - `stax`
  - `heo`
  - `shure_cosmetics`
  - `bliss_distribution`
  - `dhb`
- Apply and run one supplier at a time through `F061_run_legacy_first_checks_local.py --max-rows 50`.
- Record row counts, processed rows, pass/fail/rescan counts, and remaining rows after each supplier.

Verification status: Forced proof window required
Changed at: 2026-04-30T18:35:00Z
Latest health snapshot at: not used for this live-trial boundary
Next verifier: paused-owner proof plus one 50-row F061 supplier run

Phase result - 2026-04-30:
- Paused the running Stocklist F061 owner:
  - parent batch wrapper PID `9184`
  - Python child PID `27084`
- Backed up the paused Stocklist queue before trial writes:
  - `out/systems/F/price_list_manager/live_trial_backups/stocklist_pause_20260430T125146Z`
- Added controlled 50-row live-trial tooling:
  - `FPM120_build_f061_live_trial_samples.py`
  - `FPM121_apply_f061_live_trial_supplier.py`
- Built trial `f061_live_trial_20260430T125433Z`.
- Built exact 50-row samples for:
  - `stax`
  - `heo`
  - `shure_cosmetics`
  - `bliss_distribution`
  - `dhb`
- Each live apply created a backup under:
  - `out/systems/F/price_list_manager/live_trial_backups/trial_apply_*`

Scanner proof:
- Stax: processed `50`, pending `0`, pass `0`, fail `54`, candidate rows `54`, scrape success `1`.
- Heo: processed `50`, pending `0`, pass `1`, fail `49`, candidate rows `50`, scrape success `2`.
- Shure Cosmetics: processed `50`, pending `0`, pass `0`, fail `53`, candidate rows `53`, scrape attempted `3`, scrape success `0`.
- Bliss Distribution: processed `50`, pending `0`, pass `0`, fail `51`, candidate rows `51`, no scrape needed.
- DHB: processed `50`, pending `0`, pass `1`, fail `62`, candidate rows `63`, scrape success `4`.

Final boundary proof:
- No F061 owner process remained after the trial.
- `supplier_price_list_active_run.csv` ended with `0` rows.
- Last run state is `dhb`, `completed`, `total_rows=50`, `pending_rows=0`, `done_rows=50`.
- Focused test proof returned `12 passed`.

Phase status:
- code fix applied: yes - 50-row trial sample builder and guarded live-trial apply path are implemented.
- isolated verification passed: yes - focused FPM070/FPM100/FPM120 tests returned `12 passed`.
- live loop verification confirmed: yes - five 50-row supplier samples were applied one at a time and F061 completed each with zero pending rows.

### Phase 22 - Scheduled Live Price-List Cycle And Entertainment Trading Resume
Goal:
- Turn the price-list manager into the owner of the F cycle scanner queue.
- Run from a BAT file loaded into Windows Task Scheduler.
- Recover after the 02:10 PC restart without starting the current supplier again from row 1.
- Add Entertainment Trading as the first live resume batch, above the normal queue, as if it had been loaded through the new system.
- After Entertainment Trading completes, automatically move to the next eligible price file and scan it completely.

Planning status:
- Planning only.
- No code changes for this phase yet.
- No live F061 writes for this phase yet.

Important design rule:
- The manager owns the queue and decides what F061 should scan.
- F061 remains the scanner worker.
- The BAT file starts the manager runner, not a supplier-specific endless loop.
- The runner must be idempotent: if it starts twice, only one owner can run.

Files expected to change when implementation starts:
- `config/feeder/price_list_manager/suppliers.csv`
- `scripts/flows/F/price_list_manager/FPM130_*` or later manager scripts for live cycle ownership
- `scripts/flows/F/price_list_manager/_schemas.py`
- `scripts/flows/F/price_list_manager/_paths.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py` only if a checkpoint gap is proven
- `scripts/flows/O/O400_operator_ui.py`
- `run_F_price_list_manager_cycle.bat`
- optional helper BAT files:
  - `run_F_price_list_manager_status.bat`
  - `run_F_price_list_manager_stop.bat`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- focused tests under `tests/test_fpm*.py`

Phase 22A - Entertainment Trading folder and registry:
- Create simple operator folders:
  - `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Inbox`
  - `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Processed`
- Change Entertainment Trading from parked to active.
- Keep source method as `Email request`.
- Point the registry to the simple `Amazon price files` folder, not the older `SellerOne Price Files` path.
- Add a visible queue label such as `Resume first` or `Priority resume` so it is clear why it sits above Stax/Heo/Shure/Bliss/DHB.

Phase 22B - Import half-completed Entertainment Trading scan:
- Find the existing half-completed Entertainment Trading evidence:
  - source price file, if available
  - old active run file, if available
  - old run state, if available
  - F061 screening/result outputs, if available
  - logs/backups that contain the original `run_id`
- Prefer source-file import if the original price file exists.
- If only the half-completed active run exists, import that as a recovery batch and mark it as `legacy_resume_source`.
- Preserve row identity:
  - keep existing `run_id` if it is safe
  - keep existing `row_key` where possible
  - do not regenerate row keys if that would cause completed rows to be scanned again
- Seed manager batch state:
  - completed rows stay completed
  - pending rows stay pending
  - failed/pass/manual-review rows keep their known result state
  - unknown rows are held for review, not silently marked done
- Put the Entertainment Trading recovery batch at the top of the live queue.

Phase 22C - Live cycle runner:
- Add a manager-owned live runner, likely `FPM130_run_live_cycle.py`.
- Runner loop:
  - acquire `out/systems/F/price_list_manager/live_cycle.lock`
  - recover stale lock if the PC restarted and no owner process exists
  - check whether F061 has an active run with pending rows
  - if yes, resume that run first
  - if no, finalize the last completed run
  - select the next eligible manager batch
  - apply the batch to F061
  - run F061 for a controlled chunk
  - ingest F061 results back into manager progress
  - repeat until stopped or no eligible work remains
- Initial chunk size:
  - `50` rows while proving restart recovery
  - raise later only after we prove safe resume and scan time
- The runner must never rebuild a batch over an in-progress active run.
- The runner must never mix suppliers in one F061 active run.

Phase 22D - F061 resume contract:
- Required behavior after restart:
  - if `supplier_price_list_active_run.csv` has pending rows, continue that supplier
  - if run state says `running` but no F061 process exists, treat it as recoverable
  - if a row was in-progress when Windows restarted, requeue only that small chunk, not the whole supplier
- Need to prove whether F061 currently checkpoints after each chunk only or after each row.
- If it checkpoints only at chunk end, keep chunks small at first.
- If mid-chunk duplicate scanning is unacceptable, add per-row checkpointing before scheduling.

Phase 22E - Result ingestion and batch finalization:
- Add a result ingestion step from F061 outputs into manager batch progress.
- It must update:
  - pending rows
  - scanned rows
  - pass rows
  - fail rows
  - rescan/manual-review rows
  - last scanned timestamp
  - cooldown memory
- A supplier batch is complete only when:
  - active run has no pending rows
  - run state is `completed`
  - manager batch row counts reconcile
  - results have been ingested
- After finalization, the runner should choose the next batch automatically.

Phase 22F - BAT and Task Scheduler:
- Add `run_F_price_list_manager_cycle.bat`.
- The BAT should:
  - cd to repo root
  - set unbuffered Python logging
  - write logs to `out/systems/F/price_list_manager/live_cycle.log`
  - call the live cycle runner
  - exit cleanly if another owner is already running
  - return non-zero only on real fatal errors
- Task Scheduler setup target:
  - trigger at user logon or startup
  - add a delay after the 02:10 restart, for example 10 minutes
  - restart on failure
  - do not start a second instance if already running
  - run whether the Streamlit UI is open or not
- Optional second trigger:
  - every 15 minutes as a safety net
  - runner exits immediately if the lock says another owner is active

Phase 22G - UI integration:
- Price List Queue page should show:
  - current live owner state
  - active supplier
  - active run id
  - rows done / pending / failed / pass
  - last checkpoint time
  - next supplier after current completion
  - task scheduler status if discoverable
  - stale-lock warning
  - BBP login required warning if detected
- Entertainment Trading should show as:
  - `Priority resume`
  - method `Email request`
  - folder path under `Amazon price files`
  - current progress from the imported half-scan

Phase 22H - Health and alerts:
- Add health checks:
  - `fpm_live_cycle_single_owner`
  - `fpm_live_cycle_lock_fresh`
  - `fpm_f061_active_run_recoverable`
  - `fpm_batch_result_reconciliation`
  - `fpm_scheduler_restart_resume_ready`
  - `fpm_entertainment_resume_seeded`
- Alert only when:
  - no owner can be recovered
  - active run has pending rows but no safe resume path
  - counts do not reconcile
  - F061 crashes repeatedly on the same row
  - BBP login blocks useful scan evidence

Phase 22I - Proof path:
- Isolated proof:
  - seed a fake in-progress Entertainment Trading batch in a temp root
  - simulate completed and pending rows
  - run the live-cycle runner once
  - prove it resumes pending rows instead of rebuilding the supplier
- Controlled live proof:
  - use a 50-row Entertainment Trading recovery sample first
  - stop after one chunk
  - restart the BAT manually
  - prove it picks up the remaining rows, not row 1
- Scheduler proof:
  - register the scheduled task
  - trigger it manually once
  - prove the BAT starts the manager runner
  - prove a second trigger exits because the owner lock is active
  - after the next 02:10 restart, prove the runner resumes the same supplier from the active state

Definition of done for this phase:
- Entertainment Trading is in the manager queue at the top as a recovery batch.
- Entertainment Trading completes without restarting from row 1.
- The manager finalizes Entertainment Trading and moves to the next eligible price file.
- The BAT can be run manually and through Task Scheduler.
- After the 02:10 PC restart, the cycle resumes from the saved active state.
- UI shows the active supplier, progress, and next supplier.
- Health checks expose owner, lock, resume, and reconciliation truth.
- No Google Sheets are changed.

Verification status: Not started
Changed at: not applicable - planning only
Latest health snapshot at: not used for planning
Next verifier: Phase 22A isolated folder/registry proof before any live F061 write

Phase 22A result - 2026-04-30:
- Created the simple Entertainment Trading operator folders:
  - `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Inbox`
  - `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Processed`
- Updated `config/feeder/price_list_manager/suppliers.csv`:
  - `entertainment_trading` is active
  - source folder now points to the simple `Amazon price files` path
  - priority band is `recovery_priority`
  - notes state that this is for Phase 22 recovery resume
- Added a test-mode queue control:
  - supplier `entertainment_trading`
  - control state `prioritised`
  - priority rank `1`
- Refreshed acquisition, next action, report, and dashboard outputs.
- Current Entertainment Trading source state:
  - `missing`
  - folder is empty
  - operator action is `Request price file`
- Recovery evidence search:
  - found 2 old Entertainment Trading rows in `reference/Restocking References/google sheet pages/1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY/Amazon Supplier Process - Product Database.csv`
  - both rows are `Name not found` / `No Data`
  - rows contain ASIN/barcode references but no usable supplier cost or product title
  - no matching `entertainment_trading` F061 active-run backup was found under current `out/systems/F`
  - no matching source rows were found in the old `Amazon Price List Scanner 2.1` scanner data by ASIN/barcode

Phase 22A blocker:
- Entertainment Trading cannot be safely seeded as a scanner-ready recovery batch from the evidence found so far.
- Root cause: the only located evidence is product-database output, not the original price-list rows or an F061 active-run queue.
- Safe next action: find the original Entertainment Trading price file or an old active-run backup that includes `supplier_sku`, `supplier_title`, `barcode`, `unit_cost`, `currency`, and `vat_rate`.

Phase 22A status:
- code fix applied: yes - folder and registry activation only.
- isolated verification passed: partial - manager source/dashboard refresh sees Entertainment Trading as active and missing.
- live loop verification: not attempted; no live F061 write is safe until scanner-ready recovery rows exist.

Phase 22B result - 2026-04-30:
- Imported the original Entertainment Trading XLSX from:
  - `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Inbox\Stocklist.xlsx`
- Preserved the source artifact at:
  - `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Processed\Stocklist_20260430T142821Z_e9a97b901a.xlsx`
- Source SHA256:
  - `DC6458F69D43F50505C17E4E3BC13D2237F1A6EDAD765947740B5AE44153AE9C`
- Imported batch:
  - `entertainment_trading_source_20260430T142821Z_e9a97b901ad3`
- Column mapping:
  - `ItemCode` -> supplier SKU
  - `ItemName` -> title
  - `CodeBars` -> barcode
  - `Available` -> stock availability
  - `EUR` -> cost converted to GBP
  - supplier name -> `Entertainment Trading`
- Row reconciliation:
  - source rows: `42,717`
  - imported batch rows: `42,717`
  - scan-ready rows: `42,449`
  - held rows: `268`
  - held reason counts: `invalid_barcode_format=214`, `missing_barcode=54`
- Queue proof:
  - dashboard position: `1`
  - queue state: `Recommended`
  - control state: `Prioritised #1`
  - web unprocessed: `42,449`
- Handoff proof:
  - staged supplier: `entertainment_trading`
  - staged rows: `42,449`
  - `live_apply_allowed=0`
  - `live_write_attempted=0`
  - `live_write_succeeded=0`
  - block reason: `handoff_approval_required`
- Recovery progress correction:
  - the full imported source is not the live resume queue
  - old F061 supplier id: `stocklist_supplier`
  - old F061 run id: `stocklist_supplier_webscrape_reset_20260429T164504Z`
  - old selected run rows: `21,817`
  - old pending rows: `20,116`
  - old done rows: `1,701`
  - old failed rows recorded by F061: `1,584`
  - pending rows matched into the new Entertainment Trading batch: `20,083`
  - pending rows now held by the new converter because barcode safety fails: `33`
  - pending rows unmatched after hold classification: `0`
  - manager rows marked recovery-skipped so they are not rescanned now: `22,366`
  - manager held rows: `268`
  - latest dashboard web unprocessed: `20,083`
  - latest staged handoff rows: `20,083`
  - latest live F061 active-run rows written by manager: `0`
  - latest recovery health check: `f061_recovery_progress_import_reconciliation=ok`
- Root-cause fix applied:
  - decision consumers now use the latest appended manager decision instead of sorting by `decided_at_utc`
  - this prevents older future-dated test decisions from overriding the current recovery recommendation
- Additional recovery importer:
  - `FPM125_import_f061_recovery_progress.py` imports old F061 pending state into the manager batch without using the old active-run file as a supplier source file
  - the importer matches old pending rows by supplier SKU and barcode
  - the importer is idempotent and keeps the live F061 handoff disabled
- Tests:
  - `pytest tests\test_entertainment_trading_supplier_converter.py tests\test_fpm011_import_ready_sources.py tests\test_fpm010_check_acquisition_sources.py tests\test_fpm040_build_next_action.py tests\test_fpm050_build_next_action_report.py tests\test_fpm060_build_status_dashboard.py tests\test_fpm070_stage_f061_handoff.py tests\test_fpm080_set_queue_control.py -q`
  - result: `28 passed`
  - recovery-focused rerun: `pytest tests\test_entertainment_trading_supplier_converter.py tests\test_fpm125_import_f061_recovery_progress.py tests\test_fpm040_build_next_action.py tests\test_fpm050_build_next_action_report.py tests\test_fpm060_build_status_dashboard.py tests\test_fpm070_stage_f061_handoff.py -q`
  - recovery-focused result: `23 passed`
- No Google Sheets were changed.
- No live F061 inbox rows were written.

Phase 22B status:
- code fix applied: yes - Entertainment Trading converter/import plus stale-decision reader fix.
- isolated verification passed: yes - source hash, row counts, dashboard, report, and handoff preview reconcile.
- live loop verification: not attempted - live F061 handoff remains disabled until Phase 22C controlled runner proof.

Verification status: Isolated proof passed
Changed at: 2026-04-30T14:51:41Z
Latest health snapshot at: not used for A/B/E/H health; FPM recovery artifacts rebuilt at 2026-04-30T14:50:01Z
Next verifier: Phase 22C controlled 50-row live-cycle runner proof

Phase 22C implementation result - 2026-04-30:
- Added manager-owned live runner:
  - `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- Added launcher BAT:
  - `run_F_price_list_manager_cycle.bat`
- Added scheduler XML export:
  - `config/scheduler/AMZ_Price_List_Manager.xml`
- Added focused tests:
  - `tests/test_fpm130_live_cycle.py`
- Live runner behavior:
  - acquires `out/systems/F/price_list_manager/live/live_cycle.lock`
  - writes `live_cycle_status.csv`, `live_cycle_events.csv`, and `live_cycle_health.csv`
  - resumes an existing F061 active run before selecting any new supplier
  - applies the next manager batch only when live apply is enabled and the exact selected batch is approved
  - BAT defaults to exact-batch auto approval for the manager-selected batch because the user approved moving to live manager setup
  - scanner chunks default to `50` rows so restart recovery has small replay risk
  - if `out/locks/maintenance.requested` exists, it writes `F_restart_drain.ready` and does not start another F061 chunk
- Controlled restart integration:
  - `controlled_restart_gate.py` now detects active F manager ownership
  - F manager is accepted as safe only when it is at `F_restart_drain.ready`
  - `controlled_restart_controller.py` can pass F heartbeat age to the gate
  - post-heal relaunch can start `AMZ Price List Manager` alongside B/H when no reboot is performed
- Windows Task Scheduler:
  - registered task `AMZ Price List Manager`
  - boot trigger with `PT5M` delay
  - action: `cmd.exe /c "C:\Users\Luke\Desktop\SellerOne 2.0\run_F_price_list_manager_cycle.bat"`
  - working directory: `C:\Users\Luke\Desktop\SellerOne 2.0`
  - multiple instances: `IgnoreNew`
  - execution time limit: `PT0S`
  - restart on failure: `999` attempts every `PT5M`
  - start when available: `true`
  - registered as `InteractiveToken` because Codex does not have the Windows password required to register a stored-password task like `AMZ Orders`
- Safety proof:
  - preview-only runner check staged Entertainment Trading with `20,083` rows
  - live F061 active-run rows remained `0`
  - live lock was released after the proof
  - `AMZ Price List Manager` task state is `Ready`
  - `AMZ Controlled Restart` is still `Disabled`; code support is added, but the existing restart task was not enabled
- Tests:
  - `pytest tests\test_fpm130_live_cycle.py tests\test_controlled_restart_gate.py -q`
  - result: `7 passed`
  - final focused proof after restoring `project_control/REPRICER_RUNTIME_CONTRACT.md`:
    `pytest tests\test_fpm130_live_cycle.py tests\test_controlled_restart_gate.py tests\test_fpm125_import_f061_recovery_progress.py tests\test_fpm070_stage_f061_handoff.py tests\test_fpm100_apply_f061_handoff.py -q`
  - result: `20 passed`
  - compile proof: `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\tools\controlled_restart_gate.py scripts\tools\controlled_restart_controller.py`
  - result: passed

Phase 22C status:
- code fix applied: yes - live runner, BAT launcher, scheduler task, restart gate/controller integration.
- isolated verification passed: yes - focused tests and preview-only runner proof passed.
- live loop verification: not yet proven - the scheduled task has not been started to scan live rows in this step.

Verification status: Forced proof window required
Changed at: 2026-04-30T15:04:03Z
Latest health snapshot at: not used for A/B/E/H health; FPM scheduler proof checked at 2026-04-30T15:10:48Z
Next verifier: controlled live start of `AMZ Price List Manager` with 50-row Entertainment Trading chunk, then confirm F061 pending count decreases and manager resumes from the same active run after a launcher restart

## Phase 22D - Live Home-Time Validation And Restart
Start UTC: 2026-04-30T15:14:03Z

Goal:
- Start `AMZ Price List Manager` under Task Scheduler ownership.
- Monitor live F manager/F061 progress for 30 minutes.
- If progress is healthy, trigger controlled restart with drain enabled.
- If progress is not healthy, stop and fix the blocking issue before restart.

Monitoring target:
- `out/systems/F/price_list_manager/live/live_cycle.lock`
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/price_list_manager/live/live_cycle_events.csv`
- `out/systems/F/inbox/supplier_price_list_active_run.csv`
- `out/systems/F/price_list_manager/live/F_restart_drain.ready`

Success threshold:
- F manager task starts and owns a live lock.
- Entertainment Trading is active or resumed.
- F061 active run row status moves forward without restarting completed rows.
- No duplicate F manager owner appears.
- No live-cycle blocked/error status persists.

Automatic next step:
- If the threshold is met within 30 minutes, run controlled restart with drain enabled.
- If not met, diagnose and fix before restart.

30-minute result:
- Not successful enough to force restart.
- `AMZ Price List Manager` started and applied Entertainment Trading to F061.
- Live active run has `20,083` rows, all still `pending` after the first 30-minute watch.
- F061 child process is alive, but the manager status/heartbeat does not refresh while the old 50-row child is running.
- Restart drain has been requested so the old manager stops at the next safe boundary instead of starting another chunk.

Fix applied for next manager start:
- Default manager chunk size changed from `50` to `5` in `run_F_price_list_manager_cycle.bat`.
- `FPM130_run_live_cycle.py` now writes scanner-running status before launching F061.
- `FPM130_run_live_cycle.py` now runs F061 with a polled child process and refreshes the F manager heartbeat while F061 is active.
- `run_controlled_restart_controller.bat` default `CONTROLLED_RESTART_FORCE_REBOOT_ON_SKIP` changed from `1` to `0`, so home-time restart does not force reboot while F is blocked or mid-chunk.
- `controlled_restart_gate.py` now accepts H/F stale launcher heartbeat while that owner is already at a trusted restart-drain boundary.
- `controlled_restart_gate.py` now accepts H launcher/cycle locks while `H_restart_drain.ready` proves H is sitting at the restart boundary.

Proof after fix:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\tools\controlled_restart_gate.py scripts\tools\controlled_restart_controller.py` passed.
- `PYTHONPATH=repo;scripts pytest tests\test_fpm130_live_cycle.py tests\test_controlled_restart_gate.py -q` passed with `7 passed`.

Current live state:
- Old FPM process is still running the pre-fix 50-row child.
- Do not force reboot until `out/systems/F/price_list_manager/live/F_restart_drain.ready` exists or the old child exits cleanly.

Safe boundary reached:
- At 2026-04-30T15:50:15Z, pending dropped from `20,083` to `20,033`.
- At 2026-04-30T15:51:15Z, `F_restart_drain.ready` was written with state `drain_wait`.
- Controlled restart can now be triggered.

Restart trigger result:
- At 2026-04-30T16:13:13Z, the controlled restart gate was rechecked after the H boundary inference fix.
- Gate decision: `approved`
- Gate blockers: `0`
- Focused proof before restart:
  - `python -m py_compile scripts\tools\controlled_restart_gate.py` passed.
  - `PYTHONPATH=.;scripts pytest tests\test_controlled_restart_gate.py tests\test_fpm130_live_cycle.py -q` passed with `9 passed`.
- At 2026-04-30T16:13:42Z, `run_controlled_restart_controller.bat` was run in home-time execute mode.
- Controller outcome: `reboot_command_submitted`
- Final blockers: `0`
- Reboot attempted: `true`
- Restart proof artifact:
  - `out/locks/restart_control/restart_controller.latest.json`

Post-restart validation target:
- Confirm Windows comes back.
- Confirm `AMZ Price List Manager` starts again.
- Confirm Entertainment Trading resumes from the same active run with about `20,033` pending rows, not the original `20,083`.
- Confirm manager chunk size is now `5` and heartbeat updates while F061 is running.

Post-restart MOT result - 2026-04-30:
- Windows came back after the controlled restart.
- `AMZ Price List Manager` restarted and resumed Entertainment Trading from the same active run.
- F pending rows moved from the restart boundary `20,033` down to `19,993`.
- F chunk size is now `5`.
- F manager heartbeat and child status are updating while F061 is running.
- `AMZ Orders` is alive after restart:
  - B supervisor pid `8804`
  - B worker pid `27372`
  - B heartbeat fresh at MOT time.
- Full A015 MOT was run with `--no-toast`.
- Fresh global checklist:
  - rows `197`
  - ok `186`
  - warn `9`
  - fail `2`
- Fresh B checklist:
  - rows `32`
  - ok `30`
  - warn `1`
  - fail `1`
- Fresh H checklist:
  - rows `107`
  - ok `99`
  - warn `8`
  - fail `0`
- H runtime live status is not healthy even though the checklist has no H fail:
  - `H_runtime_status.json` mode `ERROR`
  - run id `20260430T161523Z`
  - `H_run_in_progress.txt` still names `20260430T161523Z`
  - `H_last_finalized_run_id.txt` is still `20260430T155103Z`
  - H launcher is alive, but repeated child launches fail closed with `startup_nonterminal_guard_blocked`
  - root blocker: dead owner on non-terminal H run with no boundary/result proof.
- Recovery attempted:
  - `python scripts\tools\archive_failed_H_run.py --run-id 20260430T161523Z --archive-reason post_restart_dead_owner_recovery_after_home_time_reboot`
  - result: rejected because `boundary_exists=false` and `result_exists=false`
  - this was correct fail-closed behavior.
- Broad recovery dry-run:
  - `python scripts\one_off\HB_safe_recover_background.py --dry-run --timeout-seconds 180 --heartbeat-max-age-seconds 180`
  - result: no mutation; proof not confirmed; H marker preserved.

Current status:
- F price-list manager: live and healthy.
- B/orders: live, with known B health fail still present.
- H/repricing: blocked by stale in-progress ownership marker and not safe to auto-clear from current evidence.
- Overall system: alive but not clean.

Next safe action:
- Keep F manager running.
- Do not manually delete H markers.
- Create a narrow H recovery decision/fix for interrupted run `20260430T161523Z`, either by producing hard proof for that failed run or by adding an approved startup-only archive path with tests.

## Phase 22E - Home-Time Error Repair
Start UTC: 2026-04-30T17:10:55Z

Goal:
- Repair the H home-time blocker without deleting markers by hand.
- Preserve the existing fail-closed behavior for H runs that lack proof.
- Add one narrow startup-only release route for run `20260430T161523Z`, where hard evidence shows:
  - the H owner process is dead
  - the run is still at startup
  - publish did not start
  - a matching stale H lock archive exists
- Diagnose the B token shortage fail from existing artifacts first.

Allowed files for this phase:
- `scripts/tools/archive_failed_H_run.py`
- `scripts/cycles/run_H_pricing_cycle.py`
- `tests/test_archive_failed_h_run.py`
- `tests/test_h_worker_lifecycle_contract.py`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`

Not allowed in this phase:
- No Google Sheets writes.
- No manual deletion of H markers.
- No B scripts while `out/systems/B/live/B_cycle.lock` or `out/B_cycle.lock` is active.
- No local token ledger rewrite unless a B maintenance handoff is obtained and the repair is separately proven.

Tests and isolated proof:
- Run focused tests for the H archive tool.
- Compile the archive tool.
- Recheck that no H core or guarded Python owner is active before applying the archive release.

Live monitoring target:
- `out/systems/H/live/H_run_in_progress.txt`
- `out/systems/H/live/H_run_state.json`
- `out/systems/H/live/H_worker_lifecycle.json`
- `out/systems/H/live/H_failed_run_archived.20260430T161523Z.json`
- `out/systems/H/live/H_runtime_status.json`
- `out/H_cycle.log`

Poll cadence:
- First check at +5 minutes.
- Second check at +10 minutes.
- Then every +15 minutes.
- Stop at +60 minutes.

Success threshold:
- Archive marker exists for run `20260430T161523Z` with startup-stale-lock evidence.
- `H_run_state.json` marks that run as `failed`.
- `H_worker_lifecycle.json` marks that run as `failed`.
- `H_run_in_progress.txt` is cleared only by the archive tool after the marker and failed state are written.
- The H launcher is no longer blocked by `startup_nonterminal_guard_blocked` for that run.

Automatic next step:
- If H releases cleanly, keep monitoring for launcher/runtime recovery evidence and then update this phase result.
- If H does not recover inside the bounded window, record the exact artifact still blocking startup and park as `parked pending next proof window`.
- If B remains failed while B ownership is active, leave B as diagnosed only and use the next safe B maintenance boundary for a separate token repair.

Verification status: Forced proof window required
Changed at: pending code change
Latest health snapshot at: 2026-04-30 post-restart MOT
Next verifier: focused H archive tool tests, then guarded application to run `20260430T161523Z`, then H launcher/runtime artifact monitoring

Phase 22E result:
- Updated UTC: 2026-04-30T17:40:41Z
- H startup blocker repair applied:
  - archived stale startup run `20260430T161523Z`
  - archive marker: `out/systems/H/live/H_failed_run_archived.20260430T161523Z.json`
  - evidence type: `startup_stale_lock_dead_owner`
  - `H_run_state.json` was marked `failed` for that stale run
  - `H_run_in_progress.txt` was cleared by the archive tool after marker/state/worker/terminal writes
- Isolated verification passed:
  - `python -m py_compile scripts/cycles/run_H_pricing_cycle.py scripts/tools/archive_failed_H_run.py tests/test_archive_failed_h_run.py tests/test_h_worker_lifecycle_contract.py`
  - focused pytest: `5 passed`
  - pytest emitted a Windows temp cleanup `PermissionError` after the pass summary; test result still passed.
- Live H proof passed:
  - H launcher started fresh run `20260430T171713Z`
  - terminal truth: `H_run_state.json` state `finalized`, stage `phase1_publish`, publish_status `ok`
  - terminal UTC: `2026-04-30T17:38:40Z`
  - `H_cycle_last_publish_run_id.txt`: `20260430T171713Z`
  - `H_last_finalized_run_id.txt`: `20260430T171713Z`
  - `H_run_in_progress.txt`: cleared after finalization
  - home-time monitor showed no anomalies during the recovered run and observed the next H run `20260430T173925Z`
- Additional H code repair applied:
  - root cause: the H worker lifecycle transition preserved archive-only `failure_code`, `failure_detail`, and `archive_marker_path` fields after a new run started.
  - fix: `scripts/cycles/run_H_pricing_cycle.py` now drops those stale archive fields on core-owned lifecycle transitions.
  - proof: added lifecycle contract coverage in `tests/test_h_worker_lifecycle_contract.py`.
- Residual H live artifact:
  - current live owner process was already running before the lifecycle-field patch loaded.
  - `H_worker_lifecycle.json` still carries stale archive-only `failure_code` while state is `running` for the next live run.
  - This is not blocking H runtime or home-time monitoring, but cleanup of that field is pending the next H owner reload or controlled H pause/resume.
- B status:
  - B owner is active: `out/systems/B/live/B_cycle.lock` heartbeat `2026-04-30T17:40:14Z`.
  - `token_shortages_by_sku` remains `fail`, value `6`.
  - No B script or token-ledger repair was run because B ownership is active and local token-ledger mutation needs a safe B maintenance boundary and explicit repair proof.

Verification status: H stale startup blocker repaired and live loop verification confirmed
Changed at: 2026-04-30T17:40:41Z
Latest health snapshot at: 2026-04-30 post-restart MOT
Next verifier: next H owner reload for worker lifecycle stale-field cleanup; B maintenance boundary for token shortage repair

## Operational Note - BBP Login Persistence
Date: 2026-04-30

Context:
- During the live `stocklist_supplier` F061 scan, BBP dashboard restriction capture degraded to `LOGIN`.
- User manually logged in and the scanner immediately resumed capturing real dashboard values, proven by `Dashboard yes/no => NO` at `2026-04-30 11:53:33`.
- Login requires a mobile phone text, so repeated login prompts are operationally expensive and cannot be treated as a normal unattended step.

Requirement for a future phase:
- Find a stay-logged-in solution if BBP keeps logging out during long scans.
- The solution must avoid repeatedly forcing the user through mobile phone text verification.
- Missing dashboard values caused by `LOGIN` must not become hard fails.
- Rows affected by dashboard `LOGIN` should be marked for targeted rescan, ideally passes/manual-review candidates first.
- If repeated `LOGIN` is detected during a long run, the scanner/process manager should surface a clear operator action such as `BBP login required`, rather than silently continuing to produce missing dashboard evidence.

Potential implementation options to study:
- Preserve and reuse the correct Chrome profile: `C:\Users\Luke\AppData\Local\Chrome_UC136`, `Profile 2`.
- Add a pre-scan BBP login-health probe before starting a long F061 batch.
- Add a repeated-LOGIN detector with a pause/alert threshold.
- Add a dashboard-rescan queue for rows scanned while dashboard state was unavailable.
- Avoid auto-refreshing or clearing profile state in a way that invalidates the BBP session.

Status:
- Parked pending evidence from this long scan.
- Do not interrupt the current F061 run for this unless dashboard `LOGIN` returns and materially affects pass/manual-review evidence.

## Operational Fix - Normal Scanner Login Visibility
Date: 2026-05-07

Context:
- User corrected the intended behaviour: the normal F061 scanner should run as normal.
- If BBP is logged in, scanner browser windows should stay hidden/minimized.
- If BBP is not logged in, the normal scanner window should pop up on screen so the user can log in.
- The separate FPM160 visible-login maintenance browser was the wrong mechanism for this case because it used a different window path.

Root cause:
- F061 saw BBP login/iframe failures, but `FPM130_run_live_cycle.py` only returned a generic child result and discarded the child scanner summary.
- Because `scanner_speed_browser_blocked_rows` was discarded, FPM130 did not write `f061_auth_attention` and did not switch the next normal child to visible mode.
- The window hider also needed to be stopped when FPM130 launches a visible child.

Code changes:
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`: treats BBP login/iframe failures as browser-blocked scan evidence.
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`: returns `BBP_LOGIN_REQUIRED` when dashboard Yes/No is `LOGIN`.
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`: parses the real F061 child summary, records auth attention, logs child `browser_mode`, and stops the window hider for visible children.
- `tests/test_f061_run_legacy_first_checks_local.py` and `tests/test_fpm130_live_cycle.py`: added focused regression coverage.

Proof:
- `python -m py_compile scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py tests\test_f061_run_legacy_first_checks_local.py tests\test_fpm130_live_cycle.py` passed across the edited modules.
- `pytest tests\test_f061_run_legacy_first_checks_local.py::test_f061_marks_bbp_login_and_iframe_failures_as_browser_blocked -q` passed.
- `pytest tests\test_fpm130_live_cycle.py::test_fpm130_parses_child_summary_from_current_stdout_slice tests\test_fpm130_live_cycle.py::test_fpm130_records_auth_attention_then_clears_after_clean_chunk tests\test_fpm130_live_cycle.py::test_fpm130_scanner_child_turns_visible_after_auth_attention -q` passed: `3 passed`.
- Live DHB FPM130 was restarted at a drain boundary and resumed run `fpm_dhb_operator_20260507T083136Z`.
- Live child at `2026-05-07T09:33:03Z` ran normal scanner path with `browser_mode=minimized`, detected `scanner_speed_browser_blocked_rows: 1`, and FPM130 wrote `f061_auth_attention` with `next_child_browser_mode=visible`.
- Next live child at `2026-05-07T09:35:18Z` started normal scanner path with `browser_mode=visible`; no `f_hide_scraper_windows.ps1` process was present in the proof process list.

Status:
- Code fix applied: yes.
- Isolated verification passed: yes.
- Live loop verification confirmed for the visibility handoff: yes.
- Current live scanner: DHB run `fpm_dhb_operator_20260507T083136Z`, pending rows `673` at the visible-child start.

## Planned Fix - Dashboard Yes/No Catchup Gate
Date: 2026-05-07

Problem statement:
- User observed that the dashboard Yes/No catchup options are not operating as part of normal price-list manager flow.
- Entertainment Trading appears to have completed and produced review outputs even though many rows did not get BBP dashboard Yes/No evidence.
- The ongoing requirement is not to patch finished review CSVs downstream. The system must catch missing Yes/No before a clean pass can move onward.

Evidence gathered:
- Completed Entertainment Trading handoff:
  - run `fpm_entertainment_trading_20260430T151417Z`
  - manifest built at `2026-05-06T21:22:35Z`
  - pass review rows: `62`
  - near-miss review rows: `694`
  - hard reject rows: `20007`
- Entertainment Trading pass review currently has `50` rows where `seller_history_dashboard_yes_or_no` is blank/non-YES/NO.
- Entertainment Trading near-miss review currently has `614` rows where `seller_history_dashboard_yes_or_no` is blank/non-YES/NO.
- Read-only F028 dashboard Yes/No rescan plan was run for Entertainment Trading outputs only, without applying a queue:
  - output: `out/analysis_reports/entertainment_trading_dashboard_yes_no_rescan_plan_readonly.csv`
  - summary: `out/analysis_reports/entertainment_trading_dashboard_yes_no_rescan_summary_readonly.csv`
  - output rows: `514`
  - selected-now rows: `50`
  - deferred rows: `464`
  - selected-now queue match rows: `50`
  - selected-now queue missing rows: `0`
- Existing planner:
  - `scripts/one_off/F028_build_dashboard_yes_no_rescan_plan.py`
  - supports read-only planning and optional `--apply-selected`
  - default paths were built around stocklist/latest analysis outputs, not current FPM completed-run handoffs.
- Root cause:
  - F028 is a one-off tool, not part of `FPM150_build_completed_review_pack.py`.
  - FPM150 builds the review handoff even when clean-pass rows have missing dashboard Yes/No.
  - No FPM health/checklist gate currently blocks `ready_to_publish` or downstream listing intake when selected clean-pass Yes/No catchup rows exist.

Implementation plan:
1. Add an FPM-owned dashboard Yes/No catchup planner wrapper.
   - New or extended FPM step should call the existing F028 planning logic using the completed handoff's own pass/near-miss paths and supplier converted/canonical source path.
   - The wrapper must write supplier/run-scoped outputs under the handoff directory or FPM live directory, not only global `out/analysis_reports`.
   - It must be read-only by default.

2. Add a completed-run gate before review handoff is considered publishable.
   - If clean-pass selected-now rows > 0, mark handoff as blocked with reason `dashboard_yes_no_catchup_required`.
   - Do not mark the pass pack as publishable to the operator/latest Amazon listing path while this block exists.
   - Near-miss rows stay deferred unless explicitly included in a manual review/catchup batch.

3. Add a bounded catchup run path.
   - When no F061 active run is in progress, allow the manager to stage/apply a targeted active run containing only selected clean-pass Yes/No catchup rows.
   - The run reason must be `dashboard_yes_no_rescan`.
   - It must preserve backups before queue rewrite.
   - It must not scan the whole supplier list again.
   - It must not run while another supplier scan is active.

4. Rebuild from source evidence, not by masking output.
   - After the targeted catchup scan completes, rebuild the review pack from the updated F061 evidence.
   - The success condition is that selected clean-pass missing Yes/No rows drop to `0`.
   - Do not hand-edit pass/near-miss CSVs to fill missing Yes/No.

5. Add health output.
   - Add an FPM health/check item such as `dashboard_yes_no_catchup_gate`.
   - `ok`: selected clean-pass catchup rows = `0`.
   - `warn`: selected clean-pass catchup rows > `0` and catchup is staged/runnable.
   - `fail`: pass handoff is publishable or listing-intake eligible while selected clean-pass catchup rows > `0`.

6. Damage-control path for Entertainment Trading.
   - Do not publish or list the current Entertainment Trading clean-pass pack as final until the `50` selected rows have been rescanned or explicitly reviewed.
   - Safest recovery is a targeted Entertainment Trading catchup queue for those `50` rows, then rebuild the Entertainment Trading review handoff.
   - The `464` deferred near-miss rows should remain deferred unless the operator wants a separate near-miss catchup batch.

Allowed files for implementation:
- `scripts/one_off/F028_build_dashboard_yes_no_rescan_plan.py`
- `scripts/flows/F/price_list_manager/FPM140_check_review_handoff_ready.py`
- `scripts/flows/F/price_list_manager/FPM150_build_completed_review_pack.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `scripts/flows/F/price_list_manager/_schemas.py`
- FPM tests under `tests/test_fpm*.py`
- F028 tests under `tests/test_f028_build_dashboard_yes_no_rescan_plan.py`
- This plan file

Proof required before completion:
- Focused tests prove a completed run with selected clean-pass missing Yes/No is blocked from publish/listing handoff.
- Focused tests prove near-miss missing Yes/No is deferred by default.
- Focused tests prove the targeted catchup queue contains only selected rows and requires one supplier/run scope.
- Read-only ET proof shows selected-now rows = `50` before catchup.
- After a safe forced F-owned proof window, targeted catchup proof must show:
  - active run reason `dashboard_yes_no_rescan`
  - scanned rows equal selected catchup rows, or truthful failures
  - review pack rebuilt from updated evidence
  - selected clean-pass missing Yes/No rows = `0`

Status:
- Planning complete.
- Code fix not started in this phase yet.
- Current Entertainment Trading state is not considered fully caught up.

## Design - Login Backtrack Queue With Same-Scan Evidence
Date: 2026-05-07

User requirement:
- If a product hits BBP `LOGIN`, it must not be completed as a normal PASS/FAIL/review row.
- Those rows must be bumped up the queue once login is detected.
- The retry/backtrack must not look like an unrelated new scan.
- Backtrack evidence must sit beside the original price scan so checks can prove which prices/costs the Yes/No evidence belongs to.

Plain-English design:
- Treat the first scan as the original price scan.
- If that original scan gets prices but BBP dashboard Yes/No is missing because of `LOGIN`/no iframe, freeze the original scan evidence and mark the row as `login_backtrack_pending`.
- The row is not allowed to complete, publish, enter clean pass, or move to Amazon listing intake while `login_backtrack_pending`.
- Once the user logs in, the same candidate is placed at the front of the F061 queue in a special `login_backtrack` mode.
- The backtrack scan captures only the missing BBP/dashboard evidence needed to finish the original row.
- The final review row is still one scan decision for the original candidate. It is not treated as a different supplier scan or a fresh product discovery row.

Core statuses:
- `pending`: normal unscanned row.
- `processing`: row currently being scanned.
- `login_backtrack_pending`: original scan hit LOGIN and needs missing BBP evidence.
- `login_backtrack_running`: the same candidate is being backtracked after login.
- `completed`: original scan plus any required backtrack evidence is complete.
- `failed`: true product/process failure after allowed attempts, not a login placeholder.

Queue behaviour:
1. F061 detects `BBP_LOGIN_REQUIRED`, `LOGIN`, or `No BBP iframe`.
2. F061 writes the price data it already captured, but marks the row as incomplete:
   - `scan_status=login_backtrack_pending`
   - `scan_reason=login_backtrack_required`
   - `completion_block_reason=bbp_login_required`
3. FPM130 sees that pending login-backtrack count is greater than zero.
4. FPM130 switches the next normal scanner child to visible mode so the user can log in.
5. Once the user has logged in, FPM130 runs `login_backtrack_pending` rows before normal pending rows.
6. If login is still missing, the rows stay in `login_backtrack_pending` and remain at the top of the queue.
7. If Yes/No is captured, F061 merges the backtrack evidence into the original candidate and only then marks it complete.

Evidence model:
- Keep `candidate_id` as the main identity. Do not create a new candidate for the backtrack.
- Keep `run_id`, `supplier_id`, `supplier_sku`, `barcode`, `unit_cost`, and original price fields attached to the original scan.
- Add an append-only backtrack ledger, for audit and checks:
  - proposed file: `out/systems/F/live/f_login_backtrack_evidence_live.csv`
  - one row per backtrack attempt
  - links back to the original candidate/run via `original_run_id`, `candidate_id`, and `original_observed_utc`
  - stores the original price context and the backtrack Yes/No capture side by side

Proposed backtrack ledger columns:
- `backtrack_id`
- `backtrack_observed_utc`
- `original_observed_utc`
- `original_run_id`
- `supplier_id`
- `supplier_name`
- `supplier_sku`
- `barcode`
- `candidate_id`
- `asin`
- `unit_cost`
- `api_live_price`
- `bbp_live_sell_price`
- `bbp_30d_avg_price`
- `break_even`
- `min_sell_price`
- `original_pf`
- `original_status_reason`
- `original_scrape_error`
- `backtrack_attempt_number`
- `backtrack_status`
- `backtrack_error`
- `backtrack_bbp_dashboard_yes_or_no`
- `backtrack_bbp_top_seller_names`
- `backtrack_bbp_top_seller_count`
- `backtrack_bbp_brand_match_seller`
- `backtrack_bbp_brand_match_score`
- `backtrack_bbp_brand_match_flag`
- `backtrack_profile_mode`
- `merged_into_candidate_flag`
- `merge_observed_utc`

How the final row is built:
- Final `feeder_legacy_scrape_evidence_live.csv` remains one current row per candidate.
- For a backtracked row, final fields come from:
  - original scan: price, cost, rank, product identity, ROI/economics, history
  - backtrack scan: BBP dashboard Yes/No and seller dashboard fields
- Add source flags to the current scrape evidence if schema change is approved:
  - `dashboard_yes_no_source=login_backtrack`
  - `dashboard_yes_no_original_observed_utc=<original scan time>`
  - `dashboard_yes_no_backtrack_observed_utc=<backtrack time>`
  - `dashboard_yes_no_backtrack_id=<backtrack id>`
- This avoids output masking because the final row is rebuilt from two real evidence events with a durable link between them.

Completion gates:
- F061 must not mark a row complete if:
  - `scrape_error` is `BBP_LOGIN_REQUIRED`, `LOGIN`, or `No BBP iframe`
  - the row needs dashboard Yes/No for seller-history/pass/manual-review checks
  - `bbp_dashboard_yes_or_no` is not `YES` or `NO`
- FPM150 must not build/publish a clean pass handoff if any selected clean-pass row is still `login_backtrack_pending`.
- F090 Amazon listing intake must hold any pass row where:
  - `seller_history_dashboard_yes_or_no` is blank, and
  - seller-history decision depended on that dashboard signal.

Priority rule:
- `login_backtrack_pending` rows beat normal pending rows for the same supplier.
- They do not interrupt a row already being scanned.
- They do not switch supplier while a supplier run is active unless explicitly approved.
- In a completed-run catchup case, they are staged as a bounded targeted run with `scan_reason=login_backtrack`.

What this changes for Entertainment Trading:
- The `50` clean-pass rows missing Yes/No become `login_backtrack_pending` for the original Entertainment Trading run.
- A targeted backtrack queue scans only those `50`.
- The result is merged back into the original ET evidence/review pack.
- The ET pass pack is then rebuilt and can only move on if selected clean-pass missing Yes/No is `0`.

Health checks:
- `login_backtrack_pending_rows`
  - `ok`: `0`
  - `warn`: pending rows exist and scanner/login path is available
  - `fail`: pending rows exist but pass handoff/listing intake is also eligible
- `login_backtrack_merge_integrity`
  - `ok`: every merged backtrack has matching original candidate/run/price context
  - `fail`: merged Yes/No has no original price scan link
- `login_backtrack_queue_priority`
  - `ok`: login-backtrack rows are selected before normal pending rows
  - `fail`: normal rows are processed while older login-backtrack rows for that supplier remain pending

Implementation phases:
1. Schema and ledger:
   - Add `f_login_backtrack_evidence_live.csv` contract.
   - Add source marker columns to scrape evidence if needed.
   - Add tests proving schema existence and required columns.

2. F061 detection and incomplete status:
   - On LOGIN/no iframe, write original price context and mark row `login_backtrack_pending`, not complete.
   - Write an initial backtrack ledger row with `backtrack_status=blocked_login`.
   - Do not treat LOGIN as normal `SCRAPEFAIL` for completion.

3. FPM130 queue priority:
   - Select `login_backtrack_pending` rows before normal pending rows.
   - Start visible normal scanner if login-backtrack rows exist and the last blocker was login.
   - Stop the hider while visible mode is active.

4. Backtrack capture and merge:
   - Add a `login_backtrack` scan mode that reuses the same candidate/run/price context.
   - Capture missing dashboard Yes/No and seller fields.
   - Merge into current scrape evidence with a backtrack ID.
   - Mark original row complete only after merge succeeds.

5. Review and listing gates:
   - FPM150 blocks clean pass handoff when selected rows are missing Yes/No.
   - F090 holds any pass row still missing required dashboard Yes/No.

6. Entertainment Trading recovery:
   - Build targeted ET backtrack queue for the `50` clean-pass rows.
   - Run only after current DHB ownership is at a safe boundary or completed.
   - Rebuild ET review pack from updated evidence.
   - Prove selected clean-pass missing Yes/No goes from `50` to `0`, or report exact unresolved rows.

Proof required:
- Unit tests:
  - LOGIN creates `login_backtrack_pending`, not completed.
  - Backtrack row preserves original run/candidate/unit cost/prices.
  - Backtrack rows are chosen before normal pending rows.
  - Review handoff blocks while selected clean-pass backtracks remain.
  - Listing intake holds missing Yes/No rows.
- Runtime proof:
  - one controlled login-blocked row is backtracked and merged into same candidate
  - ledger contains original price context and backtrack Yes/No context
  - final review output uses the merged same-candidate evidence

Status:
- Design complete.
- Implementation complete for schema, F061 LOGIN detection, same-scan backtrack ledger, queue priority, visible-browser selection, review handoff block, and Amazon listing intake hold.
- Isolated verification passed on 2026-05-07:
  - `python -m py_compile scripts\flows\F\_schemas.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\price_list_manager\FPM140_check_review_handoff_ready.py scripts\flows\F\price_list_manager\FPM150_build_completed_review_pack.py scripts\flows\F\F090_build_amazon_listing_intake.py tests\test_f061_run_legacy_first_checks_local.py tests\test_fpm130_live_cycle.py tests\test_fpm140_review_handoff_ready.py tests\test_f090_build_amazon_listing_intake.py`
  - `pytest tests\test_f061_run_legacy_first_checks_local.py::test_f061_login_rows_stay_in_original_queue_with_backtrack_ledger tests\test_f061_run_legacy_first_checks_local.py::test_f061_login_backtrack_merges_yes_no_onto_original_price_context tests\test_f061_run_legacy_first_checks_local.py::test_f061_login_backtrack_stress_100_rows_are_prioritized_and_not_completed tests\test_fpm130_live_cycle.py::test_fpm130_prioritizes_login_backtrack_rows_and_uses_visible_browser tests\test_fpm140_review_handoff_ready.py::test_review_handoff_blocks_completed_run_with_login_backtrack_pending tests\test_f090_build_amazon_listing_intake.py::test_f090_pass_missing_required_dashboard_yes_no_is_held_for_backtrack -q`
  - Result: 6 passed. Stress proof: 100 LOGIN rows stayed `login_backtrack_pending`, 100 ledger rows were written, and 0 were completed.
  - `pytest tests\test_f061_run_legacy_first_checks_local.py tests\test_fpm130_live_cycle.py tests\test_fpm140_review_handoff_ready.py tests\test_f090_build_amazon_listing_intake.py -q`
  - Result: 62 passed.
- Live loop verification confirmed on 2026-05-07:
  - Controlled reload marker reached drain boundary at `2026-05-07T10:11:34Z`.
  - Old owner lock cleared, then normal `run_F_price_list_manager_cycle.bat` was started.
  - New owner lock: `pid=7984`, `owner=FPM130_live_cycle`, `start=2026-05-07T10:11:59Z`.
  - New child scanner: `pid=3204`, `supplier_id=dhb`, `browser_mode=minimized`.
  - New-code proof: first post-reload chunk completed with `pending_after=593`, and the F061 summary emitted `login_backtrack_pending_rows`, `login_backtrack_merged_rows`, `login_backtrack_ledger_rows`, and `login_backtrack_evidence_path`.
- Entertainment Trading recovery started on 2026-05-07:
  - ET immutable handoff had `50` pass-review rows missing required dashboard Yes/No.
  - `F028_build_dashboard_yes_no_rescan_plan.py` now reads the exact handoff CSV, writes through the F contract writer in SQL-primary mode, and stages rows as `login_backtrack_pending`.
  - Applied rows: `50`.
  - Active selector proof before restart: `supplier_id=entertainment_trading`, `pending_rows=50`, browser mode `visible`.
  - Live child proof: `pid=9816`, `supplier_id=entertainment_trading`, `browser_mode=visible`, heartbeat `2026-05-07T10:29:00Z`.
  - DHB was deliberately paused for priority ET recovery. DHB backup path: `out/systems/F/inbox/dashboard_yes_no_rescan_backups/20260507T102747Z`.
  - Follow-up is recorded in `project_control/DUE_CHECK_REGISTER.csv` as `F_ET_LOGIN_BACKTRACK_RESTORE_DHB`.

## Current implementation addendum - 2026-05-07 F061 Browser Visibility Hardening

Root causes fixed:
- Persisted browser visibility could be missed if the state file had a UTF-8 BOM before `state=hidden`.
- `Dashboard yes/no ignored non yes/no value` was being treated as a login-required browser signal, even though it is a data-quality/backtrack case.
- A stale parent environment could keep `F061_SHOW_WINDOWS=1` or `FPM_LIVE_HIDE_SCRAPER_WINDOWS=0` for a hidden child.
- The hider-running check could match its own PowerShell checker process and incorrectly skip starting `f_hide_scraper_windows.ps1`.
- `login_backtrack_pending_rows` was being counted as auth attention; only real `scanner_speed_browser_blocked_rows` should request visible Chrome.
- A successful scrape with missing/non-binary dashboard Yes/No could complete instead of staying in backtrack.

Implementation:
- `FPM130_run_live_cycle.py` now treats browser visibility as a binary state:
  - `auth_confirmed` or saved `state=hidden` -> minimized child plus hider.
  - `auth_required` -> stop hider and show the normal scanner Chrome.
- Hidden child startup now forces `F061_SHOW_WINDOWS=0` and `FPM_LIVE_HIDE_SCRAPER_WINDOWS=1`, even if the parent shell has stale visible settings.
- The hider process check excludes its own checker process before deciding whether the hider is already running.
- Auth attention is raised only by real browser-blocked rows, not by backtrack rows alone.
- `F061_run_legacy_first_checks_local.py` now keeps a successful scrape pending if `bbp_dashboard_yes_or_no` is not exactly `YES` or `NO`; those rows get `completion_block_reason=dashboard_yes_no_backtrack_required`.

Proof:
- Compile passed for the edited F061/FPM130 modules and tests.
- Full F proof passed on 2026-05-07:
  - `pytest tests\test_f061_run_legacy_first_checks_local.py tests\test_fpm130_live_cycle.py tests\test_fpm140_review_handoff_ready.py tests\test_f090_build_amazon_listing_intake.py -q`
  - Result: `72 passed`, with 328 existing pandas fragmentation warnings in `FPM140` contract finalization tests.
- Focused proof includes:
  - hidden saved state with BOM starts minimized
  - hidden child overrides stale visible environment
  - hidden child start forces the hider
  - hider-running check excludes its own checker process
  - non-binary dashboard value does not show Chrome
  - backtrack pending without browser block does not request visible Chrome
  - missing dashboard Yes/No stays pending and is not counted as browser blocked
- Live proof after final reload:
  - owner pid `26844`, start `2026-05-07T11:15:37Z`
  - child pid `5612`, supplier `entertainment_trading`, `browser_mode=minimized`, `browser_visibility=hidden`
  - hider helper pid `27488` running `f_hide_scraper_windows.ps1`
  - live stderr shows `BBP login skipped: already authenticated` and `Dashboard yes/no => NO`
  - ET active queue had `11` `login_backtrack_pending` rows remaining at proof time.

Next move:
- Continue ET until `out/systems/F/inbox/supplier_price_list_active_run.csv` has `0` `entertainment_trading/login_backtrack_pending` rows.
- Then restore/resume DHB from `out/systems/F/inbox/dashboard_yes_no_rescan_backups/20260507T102747Z` if DHB has not already resumed.
- Durable follow-up remains `project_control/DUE_CHECK_REGISTER.csv` row `F_ET_LOGIN_BACKTRACK_RESTORE_DHB`, first check due `2026-05-07T11:30:00Z`.

Final operational proof:
- ET active backtrack queue reached `0` rows on 2026-05-07.
- ET backtrack ledger is still preserved in `out/systems/F/live/f_login_backtrack_evidence_live.csv`:
  - ledger rows: `50`
  - merged rows: `45`
  - historical missing dashboard Yes/No attempts: `4`
  - unresolved dashboard Yes/No rows: `1`
- The unresolved ET row is not treated as merged/completed; it remains a held evidence issue in the backtrack ledger.
- DHB was restored from `out/systems/F/inbox/dashboard_yes_no_rescan_backups/20260507T102747Z` using the F contract writer in SQL-primary CSV-export mode.
- Restored DHB state:
  - supplier: `dhb`
  - run_id: `fpm_dhb_operator_20260507T083136Z`
  - active rows restored: `548`
  - first resumed chunk completed and reduced active rows to `543`
- Stale reload markers were removed:
  - `out/systems/F/price_list_manager/live/f061_visible_login.requested`
  - `out/systems/F/price_list_manager/live/F_restart_drain.ready`
- FPM130 restarted normally:
  - owner pid `5680`
  - active supplier `dhb`
  - child pid `10048` then next child `22172`
  - child status `browser_mode=minimized|browser_visibility=hidden`
  - hider helper pid `27488`
- Live logged-in proof from the restarted DHB scan:
  - `BBP login skipped: already authenticated`
  - `Dashboard yes/no => NO`
  - `scanner_speed_browser_blocked_rows=0`
  - no `f061_visible_login.requested` file exists after the chunk.
- Durable due-check row `F_ET_LOGIN_BACKTRACK_RESTORE_DHB` is marked `completed/pass` in `project_control/DUE_CHECK_REGISTER.csv`.
- The remaining ET unresolved row is recorded as durable follow-up `F_ET_DASHBOARD_YES_NO_UNRESOLVED_REVIEW`, due `2026-05-08T09:00:00Z`, using `out/systems/F/live/f_login_backtrack_evidence_live.csv` as the source artifact.

Current next move:
- DHB is running under normal FPM ownership.
- No user action is needed now; the unresolved ET row must not be published unless its Yes/No is later resolved or explicitly classified as a manual-review exception.

## Current implementation addendum - 2026-05-07 Binary Scanner State Machine

Purpose:
- Remove runtime judgement from scanner browser/backtrack decisions.
- Use machine-readable states only:
  - `AUTH_STATE_LOGGED_IN`
  - `AUTH_STATE_LOGIN_REQUIRED`
  - `DASHBOARD_YES_NO_YES`
  - `DASHBOARD_YES_NO_NO`
  - `DASHBOARD_YES_NO_MISSING`
  - `NEEDS_LOGIN_RESCAN`
  - `NEEDS_YESNO_RESCAN`
  - `PENDING`
  - `DONE`
  - `UNRESOLVED`

Implementation:
- Added `scripts/flows/F/_scanner_state.py` as the shared binary decision layer.
- `FPM130_run_live_cycle.py` now uses the shared layer for:
  - auth log text -> `LOGGED_IN` or `LOGIN_REQUIRED`
  - auth state -> hidden or visible browser
  - active row state -> whether visible browser is allowed
  - queue priority: login rescan first, Yes/No rescan second, normal pending third
- `F061_run_legacy_first_checks_local.py` now uses the same dashboard Yes/No classifier and queue-priority function.
- `login_backtrack_pending` is no longer enough by itself to show Chrome.
- Only rows with `completion_block_reason=bbp_login_required`, a persisted `auth_state=LOGIN_REQUIRED`, or a real browser-blocked chunk can show Chrome.
- Rows with `completion_block_reason=dashboard_yes_no_backtrack_required` stay hidden unless the scanner actually sees login required during that scan.
- Browser visibility state file now records both legacy and binary fields:
  - `state=hidden`
  - `browser_state=HIDDEN`
  - `auth_state=LOGGED_IN`

Proof:
- Compile passed:
  - `python -m py_compile scripts\flows\F\_scanner_state.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\F061_run_legacy_first_checks_local.py tests\test_f_scanner_state.py tests\test_fpm130_live_cycle.py tests\test_f061_run_legacy_first_checks_local.py`
- Focused proof passed:
  - `pytest tests\test_f_scanner_state.py tests\test_fpm130_live_cycle.py tests\test_f061_run_legacy_first_checks_local.py -q`
  - Result: `61 passed`.
- Wider F proof passed:
  - `pytest tests\test_f_scanner_state.py tests\test_f061_run_legacy_first_checks_local.py tests\test_fpm130_live_cycle.py tests\test_fpm140_review_handoff_ready.py tests\test_f090_build_amazon_listing_intake.py -q`
  - Result: `77 passed`, with the same 328 existing pandas fragmentation warnings in `FPM140` contract finalization tests.
- Live reload proof:
  - reload requested at `2026-05-07T11:53:35Z`
  - old owner pid `5680` drained at `2026-05-07T11:54:32Z`
  - old lock cleared before restart
  - new owner pid `27332`, start `2026-05-07T11:55:04Z`
  - child pid `2764`, supplier `dhb`, `browser_mode=minimized`, `browser_visibility=hidden`
  - binary state file: `state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN`
  - first new-owner chunk completed at `2026-05-07T11:58:18Z`
  - chunk summary: `processed_rows=5`, `pending_rows=523`, `scanner_speed_browser_blocked_rows=0`, `dashboard_yes_no_unresolved_rows=0`
  - no `f061_visible_login.requested` file existed after proof.

Current next move:
- DHB continues under normal FPM ownership.
- No user action is needed now.
- The only ET follow-up is the durable unresolved-row review already recorded as `F_ET_DASHBOARD_YES_NO_UNRESOLVED_REVIEW`.

## MOT Auth Attention Visibility Fix - 2026-05-11T08:55Z

Trigger:
- Full MOT found due check `F_AUTH_ATTENTION_VISIBLE_ON_BLOCK` still open.
- Live events showed repeated `f061_auth_attention` rows with `status=deferred_login_mode` and `next_child_browser_mode=minimized`.
- This contradicted the F061 scanner login rule: real BBP/Amazon login-required evidence must surface the next normal scanner-owned browser, not keep hidden scanning indefinitely.

Root cause:
- `FPM130_run_live_cycle.py` defaulted `FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION` to off.
- Therefore `scanner_speed_browser_blocked_rows > 0` wrote hidden/deferred auth attention unless the environment flag was manually set.

Changed files:
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `tests/test_fpm130_live_cycle.py`
- `project_control/F_PRICE_LIST_SCANNER_LOGIN_MODE_DESIGN.md`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- this coding plan

Implementation:
- Default auth-attention handling is now visible unless `FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION=0` is explicitly set.
- The opt-out path remains for emergency hidden mode.
- The fix does not open a separate Chrome window and does not use `FPM160_f061_visible_login_maintenance.py`.

Proof target:
- Isolated test: focused FPM130 tests must prove blocked browser rows now request visible next child by default.
- Live proof: after a fresh FPM130 owner loads the patch, the next `scanner_speed_browser_blocked_rows > 0` event should write `f061_auth_attention status=attention_needed` with `next_child_browser_mode=visible`, and the next `f061_child_status.txt` should show `browser_mode=visible`.
- If live proof fails: inspect `out/systems/F/price_list_manager/live/live_cycle_events.csv`, `f061_child_status.txt`, and `f061_browser_visibility_state.txt`; then fix the earliest FPM130 decision branch that still writes minimized mode.

Proof status - 2026-05-11T09:07Z:
- Code fix applied: yes.
- Isolated verification passed: `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\_scanner_state.py`.
- Focused regression passed: `python -m pytest tests\test_f_scanner_state.py tests\test_fpm130_live_cycle.py tests\test_f061_run_legacy_first_checks_local.py tests\test_f_legacy_webscrape_money_input.py -q` -> `106 passed`.
- Live owner reload: old run `fpm_live_20260511T011932Z` drained at `2026-05-11T08:57:19Z`; fresh owner `fpm_live_20260511T085741Z` started at `2026-05-11T08:57:42Z` after the patch.
- Fresh owner evidence: chunks succeeded through `2026-05-11T09:06:16Z`; pending rows moved from `21393` to `21343`.
- Live loop verification confirmed: post-reload event `2026-05-11T09:19:36Z` wrote `f061_auth_attention status=attention_needed`, `rows=1`, and `next_child_browser_mode=visible`.
- Script-owned browser visibility proof: `f061_browser_visibility status=visible` appeared at `2026-05-11T09:21:51Z` with reason `auth_required`, and `f061_child_status.txt` showed `browser_visibility=visible` for the normal F061 child.
- Field interpretation: `browser_mode=minimized` is the child startup mode; `browser_visibility=visible` is the live window state after auth-required evidence surfaced the script-owned browser.
- Cleanup behavior observed: a later clean child wrote `f061_auth_attention status=cleared` at `2026-05-11T09:22:38Z`, and subsequent hidden/minimized scanning is normal after the auth attention clears.
- Durable follow-up closed: `project_control/DUE_CHECK_REGISTER.csv` row `F_AUTH_ATTENTION_VISIBLE_ON_BLOCK` is now `completed/pass`.

## 3) Global Completion Rule
- A phase is not complete until the phase status line is updated with factual proof.
- Test-mode proof must reconcile row counts before real scanner integration.
- Live F061 proof must use a safe forced proof window, not a mid-run check.
- Do not use next scheduled cycle wording when a safe forced proof window exists.
- If monitoring expires, record the exact parked condition and exact resume trigger.

## DHB Forward Progress Stall - 2026-06-06

Trigger:
- Luke reported that the price-list scanner was still on DHB after being on DHB yesterday.
- Manager evidence showed the live scanner process was alive, but repeated tiny DHB chunks were not reducing pending work cleanly.
- Recent live events showed `scanner_chunk` success rows followed by blocked `f061_memory_import` evidence, so the scanner could look busy without useful forward movement.

Manager change:
- F MOT now checks forward progress for the active supplier, not just scanner heartbeat.
- Repeated scanner chunks over the threshold with no meaningful pending-count drop now fail `f_live_owner_status` as `running/supplier_progress_stalled`.
- The work is visible through job reference `F-SCANNER-PROGRESS`.

Worker package:
- Created `F_REPAIR_PACKAGE_F_DHB_FORWARD_PROGRESS_STALL_20260606.md`.
- Job reference: `F-DHB-FORWARD-PROGRESS`.
- The package allows bounded F scanner code/tests for the no-progress loop.
- It forbids live F061 runs, restarts, queue edits, supplier switching, output rewrites, Sheets, prices, DB alignment, deletion, and separate Chrome login.

Current proof status:
- Manager-code tests and read-only F MOT retest are required after this note.
- Live scanner repair remains not yet proven until a future approved F proof window.

### PC-usability pause - 2026-06-06

Trigger:
- Luke reported the PC was still lagging and was going out for about 2 hours.

Action taken:
- Closed an unrelated Diet Planner Chrome window.
- Confirmed Streamlit UI ports 8501-8505 had no listeners.
- Changed the main manager heartbeat from every 15 minutes to every 30 minutes.
- Created the F-only maintenance marker `out/systems/F/price_list_manager/live/f061_visible_login.requested`.

Marker reason:
- `user_pc_unusable_visibility_loop_paused`.

Proof:
- `out/systems/F/price_list_manager/live/live_cycle_status.csv` reached `state=drain_wait` at `2026-06-06T11:41:43Z`.
- The same row showed `pending_rows=5489`, `last_action=restart_drain`, `last_action_status=ready`, `chunk_rows=25`, and `drain_ready=1`.
- The active F061 browser child process cleared after the drain boundary.
- PID 31944 was not running.
- No Streamlit UI listener was active.

Status:
- Parked in safe F drain wait for PC relief.
- This is not a queue edit, price change, Sheet write, DB alignment, output deletion, or worker restart.

Resume trigger:
- When Luke returns or PC load is stable, clear only the F-only maintenance marker through the controlled FPM160 clear path.
- Then confirm FPM130 leaves `drain_wait` and resumes without queue edits or process killing.

Failure path:
- If CPU remains high after Codex quiets down, investigate non-F processes first before touching F again.
