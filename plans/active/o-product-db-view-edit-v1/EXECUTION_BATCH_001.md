# Execution Batch 001

## Batch title
- Product DB operator view contract and merged read model

## Goal
- Build the first trustworthy browse dataset before any product database UI page is implemented.

## Scope
- In scope:
  - new `product_db_operator_view.csv` contract
  - read model that merges product preview, O status, ordered stock, and E demand/economics overlays
  - focused tests
- Out of scope:
  - browse page UI
  - edit page UI
  - apply path to product truth

## Files allowed
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/_source_contracts.py`
- `scripts/flows/O/O030_build_product_db_operator_view.py`
- `tests/test_o000_paths_and_schemas.py`
- `tests/test_o030_build_product_db_operator_view.py`

## Implementation notes
- Start from `out/product_db_preview.csv` as the fixed-truth base.
- Add O overlays:
  - `restock_review_queue`
  - `ordered_stock_state`
- Add E overlays:
  - `sku_sales_velocity`
  - `sku_performance_summary`
- Build one displayed `operational_status` field with locked precedence.
- Include issue flags for missing pack or cost truth.

## Verification
- Command:
  - targeted `pytest` for new O030 logic and O schema coverage
- Expected:
  - one row per SKU
  - stable status mapping
  - no duplicate identity rows
  - explicit issue flags for incomplete pack truth

## Batch completion rule
- Do not mark this batch complete until the merged snapshot contract is implemented and the focused tests pass.
