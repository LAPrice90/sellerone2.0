# Weekend Stocklist Full Scan

## Purpose
- Prepare the Stocklist Supplier queue for unattended weekend scanning.
- Prioritize rows that have not been processed yet.
- Keep already-scraped rows available after the unprocessed remainder.

## Scope
- Supplier: `stocklist_supplier`
- Owner path: `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- Queue preparation: `scripts/one_off/F010_reset_webscrape_coverage_queue.py`
- Launch wrapper: `run_F_supplier_full_legacy_scan.bat`

## Guardrails
- No Google Sheets writes.
- No local DB alignment changes.
- No A scripts.
- No full F061 rescan before queue preparation.
- No B scripts run manually.
- No WORK_LOG update unless the user approves.

