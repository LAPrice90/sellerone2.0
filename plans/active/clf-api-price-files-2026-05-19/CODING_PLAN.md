# CLF API Price Files Plan

Created UTC: 2026-05-19T11:14:44Z

## Goal
Bring CLF into the normal F price-list manager automation without manual file handling.

Plain-English route:
- CLF credentials stay in the ignored local secrets folder.
- The manager asks CLF for a fresh login token.
- The manager downloads product codes and product data in batches.
- The CLF converter turns barcode and cost rows into normal scanner rows.
- The live F owner may pick CLF only at a normal F061 boundary.

## Current Evidence
- CLF supplier row exists in `config/feeder/price_list_manager/suppliers.csv`.
- CLF adapter exists at `scripts/flows/F/suppliers/clf.py`.
- Local secret exists at `secrets/price_list_manager/clf_api.json`.
- Direct CLF API proof on 2026-05-19 returned `16457` SKUs and wrote `16456` source rows with barcodes.
- Converter proof produced `16172` scanner-ready rows and `284` held rows.

## Current Phase
Status: monitored validation.

Allowed files for this phase:
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `tests/test_fpm130_live_cycle.py`
- `plans/active/clf-api-price-files-2026-05-19/CODING_PLAN.md`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`

## Implementation
- Add URL-download and API-fetch refresh calls to the live F manager refresh path.
- Keep CLF active in the supplier registry.
- Do not interrupt the active TD Synnex F061 run.
- Let CLF queue behind the current active F run unless a later controlled boundary is approved or naturally reached.

## Tests And Proof
- Run focused CLF/API tests.
- Run FPM130 live-cycle tests.
- Run the broader FPM profile used for price-list manager changes.
- Check live F status after the patch and confirm current owner is still processing TD Synnex.

Completed proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\price_list_manager\FPM014_fetch_api_sources.py scripts\flows\F\suppliers\clf.py` passed.
- `python -m pytest tests\test_fpm130_live_cycle.py tests\test_fpm014_fetch_api_sources.py tests\test_clf_supplier_converter.py -q` passed with `69 passed`.
- `python -m pytest tests\test_fpm011_import_ready_sources.py tests\test_fpm016_fetch_gmail_email_sources.py tests\test_fpm110_run_test_mode_cycle.py tests\test_fpm130_live_cycle.py tests\test_fpm014_fetch_api_sources.py tests\test_clf_supplier_converter.py -q` passed with `87 passed`.
- F owner reloaded at a controlled drain boundary and restarted as PID `34564`.
- Live F061 child restarted as PID `6960`.
- Live TD Synnex active run continued from `43039` pending to `43014` pending after reload.
- CLF queue control set to `prioritised` rank `1`.
- Due check recorded as `F_CLF_NEXT_BATCH_SELECTION` in `project_control/DUE_CHECK_REGISTER.csv`.

## Live Monitoring Target
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/inbox/supplier_price_list_active_run.csv`
- `out/systems/F/inbox/supplier_price_list_run_state.csv`

Poll cadence:
- First check immediately after tests.
- Then leave the active TD run uninterrupted.

Success condition:
- Live owner remains single-owner.
- Current TD active run is not replaced.
- CLF is active in registry and available to the next normal manager refresh.
- At the next batch-selection boundary, CLF is selected or becomes the live active supplier.

If it fails:
- If live owner is missing, run `python -m scripts.flows.F.price_list_manager.FPM170_supervise_live_cycle --once`.
- If live owner is busy, do not start a second owner.
- If CLF is selected while F061 is busy, keep it staged/queued and wait for the normal boundary.
