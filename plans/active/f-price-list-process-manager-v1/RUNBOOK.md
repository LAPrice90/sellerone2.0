# F Price List Process Manager v1 - Runbook

Date: 2026-04-30

## Purpose
This runbook explains how to operate and test the price-list process manager once it is built.

Current status:
- plan exists
- test-mode queue fixtures are built
- acquisition source checker is built
- ready local CSV import and duplicate-file protection are built
- URL/CSV-link download into a local test-mode inbox is built
- API fetch into a local test-mode inbox is built
- placeholder scanner is built
- cooldown memory update is built
- Streamlit operator UI has a read-only `Price List Queue` page
- test-mode queue pause/prioritise controls are built through `queue_controls.csv`
- Streamlit Pause/Prioritise buttons now write test-mode controls and rebuild the manager view
- Shure Cosmetics is registered as the first supplier example
- Stax is registered as the first large keyed CSV feed example
- Heo is registered as the first authenticated API example
- CLF SOAP adapter is built and waiting for the missing auth-token source
- We Stock Lots converter is built. The website CSV export endpoint is known, but it currently requires an authenticated website session/cookie before the manager can download it automatically.
- live F061 handoff not allowed yet

## First Registered Supplier Example
Supplier:
- `shure_cosmetics`

Manager classification:
- `source_type=api_pull`
- `source_subtype=csv_link`

Existing source:
- `https://aux.shure-cosmetics.co.uk/pricelist/`

Existing converter:
- `scripts/flows/F/suppliers/shure_cosmetics.py`

Registry row:
- `config/feeder/price_list_manager/suppliers.csv`

Starter supplier list:
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

Review note:
- `plans/active/f-price-list-process-manager-v1/SHURE_COSMETICS_EXAMPLE.md`

## Safety Rules
- Do not run F061 from this manager until Phase 6 is approved and proven.
- Do not overwrite `out/systems/F/inbox/supplier_price_list_active_run.csv` from the manager in v1 test mode.
- Do not overwrite `out/systems/F/inbox/supplier_price_list_run_state.csv` from the manager in v1 test mode.
- Do not switch supplier while F061 is running.
- Do not treat an email/API/manual request as scan-worthy unless a new batch or eligible rows exist.
- Do not rescan monthly manual suppliers before a fresh list arrives.

## Standard Test-Mode Run Order
These commands run the current read-only test process. They write under `out/systems/F/price_list_manager/test_mode/` only.

```powershell
# 1) Build Shure test supplier and batch fixtures
python scripts\flows\F\price_list_manager\FPM001_build_test_fixtures.py --supplier-id shure_cosmetics --observed-utc 2026-04-30T09:00:00Z

# 2) Check supplier source availability
python scripts\flows\F\price_list_manager\FPM010_check_acquisition_sources.py --checked-at-utc 2026-04-30T09:01:00Z

# 3) Import any ready local CSV/TXT source files into test-mode batches
python scripts\flows\F\price_list_manager\FPM011_import_ready_sources.py --imported-at-utc 2026-04-30T09:02:00Z

# Optional 3a) Download ready URL/CSV-link sources into local test-mode inboxes
python scripts\flows\F\price_list_manager\FPM013_download_ready_url_sources.py --supplier-id stax --downloaded-at-utc 2026-04-30T09:02:30Z

# Optional 3b) Import the downloaded supplier source
python scripts\flows\F\price_list_manager\FPM011_import_ready_sources.py --supplier-id stax --imported-at-utc 2026-04-30T09:03:00Z

# Optional 3c) Fetch ready API suppliers into local test-mode inboxes
python scripts\flows\F\price_list_manager\FPM014_fetch_api_sources.py --supplier-id heo --fetched-at-utc 2026-04-30T09:03:30Z

# Optional 3d) Import the fetched API supplier source
python scripts\flows\F\price_list_manager\FPM011_import_ready_sources.py --supplier-id heo --imported-at-utc 2026-04-30T09:04:00Z

# 4) Run placeholder scanner against the Shure test batch
python scripts\flows\F\price_list_manager\FPM020_run_placeholder_scanner.py --scanned-at-utc 2026-04-30T09:10:00Z

# 5) Update cooldown memory from placeholder results
python scripts\flows\F\price_list_manager\FPM030_update_memory_from_results.py --observed-utc 2026-04-30T09:11:00Z

# 6) Build the read-only dashboard preview used by the UI
python scripts\flows\F\price_list_manager\FPM060_build_status_dashboard.py --built-at-utc 2026-04-30T09:12:00Z

# 7) Build the next recommended scan action
python scripts\flows\F\price_list_manager\FPM040_build_next_action.py --observed-utc 2026-04-30T13:00:00Z

# 8) Refresh the UI dashboard after the recommendation
python scripts\flows\F\price_list_manager\FPM060_build_status_dashboard.py --built-at-utc 2026-04-30T13:01:00Z

# Optional 9) Set or clear a test-mode queue control
python scripts\flows\F\price_list_manager\FPM080_set_queue_control.py --supplier-id heo --control-state prioritised --priority-rank 1 --reason "operator test"
python scripts\flows\F\price_list_manager\FPM080_set_queue_control.py --supplier-id heo --control-state normal
```

## Expected Test-Mode Outputs
- `out/systems/F/price_list_manager/test_mode/supplier_registry.csv`
- `out/systems/F/price_list_manager/test_mode/price_list_batches.csv`
- `out/systems/F/price_list_manager/test_mode/batch_rows.csv`
- `out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv`
- `out/systems/F/price_list_manager/test_mode/downloaded_sources/<supplier_id>/Inbox`
- `out/systems/F/price_list_manager/test_mode/downloaded_sources/<supplier_id>/Processed`
- `out/systems/F/price_list_manager/test_mode/batch_scan_eligibility.csv`
- `out/systems/F/price_list_manager/test_mode/placeholder_scanner_results.csv`
- `out/systems/F/price_list_manager/test_mode/barcode_scan_memory.csv`
- `out/systems/F/price_list_manager/test_mode/manager_decisions.csv`
- `out/systems/F/price_list_manager/test_mode/queue_controls.csv`
- `out/systems/F/price_list_manager/test_mode/health.csv`
- `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`
- `out/systems/F/price_list_manager/test_mode/status_dashboard.html`

## What Good Looks Like In The First Test
The first clean test should prove:
- fake source rows = 10
- converted batch rows = 10
- placeholder scanner result rows = 10
- memory rows updated = 10
- manager decision rows >= 1
- unresolved rows = 0
- health `FAIL` count = 0
- no live F061 inbox file modified

Current acquisition proof:
- supplier rows = 12
- ready rows = 4
- missing rows = 3
- waiting rows = 3
- config-needed rows = 1
- fail rows = 1
- Shure CSV link returned HTTP 200
- Stax CSV link returned HTTP 200 and downloaded as a price-file-like CSV
- Rashmian still returns login HTML and remains blocked

Current ready-source import proof:
- with empty Desktop inbox folders, ready local sources = 0
- imported batches = 0
- duplicate sources = 0
- failed sources = 0
- health `FAIL` count = 0
- focused test proof shows a ready local CSV imports once, creates valid and held rows, then dedupes on the second run

Current DHB converter proof:
- real file: `Trade Price January 2026 (2).xlsx`
- workbook sheets:
  - `Trade Price`
  - `End of Line - Whilst Stocks Las`
- source rows = 959
- scan-ready rows = 788
- held rows = 171
- price format is normalized to plain GBP with two decimal places
- barcode format is normalized to digits only
- imported file was moved to `C:\Users\Luke\Desktop\Amazon price files\DHB\Processed`

Current Bliss converter proof:
- real file: `Stock List 07.01.26 (2).xlsx`
- workbook sheets:
  - `Data`
  - `Parameters`
- source rows = 2212
- scan-ready rows = 1526
- held rows = 686
- price format is normalized to plain GBP with two decimal places
- barcode format is normalized to digits only
- imported file was moved to `C:\Users\Luke\Desktop\Amazon price files\Bliss\Processed`

Current Stax CSV-link proof:
- source URL: `https://www.staxtradecentres.co.uk/feeds/1.3/product.csv?key=rte4adf6rv&method=button`
- source type: `api_pull`
- source subtype: `csv_link`
- download bytes = 14849765
- source rows = 27201
- scan-ready rows = 24231
- held rows = 2970
- held reasons:
  - missing barcode = 1851
  - discontinued = 1100
  - discontinued and missing barcode = 19
- price format is normalized to plain GBP with two decimal places
- VAT rate is preserved as the source numeric rate
- barcode format is normalized to digits only
- imported source was moved from test-mode `Inbox` to test-mode `Processed`
- current recommendation is Stax with `24231` estimated scan rows

Current Heo API proof:
- source URL: `https://integrate.heo.com/retailer-api/v1/catalog`
- source type: `api_pull`
- source subtype: `api`
- local credential file: `secrets/price_list_manager/heo_api.json`
- credential file is ignored by git through `secrets/`
- fetched product rows = 7610
- fetched price rows = 7610
- expanded barcode rows = 7919
- downloaded bytes = 3443202
- scan-ready rows = 7754
- held rows = 165
- held reasons:
  - invalid barcode format = 163
  - missing barcode = 2
- price format is normalized to plain GBP with two decimal places
- VAT is normalized from Heo VAT type where possible
- product title prefers the English translation when Heo sends a translation list

Current CLF SOAP API status:
- source URL: `http://services.clfdistribution.com:8080/CLFWebOrdering/WebOrdering.asmx`
- source type: `api_pull`
- source subtype: `api`
- adapter: `scripts/flows/F/suppliers/clf.py`
- expected credential file: `secrets/price_list_manager/clf_api.json`
- required secret key for current adapter: `auth_token`
- blocker: the Apps Script snippet calls `getAuthenticationToken()` but does not include that function
- current source state after API fetch attempt: `error`
- current operator action: `Add API credentials`
- no CLF batch has been imported yet
- isolated tests prove:
  - SKU XML parsing
  - product XML parsing
  - VAT conversion from `STD` to `20` and `ZERO` to `0`
  - generated CSV conversion into batch rows

Current We Stock Lots status:
- source type: `api_pull`
- source subtype: `csv_link`
- converter: `scripts/flows/F/suppliers/we_stock_lots.py`
- source URL: `https://westocklots.com/api/export/stocklist/?format=csv`
- active queue status: parked by user decision on 2026-04-30
- blocker: endpoint returns `401 Unauthorized` without the logged-in website session
- current source state: `error` until authentication is available
- current operator action: `Investigate CSV link`
- source prices are EUR and are converted to GBP during supplier conversion
- do not use the old hard-coded `0.85` rate
- authenticated export check on 2026-04-30:
  - direct request returned `401 Unauthorized`
  - active F061 Chrome profile has no We Stock Lots cookies
  - normal Chrome profiles are open and locked without a remote debugging port
  - Edge has analytics cookies only, not a login session
  - keep blocked rather than disturbing the live scanner

Parking rule:
- Do not spend more implementation time on We Stock Lots unless the user explicitly reactivates it.
- Keep the converter because it may be useful later.
- Keep `active_flag=0` in the supplier registry so the active queue ignores it.
- The next useful queue work should focus on Stax, Heo, Shure, Bliss, DHB, CLF when credentials are available, and high-value daily email suppliers.

Current playground scope:
- Active now:
  - Stax
  - Heo
  - Shure Cosmetics
  - Bliss Distribution
  - DHB
- Parked until later API/email/login work:
  - Rashmian
  - TD Synnex
  - CLF
  - ABGee
  - We Stock Lots
  - Tropicana Wholesale
  - Entertainment Trading
- Reason:
  - the active set is enough to test queue behavior, batch selection, status UI, and staged handoff without adding Google/email/API access work yet.

Current next-phase handoff preview:
- selected supplier: `Stax`
- selected batch: `stax_source_20260430T144700Z_eaf2df92f4e3`
- staged rows: `24231`
- live apply allowed: `0`
- live block reason: F061 is busy with `pending_active=20216`, `running_state=1`, `pending_state=20216`
- live apply remains disabled until an explicit safe handoff rule is approved.

Dashboard queue wording:
- `Recommended` means the manager would scan that batch next.
- `Prioritised` means the operator has promoted that supplier in test mode.
- `Queued` means a ready batch has unprocessed rows but is behind the recommendation.
- `Paused` means the operator has held that supplier out of next-action selection in test mode.
- `Complete` means no unprocessed scan rows remain for the latest batch.
- `Needs Manual File` means the monthly/manual source is due and no source file is available.

Queue controls:
- controls are test-mode only
- control file: `out/systems/F/price_list_manager/test_mode/queue_controls.csv`
- set a supplier to paused:
  - `python scripts\flows\F\price_list_manager\FPM080_set_queue_control.py --supplier-id stax --control-state paused --reason "operator pause"`
- prioritise a supplier:
  - `python scripts\flows\F\price_list_manager\FPM080_set_queue_control.py --supplier-id heo --control-state prioritised --priority-rank 1 --reason "operator priority"`
- clear a supplier control:
  - `python scripts\flows\F\price_list_manager\FPM080_set_queue_control.py --supplier-id heo --control-state normal`
- after changing controls, rebuild next action and dashboard:
  - `python scripts\flows\F\price_list_manager\FPM040_build_next_action.py`
  - `python scripts\flows\F\price_list_manager\FPM060_build_status_dashboard.py`
- the Streamlit buttons write test-mode controls only
- clicking Pause or Prioritise rebuilds the next action, report, staged handoff preview, and dashboard
- live F061 handoff remains disabled

Dashboard handoff panel:
- `Blocked - F061 busy` means a staged handoff exists but live apply is not allowed because the live scanner still has active work.
- `Ready for approved handoff` may only be treated as eligible to apply after a separate explicit safe handoff approval.
- rate selection order:
  - `WE_STOCK_LOTS_EUR_GBP_RATE` environment override, for controlled tests only
  - current online EUR to GBP rate from Frankfurter
  - local cache `out/fx_rates_daily.csv`
- current conversion check returned EUR to GBP `0.86643000` from `frankfurter_latest:2026-04-29`
- isolated tests prove:
  - EUR price symbols are stripped
  - prices convert into GBP with two decimals
  - missing barcode rows are held
  - invalid price rows are held
  - positional column fallback follows the old Google Sheet mapping

Monthly manual file rule:
- DHB and Bliss are monthly manual suppliers.
- If the latest imported file is in the same calendar month as the source check, the UI shows `Done`.
- If the source check moves into a later calendar month and no new file is present, the UI shows `Needs Manual File`.
- Example proof:
  - April 30 check: DHB and Bliss show `Done`.
  - May 1 check: DHB and Bliss show `Request price file`.

Current prioritizer proof:
- eligibility rows = 38301
- scan rows = 34299
- skipped rows = 4002
- selected supplier = `stax`
- selected batch = `stax_source_20260430T144700Z_eaf2df92f4e3`
- estimated scan rows = 24231
- safe handoff flag = 0
- Shure is active in placeholder mode.
- Stax is the next recommended scan.
- Heo is registered and imported, but sits behind Stax because Stax has more eligible rows.
- CLF is blocked until the missing API auth token/token-fetch method is added.
- We Stock Lots is blocked until the website export authentication is available to the downloader.
- Bliss and DHB are registered and done for the current month, but sit behind Stax because Stax has more eligible rows.

Current Shure placeholder proof:
- source rows = 10
- converted valid rows = 10
- scan-eligible rows = 10
- placeholder scanner rows = 10
- pass rows = 1
- fail rows = 8
- rescan rows = 1
- memory rows = 10
- unresolved rows = 0
- health `FAIL` count = 0

## Dashboard Preview
The UI preview is in the existing Streamlit operator UI:
- `http://localhost:8501/?page=price_list_queue`

It should behave like a queue, not a spreadsheet:
- active supplier stays at the top
- manual missing files are visible but can move down the list
- source method is visible
- pause and prioritise controls write test-mode queue controls only
- API/CSV-link suppliers show ready unless the download path fails

UI style rule:
- match the existing operator workspace
- use compact rows, grey headers, inline badges, and dark dividers
- keep action buttons inside the supplier row
- avoid large standalone report cards for routine queue rows
- show manual-file alerts as dark operator warnings, not a separate spreadsheet-style block

The HTML preview is read-only and static:
- `out/systems/F/price_list_manager/test_mode/status_dashboard.html`

For the current Shure placeholder test, good output is:
- supplier row: `Shure Cosmetics`
- queue position: `1`
- method: `CSV link`
- file state: `Ready`
- bot status: `Test Ready`
- web unprocessed: `0`
- web pass: `1`
- web fail: `8`
- web rescan: `1`
- second-check counts: `0`

Manual monthly example output:
- `DHB` should show `Missing` and `Needs Manual File` until a CSV is present in `C:\Users\Luke\Desktop\SellerOne Price Files\DHB\inbox`
- `Bliss Distribution` should show `Missing` and `Needs Manual File` until a CSV is present in `C:\Users\Luke\Desktop\SellerOne Price Files\Bliss Distribution\inbox`
- missing manual files should not block Shure or another API supplier from being active

Current starter queue behavior:
- `Shure Cosmetics` is active from the test fixture.
- `Stax`, `CLF`, and `Heo` show as `API`.
- `TD Synnex`, `ABGee`, and `Tropicana Wholesale` show as `Daily email`.
- `Bliss Distribution`, `DHB`, and `Entertainment Trading` show as `Email request`.
- `Rashmian` shows as `Website link`.
- `We Stock Lots` shows as `Error` / `Blocked` while the website CSV export returns `401 Unauthorized`.

Desktop inbox folders:
- Simple manual test folder:
  - `C:\Users\Luke\Desktop\Amazon price files\DHB\Inbox`
  - `C:\Users\Luke\Desktop\Amazon price files\DHB\Processed`
  - `C:\Users\Luke\Desktop\Amazon price files\Bliss\Inbox`
  - `C:\Users\Luke\Desktop\Amazon price files\Bliss\Processed`
- `C:\Users\Luke\Desktop\SellerOne Price Files\Bliss Distribution\inbox`
- `C:\Users\Luke\Desktop\SellerOne Price Files\Rashmian\inbox`
- `C:\Users\Luke\Desktop\SellerOne Price Files\TD Synnex\inbox`
- `C:\Users\Luke\Desktop\SellerOne Price Files\DHB\inbox`
- `C:\Users\Luke\Desktop\SellerOne Price Files\ABGee\inbox`
- `C:\Users\Luke\Desktop\SellerOne Price Files\Tropicana Wholesale\inbox`
- `C:\Users\Luke\Desktop\SellerOne Price Files\Entertainment Trading\inbox`

Manual file handling:
- User drops DHB files into `C:\Users\Luke\Desktop\Amazon price files\DHB\Inbox`.
- User drops Bliss files into `C:\Users\Luke\Desktop\Amazon price files\Bliss\Inbox`.
- After successful import, the file is moved to the supplier's `Processed` folder.
- Duplicate files are also moved to `Processed`, but they do not create another batch.
- Files are not deleted automatically.

## Adding A Real Supplier Later
Use this order for each supplier.

1. Add supplier to the manager registry.
2. Define acquisition method:
   - manual request
   - local email attachment folder
   - API pull
   - URL download
   - local file import
3. Add or confirm converter into the universal F supplier format.
4. Run the supplier through manager test mode.
5. Confirm batch counts:
   - raw rows
   - valid rows
   - held rows
   - new rows
   - changed rows
   - cooldown-skipped rows
   - scan-eligible rows
6. Review next-action report.
7. Only after approval, allow controlled F061 handoff design for that supplier.

## Next-Action Report
The queue recommendation is built in test mode only.

Build command:
- `python scripts\flows\F\price_list_manager\FPM040_build_next_action.py`
- `python scripts\flows\F\price_list_manager\FPM050_build_next_action_report.py`
- `python scripts\flows\F\price_list_manager\FPM060_build_status_dashboard.py`

Outputs:
- `out/systems/F/price_list_manager/test_mode/batch_scan_eligibility.csv`
- `out/systems/F/price_list_manager/test_mode/manager_decisions.csv`
- `out/systems/F/price_list_manager/test_mode/next_action_report.md`
- `out/systems/F/price_list_manager/test_mode/next_action_skip_reasons.csv`
- `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`

Current proof:
- Stax is the recommended next test scan.
- Estimated scan rows are `24231`.
- Estimated skipped rows are `2970`.
- Heo has `7754` scan-ready rows and `165` held rows.
- CLF has no imported rows yet because the auth token source is missing.
- We Stock Lots has no imported rows yet because the website CSV export requires authentication.
- Bliss Distribution has `1526` scan-ready rows and `686` held rows.
- DHB has `788` scan-ready rows and `171` held rows.
- Shure Cosmetics has already completed the 10-row placeholder scan and now shows as `Complete` in the queue.
- `safe_to_handoff_flag` remains `0`.

UI:
- Open `http://localhost:8501/?page=price_list_queue`.
- The `Next Action Explanation` section shows the report.
- Pause and prioritise buttons are active for test-mode queue controls.
- They do not write live F061 files.
- The `F061 Handoff Guard` panel shows staged-batch readiness and approval state.
- `Approve` and `Revoke` in that panel write test-mode approval records only.
- Approval does not start F061 and does not write live scanner input files.

## F061 Staged Handoff
The staged handoff prepares the selected manager batch in the same column shape F061 expects.

Build commands:
- `python scripts\flows\F\price_list_manager\FPM012_enrich_batch_rows_for_f061.py`
- `python scripts\flows\F\price_list_manager\FPM070_stage_f061_handoff.py`

Outputs:
- `out/systems/F/price_list_manager/test_mode/f061_handoff_staged_active_run.csv`
- `out/systems/F/price_list_manager/test_mode/f061_handoff_staged_run_state.csv`
- `out/systems/F/price_list_manager/test_mode/f061_handoff_preview.csv`
- `out/systems/F/price_list_manager/test_mode/f061_handoff_approvals.csv`

Current staged proof:
- supplier: `Stax`
- staged rows: `24231`
- live apply allowed: `0`
- F061 idle status: `busy`
- block reason: `f061_not_idle:pending_active=20116;running_state=1;pending_state=20116`

Live handoff rule:
- do not write live F061 files while the preview says `live_apply_allowed=0`
- do not treat F061 being idle as approval
- require a matching approval row for the exact supplier and batch
- do not switch suppliers while `supplier_price_list_run_state.csv` has `run_status=running`
- do not switch suppliers while `supplier_price_list_active_run.csv` has pending rows
- live apply needs a separate approved proof window

Handoff approval command:
- record approval:
  - `python scripts\flows\F\price_list_manager\FPM090_set_f061_handoff_approval.py --supplier-id stax --batch-id stax_source_20260430T144700Z_eaf2df92f4e3 --approval-state approved --approved-by operator --reason "F061 idle proof checked"`
- revoke approval:
  - `python scripts\flows\F\price_list_manager\FPM090_set_f061_handoff_approval.py --supplier-id stax --batch-id stax_source_20260430T144700Z_eaf2df92f4e3 --approval-state revoked --approved-by operator --reason "operator revoked"`
- after approval or revoke, rebuild staged preview:
  - `python scripts\flows\F\price_list_manager\FPM070_stage_f061_handoff.py`
  - `python scripts\flows\F\price_list_manager\FPM060_build_status_dashboard.py`

Preview fields:
- `technical_ready_flag=1` means F061 is idle, rows are staged, and required fields are present.
- `approval_state=approved` means the exact selected supplier and batch have a latest approval.
- `live_apply_allowed=1` means all non-phase guards pass.
- Current phase still refuses live apply; this is readiness evidence, not a live switch.

Guarded apply preview command:
- preview only:
  - `python scripts\flows\F\price_list_manager\FPM100_apply_f061_handoff.py`
- this writes `f061_handoff_apply_preview.csv`
- preview mode must not write live F061 files

Guarded live apply command:
- only use after F061 is idle, the exact batch is approved, and the staged preview shows `live_apply_allowed=1`
- command:
  - `python scripts\flows\F\price_list_manager\FPM100_apply_f061_handoff.py --apply-live --confirm-approved-handoff`

Live apply guards:
- latest staged preview must exist
- staged active rows must match preview row count
- staged run-state rows must match preview row count
- `technical_ready_flag=1`
- `approval_state=approved`
- `live_apply_allowed=1`
- F061 must still be idle at apply time
- if any guard fails, no live write is attempted

Backup rule:
- before live write, snapshot:
  - `out/systems/F/inbox/supplier_price_list_active_run.csv`
  - `out/systems/F/inbox/supplier_price_list_run_state.csv`
- backup manifests are written under:
  - `out/systems/F/price_list_manager/test_mode/f061_handoff_backups/`
- summary backup log:
  - `out/systems/F/price_list_manager/test_mode/f061_handoff_apply_backups.csv`

Current real apply preview:
- built at `2026-04-30T17:15:00Z`
- supplier `stax`
- staged rows `24231`
- `apply_ready_flag=0`
- `live_write_attempted=0`
- `live_write_succeeded=0`
- block reason includes no approval and F061 busy with `20116` pending rows

## Test-Mode Fake-Scan Cycle
Purpose:
- prove source download, conversion, queue movement, fake scanner results, memory updates, and dashboard counts before F061 integration.

Command:
- full acquisition and fake scan:
  - `python scripts\flows\F\price_list_manager\FPM110_run_test_mode_cycle.py --max-iterations 5`
- reuse existing imported batches only:
  - `python scripts\flows\F\price_list_manager\FPM110_run_test_mode_cycle.py --skip-acquisition --max-iterations 5`
- allow repeat chunks from the same supplier:
  - add `--allow-repeat-suppliers`

Outputs:
- `test_mode_cycle_runs.csv`
- `test_mode_cycle_steps.csv`
- `placeholder_scanner_results.csv`
- `barcode_scan_memory.csv`
- `status_dashboard.csv`
- `next_action_report.md`

Health:
- `test_mode_cycle_reconciliation`
- expected fake result count is `scanner_iterations * 10`
- fail if the count does not reconcile

Current proof:
- Stax CSV link downloaded and imported.
- Shure Cosmetics CSV link downloaded and imported.
- Heo API fetched, expanded barcodes, and imported.
- DHB and Bliss existing manual batches were fake-scanned from imported source files.
- Latest Shure title enrichment fixed `Product Name` mapping:
  - before missing title `5047`
  - after missing title `0`

## 50-Row F061 Live Trial
Purpose:
- prove each converted price-list format can be handed to the real F061 scanner without committing to a long supplier run

Safe boundary:
- pause the existing F061 owner process first
- back up the current live F061 inbox files
- apply only one supplier sample at a time
- run F061 without `--loop`

Build samples:
- `python scripts\flows\F\price_list_manager\FPM120_build_f061_live_trial_samples.py --sample-rows 50`

Apply one supplier:
- `python scripts\flows\F\price_list_manager\FPM121_apply_f061_live_trial_supplier.py --supplier-id <supplier_id> --trial-id <trial_id> --apply-live --confirm-live-trial`

Run F061 once:
- `python scripts\flows\F\F061_run_legacy_first_checks_local.py --supplier-id <supplier_id> --max-rows 50 --scrape-mode legacy_module --price-source legacy --catalog-max-candidates 3`

Proof required before moving to the next supplier:
- active run has `0` pending rows
- run state is `completed`
- F061 command exits by itself
- no F061 owner process is left running

Latest trial:
- trial id: `f061_live_trial_20260430T125433Z`
- suppliers sampled: Stax, Heo, Shure Cosmetics, Bliss Distribution, DHB
- each supplier had exactly `50` scanner-ready rows
- all five F061 runs completed with `0` pending rows

## Live Price-List Manager Scheduler
Purpose:
- own the F price-list queue after the manager is approved for live operation
- resume any existing F061 active queue before choosing a new supplier
- survive the 02:10 PC restart by starting from Task Scheduler at boot

Launcher:
- `run_F_price_list_manager_cycle.bat`

Runner:
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`

Windows task:
- task name: `AMZ Price List Manager`
- trigger: at startup with `PT5M` delay
- action: `cmd.exe /c "C:\Users\Luke\Desktop\SellerOne 2.0\run_F_price_list_manager_cycle.bat"`
- working directory: `C:\Users\Luke\Desktop\SellerOne 2.0`
- multiple instances: `IgnoreNew`
- restart on failure: every `PT5M`, up to `999` times
- execution time limit: `PT0S`
- current registration uses `InteractiveToken`; a stored-password registration like `AMZ Orders` needs the Windows password and was not available to Codex

Live runner outputs:
- `out/systems/F/price_list_manager/live/live_cycle.lock`
- `out/systems/F/price_list_manager/live/live_cycle.log`
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/price_list_manager/live/live_cycle_events.csv`
- `out/systems/F/price_list_manager/live/live_cycle_health.csv`
- `out/systems/F/price_list_manager/live/F_restart_drain.ready`

Resume rule:
- if `supplier_price_list_active_run.csv` has pending rows, the runner scans that supplier first
- the manager does not rebuild or replace the active queue while pending rows exist
- if there is no pending F061 active run, the manager refreshes the queue, stages the next batch, applies the exact approved batch, and runs one chunk
- default chunk size is `50` rows

Restart drain rule:
- controlled restart writes `out/locks/maintenance.requested`
- F manager finishes the current F061 chunk before checking the marker
- at the next safe boundary, F manager writes `F_restart_drain.ready`
- controlled restart may reboot only after the gate sees F at this boundary
- after startup, Task Scheduler starts the BAT again and the runner resumes from the saved active F061 queue

Manual proof commands:
- preview without live write:
  - `python scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py --run-once --skip-refresh-before-select --chunk-rows 50`
- start the scheduled task:
  - `schtasks /Run /TN "AMZ Price List Manager"`
- stop the scheduled task owner:
  - `schtasks /End /TN "AMZ Price List Manager"`
- query the task:
  - `schtasks /Query /TN "AMZ Price List Manager" /V /FO LIST`

Current proof:
- preview-only runner staged Entertainment Trading with `20,083` rows
- live F061 active-run rows stayed `0`
- focused tests returned `7 passed`
- `AMZ Price List Manager` task is registered and `Ready`
- `AMZ Controlled Restart` is still `Disabled`; F restart-drain code is ready, but the existing controlled restart task was not enabled

## Entertainment Trading Recovery
Current folder:
- `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Inbox`
- `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Processed`

Current manager status:
- active supplier
- priority band `recovery_priority`
- queue control `Prioritised #1`
- latest imported batch `entertainment_trading_source_20260430T142821Z_e9a97b901ad3`
- dashboard position `1`
- queue state `Recommended`
- latest dashboard unprocessed rows after recovery import: `20,083`

Important:
- do not create a scanner-ready recovery batch from Product Database rows alone
- F061 needs SKU/title/barcode/cost/currency/VAT
- the only located old Entertainment Trading evidence currently has `Name not found`, `No Data`, ASIN/barcode values, and no supplier cost

Safe recovery seed sources:
- original Entertainment Trading price file
- old manager batch rows with cost/title/barcode
- old F061 active-run backup with pending/completed state

Unsafe recovery seed sources:
- Product Database rows without supplier cost
- ASIN-only output rows
- rows where title is `Name not found`

Current imported recovery source:
- source artifact: `C:\Users\Luke\Desktop\Amazon price files\Entertainment Trading\Processed\Stocklist_20260430T142821Z_e9a97b901a.xlsx`
- source SHA256: `DC6458F69D43F50505C17E4E3BC13D2237F1A6EDAD765947740B5AE44153AE9C`
- source rows: `42,717`
- scan-ready rows: `42,449`
- held rows: `268`
- held reasons: `invalid_barcode_format=214`, `missing_barcode=54`

Current F061 recovery progress import:
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
- recovery progress output: `out/systems/F/price_list_manager/test_mode/f061_recovery_progress.csv`
- recovery health check: `f061_recovery_progress_import_reconciliation=ok`
- rule: use the old F061 active-run file only as progress evidence, not as the source price file

Current handoff state:
- staged supplier: `entertainment_trading`
- staged rows: `20,083`
- `live_apply_allowed=0`
- `live_write_attempted=0`
- `live_write_succeeded=0`
- block reason: `handoff_approval_required`
- live F061 inbox active-run rows: `0`

Decision-reader rule:
- use the last appended manager decision as the current recommendation
- do not sort manager decisions by `decided_at_utc` when deciding the latest action
- reason: old test-mode decisions can contain future timestamps and would otherwise override the current recovery decision

## Rashmian URL Download
Rashmian source URL:
- `https://www.rashmian.com/fdownload.php?feedDownload=Y`

Current result:
- the URL is reachable
- unauthenticated script download returns the Rashmian login HTML page, not a price file
- manager source state is `error`
- dashboard file state is `Error`
- queue state is `Blocked`
- notes include `remote_type=auth_required_html_response`

Current decision:
- do not import the downloaded HTML as a price file
- Rashmian needs an authenticated download path before on-demand import can work

## Manual Request Supplier Behavior
Example suppliers: DHB, Bliss.

Expected behavior:
- if a request is not due, do nothing
- if a request is due, produce a `request_manual_price_file` action
- after the file arrives, store it as a new batch
- if the same monthly file is already scanned, do not scan it again

## Daily Email Supplier Behavior
Example supplier: TD Synnex.

Expected behavior:
- store each new attachment as a batch
- dedupe exact duplicate files by hash
- compare row hashes against memory
- scan only:
  - new rows
  - changed cost rows
  - cooldown-expired rows
- skip unchanged rows that are still inside cooldown

## API Supplier Behavior
Expected behavior:
- run API pull only when acquisition is due
- record API response metadata
- create a batch only when the response content or row hashes changed
- keep errors visible in manager health

## Health Checks
Required manager checks:
- `supplier_registry_unique_ids`
- `supplier_registry_active_methods_present`
- `price_list_batch_source_exists`
- `price_list_batch_file_hash_present`
- `batch_row_count_reconciliation`
- `placeholder_result_count_reconciliation`
- `barcode_memory_unique_active_keys`
- `cooldown_policy_known_fail_codes`
- `manager_decision_single_next_action`
- `f061_handoff_disabled_in_test_mode`

Pass condition:
- all required checks are `ok`

Warn condition:
- supplier has no recent source file but that is expected for its cadence
- manual request is due
- email/API source is waiting for next file
- unknown fail code is held without live scan

Fail condition:
- count reconciliation breaks
- duplicate active memory keys exist
- batch has no source hash
- manager tries to write live F061 files in test mode
- manager recommends live handoff when F061 owner state is busy or unknown

## Failure Recovery
If counts do not reconcile:
- stop at the earliest mismatch
- fix the conversion or manager count logic
- do not patch the report to make totals look right

If cooldown behavior is wrong:
- fix the cooldown mapping table or memory key selection
- do not manually edit final recommendations

If acquisition fails:
- record the failure in manager health
- keep the previous batch untouched
- recommend the next safe action

If F061 owner state is unclear:
- do not hand off
- leave manager in recommendation-only mode
- document the exact missing owner evidence

## Archive Note
When this plan is complete, preserve:
- final supplier registry format
- final batch status model
- cooldown policy table
- fake scanner test proof
- first real supplier proof
- F061 handoff proof, if Phase 6 is approved
