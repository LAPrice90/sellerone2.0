# Product DB Contract

Created: 2026-05-01

## Purpose

This contract prevents Product DB drift. Product DB is the bottleneck for scanner, pricing, and operations, so this file defines one write authority, identity rules, mirror rules, schema rules, and safe linking behavior.

## Authority Decision

### Target Write Source

Approved target authority: SQL Product DB.

Plain-English rule:

- The UI is the place humans edit products.
- SQL is the place the product truth is stored.
- Google Sheets are no longer the intended Product DB authority.
- The repricer tracker Sheet is allowed as a temporary operator output only until a UI tracker replaces it.
- CSV files are not the Product DB authority.
- SQLite is allowed for local development and proof, but production authority should follow the project-level PostgreSQL decision in `project_control/DECISIONS.md`.

Current repo evidence still shows legacy Sheet/CSV behavior:

- `project_control/SOURCE_AUTHORITY_REPORT.md` classifies `out/product_db_preview.csv` as a local dump of the `Product_DB` Google Sheet.
- A/B scripts repeatedly export or refresh `out/product_db_preview.csv` from Product DB sheet behavior.
- Current downstream code reads `out/product_db_preview.csv`, but comments and file names call it a preview, dump, or local copy.
- SQLite table `sys_product_db_preview` is currently a storage mirror created from CSV/export behavior, not yet the approved production Product DB authority.

That means there are two states:

- Current state: legacy Product DB truth is still partly Sheet/CSV shaped.
- Target state: Product DB truth must move to SQL, edited through the UI.

### Mirror Rules

- SQL Product DB = only approved future write authority.
- UI = approved human editing surface for SQL Product DB.
- `Product_DB` Google Sheet = legacy view/export only after SQL cutover.
- Repricer tracker Google Sheet = temporary operator output, not data authority, until replaced by a UI view.
- `out/product_db_preview.csv` = read-only local mirror/export.
- `out/sql/sellerone_dev.sqlite3:sys_product_db_preview` = local development/proof mirror until the SQL Product DB table is deliberately promoted.
- `out/db_snapshot.csv` = audit snapshot only.
- `out/systems/O/live/product_db_operator_view.csv` = operator view only.
- `out/systems/O/inbox/product_db_edit_events.csv` = staged edit-event inbox, not Product DB itself.

No script should silently patch `out/product_db_preview.csv`, Sheets, or a SQL mirror to "fix" Product DB. Fixes must happen through the approved SQL write path after migration, or through an approved staged edit path before migration.

## Identity Rules

### Primary Key

Hard rule:

```txt
seller_sku = PRIMARY KEY
```

Reason:

- Original audit Product DB snapshot had 608 rows and 608 unique `seller_sku` values.
- Current local SQL Product DB proof has 659 rows and 659 unique `seller_sku` values after approved scanner inserts.
- SKU is the stable internal operating identity used by pricing, operations, and order/token flows.

### ASIN Rule

Hard rule:

```txt
asin = CONTROLLED NON-UNIQUE
```

Reason:

- Current Product DB snapshot has duplicate ASINs: `0786964502`, `B07RRQX71T`, `B09NQ9ZHDQ`.
- A single ASIN can reasonably map to more than one sellable SKU in some pack, bundle, condition, marketplace, or listing-transition cases.
- Therefore ASIN must not be treated as a primary key unless the business later decides that Product DB must be one row per ASIN.

Controlled non-unique means:

- Blank ASIN is allowed only for rows not yet Amazon-linked.
- Duplicate ASIN is allowed only when each row has a distinct `seller_sku`.
- Duplicate ASIN rows must have a reason classification before automated linking trusts them.
- Link logic may use ASIN to find candidates, but must not update by ASIN alone when more than one Product DB row has that ASIN.

## Schema Rules

### Required Header Rules

- Header names must be unique.
- `seller_sku` must exist.
- `asin` must exist.
- Required downstream fields must not be silently renamed in audit exports.
- Duplicate headers are a hard schema failure.

Current known failure:

```txt
duplicate header: last_updated_A003
```

Required fix location:

- Product DB source schema or the export logic that creates `out/product_db_preview.csv`.
- Do not fix this only in `out/db_snapshot.csv`.

### Minimum Required Fields

Core identity:

- `seller_sku`
- `asin`
- `title`
- `brand_name`
- `main_image`
- `sale_status`

Supplier and cost:

- `supplier_code`
- `supplier_name`
- `supplier_pack_size`
- `amazon_pack_size`
- `supplier_catalog_price`
- `last_purchase_price`
- `vat_rate`

Pricing and fees:

- `fba_fee_10`
- `fba_fee_100`
- `referral_fee_10`
- `referral_fee_100`
- `live_listing_price`

Stock:

- `stock_total`
- `stock_available`
- `stock_reserved`
- `stock_inbound`

Audit timestamps:

- `last_updated`
- source-specific update columns, with no duplicate names

## Scanner To Product DB Link Rules

The scanner must not write Product DB directly.

Scanner output should first pass a non-destructive link simulation:

```txt
ASIN | Exists_in_DB | Match_Count | Action | Reason
B0XXX | NO | 0 | WOULD INSERT | no_product_db_asin_match
B0YYY | YES | 1 | WOULD UPDATE | single_product_db_asin_match
B0ZZZ | YES | 2 | REVIEW | multiple_product_db_asin_matches
```

Action rules:

- `WOULD INSERT`: ASIN not found in Product DB.
- `WOULD UPDATE`: ASIN found exactly once and target `seller_sku` is unambiguous.
- `REVIEW`: ASIN found more than once, ASIN blank, scanner duplicate, missing supplier SKU, or schema failure.
- `BLOCKED`: Product DB schema is broken or source data is missing required identity columns.

No Product DB write may happen from link simulation output.

## Scanner Duplicate Rule

Before link simulation, scanner rows must be de-duplicated or blocked using this logical key:

```txt
asin + supplier_sku
```

Required behavior:

- Exact duplicate `asin + supplier_sku` rows must collapse to one row.
- Same ASIN with different supplier SKU must remain visible but be marked as duplicate-ASIN review context.
- Blank ASIN rows must not be candidates for automatic Product DB link action.

Current known scanner issue:

```txt
duplicate ASIN: B0DPMGDZLZ
```

## Pricing Output Rule

Pricing proof must not contain blank write status.

Required rule:

```txt
execution_write_status MUST NOT be blank
```

Allowed normalized values:

- `APPLIED`
- `NO_WRITE_REQUIRED`
- `READ_ONLY_NO_WRITE`
- `OBSERVABILITY_BLOCK_NO_WRITE`
- `NO_ATTEMPT`
- `BLOCKED`
- `ERROR`
- `WRITE_NOT_APPLIED`

Current known issue:

```txt
Latest finalized H runtime proof run 20260501T183549Z has 0 blank execution_write_status rows and 0 invalid execution_write_status rows.
out/pricing_output.csv is a stale audit export with 20 historical blank rows and must not be treated as the latest H runtime source.
```

## Enforcement Order

1. Freeze the authority decision: Product DB target authority is SQL, edited through the UI.
2. Define the SQL Product DB table contract before moving writes.
3. Build a one-way legacy import/check from current Sheet/CSV shape into SQL staging.
4. Fix duplicate Product DB header at the source before import.
5. Add schema validation before SQL import, export, or mirror use.
6. Enforce `seller_sku` primary key in SQL.
7. Classify duplicate ASINs as controlled non-unique.
8. Build non-destructive scanner link simulation.
9. Add scanner duplicate gate.
10. Normalize pricing output write statuses.

## Implementation Artifacts

Current local implementation slice as of 2026-05-01:

- SQL Product DB table contract helper: `scripts/core/storage/product_db_contract.py`
- Product_DB duplicate header export repair helper: `coalesce_duplicate_header_rows` / `dataframe_from_product_db_sheet_rows` in `scripts/core/storage/product_db_contract.py`
- Non-destructive Product DB legacy source contract check: `scripts/one_off/P008_product_db_sql_contract_check.py`
- Product DB source health output: `out/systems/O/live/product_db_source_health.csv`
- Product DB staged import proof outputs: `out/sql_migration/product_db_contract/`
- Read-only scanner to Product DB link simulation: `scripts/one_off/P009_product_db_link_simulation.py`
- Read-only Product DB review pack: `scripts/one_off/P010_product_db_review_pack.py`
- Scanner `asin + supplier_sku` identity proof: `scripts/one_off/P012_scanner_identity_check.py`
- Repricing write-status proof summary: `scripts/one_off/P013_repricing_write_status_proof.py`
- Repricer tracker UI read model: `scripts/flows/O/O050_build_repricing_tracker_view.py`
- Repricer tracker UI page: `scripts/flows/O/O450_repricing_tracker_ui.py`, exposed in O400 as `Repricer Tracker`
- Product DB local edit-event applier: `scripts/one_off/P014_apply_product_db_edit_events.py`
- Product DB SQL authority rehearsal proof: `scripts/one_off/P015_product_db_sql_authority_rehearsal.py`
- Repricer tracker UI cutover check: `scripts/one_off/P016_repricing_tracker_ui_cutover_check.py`
- Repricer tracker UI parity proof: `scripts/one_off/P017_repricing_tracker_ui_parity_check.py`
- Product DB mirror drift guard: `scripts/one_off/P018_product_db_mirror_drift_guard.py`
- Product DB reader dependency map: `scripts/one_off/P019_product_db_reader_dependency_map.py`
- Offline PostgreSQL promotion rehearsal: `scripts/one_off/P020_product_db_postgres_promotion_rehearsal.py`
- SQL Product DB / UI authority Phase 2 sign-off bundle: `scripts/one_off/P021_sql_product_db_ui_authority_phase2_signoff.py`

Current proof position:

- Current SQL Product DB rows: 659.
- Current SQL Product DB unique `seller_sku`: 659.
- Current legacy CSV mirror rows: 608.
- Current Product DB source columns in latest contract check: 71.
- Product DB duplicate header `last_updated_A003` is fixed in the current local preview and protected in A/B Product DB export/update paths.
- Product DB staged import now passes into local SQLite staging.
- Duplicate ASINs are reported for review, not treated as a primary-key violation.
- Scanner link simulation is implemented and local-only.
- The scanner duplicate ASIN `B0DPMGDZLZ` remains visible as two rows with supplier SKUs `1320217` and `1320221`; it is not collapsed because only exact `asin + supplier_sku` duplicates collapse.
- Product DB review pack is implemented and local-only. Current duplicate ASIN review output has 3 rows: 2 suggested `legacy_or_replacement_listing_candidate`, 1 suggested `inactive_duplicate_candidate`; all remain `needs_user_decision`.
- Current scanner link review output has 51 rows: 49 `WOULD INSERT`, 2 `REVIEW`, and 0 `BLOCKED`.
- User policy decision recorded on 2026-05-01: different supplier/SKU rows for the same ASIN are separate products and must not be sold together. Classification reason: `different_sku_separate_product_not_sold_together`.
- Scanner Product DB insert path is implemented as `scripts/one_off/P011_apply_scanner_product_db_inserts.py`.
- Current SQL Product DB table `out/sql/sellerone_dev.sqlite3:product_db_products` has 659 rows and 659 unique `seller_sku` values after inserting 51 scanner products.
- Current local SQL Product DB remains 659 rows and 659 unique `seller_sku`.
- The legacy local Product DB mirror `out/product_db_preview.csv` can be rewritten by existing A/B owner behavior and was observed back at 608 rows during the 2026-05-01 home-time block. This is stale mirror evidence, not SQL authority.
- O030 now prefers local SQL `product_db_products` when present and rebuilt `out/systems/O/live/product_db_operator_view.csv` with 659 rows from SQL authority.
- P014 applies Product DB edit events only to local SQL plus mirror export, defaults to dry-run, requires `--apply --confirm-product-db-edit-apply`, and blocks unsafe ASIN identity changes.
- P015 currently reports SQL rows 659, SQL unique `seller_sku` 659, O view rows 659, CSV mirror rows 608, and status `warn` because the CSV mirror is stale.
- Scanner identity check now reports 51 scanner rows, 51 unique `asin + supplier_sku` keys, 0 exact duplicate keys, 0 blank ASIN rows, 0 missing supplier SKU rows, and 1 same-ASIN/different-supplier-SKU context row.
- P008 now reports 0 duplicate-ASIN rows requiring review because all duplicate-ASIN groups are classified; the remaining Product DB contract status is `warn` only because blank ASIN rows still exist.
- Repricer tracker UI exists and its read model is clean against the latest finalized H runtime source. Full operator cutover from the temporary Sheet still needs an explicit cutover decision.
- User-approved contract decision on 2026-05-01: `WRITE_NOT_APPLIED` is an approved write-status value because it is already produced by the write-verification path when a write was attempted but not applied.
- Read-only P013 proof classifies blank write-status rows instead of masking them. Current proof at 2026-05-01T18:56:55Z reports latest H terminal run `20260501T183549Z`, terminal state `finalized`, publish status `ok`, publish rows `49`, proof-run runtime rows `49`, runtime blank write-status rows `0`, invalid write-status rows `0`, and unknown blank root-cause rows `0`.
- Current proof-run runtime status counts are `APPLIED=3`, `NO_WRITE_REQUIRED=34`, and `READ_ONLY_NO_WRITE=12`.
- `out/pricing_output.csv` is currently marked stale audit evidence by P013/O050 because it is older than `out/phase1_runtime_floor_snapshot_latest.csv` and has 0 rows for latest proof run `20260501T183549Z`. Its 20 blank rows remain visible as stale audit context, not current H source truth.
- Latest read-only P013 at 2026-05-01T22:08:58Z saw H terminal run `20260501T215343Z` with `terminal_state=finalized`, `terminal_publish_status=ok`, runtime blank write-status rows `0`, and invalid write-status rows `0`.
- Latest P016 at 2026-05-01T22:08:59Z reports `ready_with_stale_audit_warning`, `fail_count=0`, `warn_count=1`, tracker rows `89`, terminal run `20260501T215343Z`, and Sheet status `temporary_fallback_until_explicit_operator_cutover`.
- Latest P017 at 2026-05-01T22:09:00Z reports `ready_with_stale_audit_warning`, `fail_count=0`, `warn_count=0`, missing critical tracker fields `0`, missing dashboard reference fields `0`, tracker rows `89`, and terminal run `20260501T215343Z`.
- Latest P018 at 2026-05-01T22:08:06Z reports `status=warn`, `fail_count=0`, SQL rows `659`, SQL unique `seller_sku` `659`, O view rows `659`, CSV mirror rows `608`, and CSV mirror status `mirror_stale_not_authority`.
- Latest P019 at 2026-05-01T22:08:17Z mapped 298 Product DB references across 87 files, with 0 unknown owners and 58 changes blocked without explicit approval.
- Latest P020 at 2026-05-01T22:08:18Z reports `status=ok`, `fail_count=0`, and production promotion status `not_run_requires_explicit_approval`.
- Latest P021 at 2026-05-01T22:09:01Z reports `complete_locally_pending_explicit_cutover_approvals`, `fail_count=0`, and `warn_count=0`.
- Phase 2 completion report is `plans/active/sql-product-db-ui-authority-phase2-2026-05-01/COMPLETION_REPORT.md`.
- H source code fix applied and live-proven on 2026-05-01: current-cycle no-market-data rows now emit `READ_ONLY_NO_WRITE`, parked rows emit `NO_WRITE_REQUIRED`, and the no-market-data status is re-asserted after truth reconciliation.
- H item-offers timeout root fix applied and live-proven on 2026-05-01: one-cycle retry sweeps pass the remaining retry-aware snapshot budget into the `H_item_offers_lookup.py` watchdog instead of always using the fixed 240-second helper timeout. Run `20260501T183549Z` logged `snapshot_refresh item_offers watchdog_budget_override` with `effective_seconds=609` and completed item-offers in `190.70` seconds.

## Explicit Non-Goals

- Do not change Google Sheets without explicit approval.
- Do not make CSV the authority by accident.
- Do not treat local SQLite as production authority unless explicitly approved as a temporary local-only step.
- Do not patch CSV mirrors to hide source problems.
- Do not change A, B, H, scheduler, or external integrations as part of this contract design.
