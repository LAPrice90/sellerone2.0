# Coding Plan

Date: 2026-05-01
Scope: Phase 2 for SQL Product DB authority and repricer tracker UI cutover.

## 1) Work Check Summary

I checked the current work against code, tests, and proof outputs.

Current proof position:

- Product DB SQL authority is locally proven: P015 reports SQL rows `659`, SQL unique `seller_sku` `659`, and O Product DB operator view rows `659`.
- Product DB edit-event apply is dry-run-first and currently loads SQL authority: P014 dry-run reported `loaded_source_mode=sql`, `product_db_rows=659`, `held_rows=0`, and `sql_alignment.status=ok`.
- Repricer tracker UI read model is built: O050 rebuilt `out/systems/O/live/repricer_tracker_view.csv` with `89` rows.
- Repricer tracker cutover proof is ready with one known warning: P016 reported `ready_with_stale_audit_warning`, `fail_count=0`, `warn_count=1`, latest terminal run `20260501T203514Z`, terminal state `finalized`, publish `ok`, tracker rows `89`.
- The remaining P016 warning is expected: stale compact `out/pricing_output.csv` is audit-only and still has 20 historical blank `execution_write_status` rows.

Verification run during this check:

```txt
python -m py_compile scripts\core\storage\product_db_contract.py scripts\one_off\P014_apply_product_db_edit_events.py scripts\one_off\P015_product_db_sql_authority_rehearsal.py scripts\one_off\P016_repricing_tracker_ui_cutover_check.py scripts\flows\O\O050_build_repricing_tracker_view.py scripts\flows\O\O450_repricing_tracker_ui.py tests\test_p014_apply_product_db_edit_events.py tests\test_p015_product_db_sql_authority_rehearsal.py tests\test_p016_repricing_tracker_ui_cutover_check.py tests\test_o050_repricing_tracker_view.py tests\test_o030_build_product_db_operator_view.py
```

Result: passed.

```txt
python -m pytest tests/test_product_db_sql_contract.py tests/test_p014_apply_product_db_edit_events.py tests/test_p015_product_db_sql_authority_rehearsal.py tests/test_p016_repricing_tracker_ui_cutover_check.py tests/test_o050_repricing_tracker_view.py tests/test_o030_build_product_db_operator_view.py -q
```

Result: `24 passed`. Pytest returned exit code 0, then Windows printed the known ignored temp-folder cleanup `PermissionError`.

Read-only/local proof commands:

```txt
python -m scripts.one_off.P015_product_db_sql_authority_rehearsal --format json
python -m scripts.one_off.P013_repricing_write_status_proof --format json
python -m scripts.flows.O.O050_build_repricing_tracker_view
python -m scripts.one_off.P016_repricing_tracker_ui_cutover_check --format json
python -m scripts.one_off.P014_apply_product_db_edit_events --format json
```

Result: all completed without Google Sheet writes, A runs, B runs, H runs, or scheduler changes.

## 2) Findings

### Good

- The Product DB contract work is no longer just documentation. It now has local SQL table proof, edit-event dry-run proof, schema checks, scanner identity checks, and O view proof.
- The repricer tracker UI is no longer just an idea. It has an O read model, an O UI page, health output, and a cutover proof script.
- The latest H-backed proof has no current blank or invalid `execution_write_status` rows.

### Still Not Done

- SQL Product DB is not yet system-wide authority for every runtime reader.
- Legacy `out/product_db_preview.csv` is stale at `608` rows while SQL and O view are at `659` rows.
- Many older A/B/E/H/F readers can still read the CSV mirror directly.
- PostgreSQL promotion has not happened.
- The repricer tracker Sheet is still the temporary operator fallback until the user explicitly accepts the UI tracker.

### Main Risk

The system can drift if SQL is called the authority but important runtime readers still consume stale CSV mirrors.

## 3) Phase 2 Goal

Make SQL authority operationally safe before wider cutover.

This phase is not a big-bang migration. It is a controlled bridge:

- keep SQL as Product DB authority
- keep UI as the human edit surface
- keep Sheets and CSV as temporary fallback/export surfaces
- prove each reader cutover before changing runtime ownership

## 4) Phase Plan

| Phase | Goal | Allowed files | Required proof | Status |
|---|---|---|---|---|
| 2A | Sync control docs to latest proof | this plan, `project_control/*`, sql-storage plan docs | docs reflect P014/P015/P016 latest evidence | completed |
| 2B | Operator acceptance pack for repricer tracker UI | O UI/read-model files, P016/P017, tests, docs | P017 ready-with-stale-audit-warning, missing critical fields 0, P016 fail 0; Sheet remains fallback until explicit operator acceptance | completed locally |
| 2C | Product DB CSV mirror drift control | O/Product DB proof scripts, mirror-export helpers, tests | P018 reports SQL/O rows 659, unique seller_sku 659, CSV mirror 608 classified as mirror_stale_not_authority | completed locally |
| 2D | Product DB reader dependency migration map | dependency map scripts/docs only | P019 mapped 298 references across 87 files, 0 unknown owners, 58 approval-blocked changes | completed locally |
| 2E | First safe reader cutover | O and P local/read-only readers only | O/P local readers are SQL-first when SQL exists; A/B/H runtime reader changes remain blocked without separate approval | completed locally |
| 2F | PostgreSQL promotion rehearsal | storage/Product DB DDL tests, seed/export/reconcile proof | P020 passed offline; production promotion not run and requires explicit approval | completed locally |

## 5) Boundaries

Allowed without further approval:

- edit plan/control docs
- run local/read-only proof scripts P013/P014/P015/P016
- run O read-model builders
- run focused tests
- build dependency maps

Blocked without explicit approval:

- Google Sheets writes
- A-owned runtime or A015 runs
- B-owned runtime or maintenance proof runs
- H-owned controlled runs or scheduler changes
- production PostgreSQL promotion
- changing Amazon listing/pricing writes

## 6) Proof Gates

Phase 2B repricer UI gate:

- P013 terminal state is `finalized`
- P013 publish status is `ok`
- P013 current runtime blank write-status rows = `0`
- P013 invalid write-status rows = `0`
- O050 health has no `fail`
- P016 fail count = `0`
- user confirms the UI tracker can replace daily Sheet use

Phase 2C Product DB authority gate:

- P014 dry-run loads SQL, not CSV
- P015 SQL rows match O view rows
- `seller_sku` remains unique
- CSV mirror stale status is visible and cannot silently become authority

Phase 2D reader map gate:

- every Product DB reader is listed with owner flow
- each reader is classified as SQL-ready, mirror-only, or needs flow-owned proof
- A/B/H changes are not started from this phase without separate proof planning

## 7) Current Next Action

Start Phase 2B:

- open the O repricer tracker UI and compare it with the current Sheet workflow
- record any missing fields or usability blockers
- keep the current Sheet as temporary fallback until explicit operator acceptance

## 8) One-Pass Completion Plan

This is the recommended path to finish Phase 2B through 2F in one controlled work block.

The goal is not to retire every old runtime reader tonight. The goal is to make SQL/Product DB and the O UI safe enough that wider cutover cannot drift silently.

Global boundaries for the whole pass:

- Do not write Google Sheets.
- Do not run A scripts or A015.
- Do not run B scripts or B maintenance proof.
- Do not run H controlled proof or change scheduler ownership.
- Do not write Amazon pricing/listing data.
- Do not promote to production PostgreSQL.
- Use local/read-only proof and O-owned outputs only.

### Step 0 - Baseline Snapshot

Purpose:
- Confirm the starting point before any code changes.

Commands:

```txt
python -m scripts.one_off.P015_product_db_sql_authority_rehearsal --format json
python -m scripts.one_off.P013_repricing_write_status_proof --format json
python -m scripts.flows.O.O050_build_repricing_tracker_view
python -m scripts.one_off.P016_repricing_tracker_ui_cutover_check --format json
python scripts\tools\due_check_register.py
```

Evidence to record:
- SQL Product DB rows and unique `seller_sku`.
- O Product DB view rows.
- CSV mirror rows and stale/mirror status.
- Latest H terminal run id, terminal state, publish status.
- P016 status, fail count, warning count, tracker rows.
- Due-check register fail rows.

Stop if:
- P015 has any `fail`.
- P016 has any `fail`.
- Product DB SQL rows do not match O Product DB rows.
- Runtime blank or invalid repricer write statuses reappear.

### Phase 2B - Repricer Tracker UI Parity And Acceptance Pack

Purpose:
- Prove the O repricer tracker UI is a usable replacement candidate for the Sheet workflow, while keeping the Sheet as fallback.

Implementation:
- Add a local/read-only parity proof script, proposed name:
  - `scripts/one_off/P017_repricing_tracker_ui_parity_check.py`
- The proof should compare:
  - O050 tracker view fields
  - O450/O400 UI field contract
  - H130 dashboard export fields in `out/analysis_reports/phase1_observation_view_<date>.csv`
  - P013/P016 latest proof status
- It should write:
  - `out/sql_migration/product_db_contract/repricer_tracker_ui_parity_check.csv`
  - `out/sql_migration/product_db_contract/repricer_tracker_ui_parity_summary.json`

Required checks:
- critical tracker fields present:
  - SKU
  - tracker status
  - eligible-to-write flag
  - decision-to-change-price flag
  - write-attempted flag
  - write-applied flag
  - raw execution write status
  - old price
  - new price
  - floor
  - ceiling
  - buy box state
  - strategy state
  - latest terminal run flag
- P016 fail count is `0`.
- O050 health has no `fail`.
- Missing critical field count is `0`.
- Sheet fallback status remains `temporary_fallback_until_explicit_operator_cutover`.

Tests:

```txt
python -m py_compile scripts\one_off\P017_repricing_tracker_ui_parity_check.py tests\test_p017_repricing_tracker_ui_parity_check.py
python -m pytest tests/test_p017_repricing_tracker_ui_parity_check.py tests/test_p016_repricing_tracker_ui_cutover_check.py tests/test_o050_repricing_tracker_view.py -q
```

Proof:

```txt
python -m scripts.one_off.P017_repricing_tracker_ui_parity_check --format json
```

Phase 2B complete when:
- P017 status is `ready` or `ready_with_stale_audit_warning`.
- Missing critical fields = `0`.
- P016 fail count = `0`.
- Any warning is explicitly named and non-blocking.

Important note:
- This phase can make the UI `ready for operator acceptance`.
- It must not retire or disable the Sheet. Retiring the Sheet still needs explicit operator acceptance.

### Phase 2C - Product DB CSV Mirror Drift Control

Purpose:
- Stop stale CSV mirror evidence from silently becoming Product DB authority.

Implementation:
- Add a local/read-only drift-control proof script, proposed name:
  - `scripts/one_off/P018_product_db_mirror_drift_guard.py`
- It should compare:
  - SQL `product_db_products`
  - O030 Product DB operator view
  - `out/product_db_preview.csv`
  - Product DB source health output
- It should write:
  - `out/sql_migration/product_db_contract/product_db_mirror_drift_guard.csv`
  - `out/sql_migration/product_db_contract/product_db_mirror_drift_guard_summary.json`

Required checks:
- SQL rows match O view rows.
- SQL unique `seller_sku` equals SQL rows.
- CSV mirror row count may be stale, but must be classified as `mirror_stale_not_authority`.
- O030 source mode is SQL when SQL table exists.
- P014 edit-event apply source mode is SQL.
- No Product DB proof script treats stale CSV mirror as authority.

Tests:

```txt
python -m py_compile scripts\one_off\P018_product_db_mirror_drift_guard.py tests\test_p018_product_db_mirror_drift_guard.py
python -m pytest tests/test_p018_product_db_mirror_drift_guard.py tests/test_p015_product_db_sql_authority_rehearsal.py tests/test_o030_build_product_db_operator_view.py tests/test_p014_apply_product_db_edit_events.py -q
```

Proof:

```txt
python -m scripts.one_off.P018_product_db_mirror_drift_guard --format json
```

Phase 2C complete when:
- SQL rows = O view rows.
- SQL unique `seller_sku` = SQL rows.
- CSV mirror stale state is visible.
- Any stale CSV mirror warning is classified as non-authority, not hidden.

Stop if:
- Any current O/Product DB reader falls back to CSV while SQL is present.
- SQL rows or unique keys regress.
- CSV mirror is refreshed from any source other than SQL authority.

### Phase 2D - Product DB Reader Dependency Migration Map

Purpose:
- List every Product DB reader before changing runtime consumers.

Implementation:
- Add or extend a local dependency proof, proposed name:
  - `scripts/one_off/P019_product_db_reader_dependency_map.py`
- It should scan code and control files for Product DB reads, including:
  - `product_db_preview.csv`
  - `Product_DB`
  - `product_db_products`
  - Product DB helper imports
  - O030/O420/P014/P015/P018 readers
- It should write:
  - `out/sql_migration/product_db_contract/product_db_reader_dependency_map.csv`
  - `out/sql_migration/product_db_contract/product_db_reader_dependency_summary.json`

Each reader row must include:
- file path
- flow owner: A, B, E, F, H, O, P, shared, unknown
- current source: SQL, CSV mirror, Sheet, mixed, unknown
- proposed source after cutover
- safe proof type: local-only, O-owned, F-owned, E-owned, B-owned, A-owned, H-owned
- blocked without approval flag

Tests:

```txt
python -m py_compile scripts\one_off\P019_product_db_reader_dependency_map.py tests\test_p019_product_db_reader_dependency_map.py
python -m pytest tests/test_p019_product_db_reader_dependency_map.py tests/test_p006_build_csv_dependency_map.py -q
```

Proof:

```txt
python -m scripts.one_off.P019_product_db_reader_dependency_map --format json
```

Phase 2D complete when:
- Every found reader is assigned an owner flow.
- Unknown owner count is `0`, or each unknown is recorded as a blocker in the summary.
- A/B/H runtime readers are mapped but not changed.

### Phase 2E - First Safe Reader Cutover

Purpose:
- Convert only safe, local/O-owned Product DB readers first.
- Do not touch A/B/H runtime consumers in this phase.

Recommended scope:
- O-owned readers first.
- P one-off proof/edit scripts second.
- F/E/A/B/H runtime readers remain mapped only unless separately approved.

Implementation:
- Ensure all O and P Product DB readers use the shared SQL-first Product DB contract helper.
- Add guard tests proving O/P readers do not read stale CSV as authority when SQL exists.
- If any local-only proof still reads CSV first, switch it to SQL-first with CSV fallback only when SQL table is absent.

Allowed files:
- `scripts/core/storage/product_db_contract.py`
- O-owned Product DB scripts
- P014/P015/P018/P019 proof scripts
- targeted tests
- control docs

Tests:

```txt
python -m py_compile scripts\core\storage\product_db_contract.py scripts\flows\O\O030_build_product_db_operator_view.py scripts\one_off\P014_apply_product_db_edit_events.py scripts\one_off\P015_product_db_sql_authority_rehearsal.py scripts\one_off\P018_product_db_mirror_drift_guard.py scripts\one_off\P019_product_db_reader_dependency_map.py
python -m pytest tests/test_product_db_sql_contract.py tests/test_o030_build_product_db_operator_view.py tests/test_p014_apply_product_db_edit_events.py tests/test_p015_product_db_sql_authority_rehearsal.py tests/test_p018_product_db_mirror_drift_guard.py tests/test_p019_product_db_reader_dependency_map.py -q
```

Proof:

```txt
python -m scripts.one_off.P015_product_db_sql_authority_rehearsal --format json
python -m scripts.one_off.P018_product_db_mirror_drift_guard --format json
python -m scripts.one_off.P019_product_db_reader_dependency_map --format json
```

Phase 2E complete when:
- O/P readers are SQL-first when SQL is present.
- Stale CSV is not used as authority by O/P.
- Runtime readers outside O/P are mapped and blocked from unapproved changes.

### Phase 2F - PostgreSQL Promotion Rehearsal

Purpose:
- Prepare production PostgreSQL promotion without connecting to or changing production.

Implementation:
- Add an offline promotion rehearsal, proposed name:
  - `scripts/one_off/P020_product_db_postgres_promotion_rehearsal.py`
- It should validate:
  - PostgreSQL DDL text for `product_db_products`
  - primary key on `seller_sku`
  - non-unique ASIN index
  - export/seed/reconcile plan
  - rollback plan
  - required environment variables are named but not required for offline mode
- It should write:
  - `out/sql_migration/product_db_contract/product_db_postgres_promotion_rehearsal.csv`
  - `out/sql_migration/product_db_contract/product_db_postgres_promotion_rehearsal_summary.json`

Tests:

```txt
python -m py_compile scripts\one_off\P020_product_db_postgres_promotion_rehearsal.py tests\test_p020_product_db_postgres_promotion_rehearsal.py
python -m pytest tests/test_p020_product_db_postgres_promotion_rehearsal.py tests/test_product_db_sql_contract.py -q
```

Proof:

```txt
python -m scripts.one_off.P020_product_db_postgres_promotion_rehearsal --format json
```

Phase 2F complete when:
- Offline DDL check passes.
- Seed/export/reconcile steps are listed.
- Rollback artifacts are listed.
- Summary says production promotion is `not_run_requires_explicit_approval`.

### Final Phase 2 Sign-Off Bundle

Purpose:
- One command gathers the evidence that Phase 2 is complete locally and ready for later operator decisions.

Implementation:
- Add final proof bundle script, proposed name:
  - `scripts/one_off/P021_sql_product_db_ui_authority_phase2_signoff.py`
- It should read the latest P015/P016/P017/P018/P019/P020 summaries and write:
  - `out/sql_migration/product_db_contract/sql_product_db_ui_authority_phase2_signoff.csv`
  - `out/sql_migration/product_db_contract/sql_product_db_ui_authority_phase2_signoff_summary.json`

Final tests:

```txt
python -m py_compile scripts\one_off\P017_repricing_tracker_ui_parity_check.py scripts\one_off\P018_product_db_mirror_drift_guard.py scripts\one_off\P019_product_db_reader_dependency_map.py scripts\one_off\P020_product_db_postgres_promotion_rehearsal.py scripts\one_off\P021_sql_product_db_ui_authority_phase2_signoff.py
python -m pytest tests/test_p017_repricing_tracker_ui_parity_check.py tests/test_p018_product_db_mirror_drift_guard.py tests/test_p019_product_db_reader_dependency_map.py tests/test_p020_product_db_postgres_promotion_rehearsal.py tests/test_p021_sql_product_db_ui_authority_phase2_signoff.py tests/test_p014_apply_product_db_edit_events.py tests/test_p015_product_db_sql_authority_rehearsal.py tests/test_p016_repricing_tracker_ui_cutover_check.py tests/test_o030_build_product_db_operator_view.py tests/test_o050_repricing_tracker_view.py -q
```

Final proof commands:

```txt
python -m scripts.one_off.P017_repricing_tracker_ui_parity_check --format json
python -m scripts.one_off.P018_product_db_mirror_drift_guard --format json
python -m scripts.one_off.P019_product_db_reader_dependency_map --format json
python -m scripts.one_off.P020_product_db_postgres_promotion_rehearsal --format json
python -m scripts.one_off.P021_sql_product_db_ui_authority_phase2_signoff --format json
python scripts\tools\due_check_register.py
```

Phase 2 final status can be `complete locally` only when:
- P017 status is ready or ready with only named stale-audit warning.
- P018 has `fail_count=0`.
- P019 has no unmapped blocking reader, or blockers are listed by owner flow.
- P020 says PostgreSQL promotion is rehearsed offline and not run.
- P021 has `fail_count=0`.
- Due-check register has `fail_rows=0`.

Items that remain after local completion:
- one normal operating day of UI observation before retiring the repricer tracker Sheet
- explicit approval before marking the Product DB Sheet legacy/export-only
- flow-owned proof windows before A/B/H runtime reader changes
- explicit production approval before PostgreSQL promotion

## 9) Execution Completion Report

Observed UTC: 2026-05-01T22:09:01Z

Final local status: `complete_locally_pending_explicit_cutover_approvals`

Completion report:

```txt
plans/active/sql-product-db-ui-authority-phase2-2026-05-01/COMPLETION_REPORT.md
```

Final proof evidence:

- Product DB SQL rows: `659`
- Product DB SQL unique `seller_sku`: `659`
- O Product DB view rows: `659`
- CSV mirror rows: `608`
- CSV mirror status: `mirror_stale_not_authority`
- Repricer tracker rows: `89`
- Repricer tracker status: `ready_with_stale_audit_warning`
- Latest H terminal run: `20260501T215343Z`
- H terminal state: `finalized`
- H publish status: `ok`
- Runtime blank `execution_write_status` rows: `0`
- Runtime invalid `execution_write_status` rows: `0`
- Product DB reader references mapped: `298`
- Product DB reader files mapped: `87`
- Unknown Product DB reader owners: `0`
- Runtime reader changes blocked without explicit approval: `58`
- PostgreSQL promotion status: `not_run_requires_explicit_approval`
- P021 fail count: `0`
- P021 warn count: `0`
- Due-check register fail rows: `0`

Final commands run:

```txt
python -m py_compile scripts\one_off\P017_repricing_tracker_ui_parity_check.py scripts\one_off\P018_product_db_mirror_drift_guard.py scripts\one_off\P019_product_db_reader_dependency_map.py scripts\one_off\P020_product_db_postgres_promotion_rehearsal.py scripts\one_off\P021_sql_product_db_ui_authority_phase2_signoff.py scripts\one_off\P014_apply_product_db_edit_events.py scripts\one_off\P015_product_db_sql_authority_rehearsal.py scripts\one_off\P016_repricing_tracker_ui_cutover_check.py scripts\flows\O\O030_build_product_db_operator_view.py scripts\flows\O\O050_build_repricing_tracker_view.py
python -m pytest tests/test_p017_repricing_tracker_ui_parity_check.py tests/test_p018_product_db_mirror_drift_guard.py tests/test_p019_product_db_reader_dependency_map.py tests/test_p020_product_db_postgres_promotion_rehearsal.py tests/test_p021_sql_product_db_ui_authority_phase2_signoff.py tests/test_p014_apply_product_db_edit_events.py tests/test_p015_product_db_sql_authority_rehearsal.py tests/test_p016_repricing_tracker_ui_cutover_check.py tests/test_o030_build_product_db_operator_view.py tests/test_o050_repricing_tracker_view.py -q
python -m scripts.one_off.P017_repricing_tracker_ui_parity_check --format json
python -m scripts.one_off.P018_product_db_mirror_drift_guard --format json
python -m scripts.one_off.P019_product_db_reader_dependency_map --format json
python -m scripts.one_off.P020_product_db_postgres_promotion_rehearsal --format json
python -m scripts.one_off.P021_sql_product_db_ui_authority_phase2_signoff --format json
python scripts\tools\due_check_register.py
```

Final test result:

- Py compile: passed.
- Focused pytest: `26 passed in 5.84s`.
- Known cleanup note: Windows printed the existing ignored pytest temp-folder cleanup `PermissionError` after test completion; pytest itself exited successfully.

Boundary confirmation:

- No Google Sheets writes were made.
- No A scripts or A015 were run.
- No B scripts or B maintenance proof were run.
- No H controlled proof or scheduler ownership changes were made.
- No Amazon listing/pricing writes were made.
- No production PostgreSQL promotion was run.

Remaining explicit approval gates:

- One normal operating day of repricer tracker UI observation before retiring the repricer tracker Sheet.
- Approval before marking the Product DB Sheet legacy/export-only.
- Flow-owned proof windows before A/B/H runtime reader changes.
- Production approval before PostgreSQL promotion.

## 10) Repricer Tracker UI Observation

Decision recorded: 2026-05-02.

User accepted the recommended path:

- Use the repricer tracker UI as the main tracker for one normal operating day.
- Keep the current Google Sheet as fallback during that observation window.
- Do not retire or disable the Sheet yet.

Observation due check:

- Register row: `H_REPRICER_TRACKER_UI_ONE_DAY_OBSERVATION`
- Due UTC: `2026-05-05T09:00:00Z`
- Trigger: after one normal operating day where the UI is used as the main tracker and the Sheet remains fallback.
- Success condition: P017 and P016 remain fail-free, tracker rows remain nonzero, and no missing UI field or usability blocker is recorded.
- Failure action: keep the Sheet fallback and add the missing field or blocker to the O UI task list before cutover.

## 11) Validation Update - 2026-05-02

Follow-up validation found and fixed two small control issues:

- P020 now names the repo-standard PostgreSQL env var `SELLERONE_DATABASE_URL`.
- P021 now regenerates a fuller completion report with evidence, local proof outputs, boundaries, approvals, and observation decision instead of a thin summary.

Verification commands rerun:

```txt
python -m py_compile scripts\one_off\P017_repricing_tracker_ui_parity_check.py scripts\one_off\P018_product_db_mirror_drift_guard.py scripts\one_off\P019_product_db_reader_dependency_map.py scripts\one_off\P020_product_db_postgres_promotion_rehearsal.py scripts\one_off\P021_sql_product_db_ui_authority_phase2_signoff.py scripts\one_off\P014_apply_product_db_edit_events.py scripts\one_off\P015_product_db_sql_authority_rehearsal.py scripts\one_off\P016_repricing_tracker_ui_cutover_check.py scripts\flows\O\O030_build_product_db_operator_view.py scripts\flows\O\O050_build_repricing_tracker_view.py
python -m pytest tests/test_p017_repricing_tracker_ui_parity_check.py tests/test_p018_product_db_mirror_drift_guard.py tests/test_p019_product_db_reader_dependency_map.py tests/test_p020_product_db_postgres_promotion_rehearsal.py tests/test_p021_sql_product_db_ui_authority_phase2_signoff.py tests/test_p014_apply_product_db_edit_events.py tests/test_p015_product_db_sql_authority_rehearsal.py tests/test_p016_repricing_tracker_ui_cutover_check.py tests/test_o030_build_product_db_operator_view.py tests/test_o050_repricing_tracker_view.py -q
```

Result:

- Py compile passed.
- Focused pytest passed: `26 passed`.
- Known Windows pytest temp cleanup `PermissionError` appeared after success and did not change the test result.

Latest local proof rerun:

- P021 status: `complete_locally_pending_explicit_cutover_approvals`
- P021 fail count: `0`
- P021 warn count: `0`
- Product DB SQL rows: `659`
- O Product DB view rows: `659`
- CSV mirror rows: `608`
- CSV mirror status: `mirror_stale_not_authority`
- P016 status: `ready_with_stale_audit_warning`
- P017 status: `ready_with_stale_audit_warning`
- Latest H terminal run: `20260502T113610Z`
- H terminal state: `finalized`
- H publish status: `ok`
- Runtime blank write-status rows: `0`
- Runtime invalid write-status rows: `0`
- P020 promotion status: `not_run_requires_explicit_approval`

Due-check register position:

- rows: `6`
- due rows: `2`
- warn rows: `2`
- fail rows: `0`
- The two current WARN rows are not Phase 2 blockers:
- `F_AUTH_ATTENTION_VISIBLE_ON_BLOCK`
- `H_STAGED_PUBLISH_RETRY_PATCH_LIVE_PROOF`
- `H_REPRICER_TRACKER_UI_ONE_DAY_OBSERVATION` remains not due until `2026-05-05T09:00:00Z`.
