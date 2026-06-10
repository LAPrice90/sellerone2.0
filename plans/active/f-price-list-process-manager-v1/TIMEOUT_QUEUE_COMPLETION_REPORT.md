# F Scanner Timeout Queue Completion Report

Date: 2026-05-01
Scope: F price-list process manager and F061 scanner timeout memory.

## Summary

The timeout queue system is now implemented and live-proven.

The manager can keep the full supplier price file for audit, but it now filters timed-out barcodes before F061 staging. This means failed barcodes do not keep consuming scan capacity each time a supplier file is loaded.

## What Was Built

### 1. Timeout Policy

The scanner timeout policy now has practical wait periods by fail reason.

Current key decisions:
- Standard commercial wait: 90 days.
- Higher-end wait: 180 days.
- Hazmat wait: 365 days.
- Price history fail: 180 days.
- Technical retry or scrape failure: shorter retry windows.
- Cost-sensitive fails can re-enter when supplier cost changes.

`NO_PRICE_HISTORY_365D` now maps to `PRICEHISTORYFAIL`, not generic `RESCAN`.

### 2. Shared Timeout Queue Helper

Added:
- `scripts/flows/F/price_list_manager/timeout_queue.py`

This helper decides whether each supplier row should:
- scan now
- skip because timeout is active
- skip because it was already processed
- hold because required data is missing
- re-enter because timeout expired
- re-enter because cost changed

### 3. Early Filtering After Import And Enrichment

Updated:
- `FPM011_import_ready_sources.py`
- `FPM012_enrich_batch_rows_for_f061.py`
- `FPM040_build_next_action.py`

Result:
- `batch_rows.csv` keeps the full supplier file.
- `batch_scan_eligibility.csv` only marks rows that should actually scan.
- `price_list_batches.csv` now records eligible rows and skipped-timeout rows.

### 4. Live F061 Result Memory Import

Added:
- `FPM126_update_memory_from_f061_results.py`

Updated:
- `FPM130_run_live_cycle.py`

After each successful F061 child chunk, finalized F061 screening results are imported into:
- `out/systems/F/price_list_manager/test_mode/barcode_scan_memory.csv`

This is the memory used to stop rescanning the same failed barcode later.

### 5. Graceful FPM130 Reload

FPM130 now supports a clean reload request.

If `out/locks/maintenance.requested` contains:
- `action=reload`
- `exit_after_drain=1`

Then FPM130 will:
- finish the current child chunk
- write `F_restart_drain.ready`
- write status `drain_exit`
- release `live_cycle.lock`
- exit by itself

This avoids needing to kill an elevated Python process from a non-admin session.

## Memory Rules

One shared memory table is used. We are not keeping separate supplier timeout lists.

Product-level failures use global barcode memory:
- `barcode:<barcode>`

Examples:
- `NOASIN`
- `OVER50K`
- `HAZMATFAIL`
- `PRICEHISTORYFAIL`
- `SELLERHISTORYFAIL`
- `BRANDFAIL`
- `NODATE`
- `REVIEWFAIL`
- `LOWSALESFAIL`

Cost-sensitive failures use supplier-offer memory:
- `supplier_offer:<supplier_id>:<barcode>:<unit_cost>`

Examples:
- `NOCOST`
- `ROIFAIL`
- `LOWROI`

This matters because a barcode can be bad for one supplier cost but viable at a lower cost later.

## Live Proof

Admin restart proof:
- Old FPM130 owner pid `24560` was stopped through elevated UAC helper.
- New owner pid `20456` started and resumed the same Entertainment Trading run.

Graceful reload proof:
- Reload requested with `exit_after_drain=1`.
- FPM130 exited itself at `drain_exit`.
- `live_cycle.lock` was released.
- Scheduled task restarted a fresh owner pid `25688`.

Final live state:
- Current owner pid: `25688`
- Active supplier: `entertainment_trading`
- Active F061 run: `fpm_entertainment_trading_20260430T151417Z`
- Latest observed status time: `2026-05-01T12:16:01Z`
- Pending rows: `18308`
- Chunk size: `5`
- State: `running`

Latest live memory events:
- `2026-05-01T12:01:28Z`: scanner chunk success, pending `18323`, memory import success, memory rows `1904`
- `2026-05-01T12:04:41Z`: scanner chunk success, pending `18318`, memory import success, memory rows `1909`
- `2026-05-01T12:08:10Z`: scanner chunk success, pending `18313`, memory import success, memory rows `1915`
- `2026-05-01T12:11:30Z`: scanner chunk success, pending `18308`, memory import success, memory rows `1921`

Memory file proof:
- File: `out/systems/F/price_list_manager/test_mode/barcode_scan_memory.csv`
- Rows: `1921`
- Unique memory keys: `1921`
- Last write UTC: `2026-05-01T12:15:51Z`

Latest memory health rows:
- `f061_result_memory_import`: `ok`
- `f061_result_memory_unique_keys`: `ok`
- `f061_result_memory_cost_scope`: `ok`

## Tests

Compile proof passed for touched modules.

Focused tests:
- `8 passed`

Broader touched manager suite:
- `58 passed`

Earlier timeout/import/enrichment proof:
- Focused timeout/import/enrichment tests passed.
- Broad manager tests passed.

Pytest emitted a Windows temp cleanup `PermissionError` after pass summaries in some runs. The tests had already passed and returned exit code `0`.

## Safety Notes

No Google Sheets writes were made.

No live F061 active-run rows were manually edited or pruned.

The active Entertainment Trading run was resumed through the normal FPM130 owner path.

The timeout queue does not delete supplier rows. It only prevents timed-out rows from being staged into scanner eligibility.

## Result

Completed:
- timeout policy
- early timeout filtering
- shared timeout queue helper
- live result memory importer
- graceful FPM130 reload
- live memory-import proof

Not yet observed:
- next manager batch-selection boundary using this larger live memory table to filter a brand-new supplier batch.

That will happen when the current Entertainment Trading active run reaches a manager selection boundary or a new supplier batch is prepared.

## Next Move

No further action needed now.

At the next manager batch-selection boundary, verify:
- `batch_scan_eligibility.csv` is rebuilt
- active-timeout rows are skipped
- staged F061 rows equal eligible scan rows only
- active-timeout rows staged to F061 equals `0`
