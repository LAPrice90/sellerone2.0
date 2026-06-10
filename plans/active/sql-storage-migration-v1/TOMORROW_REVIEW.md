# Tomorrow Review - SQL Product DB And Repricer Tracker

Updated: 2026-05-01T19:16:25Z

## Plain English Position

- Product DB SQL migration moved forward.
- Repricer tracker UI code and read model are in place.
- Repricer tracker UI cutover is not signed off tonight because the latest H terminal run failed after the previous clean proof.
- Google Sheets, A cycle, B cycle, H cycle, and scheduler were not changed by this block.

## Product DB Done Tonight

- Local SQL Product DB still has 659 rows and 659 unique `seller_sku`.
- The legacy CSV mirror was seen being rewritten back to 608 rows by existing owner behavior.
- O030 was changed so the O Product DB operator view prefers SQL Product DB authority when the SQL table exists.
- O030 rebuilt `out/systems/O/live/product_db_operator_view.csv` with 659 rows from SQL authority.
- P014 was added as the local Product DB edit-event applier:
  - dry-run by default
  - requires `--apply --confirm-product-db-edit-apply` for local writes
  - writes local SQL and then exports the local CSV mirror
  - blocks unsafe nonblank ASIN changes
  - blocks duplicate-ASIN creation unless a later classified path is built
- P015 was added as the SQL authority rehearsal proof:
  - SQL rows: 659
  - SQL unique `seller_sku`: 659
  - O view rows: 659
  - CSV mirror rows: 608
  - status: `warn` because the CSV mirror is stale, not because SQL/O disagree

## Repricer Tracker Position

- P013 read-only proof now sees latest terminal run `20260501T185657Z`.
- That latest terminal run is `failed`.
- Terminal publish status is `not_started`.
- Previous runtime proof run `20260501T183549Z` still has:
  - runtime blank `execution_write_status` rows: 0
  - invalid write-status rows: 0
- P016 was added as the repricer tracker UI cutover check.
- P016 currently returns `fail` because latest H terminal state is failed.
- The repricer tracker Sheet must stay temporary/fallback until a later H terminal run finalizes cleanly.

## Stale Pricing Output Position

- `out/pricing_output.csv` is still stale compact audit evidence.
- It is older than the latest runtime source and missing latest runtime run rows.
- Current tracker surfaces should use `out/phase1_runtime_floor_snapshot_latest.csv` plus terminal/publish proof, not stale compact pricing output.
- Do not patch `out/pricing_output.csv` to hide historical blanks.

## Tests Passed Tonight

- Product DB, P014, P015, O030 focused tests: 17 passed.
- Repricer tracker P016/P013/O050 focused tests: 10 passed.
- Earlier Product DB/O/P013 focused profile: 31 passed.
- Windows still prints the known ignored pytest temp cleanup `PermissionError` after successful test exit.

## Tomorrow Checks

- `project_control/DUE_CHECK_REGISTER.csv` has an open H follow-up:
  - `H_REPRICER_TRACKER_LATEST_TERMINAL_RECOVERY`
  - due: `2026-05-02T09:00:00Z`
  - trigger: morning MOT or next completed H terminal run
  - artifact: `out/sql_migration/product_db_contract/repricing_write_status_proof_summary.json`
  - success: terminal finalized, publish ok, runtime blanks 0, invalid write statuses 0

## Next Safe Work

- Continue O/Product DB SQL authority hardening.
- Do not cut over the repricer tracker UI while latest H terminal state is failed.
- Do not run or change H unless explicitly approved.
