# TD Synnex Email Price Files Plan

Created UTC: 2026-05-19T08:21:07Z

## Goal
Bring TD Synnex price files into the feeder price-list manager safely, starting with email attachment files.

Plain-English route:
- Gmail or manual download gets the attachment.
- The attachment lands in the TD Synnex inbox folder.
- The price-list manager recognises the file.
- The TD Synnex converter turns it into the standard supplier row layout.
- Only after test-mode proof should TD Synnex be considered for active queue use.

## Current Evidence
- TD Synnex supplier config exists at `config/feeder/suppliers/td_synnex.json`.
- TD Synnex manager registry row exists at `config/feeder/price_list_manager/suppliers.csv`.
- The registry row is still parked/inactive by earlier decision.
- Local TD Synnex inbox exists at `C:\Users\Luke\Desktop\SellerOne Price Files\TD Synnex\inbox`.
- Gmail connector search on 2026-05-19 found no exact TD Synnex label hit in the connected mailbox.
- Wider Gmail zip search found one sent-message zip attachment, but it was not a TD Synnex daily price file.

## Changes Made
- Added `.tsv` to manager price-file detection.
- Added `.zip` to manager price-file detection.
- Declared TD Synnex converter support for `.csv`, `.tsv`, and `.txt`.
- Added a focused test proving a TD Synnex TSV email attachment is detected, imported, converted, and moved to `Processed`.
- Added zip handling so a daily TD Synnex zip can be imported by extracting one supported price file inside it, converting the extracted TSV, and archiving the original zip.
- Added `FPM016_fetch_gmail_email_sources.py` to fetch today's newest TD Synnex zip attachment from Gmail label `TD Synnex` into the supplier inbox.
- Added the Gmail fetch step to the test-mode and live price-list manager refresh path before import.

## Validation
- Command: `python -m py_compile scripts\flows\F\price_list_manager\FPM010_check_acquisition_sources.py scripts\flows\F\price_list_manager\FPM011_import_ready_sources.py scripts\flows\F\suppliers\td_synnex.py`
- Result: passed.
- Command: `python -m pytest tests\test_fpm010_check_acquisition_sources.py tests\test_fpm011_import_ready_sources.py tests\test_f005_build_supplier_price_list_universal.py -q`
- Result: 16 passed.
- Command: `python -m pytest tests\test_fpm010_check_acquisition_sources.py tests\test_fpm011_import_ready_sources.py tests\test_fpm016_fetch_gmail_email_sources.py tests\test_fpm110_run_test_mode_cycle.py tests\test_fpm130_live_cycle.py -q`
- Result: 75 passed.
- Dependency check: `gmail_api_deps=ok`.

## Safeguards
- No Google Sheets writes were made.
- No local database alignment was made.
- No live F loop run was started.
- TD Synnex was not unparked in the active supplier registry.
- Backup snapshot created at `project_control\backups\td_synnex_email_intake_20260519T092102`.
- Backup snapshot created at `project_control\backups\td_synnex_gmail_fetch_20260519T094641`.

## Next Phase
Status: ready for first OAuth login proof.

First-login command:
- `python -m scripts.flows.F.price_list_manager.FPM016_fetch_gmail_email_sources --supplier-id td_synnex --target-date 2026-05-19`

First operator attempt:
- At PowerShell prompt `C:\Users\Luke\Desktop\SellerOne 2.0>`, the command ran but returned `email_sources=0`.
- Root cause: TD Synnex is parked with `active_flag=0`, so the normal acquisition snapshot did not include TD Synnex.
- Fix: manual named-supplier Gmail fetch now falls back to the registry row even while the supplier remains parked for live scanning.
- Follow-up proof: `python -m pytest tests\test_fpm016_fetch_gmail_email_sources.py tests\test_fpm011_import_ready_sources.py tests\test_fpm110_run_test_mode_cycle.py tests\test_fpm130_live_cycle.py -q`
- Result: 72 passed.

After that:
- Browser consent should create `secrets\price_list_manager\gmail_token.json`.
- The script should save the newest zip from today's `TD Synnex` label into `C:\Users\Luke\Desktop\SellerOne Price Files\TD Synnex\inbox`.
- Then run the existing test-mode acquisition/import path for TD Synnex only.
- Keep live scanner handoff disabled until row counts and hold reasons are reviewed.

## Real File Proof - 2026-05-19
OAuth result:
- `secrets\price_list_manager\gmail_token.json` was created.

Downloaded source:
- Gmail label: `TD Synnex`
- Message timestamp UTC: `2026-05-19T00:50:19Z`
- Zip bytes: `7054060`
- SHA1: `697fd87dcd0191bd5ae52105cd82f479f64abfae`
- Archived source: `C:\Users\Luke\Desktop\SellerOne Price Files\TD Synnex\Processed\798126_A_20260519_20260519T090242Z_697fd87dcd_20260519T091600Z_697fd87dcd.zip`

Converted batch:
- Batch id: `td_synnex_source_20260519T091600Z_697fd87dcd01`
- Source rows: `103543`
- Base scan-now rows: `81238`
- Base held rows: `22305`
- Hold reason: `missing_cost`
- Timeout/memory eligible scan rows: `43636`
- Timeout/memory skipped rows: `59907`
- Converted file: `out\systems\F\price_list_manager\test_mode\td_synnex_source_20260519T091600Z_697fd87dcd01_converted.csv`

Repair note:
- First real import exposed a parked-supplier registry fallback issue and a missing batch-header reconciliation issue.
- Both were fixed and covered by focused tests.
- Batch header was repaired from the preserved zip and converted rows, then timeout eligibility was rebuilt.

Validation:
- `python -m pytest tests\test_fpm011_import_ready_sources.py tests\test_fpm016_fetch_gmail_email_sources.py tests\test_fpm110_run_test_mode_cycle.py tests\test_fpm130_live_cycle.py -q`
- Result: `75 passed`.

Current safety state:
- TD Synnex remains parked in `config\feeder\price_list_manager\suppliers.csv`.
- No live F061 handoff was applied.
- Next decision should be whether to activate a controlled TD Synnex trial chunk or load the full eligible queue.

## Live Scanner Triage - 2026-05-19 10:39 BST
Status: in progress.

Problem:
- The TD Synnex scanner is active, but operator-facing good rows are not coming through.
- Live evidence shows F061 is browsing Amazon/BBP and making decisions.
- Root-cause evidence shows the TD Synnex converter mapped the 21-column TSV using a 20-column schema.
- Example bad handoff row: `supplier_sku=APC`, `supplier_title=30.93`, `unit_cost=43.73`.
- Expected row shape from source: `supplier_sku=AP9815`, `supplier_title=UPS INTERFACE EXTENSION`, `unit_cost=30.93`, `barcode=731304002727`.

Safeguards:
- Do not start another F061 scanner while the live owner is active.
- Request a controlled F-manager drain using `out/locks/maintenance.requested` with `exit_after_drain=1`.
- Wait for `out/systems/F/price_list_manager/live/F_restart_drain.ready` before replacing the active TD run.
- Preserve backups of TD converter, TD converted output, batch rows, active run, and run state before rebuilding.
- No Google Sheets writes.
- No local DB alignment changes.

Implementation phases:
- Phase 1: controlled drain and backup current bad TD scanner state.
- Phase 2: patch TD Synnex converter column schema and add a regression test for the real 21-column row.
- Phase 3: rebuild TD Synnex import from the preserved zip and prove field mapping.
- Phase 4: re-stage/re-apply a clean TD Synnex scanner run only after the bad active run is parked or replaced at the drain boundary.

Verification target:
- `supplier_sku` must equal real TD SKU, not brand.
- `supplier_title` must be a product description, not a price.
- `unit_cost` must equal cost price, not selling price.
- Scanner active run must show updated pending rows from the rebuilt clean handoff.

Timeout rule:
- If drain is not reached within 15 minutes, record latest `live_cycle_status.csv`, `f061_child_status.txt`, and `f061_child_stdout.log` tail, then park as `parked pending F drain boundary`.

## Live Scanner Triage Update - 2026-05-19 10:51 BST
Status: monitored validation.

Completed:
- Controlled drain reached at `2026-05-19T09:47:52Z`.
- Bad TD active run `fpm_td_synnex_20260519T090704Z` was archived and retired because it was built from shifted source columns.
- TD Synnex converter now supports the real 21-column TSV shape.
- Corrected batch now has `103543` source rows, `103457` cost-valid rows, `86` missing-cost held rows, and `57971` scanner-eligible rows after barcode/memory checks.
- Clean active run applied as `fpm_td_synnex_20260519T095000Z`.
- First clean active row proof: `supplier_sku=AP9815`, `supplier_title=UPS INTERFACE EXTENSION`, `unit_cost=30.93`, `barcode=731304002727`.
- Maintenance markers were archived at `out/systems/F/price_list_manager/live/lock_archive/td_synnex_schema_fix_20260519T095100Z`.
- F supervisor restarted manager PID `3400`, which started F061 child PID `32644`.

Validation running:
- Monitor `out/systems/F/price_list_manager/live/live_cycle_status.csv`.
- Monitor `out/systems/F/inbox/supplier_price_list_active_run.csv`.
- Monitor `out/systems/F/inbox/supplier_price_list_run_state.csv`.
- Monitor `out/systems/F/price_list_manager/live/f061_child_stdout.log`.

Success condition:
- First clean F061 child chunk finalizes with `rc=0`.
- Active run pending count drops below `57971`.
- Run state belongs to `fpm_td_synnex_20260519T095000Z`.
- Result counts are recorded as PASS/FAIL/RESCAN or equivalent terminal row states.

If it fails:
- If child exits non-zero, inspect `f061_child_stderr.log` and keep manager paused before another restart.
- If child finishes but pending count does not move, inspect FPM130 merge logic for active-run writes.
- If rows process but all rows fail business checks, classify scanner as operational but TD commercial fit currently poor, not as a scanner outage.

Validation result:
- First clean child finalized at `2026-05-19T09:53:57Z` with `rc=0`.
- Second clean child finalized at `2026-05-19T09:56:11Z` with `rc=0`.
- Third clean child finalized at `2026-05-19T09:59:39Z` with `rc=0`.
- Active run pending dropped from `57971` to `57896`.
- Run state remains `fpm_td_synnex_20260519T095000Z`.
- Live screening state for this run shows `1` PASS, `80` FAIL/timeout, and the rest pending.
- Latest live health tail is all `ok`.

Conclusion:
- Scanner is working again on the corrected TD Synnex handoff.
- Low operator-facing output was caused by the TD Synnex schema shift first, then normal commercial filters such as `OVER50K`, `NOASIN`, and `ROIFAIL`.
