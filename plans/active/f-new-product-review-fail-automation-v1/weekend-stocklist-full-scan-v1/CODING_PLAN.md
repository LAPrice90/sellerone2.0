# Coding Plan

## Current Phase
- Phase 1: Add a tested queue-order option to the existing F010 reset tool - complete.
- Phase 2: Apply a `remaining-first` stocklist queue reset - complete.
- Phase 3: Start the existing full F061 scanner wrapper - complete.
- Phase 4: Brief startup validation only - complete.

## Allowed Files
- `scripts/one_off/F010_reset_webscrape_coverage_queue.py`
- `tests/test_f010_reset_webscrape_coverage_queue.py`
- `plans/active/f-new-product-review-fail-automation-v1/weekend-stocklist-full-scan-v1/*`
- F queue/output artifacts owned by F010 and F061 during execution.

## Tests
- `python -m py_compile scripts/one_off/F010_reset_webscrape_coverage_queue.py tests/test_f010_reset_webscrape_coverage_queue.py`
- `pytest tests/test_f010_reset_webscrape_coverage_queue.py -q`

## Queue Apply
- Dry-run first with:
  - `python scripts/one_off/F010_reset_webscrape_coverage_queue.py --supplier-id stocklist_supplier --queue-order remaining-first`
- Apply only after tests pass:
  - `python scripts/one_off/F010_reset_webscrape_coverage_queue.py --supplier-id stocklist_supplier --queue-order remaining-first --apply`

## Runtime Launch
- Use existing wrapper:
  - `run_F_supplier_full_legacy_scan.bat stocklist_supplier`

## Success Threshold
- Queue is rebuilt with unprocessed rows first.
- `supplier_price_list_run_state.csv` shows `pending_rows` matching the prepared queue.
- Scanner process starts and writes to `out/systems/F/live/f061_hometime.log`.

## Current Runtime Status
- Status: `running`.
- Last startup-proof pending count: `37186`.
- Last startup-proof done count: `15`.

## Stop Rule
- If F010 tests fail, do not apply the queue.
- If queue apply fails, do not start the scanner.
- If scanner launch does not create a live process or log movement, report startup not proven.
