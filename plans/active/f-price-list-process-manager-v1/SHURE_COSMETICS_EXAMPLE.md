# Shure Cosmetics First Example

Date: 2026-04-30

## Decision
Use Shure Cosmetics as the first price-list process manager example.

Manager classification:
- `source_type`: `api_pull`
- `source_subtype`: `csv_link`
- reason: this is not a credentialed API, but it is still a machine-pulled source URL rather than a manual request or email attachment

Registered config:
- `config/feeder/price_list_manager/suppliers.csv`

Existing supplier setup:
- `config/feeder/suppliers/shure_cosmetics.json`
- `scripts/flows/F/suppliers/shure_cosmetics.py`
- source URL: `https://aux.shure-cosmetics.co.uk/pricelist/`
- existing converter output: universal F supplier format

## Evidence Checked
Safe source check:
- HEAD request to source URL returned status `200`
- content type returned `text/csv;charset=UTF-8`

Safe converter check:
- fixture used: `tests/fixtures/f_phase1/shure_cosmetics_raw_fixture.csv`
- command used converter function directly, not F005
- valid rows returned: `2`
- hold rows returned: `0`

Important safety note:
- I did not run `F005_build_supplier_price_list_universal.py` against the live repo because its current flow resets F live scanner workspace outputs before writing a fresh active run.
- The current live scanner has an active longer run, so the process-manager example must stay config/test-mode only.

## Existing Converter Behavior To Remember
The Shure converter currently:
- reads CSV using UTF-8 with Latin-1 fallback
- maps SKU from `SKU`
- maps barcode from `Barcode`
- maps cost from `Price`
- maps title from `Title`
- skips blank SKU rows
- skips SKUs ending with `DD`
- strips non-digits from barcode text

Observed fixture detail:
- `EAN 5012345678901` becomes `5012345678901`
- `SC-2002DD` is skipped because of the `DD` suffix
- `ABC123` becomes `123` and is currently treated as valid by the converter
- blank SKU row is skipped

Manager follow-up rule:
- the price-list manager should add barcode validity health before scanner handoff, so short digit-only leftovers like `123` are blocked or held instead of being treated as clean scan rows.

## First Example Expectations
When Phase 1 code exists, Shure should be the first registry row loaded into test mode.

Expected test behavior:
- source is treated as due on a daily cadence
- source acquisition adapter is `api_pull/csv_link`
- converter is `shure_cosmetics`
- live F061 handoff remains disabled
- manager decision can recommend test-mode conversion or placeholder scan only
