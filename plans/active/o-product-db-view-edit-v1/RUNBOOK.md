# Runbook

## Purpose
- give the operator one clean place to browse product truth
- keep manual changes in a separate edit workflow
- stop the reorder page from becoming the accidental product database

## Standard run order
```powershell
# Batch 001 target, once implementation starts
pytest tests/test_o030_build_product_db_operator_view.py
pytest tests/test_o410_product_database_ui.py
pytest tests/test_o420_product_database_edit_ui.py
```

## Validation steps
- Step 1:
  - open the product database browse page and confirm summary counts load
- Step 2:
  - search by SKU, ASIN, supply code, and title
- Step 3:
  - expand one row and confirm all secondary detail groups render
- Step 4:
  - open the separate edit page for one SKU and submit a change
- Step 5:
  - confirm the edit lands in `product_db_edit_events.csv`
- Step 6:
  - confirm invalid edits land in `product_db_edit_holds.csv` instead of silently disappearing

## Expected outputs
- Output:
  - browse snapshot
- Path:
  - `out/systems/O/live/product_db_operator_view.csv`
- What good looks like:
  - one row per SKU with clear status, supplier, pack, stock, ordered, demand, and economics glance fields

- Output:
  - edit submissions
- Path:
  - `out/systems/O/inbox/product_db_edit_events.csv`
- What good looks like:
  - one clean row per saved SKU edit

- Output:
  - edit holds
- Path:
  - `out/systems/O/live/product_db_edit_holds.csv`
- What good looks like:
  - bad edits are held with plain-English reasons

## Health checks
- Check:
  - product-db preview freshness
- Pass condition:
  - source preview is within expected freshness window
- Warning condition:
  - source preview is stale but still readable
- Fail condition:
  - source preview missing or too stale for safe operator use

- Check:
  - operator-view row uniqueness
- Pass condition:
  - one row per `seller_sku`
- Warning condition:
  - duplicate rows detected but isolated to known edge case
- Fail condition:
  - duplicate identity rows break browse trust

- Check:
  - edit-hold visibility
- Pass condition:
  - invalid edits are visible in holds
- Warning condition:
  - hold detail is too vague
- Fail condition:
  - invalid edits are silently dropped or applied

## Failure recovery
- If input is stale:
  - keep the page read-only and show the stale warning clearly
- If output is missing:
  - rebuild the merged operator view first; do not bypass it by making the UI read raw source files directly
- If tests fail:
  - stop and record whether the failure is in merge logic, display grouping, or edit validation
- If runtime ownership is unclear:
  - stay in read-only mode and avoid building an apply path
- If proof would clash with a live loop:
  - not expected for the browse page; for later write/apply work, plan the forced proof window first

## Archive note
- Preserve:
  - the final field ownership split
  - the status precedence rules
  - the browse-vs-edit boundary
