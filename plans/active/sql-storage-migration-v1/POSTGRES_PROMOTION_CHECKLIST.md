# PostgreSQL Promotion Checklist - Product DB

Updated: 2026-05-01T21:01:46Z

## Position

- PostgreSQL remains the production target.
- SQLite is still local proof only.
- No PostgreSQL promotion was performed in this block.
- No credentials, live database connection, Google Sheet change, A/B/H runtime proof, or scheduler change was used.
- Current next-phase planning is in `plans/active/sql-product-db-ui-authority-phase2-2026-05-01/CODING_PLAN.md`.

## Required Preconditions

- User approves the PostgreSQL promotion window explicitly.
- A fresh backup exists for code, config, local SQL, Product DB mirror/export files, and O proof outputs.
- Production PostgreSQL connection details are configured through `SELLERONE_DATABASE_URL`.
- Optional PostgreSQL driver is installed and verified.
- Product DB SQL table contract is created in PostgreSQL with `seller_sku` as primary key and ASIN as controlled non-unique.
- Rollback export path is tested before cutover.
- Last 3 publish/export snapshots are retained.

## Promotion Sequence

1. Pause or isolate writers that can mutate Product DB surfaces.
2. Prove no unauthorized owner is writing Product DB mirror/export files.
3. Seed PostgreSQL from the local SQL Product DB table, not from stale `out/product_db_preview.csv`.
4. Validate PostgreSQL row count and unique `seller_sku` count against local SQL.
5. Export PostgreSQL back to a CSV mirror and reconcile row count, `seller_sku` set, and required columns.
6. Run O030 against PostgreSQL-backed Product DB authority.
7. Run P014 dry-run against PostgreSQL-backed authority.
8. Run P015 authority rehearsal with PostgreSQL as the authority source.
9. Keep Google Sheet `Product_DB` as legacy/export-only only after explicit cutover approval.

## Required Tests Before Live Promotion

- Storage adapter PostgreSQL optional-driver behavior.
- Product DB table DDL test for PostgreSQL syntax.
- Product DB seed/export/reconcile test.
- P014 edit-event apply test against a PostgreSQL test database or disposable schema.
- O030 Product DB operator view test with SQL authority.
- P015 authority rehearsal test with stale CSV mirror present.

## Rollback Rule

- If PostgreSQL seed, validation, O view, or mirror export mismatches, stop promotion.
- Keep local SQLite/CSV compatibility in place.
- Do not alter Google Sheets to force a match.
- Record the mismatch in the active coding plan before retrying.

## Completion Gate

Promotion is complete only when:

- PostgreSQL has the Product DB authority table.
- UI edits write through the approved SQL edit-event path.
- CSV mirror is explicitly export-only.
- Product_DB Google Sheet is explicitly legacy/export-only.
- Rollback export has been tested.
- All scoped Product DB/O tests pass.
