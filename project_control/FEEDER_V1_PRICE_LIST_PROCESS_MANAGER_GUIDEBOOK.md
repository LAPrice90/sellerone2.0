# Feeder v1 Price List Process Manager Guidebook

Date: 2026-04-30

## Purpose
This guidebook defines the upstream process manager for supplier price lists.

It sits between Supplier Discovery price-list acquisition and the F scanner.

It answers:
- what price lists exist
- which supplier each list belongs to
- when each list was received
- which rows are new, changed, skipped, or scan-ready
- which supplier batch should be handled next
- whether the live scanner can safely receive a batch

## Core Rule
The manager is not the scanner.

Until the controlled handoff phase is approved and proven:
- it must not auto-start F061
- it must not replace the active F061 queue
- it must not interrupt a running scan
- it must produce recommendations and test-mode outputs only

## F061 Login/Auth Attention Rule
When the live F061 scanner itself reports BBP/Amazon login-required browser blockage, the recovery path must stay inside the normal scanner-owned child browser.

Required behavior:
- keep affected rows in the active queue as login-backtrack work
- make the next normal F061 child visible by default from FPM130
- use the normal BBP Chrome profile, not a separate maintenance browser
- let the operator complete login in that script-owned browser
- after authentication, replay and merge/backdate the login-backtrack rows before review handoff

Do not use `FPM160_f061_visible_login_maintenance.py open` for this recovery unless the operator explicitly asks for a separate maintenance browser. Hidden repeat scanning after `scanner_speed_browser_blocked_rows > 0` is not an acceptable default because it parks login rows without giving the operator a browser to fix the session.

## F Scanner Production-Line Snapshot Rule
The scanner now has a v1 production-line snapshot layer.

Plain-English model:
- the current live scanner is still the boss
- each product is treated like a box moving through stations
- each station writes a finished handoff file before the next station can touch it
- broken or unfinished handoffs stop at the station where the truth is first known

Current v1 behavior:
- `FPM130` remains the only live coordinator
- `FPM180_build_production_line_run.py` writes stage snapshots after successful scanner chunks
- snapshots are written under `out/systems/F/price_list_manager/pipeline_runs/<supplier_id>/<run_id>/`
- snapshots do not rewrite the active F061 queue yet
- browser work remains single-worker until the staged proof is clean

Each production-line stage writes:
- `rows.csv`
- `next_stage_input.csv`
- `status.csv`
- `manifest.csv`

The stage order is:
1. `intake_enrichment`
2. `catalog_identity`
3. `pricing_api`
4. `fee_hazmat_api`
5. `browser_webscrape`

Handshake rules:
- every stage uses temp-write then publish-on-complete behavior
- downstream stages read only completed manifests
- input rows must equal passed rows plus blocked rows plus retry rows
- API throttling or browser login evidence must stay as retry work, not a false product fail
- F061 login-required rows must stay in script-owned Login Mode, not a separate Chrome workaround

Operator-ready rule:
- `FPM150` raw candidate output is not user-ready
- `FPM155` is still the final AI gate that creates the operator-ready `manifest.csv`
- New Product Review and F090 must read only AI-gated pass rows

## Process Flow
1. Read supplier registry.
2. Check supplier acquisition method.
3. Acquire or wait for a price-list source.
4. Store each received file as its own batch.
5. Convert batch to universal supplier format.
6. Compare batch rows to existing scan memory.
7. Mark rows as scan-now, skip-cooldown, skip-unchanged, or blocked.
8. In test mode, feed scan-now rows to a placeholder scanner.
9. Update barcode scan memory from results.
10. Produce the next recommended action.

## Operator Queue Controls
Queue controls are test-mode only until live F061 handoff is approved.

Control file:
- `out/systems/F/price_list_manager/test_mode/queue_controls.csv`

Allowed states:
- `normal`: no override
- `paused`: remove that supplier from next-action selection
- `prioritised`: promote that supplier ahead of normal candidates

Rules:
- paused suppliers must remain visible in the dashboard as `Paused`
- prioritised suppliers must remain visible in the dashboard as `Prioritised #n`
- controls affect only the manager recommendation
- controls must not write live F061 files
- after changing controls, rebuild the next-action decision and dashboard
- Streamlit buttons may write these controls, but only through the same test-mode control path
- Streamlit button clicks must rebuild the staged handoff preview in `stage_only` mode only

Command:
- `python scripts\flows\F\price_list_manager\FPM080_set_queue_control.py --supplier-id heo --control-state prioritised --priority-rank 1 --reason "operator priority"`
- `python scripts\flows\F\price_list_manager\FPM080_set_queue_control.py --supplier-id heo --control-state normal`

## Operator UI Style
The price-list queue is part of the existing operator workspace.

Style rules:
- use compact rows, not large dashboard cards
- use grey column headers and dark row separators
- keep Pause/Prioritise controls inside the supplier row
- show source method, file state, control state, and scan counts in one scan-friendly line
- use dark operator warning rows for missing manual files
- show F061 staged handoff readiness and approval state in the same queue page
- approval controls may write test-mode approval records only
- keep backend AI QA tables out of the normal operator navigation
- `New Product Review` is the human card review page only
- `Product Listing Profile Review` is where Amazon listing draft/profile work belongs
- stale backend AI QA page links must redirect back to `New Product Review`

## Supplier Source Types
### API Pull With CSV Link
Use for suppliers where the source is a stable machine-readable URL, even if the response is just a CSV file.

First example:
- Shure Cosmetics
- source type: `api_pull`
- source subtype: `csv_link`
- source URL: `https://aux.shure-cosmetics.co.uk/pricelist/`
- existing converter: `scripts/flows/F/suppliers/shure_cosmetics.py`

Large keyed CSV example:
- Stax
- source type: `api_pull`
- source subtype: `csv_link`
- source URL: `https://www.staxtradecentres.co.uk/feeds/1.3/product.csv?key=rte4adf6rv&method=button`
- converter: `scripts/flows/F/suppliers/stax.py`
- special rule: row 1 is feed metadata, row 2 is the real product header, and row 3 can be feed metadata before product rows

Manager behavior:
- pull or stage the CSV as a batch
- hash the source file
- convert with the supplier converter
- keep live F061 handoff disabled until the controlled handoff phase

### Manual Request
Use for suppliers who provide lists only after asking.

Manager behavior:
- track when the next request is due
- produce a user task when request is due
- do not scan old monthly files again just because scanner capacity exists

Recovery-priority manual example:
- Entertainment Trading
- current folder: `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Inbox`
- processed source artifact: `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Processed\Stocklist_20260430T142821Z_e9a97b901a.xlsx`
- source SHA256: `DC6458F69D43F50505C17E4E3BC13D2237F1A6EDAD765947740B5AE44153AE9C`
- source columns: `ItemCode`, `ItemName`, `Department`, `Platform`, `Brand`, `CodeBars`, `Available`, `EUR`
- mapping rule: SKU from `ItemCode`, title from `ItemName`, barcode from `CodeBars`, availability from `Available`, cost from `EUR` converted to GBP
- current proof: source rows `42,717`, scan-ready rows `42,449`, held rows `268`
- held reason counts: `invalid_barcode_format=214`, `missing_barcode=54`
- F061 recovery proof: old run `stocklist_supplier_webscrape_reset_20260429T164504Z` had `20,116` pending rows, `20,083` matched scanner-safe rows, `33` pending-held rows, and `0` unmatched pending rows
- current resume queue: `20,083` rows, not the full `42,449` scan-ready source
- queue state: `Recommended`, `Prioritised #1`
- live F061 handoff remains disabled until the controlled runner proof

### Email Attachment
Use for suppliers who send files regularly.

Manager behavior:
- save each attachment as a batch
- dedupe exact duplicates by file hash
- scan only new, changed, or cooldown-expired rows

TD Synnex setup note:
- source type: `email_attachment`
- source subtype: `daily_email`
- inbox folder: `C:\Users\Luke\Desktop\SellerOne Price Files\TD Synnex\inbox`
- adapter: `scripts/flows/F/suppliers/td_synnex.py`
- supported attachment suffixes: `.zip`, `.tsv`, `.txt`, `.csv`
- daily email shape: zip attachment with one TSV price file inside
- Gmail source: label `TD Synnex`
- OAuth files:
- `secrets\price_list_manager\gmail_client_secret.json`
- `secrets\price_list_manager\gmail_token.json`
- on-demand fetch command:
- `python -m scripts.flows.F.price_list_manager.FPM016_fetch_gmail_email_sources --supplier-id td_synnex --target-date YYYY-MM-DD`
- parked-supplier rule: this named-supplier command may fetch TD Synnex from the registry while the supplier remains parked; the normal live cycle still only sees suppliers that the registry marks active.
- zip handling: the manager imports the zip as the source artifact, extracts the single supported price file into test-mode extracted sources, converts the extracted TSV, and archives the original zip into `Processed`
- status as of 2026-05-19: OAuth login and real Gmail zip download succeeded. Real TD Synnex file converted to `103543` source rows, `103457` cost-valid rows, `86` missing-cost holds, and `57971` timeout/memory eligible scan rows after the 21-column TSV schema fix.

Tropicana Wholesale setup note:
- source type: `email_attachment`
- source subtype: `daily_email`
- inbox folder: `C:\Users\Luke\Desktop\SellerOne Price Files\Tropicana Wholesale\inbox`
- adapter: `scripts/flows/F/suppliers/tropicana_wholesale.py`
- supported attachment suffixes: `.xlsx`, `.xls`
- Gmail source: label `Tropicana`
- on-demand fetch command:
- `python -m scripts.flows.F.price_list_manager.FPM016_fetch_gmail_email_sources --supplier-id tropicana_wholesale --target-date YYYY-MM-DD`
- status as of 2026-05-19: Gmail download succeeded for `StockExport_190526_090831.xlsx`. The workbook is a stock export, not a price list. It has brand, SKU, title, quantity, product group, and barcode, but no cost column. Import keeps all rows held with explicit reasons, mainly `missing_cost`, and does not feed them to F061.

ABGee setup note:
- source type: `email_attachment`
- source subtype: `daily_email`
- inbox folder: `C:\Users\Luke\Desktop\SellerOne Price Files\ABGee\inbox`
- adapter: `scripts/flows/F/suppliers/abgee.py`
- supported attachment suffixes: `.xlsx`, `.xls`, `.csv`, `.zip`
- Gmail source: label `ABGee`
- on-demand fetch command:
- `python -m scripts.flows.F.price_list_manager.FPM016_fetch_gmail_email_sources --supplier-id abgee --target-date YYYY-MM-DD --lookback-days 7`
- pack rule: ABGee unit codes such as `PK12` mean the source cost is a pack cost for 12 individual units. The converter stores the original pack cost and divides it into the scanner `unit_cost`.
- status as of 2026-05-22: Gmail download and import succeeded for the latest available stock feed. The file converted to `8745` source rows, `5770` converter-valid rows, `2975` held rows, and `5307` scanner-eligible rows after memory checks.

### API Pull
Use for suppliers with API access.

Manager behavior:
- call only when due
- store raw response/output
- create a batch only when source content changes
- live manager refresh path: source check, URL downloads, API fetches, Gmail fetches, import, enrichment, next-action scoring, report, dashboard

First authenticated API example:
- Heo
- source type: `api_pull`
- source subtype: `api`
- source URL: `https://integrate.heo.com/retailer-api/v1/catalog`
- credential file: `secrets/price_list_manager/heo_api.json`
- credential file is local and ignored by git
- adapter: `scripts/flows/F/suppliers/heo.py`
- fetch step: `scripts/flows/F/price_list_manager/FPM014_fetch_api_sources.py`
- special rule: fetch products and prices separately, join by product number, and expand every barcode into its own row

SOAP API example:
- CLF
- source type: `api_pull`
- source subtype: `api`
- source URL: `http://services.clfdistribution.com:8080/CLFWebOrdering/WebOrdering.asmx`
- adapter: `scripts/flows/F/suppliers/clf.py`
- special rule: fetch all product codes first, then request product data in SKU batches
- credential file: `secrets/price_list_manager/clf_api.json`
- credential file is local and ignored by git
- authentication rule: fetch a fresh `GetAuthenticationToken` token from username/password at run time, then use that token for `GetProductCodes` and `GetProductData`
- parser hardening: CLF can return malformed XML text with raw ampersands inside product descriptions, so the adapter repairs broken ampersands before XML parsing
- status as of 2026-05-19: live API probe succeeded with `16457` SKUs, `16456` source rows with barcodes, `16172` converter-valid scan-ready rows, and `284` held rows.
- status as of 2026-05-22: CLF API fetch now preserves product description as scanner title. A refreshed CLF batch imported `16528` source rows, `16246` converter-valid rows, `282` held rows, and `16230` scanner-eligible rows. The older CLF batch without titles is marked `superseded`, and superseded batches are explicit queue skips.

### URL Download Or Local File
Use for simple pull/copy suppliers and fixture-safe testing.

Manager behavior:
- store the source artifact
- convert through the supplier-specific converter
- keep conversion separate from scanning decisions

EUR-priced CSV-link example:
- We Stock Lots
- source type: `api_pull`
- source subtype: `csv_link`
- source URL: `https://westocklots.com/api/export/stocklist/?format=csv`
- adapter: `scripts/flows/F/suppliers/we_stock_lots.py`
- special rule: source prices are EUR and must be converted to GBP during supplier conversion
- rate rule: current online EUR to GBP rate first, then local FX cache fallback
- current blocker: endpoint returns `401 Unauthorized` without the logged-in website session, so the UI shows the source as blocked until authentication is available
- current operating decision: parked by user decision on 2026-04-30 because the supplier is not worth the authentication effort right now

## Batch Statuses
Allowed statuses:
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

Rules:
- one batch can be active in a scanner handoff at a time
- a newer batch can supersede an older unscanned batch only after the older batch is recorded as superseded
- batch counts must reconcile before any handoff recommendation

## Row Eligibility
Allowed values:
- `scan_now`
- `skip_cooldown`
- `skip_unchanged`
- `blocked_missing_data`

Rules:
- new rows are eligible
- changed cost rows are eligible when supplier offer memory says the old result no longer applies
- exact prior `PASS` supplier-offer rows are skipped because the product has already passed for the same barcode and cost
- unchanged rows inside cooldown are skipped
- missing required data is blocked with a reason

## Cooldown Policy
Start simple.

Policy file:
- `config/feeder/f_scanner_timeout_policy.csv`

Phase 23A status:
- the policy file exists and is operator-editable from the Streamlit Price List Queue page
- F061 reports policy-file health rows in `out/systems/F/live/feeder_legacy_sheet_health.csv`
- phase 23B wired approved policy values into F061 timeout calculation and manager next-action skip decisions
- F061 live proof on 2026-05-01 showed policy-based timeouts replacing the old 12 hour value
- manager skip-decision wiring has isolated proof; live manager skip proof waits for the next batch-selection boundary because Entertainment Trading is currently resuming an active scan

Approved balanced v3 cooldowns:
- operating reason: 90 days is the standard wait for failures that can plausibly recover over a normal market cycle; 180 days is the high end for slow-moving evidence; 365 days is reserved for hazmat or FBA eligibility
- `NOASIN`: 90 days
- `OVER50K`: 90 days
- `NOCOST`: until cost changes, max 90 days
- `ROIFAIL`: until cost changes, max 90 days
- `LOWROI`: until cost changes, max 60 days
- `SCRAPEFAIL`: 30 days
- `RESCAN`: 30 days for technical retry rows
- `PRICEHISTORYFAIL`: 180 days
- `HAZMATFAIL`: 365 days
- `BRANDFAIL`: 180 days
- `NODATE` or `REVIEWFAIL`: 90 days
- `LOWSALESFAIL`: 90 days
- `SELLERHISTORYFAIL`: 180 days
- `FAIL`: 90 days and investigate why generic

Later improvement:
- history cooldown can become dynamic by calculating when the newest blocking evidence leaves the 12-month window

## Required Health Checks
Minimum health checks:
- supplier IDs are unique
- active suppliers have an acquisition method
- each batch has a source path and hash
- raw, valid, held, and batch-row counts reconcile
- placeholder scanner result counts reconcile
- cooldown memory keys are unique
- unknown fail codes are held safely
- live F061 handoff is disabled in test mode
- F061 owner state is known before any future live handoff

## Test-Mode Proof
The first proof must use 10 fake barcodes and fake scanner results.

Required proof:
- source rows = 10
- converted rows = 10
- placeholder results = 10
- memory updates = 10
- unresolved rows = 0
- health `FAIL` count = 0
- no live F061 files changed

## Next-Action Report Proof
The process manager must explain the next recommendation before any live handoff exists.

Required report outputs:
- `next_action_report.md`
- `next_action_skip_reasons.csv`

Required report content:
- recommended supplier and batch
- estimated rows to scan
- estimated rows skipped
- skip reasons by supplier
- `safe_to_handoff_flag=0` until Phase 6 is approved
- clear statement that live F061 handoff is disabled

Current example proof:
- Active playground suppliers include Stax, Heo, Shure Cosmetics, Bliss Distribution, DHB, CLF, Entertainment Trading, and ABGee.
- Stax is the recommended next test scan.
- Stax has `24231` scan-ready rows and `2970` skipped or held rows.
- Heo has `7754` scan-ready rows and `165` skipped or held rows.
- Bliss has `1526` scan-ready rows and `686` skipped or held rows.
- DHB has `788` scan-ready rows and `171` skipped rows.
- Shure Cosmetics has `10` placeholder-processed rows and no current scan rows.
- ABGee has `5307` scanner-eligible rows and `3438` skipped or held rows from the 2026-05-22 Gmail stock-feed import.
- We Stock Lots, Rashmian, and Tropicana Wholesale remain parked until later API, email, login, or manual-source work is explicitly reactivated. CLF is reactivated as an API supplier after the 2026-05-19 authenticated SOAP proof. ABGee is reactivated as a daily Gmail attachment supplier after the 2026-05-22 stock-feed import proof.

## F061 Staged Handoff Guard
Before a manager batch can reach F061, the manager must build a staged handoff and prove the live scanner state.

Required staged outputs:
- `f061_handoff_staged_active_run.csv`
- `f061_handoff_staged_run_state.csv`
- `f061_handoff_preview.csv`
- `f061_handoff_approvals.csv`

Required guard behavior:
- stage rows only when F061-required fields are present
- block live apply when F061 has pending active rows
- block live apply when F061 run state is `running`
- block live apply when confirmation is missing
- block live apply when exact supplier/batch approval is missing
- keep live F061 writes disabled until an approved proof window

Current example:
- Bliss Distribution stages `1526` rows.
- Live apply is blocked because F061 is busy with `stocklist_supplier`.

Approval rule:
- technical readiness and approval are separate
- `technical_ready_flag=1` means the staged files are shaped correctly and F061 is idle
- `approval_state=approved` must match the exact supplier and batch
- `live_apply_allowed=1` can only appear when both technical readiness and approval are true
- this still does not execute live apply in the current phase

## F061 Guarded Apply
The guarded apply step is separate from staging.

Script:
- `scripts/flows/F/price_list_manager/FPM100_apply_f061_handoff.py`

Default behavior:
- preview only
- writes `f061_handoff_apply_preview.csv`
- does not write live F061 files

Live apply behavior:
- requires `--apply-live`
- requires `--confirm-approved-handoff`
- requires the latest staged preview to be technically ready and approved
- re-checks that F061 is idle immediately before writing
- snapshots current live F061 input files before writing staged rows

Required outputs:
- `f061_handoff_apply_preview.csv`
- `f061_handoff_apply_backups.csv`
- `f061_handoff_backups/<backup_id>/manifest.csv`

Current real status:
- Stax is staged with `24231` rows.
- Apply is blocked because F061 is still busy and the exact batch is not approved.
- No live F061 files were written by the preview-only run.

## Live Manager Ownership And Restart
The live price-list manager owner is:
- `run_F_price_list_manager_supervisor.bat`
- `scripts/flows/F/price_list_manager/FPM170_supervise_live_cycle.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- Windows task `AMZ Price List Manager`

Ownership rules:
- only one F manager owner may run at once
- Task Scheduler owns the supervisor; the supervisor owns/restarts the manager
- the supervisor heartbeat is `out/systems/F/price_list_manager/live/fpm_live_supervisor_state.txt`
- the owner lock is `out/systems/F/price_list_manager/live/live_cycle.lock`
- if F061 has pending active rows, the manager resumes that run before selecting anything else
- the manager must not replace `supplier_price_list_active_run.csv` while it contains pending rows
- default chunk size is `50` rows until restart/resume proof is complete

Restart rules:
- controlled restart creates `out/locks/maintenance.requested`
- F manager finishes its current chunk, saves F061 state, then writes `out/systems/F/price_list_manager/live/F_restart_drain.ready`
- controlled restart gate blocks reboot while F manager is active and not at the drain boundary
- after the PC starts again, Task Scheduler starts `AMZ Price List Manager`
- the manager resumes from `supplier_price_list_active_run.csv` and `supplier_price_list_run_state.csv`
- if `F_restart_drain.ready` is left behind after the maintenance request is gone, treat it as stale restart debris; the supervisor should relaunch the manager so FPM130 can clear the marker during normal startup

Health and alert rules:
- live health output is `out/systems/F/price_list_manager/live/live_cycle_health.csv`
- alert if `fpm_live_cycle_status=fail`
- warn if another owner is already running or the selected batch cannot be applied
- controlled restart must treat an active F manager as a blocker unless `F_restart_drain.ready` exists

Storage-drift backup rule:
- `FPM129_storage_drift_guard.py` must not create a full SQLite backup when the SQL and CSV contracts are already aligned.
- Full SQLite backup is allowed only immediately before a safe SQL reconcile write.
- `out/backups/f_storage_drift_reconcile_*` is capped to the newest 1 non-empty backup by default.
- Empty storage-drift backup folders are cleanup debris and should be removed by the retention pass.
- If retention cannot keep the backup family within its cap, FPM129 must block as `blocked_storage_drift` instead of continuing to write more backup data.

## AI Rescan Queue Rule
Rows routed by the AI gate to `rescan_needed` must not sit behind normal fresh scanner rows.

Required behavior:
- FPM130 promotes `ai_rescan_queue.csv` rows into `supplier_price_list_active_run.csv`
- promoted rows use `scan_status=pending`, `scan_reason=rescan_retry_required`, and `completion_block_reason=rescan_retry_pending`
- F061 must pick those rescan rows before ordinary fresh pending rows
- promotion must be idempotent, with proof in `ai_rescan_promotion_audit.csv`
- when an AI-rescan batch drains to `0` pending rows, FPM130 must force rebuild the review pack and force rerun the AI gate for that supplier/run
- old `rescan_needed` decisions must not remain operator-ready after fresh scanner evidence exists

Proof artifacts:
- promotion status: `out/systems/F/price_list_manager/live/ai_rescan_promotion_status.csv`
- active scanner queue: `out/systems/F/inbox/supplier_price_list_active_run.csv`
- scanner result proof: `out/systems/F/live/f_scanner_speed_ledger_live.csv`
- rebuilt AI gate proof: supplier handoff `manifest.csv`, `ai_review_queue.csv`, `codex_ai_review_decisions.csv`, `ai_rescan_queue.csv`

Operational rule:
- If fresh rescan evidence exists but the handoff still says `already_built`, treat that as stale paperwork. Rebuild from the source evidence instead of manually passing rows downstream.

## F061 BBP Login Recovery Rule
If F061 records BBP/Amazon login-required evidence, the login must happen in the script-owned F061 browser while the scanner is running the normal flow.

Do not use a separate standalone Chrome login window as the fix.

Required behavior:
- keep affected rows pending as login-backtrack rows
- keep the normal overnight scanner hidden/minimized while it continues ordinary pending rows
- let the next normal F061 child select login rows only when the operator presses Login in the Price List Queue UI
- show the already-created normal F061 BBP browser only after real login-option evidence is detected
- let the user log in inside that script-owned browser during Login Mode
- continue the scanner and merge/backdate recovered BBP evidence onto the original rows

Operator Login Mode:
- the Price List Queue UI writes `out/systems/F/price_list_manager/live/f061_login_mode.requested`
- FPM130 reads that file only at a normal child boundary
- the next normal F061 child starts on the normal minimized scanner path with `F061_LOGIN_MODE=1`
- the child env includes `F061_LOGIN_HOLD_SECONDS` and `F061_LOGIN_MODE_REQUEST_PATH`
- current compatibility also sets `F061_MANUAL_BBP_LOGIN_WAIT_SECONDS` to the same hold value
- UI Login Mode requests default to a 900 second hold so the operator has enough time to complete Amazon/BBP login
- FPM130 records `login_mode_child_started` in `live_cycle_events.csv`
- FPM130 records `f061_login_mode_request_state` in `live_cycle_health.csv`
- `f061_login_mode_request_state=warn` means a login request exists but no child boundary can currently handle it

F061 Login Mode runtime:
- normal mode processes ordinary `pending` rows first and leaves login-backtrack rows parked
- if only login-backtrack rows remain and Login Mode is not active, F061 must not repeatedly retry them
- Login Mode prioritizes `login_backtrack_pending` rows before ordinary pending rows
- Login Mode must not show Chrome just because the BBP iframe/container is missing
- F061/Webscrape may surface only its already-created BBP driver, and only after real Amazon/BBP login-option evidence such as `/ap/signin`, OTP/CAPTCHA/security challenge controls, or BBP login email/password/button controls
- FPM130 must not use repeated external show loops for Login Mode; browser visibility belongs to the scanner-owned Webscrape driver
- F061 records `login_mode_hold_started`, `login_mode_authenticated`, `login_mode_still_required`, and `login_mode_backlog_drained` events where applicable
- F061 updates `f061_login_mode.requested` to `holding`, `still_required`, `authenticated_backlog_remaining`, or `drained`
- `authenticated_backlog_remaining` means login worked but backlog may still remain, so FPM130 keeps Login Mode active
- `drained` means login backlog is 0 and FPM130 can return to normal child mode
- the UI and FPM130 must treat `still_required`, `drained`, `consumed`, `completed`, and cancelled request files as inactive
- F061 writes `f061_login_mode_runtime` in `out/systems/F/live/feeder_legacy_sheet_health.csv`
- after the visible manual-login hold expires, Webscrape refreshes/rechecks once before returning `BBP_LOGIN_REQUIRED`
- outside active Login Mode, browser-block/login-required chunks are recorded as `f061_auth_attention=deferred_login_mode`; they must not keep opening visible Chrome by themselves

`FPM160_f061_visible_login_maintenance.py open` is only for explicit separate-browser maintenance. It is not the default answer for BBP login-required scanner rows.

Do not force the FPM launcher or Windows process startup mode visible as a workaround. Visibility must come from the normal F061 child after it detects a real login option.

The visible F061 login browser must use the same Chrome profile as the normal legacy scanner: `Chrome_UC136` / `BBPProfile`. Do not force `Chrome_UC136v2` / `BBPProfile1` unless the operator explicitly asks to migrate profiles.

Normal F061 startup must preserve the BBP Chrome profile session. Do not force-stop specialist Chrome during routine startup; force cleanup is only for recovery after a real driver launch failure or explicit operator instruction.

If FPM was paused only to open a separate login window by mistake:
- clear `out/systems/F/price_list_manager/live/f061_visible_login.requested`
- restore `out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt` to visible/login-required
- let FPM continue through the normal scanner-owned F061 path

## Test-Mode Cycle Runner
Use the cycle runner before live scanner integration.

Script:
- `scripts/flows/F/price_list_manager/FPM110_run_test_mode_cycle.py`

It runs this chain:
- source check
- URL/API download or fetch
- ready-source import
- F061 field enrichment
- next-action scoring
- fake scan of 10 rows
- memory update
- dashboard/report rebuild
- repeat for the next supplier

Rules:
- fake results append to `placeholder_scanner_results.csv`
- already-processed row keys are skipped
- by default, suppliers already present in fake results are skipped so the test can move through the list
- use `--allow-repeat-suppliers` when testing repeated chunks from a large supplier
- live F061 files are not written

Current proof:
- real test-mode cycle downloaded/imported Stax and Shure CSV links
- real test-mode cycle fetched/imported Heo API output
- real test-mode cycle fake-scanned Stax, Heo, Shure Cosmetics, Bliss Distribution, and DHB
- Shure `Product Name` is now mapped to `supplier_title`; latest enrichment has `after_missing_title=0`

## 50-Row F061 Live Trial
Use this when the operator wants a small real scanner proof instead of a full supplier run.

Scripts:
- `scripts/flows/F/price_list_manager/FPM120_build_f061_live_trial_samples.py`
- `scripts/flows/F/price_list_manager/FPM121_apply_f061_live_trial_supplier.py`

Rules:
- pause the current F061 owner before live trial apply
- back up the current live F061 inbox before replacing it
- build one 50-row sample per supplier from the latest converted batch
- apply only one supplier to F061 at a time
- run F061 without `--loop`
- do not combine suppliers in one active run file

Current proof:
- trial `f061_live_trial_20260430T125433Z` built exact 50-row samples for Stax, Heo, Shure Cosmetics, Bliss Distribution, and DHB
- all five samples were applied one at a time
- all five F061 runs completed with `pending_rows=0`
- the final live active queue ended with `0` rows

## Entertainment Trading Recovery Rule
Entertainment Trading is active as a recovery-priority manual supplier.

Folder:
- `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Inbox`

Recovery rule:
- a half-completed scan can be imported only from source rows that contain the scanner-required fields
- required fields are SKU, title, barcode, cost, currency, and VAT
- Product Database output rows without cost/title are evidence only, not a scanner-ready recovery batch

Current evidence:
- original XLSX source has been imported and preserved in the Entertainment Trading `Processed` folder
- old F061 active-run evidence has been imported as progress state only
- old F061 supplier id: `stocklist_supplier`
- old F061 run id: `stocklist_supplier_webscrape_reset_20260429T164504Z`
- old selected run rows: `21,817`
- old pending rows: `20,116`
- old done rows: `1,701`
- pending rows matched into the manager resume queue: `20,083`
- pending rows held because the new converter rejects their barcode format: `33`
- pending rows unmatched: `0`

Recovery resume rule:
- do not stage the full Entertainment Trading source after a partial scan already exists
- stage only the rows still pending in the old F061 active-run evidence, after converter safety checks
- keep rows not present in the old pending evidence out of the resume queue so they are not rescanned
- keep invalid pending rows held instead of forcing them into F061

## Authenticated URL Sources
Some supplier download URLs may return a login page instead of a file.

Rules:
- do not import HTML as a price file
- mark the source as `error`
- show the supplier as `Blocked` in the queue
- record the remote response reason in acquisition notes

Current example:
- Rashmian URL returns `auth_required_html_response`.
- Rashmian cannot be imported on demand until an authenticated session or credentialed download path is added.

## AI Gate Page Evidence Rule
Use this when a product is being held only because the supplier title contains a pack or quantity number that the Amazon title does not repeat.

Rules:
- product descriptions, product detail text, and feature bullets are supporting evidence after the row has already passed API and web scrape checks
- the identity question is supplier title vs Amazon title plus description plus bullets, not supplier title vs Amazon title alone
- if the combined Amazon evidence plainly describes the same product as the supplier title, F032 may clear a title-only manual-review warning
- if Amazon page text clearly confirms the supplier quantity, F032 may clear a title-only pack-size warning
- if Amazon page text conflicts with the supplier quantity, keep the row in user guidance or reject it
- if page text is missing and the title does not prove the quantity, keep the row out of clean pass
- do not use missing page text alone to block a row when the supplier and Amazon titles already prove the product match

Current proof:
- `KONKKS / B09HKZWBDN` originally had blank Amazon page evidence and was routed to `Needs User Guidance`
- targeted F037 backfill captured the Amazon description saying each pack contains 50 card sleeves
- F038 merged that description into the Bliss handoff review files
- F032/FPM155 rebuilt the handoff as AI-cleared pass with `manual_review_rows=0` and `pass_review_rows=1`

## AI Gate Current Scanner Fail Rule
Use this when a page-evidence backfill rechecks an old pass row and the current scanner now rejects it before page evidence is captured.

Rules:
- current scanner evidence is stronger than an old AI title decision
- if F037 writes `skipped_current_scanner_fail`, FPM155 must route the row to `remove_from_clean_pass`
- if F037 writes `needs_asin_recheck`, FPM155 must route the row to `rescan_needed`
- these rows must not appear in New Product Review or as normal operator-visible AI-cleared rows
- FPM155 health must record `current_scanner_fail_guard_rows`
- the operator UI must warn if a current scanner fail row ever has `operator_visible_flag=1`

Current proof:
- F037 now writes `out/systems/F/page_evidence_backfill/current_scanner_fail_evidence.csv`
- FPM155 consumes that file before writing operator files
- 2026-05-21 backfill audit blocked 4 current scanner fail rows from operator visibility:
  - Entertainment Trading `1243976 / B0000DC4EL`: `LOWROI`
  - Shure Cosmetics `SCS14325 / B07BC5PZ7K`: `OVER50K`
  - Stax `6LS / B0045YGMV8`: `LOWROI`
  - Stax `309148 / B005Q7B8E4`: `LOWROI`
- Final UI proof showed `scanner_fail_visible_rows=0`

## AI Gate Stale Decision Archive Rule
Use this when a supplier/run is rebuilt and old Codex AI decisions no longer match the current `ai_review_queue.csv`.

Rules:
- `codex_ai_review_decisions.csv` is the active decision file and must only contain rows that exist in the current AI queue
- old decisions are not deleted; they are moved to `codex_ai_review_decisions_stale_archive.csv`
- FPM155 must record `stale_codex_ai_decision_rows_archived`
- active queue rows missing decisions must remain `pending_ai_decision`
- stale archived decisions must not count as current AI work

Current proof:
- Entertainment Trading had `9` current queue rows and `71` stored decisions
- FPM155 archived `62` stale decisions
- final active totals are `38` queue rows and `38` active decision rows across the AI gate
- stale active decision rows are `0`

## AI Gate Backend Proof Rule
Use this after an AI worker cycle, queue refresh, morning check, or any change to the AI gate.

Command:
- `python scripts\flows\F\price_list_manager\FPM156_build_ai_gate_quality_report.py`

What it proves:
- active AI queue rows vs active Codex AI decision rows
- active queue rows missing decisions
- active decision rows that are stale
- duplicate active decision IDs
- supplier title coverage
- Amazon title coverage
- final `New Product Review` rows carrying `ai_match_confidence=` and `ai_compare=` in `What to watch`
- missing page text warnings with example rows
- missing ROI warnings with example rows

Hard fail conditions:
- active queue row count and decision row count do not match after the AI worker cycle
- active queue row has no matching Codex AI decision
- active decision file contains stale rows
- active queue or decision row is missing its F032 decision ID
- active decision file contains duplicate F032 decision IDs
- current AI gate row is missing supplier title or Amazon title
- current visible row is missing AI reason or AI evidence
- clean-pass visible row has low AI confidence
- final review row is missing the short AI confidence or compare note in `What to watch`

Warning conditions:
- operator-visible page text is missing where page text should have been carried forward
- operator-visible rows have neither ROI percentage nor a profit fallback signal

Informational conditions:
- hidden or rejected rows may have missing page text because they are not going to the operator final list
- visible rows may use profit fallback when ROI percentage cannot be calculated from available cost/sell-price fields
- historical duplicate groups may exist in audit history when the current deduped view is clean

Current proof:
- live command returned `status=ok`, `fail_checks=0`, `warn_checks=0`
- active AI queue rows: `38`
- active Codex AI decision rows: `38`
- missing active decisions: `0`
- stale active decisions: `0`
- final review rows: `6`
- final review rows missing AI compare note: `0`
- operator-visible missing page text rows: `0`
- operator-visible missing ROI/profit-signal rows: `0`
- hidden missing page text rows: `4`
- visible rows using profit fallback instead of ROI percentage: `7`
- historical duplicate groups kept only in audit history: `2`

## New Product Review ROI Display Rule
Use this for the human `New Product Review` screen.

Rules:
- human review rows must show ROI directly when an ROI percentage exists upstream
- ROI must have its own compact column in `New Product Review`
- ROI must display as a rounded whole percentage with no decimals
- the review loader should pull ROI from the handoff `ai_review_queue.csv` if the visible review pack is missing it
- if ROI percentage is genuinely unavailable, the row must show `ROI -` rather than hiding the field
- when ROI is unavailable, keep profit fallback visible using unit profit and expected 30-day profit
- do not invent ROI from incomplete data; only display ROI when the upstream percentage exists

Current proof:
- the review card now has separate `ROI` and `Profit` columns
- Shure Cosmetics rows show ROI values recovered from the AI queue:
  - `SCS61701 / B01FIL601I`: `145%`
  - `SCS21545 / B09XF8ZZG6`: `202%`
  - `SCS22096 / B0915M1DLF`: `73%`
  - `SCS19791 / B08MVG2TDJ`: `44%`
- rows without upstream ROI show `ROI -` plus profit fallback

## AI Review Supplier Cost And ROI Rule
Use this before rows reach the human `New Product Review` screen.

Root rule:
- ROI must be calculated upstream from real supplier cost and real profit evidence.
- Do not invent ROI downstream just to make the UI look complete.
- Missing ROI after this rule means the supplier cost is genuinely missing or the source column is not recognised yet.

Recognised supplier cost columns:
- `unit_cost`
- `supplier_unit_cost`
- `cost`
- `price`
- `trade price`
- `clearance price`
- `basepriceperunit`
- `base price per unit`

Current expected behaviour:
- F032 reads the original supplier source file and stores the detected cost as `unit_cost`.
- F032 then carries that value into `supplier_unit_cost_gbp`.
- If profit per unit also exists, the handoff can calculate `profit_on_cost_pct`.
- `New Product Review` displays that value as a rounded whole-number ROI percentage.

Proof from 2026-05-21:
- Bliss `KONYKSL / B0CGX83HHK`: `77%`.
- HEO `DSG106549 / B083TLCKWB`: `50%`.
- DHB `PDL504 / B001AI8AKI`: `50%`.
- FPM156 reported `current_missing_roi_rows=0`.

## New Product Review To-Do Pack Rule
Use this for the normal operator review dropdown.

Root rule:
- The normal review-pack dropdown is a to-do list, not a full archive.
- A pack should appear only when it has undecided rows for the lane the user selected.
- Historical packs remain inspectable through the older snapshot control, but must not pollute the normal working list.

Lane behaviour:
- `Passes` shows only packs with undecided pass rows.
- `Manual review` shows only packs with undecided manual-review rows.
- `Near misses` shows only packs with undecided near-miss rows.

Label behaviour:
- Labels must state the work count, for example `Bliss Distribution - 3 passes to review`.
- Labels must not imply work exists when the selected lane has 0 undecided rows.

Proof from 2026-05-21:
- Entertainment Trading is hidden from `Passes` because it has 0 pass rows.
- Entertainment Trading appears under `Manual review` with `4 manual review`.
- Bliss, Shure, HEO, and DHB appear under `Passes` with their live pass-review counts.

## AI Gate Title-Only Clear Rule
Use this when Amazon page description text is blank.

Root rule:
- Amazon page description is useful extra evidence, not mandatory proof for every product.
- If the supplier title and Amazon title clearly describe the same item, and the AI decision is high confidence, the row can pass the AI gate without description text.
- Missing description should still warn when the row is weak, ambiguous, or lacks high-confidence same-product evidence.

Quality report behaviour:
- FPM156 must not warn on a visible row just because description text is blank when the row has a high-confidence same-product title clear.
- FPM156 must keep warning for visible rows where title evidence is not enough.

Proof from 2026-05-21:
- FPM156 reported `status=ok`, `fail_checks=0`, `warn_checks=0`.
- `current_missing_page_text_rows=0`.
- `current_visible_secondary_guard_rows=0`.

## Linked Plan
Active implementation plan:
- `plans/active/f-price-list-process-manager-v1/PROJECT_BRIEF.md`
- `plans/active/f-price-list-process-manager-v1/PLAN.md`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-price-list-process-manager-v1/RUNBOOK.md`
